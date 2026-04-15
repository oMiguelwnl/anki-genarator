# Architecture

**Analysis Date:** 2026-04-15

## Pattern Overview

**Overall:** Configuration-driven CLI pipeline with a central orchestration service.

**Key Characteristics:**
- `ankideck_generator/main.py` translates CLI arguments plus `config.yaml` into a strongly typed `RunConfig` and hands control to `ankideck_generator/core/deck_builder.py`.
- `ankideck_generator/core/deck_builder.py` is the application hub: it prepares word pools, coordinates provider calls, validates candidate cards, persists caches/progress/logs, and exports the final `.apkg`.
- External integrations are isolated behind `ankideck_generator/core/providers.py`, while normalization, validation, logging, and file IO helpers live in `ankideck_generator/utils/*.py`.

## Layers

**CLI Layer:**
- Purpose: Parse user input, load environment/configuration, and start one deck-generation run.
- Location: `ankideck_generator/__main__.py`, `ankideck_generator/main.py`
- Contains: `argparse` setup, mode alias handling, runtime/profile overrides, startup preflight.
- Depends on: `ankideck_generator/utils/config.py`, `ankideck_generator/core/models.py`, `ankideck_generator/core/deck_builder.py`
- Used by: `python -m ankideck_generator`

**Application Orchestration Layer:**
- Purpose: Execute the end-to-end build lifecycle for cards and deck export.
- Location: `ankideck_generator/core/deck_builder.py`
- Contains: `DeckBuilder`, `ProgressStore`, build stats models, serial/parallel level processing, export and cleanup flows.
- Depends on: `ankideck_generator/core/providers.py`, `ankideck_generator/core/cache_manager.py`, `ankideck_generator/core/validators.py`, `ankideck_generator/core/models.py`, `ankideck_generator/utils/*`, `config.yaml`, `definition_policy.yaml`
- Used by: `ankideck_generator/main.py`, `ankideck_generator/utils/cache_refresh.py`, tests in `ankideck_generator/tests/test_deck_builder.py` and `ankideck_generator/tests/test_deck_export.py`

**Provider Gateway Layer:**
- Purpose: Wrap all dictionary, translation, sentence, IPA, AI, and audio providers behind a single API with retry/fallback behavior.
- Location: `ankideck_generator/core/providers.py`
- Contains: `ProviderManager`, candidate result dataclasses, provider-specific HTTP/local adapters, AI readiness checks.
- Depends on: `requests`, `gtts`, optional `googletrans`, optional `pyttsx3`, optional `nltk`, helper modules in `ankideck_generator/utils/definition_tools.py` and `ankideck_generator/utils/language_tools.py`
- Used by: `ankideck_generator/core/deck_builder.py`, `ankideck_generator/utils/cache_refresh.py`

**Domain Model & Validation Layer:**
- Purpose: Define the card/run/progress/log data contracts and enforce quality rules.
- Location: `ankideck_generator/core/models.py`, `ankideck_generator/core/validators.py`
- Contains: `CardData`, `RunConfig`, `ProgressState`, `LogRecord`, `validate_card`, `ValidationContext`.
- Depends on: `pydantic`, `ankideck_generator/utils/definition_tools.py`, `ankideck_generator/utils/language_tools.py`
- Used by: `ankideck_generator/main.py`, `ankideck_generator/core/deck_builder.py`, tests across `ankideck_generator/tests/`

**Persistence & Support Utilities Layer:**
- Purpose: Handle config IO, JSON persistence, log writing, text normalization, and cache maintenance.
- Location: `ankideck_generator/utils/config.py`, `ankideck_generator/utils/file_utils.py`, `ankideck_generator/utils/logger.py`, `ankideck_generator/utils/language_tools.py`, `ankideck_generator/utils/definition_tools.py`, `ankideck_generator/utils/cache_refresh.py`
- Contains: YAML loading, atomic JSON writes, JSONL logging, tokenization/difficulty helpers, definition policy merging, Russian cache refresh tooling.
- Depends on: stdlib, `pyyaml`, `wordfreq`, optional `langdetect`, `ankideck_generator/core/*`
- Used by: all runtime layers

