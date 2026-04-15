# Codebase Structure

**Analysis Date:** 2026-04-15

## Directory Layout

```text
[project-root]/
├── ankideck_generator/          # Packaged application code, templates, tests, and generated data roots
│   ├── core/                    # Main orchestration, providers, models, validation, cache service
│   ├── utils/                   # Config, logging, file IO, text helpers, cache refresh utilities
│   ├── templates/               # HTML/CSS card templates used by deck export
│   ├── tests/                   # Pytest suite for CLI, providers, export, validators, helpers
│   ├── data/                    # Runtime cache/audio/log/progress root (generated at run time)
│   ├── __main__.py              # `python -m ankideck_generator` entrypoint
│   └── main.py                  # CLI argument parsing and run setup
├── .planning/codebase/          # Generated codebase mapping documents
├── output/                      # Generated deck/report artifacts such as `.apkg` and JSON outputs
├── config.yaml                  # Primary runtime/provider/audio/deck configuration
├── definition_policy.yaml       # Definition cleanup policy loaded by `DeckBuilder`
├── requirements.txt             # Python dependency list
├── pytest.ini                   # Pytest directory exclusions
├── README.md                    # Run guidance and environment expectations
├── AGENTS.md                    # Repo-specific agent instructions and known runtime gotchas
└── vocabGenarator.py            # Legacy standalone script outside the packaged application
```

## Directory Purposes

**`ankideck_generator/`:**
- Purpose: Main Python package.
- Contains: runtime entrypoints, source modules, templates, tests, and generated-data root directories.
- Key files: `ankideck_generator/main.py`, `ankideck_generator/__main__.py`, `ankideck_generator/core/deck_builder.py`

**`ankideck_generator/core/`:**
- Purpose: Business workflow and integration boundary.
- Contains: orchestration, providers, cache manager, validation rules, Pydantic models.
- Key files: `ankideck_generator/core/deck_builder.py`, `ankideck_generator/core/providers.py`, `ankideck_generator/core/models.py`, `ankideck_generator/core/validators.py`, `ankideck_generator/core/cache_manager.py`

**`ankideck_generator/utils/`:**
- Purpose: Shared support code used across the core workflow.
- Contains: YAML loading, atomic file IO, JSONL logger, token/language helpers, definition cleanup logic, cache refresh tooling.
- Key files: `ankideck_generator/utils/config.py`, `ankideck_generator/utils/file_utils.py`, `ankideck_generator/utils/logger.py`, `ankideck_generator/utils/definition_tools.py`, `ankideck_generator/utils/language_tools.py`, `ankideck_generator/utils/cache_refresh.py`

**`ankideck_generator/templates/`:**
- Purpose: Source templates for Anki note rendering.
- Contains: default and Russian-specific HTML/CSS files.
- Key files: `ankideck_generator/templates/card_front.html`, `ankideck_generator/templates/card_back.html`, `ankideck_generator/templates/styles.css`, `ankideck_generator/templates/card_front_ru.html`, `ankideck_generator/templates/card_back_ru.html`, `ankideck_generator/templates/styles_ru.css`

**`ankideck_generator/tests/`:**
- Purpose: Pytest suite for behavior verification.
- Contains: tests for CLI parsing, providers, validators, export, cache refresh, and deck builder behavior.
- Key files: `ankideck_generator/tests/test_main.py`, `ankideck_generator/tests/test_deck_builder.py`, `ankideck_generator/tests/test_deck_export.py`, `ankideck_generator/tests/test_providers.py`

**`ankideck_generator/data/`:**
- Purpose: Generated runtime state location.
- Contains: cache/audio/log/progress directories created during runs.
- Key files: not committed by default; paths are referenced from `config.yaml` and cleanup code in `ankideck_generator/core/deck_builder.py`

**`output/`:**
- Purpose: Generated user-facing outputs.
- Contains: final decks and report JSON files.
- Key files: `output/metadata.json`, `output/quality_report.json`, `output/review_queue.json`

**`.planning/codebase/`:**
- Purpose: Generated repository reference docs for other GSD commands.
- Contains: architecture/stack/convention/concern documents.
- Key files: `.planning/codebase/ARCHITECTURE.md`, `.planning/codebase/STRUCTURE.md`

## Key File Locations

**Entry Points:**
- `ankideck_generator/__main__.py`: package execution shim.
- `ankideck_generator/main.py`: primary CLI entry and runtime setup.
- `ankideck_generator/core/deck_builder.py`: main build/export workflow entry.
- `ankideck_generator/utils/cache_refresh.py`: maintenance entry for Russian cache normalization.
- `vocabGenarator.py`: separate standalone script not wired into the package entrypoint.

