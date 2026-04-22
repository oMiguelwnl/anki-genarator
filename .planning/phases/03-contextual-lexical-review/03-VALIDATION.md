---
phase: 03
slug: contextual-lexical-review
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-20
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest ankideck_generator/tests/test_lexical_review.py -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest ankideck_generator/tests/test_lexical_review.py -q` or the task-specific command in the map below
- **After every plan wave:** Run `python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | LEX-03 | T-03-01 | only typed `accept/correct/reject` verdicts are valid; no runtime `human_review` state leaks in | unit | `python -m pytest ankideck_generator/tests/test_lexical_review.py -q -k "contract or verdict"` | ✅ | ⬜ pending |
| 03-01-02 | 01 | 1 | LEX-01, LEX-02 | T-03-02 | malformed AI review output is rejected before orchestration consumes it | unit | `python -m pytest ankideck_generator/tests/test_providers.py -q -k "lexical_review or contextual_definition or translation"` | ✅ | ⬜ pending |
| 03-02-01 | 02 | 2 | LEX-01, LEX-02 | T-03-03 | sentence-anchored review may patch lexical fields but must not rewrite the accepted sentence or focus | unit | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "lexical_review and sentence_anchor"` | ✅ | ⬜ pending |
| 03-02-02 | 02 | 2 | LEX-03 | T-03-04 | low-confidence lexical cases reject into queue/audit artifacts with before/after evidence and reason codes | unit | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "review_queue or lexical_review_reject"` | ✅ | ⬜ pending |
| 03-03-01 | 03 | 3 | LEX-04 | T-03-05 | AI/manual corrections rerun deterministic validators before acceptance | unit | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "revalidation or interactive_edit"` | ✅ | ⬜ pending |
| 03-03-02 | 03 | 3 | COMP-04 | T-03-06 | corrected cards reach audio only after successful revalidation and acceptance gating | unit | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "audio and lexical_review"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