**Presentation / Export Layer:**
- Purpose: Render `CardData` into Anki notes and package deck assets.
- Location: `ankideck_generator/core/deck_builder.py`, `ankideck_generator/templates/card_front.html`, `ankideck_generator/templates/card_back.html`, `ankideck_generator/templates/styles.css`
- Contains: `DeckBuilder.export_deck()`, field ordering from `ankideck_generator/core/models.py`, template resolution from `config.yaml`.
- Depends on: `genanki`, template files, generated media files.
- Used by: the final step of `ankideck_generator/main.py`

## Data Flow

**CLI build flow:**

1. `ankideck_generator/__main__.py` calls `ankideck_generator/main.py:main()`.
2. `ankideck_generator/main.py` loads `.env` if available, parses flags, reads `config.yaml`, validates the requested language, and builds `RunConfig`.
3. `ankideck_generator/main.py` instantiates `DeckBuilder` from `ankideck_generator/core/deck_builder.py` and runs `preflight()` when `strict_quality` is enabled.
4. `DeckBuilder.build()` prepares per-level word pools with `wordfreq`, loads progress from `ankideck_generator/data/progress`, opens a JSONL run log under `ankideck_generator/data/logs`, and iterates level-by-level.
5. For each word, `DeckBuilder._process_word_textual()` fetches/caches lexical data through `ProviderManager`, normalizes definitions, assembles a `CardData`, and records a `LogRecord`.
6. `DeckBuilder._validate_text_candidate()` and `ankideck_generator/core/validators.py:validate_card()` reject duplicates, bad language matches, invalid IPA, missing fields, and level-profile violations before acceptance.
7. `DeckBuilder._attach_audio_to_card()` optionally generates or reuses audio files under `ankideck_generator/data/audio` and augments the same `CardData`.
8. `DeckBuilder.export_deck()` renders cards with templates from `ankideck_generator/templates/`, writes the `.apkg`, writes `output/metadata.json`, `output/quality_report.json`, and `output/review_queue.json`, then conditionally cleans generated artifacts.

**Cache refresh flow:**

1. `ankideck_generator/utils/cache_refresh.py:refresh_russian_cache_files()` constructs `DeckBuilder` and `ProviderManager` from `config.yaml`.
2. It reads cache JSON files from `ankideck_generator/data/cache`.
3. It normalizes or refreshes Russian definition/translation entries using provider calls plus definition policy rules.
4. It writes updated cache files back with `atomic_write_json()`.

**State Management:**
- Run configuration is immutable at runtime through `RunConfig` in `ankideck_generator/core/models.py`.
- In-memory mutable build state lives in `BuildStats`, `ValidationContext`, and local counters inside `DeckBuilder`.
- Durable state is split by concern: cache JSON under `ankideck_generator/data/cache`, resumable progress JSON under `ankideck_generator/data/progress`, run logs under `ankideck_generator/data/logs`, and final reports under `output/`.
- Parallel execution is confined to `DeckBuilder._build_level_parallel()` in `ankideck_generator/core/deck_builder.py`, with thread-local provider instances created by `_thread_provider_manager()`.

## Key Abstractions

**RunConfig:**
- Purpose: Carry all runtime parameters for a single build.
- Examples: `ankideck_generator/core/models.py`, constructed in `ankideck_generator/main.py`
- Pattern: Pydantic configuration object passed top-down.

**CardData:**
- Purpose: Represent one final Anki card independent of template rendering.
- Examples: `ankideck_generator/core/models.py`, populated in `ankideck_generator/core/deck_builder.py`, asserted in `ankideck_generator/tests/test_deck_export.py`
- Pattern: Transport model with a `genanki_fields()` adapter.

**DeckBuilder:**
- Purpose: Own the complete workflow from word selection through export.
- Examples: `ankideck_generator/core/deck_builder.py`
- Pattern: Orchestrator/service object with helper methods for each pipeline stage.

**ProviderManager:**
- Purpose: Hide provider-specific details behind fallback-based methods such as `definition()`, `translation()`, `sentence()`, `audio()`, and `ipa()`.
- Examples: `ankideck_generator/core/providers.py`
- Pattern: Gateway/facade with retries, provider disablement, and fallback error aggregation.

