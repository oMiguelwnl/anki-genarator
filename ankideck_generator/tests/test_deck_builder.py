from collections import Counter
from pathlib import Path
import time

import ankideck_generator.core.deck_builder as deck_builder_module
from ankideck_generator.core.deck_builder import (
    AudioTaskResult,
    DeckBuilder,
    TextTaskResult,
    _infer_discard_reason,
    _sentence_length_bounds,
)
from ankideck_generator.core.models import CardData, LogRecord, RunConfig
from ankideck_generator.core.validators import ValidationContext


def _run_config(tmp_path: Path, language: str = "es") -> RunConfig:
    return RunConfig(
        language=language,
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        wordfreq_language=language,
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


def test_build_continues_until_level_target_is_met(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.level_size = 2

    monkeypatch.setattr(
        builder,
        "_prepare_levels",
        lambda *args, **kwargs: {
            1: ["uno", "dos", "tres", "cuatro"],
            2: ["cinco", "seis", "siete", "ocho"],
            3: ["nueve", "diez", "once", "doce"],
        },
    )

    discard = {"uno", "cinco", "nueve"}

    def fake_process_word(*args, **kwargs):
        word = kwargs["word"]
        level = kwargs["level"]
        if word in discard:
            return None, LogRecord(
                focus=word,
                level=level,
                validations=["focus_not_in_lexicon"],
                status="discarded",
                discard_reason="focus_not_in_lexicon",
            )
        card = CardData(
            focus=word,
            index=0,
            ipa=f"/{word}/",
            definition="noun: useful sample definition for this card.",
            sentence=f"Esta frase usa {word} con contexto claro.",
            translation=f"This sentence uses {word} with clear context.",
            level=level,
            language="es",
        )
        return card, LogRecord(focus=word, level=level, status="accepted")

    monkeypatch.setattr(builder, "_process_word", fake_process_word)

    cards, _ = builder.build(run)
    assert len(cards) == 6
    assert [card.focus for card in cards] == ["dos", "tres", "seis", "siete", "diez", "once"]


def test_prepare_levels_preserves_frequency_order(monkeypatch, tmp_path: Path) -> None:
    _ = tmp_path
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    frequency_words = [f"mot{i}" for i in range(1, 40)]

    monkeypatch.setattr(deck_builder_module, "top_n_list", lambda language, total: frequency_words[:total])
    monkeypatch.setattr(
        deck_builder_module,
        "filter_frequent_words",
        lambda words, language, min_length=3, **kwargs: list(words),
    )

    levels = builder._prepare_levels("fr", level_size=2, seed=1, pool_multiplier=2)

    assert levels[1] == ["mot1", "mot2", "mot3", "mot4"]
    assert levels[2] == ["mot5", "mot6", "mot7", "mot8"]
    assert levels[3] == ["mot9", "mot10", "mot11", "mot12"]


def test_sentence_length_bounds_follow_level_defaults() -> None:
    assert _sentence_length_bounds({1: (2, 7), 2: (4, 10), 3: (6, 15)}, 1) == (2, 7)
    assert _sentence_length_bounds({1: (2, 7), 2: (4, 10), 3: (6, 15)}, 2) == (4, 10)
    assert _sentence_length_bounds({1: (2, 7), 2: (4, 10), 3: (6, 15)}, 3) == (6, 15)


def test_lexicon_zipf_fallback_accepts_high_frequency_words(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path, language="ru")
    run.wordfreq_language = "ru"
    run.lexicon_zipf_fallback_min = 3.0
    assert builder._lexicon_zipf_fallback_ok("дом", run) is True


def test_print_summary_includes_sentence_source_stats(tmp_path: Path, capsys) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))

    builder._print_summary(
        Counter({1: 10}),
        Counter({1: 20}),
        Counter(),
        Counter(),
        Counter(
            {
                "sentence_tatoeba_attempted": 12,
                "sentence_tatoeba_hit": 7,
                "sentence_tatoeba_seeded_hit": 4,
                "sentence_ai_rewrite_hit": 3,
                "sentence_ai_generate_hit": 2,
                "sentence_ai_skipped_good_tatoeba": 6,
                "sentence_template_fallback_hit": 5,
            }
        ),
        {1: Counter({"sentence_tatoeba_hit": 7, "sentence_template_fallback_hit": 5})},
        Counter(),
        Counter(),
        {},
        {},
        Counter(),
        {},
    )

    output = capsys.readouterr().out
    assert "Sentence source stats" in output
    assert "sentence_tatoeba_attempted: 12" in output
    assert "sentence_ai_rewrite_hit: 3" in output
    assert "sentence_ai_generate_hit: 2" in output
    assert "sentence_template_fallback_hit: 5" in output
    assert "source_mix: tatoeba=41.2%, rewrite=17.6%, ai=11.8%, template=29.4%" in output
    assert "tatoeba_seeded_share: 64.7%" in output


