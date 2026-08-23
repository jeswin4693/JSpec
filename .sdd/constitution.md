# Project Constitution

Required by master plan §45. This is the rule set every generated plan, patch and
review is checked against. Rules 1–12 are §45 verbatim; 13–20 are the JSpec
non-negotiables that §45 does not cover, carried over from `memory/DECISIONS.md`.

Amending this file is a decision — record it in `memory/DECISIONS.md`, never edit a
rule silently.

---

## Rules

1. Reuse existing implementations whenever possible.

2. Do not create duplicate functionality.

3. Do not modify unrelated files.

4. Do not introduce dependencies without approval.

5. Tests must follow existing project conventions.

6. Specifications define functional requirements.

7. Recommendations must not become requirements without approval.

8. Generated code must pass validation.

9. High-risk changes require human approval.

10. Prefer minimal patches.

11. Never expose secrets to external AI models.

12. Preserve traceability.

13. **Artifacts are typed data.** Every artifact is a validated object; markdown is a
    rendering of it, never the source of truth. Schema first, prose second. *(D-002)*

14. **Determinism boundary.** Blast radius, dependency graphs, risk arithmetic, token
    counts and diff hashes are computed in Python. Ambiguity, quality and risk
    *judgement* come from the model. Never pay a model to do arithmetic. *(D-003)*

15. **Evidence or silence.** Every model judgement carries `confidence` and non-empty
    `evidence[]`. Below the confidence floor → escalate, never guess. *(D-003)*

16. **No API key on any default path.** The system runs on Claude Code auth.
    Anything requiring `ANTHROPIC_API_KEY` by default is a design error, and `--bare`
    is forbidden — it bypasses subscription auth. *(D-006)*

17. **Minimum sufficient context.** Remove irrelevant information; never remove
    evidence required for a correct decision. The whole repository is never sent to a
    model. *(master plan §3)*

18. **Gates are priced by risk, and every gate is logged.** Low risk auto-approves and
    appends to the ledger; high risk requires a named human, an impact scan and a
    rollback plan. `gates.jsonl` is append-only — an approval that lives only in chat
    scrollback is not auditable. *(D-005)*

19. **Ask least, never twice.** Resolve unknowns in order: preferences → repo →
    profile → assume-and-flag → ask. Batch questions; persist every answer. Prefer a
    flagged assumption reviewed at a gate over a question asked mid-flight. *(D-010)*

20. **Domain knowledge lives in profiles, not in code.** Nothing Playwright-, M2M- or
    Aptean-specific belongs in `core/`. A new domain must be a YAML file, not a code
    change. *(D-011)*

---

## Precedence

1. This constitution
2. `memory/DECISIONS.md` (append-only; a later entry supersedes an earlier one by ID)
3. `docs/MASTER-PLAN-DIGEST.md`
4. `docs/AI_SDD_MASTER_PLAN.md`
5. `CLAUDE.md`

A conflict between levels is resolved upward, then **flagged to the user** — never
resolved silently.
