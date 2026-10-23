"""C-26 project profiler: point it at a repository it has never seen.

Nobody writes a config file for a tool that has not yet proved itself, so JSpec has to
be useful *before* it is configured. This reads a repository and drafts the profile
(C-25) a person would otherwise have had to write by hand.

THE HARD PART IS NOT DETECTION, IT IS HONESTY
"Tests are in `tests/`" read out of a config file is a different claim from "shared
code is probably `utils/`" guessed from a folder name. A draft that hides which is
which is worse than no draft: the reader skims it once and trusts every line equally.
So every field is a `Finding` that says how it was reached - `found` (read as written),
`inferred` (a convention applied to real evidence), `guessed` (a name and nothing else),
`confirmed` (a person said so) or `unknown` (left empty on purpose) - and carries the
evidence. A value with no evidence is not admissible (rule 15), and a field nobody knows
stays empty rather than being filled with something plausible.

DETECTION ORDER, CHEAPEST AND SUREST FIRST
1. Manifests and config files: declared dependencies, scripts, config tables. A command
   the project wrote down is `found`; one we would assume from a config's existence is
   `inferred`.
2. Layout from what is on disk: which folders hold source files, which hold files that
   match test-file patterns. A census of *names*, never of contents.
3. Folder names alone, last, and only ever as `guessed`.
Optionally a fourth, from the symbol index (C-07) when one exists: which folder do the
most other folders import. It is reported as an observation, not a field - the profile
has nowhere to put it until a component reads it (D-030).

WHERE THE KNOWLEDGE LIVES
Every language, ecosystem and command named in a rule is in `profiler_rules.yaml`, the
same split as `graph/languages.yaml` (D-033). This module reads rule tables; adding a
kind of project is a data change.

A CORRECTION IS NEVER ASKED FOR TWICE
A value set with `--set` is `confirmed`, and detection never overwrites a confirmed
field - not on the next draft, and not when the profile is later re-drafted. Fields
already accepted into `profiles/<name>.yaml` are loaded as confirmed for the same
reason. This is the whole of "persist the answer" (rule 7): the profile file *is* the
stored preference.

WHAT IT READS
File and folder *names* across the tree (never contents), plus the contents of three
manifest formats at the repository root. Nothing nested is read, and the tree walk
refuses everything in `.sdd/config.yaml`'s exclusion lists. It writes nothing into the
repository: drafts live in JSpec's own `.sdd/drafts/`, as the index does (D-037).
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import tomllib
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from jspec.config import exclude_patterns
from jspec.contracts.profile import (
    LIST_FIELDS,
    OPTIONAL_FIELDS,
    REQUIRED_FIELDS,
    Basis,
    Finding,
    Profile,
    ProfileDraft,
)
from jspec.graph.extract import is_excluded, load_languages
from jspec.paths import RootNotFound, find_up
from jspec.profiles import PROFILE_SUFFIX
from jspec.profiles import load as load_profile

RULES_FILE = Path(__file__).with_name("profiler_rules.yaml")
DRAFT_SUFFIX = ".yaml"

_PROVENANCE_WIDTH = 64
"""Evidence is clipped in the header of an accepted profile; the full text stays in the
draft. A header line that wraps is a header nobody reads."""


class ProfilerError(Exception):
    """The profiler could not run, or a draft could not be used. Names the fix."""


# --- the rule tables ---------------------------------------------------------------


@lru_cache(maxsize=1)
def load_rules() -> dict[str, Any]:
    """Parse `profiler_rules.yaml`. Cached: it cannot change mid-run."""
    raw = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    needed = (
        "manifests",
        "runners",
        "default_runner",
        "placeholder_scripts",
        "languages",
        "checks",
        "layout",
    )
    if not isinstance(raw, dict) or [k for k in needed if k not in raw]:
        missing = (
            needed if not isinstance(raw, dict) else [k for k in needed if k not in raw]
        )
        raise ProfilerError(f"{RULES_FILE} is missing sections {list(missing)}")
    return raw


# --- facts read from manifests -----------------------------------------------------


def _norm(name: str) -> str:
    """`Foo_Bar` and `foo-bar` are one dependency to every package index."""
    return re.sub(r"[-_.]+", "-", name.strip().lower())


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _dig(node: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


@dataclass
class Facts:
    """What the repository's own manifests say. Read once, held as plain data."""

    names: list[str]
    project: dict[str, Any] = field(default_factory=dict)
    package: dict[str, Any] = field(default_factory=dict)
    deps: dict[str, str] = field(default_factory=dict)
    scripts: dict[str, str] = field(default_factory=dict)
    runner: str = ""
    runner_evidence: str | None = None
    notes: list[str] = field(default_factory=list)
    manifest_names: dict[str, str] = field(default_factory=dict)


