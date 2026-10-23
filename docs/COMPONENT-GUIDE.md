# JSpec — Component Guide

**What this file is:** a plain-language description of all 27 components, detailed
enough that you can decide what you want and tell me to build it.

**Companion files:**
- `memory/AGENDA.md` — the short checklist. What is done, what is next.
- This file — the long explanation of each item on that checklist.

**JSpec is a general tool.** It must work for any team's project — a test suite, a web
service, a mobile app, a data pipeline. Nothing here is specific to one company or one
framework. All project-specific knowledge lives in `profiles/*.yaml` (see C-25).

---

## How to read each entry

| Field | Means |
|---|---|
| **In one line** | What it is, no jargon |
| **Why it exists** | What goes wrong without it |
| **What it actually does** | The steps, in order |
| **Takes in / Gives back** | Its inputs and outputs |
| **Done when** | How we know it is finished — the acceptance test |
| **Depends on** | What must exist first |
| **How to instruct me** | A sentence you can literally type |
| **What you learn** | The AI-engineering idea behind it |

## How to instruct me — the general pattern

You do not need to write a specification. A short instruction plus the component ID is
enough, because this file and `AGENDA.md` are on disk and I read them first.

The shortest form that works:

> `Build C-08.`

The better form, which removes ambiguity:

> `Build C-08 blast radius. Read the component guide first. I want forward and reverse
> traversal, and it must tell me the depth it searched.`

Add any of these when you care about them:
- **Scope:** "just the forward direction for now"
- **Constraint:** "no new dependencies" / "must work on Windows"
- **Order:** "write the tests first"
- **Depth:** "explain it as you go" (the default, per D-023) or "just build it, explain after"

If something in your instruction conflicts with this file, **your instruction wins** —
but I will say so once before proceeding, so a mistake gets caught early rather than
built.

---

# Group 1 · Foundation

*The base everything else sits on. All four are built and tested.*

---

## C-01 · Contracts ✅ done · 724 lines

**In one line:** The rulebook for what every piece of output must look like.

**Why it exists:** When you ask a model for structured information, you normally get
something *close* to what you wanted. A field missing here, a list where you expected a
number there. If the next step trusts that output, the damage travels. Contracts stop it
at the door: output that does not match the shape is rejected before anything else sees
it.

**What it actually does:**
1. Defines each artifact as a strict shape — a spec has user stories, requirements with
   IDs, success criteria that must contain a measurable number, and so on.
2. Defines shared building blocks used by all of them: an ID, a confidence score between
   0 and 1, an evidence list that must contain **at least one** entry.
3. Turns every shape into a machine-readable schema, so both in-session tools and
   headless runs validate against the same definition.
4. Fails loudly on an unknown artifact type instead of silently accepting anything.

**Takes in:** a candidate object (usually from a model).
**Gives back:** either a validated object, or a list of exactly what was wrong with it.

**Done when:** ✅ already met — 7 modules, no unimplemented functions, tests cover
accepting good specs, rejecting bad ones, and blocking planning when the spec is
ambiguous.

**Depends on:** nothing.

**How to instruct me:** *"Add the Review contract to C-01"* — when a later component
needs a new artifact shape.

**What you learn:** **Structured output.** The single most useful production-AI
technique. Look at one line: `Evidence = list[str]` with `min_length=1`. That is "cite
your source" enforced by the type system — an unevidenced claim cannot be constructed at
all. Compare that to writing "please include evidence" in a prompt and hoping.

---

## C-02 · Router ✅ done · 222 lines

**In one line:** Decides how much process a request deserves, before spending anything.

**Why it exists:** Running a full specification pipeline on a one-line typo fix costs
more than the fix is worth. But you also cannot skip the pipeline for a large feature.
Something has to judge which is which — cheaply, or the judging becomes the expense.

**What it actually does:**
1. Reads the request text and scores it against four depths: trivial, fix, feature,
   broad sweep.
2. Scores using signals it can measure — a stack trace present, failure words, creation
   words, breadth words, how many files are named, how long the request is.
3. Mixes in facts from the repository, which outrank the wording because they are
   measured rather than inferred: are tests currently failing, how many files does the
   change look like it touches, what did this user do last time.
4. Picks the highest score, and works out how confident to be from two things — how far
   ahead the winner is, **and** whether there was enough evidence to trust the win.
5. If nothing matched at all, it refuses to guess: it returns the cheap route with zero
   confidence and flags that a human or a model should decide.
6. Outputs the chosen depth, the list of steps to run, a token budget and a question
   budget.

**Takes in:** the raw request text, plus optional repository facts.
**Gives back:** depth, confidence, the steps to run, token budget, question budget, and
the list of signals that produced the decision.

**Done when:** ✅ already met — tested for route selection, confidence behaviour, repo
facts outranking wording, and budget lookup.

**Depends on:** C-01.

**How to instruct me:** *"Wire C-02 to real repo facts from C-08"* — currently it runs on
defaults because the index does not exist yet.

**What you learn:** **When *not* to call a model.** Most systems marketed as "AI agents"
spend tokens deciding what to do. That decision is usually cheap and deterministic. Also
worth studying: the confidence formula deliberately refuses to be confident on thin
evidence. An overconfident classifier is worse than an uncertain one, because nothing
downstream knows to double-check it.

---

## C-03 · Memory ✅ done · ~550 lines

**In one line:** Makes a new chat continue where the last one stopped.

**Why it exists:** Every new conversation starts blank. Without something on disk, you
re-explain the project every time, and decisions made last week get re-argued or
silently reversed.

**What it actually does:**
1. A small always-loaded file (`CLAUDE.md`) carries the working rules — read this at
   start, write that at the end, never do this.
2. `AGENDA.md` carries build state — what is done, what is next.
3. `STATE.md` carries the current situation, open questions and hazards. Overwritten, so
   it always describes now.
4. `journal/YYYY-MM-DD.md` records every session — append-only, never edited.
5. `DECISIONS.md` records every decision with its reasoning — append-only. A past entry
   is superseded by a new one, never rewritten.
6. A session-start hook surfaces state automatically, so it does not rely on anyone
   remembering to look.

**Takes in:** what happened in a session.
**Gives back:** enough context for a blank chat to resume without asking you anything.

**Done when:** ✅ met and in daily use. Outstanding: the session-start hook has not been
tested end to end.

**Depends on:** nothing.

**How to instruct me:** *"Test the C-03 session-start hook and fix it if it does not
fire."*

