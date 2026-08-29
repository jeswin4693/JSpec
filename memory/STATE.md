# STATE — JSpec / AI_SDD

> Always describes **now**. Overwrite it; don't append history here.
> History goes in `journal/`, decisions in `DECISIONS.md`.

**Last updated:** 2026-08-29 (C-25 + C-05 built; **M1 complete — JSpec runs**)
**Phase:** 0 — bootstrap, ~90% complete
**Unit of planning:** the **27-component checklist in `memory/AGENDA.md`** (D-023, D-027),
not the 13 phases. **`AGENDA.md` is the source of truth for build state** — this file
carries open questions, hazards and context around it.
**Delivery medium:** the chat, not artifacts (D-028).

---

## Where the project stands

**Phase 0 and M1 are both done. JSpec runs.** 6 of 27 components built, **99 tests
green** on 3.13, ruff clean, domain-neutrality gate clean.

Two components landed 2026-08-29:

- **C-25 profile engine** (D-030) — `Profile` contract + loader, three shipped profiles,
  21 tests. Built **thin**: `extends`, override resolution, `risk_signals` and
  `templates` all deferred until a component reads them.
- **C-05 tool surface** (D-031) — the `jspec` command. 4 commands over the 3 tools the
  built components can answer honestly; the other 7 raise `ToolUnavailable` naming their
  blocker. `mcp_server.py` now delegates to one registry instead of holding empty bodies,
  and the router skill calls real commands instead of a server that cannot start.

What works today, from a bare checkout with nothing installed:

```
python core/scripts/jspec.py classify "add password reset"   -> route, chain, budgets
python core/scripts/jspec.py plan-chain T-2 --profile X      -> steps, minus skips
python core/scripts/jspec.py validate profile file.json      -> ok, or every problem
python core/scripts/jspec.py tools                           -> all 10, with status
```

**Working mode changed again (D-023):** every delivery now ships in two halves —
build it, then teach the concept behind it. The owner is learning AI engineering by
building this and plans the chunks himself. `CLAUDE.md` §1b carries this and is
auto-loaded, so it survives new chats.

**Scope narrowed (D-024):** no LangChain / LangGraph / LlamaIndex. Retrieval is
hand-built and structure-first; vector search is the last rung, not the first. MCP
stays. Ollama and third-party model backends are dropped at the owner's instruction.

### Built and working — 6 of 27 components

| ID | Component | Evidence |
|---|---|---|
| C-01 | Contracts — 7 modules, `KINDS` registry, `json_schema()` | 724 ln, no stubs, tested |
| C-02 | Router — T-0…T-3, budgets, confidence floor | 222 ln, tested |
| C-03 | Memory — CLAUDE.md + STATE + journal + DECISIONS | in daily use |
| C-04 | Guardrails — constitution, config.yaml, CI | CI enforces no-API-key, skill lock, profile validity, domain neutrality |
| C-25 | Profile engine — contract, loader, 3 profiles | 258 ln + 21 tests, thin per D-030 |
| C-05 | Tool surface — `jspec` command, tool registry | 480 ln + 38 tests, 3 of 10 tools live |

### Stubbed / partial — 3 components

- **C-16 Risk engine** (`risk.py`) — 3 constants live, 5 functions unimplemented
- **C-12 Template registry** — 1 of 9 templates written (`specify.yaml`)
- **C-14 Skills & agents** — 3 skills (router, recall, specify) + 2 agents of ~9

### Not started — 18 components

C-06 symbol extractor · C-07 symbol store · C-08 blast radius · C-09 retriever ·
C-10 context builder · C-11 redactor · C-13 judge port · C-15 decomposer ·
C-17 gate ledger · C-18 generator · C-19 validator · C-20 repair · C-21 evals (blocked) ·
C-22 experience · C-23 traceability · C-24 cost ledger · C-26 project profiler ·
C-27 convention learner

`profiles/` now holds three profiles. `specs/`, `evals/golden/`, `evals/rubrics/` are
still empty. `.sdd/` is missing `index/ cache/ knowledge/ traces/ metrics/ gates.jsonl`.

