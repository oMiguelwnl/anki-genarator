from types import SimpleNamespace

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

    monkeypatch.setattr(requests, "get", fake_get)

    result = provider.definition("hello", "en")
    assert result.value == "a greeting"


def test_translation_fallback_libre(monkeypatch):
    config = {
        "providers": {
            "libretranslate": {"endpoint": "https://libretranslate.test/translate"}
        }
    }
    provider = ProviderManager(config, timeout_sec=1, retries=0)
    monkeypatch.setattr(provider, "_translate_google", lambda *args, **kwargs: None)
    monkeypatch.setattr(provider, "_translate_deepl", lambda *args, **kwargs: None)

    def fake_post(url, data=None, timeout=None):
        class FakeResponse:
            status_code = 200

            def json(self):
                return {"translatedText": "hello"}

        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)
    result = provider.translation("hola", "es", "en")
    assert result.value == "hello"
