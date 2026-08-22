"""SessionStart hook: surface JSpec memory so a new chat resumes where the last stopped.

Stdout is delivered to Claude at session start. Keep it short - this is prepended to
every session, so verbosity here is a permanent tax on the context window.

Never fails the session: any problem degrades to a one-line note.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

MAX_STATE_CHARS = 4000
MAX_JOURNAL_CHARS = 1200


def project_root() -> Path:
    """JSPEC_ROOT if the hook set it, else walk up looking for memory/STATE.md."""
    env = os.environ.get("JSPEC_ROOT")
    if env and (Path(env) / "memory").is_dir():
        return Path(env)
    here = Path(__file__).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "memory" / "STATE.md").is_file():
            return candidate
    return here.parents[2] if len(here.parents) > 2 else here.parent


def read_capped(path: Path, cap: int) -> str:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= cap:
        return text
    return text[:cap].rstrip() + f"\n... [truncated, read {path.name} in full if needed]"


def newest_journal(journal_dir: Path) -> Path | None:
    if not journal_dir.is_dir():
        return None
    entries = sorted(p for p in journal_dir.glob("*.md") if p.is_file())
    return entries[-1] if entries else None


def main() -> int:
    root = project_root()
    memory = root / "memory"
    out: list[str] = ["# JSpec memory (auto-loaded at session start)"]

    state = memory / "STATE.md"
    if state.is_file():
        out.append(read_capped(state, MAX_STATE_CHARS))
    else:
        out.append(
            "No `memory/STATE.md` found. If this is a fresh clone, create it before "
            "doing work - JSpec has no cross-session memory without it."
        )

    latest = newest_journal(memory / "journal")
    if latest is not None:
        out.append(f"## Most recent journal: `memory/journal/{latest.name}`")
        out.append(read_capped(latest, MAX_JOURNAL_CHARS))

    decisions = memory / "DECISIONS.md"
    if decisions.is_file():
        ids = [
            line.split("·")[0].replace("##", "").strip()
            for line in decisions.read_text(
                encoding="utf-8", errors="replace"
            ).splitlines()
            if line.startswith("## D-")
        ]
        if ids:
            out.append(
                f"## Decisions on record ({len(ids)}): {', '.join(ids)}\n"
                "Read `memory/DECISIONS.md` before proposing a change to any of them. "
                "Do not re-litigate a recorded decision."
            )

    sys.stdout.write("\n\n".join(out) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001 - a hook must never break the session
        sys.stdout.write(f"JSpec memory hook could not run: {exc}\n")
        raise SystemExit(0)
