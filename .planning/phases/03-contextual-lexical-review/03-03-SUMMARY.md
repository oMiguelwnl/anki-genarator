---
phase: 03-contextual-lexical-review
plan: 03
subsystem: testing
tags: [deck-builder, validation, audio, lexical-review, pytest]
requires:
  - phase: 03-contextual-lexical-review
    provides: sentence-anchored lexical review, correction audit evidence, and rejected queue routing
provides:
  - shared post-correction deterministic revalidation in `DeckBuilder`
  - interactive edit rejection without bypassing acceptance rules
  - corrected-card audio attachment only after final text acceptance
affects: [validation, audio, export]
tech-stack:
  added: []
  patterns: [post-correction revalidation seam, interactive edit evidence merge, audio-after-final-text-acceptance]
key-files:
  created: []
  modified: [ankideck_generator/core/deck_builder.py, ankideck_generator/tests/test_deck_builder.py]
key-decisions:
  - "DeckBuilder now routes both AI corrections and interactive edits through one reusable revalidation helper before a card can be accepted."
  - "Interactive edits merge before or after evidence into the existing lexical review audit trail instead of creating a separate review channel."
  - "Audio attachment now happens only after the final text state is accepted, so failed manual corrections never generate media."
patterns-established:
  - "Correction seam: `_revalidate_card_before_acceptance()` is the single gate for post-review text validation."
  - "Manual evidence merge: interactive edits extend `LogRecord.before` and `LogRecord.after` with changed fields before revalidation."
requirements-completed: [LEX-04, COMP-04]
duration: 7 min
completed: 2026-04-20
---

# Phase 3 Plan 3: Correction revalidation and post-acceptance audio Summary

**DeckBuilder now revalidates every lexical correction before acceptance and delays audio attachment until the final corrected text state is approved.**

## Performance

- **Duration:** 7 min
- **Started:** 2026-04-20T20:39:24Z
- **Completed:** 2026-04-20T20:46:34Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Added one reusable post-correction validation seam for AI-corrected and interactive-edited cards.
- Preserved rejection evidence and reason codes when corrected cards fail deterministic validation.
- Moved audio generation behind final text acceptance so invalid manual corrections do not produce media.

## Task Commits

Each task was committed atomically:

1. **Task 1: Revalidate every AI or manual lexical correction before acceptance** - `52ed9c9` (test), `19031d0` (feat)
2. **Task 2: Keep audio post-acceptance for corrected cards** - `f6fd3b2` (test), `ec08b3b` (feat)

**Plan metadata:** pending final docs commit for this plan.

## Files Created/Modified
- `ankideck_generator/core/deck_builder.py` - Adds the shared correction revalidation helper, merges interactive edit evidence, and moves audio after final text acceptance.
- `ankideck_generator/tests/test_deck_builder.py` - Adds regression coverage for rejected lexical corrections, interactive edit revalidation, and post-acceptance audio ordering.

## Decisions Made
- Reused `_validate_text_candidate()` and `_should_reject_errors()` as the only post-correction acceptance gate instead of inventing a review-specific policy.
- Treated interactive edits as part of the same correction audit trail by merging changed fields into `LogRecord.before` and `LogRecord.after`.
- Kept audio validation separate from text validation, but only after the corrected text state had already cleared acceptance.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- The plan-specified selector `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "audio and lexical_review"` matched zero tests after the new regressions were added, so I also ran focused `interactive_edit and audio` coverage plus the broader deck-builder file for spot-checking.
- The broader deck-builder file still has unrelated failing tests outside this plan's revalidation and audio-ordering scope; they were logged to `.planning/phases/03-contextual-lexical-review/deferred-items.md` and left untouched.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 03 is now complete for correction gating: AI and manual lexical edits must clear deterministic validation before acceptance.
- Corrected cards no longer generate audio before the final accepted text state, preserving the post-acceptance export contract.

## Self-Check: PASSED

- Found summary file on disk.
- Found task commits `52ed9c9`, `19031d0`, `f6fd3b2`, and `ec08b3b` in git history.
