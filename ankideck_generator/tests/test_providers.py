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


def test_sentence_prefers_ai_then_web(monkeypatch):
    provider = ProviderManager({"providers": {}}, timeout_sec=1, retries=0)
    calls: list[str] = []

    monkeypatch.setattr(provider, "_sentence_ai", lambda *args, **kwargs: calls.append("ai") or None)
    monkeypatch.setattr(provider, "_sentence_tatoeba", lambda *args, **kwargs: calls.append("tatoeba") or "ok")
    monkeypatch.setattr(provider, "_sentence_wordincontext", lambda *args, **kwargs: calls.append("wordincontext") or None)

    result = provider.sentence("hola", "es", allow_ai=True)
    assert result.value == "ok"
    assert calls[:2] == ["ai", "tatoeba"]


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
