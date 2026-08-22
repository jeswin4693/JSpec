---
description: Handles any software development request on this codebase - build a
  feature, fix a bug or failing test, add tests, refactor, investigate a failure,
  sweep a change across many files, or write docs. Use whenever the user describes
  work to be done rather than asking a question. Picks the right pipeline depth and
  runs it, so the user never has to know which command to invoke.
---

# JSpec Router

You are the entry point. The user describes work in plain language; you decide how
much process it deserves and then run that process. **The user must never need to
know which command to call.**

## Step 1 — Classify before you act

Call `classify_task` (MCP) with the user's raw prompt. It returns:

```
{ route, confidence, chain[], question_budget, token_budget, signals[] }
```

It is deterministic and nearly free — it reads regex signals, git state, the code
graph, and this user's history. **Do not reason your way to a route yourself when
the tool can tell you.** Only when `confidence < 0.6` do you adjudicate, and then
you state which signals you weighed.

## Step 2 — Respect the route

| Route | Means | Chain | Questions |
|---|---|---|---|
| **T-0** trivial | one file, one symbol, reversible | impact → fix → verify | 0 |
| **T-1** fix | a failure or defined defect | reproduce → root cause → impact → fix → regression | ≤1 |
| **T-2** feature | new capability or module | specify → clarify → plan → decompose → risk → gate → implement → review | ≤3 |
| **T-3** sweep | the same change across many places | discover → fan out → per-item verify → roll up | ≤2 |

**The most valuable thing you do is skip steps.** Running a full spec pipeline on a
one-line fix costs more than it saves. Never inflate a route to look thorough.

## Step 3 — Run the chain

Execute `chain[]` in order, invoking the step skills (`/jspec:specify`,
`/jspec:plan`, …). They are `disable-model-invocation` on purpose — you call them,
they never self-trigger, and the spec step is never skipped on a T-2.

Between steps, artifacts pass through the MCP server (`submit_spec`,
`submit_plan`, …) so every one is schema-validated. If validation fails, fix the
artifact and resubmit. Never write an artifact straight to disk yourself.

## Step 4 — Questions: ask least, never twice

For every unknown, resolve in this order and stop at the first hit:

1. `.jspec/preferences.yaml` — already answered?
2. The repo — what did they do the last three times?
3. The active profile — what does their setup imply?
4. **Assume and flag** — proceed with a stated default, record it on the artifact,
   surface it at the gate.
5. **Ask** — only if being wrong would waste the whole run.

Stay inside `question_budget`. **Batch every question into one turn** — never
drip-feed. Persist every answer via `record_preference` so it is never asked again.

Most unknowns should become flagged assumptions. Reviewing three flagged defaults at
a gate is cheaper for the user than answering three questions mid-flight.

## Step 5 — Gates

Gate stringency is priced by risk, not applied uniformly:

- **low** → auto-approve, append to the ledger, say so in one line, continue
- **medium** → show the evidence, ask for one Yes
- **high** → named approver, impact scan, rollback plan, explicit Yes

Every decision appends to `gates.jsonl` via `record_gate`. Never approve on the
user's behalf at medium or high.

## Step 6 — Report

Close with: route taken, steps **skipped** and why, assumptions flagged, risk
verdict + top three drivers, and cost against budget. Keep it to a few lines.

## Hard rules

- **Evidence or silence.** Every judgement carries `confidence` and non-empty
  `evidence[]`. Below threshold → escalate, don't guess.
- **Never do arithmetic the MCP server does.** Blast radius, risk scores, roll-up
  and token counts come from tools. Paying a model to add numbers is a design error.
- **Read `memory/STATE.md` first** in a new session, per `CLAUDE.md`.
- **No `ANTHROPIC_API_KEY`, ever.** If a step seems to need one, the design is wrong.
