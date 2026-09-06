# STATE — JSpec / AI_SDD

> Always describes **now**. Overwrite it; don't append history here.
> History goes in `journal/`, decisions in `DECISIONS.md`.

**Last updated:** 2026-09-06 (C-06 built, then a fix pass; **M2 started**)
**Phase:** 1 — repo intelligence, ~25% complete
**Unit of planning:** the **27-component checklist in `memory/AGENDA.md`** (D-023, D-027),
not the 13 phases. **`AGENDA.md` is the source of truth for build state** — this file
carries open questions, hazards and context around it.
**Delivery medium:** the chat, not artifacts (D-028).

---

## Where the project stands

**M1 done, M2 begun.** 7 of 27 components built, **173 tests green** on 3.13, ruff clean,
domain-neutrality gate clean.

**C-06 landed 2026-09-06** — the symbol extractor. JSpec now reads source as structure:

```
python core/scripts/jspec.py extract --profile jspec-self
  -> 26 files, 292 symbols, 1024 references, modules ['core', 'tests']
```

Four languages ship. Every grammar node-type name lives in
`core/src/jspec/graph/languages.yaml` (**D-033**), so adding a language is a data change
and no module in `core/src` names one — enforced by a test independent of the CI script.
Every edge carries a `resolution` of `exact` / `name_only` / `unresolved` (**D-034**),
recording how firmly the syntax pinned its target down rather than dropping the uncertain
ones or over-linking them.

**The environment blocker is gone.** pip is repaired (`ensurepip`), `core[graph,dev]` is
installed, and the real `jspec` console script now exists locally.

What works today:

```
jspec classify "add password reset"              -> route, chain, budgets
jspec plan-chain T-2 --profile X                 -> steps, minus skips
jspec validate profile file.json                 -> ok, or every problem
jspec extract --profile X [--file F] [--symbols] -> symbols + references
jspec tools                                      -> all 10, with status
```

### Built and working — 7 of 27 components

| ID | Component | Evidence |
|---|---|---|
| C-01 | Contracts — 8 modules, `KINDS` registry, `json_schema()` | 883 ln, tested |
| C-02 | Router — T-0…T-3, budgets, confidence floor | 231 ln, tested |
| C-03 | Memory — CLAUDE.md + STATE + journal + DECISIONS | in daily use, hook now tested |
| C-04 | Guardrails — constitution, config.yaml, CI | 5 gates; each verified in both directions |
| C-25 | Profile engine — contract, loader, 3 profiles | 258 ln + 21 tests, thin per D-030 |
| C-05 | Tool surface — `jspec` command, tool registry | 480 ln + 38 tests, 3 of 10 tools live |
| C-06 | Symbol extractor — tree-sitter, 4 languages | 943 ln + 45 tests |

### Stubbed / partial — 3 components

- **C-16 Risk engine** (`risk.py`) — 3 constants live, 5 functions unimplemented
- **C-12 Template registry** — 1 of 9 templates written (`specify.yaml`)
- **C-14 Skills & agents** — 3 skills (router, recall, specify) + 2 agents of ~9

### Not started — 17 components

C-07 symbol store · C-08 blast radius · C-09 retriever · C-10 context builder ·
C-11 redactor · C-13 judge port · C-15 decomposer · C-17 gate ledger · C-18 generator ·
C-19 validator · C-20 repair · C-21 evals (blocked) · C-22 experience ·
C-23 traceability · C-24 cost ledger · C-26 project profiler · C-27 convention learner

`specs/`, `evals/golden/`, `evals/rubrics/` are still empty. `.sdd/` is still missing
`index/ cache/ knowledge/ traces/ metrics/ gates.jsonl` — **C-07 creates `index/` first.**

## Next actions, in order

1. **C-07 symbol store.** SQLite index of C-06's output, refreshed only for files whose
   content hash changed, plus full-text search. The `module` column ships in the first
   migration (D-032). Prove the incremental path rather than asserting it: index
   everything, change one file, re-index, show only that file was re-read.
