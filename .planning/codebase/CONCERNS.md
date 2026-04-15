# Codebase Concerns

**Analysis Date:** 2026-04-15

## Tech Debt

**Monolithic deck orchestration:**
- Issue: `DeckBuilder` centralizes progress handling, provider orchestration, validation, export, cleanup, and report writing in one file; `ankideck_generator/core/deck_builder.py` is 3314 lines and `_process_word_textual()` contains many nested helpers in a single method.
- Files: `ankideck_generator/core/deck_builder.py`, `ankideck_generator/tests/test_deck_builder.py`
- Impact: Small feature changes have wide regression risk, tests become expensive to understand, and bug fixes tend to require edits in a single high-churn file.
- Fix approach: Extract focused services from `ankideck_generator/core/deck_builder.py` for resume/progress, text generation, audio attachment, export, and report output before adding more generation rules.

**Provider manager concentration:**
- Issue: `ProviderManager` mixes HTTP clients, fallback policy, TTS generation, AI prompting, auth handling, and provider disablement in one 1675-line module.
- Files: `ankideck_generator/core/providers.py`, `ankideck_generator/tests/test_providers.py`
- Impact: Retry/auth changes for one provider can alter unrelated providers, and adding a new integration increases coupling to shared mutable state like `_disabled_providers` and `_provider_timeout_streak`.
- Fix approach: Split `ankideck_generator/core/providers.py` into provider-specific adapters plus a smaller fallback coordinator with shared retry policy.

**Thin automation guardrails:**
- Issue: Repository guidance states there is no repo-local lint, typecheck, formatter, CI, or pre-commit setup; only `pytest` is verified.
- Files: `AGENTS.md`, `requirements.txt`
- Impact: Style drift, dead code, and type regressions can land undetected, especially in `ankideck_generator/core/deck_builder.py` and `ankideck_generator/core/providers.py` where most change volume sits.
- Fix approach: Add repo-local automation for linting, formatting, and a CI test job before expanding feature scope.

## Known Bugs

**Resume does not restore execution position or RNG state:**
- Symptoms: A resumed run skips previously accepted `processed_focus` and `processed_sentences`, but does not resume from the saved `level`, `index`, or `rng_state`.
- Files: `ankideck_generator/core/deck_builder.py`, `ankideck_generator/core/models.py`, `README.md`, `AGENTS.md`
- Trigger: Run with `--resume` after an interrupted generation.
- Workaround: Prefer `--no-resume`; if resume is required, treat it as best-effort deduplication rather than deterministic continuation.

**Interactive edits bypass final validation:**
- Symptoms: `_process_word()` computes `final_errors`, then allows `_interactive_edit()` to mutate the card, and accepts the edited card without rerunning validation.
- Files: `ankideck_generator/core/deck_builder.py`
- Trigger: Run with `--interactive` and edit `focus`, `definition`, `sentence`, or audio-related fields.
- Workaround: Re-run generation non-interactively or manually inspect edited cards in the exported deck.

## Security Considerations

**Cleanup can delete arbitrary in-repo directories if config paths drift:**
- Risk: `_cleanup_generated_directory()` deletes any resolved path under `Path.cwd()` or the config directory, while `runtime.cleanup_generated_artifacts` is enabled by default in `config.yaml`.
- Files: `ankideck_generator/core/deck_builder.py`, `config.yaml`, `AGENTS.md`
- Current mitigation: `_is_safe_cleanup_target()` blocks deleting the root directory itself.
- Recommendations: Restrict cleanup to an explicit allowlist of generated directories such as `ankideck_generator/data/cache`, `ankideck_generator/data/progress`, `ankideck_generator/data/logs`, and the configured audio directory.

**Provider secrets can be stored directly in tracked config:**
- Risk: `config.yaml` includes inline `api_key` fields for `deepl`, `libretranslate`, `responsivevoice`, and the AI section, and provider code reads those values directly.
- Files: `config.yaml`, `ankideck_generator/core/providers.py`
- Current mitigation: Some providers also support env-based lookup such as `ANKI_AI_KEY`, `AZURE_TTS_KEY`, `AZURE_TTS_REGION`, and `ELEVENLABS_API_KEY`.
- Recommendations: Standardize all providers on env-var loading and keep `config.yaml` free of live secrets.

## Performance Bottlenecks

**Near-duplicate sentence detection scales poorly:**
- Problem: `validate_card()` compares each candidate sentence against every seen sentence using `difflib.SequenceMatcher`.
- Files: `ankideck_generator/core/validators.py`, `ankideck_generator/core/deck_builder.py`
- Cause: Duplicate detection is O(n) per candidate and becomes O(n²) over long full runs with many rejected candidates.
- Improvement path: Add a cheaper normalization/indexing stage before `SequenceMatcher`, or restrict fuzzy comparison to a smaller candidate set.

