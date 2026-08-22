---
description: Load JSpec project memory - current state, recent journal, and past
  decisions - so a new chat continues where the last one stopped. Invoke as
  /jspec:recall.
disable-model-invocation: true
---

# JSpec — Recall

A new chat starts with no memory of previous chats. This folder carries it instead.

## Read, in this order

1. **`memory/STATE.md`** — where the project stands right now, next actions, open
   questions, hazards. Always current; never a history.
2. **Newest 1–2 files in `memory/journal/`** — what actually happened most recently,
   including findings and corrections.
3. **`memory/DECISIONS.md`** — every decision already made, with its reasoning.

## Then

State in **one or two lines** where the project stands and what the next action is.
Don't summarise the whole history back at the user — they lived it. They need the
resume point, not the recap.

## The rule that makes memory work

**Never re-litigate a decision in `DECISIONS.md`.** Those entries carry their
reasoning precisely so they don't get re-argued every session. If you believe one is
now wrong, say so once, cite its ID, and ask — then supersede it with a new entry
rather than editing the old one.

## Before the session ends

Per `CLAUDE.md` §0b: append to today's journal, overwrite `STATE.md` to describe
*now*, append any new decision. A session isn't finished until a new chat tomorrow
could continue from what's on disk.
