import json
from pathlib import Path
import requests
import time
from urllib.parse import quote

import pytest

import ankideck_generator.core.providers as providers_module
from ankideck_generator.core.models import LexicalReviewRequest, StructuredSentenceBatch
from ankideck_generator.core.providers import ProviderManager


def _fixture_text(name: str) -> str:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "ai_sentence_candidates"
        / name
    )
    return path.read_text(encoding="utf-8")


def test_definition_fallback_dictionaryapi(monkeypatch):
    config = {"providers": {}}
    provider = ProviderManager(config, timeout_sec=1, retries=0)

    monkeypatch.setattr(provider, "_definition_wordnet", lambda *args, **kwargs: None)
    monkeypatch.setattr(provider, "_definition_wiktionary", lambda *args, **kwargs: None)

    def fake_get(url, timeout=None, params=None):
        class FakeResponse:
            status_code = 200

            def json(self):
                if "dictionaryapi" in url:
                    return [
                        {"meanings": [{"definitions": [{"definition": "a greeting"}]}]}
                    ]
                return {}

        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)

    result = provider.definition("hello", "en")
    assert result.value == "a greeting"


def test_translation_fallback_libre(monkeypatch):
    config = {
        "providers": {
            "libretranslate": {"endpoint": "https://libretranslate.test/translate", "enabled": True}
        }
    }
    provider = ProviderManager(config, timeout_sec=1, retries=0)
    monkeypatch.setattr(provider, "_translate_ai", lambda *args, **kwargs: None)
    monkeypatch.setattr(provider, "_translate_google", lambda *args, **kwargs: None)
    monkeypatch.setattr(provider, "_translate_deepl", lambda *args, **kwargs: None)

    def fake_post(url, data=None, timeout=None):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {"translatedText": "hello"}

        return FakeResponse()

    monkeypatch.setattr(provider._session, "post", fake_post)
    result = provider.translation("hola", "es", "en")
    assert result.value == "hello"