def gather_facts(root: Path, patterns: tuple[str, ...], rules: dict[str, Any]) -> Facts:
    """Read the root's manifests. A manifest that cannot be read is a note, not a crash:
    half a draft with an honest gap beats no draft."""
    manifests = rules["manifests"]
    names = sorted(n for n in os.listdir(root) if not is_excluded(n, patterns))
    facts = Facts(names=names, manifest_names=dict(manifests))

    def read(name: str) -> str | None:
        try:
            return (root / name).read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            facts.notes.append(f"could not read {name}: {exc}")
            return None

    def add(dep: str, source: str) -> None:
        if dep:
            facts.deps.setdefault(_norm(dep), source)

    package_name = manifests["package_json"]
    if package_name in names and (text := read(package_name)) is not None:
        try:
            facts.package = _dict(json.loads(text))
        except json.JSONDecodeError as exc:
            facts.notes.append(f"{package_name} is not valid JSON ({exc.msg}): ignored")
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            for dep in _dict(facts.package.get(key)):
                add(dep, package_name)
        placeholders = rules["placeholder_scripts"]
        for key, value in _dict(facts.package.get("scripts")).items():
            if isinstance(value, str) and not any(p in value for p in placeholders):
                facts.scripts[key] = value

    project_name = manifests["project_toml"]
    if project_name in names and (text := read(project_name)) is not None:
        try:
            facts.project = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            facts.notes.append(f"{project_name} is not valid TOML ({exc}): ignored")
        table = _dict(facts.project.get("project"))
        specs = _list(table.get("dependencies"))
        for group in _dict(table.get("optional-dependencies")).values():
            specs += _list(group)
        for group in _dict(facts.project.get("dependency-groups")).values():
            specs += _list(group)
        for spec in specs:
            match = (
                re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", spec)
                if isinstance(spec, str)
                else None
            )
            add(match.group(0) if match else "", project_name)

    for name in fnmatch.filter(names, manifests["requirement_lists"]):
        for line in (read(name) or "").splitlines():
            match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)", line)
            if match and not line.lstrip().startswith("#"):
                add(match.group(1), name)

    for rule in rules["runners"]:
        if rule["file"] in names:
            facts.runner, facts.runner_evidence = rule["run"], f"{rule['file']} exists"
            break
    else:
        facts.runner = rules["default_runner"]

    # A manifest in a sub-folder is invisible here, and saying so is the difference
    # between "no linter configured" and "a linter we did not look for".
    nested = (manifests["package_json"], manifests["project_toml"])
    for name in names:
        if name.startswith(".") or not (root / name).is_dir():
            continue
        try:
            inside = set(os.listdir(root / name))
        except OSError:
            continue
        if hits := [m for m in nested if m in inside]:
            facts.notes.append(
                f"{name}/{hits[0]} exists but only the repository root's manifests are "
                f"read; commands declared there are not in this draft"
            )
    return facts


# --- the rule language -------------------------------------------------------------


def _holds(cond: dict[str, Any], facts: Facts) -> str | None:
    """The evidence that satisfies a condition, or None. A condition no rule table may
    use is an error: a typo in the data must not read as 'nothing matched'."""
    if "any" in cond:
        for inner in cond["any"]:
            if (evidence := _holds(inner, facts)) is not None:
                return evidence
        return None
    if "file" in cond:
        hits = fnmatch.filter(facts.names, cond["file"])
        return f"{hits[0]} exists" if hits else None
    if "toml" in cond:
        found = _dig(facts.project, cond["toml"]) is not None
        name = facts.manifest_names["project_toml"]
        return f"{name} has [{cond['toml']}]" if found else None
    if "dep" in cond:
        source = facts.deps.get(_norm(cond["dep"]))
        return f"dependency {cond['dep']!r} declared in {source}" if source else None
    if "script" in cond:
        value = facts.scripts.get(cond["script"])
        name = facts.manifest_names["package_json"]
        return f"{name} scripts.{cond['script']} = {value!r}" if value else None
    raise ProfilerError(f"unknown condition {cond!r} in {RULES_FILE.name}")


