"""Gate contract: one immutable row in the approval ledger.

Gate stringency scales with computed risk (D-005). Uniform gates cause gate fatigue,
and gate fatigue causes rubber-stamping - so low risk auto-approves and logs, while
high risk demands a named human, an impact scan and a rollback plan.

The rule that gives that teeth is enforced here, in the schema, not by convention:
a HIGH-band gate whose approver is automated is rejected outright.

Keep this module free of I/O and of model calls. Appending to `gates.jsonl` is the
MCP server's job; this only defines what a valid row looks like.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from jspec.contracts.base import Evidence
from jspec.contracts.risk import RiskBand

AUTOMATED_APPROVERS = frozenset({"auto", "automatic", "system", "jspec", "claude", ""})
"""Names that do not identify an accountable person. Rejected at HIGH band."""


class GateDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    AUTO_APPROVED = "AUTO_APPROVED"


class Gate(BaseModel):
    """An approval, tied to a specific risk score and a specific diff.

    Every field exists so the row answers one question months later: who allowed
    what, when, against which risk, on exactly which change. An approval that lives
    only in chat scrollback answers none of those and is gone next session.
    """

    wp_id: str = Field(pattern=r"^WP-\d{3}$")
    decision: GateDecision
    band: RiskBand
    approver: str = Field(
        min_length=1,
        description="A person's name or id at HIGH band; may be automated at LOW.",
    )
    timestamp: str = Field(description="ISO 8601; supplied by the caller, never now()")
    risk_at_approval: float = Field(ge=0.0)
    diff_hash: str = Field(
        pattern=r"^[0-9a-f]{64}$",
        description="sha256 of the diff being approved. Binds the approval to a change.",
    )
    evidence_refs: Evidence

    rollback_plan: str | None = Field(
        default=None, description="Required at HIGH band: how this is undone."
    )
    impact_scan_ref: str | None = Field(
        default=None, description="Required at HIGH band: where the blast radius is."
    )

    @model_validator(mode="after")
    def _high_risk_requires_an_accountable_human(self) -> Gate:
        if self.band is not RiskBand.HIGH:
            return self

        if self.approver.strip().lower() in AUTOMATED_APPROVERS:
            raise ValueError(
                f"{self.wp_id}: a HIGH-band gate needs a named human approver, got "
                f"'{self.approver}' - this is the rule the whole ledger exists to "
                f"enforce, so it is checked by the schema, not by convention"
            )
        if self.decision is GateDecision.AUTO_APPROVED:
            raise ValueError(
                f"{self.wp_id}: HIGH band cannot be AUTO_APPROVED"
            )
        missing = [
            name
            for name, value in (
                ("rollback_plan", self.rollback_plan),
                ("impact_scan_ref", self.impact_scan_ref),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"{self.wp_id}: HIGH band requires {missing}")
        return self


__all__ = [
    "AUTOMATED_APPROVERS",
    "Gate",
    "GateDecision",
]
