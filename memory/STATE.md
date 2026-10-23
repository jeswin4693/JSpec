# STATE — JSpec / AI_SDD

> Always describes **now**. Overwrite it; don't append history here.
> History goes in `journal/`, decisions in `DECISIONS.md`.

**Last updated:** 2026-10-23 (C-08 blast radius and C-26 project profiler built; M2 complete)
**Phase:** 1 — repo intelligence, built. **The two-week use period of M2 starts now.**
**Unit of planning:** the **27-component checklist in `memory/AGENDA.md`** (D-023, D-027),
not the 13 phases. **`AGENDA.md` is the source of truth for build state** — this file
carries open questions, hazards and context around it.
**Delivery medium:** the chat, not artifacts (D-028).

---

## Where the project stands

**M1 and M2 done.** 10 of 27 components built, **322 tests green** on 3.13, ruff clean,
format clean, domain-neutrality gate clean. **Uncommitted** — C-08 and C-26 are on disk but
not yet committed (see Watch out for).

**C-26 landed 2026-10-23** — the project profiler. JSpec can now draft a profile for a
repository it has never seen, and show how sure it is of each field:

```
jspec profile draft .            -> languages [python] (inferred), source_dirs [core/src/]
                                    (inferred), test_dirs [tests/] (found: pytest.ini),
                                    validation.test pytest (inferred); lint/format/typecheck
                                    unknown - their config is in core/pyproject.toml, nested
jspec profile draft . --set validation.lint="ruff check core tests"   -> confirmed, kept
jspec profile accept NAME        -> profiles/NAME.yaml, only if nothing blocks it
```

