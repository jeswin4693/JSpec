"""JSpec MCP server - the same tool surface behind an MCP transport.

STATUS: INERT, deliberately. D-025 defers MCP until after M2: the tool surface ships
first as the `jspec` command (`jspec.cli`), because only one of MCP's three benefits
- *forcing* a response shape rather than requesting it - actually requires it. The
symbol index and the risk arithmetic run identically from a command. `jspec/.mcp.json`
stays on disk but this server does not start; do not read its presence as a working
server.

This module holds no logic of its own. Every tool delegates to `jspec.tools`, which
is the single source of truth for what exists and what each unbuilt tool waits on. A
second status list here would drift, and a drifted list is worse than none: it would
advertise a tool that cannot run.

Three tools are answerable today (classify_task, plan_chain, validate_artifact). The
other seven raise `ToolUnavailable` naming their blocking component.

This server performs NO model calls and needs NO API key (D-006). Claude Code supplies
judgement; this supplies arithmetic, graph queries, validation and state. Tool input
schemas come from `jspec.contracts`, which is how artifacts get enforced structure
without the Anthropic API (D-002).
"""

from __future__ import annotations

from typing import Any

from jspec import tools

# --- routing ---------------------------------------------------------------------


def classify_task(prompt: str) -> dict[str, Any]:
    """Route a raw prompt to T-0..T-3 with confidence, chain, and budgets.

    Wraps `jspec.router.classify`. Deterministic and nearly free - the router must
    never cost a model call.
    """
    return tools.classify_task(prompt)


def plan_chain(
    route: str, profile: str | None = None, skip: list[str] | None = None
) -> dict[str, Any]:
    """The ordered steps for a route under a profile, minus justified skips."""
    return tools.plan_chain(route, profile=profile, skip=skip)


# --- artifacts -------------------------------------------------------------------


def submit_spec(spec: dict) -> dict:
    """Validate against `contracts.spec.Spec`, persist, render markdown.

    Returns `{ok, path, errors}`. Skills must never write spec.md directly - an
    artifact that bypassed validation is untrusted.
    """
    raise tools.unavailable("submit_spec")


def validate_artifact(kind: str, payload: dict) -> dict[str, Any]:
    """Validate any artifact without persisting it. Used by evals and by CI."""
    return tools.validate_artifact(kind, payload)


# --- analysis (deterministic - no model) -----------------------------------------


def blast_radius(symbol: str, path: str | None = None) -> dict:
    """Files and modules importing or calling `symbol`, via the symbol graph.

    This is a graph traversal, not an opinion. It is what makes the risk numbers
    trustworthy enough to gate on (D-003).
    """
    raise tools.unavailable("blast_radius")


def find_existing(intent: str) -> dict:
    """Existing methods/helpers/locators that already do this.

    Reuse enforcement: answers "does this already exist?" before a line is written,
    in milliseconds instead of a manual read-through.
    """
    raise tools.unavailable("find_existing")


def score_risk(work_packages: list[dict]) -> dict:
    """Per-WP risk, DAG propagation, correlation, then one verdict + top 3 drivers."""
    raise tools.unavailable("score_risk")


# --- governance & memory ---------------------------------------------------------


def record_gate(
    wp_id: str,
    decision: str,
    approver: str,
    risk_at_approval: float,
    diff_hash: str,
    evidence_refs: list[str],
) -> dict:
    """Append to `gates.jsonl`. Append-only - never rewrite a past gate."""
    raise tools.unavailable("record_gate")


def record_preference(key: str, value: str, source: str) -> dict:
    """Persist a resolved unknown so it is never asked twice (D-010)."""
    raise tools.unavailable("record_preference")


def record_cost(step: str, tokens: int, usd: float, budget: int) -> dict:
    """Token ledger: budget vs actual, per step, per run.

    The router reads this history to get cheaper over time. What gets measured gets
    reduced - and it is what turns a claim about efficiency into a number.
    """
    raise tools.unavailable("record_cost")


TOOLS = (
    classify_task,
    plan_chain,
    submit_spec,
    validate_artifact,
    blast_radius,
    find_existing,
    score_risk,
    record_gate,
    record_preference,
    record_cost,
)


def main() -> None:
    raise NotImplementedError(
        "The MCP server is deferred until after M2 (D-025). The tool surface ships "
        "as the `jspec` command - run `jspec tools` to see all ten and their status. "
        "Wrap the proven tools in an MCP transport here once M2 lands."
    )


if __name__ == "__main__":
    main()
