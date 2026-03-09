from ankideck_generator.core.models import CardData
from ankideck_generator.core.validators import ValidationContext, validate_card


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


def test_validate_card_russian_required_fields() -> None:
    card = CardData(
        focus="ц",
        sentence="В цирке есть цирковые артисты.",
        translation="In the circus there are circus performers.",
        ipa="/ts/",
        spellings="",
        example_word="цирк",
        word_translation="circus",
        letter_audio="",
        level=1,
        language="ru",
    )
    ctx = ValidationContext()
    errors = validate_card(
        card,
        ctx,
        {
            "definition_required": False,
            "ipa_required": True,
            "translation_required": True,
            "spellings_required": True,
            "example_word_required": True,
            "word_translation_required": True,
            "letter_audio_required": True,
            "no_duplicate_focus": False,
            "no_duplicate_sentences": False,
            "focus_in_sentence": False,
            "example_word_in_sentence": True,
            "valid_characters": False,
            "ipa_format": True,
            "audio_generated": False,
            "definition_not_literal_translation": False,
            "sentence_length": (5, 25),
            "sentence_difficulty_matches_level": False,
        },
    )
    assert "spellings_missing" in errors
    assert "letter_audio_missing" in errors