**Timed-out local TTS work can leave background threads alive:**
- Problem: `_run_local_with_timeout()` returns after `worker.join(timeout)`, but timed-out local synthesis threads keep running as daemon threads.
- Files: `ankideck_generator/core/providers.py`, `ankideck_generator/tests/test_providers.py`
- Cause: Python threads are not cancelled when `pyttsx3` work blocks past the timeout.
- Improvement path: Isolate local TTS in a subprocess or a killable worker instead of a daemon thread.

## Fragile Areas

**Current-working-directory coupling for generated files:**
- Files: `ankideck_generator/main.py`, `ankideck_generator/core/deck_builder.py`, `AGENTS.md`
- Why fragile: The CLI expects execution from the repo root, templates resolve from `config.yaml`, but generated outputs such as `output/metadata.json` and cleanup roots depend on the current working directory.
- Safe modification: Normalize all generated paths from the config location or an explicit runtime root before changing export or cleanup behavior.
- Test coverage: `ankideck_generator/tests/test_deck_export.py` checks export behavior under controlled `tmp_path`, but there is no broader test for wrong-working-directory execution.

**Generated JSON files are a single point of failure:**
- Files: `ankideck_generator/utils/file_utils.py`, `ankideck_generator/core/cache_manager.py`, `ankideck_generator/core/deck_builder.py`, `ankideck_generator/utils/cache_refresh.py`
- Why fragile: `read_json()` uses raw `json.load()` with no recovery path; one truncated cache or progress file can abort generation or cache refresh.
- Safe modification: Add error-tolerant reads, quarantine bad files, and validate `ProgressState` payloads before use.
- Test coverage: `ankideck_generator/tests/test_cache_manager.py` only covers a happy-path roundtrip.

**Russian export path is partially implemented:**
- Files: `ankideck_generator/core/deck_builder.py`, `ankideck_generator/core/models.py`, `ankideck_generator/templates/card_front_ru.html`, `ankideck_generator/templates/card_back_ru.html`, `ankideck_generator/templates/styles_ru.css`, `ankideck_generator/tests/test_deck_export.py`, `AGENTS.md`
- Why fragile: Russian-specific templates and `ANKI_FIELD_ORDER_RU` exist, but `_deck_config_for_language()` always returns the default field order and tests currently lock in that default behavior.
- Safe modification: Add explicit language-specific deck config selection and update export tests in `ankideck_generator/tests/test_deck_export.py` at the same time.
- Test coverage: Coverage currently preserves the default export instead of the intended Russian-specific path.

## Scaling Limits

**External-provider fan-out drives latency and cost:**
- Current capacity: `config.yaml` sets `full_level_size: 1000`, `max_attempts_per_level_full: 8000`, `ai_max_calls_per_word: 10`, and `ai_max_calls_per_field: 4`.
- Limit: `ProviderManager._ai_request()` iterates provider -> API key -> model serially, so larger runs increase latency and provider spend quickly.
- Scaling path: Tighten per-stage budgets, cache more aggressively, and add provider-level metrics/quotas before increasing `full_level_size` or concurrency.

## Dependencies at Risk

**`googletrans==4.0.0rc1`:**
- Risk: Project docs and the CLI warn that `googletrans` is unstable on newer Python versions.
- Impact: Translation fallback can degrade or fail during startup/import on unsupported runtimes.
- Migration plan: Replace `googletrans` with a maintained translation backend or move it behind an optional provider flag with stronger runtime checks.

## Missing Critical Features

**Deterministic resume support:**
- Problem: `ProgressState` stores `level`, `index`, and `rng_state`, but the runtime does not restore them in `ankideck_generator/core/deck_builder.py`.
- Blocks: Reliable crash recovery and long-running generation workflows.

**Language-specific Russian export wiring:**
- Problem: `ANKI_FIELD_ORDER_RU` and `templates/*_ru.*` are present, but export still uses the default model path.
- Blocks: Shipping the Russian deck shape implied by `ankideck_generator/core/models.py` and the template set under `ankideck_generator/templates/`.

## Test Coverage Gaps

**Resume and progress restoration:**
- What's not tested: Reloading `ProgressState.level`, `ProgressState.index`, and `ProgressState.rng_state` from `ankideck_generator/data/progress/<language>_<mode>.json`.
- Files: `ankideck_generator/core/deck_builder.py`, `ankideck_generator/core/models.py`, `ankideck_generator/tests/test_main.py`
- Risk: Resume can appear supported while silently restarting selection order.
- Priority: High

**Interactive editing and post-edit validation:**
- What's not tested: `_interactive_edit()` flows and revalidation after a user changes card fields.
- Files: `ankideck_generator/core/deck_builder.py`
- Risk: Invalid cards can be accepted only in interactive mode and escape automated checks.
- Priority: High

**Corrupt cache/progress handling:**
- What's not tested: Recovery from malformed JSON in cache, progress, or output files.
- Files: `ankideck_generator/utils/file_utils.py`, `ankideck_generator/core/cache_manager.py`, `ankideck_generator/utils/cache_refresh.py`
- Risk: One interrupted write can break future runs until files are manually removed.
- Priority: Medium

---

*Concerns audit: 2026-04-15*
