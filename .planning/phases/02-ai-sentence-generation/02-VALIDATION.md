---
phase: 02
slug: ai-sentence-generation
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-20
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest ankideck_generator/tests/test_providers.py -q -k "structured_sentence or sentence_ai_candidates"` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest ankideck_generator/tests/test_providers.py -q -k "structured_sentence or sentence_ai_candidates"` or the task-specific command in PLAN.md.
- **After every plan wave:** Run `python -m pytest -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | AIG-01, AIG-02 | T-02-01 / T-02-02 | Reject malformed or over/under-sized AI payloads before they enter orchestration | unit | `python -m pytest ankideck_generator/tests/test_providers.py -q -k "structured_sentence or sentence_ai_candidates"` | ✅ | ⬜ pending |
| 02-02-01 | 02 | 2 | AIG-01, AIG-02 | T-02-03 / T-02-04 | Service enforces exact target-form and wrong-language rejection before lexical flow | unit | `python -m pytest ankideck_generator/tests/test_sentence_generation.py -q` | ✅ | ⬜ pending |
| 02-03-01 | 03 | 3 | AIG-03, AIG-04 | T-02-05 / T-02-06 | `DeckBuilder` routes AI-first and only enters web fallback on bounded failure/low-yield cases | unit/integration | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "sentence_ai or sentence_rewrite or tatoeba or structured"` | ✅ | ⬜ pending |
| 02-04-01 | 04 | 4 | AIG-01, AIG-02, AIG-03, AIG-04 | T-02-01 through T-02-06 | Fixture regressions preserve malformed-payload and fallback behavior across future prompt/schema changes | fixture/integration | `python -m pytest ankideck_generator/tests/test_providers.py ankideck_generator/tests/test_sentence_generation.py ankideck_generator/tests/test_deck_builder.py -q -k "structured or sentence"` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- Existing infrastructure covers all phase requirements.

---

## Manual-Only Verifications

- All phase behaviors have automated verification.

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