**What you learn:** **Memory architecture with tiers.** Three kinds of memory with
different lifespans and different sizes: rules (small, stable, always loaded), state
(medium, overwritten), history (large, append-only, read on demand). The common failure
is one growing memory file — it eventually fills the context window and squeezes out the
actual work.

---

## C-04 · Guardrails ✅ done · ~300 lines

**In one line:** Turns the project's rules from suggestions into things that cannot be
violated.

**Why it exists:** A rule written in a document is advice. Under time pressure, advice
loses. A rule enforced by an automated check does not lose.

**What it actually does:**
1. `constitution.md` states the non-negotiable rules and their order of precedence.
2. `config.yaml` holds every tunable setting in one place — token budgets, retrieval
   order, the never-send list, risk weights, repair limits.
3. CI runs on two Python versions and checks: lint, formatting, tests.
4. CI also checks the things a human reviewer would miss — that config files parse, that
   every prompt template declares its four required fields, that every skill declares a
   description, and that no skill except the router can trigger itself.
5. One check exists purely to protect the project's hardest constraint: **the build fails
   if an API key or a forbidden flag appears anywhere in the source.**

**Takes in:** the repository, on every push.
**Gives back:** pass, or a failure naming the exact rule broken.

**Done when:** ✅ met. Ongoing: add a check whenever a new invariant is agreed.

**Depends on:** nothing.

**How to instruct me:** *"Add a CI check to C-04 that fails if anything domain-specific
appears in core/"* — that would enforce D-027 mechanically.

**What you learn:** **Policy as data, enforced mechanically.** For every rule you write,
ask: what would make this impossible rather than merely discouraged? Most real safety
engineering in software looks like this — unglamorous automated checks, not clever
design.

---

# Group 1b · Adaptation

*What makes JSpec work for anyone's project instead of one team's. All three are new
(added 26 Aug) and none exist yet.*

---

## C-25 · Profile engine ✅ done · 258 lines + 21 tests

> **As built (D-030):** shipped deliberately thin. `extends` / override
> resolution, `risk_signals` and `templates` are all deferred until a component
> actually reads them - an inheritance system with one user is a configuration
> language nobody asked for. Three profiles ship; two CI gates enforce them.

**In one line:** The one place where facts about a specific project are allowed to live.

**Why it exists:** JSpec has to work for a test suite, a web service, a mobile app and a
data pipeline. If knowledge about any one of those leaks into the main code, the main code
slowly fills with special cases until adding a new kind of project means changing code
instead of writing a config file. That is how a general tool quietly becomes a
single-team tool.

**What it actually does:**
1. Defines the `Profile` shape: which languages, where tests live, where shared code
   lives, the command that runs the tests, what counts as "validated", what counts as
   "risky" here, which prompt templates to use, the team's conventions.
2. Loads a profile from `profiles/<name>.yaml` and validates it — a broken profile fails
   at load with a clear message, not silently at use.
3. Resolves overrides, so a project can adjust a base profile without copying it.
4. Every other component asks the profile instead of assuming. "How do I run the tests?"
   is a profile question, never a hard-coded string.

**Takes in:** a profile name, or a project directory to resolve one for.
**Gives back:** a validated profile object every other component reads from.

**Done when:**
- The `Profile` contract exists and is validated like every other artifact
- Two **deliberately different** examples ship — one test-suite profile, one web-service
  profile — so nobody mistakes one for the model
- A missing or malformed profile fails loudly at load, naming the problem
- No other component contains a hard-coded language, framework or path

**Depends on:** C-01.

**How to instruct me:** *"Build C-25. Contract first, then loader and override resolution.
Ship two different example profiles. Nothing outside the profile should know what
framework we are looking at."*

**What you learn:** **Where to put the generalization boundary.** Every tool serving more
than one team has exactly one of these lines, and it fails in two directions. Too deep in
the code and you get endless special cases. Too far out and the profile becomes a second
program nobody can write, so nobody adopts it. The test is one question: **can a new kind
of project be added by writing only data?** Build this *before* the first tools, or they
will bake in assumptions you then have to dig back out.

---

## C-26 · Project profiler ✅ done · ~885 lines + 66 tests

**In one line:** Point it at a repository it has never seen, and it works out what the
project is.

**Why it exists:** Asking a new user to hand-write a config file before the tool does
anything useful is how tools die at install. Nobody configures a thing that has not yet
proved itself.

**What it actually does:**
1. Looks for the obvious evidence first — manifest files, lock files, config files,
   declared dependencies. These give near-certain answers.
2. Infers layout from the symbol index: where do most test files live, which directory is
   imported by the most others (that is the shared code), where is the entry point.
3. Guesses the rest from naming conventions — and **marks every guess as a guess.**
4. Writes a draft profile with confidence noted per field.
5. Shows the user the draft, asks them to correct it, saves the corrected version.

**Takes in:** a path to a repository.
**Gives back:** a draft profile, with each field marked *found* or *guessed*.

**Done when:**
- Run against three genuinely different repositories, it produces a usable draft for each
- Every field says whether it was found in a config file or inferred
- The user's corrections are saved and never asked about again
- It never silently invents a value — an unknown field is left empty and flagged

**Depends on:** C-06, C-07, C-25.

**How to instruct me:** *"Build C-26. Detect from manifests first, infer layout from the
index second, guess from naming last. Every field must record whether it was found or
guessed. Test it against three different repos."*

**What you learn:** **Zero-configuration onboarding, and honest uncertainty.** The design
rule is that the tool must be useful *before* it is configured. But the genuinely
interesting engineering is the confidence marking. "Tests are in `tests/`" (found the
config — certain) is a different claim from "shared code is probably `utils/`" (guessed
from a folder name). **A draft that hides which parts are guesses is worse than no
draft**, because the user skims it once and then trusts all of it equally.

**As built.** `core/src/jspec/profiler.py`, with every ecosystem fact in
`profiler_rules.yaml` (a four-condition rule language: file, toml, dep, script). Two
commands: `jspec profile draft ROOT [--name N] [--set FIELD=VALUE] [--use-index]` writes a
field-by-field draft to JSpec's own `.sdd/drafts/` and prints what needs attention;
`jspec profile accept NAME [--accept-guesses] [--overwrite]` writes `profiles/<name>.yaml`
only if nothing blocks it. Each field is `found`, `inferred`, `guessed`, `confirmed` or
`unknown`, with evidence; a person's `--set` is `confirmed` and survives every later draft.
Design in D-040.

