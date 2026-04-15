# Coding Conventions

**Analysis Date:** 2026-04-15

## Naming Patterns

**Files:**
- Use lowercase snake_case module names for package code and tests, e.g. `ankideck_generator/core/deck_builder.py`, `ankideck_generator/utils/language_tools.py`, and `ankideck_generator/tests/test_providers.py`.

**Functions:**
- Use snake_case for functions and methods, including private helpers with a leading underscore, e.g. `ankideck_generator/main.py::build_arg_parser`, `ankideck_generator/core/deck_builder.py::_build_level_serial`, and `ankideck_generator/utils/file_utils.py::atomic_write_json`.

**Variables:**
- Use snake_case for locals, parameters, and config values, e.g. `provider_timeout_overrides` in `ankideck_generator/main.py`, `processed_focus` in `ankideck_generator/core/deck_builder.py`, and `path_obj` in `ankideck_generator/utils/config.py`.

**Types:**
- Use PascalCase for classes, dataclasses, and Pydantic models, e.g. `RunConfig` and `LogRecord` in `ankideck_generator/core/models.py`, `ValidationContext` in `ankideck_generator/core/validators.py`, and `SentenceCandidate` in `ankideck_generator/core/providers.py`.

## Code Style

**Formatting:**
- No formatter config is detected in the repo root: `.prettierrc*`, `pyproject.toml`, `setup.cfg`, `tox.ini`, `ruff.toml`, `.flake8`, and `mypy.ini` are not present at `C:\dev\script-dev`.
- Follow the existing style in `ankideck_generator/main.py`, `ankideck_generator/core/deck_builder.py`, and `ankideck_generator/core/providers.py`: 4-space indentation, type hints on public functions, trailing commas in multiline calls, and blank lines between import groups.

**Linting:**
- No repo-local lint config is detected at `C:\dev\script-dev`.
- Treat consistency with existing source as the enforced standard; the closest thing to a style baseline is the current Python code in `ankideck_generator/core/*.py` and `ankideck_generator/utils/*.py`.

## Import Organization

**Order:**
1. Standard library imports first, e.g. `argparse`, `Path`, `threading` in `ankideck_generator/main.py` and `ankideck_generator/core/providers.py`
2. Third-party imports second, e.g. `colorama`, `genanki`, `requests`, `gTTS`, `pydantic` in `ankideck_generator/main.py`, `ankideck_generator/core/deck_builder.py`, and `ankideck_generator/core/models.py`
3. Local package imports last, usually relative inside the package, e.g. `from .core.deck_builder import DeckBuilder` in `ankideck_generator/main.py` and `from ..utils.file_utils import ensure_dir` in `ankideck_generator/core/providers.py`

**Path Aliases:**
- No path alias system is used.
- Package code uses relative imports such as `from ..utils.language_tools import ...` in `ankideck_generator/core/deck_builder.py`.
- Tests use absolute package imports such as `from ankideck_generator.core.models import CardData` in `ankideck_generator/tests/test_validators.py`.

## Error Handling

**Patterns:**
- Raise explicit exceptions for hard startup/config failures, e.g. `FileNotFoundError` in `ankideck_generator/utils/config.py` and `RuntimeError` for missing optional dependencies in `ankideck_generator/utils/config.py` and `ankideck_generator/core/deck_builder.py`.
- Convert provider/network failures into result objects instead of propagating most operational errors. `ankideck_generator/core/providers.py` returns `ProviderResult`, `SentenceCandidatesResult`, or `DefinitionCandidatesResult` with an `error` field.
- Keep broad `except Exception` blocks limited to optional imports and safety nets, usually annotated with `# pragma: no cover`, e.g. `ankideck_generator/main.py`, `ankideck_generator/core/providers.py`, and `ankideck_generator/core/deck_builder.py`.
- Prefer boolean/tuple status returns at orchestration boundaries, e.g. `DeckBuilder.preflight()` in `ankideck_generator/core/deck_builder.py` returns `(ok, message)`.

## Logging

