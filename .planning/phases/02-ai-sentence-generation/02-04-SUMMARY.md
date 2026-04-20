# 02-04 Summary

- Added canonical structured sentence fixtures under `ankideck_generator/tests/fixtures/ai_sentence_candidates/` for valid and malformed AI batches.
- Switched provider and deck-builder regressions to use stable structured fixtures rather than inline-only payloads.
- Verified the full repository after the AI-first sentence-generation changes.

## Verification

- `python -m pytest -q`
