"""The tool surface: facts a skill can ask for, and the registry of what exists.

A tool returns **ground truth, never an opinion**. The moment one starts returning
judgement, a second model call is hidden behind an API and the audit trail is gone -
which is the whole reason the deterministic half of this system exists (D-003).

Ten tools are specified. Five are implemented here, because five are all that the
built components can answer honestly:

    classify_task     <- jspec.router          (C-02, built)
    plan_chain        <- jspec.router          (C-02, built)
    validate_artifact <- jspec.contracts.KINDS (C-01, built)
    find_existing     <- jspec.graph.store     (C-07, built)
    blast_radius      <- jspec.graph.traverse  (C-08, built)

The other five raise `ToolUnavailable` naming the component they wait on. That is a
deliberate choice over returning something plausible: a missing tool gets built, a
lying tool gets trusted. Placeholder data here would flow into a risk score and out
to a gate, and nothing downstream could tell it from a measurement.

`REGISTRY` is the single source of truth for what exists. `jspec.mcp_server` is the
same ten tools behind an MCP transport, deferred until after M2 (D-025); it reads
its status from here rather than keeping a second list that would drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from jspec.contracts import KINDS
from jspec.profiles import ProfileError, load
from jspec.router import CHAINS, Classification, RepoState, Route
from jspec.router import classify as _classify
from jspec.router import plan_chain as _plan_chain


class ToolUnavailable(RuntimeError):
    """A specified tool whose engine is not built yet. Names what it waits on."""


@dataclass(frozen=True)
class Tool:
    """One entry in the tool surface."""

    name: str
    summary: str
    blocked_by: str | None = None
    reason: str = ""

    @property
    def ready(self) -> bool:
        return self.blocked_by is None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "summary": self.summary,
            "status": "ready" if self.ready else "blocked",
            "blocked_by": self.blocked_by,
            "reason": self.reason or None,
        }


REGISTRY: tuple[Tool, ...] = (
    Tool(
        "classify_task",
        "Route a raw prompt to T-0..T-3 with confidence, chain and budgets.",
    ),
    Tool(
        "plan_chain",
        "The ordered steps for a route, minus justified skips.",
    ),
    Tool(
        "validate_artifact",
        "Validate any artifact against its contract, without persisting it.",
    ),
    Tool(
        "submit_spec",
        "Validate a spec, persist it, render markdown.",
        blocked_by="C-14",
        reason="needs the specify step and a renderer; arrives with C-12/C-14",
    ),
    Tool(
        "blast_radius",
        "What a change to a name or file affects, or what it relies on: certain and "
        "possible kept apart, depth reported.",
    ),
    Tool(
        "find_existing",
        "Existing helpers that already do this, before a line is written.",
    ),
    Tool(
        "score_risk",
        "Per-package risk, DAG propagation, correlation, one verdict + 3 drivers.",
        blocked_by="C-16",
        reason="risk.py has its formulas in docstrings and five empty functions",
    ),
    Tool(
        "record_gate",
        "Append an approval to the gate ledger. Append-only.",
        blocked_by="C-17",
        reason="needs .sdd/gates.jsonl and the risk bands that price a gate",
    ),
    Tool(
        "record_preference",
        "Persist a resolved unknown so it is never asked twice (D-010).",
        blocked_by="C-05",
        reason="storage path unresolved: skills/router/SKILL.md says "
        ".jspec/preferences.yaml, the repo layout says .sdd/ - needs a decision",
    ),
    Tool(
        "record_cost",
        "Token ledger: budget vs actual, per step, per run.",
        blocked_by="C-24",
        reason="needs .sdd/metrics/tokens.jsonl, which config.yaml declares but "
        "nothing creates",
    ),
)

BY_NAME: dict[str, Tool] = {tool.name: tool for tool in REGISTRY}


def describe() -> dict[str, Any]:
    """The whole surface with per-tool status. What `jspec tools` prints."""
    ready = [t for t in REGISTRY if t.ready]
    return {
        "total": len(REGISTRY),
        "ready": len(ready),
        "blocked": len(REGISTRY) - len(ready),
        "tools": [t.as_dict() for t in REGISTRY],
    }


def unavailable(name: str) -> ToolUnavailable:
    """The error a specified-but-unbuilt tool raises."""
    tool = BY_NAME.get(name)
    if tool is None:
        return ToolUnavailable(f"unknown tool {name!r}; known tools: {sorted(BY_NAME)}")
    return ToolUnavailable(
        f"{name} is specified but not built: it waits on {tool.blocked_by} "
        f"({tool.reason}). Returning a placeholder here would put invented data "
        f"into a risk score, so it raises instead."
    )


# --- the four that are answerable today ------------------------------------------


def classify_task(
    prompt: str,
    *,
    dirty: bool = False,
    failing_tests: int = 0,
    files_touched: int | None = None,
) -> dict[str, Any]:
    """Route a prompt. Deterministic - no model call, and none is wanted.

    Repo facts are passed in rather than discovered here: the router's docstring is
    explicit that `RepoState` holds facts "supplied by the caller from git and the
    code graph - never guessed here". Guessing them inside the tool would make the
    same prompt classify differently depending on which directory it ran from.
    """
    state = RepoState(
        dirty=dirty,
        failing_tests=failing_tests,
        estimated_files_touched=files_touched,
    )
    return _classify(prompt, state).to_dict()


def plan_chain(
    route: str,
    profile: str | None = None,
    skip: list[str] | None = None,
) -> dict[str, Any]:
    """The ordered steps for a route, minus justified skips.

    `profile` is resolved and reported but does **not** yet alter step selection -
    no component makes the chain profile-dependent. It is accepted because loading
    it here catches a misspelled profile at the start of a run rather than six steps
    in, and because the run needs to record which profile it used. When something
    does vary the chain by profile, this is where it goes.

    An unknown skip is an error, not a no-op. Silently ignoring one leaves the
    caller believing they skipped a step that in fact ran.
    """
    try:
        route_enum = Route(route)
    except ValueError:
        raise ValueError(
            f"unknown route {route!r}; expected one of {[r.value for r in Route]}"
        ) from None

    requested = list(skip or [])
    chain = CHAINS[route_enum]
    unknown = [step for step in requested if step not in chain]
    if unknown:
        raise ValueError(f"cannot skip {unknown}: not in the {route} chain {list(chain)}")

    resolved_profile = None
    if profile is not None:
        # Raises ProfileError, which the CLI reports as a usage error. Failing here
        # is the point: a typo'd profile name should stop the run immediately.
        resolved_profile = load(profile).name

    # The route was supplied, not inferred, so confidence is not a claim about a
    # judgement - it records that nothing here had to guess.
    classification = Classification(
        route=route_enum,
        confidence=1.0,
        signals=["route supplied by the caller, not inferred"],
    )
    steps = _plan_chain(classification, tuple(requested))
    return {
        "route": route,
        "profile": resolved_profile,
        "steps": steps,
        "skipped": requested,
        "question_budget": classification.question_budget,
        "token_budget": classification.token_budget,
    }


def validate_artifact(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate an artifact against its contract. Does not persist anything.

    Returns the verdict rather than raising, because "this artifact is invalid" is
    an answer the caller acts on - it fixes the artifact and resubmits. An unknown
    *kind*, by contrast, is a caller bug and does raise.
    """
    try:
        model = KINDS[kind]
    except KeyError:
        raise KeyError(
            f"unknown artifact kind {kind!r}; known kinds: {sorted(KINDS)}"
        ) from None

    from pydantic import ValidationError

    try:
        model.model_validate(payload)
    except ValidationError as exc:
        return {
            "ok": False,
            "kind": kind,
            "errors": [
                {
                    "field": ".".join(str(p) for p in err["loc"]) or "<root>",
                    "problem": err["msg"],
                }
                for err in exc.errors()
            ],
        }
    return {"ok": True, "kind": kind, "errors": []}


