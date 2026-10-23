# DECISIONS — JSpec

Append-only. Newest at the bottom. Never edit or delete a past entry; supersede it
with a new one that references the old ID.

Format: `## D-NNN · YYYY-MM-DD · title` → **Decision / Why / Consequence**

---

## D-001 · 2026-08-22 · Build on GitHub Spec Kit's model, not on a Polaris copy

**Decision:** Take current open-source Spec Kit as the conceptual base and extend
it via extensions/presets rather than forking a frozen internal tool.

**Why:** Aptean's Polaris is verifiably a Spec Kit derivative — `.polaris/metadata.yaml`
carries migrations `0.15.0_kittify_to_polaris` and `0.12.1_remove_kitty_specs_from_gitignore`,
and its `spec-template.md` reproduces Spec Kit's P1/P2/P3 stories, `FR-xxx`, `SC-xxx`
and `[NEEDS CLARIFICATION]` verbatim. It forked and froze at v2026.2.9; upstream has
since shipped `clarify`, `converge`, `analyze`, `checklist` and role bundles that
Polaris lacks.

**Consequence:** Don't inherit Polaris's gaps. Upstream improvements stay available.

## D-002 · 2026-08-22 · Typed artifacts, not prose

**Decision:** Every artifact is a validated Pydantic object; markdown is a rendering.

**Why:** Polaris records risk as free-text under `### Risks & Mitigations`. Prose
cannot be summed, ranked, or graded — which is why Polaris could never roll risk up
to a feature verdict or measure whether a template change helped.

**Consequence:** Schema first. Everything downstream (roll-up, evals, dashboards)
becomes possible; nothing downstream is possible without it.

## D-003 · 2026-08-22 · Determinism boundary

**Decision:** Blast radius, dependency graphs, risk arithmetic, token counts, diff
hashes → Python. Ambiguity, quality and risk judgement → the model. Every model
output carries `confidence` + non-empty `evidence[]`.

**Why:** Deterministic work is cheaper, exact, reproducible — and more accurate than
asking a model. Cost then scales with judgement, not bookkeeping.

**Consequence:** `blast_radius` is a graph traversal, not an opinion. This is what
makes the risk numbers trustworthy enough to gate on.

## D-004 · 2026-08-22 · Risk roll-up: dominant + tail, DAG propagation, correlation

**Decision:** `wp_risk = max(items) + λ·Σ(rest)`; `exposure = own_risk × (1 + w·descendants)`;
work packages sharing entries in `touches` are treated as correlated, not independent.

**Why:** A plain sum dilutes one severe risk among ten trivial ones; a plain max makes
the ten trivial ones free. Foundation packages carry downstream exposure. Independent-risk
math systematically under-reports shared-surface exposure — decisive in App Central,
where shared page objects and support utilities span M2M / CRM / EAM / Pay.

**Consequence:** Output is one Combined Risk Register, one verdict
(`GO` / `GO-WITH-GATES` / `NO-GO`) and the top three drivers.

## D-005 · 2026-08-22 · Risk-priced gates + append-only gate ledger

**Decision:** Gate stringency scales with computed risk — low auto-approves and logs,
high requires a named human plus impact scan and rollback plan. Every gate appends
`{wp_id, decision, approver, timestamp, risk_at_approval, diff_hash, evidence_refs}`
to `gates.jsonl`.

**Why:** Uniform gates cause gate fatigue, and gate fatigue causes rubber-stamping.
And an approval that lives only in chat scrollback is not auditable and is gone next
session.

**Consequence:** Reviewers look at 3 things, not 40. Every change traces to a specific
approval against a specific risk score and a specific diff.

## D-006 · 2026-08-22 · No Anthropic API key — Claude Code is the gateway

**Decision:** The default path uses only Claude Code Enterprise auth. Structured
output comes from MCP tool schemas in-session and
`claude -p --output-format json --json-schema` headless. `--bare` is forbidden
(it bypasses subscription login and requires a key). A `judge` port allows
`claude-code` / `claude-headless` / `anthropic-api` / `other` backends.

**Why:** The owner has Claude Code Enterprise and no API key. An earlier design
assumed a direct-API "model gateway" — wrong for this constraint. This also
explains Polaris's architecture: Python CLI plus markdown commands *because* it
has no key. That was constraint-driven, not lazy.

**Consequence:** Zero credential dependency. Prompt-caching control and the Batch
API (50%) are unavailable on the default path — available to teams that do hold a key.

## D-007 · 2026-08-22 · Distribute as a Claude Code plugin; VS Code extension last

**Decision:** The product is a plugin (`.claude-plugin/plugin.json` + `skills/`,
`agents/`, `hooks/`, `.mcp.json`, `bin/`). Rollout path: `--plugin-dir` → private-repo
marketplace → enterprise managed settings force-enable → community marketplace.
Any VS Code extension is a thin view built last.

**Why:** The plugin gives global distribution with zero UI code, and Claude Code
already has a VS Code extension. Building UI against a moving core means rebuilding
it repeatedly.

**Consequence:** Extension may only render (kanban, risk dashboard, gate buttons,
diff preview) and delegate. Removing it must break nothing.

## D-008 · 2026-08-22 · One model-invoked router; every step skill locked

**Decision:** `skills/router/SKILL.md` is model-invoked with a broad description.
Every pipeline step skill sets `disable-model-invocation: true`.

