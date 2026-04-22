---
phase: 04-duplicate-guard-and-review-workflow
plan: 01
subsystem: validation
tags: [duplicates, validators, sequence-matcher, reporting]
requires:
  - phase: 03-contextual-lexical-review
    provides: accepted-card validation flow and audit-ready rejection logging
provides:
  - typed duplicate evidence for exact and near duplicate rejection
  - accepted-card-only duplicate memory with bounded shortlist matching
  - exact and near duplicate reason codes for downstream reporting
affects: [review-queue, quality-report, deck-builder]
tech-stack:
  added: []
  patterns: [normalized duplicate signatures, accepted-card-only memory, shortlist-bounded fuzzy matching]
key-files:
  created: []
  modified: [ankideck_generator/core/models.py, ankideck_generator/core/validators.py, ankideck_generator/tests/test_validators.py]
key-decisions:
  - "Duplicate evidence is a typed model carrying kind, bucket key, normalized sentence, and similarity for downstream audit consumers."
  - "Near-duplicate checks stay bounded to a same-focus shortlist of at most 12 accepted sentences before SequenceMatcher runs."
patterns-established:
  - "Validator duplicate checks distinguish duplicate_sentence_exact from duplicate_sentence_near."
  - "ValidationContext preserves last_duplicate_evidence for the most recent duplicate rejection."
requirements-completed: [QUAL-01]
duration: 5min
completed: 2026-04-22
---

# Phase 4 Plan 1: Duplicate Guard Foundation Summary

**Normalized accepted-card duplicate signatures with exact-vs-near reason codes and bounded shortlist matching for obvious rewrites.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-22T17:45:46Z
- **Completed:** 2026-04-22T17:50:46Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added `DuplicateDecisionEvidence` so duplicate rejections carry structured exact/near evidence.
- Extended `ValidationContext` with accepted-card duplicate memory and `last_duplicate_evidence`.
- Proved exact duplicate, near duplicate, and shortlist-bounded behavior with focused validator regressions.

## Task Commits

Observed implementation commit(s):

1. **Task 1: Define structured exact and near-duplicate validation evidence** - `64d0913` (feat, pre-existing consolidated Phase 04 implementation)
2. **Task 2: Wire duplicate evidence through DeckBuilder and runtime error policy** - `64d0913` (feat, pre-existing consolidated Phase 04 implementation)

**Plan metadata:** pending docs commit from this execution.

## Files Created/Modified
- `ankideck_generator/core/models.py` - Adds `DuplicateDecisionEvidence` and `LogRecord.duplicate_evidence` support.
- `ankideck_generator/core/validators.py` - Normalizes duplicate text, keeps accepted-card memory, and emits exact/near duplicate reason codes.
- `ankideck_generator/tests/test_validators.py` - Locks exact duplicate, near duplicate, and shortlist-limit behavior.

## Decisions Made
- Used NFKC, lowercase, punctuation stripping, and whitespace collapse to make exact duplicate checks resilient to formatting-only tampering.
- Limited near-duplicate matching to same-focus accepted sentences with a shortlist cap of 12 before `SequenceMatcher` runs.

## Deviations from Plan

None - implementation already matched the plan and only required verification plus summary/state completion.

## Issues Encountered
- The implementation was already present in existing commit `64d0913`, so this execution could verify and document it but could not retroactively recreate per-task atomic commits.

## TDD Gate Compliance
- Warning: no separate `test(04-01)` or `feat(04-01)` gate commits were found; the verified implementation exists in consolidated commit `64d0913`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Duplicate evidence and reason codes are ready for review-queue serialization and quality-report aggregation.
- DeckBuilder can safely consume validator evidence without widening duplicate scope beyond accepted cards.

## Self-Check: PASSED

---
*Phase: 04-duplicate-guard-and-review-workflow*
*Completed: 2026-04-22*
