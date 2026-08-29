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

Run the `jspec` command. It is deterministic, needs no model call, and costs
nothing:

```bash
jspec classify "<the user's raw prompt>"
```

If `jspec` is not on PATH (the package is not pip-installed), use the launcher — same
code, no install, works from any directory:

```bash
python <repo>/core/scripts/jspec.py classify "<the user's raw prompt>"
```

Supply repo facts when you have them — they are measured, so they outrank
vocabulary and sharply raise confidence:

```bash
jspec classify "<prompt>" --failing-tests 3 --files-touched 40
```

It prints JSON:

```
{ route, confidence, chain[], question_budget, token_budget, signals[],
  needs_model_adjudication }
```

**Do not reason your way to a route yourself when the tool can tell you.** Only when
`needs_model_adjudication` is true (confidence below 0.6) do you adjudicate, and then
you state which signals you weighed.

Then get the steps to run, skipping only what you can justify:

```bash
jspec plan-chain T-2 --profile <name> --skip clarify
```

Run `jspec tools` to see all ten tools and which are built. Seven are not yet — they
refuse rather than guess, and the message names the component each waits on. If a
step needs one of those, say so plainly and stop; do not substitute your own estimate
for a measurement.

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

Between steps, every artifact is schema-validated before it travels:

```bash
echo '<artifact json>' | jspec validate spec -
```

Exit 0 means valid; exit 1 means it printed the problems — fix them and revalidate.
Never let an unvalidated artifact reach the next step.

`submit_spec` (validate **and** persist **and** render) is not built yet — it waits
on C-12/C-14. Until then, validate with the command above and hand the artifact to
the next step in-session rather than writing spec files to disk.

## Step 4 — Questions: ask least, never twice

For every unknown, resolve in this order and stop at the first hit:

1. `.jspec/preferences.yaml` — already answered?
2. The repo — what did they do the last three times?
3. The active profile — what does their setup imply?
4. **Assume and flag** — proceed with a stated default, record it on the artifact,
   surface it at the gate.
5. **Ask** — only if being wrong would waste the whole run.

Stay inside `question_budget` (the classify output tells you the number).
**Batch every question into one turn** — never drip-feed.

`record_preference` is not built yet, so an answer cannot be persisted automatically:
carry answers within the session, and note anything durable in `memory/` at the end.

Most unknowns should become flagged assumptions. Reviewing three flagged defaults at
a gate is cheaper for the user than answering three questions mid-flight.

## Step 5 — Gates

Gate stringency is priced by risk, not applied uniformly:

- **low** → auto-approve, append to the ledger, say so in one line, continue
- **medium** → show the evidence, ask for one Yes
- **high** → named approver, impact scan, rollback plan, explicit Yes

`record_gate` and the ledger are not built yet (C-17). Until they are, state the
gate decision explicitly in your report so it is at least visible in the transcript.
**Never approve on the user's behalf at medium or high.**

## Step 6 — Report

Close with: route taken, steps **skipped** and why, assumptions flagged, risk
verdict + top three drivers, and cost against budget. Keep it to a few lines.

## Hard rules

- **Evidence or silence.** Every judgement carries `confidence` and non-empty
  `evidence[]`. Below threshold → escalate, don't guess.
- **Never do arithmetic a tool does.** Blast radius, risk scores, roll-up and token
  counts come from `jspec`, not from you. Paying a model to add numbers is a design
  error. Where the tool is not built yet, say the number is unavailable — never
  estimate one and present it as measured.
- **Read `memory/STATE.md` first** in a new session, per `CLAUDE.md`.
- **No `ANTHROPIC_API_KEY`, ever.** If a step seems to need one, the design is wrong.