Every field is `found` / `inferred` / `guessed` / `confirmed` / `unknown` with evidence; the
draft is its own contract (`profile_draft`) because a real `Profile` cannot hold an unknown
test command. Design: **D-040**. **Not yet proven on a real external repository** — only
three synthetic ones and this repo (owner's scope rule). Only root-level manifests are read.

**C-08 landed 2026-10-23** — blast radius. JSpec now answers "what breaks if I change
this?" over the graph it stored, and says how sure it is:

```
jspec blast-radius ensureAvaTaxEnabled <M2M>  -> 0 certain, 2 possible, 0.56 s end to end
                                                 = the two real call sites (text search: 10 hits, 8 comments)
jspec blast-radius open_store                  -> 6 certain, 3 possible (this repo, dogfooded)
jspec blast-radius button <M2M>                -> 177 definitions, 3,308 possible, 1.26 s (was 35 s)
```

A name walks the call graph; a file walks the import graph; both directions. Every result
is **certain or possible**, the depth searched is always reported (`limit / reached /
complete / stopped_by`), and the answer carries `limits` and an `index` block saying what it
could not see. Design: **D-039**. Known weak spot, found by the stress test: common names
(`click`: 0 certain, 8,143 possible, 2,599 files) are honest and useless — narrowing a bare
call by *which names* a file imports would sharpen it, and is deferred.

**C-07 landed 2026-09-16** — the symbol store. JSpec now remembers what it parsed:

```
jspec index --profile playwright-e2e <M2M>   -> 1885 files, 8911 symbols, 199615 refs, 10.9 s
jspec index --profile playwright-e2e <M2M>   -> files_parsed 0, files_unchanged 1885, 1.9 s
jspec find ensureAvaTaxEnabled <M2M>         -> support/avalaraSetupPage.ts:325, 0.43 s end to end
```

Content hashes, never timestamps. One database per indexed root under JSpec's own
`.sdd/index/`, never in the repository being read (**D-037**). Edges are stored with
`module` and `resolution`; traversal is left to C-08 (**D-038**).

**C-06 landed 2026-09-06** — the symbol extractor. JSpec now reads source as structure:

```
python core/scripts/jspec.py extract --profile jspec-self
  -> 27 files, 292 symbols, 1030 references, modules ['core', 'tests']
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
jspec extract --profile X [--file F] [--symbols] -> symbols + references (one pass)
jspec index   --profile X [root] [--rebuild]     -> refresh the store, parsing only changes
jspec find    NAME [root] [--text|--kind|--file] -> where it is, or what is like it
jspec blast-radius TARGET [root] [--direction dependents|dependencies] [--file F]
                                   [--depth N] [--limit N]   -> affected, certain vs possible
jspec profile draft ROOT [--name N] [--set F=V] [--use-index]  -> a field-by-field draft
jspec profile accept NAME [--accept-guesses] [--overwrite]     -> profiles/NAME.yaml
jspec tools                                      -> all 10, with status (5 ready)
```

### Built and working — 10 of 27 components

| ID | Component | Evidence |
|---|---|---|
| C-01 | Contracts — 8 modules, `KINDS` registry, `json_schema()` | 883 ln, tested |
| C-02 | Router — T-0…T-3, budgets, confidence floor | 231 ln, tested |
| C-03 | Memory — CLAUDE.md + STATE + journal + DECISIONS | in daily use, hook now tested |
| C-04 | Guardrails — constitution, config.yaml, CI | 5 gates; each verified in both directions |
| C-25 | Profile engine — contract, loader, 3 profiles | 258 ln + 21 tests, thin per D-030 |
| C-05 | Tool surface — `jspec` command, tool registry | 480 ln + 38 tests, 3 of 10 tools live |
| C-06 | Symbol extractor — tree-sitter, 4 languages | 943 ln + 45 tests |
| C-07 | Symbol store — SQLite, content hash, FTS5 | 674 ln + 33 tests |
| C-08 | Blast radius — BFS over (node, tainted), certain/possible, 2 graphs | ~810 ln + 54 tests |
| C-26 | Project profiler — field-by-field draft, found/inferred/guessed/confirmed/unknown | ~885 ln + 66 tests |

### Stubbed / partial — 3 components

- **C-16 Risk engine** (`risk.py`) — 3 constants live, 5 functions unimplemented
- **C-12 Template registry** — 1 of 9 templates written (`specify.yaml`)
- **C-14 Skills & agents** — 3 skills (router, recall, specify) + 2 agents of ~9

### Not started — 14 components

C-09 retriever · C-10 context builder ·
C-11 redactor · C-13 judge port · C-15 decomposer · C-17 gate ledger · C-18 generator ·
C-19 validator · C-20 repair · C-21 evals (blocked) · C-22 experience ·
C-23 traceability · C-24 cost ledger · C-27 convention learner

`specs/`, `evals/golden/`, `evals/rubrics/` are still empty. `.sdd/` now has `index/`; still missing
`cache/ knowledge/ traces/ metrics/ gates.jsonl`.

## Next actions, in order

1. **Commit C-08 and C-26** (D-022: git is the rollback mechanism; boundary commits) —
   as two commits if possible: C-08's files first (it is the dependency), then C-26's.
   Stage by path; the working tree also holds two untracked items that are not JSpec's
   (see Watch out for).
2. **Use M2 for two weeks before building more** — that is the milestone's own
   instruction. Watch: is `possible` too noisy on common names? Does depth 4 feel right?
   Is the file graph's import matching missing aliases (`@/…`) on a real TS suite? Does the
   profiler draft something usable for a repository that is not this one?
3. **Then M3.** C-09 retriever and C-11 redactor have no unbuilt dependencies. C-21's
   golden set still blocks on the owner and gates M5.
4. **Ask before the real-repo proof.** C-26's acceptance names three real repositories;
   only synthetic ones and this repo have been used. Reading another repo needs the owner's
   go-ahead (scope rule below).

Deferred, with the reason recorded in D-038: a **stat-based pre-filter** before hashing.
A no-change re-index of 1,885 files costs 1.9-2.4 s against the ~1 s the component guide
asked for, and the floor is the walk plus a full read of every file.

## Verified against a real external repo (2026-09-16)

C-06 was run on `Documents/GitHub/Made2Manage-Automation` with the shipped
`playwright-e2e` profile, unmodified: **1,885 files, 8,911 symbols, 199,615
references, 64s, zero unreadable, zero parse failures**, split across
`page-objects / support / tests`. First external-repo evidence for the extractor.

**Two facts C-07 and C-08 must design for:**

- **Scale.** 8,911 symbols and ~200k edges. The incremental-on-content-hash path is
  load-bearing at that size, not an optimisation.
- **72% of edges are `name_only`** (143,261 vs 56,083 `exact`). On a page-object suite
  nearly every call is `this.x()` or `page.y()`, so D-034's resolution tag is the
  majority of the graph there. **C-08 must report "N certain, M possible"** — a bare
  count would be actively misleading on this repo.

Worked example kept for C-08's acceptance: `ensureAvaTaxEnabled` resolves to
`support/avalaraSetupPage.ts:325-354`, `parent AvalaraSetupPage` - **not**
`navigation.ts` where the prompt guessed it. 10 files *mention* it, per `grep`. **Resolved
by C-08 (2026-10-23):** only two actually call it (`…695270…spec.ts:301`,
`…695265…spec.ts:226`, both `possible` — a member call on `avtsetup`); the other eight
mentions are comments and docs. That gap is what the component is for.

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

## Algorithms chosen for components not yet built (raised 2026-09-16)

Owner asked whether the design uses graph/DSA properly. It does - C-06 emits nodes and
edges, C-07 persists them as an adjacency list indexed in both directions, C-08 is the
traversal. Four structures were named for later components and should not be
re-derived:

- **C-08 uses BFS, not DFS** (built, D-039). Not for speed (both O(V+E)) but because BFS explores in
  rings of distance: ring 1 breaks immediately, ring 4 probably never, and the first
  arrival at a node is the shortest connection chain - which the guide requires per
  result. A DFS depth limit is meaningless ("deep down some paths, untouched on
  others"), and a truncated answer shaped like a complete one is what D-034 forbids.
  DFS keeps one job: back-edge cycle detection.
- **C-08 may need Tarjan SCC + topological order + memoised DP** for *all-pairs*
  reachability (`reachable(v) = {v} ∪ ⋃ reachable(children)` - real overlapping
  subproblems). Only if a repo-wide ranking feature appears; a single query is plain
  BFS, and computing the whole closure to answer one question is waste.
- **C-10's real problem is 0/1 knapsack**, not retrieval: maximise Σrelevance subject to
  Σtokens ≤ budget. **Solve it greedily by value-density, not with exact DP**, and say
  so in the docstring. Reasons: relevance values are noisy estimates (exact optimisation
  of a guess is false precision), items have precedence constraints (a method without
  its class is useless) which makes it NP-hard anyway, and the expansion ladder already
  encodes that precedence tree.
- **C-16 should use Union-Find** for "amplify packages touching the same files" -
  correlated packages are connected components over a package/file bipartite graph.

**C-07 schema v2, when 1.9 s starts to annoy: Merkle directory hashing.**
`hash(dir) = H(hash(child1) || hash(child2) || ...)`, so a matching directory hash
proves every file beneath it is unchanged without reading any of them. Descend only
into subtrees whose hash differs. Better than the stat pre-filter deferred in D-038
because it keeps hashes as the sole authority - no timestamp trust - for ~100x less
I/O. This is how git tree objects make `git status` instant. Do it **after C-08**:
blast radius is worth more than 1.5 saved seconds. (C-08 is now built, so this is
unblocked — but the cost is still unfelt; do it when it annoys, not before.)

**The ranking that matters for tokens**, measured, so effort goes to the top of it:
sending a graph *answer* instead of the code it describes is ~600x (60 tokens vs 40k);
symbol instead of whole file is 40x (30 lines of 1,217); route-depth skipping 3-8x;
knapsack packing inside the budget only 1.2-2x. **The graph's value is that its answer
replaces code you would otherwise have had to send** - not that traversal is elegant.

## Watch out for

- **The guide's line estimates run about 3x low for any component with an honesty model.**
  C-08 was ~200 → ~810, C-26 ~300 → ~885 (about 650 of it code; ruff's one-argument-per-line
  formatting and the docstrings are the rest). Plan the next ones accordingly — C-09 and C-10
  carry the same kind of "say how sure you are" burden.
- **`profile draft` writes to `.sdd/drafts/`** (gitignored) and reads `profiles/` to find an
  already-accepted profile of the same name. Both are JSpec's own folders, never the
  profiled repository. A draft holds an absolute local path; it is not shareable.
- **`profile draft` reads only the repository root's manifests.** A project whose config
  lives in a sub-folder (this one: `core/pyproject.toml`) gets lint/format/typecheck as
  `unknown`, with an observation naming the unread file. That is the design; widening it
  means deciding which directory a command runs from.
- **C-08 and C-26 are uncommitted, and the working tree holds two items that are not JSpec's.**
  `.work-folder-info` and `d8c323a9-552d-473a-8172-75f6001b63a5/` (contains
  `SynapseNotebook/`) appeared on 2026-10-23 at 11:35 — Fabric/Synapse editor-extension
  metadata, not created by JSpec work. Not gitignored. Do not `git add -A`; stage by path.
- **The M2M index is now 2,932 files / 11,458 symbols / 263,837 refs**, up from 1,885 /
  8,911 / 199,615 in September (1,054 files added, 302 changed). The numbers quoted in
  older notes are the September ones. Refreshing it cost 116 s — first-touch OneDrive
  hydration, not the index.
- **Scope rule from the owner, 2026-10-23: stay inside `AI_SDD`.** Do not read other
  folders or repos. JSpec's own index under `.sdd/index/` is in scope and is how M2M
  answers are checked; M2M *source* is not. (One grep into the M2M repo was made this
  session before the instruction and is not to be repeated.)
- **`blast-radius` is only as fresh as the last `jspec index`.** It never re-parses. A
  stale index gives a confident answer about code that has since moved (the M2M method
  moved from line 325 to 375 between September and October).
- **`name_only` is a property of the graph, not a bug of C-08.** If `possible` looks too
  large, the fix is better *resolution* (which names a file imports), not hiding edges.
- **The C-06 self-index figures move whenever a source file is added.** They are 27
  files / 292 symbols / 1030 references as of this session's start and 29 / 373 / 1396
  after C-07 landed. Do not treat a mismatch as drift; re-run `jspec extract --profile
  jspec-self` before believing either number.
- **`git status` cannot detect a stray index.** `.sdd/index/` is gitignored, so a
  database written into the wrong place is invisible to git by construction. The CI gate
  asserts the positive instead - the store is under `.sdd/index` and no `*.db` exists
  anywhere else in the tree.
- **SQLite fires row triggers for foreign-key cascades only when `recursive_triggers` is
  on.** `store._forget()` therefore deletes from `symbols`, `refs` and `files`
  explicitly rather than leaning on `ON DELETE CASCADE`: a cascade would leave the FTS5
  index holding entries for symbols that no longer exist. There is a test for exactly
  that (`test_deleting_a_file_clears_its_full_text_entries`).
- **First-touch file I/O on this machine is 50x slower than warm.** Reading and hashing
  the M2M suite's 21 MB costs 17.3 s the first time and 0.33 s the second - OneDrive
  hydration plus Defender's on-access scan. Any timing measured here is meaningless
  unless it says which of the two it is.

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
