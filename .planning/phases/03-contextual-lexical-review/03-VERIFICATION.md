---
phase: 03-contextual-lexical-review
verified: 2026-04-22T00:00:00Z
status: human_needed
score: 5/5 must-haves verified
overrides_applied: 0
human_verification:
  - test: "Run one real interactive correction flow"
    expected: "Editing a lexical field in interactive mode reruns validation, rejects invalid edits, and preserves before/after evidence in review artifacts"
    why_human: "The CLI prompt flow and user decision path are human-facing; unit tests cover the seam but not the real terminal interaction"
  - test: "Run one end-to-end build with audio enabled"
    expected: "Accepted corrected cards receive audio and rejected post-correction cards do not, while output/review_queue.json and export artifacts stay coherent"
    why_human: "Automated tests verify ordering with stubs, but not the full runtime behavior with actual configured providers and export side effects"
---

# Phase 3: Contextual Lexical Review Verification Report

**Phase Goal:** Build translation and definition around the accepted sentence context, add a review/correction stage, and force deterministic revalidation after any automated or human edit.
**Verified:** 2026-04-22T00:00:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
| --- | --- | --- | --- |
| 1 | Translation and definition are created or reviewed with the sentence, target word, and intended sense together. | ✓ VERIFIED | `LexicalReviewRequest` includes `focus_word`, `accepted_sentence`, `current_definition`, `current_translation`, `source_definition`, and `candidate_senses` in `core/models.py:120-173`; `DeckBuilder` builds that request from the accepted sentence and lexical candidates in `core/deck_builder.py:2871-2895`. |
| 2 | Review can accept, correct, reject, or route a card to human review with structured reasons. | ✓ VERIFIED | Verdicts are constrained to `accept|correct|reject` in `core/models.py:44,152-173`; malformed/non-typed payloads are rejected in `core/providers.py:1603-1627` and `tests/test_providers.py:144-170`; rejects are written as structured queue items with `reason_codes`, `before`, `after`, and `selection_reasons` in `core/deck_builder.py:1028-1055,3499-3502`, which is the codebase’s human-review route. |
| 3 | Audio remains a post-acceptance step and corrected cards are revalidated before they can pass. | ✓ VERIFIED | `_process_word()` revalidates immediately after textual generation and again after interactive edits before audio (`core/deck_builder.py:1368-1413`); `_attach_audio_to_card()` is called only after those gates; rejection on failed revalidation happens in `_revalidate_card_before_acceptance()` (`core/deck_builder.py:1532-1563`). |
| 4 | Fixable lexical issues are auto-corrected without blocking the run. | ✓ VERIFIED | `LexicalReviewService.review()` can convert misaligned lexical output into a `correct` verdict with minimal field patches (`core/lexical_review.py:15-87`); `DeckBuilder` applies corrected definition/translation in place without rewriting the accepted sentence (`core/deck_builder.py:2905-2919`); regression: `tests/test_deck_builder.py:58-170`. |
| 5 | Failed automated or manual corrections are rejected with evidence instead of bypassing acceptance gates. | ✓ VERIFIED | Failed post-correction validation sets `lifecycle_state="rejected"`, appends validation errors into `reason_codes`, and keeps `before/after` evidence (`core/deck_builder.py:1532-1563`); regressions cover AI-correction failure and interactive-edit failure in `tests/test_deck_builder.py:486-632`. |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| --- | --- | --- | --- |
| `ankideck_generator/core/models.py` | typed lexical review contracts and reason-code-aware payloads | ✓ VERIFIED | Contains `LexicalReviewRequest`, `LexicalReviewCorrection`, and `LexicalReviewResult` with typed verdicts and evidence fields (`120-173`); imported by provider/service/orchestration code. |
| `ankideck_generator/core/providers.py` | lexical review AI transport | ✓ VERIFIED | Exposes `lexical_review()` and `_lexical_review_ai()` (`681-711`, `1603-1627`) and validates AI JSON with `LexicalReviewResult.model_validate`. |
| `ankideck_generator/core/lexical_review.py` | sentence-anchored review service contract | ✓ VERIFIED | `LexicalReviewService.review()` resolves winning sense, patches minimal corrections, and rejects unresolved ambiguity (`6-109`); wired from `DeckBuilder`. |
| `ankideck_generator/core/deck_builder.py` | lexical review orchestration, queue routing, revalidation, audio-after-acceptance ordering | ✓ VERIFIED | `_process_word_textual()`, `_revalidate_card_before_acceptance()`, and `_process_word()` implement review, rejection, validator reruns, and delayed audio (`1368-1413`, `1532-1563`, `2871-3041`). |
| `ankideck_generator/tests/test_providers.py` | provider lexical review regressions | ✓ VERIFIED | Includes malformed lexical-review payload rejection regression (`144-170`); targeted pytest passed. |
| `ankideck_generator/tests/test_lexical_review.py` | lexical review service regressions | ✓ VERIFIED | Covers invalid verdict, correction payload, auto-pick, and unresolved ambiguity (`42-156`); targeted pytest passed. |
| `ankideck_generator/tests/test_deck_builder.py` | end-to-end lexical review/revalidation regressions | ✓ VERIFIED | Covers auto-correct, reject-to-queue, post-correction rejection, interactive revalidation, and audio ordering (`58-170`, `273-389`, `486-787`); targeted pytest passed. |

