# External Integrations

**Analysis Date:** 2026-04-15

## APIs & External Services

**Lexicon / Definitions:**
- Wiktionary REST API - primary dictionary/word existence source in `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session` from `requests`
  - Auth: none detected
- NLTK WordNet - English-only offline fallback for definitions in `ankideck_generator/core/providers.py`.
  - SDK/Client: `nltk` / `nltk.corpus.wordnet`
  - Auth: not applicable
- DictionaryAPI.dev - English-only HTTP fallback in `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: none detected

**Translation:**
- Google Translate (unofficial client) - first translation fallback in `ankideck_generator/core/providers.py`.
  - SDK/Client: `googletrans.Translator`
  - Auth: none detected
- DeepL API - configured HTTP fallback in `config.yaml` and called from `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: `providers.deepl.api_key` in `config.yaml` (no env indirection detected)
- LibreTranslate - optional HTTP fallback in `config.yaml` and `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: optional `providers.libretranslate.api_key` in `config.yaml`

**Sentence Sources / Generation:**
- Tatoeba API - primary web sentence source in `config.yaml` and `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: none detected
- WordInContext - placeholder secondary sentence source referenced in `config.yaml` and stubbed in `ankideck_generator/core/providers.py`.
  - SDK/Client: planned `requests.Session`
  - Auth: not implemented
- AI chat-completions providers - sentence generation, sentence rewrites, definitions, translations, IPA, and phonetic spelling in `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: `ANKI_AI_KEY`, `GROQ_API_KEY_1`, `GROQ_API_KEY_2`, or inline provider keys resolved in `ankideck_generator/core/providers.py`

**Text-to-Speech / Audio:**
- Google Text-to-Speech - default cloud TTS fallback in `ankideck_generator/core/providers.py` and `config.yaml`.
  - SDK/Client: `gtts.gTTS`
  - Auth: none detected
- ResponsiveVoice API - optional HTTP TTS provider in `config.yaml` and `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: `providers.responsivevoice.api_key` in `config.yaml`
- Azure Cognitive Services Speech - primary configured TTS provider in `config.yaml` and `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: `AZURE_TTS_KEY`, `AZURE_TTS_REGION`
- ElevenLabs - Russian-oriented cloud TTS fallback in `config.yaml` and `ankideck_generator/core/providers.py`.
  - SDK/Client: `requests.Session`
  - Auth: `ELEVENLABS_API_KEY`
- Local system TTS - offline fallback in `ankideck_generator/core/providers.py`.
  - SDK/Client: `pyttsx3`
  - Auth: not applicable

## Data Storage

**Databases:**
- No application database detected.
  - Connection: Not applicable
  - Client: Not applicable

**File Storage:**
- Local filesystem only.
  - Cache files: `ankideck_generator/data/cache/*.json` via `ankideck_generator/core/cache_manager.py`
  - Progress files: `ankideck_generator/data/progress/*.json` via `ProgressStore` usage in `ankideck_generator/core/deck_builder.py`
  - Logs: `ankideck_generator/data/logs/run-*.jsonl` via `ankideck_generator/utils/logger.py`
  - Audio: `ankideck_generator/data/audio` from `config.yaml`
  - Reports: `output/review_queue.json`, `output/quality_report.json`, `output/metadata.json` from `ankideck_generator/core/deck_builder.py`
  - Final export: `output/deck.apkg` by default from `ankideck_generator/main.py`

**Caching:**
- JSON file caches only; no Redis or external cache detected.
  - Managed by `ankideck_generator/core/cache_manager.py`
  - Versioned keys generated in `ankideck_generator/core/deck_builder.py`

## Authentication & Identity

**Auth Provider:**
- No user authentication system detected.
  - Implementation: CLI process reads provider secrets from environment variables loaded by `python-dotenv` in `ankideck_generator/main.py` and resolved in `ankideck_generator/core/providers.py`.

## Monitoring & Observability

**Error Tracking:**
- None detected.

**Logs:**
- Structured JSONL run logs written by `ankideck_generator/utils/logger.py` and created from `ankideck_generator/core/deck_builder.py`.
- Provider-level fallback errors are carried in `ProviderResult.fallback_errors` from `ankideck_generator/core/models.py` and written into run/report outputs by `ankideck_generator/core/deck_builder.py`.

## CI/CD & Deployment

**Hosting:**
- Not applicable; this repo is a local CLI/export tool, not a deployed service.

**CI Pipeline:**
- Not detected. No GitHub Actions, pre-commit, or other CI config was found at the repo root.

## Environment Configuration

**Required env vars:**
- `ANKI_AI_KEY` - default AI provider key in `config.yaml`
- `GROQ_API_KEY_1`, `GROQ_API_KEY_2` - Groq fallback key rotation in `config.yaml`
- `AZURE_TTS_KEY`, `AZURE_TTS_REGION` - Azure TTS credentials in `config.yaml`
- `ELEVENLABS_API_KEY` - ElevenLabs credential in `config.yaml`
- `.env` presence is supported and expected by `ankideck_generator/main.py`; contents were not inspected.

**Secrets location:**
- Environment variables loaded from the repo-root `.env` by `ankideck_generator/main.py`.
- Some providers also allow inline keys in `config.yaml` (`deepl.api_key`, `libretranslate.api_key`, `responsivevoice.api_key`, `ai.api_key`), but preflight messaging in `ankideck_generator/core/providers.py` points operators toward env-based configuration.

## Webhooks & Callbacks

**Incoming:**
- None detected.

**Outgoing:**
- HTTPS requests to external provider endpoints from `ankideck_generator/core/providers.py`, including:
  - `https://en.wiktionary.org/api/rest_v1/page/definition/...`
  - `https://api.dictionaryapi.dev/api/v2/entries/en/...`
  - `https://api-free.deepl.com/v2/translate`
  - `https://libretranslate.com/translate`
  - `https://tatoeba.org/eng/api_v0/search`
  - `https://api.responsivevoice.org/v1/text:speech`
  - Azure Speech endpoint derived from region in `ankideck_generator/core/providers.py`
  - `https://api.elevenlabs.io/v1/text-to-speech/...`
  - `https://api.elevenlabs.io/v1/voices`
  - `https://openrouter.ai/api/v1/chat/completions`
  - `https://api.groq.com/openai/v1/chat/completions`

---

*Integration audit: 2026-04-15*
