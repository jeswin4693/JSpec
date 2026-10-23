"""`jspec` - the command line a skill calls to get a fact.

This is the bridge (C-05). Claude Code supplies judgement; this supplies the things
judgement should never be paid to do - classification, chain selection, schema
validation. D-025 settled the shape: a plain command invoked via Bash, not an MCP
server. MCP wraps the tools that prove useful after M2.

`core/pyproject.toml` has declared the entry point `jspec = "jspec.cli:main"` since
the first commit; this module is what it was pointing at.

Every command prints JSON to stdout, including `tools`. The primary reader is a
model, and one predictable output shape beats a prettier one per command - a skill
that has to parse two formats will eventually parse one of them wrong.

Exit codes are the fast signal, so a caller need not parse to know what happened:

    0  the question was answered
    1  the answer is "no" (an artifact failed validation)
    2  the caller made a mistake (unknown kind, bad route, unreadable file)
    3  the tool is specified but not built yet - the message names the component

Only commands backed by a built component are registered. Six more are specified
in `jspec.tools.REGISTRY`; `jspec tools` lists all ten with their status, so what is
coming stays visible without putting a command on the menu that can only fail.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from jspec import tools
from jspec.config import ConfigError
from jspec.graph import ExtractError
from jspec.graph.store import StoreError
from jspec.profiler import ProfilerError
from jspec.profiles import ProfileError

EXIT_OK = 0
EXIT_ANSWER_IS_NO = 1
EXIT_USAGE = 2
EXIT_NOT_BUILT = 3


def _use_utf8() -> None:
    """Force UTF-8 on both streams, whatever the console codepage says.

    Stdout is already safe - `json.dump` escapes non-ASCII by default - but stderr
    is not, and an error message is where a real path is most likely to appear. On a
    Windows cp1252 console `café/app.py` came back as `caf?/app.py`, which
    breaks the rule every error message here is written to: name the file and the
    fix. Mirrored in core/scripts/session_start.py, which cannot import this package.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):  # not a reconfigurable stream
            pass


