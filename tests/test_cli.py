"""Tool surface tests - the bridge between a skill and the deterministic core.

The point of C-05 is that a skill can get a *fact* instead of making a guess. So the
tests that matter most are not the happy paths; they are:

  - `TestUnbuiltToolsRefuse` - a tool whose engine does not exist must raise, naming
    the component it waits on. A placeholder answer here would flow into a risk score
    and out to a gate, and nothing downstream could tell it from a measurement.
  - `TestCallerMistakesAreRejected` - a misspelled route, an unknown skip or a bad
    profile stops the run immediately, rather than silently doing something adjacent.

Exit codes are part of the contract: 0 answered, 1 the answer is no, 2 caller error,
3 not built yet. A caller reads the code before it parses anything.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from jspec.cli import (
    EXIT_ANSWER_IS_NO,
    EXIT_NOT_BUILT,
    EXIT_OK,
    EXIT_USAGE,
    main,
)

from jspec import tools

VALID_PROFILE = {
    "name": "demo",
    "description": "A profile for testing.",
    "languages": ["python"],
    "source_dirs": ["src/"],
    "validation": {"test": "pytest"},
}


def run(capsys, *argv: str) -> tuple[int, dict, str]:
    """Invoke the CLI, returning (exit code, parsed stdout, stderr)."""
    code = main(list(argv))
    captured = capsys.readouterr()
    payload = json.loads(captured.out) if captured.out.strip() else {}
    return code, payload, captured.err


class TestClassify:
    def test_a_feature_request_gets_the_feature_chain(self, capsys) -> None:
        code, out, _ = run(capsys, "classify", "add password reset with email link")
        assert code == EXIT_OK
        assert out["route"] == "T-2"
        assert out["chain"][0] == "specify"
        assert out["token_budget"] == 9000

    def test_a_typo_fix_gets_the_cheap_chain(self, capsys) -> None:
        code, out, _ = run(capsys, "classify", "fix the typo in the readme")
        assert code == EXIT_OK
        assert out["route"] == "T-0"
        assert out["token_budget"] == 900
        assert out["question_budget"] == 0

    def test_low_confidence_is_flagged_for_adjudication(self, capsys) -> None:
        """The router must never return an uncertain route as if it were settled."""
        _, out, _ = run(capsys, "classify", "fix the typo in the readme")
        assert out["confidence"] < 0.6
        assert out["needs_model_adjudication"] is True

    def test_repo_facts_outrank_vocabulary(self, capsys) -> None:
        """Measured facts beat word-matching - the point of the RepoState flags.

        Bare, this prompt ties on vocabulary. Told the graph estimate, the router
        gets it right and gets confident, which is the whole reason the caller is
        allowed to supply repo state.
        """
        _, bare, _ = run(capsys, "classify", "rename every getUser call in the repo")
        _, informed, _ = run(
            capsys,
            "classify",
            "rename every getUser call in the repo",
            "--files-touched",
            "40",
        )
        assert informed["route"] == "T-3"
        assert informed["confidence"] > bare["confidence"]

    def test_failing_tests_push_toward_the_fix_route(self, capsys) -> None:
        _, out, _ = run(
            capsys, "classify", "the checkout page is broken", "--failing-tests", "3"
        )
        assert out["route"] == "T-1"
        assert any("failing test" in s for s in out["signals"])


class TestPlanChain:
    def test_returns_the_chain_for_a_route(self, capsys) -> None:
        code, out, _ = run(capsys, "plan-chain", "T-2")
        assert code == EXIT_OK
        assert out["steps"][0] == "specify"
        assert out["skipped"] == []

    def test_a_justified_skip_is_removed_and_reported(self, capsys) -> None:
        """A silently shortened chain reads as full coverage when it was not."""
        _, out, _ = run(capsys, "plan-chain", "T-2", "--skip", "clarify")
        assert "clarify" not in out["steps"]
        assert out["skipped"] == ["clarify"]

    def test_a_profile_is_resolved_and_reported(self, capsys) -> None:
        _, out, _ = run(capsys, "plan-chain", "T-2", "--profile", "python-service")
        assert out["profile"] == "python-service"

    def test_no_profile_is_honest_about_it(self, capsys) -> None:
        _, out, _ = run(capsys, "plan-chain", "T-2")
        assert out["profile"] is None


class TestValidate:
    def test_a_valid_artifact_passes(self, capsys, tmp_path: Path) -> None:
        path = tmp_path / "p.json"
        path.write_text(json.dumps(VALID_PROFILE), encoding="utf-8")
        code, out, _ = run(capsys, "validate", "profile", str(path))
        assert code == EXIT_OK
        assert out["ok"] is True

    def test_an_invalid_artifact_exits_one_and_lists_every_problem(
        self, capsys, tmp_path: Path
    ) -> None:
        """Exit 1 means 'the answer is no', not 'the tool broke'."""
        bad = {**VALID_PROFILE, "languages": ["Python"], "validation": {}}
        path = tmp_path / "p.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        code, out, _ = run(capsys, "validate", "profile", str(path))
        assert code == EXIT_ANSWER_IS_NO
        assert out["ok"] is False
        fields = {e["field"] for e in out["errors"]}
        assert {"languages", "validation.test"} <= fields

    def test_reads_from_stdin(self, capsys, monkeypatch) -> None:
        import io

        monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(VALID_PROFILE)))
        code, out, _ = run(capsys, "validate", "profile", "-")
        assert code == EXIT_OK and out["ok"] is True


class TestUnbuiltToolsRefuse:
    """The most important class in this file.

    A missing tool gets built. A lying tool gets trusted.
    """

    @pytest.mark.parametrize(
        "name",
        [
            "blast_radius",
            "score_risk",
            "record_gate",
            "record_preference",
            "record_cost",
            "submit_spec",
        ],
    )
    def test_every_unbuilt_tool_raises_naming_its_component(self, name: str) -> None:
        import inspect

        from jspec import mcp_server

        func = getattr(mcp_server, name)
        # Each tool has its own arity; supply exactly as many dummies as it takes,
        # so the test proves the refusal rather than tripping over the signature.
        required = [
            p
            for p in inspect.signature(func).parameters.values()
            if p.default is inspect.Parameter.empty
        ]
        with pytest.raises(tools.ToolUnavailable) as exc:
            func(*[{} for _ in required])
        assert tools.BY_NAME[name].blocked_by in str(exc.value)

    @pytest.mark.parametrize("name", [t.name for t in tools.REGISTRY if not t.ready])
    def test_no_unbuilt_tool_is_exposed_as_a_command(self, name: str) -> None:
        """A command that can only fail does not belong on the menu.

        Checked by behaviour rather than by reading the parser's internals: argparse
        exits 2 on an unknown command, and that is what a caller would actually hit.
        """
        with pytest.raises(SystemExit) as exc:
            main([name])
        assert exc.value.code == EXIT_USAGE

    def test_the_mcp_server_still_refuses_to_start(self) -> None:
        """D-025 defers it. `.mcp.json` on disk must not be read as 'working'."""
        from jspec import mcp_server

        with pytest.raises(NotImplementedError, match="D-025"):
            mcp_server.main()


class TestCallerMistakesAreRejected:
    def test_unknown_route(self, capsys) -> None:
        code, _, err = run(capsys, "plan-chain", "T-9")
        assert code == EXIT_USAGE
        assert "T-9" in err

    def test_unknown_skip_is_not_silently_ignored(self, capsys) -> None:
        """Ignoring it leaves the caller believing they skipped a step that ran."""
        code, _, err = run(capsys, "plan-chain", "T-2", "--skip", "nonsense")
        assert code == EXIT_USAGE
        assert "nonsense" in err

    def test_misspelled_profile_suggests_the_right_one(self, capsys) -> None:
        code, _, err = run(capsys, "plan-chain", "T-2", "--profile", "pyton-service")
        assert code == EXIT_USAGE
        assert "python-service" in err

    def test_unknown_artifact_kind_lists_the_known_ones(
        self, capsys, tmp_path: Path
    ) -> None:
        path = tmp_path / "x.json"
        path.write_text("{}", encoding="utf-8")
        code, _, err = run(capsys, "validate", "spek", str(path))
        assert code == EXIT_USAGE
        assert "spec" in err and "'spek'" not in err.split("known kinds")[1]

    def test_missing_file(self, capsys, tmp_path: Path) -> None:
        code, _, err = run(capsys, "validate", "profile", str(tmp_path / "gone.json"))
        assert code == EXIT_USAGE
        assert "cannot read" in err

    def test_malformed_json(self, capsys, tmp_path: Path) -> None:
        path = tmp_path / "bad.json"
        path.write_text("{not json", encoding="utf-8")
        code, _, err = run(capsys, "validate", "profile", str(path))
        assert code == EXIT_USAGE
        assert "not valid JSON" in err

    def test_json_that_is_not_an_object(self, capsys, tmp_path: Path) -> None:
        path = tmp_path / "list.json"
        path.write_text("[1, 2]", encoding="utf-8")
        code, _, err = run(capsys, "validate", "profile", str(path))
        assert code == EXIT_USAGE
        assert "JSON object" in err


class TestToolsListing:
    def test_lists_all_ten_with_status(self, capsys) -> None:
        code, out, _ = run(capsys, "tools")
        assert code == EXIT_OK
        assert out["total"] == 10
        assert out["ready"] + out["blocked"] == 10

    def test_every_blocked_tool_says_what_it_waits_on(self) -> None:
        for tool in tools.REGISTRY:
            if not tool.ready:
                assert tool.blocked_by and tool.reason, tool.name

    def test_the_registry_and_the_mcp_surface_hold_the_same_ten(self) -> None:
        """Two lists would drift, and a drifted list advertises a dead tool."""
        from jspec import mcp_server

        assert {t.__name__ for t in mcp_server.TOOLS} == set(tools.BY_NAME)


class TestExitCodesAreDistinct:
    def test_the_four_codes_do_not_collide(self) -> None:
        codes = {EXIT_OK, EXIT_ANSWER_IS_NO, EXIT_USAGE, EXIT_NOT_BUILT}
        assert len(codes) == 4
