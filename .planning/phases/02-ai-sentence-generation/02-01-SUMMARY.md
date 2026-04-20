# 02-01 Summary

- Added `StructuredSentenceCandidate` and `StructuredSentenceBatch` contracts in `ankideck_generator/core/models.py` with exact-three candidate enforcement and prompt/schema metadata.
- Added validated structured AI transport in `ankideck_generator/core/providers.py`, including fenced/raw JSON parsing and Pydantic validation.
- Added fixture-backed provider regressions in `ankideck_generator/tests/test_providers.py`.

## Verification

- `python -m pytest ankideck_generator/tests/test_providers.py -q -k "structured_sentence or sentence_ai_candidates"`
