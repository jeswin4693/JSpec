# JSpec

AI-native **spec-driven development** for any IT team. A Claude Code plugin plus a
Python MCP server: you describe the work in plain language, JSpec picks the right
depth of process, splits big work into gated work packages, scores and rolls up risk,
and keeps an audit ledger.

**No Anthropic API key.** It runs on your Claude Code auth.

## What makes it different

Spec Kit and Polaris are template packs — markdown conventions where the intelligence
is whatever agent happens to read them, unmanaged and unmeasured. JSpec makes three
different choices:

| | |
|---|---|
| **Artifacts are typed data** | A validated object, not prose. Markdown is a rendering. Prose risk can't be summed; prose specs can't be graded. |
| **Determinism boundary** | Blast radius, dependency graphs, risk arithmetic, token counts → Python. Ambiguity and judgement → the model. Never pay a model to do arithmetic. |
| **Risk rolls up to one verdict** | Dominant+tail per package, propagated along the DAG, amplified for shared surfaces → `GO` / `GO-WITH-GATES` / `NO-GO` plus the three drivers. |

And one thing nobody ships: **gates priced by risk**. Low risk auto-approves and logs;
high risk demands a named human. Uniform gates cause gate fatigue, and gate fatigue
causes rubber-stamping.

## You never type a command

One model-invoked router skill classifies whatever you say and runs the right chain:

| Route | For | Questions |
|---|---|---|
| **T-0** | one file, reversible | 0 |
| **T-1** | a failure or defect | ≤1 |
| **T-2** | a feature or module | ≤3 |
| **T-3** | the same change in many places | ≤2 |

Slash commands still work if you want manual control. **The router's most valuable
decision is which steps to skip** — running a full spec pipeline on a one-line fix
costs more than it saves.

## Try it

```bash
claude --plugin-dir ./jspec        # load it
/jspec:recall                      # resume from memory
```

## Layout

| Path | Holds |
|---|---|
| `memory/` | cross-session memory — `STATE.md`, `DECISIONS.md`, `journal/` |
| `jspec/` | the plugin: skills, agents, hooks, `.mcp.json` |
| `core/` | Python: contracts, router, risk engine, MCP server |
| `templates/` | prompt registry — every template declares schema, budgets, rubric |
| `profiles/` | per-domain config; a new domain is a YAML file, not a code change |
| `evals/` | golden set + rubrics — the only proof quality is improving |

## Status

**Build step 1 of 11.** Contracts and the router are real; the MCP server and risk
engine are stubs with settled signatures. See `memory/STATE.md` for exactly where
things stand and what's next.

Read `CLAUDE.md` first — it defines the session memory protocol that lets a new chat
continue where the last one stopped.