2. **C-08 blast radius** — transitive closure over the graph, cycle-safe, depth-limited
   *with the depth reported*, reverse direction, connection chain per result. It should
   consume C-06's `resolution` so it can say "7 certain, 3 possible".
3. **C-26 project profiler**, then **stop and use M2 for two weeks** before building more.
4. Commit at each component boundary. D-022 makes git the rollback mechanism.

Full detail, dependencies and acceptance tests: **`docs/COMPONENT-GUIDE.md`** — read the
relevant entry before building any component.

## Open questions

| # | Question | Blocks |
|---|---|---|
| 2 | Risk band thresholds, and who counts as a named approver | C-17 |
| 3 | How does headless `claude -p` authenticate inside an Azure DevOps pipeline? | CI rollout only |
| 4 | Directory-management access in the Aptean Enterprise org | public marketplace only |

**Closed 2026-09-06 (fix pass):**
- **C-02's `FILE_PATH` regex** — now shape-based, not a language list (D-035). Zero
  regressions, six more languages recognised, prose rejected.
- **The SessionStart hook was silently failing on Windows** — every session had been
  starting with no memory loaded (D-036). Fixed and now tested.

**Closed 2026-09-06:**
- **Where language reading rules live** — shipped data beside the extractor, not config,
  not profiles (D-033). `.sdd/config.yaml`'s `index.languages` key was removed.
- **How an unresolvable call is recorded** — kept and labelled, never dropped or
  over-linked (D-034).
- **pip broken in `.venv`** — repaired with `ensurepip`; `core[graph,dev]` installed.

## Watch out for

- **`check_domain_neutrality.py` screens tool names only, not language names.** It would
  not have caught C-02's extension list, and it will not catch the next one.
  `tests/test_graph.py::test_no_module_in_core_names_a_language` is the half that
  screens language names; keep both.
- **CI installs the package NON-editable, so `find_up`'s walk-up fallback does not
  work there.** `jspec/config.py` lands in site-packages, and walking up finds no
  `.sdd/` and no `profiles/`. `tests/conftest.py` sets `JSPEC_ROOT` for the suite,
  which is what `jspec/.mcp.json` already does in production. **Any new test that
  resolves a root implicitly depends on that file** - pass an explicit root where you
  can. Caught by building the wheel and importing it from outside the repo, not by
  the local suite, which runs editable and passes either way.
- **`core/pyproject.toml` had an invalid `readme` key** pointing outside the project
  directory. That — not the broken pip — is why `pip install -e core` had never actually
  succeeded. Removed; a `core/README.md` would duplicate the root one.
- **The launcher had a self-import bug that only appeared once the package was
  installed.** `core/scripts/jspec.py` skipped its `sys.path` insert when `core/src` was
  already present, leaving its own directory first — where `jspec.py` shadows the `jspec`
  package. Fixed by dropping the script's own directory and forcing `core/src` to the
  front. All three invocation modes now verified.
- **Two artifacts exist but are no longer the medium (D-028).** *JSpec Blueprint* and
  *JSpec Component Atlas* (2026-08-26; the atlas predates C-25…C-27, so it shows 24
  components). If either is ever updated, update in place — never republish as new.
- **Stub labels still use pre-merge numbering.** `risk.py` says `"build step 2"` while its
  docstring says Phase 7. Renumber to component IDs when touching it.
- **`docs/JSpec-Agenda.docx` is untracked**, pending the owner's call on whether a
  generated binary belongs in git. Regenerate with:
  `./.venv/Scripts/python.exe core/scripts/md_to_docx.py docs/JSpec-Agenda.docx "JSpec Build Agenda" memory/AGENDA.md docs/COMPONENT-GUIDE.md`
- **`record_preference` has no agreed storage path.** The router skill says
  `.jspec/preferences.yaml`; the repo layout says `.sdd/`. `jspec tools` lists it as
  blocked on exactly this.
- **`templates/registry.yaml` declares 9 templates; 1 exists.** Check before assuming.
- **Two state files, different jobs.** `memory/STATE.md` = across chats.
  `.sdd/state.json` = across steps of one task. Do not merge them.
- Parent `Documents/CLAUDE.md` is the **M2M Playwright** ruleset, not this project's.