**Beyond or short of the guide:** the draft is its own contract (`profile_draft`), because a
real `Profile` cannot hold an unknown test command. Layout from the symbol index is an
*observation*, since no profile field can hold "shared code" yet (D-030). **Short of it:**
validated on three synthetic repositories and this one, **not on a real external
repository** — the owner's scope rule forbids reading others, so that remains open. Only
root-level manifests are read; nested ones are reported as unread. On this repository it
gets languages, source dirs, test dirs and the test command right, and reports
lint/format/typecheck as unknown because their config is in `core/pyproject.toml`.

---

## C-27 · Convention learner ⬜ not started · ~250 lines

**In one line:** Works out how *this* team actually writes code, so output looks like
theirs.

**Why it exists:** Generated code that is technically correct but stylistically foreign
gets rewritten by hand, which means the tool saved nothing. And you cannot get this from a
settings file — nobody fills one in honestly, and nobody keeps it updated.

**What it actually does:**
1. Scans the symbol index for repeated patterns: naming style, file organisation, how a
   common operation is normally done here, what usually appears at the top of a file.
2. Counts how often each pattern occurs versus its alternatives.
3. Records a pattern as a convention **only** when it is frequent enough to be a rule
   rather than one person's habit.
4. Stores these as preferences, and feeds them into the prompt when generating.
5. Re-checks periodically, because conventions drift.

**Takes in:** the symbol index, plus a threshold for what counts as a convention.
**Gives back:** a list of observed conventions with how often each was seen.

**Done when:**
- Given a repository with a clear house style, it names that style correctly
- A pattern appearing twice does not become a rule; one appearing in most files does
- Every recorded convention carries its evidence count, so you can argue with it
- Conventions feed into generation and visibly change the output

**Depends on:** C-07, C-09, C-25.

**How to instruct me:** *"Build C-27. Frequency analysis over the index, with a
configurable threshold. Every convention must record how many times it was observed."*

**What you learn:** **Observed preferences beat configured ones.** The code never lies
about how a team really works. The hard question here is statistical, not technical: **how
many occurrences turn a pattern into a convention?** Set the threshold too low and you
will confidently enforce one developer's bad habit on everyone — which is worse than
having no conventions at all, because now it is automated.

---

# Group 2 · The bridge

*Nothing in the system runs until this exists.*

---

## C-05 · Tool surface ✅ done · 480 lines + 38 tests

> **As built (D-031):** one `jspec` command, not per-skill scripts. 3 of the 10
> tools are live; the other 7 raise `ToolUnavailable` naming their blocker. The
> third live tool is `plan_chain`, **not** the `blast_radius` named below -
> that needs C-07, which did not exist. Deviation recorded rather than glossed.

**In one line:** How the model-facing side actually calls the Python side.

**Why it exists:** Right now there are two halves that cannot talk. The skills describe
what to do; the Python does the exact work. Ten connecting functions are named and
documented, and **every single one is empty.** Nothing can be tested until they are not.

**What it actually does:**
1. Exposes typed functions the model can call: classify a task, validate an artifact, ask
   what breaks, find existing code, score risk, record an approval, record a preference,
   record cost.
2. Each takes structured input and returns structured output — never prose.
3. Validates input against the contracts before doing anything.
4. Reads all project-specific behaviour from the profile (C-25), never from hard-coded
   values.
5. Runs as scripts bundled inside the skill folders, called with Bash (decision D-025 — an
   MCP server wraps the proven ones later).

**Takes in:** a function name and structured arguments.
**Gives back:** structured output, or a clear error.

**Done when:**
- Three tools work end to end from inside a real session: classify a task, validate an
  artifact, ask what breaks
- Each validates its input and returns a useful message on bad input
- No hard-coded project assumptions — everything project-specific comes from the profile
- A skill can call one and use the result without any manual step

**Depends on:** C-01, C-25.

**How to instruct me:** *"Build C-05 with three tools first — classify_task,
validate_artifact, blast_radius. Bundled scripts, not MCP. Read the profile for anything
project-specific. Show me it working from a real session."*

**What you learn:** **Tool use and function calling — what "agent" actually means.** Write
one of these by hand and the mystique disappears entirely. The mechanism is a loop: the
model picks a tool, your code runs it, the result goes back into the conversation, the
model continues. That is all there is. The schema on each tool does double duty as both
documentation and validation, which is why C-01 had to come first.

---

# Group 3 · Repo intelligence

*Where the tool first becomes worth opening in the morning.*

---

## C-06 · Symbol extractor ✅ done · 943 lines + 45 tests

> **As built (D-033, D-034):** four languages ship. Every grammar node-type name
> lives in `core/src/jspec/graph/languages.yaml`, so no module in `core/src`
> names a language and adding one is a data change. Every reference carries a
> `resolution` - `exact`, `name_only` or `unresolved` - recording how firmly the
> syntax pinned its target down, rather than dropping uncertain edges or
> over-linking them. Run it with `jspec extract --profile <name>`.

**In one line:** Reads source code properly, instead of treating it as text.

**Why it exists:** Everything downstream — finding things, knowing what breaks, matching
the house style — depends on knowing what is actually in the code. Searching text finds
matches in comments and strings and misses everything indirect. A parser knows a function
is a function.

**What it actually does:**
1. For each source file, parses it into a syntax tree using tree-sitter.
2. Walks the tree pulling out what matters: functions, classes, methods, imports, exports,
   and which things call which.
3. Records each with its exact file and line, so every later answer can be checked.
4. Handles multiple languages behind one interface — which languages to load comes from
   the profile, not a hard-coded list.
5. Skips what it should not read: build output, dependencies, and anything on the
   never-send list.

**Takes in:** a file or directory, plus the profile's language list.
**Gives back:** a list of symbols, each with kind, name, file, line, and relationships.

**Done when:**
- Two genuinely different languages are extracted through the same interface
- Every symbol carries an accurate file and line, spot-checked by hand
- A syntax error in one file does not stop the run — it is reported and skipped
- Adding a language requires a profile change, not a code change

**Depends on:** nothing (but pairs with C-25).

**How to instruct me:** *"Build C-06 using tree-sitter. One extractor interface, languages
driven by the profile. Start with one language and prove the interface before adding a
second."*

**What you learn:** **Parsing beats text processing — and the unit you index decides
everything downstream.** This is the first serious lesson about retrieval. The standard
tutorial approach chops files into fixed-size chunks and embeds them, which shreds exactly
the structure that makes code answerable. A function is a natural unit. An import is a real
edge. Throwing those away to make everything look like prose is a downgrade, not a
simplification.

