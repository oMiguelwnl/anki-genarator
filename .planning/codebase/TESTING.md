# Testing Patterns

**Analysis Date:** 2026-04-15

## Test Framework

**Runner:**
- `pytest` `>=7.4.0` from `requirements.txt`
- Config: `pytest.ini`

**Assertion Library:**
- Built-in `pytest` assertion rewriting with plain `assert`, e.g. `ankideck_generator/tests/test_validators.py` and `ankideck_generator/tests/test_deck_builder.py`

**Run Commands:**
```bash
python -m pytest -q                                  # Run all tests
python -m pytest ankideck_generator/tests/test_main.py -q  # Run one file
python -m pytest ankideck_generator/tests/test_deck_export.py::test_deck_export -q  # Run one test
```

## Test File Organization

**Location:**
- Tests live in a package-local test directory: `ankideck_generator/tests/`
- Tests are separate from implementation modules rather than co-located next to each source file.

**Naming:**
- Use `test_*.py` filenames, e.g. `ankideck_generator/tests/test_main.py`, `ankideck_generator/tests/test_providers.py`, and `ankideck_generator/tests/test_deck_builder.py`.
- Use `test_<behavior>()` function names that describe a single rule, fallback, or regression, e.g. `test_process_word_skips_sentence_ai_when_tatoeba_is_strong_enough` in `ankideck_generator/tests/test_deck_builder.py`.

**Structure:**
```
ankideck_generator/tests/
├── test_cache_manager.py
├── test_cache_refresh.py
├── test_deck_builder.py
├── test_deck_export.py
├── test_definition_tools.py
├── test_language_tools.py
├── test_main.py
├── test_providers.py
└── test_validators.py
```

## Test Structure

**Suite Organization:**
```python
def test_process_word_retries_sentence_web_before_ai(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class FakeProviders:
        sentence_ai_calls = 0
        sentence_web_calls = 0
        ...

    card, _log = builder._process_word(...)

    assert card is not None
    assert providers.sentence_web_calls == 1
    assert providers.sentence_ai_calls == 2
```

**Patterns:**
- Arrange with inline helpers and fake classes inside each test, as in `ankideck_generator/tests/test_deck_builder.py` and `ankideck_generator/tests/test_main.py`.
- Use pytest built-ins instead of shared fixture modules: `monkeypatch`, `tmp_path`, and `capsys` appear throughout `ankideck_generator/tests/test_providers.py`, `ankideck_generator/tests/test_deck_builder.py`, and `ankideck_generator/tests/test_deck_export.py`.
- No repo-level `conftest.py` exists for the project test suite; setup is intentionally local to each file.

## Mocking

**Framework:** `pytest` `monkeypatch` + inline fake classes/functions

**Patterns:**
```python
monkeypatch.setattr(provider._session, "get", fake_get)
monkeypatch.setattr(provider, "_sentence_ai", lambda *args, **kwargs: calls.append("ai") or None)
monkeypatch.setattr(main_module, "DeckBuilder", FakeBuilder)
```

```python
class FakeProviders:
    def translation_web(self, text, src, dest):
        if text.startswith("adjective:"):
            return Result("adjective: in good condition or quality", provider_name="googletrans")
        return Result("I feel good today.", provider_name="googletrans")
```

**What to Mock:**
- External HTTP calls and sessions in `ankideck_generator/tests/test_providers.py`
- Provider fallbacks and AI/web selection branches in `ankideck_generator/tests/test_deck_builder.py`
- CLI wiring in `ankideck_generator/tests/test_main.py`
- Third-party constructors such as `Translator`, `gTTS`, and `pyttsx3` in `ankideck_generator/tests/test_providers.py`
- Module-level helpers when testing orchestration boundaries, e.g. `top_n_list` in `ankideck_generator/tests/test_deck_builder.py`

**What NOT to Mock:**
- Pure transformation/validation helpers. `ankideck_generator/tests/test_definition_tools.py`, `ankideck_generator/tests/test_language_tools.py`, and much of `ankideck_generator/tests/test_validators.py` call real functions directly.
- Export packaging logic in `ankideck_generator/tests/test_deck_export.py`, which writes a real `.apkg`, opens it with `zipfile`, and inspects the extracted SQLite model.

