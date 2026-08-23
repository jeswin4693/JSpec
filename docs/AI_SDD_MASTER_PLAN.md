<!--
PROVENANCE
  Source   : "AI_SDD_MASTER_PLAN.md - Master Claude Code Build Prompt", supplied by
             Jeswin J on 2026-08-23.
  Status   : Governing build specification for this repository, as reconciled by
             DECISIONS.md D-016 through D-021.
  Repair   : The source arrived mojibaked - UTF-8 read as Latin-1, so every arrow
             character became "a-circumflex" and every box-drawing glyph became a run
             of them. Those have been repaired to the correct characters. No other
             edit was made to the text.
  Loading  : This file is LOAD-ON-DEMAND, not auto-imported - it is ~12k tokens and
             section 60 of this very document forbids spending context unnecessarily.
             The binding rules are auto-loaded via docs/MASTER-PLAN-DIGEST.md instead.
  Amended  : Sections 5, 32, 33, 62 and the phase order in 57 are amended by
             DECISIONS.md D-017, D-018 and D-020. The amendments are recorded there
             and summarised in the digest; this document is preserved as written.
-->

# AI Spec-Driven Software Development System
## Master Build Specification for Claude Code

---

# 0. ROLE

You are Claude Code acting as the principal software architect, senior TypeScript engineer, AI systems engineer, code-intelligence engineer, test engineer, and technical reviewer for this project.

Your task is to BUILD the system described in this document.

Do not merely explain how to build it.

You must progressively implement it in the repository.

However:

**DO NOT attempt to implement the entire system in one operation.**

Work incrementally.

Complete one phase, validate it, document it, and then proceed to the next phase.

---

# 1. PROJECT VISION

Build an:

# Experience-Augmented AI Spec-Driven Software Development System

The system should help developers transform:

Requirement
→ Specification
→ Specification Review
→ Engineering Experience Review
→ Repository Retrieval
→ Implementation Plan
→ Code Generation
→ Validation
→ Repair
→ Traceability
→ Knowledge Capture

The system must work with external AI models such as:

- Claude
- GPT
- Gemini
- Other LLM providers

The architecture MUST remain model-independent.

---

# 2. PRIMARY OBJECTIVE

The system is NOT simply an AI code generator.

Its purpose is to combine:

    Specification
    +
    Existing Repository
    +
    Engineering Experience
    +
    AI Reasoning
    +
    Automated Validation

to produce:

    Small
    Correct
    Maintainable
    Tested
    Traceable
    Token-efficient
    Evidence-grounded

software changes.

---

# 3. CRITICAL DESIGN PRINCIPLE

The LLM must NOT be given the entire repository by default.

Never use:

    Entire repository
        →
    LLM

Instead use:

    Task
      →
    Specification
      →
    Repository Index
      →
    Search
      →
    Ranking
      →
    Relevant Symbols
      →
    Progressive Context Expansion
      →
    Minimal Sufficient Context
      →
    LLM

The system must optimize for:

# Minimum Sufficient Context

NOT:

# Minimum Context

The goal is to remove irrelevant information while preserving the evidence required for a correct decision.

---

# 4. CORE PRINCIPLES

Follow these principles throughout implementation.

1. Specification before implementation.

2. Evidence before AI reasoning.

3. Retrieval before generation.

4. Reuse before creation.

5. Symbols before files.

6. Relevant context before large context.

7. Plan before modification.

8. Minimal patch before large rewrite.

9. Validation before completion.

10. Human approval for high-risk changes.

11. Never trust generated code without validation.

12. Never hallucinate repository APIs.

13. Never invent files or functions.

14. Never modify unrelated files.

15. Never silently turn recommendations into requirements.

16. Prefer deterministic processing over AI when deterministic processing is sufficient.

17. Use AI only where reasoning adds value.

18. Cache reusable information.

19. Incrementally update indexes.

20. Track token usage.

21. Track retrieval quality.

22. Track model cost and latency.

23. Preserve traceability.

24. Capture durable engineering knowledge.

---

# 5. TECHNOLOGY BASELINE

