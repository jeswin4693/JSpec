---
description: Produce a validated specification from a routed request. Called by the
  JSpec router on T-2 and T-3 routes, or invoked directly as /jspec:specify.
disable-model-invocation: true
---

# JSpec — Specify

Turn a request into a **validated `Spec` object**. Template contract:
`templates/specify.yaml` (inputs, output schema, question budget 3, token budget 2400).

## What a spec is, and is not

**Is:** what and why. User journeys, requirements, measurable outcomes.
**Is not:** how. No framework, no file paths, no library choices, no schema design.
Technology leaking into a spec is the single most common failure — the Spec Critic
checks for it explicitly.

## Produce

1. **User stories, prioritised P1/P2/P3.** Each must be *independently testable* —
   implement only that one and you still have something that delivers value. If a
   story can't stand alone, it isn't a story; fold it into one that can.
2. **`FR-nnn` functional requirements.** One capability each, stated as
   "System MUST …" or "Users MUST be able to …". Every requirement carries
   `testable: true|false`. If false, say what would make it testable.
3. **`SC-nnn` success criteria.** Measurable and technology-agnostic — a number, a
   threshold, or an observable outcome. "Works well" is not a success criterion.
4. **Edge cases.** Boundaries and error paths, not a wish list.
5. **Clarifications.** Anything genuinely ambiguous, marked and attributed to the
   requirement it affects.

## Submit, don't write

Call `submit_spec` with the structured object. The MCP server validates against the
schema and renders the markdown. **Do not write `spec.md` yourself** — an artifact
that bypassed validation is untrusted, and hand-written markdown is exactly how
prose creeps back in.

If validation fails, read the error, fix the object, resubmit.

## Unknowns

Follow the router's resolution order: preferences → repo → profile →
assume-and-flag → ask. Budget is **3 questions**, batched into one turn.

Prefer flagging over asking. A requirement marked
`[ASSUMED: dual-environment, both AKS and Appcentral]` costs the user two seconds to
correct at the gate; a question costs them a context switch now.

## Then

Hand off to the Spec Critic (`agents/spec-critic.md`). Do not proceed to planning
until the critic's findings are addressed or explicitly waived — an unclarified spec
is the most expensive artifact in the pipeline, because everything downstream
inherits its ambiguity.