def test_sentence_prefers_web_then_ai(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    calls: list[str] = []

    monkeypatch.setattr(provider, "_sentence_ai", lambda *args, **kwargs: calls.append("ai") or None)
    monkeypatch.setattr(provider, "_sentence_tatoeba", lambda *args, **kwargs: calls.append("tatoeba") or "ok")
    monkeypatch.setattr(provider, "_sentence_wordincontext", lambda *args, **kwargs: calls.append("wordincontext") or None)

    result = provider.sentence("hola", "es", allow_ai=True)
    assert result.value == "ok"
    assert calls[:1] == ["tatoeba"]


def test_structured_sentence_batch_requires_exactly_three_candidates() -> None:
    payload = json.loads(_fixture_text("valid_batch.json"))
    StructuredSentenceBatch.model_validate(payload)

    payload["candidates"] = payload["candidates"][:2]
    with pytest.raises(Exception):
        StructuredSentenceBatch.model_validate(payload)


def test_sentence_ai_candidates_parses_fenced_json_fixture(monkeypatch) -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    payload = _fixture_text("valid_batch.json")

    monkeypatch.setattr(
        provider,
        "_ai_request",
        lambda *args, **kwargs: f"```json\n{payload}\n```",
    )

    result = provider.sentence_ai_candidates(
        "bien",
        "es",
        requested_pos="adjective",
        requested_sense="in good condition or quality",
        target_level=1,
    )

    assert result.error is None
    assert result.batch is not None
    assert len(result.batch.candidates) == 3
    assert result.batch.focus_word == "bien"


def test_sentence_ai_candidates_rejects_malformed_payload(monkeypatch) -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    payload = _fixture_text("malformed_batch.json")

    monkeypatch.setattr(
        provider,
        "_ai_request",
        lambda *args, **kwargs: payload,
    )

    result = provider.sentence_ai_candidates(
        "bien",
        "es",
        requested_pos="adjective",
        requested_sense="in good condition or quality",
        target_level=1,
    )

    assert result.batch is None
    assert result.error is not None
    assert "structured_sentence_validation_error" in result.error


def test_lexical_review_rejects_malformed_payload(monkeypatch) -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    request = LexicalReviewRequest(
        focus_word="banco",
        language="es",
        target_translation_language="en",
        accepted_sentence="Me senté en el banco del parque.",
        current_definition="financial institution",
        current_translation="bank",
        source_definition="bench in a park or public place",
        candidate_senses=[
            "financial institution",
            "bench in a park or public place",
        ],
    )

    monkeypatch.setattr(
        provider,
        "_ai_request",
        lambda *args, **kwargs: '{"verdict":"human_review"}',
    )

    result = provider.lexical_review(request)

    assert result.review is None
    assert result.error is not None
    assert "lexical_review_validation_error" in result.error


def test_translation_prefers_web_then_ai(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    calls: list[str] = []

    monkeypatch.setattr(provider, "_translate_google", lambda *args, **kwargs: calls.append("googletrans") or "ok")
    monkeypatch.setattr(provider, "_translate_deepl", lambda *args, **kwargs: calls.append("deepl") or None)
    monkeypatch.setattr(provider, "_translate_libre", lambda *args, **kwargs: calls.append("libretranslate") or None)
    monkeypatch.setattr(provider, "_translate_ai", lambda *args, **kwargs: calls.append("ai") or "ai-text")

    result = provider.translation("hola", "es", "en", allow_ai=True)
    assert result.value == "ok"
    assert calls == ["googletrans"]


def test_provider_manager_initializes_googletrans_with_timeout(monkeypatch):
    captured: dict[str, object] = {}

    class FakeTranslator:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

    monkeypatch.setattr(providers_module, "Translator", FakeTranslator)

    ProviderManager({"providers": {}}, timeout_sec=9, retries=0)
    assert captured["timeout"] == 9


def test_audio_gtts_passes_timeout(monkeypatch, tmp_path):
    provider = ProviderManager(
        {"providers": {}},
        timeout_sec=9,
        retries=0,
        timeout_overrides={"gtts": 7},
    )
    captured: dict[str, object] = {}

    class FakeGTTS:
        def __init__(self, *args, **kwargs):
            captured["timeout"] = kwargs.get("timeout")

        def save(self, target):
            captured["target"] = target
            tmp_path.joinpath("ok.mp3").write_bytes(b"audio")

    monkeypatch.setattr(providers_module, "gTTS", FakeGTTS)

    provider._audio_gtts("hola", "es", tmp_path, "sample")
    assert captured["timeout"] == 7


def test_audio_pyttsx3_times_out(monkeypatch, tmp_path):
    provider = ProviderManager(
        {"providers": {}},
        timeout_sec=1,
        retries=0,
        timeout_overrides={"pyttsx3": 1},
    )

    class SlowEngine:
        def save_to_file(self, text, path):
            _ = (text, path)

        def runAndWait(self):
            time.sleep(1.2)

        def stop(self):
            return None

    class FakePyttsx3:
        @staticmethod
        def init():
            return SlowEngine()

    monkeypatch.setattr(providers_module, "pyttsx3", FakePyttsx3)

    start = time.time()
    try:
        provider._audio_pyttsx3("hola", tmp_path, "sample")
    except Exception as exc:
        assert "timed out" in str(exc)
    else:
        raise AssertionError("pyttsx3 timeout should abort blocked synthesis")
    assert time.time() - start < 1.2


def test_definition_prefers_wiktionary_before_ai(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    calls: list[str] = []

    monkeypatch.setattr(
        provider,
        "_definition_wiktionary",
        lambda *args, **kwargs: calls.append("wiktionary") or "meaning from lexicon",
    )
    monkeypatch.setattr(
        provider,
        "_definition_wordnet",
        lambda *args, **kwargs: calls.append("wordnet") or None,
    )
    monkeypatch.setattr(
        provider,
        "_definition_dictionaryapi",
        lambda *args, **kwargs: calls.append("dictionaryapi") or None,
    )
    monkeypatch.setattr(
        provider,
        "_definition_ai",
        lambda *args, **kwargs: calls.append("ai") or "meaning from ai",
    )

    result = provider.definition("bonjour", "fr", allow_ai=True)
    assert result.value == "meaning from lexicon"
    assert calls == ["wiktionary"]


def test_word_exists_uses_wiktionary_bucket(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)

    def fake_get(url, timeout=None):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "French": [
                        {"definitions": [{"definition": "adjective: excluded"}]}
                    ]
                }

        _ = (url, timeout)
        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)
    result = provider.word_exists("exclus", "fr")
    assert result.value == "exclus"


def test_wiktionary_definition_adds_part_of_speech_and_prefers_semantic(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)

    def fake_get(url, timeout=None):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {
                    "fr": [
                        {
                            "partOfSpeech": "pronoun",
                            "definitions": [
                                {"definition": "plural of autre"},
                                {"definition": "all people or things in a group"},
                            ],
                        }
                    ]
                }

        _ = (url, timeout)
        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)
    result = provider.definition("tout", "fr", allow_ai=False)
    assert result.value == "pronoun: all people or things in a group"


