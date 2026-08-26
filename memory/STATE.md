# STATE — JSpec / AI_SDD

> Always describes **now**. Overwrite it; don't append history here.
> History goes in `journal/`, decisions in `DECISIONS.md`.

**Last updated:** 2026-08-26
**Phase:** 0 — bootstrap, ~90% complete
**Unit of planning:** the **27-component checklist in `memory/AGENDA.md`** (D-023, D-027),
not the 13 phases. **`AGENDA.md` is the source of truth for build state** — this file
carries open questions, hazards and context around it.
**Delivery medium:** the chat, not artifacts (D-028).

---

## Where the project stands

Phase 0 is essentially done. The foundation, the type system and the router are
built and tested — 40 tests green on 3.13. **Nothing runs end to end**, because
`core/src/jspec/mcp_server.py` is ten tool signatures with zero bodies. That single
file is the only thing between a design and a working tool.

**Working mode changed again (D-023):** every delivery now ships in two halves —
build it, then teach the concept behind it. The owner is learning AI engineering by
building this and plans the chunks himself. `CLAUDE.md` §1b carries this and is
auto-loaded, so it survives new chats.

**Scope narrowed (D-024):** no LangChain / LangGraph / LlamaIndex. Retrieval is
hand-built and structure-first; vector search is the last rung, not the first. MCP
stays. Ollama and third-party model backends are dropped at the owner's instruction.

### Built and working — 4 of 24 components

| ID | Component | Evidence |
|---|---|---|
| C-01 | Contracts — 7 modules, `KINDS` registry, `json_schema()` | 724 ln, no stubs, tested |
| C-02 | Router — T-0…T-3, budgets, confidence floor | 222 ln, tested |
| C-03 | Memory — CLAUDE.md + STATE + journal + DECISIONS | in daily use |
| C-04 | Guardrails — constitution, config.yaml, CI | CI enforces no-API-key + skill lock |

### Stubbed — 3 components

- **C-05 Tool surface** (`mcp_server.py`) — 10 signatures, 0 bodies. **Blocks everything.**
- **C-16 Risk engine** (`risk.py`) — 3 constants, 5 functions unimplemented
- **C-12 Template registry** — 1 of 9 templates written (`specify.yaml`)

### Not started — 17 components

C-06 symbol extractor · C-07 symbol store · C-08 blast radius · C-09 retriever ·
C-10 context builder · C-11 redactor · C-13 judge port · C-14 skills (3 of ~9 done) ·
C-15 decomposer · C-17 gate ledger · C-18 generator · C-19 validator · C-20 repair ·
C-21 evals · C-22 experience · C-23 traceability · C-24 cost ledger

`profiles/`, `specs/`, `evals/golden/`, `evals/rubrics/` are all empty. `.sdd/` is
missing `index/ cache/ knowledge/ traces/ metrics/ gates.jsonl`.

## Next actions, in order

1. **M1 — C-05.** Decide MCP server vs. scripts bundled in the skill (open question
   below), then implement three tools first: `classify_task`, `validate_artifact`,
   `blast_radius`. Nothing is testable until this lands.
2. **M2 — C-06 → C-07 → C-08.** tree-sitter extractor → SQLite index on content hash
   → graph traversal. **Stop here and use it for two weeks** before building more.
3. Commit at each component boundary. D-022 makes git the rollback mechanism.
4. Then M3 (C-09…C-14), M4 (C-15…C-17), M5 (C-21), M6 (C-18…C-24).

Full detail, dependencies and per-component learning notes: **JSpec Component Atlas**
artifact, published 2026-08-26.

## Open questions

| # | Question | Blocks |
|---|---|---|
| 1 | Which repos enter the code graph — M2M only, or App Central shared / CRM / EAM too? | C-06 / C-07 |
| 2 | Risk band thresholds, and who counts as a named approver | C-17 |
| 3 | How does headless `claude -p` authenticate inside an Azure DevOps pipeline? | CI rollout only |
| 4 | Directory-management access in the Aptean Enterprise org | public marketplace only |

**Closed 2026-08-26:**
- **Ollama / local-model backends** — dropped by the owner (D-024). The old
  data-handling sign-off question dies with it: nothing leaves the machine.
- **C-05 shape** — **bundled scripts first**, MCP wraps the proven tools after M2
  (D-025). *M1 is unblocked; the owner sequences when it starts.*
- **Golden set** — reconstruct from the 5,099 commits, owner corrects the inferred
  reasoning (D-026). Read-only on the M2M repo; `.claude/api.md` never touched.

## Watch out for

- **Two artifacts exist and both stay current.** *JSpec Blueprint* (what this is, why
  it's useful, the three questions) and *JSpec Component Atlas* (all 24 components,
  chunk plan, framework verdicts). Update rather than republishing new ones.
- **Stub labels still use pre-merge numbering.** `risk.py` says `"build step 2"` while
  its docstring says Phase 7; `mcp_server.py` scatters steps 3/4/6/8/9. Renumber to
  component IDs when touching either file.
- **The 2026-08-23 session was never journaled** — the largest commit (`ccf8699`,
  3,088 insertions) has no journal entry. Backfill from the commit if it matters.
- **`templates/registry.yaml` declares 9 templates; 1 exists.** Check the file exists
  before assuming a template is available.
- **Two state files, different jobs.** `memory/STATE.md` = across chats.
  `.sdd/state.json` = across steps of one task. Do not merge them.
- Parent `Documents/CLAUDE.md` is the **M2M Playwright** ruleset, not this project's.