def _emit(payload: dict[str, Any]) -> None:
    """One JSON object per invocation, on stdout. Errors go to stderr."""
    json.dump(payload, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")


def _read_payload(source: str) -> dict[str, Any]:
    """Read a JSON artifact from a path, or from stdin when the path is `-`."""
    if source == "-":
        raw = sys.stdin.read()
        where = "<stdin>"
    else:
        try:
            with open(source, encoding="utf-8") as handle:
                raw = handle.read()
        except OSError as exc:
            raise ValueError(f"cannot read {source}: {exc}") from exc
        where = source

    if not raw.strip():
        raise ValueError(f"{where} is empty")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{where} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        # TRY004 suggests TypeError, but this is malformed *input*, not a Python
        # type bug - and main() maps ValueError to the usage exit code on purpose.
        raise ValueError(  # noqa: TRY004
            f"{where} must contain a JSON object, got {type(payload).__name__}"
        )
    return payload


# --- commands --------------------------------------------------------------------


def cmd_classify(args: argparse.Namespace) -> int:
    _emit(
        tools.classify_task(
            args.prompt,
            dirty=args.dirty,
            failing_tests=args.failing_tests,
            files_touched=args.files_touched,
        )
    )
    return EXIT_OK


def cmd_plan_chain(args: argparse.Namespace) -> int:
    _emit(tools.plan_chain(args.route, profile=args.profile, skip=args.skip))
    return EXIT_OK


def cmd_validate(args: argparse.Namespace) -> int:
    result = tools.validate_artifact(args.kind, _read_payload(args.payload))
    _emit(result)
    return EXIT_OK if result["ok"] else EXIT_ANSWER_IS_NO


def cmd_extract(args: argparse.Namespace) -> int:
    """Run C-06 over a tree and print what it found.

    Not one of the ten tools in `jspec.tools.REGISTRY`, and deliberately so: that
    registry is the surface a *skill* may call; the skill-facing graph tools
    (`blast_radius`, `find_existing`) answer from the store, not from a fresh parse.
    This command exists because C-06's acceptance criterion is that
    every symbol's file and line can be spot-checked by hand, and a component with
    no way to run it cannot be checked at all.
    """
    from pathlib import Path

    from jspec.graph.extract import (
        _language_by_extension,
        extract_file,
        extract_tree,
    )
    from jspec.profiles import load as load_profile

    profile = load_profile(args.profile)
    root = Path(args.root)
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")

    if args.file:
        target = root / args.file
        spec = _language_by_extension(profile.languages).get(target.suffix)
        if spec is None:
            raise ValueError(
                f"profile {profile.name!r} has no language that reads "
                f"{target.suffix!r}; it declares {profile.languages}"
            )
        rows = [extract_file(target, spec, root)]
        payload: dict[str, Any] = {
            "root": root.resolve().as_posix(),
            "profile": profile.name,
            "files": [r.model_dump(mode="json") for r in rows],
        }
        _emit(payload)
        return EXIT_OK

    report = extract_tree(root, profile)
    payload = report.to_dict()
    if args.symbols:
        payload["rows"] = [f.model_dump(mode="json") for f in report.files]
    _emit(payload)
    return EXIT_OK


def cmd_index(args: argparse.Namespace) -> int:
    """Bring the symbol store level with a tree (C-07).

    Prints the run summary, whose headline is `files_parsed` against `files_seen`:
    after the first run that should be the number of files you actually edited.
    """
    from pathlib import Path

    from jspec.graph.store import open_store
    from jspec.profiles import load as load_profile

    profile = load_profile(args.profile)
    root = Path(args.root)
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")

    with open_store(root) as store:
        stats = store.refresh(root, profile, rebuild=args.rebuild)
    _emit(stats.to_dict())
    return EXIT_OK


def cmd_find(args: argparse.Namespace) -> int:
    """Ask the store what exists, by exact name or by text (C-07).

    Exact lookup first, full-text only when asked, because they answer different
    questions: `--text` is for "is there anything like this?", a bare name is for
    "where is this?". A store that has never been indexed says so and names the
    command that fixes it, rather than returning an empty list that reads like
    "nothing here".
    """
    from pathlib import Path

    from jspec.graph.store import open_store

    root = Path(args.root)
    with open_store(root, create=False) as store:
        store.require_indexed(f"run `jspec index {args.root} --profile <name>` first")
        rows = (
            store.search(args.query, limit=args.limit)
            if args.text
            else store.lookup(
                args.query or None,
                kind=args.kind,
                file=args.file,
                module=args.module,
                limit=args.limit,
            )
        )
        _emit(
            {
                "query": args.query,
                "mode": "text" if args.text else "exact",
                "matches": len(rows),
                "rows": rows,
            }
        )
    return EXIT_OK


def cmd_blast_radius(args: argparse.Namespace) -> int:
    """Who is affected if this changes, or what it relies on (C-08).

    Answers from the index and never re-parses, so it is only as fresh as the last
    `jspec index`. An unindexed root is an error that names the command, not an empty
    result: "no dependents" and "nothing was looked at" must never read the same.
    """
    _emit(
        tools.blast_radius(
            args.target,
            root=args.root,
            file=args.file,
            direction=args.direction,
            depth=args.depth,
            limit=args.limit,
        )
    )
    return EXIT_OK


def _parse_sets(pairs: list[str] | None) -> dict[str, str]:
    """`--set field=value` pairs. A malformed pair is a usage error, not a skipped one."""
    corrections: dict[str, str] = {}
    for pair in pairs or []:
        field, separator, value = pair.partition("=")
        if not separator or not field.strip():
            raise ValueError(f"--set expects field=value, got {pair!r}")
        corrections[field.strip()] = value
    return corrections


def cmd_profile_draft(args: argparse.Namespace) -> int:
    """Draft a profile for a repository JSpec has never seen (C-26).

    Reads names across the tree and three manifests at its root; writes nothing into
    it. The draft lands in JSpec's own `.sdd/drafts/`, and a value given with `--set`
    is `confirmed`, so it survives every later draft - that is how a correction is
    never asked for twice.
    """
    from pathlib import Path

    from jspec import profiler
    from jspec.contracts.profile import Basis
    from jspec.graph.store import open_store
    from jspec.profiles import load as load_profile

    root = Path(args.root)
    if not root.is_dir():
        raise ValueError(f"{root} is not a directory")
    name = args.name or profiler.slug(root.resolve().name)
    directory = profiler.drafts_dir()

    try:
        accepted = load_profile(name)
    except ProfileError:
        accepted = None  # no profile by this name yet: the usual first run

    store = None
    note = None
    if args.use_index:
        try:
            store = open_store(root, create=False)
            store.require_indexed(f"run `jspec index {args.root} --profile {name}` first")
        except StoreError as exc:
            note = f"no index used: {exc}"
            store = None
    try:
        draft = profiler.profile_repo(
            root,
            name=args.name,
            corrections=_parse_sets(args.set),
            previous=profiler.load_draft(name, directory),
            accepted=accepted,
            index=store,
        )
    finally:
        if store is not None:
            store.close()
    if note:
        draft.observations.append(note)

    saved = profiler.save_draft(draft, directory)
    counts = {basis.value: 0 for basis in Basis}
    for finding in draft.findings:
        counts[finding.basis.value] += 1
    _emit(
        {
            "name": draft.name,
            "root": draft.root,
            "saved_to": saved.as_posix(),
            "summary": counts,
            "needs_attention": profiler.attention(draft),
            "findings": [f.model_dump(mode="json") for f in draft.findings],
            "observations": draft.observations,
            "next": f"correct anything above with --set, then: jspec profile accept {draft.name}",
        }
    )
    return EXIT_OK


def cmd_profile_accept(args: argparse.Namespace) -> int:
    """Turn a saved draft into `profiles/<name>.yaml` (C-26).

    Exit 1 when it is not accepted, with every blocker listed: a refusal is an answer,
    not a usage error. Guesses need `--accept-guesses`, because reading a draft and
    agreeing to every line of it are different statements.
    """
    from jspec import profiler
    from jspec.profiles import profiles_dir

    directory = profiler.drafts_dir()
    draft = profiler.load_draft(args.name, directory)
    if draft is None:
        raise ValueError(
            f"no draft named {args.name!r} in {directory}; "
            f"run `jspec profile draft <root> --name {args.name}` first"
        )
    result = profiler.accept(
        draft,
        profiles_directory=profiles_dir(),
        drafts_directory=directory,
        accept_guesses=args.accept_guesses,
        overwrite=args.overwrite,
    )
    _emit(result)
    return EXIT_OK if result["accepted"] else EXIT_ANSWER_IS_NO


def cmd_tools(_: argparse.Namespace) -> int:
    _emit(tools.describe())
    return EXIT_OK


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jspec",
        description="Deterministic answers for JSpec skills. No model calls here.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    classify = sub.add_parser(
        "classify",
        help="How much process does this request deserve?",
        description="Route a prompt to T-0..T-3 with confidence, chain and budgets.",
    )
    classify.add_argument("prompt", help="The user's raw request, quoted.")
    # Repo facts outrank vocabulary in the router because they are measured rather
    # than inferred - but only the caller can measure them, so they are flags.
    classify.add_argument(
        "--dirty", action="store_true", help="Working tree has uncommitted changes."
    )
    classify.add_argument(
        "--failing-tests",
        type=int,
        default=0,
        metavar="N",
        help="Known failing tests. Strong signal for the fix route.",
    )
    classify.add_argument(
        "--files-touched",
        type=int,
        default=None,
        metavar="N",
        help="Estimated files this will touch, from the code graph.",
    )
    classify.set_defaults(func=cmd_classify)

    plan = sub.add_parser(
        "plan-chain",
        help="Which steps run for a route, minus justified skips.",
        description="Ordered steps for a route. Unknown skips are rejected.",
    )
    plan.add_argument("route", help="One of T-0, T-1, T-2, T-3.")
    plan.add_argument(
        "--profile",
        default=None,
        help="Profile name. Resolved and reported; does not yet alter the chain.",
    )
    plan.add_argument(
        "--skip",
        action="append",
        default=None,
        metavar="STEP",
        help="Step to skip. Repeatable. Must exist in the chain.",
    )
    plan.set_defaults(func=cmd_plan_chain)

    validate = sub.add_parser(
        "validate",
        help="Does this artifact match its contract?",
        description="Validate an artifact. Prints the problems; persists nothing.",
    )
    validate.add_argument("kind", help="Artifact kind, e.g. spec, plan, profile.")
    validate.add_argument("payload", help="Path to a JSON file, or - for stdin.")
    validate.set_defaults(func=cmd_validate)

    extract = sub.add_parser(
        "extract",
        help="Parse a tree into symbols and references (C-06).",
        description="Read source as structure. Prints a summary; --symbols adds rows.",
    )
    extract.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root folder to index. Every sub-folder under it is walked (D-032).",
    )
    extract.add_argument(
        "--profile",
        required=True,
        help="Profile name. Supplies the languages and the directories to walk.",
    )
    extract.add_argument(
        "--file",
        default=None,
        metavar="PATH",
        help="Root-relative path. Extract only this file, and print every row - "
        "the fast way to check a symbol's line by hand.",
    )
    extract.add_argument(
        "--symbols",
        action="store_true",
        help="Include every symbol and reference, not just the totals.",
    )
    extract.set_defaults(func=cmd_extract)

    index = sub.add_parser(
        "index",
        help="Index a tree into the symbol store, re-reading only what changed (C-07).",
        description="Refresh the SQLite symbol index. Prints what it actually parsed.",
    )
    index.add_argument(
        "root",
        nargs="?",
        default=".",
        help="Root folder to index. The store lives in JSpec's .sdd/index, never here.",
    )
    index.add_argument(
        "--profile",
        required=True,
        help="Profile name. Supplies the languages and the directories to walk.",
    )
    index.add_argument(
        "--rebuild",
        action="store_true",
        help="Re-parse every file regardless of hash - for after a grammar change.",
    )
    index.set_defaults(func=cmd_index)

    find = sub.add_parser(
        "find",
        help="What exists in the index: by name, kind, file, module or text (C-07).",
        description="Query the symbol store. Exact by default; --text for full-text.",
    )
    find.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Symbol name for an exact match, or words to search with --text.",
    )
    find.add_argument(
        "root",
        nargs="?",
        default=".",
        help="The indexed root, so the right store is opened.",
    )
    find.add_argument(
        "--text",
        action="store_true",
        help="Full-text prefix search over names and paths instead of exact match.",
    )
    find.add_argument("--kind", default=None, help="function, class, method, interface.")
    find.add_argument(
        "--file", default=None, metavar="PATH", help="Only symbols in this file."
    )
    find.add_argument("--module", default=None, help="Only symbols in this sub-folder.")
    find.add_argument("--limit", type=int, default=50, help="Maximum rows. Default 50.")
    find.set_defaults(func=cmd_find)

    blast = sub.add_parser(
        "blast-radius",
        help="What a change to a name or file affects, or relies on (C-08).",
        description="Walk the call graph (a name) or import graph (a file). Every "
        "result is certain or possible; the depth searched is always reported.",
    )
    blast.add_argument(
        "target",
        help="A definition name, or an indexed file path (a unique tail is fine).",
    )
    blast.add_argument(
        "root",
        nargs="?",
        default=".",
        help="The indexed root, so the right store is opened.",
    )
    blast.add_argument(
        "--direction",
        choices=["dependents", "dependencies"],
        default="dependents",
        help="dependents: who is affected if this changes (default). "
        "dependencies: what this relies on.",
    )
    blast.add_argument(
        "--file",
        default=None,
        metavar="PATH",
        help="Root-relative path, to pick one definition when a name is defined "
        "in several places.",
    )
    blast.add_argument(
        "--depth",
        type=int,
        default=None,
        metavar="N",
        help="Rings to search. Default 4. The answer says if this limit stopped it.",
    )
    blast.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum rows printed; counts stay complete.",
    )
    blast.set_defaults(func=cmd_blast_radius)

    profile = sub.add_parser(
        "profile",
        help="Draft a profile for a repository it has never seen, then accept it (C-26).",
        description="Every drafted field says whether it was found, inferred or guessed.",
    )
    profile_sub = profile.add_subparsers(dest="profile_command", required=True)

    draft = profile_sub.add_parser(
        "draft",
        help="Read a repository and draft its profile. Writes nothing into it.",
        description="Detect languages, layout and validation commands, field by field.",
    )
    draft.add_argument("root", nargs="?", default=".", help="The repository to profile.")
    draft.add_argument(
        "--name",
        default=None,
        help="Profile id (3-16 characters). Default: derived from the folder name.",
    )
    draft.add_argument(
        "--set",
        action="append",
        default=None,
        metavar="FIELD=VALUE",
        help="Correct a field. Lists are comma-separated. Marked confirmed, and kept "
        "on every later draft. Repeatable.",
    )
    draft.add_argument(
        "--use-index",
        action="store_true",
        help="Also report which folders the most others import, from the symbol index "
        "if this root has been indexed. Never triggers indexing.",
    )
    draft.set_defaults(func=cmd_profile_draft)

    accept = profile_sub.add_parser(
        "accept",
        help="Write a saved draft to profiles/<name>.yaml, if nothing blocks it.",
        description="Refuses while a required field is unknown or a guess is unconfirmed.",
    )
    accept.add_argument("name", help="The draft's name, as printed by `profile draft`.")
    accept.add_argument(
        "--accept-guesses",
        action="store_true",
        help="Accept fields marked guessed as they stand (recorded as confirmed).",
    )
    accept.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing profile of that name.",
    )
    accept.set_defaults(func=cmd_profile_accept)

    listing = sub.add_parser(
        "tools",
        help="All ten tools and what each is waiting on.",
        description="The tool surface, including the seven not built yet.",
    )
    listing.set_defaults(func=cmd_tools)

    return parser


def main(argv: list[str] | None = None) -> int:
    _use_utf8()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except tools.ToolUnavailable as exc:
        print(f"not built yet: {exc}", file=sys.stderr)
        return EXIT_NOT_BUILT
    except (ProfileError, ProfilerError) as exc:
        print(f"profile error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (ExtractError, ConfigError, StoreError) as exc:
        # All three mean the run could not start honestly - an unsupported language,
        # a missing grammar, unreadable exclusion rules, an index written by another
        # schema version. None of them is a "no".
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (ValueError, KeyError) as exc:
        # `str(KeyError(msg))` is `repr(msg)`, so it arrives wrapped in quotes. Read
        # the argument directly instead - the message was written to be read.
        message = exc.args[0] if exc.args else str(exc)
        print(f"error: {message}", file=sys.stderr)
        return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