---

## C-07 · Symbol store ✅ done 2026-09-16 · 674 lines + 33 tests

**In one line:** Remembers everything C-06 found, and updates only what changed.

**Why it exists:** Re-parsing an entire repository every time you ask a question makes the
tool too slow to use. A tool too slow to use does not get used.

**What it actually does:**
1. Stores every symbol in a local SQLite database with its file, line, kind and
   relationships.
2. Records a hash of each file's contents alongside it.
3. On refresh, re-reads only files whose hash changed. Everything else is left alone.
4. Adds a full-text index, so text search is fast without a separate tool.
5. Handles deleted and renamed files without leaving stale entries behind.

**Takes in:** the symbols from C-06.
**Gives back:** fast lookup by name, by file, by kind, or by text.

**Done when:**
- A full index of a large repository completes in a time you would tolerate
- Re-indexing after changing one file takes about a second
- Deleting a file removes its symbols
- A query by name returns the right answer with correct file and line

**Depends on:** C-06.

**How to instruct me:** *"Build C-07. SQLite, content-hash based incremental refresh, plus
full-text search. Prove the incremental path: index everything, change one file, re-index,
and show me only that file was re-read."*

**What you learn:** **Content addressing.** Hash the contents, never trust the timestamp —
timestamps lie after a checkout, a copy, or a clock change. This exact idea sits underneath
Git objects, build caches and container layers, so learning it once pays off everywhere.

**As built.** `core/src/jspec/graph/store.py`, SQLite via the standard library, schema
version 1. Reuses C-06's `iter_source_files` for the walk and `extract_file` per dirty
file rather than adding a second walker. FTS5 is probed rather than assumed, and
`search()` names the missing module if a SQLite build lacks it instead of silently
degrading. `jspec index` and `jspec find` are the two new commands; `find_existing`
became the fourth ready tool in the registry, and `blast_radius` moved from "blocked by
C-07" to "blocked by C-08" (D-038); C-08 has since made it the fifth ready tool.

**Measured on the Made2Manage suite** (1,885 files, 8,911 symbols, 199,615 references):
full index 10.9 s, **re-index with nothing changed 1.9 s and zero files parsed**, one
file edited 2.5 s, database 67.5 MB. Queries: exact name 0.53 ms, FTS prefix 0.69 ms,
one-hop callers 0.24 ms — against 13,800 ms to answer the same question by re-parsing.

**Deviation from "about a second".** A no-change re-index costs 1.9-2.4 s on that suite,
not ~1 s: the floor is the directory walk plus a full read of every file to hash it. The
fix is git's other trick, a stat-based pre-filter before hashing, deferred with its
reason in D-038 rather than quietly counted as met.

**Where the decisions are:** D-037 (one database per root, in JSpec's `.sdd/index`, never
in the indexed repository) and D-038 (edges stored but traversal left to C-08;
full text over names, not bodies).

---

## C-08 · Blast radius ✅ done · ~810 lines + 54 tests · **first component that earns its keep**

**In one line:** Tells you everything that will break, before you change anything.

**Why it exists:** This is the most expensive question in most working weeks, and today it
is answered by hand with a text search. Text search misses indirect callers — A calls B,
and B calls the thing you are changing — and it finds false matches in comments. You
discover what was missed when the build breaks, hours later.

**What it actually does:**
1. Takes a name: a function, class or file.
2. Looks it up in the index and finds everything that directly calls or imports it.
3. Then finds everything that calls *those*, and repeats. That is what makes it complete
   rather than a single hop.
4. Detects cycles and refuses to loop forever.
5. Stops at a depth limit and **reports the depth it reached**, so a truncated answer never
   looks like a complete one.
6. Works in reverse too: "what does this thing depend on?"
7. Returns the chain for each result, so you can see *how* something is connected, not just
   that it is.

**Takes in:** a symbol name, optionally a file to disambiguate, optionally a depth limit.
**Gives back:** affected files and symbols, the connection path for each, a total count,
and the depth searched.

**Done when:**
- On a small hand-built test repository, it returns every caller — verified manually
- Circular references do not hang it
- The depth searched is always reported
- Reverse direction works
- It runs fast enough to use casually, not as a special occasion

**Depends on:** C-07.

**How to instruct me:** *"Build C-08. Forward and reverse traversal over the C-07 index,
cycle-safe, depth-limited with the depth reported. Include the connection chain for each
result. Test it against a small repo where I can check the answer by hand."*

**What you learn:** **Deterministic grounding.** The reason to compute this rather than ask
a model is that a model returns a plausible answer and this returns a fact. Every AI system
you would actually trust has a layer like this underneath the language model — the model
handles judgement, this handles truth. Confusing those two is the most common architectural
mistake in AI tooling.

**As built.** `core/src/jspec/graph/traverse.py`; `jspec blast-radius TARGET [root]
[--direction dependents|dependencies] [--file F] [--depth N] [--limit N]`; `blast_radius`
is the fifth ready tool. A name walks the call graph, a file walks the import graph. Every
result is **certain or possible**, and the answer always carries the depth searched
(`limit / reached / complete / stopped_by`), what it cannot see (`limits`), and how
complete the index is (`index`). Design in D-039.

**Beyond the guide's list:** the certain/possible split (72% of the M2M graph is
`name_only`), the import graph for file targets, class targets that include their
methods, and `entry_stems` in `languages.yaml`. **Measured on M2M:** `ensureAvaTaxEnabled`
in 0.56 s end to end, two possible dependents, matching the two real call sites exactly.
**Honest limit:** a common name like `click` returns 0 certain and 8,143 possible — correct,
and not useful; narrowing by what a file imports would sharpen it (deferred, D-039).

---

# Group 4 · Context

*This is the retrieval layer — what most people mean when they say "RAG".*

---

## C-09 · Retriever ⬜ not started · ~250 lines

**In one line:** Finds the right handful of files instead of reading fifty.

**Why it exists:** A model given too little context invents things. Given too much, it
loses the thread in the middle and costs a fortune. Something has to pick the few files
that actually matter for this specific question.

**What it actually does:** Tries methods in order, cheapest and most precise first, and
stops as soon as one answers well enough.
1. **Exact** — the request names a file or symbol directly. Just fetch it.
2. **Symbol** — look the name up in the index. Precise, instant.
3. **Text** — full-text search across the indexed content.
4. **Structural** — walk the graph. "What is connected to this thing?"
5. **Semantic** — meaning-based search, for when the words do not match but the intent
   does. **This is the last resort, not the first.**
