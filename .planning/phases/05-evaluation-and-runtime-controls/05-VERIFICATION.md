---
phase: 05-evaluation-and-runtime-controls
verified: 2026-04-23T00:14:30Z
status: passed
score: 6/6 must-haves verified
overrides_applied: 0
---

# Phase 05: Evaluation and Runtime Controls Verification Report

**Phase Goal:** Add reproducible evaluation, acceptance thresholds, and operational guardrails so the milestone can prove quality gains above the current baseline without runaway cost or latency.
**Verified:** 2026-04-23T00:14:30Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Repo benchmark cases load reproducibly and explicitly cover language, ambiguity, and difficulty slices. | ✓ VERIFIED | `ankideck_generator/core/evaluation.py:158-163` loads and validates repo JSON into `BenchmarkCase`; `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json:1-46` covers `es`/`fr`, `low`/`medium`/`high`, and `beginner`/`intermediate`/`advanced`; `test_evaluation.py:24-49` enforces coverage and malformed-row rejection. |
| 2 | Prompt/model/validator changes can be compared with reproducible metric bundles and stable experiment identity. | ✓ VERIFIED | `evaluation.py:101-129,210-237` canonicalizes inputs, hashes experiment + benchmark cases, and builds deterministic bundles; `test_evaluation.py:52-126` verifies stable fingerprints, slice summaries, and reproducible bundle assembly. |
| 3 | Runtime reporting exposes per-stage latency, AI-budget usage, and latency per accepted card from accepted-only outputs. | ✓ VERIFIED | `deck_builder.py:3642-3738` computes `stage_latency_ms`, `ai_budget_usage`, `runtime_guardrails`, and `latency_per_accepted_card_ms`; `test_deck_builder.py:3731-3795` asserts those fields in `quality_report.json`. |
| 4 | Configured guardrails stop runaway AI calls, including lexical review, and evaluation runs can preserve log evidence. | ✓ VERIFIED | `deck_builder.py:1671-1683` enforces global + stage budgets, `2999-3027` rejects lexical review when its stage budget is exhausted, and `3843-3845` preserves logs when `preserve_evaluation_logs` is true; `main.py:19-41,157-164,239-291` wires config into `RunConfig`; `test_main.py:242-316` and `test_deck_builder.py:3639-3817` verify the wiring and behavior. |
| 5 | A runnable evaluation path loads benchmark fixtures and accepted-only runtime output, then writes a reproducible benchmark bundle. | ✓ VERIFIED | `evaluation.py:299-337` implements `run_release_benchmark()` to load benchmark cases, thresholds, and `quality_report.json`, then write the bundle with `atomic_write_json`; `test_evaluation.py:208-230` executes that path and verifies the bundle contents. |
| 6 | The release verdict is machine-readable and enforces accepted-card-rate strictly greater than 0.60 while carrying fingerprint, slice metrics, runtime latency, and threshold evidence. | ✓ VERIFIED | `release_thresholds.json:4-28` encodes `accepted_card_rate > 0.6` and required runtime fields; `evaluation.py:240-296` computes pass/fail verdicts with explicit failed checks and missing-field rejection; `test_evaluation.py:196-319` verifies strict fail at `0.60`, pass at `0.61`, latency propagation, fingerprint propagation, and malformed payload rejection. |

