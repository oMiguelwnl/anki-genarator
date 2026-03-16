from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote
from xml.sax.saxutils import escape as xml_escape

import requests
from gtts import gTTS

from ..utils.file_utils import ensure_dir
from ..utils.language_tools import LANG_CODE_TO_NAME, score_sentence
from .models import ProviderResult

try:
    import pyttsx3
except Exception:  # pragma: no cover - optional
    pyttsx3 = None

try:
    from googletrans import Translator
except Exception:  # pragma: no cover - optional
    Translator = None

try:
    import nltk
    from nltk.corpus import wordnet
except Exception:  # pragma: no cover - optional
    nltk = None
    wordnet = None


class ProviderError(Exception):
    pass


class ProviderManager:
    def __init__(self, config: dict, timeout_sec: int, retries: int) -> None:
        self.config = config
        self.timeout_sec = timeout_sec
        self.retries = retries
        self._session = requests.Session()
        self._translator = Translator() if Translator else None
        self._elevenlabs_voice_cache: dict[str, str] = {}
        self._elevenlabs_voices: list[dict] | None = None
        self._ai_config = (config or {}).get("providers", {}).get("ai", {}) if config else {}
        self._ai_request_count = 0
        providers = self._ai_config.get("providers") or self._ai_config.get("provider") or "openrouter"
        if isinstance(providers, list):
            self._ai_providers = providers
        else:
            self._ai_providers = [str(providers)]

    def validate_ai_ready(self) -> tuple[bool, str]:
        for provider_name in self._ai_providers:
            profile = self._ai_config.get(provider_name, {})
            endpoint = profile.get("endpoint") or self._ai_config.get("endpoint")
            models = (
                profile.get("models")
                or profile.get("model")
                or self._ai_config.get("models")
                or self._ai_config.get("model")
            )
            keys = self._resolve_api_keys(profile)
            if endpoint and models and keys:
                return True, ""
        return (
            False,
            (
                "AI preflight failed: no AI provider is fully configured. "
                "Set ANKI_AI_KEY or provider-specific keys in .env and ensure endpoint/models exist in config.yaml."
            ),
        )

    def _wrap(self, provider_name: str, fn: Callable[[], str | None]) -> ProviderResult:
        start = time.time()
        last_exc: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                value = fn()
                if value is None or value == "":
                    raise ProviderError("empty result")
                elapsed = int((time.time() - start) * 1000)
                return ProviderResult(value=value, provider_name=provider_name, elapsed_ms=elapsed)
            except Exception as exc:  # pragma: no cover - network errors
                last_exc = exc
                if attempt >= self.retries:
                    break
        elapsed = int((time.time() - start) * 1000)
        return ProviderResult(value=None, provider_name=provider_name, elapsed_ms=elapsed, error=str(last_exc))

    def definition(
        self, word: str, language: str, allow_ai: bool = True, definition_language: str | None = None
    ) -> ProviderResult:
        target_lang = definition_language or language
        if target_lang != language:
            providers: list[tuple[str, Callable[[], str | None]]] = []
            if allow_ai:
                providers.append(("ai", lambda: self._definition_ai(word, target_lang)))
            return self._fallback(providers)

        providers: list[tuple[str, Callable[[], str | None]]] = []
        if allow_ai:
            providers.append(("ai", lambda: self._definition_ai(word, language)))
        providers.append(("wiktionary", lambda: self._definition_wiktionary(word, language)))
        providers.append(("wordnet", lambda: self._definition_wordnet(word, language)))
        providers.append(("dictionaryapi", lambda: self._definition_dictionaryapi(word, language)))
        return self._fallback(providers)

    def translation(self, text: str, src: str, dest: str, allow_ai: bool = True) -> ProviderResult:
        providers: list[tuple[str, Callable[[], str | None]]] = [
            ("googletrans", lambda: self._translate_google(text, src, dest)),
            ("deepl", lambda: self._translate_deepl(text, src, dest)),
            ("libretranslate", lambda: self._translate_libre(text, src, dest)),
        ]
        if allow_ai:
            providers.append(("ai", lambda: self._translate_ai(text, src, dest)))
        return self._fallback(providers)

    def sentence(self, word: str, language: str, allow_ai: bool = True) -> ProviderResult:
        providers: list[tuple[str, Callable[[], str | None]]] = []
        providers.extend(
            [
                ("tatoeba", lambda: self._sentence_tatoeba(word, language)),
                ("wordincontext", lambda: self._sentence_wordincontext(word, language)),
            ]
        )
        if allow_ai:
            providers.append(("ai", lambda: self._sentence_ai(word, language)))
        return self._fallback(providers)

    def sentence_ai(self, word: str, language: str) -> ProviderResult:
        return self._wrap("ai", lambda: self._sentence_ai(word, language))

    def sentence_web(self, word: str, language: str) -> ProviderResult:
        providers = [
            ("tatoeba", lambda: self._sentence_tatoeba(word, language)),
            ("wordincontext", lambda: self._sentence_wordincontext(word, language)),
        ]
        return self._fallback(providers)

    def translation_ai(self, text: str, src: str, dest: str) -> ProviderResult:
        return self._wrap("ai", lambda: self._translate_ai(text, src, dest))

    def translation_web(self, text: str, src: str, dest: str) -> ProviderResult:
        providers = [
            ("googletrans", lambda: self._translate_google(text, src, dest)),
            ("deepl", lambda: self._translate_deepl(text, src, dest)),
            ("libretranslate", lambda: self._translate_libre(text, src, dest)),
        ]
        return self._fallback(providers)

    def audio(
        self,
        text: str,
        language: str,
        output_dir: str | Path,
        filename_hint: str,
        provider_order: list[str] | None = None,
        voice: str | None = None,
        voice_gender_preference: str | None = None,
    ) -> ProviderResult:
        order = _normalize_provider_order(provider_order) or [
            "gtts",
            "responsivevoice",
            "pyttsx3",
        ]
        providers: list[tuple[str, Callable[[], str | None]]] = []
        for provider_name in order:
            provider_hint = f"{filename_hint}__{provider_name}"
            if provider_name == "azure_tts":
                providers.append(
                    (
                        "azure_tts",
                        lambda hint=provider_hint, v=voice: self._audio_azure_tts(
                            text, language, output_dir, hint, voice=v
                        ),
                    )
                )
            elif provider_name == "elevenlabs":
                providers.append(
                    (
                        "elevenlabs",
                        lambda hint=provider_hint, pref=voice_gender_preference: self._audio_elevenlabs(
                            text, language, output_dir, hint, voice_gender_preference=pref
                        ),
                    )
                )
            elif provider_name == "gtts":
                providers.append(
                    (
                        "gtts",
                        lambda hint=provider_hint: self._audio_gtts(
                            text, language, output_dir, hint
                        ),
                    )
                )
            elif provider_name == "responsivevoice":
                providers.append(
                    (
                        "responsivevoice",
                        lambda hint=provider_hint: self._audio_responsivevoice(
                            text, language, output_dir, hint
                        ),
                    )
                )
            elif provider_name == "pyttsx3":
                providers.append(
                    (
                        "pyttsx3",
                        lambda hint=provider_hint: self._audio_pyttsx3(
                            text, output_dir, hint
                        ),
                    )
                )
        if not providers:
            return ProviderResult(value=None, provider_name="none", elapsed_ms=0, error="no providers")
        return self._fallback(providers)

    def ipa(self, word: str, language: str, allow_ai: bool = True) -> ProviderResult:
        if not allow_ai:
            return ProviderResult(value=None, provider_name="ai", elapsed_ms=0, error="ai_budget_exceeded")
        providers = [
            ("ai", lambda: self._ipa_ai(word, language)),
        ]
        return self._fallback(providers)

    def phonetic_spelling(self, ipa: str, language: str, allow_ai: bool = True) -> ProviderResult:
        if not allow_ai:
            return ProviderResult(value=None, provider_name="ai", elapsed_ms=0, error="ai_budget_exceeded")
        return self._wrap("ai", lambda: self._phonetic_spelling_ai(ipa, language))

    def _fallback(self, providers: list[tuple[str, Callable[[], str | None]]]) -> ProviderResult:
        last_result: ProviderResult | None = None
        fallback_errors: dict[str, str] = {}
        for name, fn in providers:
            result = self._wrap(name, fn)
            if result.value:
                if fallback_errors:
                    result.fallback_errors = fallback_errors
                return result
            if result.error:
                fallback_errors[name] = result.error
            last_result = result
        if last_result:
            if fallback_errors:
                last_result.fallback_errors = fallback_errors
            return last_result
        return ProviderResult(value=None, provider_name="none", elapsed_ms=0, error="no providers")

    def _definition_wordnet(self, word: str, language: str) -> str | None:
        if language != "en" or wordnet is None:
            return None
        try:
            try:
                wordnet.synsets("test")
            except LookupError:
                if nltk:
                    nltk.download("wordnet", quiet=True)
        except Exception:
            return None
        synsets = wordnet.synsets(word)
        if not synsets:
            return None
        return synsets[0].definition()

    def _definition_wiktionary(self, word: str, language: str) -> str | None:
        lang_name = LANG_CODE_TO_NAME.get(language, "English")
        url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{quote(word)}"
        resp = self._session.get(url, timeout=self.timeout_sec)
        if resp.status_code != 200:
            return None
        data = resp.json()
        entries = data.get(lang_name)
        if not entries:
            return None
        definitions = entries[0].get("definitions")
        if not definitions:
            return None
        return definitions[0].get("definition")

    def _definition_dictionaryapi(self, word: str, language: str) -> str | None:
        if language != "en":
            return None
        url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word)}"
        resp = self._session.get(url, timeout=self.timeout_sec)
        if resp.status_code != 200:
            return None
        payload = resp.json()
        for entry in payload:
            meanings = entry.get("meanings") or []
            for meaning in meanings:
                definitions = meaning.get("definitions") or []
                if definitions:
                    return definitions[0].get("definition")
        return None

    def _translate_google(self, text: str, src: str, dest: str) -> str | None:
        if not self._translator:
            return None
        result = self._translator.translate(text, src=src, dest=dest)
        return result.text

    def _translate_deepl(self, text: str, src: str, dest: str) -> str | None:
        api_key = self.config.get("providers", {}).get("deepl", {}).get("api_key")
        endpoint = self.config.get("providers", {}).get("deepl", {}).get("endpoint")
        if not api_key or not endpoint:
            return None
        payload = {
            "auth_key": api_key,
            "text": text,
            "source_lang": src.upper(),
            "target_lang": dest.upper(),
        }
        resp = self._session.post(endpoint, data=payload, timeout=self.timeout_sec)
        if resp.status_code != 200:
            return None
        data = resp.json()
        translations = data.get("translations")
        if not translations:
            return None
        return translations[0].get("text")

    def _translate_libre(self, text: str, src: str, dest: str) -> str | None:
        config = self.config.get("providers", {}).get("libretranslate", {})
        endpoint = config.get("endpoint")
        api_key = config.get("api_key")
        enabled = config.get("enabled", False)
        # Avoid slow unauthenticated public endpoints unless explicitly enabled.
        if not endpoint or (not enabled and not api_key):
            return None
        payload = {
            "q": text,
            "source": src,
            "target": dest,
            "format": "text",
        }
        if api_key:
            payload["api_key"] = api_key
        resp = self._session.post(endpoint, data=payload, timeout=self.timeout_sec)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data.get("translatedText")

    def _sentence_tatoeba(self, word: str, language: str) -> str | None:
        endpoint = self.config.get("providers", {}).get("tatoeba", {}).get("endpoint")
        if not endpoint:
            return None
        params = {
            "query": word,
            "from": language,
            "sort": "relevance",
            "limit": 20,
        }
        resp = self._session.get(endpoint, params=params, timeout=self.timeout_sec)
        if resp.status_code != 200:
            return None
        data = resp.json()
        results = data.get("results") or []
        if not results:
            return None
        word_lower = word.lower()
        candidates: list[str] = []
        for item in results:
            sentence = (item.get("text") or "").strip()
            if not sentence:
                continue
            if word_lower not in sentence.lower():
                continue
            candidates.append(sentence)
        if not candidates:
            return None
        return _best_sentence(candidates, word, language)

    def _sentence_wordincontext(self, word: str, language: str) -> str | None:
        # Placeholder for paid API; return None to trigger fallback.
        _ = (word, language)
        return None

    def _audio_gtts(self, text: str, language: str, output_dir: str | Path, filename_hint: str) -> str | None:
        ensure_dir(output_dir)
        safe_name = _safe_filename(filename_hint)
        path = Path(output_dir) / f"{safe_name}.mp3"
        tts = gTTS(text=text, lang=language)
        tts.save(str(path))
        return str(path)

    def _audio_responsivevoice(self, text: str, language: str, output_dir: str | Path, filename_hint: str) -> str | None:
        config = self.config.get("providers", {}).get("responsivevoice", {})
        api_key = config.get("api_key")
        endpoint = config.get("endpoint")
        if not api_key or not endpoint:
            return None
        params = {
            "key": api_key,
            "src": text,
            "hl": language,
        }
        resp = self._session.get(endpoint, params=params, timeout=self.timeout_sec)
        if resp.status_code != 200:
            return None
        ensure_dir(output_dir)
        safe_name = _safe_filename(filename_hint)
        path = Path(output_dir) / f"{safe_name}.mp3"
        path.write_bytes(resp.content)
        return str(path)

    def _audio_pyttsx3(self, text: str, output_dir: str | Path, filename_hint: str) -> str | None:
        if pyttsx3 is None:
            return None
        ensure_dir(output_dir)
        safe_name = _safe_filename(filename_hint)
        path = Path(output_dir) / f"{safe_name}.wav"
        engine = pyttsx3.init()
        engine.save_to_file(text, str(path))
        engine.runAndWait()
        return str(path)

    def _audio_azure_tts(
        self,
        text: str,
        language: str,
        output_dir: str | Path,
        filename_hint: str,
        voice: str | None = None,
    ) -> str | None:
        config = self.config.get("providers", {}).get("azure_tts", {})
        api_key_env = config.get("api_key_env") or "AZURE_TTS_KEY"
        region_env = config.get("region_env") or "AZURE_TTS_REGION"
        api_key = config.get("api_key") or _resolve_env_value(api_key_env)
        region = config.get("region") or _resolve_env_value(region_env)
        endpoint = config.get("endpoint") or (
            f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1" if region else None
        )
        voice_map = config.get("voice_map") or {}
        voice_name = voice or voice_map.get(language) or config.get("voice")
        if not api_key:
            raise ProviderError("azure_tts missing api_key")
        if not endpoint:
            raise ProviderError("azure_tts missing endpoint or region")
        if not voice_name:
            raise ProviderError("azure_tts missing voice for language")
        output_format = config.get("output_format") or "audio-16khz-32kbitrate-mono-mp3"
        locale = _voice_locale(voice_name) or language
        ssml = (
            f"<speak version='1.0' xml:lang='{locale}'>"
            f"<voice name='{voice_name}'>{xml_escape(text)}</voice></speak>"
        )
        headers = {
            "Ocp-Apim-Subscription-Key": api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": output_format,
            "User-Agent": "ankideck-generator",
        }
        resp = self._session.post(endpoint, data=ssml.encode("utf-8"), headers=headers, timeout=self.timeout_sec)
        if resp.status_code != 200:
            raise ProviderError(f"azure_tts HTTP {resp.status_code}: {resp.text[:200]}")
        ensure_dir(output_dir)
        safe_name = _safe_filename(filename_hint)
        ext = _audio_extension_from_format(output_format)
        path = Path(output_dir) / f"{safe_name}.{ext}"
        path.write_bytes(resp.content)
        return str(path)

    def _audio_elevenlabs(
        self,
        text: str,
        language: str,
        output_dir: str | Path,
        filename_hint: str,
        voice_gender_preference: str | None = None,
    ) -> str | None:
        _ = language
        config = self.config.get("providers", {}).get("elevenlabs", {})
        api_key_env = config.get("api_key_env") or "ELEVENLABS_API_KEY"
        api_key = config.get("api_key") or _resolve_env_value(api_key_env)
        if not api_key:
            raise ProviderError("elevenlabs missing api_key")
        voice_id = config.get("voice_id") or ""
        voice_name = config.get("voice_name") or ""
        gender_pref = voice_gender_preference or config.get("voice_gender_preference") or ""
        if not voice_id:
            voice_id = self._resolve_elevenlabs_voice_id(api_key, voice_name, gender_pref)
        if not voice_id:
            raise ProviderError("elevenlabs voice_id not found")
        model_id = config.get("model_id") or "eleven_multilingual_v2"
        endpoint = config.get("endpoint") or "https://api.elevenlabs.io/v1/text-to-speech"
        output_format = config.get("output_format") or ""
        url = endpoint.rstrip("/") + f"/{voice_id}"
        if output_format:
            url = f"{url}?output_format={quote(str(output_format))}"
        headers = {
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        payload = {
            "text": text,
            "model_id": model_id,
        }
        resp = self._session.post(url, json=payload, headers=headers, timeout=self.timeout_sec)
        if resp.status_code != 200:
            raise ProviderError(f"elevenlabs HTTP {resp.status_code}: {resp.text[:200]}")
        ensure_dir(output_dir)
        safe_name = _safe_filename(filename_hint)
        ext = _audio_extension_from_format(output_format) or "mp3"
        path = Path(output_dir) / f"{safe_name}.{ext}"
        path.write_bytes(resp.content)
        return str(path)

    def _resolve_elevenlabs_voice_id(
        self, api_key: str, voice_name: str, gender_preference: str
    ) -> str | None:
        cache_key = (voice_name or "").strip().lower() or f"gender:{gender_preference.lower()}"
        cached = self._elevenlabs_voice_cache.get(cache_key)
        if cached:
            return cached
        voices = self._elevenlabs_voices or self._fetch_elevenlabs_voices(api_key)
        self._elevenlabs_voices = voices
        if not voices:
            return None
        if voice_name:
            for voice in voices:
                if str(voice.get("name", "")).strip().lower() == voice_name.strip().lower():
                    voice_id = voice.get("voice_id")
                    if voice_id:
                        self._elevenlabs_voice_cache[cache_key] = voice_id
                        return voice_id
        gender = gender_preference.strip().lower()
        if gender:
            for voice in voices:
                labels = voice.get("labels") or {}
                if str(labels.get("gender", "")).strip().lower() == gender:
                    voice_id = voice.get("voice_id")
                    if voice_id:
                        self._elevenlabs_voice_cache[cache_key] = voice_id
                        return voice_id
        fallback = voices[0].get("voice_id")
        if fallback:
            self._elevenlabs_voice_cache[cache_key] = fallback
        return fallback

    def _fetch_elevenlabs_voices(self, api_key: str) -> list[dict]:
        config = self.config.get("providers", {}).get("elevenlabs", {})
        endpoint = config.get("voices_endpoint") or "https://api.elevenlabs.io/v1/voices"
        headers = {"xi-api-key": api_key}
        resp = self._session.get(endpoint, headers=headers, timeout=self.timeout_sec)
        if resp.status_code != 200:
            raise ProviderError(f"elevenlabs voices HTTP {resp.status_code}: {resp.text[:200]}")
        data = resp.json()
        voices = data.get("voices")
        return voices if isinstance(voices, list) else []

    def _ai_request(self, system_prompt: str, user_prompt: str, first_line_only: bool = True) -> str | None:
        last_error: str | None = None
        self._ai_request_count += 1
        for provider_name in self._ai_providers:
            profile = self._ai_config.get(provider_name, {})
            endpoint = profile.get("endpoint") or self._ai_config.get("endpoint")
            models = (
                profile.get("models")
                or profile.get("model")
                or self._ai_config.get("models")
                or self._ai_config.get("model")
            )
            api_keys = self._resolve_api_keys(profile)
            if not endpoint or not models or not api_keys:
                continue
            model_list = models if isinstance(models, list) else [models]
            if len(model_list) > 1:
                offset = self._ai_request_count % len(model_list)
                model_list = model_list[offset:] + model_list[:offset]
            for api_key in api_keys:
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                extra_headers = profile.get("headers") or {}
                if isinstance(extra_headers, dict):
                    headers.update({str(k): str(v) for k, v in extra_headers.items() if v is not None})
                for model in model_list:
                    payload = {
                        "model": model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": self._ai_config.get("temperature", 0.4),
                    }
                    resp = self._session.post(endpoint, json=payload, headers=headers, timeout=self.timeout_sec)
                    if resp.status_code != 200:
                        last_error = f"{provider_name} HTTP {resp.status_code}: {resp.text[:200]}"
                        continue
                    data = resp.json()
                    choices = data.get("choices") or []
                    if not choices:
                        last_error = f"{provider_name} empty choices"
                        continue
                    message = choices[0].get("message") or {}
                    content = message.get("content") or ""
                    text = _first_line(content) if first_line_only else str(content).strip()
                    if text:
                        return text
        if last_error:
            raise ProviderError(last_error)
        return None

    def _resolve_api_keys(self, profile: dict) -> list[str]:
        keys: list[str] = []
        profile_keys = profile.get("api_keys")
        if isinstance(profile_keys, list):
            keys.extend([k for k in profile_keys if k])
        profile_key_envs = profile.get("api_key_envs")
        if isinstance(profile_key_envs, list):
            for env_name in profile_key_envs:
                if env_name:
                    value = os.environ.get(env_name)
                    if value:
                        keys.append(value)

        api_key = profile.get("api_key") or self._ai_config.get("api_key")
        if api_key:
            keys.append(api_key)

        api_key_env = profile.get("api_key_env") or self._ai_config.get("api_key_env")
        if api_key_env:
            value = os.environ.get(api_key_env)
            if value:
                keys.append(value)

        return [k.strip() for k in keys if k.strip()]

    def _sentence_ai(self, word: str, language: str) -> str | None:
        system = (
            "You generate natural, simple example sentences for language learners. "
            "Return only one sentence, no quotes, no extra text."
        )
        user = (
            f"Language: {language}. "
            f"Create one natural everyday sentence with 5 to 25 words that includes the word '{word}'. "
            "Avoid proper nouns, avoid idioms, and keep it clear and simple."
        )
        text = self._ai_request(system, user)
        if not text:
            return None
        lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
        return _best_sentence(lines, word, language)

    def _definition_ai(self, word: str, language: str) -> str | None:
        system = (
            "You provide concise dictionary-style definitions. "
            "Return exactly one definition, no examples."
        )
        user = (
            f"Language: {language}. Define the word '{word}' in the same language. "
            "Return 6-10 words. If you know POS, prefix noun/verb/adjective/adverb."
        )
        return self._ai_request(system, user)

    def _translate_ai(self, text: str, src: str, dest: str) -> str | None:
        system = "You translate text accurately. Return only the translation."
        user = f"Translate from {src} to {dest}: {text}"
        return self._ai_request(system, user)

    def _ipa_ai(self, word: str, language: str) -> str | None:
        system = "You provide IPA transcriptions. Return only the IPA symbols."
        user = f"Give IPA for the word '{word}' in language '{language}'."
        return self._ai_request(system, user)

    def _phonetic_spelling_ai(self, ipa: str, language: str) -> str | None:
        system = (
            "You convert IPA into a simple, readable pronunciation guide for learners. "
            "Use Latin letters and hyphens if helpful. Return only the pronunciation, no IPA, no quotes."
        )
        user = f"Language: {language}. IPA: {ipa}"
        return self._ai_request(system, user)


def _safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned[:80] if len(cleaned) > 80 else cleaned


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0].strip() if text else ""


