"""Risk scoring and roll-up.

STATUS: STUB. Signatures and the maths are specified; bodies are not implemented.
Build step 2. See DECISIONS.md D-004 for why these three rules and not a sum or a max.

Everything in this module is arithmetic. No model calls, ever - paying a model to add
numbers is a design error (D-003).
"""

from __future__ import annotations

from dataclasses import dataclass

LAMBDA_TAIL = 0.15
"""Weight on non-dominant risks. A plain max makes ten trivial risks free; a plain
sum dilutes one severe risk among them. Tune against real outcomes, not taste."""

W_DESCENDANTS = 0.10
"""Weight on downstream exposure per dependent work package. Risk in a foundation
package is worth more than identical risk in a leaf."""

W_CORRELATION = 0.20
"""Amplifier for work packages sharing a file or module. Independent-risk maths
systematically under-reports shared-surface exposure - decisive where shared page
objects and support utilities span several products."""


@dataclass(frozen=True)
class Verdict:
    decision: str  # GO | GO-WITH-GATES | NO-GO
    score: float
    drivers: tuple[str, ...]  # the three that produced the decision
    needs_review: bool


def item_score(
    likelihood: int, impact: int, reversibility: int, detectability: int
) -> float:
    """Single risk item. All inputs 1-5.

    Reversibility and detectability are multipliers, not addends: an irreversible
    change that only production surfaces is categorically worse than a reversible one
    CI catches, at the same likelihood and impact.
    """
    raise NotImplementedError("build step 2")


def wp_risk(item_scores: list[float]) -> float:
    """Dominant + tail: `max(items) + LAMBDA_TAIL * sum(rest)`."""
    raise NotImplementedError("build step 2")


def propagate(
    wp_scores: dict[str, float], depends_on: dict[str, list[str]]
) -> dict[str, float]:
    """Push exposure up the DAG: `own * (1 + W_DESCENDANTS * n_descendants)`.

    Must detect cycles and refuse rather than recurse - a cyclic work-package graph
    is a decomposition bug worth surfacing, not smoothing over.
    """
    raise NotImplementedError("build step 2")


def correlate(
    exposures: dict[str, float], touches: dict[str, list[str]]
) -> dict[str, float]:
    """Amplify work packages whose `touches` sets intersect."""
    raise NotImplementedError("build step 2")


def rollup(
    wp_items: dict[str, list[float]],
    depends_on: dict[str, list[str]],
    touches: dict[str, list[str]],
) -> Verdict:
    """One feature-level verdict plus the top three drivers.

    A verdict without drivers is unusable: nobody can act on a number. The point of
    the roll-up is that a reviewer reads three lines instead of forty work packages.
    """
    raise NotImplementedError("build step 2")


__all__ = [
    "LAMBDA_TAIL",
    "W_CORRELATION",
    "W_DESCENDANTS",
    "Verdict",
    "correlate",
    "item_score",
    "propagate",
    "rollup",
    "wp_risk",
]