**Configuration:**
- `config.yaml`: language, provider, audio, deck, cache, and runtime settings.
- `definition_policy.yaml`: rule-driven definition cleanup policy.
- `pytest.ini`: pytest recursion exclusions for generated directories.
- `requirements.txt`: installable dependencies.
- `.python-version`: local Python version pin referenced by `AGENTS.md`.

**Core Logic:**
- `ankideck_generator/core/deck_builder.py`: word pool preparation, processing pipeline, export, cleanup.
- `ankideck_generator/core/providers.py`: provider adapters, fallback ordering, AI/audio integration.
- `ankideck_generator/core/validators.py`: card validation rules and duplicate/language checks.
- `ankideck_generator/core/models.py`: core runtime and card data models.
- `ankideck_generator/utils/definition_tools.py`: definition normalization and policy merge logic.
- `ankideck_generator/utils/language_tools.py`: tokenization, stopword filtering, sentence scoring, language checks.

**Testing:**
- `ankideck_generator/tests/test_main.py`: CLI argument and runtime override tests.
- `ankideck_generator/tests/test_deck_builder.py`: orchestration and card-generation behavior.
- `ankideck_generator/tests/test_deck_export.py`: `.apkg` export structure and cleanup behavior.
- `ankideck_generator/tests/test_providers.py`: provider fallback and adapter behavior.
- `ankideck_generator/tests/temp_pytest_root/`: generated temp directories excluded from normal pytest discovery.

## Naming Conventions

**Files:**
- Package modules use lowercase snake_case: `deck_builder.py`, `cache_manager.py`, `language_tools.py`.
- Tests use `test_*.py`: `test_validators.py`, `test_cache_refresh.py`.
- Templates use descriptive lowercase names with optional language suffixes: `card_front.html`, `card_back_ru.html`, `styles_ru.css`.
- Root config/policy files use plain descriptive names: `config.yaml`, `definition_policy.yaml`.

**Directories:**
- Package directories are short lowercase nouns: `core/`, `utils/`, `templates/`, `tests/`, `data/`.
- Generated/runtime directories are nested by concern under `ankideck_generator/data/`: `audio/`, `cache/`, `logs/`, `progress/`.
- GSD-generated docs live under `.planning/codebase/`.

## Where to Add New Code

**New Feature:**
- Primary code: extend `ankideck_generator/core/deck_builder.py` when the change affects build orchestration, or add helper logic under `ankideck_generator/utils/` when it is reusable support logic.
- Tests: add or update matching tests in `ankideck_generator/tests/`, usually near the touched module (`test_deck_builder.py`, `test_providers.py`, `test_validators.py`).

**New Component/Module:**
- Implementation: put provider-facing features in `ankideck_generator/core/providers.py` or a new peer module under `ankideck_generator/core/` if the concern becomes large enough.
- If the logic is pure normalization, parsing, or file support, place it under `ankideck_generator/utils/` and import it into `ankideck_generator/core/`.

**Utilities:**
- Shared helpers: use `ankideck_generator/utils/`.
- File/JSON helpers belong with `ankideck_generator/utils/file_utils.py`.
- Text or language heuristics belong with `ankideck_generator/utils/language_tools.py`.
- Definition normalization rules belong with `ankideck_generator/utils/definition_tools.py` and `definition_policy.yaml` before adding hardcoded logic to `ankideck_generator/core/deck_builder.py` or `ankideck_generator/core/providers.py`.

## Special Directories

**`ankideck_generator/data/`:**
- Purpose: Runtime-generated cache, progress, logs, and audio roots.
- Generated: Yes
- Committed: No (`.gitignore` excludes `ankideck_generator/data/audio/`, `ankideck_generator/data/cache/`, `ankideck_generator/data/logs/`, and `ankideck_generator/data/progress/`)

**`output/`:**
- Purpose: Generated deck packages and summary JSON artifacts.
- Generated: Yes
- Committed: No (`.gitignore` excludes `/output/`)

**`ankideck_generator/tests/temp_pytest_root/`:**
- Purpose: Temporary pytest workspaces created by tests.
- Generated: Yes
- Committed: No (`.gitignore` and `pytest.ini` exclude it)

**`.planning/codebase/`:**
- Purpose: GSD reference documentation written by mapper commands.
- Generated: Yes
- Committed: Yes, if the orchestrator chooses to stage documentation changes.

**`.venv/`:**
- Purpose: Local Python environment.
- Generated: Yes
- Committed: No

---

*Structure analysis: 2026-04-15*
