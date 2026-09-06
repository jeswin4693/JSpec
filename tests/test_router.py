"""Router tests.

The router is deterministic by design (DECISIONS.md D-009), which is exactly why it
is testable. Every assertion here is a routing decision we do not want to regress.
"""

from __future__ import annotations

import pytest
from jspec.router import (
    CONFIDENCE_FLOOR,
    FILE_PATH,
    RepoState,
    Route,
    classify,
    plan_chain,
)


class TestRouteSelection:
    def test_small_change_vocabulary_and_one_file_routes_trivial(self) -> None:
        c = classify("rename the timeout constant in config.py")
        assert c.route is Route.T0_TRIVIAL
        assert c.confidence > 0.9
        assert c.question_budget == 0

    def test_stack_trace_routes_to_fix(self) -> None:
        c = classify(
            "the labor backflush test is failing with Timeout 30000ms exceeded"
        )
        assert c.route is Route.T1_FIX
        assert c.confidence > 0.9

    def test_assertion_text_alone_is_enough_for_fix(self) -> None:
        c = classify("expect(locator).toBeVisible() is not passing any more")
        assert c.route is Route.T1_FIX

    def test_breadth_vocabulary_routes_to_sweep(self) -> None:
        c = classify("update every spec across the whole suite to use the new helper")
        assert c.route is Route.T3_SWEEP

    def test_detailed_creation_request_routes_to_feature(self) -> None:
        c = classify(
            "implement a new reporting module per ADO-696633 with the following "
            "requirements covering export, scheduling and per-tenant permissions, "
            "including the acceptance criteria the product owner supplied today"
        )
        assert c.route is Route.T2_FEATURE
        assert c.question_budget == 3


class TestConfidence:
    def test_weak_single_signal_defers_to_the_model(self) -> None:
        """Regression: 'hmm' once scored 0.95 because only the MARGIN was measured.

        A lone weak signal beats an empty field by a wide margin while telling us
        almost nothing. Confidence must scale with absolute evidence too, or
        one-word prompts get sent confidently down the wrong pipeline.
        """
        c = classify("hmm")
        assert c.confidence < CONFIDENCE_FLOOR
        assert c.needs_model_adjudication is True

    def test_no_signals_at_all_yields_zero_confidence(self) -> None:
        """Nothing matched: the router must refuse to invent a route.

        Needs a prompt long enough not to trip the terse-prompt signal, or that
        signal alone counts as (weak) evidence.
        """
        c = classify(
            "the quick brown fox jumped over the lazy dog while the rain fell "
            "steadily against the window of the empty house on the hill"
        )
        assert c.confidence == 0.0
        assert c.needs_model_adjudication is True
        assert c.signals == ["no signals matched"]

    def test_short_gibberish_is_weak_evidence_not_no_evidence(self) -> None:
        """A terse prompt IS a signal - just a weak one. It must still defer."""
        c = classify("!!! ??? ...")
        assert 0.0 < c.confidence < CONFIDENCE_FLOOR
        assert c.needs_model_adjudication is True

    def test_contested_prompt_defers_rather_than_guessing(self) -> None:
        """Creation + breadth vocabulary together is genuinely ambiguous."""
        c = classify("add support for every environment across the whole suite")
        assert c.needs_model_adjudication is True

    def test_confidence_never_reaches_certainty(self) -> None:
        c = classify("rename the flag in config.py")
        assert c.confidence <= 0.95


class TestRepoFactsOutrankVocabulary:
    def test_graph_estimate_of_one_file_overrides_creation_words(self) -> None:
        """Measured facts beat inferred ones (D-003)."""
        c = classify("add a new helper", RepoState(estimated_files_touched=1))
        assert c.route is Route.T0_TRIVIAL

    def test_many_files_touched_escalates_to_sweep(self) -> None:
        c = classify("add a new helper", RepoState(estimated_files_touched=30))
        assert c.route is Route.T3_SWEEP

    def test_failing_tests_pull_towards_fix(self) -> None:
        c = classify("look at the login helper", RepoState(failing_tests=3))
        assert c.route is Route.T1_FIX


