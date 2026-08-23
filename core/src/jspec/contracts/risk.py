"""Risk contracts: the typed inputs and the typed verdict.

The split here is the determinism boundary in miniature (D-003, constitution rule 14).
The MODEL supplies `likelihood`, `impact`, `reversibility`, `detectability`,
`description`, `mitigation` - all judgement, each carrying evidence. Everything after
that is arithmetic and lives in `jspec.risk`: scoring, DAG propagation, correlation,
and the roll-up that produces a `Verdict`.

A model is never asked for a `Verdict`. That is the point.

Keep this module free of I/O and of model calls.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from jspec.contracts.base import Confidence, Evidence, Id, Score1to5


class Decision(str, Enum):
    GO = "GO"
    GO_WITH_GATES = "GO-WITH-GATES"
    NO_GO = "NO-GO"


class RiskBand(str, Enum):
    """Which gate a work package must pass (D-005). Band boundaries are runtime
    policy and live in `.sdd/config.yaml`; they are deliberately not hardcoded here,
    so tuning thresholds never requires a schema change."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskItem(BaseModel):
    """One scored hazard.

    `category` is a plain string, not an Enum, on purpose: the taxonomy belongs to
    `profiles/*.yaml` (D-011, constitution rule 20). Baking a Playwright or M2M risk
    vocabulary into `core/` would make adding a domain a code change.
    """

    id: Id = Field(pattern=r"^RK-\d{3}$")
    category: str = Field(min_length=2, description="From the active profile's taxonomy")
    description: str = Field(min_length=10)

    likelihood: Score1to5
    impact: Score1to5
    reversibility: Score1to5 = Field(
        description="1 = trivially revertible, 5 = effectively permanent"
    )
    detectability: Score1to5 = Field(
        description="1 = CI catches it immediately, 5 = only production surfaces it"
    )

    mitigation: str = Field(
        min_length=5,
        description="What reduces this. 'Be careful' is not a mitigation.",
    )

    confidence: Confidence
    evidence: Evidence


class Verdict(BaseModel):
    """One feature-level decision, plus the three findings that produced it.

    `drivers` is capped at three deliberately. A verdict without drivers is unusable
    because nobody can act on a bare number, and a verdict with forty is the same
    problem wearing a different hat - the whole point of the roll-up is that a
    reviewer reads three lines instead of forty work packages.
    """

    decision: Decision
    score: float = Field(ge=0.0)
    drivers: list[str] = Field(max_length=3)
    needs_review: bool = False

    @model_validator(mode="after")
    def _non_trivial_verdicts_explain_themselves(self) -> Verdict:
        if self.decision is not Decision.GO and not self.drivers:
            raise ValueError(
                f"{self.decision.value} requires at least one driver - a verdict that "
                f"blocks or gates work must say what drove it"
            )
        return self


__all__ = [
    "Decision",
    "RiskBand",
    "RiskItem",
    "Verdict",
]