6. **Merge** — combine results from whichever rungs ran, ranked, with the score visible so
   you can see why each file was chosen.

**Takes in:** a request, plus the profile and the index.
**Gives back:** a ranked list of files or symbols, each with a score and the reason it was
picked.

**Done when:**
- Each rung works on its own and can be tested on its own
- A request naming a file directly never reaches the expensive rungs
- Every result explains why it was chosen
- The semantic rung can be switched off entirely and the system still works

**Depends on:** C-07, C-08.

**How to instruct me:** *"Build C-09 as a ladder. Each rung a separate function, stop early
when a rung answers. Skip the semantic rung for now — build the first four and show me
where they fail before we add embeddings."*

**What you learn:** **RAG, done properly.** Notice where semantic search sits: second to
last. The tutorial version of RAG — chunk everything, embed it, take the closest match — is
the *weakest* rung on this ladder, and for code it is actively harmful. Exact and symbol
lookup are faster, cheaper and exactly precise. **Reach for embeddings when you can
demonstrate the cheap rungs failing on a real question, and not one day sooner.** Building
the vector store first is the most common and most expensive mistake in this whole field.

---

## C-10 · Context builder ⬜ not started · ~300 lines

**In one line:** Fits what the model needs to know into the space available.

**Why it exists:** Retrieval finds candidate files. That is not the same as a prompt. Files
have to be trimmed, ordered and fitted inside a budget — and a budget that is silently
exceeded produces a truncated prompt, which produces confident nonsense.

**What it actually does:**
1. Counts tokens for real, rather than estimating.
2. Starts narrow: just the symbol in question.
3. Expands outward only as far as needed — the enclosing class, then related symbols, then
   its dependencies, then a range of the file, then the whole file. It stops the moment it
   has enough.
4. If the budget is exceeded, compresses: summarise the less relevant parts rather than
   dropping them silently.
5. Records what was included, what was left out, and what it cost — so an unhelpful answer
   can be traced to what the model was actually shown.

**Takes in:** the retrieval results, a token budget, and the task.
**Gives back:** the assembled context, plus a record of what was included and dropped.

**Done when:**
- Token counts are accurate, not estimated
- The expansion ladder is visible in the output — you can see how far it went
- Exceeding the budget compresses rather than truncating
- Every run records what was included and what it cost

**Depends on:** C-09.

**How to instruct me:** *"Build C-10. Real token counting, the expansion ladder from
narrowest to widest, compression on overflow. Log what was included and dropped every
time."*

**What you learn:** **Context engineering** — the discipline that separates working AI
systems from impressive demos. The target is **minimum *sufficient* context**: not minimum,
not maximum. Too little and the model hallucinates; too much and it loses information in
the middle of a long prompt. Both failures look like "the AI is bad" and neither one is.
The skill is measuring instead of guessing.

---

## C-11 · Redactor ⬜ not started · ~150 lines

**In one line:** Makes sure secrets never end up in a prompt.

**Why it exists:** Almost no real data leak in an AI system is a clever attack. It is a
credentials file that got swept into context by a careless pattern match, and then sent
somewhere.

**What it actually does:**
1. Holds a never-send list — environment files, credential files, keys, certificates, and
   anything the profile adds.
2. Scans candidate content for secret-shaped patterns even in files that passed the list.
3. Redacts what it finds, and records that a redaction happened.
4. **Fails closed:** if the detector itself errors, the send is blocked. It never falls
   through to "probably fine".

**Takes in:** any content about to be assembled into context.
**Gives back:** the safe version, plus a record of what was removed — or a hard stop.

**Done when:**
- A file on the never-send list cannot reach context by any path
- A secret pasted inside an otherwise ordinary file is caught
- A deliberately broken detector blocks the send rather than passing it
- Every redaction is logged

**Depends on:** nothing.

**How to instruct me:** *"Build C-11. Never-send list plus pattern detection, fail closed.
Write a test that breaks the detector on purpose and proves the send is blocked."*

**What you learn:** **Fail-closed design.** When a safety check cannot run, the safe answer
is no, not yes. This is one line of design thinking that separates systems you can put in
front of an auditor from systems you cannot.

---

# Group 5 · Judgement

*The only part of the system where a model does the thinking.*

---

## C-12 · Template registry 🟡 1 of 9 · ~400 lines remaining

**In one line:** The prompts, stored as proper versioned files instead of buried in code.

**Why it exists:** A prompt hidden inside code cannot be compared, budgeted or graded — so
nobody can tell whether editing it made things better or worse. Every prompt here declares
four things that make it improvable: what shape it must output, how many questions it may
ask, how many tokens it may spend, and which rubric grades it.

**What it actually does:**
1. Keeps each prompt in its own file with those four declarations at the top.
2. A registry lists them all, so the router can look up which one to use.
3. Prompts take named inputs — the request, what already exists in the codebase, known
   preferences, the profile — and fill them in.
4. Each declares checks its output must pass, beyond just matching the shape.
5. CI refuses to build if any template is missing one of the four required fields.

**Takes in:** a template name plus its inputs.
**Gives back:** the filled-in prompt, with its budgets and its output shape attached.

**Done when:**
- All nine exist: route, specify, clarify, plan, decompose, risk, fix, review, converge
- Each declares output shape, question budget, token budget and rubric
- Each has been run at least once and produced valid output
- No prompt text lives anywhere else in the codebase

**Depends on:** C-01.

**How to instruct me:** *"Build the C-12 plan template. Copy the structure of specify.yaml.
Keep the token budget under X."* — one at a time is fine; they are independent.

**What you learn:** **Prompts as versioned, measurable artifacts.** This is the difference
between prompt *fiddling* and prompt *engineering*. If you cannot diff a prompt, budget it
and grade it, you are guessing — and you will confidently make it worse at some point
without noticing.

---

## C-13 · Judge port ⬜ not started · ~200 lines

**In one line:** One way to ask for a validated answer, whichever mechanism runs underneath.

**Why it exists:** There are two genuinely different ways to get structured output here — a
tool schema inside a live session, or a headless command in CI. The rest of the system
should not have to know or care which one ran.

**What it actually does:**
1. Defines one interface: here is a prompt and a required output shape, give me a validated
   object.
2. Backend one: in-session, using the tool schema mechanism.
3. Backend two: headless, using a command-line call that returns validated JSON.
4. Neither requires an API key — both run on the existing Claude Code login.
5. Returns the object plus what it cost.

