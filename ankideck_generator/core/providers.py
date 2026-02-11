from __future__ import annotations

import time
from pathlib import Path
import os
from typing import Callable
from urllib.parse import quote

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
        self._translator = Translator() if Translator else None
        self._ai_config = (config or {}).get("providers", {}).get("ai", {}) if config else {}
        providers = self._ai_config.get("providers") or self._ai_config.get("provider") or "openrouter"
        if isinstance(providers, list):
            self._ai_providers = providers
        else:
            self._ai_providers = [str(providers)]

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

        providers = [
            ("wordnet", lambda: self._definition_wordnet(word, language)),
            ("wiktionary", lambda: self._definition_wiktionary(word, language)),
            ("dictionaryapi", lambda: self._definition_dictionaryapi(word, language)),
        ]
        if allow_ai:
            providers.append(("ai", lambda: self._definition_ai(word, language)))
        return self._fallback(providers)

    def translation(self, text: str, src: str, dest: str, allow_ai: bool = True) -> ProviderResult:
        providers = [
            ("googletrans", lambda: self._translate_google(text, src, dest)),
            ("deepl", lambda: self._translate_deepl(text, src, dest)),
            ("libretranslate", lambda: self._translate_libre(text, src, dest)),
        ]
        if allow_ai:
            providers.append(("ai", lambda: self._translate_ai(text, src, dest)))
        return self._fallback(providers)

    def sentence(self, word: str, language: str, allow_ai: bool = True) -> ProviderResult:
        providers = [
            ("tatoeba", lambda: self._sentence_tatoeba(word, language)),
            ("wordincontext", lambda: self._sentence_wordincontext(word, language)),
        ]
        if allow_ai:
            providers.append(("ai", lambda: self._sentence_ai(word, language)))
        return self._fallback(providers)

    def sentence_ai(self, word: str, language: str) -> ProviderResult:
        return self._wrap("ai", lambda: self._sentence_ai(word, language))

    def audio(self, text: str, language: str, output_dir: str | Path, filename_hint: str) -> ProviderResult:
        providers = [
            ("gtts", lambda: self._audio_gtts(text, language, output_dir, filename_hint)),
            ("responsivevoice", lambda: self._audio_responsivevoice(text, language, output_dir, filename_hint)),
            ("pyttsx3", lambda: self._audio_pyttsx3(text, output_dir, filename_hint)),
        ]
        return self._fallback(providers)

    def ipa(self, word: str, language: str, allow_ai: bool = True) -> ProviderResult:
        if not allow_ai:
            return ProviderResult(value=None, provider_name="ai", elapsed_ms=0, error="ai_budget_exceeded")
        providers = [
            ("ai", lambda: self._ipa_ai(word, language)),
        ]
        return self._fallback(providers)

    def _fallback(self, providers: list[tuple[str, Callable[[], str | None]]]) -> ProviderResult:
        last_result: ProviderResult | None = None
        for name, fn in providers:
            result = self._wrap(name, fn)
            if result.value:
                return result
            last_result = result
        return last_result or ProviderResult(value=None, provider_name="none", elapsed_ms=0, error="no providers")

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
        resp = requests.get(url, timeout=self.timeout_sec)
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
        resp = requests.get(url, timeout=self.timeout_sec)
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
        resp = requests.post(endpoint, data=payload, timeout=self.timeout_sec)
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
        if not endpoint:
            return None
        payload = {
            "q": text,
            "source": src,
            "target": dest,
            "format": "text",
        }
        api_key = config.get("api_key")
        if api_key:
            payload["api_key"] = api_key
        resp = requests.post(endpoint, data=payload, timeout=self.timeout_sec)
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
        resp = requests.get(endpoint, params=params, timeout=self.timeout_sec)
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
        resp = requests.get(endpoint, params=params, timeout=self.timeout_sec)
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

    def _ai_request(self, system_prompt: str, user_prompt: str) -> str | None:
        last_error: str | None = None
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
                    resp = requests.post(endpoint, json=payload, headers=headers, timeout=self.timeout_sec)
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
                    text = _first_line(content)
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
            f"Create three natural everyday sentences (one per line) with 5 to 25 words that include the word '{word}'. "
            "Avoid proper nouns, avoid idioms, and keep it clear and simple."
        )
        text = self._ai_request(system, user)
        if not text:
            return None
        lines = [line.strip("- ").strip() for line in text.splitlines() if line.strip()]
        return _best_sentence(lines, word, language)

    def _definition_ai(self, word: str, language: str) -> str | None:
        system = "You provide concise dictionary-style definitions. Return only the definition."
        user = f"Language: {language}. Define the word '{word}' in the same language."
        return self._ai_request(system, user)

    def _translate_ai(self, text: str, src: str, dest: str) -> str | None:
        system = "You translate text accurately. Return only the translation."
        user = f"Translate from {src} to {dest}: {text}"
        return self._ai_request(system, user)

    def _ipa_ai(self, word: str, language: str) -> str | None:
        system = "You provide IPA transcriptions. Return only the IPA symbols."
        user = f"Give IPA for the word '{word}' in language '{language}'."
        return self._ai_request(system, user)


def _safe_filename(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned[:80] if len(cleaned) > 80 else cleaned


def _first_line(text: str) -> str:
    return text.strip().splitlines()[0].strip() if text else ""


def _best_sentence(candidates: list[str], focus: str, language: str) -> str | None:
    if not candidates:
        return None
    scored = [(score_sentence(sent, focus, language), sent) for sent in candidates]
    scored.sort(key=lambda item: item[0], reverse=True)
    best_score, best_sentence = scored[0]
    return best_sentence if best_score > 0 else None
