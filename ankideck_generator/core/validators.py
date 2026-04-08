from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from ..utils.definition_tools import definition_has_pos
from ..utils.language_tools import (
    difficulty,
    is_semantic_definition,
    text_contains_focus,
    text_matches_language,
    valid_focus_characters,
    valid_sentence_characters,
)
from .models import CardData

IPA_RE = re.compile(r"^/[^/]+/(?:\s*\([^()]+\))?$")
CLAUSE_PUNCTUATION = {";", ":"}


@dataclass
class ValidationContext:
    seen_focus: set[str] = field(default_factory=set)
    seen_sentence: set[str] = field(default_factory=set)


def validate_card(
    card: CardData,
    ctx: ValidationContext,
    validations: dict[str, object],
    *,
    commit: bool = True,
) -> list[str]:
    errors: list[str] = []

    if validations.get("spellings_required"):
        if not card.spellings:
            errors.append("spellings_missing")

    if validations.get("example_word_required"):
        if not card.example_word:
            errors.append("example_word_missing")

    if validations.get("word_translation_required"):
        if not card.word_translation:
            errors.append("word_translation_missing")

    if validations.get("letter_audio_required"):
        if not card.letter_audio:
            errors.append("letter_audio_missing")

    if validations.get("word_audio_required"):
        if not card.word_audio:
            errors.append("word_audio_missing")

    if validations.get("sentence_audio_required"):
        if not card.sentence_audio:
            errors.append("sentence_audio_missing")

    if validations.get("definition_required"):
        if not card.definition:
            errors.append("definition_missing")

    if validations.get("definition_semantic"):
        if card.definition and not is_semantic_definition(card.definition, card.focus):
            errors.append("definition_nonsemantic")

    if validations.get("definition_requires_pos"):
        if card.definition and not definition_has_pos(card.definition):
            errors.append("definition_missing_pos")

    if validations.get("ipa_required"):
        if not card.ipa:
            errors.append("ipa_missing")

    if validations.get("translation_required"):
        if not card.translation:
            errors.append("translation_missing")

    if validations.get("no_duplicate_focus"):
        if card.focus.lower() in ctx.seen_focus:
            errors.append("duplicate_focus")

    if validations.get("no_duplicate_sentences"):
        if card.sentence.lower() in ctx.seen_sentence:
            errors.append("duplicate_sentence")

    if validations.get("focus_in_sentence"):
        if not text_contains_focus(card.sentence, card.focus):
            errors.append("focus_not_in_sentence")

    if validations.get("sentence_matches_language"):
        if card.sentence and not text_matches_language(
            card.sentence, card.language, min_score=0.55, min_tokens=3
        ):
            errors.append("sentence_wrong_language")

    if validations.get("source_definition_matches_language"):
        if card.source_definition:
            body = (
                card.source_definition.split(":", 1)[1].strip()
                if ":" in card.source_definition
                else card.source_definition.strip()
            )
            alpha_tokens = [
                token for token in body.split() if any(char.isalpha() for char in token)
            ]
            if len(alpha_tokens) >= 2 and not text_matches_language(
                body, card.language, min_score=0.25, min_tokens=2
            ):
                errors.append("source_definition_wrong_language")

    if validations.get("definition_matches_translation_language"):
        expected_language = card.translation_language or "en"
        if card.definition:
            body = (
                card.definition.split(":", 1)[1].strip()
                if ":" in card.definition
                else card.definition.strip()
            )
            alpha_tokens = [
                token for token in body.split() if any(char.isalpha() for char in token)
            ]
            if len(alpha_tokens) >= 2 and not text_matches_language(
                body, expected_language, min_score=0.25, min_tokens=2
            ):
                errors.append("definition_wrong_language")

    if validations.get("example_word_in_sentence"):
        if card.example_word and not text_contains_focus(card.sentence, card.example_word):
            errors.append("example_word_not_in_sentence")

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
            ratio = SequenceMatcher(
                None, card.definition.lower(), card.translation.lower()
            ).ratio()
            if ratio > 0.85:
                errors.append("definition_too_similar_translation")

    length_config = validations.get("sentence_length")
    if isinstance(length_config, dict):
        length_range = length_config.get(card.level)
        if isinstance(length_range, (list, tuple)) and len(length_range) == 2:
            min_len, max_len = length_range
            word_count = len(card.sentence.split())
            if not (min_len <= word_count <= max_len):
                errors.append("sentence_length_invalid")

    profile_error = _sentence_profile_error(
        card.sentence,
        card.level,
        validations.get("sentence_profile"),
    )
    if profile_error:
        errors.append(profile_error)

    if validations.get("sentence_difficulty_matches_level"):
        score = difficulty(card.sentence, card.language)
        avg = score.average_zipf
        level_validation_mode = str(
            validations.get("level_validation_mode", "zipf_hard")
        ).strip() or "zipf_hard"
        if level_validation_mode == "profile_hard_zipf_soft":
            if card.level == 1 and avg < 3.0:
                errors.append("sentence_too_hard_for_level1")
        else:
            if card.level == 1 and avg < 3.0:
                errors.append("sentence_too_hard_for_level1")
            if card.level == 2 and not (2.5 <= avg <= 5.0):
                errors.append("sentence_not_level2")
            if card.level == 3 and avg > 4.5:
                errors.append("sentence_too_easy_for_level3")

    if not errors and commit:
        ctx.seen_focus.add(card.focus.lower())
        ctx.seen_sentence.add(card.sentence.lower())

    return errors


def _sentence_profile_error(
    sentence: str,
    level: int,
    profile_config: object,
) -> str | None:
    if not isinstance(profile_config, dict):
        return None
    level_profile = profile_config.get(level)
    if not isinstance(level_profile, dict):
        return None

    max_commas = level_profile.get("max_commas")
    if isinstance(max_commas, int) and sentence.count(",") > max_commas:
        return "sentence_profile_invalid"

    forbid_clause_punctuation = bool(level_profile.get("forbid_clause_punctuation", False))
    if forbid_clause_punctuation and any(mark in sentence for mark in CLAUSE_PUNCTUATION):
        return "sentence_profile_invalid"

    return None
