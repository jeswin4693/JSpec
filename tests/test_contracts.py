"""Spec contract tests.

These assertions are the whole point of typed artifacts (DECISIONS.md D-002): a
malformed spec must be impossible, not merely unlikely. Each rejection below is a
class of bad spec that would otherwise reach the planner and poison everything
downstream.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from jspec.contracts.spec import Spec
from pydantic import ValidationError

VALID: dict[str, Any] = {
    "feature_slug": "026-dual-env-webapi",
    "title": "Dual-environment WebAPI specs",
    "intake_ref": "ADO-696633",
    "created": "2026-08-22",
    "stories": [
        {
            "id": "US-001",
            "title": "Run one spec on both environments",
            "journey": "A tester runs the same API spec against two environments without editing it.",
            "priority": "P1",
            "why_this_priority": "Editing files per environment is the current failure source.",
            "independent_test": "Run the spec under each project and confirm both pass unmodified.",
            "acceptance": [
                {
                    "given": "a spec resolving config per project",
                    "when": "it runs under either project",
                    "then": "it passes with no file edits",
                }
            ],
        }
    ],
    "requirements": [
        {
            "id": "FR-001",
            "text": "System MUST resolve company per project.",
            "testable": True,
        }
    ],
    "success_criteria": [
        {
            "id": "SC-001",
            "text": "Same spec passes on both projects.",
            "measure": "2 of 2 projects green, 0 file edits",
        }
    ],
    "confidence": 0.82,
    "evidence": ["test-data/apiConfig.ts:1"],
}


def variant(**overrides: Any) -> dict[str, Any]:
    return {**VALID, **overrides}


class TestAcceptsValidSpecs:
    def test_valid_spec_round_trips(self) -> None:
        spec = Spec.model_validate(VALID)
        assert spec.feature_slug == "026-dual-env-webapi"
        assert spec.is_plannable is True

    def test_untestable_requirement_is_allowed_when_explained(self) -> None:
        """Honest 'this isn't testable yet, and here's why' must survive."""
        spec = Spec.model_validate(
            variant(
                requirements=[
                    {
                        "id": "FR-001",
                        "text": "System MUST behave appropriately for unknown projects.",
                        "testable": False,
                        "untestable_reason": "'appropriately' undefined - needs an error contract.",
                    }
                ]
            )
        )
        assert spec.requirements[0].testable is False


class TestBlocksPlanningOnAmbiguity:
    def test_open_clarification_makes_a_spec_unplannable(self) -> None:
        """An unclarified spec is the most expensive artifact in the pipeline -
        everything downstream inherits the ambiguity."""
        spec = Spec.model_validate(
            variant(open_clarifications=["which company for Appcentral?"])
        )
        assert spec.is_plannable is False


class TestRejectsBadSpecs:
    def test_untestable_requirement_without_a_reason(self) -> None:
        with pytest.raises(ValidationError, match="untestable_reason"):
            Spec.model_validate(
                variant(
                    requirements=[
                        {
                            "id": "FR-001",
                            "text": "System MUST do the thing.",
                            "testable": False,
                        }
                    ]
                )
            )

    @pytest.mark.parametrize("hope", ["fast", "works well", "better", "user-friendly"])
    def test_success_criterion_that_is_a_hope_not_a_measure(self, hope: str) -> None:
        with pytest.raises(ValidationError, match="hope"):
            Spec.model_validate(
                variant(
                    success_criteria=[
                        {"id": "SC-001", "text": "It should be quick.", "measure": hope}
                    ]
                )
            )

    def test_spec_with_no_p1_story_has_no_mvp_slice(self) -> None:
        with pytest.raises(ValidationError, match="P1"):
            Spec.model_validate(
                variant(stories=[{**VALID["stories"][0], "priority": "P3"}])
            )

    def test_duplicate_requirement_ids(self) -> None:
        with pytest.raises(ValidationError, match="duplicate requirement ids"):
            Spec.model_validate(
                variant(
                    requirements=[VALID["requirements"][0], VALID["requirements"][0]]
                )
            )

    def test_duplicate_story_ids(self) -> None:
        with pytest.raises(ValidationError, match="duplicate story ids"):
            Spec.model_validate(
                variant(stories=[VALID["stories"][0], VALID["stories"][0]])
            )

    def test_judgement_without_evidence(self) -> None:
        """Evidence or silence (D-003). A verdict with no citation is inadmissible."""
        with pytest.raises(ValidationError):
            Spec.model_validate(variant(evidence=[]))

    def test_spec_with_no_requirements(self) -> None:
        with pytest.raises(ValidationError):
            Spec.model_validate(variant(requirements=[]))

    def test_malformed_feature_slug(self) -> None:
        with pytest.raises(ValidationError):
            Spec.model_validate(variant(feature_slug="Dual Env WebAPI"))

    def test_malformed_requirement_id(self) -> None:
        with pytest.raises(ValidationError):
            Spec.model_validate(
                variant(
                    requirements=[
                        {"id": "REQ-1", "text": "System MUST x.", "testable": True}
                    ]
                )
            )

    def test_confidence_outside_zero_to_one(self) -> None:
        with pytest.raises(ValidationError):
            Spec.model_validate(variant(confidence=1.4))


class TestSchemaExport:
    def test_json_schema_exports_for_mcp_and_headless_use(self) -> None:
        """The same schema feeds MCP tool inputs and `claude -p --json-schema`,
        which is how artifacts get enforced structure with no API key (D-006)."""
        schema = Spec.model_json_schema()
        assert schema["type"] == "object"
        assert "$defs" in schema
        for required in ("stories", "requirements", "success_criteria", "evidence"):
            assert required in schema["required"], f"{required} must be required"
        json.dumps(schema)  # must be serialisable to reach either consumer