# --- a census of names -------------------------------------------------------------


@dataclass
class Census:
    """Every recognised source file by relative path, with its language. Names only."""

    files: list[tuple[str, str]] = field(default_factory=list)

    @property
    def by_language(self) -> Counter[str]:
        return Counter(language for _, language in self.files)


def _extension_map(rules: dict[str, Any]) -> dict[str, str]:
    """Extension -> language. Readable languages come from `graph/languages.yaml`, the
    one authority; the rules add only languages JSpec cannot read yet."""
    mapping: dict[str, str] = {}
    for spec in load_languages().values():
        for extension in sorted(spec.extensions):
            mapping.setdefault(extension.lower(), spec.name)
    for known in rules["languages"]["known"]:
        for extension in known.get("extensions", ()):
            mapping.setdefault(extension.lower(), known["id"])
    return mapping


def take_census(root: Path, patterns: tuple[str, ...], rules: dict[str, Any]) -> Census:
    extensions = _extension_map(rules)
    census = Census()
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        # Hidden folders hold tooling, not source, and pruning in place keeps the walk
        # out of dependency trees instead of filtering their contents afterwards.
        dirnames[:] = sorted(
            d
            for d in dirnames
            if not d.startswith(".") and not _excluded(here / d, root, patterns)
        )
        for filename in sorted(filenames):
            language = extensions.get(Path(filename).suffix.lower())
            if language and not _excluded(here / filename, root, patterns):
                census.files.append((_rel(here / filename, root), language))
    return census


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _excluded(path: Path, root: Path, patterns: tuple[str, ...]) -> bool:
    return is_excluded(_rel(path, root), patterns)


# --- the findings ------------------------------------------------------------------


def _finding(
    field_name: str,
    value: Any,
    basis: Basis,
    evidence: list[str],
    note: str | None = None,
) -> Finding:
    return Finding(
        field=field_name, value=value, basis=basis, evidence=evidence, note=note
    )


def _unknown(field_name: str, note: str) -> Finding:
    return Finding(field=field_name, value=None, basis=Basis.UNKNOWN, note=note)


def _languages(
    census: Census, facts: Facts, rules: dict[str, Any], seen: list[str]
) -> Finding:
    cfg = rules["languages"]
    known = {k["id"]: k for k in rules["languages"]["known"]}
    readable = set(load_languages())
    counts = census.by_language
    total = sum(counts.values())
    chosen: list[str] = []
    evidence: list[str] = []
    weak = False

    for language, count in counts.most_common():
        share = count / total
        if share < cfg["min_share"] and count < cfg["min_files"]:
            seen.append(
                f"also saw {count} {language} file(s) ({share:.0%}); left out of languages - "
                f"add it with --set languages=... if it matters"
            )
            continue
        if language not in readable:
            seen.append(
                f"{language}: {count} files detected, but JSpec has no reading rules for it "
                f"(graph/languages.yaml), so it cannot be indexed yet"
            )
            continue
        rule = known.get(language, {})
        manifest = (
            _holds(rule["evidence"], facts)
            if isinstance(rule.get("evidence"), dict)
            else None
        )
        evidence.append(
            f"{count} {language} files ({share:.0%} of source files)"
            + (f"; {manifest}" if manifest else "")
        )
        weak = weak or manifest is None
        chosen.append(language)

    if not chosen:
        reason = (
            "no source files of a language JSpec can read were found"
            if total == 0
            else "the languages found cannot be read yet (see observations)"
        )
        return _unknown("languages", reason)
    return _finding(
        "languages", chosen, Basis.INFERRED if weak else Basis.FOUND, evidence
    )