def find_existing(
    query: str,
    *,
    root: str = ".",
    kind: str | None = None,
    module: str | None = None,
    limit: int = 20,
) -> dict[str, Any]:
    """What already exists with this name or close to it, from the symbol store.

    The reuse question, answered from an index instead of from memory. This is the
    tool that makes "search before you write a new helper" cheap enough to be
    habitual - 0.5ms against a 9,000-symbol index, versus a model recalling what it
    thinks the repository contains.

    Two rungs, cheapest first, and the answer says which one replied: an exact name
    match, then full-text prefix search only if exact found nothing. That ordering
    is C-09's ladder in miniature - the expensive method is the fallback, never the
    opening move. `mode` is in the payload because "no exact match, but here are
    six similarly named things" and "here is the exact thing" are different answers
    and a caller must not confuse them.

    An unindexed root raises rather than returning an empty list: "nothing found"
    and "nothing looked" are indistinguishable to a reader, and the second one is a
    missing step, not a fact about the repository.
    """
    from pathlib import Path

    from jspec.graph.store import open_store

    with open_store(Path(root), create=False) as store:
        store.require_indexed(f"run `jspec index {root} --profile <name>` first")
        rows = store.lookup(query, kind=kind, module=module, limit=limit)
        mode = "exact"
        if not rows and store.full_text_search:
            rows = [
                row
                for row in store.search(query, limit=limit)
                if (kind is None or row["kind"] == kind)
                and (module is None or row["module"] == module)
            ]
            mode = "text"
        return {
            "query": query,
            "root": Path(root).resolve().as_posix(),
            "mode": mode,
            "matches": len(rows),
            "rows": rows,
        }


def blast_radius(
    target: str,
    *,
    root: str = ".",
    file: str | None = None,
    direction: str = "dependents",
    depth: int | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    """What is affected if `target` changes - or what it relies on.

    A fact from the graph, not an opinion (D-003). `target` is a definition name or an
    indexed file path; `direction` is `dependents` (who is affected) or `dependencies`
    (what it uses). Every result is `certain` or `possible`, the depth searched is
    always reported, and a search cut short says so - see `jspec.graph.traverse`.

    Like `find_existing`, an unindexed root raises rather than answering `[]`: "no
    dependents" and "nothing was looked at" must never read the same.
    """
    from pathlib import Path

    from jspec.graph.store import open_store
    from jspec.graph.traverse import DEFAULT_DEPTH
    from jspec.graph.traverse import blast_radius as _blast_radius

    with open_store(Path(root), create=False) as store:
        return _blast_radius(
            store,
            target,
            file=file,
            direction=direction,
            depth=DEFAULT_DEPTH if depth is None else depth,
            limit=limit,
        )


__all__ = [
    "BY_NAME",
    "REGISTRY",
    "ProfileError",
    "Tool",
    "ToolUnavailable",
    "blast_radius",
    "classify_task",
    "describe",
    "find_existing",
    "plan_chain",
    "unavailable",
    "validate_artifact",
]