def test_process_word_uses_source_language_for_definition(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
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

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
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

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
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


def test_process_word_discards_missing_definition_even_in_test_mode(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    builder.config.setdefault("runtime", {})["test_accept_all"] = True
    run = _run_config(tmp_path, language="fr")
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str | None, provider_name: str = "ai", error: str | None = None):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = error

    class FakeProviders:
        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("", provider_name="wiktionary", error="empty result")

        def definition_ai(self, word, language, semantic_only=True):
            _ = (word, language, semantic_only)
            return Result("", provider_name="ai", error="empty result")

        def definition_from_context(self, word, sentence, language, definition_language=None):
            _ = (word, sentence, language, definition_language)
            return Result("", provider_name="ai", error="empty result")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ki/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("kee")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result(f"Mot {word}.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result(f"Mot {word}.", provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            return Result("Word meaning.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("Word meaning.", provider_name="ai")

    card, log = builder._process_word(
        word="maison",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is None
    assert log.status == "discarded"
    assert "definition_missing" in log.validations


def test_should_reject_errors_allows_single_soft_error_in_full_mode(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.mode = "full"

    assert builder._should_reject_errors(["sentence_length_invalid"], run) is False


def test_should_reject_errors_rejects_multiple_soft_errors_in_full_mode(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.mode = "full"

    assert (
        builder._should_reject_errors(
            ["sentence_length_invalid", "sentence_profile_invalid"], run
        )
        is True
    )


def test_should_reject_errors_rejects_hard_error_in_test_mode(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)

    assert builder._should_reject_errors(["definition_missing"], run) is True


def test_should_reject_errors_allows_soft_errors_in_test_mode(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)

    assert builder._should_reject_errors(["sentence_length_invalid"], run) is False


def test_infer_discard_reason_prioritizes_definition_error() -> None:
    reason = _infer_discard_reason(
        ["definition_missing"],
        {"sentence": "provider_disabled", "sentence:tatoeba": "provider_disabled"},
    )
    assert reason == "definition_generation_failed"


def test_process_word_retries_sentence_web_before_ai(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
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

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_ai_calls += 1
            if self.sentence_ai_calls == 1:
                return Result("", error="empty result")
            return Result("Hoy me siento bien en casa.")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
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


def test_process_word_generates_audio_fields_when_enabled(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    ctx = ValidationContext()
    builder.config["audio"] = {
        "enabled": True,
        "required": False,
        "output_dir": str(tmp_path / "audio"),
        "provider_order": ["fake"],
        "language_overrides": {},
        "use_legacy_cache": False,
    }

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "fake"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad", provider_name="ai")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/", provider_name="ai")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("zhee-VYA", provider_name="ai")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Hoy me siento bien en casa.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Hoy me siento bien en casa.", provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good today.", provider_name="ai")

        def audio(
            self,
            text,
            language,
            output_dir,
            filename_hint,
            provider_order=None,
            voice=None,
            voice_gender_preference=None,
        ):
            _ = (language, filename_hint, provider_order, voice, voice_gender_preference)
            safe = text.replace(" ", "_")
            path = Path(output_dir) / f"{safe}.mp3"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"audio")
            return Result(str(path), provider_name="fake")

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
    assert card.word_audio.startswith("[sound:")
    assert card.sentence_audio.startswith("[sound:")
    assert len(media_files) == 2


def test_process_word_uses_cached_audio_when_enabled(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    ctx = ValidationContext()
    builder.config["audio"] = {
        "enabled": True,
        "required": False,
        "output_dir": str(tmp_path / "audio"),
        "provider_order": ["fake"],
        "language_overrides": {},
        "use_legacy_cache": True,
    }

    word_path = tmp_path / "audio" / "cached_word.mp3"
    sentence_path = tmp_path / "audio" / "cached_sentence.mp3"
    word_path.parent.mkdir(parents=True, exist_ok=True)
    word_path.write_bytes(b"audio")
    sentence_path.write_bytes(b"audio")

    class FakeCache:
        def get(self, _kind, key):
            if key.startswith("word::bien"):
                return str(word_path)
            if key.startswith("sentence::Hoy me siento bien en casa."):
                return str(sentence_path)
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
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("zhee-VYA")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Hoy me siento bien en casa.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Hoy me siento bien en casa.")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good today.")

        def audio(self, *args, **kwargs):
            raise AssertionError("audio provider should not be called when cache hits")

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
    assert card.word_audio == f"[sound:{word_path.name}]"
    assert card.sentence_audio == f"[sound:{sentence_path.name}]"


def test_process_word_uses_azure_first_for_russian_audio(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path, language="ru")
    ctx = ValidationContext()
    builder.config["audio"]["enabled"] = True
    builder.config["audio"]["required"] = False
    builder.config["audio"]["output_dir"] = str(tmp_path / "audio")

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "azure_tts"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        audio_calls: list[tuple[list[str] | None, str | None]] = []

        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adverb: maybe, perhaps, possibly.", provider_name="wiktionary")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/может/", provider_name="ai")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("MO-zhyet", provider_name="ai")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result(f"Он думает, что {word} это возможно.", provider_name="tatoeba")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence_ai should not run when web sentence is valid")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            return Result("He thinks that maybe this is possible.", provider_name="googletrans")

        def translation_ai(self, *args, **kwargs):
            raise AssertionError("translation_ai should not run")

        def audio(
            self,
            text,
            language,
            output_dir,
            filename_hint,
            provider_order=None,
            voice=None,
            voice_gender_preference=None,
        ):
            _ = (text, language, filename_hint, voice_gender_preference)
            self.audio_calls.append((list(provider_order or []), voice))
            path = Path(output_dir) / f"{filename_hint}.mp3"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"audio")
            return Result(str(path), provider_name="azure_tts")

    providers = FakeProviders()
    card, _log = builder._process_word(
        word="может",
        level=3,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=providers,
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert providers.audio_calls
    assert providers.audio_calls[0][0][:4] == ["azure_tts", "elevenlabs", "gtts", "pyttsx3"]
    assert providers.audio_calls[0][1] == "ru-RU-DmitryNeural"


def test_process_word_retries_when_sentence_is_wrong_language(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="fr")
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
        sentence_web_calls = 0
        sentence_ai_calls = 0

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: qui ferme completement un acces")

        def definition_ai(self, word, language, semantic_only=True):
            _ = (word, language, semantic_only)
            return Result("adjective: qui ferme completement un acces")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ekskly/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("eks-KLU")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_web_calls += 1
            return Result("I exclusively drink bottled water.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_ai_calls += 1
            return Result("Ce dossier reste exclus au service.", provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            if "qui ferme" in text:
                return Result("adjective: that fully closes an access")
            return Result("This file remains restricted to the service.")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("This file remains restricted to internal service.")

    card, _log = builder._process_word(
        word="exclus",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.sentence == "Ce dossier reste exclus au service."


def test_process_word_rewrites_tatoeba_sentence_when_only_level_validation_fails(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    run.level_size = 2
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(
            self,
            value: str,
            provider_name: str = "ai",
            error: str | None = None,
        ):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = error

    class FakeProviders:
        sentence_web_calls = 0
        sentence_rewrite_calls = 0

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("byen")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_web_calls += 1
            return Result(
                "Hoy me siento bien en casa con mis amigos del barrio.",
                provider_name="tatoeba",
            )

        def sentence_rewrite(
            self,
            sentence,
            word,
            language,
            level=None,
            min_words=None,
            max_words=None,
        ):
            _ = (sentence, word, language, level, min_words, max_words)
            self.sentence_rewrite_calls += 1
            return Result("Hoy me siento bien en casa.", provider_name="ai")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence_ai should not run after a successful rewrite")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result(
                    "adjective: in good condition or quality",
                    provider_name="googletrans",
                )
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

    providers = FakeProviders()
    card, log = builder._process_word(
        word="bien",
        level=2,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=providers,
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.sentence == "Hoy me siento bien en casa."
    assert providers.sentence_web_calls == 1
    assert providers.sentence_rewrite_calls == 1
    assert log.event_counts["sentence_tatoeba_attempted"] == 1
    assert log.event_counts["sentence_ai_rewrite_attempted"] == 1
    assert log.event_counts["sentence_ai_rewrite_hit"] == 1
    assert "sentence_ai_generate_attempted" not in log.event_counts


def test_process_word_skips_sentence_ai_when_tatoeba_is_strong_enough(
    tmp_path: Path, monkeypatch
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    ctx = ValidationContext()
    tatoeba_sentence = "Hoy me siento bien en casa."

    monkeypatch.setattr(
        deck_builder_module,
        "_sentence_selection_score",
        lambda text, *_args, **_kwargs: 1.72 if text == tatoeba_sentence else 1.0,
    )

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

    class Candidate:
        def __init__(self, text: str, query_mode: str = "exact"):
            self.text = text
            self.provider_name = "tatoeba"
            self.source = "tatoeba"
            self.query_mode = query_mode

    class CandidateResult:
        def __init__(self, candidates):
            self.candidates = candidates
            self.provider_name = "tatoeba"
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("byen")

        def sentence_web_candidates(self, word, language, **kwargs):
            _ = (word, language, kwargs)
            return CandidateResult([Candidate(tatoeba_sentence)])

        def sentence_rewrite(self, *args, **kwargs):
            raise AssertionError("sentence_rewrite should not run for a strong Tatoeba hit")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence_ai should not run for a strong Tatoeba hit")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

    card, log = builder._process_word(
        word="bien",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.sentence == tatoeba_sentence
    assert log.event_counts["sentence_tatoeba_hit"] == 1
    assert log.event_counts["sentence_ai_skipped_good_tatoeba"] == 1
    assert "sentence_ai_generate_attempted" not in log.event_counts


def test_process_word_prefers_tatoeba_when_ai_margin_is_small(
    tmp_path: Path, monkeypatch
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    ctx = ValidationContext()
    tatoeba_sentence = "Hoy me siento bien en casa."
    ai_sentence = "Hoy bien parece normal en casa."
    scores = {
        tatoeba_sentence: 1.55,
        ai_sentence: 1.70,
    }

    monkeypatch.setattr(
        deck_builder_module,
        "_sentence_selection_score",
        lambda text, *_args, **_kwargs: scores.get(text, 0.0),
    )

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

    class Candidate:
        def __init__(self, text: str):
            self.text = text
            self.provider_name = "tatoeba"
            self.source = "tatoeba"
            self.query_mode = "exact"

    class CandidateResult:
        def __init__(self, candidates):
            self.candidates = candidates
            self.provider_name = "tatoeba"
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("byen")

        def sentence_web_candidates(self, word, language, **kwargs):
            _ = (word, language, kwargs)
            return CandidateResult([Candidate(tatoeba_sentence)])

        def sentence_ai(self, word, language, **kwargs):
            _ = (word, language, kwargs)
            return Result(ai_sentence, provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

    card, log = builder._process_word(
        word="bien",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.sentence == tatoeba_sentence
    assert log.event_counts["sentence_tatoeba_hit"] == 1
    assert log.event_counts["sentence_ai_generate_attempted"] == 1
    assert "sentence_ai_generate_hit" not in log.event_counts


def test_process_word_uses_ai_when_it_is_materially_better_than_tatoeba(
    tmp_path: Path, monkeypatch
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    ctx = ValidationContext()
    tatoeba_sentence = "Hoy me siento bien en casa."
    ai_sentence = "Hoy bien parece estable en casa."
    scores = {
        tatoeba_sentence: 1.42,
        ai_sentence: 1.78,
    }

    monkeypatch.setattr(
        deck_builder_module,
        "_sentence_selection_score",
        lambda text, *_args, **_kwargs: scores.get(text, 0.0),
    )

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

    class Candidate:
        def __init__(self, text: str):
            self.text = text
            self.provider_name = "tatoeba"
            self.source = "tatoeba"
            self.query_mode = "exact"

    class CandidateResult:
        def __init__(self, candidates):
            self.candidates = candidates
            self.provider_name = "tatoeba"
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("byen")

        def sentence_web_candidates(self, word, language, **kwargs):
            _ = (word, language, kwargs)
            return CandidateResult([Candidate(tatoeba_sentence)])

        def sentence_ai(self, word, language, **kwargs):
            _ = (word, language, kwargs)
            return Result(ai_sentence, provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

    card, log = builder._process_word(
        word="bien",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.sentence == ai_sentence
    assert log.event_counts["sentence_ai_generate_attempted"] == 1
    assert log.event_counts["sentence_ai_generate_hit"] == 1
    assert "sentence_tatoeba_hit" not in log.event_counts


def test_process_word_retries_meta_definition_with_semantic_ai(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="fr")
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
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("verb: simple past of interesser", provider_name="wiktionary")

        def definition_ai(self, word, language, semantic_only=True):
            _ = (word, semantic_only)
            if language == "fr":
                return Result("verb: attirait l attention ou la curiosite")
            return Result("verb: attracted attention or curiosity")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ɛ̃.te.ʁɛ.sɛ/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("ahn-teh-reh-SEH")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Ce sujet interessait tout le groupe hier.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Ce sujet interessait tout le groupe hier.", provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            if "attirait" in text:
                return Result("verb: attracted attention or curiosity", provider_name="googletrans")
            return Result("That topic interested the whole group yesterday.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("That topic interested the whole group yesterday.", provider_name="ai")

    card, _log = builder._process_word(
        word="interessait",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert "simple past of" not in card.definition.lower()
    assert "attracted attention" in card.definition.lower()


def test_process_word_discards_focus_not_in_lexicon(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="fr")
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str | None, provider_name: str = "wiktionary", error: str | None = None):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = error

    class FakeProviders:
        def word_exists(self, word, language):
            _ = (word, language)
            return Result(None, error="empty result")

    card, log = builder._process_word(
        word="soft",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is None
    assert "focus_not_in_lexicon" in log.validations


def test_process_word_uses_slug_hash_audio_name(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    ctx = ValidationContext()
    builder.config["audio"] = {
        "enabled": True,
        "required": False,
        "output_dir": str(tmp_path / "audio"),
        "provider_order": ["fake"],
        "language_overrides": {},
        "use_legacy_cache": False,
        "filename_style": "slug_hash",
        "filename_slug_words": 3,
    }

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "fake"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        hints: list[str] = []

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad", provider_name="ai")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/", provider_name="ai")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("zhee-VYA", provider_name="ai")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Hoy me siento bien en casa.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Hoy me siento bien en casa.", provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good today.", provider_name="ai")

        def audio(
            self,
            text,
            language,
            output_dir,
            filename_hint,
            provider_order=None,
            voice=None,
            voice_gender_preference=None,
        ):
            _ = (text, language, provider_order, voice, voice_gender_preference)
            self.hints.append(filename_hint)
            path = Path(output_dir) / f"{filename_hint}.mp3"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"audio")
            return Result(str(path), provider_name="fake")

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
    assert providers.hints
    assert all(len(hint) < 50 for hint in providers.hints)
    assert providers.hints[0].startswith("es_word_")
    assert "Hoy_me_siento_bien_en_casa" not in providers.hints[-1]


def test_build_parallel_preserves_order_with_out_of_order_futures(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.level_size = 2
    run.concurrency = 3
    run.audio_concurrency = 2

    monkeypatch.setattr(
        builder,
        "_prepare_levels",
        lambda *args, **kwargs: {
            1: ["uno", "dos", "tres"],
            2: ["cuatro", "cinco", "seis"],
            3: ["siete", "ocho", "nueve"],
        },
    )

    sentences_by_level = {
        1: "Esta frase usa {word} con contexto claro.",
        2: "Ayer estudiamos {word} durante la auditoria interna.",
        3: "Durante la reestructuracion presupuestaria, {word} incumplio especificaciones contractuales.",
    }

    def fake_text_task(word, level, index, run, cache):
        _ = (run, cache)
        delays = {"uno": 0.05, "dos": 0.01, "cuatro": 0.05, "cinco": 0.01, "siete": 0.05, "ocho": 0.01}
        time.sleep(delays.get(word, 0.0))
        card = CardData(
            focus=word,
            index=0,
            ipa=f"/{word}/",
            definition="noun: useful sample definition for this card.",
            sentence=sentences_by_level[level].format(word=word),
            translation=f"This sentence uses {word} with clear context.",
            level=level,
            language="es",
        )
        return TextTaskResult(
            candidate_index=index - 1,
            card=card,
            log_record=LogRecord(focus=word, level=level, status="candidate"),
        )

    def fake_audio_task(accepted_index, card, log_record, run, cache):
        _ = (run, cache)
        delays = {"uno": 0.05, "dos": 0.01, "cuatro": 0.05, "cinco": 0.01, "siete": 0.05, "ocho": 0.01}
        time.sleep(delays.get(card.focus, 0.0))
        card.word_audio = f"[sound:{card.focus}.mp3]"
        card.sentence_audio = f"[sound:{card.focus}_sentence.mp3]"
        card.audio = card.word_audio
        return AudioTaskResult(
            accepted_index=accepted_index,
            card=card,
            log_record=log_record,
            media_files=[f"media/{card.focus}.mp3", f"media/{card.focus}_sentence.mp3"],
        )

    monkeypatch.setattr(builder, "_process_word_textual_task", fake_text_task)
    monkeypatch.setattr(builder, "_attach_audio_task", fake_audio_task)

    cards, media_files = builder.build(run)

    assert [card.focus for card in cards] == ["uno", "dos", "cuatro", "cinco", "siete", "ocho"]
    assert len(media_files) == 12


def test_parallel_build_only_generates_audio_for_textually_valid_cards(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.level_size = 1
    run.concurrency = 2
    run.audio_concurrency = 2

    monkeypatch.setattr(
        builder,
        "_prepare_levels",
        lambda *args, **kwargs: {
            1: ["ruim", "bom"],
            2: ["xilofono", "yate"],
            3: ["zangano", "wafle"],
        },
    )

    audio_calls: list[str] = []
    sentences_by_level = {
        1: "Esta frase usa {word} con contexto claro.",
        2: "Ayer estudiamos {word} durante la auditoria interna.",
        3: "Durante la reestructuracion presupuestaria, {word} incumplio especificaciones contractuales.",
    }

    def fake_text_task(word, level, index, run, cache):
        _ = (index, run, cache)
        if word in {"ruim", "xilofono", "zangano"}:
            card = CardData(
                focus=word,
                index=0,
                ipa=f"/{word}/",
                definition="",
                sentence=sentences_by_level[level].format(word=word),
                translation=f"This sentence uses {word} with clear context.",
                level=level,
                language="es",
            )
        else:
            card = CardData(
                focus=word,
                index=0,
                ipa=f"/{word}/",
                definition="noun: useful sample definition for this card.",
                sentence=sentences_by_level[level].format(word=word),
                translation=f"This sentence uses {word} with clear context.",
                level=level,
                language="es",
            )
        return TextTaskResult(
            candidate_index=index - 1,
            card=card,
            log_record=LogRecord(focus=word, level=level, status="candidate"),
        )

    def fake_audio_task(accepted_index, card, log_record, run, cache):
        _ = (accepted_index, run, cache)
        audio_calls.append(card.focus)
        card.word_audio = f"[sound:{card.focus}.mp3]"
        card.sentence_audio = f"[sound:{card.focus}_sentence.mp3]"
        card.audio = card.word_audio
        return AudioTaskResult(
            accepted_index=accepted_index,
            card=card,
            log_record=log_record,
            media_files=[f"media/{card.focus}.mp3"],
        )

    monkeypatch.setattr(builder, "_process_word_textual_task", fake_text_task)
    monkeypatch.setattr(builder, "_attach_audio_task", fake_audio_task)

    cards, _ = builder.build(run)

    assert [card.focus for card in cards] == ["bom", "yate", "wafle"]
    assert audio_calls == ["bom", "yate", "wafle"]


def test_process_word_ignores_legacy_sentence_cache_key(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="fr")
    ctx = ValidationContext()

    legacy_sentence = "Ce dossier exclus reste prive."
    legacy_sentence_key = "exclus::lvl1::2-7::v3"

    class FakeCache:
        def __init__(self):
            self.data = {"sentences": {legacy_sentence_key: legacy_sentence}}

        def get(self, kind, key):
            return self.data.get(kind, {}).get(key)

        def set(self, kind, key, value):
            self.data.setdefault(kind, {})[key] = value

    class Result:
        def __init__(self, value: str, provider_name: str = "tatoeba"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        sentence_web_calls = 0

        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: reserve a un usage interne.", provider_name="wiktionary")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_web_calls += 1
            return Result("Ce dossier exclus reste prive.", provider_name="tatoeba")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence_ai should not run on a valid rebuilt sentence")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: restricted to internal use only", provider_name="googletrans")
            return Result("This restricted file stays private.", provider_name="googletrans")

        def translation_ai(self, *args, **kwargs):
            raise AssertionError("translation_ai should not run")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ekskly/", provider_name="ai")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("eks-KLU", provider_name="ai")

    providers = FakeProviders()
    card, _log = builder._process_word(
        word="exclus",
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


def test_process_word_ignores_invalid_cached_translation_and_regenerates(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="fr")
    ctx = ValidationContext()

    sentence = "Ce dossier exclus reste prive."
    source_key = "exclus::fr::v3"
    definition_key = "exclus::en::v3"
    sentence_key = "exclus::lvl1::2-7::sv2::v3"
    translation_key = f"{sentence}::fr->en::v3"

    class FakeCache:
        def __init__(self):
            self.data = {
                "definitions": {
                    source_key: "adjective: reserve a un usage interne.",
                    definition_key: "adjective: restricted to internal use only.",
                },
                "sentences": {sentence_key: sentence},
                "translations": {
                    translation_key: sentence,
                },
            }

        def get(self, kind, key):
            return self.data.get(kind, {}).get(key)

        def set(self, kind, key, value):
            self.data.setdefault(kind, {})[key] = value

    class Result:
        def __init__(self, value: str, provider_name: str = "googletrans"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        translation_web_calls = 0

        def definition(self, *args, **kwargs):
            raise AssertionError("definition provider should not be called with valid cache")

        def definition_ai(self, *args, **kwargs):
            raise AssertionError("definition ai should not be called with valid cache")

        def definition_from_context(self, *args, **kwargs):
            raise AssertionError("context definition should not be called with valid cache")

        def sentence_web(self, *args, **kwargs):
            raise AssertionError("sentence provider should not be called with valid cache")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence ai should not be called with valid cache")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            self.translation_web_calls += 1
            return Result("This restricted file stays private.", provider_name="googletrans")

        def translation_ai(self, *args, **kwargs):
            raise AssertionError("translation ai should not be needed")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ekskly/", provider_name="ai")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("eks-KLU", provider_name="ai")

        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

    providers = FakeProviders()
    card, _log = builder._process_word(
        word="exclus",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=providers,
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert providers.translation_web_calls == 1
    assert card.translation == "This restricted file stays private."


def test_process_word_uses_english_gloss_as_final_definition(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="ru")
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "wiktionary"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        translation_web_calls = 0

        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adverb: maybe, perhaps, possibly.", provider_name="wiktionary")

        def definition_ai(self, *args, **kwargs):
            raise AssertionError("definition_ai should not run when gloss is already usable")

        def definition_from_context(self, *args, **kwargs):
            raise AssertionError("definition_from_context should not run when gloss is already usable")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result(f"Он говорит, что {word} все понимают.", provider_name="tatoeba")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence_ai should not run on valid sentence")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            self.translation_web_calls += 1
            return Result("He says that maybe everyone understands.")

        def translation_ai(self, *args, **kwargs):
            raise AssertionError("translation_ai should not run")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/может/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("MO-zhyet")

    providers = FakeProviders()
    card, log = builder._process_word(
        word="может",
        level=3,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=providers,
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.definition == "adverb: maybe, perhaps, possibly."
    assert card.source_definition == ""
    assert "source_definition_wrong_language" not in log.validations
    assert providers.translation_web_calls == 1


def test_process_word_accepts_single_word_definition_gloss(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="ru")
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "wiktionary"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adverb: already", provider_name="ai")

        def definition_ai(self, *args, **kwargs):
            raise AssertionError("definition_ai should not run when one-word gloss is valid")

        def definition_from_context(self, *args, **kwargs):
            raise AssertionError("definition_from_context should not run when one-word gloss is valid")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result(f"\u041e\u043d \u0443\u0436\u0435 \u0434\u043e\u043c\u0430.", provider_name="tatoeba")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence_ai should not run on valid sentence")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            return Result("He is already home.", provider_name="googletrans")

        def translation_ai(self, *args, **kwargs):
            raise AssertionError("translation_ai should not run")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/u\u0290e/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("oo-ZHE")

    card, log = builder._process_word(
        word="\u0443\u0436\u0435",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.definition == "adverb: already."
    assert "definition_wrong_language" not in log.validations


def test_process_word_translates_single_word_source_definition(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="es")
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "wiktionary"):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        translation_ai_calls = 0

        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adverb: ya", provider_name="wiktionary")

        def definition_ai(self, *args, **kwargs):
            raise AssertionError("definition_ai should not run when source gloss is usable")

        def definition_from_context(self, *args, **kwargs):
            raise AssertionError("definition_from_context should not run when source gloss is usable")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Ya estoy en casa.", provider_name="tatoeba")

        def sentence_ai(self, *args, **kwargs):
            raise AssertionError("sentence_ai should not run on valid sentence")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            if text.startswith("adverb:"):
                return Result("adverb: already", provider_name="googletrans")
            return Result("I am already home.", provider_name="googletrans")

        def translation_ai(self, *args, **kwargs):
            self.translation_ai_calls += 1
            raise AssertionError("translation_ai should not run")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ʝa/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("ya")

    providers = FakeProviders()
    card, log = builder._process_word(
        word="ya",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=providers,
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.source_definition == "adverb: ya."
    assert card.definition == "adverb: already."
    assert providers.translation_ai_calls == 0
    assert "definition_wrong_language" not in log.validations


def test_process_word_passes_sentence_bounds_to_sentence_providers(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="es")
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
        sentence_bounds: list[tuple[int | None, int | None]] = []

        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad", provider_name="ai")

        def definition_ai(self, word, language, semantic_only=True):
            _ = (word, language, semantic_only)
            return Result("adjective: en buen estado o calidad", provider_name="ai")

        def definition_from_context(self, word, sentence, language, definition_language=None):
            _ = (word, sentence, language, definition_language)
            return Result("adjective: en buen estado o calidad", provider_name="ai")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level)
            self.sentence_bounds.append((kwargs.get("min_words"), kwargs.get("max_words")))
            return Result("Hoy me siento bien en casa.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level)
            self.sentence_bounds.append((kwargs.get("min_words"), kwargs.get("max_words")))
            return Result("Hoy me siento bien en casa.", provider_name="ai")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/", provider_name="ai")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("zhee-VYA", provider_name="ai")

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
    assert providers.sentence_bounds
    assert providers.sentence_bounds[0] == (2, 7)