**Takes in:** a prompt, a required output shape, and which backend to use.
**Gives back:** a validated object, plus the cost.

**Done when:**
- The same request through both backends produces the same shape of result
- Nothing downstream can tell which backend ran
- Neither path requires a key, and CI still proves no key is needed
- Cost is reported

**Depends on:** C-01, C-05.

**How to instruct me:** *"Build C-13 with both backends. Prove the same call works through
each and downstream code cannot tell the difference."*

**What you learn:** **Designing to a capability, not a vendor.** Portability does not mean
"we support five providers" — it means the rest of the system cannot tell which one is
running. That distinction is what makes a system survive a provider change.

---

## C-14 · Skills & agents 🟡 3 of ~9 · ~600 lines remaining

**In one line:** The model-facing layer — what actually decides and drafts.

**Why it exists:** Someone has to do the judgement work: reading the request, writing the
spec, criticising it, planning the change. That is the model's job, and skills are how you
give it a specific job rather than a vague one.

**What it actually does:**
1. One entry-point skill triggers itself from what you type — you never need to remember a
   command name.
2. Every other skill is **locked**, so the model cannot jump into the middle of the pipeline
   and skip the spec.
3. Each skill does one thing: route, specify, plan, decompose, review, repair.
4. Two adversarial agents exist to attack output rather than produce it: a critic that
   attacks a spec for untestable requirements and hidden ambiguity, and a refuter whose only
   job is to disprove a claim.
5. The refuter is spawned three times per claim, and a majority disproof kills the claim.

**Takes in:** whatever you typed, plus the context and the template.
**Gives back:** a drafted artifact that has already survived criticism.

**Done when:**
- Skills exist for plan, decompose, review, repair and converge
- Only the entry-point skill can trigger itself; CI enforces this
- The critic runs on every spec before you see it
- The refuter pattern is wired and demonstrably kills a bad claim

**Depends on:** C-05, C-12.

**How to instruct me:** *"Build the C-14 review skill and wire the critic loop so no spec
reaches me unattacked."*

**What you learn:** **Agent patterns that actually work.** Two ideas worth taking away.
Several single-purpose agents beat one omniscient prompt. And **adversarial verification** —
three independent attempts to disprove a claim, majority wins — catches plausible-but-wrong
output far better than asking the same model to check its own homework. This is the useful
kind of multi-agent design, as opposed to the "team of seven AI employees" version that is
mostly theatre.

---

# Group 6 · Planning & governance

*The second big payoff, and the part that makes this defensible to anyone senior.*

---

## C-15 · Decomposer ⬜ not started · ~250 lines

**In one line:** Breaks one specification into pieces that can each be built and checked
separately.

**Why it exists:** Large changes fail as one big lump because nothing is verifiable until
the end. Splitting them lets each piece be proven before the next starts.

**What it actually does:**
1. Reads the validated spec.
2. Produces work packages, each with what it does, which files it will touch, and what
   proves it works.
3. Records dependencies between them — what must be done before what.
4. Checks the dependency graph for cycles and refuses a circular plan, because that is a
   decomposition bug worth surfacing.
5. Each package must be independently testable. If it cannot be, it gets folded into one
   that can.

**Takes in:** a validated spec.
**Gives back:** a validated plan — packages, dependencies, and what each touches.

**Done when:**
- Every package states its own test
- The dependency graph is acyclic, and a cycle is rejected with a message
- Every package names the files it expects to touch, which C-16 needs
- A package that cannot stand alone is merged rather than shipped as half a thing

**Depends on:** C-01, C-12.

**How to instruct me:** *"Build C-15. Every package must be independently testable and
declare what it touches. Reject cyclic plans."*

**What you learn:** **Decomposition, and what makes a piece a piece.** Splitting is easy.
The hard constraint is *independently verifiable* — if a package cannot be tested on its
own, it is half of something, and it will hide its own failure until integration.

---

## C-16 · Risk engine 🟡 stub · 97 → ~250 lines

**In one line:** Turns risk judgements into one number and one verdict you can act on.

**Why it exists:** Written risk notes cannot be added up, ranked or compared between runs.
Numbers can. And a reviewer looking at forty work packages reads none of them, whereas a
reviewer given one verdict and its three main causes reads all three.

**What it actually does:**
1. The model supplies four judgements per risk on a 1–5 scale: how likely, how bad, how
   reversible, how detectable.
2. Each item is scored — with reversibility and detectability acting as **multipliers**, not
   additions, because an irreversible change only production catches is categorically worse
   than a reversible one CI catches.
3. Each package combines its items as **dominant plus tail** — the worst risk, plus a small
   fraction of the rest. A plain sum dilutes one severe risk among ten trivial ones; a plain
   maximum makes the ten trivial ones free.
4. Risk propagates up the dependency graph — a foundation package carries the exposure of
   everything depending on it.
5. Packages touching the same files are treated as **correlated**, not independent, because
   independent-risk maths under-reports shared-surface exposure.
6. Produces one verdict — go, go with gates, or no-go — plus the top three drivers.

**Takes in:** risk items per package, the dependency graph, and what each package touches.
**Gives back:** a per-package score, a single verdict, and the three main causes.

**Done when:**
- All five functions implemented, with the formulas from the existing docstrings
- Cyclic dependency graphs are refused, not silently smoothed over
- The verdict always comes with exactly three named drivers
- Weights are configurable, and the maths does not change when they are

**Depends on:** C-01, C-15.

**How to instruct me:** *"Build C-16. The formulas are already in the docstrings —
implement them with tests, including a cycle-refusal test."*

**What you learn:** **Hybrid symbolic and neural, and choosing the right granularity for a
model's judgement.** The model supplies four small ordinal judgements; Python does every
calculation. Note *why* the scale is 1–5 rather than 1–100: a model cannot reliably
distinguish 63 from 67, and pretending it can makes the downstream arithmetic look more
trustworthy than it actually is. Knowing where a model's judgement is reliable — and
truncating the scale to that — is a real and underrated skill.

---

## C-17 · Gate ledger ⬜ not started · ~200 lines

**In one line:** A permanent record of who approved what, at what risk, against which change.

**Why it exists:** An approval that lives only in a chat window did not happen. It cannot
be audited, and it is gone by next session.

**What it actually does:**
1. Scales the gate to the computed risk: low risk auto-approves and logs; high risk requires
   a named human plus an impact summary and a rollback plan.
