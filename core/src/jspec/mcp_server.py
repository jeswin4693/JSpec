"""JSpec MCP server - the deterministic half of the system.

STATUS: STUB. Tool signatures are settled; bodies are not implemented. Build step 3.

This server performs NO model calls and needs NO API key (D-006). Claude Code supplies
judgement; this supplies arithmetic, graph queries, validation, and state. Tool input
schemas are generated from `jspec.contracts`, which is how artifacts get enforced
structure without the Anthropic API (D-002).

Run as: python -m jspec.mcp_server   (see jspec/.mcp.json)
"""

from __future__ import annotations

# --- routing ---------------------------------------------------------------------


def classify_task(prompt: str) -> dict:
    """Route a raw prompt to T-0..T-3 with confidence, chain, and budgets.

    Wraps `jspec.router.classify`, supplying RepoState from git and the code graph.
    Deterministic and nearly free - the router must never cost a model call.
    """
    raise NotImplementedError("build step 3")


def plan_chain(route: str, profile: str, skip: list[str] | None = None) -> dict:
    """The ordered steps for a route under a profile, minus justified skips."""
    raise NotImplementedError("build step 3")


# --- artifacts -------------------------------------------------------------------


def submit_spec(spec: dict) -> dict:
    """Validate against `contracts.spec.Spec`, persist, render markdown.

    Returns `{ok, path, errors}`. Skills must never write spec.md directly - an
    artifact that bypassed validation is untrusted.
    """
    raise NotImplementedError("build step 3")


def validate_artifact(kind: str, payload: dict) -> dict:
    """Validate any artifact without persisting it. Used by evals and by CI."""
    raise NotImplementedError("build step 3")


# --- analysis (deterministic - no model) -----------------------------------------


def blast_radius(symbol: str, path: str | None = None) -> dict:
    """Files and modules importing or calling `symbol`, via the symbol graph.

    This is a graph traversal, not an opinion. It is what makes the risk numbers
    trustworthy enough to gate on (D-003).
    """
    raise NotImplementedError("build step 6")


def find_existing(intent: str) -> dict:
    """Existing methods/helpers/locators that already do this.

    Reuse enforcement: answers "does this already exist?" before a line is written,
    in milliseconds instead of a manual read-through.
    """
    raise NotImplementedError("build step 6")


def score_risk(work_packages: list[dict]) -> dict:
    """Per-WP risk, DAG propagation, correlation, then one verdict + top 3 drivers."""
    raise NotImplementedError("build step 8")


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
    raise NotImplementedError("build step 9")


def record_preference(key: str, value: str, source: str) -> dict:
    """Persist a resolved unknown so it is never asked twice (D-010)."""
    raise NotImplementedError("build step 3")


def record_cost(step: str, tokens: int, usd: float, budget: int) -> dict:
    """Token ledger: budget vs actual, per step, per run.

    The router reads this history to get cheaper over time. What gets measured gets
    reduced - and it is what turns a claim about efficiency into a number.
    """
    raise NotImplementedError("build step 4")


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
        "MCP server not implemented yet - build step 3. "
        "Contracts (contracts/spec.py) and the router (router.py) are done; wire "
        "them to an MCP transport here."
    )


if __name__ == "__main__":
    main()
