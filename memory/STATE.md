# STATE — JSpec / AI_SDD

> Always describes **now**. Overwrite it; don't append history here.
> History goes in `journal/`, decisions in `DECISIONS.md`.

**Last updated:** 2026-08-23
**Phase:** 0 — bootstrap (merged phase order; see `CLAUDE.md` §5)

---

## Where the project stands

The owner supplied a 70-section Master Build Specification on 2026-08-23. It was
reconciled with the existing JSpec design rather than replacing it — see
`DECISIONS.md` **D-016…D-022**, and `docs/MASTER-PLAN-DIGEST.md` for the one-page
binding summary that is auto-loaded every session.

**Four conflicts, settled:** core stays Python (D-017) · provider adapters yes,
key-based default no (D-018) · layout mapped, not renamed (D-019) · an eval phase is
inserted at 4.5 because the master plan had no phase that measures artifact quality
(D-020). **Six engines adopted** from the document that JSpec lacked: context
engineering, experience, repair, traceability, knowledge capture, security/redaction
(D-021).

**Working mode changed (D-022):** no more Yes/No approval per file. Act; ask only on
genuine ambiguity. Still confirm destructive, outbound, or high-risk shared changes.

### Exists and is real

- `docs/AI_SDD_MASTER_PLAN.md` — the governing spec, 70 sections, mojibake repaired,
  §5/§32/§33/§57/§62 annotated with their amendments
- `docs/MASTER-PLAN-DIGEST.md` — auto-imported by `CLAUDE.md`
- `.sdd/constitution.md` — §45's 12 rules + 8 JSpec non-negotiables + precedence order
- `.sdd/config.yaml` — providers, context ladder, preferences, never-send list,
  retrieval order, repair limit, risk bands, native validation commands
- `.sdd/state.json` — task state (§55)
- `core/src/jspec/contracts/spec.py` — Spec-side contracts, tested
- `core/src/jspec/router.py` — deterministic T-0…T-3 classifier, tested
- `templates/registry.yaml` + `templates/specify.yaml`
- `jspec/` — plugin manifest, 3 skills, 2 agents, hooks, `.mcp.json`
- CI on 3.12 + 3.13, including a check that fails the build if an API key appears

### Stubbed or missing

- `core/src/jspec/mcp_server.py` — 10 signatures, 0 bodies
- `core/src/jspec/risk.py` — constants only, 5 functions unimplemented
- Contracts: `Plan`, `WorkPackage`, `RiskItem`, `Gate`, `Review`, `Drift`, `Fix`,
  `Clarifications`, `Classification` — **in progress this session**
- Templates: 8 of 9 declared in `registry.yaml` have no body file
- Rubrics: 0 of 9 · Profiles: 0 · Golden cases: **0**
- Repository intelligence / retrieval / context engineering / experience — not started

## Next actions, in order

1. Finish Phase 0: the remaining contracts + `KINDS` schema-export registry + tests;
   green `pytest` and `ruff` on Python 3.13.
2. Commit. D-022 makes git the rollback mechanism, so phase-boundary commits are now
   load-bearing rather than optional.
3. Report per master plan §67 and **stop** — §66 forbids auto-continuing to Phase 1.
4. Then Phase 1 (repository intelligence): tree-sitter symbol extraction → SQLite,
   incremental re-index on content hash, `blast_radius` as a real graph traversal.
5. **Golden set** — still the one blocking owner input, now for Phase 4.5. Approved
   approach: mine `../GitHub/Made2Manage-Automation` (5,099 commits) for
   request→rework pairs, owner corrects the reconstruction.

## Open questions

| # | Question | Blocks |
|---|---|---|
| 1 | Which repos enter the code graph — M2M only, or App Central shared / CRM / EAM too? | Phase 1 |
| 2 | Risk band thresholds and who counts as a named approver | gates |
| 3 | How does headless `claude -p` authenticate inside an Azure DevOps pipeline on Enterprise? | CI rollout only |
| 4 | Data-handling sign-off: repo is classified `Internal`. §46 redaction is now designed — does that satisfy it? | CI rollout only |
| 5 | Directory-management access in the Aptean Enterprise org | public marketplace only |

**Resolved since last update:** no AI API key is available and none will be — Claude
Code integration only. That is now settled in D-018, not an open question.

## Watch out for

- **`risk.py` mislabels its own stubs** `"build step 2"` while `mcp_server.py` says
  risk work is `"build step 8"`. Both predate the merged phase order and should be
  renumbered to the phase map in `CLAUDE.md` §5.
- **Two state files, different jobs.** `memory/STATE.md` = across chats.
  `.sdd/state.json` = across steps of one task. Do not merge them.
- **`templates/registry.yaml` declares 9 templates; 1 exists.** The registry is
  aspirational — check the file exists before assuming a template is available.
- Parent `Documents/CLAUDE.md` is the **M2M Playwright** ruleset, not this project's.
- Autopilot risk: the master plan's §69 runs the full chain for every `sdd implement`.
  Route depth (T-0…T-3) is the guard, and it must survive the merge.