2. Appends every decision to a file — never rewrites a past entry.
3. Each entry records: which package, the decision, who approved it, when, the risk score at
   that moment, a hash of the exact change, and links to the evidence.
4. The hash matters: it proves the approval was for *this* change and not a later one.

**Takes in:** a package, a decision, an approver, the risk score, and the change.
**Gives back:** an appended ledger entry, and a readable history.

**Done when:**
- Low risk auto-approves without a prompt; high risk cannot proceed without a named person
- The ledger is genuinely append-only — a past entry cannot be edited
- Every entry ties an approval to a specific risk score and a specific change hash
- The history is readable and answers "why does this exist?" by lookup

**Depends on:** C-16.

**How to instruct me:** *"Build C-17. Append-only, risk-scaled stringency, and every entry
must include the diff hash so an approval cannot be reused for a different change."*

**What you learn:** **Human-in-the-loop, designed rather than bolted on.** The
counter-intuitive part: a system that asks about everything is *less* safe than one that
asks about three things, because uniform gates cause fatigue and fatigue causes
rubber-stamping. Pricing the gate to the risk is what keeps the approvals meaningful.

---

# Group 7 · The execution loop

*Write, check, fix, and know when to stop.*

---

## C-18 · Generator ⬜ not started · ~300 lines

**In one line:** Writes code that looks like this project's code, not like generic code.

**Why it exists:** Output that is technically correct but stylistically foreign gets
rewritten by hand — which means the tool saved nothing. The fix is not a better model; it is
better examples.

**What it actually does:**
1. Retrieves the closest existing example of what is being asked for.
2. Reads that example as the pattern to match: its imports, its structure, its naming, how
   it handles errors, how it logs.
3. Applies the learned conventions from C-27.
4. Checks whether the thing already exists before writing anything new — reuse before
   creation.
5. Produces the change, stating which existing file it used as its reference.

**Takes in:** a work package, retrieved examples, and the conventions.
**Gives back:** the change, plus which reference file it followed.

**Done when:**
- Output follows the reference file's shape, not a generic template
- It always names the reference it used, so you can judge whether it picked well
- It refuses to duplicate something that already exists, and says what it found instead
- Given the same package twice, the output is recognisably consistent

**Depends on:** C-09, C-14, C-27.

**How to instruct me:** *"Build C-18. It must retrieve the closest existing example and
match it, and it must always tell me which file it used as the reference."*

**What you learn:** **Grounded generation.** Retrieve the nearest real example and match it,
instead of generating from the model's average of all code everywhere. This is few-shot
learning where the examples come from the repository itself. Worth internalising: **output
that looks generic in a specific codebase is a retrieval failure, not a model failure** —
the fix is upstream in C-09, not in the prompt.

---

## C-19 · Validator ⬜ not started · ~200 lines · **highest leverage single component**

**In one line:** Runs the real checks and reads the results properly.

**Why it exists:** Everything else in this system is reasoning about code. This is the only
part that finds out what is actually true. A test result is not an opinion.

**What it actually does:**
1. Asks the profile what "validated" means here — which commands, in what order.
2. Runs them for real.
3. Parses the output into structured results rather than handing back a wall of text: which
   test failed, in which file, on which line, with what message.
4. Distinguishes the kinds of failure — a syntax error, a failed assertion, a timeout, a
   missing dependency — because C-20 needs to know which it is.
5. Reports honestly. A skipped check is reported as skipped, never as a pass.

**Takes in:** a change, and the profile's validation commands.
**Gives back:** structured results — what passed, what failed, where, and why.

**Done when:**
- Validation commands come entirely from the profile, nothing hard-coded
- Failures are parsed into file, line and message, not returned as raw text
- Failure types are classified
- A skipped or errored check is never reported as a pass

**Depends on:** C-01, C-25.

**How to instruct me:** *"Build C-19. Commands from the profile, structured results with
file and line, and classify the failure type. Never report a skip as a pass."*

**What you learn:** **Closing the loop with ground truth.** This is the same insight behind
training models on verifiable rewards: a system that can check its own work against reality
improves dramatically faster than one that only reasons about it. If you build one thing
from this group, build this one — it makes everything upstream of it better, because the
upstream parts finally get told when they were wrong.

---

## C-20 · Repair engine ⬜ not started · ~300 lines

**In one line:** Fixes what failed — and knows when to stop trying.

**Why it exists:** Something will fail. The naive response is "try again", which in an
automated loop means burning money while quietly making the code worse.

**What it actually does:**
1. Classifies the failure using C-19's output.
2. Fetches context specific to *that kind* of failure — a missing import needs different
   context from a failed assertion.
3. Diagnoses, patches, re-validates.
4. Counts attempts. After three, it **stops**, reports what it tried, and says plainly why
   it is handing over.
5. Never silently reports success on an attempt that did not actually pass.

**Takes in:** a validation failure, and the change that caused it.
**Gives back:** a fix that passes, or an honest escalation after three tries.

**Done when:**
- Attempts are capped at three and the cap cannot be bypassed
- Each attempt targets the specific failure type, not a generic retry
- The escalation states what was tried and why it stopped
- A failure that gets worse across attempts is detected and abandoned early

**Depends on:** C-09, C-19.

**How to instruct me:** *"Build C-20. Three attempts maximum, failure-specific context per
attempt, and an escalation message that says exactly what was tried."*

**What you learn:** **Bounded self-correction.** Unbounded retry loops are the most common
way automated systems waste money and damage code — each attempt adds mess while confidence
stays high. **The engineering here is in the cap and the handover, not the retry.** Knowing
when to stop is a design decision, and it has to be made before the loop is written, not
after it misbehaves.

---

# Group 8 · Proof & learning

*What turns a tool that works today into one that gets better.*

---

## C-21 · Eval harness 🔴 blocked on you · ~300 lines

**In one line:** Proves whether a change made the output better or worse.

**Why it exists:** Without this, every prompt change is a guess. You will improve something,
break something else, and have no way to tell which happened. This is the single clearest
line between people who ship AI systems and people who demo them.

**What it actually does:**
1. Holds a golden set — real cases, each with the original request and what actually had to
   be reworked.
2. Runs the system against each case.
3. Scores the output against a written rubric per artifact type, rather than a vibe.
4. Compares against the last run and reports what improved, what regressed, and what stayed
   the same.
5. Never lets the model that produced an artifact be its only grader.

**Takes in:** the golden set, and the rubrics.
**Gives back:** a score per case, and a comparison against the previous run.

