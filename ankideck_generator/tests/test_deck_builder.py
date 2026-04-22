import json
from collections import Counter
from pathlib import Path
import random
import time

import ankideck_generator.core.deck_builder as deck_builder_module
from ankideck_generator.core.deck_builder import (
    AudioTaskResult,
    BuildStats,
    DeckBuilder,
    TextTaskResult,
    _infer_discard_reason,
    _sentence_length_bounds,
)
from ankideck_generator.core.models import (
    CardData,
    DuplicateDecisionEvidence,
    LexicalReviewResult,
    LogRecord,
    ProgressState,
    RunConfig,
    StructuredSentenceBatch,
)
from ankideck_generator.core.providers import StructuredSentenceBatchResult
from ankideck_generator.utils.logger import JsonLogger
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


def _ai_sentence_fixture_payload(name: str) -> dict[str, object]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "ai_sentence_candidates"
        / name
    )
    return json.loads(path.read_text(encoding="utf-8"))


class TestDeckBuilderLexicalReviewSentenceAnchor:
    def test_process_word_auto_corrects_definition_without_rewriting_sentence(
        self, tmp_path: Path
    ) -> None:
        builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
        builder.config["audio"]["enabled"] = False
        run = _run_config(tmp_path)

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

        class ReviewTransport:
            def __init__(self, review: LexicalReviewResult):
                self.review = review
                self.provider_name = "ai"
                self.elapsed_ms = 1
                self.error = None

        class FakeProviders:
            lexical_review_calls = 0

            def definition(self, word, language, allow_ai=True, definition_language=None):
                _ = (word, language, allow_ai, definition_language)
                return Result("noun: banco de parque")

            def ipa(self, word, language, allow_ai=True):
                _ = (word, language, allow_ai)
                return Result("/ˈbaŋ.ko/")

            def phonetic_spelling(self, ipa, language, allow_ai=True):
                _ = (ipa, language, allow_ai)
                return Result("BAN-ko")

            def sentence_web(self, word, language, level=None, **kwargs):
                _ = (word, language, level, kwargs)
                return Result("Me sente en el banco del parque.", provider_name="tatoeba")

            def sentence_ai(self, word, language, level=None, **kwargs):
                _ = (word, language, level, kwargs)
                return Result("Me sente en el banco del parque.")

            def translation_web(self, text, src, dest):
                _ = (src, dest)
                if text.startswith("noun:"):
                    return Result("noun: financial institution", provider_name="googletrans")
                return Result("I sat on the bench in the park.", provider_name="googletrans")

            def translation_ai(self, text, src, dest):
                _ = (text, src, dest)
                return Result("I sat on the bench in the park.")

            def lexical_review(self, request, **kwargs):
                _ = kwargs
                self.lexical_review_calls += 1
                return ReviewTransport(
                    LexicalReviewResult.model_validate(
                        {
                            "verdict": "correct",
                            "focus_word": request.focus_word,
                            "language": request.language,
                            "target_translation_language": request.target_translation_language,
                            "accepted_sentence": request.accepted_sentence,
                            "current_definition": request.current_definition,
                            "current_translation": request.current_translation,
                            "source_definition": request.source_definition,
                            "candidate_senses": list(request.candidate_senses),
                            "winning_sense": "noun: bench in a park or public place.",
                            "losing_sense_candidates": ["noun: financial institution"],
                            "corrected_definition": "noun: bench in a park or public place.",
                            "corrected_translation": None,
                            "reason_codes": ["definition_sentence_mismatch"],
                            "before": {
                                "definition": request.current_definition,
                                "translation": request.current_translation,
                            },
                            "after": {
                                "definition": "noun: bench in a park or public place.",
                                "translation": request.current_translation,
                            },
                            "selection_reasons": {
                                "winning_sense": "park sentence context favors seating sense"
                            },
                        }
                    )
                )

        card, log = builder._process_word_textual(
            word="banco",
            level=1,
            index=1,
            run=run,
            cache=FakeCache(),
            providers=FakeProviders(),
        )

        assert card is not None
        assert card.definition == "noun: bench in a park or public place."
        assert card.translation == "I sat on the bench in the park."
        assert card.sentence == "Me sente en el banco del parque."
        assert card.focus == "banco"
        assert log.before["definition"] == "noun: financial institution"
        assert log.after["definition"] == "noun: bench in a park or public place."

    def test_process_word_sentence_anchor_lexical_review_accepts_aligned_fields(
        self, tmp_path: Path
    ) -> None:
        builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
        builder.config["audio"]["enabled"] = False
        run = _run_config(tmp_path)

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

        class ReviewTransport:
            def __init__(self, review: LexicalReviewResult):
                self.review = review
                self.provider_name = "ai"
                self.elapsed_ms = 1
                self.error = None

        class FakeProviders:
            lexical_review_calls = 0

            def definition(self, word, language, allow_ai=True, definition_language=None):
                _ = (word, language, allow_ai, definition_language)
                return Result("noun: bench in a park or public place")

            def ipa(self, word, language, allow_ai=True):
                _ = (word, language, allow_ai)
                return Result("/ˈbaŋ.ko/")

            def phonetic_spelling(self, ipa, language, allow_ai=True):
                _ = (ipa, language, allow_ai)
                return Result("BAN-ko")

            def sentence_web(self, word, language, level=None, **kwargs):
                _ = (word, language, level, kwargs)
                return Result("Me sente en el banco del parque.", provider_name="tatoeba")

            def sentence_ai(self, word, language, level=None, **kwargs):
                _ = (word, language, level, kwargs)
                return Result("Me sente en el banco del parque.")

            def translation_web(self, text, src, dest):
                _ = (src, dest)
                if text.startswith("noun:"):
                    return Result("noun: bench in a park or public place", provider_name="googletrans")
                return Result("I sat on the bench in the park.", provider_name="googletrans")

            def translation_ai(self, text, src, dest):
                _ = (text, src, dest)
                raise AssertionError("translation_ai should not run for aligned fields")

            def lexical_review(self, request, **kwargs):
                _ = kwargs
                self.lexical_review_calls += 1
                return ReviewTransport(
                    LexicalReviewResult.model_validate(
                        {
                            "verdict": "accept",
                            "focus_word": request.focus_word,
                            "language": request.language,
                            "target_translation_language": request.target_translation_language,
                            "accepted_sentence": request.accepted_sentence,
                            "current_definition": request.current_definition,
                            "current_translation": request.current_translation,
                            "source_definition": request.source_definition,
                            "candidate_senses": list(request.candidate_senses),
                            "winning_sense": request.current_definition,
                            "losing_sense_candidates": [],
                            "reason_codes": [],
                            "selection_reasons": {"winning_sense": "already_aligned"},
                        }
                    )
                )

        providers = FakeProviders()
        card, log = builder._process_word_textual(
            word="banco",
            level=1,
            index=1,
            run=run,
            cache=FakeCache(),
            providers=providers,
        )

        assert card is not None
        assert providers.lexical_review_calls == 1
        assert card.definition == "noun: bench in a park or public place."
        assert card.translation == "I sat on the bench in the park."
        assert log.before == {}
        assert log.after == {}