**Framework:** JsonLogger + console `print`

**Patterns:**
- Use structured JSONL logs for run records through `JsonLogger` in `ankideck_generator/utils/logger.py` and `DeckBuilder._record_log()` in `ankideck_generator/core/deck_builder.py`.
- Use plain console output for CLI/user-facing status and summaries in `ankideck_generator/main.py` and `ankideck_generator/core/deck_builder.py`.
- Preserve `.model_dump()` payloads when logging Pydantic models, e.g. `logger.log(log_record.model_dump())` in `ankideck_generator/core/deck_builder.py`.

## Comments

**When to Comment:**
- Comments are sparse. Add comments only for compatibility notes, optional dependency behavior, or defensive branches, matching `# pragma: no cover - optional` and `# pragma: no cover - safety net` in `ankideck_generator/main.py`, `ankideck_generator/core/providers.py`, and `ankideck_generator/core/deck_builder.py`.

**JSDoc/TSDoc:**
- Not applicable in this Python repo.
- Python docstrings are also largely absent; prefer readable names and type hints over explanatory docstrings, matching `ankideck_generator/core/models.py` and `ankideck_generator/utils/file_utils.py`.

## Function Design

**Size:**
- Utility modules keep functions small and single-purpose, e.g. `ensure_dir()` and `atomic_write_json()` in `ankideck_generator/utils/file_utils.py`.
- Orchestration methods can be very large and stateful, especially `DeckBuilder` in `ankideck_generator/core/deck_builder.py`; extend it by adding narrowly scoped private helpers instead of adding more inline branching.

**Parameters:**
- Use typed config/data objects for complex call sites. `ankideck_generator/main.py` constructs a `RunConfig`, and downstream code passes that object through `DeckBuilder.build()` and `DeckBuilder.export_deck()`.
- Internal helpers often use keyword-only parameters for readability, e.g. `_build_level_serial()` and `_build_level_parallel()` in `ankideck_generator/core/deck_builder.py`.

**Return Values:**
- Return tuples for multi-part orchestration results, e.g. `(cards, media_files)` from `DeckBuilder.build()` in `ankideck_generator/core/deck_builder.py`.
- Return Pydantic models or dataclasses for structured results, e.g. `ProviderResult` in `ankideck_generator/core/models.py` and `TextTaskResult` in `ankideck_generator/core/deck_builder.py`.
- Return normalized primitives from low-level utilities, e.g. `dict[str, Any]` from `load_config()` in `ankideck_generator/utils/config.py`.

## Module Design

**Exports:**
- Modules export concrete functions/classes directly; there is no barrel-file pattern. Import from the owning module, e.g. `ankideck_generator.core.validators`, `ankideck_generator.core.providers`, and `ankideck_generator.utils.definition_tools`.

**Barrel Files:**
- `ankideck_generator/__init__.py`, `ankideck_generator/core/__init__.py`, and `ankideck_generator/utils/__init__.py` are not used as aggregation layers.

## Repo-Specific Conventions

- Use Python `3.11`, matching `C:\dev\script-dev\.python-version` and the warning path in `ankideck_generator/main.py`.
- Resolve repo config from `config.yaml` and keep policy-driven behavior in config/policy files rather than hardcoding new rules, matching `ankideck_generator/main.py`, `ankideck_generator/utils/config.py`, and `ankideck_generator/core/deck_builder.py`.
- Use `Path` objects for filesystem work and helper wrappers like `ensure_dir()`, `read_json()`, and `atomic_write_json()` from `ankideck_generator/utils/file_utils.py` instead of open-coded directory creation and JSON writes.
- Preserve structured schema definitions in `ankideck_generator/core/models.py` when adding new run, card, or log data.
- In tests, instantiate repo objects with real package imports and the real root config path (`Path(__file__).resolve().parents[2] / "config.yaml"`), matching `ankideck_generator/tests/test_deck_builder.py` and `ankideck_generator/tests/test_deck_export.py`.

---

*Convention analysis: 2026-04-15*
