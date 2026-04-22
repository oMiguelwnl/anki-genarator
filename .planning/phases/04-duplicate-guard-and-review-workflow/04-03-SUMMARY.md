---
phase: 04-duplicate-guard-and-review-workflow
plan: 03
subsystem: reporting
tags: [quality-report, duplicates, export, compatibility]
requires:
  - phase: 04-duplicate-guard-and-review-workflow
    provides: review queue payloads with duplicate evidence and separated diagnostics
provides:
  - dedicated acceptance quality, duplicate diagnostics, and review diagnostics report sections
  - exact-vs-near duplicate rates overall and by level
  - output compatibility coverage for quality report, review queue, metadata, and apkg export
affects: [quality-report, export, evaluation]
tech-stack:
  added: []
  patterns: [compatibility-preserving report growth, derived duplicate rates, sectioned diagnostics]
key-files:
  created: []
  modified: [ankideck_generator/core/deck_builder.py, ankideck_generator/tests/test_deck_builder.py, ankideck_generator/tests/test_deck_export.py]
key-decisions:
  - "quality_report.json grows via dedicated sections while preserving legacy top-level counters and file outputs for compatibility."
  - "Duplicate diagnostics split exact and near rejects overall and by level instead of collapsing into one duplicate bucket."
patterns-established:
  - "Report metrics derive from BuildStats counters and rejected-item evidence instead of ad hoc report-only logic."
  - "Deck export compatibility is protected by keeping the existing export regression unchanged."
requirements-completed: [COMP-03]
duration: 5min
completed: 2026-04-22
---

# Phase 4 Plan 3: Quality Report Diagnostics Summary

**Compatibility-safe quality reporting with dedicated acceptance, duplicate, and review diagnostics plus exact-vs-near duplicate rates.**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-22T17:45:46Z
- **Completed:** 2026-04-22T17:50:46Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Expanded `quality_report.json` with `acceptance_quality`, `duplicate_diagnostics`, and `review_diagnostics` sections.
- Split duplicate reporting into exact and near reject counts overall and by level.
- Verified richer reporting still coexists with `review_queue.json`, metadata, and `.apkg` export generation.

## Task Commits

Observed implementation commit(s):

1. **Task 1: Publish dedicated acceptance, duplicate, and review report sections** - `64d0913` (feat, pre-existing consolidated Phase 04 implementation)
2. **Task 2: Prove output compatibility for deck export and structured reports** - `64d0913` (feat, pre-existing consolidated Phase 04 implementation)

**Plan metadata:** pending docs commit from this execution.

## Files Created/Modified
- `ankideck_generator/core/deck_builder.py` - Publishes acceptance, duplicate, and review diagnostics while keeping existing counters.
- `ankideck_generator/tests/test_deck_builder.py` - Verifies duplicate diagnostics sections and configured output-file generation.
- `ankideck_generator/tests/test_deck_export.py` - Keeps `.apkg` export compatibility as the unchanged sentinel regression.

## Decisions Made
- Preserved existing top-level counters and output files so richer reporting does not break downstream consumers.
- Derived duplicate and acceptance rates from existing build counters and rejected-item diagnostics for reproducible reporting.

## Deviations from Plan

None - implementation already matched the plan and only required verification plus summary/state completion.

## Issues Encountered
- The implementation was already present in existing commit `64d0913`, so this execution could verify and document it but could not retroactively recreate per-task atomic commits.

## TDD Gate Compliance
- Warning: no separate `test(04-03)` or `feat(04-03)` gate commits were found; the verified implementation exists in consolidated commit `64d0913`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Phase 5 can consume explicit acceptance and duplicate metrics without changing the export contract.
- Existing output compatibility is preserved, so evaluation work can focus on metrics and guardrails instead of schema recovery.

## Self-Check: PASSED

---
*Phase: 04-duplicate-guard-and-review-workflow*
*Completed: 2026-04-22*
