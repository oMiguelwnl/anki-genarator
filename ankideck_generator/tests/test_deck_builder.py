from pathlib import Path
import json

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


def _ru_run_config(tmp_path: Path, mode: str = "test", level_size: int = 2) -> RunConfig:
    return RunConfig(
        language="ru",
        mode=mode,
        interactive=False,
        output_path=str(tmp_path / f"deck-{mode}.apkg"),
        resume=False,
        level_size=level_size,
        target_translation="en",
        wordfreq_language="ru",
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

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai)
            self.definition_language = definition_language or ""
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def sentence(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result(f"Hoy me siento {word} en casa.")

        def sentence_web(self, word, language):
            _ = (word, language)
            return Result(f"Hoy me siento {word} en casa.", provider_name="tatoeba")

        def translation_ai(self, text, src, dest):
            _ = (src, dest)
            return Result("I feel good today.")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            return Result("I feel good today.", provider_name="googletrans")

        def sentence_ai(self, word, language):
            _ = (word, language)
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


def test_process_word_retries_sentence_ai_before_web(tmp_path: Path) -> None:
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

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def sentence_ai(self, word, language):
            _ = (word, language)
            self.sentence_ai_calls += 1
            if self.sentence_ai_calls == 1:
                return Result("", error="empty result")
            return Result("Hoy me siento bien en casa.")

        def sentence_web(self, word, language):
            _ = (word, language)
            return Result("Hoy me siento bien en casa.", provider_name="tatoeba")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
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
    assert providers.sentence_ai_calls == 2


def test_build_russian_respects_test_and_full_inventory_size(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run_test = _ru_run_config(tmp_path, mode="test", level_size=2)
    run_full = _ru_run_config(tmp_path, mode="full", level_size=1)
    inventory = [
        {"spellings": "ц", "ipa": "/ts/", "example_word": "цирк"},
        {"spellings": "ж", "ipa": "/ʐ/", "example_word": "жук"},
        {"spellings": "ш", "ipa": "/ʂ/", "example_word": "школа"},
    ]

    monkeypatch.setattr(builder, "_load_russian_inventory", lambda *args, **kwargs: inventory)

    def fake_process_russian_entry(*args, **kwargs):
        entry = kwargs["entry"]
        index = kwargs["index"]
        card = CardData(
            focus=entry["spellings"],
            index=index,
            ipa=entry["ipa"],
            sentence=f"Это предложение с словом {entry['example_word']}.",
            translation="This is a sentence.",
            word_audio="[sound:ru_word.mp3]",
            sentence_audio="[sound:ru_sentence.mp3]",
            spellings=entry["spellings"],
            example_word=entry["example_word"],
            word_translation="test",
            letter_audio="[sound:ru_letter.mp3]",
            level=1,
            language="ru",
        )
        return card, LogRecord(focus=entry["spellings"], level=1, status="accepted")

    monkeypatch.setattr(builder, "_process_russian_entry", fake_process_russian_entry)

    cards_test, _ = builder.build(run_test)
    assert len(cards_test) == 2
    assert [card.index for card in cards_test] == [1, 2]

    cards_full, _ = builder.build(run_full)
    assert len(cards_full) == 3
    assert [card.index for card in cards_full] == [1, 2, 3]


def test_load_russian_inventory_uses_cache_after_first_generation(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _ru_run_config(tmp_path)

    class FakeCache:
        def __init__(self):
            self.data: dict[tuple[str, str], object] = {}

        def get(self, kind, key):
            return self.data.get((kind, key))

        def set(self, kind, key, value):
            self.data[(kind, key)] = value

    class Result:
        def __init__(self, value: str, provider_name: str = "ai"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        calls = 0

        def russian_phoneme_inventory(self, *_args, **_kwargs):
            self.calls += 1
            payload = [
                {"spellings": "ц", "ipa": "/ts/", "example_word": "цирк"},
                {"spellings": "ц", "ipa": "/ts/", "example_word": "цепь"},
                {"spellings": "x", "ipa": "/x/", "example_word": "test"},
            ]
            return Result(json.dumps(payload, ensure_ascii=False))

    cache = FakeCache()
    providers = FakeProviders()

    first = builder._load_russian_inventory(cache, providers, run)
    second = builder._load_russian_inventory(cache, providers, run)

    assert providers.calls == 1
    assert first == second
    assert first == [{"spellings": "ц", "ipa": "/ts/", "example_word": "цирк"}]


def test_process_russian_entry_populates_extra_fields_and_audio(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _ru_run_config(tmp_path)
    ctx = ValidationContext()
    media_files: list[str] = []

    class FakeCache:
        def __init__(self):
            self.data: dict[tuple[str, str], str] = {}

        def get(self, kind, key):
            return self.data.get((kind, key))

        def set(self, kind, key, value):
            self.data[(kind, key)] = value

    class Result:
        def __init__(self, value: str, provider_name: str = "ai", error: str | None = None):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = error

    class FakeProviders:
        def translation_web(self, text, src, dest):
            _ = (src, dest)
            if " " not in text:
                return Result("circus", provider_name="googletrans")
            return Result("The circus has zirconium cylinders.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("fallback translation")

        def sentence_ai(self, word, language):
            _ = language
            return Result(f"В цирке есть цилиндры и слово {word}.")

        def sentence_web(self, word, language):
            _ = (word, language)
            return Result("unused", provider_name="tatoeba")

        def audio(self, text, language, output_dir, filename_hint):
            _ = (text, language, output_dir)
            path = tmp_path / f"{filename_hint}.mp3"
            path.write_bytes(b"fake")
            return Result(str(path), provider_name="gtts")

    entry = {"spellings": "ц", "ipa": "/ts/", "example_word": "цирк"}
    card, _log = builder._process_russian_entry(
        entry=entry,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=media_files,
    )

    assert card is not None
    assert card.spellings == "ц"
    assert card.example_word == "цирк"
    assert card.word_translation == "circus"
    assert card.letter_audio.startswith("[sound:")
    assert card.word_audio.startswith("[sound:")
    assert card.sentence_audio.startswith("[sound:")
    assert len(media_files) == 3
