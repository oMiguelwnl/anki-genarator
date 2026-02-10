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