def _check(name: str, facts: Facts, rules: dict[str, Any]) -> Finding:
    field_name = f"validation.{name}"
    for candidate in rules["checks"].get(name, ()):
        evidence = _holds(candidate["when"], facts)
        if evidence is None:
            continue
        basis = Basis(candidate["basis"])
        command: str = candidate["command"]
        proof = [evidence]
        note = None
        if "{runner}" in command:
            command = command.replace("{runner}", facts.runner)
            if facts.runner_evidence:
                proof.append(f"{facts.runner_evidence}, so the runner is {facts.runner}")
            else:
                # The script was read, but the program that runs it was not.
                basis = Basis.INFERRED
                proof.append(f"no lockfile found; assuming {facts.runner}")
                note = "check the package manager"
        return _finding(field_name, command, basis, proof, note)
    return _unknown(
        field_name, f"no evidence of a {name} command in the repository's manifests"
    )


def _top(rel: str, descend: list[str]) -> str:
    """The folder a file is filed under: its top-level folder, or the conventional
    container just below it (`core/src/`), or `.` at the root."""
    parts = rel.split("/")
    if len(parts) == 1:
        return "."
    if len(parts) > 2 and parts[1] in descend and parts[0] not in descend:
        return f"{parts[0]}/{parts[1]}/"
    return f"{parts[0]}/"