> **AMENDED by D-017.** The core is Python 3.12/3.13, not TypeScript. The reasoning:
> ~1,054 lines of tested Python already exist with green CI; `tree-sitter` parses
> TypeScript and TSX perfectly well, so analysing TS repositories does not require
> writing the tool in TS. `ts-morph` remains available later as an optional sidecar
> if type-aware semantic analysis proves necessary. Everything else in this section
> stands.

Unless repository constraints require otherwise, use:

    TypeScript
    Node.js
    npm
    Git

Prefer a simple architecture initially.

Do NOT introduce unnecessary frameworks.

Avoid adding:

- large agent frameworks
- unnecessary orchestration frameworks
- unnecessary vector databases
- unnecessary microservices
- unnecessary infrastructure

The first version should be:

# Local-first and CLI-first.

---

# 6. TARGET USER WORKFLOW

The eventual developer experience should support commands such as:

    sdd init

    sdd scan

    sdd analyze <spec>

    sdd review <spec>

    sdd plan <spec>

    sdd implement <spec>

    sdd validate

    sdd impact

    sdd explain

    sdd learn

    sdd status

    sdd tokens

---

# 7. TARGET ARCHITECTURE

The system should eventually contain:

    CLI / UI
       →
    Task Orchestrator
       →
    Specification Engine
       →
    Repository Intelligence Engine
       →
    Experience Engine
       →
    Retrieval Engine
       →
    Context Engineering Engine
       →
    AI Gateway
       →
    Model Router
       →
    Planning Engine
       →
    Code Generation Engine
       →
    Validation Engine
       →
    Repair Engine
       →
    Traceability Engine
       →
    Knowledge Capture Engine

Supporting all of these:

    Cache
    Storage
    Security
    Configuration
    Observability
    Token Accounting

---

# 8. PROJECT STRUCTURE

Create and maintain this structure:

    .sdd/
    │
    ├── constitution.md
    ├── config.yaml
    ├── state.json
    │
    ├── specs/
    │   ├── active/
    │   ├── completed/
    │   └── archived/
    │
    ├── knowledge/
    │   ├── architecture/
    │   ├── patterns/
    │   ├── anti-patterns/
    │   ├── incidents/
    │   ├── lessons/
    │   ├── decisions/
    │   └── domain/
    │
    ├── index/
    │   ├── files/
    │   ├── symbols/
    │   ├── dependencies/
    │   └── embeddings/
    │
    ├── cache/
    │   ├── summaries/
    │   ├── retrieval/
    │   └── ai/
    │
    ├── plans/
    ├── reviews/
    ├── traces/
    ├── metrics/
    └── prompts/

Application source:

    src/
    │
    ├── cli/
    │
    ├── orchestrator/
    │
    ├── specification/
    │   ├── parser/
    │   ├── analyzer/
    │   ├── critic/
    │   └── models/
    │
    ├── repository/
    │   ├── scanner/
    │   ├── classifier/
    │   ├── ast/
    │   ├── symbols/
    │   └── dependencies/
    │
    ├── retrieval/
    │   ├── exact/
    │   ├── lexical/
    │   ├── semantic/
    │   ├── structural/
    │   ├── hybrid/
    │   └── ranking/
    │
    ├── context/
    │   ├── builder/
    │   ├── budget/
    │   ├── compression/
    │   └── progressive/
    │
    ├── experience/
    │   ├── knowledge/
    │   ├── incidents/
    │   ├── decisions/
    │   └── lessons/
    │
    ├── ai/
    │   ├── gateway/
    │   ├── providers/
    │   ├── router/
    │   └── schemas/
    │
    ├── planning/
    │
    ├── generation/
    │
    ├── validation/
    │
    ├── repair/
    │
    ├── traceability/
    │
    ├── cache/
    │
    ├── security/
    │
    ├── config/
    │
    └── observability/

---

# 9. PHASED DEVELOPMENT RULE

You MUST develop the system in phases.

Do not jump directly to Phase 8 or Phase 10.

Each phase must contain:

    Implementation
    Tests
    Documentation
    Validation
    Example usage