def test_process_word_rejects_low_confidence_ambiguity_to_review_queue(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)

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

    class ReviewTransport:
        def __init__(self, review: LexicalReviewResult):
            self.review = review
            self.provider_name = "ai"
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("noun: banco")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ˈbaŋ.ko/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("BAN-ko")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Vi el banco cerca del rio.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Vi el banco cerca del rio.")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            if text.startswith("noun:"):
                return Result("noun: bank", provider_name="googletrans")
            return Result("I saw the bank near the river.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I saw the bank near the river.")

        def lexical_review(self, request, **kwargs):
            _ = kwargs
            return ReviewTransport(
                LexicalReviewResult.model_validate(
                    {
                        "verdict": "reject",
                        "focus_word": request.focus_word,
                        "language": request.language,
                        "target_translation_language": request.target_translation_language,
                        "accepted_sentence": request.accepted_sentence,
                        "current_definition": request.current_definition,
                        "current_translation": request.current_translation,
                        "source_definition": request.source_definition,
                        "candidate_senses": [
                            "noun: financial institution",
                            "noun: land alongside a river",
                        ],
                        "winning_sense": None,
                        "losing_sense_candidates": [
                            "noun: financial institution",
                            "noun: land alongside a river",
                        ],
                        "reason_codes": ["lexical_review_unresolved_ambiguity"],
                        "before": {
                            "definition": request.current_definition,
                            "translation": request.current_translation,
                        },
                        "after": {},
                        "selection_reasons": {
                            "winning_sense": "sentence context did not disambiguate river-vs-finance sense"
                        },
                    }
                )
            )

    card, log = builder._process_word_textual(
        word="banco",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
    )

    assert card is None
    assert log.lifecycle_state == "rejected"
    assert "lexical_review_unresolved_ambiguity" in log.reason_codes

    stats = BuildStats()
    logger = JsonLogger(str(tmp_path / "run.jsonl"))
    builder._record_log(logger, stats, log)

    assert len(stats.needs_review_items) == 1
    item = stats.needs_review_items[0]
    assert item["lifecycle_state"] == "rejected"
    assert item["reason_codes"] == ["lexical_review_unresolved_ambiguity"]
    assert item["before"]["definition"]
    assert item["before"]["translation"] == "I saw the bank near the river."
    assert item["after"]["losing_sense_candidates"]
    assert item["selection_reasons"]["winning_sense"].startswith("sentence context")


def test_process_word_lexical_review_reject_never_uses_human_review_state(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)

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

    class ReviewTransport:
        def __init__(self, review: LexicalReviewResult):
            self.review = review
            self.provider_name = "ai"
            self.elapsed_ms = 1
            self.error = None

    class FakeProviders:
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("noun: banco")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ˈbaŋ.ko/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("BAN-ko")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Vi el banco cerca del rio.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Vi el banco cerca del rio.")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            if text.startswith("noun:"):
                return Result("noun: bank", provider_name="googletrans")
            return Result("I saw the bank near the river.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I saw the bank near the river.")

        def lexical_review(self, request, **kwargs):
            _ = kwargs
            return ReviewTransport(
                LexicalReviewResult.model_validate(
                    {
                        "verdict": "reject",
                        "focus_word": request.focus_word,
                        "language": request.language,
                        "target_translation_language": request.target_translation_language,
                        "accepted_sentence": request.accepted_sentence,
                        "current_definition": request.current_definition,
                        "current_translation": request.current_translation,
                        "source_definition": request.source_definition,
                        "candidate_senses": ["noun: financial institution", "noun: land alongside a river"],
                        "reason_codes": ["lexical_review_unresolved_ambiguity"],
                    }
                )
            )

    card, log = builder._process_word(
        word="banco",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ValidationContext(),
        media_files=[],
    )

    assert card is None
    assert log.lifecycle_state == "rejected"
    assert log.lifecycle_state != "human-review"