def _declared_test_dirs(
    root: Path, facts: Facts, rules: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """Test folders a config file names outright, with where it said so."""
    for rule in rules["layout"]["declared_test_dirs"]:
        raw: list[str] = []
        where = ""
        if "toml" in rule:
            value = _dig(facts.project, rule["toml"])
            raw = (
                [value]
                if isinstance(value, str)
                else [v for v in _list(value) if isinstance(v, str)]
            )
            where = f"{facts.manifest_names['project_toml']} [{rule['toml']}]"
        elif "file" in rule:
            hits = fnmatch.filter(facts.names, rule["file"])
            if hits:
                try:
                    text = (root / hits[0]).read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                match = re.search(rule["regex"], text)
                if match:
                    raw = [p for p in re.split(r"[\s,]+", match.group(1).strip()) if p]
                    where = hits[0]
        dirs = [_dir(p) for p in raw if _dir(p)]
        if dirs:
            return dirs, [f"{where} says {dirs}"]
    return [], []


def _dir(raw: str) -> str:
    cleaned = raw.strip().strip("'\"").removeprefix("./").strip("/")
    return f"{cleaned}/" if cleaned else ""


def _layout(
    root: Path,
    census: Census,
    facts: Facts,
    rules: dict[str, Any],
    languages: list[str],
    seen: list[str],
) -> tuple[Finding, Finding]:
    layout = rules["layout"]
    files = [rel for rel, language in census.files if language in languages]
    by_dir: dict[str, list[str]] = {}
    for rel in files:
        by_dir.setdefault(_top(rel, layout["descend_into"]), []).append(rel)

    def is_test_file(rel: str) -> bool:
        return any(
            fnmatch.fnmatch(rel.rsplit("/", 1)[-1], p)
            for p in layout["test_file_patterns"]
        )

    def leaf(directory: str) -> str:
        return directory.rstrip("/").rpartition("/")[2]

    dedicated: dict[str, tuple[Basis, str]] = {}
    for directory, members in sorted(by_dir.items()):
        tests = sum(is_test_file(m) for m in members)
        named = leaf(directory) in layout["test_dir_names"]
        # Strictly more than half: a library with one test file per module is exactly half
        # tests and is not a test folder - its tests live beside the code.
        if tests and (tests / len(members) > 0.5 or named):
            reason = (
                f"{directory}: {tests} of {len(members)} files match test-file patterns"
            )
            dedicated[directory] = (
                Basis.INFERRED,
                reason + (", and the name says tests" if named else ""),
            )
        elif named:
            reason = f"{directory}: named like a test folder, but no file in it matches a test pattern"
            dedicated[directory] = (Basis.GUESSED, reason)

    # -- test_dirs
    declared, declared_evidence = _declared_test_dirs(root, facts, rules)
    declared = [d for d in declared if (root / d).is_dir()]
    if declared:
        test_dirs = _finding("test_dirs", declared, Basis.FOUND, declared_evidence)
        extra = sorted(set(dedicated) - set(declared))
        if extra:
            seen.append(
                f"test files also live in {extra}; the config names only {declared}"
            )
    elif dedicated:
        weakest = (
            Basis.GUESSED
            if any(b is Basis.GUESSED for b, _ in dedicated.values())
            else Basis.INFERRED
        )
        test_dirs = _finding(
            "test_dirs", sorted(dedicated), weakest, [r for _, r in dedicated.values()]
        )
    else:
        count = sum(is_test_file(rel) for rel in files)
        what = (
            f"{count} test file(s), all beside the code and none in a dedicated folder"
            if count
            else f"no file matches a test pattern among {len(files)} source files"
        )
        test_dirs = _finding(
            "test_dirs",
            [],
            Basis.INFERRED,
            [what],
            "none - tests live beside sources" if count else "no tests found",
        )

    # -- source_dirs
    candidates = [d for d in by_dir if d not in dedicated]
    real = [
        d
        for d in candidates
        if d != "." and d.split("/")[0] not in layout["non_source_dir_names"]
    ]
    for d in candidates:
        if d not in real and d != ".":
            seen.append(
                f"{d} holds {len(by_dir[d])} source file(s) but is named like non-source "
                f"({d.split('/')[0]}); left out of source_dirs"
            )
    # `core/` and `core/src/` both appear when a container sits beside other folders
    # (`core/scripts/`). The inner one is the source root; the outer is what is left
    # around it, and listing both would say the same files twice.
    outer = [d for d in real if any(o != d and o.startswith(d) for o in real)]
    for d in outer:
        seen.append(
            f"{d} also holds {len(by_dir[d])} source file(s) outside "
            f"{sorted(o for o in real if o != d and o.startswith(d))}; left out of source_dirs"
        )
    real = [d for d in real if d not in outer]
    if real:
        chosen, why = real, [f"{d}: {len(by_dir[d])} source files" for d in sorted(real)]
        if "." in by_dir:
            seen.append(
                f"{len(by_dir['.'])} source file(s) sit at the repository root; left out"
            )
    elif "." in candidates:
        chosen, why = (
            ["."],
            [f".: {len(by_dir['.'])} source files, all at the repository root"],
        )
    elif dedicated:
        chosen = sorted(dedicated)
        why = [
            f"{d}: the only source there is, and it is tests - the suite is the code"
            for d in chosen
        ]
    else:
        return _unknown("source_dirs", "no source files were found to place"), test_dirs
    return _finding("source_dirs", sorted(chosen), Basis.INFERRED, sorted(why)), test_dirs


def _shared_candidates(store: Any) -> list[str]:
    """Which folders the most other folders import, from the symbol index (C-07).

    A fact about the repository that no `Profile` field can hold yet, so it is an
    observation. Counted as distinct importing *files outside the folder*: a folder
    imported only by itself is not shared, and an importer counted once per file it
    pulls in would reward a folder for being split into many small files."""
    from jspec.graph.traverse import imported_by

    modules = {row["path"]: row["module"] for row in store.files()}
    pairs = {
        (importer, modules[target])
        for target, importers in imported_by(store).items()
        if target in modules
        for importer in importers
        if modules.get(importer) != modules[target]
    }
    ranked = Counter(module for _, module in pairs).most_common(3)
    if not ranked:
        return ["no folder is imported from another folder in the index"]
    shown = ", ".join(f"{m} ({n} files)" for m, n in ranked)
    return [f"most imported by files in other folders (candidate shared code): {shown}"]


# --- assembling a draft ------------------------------------------------------------


def slug(folder: str) -> str:
    """A folder name as a valid profile id (3-16 characters)."""
    cleaned = re.sub(r"[^a-z0-9]+", "-", folder.lower()).strip("-")[:16].strip("-")
    if len(cleaned) < 3:
        cleaned = f"{cleaned}-repo".strip("-")
    return cleaned[:16].strip("-") or "repo-profile"


def parse_correction(field_name: str, raw: str) -> str | list[str] | None:
    """A `--set field=value` as a value. Lists are comma-separated; empty clears an
    optional field and is refused for a required one."""
    if field_name not in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS):
        known = [*REQUIRED_FIELDS, *OPTIONAL_FIELDS]
        raise ProfilerError(f"cannot set {field_name!r}; the fields are {known}")
    value = raw.strip()
    if field_name in LIST_FIELDS:
        items = [part.strip() for part in value.split(",") if part.strip()]
        if not items and field_name in REQUIRED_FIELDS:
            raise ProfilerError(f"{field_name} is required and cannot be blank")
        return items
    if not value:
        if field_name in REQUIRED_FIELDS:
            raise ProfilerError(f"{field_name} is required and cannot be blank")
        return None
    return value