**Why:** The user must not need to know which command to run. Model-invoked skills
engage from task context alone. Locking the step skills stops the model wandering
into the middle of the pipeline and skipping the spec.

**Consequence:** User types plain language; the chain runs itself. Slash commands
remain available for manual control.

## D-009 · 2026-08-22 · Route depth T-0…T-3, and the router's job is skipping

**Decision:** Four depths — T-0 trivial, T-1 fix, T-2 feature, T-3 sweep — chosen by
deterministic signals (ID patterns, stack traces, keywords, estimated files touched,
git state, this user's history). Model adjudicates only low-confidence cases.

**Why:** Forcing a one-line fix through a full spec pipeline costs more than it saves.
An autopilot that always runs everything is a token liability.

**Consequence:** Judge the router on tokens-per-accepted-outcome, never on how much
of the pipeline it exercised.

## D-010 · 2026-08-22 · Ask least, never twice

**Decision:** Question budget per route (T-0: 0, T-1: ≤1, T-2: ≤3, T-3: ≤2).
Resolution order for any unknown: preferences → repo → profile → assume-and-flag →
ask. Questions are batched, never drip-fed. Every answer persists to
`.jspec/preferences.yaml`.

**Why:** "Fully automatic" and "never guess" conflict unless bounded. Most unknowns
should become flagged assumptions reviewed cheaply at a gate — a question costs 90
seconds before planning and a day after implementation.

**Consequence:** Preferences are mostly *observed* from the repo, not configured.

## D-011 · 2026-08-22 · Domain-agnostic core; domains are YAML profiles

**Decision:** Nothing Playwright-, M2M- or Aptean-specific in `core/`. Each domain is
`profiles/<name>.yaml` declaring templates, risk taxonomy, runner, rubric, role bundles.

**Why:** Target audience is all IT professionals, not one QA team. A new domain must be
a data file, not a code change.

**Consequence:** The owner's M2M Playwright work becomes exactly one profile.

## D-012 · 2026-08-22 · MCP server is the cross-agent interop layer

**Decision:** The deterministic core ships as an MCP server; artifacts stay plain
markdown + JSON on disk.

**Why:** MCP is a cross-agent standard — Copilot, Cursor and others speak it. Only
`skills/` are Claude-Code-specific.

**Consequence:** Other-agent teams get the risk engine, gate ledger, decomposition
and templates, and supply their own judgement layer. No lock-in.

## D-013 · 2026-08-22 · Python, pinned to 3.12/3.13

**Decision:** Python for the core. Pin 3.12 or 3.13 via `uv`, not the system 3.14.3.

**Why:** Matches Spec Kit and Polaris (interop) and the code-analysis ecosystem.
Python 3.14 is new enough that `tree-sitter` bindings and `sqlite-vec` wheels lag,
which means building from source.

**Consequence:** System Python stays untouched; the project uses its own venv.

## D-014 · 2026-08-22 · Named JSpec; RCA-Agent deleted

**Decision:** Project name is **JSpec**. The `RCA-Agent` design folder was deleted at
the owner's instruction. Its RCA-category taxonomy remains a good future source of
learned `likelihood` priors for the risk model, if that work is ever revived.

**Consequence:** `AI_SDD` now holds exactly one project.

## D-015 · 2026-08-22 · Memory lives in the repo, in three tiers

**Decision:** `CLAUDE.md` (auto-loaded protocol, small and stable) → `memory/STATE.md`
(current state, overwritten) → `memory/journal/*.md` + `DECISIONS.md` (append-only
history, read on demand). A `SessionStart` hook surfaces state automatically.

**Why:** Each new chat starts blank. The folder has to carry continuity, and it must
not depend on anyone remembering to look.

**Consequence:** A session isn't finished until a new chat tomorrow could continue
from what's on disk.

## D-016 · 2026-08-23 · The Master Plan is the governing build specification

**Decision:** `docs/AI_SDD_MASTER_PLAN.md` (70 sections, supplied by the owner
2026-08-23) becomes the governing build specification for this repository, reconciled
with D-001…D-015 rather than replacing them. Where the two disagree, D-017…D-021
settle it. Where they agree — which is roughly 60% of the document — the existing
design already implements it.

**Why:** The document is a stronger articulation of the retrieval, context and
experience layers than JSpec had; JSpec is a stronger articulation of measurement and
governance than the document has. Neither is a superset. Adopting one wholesale would
have discarded real work.

**Consequence:** Phase order and vocabulary follow the master plan. Determinism,
typed artifacts, no-API-key, risk roll-up, gates and session memory follow JSpec.
The full document is load-on-demand; `docs/MASTER-PLAN-DIGEST.md` is auto-imported.

## D-017 · 2026-08-23 · Core stays Python — §5's TypeScript baseline is amended

**Decision:** The core remains Python 3.12/3.13. Master plan §5 (TypeScript / Node /
npm) is amended, not followed. D-013 stands.

**Why:** 1,054 lines of tested Python already exist with green CI on 3.12 and 3.13.
The strongest argument for TypeScript was that the primary target repo
(Made2Manage-Automation) is TypeScript — but `tree-sitter-language-pack` parses TS and
TSX perfectly well, so analysing TypeScript does not require writing the tool in
TypeScript. `ts-morph`'s genuine advantage is *type-aware* semantic analysis, which is
narrow enough to buy later as an optional sidecar rather than by rewriting the core.

**Consequence:** No rewrite. The CLI is `python -m jspec` / plugin `bin/`, not
`npm i -g sdd`. If type-aware analysis proves necessary at Phase 1, a ts-morph sidecar
is added behind a tool interface — that would be a new decision, not a reversal.

## D-018 · 2026-08-23 · AI Gateway: adapters required, key-based default forbidden

**Decision:** Master plan §32/§33/§62 are satisfied by the D-006 judge port. Provider
independence is required and already designed. What is amended is the *default*: the
default backend is `claude-code` (in-session) and `claude-headless` (CI). No default
path may require `ANTHROPIC_API_KEY` or any other provider key. `--bare` stays
forbidden. §33's cost-tier model routing is available only on key-based backends and
is disabled by default in `.sdd/config.yaml`.

**Why:** The owner has Claude Code Enterprise and confirmed on 2026-08-23 that no AI
API key is available — only Claude Code integration. §32 as written (ClaudeProvider /
OpenAIProvider / GeminiProvider) cannot run on this machine. But §62's actual
requirement is that provider specifics live behind adapters, which D-006 already does.

**Consequence:** The architecture the document asks for is preserved; only the default
changes. On `claude-code`, the lever for spending less is route depth (T-0…T-3) and
step skipping, not model downgrade. CI enforces the no-key rule.

## D-019 · 2026-08-23 · Map the §8 layout onto the existing tree; do not rename

**Decision:** Keep `memory/ jspec/ core/ templates/ profiles/ specs/ evals/`. Add
`.sdd/` for what §8 asks for that genuinely did not exist: `constitution.md`,
`config.yaml`, `state.json`, `index/`, `cache/`, `knowledge/`, `traces/`, `metrics/`,
`gates.jsonl`. Add `docs/`. `src/*` subsystem names map onto `core/src/jspec/` modules.

**Why:** Most of §8 already had a home under a different name. Renaming would break
`.mcp.json`, `hooks/hooks.json`, `pytest.ini`'s pythonpath and the CI paths, for zero
capability gained.

**Consequence:** Two state files with distinct jobs, documented so they are not
confused: `memory/STATE.md` is cross-session memory (D-015); `.sdd/state.json` is
cross-step task state (§55).

## D-020 · 2026-08-23 · An evaluation phase is inserted at 4.5

**Decision:** Insert an eval phase between master plan Phase 4 and Phase 5. Nothing
past it proceeds unproven.

**Why:** The master plan's 13 phases contain no phase that measures whether the
artifacts the system *produces* are improving. §68's Definition of Done — tests pass,
types pass, docs exist — proves the code runs, not that the specifications, plans and
patches are good. §21 asks to "track retrieval quality" and §47 asks to track
everything, but no phase builds the thing that scores quality. This is the one place
the document is judged wrong rather than merely different.

**Consequence:** Master plan §57's phase order is amended. The blocking input is the
golden set — real features with what got reworked and why — which only the owner can
supply.

## D-021 · 2026-08-23 · Six engines adopted from the master plan

**Decision:** Adopt, as genuine additions the JSpec design lacked: (1) **Context
Engineering** — `ContextBuilder`, `TokenBudgetManager`, `ContextCompressor`,
`ProgressiveContextExpander`, and §23's expansion ladder; (2) **Experience Engine** —
retrievable engineering knowledge (EXP-nnn lessons, incidents, anti-patterns) searched
by similarity to the task; (3) **Repair Engine** — classify → failure-specific context
→ diagnose → patch → validate, capped at 3 attempts then `HUMAN_REVIEW_REQUIRED`;
(4) **Traceability** — requirement → spec → plan → code → test → result;
(5) **Knowledge Capture** — results and feedback becoming candidate lessons;
(6) **Security / redaction** — secret detection before any context leaves the machine.

**Why:** Each is absent from D-001…D-015 and each is load-bearing. §3's "minimum
*sufficient* context, not minimum context" is a sharper formulation than JSpec's token
discipline. The Experience Engine is the RCA-Agent taxonomy returning with a proper
spec, exactly as D-014 anticipated. Knowledge Capture is the only loop that makes the
system compound. Security/redaction directly answers the open question about sending
context from an `Internal`-classified repo off-machine.

**Consequence:** These become Phases 4, 5, 10, 11, 12 and a cross-cutting security
policy. `.sdd/config.yaml` already encodes the ladder, the repair limit, the context
preferences and the never-send list.

## D-022 · 2026-08-23 · Act, don't poll — the per-file approval gate is retired

**Decision:** Stop asking Yes/No before each file write. Owner's standing instruction,
2026-08-23: *"Always don't ask Yes or No questions. Just do, and if any clarification
is needed really, ask me."* Confirmation is still required for destructive or
irreversible operations, anything leaving the machine, and high-risk shared changes
(constitution rule 9). Questions are for genuine ambiguity that would make the output
wrong — not for permission.

**Why:** The gate was inherited from the M2M Playwright ruleset, where a wrong edit
breaks a live automation suite. Here it was costing a round trip per step on a
greenfield repo with git as the safety net, and the owner said so explicitly.

**Consequence:** Supersedes the approval-gate bullet in `CLAUDE.md` §1. Git history is
now the rollback mechanism, which makes committing at phase boundaries load-bearing
rather than optional.

## D-023 · 2026-08-26 · Teach as you build; many small components, not few big phases

**Decision:** Every meaningful unit of work ships in two halves — build it, then teach
it. The teaching half names the AI-engineering concept the component embodies, why it
is done this way here, and what the common wrong way looks like. Additionally, work is
decomposed into many small named components (~24, grouped in 8 layers) with stated
dependencies, replacing the 13 large phases as the unit of planning. The phase order
(D-016, CLAUDE.md §5) still governs *sequence*; components are the *chunks*.

**Why:** The owner is using this build as his route into AI engineering — "I am
learning each and every thing that what we are developing" (2026-08-26). He intends to
plan the chunks and instruct the work himself, not delegate it. That only functions if
he can reason about each mechanism, so a delivery without an explanation is an
incomplete delivery. Large phases are also unplannable by hand: "phase 3, retrieval" is
not something you can schedule, whereas "C-09 retriever, depends on C-07, ~250 lines"
is.

**Consequence:** `CLAUDE.md` gains §1b, which is auto-loaded every session, so this
survives new chats and context compaction. Component atlas published as an artifact and
referenced from `STATE.md`. Output format is now build + concept + why-not-the-other-way,
scaled to task size.

## D-024 · 2026-08-26 · No orchestration framework; RAG built by hand; MCP kept

**Decision:** No LangChain / LangGraph / LlamaIndex dependency. Retrieval (C-09) and
context assembly (C-10) are written directly against the symbol index. MCP stays, as a
thin protocol for the tool surface (C-05). Vector search is the *last* rung of the
retrieval ladder, added only after exact/symbol/lexical/structural are proven
insufficient — never the first thing built. Ollama and all local/third-party model
backends are dropped from scope (supersedes the exploratory framing of D-018's `other`
backend, which stays in config as an unused slot).

**Why:** Three reasons, in order of weight. (1) A framework does the interesting part
for you, and the interesting part is the thing the owner is here to learn (D-023).
(2) LangChain's default paths assume a provider API key, which is the one constraint
this project cannot bend (D-006, D-018). (3) The naive RAG recipe — chunk everything,
embed, cosine similarity — is actively wrong for code, which has real structure: a
function is a natural unit and an import is a real edge. `.sdd/config.yaml`'s
`retrieval.order` already encodes the better approach.

**Consequence:** More code written by hand, and it is understood. MCP earns its keep by
being a protocol rather than a framework. If a vector store is ever added it enters at
the bottom of the existing ladder, behind the same interface, as a new decision.

## D-025 · 2026-08-26 · C-05 ships as bundled scripts first; MCP wraps the proven tools later

**Decision:** The tool surface (C-05) is built as **Python scripts bundled inside the
skill folders**, invoked via Bash — not as an MCP server. The MCP server is deferred
until after M2, at which point the tools that proved useful get wrapped in it for
forced schema validation and cross-agent reuse. Owner's call, 2026-08-26.

**Why:** Of the three jobs the deterministic core exists for, only one — *forcing* a
response shape rather than requesting it — actually requires MCP. The symbol index and
the risk arithmetic run identically from a script. Bundled scripts unblock M1 in days
instead of weeks, install as one artifact, work in any folder immediately, and leave
every mechanism visible, which D-023 requires. Wrapping later costs some rework; being
blocked costs everything.

**Consequence:** Amends D-012's framing of MCP as *the* interop layer — MCP is now a
later optimisation, not the entry point. `jspec/.mcp.json` stays on disk but is inert
until the wrap happens; do not treat its presence as a working server. Schema
validation in the interim is a script-side Pydantic check, which *rejects* but cannot
force a retry — a known and accepted gap until MCP lands.

## D-026 · 2026-08-26 · Golden set is reconstructed from git history, then owner-corrected

**Decision:** The C-21 golden set is produced by mining `../GitHub/Made2Manage-Automation`
(5,099 commits) for request→rework pairs, reconstructing 5–10 cases, and having the
owner correct what was inferred wrongly. Owner's call, 2026-08-26.

**Why:** Least owner effort for a blocking input, and git history holds the ground truth
about what actually got reworked. The reconstruction will get the *what* right and the
*why* wrong — the why is what the correction pass is for, and the why is the part that
makes a case useful as an eval.

**Consequence:** Every golden case must record which parts are observed from history and
which are owner-supplied, because an eval built on an invented rationale measures nothing.
Reads the M2M repo only — no writes, and `.claude/api.md` is never touched (§46, C-11).

## D-027 · 2026-08-26 · Domain-neutrality gets components, not just a principle

**Decision:** D-011's domain-agnostic principle is now backed by three real components,
because a declared principle with no implementation is how a general tool quietly
becomes a single-team tool:

- **C-25 Profile engine** — the `Profile` contract, loader, merge/override resolution,
  and validation. Everything domain-specific is read from here. Moves into **M1**,
  alongside C-05, so the first tools are written against a profile from day one rather
  than retrofitted.
- **C-26 Project profiler** — scan an unknown repository, detect stack / layout /
  runner / test framework, emit a *draft* profile the user corrects. Needs C-06, C-07.
- **C-27 Convention learner** — infer the team's house style (naming, structure,
  recurring patterns) from their own code and populate preferences. Needs C-07, C-09.
  This is what D-010's "preferences are mostly *observed* from the repo, not
  configured" was always describing; it had no home until now.

