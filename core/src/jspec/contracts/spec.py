"""Spec contracts.

The spec is a validated object. Markdown is a rendering of it, never the source of
truth (DECISIONS.md D-002). These models are exported as JSON Schema and used two
ways, both without an API key (D-006):

  - as MCP tool input schemas, for in-session work
  - via `claude -p --output-format json --json-schema`, for headless and evals

Keep this module free of I/O and of model calls.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator, model_validator

Id = Annotated[str, Field(min_length=3, max_length=16)]
Evidence = Annotated[list[str], Field(min_length=1)]
"""At least one `path:line` or quoted source. A judgement without evidence is not
admissible (D-003)."""


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class AcceptanceScenario(BaseModel):
    """Given/When/Then. Split into three fields so it can be checked, not just read."""

    given: str = Field(min_length=3)
    when: str = Field(min_length=3)
    then: str = Field(min_length=3)


class UserStory(BaseModel):
    id: Id = Field(pattern=r"^US-\d{3}$")
    title: str = Field(min_length=3, max_length=120)
    journey: str = Field(min_length=20, description="Plain language. No technology.")
    priority: Priority
    why_this_priority: str = Field(min_length=10)
    independent_test: str = Field(
        min_length=20,
        description=(
            "How this story is validated ALONE. If implementing only this story "
            "delivers nothing demonstrable, it is not independent - fold it into one "
            "that is."
        ),
    )
    acceptance: list[AcceptanceScenario] = Field(min_length=1)


class Requirement(BaseModel):
    id: Id = Field(pattern=r"^FR-\d{3}$")
    text: str = Field(min_length=10)
    testable: bool
    untestable_reason: str | None = Field(
        default=None,
        description="Required when testable is False: what would make it testable.",
    )
    clarifications: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _reason_required_when_untestable(self) -> Requirement:
        if not self.testable and not self.untestable_reason:
            raise ValueError(
                f"{self.id}: testable=False requires untestable_reason - say what "
                f"would make it testable instead of leaving it unexplained"
            )
        return self


class SuccessCriterion(BaseModel):
    id: Id = Field(pattern=r"^SC-\d{3}$")
    text: str = Field(min_length=10)
    measure: str = Field(
        min_length=3,
        description="The number, threshold, or observable outcome. Not a hope.",
    )
    technology_agnostic: bool = True

    @field_validator("measure")
    @classmethod
    def _reject_hopes(cls, v: str) -> str:
        hopes = {
            "works well",
            "works reliably",
            "user friendly",
            "user-friendly",
            "fast",
            "good performance",
            "improved",
            "better",
        }
        if v.strip().lower() in hopes:
            raise ValueError(
                f"'{v}' is a hope, not a measure. Give a number, a threshold, or an "
                f"observable outcome."
            )
        return v


class Assumption(BaseModel):
    """A resolved-by-default unknown, surfaced for cheap correction at the gate.

    Preferred over asking the user (D-010): reviewing a flagged default costs seconds,
    answering a mid-flight question costs a context switch.
    """

    about: str = Field(min_length=3)
    assumed: str = Field(min_length=1)
    source: str = Field(
        description="preferences | repo | profile | default - where it came from"
    )
    affects: list[str] = Field(default_factory=list, description="FR/SC/US ids")


class Spec(BaseModel):
    """A specification: what and why. Never how."""

    feature_slug: str = Field(pattern=r"^\d{3}-[a-z0-9-]+$")
    title: str = Field(min_length=3, max_length=120)
    intake_ref: str | None = Field(
        default=None, description="Work item / issue / source id, if any"
    )
    created: str = Field(description="ISO date; supplied by the caller, never now()")

    stories: list[UserStory] = Field(min_length=1)
    requirements: list[Requirement] = Field(min_length=1)
    success_criteria: list[SuccessCriterion] = Field(min_length=1)
    edge_cases: list[str] = Field(default_factory=list)

    assumptions: list[Assumption] = Field(default_factory=list)
    open_clarifications: list[str] = Field(default_factory=list)

    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Evidence

    @model_validator(mode="after")
    def _one_p1_and_unique_ids(self) -> Spec:
        if not any(s.priority is Priority.P1 for s in self.stories):
            raise ValueError(
                "at least one P1 story is required - without it there is no MVP slice"
            )
        for label, ids in (
            ("story", [s.id for s in self.stories]),
            ("requirement", [r.id for r in self.requirements]),
            ("success criterion", [c.id for c in self.success_criteria]),
        ):
            dupes = {i for i in ids if ids.count(i) > 1}
            if dupes:
                raise ValueError(f"duplicate {label} ids: {sorted(dupes)}")
        return self

    @property
    def is_plannable(self) -> bool:
        """A spec with open clarifications must not proceed to planning.

        Everything downstream inherits the ambiguity, which makes an unclarified spec
        the most expensive artifact in the pipeline.
        """
        return not self.open_clarifications


__all__ = [
    "AcceptanceScenario",
    "Assumption",
    "Priority",
    "Requirement",
    "Spec",
    "SuccessCriterion",
    "UserStory",
]