After completing a phase:

1. Run tests.
2. Run type checking.
3. Run linting if configured.
4. Review the architecture.
5. Update project state.
6. Update documentation.
7. Record decisions.
8. Report what was completed.
9. Identify the next phase.

---

# 10. PHASE 0 - PROJECT BOOTSTRAP

Create:

    package.json
    tsconfig.json
    src/
    tests/
    README.md
    .gitignore
    .sdd/
    .sdd/constitution.md
    .sdd/config.yaml
    .sdd/state.json

Set up:

    TypeScript
    Node.js
    test framework
    linting
    formatting

Do not introduce AI yet.

Goal:

# Establish a clean engineering foundation.

---

# 11. PHASE 1 - REPOSITORY INTELLIGENCE

Build the Repository Intelligence Engine.

It must scan a repository and understand:

    Files
    Directories
    Languages
    File types
    Classes
    Functions
    Methods
    Imports
    Exports
    Interfaces
    Types
    Dependencies

For TypeScript/JavaScript specifically support AST analysis.

Prefer:

    TypeScript compiler APIs
    or
    ts-morph

where appropriate.

---

# 12. FILE MANIFEST

Create a file metadata model.

Example:

    {
      "path": "src/pages/LoginPage.ts",
      "language": "typescript",
      "category": "page-object",
      "size": 4821,
      "lines": 143,
      "hash": "...",
      "symbols": [...]
    }

Do not rely on line count as the primary relevance mechanism.

A large file may contain the exact required symbol.

A small file may be completely irrelevant.

Relevance must come from:

    semantics
    symbols
    dependencies
    task relationship
    search evidence

NOT file size alone.

---

# 13. PHASE 1 SYMBOL INDEX

Extract:

    classes
    methods
    functions
    interfaces
    types
    constants
    exports
    imports

Store symbol metadata.

Example:

    FinancePage.processSelectedModules

with:

    file
    class
    method
    parameters
    return type
    source range
    references
    dependencies

---

# 14. PHASE 1 DEPENDENCY GRAPH

Build:

    File → File

and:

    Symbol → Symbol

relationships.

Example:

    LoginTest
       →
    LoginPage
       →
    AuthHelper
       →
    Config

Store enough metadata to support impact analysis.

---

# 15. PHASE 1 INCREMENTAL INDEXING

Use content hashes.

If:

    file hash unchanged

then:

    do not reparse

If:

    file changed

then:

    re-index only that file and affected dependencies.

Never reprocess the entire repository unnecessarily.

---

# 16. PHASE 1 TESTS

Create tests for:

- file discovery
- file classification
- AST parsing
- symbol extraction
- dependency extraction
- hashing
- incremental indexing

The Repository Intelligence Engine must be usable without any LLM.

---

# 17. PHASE 2 - SPECIFICATION ENGINE

Implement:

    Markdown parser
    Requirement extractor
    Requirement model
    Acceptance criteria extraction
    Preconditions
    Actions
    Expected results
    Constraints

Support a structured Markdown specification.

Example:

    # Feature

    ## Objective

    ## Preconditions

    ## Scenario

    ## Expected Result

    ## Acceptance Criteria

---

# 18. SPECIFICATION INTERNAL MODEL

Use a structured model similar to:

    Specification
      ├── id
      ├── title
      ├── objective
      ├── actors
      ├── preconditions
      ├── requirements
      ├── scenarios
      ├── acceptanceCriteria
      ├── constraints
      └── metadata

---

# 19. PHASE 2 SPECIFICATION CRITIC

The Specification Critic must identify:

    ambiguity
    missing requirements
    conflicting requirements
    missing error handling
    missing edge cases
    missing security considerations
    missing performance considerations
    missing accessibility considerations
    missing testing scenarios
    missing observability

Every finding must be classified:

    REQUIRED
    RECOMMENDED
    RISK
    OPEN_QUESTION
    OPTIONAL

Do not silently modify the original specification.

---

# 20. PHASE 3 - RETRIEVAL ENGINE

