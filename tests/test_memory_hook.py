"""SessionStart hook tests (C-03).

This file exists because of a bug it would have caught. The hook writes the memory
files to stdout, Claude Code captures that through a pipe, and on Windows Python
then encodes with the locale codepage. `memory/STATE.md` is full of arrows and
bullets, so the first one raised `UnicodeEncodeError`, the top-level handler
swallowed it, and every session on this machine started with **no memory loaded** -
reporting only a one-line "could not run" that nothing was watching for.

Nothing tested the hook at all, which is how a failure this total stayed invisible.
So the tests below run it the way the harness does: as a subprocess, capturing
stdout, including once under a deliberately legacy codepage.

It is invoked by `jspec/hooks/hooks.json` as bare `python`, so it must keep working
with no package installed and no environment set up. These tests run it by path, for
the same reason.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "core" / "scripts" / "session_start.py"

# Characters that actually appear in the memory files and are absent from cp1252's
# usable range for this purpose - the arrow is the one that broke it.
NON_ASCII = "→ · —"


def run_hook(root: Path | None = None, encoding: str | None = None):
    """Run the hook as a subprocess, the way the harness does."""
    env = dict(os.environ)
    if root is not None:
        env["JSPEC_ROOT"] = str(root)
    if encoding is not None:
        env["PYTHONIOENCODING"] = encoding
    return subprocess.run(
        [sys.executable, str(HOOK)],
        capture_output=True,
        # The exit code is the thing under test - a hook that fails the session is
        # the failure mode - so it is asserted on, never raised on.
        check=False,
        env=env,
        # Decode as UTF-8 here regardless: the point is what the hook *emitted*.
        encoding="utf-8",
        errors="replace",
    )


def write_memory(root: Path, *, state: str, journal: str = "", decisions: str = ""):
    memory = root / "memory"
    (memory / "journal").mkdir(parents=True, exist_ok=True)
    (memory / "STATE.md").write_text(state, encoding="utf-8")
    if journal:
        (memory / "journal" / "2026-01-01.md").write_text(journal, encoding="utf-8")
    if decisions:
        (memory / "DECISIONS.md").write_text(decisions, encoding="utf-8")
    return memory


class TestItSurvivesALegacyCodepage:
    """The regression this file was written for."""

    @pytest.mark.parametrize("encoding", ["cp1252", "ascii", "utf-8"])
    def test_non_ascii_memory_is_emitted_whatever_the_console_encoding(
        self, tmp_path: Path, encoding: str
    ) -> None:
        write_memory(tmp_path, state=f"# STATE\n\nPhase 1 {NON_ASCII} still going.\n")

        result = run_hook(tmp_path, encoding=encoding)

        assert result.returncode == 0
        assert "could not run" not in result.stdout, (
            f"the hook degraded under {encoding}: {result.stdout[:200]}"
        )
        assert "Phase 1" in result.stdout
        assert "→" in result.stdout, "the arrow must survive, not be dropped"

    def test_the_real_repository_memory_loads(self) -> None:
        """The shipped memory files are exactly the ones that broke it."""
        result = run_hook(REPO_ROOT)

        assert result.returncode == 0
        assert "could not run" not in result.stdout
        assert "JSpec memory" in result.stdout
        assert "Decisions on record" in result.stdout


class TestItNeverFailsTheSession:
    """A hook that raises would block a session from starting at all."""

    def test_missing_memory_still_exits_zero_and_says_so(self, tmp_path: Path) -> None:
        (tmp_path / "memory").mkdir()

        result = run_hook(tmp_path)

        assert result.returncode == 0
        assert "No `memory/STATE.md` found" in result.stdout

    def test_unreadable_bytes_do_not_crash_it(self, tmp_path: Path) -> None:
        """`read_capped` decodes with errors='replace'; this pins that."""
        memory = tmp_path / "memory"
        memory.mkdir()
        (memory / "STATE.md").write_bytes(b"# STATE\n\xff\xfe not valid utf-8\n")

        result = run_hook(tmp_path)

        assert result.returncode == 0
        assert "STATE" in result.stdout


class TestItSaysWhatTheSessionNeeds:
    def test_it_carries_state_the_newest_journal_and_the_decision_ids(
        self, tmp_path: Path
    ) -> None:
        write_memory(
            tmp_path,
            state="# STATE\n\nBuilding C-07 next.\n",
            journal="# Journal\n\nBuilt the extractor.\n",
            decisions="## D-001 · 2026-01-01 · First\n\n## D-002 · x · Second\n",
        )

        result = run_hook(tmp_path)

        assert "Building C-07 next." in result.stdout
        assert "2026-01-01.md" in result.stdout
        assert "Built the extractor." in result.stdout
        assert "D-001" in result.stdout and "D-002" in result.stdout
        assert "Decisions on record (2)" in result.stdout

    def test_the_newest_journal_wins(self, tmp_path: Path) -> None:
        memory = tmp_path / "memory"
        (memory / "journal").mkdir(parents=True)
        (memory / "STATE.md").write_text("# STATE\n", encoding="utf-8")
        (memory / "journal" / "2026-01-01.md").write_text("oldest\n", encoding="utf-8")
        (memory / "journal" / "2026-09-06.md").write_text("newest\n", encoding="utf-8")

        result = run_hook(tmp_path)

        assert "2026-09-06.md" in result.stdout
        assert "oldest" not in result.stdout

    def test_a_long_state_file_is_truncated_not_dumped(self, tmp_path: Path) -> None:
        """Output here is a permanent tax on every session's context window."""
        write_memory(tmp_path, state="# STATE\n\n" + ("filler line\n" * 2000))

        result = run_hook(tmp_path)

        assert "truncated" in result.stdout
        assert len(result.stdout) < 8000
