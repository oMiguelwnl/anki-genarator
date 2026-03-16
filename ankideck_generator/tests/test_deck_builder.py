from pathlib import Path

from ankideck_generator.core.deck_builder import DeckBuilder
from ankideck_generator.core.models import CardData, LogRecord, RunConfig
from ankideck_generator.core.validators import ValidationContext


def _run_config(tmp_path: Path) -> RunConfig:
    return RunConfig(
        language="es",
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        wordfreq_language="es",
        timeout_sec=1,
        retries=0,
        seed=1,
        cache_path=str(tmp_path / "cache"),
        autosave_every=1,
    )


def test_build_assigns_sequential_sortindex(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)

    monkeypatch.setattr(builder, "_prepare_levels", lambda *args, **kwargs: {1: ["uno"], 2: ["dos"], 3: ["tres"]})

    def fake_process_word(*args, **kwargs):
        word = kwargs["word"]
        level = kwargs["level"]
        card = CardData(
            focus=word,
            index=0,
            ipa=f"/{word}/",
            definition="Definicao simples para aprendizagem.",
            sentence=f"Esta frase usa {word} com contexto claro.",
            translation=f"This sentence uses {word} with clear context.",
            level=level,
            language="es",
        )
        log_record = LogRecord(focus=word, level=level, status="accepted")
        return card, log_record

    monkeypatch.setattr(builder, "_process_word", fake_process_word)

    cards, _ = builder.build(run)
    assert [card.index for card in cards] == [1, 2, 3]
    assert all(card.index > 0 for card in cards)


def test_process_word_uses_source_language_for_definition(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "ai"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        definition_language = ""
        translation_calls: list[str] = []

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai)
            self.definition_language = definition_language or ""
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("zhee-VYA")

        def sentence(self, word, language, allow_ai=True, level=None):
            _ = (word, language, allow_ai, level)
            return Result(f"Hoy me siento {word} en casa.")

        def sentence_web(self, word, language, level=None):
            _ = (word, language, level)
            return Result(f"Hoy me siento {word} en casa.", provider_name="tatoeba")

        def translation_ai(self, text, src, dest):
            _ = (src, dest)
            return Result("I feel good today.")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            self.translation_calls.append(text)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good today.", provider_name="googletrans")

        def sentence_ai(self, word, language, level=None):
            _ = (word, language, level)
            return Result(f"Hoy me siento {word} en casa.")

    providers = FakeProviders()
    media_files: list[str] = []

    card, _log = builder._process_word(
        word="bien",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=providers,
        ctx=ctx,
        media_files=media_files,
    )

    assert card is not None
    assert providers.definition_language == "es"
    assert card.definition == "adjective: in good condition or quality."


def test_process_word_retries_sentence_web_before_ai(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "ai", error: str | None = None):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = error

    class FakeProviders:
        sentence_ai_calls = 0
        sentence_web_calls = 0

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("zhee-VYA")

        def sentence_ai(self, word, language, level=None):
            _ = (word, language, level)
            self.sentence_ai_calls += 1
            if self.sentence_ai_calls == 1:
                return Result("", error="empty result")
            return Result("Hoy me siento bien en casa.")

        def sentence_web(self, word, language, level=None):
            _ = (word, language, level)
            self.sentence_web_calls += 1
            return Result("", provider_name="tatoeba", error="empty result")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

    providers = FakeProviders()
    card, _log = builder._process_word(
        word="bien",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=providers,
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert providers.sentence_web_calls == 1
    assert providers.sentence_ai_calls == 2


