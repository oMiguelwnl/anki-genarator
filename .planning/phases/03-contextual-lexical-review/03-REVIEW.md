---
phase: 03-contextual-lexical-review
reviewed: 2026-04-22T09:18:31Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - ankideck_generator/core/models.py
  - ankideck_generator/core/providers.py
  - ankideck_generator/core/lexical_review.py
  - ankideck_generator/core/deck_builder.py
  - ankideck_generator/tests/test_providers.py
  - ankideck_generator/tests/test_lexical_review.py
  - ankideck_generator/tests/test_deck_builder.py
  - .planning/phases/03-contextual-lexical-review/03-01-SUMMARY.md
  - .planning/phases/03-contextual-lexical-review/03-02-SUMMARY.md
  - .planning/phases/03-contextual-lexical-review/03-03-SUMMARY.md
findings:
  critical: 0
  warning: 2
  info: 1
  total: 3
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-04-22T09:18:31Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the Phase 03 lexical-review implementation across the provider contract, service logic, deck-builder integration, and new tests. The main regression risk is that the deck builder pre-seeds a winning sense, which the service currently trusts ahead of the provider result; that can suppress intended ambiguity rejection. I also found a contract-validation gap around schema versioning and a smaller error-classification issue in the provider transport.

## Warnings

### WR-01: Pre-seeded winning sense can bypass ambiguity rejection

**File:** `ankideck_generator/core/deck_builder.py:2879-2890`, `ankideck_generator/core/lexical_review.py:94-99`
**Issue:** `DeckBuilder` always sends `winning_sense=source_definition or None`, and `LexicalReviewService._resolve_winning_sense()` prefers `request.winning_sense` before any fallback matching. That means a non-empty source definition can force a winning sense even when the provider returned `reject`, returned no review, or could not disambiguate the candidate senses. This undermines the new queue-first ambiguity flow described in the phase summaries and can turn ambiguous cards into `accept`/`correct` outcomes instead of rejected review items.
**Fix:** Stop pre-populating `request.winning_sense` from `source_definition`; pass the source definition only as evidence in `source_definition`/`candidate_senses`, then let the service pick a winner only from the provider result, a single-candidate case, or an exact `source_definition` match. Add a regression test where the provider returns `reject` or transport failure while `source_definition` is present, and assert the card still lands in the rejected review queue.

### WR-02: Lexical-review contract versions are not actually validated

**File:** `ankideck_generator/core/models.py:121-122`, `ankideck_generator/core/models.py:153-154`
**Issue:** `prompt_version` and `schema_version` are declared as plain `str` fields with defaults, so `LexicalReviewRequest`/`LexicalReviewResult` will accept unexpected version strings. That weakens the typed transport guarantee added in this phase: an old or incompatible AI payload can still validate and flow into review logic even though the schema version changed.
**Fix:** Make these fields strict version literals, e.g. `Literal[LEXICAL_REVIEW_PROMPT_VERSION]` and `Literal[LEXICAL_REVIEW_SCHEMA_VERSION]`, or add explicit validators that reject mismatches. Add tests that a payload with the wrong prompt/schema version fails validation in `test_lexical_review.py` and/or `test_providers.py`.

## Info

### IN-01: Malformed lexical-review JSON is reported with the wrong error code

**File:** `ankideck_generator/core/providers.py:1465-1469`, `ankideck_generator/core/providers.py:1623-1627`
**Issue:** `_ai_request_json()` always raises `structured_sentence_malformed_json` when JSON extraction fails. `lexical_review()` reuses that helper, so a malformed lexical-review response is misclassified as a sentence-generation error. That makes logs and any downstream triage based on error codes harder to trust.
**Fix:** Parameterize `_ai_request_json()` with a caller-specific error prefix or wrap the exception in `_lexical_review_ai()` so lexical review emits `lexical_review_malformed_json`. Add a provider test for malformed lexical-review JSON, not just schema-validation failures.

---

_Reviewed: 2026-04-22T09:18:31Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
