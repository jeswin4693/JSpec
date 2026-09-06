"""C-06 - the symbol extractor. Reads source as structure, not as text.

Every answer downstream rests on this: what exists, where it is, and what points at
what. Searching text finds matches inside comments and strings, misses everything
indirect, and cannot tell a definition from a mention. A parser knows the difference,
so this parses.

WHAT IT DOES NOT DO, deliberately:

  - It does not decide which `save` a `user.save()` means. That needs the whole
    repository, which is C-07's index, and often types, which nothing here has. Each
    reference is tagged with how much the syntax pinned it down (`Resolution`) and
    the linking is left to the component that can do it honestly.
  - It does not hold state between files. One file in, one `FileSymbols` out, so
    C-07 can re-extract exactly the files whose content hash moved and nothing else.
  - It knows no language. Every node-type name lives in `languages.yaml`; this
    module only knows how to follow a rule table. That is what makes supporting a
    new language a data change (constitution rule 20, D-011).

ERROR RECOVERY. A syntax error does not stop the run, and it does not discard the
file either: tree-sitter builds a tree with ERROR nodes in it, so a file that is
half-broken still yields the half that parsed, flagged with `parse_error`. Reporting
partial truth beats reporting none, as long as it is labelled - which is the same
rule C-08 follows when it reports the depth it reached.
"""

from __future__ import annotations

import fnmatch
import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from jspec.contracts.graph import (
    ROOT_MODULE,
    FileSymbols,
    Reference,
    ReferenceKind,
    Resolution,
    Symbol,
    SymbolKind,
)
from jspec.contracts.profile import Profile

LANGUAGES_FILE = Path(__file__).with_name("languages.yaml")

QUOTE_CHARS = "'" + '"' + chr(96)
"""Quote characters stripped from an imported module path. A grammar hands back the
string node including its delimiters, and the delimiter is not part of the path."""

UNRESOLVED_TARGET = "<computed>"
"""Name recorded when a call names nothing usable at all - the callee is itself the
result of an expression. The edge is kept so the count stays honest; see
`Resolution` in `jspec.contracts.graph`."""


class ExtractError(Exception):
    """Extraction could not start. Names the language or file and the fix."""


# --- the rule table ---------------------------------------------------------------


@dataclass(frozen=True)
class DefinitionRule:
    """One way this language spells a definition."""

    node: str
    kind: SymbolKind
    name_field: str
    value_field: str | None = None
    value_types: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CallRule:
    node: str
    target_field: str


@dataclass(frozen=True)
class ImportRule:
    node: str
    module_field: str
    strip_quotes: bool = False
    alias_node: str | None = None
    alias_name_field: str | None = None


@dataclass(frozen=True)
class LanguageSpec:
    """One language's reading rules, as loaded from `languages.yaml`."""

    name: str
    grammar: str
    extensions: frozenset[str]
    identifier_nodes: frozenset[str]
    member_nodes: frozenset[str]
    member_name_field: str
    definitions: dict[str, tuple[DefinitionRule, ...]]
    calls: dict[str, CallRule]
    imports: dict[str, tuple[ImportRule, ...]]


def _group(rules: list[Any]) -> dict[str, tuple[Any, ...]]:
    """Index rules by the node type they fire on - the walk looks up per node."""
    grouped: dict[str, list[Any]] = {}
    for rule in rules:
        grouped.setdefault(rule.node, []).append(rule)
    return {node: tuple(items) for node, items in grouped.items()}


@lru_cache(maxsize=1)
def load_languages() -> dict[str, LanguageSpec]:
    """Parse `languages.yaml` into rule tables.

    Cached: the file cannot change mid-run, and re-parsing it per file would
    dominate the cost of indexing a small repository.
    """
    raw = yaml.safe_load(LANGUAGES_FILE.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("languages"), dict):
        raise ExtractError(f"{LANGUAGES_FILE} has no top-level 'languages:' mapping")

    specs: dict[str, LanguageSpec] = {}
    for name, body in raw["languages"].items():
        member = body.get("member") or {}
        definitions = [
            DefinitionRule(
                node=d["node"],
                kind=SymbolKind(d["kind"]),
                name_field=d["name_field"],
                value_field=d.get("value_field"),
                value_types=frozenset(d.get("value_types") or ()),
            )
            for d in body.get("definitions") or ()
        ]
        imports = [
            ImportRule(
                node=i["node"],
                module_field=i["module_field"],
                strip_quotes=bool(i.get("strip_quotes")),
                alias_node=i.get("alias_node"),
                alias_name_field=i.get("alias_name_field"),
            )
            for i in body.get("imports") or ()
        ]
        calls = [
            CallRule(node=c["node"], target_field=c["target_field"])
            for c in body.get("calls") or ()
        ]
        specs[name] = LanguageSpec(
            name=name,
            grammar=body["grammar"],
            extensions=frozenset(body.get("extensions") or ()),
            identifier_nodes=frozenset(body.get("identifier_nodes") or ()),
            member_nodes=frozenset(member.get("nodes") or ()),
            member_name_field=member.get("name_field", ""),
            definitions=_group(definitions),
            calls={c.node: c for c in calls},
            imports=_group(imports),
        )
    return specs