class TestBudgetsAndChains:
    @pytest.mark.parametrize("route", list(Route))
    def test_every_route_has_a_chain_and_budgets(self, route: Route) -> None:
        """A route with no chain would silently do nothing."""
        c = classify("x")
        c.route = route
        assert len(c.chain) >= 3
        assert c.token_budget > 0
        assert c.question_budget >= 0

    def test_trivial_route_is_the_cheapest(self) -> None:
        """The router's most valuable decision is skipping work (D-009)."""
        trivial = classify("rename the constant in a.py").token_budget
        feature = classify(
            "implement a new module with the following detailed requirements " * 4
        ).token_budget
        assert trivial < feature

    def test_feature_route_never_skips_specify_implicitly(self) -> None:
        c = classify("implement a new module with detailed requirements " * 4)
        assert c.chain[0] == "specify"

    def test_plan_chain_honours_explicit_skips(self) -> None:
        c = classify("implement a new module with detailed requirements " * 4)
        steps = plan_chain(c, skip=("clarify",))
        assert "clarify" not in steps
        assert "specify" in steps

    def test_plan_chain_ignores_unknown_skip_names(self) -> None:
        c = classify("rename the constant in a.py")
        assert plan_chain(c, skip=("not-a-step",)) == list(c.chain)


class TestSerialisation:
    def test_to_dict_carries_everything_the_caller_needs(self) -> None:
        d = classify("fix the flaky grid test").to_dict()
        for key in (
            "route",
            "confidence",
            "chain",
            "question_budget",
            "token_budget",
            "signals",
            "needs_model_adjudication",
        ):
            assert key in d, f"missing {key}"

    def test_signals_explain_the_decision(self) -> None:
        """A route with no stated reasoning is unauditable."""
        c = classify("rename the timeout constant in config.py")
        assert c.signals
        assert all("+" in s for s in c.signals)


class TestFilePathIsShapeNotVocabulary:
    """`FILE_PATH` recognises a filename by its shape, not by a language list.

    It used to enumerate ten extensions, which put domain knowledge in `core/`
    (constitution rule 20) and silently failed on every language not listed. These
    tests pin both halves of the replacement: what it must still match, and what it
    must never match.
    """

    @pytest.mark.parametrize(
        "text",
        [
            "config.py",
            "a.py",
            "src/app.tsx",
            "docker-compose.yml",
            "Store.java",
            "page-objects/m2m/navigation.ts",
        ],
    )
    def test_it_still_matches_everything_the_old_list_did(self, text: str) -> None:
        assert FILE_PATH.findall(text) == [text]

    @pytest.mark.parametrize(
        "text", ["main.rs", "README.md", "schema.json", "deploy.tf", "Model.kt"]
    )
    def test_it_now_matches_languages_the_old_list_missed(self, text: str) -> None:
        """The point of the change: JSpec is meant to be domain-agnostic."""
        assert FILE_PATH.findall(text) == [text]

    def test_a_windows_path_matches_in_full(self) -> None:
        """Regression guard. A first attempt at this pattern dropped the backslash
        from the separator class, so a Windows path matched only its last segment
        and the count of files named came out wrong."""
        text = chr(92).join(["page-objects", "m2m", "navigation.ts"])
        assert FILE_PATH.findall(text) == [text]

    @pytest.mark.parametrize(
        "text", ["e.g.", "i.e.", "etc.", "version 3.13", "v1.2.3", "U.S.A."]
    )
    def test_prose_and_version_numbers_are_not_files(self, text: str) -> None:
        """A one-character suffix, or one starting with a digit, is not an extension.

        This is what keeps the signal usable now that the extension list is gone.
        """
        assert FILE_PATH.findall(text) == []

    def test_the_signal_counts_files_not_mentions(self) -> None:
        """The bump fires on exactly one file named; two must not trigger it."""
        assert len(FILE_PATH.findall("move helper from a.py to b.py")) == 2
        assert "exactly one file named" not in " ".join(
            classify("move the helper from a.py to b.py").signals
        )

    def test_one_named_file_still_pushes_toward_trivial(self) -> None:
        signals = " ".join(classify("rename the constant in config.py").signals)
        assert "exactly one file named" in signals