## Next actions, in order

1. **M2 — C-06 → C-07 → C-08 → C-26.** tree-sitter extractor → SQLite index on content
   hash → graph traversal → draft-profile generator. Scope settled (D-032): **one root
   folder, every sub-folder indexed, cross-folder calls followed, and a module column in
   the schema from the first migration.** C-08 must report which sub-folder each caller
   lives in. **Stop here and use it for two weeks** before building more.
2. Commit at each component boundary. D-022 makes git the rollback mechanism.
3. Then M3 (C-09…C-14, C-27), M4 (C-15…C-17), M5 (C-21), M6 (C-19 first, then
   C-18, C-20, C-22, C-23, C-24).

Full detail, dependencies, acceptance tests and per-component learning notes:
**`docs/COMPONENT-GUIDE.md`** (1,210 ln, all 27 components) — read the relevant entry
before building any component. `memory/AGENDA.md` carries the checklist and milestones.

## Open questions

| # | Question | Blocks |
|---|---|---|
| 2 | Risk band thresholds, and who counts as a named approver | C-17 |
| 3 | How does headless `claude -p` authenticate inside an Azure DevOps pipeline? | CI rollout only |
| 4 | Directory-management access in the Aptean Enterprise org | public marketplace only |

**Closed 2026-08-29:**
- **Code-graph scope** — one root folder, every sub-folder indexed, cross-folder calls
  followed (D-032). *M2 is unblocked.*
- **C-05 shape** — one `jspec` command, not per-skill scripts (D-031), amending where
  D-025 put the files but not its substance.

**Closed 2026-08-26:**
- **Ollama / local-model backends** — dropped by the owner (D-024). The old
  data-handling sign-off question dies with it: nothing leaves the machine.
- **C-05 shape** — **bundled scripts first**, MCP wraps the proven tools after M2
  (D-025). *M1 is unblocked; the owner sequences when it starts.*
- **Golden set** — reconstruct from the 5,099 commits, owner corrects the inferred
  reasoning (D-026). Read-only on the M2M repo; `.claude/api.md` never touched.

## Watch out for

- **Two artifacts exist but are no longer the medium (D-028).** *JSpec Blueprint* and
  *JSpec Component Atlas* (published 2026-08-26, atlas predates C-25…C-27 so it shows
  24 components). Left in place; explanation now goes in the chat. If either is ever
  updated, update in place — never republish as a new artifact.
- **Stub labels still use pre-merge numbering.** `risk.py` says `"build step 2"` while
  its docstring says Phase 7; `mcp_server.py` scatters steps 3/4/6/8/9. Renumber to
  component IDs when touching either file.
- **`docs/JSpec-Agenda.docx` is untracked, pending the owner's call** on whether a
  generated binary belongs in git. The generator, `core/scripts/md_to_docx.py`
  (stdlib-only), is the real source. Regenerate with:
  `./.venv/Scripts/python.exe core/scripts/md_to_docx.py docs/JSpec-Agenda.docx "JSpec Build Agenda" memory/AGENDA.md docs/COMPONENT-GUIDE.md`
- **pip is broken inside `.venv`** (`No module named pip.__main__`), so the package
  cannot be installed locally and the `jspec` console script does not exist here. Use
  `python core/scripts/jspec.py …`, the zero-install launcher. CI installs properly and
  gets the real entry point. Fixing the venv is unblocked-but-unowned work.
- **`record_preference` has no agreed storage path.** `jspec/skills/router/SKILL.md`
  says `.jspec/preferences.yaml`; the repo layout says `.sdd/`. Decide before building
  it — `jspec tools` lists it as blocked on exactly this.
- **`templates/registry.yaml` declares 9 templates; 1 exists.** Check the file exists
  before assuming a template is available.
- **Two state files, different jobs.** `memory/STATE.md` = across chats.
  `.sdd/state.json` = across steps of one task. Do not merge them.
- Parent `Documents/CLAUDE.md` is the **M2M Playwright** ruleset, not this project's.
