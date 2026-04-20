# 02-03 Summary

- Re-routed sentence generation in `ankideck_generator/core/deck_builder.py` to AI-first ordering with bounded web salvage only after malformed or low-yield AI outcomes.
- Updated compatibility fingerprint inputs to include structured sentence prompt/schema/policy versions.
- Added routing regressions in `ankideck_generator/tests/test_deck_builder.py` for valid AI batches, malformed AI fallback, and low-yield fallback.

## Verification

- `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "sentence_ai or sentence_rewrite or tatoeba or structured"`