**Done when:**
- Five to ten real cases exist in the golden set
- Nine rubrics exist, one per artifact type
- A run produces a score you can compare to last time
- Each golden case marks which parts are observed fact and which were reconstructed

**Depends on:** C-13, **and the golden set** — which only you can supply. Agreed approach
(D-026): I reconstruct cases from the project's git history, you correct the reasoning I get
wrong.

**How to instruct me:** *"Start the C-21 golden set. Mine the history for request-to-rework
pairs, draft five cases, and mark clearly which parts you observed versus inferred."*

**What you learn:** **Evals and LLM-as-judge** — the most under-taught skill in this whole
field. Also the trap worth knowing: a model grading its own output scores it generously and
consistently, so it looks like a working eval while measuring nothing.

---

## C-22 · Experience store ⬜ not started · ~250 lines

**In one line:** Remembers lessons learned, and surfaces the relevant ones automatically.

**Why it exists:** The same mistakes recur. Without somewhere to put a lesson, it lives in
one person's head and leaves when they do.

**What it actually does:**
1. Records lessons, incidents and anti-patterns as structured entries, not free text.
2. Each carries what happened, what was learned, and what to do differently.
3. When a new task arrives, finds the few past lessons genuinely relevant to it.
4. Injects those into the context, so a known mistake is not made again.
5. Prunes or supersedes lessons that stop being true.

**Takes in:** a task, plus the accumulated lessons.
**Gives back:** the two or three lessons that actually apply here.

**Done when:**
- Lessons are structured and validated, not prose
- Retrieval surfaces relevant lessons and suppresses irrelevant ones
- A lesson visibly changes generated output
- A superseded lesson stops being retrieved

**Depends on:** C-09, C-10.

**How to instruct me:** *"Build C-22. Structured lessons, similarity retrieval, and prove
that injecting one changes the output."*

**What you learn:** **Long-term memory that compounds — and why retrieval is the hard
part.** Storing lessons is trivial. The real problem is that with two hundred lessons, which
three matter for *this* task? Get that wrong and you have built a landfill with a search box
attached, which is worse than nothing because people stop trusting it.

---

## C-23 · Traceability ⬜ not started · ~200 lines

**In one line:** Lets you follow any line of code back to the reason it exists.

**Why it exists:** "Why is this here?" is currently answered by archaeology — reading old
commits and guessing. It should be a lookup.

**What it actually does:**
1. Records a link every time an artifact is produced: this requirement produced this spec,
   which produced this plan, which produced this change, which was checked by this test.
2. Links work in both directions — from requirement forward to code, and from code back to
   requirement.
3. Populated as work happens, never reconstructed afterwards, because reconstruction is
   guesswork.
4. Joins up with the approval ledger, so a change traces to both its reason and its
   approval.

**Takes in:** each artifact as it is created.
**Gives back:** the chain, in either direction.

**Done when:**
- Any change can be traced back to the requirement that asked for it
- Any requirement can be traced forward to the code and tests that satisfy it
- Links are written at creation time, not inferred later
- A gap in the chain is visible rather than silently missing

**Depends on:** C-01, C-17.

**How to instruct me:** *"Build C-23. Links written at creation time, traversable both ways,
and gaps must be visible."*

**What you learn:** **Provenance and explainability.** In any audited environment, the
question "who decided this and why" eventually arrives, and the only good answer is a link
rather than a memory. Systems that cannot answer it get replaced by ones that can.

---

## C-24 · Cost ledger ⬜ not started · ~150 lines

**In one line:** Records what each run cost against what it was budgeted.

**Why it exists:** "This is efficient" is a claim. A number is a fact. And the router can
only get cheaper over time if it can see what things actually cost.

**What it actually does:**
1. Records, per step and per run: the budget, the actual spend, and whether the outcome was
   accepted.
2. Appends to a ledger, so history accumulates.
3. Reports budget versus actual, and flags steps that routinely overrun.
4. The router reads this history to make better depth decisions next time.

**Takes in:** each step's budget and actual usage, and whether the result was accepted.
**Gives back:** a running ledger and a report.

**Done when:**
- Every step records budget, actual and outcome
- Overruns are visible per step, not just in aggregate
- The router demonstrably uses the history
- Cost per *accepted* outcome is reported, not just cost

**Depends on:** C-05.

**How to instruct me:** *"Build C-24. Per-step budget versus actual, and report cost per
accepted outcome rather than raw token count."*

**What you learn:** **Observability, and choosing the right metric.** The wrong metric is
tokens used. The right one is **tokens per accepted outcome** — a run that spent half as much
and got rejected cost you more, not less. Optimising the wrong metric here is how systems
get cheaper and worse simultaneously while the dashboard looks great.

---

# Build order

Dependencies force most of this. What you actually choose is where to stop and start using
it — and there are two good stopping points long before the end.

| Milestone | Components | What you get |
|---|---|---|
| **M1** It runs at all | C-25 → C-05 | Skills can call Python, against a profile from day one. Nothing else is testable until this lands. |
| **M2** It knows the repo | C-06 → C-07 → C-08 → C-26 | **Blast radius.** Stop here and use it for two weeks. What you learn from using it will change what you build next. |
| **M3** It writes grounded specs | C-09, C-10, C-11, C-12, C-13, C-14, C-27 | A vague request becomes a validated spec, grounded in the real codebase, already attacked by a critic. Largest block of work. |
| **M4** It governs | C-15, C-16, C-17 | Work packages, a risk verdict with three named causes, gates priced to risk, a permanent approval trail. Second natural stopping point. |
| **M5** It proves itself | C-21 | Buildable any time after M3. Everything after it is unmeasurable without it. |
| **M6** It closes the loop | C-19 first, then C-18, C-20, C-22, C-23, C-24 | Generate, validate, repair, remember, trace, measure. C-19 first, because ground truth improves everything upstream. |

**If you only ever do two things: M1 then M2.** Four components. At the end you have a tool
that completely and instantly answers the most expensive question in your working week —
*what will this change break?*

---

# Questions still blocking work

| # | Question | Blocks |
|---|---|---|
| 1 | Which repositories enter the code graph — one, or several that share code? | C-06, C-07 |
| 2 | Risk band thresholds, and who counts as a named approver | C-17 |
| 3 | How does the headless path authenticate inside a CI pipeline? | CI rollout only |

Already settled: C-05 ships as bundled scripts (D-025) · golden set is reconstructed then
corrected (D-026) · no orchestration frameworks (D-024) · domain neutrality has components
(D-027) · explanations go in the chat (D-028).
