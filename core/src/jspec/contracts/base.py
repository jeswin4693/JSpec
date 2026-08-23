"""Primitives shared by every artifact contract.

These live here rather than inside any one artifact module because they are not
spec-specific: a gate row, a risk item and a work package all need `Evidence`, and
three separate definitions of "at least one citation" would drift apart within a
month (constitution rule 2 - do not create duplicate functionality).

Keep this module free of I/O and of model calls.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, Field

Id = Annotated[str, Field(min_length=3, max_length=16)]

Evidence = Annotated[list[str], Field(min_length=1)]
"""At least one `path:line` or quoted source. A judgement without evidence is not
admissible (D-003, constitution rule 15)."""

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]

Score1to5 = Annotated[int, Field(ge=1, le=5)]
"""Risk inputs are a 1-5 ordinal. Finer granularity here is false precision - the
model cannot reliably distinguish a 63 from a 67, and pretending otherwise makes the
downstream arithmetic look more trustworthy than it is."""


class AcceptanceScenario(BaseModel):
    """Given/When/Then. Split into three fields so it can be checked, not just read."""

    given: str = Field(min_length=3)
    when: str = Field(min_length=3)
    then: str = Field(min_length=3)


__all__ = [
    "AcceptanceScenario",
    "Confidence",
    "Evidence",
    "Id",
    "Score1to5",
]