def supported() -> tuple[str, ...]:
    """Language ids this build can read, sorted.

    A profile naming anything else is an error carrying this list, not a silent
    empty index - which is the failure mode that looks like "the repo has no code".
    """
    return tuple(sorted(load_languages()))


def spec_for(language: str) -> LanguageSpec:
    """The reading rules for one language, or an error naming what is available."""
    try:
        return load_languages()[language]
    except KeyError:
        raise ExtractError(
            f"no reading rules for language {language!r}; "
            f"supported: {list(supported())}. Add a block to "
            f"{LANGUAGES_FILE.name} - it is data, not code."
        ) from None


@lru_cache(maxsize=16)
def _parser(grammar: str) -> Any:
    """One parser per grammar, reused across files. Building one is not free."""
    try:
        from tree_sitter_language_pack import get_parser
    except ImportError as exc:  # pragma: no cover - depends on install extras
        raise ExtractError(
            "the code graph needs the graph extra: pip install -e 'core[graph]'"
        ) from exc
    try:
        return get_parser(grammar)
    except Exception as exc:
        raise ExtractError(
            f"no grammar named {grammar!r} in the installed language pack: {exc}"
        ) from exc


# --- paths ------------------------------------------------------------------------


def module_of(relative: str) -> str:
    """The top-level sub-folder a file lives in (D-032), or '.' at the root."""
    head, _, tail = relative.partition("/")
    return head if tail else ROOT_MODULE


def is_excluded(relative: str, patterns: tuple[str, ...]) -> bool:
    """Whether a root-relative path is forbidden by any exclusion glob.

    Each pattern is tested against the path, its basename and every ancestor
    directory, so a rule written for a directory also excludes what is inside it and
    a rule written for a file matches at any depth. Erring toward exclusion is
    correct here: skipping a file loses one row, reading a forbidden one is exactly
    what `security.fail_closed` exists to prevent.
    """
    parts = relative.split("/")
    candidates = [relative, parts[-1]]
    candidates += ["/".join(parts[:i]) for i in range(1, len(parts))]
    for pattern in patterns:
        stripped = pattern.rstrip("/")
        for base in {stripped, stripped.split("/**")[0]}:
            if base and any(fnmatch.fnmatch(c, base) for c in candidates):
                return True
    return False


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _language_by_extension(languages: list[str]) -> dict[str, LanguageSpec]:
    """Map file extension to reading rules, for the languages this profile declares.

    First declaration wins, so a profile listing two languages that claim the same
    extension resolves deterministically rather than by dict ordering luck.
    """
    by_extension: dict[str, LanguageSpec] = {}
    for name in languages:
        spec = spec_for(name)
        for extension in spec.extensions:
            by_extension.setdefault(extension, spec)
    return by_extension


def iter_source_files(
    root: Path, profile: Profile, patterns: tuple[str, ...]
) -> list[tuple[Path, LanguageSpec]]:
    """Every file under the profile's directories that one of its languages can read.

    Test directories are walked as well as source directories. A test is a caller
    like any other, and an index that omits them answers "who calls this?" while
    hiding the callers most likely to break first.

    Sorted, so two runs over an unchanged tree produce identical output - which is
    what lets C-07 compare runs at all.
    """
    by_extension = _language_by_extension(profile.languages)
    seen: set[Path] = set()
    found: list[tuple[Path, LanguageSpec]] = []

    for declared in [*profile.source_dirs, *profile.test_dirs]:
        start = (root / declared).resolve()
        if not start.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(start):
            here = Path(dirpath)
            # Prune in place. Walking into a dependency directory and filtering
            # afterwards costs minutes on a real repository.
            dirnames[:] = [
                d
                for d in sorted(dirnames)
                if not is_excluded(_relative(here / d, root), patterns)
            ]
            for filename in sorted(filenames):
                path = here / filename
                spec = by_extension.get(path.suffix)
                if spec is None or path in seen:
                    continue
                if is_excluded(_relative(path, root), patterns):
                    continue
                seen.add(path)
                found.append((path, spec))
    return found


