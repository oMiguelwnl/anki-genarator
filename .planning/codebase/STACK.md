# Technology Stack

**Analysis Date:** 2026-04-15

## Languages

**Primary:**
- Python 3.11 - CLI, generation pipeline, provider orchestration, export, and tests in `ankideck_generator/`, with the runtime pinned in `.python-version` and reinforced in `README.md`.

**Secondary:**
- YAML - runtime/provider/deck configuration in `config.yaml` and definition cleanup policy in `definition_policy.yaml`.
- HTML/CSS - Anki card templates in `ankideck_generator/templates/card_front.html`, `ankideck_generator/templates/card_back.html`, and `ankideck_generator/templates/styles.css` plus Russian variants in `ankideck_generator/templates/*_ru.*`.
- JSON - cache, progress, logs, metadata, review queue, and quality report payloads written by `ankideck_generator/core/deck_builder.py` and helpers in `ankideck_generator/utils/file_utils.py`.

## Runtime

**Environment:**
- CPython 3.11 - required by `.python-version`; `ankideck_generator/main.py` warns that full generation on newer Python versions is risky because `googletrans` is unstable.

**Package Manager:**
- `pip` via `python -m pip install -r requirements.txt` as documented in `AGENTS.md`.
- Lockfile: missing (`requirements.txt` is present, but no `poetry.lock`, `Pipfile.lock`, or `uv.lock` was detected at the repo root).

## Frameworks

**Core:**
- Standard-library CLI (`argparse`) - command parsing in `ankideck_generator/main.py`.
- Pydantic 2 - typed runtime and card models in `ankideck_generator/core/models.py`.

**Testing:**
- Pytest - test runner used across `ankideck_generator/tests/` and scoped by `pytest.ini`.

**Build/Dev:**
- `genanki` - `.apkg` deck/model/package generation in `ankideck_generator/core/deck_builder.py`.
- `tqdm` - progress bars during level builds in `ankideck_generator/core/deck_builder.py`.
- `python-dotenv` - environment loading from `.env` in `ankideck_generator/main.py`.
- `PyYAML` - config/policy loading in `ankideck_generator/utils/config.py` and indirectly through `DeckBuilder` in `ankideck_generator/core/deck_builder.py`.

## Key Dependencies

**Critical:**
- `genanki>=0.13.0` - exports final Anki packages from cards and templates in `ankideck_generator/core/deck_builder.py`.
- `requests>=2.28.0` - shared HTTP client for external providers in `ankideck_generator/core/providers.py`.
- `wordfreq>=3.0.0` - difficulty scoring and lexicon sourcing in `ankideck_generator/core/deck_builder.py` and `ankideck_generator/utils/language_tools.py`.
- `pydantic>=2.0.0` - validates `RunConfig`, `CardData`, and provider result models in `ankideck_generator/core/models.py`.
- `pyyaml>=6.0` - required to load `config.yaml` through `ankideck_generator/utils/config.py`.

**Infrastructure:**
- `googletrans==4.0.0rc1` - first translation fallback in `ankideck_generator/core/providers.py`.
- `gtts>=2.3.0` and `pyttsx3>=2.90` - cloud/local TTS options in `ankideck_generator/core/providers.py`.
- `nltk>=3.8.0` - optional WordNet-backed English definitions in `ankideck_generator/core/providers.py`.
- `langdetect>=1.0.9` - language validation utilities in `ankideck_generator/utils/language_tools.py`.
- `colorama>=0.4.6` - colored CLI warnings/errors in `ankideck_generator/main.py`.
- `pytest>=7.4.0` and `requests-mock>=1.11.0` - automated verification dependencies declared in `requirements.txt`.

## Configuration

**Environment:**
- `.env` file present at the repo root; `ankideck_generator/main.py` loads it with `load_dotenv()` when available.
- Core runtime/provider settings live in `config.yaml`, including languages, provider endpoints, cache paths, audio order, deck templates, retry/timeout budgets, and strict-quality rules.
- Definition cleanup is policy-driven via `definitions.policy_path: "definition_policy.yaml"` in `config.yaml`, with concrete cleanup rules stored in `definition_policy.yaml`.
- Required secret names referenced by code/config include `ANKI_AI_KEY`, `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, `AZURE_TTS_KEY`, `AZURE_TTS_REGION`, and `ELEVENLABS_API_KEY` in `config.yaml` and `ankideck_generator/core/providers.py`.

**Build:**
- Runtime config: `config.yaml`
- Definition policy: `definition_policy.yaml`
- CLI entrypoints: `ankideck_generator/__main__.py`, `ankideck_generator/main.py`
- Pytest config: `pytest.ini`
- Deck templates: `ankideck_generator/templates/card_front.html`, `ankideck_generator/templates/card_back.html`, `ankideck_generator/templates/styles.css`

## Platform Requirements

**Development:**
- Run from the repo root so relative paths from `config.yaml` and generated output paths resolve correctly, per `AGENTS.md`.
- Python 3.11 environment with dependencies from `requirements.txt`.
- Network access is required for the configured web providers in `ankideck_generator/core/providers.py` unless all needed data is already cached in `ankideck_generator/data/cache`.
- No repo-local lint, formatter, type checker, pre-commit, or CI config was detected; the only verified automated check documented in `AGENTS.md` is `python -m pytest -q`.

**Production:**
- Local/CLI execution that writes an Anki package to `output/deck.apkg` by default from `ankideck_generator/main.py`.
- Generated artifacts are file-system based: cache in `ankideck_generator/data/cache`, progress in `ankideck_generator/data/progress`, logs in `ankideck_generator/data/logs`, metadata in `output/metadata.json`, and quality outputs in `output/review_queue.json` / `output/quality_report.json`.

---

*Stack analysis: 2026-04-15*