def test_wiktionary_meta_definition_resolves_lemma_meaning_for_verbs(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)

    def fake_get(url, timeout=None):
        class FakeResponse:
            status_code = 200

            def json(self):
                if url.endswith("/" + quote("говорил")):
                    return {
                        "ru": [
                            {
                                "partOfSpeech": "verb",
                                "definitions": [
                                    {
                                        "definition": "masculine singular past indicative imperfective of говори́ть"
                                    }
                                ],
                            }
                        ]
                    }
                return {
                    "ru": [
                        {
                            "partOfSpeech": "verb",
                            "definitions": [
                                {"definition": "to speak, to talk"}
                            ],
                        }
                    ]
                }

        _ = timeout
        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)
    result = provider.definition("говорил", "ru", allow_ai=False)
    assert result.value == "verb: to speak, to talk, past tense, imperfective"


def test_wiktionary_meta_definition_uses_formof_lemma_for_nouns(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)

    def fake_get(url, timeout=None):
        class FakeResponse:
            status_code = 200

            def json(self):
                if url.endswith("/" + quote("управления")):
                    return {
                        "ru": [
                            {
                                "partOfSpeech": "noun",
                                "definitions": [
                                    {
                                        "definition": "genitive singular",
                                        "formOf": [{"word": "управление"}],
                                    }
                                ],
                            }
                        ]
                    }
                return {
                    "ru": [
                        {
                            "partOfSpeech": "noun",
                            "definitions": [
                                {"definition": "control, administration"}
                            ],
                        }
                    ]
                }

        _ = timeout
        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)
    result = provider.definition("управления", "ru", allow_ai=False)
    assert result.value == "noun: control, administration"


def test_definition_candidates_skips_ai_when_lexicon_candidates_exist(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)

    monkeypatch.setattr(
        provider,
        "_wiktionary_definitions",
        lambda *args, **kwargs: [
            "adjective: in good condition or quality",
            "adverb: well, satisfactorily",
        ],
    )
    monkeypatch.setattr(
        provider,
        "_definition_ai",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("definition AI should stay as fallback")
        ),
    )
    monkeypatch.setattr(
        provider,
        "_definition_from_context_ai",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("context definition AI should stay as fallback")
        ),
    )

    result = provider.definition_candidates(
        "bien",
        "es",
        allow_ai=True,
        definition_language="es",
        sentence="Hoy me siento bien en casa.",
    )

    values = [candidate.text for candidate in result.candidates]
    assert "adjective: in good condition or quality" in values
    assert "adverb: well, satisfactorily" in values


def test_definition_candidates_uses_context_ai_when_lexicon_is_empty(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)

    monkeypatch.setattr(provider, "_wiktionary_definitions", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        provider,
        "_definition_ai",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("direct definition AI should not run after context AI succeeds")
        ),
    )
    monkeypatch.setattr(
        provider,
        "_definition_from_context_ai",
        lambda *args, **kwargs: "adjective: fitting the example sentence context",
    )

    result = provider.definition_candidates(
        "bien",
        "es",
        allow_ai=True,
        definition_language="es",
        sentence="Hoy me siento bien en casa.",
    )

    values = [candidate.text for candidate in result.candidates]
    assert values == ["adjective: fitting the example sentence context"]


def test_wrap_does_not_retry_deterministic_empty_result() -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=3)
    calls = {"count": 0}

    def returns_empty():
        calls["count"] += 1
        return ""

    result = provider._wrap("tatoeba", returns_empty)
    assert result.value is None
    assert calls["count"] == 1


def test_wrap_retries_ai_empty_result() -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=2)
    calls = {"count": 0}

    def returns_empty_then_value():
        calls["count"] += 1
        if calls["count"] < 3:
            return ""
        return "ok"

    result = provider._wrap("ai", returns_empty_then_value)
    assert result.value == "ok"
    assert calls["count"] == 3


def test_wrap_disables_provider_after_repeated_timeouts() -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    calls = {"count": 0}

    def timeout_fn():
        calls["count"] += 1
        raise requests.exceptions.ReadTimeout("timed out")

    provider._wrap("responsivevoice", timeout_fn)
    provider._wrap("responsivevoice", timeout_fn)
    provider._wrap("responsivevoice", timeout_fn)

    result = provider._wrap("responsivevoice", timeout_fn)
    assert result.error == "provider_disabled"
    assert calls["count"] == 3


