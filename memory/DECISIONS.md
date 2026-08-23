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