IDs continue from 24 deliberately — existing component IDs are stable and never
renumbered, because they are referenced from STATE.md, the journal and the artifacts.

**Why:** Owner correction, 2026-08-26: *"This is common project which we are
developing, not for specific M2M or anyother things. If we implement means, based on
user requirements, it have to work as per their works."* Correct, and the repo agreed
with him already — but `profiles/` was empty, no code read or wrote a profile, and the
24-component atlas had no component for adaptation at all. The M2M-heavy examples in
this session's two artifacts made the *product* look domain-specific when only the
*illustration* was. Both were corrected.

**Consequence:** The profile is the generalization boundary. Any Playwright-, M2M-,
Aptean- or language-specific fact appearing in `core/` is a defect, catchable in review
and eventually in CI. Profiles are **generated then corrected**, never hand-authored as
a precondition of install — the same machine-drafts/human-corrects pattern as D-026.
`profiles/playwright-e2e.yaml` becomes one example among several (python-service,
react-app), never the reference implementation. The M2M repo stays useful as *test
data* for evals (D-026) — that is not a domain dependency in the core.

## D-028 · 2026-08-26 · Deliver in the chat, not in artifacts

**Decision:** All explanation, architecture, plans and teaching go **in the Claude Code
chat**. No HTML artifacts unless the owner explicitly asks for one.

