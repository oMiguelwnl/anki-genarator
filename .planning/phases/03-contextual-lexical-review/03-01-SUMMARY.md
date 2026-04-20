---
phase: 03-contextual-lexical-review
plan: 01
subsystem: api
tags: [pydantic, ai-review, lexical-review, providers, pytest]
requires:
  - phase: 02-ai-sentence-generation
    provides: accepted sentence contracts and structured AI transport patterns
provides:
  - typed lexical review request and result contracts
  - validated AI lexical review transport in ProviderManager
  - sentence-anchored lexical review service for sense normalization
affects: [deck-builder, review-queue, validation]
tech-stack:
  added: []
  patterns: [pydantic contract validation, service seam around ProviderManager, typed AI transport wrappers]
key-files:
  created: [ankideck_generator/core/lexical_review.py]
  modified: [ankideck_generator/core/models.py, ankideck_generator/core/providers.py, ankideck_generator/tests/test_providers.py, ankideck_generator/tests/test_lexical_review.py]
key-decisions:
  - "Lexical review uses explicit Pydantic request and result models with accept, correct, and reject as the only valid verdicts."
  - "ProviderManager validates lexical review JSON into a typed transport result before domain policy consumes it."
  - "LexicalReviewService resolves an explainable winning sense locally and rejects unresolved ambiguity instead of inventing a runtime human-review state."
patterns-established:
  - "Typed AI review contract: request and result schemas live in core/models.py and are validated at the provider boundary."
  - "Sentence-anchored review policy: service logic infers a winning sense from existing evidence and preserves losing candidates for audit."
requirements-completed: [LEX-01, LEX-02, LEX-03]
duration: 4 min
completed: 2026-04-20
---

# Phase 3 Plan 1: Contextual lexical-review contracts Summary

**Typed lexical review contracts, validated AI transport, and a sentence-anchored sense-selection service for definition and translation review**

## Performance

- **Duration:** 4 min
- **Started:** 2026-04-20T20:07:21Z
- **Completed:** 2026-04-20T20:12:04Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added explicit lexical review request, correction, and result contracts with a fixed accept/correct/reject verdict taxonomy.
- Added `ProviderManager.lexical_review()` to validate structured AI output before orchestration can consume it.
- Added `LexicalReviewService` to normalize winning-sense selection, minimal definition correction, and ambiguity rejection.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add typed lexical-review contracts and verdict taxonomy** - `56358b8` (test), `02985c3` (feat)
2. **Task 2: Add provider transport and lexical-review service scaffold** - `0cad81a` (test), `58f2c57` (feat)

**Plan metadata:** recorded in the final docs commit for this plan.

## Files Created/Modified
- `ankideck_generator/core/models.py` - Adds typed lexical review request, correction, and result contracts.
- `ankideck_generator/core/providers.py` - Adds lexical review transport and Pydantic validation for AI payloads.
- `ankideck_generator/core/lexical_review.py` - Adds sentence-anchored lexical review policy and ambiguity handling.
- `ankideck_generator/tests/test_providers.py` - Verifies malformed lexical review payloads are rejected.
- `ankideck_generator/tests/test_lexical_review.py` - Verifies verdict contracts, sense auto-picking, and unresolved ambiguity rejection.

## Decisions Made
- Used a dedicated `LexicalReviewTransportResult` wrapper so malformed AI output surfaces as an error instead of partial success.
- Let the service infer a winning sense from existing evidence (`source_definition` or a single candidate) before rejecting ambiguity.
- Kept corrections minimal by auto-patching the definition only when the winning sense clearly differs from the current definition.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for `03-02-PLAN.md` to wire lexical review into `DeckBuilder` and queue artifacts.
- Provider transport and service seams are in place for downstream orchestration work.

## Self-Check: PASSED

- Found summary file on disk.
- Found task commits `56358b8`, `02985c3`, `0cad81a`, and `58f2c57` in git history.
