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

Only commands backed by a built component are registered. Seven more are specified
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
    registry is the surface a *skill* may call, and the skill-facing graph tools
    (`blast_radius`, `find_existing`) stay blocked until C-07 can resolve a name to
    a definition. This command exists because C-06's acceptance criterion is that
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
    except ProfileError as exc:
        print(f"profile error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except (ExtractError, ConfigError) as exc:
        # Both mean the run could not start honestly - an unsupported language, a
        # missing grammar, unreadable exclusion rules. None of them is a "no".
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