def test_process_word_revalidation_rejects_invalid_lexical_review_correction(
    monkeypatch,
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    run.mode = "full"
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    corrected_card = CardData(
        focus="banco",
        index=1,
        ipa="/ˈbaŋ.ko/ (BAN-ko)",
        source_definition="noun: banco de parque.",
        definition="park bench",
        sentence="Me sente en el banco del parque.",
        translation="I sat on the bench in the park.",
        translation_language="en",
        level=1,
        language="es",
        lifecycle_state="generated",
    )
    corrected_log = LogRecord(
        focus="banco",
        level=1,
        lifecycle_state="generated",
        status="candidate",
        review_notes=["lexical_review_corrected"],
        reason_codes=["definition_sentence_mismatch"],
        before={
            "definition": "noun: bench in a park or public place.",
            "translation": "I sat on the bench in the park.",
        },
        after={
            "definition": "park bench",
            "translation": "I sat on the bench in the park.",
        },
    )

    monkeypatch.setattr(
        builder,
        "_process_word_textual",
        lambda **_kwargs: (corrected_card.model_copy(deep=True), corrected_log.model_copy(deep=True)),
    )
    monkeypatch.setattr(
        builder,
        "_attach_audio_to_card",
        lambda **_kwargs: (_kwargs["card"], _kwargs["log_record"], []),
    )

    card, log = builder._process_word(
        word="banco",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=object(),
        ctx=ctx,
        media_files=[],
    )

    assert card is None
    assert log.lifecycle_state == "rejected"
    assert "definition_sentence_mismatch" in log.reason_codes
    assert "definition_missing_pos" in log.validations
    assert log.before["definition"] == "noun: bench in a park or public place."
    assert log.after["definition"] == "park bench"


def test_interactive_edit_reruns_validation_before_acceptance(
    monkeypatch, tmp_path: Path
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    run.mode = "full"
    run.interactive = True
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    base_card = CardData(
        focus="banco",
        index=1,
        ipa="/ˈbaŋ.ko/ (BAN-ko)",
        source_definition="noun: banco de parque.",
        definition="noun: bench in a park or public place.",
        sentence="Me sente en el banco del parque.",
        translation="I sat on the bench in the park.",
        translation_language="en",
        level=1,
        language="es",
        lifecycle_state="generated",
    )
    base_log = LogRecord(
        focus="banco",
        level=1,
        lifecycle_state="generated",
        status="candidate",
    )

    monkeypatch.setattr(
        builder,
        "_process_word_textual",
        lambda **_kwargs: (base_card.model_copy(deep=True), base_log.model_copy(deep=True)),
    )
    monkeypatch.setattr(
        builder,
        "_attach_audio_to_card",
        lambda **_kwargs: (_kwargs["card"], _kwargs["log_record"], []),
    )
    monkeypatch.setattr(
        builder,
        "_interactive_edit",
        lambda card, _log_record: card.model_copy(update={"definition": "bench"}),
    )

    card, log = builder._process_word(
        word="banco",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=object(),
        ctx=ctx,
        media_files=[],
    )

    assert card is None
    assert log.lifecycle_state == "rejected"
    assert "definition_missing_pos" in log.validations
    assert log.before["definition"] == "noun: bench in a park or public place."
    assert log.after["definition"] == "bench"


def test_interactive_edit_revalidation_rejects_before_audio_generation(
    monkeypatch, tmp_path: Path
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = True
    run = _run_config(tmp_path)
    run.mode = "full"
    run.interactive = True
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    base_card = CardData(
        focus="banco",
        index=1,
        ipa="/banco/",
        source_definition="noun: banco de parque.",
        definition="noun: bench in a park or public place.",
        sentence="Me sente en el banco del parque.",
        translation="I sat on the bench in the park.",
        translation_language="en",
        level=1,
        language="es",
        lifecycle_state="generated",
    )
    base_log = LogRecord(
        focus="banco",
        level=1,
        lifecycle_state="generated",
        status="candidate",
        review_notes=["lexical_review_corrected"],
    )
    audio_calls: list[str] = []

    monkeypatch.setattr(
        builder,
        "_process_word_textual",
        lambda **_kwargs: (base_card.model_copy(deep=True), base_log.model_copy(deep=True)),
    )
    monkeypatch.setattr(
        builder,
        "_interactive_edit",
        lambda card, _log_record: card.model_copy(update={"definition": "bench"}),
    )

    def fake_attach_audio(**kwargs):
        audio_calls.append(kwargs["card"].definition)
        card = kwargs["card"].model_copy(deep=True)
        card.word_audio = "[sound:banco.mp3]"
        card.sentence_audio = "[sound:banco_sentence.mp3]"
        card.audio = card.word_audio
        return card, kwargs["log_record"], ["media/banco.mp3"]

    monkeypatch.setattr(builder, "_attach_audio_to_card", fake_attach_audio)

    card, log = builder._process_word(
        word="banco",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=object(),
        ctx=ctx,
        media_files=[],
    )

    assert card is None
    assert log.lifecycle_state == "rejected"
    assert audio_calls == []


def test_interactive_edit_valid_correction_generates_audio_after_acceptance(
    monkeypatch, tmp_path: Path
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = True
    run = _run_config(tmp_path)
    run.mode = "full"
    run.interactive = True
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    base_card = CardData(
        focus="banco",
        index=1,
        ipa="/banco/",
        source_definition="noun: banco de parque.",
        definition="noun: bench in a park or public place.",
        sentence="Me sente en el banco del parque.",
        translation="I sat on the bench in the park.",
        translation_language="en",
        level=1,
        language="es",
        lifecycle_state="generated",
    )
    base_log = LogRecord(
        focus="banco",
        level=1,
        lifecycle_state="generated",
        status="candidate",
        review_notes=["lexical_review_corrected"],
    )
    call_order: list[str] = []

    monkeypatch.setattr(
        builder,
        "_process_word_textual",
        lambda **_kwargs: (base_card.model_copy(deep=True), base_log.model_copy(deep=True)),
    )

    def fake_interactive_edit(card, _log_record):
        call_order.append("interactive")
        return card.model_copy(
            update={"definition": "noun: public bench for sitting outdoors."}
        )

    def fake_attach_audio(**kwargs):
        call_order.append("audio")
        card = kwargs["card"].model_copy(deep=True)
        card.word_audio = "[sound:banco.mp3]"
        card.sentence_audio = "[sound:banco_sentence.mp3]"
        card.audio = card.word_audio
        return card, kwargs["log_record"], ["media/banco.mp3"]

    monkeypatch.setattr(builder, "_interactive_edit", fake_interactive_edit)
    monkeypatch.setattr(builder, "_attach_audio_to_card", fake_attach_audio)

    card, log = builder._process_word(
        word="banco",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=object(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert log.lifecycle_state == "accepted"
    assert card.word_audio == "[sound:banco.mp3]"
    assert call_order == ["interactive", "audio"]


def test_process_word_rejects_duplicate_candidate_against_accepted_cards_only(
    monkeypatch, tmp_path: Path
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="en")
    run.mode = "full"
    ctx = ValidationContext()

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    candidate_cards = iter(
        [
            CardData(
                focus="house",
                index=1,
                ipa="/haʊs/",
                definition="",
                sentence="I see the bright old house today.",
                translation="I see the bright old house today.",
                translation_language="en",
                level=1,
                language="en",
                lifecycle_state="generated",
            ),
            CardData(
                focus="house",
                index=1,
                ipa="/haʊs/",
                definition="noun: a building for people to live in.",
                sentence="I see the bright old house today.",
                translation="I see the bright old house today.",
                translation_language="en",
                level=1,
                language="en",
                lifecycle_state="generated",
            ),
            CardData(
                focus="house",
                index=1,
                ipa="/haʊs/",
                definition="noun: a building for people to live in.",
                sentence="I see the bright old house today!",
                translation="I see the bright old house today.",
                translation_language="en",
                level=1,
                language="en",
                lifecycle_state="generated",
            ),
        ]
    )

    def fake_process_word_textual(**_kwargs):
        card = next(candidate_cards)
        return card, LogRecord(
            focus=card.focus,
            level=card.level,
            lifecycle_state="generated",
            status="candidate",
        )

    monkeypatch.setattr(builder, "_process_word_textual", fake_process_word_textual)
    monkeypatch.setattr(
        builder,
        "_attach_audio_to_card",
        lambda **kwargs: (kwargs["card"], kwargs["log_record"], []),
    )

    first_card, first_log = builder._process_word(
        word="house",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=object(),
        ctx=ctx,
        media_files=[],
    )
    second_card, second_log = builder._process_word(
        word="house",
        level=1,
        index=2,
        run=run,
        cache=FakeCache(),
        providers=object(),
        ctx=ctx,
        media_files=[],
    )
    third_card, third_log = builder._process_word(
        word="house",
        level=1,
        index=3,
        run=run,
        cache=FakeCache(),
        providers=object(),
        ctx=ctx,
        media_files=[],
    )

    assert first_card is None
    assert first_log.lifecycle_state == "rejected"
    assert "definition_missing" in first_log.validations

    assert second_card is not None
    assert second_log.lifecycle_state == "accepted"

    assert third_card is None
    assert third_log.lifecycle_state == "rejected"
    assert "duplicate_sentence_exact" in third_log.validations
    assert "duplicate_sentence_exact" in third_log.reason_codes
    assert third_log.duplicate_evidence is not None
    assert third_log.duplicate_evidence.kind == "exact"


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


def test_build_soft_expands_attempt_cap_when_more_words_are_available(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.level_size = 1
    run.max_attempts_per_level = 1

    monkeypatch.setattr(
        builder,
        "_prepare_levels",
        lambda *args, **kwargs: {
            1: ["uno", "dos"],
            2: ["tres", "cuatro"],
            3: ["cinco", "seis"],
        },
    )

    def fake_process_word(*args, **kwargs):
        word = kwargs["word"]
        level = kwargs["level"]
        if word in {"uno", "tres", "cinco"}:
            return None, LogRecord(
                focus=word,
                level=level,
                validations=["definition_missing"],
                status="discarded",
                discard_reason="definition_generation_failed",
            )
        return (
            CardData(
                focus=word,
                index=0,
                ipa=f"/{word}/",
                definition="noun: useful sample definition for this card.",
                sentence=f"Esta frase usa {word} con contexto claro.",
                translation=f"This sentence uses {word} with clear context.",
                level=level,
                language="es",
            ),
            LogRecord(focus=word, level=level, status="accepted"),
        )

    monkeypatch.setattr(builder, "_process_word", fake_process_word)

    cards, _ = builder.build(run)
    assert [card.focus for card in cards] == ["dos", "cuatro", "seis"]


def test_prepare_levels_uses_strict_frequency_order_within_level_bands(
    monkeypatch, tmp_path: Path
) -> None:
    _ = tmp_path
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    frequency_words = [f"mot{i}" for i in range(1, 121)]

    monkeypatch.setattr(deck_builder_module, "top_n_list", lambda language, total: frequency_words[:total])
    monkeypatch.setattr(
        deck_builder_module,
        "filter_frequent_words",
        lambda words, language, min_length=3, **kwargs: list(words),
    )

    levels = builder._prepare_levels("fr", level_size=2, seed=1, pool_multiplier=2)
    levels_other_seed = builder._prepare_levels("fr", level_size=2, seed=2, pool_multiplier=2)

    assert levels == levels_other_seed
    assert levels[1] == ["mot1", "mot2", "mot3", "mot4"]
    assert levels[2] == ["mot25", "mot26", "mot27", "mot28"]
    assert levels[3] == ["mot49", "mot50", "mot51", "mot52"]


def test_sentence_length_bounds_follow_level_defaults() -> None:
    assert _sentence_length_bounds({1: (2, 7), 2: (4, 10), 3: (6, 15)}, 1) == (5, 7)
    assert _sentence_length_bounds({1: (2, 7), 2: (4, 10), 3: (6, 15)}, 2) == (5, 10)
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
            }
        ),
        {1: Counter({"sentence_tatoeba_hit": 7, "sentence_ai_generate_hit": 2})},
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
    assert "sentence_reject_rate: 0.0%" in output
    assert "source_mix: tatoeba=58.3%, rewrite=25.0%, ai=16.7%" in output
    assert "tatoeba_seeded_share: 91.7%" in output


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


def test_process_word_retries_ai_before_web_fallback(tmp_path: Path) -> None:
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
    assert providers.sentence_ai_calls == 2
    assert providers.sentence_web_calls == 0


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

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=None,
                provider_name="ai",
                elapsed_ms=1,
                error="structured_sentence_validation_error: malformed batch",
            )

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result(f"Он думает, что {word} это возможно.", provider_name="tatoeba")

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
    run.sentence_ai_attempts = 1
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

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=None,
                provider_name="ai",
                elapsed_ms=1,
                error="structured_sentence_validation_error: malformed batch",
            )

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
    assert log.event_counts["sentence_ai_malformed_batch"] == 1
    assert log.event_counts["sentence_tatoeba_attempted"] == 1
    assert log.event_counts["sentence_ai_rewrite_attempted"] == 1
    assert log.event_counts["sentence_ai_rewrite_hit"] == 1
    assert log.event_counts["sentence_ai_low_yield_fallback"] == 1


def test_process_word_uses_valid_ai_batch_without_web_fallback(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    ctx = ValidationContext()
    payload = _ai_sentence_fixture_payload("valid_batch.json")

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
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("byen")

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=StructuredSentenceBatch.model_validate(payload),
                provider_name="ai",
                elapsed_ms=1,
            )

        def sentence_web_candidates(self, *args, **kwargs):
            raise AssertionError("web fallback should not run when AI yields a valid batch")

        def sentence_rewrite(self, *args, **kwargs):
            raise AssertionError("sentence_rewrite should not run when AI already succeeded")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

    providers = FakeProviders()
    card, log = builder._process_word(
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
    assert card.sentence in {item["sentence"] for item in payload["candidates"]}
    assert log.event_counts["sentence_ai_generate_attempted"] == 1
    assert log.event_counts["sentence_ai_generate_hit"] == 1
    assert "sentence_tatoeba_attempted" not in log.event_counts


def test_process_word_uses_web_fallback_only_after_ai_low_yield(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    run.sentence_ai_attempts = 1
    ctx = ValidationContext()
    payload = _ai_sentence_fixture_payload("valid_batch.json")
    payload["candidates"] = [
        {
            "sentence": "This word bien appears in this example.",
            "target_form": "bien",
            "requested_pos": "adjective",
            "requested_sense": "in good condition or quality",
            "validation_signals": ["meta_example"],
            "rationale": "meta_example",
        },
        {
            "sentence": "This sentence uses bien in English now.",
            "target_form": "bien",
            "requested_pos": "adjective",
            "requested_sense": "in good condition or quality",
            "validation_signals": ["wrong_language"],
            "rationale": "wrong_language",
        },
        {
            "sentence": "Today bien appears inside an English sentence.",
            "target_form": "bien",
            "requested_pos": "adjective",
            "requested_sense": "in good condition or quality",
            "validation_signals": ["wrong_language"],
            "rationale": "wrong_language",
        },
    ]

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
        sentence_web_calls = 0

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("byen")

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=StructuredSentenceBatch.model_validate(payload),
                provider_name="ai",
                elapsed_ms=1,
            )

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_web_calls += 1
            return Result("Hoy me siento bien en casa.", provider_name="tatoeba")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

    providers = FakeProviders()
    card, log = builder._process_word(
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
    assert card.sentence == "Hoy me siento bien en casa."
    assert log.event_counts["sentence_ai_generate_attempted"] == 1
    assert log.event_counts["sentence_ai_low_yield_fallback"] == 1
    assert log.event_counts["sentence_tatoeba_hit"] == 1
    assert providers.sentence_web_calls == 1


def test_process_word_uses_web_fallback_only_after_malformed_ai_batch(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)
    run.sentence_ai_attempts = 1
    ctx = ValidationContext()
    malformed_payload = _ai_sentence_fixture_payload("malformed_batch.json")

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
        sentence_web_calls = 0

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("adjective: en buen estado o calidad")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/bjen/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("byen")

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            try:
                StructuredSentenceBatch.model_validate(malformed_payload)
            except Exception as exc:
                return StructuredSentenceBatchResult(
                    batch=None,
                    provider_name="ai",
                    elapsed_ms=1,
                    error=f"structured_sentence_validation_error: {exc}",
                )
            raise AssertionError("malformed fixture should not validate")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_web_calls += 1
            return Result("Hoy me siento bien en casa.", provider_name="tatoeba")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            if text.startswith("adjective:"):
                return Result("adjective: in good condition or quality", provider_name="googletrans")
            return Result("I feel good at home today.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I feel good at home today.", provider_name="ai")

    providers = FakeProviders()
    card, log = builder._process_word(
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
    assert card.sentence == "Hoy me siento bien en casa."
    assert log.event_counts["sentence_ai_malformed_batch"] == 1
    assert log.event_counts["sentence_ai_low_yield_fallback"] == 1
    assert providers.sentence_web_calls == 1


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
    legacy_sentence_key = "exclus::lvl1::2-7::v4"

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

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=None,
                provider_name="ai",
                elapsed_ms=1,
                error="structured_sentence_validation_error: malformed batch",
            )

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_web_calls += 1
            return Result("Ce dossier exclus reste prive.", provider_name="tatoeba")

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
    source_key = "exclus::fr::v4"
    definition_key = "exclus::en::v4"
    sentence_key = "exclus::lvl1::5-7::sv2::v4"
    translation_key = f"{sentence}::fr->en::v4"

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


def test_process_word_refresh_text_cache_bypasses_cached_text(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path, language="fr")
    run.refresh_text_cache = True
    ctx = ValidationContext()

    class FakeCache:
        def get(self, kind, key):
            if kind in {"definitions", "sentences", "translations", "word_translations"}:
                return "stale cached text"
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
        definition_calls = 0
        sentence_calls = 0
        translation_calls = 0

        def word_exists(self, word, language):
            _ = (word, language)
            return Result(word, provider_name="wiktionary")

        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            self.definition_calls += 1
            return Result("adjective: reserve a un usage interne.")

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=None,
                provider_name="ai",
                elapsed_ms=1,
                error="structured_sentence_validation_error: malformed batch",
            )

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            self.sentence_calls += 1
            return Result("Ce dossier exclus reste prive.", provider_name="tatoeba")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            self.translation_calls += 1
            if text.startswith("adjective:"):
                return Result("adjective: restricted to internal use only.", provider_name="googletrans")
            return Result("This restricted file stays private.", provider_name="googletrans")

        def translation_ai(self, *args, **kwargs):
            raise AssertionError("translation_ai should not be needed")

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
    assert providers.definition_calls == 1
    assert providers.sentence_calls == 1
    assert providers.translation_calls >= 1


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

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=None,
                provider_name="ai",
                elapsed_ms=1,
                error="structured_sentence_validation_error: malformed batch",
            )

        def definition_ai(self, *args, **kwargs):
            raise AssertionError("definition_ai should not run when gloss is already usable")

        def definition_from_context(self, *args, **kwargs):
            raise AssertionError("definition_from_context should not run when gloss is already usable")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result(f"Он говорит, что {word} все понимают.", provider_name="tatoeba")

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


def test_process_word_accepts_single_word_english_gloss_for_russian(tmp_path: Path) -> None:
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
            return Result("noun: time", provider_name="wiktionary")

        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=None,
                provider_name="ai",
                elapsed_ms=1,
                error="structured_sentence_validation_error: malformed batch",
            )

        def definition_ai(self, *args, **kwargs):
            raise AssertionError("definition_ai should not run when gloss is usable")

        def definition_from_context(self, *args, **kwargs):
            raise AssertionError("definition_from_context should not run when gloss is usable")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Время идет быстро сегодня утром.", provider_name="tatoeba")

        def translation_web(self, text, src, dest):
            _ = (text, src, dest)
            return Result("Time passes quickly this morning.", provider_name="googletrans")

        def translation_ai(self, *args, **kwargs):
            raise AssertionError("translation_ai should not run")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/vrʲemʲə/", provider_name="ai")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("VRYE-mya", provider_name="ai")

    card, _log = builder._process_word(
        word="время",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
        ctx=ctx,
        media_files=[],
    )

    assert card is not None
    assert card.definition == "noun: time."


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
    assert providers.sentence_bounds[0] == (5, 7)


def test_build_resume_restores_rng_state_when_fingerprint_matches(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.resume = True
    fingerprint = builder._build_compatibility_fingerprint(run)
    saved_rng_state = random.Random(7).getstate()
    progress_path = tmp_path / "ankideck_generator" / "data" / "progress" / "es_test.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_state = ProgressState(
        language=run.language,
        mode=run.mode,
        schema_version=1,
        compatibility_fingerprint=fingerprint,
        level=2,
        index=-1,
        rng_state=saved_rng_state,
        processed_focus=["uno"],
        processed_sentences=["Frase para uno."],
        created_cards=1,
    )
    progress_path.write_text(
        json.dumps(progress_state.model_dump(), indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        builder,
        "_prepare_levels",
        lambda *args, **kwargs: {1: ["uno"], 2: ["dos"], 3: ["tres"]},
    )

    processed_words: list[str] = []

    def fake_process_word(*args, **kwargs):
        word = kwargs["word"]
        level = kwargs["level"]
        processed_words.append(word)
        return (
            CardData(
                focus=word,
                index=0,
                ipa=f"/{word}/",
                definition="noun: useful sample definition for this card.",
                sentence=f"Esta frase usa {word} con contexto claro.",
                translation=f"This sentence uses {word} with clear context.",
                level=level,
                language="es",
            ),
            LogRecord(
                focus=word,
                level=level,
                status="accepted",
                lifecycle_state="accepted",
            ),
        )

    restored_rng_state: dict[str, object] = {}

    monkeypatch.setattr(builder, "_process_word", fake_process_word)
    monkeypatch.setattr(
        deck_builder_module.random,
        "setstate",
        lambda state: restored_rng_state.setdefault("value", state),
    )

    cards, _ = builder.build(run)

    assert restored_rng_state["value"] == saved_rng_state
    assert processed_words == ["dos", "tres"]
    assert [card.index for card in cards] == [2, 3]


def test_build_quarantines_incompatible_progress_and_starts_clean(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.resume = True
    incompatible_fingerprint = builder._build_compatibility_fingerprint(run).model_copy(
        update={"digest": "stale"}
    )
    progress_path = tmp_path / "ankideck_generator" / "data" / "progress" / "es_test.json"
    progress_path.parent.mkdir(parents=True, exist_ok=True)
    progress_state = ProgressState(
        language=run.language,
        mode=run.mode,
        schema_version=1,
        compatibility_fingerprint=incompatible_fingerprint,
        level=2,
        index=0,
        rng_state=random.Random(3).getstate(),
        processed_focus=["uno"],
        processed_sentences=["Frase para uno."],
        created_cards=1,
    )
    progress_path.write_text(
        json.dumps(progress_state.model_dump(), indent=2),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        builder,
        "_prepare_levels",
        lambda *args, **kwargs: {1: ["uno"], 2: ["dos"], 3: ["tres"]},
    )

    processed_words: list[str] = []

    def fake_process_word(*args, **kwargs):
        word = kwargs["word"]
        level = kwargs["level"]
        processed_words.append(word)
        return (
            CardData(
                focus=word,
                index=0,
                ipa=f"/{word}/",
                definition="noun: useful sample definition for this card.",
                sentence=f"Esta frase usa {word} con contexto claro.",
                translation=f"This sentence uses {word} with clear context.",
                level=level,
                language="es",
            ),
            LogRecord(focus=word, level=level, status="accepted"),
        )

    monkeypatch.setattr(builder, "_process_word", fake_process_word)

    builder.build(run)

    assert processed_words == ["uno", "dos", "tres"]
    quarantined_files = list(progress_path.parent.glob("es_test.incompatible.*.json.quarantine"))
    assert len(quarantined_files) == 1


def test_build_checkpoints_wait_for_final_decisions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.level_size = 1
    run.concurrency = 2
    run.audio_concurrency = 2
    run.autosave_every = 1

    monkeypatch.setattr(
        builder,
        "_prepare_levels",
        lambda *args, **kwargs: {1: ["uno", "dos"], 2: [], 3: []},
    )

    captured_saves: list[ProgressState] = []

    def fake_save(self, state):
        captured_saves.append(state.model_copy(deep=True))

    def fake_text_task(word, level, index, run, cache):
        _ = (index, run, cache)
        if word == "dos":
            return TextTaskResult(
                candidate_index=1,
                card=None,
                log_record=LogRecord(
                    focus=word,
                    level=level,
                    status="discarded",
                    lifecycle_state="rejected",
                    discard_reason="definition_missing",
                    validations=["definition_missing"],
                ),
            )
        return TextTaskResult(
            candidate_index=0,
            card=CardData(
                focus=word,
                index=0,
                ipa=f"/{word}/",
                definition="noun: useful sample definition for this card.",
                sentence=f"Esta frase usa {word} con contexto claro.",
                translation=f"This sentence uses {word} with clear context.",
                level=level,
                language="es",
                lifecycle_state="generated",
            ),
            log_record=LogRecord(
                focus=word,
                level=level,
                status="candidate",
                lifecycle_state="generated",
            ),
        )

    def fake_audio_task(accepted_index, card, log_record, run, cache):
        _ = (accepted_index, run, cache)
        time.sleep(0.05)
        card.word_audio = f"[sound:{card.focus}.mp3]"
        card.sentence_audio = f"[sound:{card.focus}_sentence.mp3]"
        card.audio = card.word_audio
        return AudioTaskResult(
            accepted_index=accepted_index,
            card=card,
            log_record=log_record,
            media_files=[f"media/{card.focus}.mp3"],
        )

    monkeypatch.setattr(deck_builder_module.ProgressStore, "save", fake_save)
    monkeypatch.setattr(builder, "_process_word_textual_task", fake_text_task)
    monkeypatch.setattr(builder, "_attach_audio_task", fake_audio_task)

    builder.build(run)

    assert captured_saves[0].index == -1
    assert captured_saves[0].created_cards == 0
    assert any(state.created_cards == 1 for state in captured_saves[1:])


def test_write_quality_outputs_only_rejected_cards_enter_review_queue(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.review_queue_path = str(tmp_path / "output" / "review_queue.json")
    run.quality_report_path = str(tmp_path / "output" / "quality_report.json")

    stats = BuildStats()
    logger = deck_builder_module.JsonLogger(tmp_path / "run.jsonl")
    stats.cards.append(
        CardData(
            focus="bien",
            definition="adjective: in good condition or quality.",
            sentence="Hoy me siento bien en casa.",
            translation="I feel good at home today.",
            level=1,
            language="es",
        )
    )
    stats.attempted_by_level[1] = 2
    stats.accepted_by_level[1] = 1
    stats.validation_counter["definition_missing"] = 1
    stats.definition_source_counter["translated_source"] = 1
    stats.ambiguous_focus_counter["bien"] = 1
    stats.definition_score_total = 1.6
    stats.definition_score_samples = 2

    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="bien",
            level=1,
            status="accepted",
            lifecycle_state="accepted",
            review_notes=["definition_corrected"],
            before={"definition": "old gloss"},
            after={"definition": "new gloss"},
        ),
    )
    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="mal",
            level=1,
            status="discarded",
            lifecycle_state="rejected",
            discard_reason="definition_missing",
            reason_codes=["definition_missing"],
            review_notes=["definition_polysemy_detected"],
            provider="groq",
            model="llama-3.1-8b-instant",
        ),
    )

    builder._write_quality_outputs(run, stats)

    report = json.loads(Path(run.quality_report_path).read_text(encoding="utf-8"))
    review_queue = json.loads(Path(run.review_queue_path).read_text(encoding="utf-8"))

    assert report["needs_review"] == 1
    assert report["accepted_with_corrections"] == 1
    assert report["definition_sources"]["translated_source"] == 1
    assert report["definition_score"]["average"] == 0.8
    assert "provider_success_counter" in report
    assert "provider_error_counter" in report
    assert [item["focus"] for item in review_queue] == ["mal"]
    assert review_queue[0]["reason_codes"] == ["definition_missing"]


def test_write_quality_outputs_duplicate_review_queue_artifact_shape(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.review_queue_path = str(tmp_path / "output" / "review_queue.json")
    run.quality_report_path = str(tmp_path / "output" / "quality_report.json")

    stats = BuildStats()
    logger = deck_builder_module.JsonLogger(tmp_path / "run.jsonl")

    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="house",
            level=1,
            status="discarded",
            lifecycle_state="rejected",
            discard_reason="duplicate_rejected",
            reason_codes=["duplicate_sentence_near"],
            validations=["duplicate_sentence_near"],
            review_notes=["definition_low_translation_alignment"],
            providers={"definition": "googletrans", "translation": "googletrans"},
            after={
                "focus": "house",
                "sentence": "I see the bright old house today again.",
                "definition": "noun: a building for people to live in.",
                "translation": "I see the bright old house today again.",
                "source_definition": "noun: house.",
                "ipa": "/haʊs/",
            },
            duplicate_evidence=DuplicateDecisionEvidence(
                kind="near",
                focus="house",
                candidate_sentence="I see the bright old house today again.",
                matched_sentence="I see the bright old house today.",
                normalized_sentence="i see the bright old house today again",
                bucket_key="house::i see the bright old house today",
                similarity=0.95,
            ),
        ),
    )

    builder._write_quality_outputs(run, stats)

    review_queue = json.loads(Path(run.review_queue_path).read_text(encoding="utf-8"))
    item = review_queue[0]

    assert item["card_snapshot"] == {
        "focus": "house",
        "sentence": "I see the bright old house today again.",
        "definition": "noun: a building for people to live in.",
        "translation": "I see the bright old house today again.",
        "source_definition": "noun: house.",
        "ipa": "/haʊs/",
    }
    assert item["changed_fields"] == [
        "definition",
        "focus",
        "ipa",
        "sentence",
        "source_definition",
        "translation",
    ]
    assert item["hard_validation_errors"] == ["duplicate_sentence_near"]
    assert item["review_flags"] == ["definition_low_translation_alignment"]
    assert item["duplicate_evidence"]["kind"] == "near"
    assert item["duplicate_evidence"]["matched_sentence"] == "I see the bright old house today."
    assert item["field_providers"] == {
        "definition": "googletrans",
        "translation": "googletrans",
    }
    assert item["decision_source"] == {
        "stage": "duplicate_guard",
        "provider": "duplicate_guard",
        "model": "sequence_matcher@0.90",
    }


