# 02-02 Summary

- Added `SentenceGenerationService` in `ankideck_generator/core/sentence_generation.py` to build prompts, validate structured batches, and reject focus-mismatch, wrong-language, and artificial candidates before lexical resolution.
- Added a narrow sentence-service seam in `ankideck_generator/core/deck_builder.py` so orchestration consumes normalized sentence candidates instead of raw JSON payloads.
- Added direct service tests in `ankideck_generator/tests/test_sentence_generation.py`.

## Verification

- `python -m pytest ankideck_generator/tests/test_sentence_generation.py -q`
