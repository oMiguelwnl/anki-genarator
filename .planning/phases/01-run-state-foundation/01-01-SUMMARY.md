# 01-01 Summary

- Added `CardLifecycleState`, `CompatibilityFingerprint`, and structured audit fields in `ankideck_generator/core/models.py`.
- Added deterministic fingerprint and quarantine helpers in `ankideck_generator/core/run_state.py`.
- Added direct regression coverage in `ankideck_generator/tests/test_run_state.py` for lifecycle validation, audit payloads, fingerprint stability, fingerprint invalidation, and quarantine naming.

## Verification

- `python -m pytest ankideck_generator/tests/test_run_state.py -q`