**ProgressStore / CacheManager / JsonLogger:**
- Purpose: Separate persistence concerns for progress, reusable data, and append-only logs.
- Examples: `ankideck_generator/core/deck_builder.py:ProgressStore`, `ankideck_generator/core/cache_manager.py`, `ankideck_generator/utils/logger.py`
- Pattern: Small infrastructure services used by the orchestrator.

**Definition policy:**
- Purpose: Keep definition cleanup rule-driven instead of hardcoded in provider code.
- Examples: `definition_policy.yaml`, `ankideck_generator/utils/definition_tools.py`, `DeckBuilder._load_definition_policy()` in `ankideck_generator/core/deck_builder.py`
- Pattern: Configurable normalization policy loaded once and reused globally.

## Entry Points

**CLI module:**
- Location: `ankideck_generator/__main__.py`
- Triggers: `python -m ankideck_generator`
- Responsibilities: Delegate process exit code to `ankideck_generator/main.py:main()`.

**Main application entry:**
- Location: `ankideck_generator/main.py`
- Triggers: CLI execution and tests in `ankideck_generator/tests/test_main.py`
- Responsibilities: Parse args, load config, compute effective runtime settings, construct `RunConfig`, run preflight, call build/export.

**Deck orchestration entry:**
- Location: `ankideck_generator/core/deck_builder.py:DeckBuilder.build()`
- Triggers: `ankideck_generator/main.py`
- Responsibilities: Prepare level word pools, resume progress, process words, collect logs/stats, write quality outputs.

**Deck export entry:**
- Location: `ankideck_generator/core/deck_builder.py:DeckBuilder.export_deck()`
- Triggers: `ankideck_generator/main.py`, tests in `ankideck_generator/tests/test_deck_export.py`
- Responsibilities: Load templates, create `genanki` model/deck, attach media, write `.apkg`, emit metadata, clean generated artifacts when configured.

**Cache maintenance entry:**
- Location: `ankideck_generator/utils/cache_refresh.py:refresh_russian_cache_files()`
- Triggers: direct utility use
- Responsibilities: Rebuild or normalize Russian cache entries using the same provider/config stack.

**Legacy standalone script:**
- Location: `vocabGenarator.py`
- Triggers: direct script execution
- Responsibilities: Separate markdown-to-vocabulary generator not imported by the packaged `ankideck_generator` flow.

## Error Handling

**Strategy:** Fail fast on startup misconfiguration, then use provider fallback plus validation-driven rejection during card generation.

**Patterns:**
- `ProviderManager._wrap()` and `ProviderManager._fallback()` in `ankideck_generator/core/providers.py` convert exceptions into `ProviderResult` objects instead of propagating transient provider failures.
- `DeckBuilder.preflight()` in `ankideck_generator/core/deck_builder.py` blocks strict runs before work starts when AI configuration is incomplete.
- `DeckBuilder._process_word()` in `ankideck_generator/core/deck_builder.py` turns validation failures into discarded cards with logged discard reasons rather than raising.
- `DeckBuilder._process_word_textual_task()` and `DeckBuilder._attach_audio_task()` catch per-item exceptions in parallel mode and downgrade them to loggable errors.
- `ankideck_generator/core/validators.py:validate_card()` centralizes reject/accept decisions through named validation error codes.

## Cross-Cutting Concerns

**Logging:** JSONL run logs are written through `ankideck_generator/utils/logger.py:JsonLogger` to `ankideck_generator/data/logs/run-*.jsonl`, with per-card provider usage, timings, validation errors, and review notes assembled in `ankideck_generator/core/models.py:LogRecord`.

**Validation:** All content validation funnels through `ankideck_generator/core/validators.py` and `_validations_for_language()` in `ankideck_generator/core/deck_builder.py`; use this path instead of embedding ad hoc checks in provider code.

**Authentication:** Provider credentials are configured indirectly through `config.yaml` plus environment variable names resolved inside `ankideck_generator/core/providers.py`; secrets are expected from `.env` at process startup, not from checked-in code.

---

*Architecture analysis: 2026-04-15*