Implement retrieval in this order:

    1. Exact search
    2. Symbol search
    3. Lexical search
    4. Structural search
    5. Semantic search
    6. Hybrid ranking

Use cheap retrieval methods before expensive ones.

Semantic retrieval should NOT be the first tool for every task.

---

# 21. RELEVANCE RANKING

Rank candidates based on:

    exact match
    symbol similarity
    lexical relevance
    semantic similarity
    dependency relationship
    file category
    historical relevance
    task relationship

Do not rank based simply on:

    largest file
    newest file
    most frequently modified file

---

# 22. PHASE 4 - CONTEXT ENGINEERING

This is a critical component.

Build:

    ContextBuilder
    TokenBudgetManager
    ContextCompressor
    ProgressiveContextExpander

The system must create:

# Minimum Sufficient Context

for each AI operation.

---

# 23. PROGRESSIVE CONTEXT EXPANSION

Default:

    retrieve symbol

If insufficient:

    retrieve surrounding class

If insufficient:

    retrieve related symbols

If insufficient:

    retrieve dependency

If insufficient:

    retrieve file range

Only when absolutely necessary:

    retrieve full file

Never automatically read the entire repository.

---

# 24. CONTEXT PREFERENCES

Support:

    ALWAYS_INCLUDE
    PREFERRED
    OPTIONAL
    NEVER_INCLUDE