def test_review_queue_preserves_decision_source_and_field_providers(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    stats = BuildStats()
    logger = deck_builder_module.JsonLogger(tmp_path / "run.jsonl")

    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="banco",
            level=1,
            status="discarded",
            lifecycle_state="rejected",
            discard_reason="lexical_review_rejected",
            reason_codes=["lexical_review_unresolved_ambiguity"],
            validations=[],
            review_notes=["lexical_review_rejected"],
            providers={
                "definition": "wiktionary",
                "translation": "googletrans",
                "lexical_review": "ai",
            },
            provider="ai",
            model="llama-3.1-8b-instant",
            after={
                "focus": "banco",
                "sentence": "Vi el banco cerca del rio.",
                "definition": "noun: bank",
                "translation": "I saw the bank near the river.",
                "source_definition": "noun: banco.",
                "ipa": "",
            },
        ),
    )

    item = stats.needs_review_items[0]

    assert item["field_providers"] == {
        "definition": "wiktionary",
        "translation": "googletrans",
        "lexical_review": "ai",
    }
    assert item["decision_source"] == {
        "stage": "review",
        "provider": "ai",
        "model": "llama-3.1-8b-instant",
    }
    assert item["hard_validation_errors"] == []
    assert item["review_flags"] == ["lexical_review_rejected"]