**Score:** 6/6 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `ankideck_generator/core/evaluation.py` | Typed benchmark loader, reproducible bundle builder, release gate runner/verdict | ✓ VERIFIED | 337-line substantive module with Pydantic adapters, canonical hashing, bundle writing, threshold evaluation, and runnable `run_release_benchmark()`. |
| `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` | Repo benchmark corpus segmented by required slices | ✓ VERIFIED | 4 fixture rows spanning both languages and all ambiguity/difficulty slices used by loader/tests. |
| `ankideck_generator/tests/fixtures/evaluation/release_thresholds.json` | Versioned release threshold fixture including `> 0.60` gate | ✓ VERIFIED | Encodes strict acceptance-rate comparator plus latency guardrail and required report fields. |
| `ankideck_generator/core/models.py` | `RunConfig` fields for stage budgets/log retention and `LogRecord` stage/event surfaces | ✓ VERIFIED | `RunConfig.ai_stage_call_limits` and `RunConfig.preserve_evaluation_logs` added at `175-219`; `LogRecord.stage_timings`/`event_counts` present at `253-275`. |
| `ankideck_generator/core/deck_builder.py` | Runtime metric emission, stage guardrails, lexical-review budget enforcement, cleanup retention | ✓ VERIFIED | Budget gate, lexical-review rejection path, report fields, and cleanup retention are all implemented and tested. |
| `ankideck_generator/main.py` | CLI/config wiring for guardrail settings | ✓ VERIFIED | Parses and validates stage-budget mappings, preserves defaults, and passes values into `RunConfig`. |
| `ankideck_generator/tests/test_evaluation.py` | Regression coverage for evaluation path and release gate | ✓ VERIFIED | 15 evaluation tests passed. |
| `ankideck_generator/tests/test_deck_builder.py` | Regression coverage for runtime metrics and guardrails | ✓ VERIFIED | Guardrail/latency/log-retention tests present and passing. |
| `ankideck_generator/tests/test_main.py` | Regression coverage for runtime config wiring | ✓ VERIFIED | Config-to-`RunConfig` guardrail wiring test present and passing. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `main.py` | `RunConfig` | RunConfig construction | ✓ WIRED | `main.py:157-164,239-291` parses `preserve_evaluation_logs` and merged `ai_stage_call_limits` and passes both into `RunConfig`. |
| `deck_builder.py` | `quality_report.json` | `_write_quality_outputs` | ✓ WIRED | `deck_builder.py:3683-3771` serializes `accepted_card_rate`, `stage_latency_ms`, `ai_budget_usage`, `runtime_guardrails`, and `latency_per_accepted_card_ms` to `run.quality_report_path`. |
| `deck_builder.py` | lexical review call path | shared allow-AI gate + stage timing | ✓ WIRED | `deck_builder.py:2999-3037` applies stage budget to lexical review and records `lexical_review_ms`; `test_deck_builder.py:3639-3728` verifies timing capture. |
| `evaluation.py` | `quality_report.json` | typed accepted-only report adapter | ✓ WIRED | `evaluation.py:170-172,309-323` validates quality-report payloads and lifts runtime metrics into the bundle. |
| benchmark fixture loader | benchmark bundle writer | runner entrypoint | ✓ WIRED | `evaluation.py:307-330` loads fixture rows and writes a bundle in one path. |
| quality-report metrics | release readiness verdict | accepted-only benchmark aggregation | ✓ WIRED | `evaluation.py:240-296` evaluates threshold checks from bundle/report surfaces, including strict acceptance-rate gating. |
| experiment fingerprint | release report | report serialization | ✓ WIRED | `evaluation.py:231-235,289,331-336` carries fingerprint from bundle into returned release report; `test_evaluation.py:252-272` verifies propagation. |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `ankideck_generator/core/deck_builder.py` | `stage_latency_ms`, `ai_budget_usage`, `latency_per_accepted_card_ms` | Aggregated `stats.stage_counter`, `stats.event_counter`, and accepted-card counts in `_write_quality_outputs()` | Yes — derived from recorded run logs and accepted-card counters, not static placeholders | ✓ FLOWING |
| `ankideck_generator/core/evaluation.py` | `metrics`, `runtime_metrics`, `release_report` | Validated `quality_report.json`, typed thresholds, and benchmark fixtures inside `run_release_benchmark()` | Yes — `load_quality_report()` and `load_release_thresholds()` reject malformed inputs before bundle/verdict generation | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Evaluation path regressions pass | `python -m pytest ankideck_generator/tests/test_evaluation.py -q` | `15 passed in 0.16s` | ✓ PASS |
| CLI/config guardrail wiring passes | `python -m pytest ankideck_generator/tests/test_main.py -q` | `10 passed in 0.58s` | ✓ PASS |
| Deck-builder guardrail metrics behave as expected | `python -m pytest ankideck_generator/tests/test_deck_builder.py -k "runtime_guardrails or lexical_review_stage_timing or preserve_evaluation_logs" -q` | `2 passed, 52 deselected in 0.76s` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `QUAL-04` | `05-03-PLAN.md` | Accepted-card rate improves above 60% on the benchmark/release dataset before milestone completion. | ✓ SATISFIED | `release_thresholds.json:4-10` encodes `accepted_card_rate > 0.6`; `evaluation.py:269-283` applies the comparator; `test_evaluation.py:233-272` proves fail at `0.60` and pass at `0.61`. |
| `EVAL-01` | `05-01-PLAN.md` | Representative benchmark/gold set segmented by language, ambiguity, and frequency or difficulty slice. | ✓ SATISFIED | `benchmark_cases.json:1-46` plus `test_evaluation.py:24-49` give repo-owned coverage across language, ambiguity, and difficulty slices. |
| `EVAL-02` | `05-01-PLAN.md`, `05-02-PLAN.md`, `05-03-PLAN.md` | Prompt/model/validator changes can be evaluated against reproducible quality/runtime metrics including acceptance rate and cost/latency per accepted card. | ✓ SATISFIED | Deterministic fingerprints/bundles at `evaluation.py:101-129,210-237`; runtime metrics at `deck_builder.py:3644-3738`; runnable benchmark-to-verdict path at `evaluation.py:299-337`. |
| `EVAL-04` | `05-02-PLAN.md` | Runtime enforces configurable AI call budgets/guardrails so builds remain operationally viable. | ✓ SATISFIED | Budget enforcement in `deck_builder.py:1671-1683` and lexical-review rejection path in `2999-3027`; config wiring in `main.py:19-41,157-164,239-291`; regression coverage in `test_main.py:242-316` and `test_deck_builder.py:3731-3817`. |

No orphaned Phase 5 requirements were found in `REQUIREMENTS.md`; the traceability table maps `QUAL-04`, `EVAL-01`, `EVAL-02`, and `EVAL-04` to Phase 5. Note: `REQUIREMENTS.md` still shows `QUAL-04` as pending in the checkbox list, but implementation and tests now satisfy it.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | No TODO/FIXME/placeholder or stub patterns detected in Phase 05 implementation files. | — | No blocker anti-patterns found. |
| `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` | 1 | Minimal benchmark corpus (4 rows) | ℹ️ Info | Satisfies slice-contract verification, but benchmark representativeness is intentionally thin and may limit future tuning confidence. |
| `ankideck_generator/tests/test_evaluation.py` | 208 | Bundle-write test checks one write path, not repeated byte-for-byte disk output | ℹ️ Info | Reproducibility is still covered in-memory (`95-126`), but on-disk repeatability is indirectly rather than directly tested. |

### Gaps Summary

No blocking implementation gaps found. The codebase now contains a working evaluation module, repo-stored benchmark and threshold fixtures, accepted-only runtime metric reporting, stage-budget guardrails including lexical review, optional evaluation-log retention, and a machine-readable release verdict that enforces `accepted_card_rate > 0.60`.

---

_Verified: 2026-04-23T00:14:30Z_
_Verifier: the agent (gsd-verifier)_