# --- extraction -------------------------------------------------------------------


@dataclass(frozen=True)
class _Enclosing:
    """A definition the walk is currently inside."""

    name: str
    kind: SymbolKind


def _text(node: Any) -> str:
    return node.text.decode("utf-8", errors="replace")


def _definition_match(rule: DefinitionRule, node: Any) -> bool:
    """Whether a node satisfies a rule's optional value constraint.

    A binding to a lambda and a binding to a number are the same node type in most
    grammars; only the first is a definition. Without this check, a modern codebase
    indexes every constant as a function.
    """
    if not rule.value_types:
        return True
    if rule.value_field is None:
        return False
    value = node.child_by_field_name(rule.value_field)
    return value is not None and value.type in rule.value_types


def _call_target(node: Any, rule: CallRule, spec: LanguageSpec) -> tuple[str, Resolution]:
    """The callee name, and how firmly the syntax pins it down."""
    target = node.child_by_field_name(rule.target_field)
    if target is None:
        return UNRESOLVED_TARGET, Resolution.UNRESOLVED
    if target.type in spec.identifier_nodes:
        return _text(target), Resolution.EXACT
    if target.type in spec.member_nodes:
        named = target.child_by_field_name(spec.member_name_field)
        if named is not None:
            return _text(named), Resolution.NAME_ONLY
    # A call through a subscript, a parenthesised expression, or another call. The
    # name recorded is the syntactic form, which is all that is true about it.
    return target.type or UNRESOLVED_TARGET, Resolution.UNRESOLVED


def _import_names(node: Any, rule: ImportRule) -> list[str]:
    """Every module path one import statement names. Repeated fields are normal."""
    names: list[str] = []
    for child in node.children_by_field_name(rule.module_field):
        if rule.alias_node and child.type == rule.alias_node and rule.alias_name_field:
            inner = child.child_by_field_name(rule.alias_name_field)
            if inner is not None:
                child = inner
        text = _text(child)
        if rule.strip_quotes:
            text = text.strip(QUOTE_CHARS)
        if text:
            names.append(text)
    return names


def extract_source(
    source: bytes, *, relative: str, spec: LanguageSpec, module: str | None = None
) -> FileSymbols:
    """Extract one file's symbols and references from its bytes.

    Bytes rather than text because tree-sitter's offsets index the bytes it parsed;
    decoding first and re-encoding invites an off-by-some on any file that is not
    clean UTF-8, and the file that is not clean UTF-8 is the one nobody tests.
    """
    result = FileSymbols(
        file=relative,
        module=module if module is not None else module_of(relative),
        language=spec.name,
    )
    tree = _parser(spec.grammar).parse(source)
    result.parse_error = bool(tree.root_node.has_error)

    def visit(node: Any, enclosing: tuple[_Enclosing, ...]) -> None:
        inner = enclosing
        container = enclosing[-1] if enclosing else None
        in_type = container is not None and container.kind in (
            SymbolKind.CLASS,
            SymbolKind.INTERFACE,
        )

        for rule in spec.definitions.get(node.type, ()):
            if not _definition_match(rule, node):
                continue
            named = node.child_by_field_name(rule.name_field)
            if named is None:
                continue  # an anonymous definition has no name worth indexing
            name = _text(named)
            kind = rule.kind
            # A function written inside a type is a method. Deriving that from the
            # tree rather than from a node type means the rule holds for languages
            # whose grammar has no separate node for it.
            if kind is SymbolKind.FUNCTION and in_type:
                kind = SymbolKind.METHOD
            result.symbols.append(
                Symbol(
                    kind=kind,
                    name=name,
                    file=result.file,
                    module=result.module,
                    line=node.start_point[0] + 1,
                    end_line=node.end_point[0] + 1,
                    parent=container.name if in_type and container else None,
                    language=spec.name,
                )
            )
            inner = enclosing + (_Enclosing(name=name, kind=kind),)
            break

        call_rule = spec.calls.get(node.type)
        if call_rule is not None:
            name, resolution = _call_target(node, call_rule, spec)
            result.references.append(
                Reference(
                    kind=ReferenceKind.CALL,
                    name=name,
                    file=result.file,
                    module=result.module,
                    line=node.start_point[0] + 1,
                    from_symbol=container.name if container else None,
                    resolution=resolution,
                    language=spec.name,
                )
            )

        for import_rule in spec.imports.get(node.type, ()):
            for name in _import_names(node, import_rule):
                result.references.append(
                    Reference(
                        kind=ReferenceKind.IMPORT,
                        name=name,
                        file=result.file,
                        module=result.module,
                        line=node.start_point[0] + 1,
                        from_symbol=container.name if container else None,
                        resolution=Resolution.EXACT,
                        language=spec.name,
                    )
                )

        for child in node.children:
            visit(child, inner)

    visit(tree.root_node, ())
    return result


