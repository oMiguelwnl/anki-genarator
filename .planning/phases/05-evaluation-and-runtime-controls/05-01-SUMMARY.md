---
phase: 05-evaluation-and-runtime-controls
plan: 01
subsystem: testing
tags: [pytest, pydantic, benchmark, evaluation]
requires:
  - phase: 04-duplicate-guard-and-review-workflow
    provides: accepted-card quality outputs and duplicate diagnostics used as the evaluation metric shape
provides:
  - typed repo-backed benchmark fixture loading
  - deterministic experiment fingerprints for evaluation runs
  - reproducible slice-aware benchmark bundle assembly
affects: [05-02, 05-03, evaluation, release-gate]
tech-stack:
  added: []
  patterns: [pydantic fixture validation, canonical-json fingerprinting, deterministic slice aggregation]
key-files:
  created:
    [ankideck_generator/core/evaluation.py, ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json, ankideck_generator/tests/test_evaluation.py]
  modified: []
key-decisions:
  - "Kept benchmark evaluation in a standalone core/evaluation.py module so fixture loading and aggregation stay pure and credential-free."
  - "Derived experiment identity from canonical JSON over experiment metadata plus validated benchmark cases to make repeated runs byte-stable."
  - "Summarized benchmark coverage by language, ambiguity, difficulty, and quality dimension counts so downstream plans can reuse one deterministic bundle contract."
patterns-established:
  - "Benchmark fixtures live in repo-owned JSON and are validated row-by-row with Pydantic before any metric math runs."
  - "Evaluation bundles are assembled from canonicalized inputs so fingerprint and summary output are order-insensitive."
requirements-completed: [EVAL-01, EVAL-02]
duration: 3 min
completed: 2026-04-22
---

# Phase 05 Plan 01: Define repo-stored benchmark fixtures and typed evaluation aggregation Summary

**Repo-backed benchmark fixtures with deterministic experiment fingerprints and slice-aware evaluation bundles**

## Performance

- **Duration:** 3 min
- **Started:** 2026-04-22T18:59:25Z
- **Completed:** 2026-04-22T19:03:21Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- Added a repo-owned benchmark corpus covering required language, ambiguity, and difficulty slices.
- Added failing-then-passing pytest coverage for fixture validation, deterministic fingerprints, and reproducible bundle assembly.
- Implemented a pure evaluation helper module that validates benchmark rows before computing summaries.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add benchmark fixture rows and failing evaluation regressions** - `cc1e6d5` (test)
2. **Task 2: Implement typed benchmark loading and deterministic metric aggregation** - `c283d3d` (feat)

## Files Created/Modified
- `ankideck_generator/core/evaluation.py` - Typed benchmark models plus deterministic fingerprint, summary, and bundle helpers.
- `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` - Versioned benchmark rows spanning required evaluation slices.
- `ankideck_generator/tests/test_evaluation.py` - Regression coverage for fixture validation and reproducible aggregation behavior.

## Decisions Made
- Kept evaluation helpers independent of live providers so benchmark math stays pure and offline-testable.
- Used canonical JSON hashing for experiment identity so list order and dict ordering do not change benchmark fingerprints.
- Mirrored `quality_report.json` metric names in the benchmark helpers so downstream runner work can reuse existing report shapes.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Ready for 05-02 to thread runtime budgets and stage metrics into the same evaluation/reporting story.
- No blockers from this plan.

## Self-Check: PASSED

- Verified summary and evaluation files exist on disk.
- Verified task commits `cc1e6d5` and `c283d3d` exist in git history.
