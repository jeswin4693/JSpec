"""Deterministic task router.

Classifies a raw user prompt into a route (T-0..T-3) using regex signals, git state,
and history - no model call. The model adjudicates only when confidence is low
(D-009). Routing that costs tokens defeats the point.

The most valuable thing the router does is choose the SHALLOW route. Running a full
spec pipeline on a one-line fix costs more than it saves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from jspec.contracts.routing import Route

CONFIDENCE_FLOOR = 0.6
"""Below this, the caller asks the model to adjudicate and must state which signals
it weighed."""

EVIDENCE_SATURATION = 3.0
"""Total signal weight at which we consider the evidence complete. Below it,
confidence is scaled down even when one route wins by a mile - a single weak signal
is a wide margin over nothing and still tells us almost nothing."""


# Route itself is data and lives in `jspec.contracts.routing`, imported above and
# re-exported here so existing callers keep working. The tables below are policy and
# stay in the router: which steps a depth runs, and what it may spend.
CHAINS: dict[Route, tuple[str, ...]] = {
    Route.T0_TRIVIAL: ("impact", "fix", "verify"),
    Route.T1_FIX: ("reproduce", "root_cause", "impact", "fix", "regression"),
    Route.T2_FEATURE: (
        "specify",
        "clarify",
        "plan",
        "decompose",
        "risk",
        "gate",
        "implement",
        "review",
    ),
    Route.T3_SWEEP: ("discover", "fan_out", "verify_each", "rollup"),
}

QUESTION_BUDGET: dict[Route, int] = {
    Route.T0_TRIVIAL: 0,
    Route.T1_FIX: 1,
    Route.T2_FEATURE: 3,
    Route.T3_SWEEP: 2,
}

TOKEN_BUDGET: dict[Route, int] = {
    Route.T0_TRIVIAL: 900,
    Route.T1_FIX: 2600,
    Route.T2_FEATURE: 9000,
    Route.T3_SWEEP: 7000,
}

# --- signal patterns -------------------------------------------------------------
# Weights are deliberately coarse. Precision here is false precision; the point is
# to be confidently right on the easy majority and defer the rest.

WORK_ITEM = re.compile(r"\b(?:ADO|AB#|JIRA|GH)[-# ]?(\d{3,})\b", re.IGNORECASE)
STACK_TRACE = re.compile(
    r"(?:^\s+at\s+\S+|Traceback \(most recent call last\)|"
    r"\w+Error:|\w+Exception:|expect\(.+\)\.to|Timeout \d+ms exceeded)",
    re.MULTILINE,
)
# Shape, not vocabulary: a stem, optional path segments, then a 2-6 character
# extension beginning with a letter. The previous version enumerated ten
# languages, which put domain knowledge in core/ (constitution rule 20) and
# silently failed to recognise every language that was not on the list. The
# length floor on the extension is what keeps prose out: "e.g.", "i.e." and
# "U.S.A." have one-character suffixes, and requiring a leading letter rejects
# "3.13" and "v1.2.3". A method call such as `obj.save` does still match; the
# bump it earns is toward T-0, which is the right direction for a prompt naming
# one small thing, and fix or feature vocabulary in the same prompt outweighs it.
FILE_PATH = re.compile(r"\b[\w-]+(?:[./\\][\w-]+)*\.[A-Za-z][A-Za-z0-9]{1,5}\b")

FIX_WORDS = re.compile(
    r"\b(fix|failing|fails|failed|broken|break(?:ing)?|bug|error|crash|"
    r"regress\w*|flaky|why is|not working|wrong)\b",
    re.IGNORECASE,
)
FEATURE_WORDS = re.compile(
    r"\b(add|create|implement|build|new|support for|introduce|enable|design)\b",
    re.IGNORECASE,
)
SWEEP_WORDS = re.compile(
    r"\b(all|every|across|each of the|bulk|everywhere|throughout|"
    r"whole (?:repo|suite|codebase)|migrate)\b",
    re.IGNORECASE,
)
TRIVIAL_WORDS = re.compile(
    r"\b(rename|typo|bump|comment|log message|constant|import|"
    r"one[- ]liner|small change)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RepoState:
    """Facts the caller supplies from git and the code graph - never guessed here."""

    dirty: bool = False
    failing_tests: int = 0
    estimated_files_touched: int | None = None
    recent_routes: tuple[Route, ...] = ()
    """This user's last N routes, newest first - habit is a real signal."""