def _confirmed(field_name: str, value: str | list[str] | None, source: str) -> Finding:
    """A value a person owns. A confirmed `None` means "there is none" - said, not
    unknown - which is why it is a different basis from `unknown`: that would ask again."""
    return Finding(
        field=field_name, value=value, basis=Basis.CONFIRMED, evidence=[source]
    )


def _from_profile(profile: Profile, where: str) -> dict[str, Finding]:
    values: dict[str, str | list[str] | None] = {
        "name": profile.name,
        "description": profile.description,
        "languages": profile.languages,
        "source_dirs": profile.source_dirs,
        "test_dirs": profile.test_dirs,
        "validation.test": profile.validation.test,
        "validation.lint": profile.validation.lint,
        "validation.format": profile.validation.format,
        "validation.typecheck": profile.validation.typecheck,
    }
    return {
        f: _confirmed(f, v, f"accepted earlier in {where}") for f, v in values.items()
    }


def profile_repo(
    root: Path,
    *,
    name: str | None = None,
    corrections: dict[str, str] | None = None,
    previous: ProfileDraft | None = None,
    accepted: Profile | None = None,
    index: Any = None,
    patterns: tuple[str, ...] | None = None,
) -> ProfileDraft:
    """Draft a profile for the repository at `root`.

    Layers, weakest first, so a person always outranks a detector: what was detected,
    then a profile accepted earlier, then confirmed fields of the previous draft, then
    this call's `corrections`. Nothing about the repository is written to.
    """
    root = Path(root)
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")
    rules = load_rules()
    patterns = exclude_patterns() if patterns is None else patterns

    facts = gather_facts(root, patterns, rules)
    census = take_census(root, patterns, rules)
    observations = list(facts.notes)

    languages = _languages(census, facts, rules, observations)
    chosen = [v for v in (languages.value or []) if isinstance(v, str)]
    source_dirs, test_dirs = _layout(root, census, facts, rules, chosen, observations)

    folder = root.resolve().name
    detected: dict[str, Finding] = {
        "name": _finding(
            "name",
            name or slug(folder),
            Basis.CONFIRMED if name else Basis.INFERRED,
            ["--name was given"]
            if name
            else [f"derived from the folder name {folder!r}"],
        ),
        "description": _finding(
            "description",
            f"{', '.join(chosen)} project {folder!r}, profiled by JSpec"
            if chosen
            else f"Project {folder!r}, profiled by JSpec (language not detected)",
            Basis.INFERRED,
            ["generated from the folder name and the detected languages"],
            "edit this to say what the project is",
        ),
        "languages": languages,
        "source_dirs": source_dirs,
        "test_dirs": test_dirs,
    }
    for check in ("test", "lint", "format", "typecheck"):
        detected[f"validation.{check}"] = _check(check, facts, rules)

    layers: list[dict[str, Finding]] = [detected]
    if accepted is not None:
        layers.append(
            _from_profile(accepted, f"profiles/{accepted.name}{PROFILE_SUFFIX}")
        )
    if previous is not None:
        layers.append(
            {f.field: f for f in previous.findings if f.basis is Basis.CONFIRMED}
        )
    if corrections:
        layers.append(
            {
                f: _confirmed(
                    f, parse_correction(f, raw), f"set by a person: --set {f}=..."
                )
                for f, raw in corrections.items()
            }
        )
    merged: dict[str, Finding] = {}
    for layer in layers:
        merged.update(layer)

    if index is not None:
        observations.extend(_shared_candidates(index))

    order = [*REQUIRED_FIELDS, *OPTIONAL_FIELDS]
    return ProfileDraft(
        root=root.resolve().as_posix(),
        findings=[merged[f] for f in order],
        observations=observations,
    )


# --- saving, loading and accepting -------------------------------------------------


def drafts_dir(jspec_root: Path | None = None) -> Path:
    """`.sdd/drafts/` of JSpec itself - never inside the repository being profiled."""
    try:
        return find_up(".sdd", jspec_root) / "drafts"
    except RootNotFound as exc:
        raise ProfilerError(str(exc)) from exc


