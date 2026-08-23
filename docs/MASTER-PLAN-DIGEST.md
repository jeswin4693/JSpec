# Master Plan — binding digest

Auto-loaded every session via `CLAUDE.md`. The full 70-section specification is
`docs/AI_SDD_MASTER_PLAN.md` — **load-on-demand only** (~12k tokens; §60 of that
document forbids spending context unnecessarily). Read the relevant section, not
the file.

Reconciliation with the pre-existing JSpec design is recorded in
`memory/DECISIONS.md` **D-016 … D-021**. Never re-litigate those.

---

## The four settled conflicts

| # | Master Plan says | Settled as | Decision |
|---|---|---|---|
| 1 | TypeScript core (§5) | **Python 3.12/3.13.** tree-sitter parses TS fine; you don't write the tool in TS to analyse TS | D-017 |
| 2 | Provider gateway w/ API keys (§32, §33, §62) | **Adapters yes, key-based default no.** Default backend is Claude Code auth. No path may require a provider key. `--bare` forbidden | D-018 |
| 3 | `.sdd/` + 20-subsystem `src/` (§8) | **Map, don't rename.** Existing tree kept; `.sdd/` added for what was genuinely missing | D-019 |
| 4 | No phase measures artifact quality | **Eval phase inserted at 4.5.** Nothing past it proceeds unproven | D-020 |

## Non-negotiables (master plan ∩ JSpec — both agree)

1. **Minimum *sufficient* context** — never minimum context, never whole-repo → LLM (§3).
2. **Deterministic over AI wherever sufficient** (§4.16 = D-003). Arithmetic, graphs,
   hashes, token counts → Python. Ambiguity and judgement → the model.
3. **Evidence or silence** — every model judgement carries `confidence` + non-empty
   `evidence[]` (§4.2 = D-003).
4. **Typed artifacts** — validated objects; markdown is a rendering (§35 = D-002).
5. **Reuse before creation** (§4.4). **Minimal patch before rewrite** (§39).
6. **Never** hallucinate repo APIs, invent files, or modify unrelated files (§4.12–14).
7. **Never** silently turn a recommendation into a requirement (§4.15).
8. **No API key on any default path** (D-006). CI fails the build if one appears.
9. Human approval for high-risk changes; **risk-priced** gates, append-only ledger
   (§56 + D-005).

## Merged phase order

`0 bootstrap → 1 repo intelligence → 2 specification → 3 retrieval → 4 context
engineering → 4.5 EVALS → 5 experience → 6 AI gateway → 7 planning → 8 generation
→ 9 validation → 10 repair → 11 traceability → 12 knowledge capture`

Running alongside all phases (JSpec, retained): route depth T-0…T-3 and step
skipping (D-009) · risk roll-up to one verdict + 3 drivers (D-004) · gate ledger
(D-005) · question budget (D-010) · domain profiles (D-011) · session memory (D-015).

**Do not skip foundations. Do not jump phases** (§9, §57).

## Per-phase discipline

Each phase ships: implementation · tests · docs · validation · example (§9).
A phase is done only when tests pass, types pass, docs exist, state is updated,
and **no unrelated changes exist** (§68). Report per §67, then stop.

## Before reading any file

Ask *why do I need this file?* If unclear, **do not read it** (§59). Prefer search,
symbol lookup, references, targeted ranges over full-file reads. Expansion ladder
(§23): `symbol → enclosing class → related symbols → dependencies → file range →
full file`. Full-file reads require justification; whole-repo reads never happen.

## Never send off-machine

`.env` · credentials · API keys · certificates · private keys · production secrets ·
customer data · `.claude/api.md` in the M2M repo (§46). Detect and redact before any
context leaves the machine.
