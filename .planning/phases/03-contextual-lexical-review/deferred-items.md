# Deferred Items

## 2026-04-20

- Running `python -m pytest ankideck_generator/tests/test_deck_builder.py -q` exposed pre-existing failures outside plan 03-03 scope in other `DeckBuilder` definition and Russian-path tests. The current plan only changed post-correction revalidation and audio ordering, so those broader failures were not fixed here.
