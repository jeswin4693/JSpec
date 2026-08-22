# STATE — JSpec

> Always describes **now**. Overwrite it; don't append history here.
> History goes in `journal/`, decisions in `DECISIONS.md`.

**Last updated:** 2026-08-22
**Build step:** 1 of 11 — contracts (scaffold just created)

---

## Where the project stands

Scaffold created. Architecture settled after a long design conversation
(see `journal/2026-08-22.md`). `git init` done — repo has no commits yet.

**Exists and is real:**

- `CLAUDE.md` — session start/end memory protocol, non-negotiables
- `memory/` — this file, `DECISIONS.md`, `journal/`
- `jspec/` — plugin manifest, `skills/router` (model-invoked), `skills/specify`
  and `skills/recall` (`disable-model-invocation`), `hooks/hooks.json`, `.mcp.json`
- `core/src/jspec/contracts/spec.py` — Pydantic contracts
- `core/src/jspec/router.py` — deterministic task classifier
- `templates/registry.yaml` + `templates/specify.yaml`

**Stubbed, not yet working:**

- `core/src/jspec/mcp_server.py` — tool signatures only
- `core/src/jspec/risk.py` — roll-up math not implemented
- retrieval / code graph — not started
- `evals/` — empty; **golden set not yet collected**

## Next actions, in order

1. `uv init` in `core/`, pin **Python 3.12 or 3.13** (system Python is 3.14 —
   `tree-sitter` and `sqlite-vec` wheels lag there).
2. Finish `contracts/` — `Plan`, `WorkPackage`, `RiskItem`, `Gate`. Export JSON
   Schema for each (needed by both MCP tools and `--json-schema`).
3. Implement `mcp_server.py`: `classify_task`, `plan_chain`, `submit_spec`,
   `validate_artifact`. Pure Python, zero model calls.
4. Wire `skills/specify` → `submit_spec` → validated artifact on disk.
5. **Collect the golden set** (blocking for step 4 of the build order): 5–10 real
   features with the original request, the final implementation, and **what went
   wrong / got reworked**. Owner action, ~2–3 hours. Candidates from the M2M repo:
   labor entry to job order, selective labor backflush, OT pay after deleting
   hours, closed-JO serial LABR time edit, username field length.

## Open questions

| # | Question | Blocks |
|---|---|---|
| 1 | How does headless `claude -p` authenticate inside an Azure DevOps pipeline on the Enterprise plan? Ask the Claude Code admin at Aptean. | build step 9 only — nothing before it |
| 2 | Data-handling sign-off: Claude Code sends code context off-machine; repo is classified `Internal`. | CI rollout, not local dev |
| 3 | Which repos enter the code graph — M2M only, or App Central shared / CRM / EAM too? | step 6 (retrieval) |
| 4 | Does the owner have directory-management access in the Aptean Enterprise org (needed to publish to the community marketplace)? | public distribution only |

## Watch out for

- **No commits yet.** Commit before any large refactor — deletions here are
  otherwise unrecoverable (that's how `RCA-Agent` went).
- Parent `Documents/CLAUDE.md` is the **M2M Playwright** ruleset. It is not this
  project's spec. Don't apply page-object/AG-Grid rules to Python here.
- Autopilot risk: chaining the full pipeline onto a one-line fix costs more than
  it saves. Route depth (T-0…T-3) is the guard.
