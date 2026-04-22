# Phase 3: contextual-lexical-review - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Build translation and definition around the already accepted sentence context, add an AI-first review/correction stage for lexical fields, and rerun deterministic validation before anything reaches acceptance or audio. This phase does not reopen sentence generation as the primary lever and does not add a blocking human-review runtime lane to the main execution path.

</domain>

<decisions>
## Implementation Decisions

### Review routing
- **D-01:** Fixable lexical issues should be auto-corrected and the run should continue without operator intervention.
- **D-02:** If lexical review remains low-confidence after checking sentence context, the card should be rejected into `review_queue.json` with structured reason codes instead of entering a blocking `human-review` runtime state.
- **D-03:** Uncertain cards must not interrupt unattended runs; manual follow-up happens after the run from queue artifacts.
- **D-04:** Accepted corrections must preserve full before/after snapshots and reason codes in audit data.

### Correction scope
- **D-05:** Phase 3 may correct `definition` and `translation`, but it should not retake ownership of sentence generation by default.
- **D-06:** The accepted sentence is the anchor; when lexical meaning clashes with the sentence, the lexical fields should be realigned to the sentence rather than rewriting the sentence to fit them.
- **D-07:** When only one lexical field is wrong, prefer a minimal patch to that field instead of regenerating the entire lexical bundle.
- **D-08:** The visible focus word stays locked once the sentence has been accepted.

### Ambiguous sense handling
- **D-09:** When multiple senses are plausible, auto-pick the best sentence-matched sense by default so the run keeps moving.
- **D-10:** The final learner-facing definition must stay single-sense and concise, not a multi-sense dump.
- **D-11:** Preserve losing sense candidates and the rationale for the winning choice in audit data.
- **D-12:** Escalate ambiguity only when the reviewer cannot clearly justify one sense from the sentence context.

### Acceptance bar
- **D-13:** Any AI or manual correction must rerun the full deterministic validator suite before acceptance.
- **D-14:** Corrected cards use the same hard-vs-soft acceptance thresholds as the rest of the pipeline after revalidation.
- **D-15:** Interactive/manual edits do not get a bypass path or a looser gate than AI corrections.
- **D-16:** If a correction fails revalidation, reject the card to follow-up queue with before/after evidence and reason codes.

### the agent's Discretion
- Exact typed schema for review verdicts and reason-code taxonomy, as long as it supports accept/correct/reject plus rejected-queue fallback.
- Exact helper/service extraction boundaries between `DeckBuilder` and `ProviderManager`.
- Exact scoring or tie-break logic for the "best sentence-matched sense," as long as the winning choice remains explainable in audit data.
- Exact storage shape for losing-candidate evidence in logs and review artifacts.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope
- `.planning/PROJECT.md` — Product direction, non-negotiables, and the AI-first lexical quality goals.
- `.planning/REQUIREMENTS.md` — Phase 3 requirements `LEX-01` through `LEX-04` plus `COMP-04`.
- `.planning/ROADMAP.md` — Phase 3 goal, success criteria, and plan breakdown.
- `.planning/STATE.md` — Current project position and carried milestone decisions.

### Prior phase decisions
- `.planning/phases/01-run-state-foundation/01-CONTEXT.md` — Locks the AI-first autonomous flow, compact lifecycle posture, accepted-card semantics, and rejected-queue audit pattern.
- `.planning/phases/02-ai-sentence-generation/02-CONTEXT.md` — Locks structured AI sentence generation and the accepted-sentence-first starting point for Phase 3.

### Codebase analysis
- `.planning/codebase/ARCHITECTURE.md` — Current orchestration, provider gateway, validation flow, and export boundary.
- `.planning/codebase/CONCERNS.md` — Existing interactive-edit validation gap and other constraints around `DeckBuilder`.
- `.planning/codebase/CONVENTIONS.md` — Repo guidance for minimal helper extraction, typed models, and focused regression coverage.
- `.planning/codebase/STRUCTURE.md` — Where core pipeline code, tests, and output artifacts live.
- `.planning/codebase/INTEGRATIONS.md` — Existing translation, AI, and TTS integrations plus output artifact surfaces.

### Runtime policy
- `config.yaml` — Active lexical runtime knobs, queue/report paths, and validation budgets that Phase 3 must stay compatible with.
- `definition_policy.yaml` — Policy-driven definition normalization rules that should remain config-first.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ankideck_generator/core/providers.py::definition_candidates()` and `definition_from_context()` — Existing seams for source-language and sentence-aware definition retrieval.
- `ankideck_generator/core/providers.py::translation_web()` and `translation_ai()` — Current translation providers that can sit behind a new lexical review contract.
- `ankideck_generator/core/deck_builder.py` candidate previews, `review_notes`, `selection_reasons`, `before`, and `after` fields — Existing audit containers for corrected cards and ambiguity evidence.
- `ankideck_generator/core/validators.py::validate_card()` and `ValidationContext` — Existing deterministic gate to rerun after AI or manual edits.
- `ankideck_generator/core/deck_builder.py::_record_log()` and `_write_quality_outputs()` — Existing outputs for rejected follow-up queueing and accepted-with-corrections reporting.

### Established Patterns
- Sentence context is chosen before lexical resolution when `config.yaml` keeps `runtime.definition_context_first: true`; Phase 3 should treat the accepted sentence as the anchor.
- The runtime prefers file-based queue/report artifacts and machine-readable reason codes over blocking review workflows.
- Hard-vs-soft validation thresholds already exist and should stay deterministic after correction.
- Provider-facing behavior belongs behind `ProviderManager`, with minimal helper extraction around the large `DeckBuilder` orchestrator.

### Integration Points
- `ankideck_generator/core/deck_builder.py::_process_word_textual()` — Where sentence context, definition candidates, translation, review notes, and candidate evidence already meet.
- `ankideck_generator/core/deck_builder.py::_process_word()` — Current acceptance and audio gate; post-correction revalidation must happen here or an equivalent pre-audio seam.
- `ankideck_generator/core/deck_builder.py::_interactive_edit()` — Existing manual edit path that must be brought under the same revalidation contract.
- `output/review_queue.json` and `output/quality_report.json` — Existing artifact contract Phase 3 should preserve while enriching lexical review evidence.

</code_context>

<specifics>
## Specific Ideas

- The accepted sentence stays fixed; Phase 3 aligns lexical fields to that sentence instead of rewriting the sentence to salvage meaning.
- Long runs should stay autonomous; low-confidence cases are handled through rejected queue artifacts after the run, not by blocking execution.
- Final learner-facing definitions should read as one clear sense even when audit data keeps alternate candidates.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 03-contextual-lexical-review*
*Context gathered: 2026-04-20*