@dataclass
class Classification:
    route: Route
    confidence: float
    signals: list[str] = field(default_factory=list)

    @property
    def chain(self) -> tuple[str, ...]:
        return CHAINS[self.route]

    @property
    def question_budget(self) -> int:
        return QUESTION_BUDGET[self.route]

    @property
    def token_budget(self) -> int:
        return TOKEN_BUDGET[self.route]

    @property
    def needs_model_adjudication(self) -> bool:
        return self.confidence < CONFIDENCE_FLOOR

    def to_dict(self) -> dict[str, object]:
        return {
            "route": self.route.value,
            "confidence": round(self.confidence, 2),
            "chain": list(self.chain),
            "question_budget": self.question_budget,
            "token_budget": self.token_budget,
            "signals": self.signals,
            "needs_model_adjudication": self.needs_model_adjudication,
        }


def classify(prompt: str, repo: RepoState | None = None) -> Classification:
    """Score a prompt against each route. Highest score wins; margin sets confidence."""
    repo = repo or RepoState()
    scores: dict[Route, float] = dict.fromkeys(Route, 0.0)
    signals: list[str] = []

    def bump(route: Route, weight: float, why: str) -> None:
        scores[route] += weight
        signals.append(f"{why} (+{weight:g} {route.value})")

    if STACK_TRACE.search(prompt):
        bump(Route.T1_FIX, 3.0, "stack trace or assertion text present")
    if FIX_WORDS.search(prompt):
        bump(Route.T1_FIX, 1.5, "failure vocabulary")
    if FEATURE_WORDS.search(prompt):
        bump(Route.T2_FEATURE, 1.5, "creation vocabulary")
    if SWEEP_WORDS.search(prompt):
        bump(Route.T3_SWEEP, 2.0, "breadth vocabulary")
    if TRIVIAL_WORDS.search(prompt):
        bump(Route.T0_TRIVIAL, 1.5, "small-change vocabulary")

    if WORK_ITEM.search(prompt):
        # A tracked item is usually specified work, but a filed bug is still a fix.
        bump(Route.T2_FEATURE, 1.0, "work item reference")
    if len(FILE_PATH.findall(prompt)) == 1:
        bump(Route.T0_TRIVIAL, 1.0, "exactly one file named")

    # Prompt length: a one-line ask is rarely a feature.
    words = len(prompt.split())
    if words <= 12:
        bump(Route.T0_TRIVIAL, 0.5, f"terse prompt ({words} words)")
    elif words >= 60:
        bump(Route.T2_FEATURE, 0.5, f"detailed prompt ({words} words)")

    # Repo facts outrank vocabulary - they are measured, not inferred.
    if repo.failing_tests > 0:
        bump(Route.T1_FIX, 2.0, f"{repo.failing_tests} failing test(s) on record")
    n = repo.estimated_files_touched
    if n is not None:
        if n <= 1:
            bump(Route.T0_TRIVIAL, 2.0, "graph estimate: <=1 file touched")
        elif n >= 15:
            bump(Route.T3_SWEEP, 2.0, f"graph estimate: {n} files touched")
        elif n >= 5:
            bump(Route.T2_FEATURE, 1.0, f"graph estimate: {n} files touched")
    if repo.recent_routes:
        habit = repo.recent_routes[0]
        bump(habit, 0.5, f"user's most recent route was {habit.value}")

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, best_score), (_, runner_up) = ranked[0], ranked[1]

    if best_score == 0.0:
        # Nothing matched. Do not invent a route - defer, and default shallow so a
        # wrong guess is cheap rather than expensive.
        return Classification(Route.T1_FIX, 0.0, ["no signals matched"])

    # Confidence needs BOTH a clear winner and enough evidence to trust the win.
    # Margin alone is not enough: a lone 0.5-weight signal beats an empty field by a
    # wide margin while telling us almost nothing, and would otherwise score 0.95.
    margin = (best_score - runner_up) / (best_score * 2)  # 0..0.5
    strength = min(1.0, best_score / EVIDENCE_SATURATION)  # 0..1
    confidence = min(0.95, (0.5 + margin) * strength)
    return Classification(best, confidence, signals)


def plan_chain(classification: Classification, skip: tuple[str, ...] = ()) -> list[str]:
    """The ordered steps to run, minus any the caller has justified skipping.

    Skips must be reported to the user (`skipped and why`). A silently shortened
    chain reads as full coverage when it wasn't.
    """
    return [step for step in classification.chain if step not in skip]


__all__ = [
    "CHAINS",
    "CONFIDENCE_FLOOR",
    "Classification",
    "RepoState",
    "Route",
    "classify",
    "plan_chain",
]