## Fixtures and Factories

**Test Data:**
```python
def _run_config(tmp_path: Path, language: str = "es") -> RunConfig:
    return RunConfig(
        language=language,
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        ...
    )
```

**Location:**
- Per-file helpers live at the top of the relevant test module, e.g. `_run_config()` in `ankideck_generator/tests/test_deck_builder.py` and `_read_model_from_apkg()` in `ankideck_generator/tests/test_deck_export.py`.
- There is no shared fixtures package and no central factory module.

## Coverage

**Requirements:** No enforced coverage target

**View Coverage:**
```bash
python -m pytest --collect-only -q
```

- `python -m pytest --collect-only -q` currently collects **102 tests** across **9 files** under `ankideck_generator/tests/`.
- No `coverage`, `pytest-cov`, or threshold config is detected in `pytest.ini`, `pyproject.toml`, or other repo-root config files.
- Current coverage signals are breadth-of-behavior, not percentages: there is strong regression coverage around `ankideck_generator/core/deck_builder.py`, `ankideck_generator/core/providers.py`, `ankideck_generator/core/validators.py`, and export behavior in `ankideck_generator/tests/test_deck_export.py`.

## Test Types

**Unit Tests:**
- Most tests are unit-style and target a single function or code path with local fakes, e.g. `ankideck_generator/tests/test_definition_tools.py`, `ankideck_generator/tests/test_language_tools.py`, and `ankideck_generator/tests/test_validators.py`.

**Integration Tests:**
- Narrow file/integration tests exist for deck export and generated artifacts in `ankideck_generator/tests/test_deck_export.py`.
- `ankideck_generator/tests/test_cache_manager.py` and `ankideck_generator/tests/test_cache_refresh.py` exercise real filesystem/JSON mutation behavior rather than full mocks.

**E2E Tests:**
- Not used.

## Common Patterns

**Async Testing:**
```python
start = time.time()
try:
    provider._audio_pyttsx3("hola", tmp_path, "sample")
except Exception as exc:
    assert "timed out" in str(exc)
else:
    raise AssertionError("pyttsx3 timeout should abort blocked synthesis")
assert time.time() - start < 1.2
```

- There are no `async def` tests.
- Concurrency/timeouts are tested synchronously through elapsed-time assertions, thread-based code paths, and call counters, especially in `ankideck_generator/tests/test_providers.py` and `ankideck_generator/tests/test_deck_builder.py`.

**Error Testing:**
```python
provider._wrap("responsivevoice", timeout_fn)
provider._wrap("responsivevoice", timeout_fn)
provider._wrap("responsivevoice", timeout_fn)

result = provider._wrap("responsivevoice", timeout_fn)
assert result.error == "provider_disabled"
assert calls["count"] == 3
```

- Error-path tests usually assert on returned error codes or blocked fallback calls rather than exception types, matching `ankideck_generator/tests/test_providers.py` and `ankideck_generator/tests/test_deck_builder.py`.
- Use `raise AssertionError(...)` inside fake providers to prove a fallback path must not run, e.g. in `ankideck_generator/tests/test_providers.py` and `ankideck_generator/tests/test_deck_builder.py`.

## Current Coverage Signals by Area

- `ankideck_generator/tests/test_deck_builder.py` is the deepest suite (35 tests) and is the main reference when changing `ankideck_generator/core/deck_builder.py`.
- `ankideck_generator/tests/test_providers.py` covers provider fallback order, timeout behavior, and Tatoeba query construction for `ankideck_generator/core/providers.py`.
- `ankideck_generator/tests/test_validators.py`, `ankideck_generator/tests/test_definition_tools.py`, and `ankideck_generator/tests/test_language_tools.py` cover the repo's rule-heavy text normalization and validation logic.
- `ankideck_generator/tests/test_main.py` covers CLI argument parsing and `RunConfig` wiring from `ankideck_generator/main.py`.
- `ankideck_generator/tests/test_deck_export.py` covers output schema and cleanup behavior for `DeckBuilder.export_deck()`.

---

*Testing analysis: 2026-04-15*