**Why:** Owner instruction, 2026-08-26: *"I dont need anything in HTML, instead Can I
able to get them all the things only in Claude Code chat, so that I can learn on that
too and ask doubts between them."* The point of D-023's teaching mode is that he can
interrupt and ask questions mid-explanation. A published page is a monologue — he has
to read it elsewhere and come back, which breaks exactly the back-and-forth that makes
the teaching work.

**Consequence:** Long answers are structured with clear headed sections so he can point
at one and ask about it. Durable reference material goes to `memory/` and
`DECISIONS.md` on disk — which is where it belonged anyway, and it is version-controlled
and greppable, unlike a page. Two artifacts already published (JSpec Blueprint, JSpec
Component Atlas) are left in place but are no longer the medium; do not update them
unless asked.

## D-029 · 2026-08-26 · The session journal is local memory, not a committed artifact

**Decision:** `memory/journal/` is git-excluded. It keeps being written every session
(CLAUDE.md §0b, unchanged) and keeps being read at session start — it is simply not
version-controlled. `memory/journal/2026-08-22.md`, tracked since the initial commit, is
untracked with `git rm --cached` so the file survives on disk. Everything else commits.

**Why:** Owner instruction, 2026-08-26: *"Commit all the things, but not the chat history
things forever, Just remember, but not need in repo."* The journal is working memory that
serves one purpose — letting a new chat resume — and it grows by a page per session
forever. Committing it means the repository's history becomes mostly transcript, and a
reader looking for the project cannot find it. Anything from a session that must outlive
the machine already has a committed home: `DECISIONS.md` for decisions, `AGENDA.md` for
build state, `docs/` for reference.

