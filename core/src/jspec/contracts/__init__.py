"""Artifact contracts. Pydantic models -> JSON Schema. No I/O, no model calls.

`KINDS` is the single mapping from artifact kind to model. Both consumers read it:

  - MCP tool input schemas, for in-session work
  - `claude -p --output-format json --json-schema`, for headless runs and evals

Both, because neither requires an API key (D-006, constitution rule 16). Two separate
mappings would drift, and a drifted schema registry fails silently - the wrong shape
validates against the wrong model and nobody finds out until an artifact is already
downstream.

Contracts for later phases (`Review`, `Drift`, `Fix`, `Clarifications`) are not here
yet; they arrive with the phases that produce them, so `KINDS` never advertises a
schema nothing can emit.
"""

from __future__ import annotations

from pydantic import BaseModel

from jspec.contracts.base import (
    AcceptanceScenario,
    Confidence,
    Evidence,
    Id,
    Score1to5,
)
from jspec.contracts.gate import Gate, GateDecision
from jspec.contracts.graph import (
    FileSymbols,
    Reference,
    ReferenceKind,
    Resolution,
    Symbol,
    SymbolKind,
)
from jspec.contracts.plan import Plan, WorkPackage
from jspec.contracts.profile import Basis, Finding, Profile, ProfileDraft, Validation
from jspec.contracts.risk import Decision, RiskBand, RiskItem, Verdict
from jspec.contracts.routing import Classification, Route
from jspec.contracts.spec import (
    Assumption,
    Priority,
    Requirement,
    Spec,
    SuccessCriterion,
    UserStory,
)

KINDS: dict[str, type[BaseModel]] = {
    "classification": Classification,
    "profile": Profile,
    # C-26. Hand-edited by a person between `draft` and `accept`, so the loader
    # validates it - which is the live consumer that earns it an entry.
    "profile_draft": ProfileDraft,
    "spec": Spec,
    "plan": Plan,
    "work_package": WorkPackage,
    "risk_item": RiskItem,
    "verdict": Verdict,
    "gate": Gate,
    # C-06's output. Registered because C-07 mirrors these two as its table rows,
    # so one shape defines the contract, the schema and the columns. `FileSymbols`
    # is not registered: it is the per-file container C-06 returns, and nothing
    # downstream validates one on its own - the bar for a KINDS entry is a live
    # consumer, not a plausible one.
    "symbol": Symbol,
    "reference": Reference,
}


def json_schema(kind: str) -> dict[str, object]:
    """JSON Schema for one artifact kind.

    Raises KeyError naming the known kinds - a typo'd kind should fail loudly here
    rather than produce an empty schema that validates everything.
    """
    try:
        model = KINDS[kind]
    except KeyError:
        raise KeyError(
            f"unknown artifact kind {kind!r}; known kinds: {sorted(KINDS)}"
        ) from None
    return model.model_json_schema()


__all__ = [
    "KINDS",
    "AcceptanceScenario",
    "Assumption",
    "Basis",
    "Classification",
    "Confidence",
    "Decision",
    "Evidence",
    "FileSymbols",
    "Finding",
    "Gate",
    "GateDecision",
    "Id",
    "Plan",
    "Priority",
    "Profile",
    "ProfileDraft",
    "Reference",
    "ReferenceKind",
    "Requirement",
    "Resolution",
    "RiskBand",
    "RiskItem",
    "Route",
    "Score1to5",
    "Spec",
    "SuccessCriterion",
    "Symbol",
    "SymbolKind",
    "UserStory",
    "Validation",
    "Verdict",
    "WorkPackage",
    "json_schema",
]