Example:

    specs/**            ALWAYS_INCLUDE
    src/pages/**        PREFERRED
    tests/**            PREFERRED
    docs/**             OPTIONAL
    node_modules/**     NEVER_INCLUDE
    .env*               NEVER_INCLUDE
    secrets/**          NEVER_INCLUDE

---

# 25. USER CONTEXT RESTRICTIONS

Support commands such as:

    sdd implement spec.md \
      --include specs/** src/pages/** tests/**

The retrieval engine must obey explicit user restrictions.

If the user says:

    "Use only these files"

do not retrieve outside them.

---

# 26. TOKEN BUDGETING

Every AI operation must have:

    target token budget
    maximum token budget

Example:

    analysis:
        target = 4000
        maximum = 8000

    planning:
        target = 8000
        maximum = 16000

Do not hardcode these values globally.

Make them configurable.

---

# 27. TOKEN ACCOUNTING

Track:

    input tokens
    output tokens
    cached tokens
    context tokens
    model
    provider
    task
    latency
    estimated cost

Expose:

    sdd tokens

which reports usage.

---

# 28. TOKEN OPTIMIZATION

Implement:

    caching
    deduplication
    source hashing
    symbol retrieval
    progressive retrieval
    context compression
    diff-based context
    model routing
    prompt modularization

Do NOT reduce tokens by removing information blindly.

Reduce:

# irrelevant information.

---

# 29. PHASE 5 - EXPERIENCE ENGINE

Create an engineering knowledge system.

Categories:

    architecture
    patterns
    anti-patterns
    security
    performance
    accessibility
    testing
    incidents
    decisions
    lessons
    domain knowledge

---

# 30. ENGINEERING EXPERIENCE FORMAT

Support documents such as:

    ---
    id: EXP-001
    type: lesson
    category: testing
    tags:
      - playwright
      - async
    ---

    # Lesson

    Description...

    ## Problem

    ...

    ## Cause

    ...

    ## Prevention

    ...

---

# 31. HISTORICAL EXPERIENCE RETRIEVAL

When analyzing a specification:

    search experience

for:

    similar features
    similar bugs
    similar architecture
    similar incidents
    similar decisions

Do not inject all experience into every prompt.

Only retrieve relevant knowledge.

---

# 32. PHASE 6 - AI GATEWAY

> **AMENDED by D-018.** The adapter requirement stands and is already satisfied by
> the D-006 judge port. What changes is the DEFAULT: the default backend is Claude
> Code auth (`claude-code` in-session, `claude-headless` for CI). Key-based providers
> remain implementable behind the same interface for teams that hold keys, but no
> default path may require `ANTHROPIC_API_KEY` or any other provider key, and
> `--bare` is forbidden. CI enforces this.

Create an abstraction:

    interface LLMProvider

Support:

    ClaudeProvider
    OpenAIProvider
    GeminiProvider

The rest of the application must depend on:

    AI Gateway

NOT:

    direct Claude API
    direct OpenAI API
    direct Gemini API

---

# 33. MODEL ROUTER

> **AMENDED by D-018.** Cost-tier routing requires per-model API access and is
> therefore available only on key-based backends. On the default Claude Code backend
> the equivalent lever is ROUTE DEPTH (T-0..T-3) and step skipping - spend less by
> doing less, not by downgrading the model.

Implement model selection based on task complexity.

Examples:

    classification
        → inexpensive model

    extraction
        → inexpensive/medium model

    retrieval interpretation
        → medium model

    planning
        → strong model

    complex debugging
        → strongest available model

Do not use an expensive model for every operation.

---

# 34. AI PROMPT ARCHITECTURE

Create modular prompts.

    prompts/
      system/
      specification/
      review/
      retrieval/
      planning/
      generation/
      validation/
      repair/

Do not create one giant prompt containing the entire system.

Prompts should be composable.

---

# 35. STRUCTURED OUTPUT

Prefer structured JSON output validated against schemas.

Example:

    {
      "decision": "reuse",
      "confidence": 0.93,
      "evidence": [
        {
          "symbol": "FinancePage.processSelectedModules",
          "reason": "Matches required behavior"
        }
      ]
    }

Use schema validation.

Never blindly trust malformed model output.

---

# 36. PHASE 7 - PLANNING ENGINE

Before code generation:

    Specification
        +
    Retrieved repository evidence
        +
    Experience evidence
        +
    Project constitution
        →
    Implementation Plan

The plan must contain:

    requirements
    affected files
    reusable components
    new components
    risks
    tests
    validation strategy

---

# 37. PLAN VALIDATION

Before implementation verify:

1. Every requirement has a plan.

2. Every reused component actually exists.

3. New components are genuinely necessary.

4. No unrelated files are planned.

5. Risks have mitigation.

6. Tests cover acceptance criteria.

If any check fails:

    retrieve more evidence
    or
    request clarification

Do not guess.

---

# 38. PHASE 8 - CODE GENERATION

Code generation must:

    reuse existing code
    follow project conventions
    minimize changes
    preserve architecture
    avoid duplication
    create tests
    avoid unrelated modifications

Prefer:

    patch

over:

    complete file rewrite

---

# 39. MINIMAL PATCH PRINCIPLE

If the required change is:

    8 lines

do not regenerate:

    600 lines

The system should produce focused modifications.

---

# 40. PHASE 9 - VALIDATION

Validate:

    syntax
    type checking
    lint
    unit tests
    integration tests
    Playwright tests
    specification compliance

Use project-native commands where possible.

Do not invent commands without checking the repository.

---

# 41. PHASE 10 - REPAIR ENGINE

When validation fails:

    failure
       →
    classify
       →
    retrieve failure-specific context
       →
    diagnose
       →
    create patch
       →
    validate

Do not resend the complete original context.

---

# 42. REPAIR LIMIT

Maximum automatic repair attempts must be configurable.

Default:

    3

After the limit:

    HUMAN_REVIEW_REQUIRED

Never create infinite loops.

---

# 43. PHASE 11 - TRACEABILITY

Maintain:

    Requirement
       →
    Specification
       →
    Plan
       →
    Code
       →
    Test
       →
    Result

Generate a traceability report.

Example:

    REQ-001
      spec.md:12
        →
      LoginPage.login()
        →
      login.spec.ts:25
        →
      PASS

---

# 44. PHASE 12 - KNOWLEDGE CAPTURE

After successful work:

    implementation
        +
    test results
        +
    human feedback
        →
    candidate lesson

Only durable information should be stored.

Categories:

    lesson
    correction
    architecture decision
    bug pattern
    domain knowledge
    project preference

---

# 45. PROJECT CONSTITUTION

Create:

    .sdd/constitution.md

Default rules:

    # Project Constitution

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

---

# 46. SECURITY

Never send these automatically to external models:

    .env
    credentials
    API keys
    certificates
    private keys
    production secrets
    sensitive customer data

Implement:

    secret detection
    redaction
    file policy
    provider policy

---

# 47. OBSERVABILITY

Track:

    task ID
    phase
    model
    provider
    input tokens
    output tokens
    retrieval count
    retrieved files
    retrieved symbols
    validation result
    repair attempts
    latency
    estimated cost

The system must make token consumption measurable.

---

# 48. CACHE

Cache:

    file hashes
    AST
    symbols
    dependencies
    embeddings
    summaries
    retrieval results
    safe AI responses
    test results

Invalidate cache using content hashes and dependency changes.

---

# 49. GIT INTEGRATION

Use Git for:

    changed files
    diffs
    history
    commit information
    impact analysis

Prefer diffs over unchanged source when analyzing a change.

---

# 50. IMPACT ANALYSIS

Before modifying a shared component:

    identify dependents
    identify affected tests
    estimate risk

Return:

    LOW
    MEDIUM
    HIGH

High-risk modifications require human approval.

---

# 51. AGENT ARCHITECTURE

Do not build a multi-agent system initially.

Once the core system works, agents may be introduced:

    SpecificationAgent
    RetrievalAgent
    ExperienceAgent
    PlanningAgent
    CodingAgent
    TestingAgent
    DebuggingAgent
    ReviewAgent

Agents must operate through controlled tools.

They must not freely read or modify the entire repository.

---

# 52. TOOL ARCHITECTURE

Potential tools:

    searchFiles()
    searchSymbols()
    readSymbol()
    readFileRange()
    findReferences()
    findDependencies()
    searchExperience()
    inspectGit()
    getDiff()
    runTypecheck()
    runTests()
    runPlaywright()
    applyPatch()
    validateSpecification()

Tools must have narrow responsibilities.

---

# 53. TOOL PERMISSIONS

Example:

    Reviewer:
        READ

    Planner:
        READ

    Coding:
        READ + PATCH

    Tester:
        READ + EXECUTE

    Deployment:
        restricted

Never give every agent every capability.

---

# 54. ERROR HANDLING

Every module must:

    validate input
    handle missing data
    handle malformed AI output
    handle tool failure
    log useful diagnostics
    preserve task state

Never silently swallow errors.

---

# 55. TASK STATE

Maintain:

    .sdd/state.json

Example:

    {
      "taskId": "...",
      "phase": "planning",
      "specification": "...",
      "status": "awaiting_approval",
      "attempt": 1
    }

The system must be resumable.

---

# 56. HUMAN APPROVAL

Require approval for:

    architecture changes
    database migrations
    security-sensitive changes
    dependency additions
    destructive commands
    high-risk shared changes
    production operations

Support:

    approve
    reject
    modify

---

# 57. DEVELOPMENT ORDER

> **AMENDED by D-020.** An evaluation phase is inserted between Phase 4 and Phase 5.
> This document contains no phase that measures whether the artifacts the system
> produces are improving - section 68's Definition of Done proves the CODE runs, not
> that the SPECIFICATIONS and PLANS are good. Nothing past Phase 4.5 proceeds
> unproven.

Implement in exactly this order unless a strong technical reason exists:

    Phase 0
      →
    Phase 1
      →
    Phase 2
      →
    Phase 3
      →
    Phase 4
      →
    Phase 5
      →
    Phase 6
      →
    Phase 7
      →
    Phase 8
      →
    Phase 9
      →
    Phase 10
      →
    Phase 11
      →
    Phase 12

Do not skip foundational phases.

---

# 58. CLAUDE CODE OPERATING RULES

When working in this repository:

## Before modifying anything

Inspect:

    package.json
    tsconfig.json
    README.md
    .sdd/constitution.md
    .sdd/config.yaml
    current project state

Do not read every source file.

Use repository search first.

---

# 59. CONTEXT RULE

Before reading a file ask:

    Why do I need this file?

If the answer is unclear:

    DO NOT READ IT.

Prefer:

    search
    symbol lookup
    references
    targeted ranges

over:

    full-file reading.

---

# 60. TOKEN RULE

At every stage ask:

    Can this task be completed with less context?

If yes:

    retrieve less.

But never remove evidence necessary for correctness.

---

# 61. MODIFICATION RULE

Before editing:

    identify exact files
    identify exact symbols
    identify exact change

Then modify.

After editing:

    inspect diff

Reject changes that are unrelated to the task.

---

# 62. AI MODEL RULE

> **AMENDED by D-018.** See section 32. Provider independence is required; a
> key-based provider on the default path is not.

Do not assume a specific AI provider.

The system architecture must support:

    Claude
    GPT
    Gemini
    Other providers

Provider-specific features must live behind adapters.

---

# 63. TEST RULE

Every new module must have tests.

Every bug fixed must have a regression test when practical.

Every phase must finish with passing tests.

---

# 64. DOCUMENTATION RULE

For every major component document:

    purpose
    inputs
    outputs
    dependencies
    failure modes
    token behavior
    examples

---

# 65. DECISION RULE

When multiple implementations are possible:

1. Prefer simplest.
2. Prefer existing project conventions.
3. Prefer deterministic implementation.
4. Prefer lower operational complexity.
5. Prefer lower token consumption.
6. Prefer maintainability.

Do not introduce complexity merely because it is technically interesting.

---

# 66. FIRST TASK

When this master plan is first loaded:

DO NOT implement the entire platform.

Perform only:

# Phase 0 - Project Bootstrap

Then:

1. Inspect the current repository.

2. Determine whether a project already exists.

3. Identify existing technology.

4. Preserve compatible existing configuration.

5. Create missing project foundation.

6. Create `.sdd/constitution.md`.

7. Create `.sdd/config.yaml`.

8. Create `.sdd/state.json`.

9. Create README.

10. Set up testing.

11. Run tests.

12. Run TypeScript validation.

13. Report the result.

Then STOP.

Do not automatically continue to Phase 1 unless explicitly instructed.

---

# 67. AFTER EACH PHASE

Report:

    Phase:
    Status:

    Implemented:
      - ...

    Tests:
      - ...

    Validation:
      - ...

    Files changed:
      - ...

    Token optimization:
      - ...

    Architecture decisions:
      - ...

    Known limitations:
      - ...

    Next phase:
      - ...

---

# 68. DEFINITION OF DONE

A phase is NOT complete merely because code exists.

A phase is complete only when:

    implementation exists
    tests exist
    tests pass
    type checking passes
    documentation exists
    architecture remains coherent
    no unrelated changes exist
    state is updated

---

# 69. FINAL SYSTEM SUCCESS CRITERIA

The mature system should be able to execute:

    sdd implement specs/example.md

and perform:

    Specification analysis
        →
    Missing requirement detection
        →
    Experience retrieval
        →
    Repository retrieval
        →
    Minimal context construction
        →
    Implementation planning
        →
    Human approval
        →
    Minimal patch generation
        →
    Validation
        →
    Targeted repair
        →
    Final verification
        →
    Traceability
        →
    Knowledge capture

while:

    avoiding unnecessary file reads
    avoiding unnecessary token usage
    avoiding duplicate code
    avoiding hallucinated APIs
    avoiding unrelated modifications
    preserving project conventions
    preserving human control

---

# 70. FINAL PRINCIPLE

You are not building a chatbot.

You are not building a generic code generator.

You are building:

# An AI-assisted Software Engineering System.

Its intelligence comes from combining:

    Requirements
    +
    Specifications
    +
    Repository Intelligence
    +
    Engineering Experience
    +
    Retrieval
    +
    Context Engineering
    +
    AI Reasoning
    +
    Automated Validation
    +
    Human Judgment

The LLM is one component.

The engineering system is the product.

Build the system incrementally.

Start with Phase 0.

Do not skip foundations.

Do not over-engineer.

Do not consume context unnecessarily.

Do not claim success without validation.

Always prefer evidence over assumption.

Always prefer minimal sufficient context over maximum context.

Always prefer reuse over recreation.

Always prefer a small correct change over a large generated change.
