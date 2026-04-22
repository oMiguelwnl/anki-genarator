# Roadmap: Anki Deck Generator

## Overview

This roadmap converts the current brownfield CLI from a provider-first text pipeline into an AI-first, accepted-card pipeline without breaking the parts that already work: `wordfreq` intake, repo-root CLI execution, `.apkg` export, audio or TTS generation, cache or progress artifacts, and structured output files. The sequence starts by hardening state and orchestration boundaries, then introduces structured AI generation, contextual review, duplicate control, and finally evaluation plus runtime guardrails so quality gains are measurable and sustainable.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions if needed later

- [x] **Phase 1: Run State Foundation** - Establish explicit card states, safe export gating, and versioned runtime artifacts.
- [x] **Phase 2: AI Sentence Generation** - Make structured AI sentence generation the primary path while preserving bounded fallback behavior.
- [x] **Phase 3: Contextual Lexical Review** - Resolve and review translation plus definition in sentence context before acceptance.
- [x] **Phase 4: Duplicate Guard and Review Workflow** - Add scalable duplicate prevention, audit-ready review artifacts, and accepted-card reporting.
- [ ] **Phase 5: Evaluation and Runtime Controls** - Add benchmark-driven release checks and cost or latency guardrails.

## Phase Details

### Phase 1: Run State Foundation
**Goal**: Introduce explicit pipeline states, versioned cache and progress contracts, export-on-accepted-only behavior, and orchestration seams that let later AI stages land without destabilizing the existing CLI.
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, COMP-01, COMP-02, COMP-05
**Success Criteria** (what must be TRUE):
  1. The runtime can distinguish generated, reviewed, accepted, rejected, and human-review card states.
  2. Resume and cache artifacts store enough version information to prevent stale AI outputs from silently reappearing.
  3. Export consumes only accepted cards while keeping the current repo-root CLI and non-AI fallback behavior intact.
**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Define compact lifecycle, audit, and compatibility-fingerprint contracts.
- [x] 01-02-PLAN.md — Wire deterministic resume and final-decision checkpoint seams into `DeckBuilder`.
- [x] 01-03-PLAN.md — Enforce accepted-only export and rejected-only review artifacts.

### Phase 2: AI Sentence Generation
**Goal**: Move sentence generation to a structured AI-first flow that produces constrained candidate sets, rejects malformed outputs early, and keeps web sources as bounded fallback rather than the default path.
**Depends on**: Phase 1
**Requirements**: AIG-01, AIG-02, AIG-03, AIG-04
**Success Criteria** (what must be TRUE):
  1. The system requests structured sentence candidates from AI for a target word and context.
  2. Wrong-language, malformed, or focus-missing candidates are rejected before lexical resolution begins.
  3. Configured languages still flow through the existing `wordfreq`-based intake and bounded fallback sources remain available.
**Plans**: 4 plans

Plans:
- [x] 02-01-PLAN.md — Add typed candidate schemas, prompt versioning, and AI sentence-generation transport.
- [x] 02-02-PLAN.md — Extract a sentence-generation service and early-rejection seam from `DeckBuilder`.
- [x] 02-03-PLAN.md — Re-route sentence selection to AI-first with bounded fallback and contract fingerprinting.
- [x] 02-04-PLAN.md — Add fixture-based regressions for structured AI batches and salvage-only fallback.

### Phase 3: Contextual Lexical Review
**Goal**: Build translation and definition around the accepted sentence context, add a review or correction stage, and force deterministic revalidation after any automated or human edit.
**Depends on**: Phase 2
**Requirements**: LEX-01, LEX-02, LEX-03, LEX-04, COMP-04
**Success Criteria** (what must be TRUE):
  1. Translation and definition are created or reviewed with the sentence, target word, and intended sense together.
  2. Review can accept, correct, reject, or route a card to human review with structured reasons.
  3. Audio remains a post-acceptance step and corrected cards are revalidated before they can pass.
**Plans**: 3 plans

Plans:
- [x] 03-01-PLAN.md — Define contextual lexical-review contracts, typed verdicts, and AI transport.
- [x] 03-02-PLAN.md — Integrate sentence-anchored lexical review, audit evidence, and reject-queue routing.
- [x] 03-03-PLAN.md — Revalidate all corrections before acceptance and keep audio post-acceptance.

### Phase 4: Duplicate Guard and Review Workflow
**Goal**: Replace flat duplicate checks with indexed guardrails, preserve audit-ready review artifacts, and make accepted-card quality visible in structured outputs.
**Depends on**: Phase 3
**Requirements**: QUAL-01, QUAL-02, QUAL-03, COMP-03, EVAL-03
**Success Criteria** (what must be TRUE):
  1. Exact duplicates and near-duplicates are blocked or flagged before export.
  2. Review artifacts record before or after content, reason codes, and provider or model provenance.
  3. `.apkg`, metadata, quality report, and review queue outputs remain intact with richer acceptance diagnostics.
**Plans**: 3 plans

Plans:
- [x] 04-01-PLAN.md — Build normalized duplicate signatures, exact/near reason codes, and accepted-card-only shortlist guards.
- [x] 04-02-PLAN.md — Integrate audit-ready review queue artifacts with duplicate evidence and decisive-source provenance.
- [x] 04-03-PLAN.md — Publish acceptance/duplicate diagnostics in quality_report.json while preserving export compatibility.

### Phase 5: Evaluation and Runtime Controls
**Goal**: Add reproducible evaluation, acceptance thresholds, and operational guardrails so the milestone can prove quality gains above the current baseline without runaway cost or latency.
**Depends on**: Phase 4
**Requirements**: QUAL-04, EVAL-01, EVAL-02, EVAL-04
**Success Criteria** (what must be TRUE):
  1. The project can run a representative benchmark or gold set across core language and ambiguity slices.
  2. Prompt, model, and validator changes produce reproducible quality and runtime metrics.
  3. Runtime budgets or guardrails limit AI call volume while keeping accepted-only export behavior intact.
**Plans**: 3 plans

Plans:
- [x] 05-01-PLAN.md — Define repo-stored benchmark fixtures and typed evaluation aggregation for sentence, lexical, duplicate, and acceptance quality.
- [ ] 05-02-PLAN.md — Extend runtime metrics and per-stage AI guardrails, including lexical-review budget coverage.
- [ ] 05-03-PLAN.md — Enforce the release gate and readiness reporting for the milestone target above 60% accepted-card rate.

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Run State Foundation | 3/3 | Complete | - |
| 2. AI Sentence Generation | 4/4 | Complete | - |
| 3. Contextual Lexical Review | 3/3 | Complete | 2026-04-22 |
| 4. Duplicate Guard and Review Workflow | 3/3 | Complete | 2026-04-22 |
| 5. Evaluation and Runtime Controls | 0/3 | Not started | - |