**Consequence:** **Git is no longer the journal's backup.** This folder syncs to OneDrive,
which is. That is an accepted trade, not an oversight — the journal is reconstructible
from the commits and the decisions if it is ever lost, as the 2026-08-23 backfill proved.
`.gitignore` carries the reasoning inline so nobody "helpfully" re-adds it, and CLAUDE.md
§0b says never to force-add it.

## D-030 · 2026-08-29 · C-25 ships thin; the profile engine is a seam, not a config language

**Decision:** The `Profile` contract carries only fields something reads: `name`,
`description`, `languages`, `source_dirs`, `test_dirs`, `validation`. Deferred, each
until a live consumer exists — `extends`/override resolution (no profile inherits from
another yet), `risk_signals` (C-16 is a stub and should state its own shape),
`templates` (C-12 has 1 of 9), `shared_dirs` (C-16's correlation amplifier does not
exist). `resolve(project_dir)` auto-detection is not here either: that is C-26's job,
and two detectors disagreeing is worse than one arriving later.
`docs/COMPONENT-GUIDE.md` sizes C-25 at ~250 lines including override resolution; the
shipped contract + loader is 258 lines with the deferrals removed and the failure modes
added instead.

**Why:** The owner asked the right question — *"why is there a need of profiles here?"*
The answer that survives scrutiny is not "other teams someday". It is that two real
projects already exist on this machine (this repo, Python/pytest; the Playwright suite,
TypeScript/playwright), `.sdd/config.yaml` can hold only one set of commands, and its own
comment already said those belonged in a profile. That justifies the *seam*. It does not
justify an inheritance system with one user. Premature generalization and premature
specialization fail asymmetrically: hardcoding is cheap to write and expensive to undo,
a config layer is expensive to write and cheap to ignore — so create the seam, leave it
thin, and add a field only when something reads it.

