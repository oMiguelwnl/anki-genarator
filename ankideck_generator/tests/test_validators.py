from ankideck_generator.core.models import CardData
from ankideck_generator.core.validators import ValidationContext, validate_card
import ankideck_generator.core.validators as validators_module


def test_validate_card_focus_in_sentence() -> None:
    card = CardData(
        focus="hello",
        sentence="this is a test",
        level=1,
        language="en",
        audio="sound",
    )
    ctx = ValidationContext()
    errors = validate_card(card, ctx, {
        "definition_required": False,
        "ipa_required": False,
        "translation_required": False,
        "focus_in_sentence": True,
        "no_duplicate_focus": False,
        "no_duplicate_sentences": False,
        "valid_characters": False,
        "ipa_format": False,
        "audio_generated": False,
        "definition_not_literal_translation": False,
        "sentence_length": (1, 20),
        "sentence_difficulty_matches_level": False,
    })
    assert "focus_not_in_sentence" in errors


def test_validate_card_ipa_with_pronunciation_suffix() -> None:
    card = CardData(
        focus="hello",
        sentence="hello there",
        level=1,
        language="en",
        ipa="/heh-lo/ (huh-LOH)",
    )
    ctx = ValidationContext()
    errors = validate_card(card, ctx, {
        "definition_required": False,
        "ipa_required": True,
        "translation_required": False,
        "focus_in_sentence": False,
        "no_duplicate_focus": False,
        "no_duplicate_sentences": False,
        "valid_characters": False,
        "ipa_format": True,
        "audio_generated": False,
        "definition_not_literal_translation": False,
        "sentence_length": (1, 20),
        "sentence_difficulty_matches_level": False,
    })
    assert "invalid_ipa" not in errors


def test_validate_card_requires_word_and_sentence_audio() -> None:
    card = CardData(
        focus="hello",
        sentence="hello there",
        level=1,
        language="en",
        word_audio="",
        sentence_audio="",
    )
    ctx = ValidationContext()
    errors = validate_card(card, ctx, {
        "definition_required": False,
        "ipa_required": False,
        "translation_required": False,
        "focus_in_sentence": True,
        "no_duplicate_focus": False,
        "no_duplicate_sentences": False,
        "valid_characters": False,
        "ipa_format": False,
        "audio_generated": False,
        "word_audio_required": True,
        "sentence_audio_required": True,
        "definition_not_literal_translation": False,
        "sentence_length": (1, 20),
        "sentence_difficulty_matches_level": False,
    })
    assert "word_audio_missing" in errors
    assert "sentence_audio_missing" in errors


def test_validate_card_rejects_wrong_sentence_language() -> None:
    card = CardData(
        focus="exclus",
        sentence="I exclusively drink bottled water.",
        level=1,
        language="fr",
    )
    ctx = ValidationContext()
    errors = validate_card(card, ctx, {
        "definition_required": False,
        "definition_semantic": False,
        "definition_matches_translation_language": False,
        "source_definition_matches_language": False,
        "ipa_required": False,
        "translation_required": False,
        "focus_in_sentence": True,
        "sentence_matches_language": True,
        "no_duplicate_focus": False,
        "no_duplicate_sentences": False,
        "valid_characters": False,
        "ipa_format": False,
        "audio_generated": False,
        "definition_not_literal_translation": False,
        "sentence_length": {1: (1, 20)},
        "sentence_difficulty_matches_level": False,
    })
    assert "sentence_wrong_language" in errors


def test_validate_card_rejects_nonsemantic_definition() -> None:
    card = CardData(
        focus="interessait",
        definition="verb: simple past of interest.",
        sentence="Ce sujet interessait tout le groupe hier soir.",
        level=1,
        language="fr",
        translation_language="en",
    )
    ctx = ValidationContext()
    errors = validate_card(card, ctx, {
        "definition_required": True,
        "definition_semantic": True,
        "definition_matches_translation_language": True,
        "source_definition_matches_language": False,
        "ipa_required": False,
        "translation_required": False,
        "focus_in_sentence": True,
        "sentence_matches_language": False,
        "no_duplicate_focus": False,
        "no_duplicate_sentences": False,
        "valid_characters": False,
        "ipa_format": False,
        "audio_generated": False,
        "definition_not_literal_translation": False,
        "sentence_length": {1: (1, 20)},
        "sentence_difficulty_matches_level": False,
    })
    assert "definition_nonsemantic" in errors


def test_validate_card_requires_definition_pos() -> None:
    card = CardData(
        focus="madrugada",
        definition="The early hours before dawn in the night.",
        sentence="La madrugada fue tranquila y silenciosa en el barrio.",
        level=1,
        language="es",
        translation_language="en",
    )
    ctx = ValidationContext()
    errors = validate_card(card, ctx, {
        "definition_required": True,
        "definition_semantic": True,
        "definition_requires_pos": True,
        "definition_matches_translation_language": True,
        "source_definition_matches_language": False,
        "ipa_required": False,
        "translation_required": False,
        "focus_in_sentence": True,
        "sentence_matches_language": False,
        "no_duplicate_focus": False,
        "no_duplicate_sentences": False,
        "valid_characters": False,
        "ipa_format": False,
        "audio_generated": False,
        "definition_not_literal_translation": False,
        "sentence_length": {1: (1, 20)},
        "sentence_difficulty_matches_level": False,
    })
    assert "definition_missing_pos" in errors


def test_validate_card_profile_hard_zipf_soft_skips_level2_and_level3_zipf_errors(
    monkeypatch,
) -> None:
    scores = iter([1.5, 5.8])

    class FakeDifficulty:
        def __init__(self, average_zipf: float):
            self.average_zipf = average_zipf

    monkeypatch.setattr(
        validators_module,
        "difficulty",
        lambda sentence, language: FakeDifficulty(next(scores)),
    )

    ctx = ValidationContext()
    validations = {
        "definition_required": False,
        "ipa_required": False,
        "translation_required": False,
        "focus_in_sentence": True,
        "sentence_matches_language": False,
        "no_duplicate_focus": False,
        "no_duplicate_sentences": False,
        "valid_characters": False,
        "ipa_format": False,
        "audio_generated": False,
        "definition_not_literal_translation": False,
        "sentence_length": {2: (4, 10), 3: (6, 15)},
        "sentence_profile": {
            2: {"max_commas": 1, "forbid_clause_punctuation": True},
            3: {"max_commas": 1, "forbid_clause_punctuation": True},
        },
        "sentence_difficulty_matches_level": True,
        "level_validation_mode": "profile_hard_zipf_soft",
    }

    level2_errors = validate_card(
        CardData(
            focus="bien",
            sentence="Hoy me siento bien en casa.",
            level=2,
            language="es",
        ),
        ctx,
        validations,
        commit=False,
    )
    level3_errors = validate_card(
        CardData(
            focus="tema",
            sentence="Este tema sigue tema en debate interno ahora.",
            level=3,
            language="es",
        ),
        ctx,
        validations,
        commit=False,
    )

    assert "sentence_not_level2" not in level2_errors
    assert "sentence_too_easy_for_level3" not in level3_errors


