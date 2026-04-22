---
phase: 05
slug: evaluation-and-runtime-controls
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-22
---

# Phase 05 - Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | `pytest 9.0.2` |
| **Config file** | none found - rely on direct `pytest` invocation |
| **Quick run command** | `python -m pytest ankideck_generator/tests/test_evaluation.py -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~30-90 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest ankideck_generator/tests/test_evaluation.py -q`
- **After every plan wave:** Run `python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | EVAL-01 | T-05-01 | Benchmark fixture rows are validated before use and keep slice labels explicit | unit | `python -m pytest ankideck_generator/tests/test_evaluation.py -q -k benchmark_fixture` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | EVAL-02 | T-05-02 | Evaluation results include stable experiment identity and reproducible metric summaries | unit | `python -m pytest ankideck_generator/tests/test_evaluation.py -q -k fingerprint` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 1 | EVAL-04 | T-05-03 | AI budgets enforce bounded retries and expose exhaustion events in reports | unit | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k budget` | ✅ | ⬜ pending |
| 05-03-01 | 03 | 2 | QUAL-04 | T-05-04 | Release gate computes accepted-card rate from accepted-only pipeline outputs | unit / artifact | `python -m pytest ankideck_generator/tests/test_evaluation.py -q -k accepted_card_rate` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠ flaky*

---

## Wave 0 Requirements

- [ ] `ankideck_generator/tests/test_evaluation.py` - add benchmark fixture loading, slice aggregation, fingerprint, and threshold-gate coverage
- [ ] `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` - add representative benchmark cases segmented by language, ambiguity, and level
- [ ] `ankideck_generator/tests/test_deck_builder.py` - add budget and lexical-review timing/report regressions
- [ ] Any new evaluation artifact schema test if Phase 05 adds a file beyond `output/quality_report.json`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live-provider benchmark run in a credentialed environment | QUAL-04 / EVAL-02 | Local shell currently lacks live AI credentials, so true end-to-end benchmark runs cannot be exercised offline | Run the benchmark path with valid provider credentials, confirm experiment identity is recorded, and compare acceptance and runtime metrics against the release thresholds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all missing references
- [ ] No watch-mode flags
- [x] Feedback latency < 90s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
