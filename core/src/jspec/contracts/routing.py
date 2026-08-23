"""Routing contracts: the four depths, and the serialised classification artifact.

`Route` lives here rather than in `jspec.router` because it is data, not logic - the
router's CHAINS, QUESTION_BUDGET and TOKEN_BUDGET tables are policy and stay there,
but the four depths themselves are referenced by contracts, templates, profiles and
the MCP tool schema. One definition, imported everywhere.

Two representations of a classification exist on purpose, at different layers:

  - `jspec.router.Classification` - a dataclass with computed properties; the
    in-process result of classifying, cheap to build and never serialised directly.
  - `Classification` here - the flat artifact that crosses the MCP boundary. It is
    exactly what `router.Classification.to_dict()` produces, and validating that
    output against this model is what keeps the two from drifting.

Keep this module free of I/O and of model calls.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from jspec.contracts.base import Confidence


class Route(str, Enum):
    """How much process a request deserves.

    The router's most valuable decision is choosing the shallow one. An autopilot
    that always runs the full pipeline is a token liability, so these are judged on
    tokens-per-accepted-outcome, never on how much of the pipeline they exercised
    (D-009).
    """

    T0_TRIVIAL = "T-0"
    T1_FIX = "T-1"
    T2_FEATURE = "T-2"
    T3_SWEEP = "T-3"


class Classification(BaseModel):
    """The routing decision, as it crosses the MCP boundary."""

    route: Route
    confidence: Confidence
    chain: list[str] = Field(min_length=1, description="Ordered steps for this route")
    question_budget: int = Field(ge=0)
    token_budget: int = Field(gt=0)
    signals: list[str] = Field(
        default_factory=list,
        description="Which signals fired, and their weights. Shown when adjudicating.",
    )
    needs_model_adjudication: bool = False

    @model_validator(mode="after")
    def _low_confidence_must_be_flagged(self) -> Classification:
        """A route the router is unsure of must say so.

        Silently returning a low-confidence route reads as certainty to every caller
        downstream, and the whole escalation path (D-003: below threshold, escalate)
        depends on this flag being honest.
        """
        if self.confidence < 0.6 and not self.needs_model_adjudication:
            raise ValueError(
                f"confidence {self.confidence} is below the floor but "
                f"needs_model_adjudication is False - a route this uncertain must be "
                f"escalated, not returned as if it were settled"
            )
        return self


__all__ = [
    "Classification",
    "Route",
]
