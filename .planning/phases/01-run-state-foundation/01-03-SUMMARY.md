# 01-03 Summary

- Updated `ankideck_generator/core/deck_builder.py` so deck export includes only cards whose lifecycle state is `accepted`.
- Restricted `review_queue.json` to rejected outcomes and added aggregate `accepted_with_corrections` reporting in `quality_report.json`.
- Added regression coverage in `ankideck_generator/tests/test_deck_builder.py` and `ankideck_generator/tests/test_deck_export.py` for rejected-only review artifacts and accepted-only export.

## Verification

- `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "quality_outputs or review_queue or accepted_only"`
- `python -m pytest ankideck_generator/tests/test_deck_export.py -q`
