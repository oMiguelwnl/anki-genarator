# AGENTS.md

## Commands
- Use Python `3.11` (`.python-version`; `main.py` warns that full generation is not recommended on newer versions because `googletrans` is unstable there).
- Install deps with `python -m pip install -r requirements.txt`.
- Run the CLI from the repo root: `python -m ankideck_generator --language es --mode build --no-resume --output output/deck.apkg`.
- `--mode build` is only an alias for `full`.
- Verified test commands:
- `python -m pytest -q`
- `python -m pytest ankideck_generator/tests/test_main.py -q`
- `python -m pytest ankideck_generator/tests/test_deck_export.py::test_deck_export -q`
- No repo-local lint, typecheck, formatter, CI, or pre-commit config was found; the only verified automated check is `pytest`.

## Layout
- CLI entrypoint: `ankideck_generator/__main__.py` -> `ankideck_generator/main.py`.
- Main orchestration lives in `ankideck_generator/core/deck_builder.py`.
- Provider fallback / HTTP / TTS logic lives in `ankideck_generator/core/providers.py`.
- Definition cleanup is policy-driven: `DeckBuilder` loads `definitions.policy_path` from `config.yaml`, which currently points to `definition_policy.yaml`. Prefer policy edits before hardcoding new cleanup rules.

## Path And Runtime Gotchas
- Run from the repo root. Template and policy paths resolve relative to `config.yaml`, but generated artifacts are written relative to the current working directory.
- Generated paths to expect:
- cache: `ankideck_generator/data/cache`
- progress: `ankideck_generator/data/progress/<language>_<mode>.json`
- logs: `ankideck_generator/data/logs/run-*.jsonl`
- review/report: `output/review_queue.json`, `output/quality_report.json`
- export metadata: `output/metadata.json`
- Treat `output/` and `ankideck_generator/data/{audio,cache,logs,progress}` as generated artifacts, not hand-maintained source files.
- `runtime.strict_quality` defaults to `true`. Startup preflight fails unless at least one AI profile has endpoint + model + key (`ANKI_AI_KEY` or configured provider keys such as `GROQ_API_KEY_1/2`).
- `test` mode is intentionally cheaper: `runtime.test_disable_audio: true`, so audio is skipped there unless config changes.
- `--resume` works, but both `README.md` and the CLI warn against using it for final exports; prefer `--no-resume`.
- `runtime.cleanup_generated_artifacts: true` makes export delete generated cache, progress, log, and audio directories after writing the deck.

## Tested Behavior To Preserve
- Provider fallback order is covered by tests and should not be changed casually:
- definitions: `wiktionary -> wordnet -> dictionaryapi -> ai`
- translations: `googletrans -> deepl -> libretranslate -> ai`
- sentences: `tatoeba -> wordincontext -> ai`
- Export currently always uses the default deck config and field order from `DeckBuilder._deck_config_for_language()`. `ANKI_FIELD_ORDER_RU` and `templates/*_ru.*` exist, but they are not wired into export today.
