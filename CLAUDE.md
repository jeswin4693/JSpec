# CLAUDE.md — JSpec

**Project:** JSpec — AI-native Spec-Driven Development for any IT team.
**Owner:** Jeswin J (Aptean)
**This file is auto-loaded at the start of every session in this folder.**

---

## 0. SESSION START PROTOCOL — do this before anything else

Every new chat starts with no memory of previous chats. This folder carries that
memory instead. **Before responding to the first request of a session:**

1. Read `memory/STATE.md` — current state, what's done, what's next, open questions.
2. Read the newest 1–2 files in `memory/journal/` — what happened most recently.
3. Skim `memory/DECISIONS.md` — decisions already made. **Never re-litigate a
   decision recorded there.** If you think one is wrong, say so once, cite the
   entry, and ask.

Then state in one line where the project stands, and continue the work.

## 0b. SESSION END PROTOCOL — do this before the session goes quiet

Whenever you finish a meaningful unit of work (not every message):

1. Append to today's journal: `memory/journal/YYYY-MM-DD.md` (create if absent).
2. Update `memory/STATE.md` — it must always describe *now*, not history.
3. Append any new decision to `memory/DECISIONS.md` (append-only, never edit past
   entries).
4. If a fact will matter in months, not days, also write it to persistent memory
   at `C:\Users\jj1\.claude\projects\c--Users-jj1-OneDrive---Aptean-online-Documents-AI-SDD\memory\`
   and index it in that folder's `MEMORY.md`.

**Rule of thumb:** if a new chat tomorrow couldn't continue from what's on disk,
the session isn't finished.

---

## 1. Scope note

`Documents/CLAUDE.md` (the M2M Playwright rules: F-01…F-22, page-objects/m2m,
AG-Grid, ExtJS) governs the **Made2Manage-Automation repo**. It does not describe
this project — JSpec is Python + a Claude Code plugin, not Playwright specs.

What carries over here, because it is good practice and the owner relies on it:

- **Approval gate.** Ask Yes/No before creating, editing, or deleting files.
  Silence is not approval. A prior session's Yes never carries forward.
- **Files are truth.** Never answer from memory about this codebase. Read it.
- **No blind changes.** Scan for callers/importers before changing a shared thing.
- **Reuse before adding.** Search before writing a new helper. Duplicated logic
  is rejected.
- **Scale output to task size.** Dense, no filler.

## 2. What JSpec is

A Claude Code **plugin** plus a Python **MCP server**. Claude Code supplies the
judgement; the MCP server supplies everything deterministic. **No Anthropic API
key is required or used** — it runs on the user's Claude Code auth.

```
Judgement    jspec/skills/ + jspec/agents/     → Claude Code
Determinism  core/ (MCP server, graph, risk)   → plain Python, no model calls
Contracts    core/src/jspec/contracts/         → Pydantic → JSON Schema
Memory       memory/                           → this folder
```

## 3. Non-negotiables

1. **Artifacts are typed data.** Markdown is a rendering of a validated object,
   never the source of truth. Schema first, prose second.
2. **Determinism boundary.** Blast radius, dependency graphs, risk arithmetic,
   token counting, diff hashes → Python. Ambiguity, quality, and risk *judgement*
   → the model. Never pay a model to do arithmetic.
3. **No API key.** Anything requiring `ANTHROPIC_API_KEY` on the default path is
   a design error. Structured output comes from MCP tool schemas in-session, and
   `claude -p --output-format json --json-schema` headless.
   `--bare` is forbidden — it bypasses subscription auth and demands a key.
4. **Evidence or silence.** Every model judgement carries `confidence` and
   non-empty `evidence[]`. Below threshold → escalate, never guess.
5. **Domain-agnostic core.** Nothing Playwright-, M2M-, or Aptean-specific in
   `core/`. Domain knowledge lives in `profiles/*.yaml`.
6. **Token discipline is a feature.** Every template declares a token budget;
   every run logs actual cost. The router's most valuable decision is which
   steps to *skip*.
7. **Ask least, never twice.** Resolution order for any unknown: preferences →
   repo → profile → assume-and-flag → ask. Persist every answer.

## 4. Where things live

| Path | Holds |
|---|---|
| `memory/` | session memory — read at start, written at end |
| `jspec/` | the Claude Code plugin (skills, agents, hooks, `.mcp.json`) |
| `core/` | Python: contracts, MCP server, router, risk engine |
| `templates/` | prompt template registry — one per command, with budgets |
| `profiles/` | per-domain config (playwright-e2e, python-service, …) |
| `specs/` | generated artifacts |
| `evals/` | golden set + rubrics — the only proof quality is improving |

## 5. Build order (never skip step 4)

1. contracts → 2. MCP server → 3. one skill end-to-end → **4. evals** →
5. critics → 6. retrieval → 7. plan/decompose → 8. risk + gates →
9. implement/review → 10. profiles → 11. VS Code extension (last).

Building agents 5–11 before the eval harness exists is how a spec framework
becomes markdown nobody can prove works. Current position: see `memory/STATE.md`.
