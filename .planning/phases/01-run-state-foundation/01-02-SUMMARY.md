# 01-02 Summary

- Added compatibility-aware resume loading in `ankideck_generator/core/deck_builder.py`, including progress quarantine for corrupt or incompatible artifacts.
- Restored saved RNG state when progress fingerprints match and resumed from the saved level/index with preserved sort-index numbering.
- Centralized final accepted vs rejected handling so checkpoint saves happen only after final decisions.
- Added regression coverage in `ankideck_generator/tests/test_deck_builder.py` for compatible resume, incompatible progress quarantine, and final-decision checkpoint timing.

## Verification

- `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "resume or progress or checkpoint or quarantine"`
