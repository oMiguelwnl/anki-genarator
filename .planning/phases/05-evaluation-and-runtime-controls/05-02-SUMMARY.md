---
phase: 05-evaluation-and-runtime-controls
plan: 02
subsystem: runtime
tags: [pytest, pydantic, runtime-guardrails, latency, evaluation]
requires:
  - phase: 05-evaluation-and-runtime-controls
    provides: benchmark fixtures and typed evaluation aggregation from 05-01
provides:
  - stage-specific AI call limits wired through runtime config
  - lexical review latency and budget visibility in quality_report.json
  - per-accepted-card runtime latency metrics and optional log retention
affects: [quality_report.json, evaluation, runtime budgets, release gate]
tech-stack:
  added: []
  patterns: [shared AI stage budget accounting, accepted-card runtime metrics, explicit evaluation log retention]
key-files:
  created: [.planning/phases/05-evaluation-and-runtime-controls/05-02-SUMMARY.md]
  modified:
    - ankideck_generator/core/models.py
    - ankideck_generator/core/deck_builder.py
    - ankideck_generator/main.py
    - ankideck_generator/tests/test_deck_builder.py
    - ankideck_generator/tests/test_main.py
key-decisions:
  - "Per-stage AI limits merge runtime defaults with mode-profile overrides into one RunConfig map."
  - "Lexical review budget exhaustion rejects the card with explicit guardrail evidence instead of silently skipping review."
  - "Evaluation log cleanup stays opt-in via preserve_evaluation_logs so normal builds still clean generated artifacts."
patterns-established:
  - "Runtime guardrails are reported via event_counter-derived ai_budget_usage and runtime_guardrails sections in quality_report.json."
  - "Latency per accepted card is derived from aggregated stage timings divided by accepted-card count."
requirements-completed: [EVAL-02, EVAL-04]
duration: 14 min
completed: 2026-04-22
---

# Phase 05 Plan 02: Runtime guardrail reporting Summary

**Shared stage-budget enforcement with lexical-review timing, accepted-card latency metrics, and opt-in evaluation log retention.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-04-22T19:10:43Z
- **Completed:** 2026-04-22T19:24:53Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- Added failing regressions that locked runtime guardrails, lexical-review timing, accepted-card latency metrics, and config wiring before implementation.
- Extended `RunConfig`, `main.py`, and `DeckBuilder` to enforce per-stage AI budgets and publish machine-readable runtime metrics in `quality_report.json`.
- Preserved JSONL run logs for evaluation runs when explicitly requested while keeping normal cleanup behavior intact.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add failing guardrail and config-wiring regressions** - `22963d0` (test)
2. **Task 2: Extend RunConfig, DeckBuilder, and reports with shared stage guardrails** - `944be61` (feat)

**Plan metadata:** pending docs commit

## Files Created/Modified
- `ankideck_generator/core/models.py` - adds stage-budget and evaluation-log retention fields to `RunConfig`
- `ankideck_generator/core/deck_builder.py` - tracks stage AI usage, lexical-review timing, guardrail events, runtime metrics, and cleanup retention
- `ankideck_generator/main.py` - validates and maps runtime stage-budget config into `RunConfig`
- `ankideck_generator/tests/test_deck_builder.py` - covers lexical-review timing, runtime guardrails, accepted-card latency metrics, and log retention
- `ankideck_generator/tests/test_main.py` - verifies runtime stage-budget and log-retention config wiring

## Decisions Made
- Merged runtime-level and mode-profile stage budgets into one validated `ai_stage_call_limits` map so the pipeline keeps a single guardrail system.
- Treated blocked lexical review as a rejected card with explicit machine-readable guardrail evidence because acceptance without review would break Phase 03 correctness guarantees.
- Stored accepted-card latency as both total runtime and per-stage runtime per accepted card so downstream benchmark adapters can consume one stable report surface.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `quality_report.json` now exposes the runtime guardrail and latency surface that 05-03 can use for release-gate reporting.
- Full `pytest` suite is green, so Phase 05 can proceed to the release-gate plan.

## Self-Check: PASSED

- FOUND: `.planning/phases/05-evaluation-and-runtime-controls/05-02-SUMMARY.md`
- FOUND: `22963d0` and `944be61` in `git log --oneline --all --grep="05-02"`