def test_wrap_does_not_disable_tatoeba_after_repeated_timeouts() -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    calls = {"count": 0}

    def timeout_fn():
        calls["count"] += 1
        raise requests.exceptions.ReadTimeout("timed out")

    provider._wrap("tatoeba", timeout_fn)
    provider._wrap("tatoeba", timeout_fn)
    provider._wrap("tatoeba", timeout_fn)

    result = provider._wrap("tatoeba", timeout_fn)
    assert result.error == "timed out"
    assert calls["count"] == 4


def test_sentence_tatoeba_uses_exact_query_and_pagination(monkeypatch) -> None:
    config = {
        "providers": {
            "tatoeba": {
                "endpoint": "https://tatoeba.test/api_v0/search",
                "exact_match": True,
                "native_only": True,
                "exclude_orphans": True,
                "exclude_unapproved": True,
                "max_pages": 2,
                "page_size": 2,
            }
        }
    }
    provider = ProviderManager(config, timeout_sec=1, retries=0)
    seen_params: list[dict[str, object]] = []

    def fake_get(url, params=None, timeout=None):
        _ = (url, timeout)
        seen_params.append(dict(params or {}))

        class FakeResponse:
            status_code = 200

            def json(self):
                if params.get("page") == 1:
                    return {
                        "results": [
                            {"text": "The category changes fast."},
                            {"text": "Another category appears here."},
                        ]
                    }
                return {"results": [{"text": "The cat sleeps here."}]}

        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)
    result = provider.sentence_web("cat", "en", min_words=3, max_words=6)

    assert result.value == "The cat sleeps here."
    assert seen_params[0]["query"] == "=cat"
    assert seen_params[0]["native"] == "yes"
    assert seen_params[0]["orphans"] == "no"
    assert seen_params[0]["unapproved"] == "no"
    assert seen_params[0]["page"] == 1
    assert seen_params[1]["page"] == 2


def test_sentence_tatoeba_relaxes_query_when_exact_is_not_strong(monkeypatch) -> None:
    config = {
        "providers": {
            "tatoeba": {
                "endpoint": "https://tatoeba.test/api_v0/search",
                "exact_match": True,
                "max_pages": 1,
                "page_size": 10,
            }
        }
    }
    provider = ProviderManager(config, timeout_sec=1, retries=0)
    seen_queries: list[str] = []

    def fake_get(url, params=None, timeout=None):
        _ = (url, timeout)
        seen_queries.append(str((params or {}).get("query", "")))

        class FakeResponse:
            status_code = 200

            def json(self):
                if params.get("query") == "=cat":
                    return {"results": [{"text": "The cat."}]}
                return {
                    "results": [
                        {"text": "The cat sleeps here."},
                        {"text": "The cat sleeps here."},
                    ]
                }

        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)
    result = provider.sentence_web_candidates("cat", "en", min_words=3, max_words=6)

    assert [candidate.text for candidate in result.candidates] == [
        "The cat sleeps here.",
        "The cat.",
    ]
    assert result.candidates[0].query_mode == "relaxed"
    assert seen_queries == ["=cat", "cat"]


def test_sentence_tatoeba_keeps_short_candidate_for_rewrite(monkeypatch) -> None:
    config = {
        "providers": {
            "tatoeba": {
                "endpoint": "https://tatoeba.test/api_v0/search",
                "exact_match": True,
                "max_pages": 1,
                "page_size": 10,
            }
        }
    }
    provider = ProviderManager(config, timeout_sec=1, retries=0)

    def fake_get(url, params=None, timeout=None):
        _ = (url, params, timeout)

        class FakeResponse:
            status_code = 200

            def json(self):
                return {"results": [{"text": "Когда праздник?"}]}

        return FakeResponse()

    monkeypatch.setattr(provider._session, "get", fake_get)
    result = provider.sentence_web_candidates("когда", "ru", min_words=5, max_words=7)

    assert [candidate.text for candidate in result.candidates] == ["Когда праздник?"]


def test_fallback_reports_provider_disabled_when_all_candidates_are_disabled() -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    provider._disabled_providers.update({"gtts", "responsivevoice"})

    result = provider._fallback(
        [
            ("gtts", lambda: "unused"),
            ("responsivevoice", lambda: "unused"),
        ]
    )

    assert result.error == "provider_disabled"