### Key Link Verification

| From | To | Via | Status | Details |
| --- | --- | --- | --- | --- |
| `core/providers.py` | `core/models.py` | typed Pydantic validation of review payloads | ✓ WIRED | `providers.py:1623-1627` validates AI JSON with `LexicalReviewResult.model_validate(...)`. |
| `core/lexical_review.py` | `core/providers.py` | service request/response around accepted sentence context | ✓ WIRED | `LexicalReviewService.review()` calls provider `lexical_review(request)` in `lexical_review.py:10-13`. |
| `core/deck_builder.py` | `core/lexical_review.py` | review call built from accepted sentence and lexical candidates | ✓ WIRED | `DeckBuilder` imports `LexicalReviewService` and calls it with accepted sentence, focus word, and sense candidates in `deck_builder.py:55,2871-2895`. |
| `core/deck_builder.py` | `output/review_queue.json` | rejected cards flow through existing queue artifact path | ✓ WIRED | Rejected `LogRecord`s become `stats.needs_review_items` in `_record_log()` (`1028-1055`) and are written to `run.review_queue_path` (`3499-3502`). |
| `core/deck_builder.py` | `core/validators.py` | `_validate_text_candidate()` after AI/manual edits | ✓ WIRED | `_process_word()` calls `_revalidate_card_before_acceptance()` before audio and again after interactive edits; that helper calls `_validate_text_candidate()`, which calls `validate_card()` (`1368-1413`, `1532-1563`, `3215-3237`). |
| `core/deck_builder.py` | `ProviderManager.audio()` | `_attach_audio_to_card()` only after corrected text clears revalidation | ✓ WIRED | `_attach_audio_to_card()` is invoked only after revalidation succeeds (`1413`), and `_attach_audio_to_card()` calls `providers.audio(...)` (`3169-3177`). |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| --- | --- | --- | --- | --- |
| `core/lexical_review.py` | `winning_sense`, `reason_codes`, corrections | Provider transport result plus request evidence | Yes — `review()` merges provider result with request data and explicit ambiguity logic (`10-87`) | ✓ FLOWING |
| `core/deck_builder.py` | lexical review request payload | Accepted sentence + selected definition/translation + candidate previews (`2871-2895`) | Yes — built from upstream sentence/definition selection, not hardcoded placeholders | ✓ FLOWING |
| `core/deck_builder.py` | `stats.needs_review_items` | Rejected `LogRecord` fields in `_record_log()` | Yes — queue items carry live `reason_codes`, `before`, `after`, and `selection_reasons` (`1028-1055`) | ✓ FLOWING |
| `core/deck_builder.py` | audio attachment decision | `_revalidate_card_before_acceptance()` gate before `_attach_audio_to_card()` | Yes — audio path is conditioned on validated accepted text state (`1368-1413`) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| --- | --- | --- | --- |
| Lexical review contracts reject invalid verdicts and support ambiguity handling | `python -m pytest ankideck_generator/tests/test_lexical_review.py -q` | `4 passed` | ✓ PASS |
| Provider lexical-review transport rejects malformed AI payloads | `python -m pytest ankideck_generator/tests/test_providers.py -q -k lexical_review` | `1 passed, 25 deselected` | ✓ PASS |
| DeckBuilder applies lexical review, queue routing, revalidation, and audio ordering seams | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "lexical_review or interactive_edit or audio_after_acceptance or revalidation or review_queue"` | `8 passed, 39 deselected` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| --- | --- | --- | --- | --- |
| `LEX-01` | `03-01`, `03-02` | Translation is generated or reviewed with the accepted sentence context, target word, and intended sense together. | ✓ SATISFIED | `LexicalReviewRequest` carries sentence/focus/sense data (`models.py:120-173`); `DeckBuilder` builds the request from accepted sentence + lexical candidates (`deck_builder.py:2871-2895`). |
| `LEX-02` | `03-01`, `03-02` | Definition or gloss is concise, learner-facing, and validated against the exact usage in the accepted sentence. | ✓ SATISFIED | Definition normalization/selection remains active in `deck_builder.py`, then lexical review compares the selected definition against the accepted sentence and can patch it minimally (`2879-2919`); regressions cover sentence-anchored correction (`tests/test_deck_builder.py:58-170`). |
| `LEX-03` | `03-01`, `03-02` | A review stage can accept, correct, reject, or route a card to human review with machine-readable reasons. | ✓ SATISFIED | Typed verdicts exist in `models.py`; unresolved items are rejected with structured reasons and written to `review_queue.json` for human follow-up (`deck_builder.py:1028-1055,3499-3502`). |
| `LEX-04` | `03-03` | Deterministic validators rerun after any AI or human correction before a card can be accepted. | ✓ SATISFIED | `_process_word()` reruns `_revalidate_card_before_acceptance()` after textual corrections and after interactive edits (`1368-1413`); helper calls `validate_card()` through `_validate_text_candidate()` (`1532-1563`, `3215-3237`). |
| `COMP-04` | `03-03` | Audio or TTS generation remains post-acceptance and continues to integrate with deck export. | ✓ SATISFIED | Audio attachment occurs only after revalidation (`1413`), and `_attach_audio_to_card()` fills `word_audio`/`sentence_audio` fields on `CardData` used by export (`3201-3213`, `models.py:68-89`). |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
| --- | --- | --- | --- | --- |
| — | — | No Phase 3 blocker stub/placeholder patterns found in the checked source or test files. | ℹ️ Info | Grep hits were normal default initializers and test fixtures, not hollow implementations. |

### Human Verification Required

### 1. Interactive correction flow

**Test:** Run the CLI in interactive mode, edit a definition or translation for a card, and also try an invalid edit.
**Expected:** Valid edits proceed; invalid edits are rejected after revalidation; `before`/`after` evidence and reason codes remain visible in follow-up artifacts.
**Why human:** The prompt/response loop is a real terminal user flow not fully exercised by the non-interactive automated checks.

### 2. End-to-end corrected-card audio flow

**Test:** Run a real build with audio enabled and capture one corrected accepted card plus one corrected rejected card.
**Expected:** Only the accepted corrected card gets audio/TTS; the rejected card appears in `output/review_queue.json` without media side effects; export artifacts remain coherent.
**Why human:** Unit tests verify control-flow ordering with stubs, but not the full configured provider/export path.

### Gaps Summary

No code-level gaps were found against the Phase 3 must-haves. The phase goal is implemented in the codebase: lexical review is sentence-anchored and typed, reject/correct behavior is wired into `DeckBuilder`, deterministic validation reruns after AI and manual edits, and audio is delayed until after text acceptance. Status is `human_needed` only because the interactive CLI correction flow and full provider-backed audio/export behavior still need manual confirmation.

### Verification Notes

- **Partial/alternative interpretation checked:** `LEX-03` does not introduce a runtime `human-review` lifecycle state in Phase 3; instead, unresolved cards are routed into `review_queue.json` with structured reasons. That matches the Phase 3 plans and satisfies the human-review intent through queue artifacts.
- **One test that is narrower than its headline:** `test_interactive_edit_valid_correction_generates_audio_after_acceptance` proves ordering (`interactive` before `audio`) with monkeypatched seams, but it does not by itself prove real provider/export integration.
- **One uncovered error path:** there is direct coverage for malformed lexical-review payloads, but no focused Phase 3 test for a provider transport exception/network failure during `ProviderManager.lexical_review()` followed by downstream queue handling.

---

_Verified: 2026-04-22T00:00:00Z_
_Verifier: the agent (gsd-verifier)_