**Consequence:** `.sdd/config.yaml` no longer carries `validation.python` — those
commands moved to `profiles/jspec-self.yaml` (constitution rule 2: the duplicate is what
drifts). The config file gained a `profiles:` section with **no `default:` key**, on
purpose: a global default profile is how the wrong linter silently runs against the wrong
repository. Two CI gates now enforce rule 20 — every shipped profile must validate and
declare `validation.test`, and `core/scripts/check_domain_neutrality.py` fails the build
if any module outside `profiles.py` / `contracts/profile.py` names a language, framework
or test runner in executable code (docstrings are stripped first, so explaining a rule is
not breaking it). Adding a field to `Profile` later is cheap; removing one that shipped
profiles already set is not.

## D-031 · 2026-08-29 · The tool surface is one `jspec` command, not per-skill scripts

**Decision:** C-05 ships as a single command with subcommands — `jspec.cli` behind the
`jspec = "jspec.cli:main"` entry point that `core/pyproject.toml` has declared since the
first commit — plus `core/scripts/jspec.py`, a dependency-free launcher for checkouts
where the package is not installed. Only the three tools backed by built components are
registered as commands (`classify`, `plan-chain`, `validate`, plus `tools`); the other
seven stay visible through `jspec tools` with the component each waits on. Owner's call,
2026-08-29, on a flagged reading of D-025.

**Why:** D-025 says "Python scripts bundled inside the skill folders, invoked via Bash".
Read literally that puts shared logic in three skill folders at once, which constitution
rule 2 forbids — and D-025's stated reasons (invoked via Bash, not MCP, unblocks M1 in
days, every mechanism visible) are all satisfied by one command. This amends D-025's
*location*, not its substance: still scripts, still Bash, still no MCP until after M2.
The launcher exists because pip is broken inside this repo's venv, so "just install it"
is not available and a skill must work in a bare checkout.

**Consequence:** `jspec.mcp_server` keeps its ten signatures but holds no logic — it
delegates to `jspec.tools`, the single registry of what exists, so the two surfaces
cannot drift. `main()` still refuses to start, now citing D-025 rather than a stale
build-step number. The router skill was rewired from "call `classify_task` (MCP)" — an
instruction nothing could execute — to the real commands, and it now states plainly
which steps are unavailable rather than implying the whole pipeline works.

## D-032 · 2026-08-29 · The code graph spans one root folder and every sub-folder in it

**Decision:** The symbol index (C-06/C-07) is built over **one root directory, indexed
recursively across all of its sub-folders**, and calls that cross sub-folder boundaries
are followed like any other. Every indexed symbol carries which sub-folder it belongs
to, from the first version — not added later. Owner's answer, 2026-08-29, to the last
open question blocking M2.

**Why:** The failure this prevents is the dangerous kind. Change something in a shared
sub-folder, ask what breaks, and an index scoped to one sub-folder answers "3 places"
with total confidence when the true answer is twenty — including callers in sibling
folders it never read. It does not say "I am unsure"; it returns a clean, incomplete
list, and a clean list is one you stop double-checking.

**Consequence:** The index schema carries a module/sub-folder column from the first
migration. Retrofitting it means rebuilding the index and rewriting every query, whereas
including it now costs one column that stays uniform if a project only ever has one
module. Blast radius (C-08) must report which sub-folder each caller lives in, since
"this breaks something in another module" is a different conversation from "this breaks
two files next to the one you are editing". Note this is a **single root**, not several
separately-cloned repositories: cross-repository indexing is not in scope and should be
raised as a new question if it ever is.

## D-033 · 2026-09-06 · Language reading rules are data shipped beside the extractor

C-06 needs a table of grammar node types per language. Three places could hold it, and
two of them are wrong:

- **`.sdd/config.yaml`** already had `index.languages: [python, typescript, ...]`. It is
  **removed.** Which languages a project uses is a per-project fact, and constitution
  rule 20 (D-011) assigns per-project facts to `profiles/*.yaml`, where every profile
  already declares `languages:`. Two authorities for one fact is rule 2, and the copy
  nobody edits is the one that goes stale. Nothing read the config key — verified before
  removing it.
- **`profiles/*.yaml`** is wrong for the node-type table itself. A profile holds facts
  about one *project*; node types are facts about a *language*, identical for every
  project ever written in it. Putting them there copies the same table into every
  profile.
- **`core/src/jspec/graph/languages.yaml`** — where it went. Shipped data, one copy,
  loaded by the extractor.

The split, stated once: **the profile says WHICH languages a project uses; this file says
HOW to read one.**

