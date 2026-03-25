import requests

from ankideck_generator.core.providers import ProviderManager


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


def test_wrap_does_not_retry_deterministic_empty_result() -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=3)
    calls = {"count": 0}

    def returns_empty():
        calls["count"] += 1
        return ""

    result = provider._wrap("tatoeba", returns_empty)
    assert result.value is None
    assert calls["count"] == 1


def test_wrap_disables_provider_after_repeated_timeouts() -> None:
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    calls = {"count": 0}

    def timeout_fn():
        calls["count"] += 1
        raise requests.exceptions.ReadTimeout("timed out")

    provider._wrap("tatoeba", timeout_fn)
    provider._wrap("tatoeba", timeout_fn)
    provider._wrap("tatoeba", timeout_fn)

    result = provider._wrap("tatoeba", timeout_fn)
    assert result.error == "provider_disabled"
    assert calls["count"] == 3
