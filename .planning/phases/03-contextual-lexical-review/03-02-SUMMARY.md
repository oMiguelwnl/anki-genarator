---
phase: 03-contextual-lexical-review
plan: 02
subsystem: api
tags: [deck-builder, lexical-review, review-queue, pytest]
requires:
  - phase: 03-contextual-lexical-review
    provides: typed lexical review contracts, provider transport, and review service behavior
provides:
  - sentence-anchored lexical review inside DeckBuilder
  - minimal lexical field patching for correctable cards
  - rejected lexical-review routing into existing queue artifacts with audit evidence
affects: [validation, review-queue, audio-gating]
tech-stack:
  added: []
  patterns: [sentence-anchored lexical correction, rejected-review artifact routing, before-after lexical audit snapshots]
key-files:
  created: []
  modified: [ankideck_generator/core/deck_builder.py, ankideck_generator/core/lexical_review.py, ankideck_generator/tests/test_deck_builder.py]
key-decisions:
  - "DeckBuilder now invokes lexical review after sentence selection and lexical field assembly so the accepted sentence remains the immutable anchor."
  - "Correct lexical-review verdicts patch only the provided lexical fields and keep the accepted sentence plus focus word untouched."
  - "Reject lexical-review verdicts reuse the existing rejected-card queue contract with reason codes and before or after evidence instead of creating a human-review runtime state."
patterns-established:
  - "Sentence-anchored review orchestration: DeckBuilder builds a LexicalReviewRequest from accepted sentence, current lexical fields, and candidate evidence before finalizing the card."
  - "Queue-first ambiguity handling: unresolved lexical ambiguity is logged as a rejected outcome with durable audit snapshots and reason codes."
requirements-completed: [LEX-01, LEX-02, LEX-03]
duration: 4 min
completed: 2026-04-20
---

# Phase 3 Plan 2: Sentence-anchored lexical review routing Summary

**Sentence-anchored lexical review now corrects mismatched definition or translation fields in place and routes unresolved ambiguity into the existing rejected-card queue with audit evidence.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-20T20:29:36Z
- **Completed:** 2026-04-20T20:33:38Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Wired `DeckBuilder._process_word_textual()` to call `LexicalReviewService` after sentence selection and lexical field assembly.
- Preserved the accepted sentence and focus word while allowing definition-only or translation-only correction.
- Routed reject verdicts through the existing rejected queue flow with reason codes, before or after snapshots, and sense evidence.

## Task Commits

Each task was committed atomically:

1. **Task 1: Apply sentence-anchored lexical review inside `_process_word_textual()`** - `e161beb` (test), `3727e78` (feat)
2. **Task 2: Route unresolved lexical cases to rejected queue artifacts with audit evidence** - `0e8b473` (test), `c8508a1` (feat)

**Plan metadata:** pending final docs commit for this plan.

## Files Created/Modified
- `ankideck_generator/core/deck_builder.py` - Calls lexical review, applies minimal lexical patches, and rejects unresolved ambiguity into queue artifacts.
- `ankideck_generator/core/lexical_review.py` - Preserves reject-path selection reasons from the review service for audit output.
- `ankideck_generator/tests/test_deck_builder.py` - Covers sentence-anchored correction and rejected queue routing regressions.

## Decisions Made
- Kept lexical review after translation assembly so review sees the full lexical bundle against the accepted sentence.
- Stored correction evidence in `LogRecord.before` and `LogRecord.after` instead of inventing a second audit channel.
- Reused `lifecycle_state="rejected"` and `stats.needs_review_items` for unresolved lexical ambiguity to preserve autonomous runs.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Preserve reject-path winning-sense rationale from the review service**
- **Found during:** Task 2 (Route unresolved lexical cases to rejected queue artifacts with audit evidence)
- **Issue:** Reject results from `LexicalReviewService` dropped provider-supplied `selection_reasons`, which removed the winning-sense rationale from queue artifacts.
- **Fix:** Merged transport `selection_reasons` into the reject result before `DeckBuilder` writes queue evidence.
- **Files modified:** `ankideck_generator/core/lexical_review.py`
- **Verification:** `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "review_queue or lexical_review_reject"`
- **Committed in:** `c8508a1`

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** The auto-fix restored required audit evidence without expanding scope.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for `03-03-PLAN.md` to enforce deterministic revalidation after corrections and keep audio strictly post-acceptance.
- Queue artifacts now carry enough lexical evidence for downstream validation and review reporting.

## Self-Check: PASSED

- Found summary file on disk.
- Found task commits `e161beb`, `3727e78`, `0e8b473`, and `c8508a1` in git history.