It is YAML rather than a Python dict for a specific reason. `check_domain_neutrality.py`
screens *tool* names, so a node-type table in a `.py` module would have passed the gate
while being exactly the erosion the gate exists to stop ("one `if language == ...` at a
time"). Keeping it as data makes the rule literally true: no module in `core/src` names a
language, and `tests/test_graph.py::test_no_module_in_core_names_a_language` enforces it
independently of the CI script.

**Consequence:** supporting a new language is a YAML block, with no new logic. The
acceptance criterion "adding a language requires a profile change, not a code change" is
read honestly: adding a language *to a project* is a profile edit; teaching JSpec a
language it has never seen is a data edit. Neither is a code change.

## D-034 · 2026-09-06 · A reference records how firmly the syntax pinned its target down

`user.save()` cannot be resolved to a definite `save` without type inference. The two
tempting options are both dishonest: drop the edge, which understates blast radius, or
link it to every `save` in the repository, which drowns the answer.

Instead every `Reference` carries `resolution`:

- `exact` — a single bare identifier: `foo()`, `import a.b`
- `name_only` — a member on an unknown receiver: `user.save()`. The final name is known,
  the owner is not.
- `unresolved` — nothing usable was named: `handlers[i]()`. Kept, not dropped, so the
  edge count stays honest; the recorded name is the syntactic form.

This is a statement about **syntax**, not about the repository: C-06 sees one file at a
time. C-07 and C-08 combine it with their own lookup, and C-08 can then report "7 callers
certain, 3 possible" instead of one undifferentiated list.

It is the same rule C-08 already commits to with its depth limit, generalised: **a partial
answer must never be shaped like a complete one.** Owner chose the defaults; this records
which default was taken and why the other two were refused.

## D-035 · 2026-09-06 · The router recognises a filename by shape, not by a language list

`router.py`'s `FILE_PATH` regex enumerated ten extensions
(`py|ts|tsx|js|cs|java|go|rb|sql|ya?ml`). That is domain knowledge in `core/`, which
constitution rule 20 (D-011) forbids, and which `check_domain_neutrality.py` misses
because it screens *tool* names and these are extensions. Found by C-06's neutrality
test, deferred at the time as C-02's call, then fixed on the owner's instruction to fix
anything showing issues.

Replaced with a **shape**: a stem, optional path segments, then a 2-6 character
extension beginning with a letter.

The rejected alternative was to read extensions from `graph/languages.yaml`. That would
have *narrowed* the regex to the four shipped languages, so a prompt naming `Store.java`
would have stopped registering — a regression dressed as a cleanup.

Verified against a battery before adopting: **zero regressions** on everything the old
list matched (including Windows backslash paths), six new languages recognised
(`.rs .md .json .tf .sh .kt`), and prose correctly rejected — `e.g.`, `i.e.`, `U.S.A.`,
`3.13`, `v1.2.3` all fail, because a one-character suffix or one starting with a digit
is not an extension.

**Known and accepted:** `obj.save` now matches. The bump it earns is toward T-0, which
is the right direction for a prompt naming one small thing, and any fix or feature
vocabulary in the same prompt outweighs it. Pinned in `tests/test_router.py` so the
trade-off is measurable rather than hidden.

## D-036 · 2026-09-06 · Every entry point forces UTF-8 on its own streams

The SessionStart hook was **silently failing on Windows**. Claude Code captures its
stdout through a pipe; Python then encodes with the locale codepage (cp1252 here); the
memory files are full of arrows and bullets; the first one raised `UnicodeEncodeError`;
the top-level handler swallowed it and printed "could not run". **Every session on this
machine had been starting with no memory loaded** — the exact failure C-03 exists to
prevent, invisible because nothing tested the hook.

Both entry points now call a local `_use_utf8()` that reconfigures stdout and stderr.
`jspec.cli` needed it too: its stdout was already safe (`json.dump` escapes non-ASCII by
default) but stderr was not, and `café/app.py` came back as `caf?/app.py`, breaking the
rule every error message here is written to — name the file and the fix.

The helper is **duplicated on purpose**. `hooks.json` runs the hook with bare `python`,
so it cannot import the package; making it able to would break the requirement that it
works in a checkout with nothing installed. Four lines of stdlib boilerplate with no
logic to drift is the cheaper of the two evils, and both copies say so.

**The real lesson is the test gap, not the encoding.** `tests/test_memory_hook.py` now
runs the hook as a subprocess under cp1252, ascii and utf-8. Verified in both
directions: reverting the fix fails four tests.

## D-037 · 2026-09-16 · The symbol index lives in JSpec's `.sdd/index`, one database per root

`.sdd/config.yaml` already said `index.root: .sdd/index`, but not *whose* `.sdd`. The
first tree JSpec indexed that was not itself — the Made2Manage suite — made the question
real, because that repository has no `.sdd/` at all.

**Settled: JSpec's own `.sdd/index/`, one SQLite file per indexed root, named
`<folder>-<8 hex of the absolute path>.db`.** Never inside the tree being read.

- Indexing a repository must not add an untracked 67 MB binary to someone's working
  tree. `jspec extract` was read-only with respect to its target and `jspec index`
  stays that way. Master plan §4.12–14 forbids modifying unrelated files; a cache
  written into another team's checkout is exactly that.
- The digest keeps two checkouts of the same repository apart; the folder name keeps the
  directory listing readable. Deterministic, so the same root always reopens the same
  index rather than silently starting a second one.
- Relative `index.root` resolves against the directory holding `.sdd/`, never the
  current working directory — a cache that moves when you `cd` is a cache that gets
  rebuilt for no reason.

Enforced by a CI gate that asserts the positive (the store is under `.sdd/index`) and
then that no `*.db` exists anywhere else in the tree. The obvious check — "git sees no
new file" — is worthless here: `.sdd/index/` is gitignored, so a database dropped
anywhere ignored is invisible to git by construction.

`.gitignore` gained `.sdd/index/`, `.sdd/cache/`, `.sdd/traces/`, `.sdd/metrics/` and
`.sdd/gates.jsonl`. The pre-existing entries pointed at `.jspec/`, the name D-019
replaced, so nothing had been ignored since; the old lines stay because
`record_preference` still has no agreed home and `skills/router/SKILL.md` names `.jspec/`.

## D-038 · 2026-09-16 · The store holds edges, not traversal; full text covers names, not bodies

Two scope questions, answered once so C-08 and C-09 inherit them.

**References are stored, with `module` and `resolution`, from the first migration.**
They are 96% of the rows (199,615 of 208,526 on the M2M suite) and nothing queries them
yet — C-08 does. Storing them later would mean re-reading every file in every repository
the tool has ever seen, which is the same argument D-032 made for `module`. Measured
cost of keeping them: 67.5 MB, about 3.2× the size of the source indexed, in a file that
is disposable by design.

**Traversal is not in the store.** One hop is a query; the transitive closure, the cycle
guard and the reported depth limit are C-08's. So `blast_radius`'s registry entry moved
from "blocked by C-07" to "blocked by C-08" rather than becoming ready — a one-hop answer
presented as a blast radius would be precisely the partial-answer-shaped-like-a-complete-
one that D-034 refuses.

**Full-text search covers `name`, `qualified_name` and `file` — not source bodies.**
Searching source text is C-09's lexical rung, where ripgrep already does it better, and
indexing bodies would multiply the database for a capability that arrives later anyway.
Every word becomes a prefix term, so `ensureAva` finds `ensureAvaTaxEnabled`.

Deferred with its reason recorded: a **stat-based pre-filter** (size + mtime as a cheap
"might have changed" hint before hashing, the other half of git's trick). Measured need —
a no-change re-index of 1,885 files costs 1.9–2.4 s, against the ~1 s the component guide
asked for, and the floor is the walk plus a full read of every file. It is an
optimisation with a correctness trap in it, so it waits until the cost is felt.

## D-039 · 2026-10-23 · C-08 walks two graphs, and calls an edge certain only on evidence

C-08 is `core/src/jspec/graph/traverse.py`. Seven choices, recorded so C-09 and C-16
inherit them rather than re-derive them.

**Two graphs, never merged.** A *name* is answered over the call graph (nodes are
definitions); a *file* over the import graph (nodes are files). Merging them would make
every importer of a module a caller of every function in it. Each walks both ways:
`dependents` (who is affected) and `dependencies` (what it relies on).

**Breadth-first over `(node, tainted)` states.** BFS because the first arrival at a node
is the shortest chain, rings of distance mean something, and a depth limit on DFS is
meaningless. `tainted` = "a possible edge is on the path so far", so one pass yields both
sets: reached untainted is **certain**, reached only tainted is **possible**. A node
reached both ways is certain and is shown with its *certain* chain and depth. A chain is
as strong as its weakest link.

**An edge is certain only on evidence, and every simplification errs toward possible.**
Call: a bare name found in its own file, else in a file this file imports, exactly once.
A member call is never certain. A bare name with neither is *possible even when the repo
defines it once* — it may be a library function of the same name (a first draft called
that certain; caught in review, and now pinned by a test). Import: a relative path that
resolves to exactly one file, or a dotted/path name of two or more segments matching
exactly one file's tail; one bare word is never certain (`os` would "certainly" mean any
local `os.py`). Forward and reverse share one resolver, `_Graph.targets`, and a property
test proves they agree.

**Depth is reported, and the ring after the limit is peeked at.** `complete: false,
stopped_by: "depth"` means something was actually cut; a search that ends exactly at the
limit is not called truncated. `MAX_STATES = 20,000` is a second ceiling, reported as
`stopped_by: "size"`. Default depth 4. Counts are always complete; `--limit` caps only the
rows printed, and `omitted` says how many.

**Ambiguity is searched, not refused.** A name defined several times searches every
definition, lists them under `targets`, sets `ambiguous`, and each edge's certainty
already accounts for it; `--file` narrows. A class target also seeds its methods —
changing a class changes what they do.

**Language facts stay in data.** Which file stands for an imported directory
(`__init__`, `index`) is `entry_stems` in `languages.yaml` (D-033), so `core/` still names
no language. `SymbolStore.references()` was added with no row limit by design: a walk that
stops reading edges at row 50 returns a blast radius with callers missing and nothing to
say so.

**Every answer carries what it cannot see.** `limits` (calls and imports only — a
function passed as a value, a decorator, an inheritance link or a type reference leaves no
edge; a computed call has no name) and `index` (unresolved calls, parse failures) travel
with the result so absence reads as "not seen", not "not there".

**Measured, Made2Manage (2,932 files, 11,458 symbols, 263,837 refs).**
`ensureAvaTaxEnabled`: 0.56 s end to end, 2 possible dependents, **exactly the two real
call sites** (`…695270…spec.ts:301`, `…695265…spec.ts:226`) — the other eight text-search
hits were comments and docs. `button` (177 definitions): 35 s, then 1.26 s after computing
the member-call callers once per name instead of once per definition — counts identical.
`click`: 0 certain, 8,143 possible, 2,599 files (every `page.click()` could be the repo's
`click`). That last one is not a bug; it is `name_only` honestly reported, and the reason
the split exists.

**Deviation from the guide.** ~810 lines, not ~200. The file graph, import resolution
and the certainty model were not in the guide's estimate; the model is the part that makes
the answer trustworthy on a graph that is 72% `name_only`, and I judged it not optional.
Deferred: narrowing a call by *which names* a file imports (only whether it imports the
defining file at all) — it would turn some possibles into certains, never the reverse.
