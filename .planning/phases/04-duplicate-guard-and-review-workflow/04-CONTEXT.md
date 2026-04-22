# Phase 4: Duplicate Guard and Review Workflow - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the current flat duplicate checks with scalable exact and near-duplicate guardrails against accepted cards, preserve audit-ready review artifacts for rejected outcomes, and make accepted-card duplicate and acceptance quality visible in structured outputs. This phase does not add a blocking runtime review lane, a new reviewer UI, or broader semantic clustering beyond bounded duplicate control.

</domain>

<decisions>
## Implementation Decisions

### Duplicate Guard
- **D-01:** Near-duplicates should mean obvious rewordings of the same accepted card, not only punctuation or case variants and not full semantic card clustering.
- **D-02:** Duplicate comparison scope is accepted cards only.
- **D-03:** Near-duplicate matching should use a balanced threshold that catches obvious rewrites without suppressing legitimate example variety.
- **D-04:** The duplicate shortlist should be keyed by `focus + normalized sentence`, not sentence-only and not the full lexical card bundle.

### Duplicate Disposition
- **D-05:** Exact duplicates are rejected immediately.
- **D-06:** Near-duplicates are rejected into `output/review_queue.json` with evidence; they are not allowed into export and do not create a blocking runtime review step.
- **D-07:** The first accepted card remains the winner for that run; a later colliding candidate does not replace it.
- **D-08:** Duplicate decisions must be visible in both `output/review_queue.json` and `output/quality_report.json`.

### Review Artifacts
- **D-09:** Rejected-item artifacts should be audit-ready but still readable by a human without reconstructing the entire run from logs.
- **D-10:** Each rejected or duplicate-queued item should preserve the relevant textual card state needed to explain the decision, including focus, sentence, definition, translation, and changed fields when present.
- **D-11:** Queue provenance should preserve field-level provider information plus the decisive model or provider for the final review or duplicate decision.
- **D-12:** Reason codes should stay specific enough to distinguish duplicate classes and review-failure families, not collapse into broad buckets only.

### Accepted-Card Reporting
- **D-13:** Top-line `quality_report.json` metrics should emphasize accepted-card rate, duplicate reject rate, and accepted-with-corrections counts.
- **D-14:** Duplicate diagnostics should split exact versus near-duplicate counts by level and overall.
- **D-15:** Accepted cards should remain classified as clean accepts versus corrected accepts.
- **D-16:** `quality_report.json` should expose dedicated sections for duplicate diagnostics, acceptance quality, and review diagnostics instead of burying everything in flat counters.

### the agent's Discretion
- Exact normalization helpers, signature format, and hashing details for the duplicate shortlist.
- Exact shortlist size and fuzzy-threshold numeric values, as long as they implement the balanced posture above.
- Exact JSON field names and section nesting inside `quality_report.json` and `review_queue.json`, as long as the locked decisions above remain visible.
- Exact duplicate-specific reason-code names, as long as exact and near-duplicate outcomes remain distinguishable.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope
- `.planning/PROJECT.md` — Product direction, acceptance-rate goal, duplicate-quality expectations, and brownfield constraints.
- `.planning/REQUIREMENTS.md` — Phase 4 requirements `QUAL-01`, `QUAL-02`, `QUAL-03`, `COMP-03`, and `EVAL-03`.
- `.planning/ROADMAP.md` — Phase 4 goal, success criteria, and plan breakdown.
- `.planning/STATE.md` — Current project position and carried milestone decisions.

### Prior phase decisions
- `.planning/phases/01-run-state-foundation/01-CONTEXT.md` — Locks rejected-only `review_queue.json`, accepted-only export posture, and aggregate reporting for corrected accepted cards.
- `.planning/phases/03-contextual-lexical-review/03-CONTEXT.md` — Locks autonomous execution, rejected-queue follow-up instead of blocking runtime review, and audit-ready before or after evidence.

### Codebase analysis
- `.planning/codebase/ARCHITECTURE.md` — Current validation, orchestration, and output-writing boundaries.
- `.planning/codebase/CONCERNS.md` — Duplicate-scaling hotspot, reporting fragility, and large-file risk areas in `DeckBuilder`.
- `.planning/codebase/CONVENTIONS.md` — Minimal helper extraction, typed models, JSON/file handling, and focused regression expectations.
- `.planning/codebase/STRUCTURE.md` — Locations of core pipeline code, runtime artifacts, and output contracts.
- `.planning/codebase/TESTING.md` — Existing validator and deck-builder regression patterns to extend.

### Runtime contract
- `config.yaml` — Active duplicate validation rules, output paths for `review_queue.json` and `quality_report.json`, and hard or soft error policy.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ankideck_generator/core/validators.py::ValidationContext` and `validate_card()` — Current exact and near-duplicate gate using `duplicate_focus` and `duplicate_sentence`.
- `ankideck_generator/core/deck_builder.py::_validate_text_candidate()` — Existing pre-acceptance validation seam that can adopt shortlist-based duplicate checks without widening scope.
- `ankideck_generator/core/deck_builder.py::_record_log()` — Current rejected-item assembly path for queue artifacts, including reason codes, before or after state, provider data, and candidate evidence.
- `ankideck_generator/core/deck_builder.py::_write_quality_outputs()` — Existing report writer that already tracks accepted counts, corrected accepts, provider counters, and review totals.
- `ankideck_generator/core/models.py::LogRecord` and `BuildStats` — Current structured containers for provenance, counters, and review evidence.

### Established Patterns
- Duplicate memory currently follows accepted cards through `ValidationContext`, `processed_focus`, and `processed_sentences` rather than a separate persistent duplicate index.
- Rejected outcomes flow into `output/review_queue.json`, while accepted-but-corrected cards stay visible through aggregate metrics in `output/quality_report.json`.
- Reporting and review artifacts are file-based JSON snapshots with machine-readable reason codes.
- The repo prefers narrowly scoped helper extraction around `DeckBuilder` rather than sweeping pipeline rewrites.

### Integration Points
- `ankideck_generator/core/validators.py` — Primary seam for normalized signature logic, exact or near duplicate detection, and duplicate reason codes.
- `ankideck_generator/core/deck_builder.py::_validate_text_candidate()` and the acceptance path around `_process_word()` — Where duplicate decisions must stay aligned with final acceptance.
- `ankideck_generator/core/deck_builder.py::_record_log()` and `_write_quality_outputs()` — Where duplicate evidence and accepted-card diagnostics reach `review_queue.json` and `quality_report.json`.
- `ankideck_generator/tests/test_validators.py` and `ankideck_generator/tests/test_deck_builder.py` — Existing focused regression points for duplicate behavior and output-schema preservation.

</code_context>

<specifics>
## Specific Ideas

- The duplicate guard should be paraphrase-aware enough to catch obvious rewordings, but not so aggressive that it suppresses legitimate sentence variety for the same focus word.
- Queue artifacts should explain why a card was rejected or flagged without forcing downstream readers to reconstruct the full execution trace from logs.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-duplicate-guard-and-review-workflow*
*Context gathered: 2026-04-22*
