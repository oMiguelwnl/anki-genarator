from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..utils.language_tools import difficulty, valid_focus_characters, valid_sentence_characters
from .models import CardData

IPA_RE = re.compile(r"^[\s\./ˈˌa-zA-Zɐɑɒæɓɔçðɘəɛɜɞɡɪɯɲŋɵøœʃʊʌʒʔːˑ˞̃ˠˤʼʲʰ]+$")


@dataclass
class ValidationContext:
    seen_focus: set[str] = field(default_factory=set)
    seen_sentence: set[str] = field(default_factory=set)


def validate_card(card: CardData, ctx: ValidationContext, validations: dict[str, object]) -> list[str]:
    errors: list[str] = []

    if validations.get("definition_required"):
        if not card.definition:
            errors.append("definition_missing")

    if validations.get("ipa_required"):
        if not card.ipa:
            errors.append("ipa_missing")

    if validations.get("translation_required"):
        if card.level in {1, 2} and not card.translation:
            errors.append("translation_missing")

    if validations.get("no_duplicate_focus"):
        if card.focus.lower() in ctx.seen_focus:
            errors.append("duplicate_focus")

    if validations.get("no_duplicate_sentences"):
        if card.sentence.lower() in ctx.seen_sentence:
            errors.append("duplicate_sentence")

    if validations.get("focus_in_sentence"):
        if card.focus.lower() not in card.sentence.lower():
            errors.append("focus_not_in_sentence")

    if validations.get("valid_characters"):
        if not valid_focus_characters(card.focus):
            errors.append("invalid_focus_characters")
        if not valid_sentence_characters(card.sentence):
            errors.append("invalid_sentence_characters")

    if validations.get("ipa_format"):
        if card.ipa and not IPA_RE.match(card.ipa):
            errors.append("invalid_ipa")

    if validations.get("audio_generated"):
        if not card.audio:
            errors.append("audio_missing")

    if validations.get("definition_not_literal_translation"):
        if (
            card.definition
            and card.translation
            and card.translation_language
            and card.translation_language != card.language
        ):
            ratio = SequenceMatcher(None, card.definition.lower(), card.translation.lower()).ratio()
            if ratio > 0.85:
                errors.append("definition_too_similar_translation")

    length_range = validations.get("sentence_length")
    if isinstance(length_range, (list, tuple)) and len(length_range) == 2:
        min_len, max_len = length_range
        word_count = len(card.sentence.split())
        if not (min_len <= word_count <= max_len):
            errors.append("sentence_length_invalid")

    if validations.get("sentence_difficulty_matches_level"):
        score = difficulty(card.sentence, card.language)
        avg = score.average_zipf
        if card.level == 1 and avg < 3.0:
            errors.append("sentence_too_hard_for_level1")
        if card.level == 2 and not (2.5 <= avg <= 5.0):
            errors.append("sentence_not_level2")
        if card.level == 3 and avg > 4.5:
            errors.append("sentence_too_easy_for_level3")

    if not errors:
        ctx.seen_focus.add(card.focus.lower())
        ctx.seen_sentence.add(card.sentence.lower())

    return errors
