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