def _extract_json_payload(text: str) -> Any | None:
    candidate = text.strip()
    if not candidate:
        return None
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        candidate = fenced.group(1).strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        start_obj = candidate.find("{")
        start_arr = candidate.find("[")
        starts = [index for index in (start_obj, start_arr) if index >= 0]
        if not starts:
            return None
        start = min(starts)
        cropped = candidate[start:].strip()
        try:
            return json.loads(cropped)
        except json.JSONDecodeError:
            return None


def _best_sentence(candidates: list[str], focus: str, language: str) -> str | None:
    if not candidates:
        return None
    scored = [(score_sentence(sent, focus, language), sent) for sent in candidates]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_sentence = scored[0]
    return best_sentence if best_score > 0 else None


def _normalize_provider_order(value: list[str] | str | None) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    return [str(item).strip() for item in value if str(item).strip()]


def _resolve_env_value(name: str | None) -> str | None:
    if not name:
        return None
    value = os.environ.get(name)
    return value if value else None


def _voice_locale(voice_name: str) -> str | None:
    parts = voice_name.split("-")
    if len(parts) >= 2:
        return f"{parts[0]}-{parts[1]}"
    return None


def _audio_extension_from_format(value: str | None) -> str:
    if not value:
        return "mp3"
    text = str(value).lower()
    if "wav" in text or "riff" in text or "pcm" in text:
        return "wav"
    if "ogg" in text:
        return "ogg"
    if "opus" in text:
        return "opus"
    if "mp3" in text or "mpeg" in text:
        return "mp3"
    return "mp3"