def test_write_quality_outputs_reports_duplicate_diagnostics_sections(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.review_queue_path = str(tmp_path / "output" / "review_queue.json")
    run.quality_report_path = str(tmp_path / "output" / "quality_report.json")

    stats = BuildStats()
    logger = deck_builder_module.JsonLogger(tmp_path / "run.jsonl")
    stats.cards.extend(
        [
            CardData(
                focus="home",
                definition="noun: a place where someone lives.",
                sentence="Home feels calm tonight.",
                translation="Home feels calm tonight.",
                level=1,
                language="en",
            ),
            CardData(
                focus="house",
                definition="noun: a building for people to live in.",
                sentence="The house is bright today.",
                translation="The house is bright today.",
                level=1,
                language="en",
            ),
        ]
    )
    stats.attempted_by_level[1] = 4
    stats.accepted_by_level[1] = 2

    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="house",
            level=1,
            status="accepted",
            lifecycle_state="accepted",
            review_notes=["definition_corrected"],
            before={"definition": "old gloss"},
            after={"definition": "noun: a building for people to live in."},
        ),
    )
    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="house",
            level=1,
            status="discarded",
            lifecycle_state="rejected",
            discard_reason="duplicate_rejected",
            reason_codes=["duplicate_sentence_exact"],
            validations=["duplicate_sentence_exact"],
            after={"focus": "house", "sentence": "The house is bright today."},
            duplicate_evidence=DuplicateDecisionEvidence(
                kind="exact",
                focus="house",
                candidate_sentence="The house is bright today.",
                matched_sentence="The house is bright today.",
                normalized_sentence="the house is bright today",
                bucket_key="house::the house is bright today",
                similarity=1.0,
            ),
        ),
    )
    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="house",
            level=1,
            status="discarded",
            lifecycle_state="rejected",
            discard_reason="duplicate_rejected",
            reason_codes=["duplicate_sentence_near"],
            validations=["duplicate_sentence_near"],
            review_notes=["definition_low_translation_alignment"],
            after={"focus": "house", "sentence": "The bright house feels sunny today."},
            duplicate_evidence=DuplicateDecisionEvidence(
                kind="near",
                focus="house",
                candidate_sentence="The bright house feels sunny today.",
                matched_sentence="The house is bright today.",
                normalized_sentence="the bright house feels sunny today",
                bucket_key="house::the house is bright today",
                similarity=0.92,
            ),
        ),
    )

    builder._write_quality_outputs(run, stats)

    report = json.loads(Path(run.quality_report_path).read_text(encoding="utf-8"))

    assert report["accepted_card_rate"] == 0.5
    assert report["duplicate_reject_rate"] == 0.5
    assert report["accepted_with_corrections"] == 1
    assert report["acceptance_quality"] == {
        "accepted_cards": 2,
        "accepted_card_rate": 0.5,
        "clean_accepts": 1,
        "corrected_accepts": 1,
    }
    assert report["duplicate_diagnostics"] == {
        "overall": {"exact": 1, "near": 1, "total": 2},
        "by_level": {"1": {"exact": 1, "near": 1, "total": 2}},
        "exact_rejects": 1,
        "near_rejects": 1,
        "duplicate_reject_rate": 0.5,
    }
    assert report["review_diagnostics"] == {
        "queue_items": 2,
        "top_reason_codes": {
            "duplicate_sentence_exact": 1,
            "duplicate_sentence_near": 1,
        },
        "hard_validation_errors": {
            "duplicate_sentence_exact": 1,
            "duplicate_sentence_near": 1,
        },
        "review_flags": {"definition_low_translation_alignment": 1},
    }