def save_draft(draft: ProfileDraft, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{draft.name}{DRAFT_SUFFIX}"
    header = (
        "# A drafted profile, field by field, before anyone has agreed to it.\n"
        "# Correct a value and set its `basis` to `confirmed`, or use\n"
        "#   jspec profile draft <root> --set field=value\n"
        "# Then:  jspec profile accept " + draft.name + "\n"
    )
    body = yaml.safe_dump(
        draft.model_dump(mode="json"), sort_keys=False, allow_unicode=True
    )
    path.write_text(header + body, encoding="utf-8")
    return path


def load_draft(name: str, directory: Path) -> ProfileDraft | None:
    """The saved draft for `name`, or None. A damaged one is an error naming the file -
    silently starting over would discard the corrections a person already made."""
    path = directory / f"{name}{DRAFT_SUFFIX}"
    if not path.is_file():
        return None
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return ProfileDraft.model_validate(raw)
    except (yaml.YAMLError, ValidationError) as exc:
        raise ProfilerError(f"{path} is not a valid draft: {exc}") from exc


def attention(draft: ProfileDraft) -> list[dict[str, str]]:
    """What a person should look at: every guess, and every field that is empty."""
    items = []
    for f in draft.findings:
        if f.basis in (Basis.GUESSED, Basis.UNKNOWN):
            why = f.note or (f.evidence[0] if f.evidence else "no evidence")
            items.append({"field": f.field, "basis": f.basis.value, "why": why})
    return items


def accept(
    draft: ProfileDraft,
    *,
    profiles_directory: Path,
    drafts_directory: Path,
    accept_guesses: bool = False,
    overwrite: bool = False,
) -> dict[str, Any]:
    """Turn a draft into `profiles/<name>.yaml`, or say exactly what is in the way.

    Two things block it: a required field nobody knows (there is no valid profile to
    write), and a guess nobody has confirmed. A guess may be accepted as it stands, but
    only by saying so - `accept_guesses` - because "I read the draft" and "I agreed to
    every line" are different statements and this is where they get separated.
    """
    blockers: list[str] = []
    unknown = draft.unknown_required()
    if unknown:
        blockers.append(f"unknown required fields {unknown}: set them with --set")
    guessed = draft.guessed()
    if guessed and not accept_guesses:
        blockers.append(
            f"guessed fields {guessed}: confirm each with --set, or pass --accept-guesses"
        )
    path = profiles_directory / f"{draft.name}{PROFILE_SUFFIX}"
    if path.exists() and not overwrite:
        blockers.append(f"{path} already exists; pass --overwrite to replace it")
    try:
        profile = draft.to_profile() if not unknown else None
    except ValueError as exc:
        blockers.append(str(exc))
        profile = None
    if blockers or profile is None:
        return {"accepted": False, "name": draft.name, "blockers": blockers}

    provenance = "\n".join(
        f"#   {f.field:<22}{f.basis.value:<10}"
        f"{(f.evidence[0] if f.evidence else '-')[:_PROVENANCE_WIDTH]}"
        for f in draft.findings
    )
    text = (
        f"# Drafted by `jspec profile draft` from the folder {Path(draft.root).name!r}.\n"
        f"# How each field was reached (the full evidence is in .sdd/drafts/):\n"
        f"{provenance}\n"
        f"# From here on this is your file: edit it freely.\n\n"
        + yaml.safe_dump(
            profile.model_dump(mode="json", exclude_none=True), sort_keys=False
        )
    )
    profiles_directory.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    try:
        load_profile(draft.name, profiles_directory)
    except Exception:
        # What was written must load, or it is worse than nothing. Remove it rather
        # than leave a profile that fails later, in someone else's session.
        path.unlink(missing_ok=True)
        raise

    # Accepting a guess is confirming it. Record that, or the next draft asks again.
    settled = [
        f.model_copy(
            update={
                "basis": Basis.CONFIRMED,
                "evidence": [*f.evidence, "accepted as it stood"],
            }
        )
        if f.basis is Basis.GUESSED
        else f
        for f in draft.findings
    ]
    save_draft(draft.model_copy(update={"findings": settled}), drafts_directory)
    return {"accepted": True, "name": draft.name, "path": path.as_posix(), "blockers": []}


__all__ = [
    "ProfilerError",
    "accept",
    "attention",
    "drafts_dir",
    "load_draft",
    "load_rules",
    "parse_correction",
    "profile_repo",
    "save_draft",
    "slug",
]
