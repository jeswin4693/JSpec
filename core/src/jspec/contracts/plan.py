"""Plan contracts: the HOW, and its decomposition into shippable pieces.

A `Spec` says what and why; a `Plan` says how. The split matters because technology
leaking into a spec is the most expensive defect in the pipeline - every downstream
artifact inherits it - so the plan is where framework names, file paths and schema
design are finally allowed.

Keep this module free of I/O and of model calls.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from jspec.contracts.base import AcceptanceScenario, Confidence, Evidence, Id
from jspec.contracts.risk import RiskItem


def _find_cycle(edges: dict[str, list[str]]) -> list[str] | None:
    """Return one cycle as a path, or None. Three-colour DFS.

    Returned so the error message can name the actual loop - "there is a cycle"
    sends someone hunting through forty work packages; "WP-003 -> WP-007 -> WP-003"
    does not.
    """
    white, grey, black = 0, 1, 2
    colour = dict.fromkeys(edges, white)
    path: list[str] = []

    def visit(node: str) -> list[str] | None:
        colour[node] = grey
        path.append(node)
        for nxt in edges.get(node, ()):
            if colour.get(nxt) == grey:
                return [*path[path.index(nxt) :], nxt]
            if colour.get(nxt) == white:
                found = visit(nxt)
                if found:
                    return found
        path.pop()
        colour[node] = black
        return None

    for node in edges:
        if colour[node] == white:
            found = visit(node)
            if found:
                return found
    return None


class WorkPackage(BaseModel):
    """A unit of work that can be gated, risked and shipped on its own."""

    id: Id = Field(pattern=r"^WP-\d{3}$")
    title: str = Field(min_length=3, max_length=120)
    intent: str = Field(min_length=10, description="Why this package exists at all")

    depends_on: list[str] = Field(
        default_factory=list,
        description="WP ids that must land first. These edges form the DAG.",
    )
    touches: list[str] = Field(
        default_factory=list,
        description=(
            "Files or modules this package modifies. This is the correlation key: "
            "packages sharing entries here are treated as correlated rather than "
            "independent, because independent-risk maths systematically under-reports "
            "shared-surface exposure (D-004)."
        ),
    )

    subtasks: list[str] = Field(default_factory=list)
    acceptance: list[AcceptanceScenario] = Field(min_length=1)

    parallel_safe: bool = Field(
        default=False,
        description=(
            "The [P] marker. Computed from disjoint `touches`, never asked of the "
            "model - whether two file sets intersect is arithmetic, not judgement."
        ),
    )
    estimated_files_touched: int = Field(default=0, ge=0)

    risks: list[RiskItem] = Field(default_factory=list)

    @model_validator(mode="after")
    def _no_self_dependency(self) -> WorkPackage:
        if self.id in self.depends_on:
            raise ValueError(f"{self.id}: a work package cannot depend on itself")
        return self


class Plan(BaseModel):
    """An approach plus the DAG of work packages that realises it."""

    feature_slug: str = Field(pattern=r"^\d{3}-[a-z0-9-]+$")
    spec_ref: str = Field(description="Path or id of the Spec this plan implements")
    created: str = Field(description="ISO date; supplied by the caller, never now()")

    approach: str = Field(min_length=20, description="The chosen HOW")
    alternatives_considered: list[str] = Field(
        default_factory=list,
        description=(
            "What was weighed and rejected. A plan with no alternatives was not a "
            "decision, it was the first idea written down."
        ),
    )
    non_goals: list[str] = Field(default_factory=list)

    work_packages: list[WorkPackage] = Field(min_length=1)

    confidence: Confidence
    evidence: Evidence

    @model_validator(mode="after")
    def _dag_is_wellformed(self) -> Plan:
        ids = [wp.id for wp in self.work_packages]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate work package ids: {sorted(dupes)}")

        known = set(ids)
        edges: dict[str, list[str]] = {}
        for wp in self.work_packages:
            unknown = sorted(d for d in wp.depends_on if d not in known)
            if unknown:
                raise ValueError(
                    f"{wp.id}: depends_on references unknown work packages: {unknown}"
                )
            edges[wp.id] = list(wp.depends_on)

        cycle = _find_cycle(edges)
        if cycle:
            raise ValueError(
                "dependency cycle in work packages: "
                + " -> ".join(cycle)
                + " - refuse rather than recurse; a cyclic decomposition is a real "
                "bug worth surfacing, not something to smooth over"
            )
        return self

    @property
    def roots(self) -> list[str]:
        """Packages with no dependencies - where implementation can start today."""
        return [wp.id for wp in self.work_packages if not wp.depends_on]


__all__ = [
    "Plan",
    "WorkPackage",
]
