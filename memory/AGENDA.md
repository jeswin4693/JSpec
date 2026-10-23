# AGENDA — JSpec build checklist

The full build, as 27 components in 9 groups. **This file is the source of truth for
"what is done and what is next."** Read at session start; updated whenever a component
changes state.

**Detailed description of every component — what it does, its inputs and outputs, its
acceptance test, and how to instruct me to build it — is in `docs/COMPONENT-GUIDE.md`.**
Read that before starting any component.

**JSpec is a general tool for any team's project.** Nothing here is specific to
Playwright, M2M or Aptean — all domain knowledge lives in `profiles/*.yaml` (D-011,
D-027). Where an example is needed below it is labelled as an example.

---

## Progress

| | Count | Which |
|---|---|---|
| ✅ Done | **10** | C-01, C-02, C-03, C-04, C-05, C-06, C-07, C-08, C-25, C-26 |
| 🟡 Partial / stub | **3** | C-12, C-14, C-16 |
| ⬜ Not started | **14** | everything else |
| **Total** | **27** | 9 groups, 6 milestones |

**Right now:** **M2 is complete — C-26 landed 2026-10-23, the same day as C-08.** 322
tests green. `jspec blast-radius` answers "what breaks if I change this?" with every result
**certain or possible** (D-039); `jspec profile draft` / `accept` drafts a profile for a
repository it has never seen, every field marked `found`, `inferred`, `guessed`,
`confirmed` or `unknown`, and never fills a gap with a plausible value (D-040). On this
repository the draft gets languages, source dirs, test dirs and the test command right.
**Next:** **stop and use M2 for two weeks** — that is the milestone's own instruction, and
it is now due. Two open things to watch: is `possible` too noisy on common names (`click`:
0 certain, 8,143 possible), and does the profiler hold up on a *real* external repository
(only synthetic ones and this repo so far; needs the owner's go-ahead to read another).
After the pause: **M3**, starting with C-09 (retriever) and C-11 (redactor).

**Legend:** `[x]` done · `[~]` partial or stub · `[ ]` not started · `[!]` blocked on input

---

## How to update this file

When a component changes state: flip its box, update its status note, update the
Progress table, and set **Right now / Next**. Add a line to `journal/YYYY-MM-DD.md`
saying what changed. Never renumber a component ID — they are referenced from
`STATE.md`, the journal and `DECISIONS.md`.

---

## Group 1 · Foundation — *the base everything sits on*

- [x] **C-01 · Contracts** — The definition of every artifact the system produces: spec,
      plan, work package, risk item, approval. Anything that does not fit the shape is
      rejected before it can travel downstream.
      · 724 ln · needs: — · *teaches: structured output / constrained generation*

- [x] **C-02 · Router** — Reads a request and decides how much process it deserves
      (trivial / fix / feature / sweep), then sets the token and question budget for the
      run. No model call.
      · 231 ln · needs: C-01 · *teaches: when NOT to call a model*

- [x] **C-03 · Memory** — Continuity across chats: a small auto-loaded protocol, a
      current-state file, an append-only history, and this agenda.
      · ~550 ln + 9 hook tests · needs: — · *teaches: agent memory architecture*

- [x] **C-04 · Guardrails** — The constitution (rules), `config.yaml` (knobs) and CI
      (enforcement), including the check that fails the build if an API key appears.
      · ~300 ln · needs: — · *teaches: policy as data, enforced mechanically*

## Group 1b · Adaptation — *what makes it work for anyone*

- [x] **C-25 · Profile engine** — The `Profile` contract, loader and validation. The
      single place any project-specific fact may live: languages, layout, validation
      commands. Shipped **thin** (D-030): `extends`/override resolution, `risk_signals`
      and `templates` deferred until a component reads them. 3 profiles ship
      (python-service, playwright-e2e, jspec-self); 2 CI gates enforce it.
      · 258 ln + 21 tests · needs: C-01 · *teaches: where to put the generalization boundary*

- [x] **C-26 · Project profiler** — Point it at a repository it has never seen; it works
      out the languages, frameworks, test runner and layout, then writes a **draft**
      profile the user corrects. Every guess marked as a guess. Each field is found /
      inferred / guessed / confirmed / unknown with evidence; the draft is its own
      contract because a real `Profile` cannot hold an unknown test command; a person's
      correction is `confirmed` and never overwritten; `accept` refuses unknown required
      fields and unconfirmed guesses, and what it writes must load (D-040). **Not yet
      proven on a real external repository; only root-level manifests are read.**
      · ~885 ln + 66 tests · needs: C-06, C-07, C-25 · *teaches: zero-config onboarding, honest uncertainty*

- [ ] **C-27 · Convention learner** — Infer how *this* team actually writes code — naming,
      structure, recurring patterns — so generated work looks like theirs, not generic.
      · ~250 ln · needs: C-07, C-09, C-25 · *teaches: observed preferences beat configured ones*

## Group 2 · The bridge — *nothing runs until this exists*

- [x] **C-05 · Tool surface** — How a skill calls the Python side. `jspec` command
      (`cli.py`) + `tools.py` registry; 4 commands over 3 built tools, invoked via Bash
      per D-025. The other 7 raise `ToolUnavailable` naming their blocker — never a
      placeholder. **Deviation from the guide:** its third named tool was `blast_radius`,
      which needs C-07; `plan_chain` took its place. Zero-install launcher at
      `core/scripts/jspec.py` because pip is broken in the venv.
      · 480 ln + 38 tests · needs: C-01, C-25 · *teaches: tool use, function calling, what MCP is*

## Group 3 · Repo intelligence — *where it first becomes worth using*

- [x] **C-06 · Symbol extractor** — Parses source into symbols and edges via
      tree-sitter, each with its exact file and line. Four languages ship. Every
      node-type name lives in `graph/languages.yaml` (D-033), so adding a language is a
      data change and `core/` names no language. Each edge carries a `resolution`
      (`exact` / `name_only` / `unresolved`) recording how firmly the syntax pinned its
      target down — a member call is kept *and* labelled rather than dropped or
      over-linked. Syntax errors are flagged, not fatal: whatever parsed is still
      returned.
      · 943 ln + 45 tests · needs: — · *teaches: parsing beats text processing; the unit you index decides everything*

- [x] **C-07 · Symbol store** — A SQLite index of every symbol *and every edge*, refreshed
      only for files whose content hash actually changed, plus FTS5 search over names.
      One database per indexed root, in JSpec's own `.sdd/index`, never in the repository
      being read (D-037). Traversal deliberately left to C-08 (D-038). Proven, not
      asserted: the extractor is injected so a test can count parses, and CI indexes this
      repo twice and fails if the second run parses a single file.
      · 674 ln + 33 tests · needs: C-06 · *teaches: incremental indexing, content addressing*

- [x] **C-08 · Blast radius** — "Who calls this, and who calls them?" — the transitive
      closure over the call and import graph. Change a shared thing, get the complete
      downstream list before touching it. A name walks the call graph, a file the import
      graph; both directions; breadth-first over `(node, tainted)` so every result is
      **certain or possible**; the depth searched is always reported, and the ring past
      the limit is peeked at so "cut short" is never guessed. An edge is certain only on
      evidence, and every simplification errs toward possible (D-039). **Over estimate:**
      ~810 lines against ~200 — the certainty model and the file graph were not in it.
      · ~810 ln + 54 tests · needs: C-07 · *teaches: deterministic grounding* · **first component that earns its keep**

## Group 4 · Context — *this is the RAG layer*

- [ ] **C-09 · Retriever** — Find the right handful of files instead of reading fifty. A
      ladder, cheapest first: exact → symbol → text → structural (graph) → semantic →
      merged rank. Stops as soon as a rung answers well enough.
      · ~250 ln · needs: C-07, C-08 · *teaches: RAG done properly — semantic search is the last resort, not the first*

- [ ] **C-10 · Context builder** — Assemble the prompt inside a token budget, expanding
      outward only as far as needed: symbol → enclosing class → related symbols →
      dependencies → file range → whole file.
      · ~300 ln · needs: C-09 · *teaches: context engineering — minimum SUFFICIENT context*

- [ ] **C-11 · Redactor** — Detect and strip secrets before any context is assembled.
      Never-send list from config. Fails closed: if the detector errors, block the send.
      · ~150 ln · needs: — · *teaches: fail-closed security design*

## Group 5 · Judgement — *the only part where a model thinks*

- [~] **C-12 · Template registry** — The prompt bodies as versioned data files, each
      declaring its output schema, question budget, token budget and rubric.
      **1 of 9 written** (`specify.yaml`). Missing: route, clarify, plan, decompose, risk,
      fix, review, converge.
      · ~400 ln left · needs: C-01 · *teaches: prompts as versioned, measurable artifacts*

- [ ] **C-13 · Judge port** — One interface, two ways to get a validated answer: an
      in-session tool schema, or headless `claude -p --json-schema` for CI and evals. No
      key-based path.
      · ~200 ln · needs: C-01, C-05 · *teaches: designing to a capability, not a vendor*

- [~] **C-14 · Skills & agents** — The model-facing layer. One router skill that triggers
      itself; every step skill locked so the model cannot skip into the middle. Plus the
      critic and refuter agents. **3 of ~9 done.**
      · ~600 ln left · needs: C-05, C-12 · *teaches: agent patterns — single-purpose agents, adversarial verification*

## Group 6 · Planning & governance — *the second big payoff*

- [ ] **C-15 · Decomposer** — Turn one spec into work packages with dependencies, each
      independently testable, each declaring the files it will touch.
      · ~250 ln · needs: C-01, C-12 · *teaches: decomposition — what makes a piece a piece*

- [~] **C-16 · Risk engine** — The arithmetic: score each item, combine per package as
      dominant-plus-tail, propagate up the dependency graph, amplify packages touching the
      same files, produce one verdict plus its top three drivers. **Formulas written in
      docstrings; 5 functions unimplemented.**
      · 97 → ~250 ln · needs: C-01, C-15 · *teaches: hybrid symbolic + neural; choosing granularity for a model's judgement*

- [ ] **C-17 · Gate ledger** — Append-only record of every approval: package, decision,
      approver, timestamp, risk score at approval, diff hash, evidence. Stringency scales
      with computed risk.
      · ~200 ln · needs: C-16 · *teaches: human-in-the-loop designed, not bolted on*

## Group 7 · The execution loop — *write, check, fix, stop*

- [ ] **C-18 · Generator** — Write the code following *this* repository's own patterns
      rather than generic ones — imports, structure, naming, error handling.
      · ~300 ln · needs: C-09, C-14, C-27 · *teaches: grounded generation — few-shot from the repo itself*

- [ ] **C-19 · Validator** — Run the real checks (lint, types, tests — commands come from
      the profile), parse the output, return a structured result.
      · ~200 ln · needs: C-01, C-25 · *teaches: closing the loop with ground truth* · **highest-leverage single component**

- [ ] **C-20 · Repair engine** — Classify the failure, pull failure-specific context,
      diagnose, patch, re-validate. Three attempts, then stop and escalate with a reason.
      · ~300 ln · needs: C-09, C-19 · *teaches: bounded self-correction — the engineering is in the CAP*

## Group 8 · Proof & learning — *what makes it compound*

- [!] **C-21 · Eval harness** — Score the artifacts the system produces against real
      examples using written rubrics, and report whether a change made things better or
      worse. **Blocked on the golden set** — 5–10 real cases (D-026: reconstruct from git
      history, owner corrects).
      · ~300 ln · needs: C-13 + golden set · *teaches: evals and LLM-as-judge — the most under-taught skill in AI*

- [ ] **C-22 · Experience store** — A searchable library of lessons, incidents and
      anti-patterns, retrieved by similarity to the task in front of you.
      · ~250 ln · needs: C-09, C-10 · *teaches: long-term memory that compounds; retrieval is the hard part*

- [ ] **C-23 · Traceability** — Requirement → spec → plan → code → test → result,
      followable in both directions.
      · ~200 ln · needs: C-01, C-17 · *teaches: provenance and explainability*

- [ ] **C-24 · Cost ledger** — Budget versus actual, per step, per run. The router reads
      this history to get cheaper over time.
      · ~150 ln · needs: C-05 · *teaches: observability — tokens per ACCEPTED outcome, not tokens used*

---

## Milestones — the order to build in

- [x] **M1 · It runs at all** — ~~`C-25`~~ → ~~`C-05`~~ · **done 2026-08-29**
      Skills call Python against a profile. `jspec classify "add password reset"` returns
      a route, a chain and a budget; `jspec validate` rejects a malformed artifact and
      names every field. **2 components, both done.**

- [x] **M2 · It knows the repo — stop here and use it** — ~~`C-06`~~ → ~~`C-07`~~ → ~~`C-08`~~ → ~~`C-26`~~ · **built 2026-10-23; the two-week use period starts now**
      Blast radius works. "What breaks if I change this?" answered completely, in
      milliseconds. **This alone is worth the project.** Use it for two weeks before
      building more — what you learn will change what you build next. **4 components.**

- [ ] **M3 · It writes grounded specs** — `C-09`, `C-10`, `C-11`, `C-12`, `C-13`, `C-14`, `C-27`
      A vague request becomes a validated spec, grounded in what the repo actually
      contains, attacked by a critic first. Largest block. **7 components.**

- [ ] **M4 · It governs** — `C-15`, `C-16`, `C-17`
      Work packages, a risk verdict with three named drivers, gates priced to risk, a
      permanent approval ledger. Second natural stopping point. **3 components.**

- [ ] **M5 · It proves itself** — `C-21`
      Buildable any time after M3. Do not skip: everything after it is unmeasurable
      without it, and unmeasurable improvements tend not to be improvements. **1 component.**

- [ ] **M6 · It closes the loop** — `C-19` first, then `C-18`, `C-20`, `C-22`, `C-23`, `C-24`
      Generate, validate, repair, remember, trace, measure. C-19 first because ground
      truth improves everything upstream of it. **6 components.**

---

## Open questions blocking work

| # | Question | Blocks |
|---|---|---|
| 2 | Risk band thresholds, and who counts as a named approver | C-17 |
| 3 | How does headless `claude -p` authenticate inside a CI pipeline? | CI rollout only |
| 4 | Directory-management access in the Aptean Enterprise org | public marketplace only |

Settled: language data lives beside the extractor, not in config or profiles (D-033) ·
code-graph scope (D-032, one root + all sub-folders) · C-05 shape (D-025,
bundled scripts) · golden set method (D-026, reconstruct then correct) · no frameworks / no Ollama (D-024) · domain neutrality gets components
(D-027) · deliver in chat (D-028).