def test_process_word_records_lexical_review_stage_timing(tmp_path: Path) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"]["enabled"] = False
    run = _run_config(tmp_path)

    class FakeCache:
        def get(self, *_args, **_kwargs):
            return None

        def set(self, *_args, **_kwargs):
            return None

    class Result:
        def __init__(self, value: str, provider_name: str = "ai", elapsed_ms: int = 1):
            self.value = value
            self.provider_name = provider_name
            self.elapsed_ms = elapsed_ms
            self.error = None

    class ReviewTransport:
        def __init__(self, review: LexicalReviewResult):
            self.review = review
            self.provider_name = "ai"
            self.elapsed_ms = 17
            self.error = None

    class FakeProviders:
        def definition(self, word, language, allow_ai=True, definition_language=None):
            _ = (word, language, allow_ai, definition_language)
            return Result("noun: bench in a park or public place")

        def ipa(self, word, language, allow_ai=True):
            _ = (word, language, allow_ai)
            return Result("/ˈbaŋ.ko/")

        def phonetic_spelling(self, ipa, language, allow_ai=True):
            _ = (ipa, language, allow_ai)
            return Result("BAN-ko")

        def sentence_web(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Me sente en el banco del parque.", provider_name="tatoeba")

        def sentence_ai(self, word, language, level=None, **kwargs):
            _ = (word, language, level, kwargs)
            return Result("Me sente en el banco del parque.")

        def translation_web(self, text, src, dest):
            _ = (src, dest)
            if text.startswith("noun:"):
                return Result("noun: bench in a park or public place", provider_name="googletrans")
            return Result("I sat on the bench in the park.", provider_name="googletrans")

        def translation_ai(self, text, src, dest):
            _ = (text, src, dest)
            return Result("I sat on the bench in the park.")

        def lexical_review(self, request, **kwargs):
            _ = kwargs
            return ReviewTransport(
                LexicalReviewResult.model_validate(
                    {
                        "verdict": "accept",
                        "focus_word": request.focus_word,
                        "language": request.language,
                        "target_translation_language": request.target_translation_language,
                        "accepted_sentence": request.accepted_sentence,
                        "current_definition": request.current_definition,
                        "current_translation": request.current_translation,
                        "source_definition": request.source_definition,
                        "candidate_senses": list(request.candidate_senses),
                        "winning_sense": request.current_definition,
                        "reason_codes": [],
                        "selection_reasons": {"winning_sense": "already_aligned"},
                    }
                )
            )

    card, log = builder._process_word_textual(
        word="banco",
        level=1,
        index=1,
        run=run,
        cache=FakeCache(),
        providers=FakeProviders(),
    )

    assert card is not None
    assert log.providers["lexical_review"] == "ai"
    assert log.stage_timings["lexical_review_ms"] == 17


def test_write_quality_outputs_reports_runtime_guardrails_and_latency_per_accepted_card(
    tmp_path: Path,
) -> None:
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = _run_config(tmp_path)
    run.review_queue_path = str(tmp_path / "output" / "review_queue.json")
    run.quality_report_path = str(tmp_path / "output" / "quality_report.json")

    stats = BuildStats()
    logger = deck_builder_module.JsonLogger(tmp_path / "run.jsonl")
    stats.cards.append(
        CardData(
            focus="banco",
            definition="noun: bench in a park or public place.",
            sentence="Me sente en el banco del parque.",
            translation="I sat on the bench in the park.",
            level=1,
            language="es",
        )
    )
    stats.attempted_by_level[1] = 2
    stats.accepted_by_level[1] = 1

    builder._record_log(
        logger,
        stats,
        LogRecord(
            focus="banco",
            level=1,
            status="accepted",
            lifecycle_state="accepted",
            providers={"lexical_review": "ai", "translation": "googletrans"},
            stage_timings={"lexical_review_ms": 17, "translation_ms": 5},
            event_counts={
                "ai_stage_usage.lexical_review": 1,
                "ai_stage_budget_exhausted.lexical_review": 1,
            },
        ),
    )

    builder._write_quality_outputs(run, stats)

    report = json.loads(Path(run.quality_report_path).read_text(encoding="utf-8"))

    assert report["stage_latency_ms"] == {
        "lexical_review": 17,
        "translation": 5,
    }
    assert report["ai_budget_usage"] == {
        "total_ai_calls": 1,
        "by_stage": {"lexical_review": 1},
    }
    assert report["runtime_guardrails"] == {
        "stage_budget_exhausted": {"lexical_review": 1},
    }
    assert report["latency_per_accepted_card_ms"] == {
        "accepted_cards": 1,
        "total_runtime_ms": 22,
        "overall": 22.0,
        "by_stage": {
            "lexical_review": 17.0,
            "translation": 5.0,
        },
    }


def test_cleanup_run_artifacts_preserves_logs_when_enabled_for_evaluation(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config.setdefault("runtime", {})["cleanup_generated_artifacts"] = True
    run = _run_config(tmp_path)
    object.__setattr__(run, "preserve_evaluation_logs", True)

    cache_dir = Path(run.cache_path)
    cache_dir.mkdir(parents=True)
    (cache_dir / "cache.json").write_text("{}", encoding="utf-8")
    progress_dir = Path("ankideck_generator/data/progress")
    progress_dir.mkdir(parents=True)
    (progress_dir / "es_test.json").write_text("{}", encoding="utf-8")
    log_dir = Path("ankideck_generator/data/logs")
    log_dir.mkdir(parents=True)
    log_path = log_dir / "run-test.jsonl"
    log_path.write_text('{"focus":"banco"}\n', encoding="utf-8")
    builder._last_run_log_path = str(log_path)

    builder._cleanup_run_artifacts(
        run,
        cleanup_audio=False,
        audio_dir=tmp_path / "audio",
        media_files=[],
    )

    assert not cache_dir.exists()
    assert not progress_dir.exists()
    assert log_path.exists()