def extract_file(path: Path, spec: LanguageSpec, root: Path) -> FileSymbols:
    """Extract one file from disk. An unreadable file is reported, never dropped."""
    relative = _relative(path, root)
    try:
        source = path.read_bytes()
    except OSError as exc:
        return FileSymbols(
            file=relative,
            module=module_of(relative),
            language=spec.name,
            error=f"could not read: {exc}",
        )
    try:
        return extract_source(source, relative=relative, spec=spec)
    except Exception as exc:  # noqa: BLE001
        # Deliberately blind. A grammar that crashes on one pathological file must
        # not take the other ten thousand with it, and narrowing this to the
        # exceptions a native parser happens to raise today would be a guess that
        # silently stops holding on the next language pack release. The file is
        # reported with its error, which is the honest outcome.
        return FileSymbols(
            file=relative,
            module=module_of(relative),
            language=spec.name,
            error=f"could not parse: {exc}",
        )


@dataclass
class ExtractReport:
    """One run's totals, plus the rows themselves.

    Counts are kept separate from rows because the first question anyone asks of an
    index is "did it read what I think it read?", and answering that should not mean
    walking tens of thousands of symbols.
    """

    root: str
    profile: str
    files: list[FileSymbols] = field(default_factory=list)

    @property
    def symbols(self) -> list[Symbol]:
        return [s for f in self.files for s in f.symbols]

    @property
    def references(self) -> list[Reference]:
        return [r for f in self.files for r in f.references]

    def to_dict(self) -> dict[str, Any]:
        """The run summary. What `jspec extract` prints.

        `by_resolution` is here rather than buried in the rows because it is the
        honest headline: it says what share of the edges the syntax actually pinned
        down, so nobody reads a call graph as more certain than it is.
        """
        failed = [f for f in self.files if f.error]
        partial = [f for f in self.files if f.parse_error and not f.error]
        by_resolution = {r.value: 0 for r in Resolution}
        for reference in self.references:
            by_resolution[reference.resolution.value] += 1
        return {
            "root": self.root,
            "profile": self.profile,
            "files_scanned": len(self.files),
            "files_unreadable": len(failed),
            "files_with_syntax_errors": len(partial),
            "symbols": len(self.symbols),
            "references": len(self.references),
            "by_kind": {
                kind.value: sum(1 for s in self.symbols if s.kind is kind)
                for kind in SymbolKind
            },
            "by_resolution": by_resolution,
            "modules": sorted({f.module for f in self.files}),
            "unreadable": [{"file": f.file, "error": f.error} for f in failed],
            "syntax_errors": [f.file for f in partial],
        }


def extract_tree(
    root: Path, profile: Profile, patterns: tuple[str, ...] | None = None
) -> ExtractReport:
    """Extract every readable file under one root, per the profile's languages.

    `patterns` defaults to the exclusion rules in `.sdd/config.yaml`. It is a
    parameter so that a caller analysing an unusual tree can widen or narrow them
    without inventing a second config file, and so tests do not silently depend on
    the shipped one.
    """
    if patterns is None:
        from jspec.config import exclude_patterns

        patterns = exclude_patterns()

    unknown = [lang for lang in profile.languages if lang not in load_languages()]
    if unknown:
        raise ExtractError(
            f"profile {profile.name!r} names unsupported languages {unknown}; "
            f"supported: {list(supported())}"
        )

    report = ExtractReport(root=root.resolve().as_posix(), profile=profile.name)
    for path, spec in iter_source_files(root, profile, patterns):
        report.files.append(extract_file(path, spec, root))
    return report


__all__ = [
    "CallRule",
    "DefinitionRule",
    "ExtractError",
    "ExtractReport",
    "ImportRule",
    "LanguageSpec",
    "extract_file",
    "extract_source",
    "extract_tree",
    "is_excluded",
    "iter_source_files",
    "load_languages",
    "module_of",
    "spec_for",
    "supported",
]
