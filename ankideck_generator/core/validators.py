from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
import unicodedata

from ..utils.definition_tools import definition_has_pos
from ..utils.language_tools import (
    difficulty,
    is_semantic_definition,
    text_contains_focus,
    text_matches_language,
    valid_focus_characters,
    valid_sentence_characters,
)
from .models import CardData, DuplicateDecisionEvidence

IPA_RE = re.compile(r"^/[^/]+/(?:\s*\([^()]+\))?$")
CLAUSE_PUNCTUATION = {";", ":"}
ARTIFICIAL_SENTENCE_PATTERNS = [
    re.compile(r"\bthis\s+(?:sentence|word|example)\b", re.IGNORECASE),
    re.compile(r"\bin\s+this\s+example\b", re.IGNORECASE),
    re.compile(r"\besta\s+(?:frase|oracion|palabra|ejemplo)\b", re.IGNORECASE),
    re.compile(r"\bcette\s+(?:phrase|exemple)\b", re.IGNORECASE),
    re.compile(r"\bce\s+mot\b", re.IGNORECASE),
    re.compile(r"\bquesta\s+(?:frase|parola|esempio)\b", re.IGNORECASE),
    re.compile(r"\bdies(?:er|es)\s+(?:satz|wort|beispiel)\b", re.IGNORECASE),
    re.compile(r"\bэто\s+слово\b", re.IGNORECASE),
    re.compile(r"\bв\s+этом\s+примере\b", re.IGNORECASE),
]
DUPLICATE_SHORTLIST_LIMIT = 12
NEAR_DUPLICATE_SENTENCE_THRESHOLD = 0.90
_DUPLICATE_PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)


@dataclass
class ValidationContext:
    seen_focus: set[str] = field(default_factory=set)
    seen_sentence: set[str] = field(default_factory=set)
    accepted_sentences_by_focus: dict[str, list[str]] = field(default_factory=dict)
    accepted_sentence_buckets: dict[str, str] = field(default_factory=dict)
    last_duplicate_evidence: DuplicateDecisionEvidence | None = None


def normalize_duplicate_focus(value: str) -> str:
    return _normalize_duplicate_text(value)


def normalize_duplicate_sentence(sentence: str) -> str:
    return _normalize_duplicate_text(sentence)


def remember_accepted_card(ctx: ValidationContext, focus: str, sentence: str) -> None:
    focus_key = normalize_duplicate_focus(focus)
    sentence_key = normalize_duplicate_sentence(sentence)

    if focus_key:
        ctx.seen_focus.add(focus_key)
    if sentence_key:
        ctx.seen_sentence.add(sentence_key)

    if not focus_key or not sentence_key:
        return

    bucket_key = _duplicate_bucket_key(focus_key, sentence_key)
    ctx.accepted_sentence_buckets.setdefault(bucket_key, sentence)
    focus_bucket = ctx.accepted_sentences_by_focus.setdefault(focus_key, [])
    if sentence not in focus_bucket:
        focus_bucket.append(sentence)


def validate_card(
    card: CardData,
    ctx: ValidationContext,
    validations: dict[str, object],
    *,
    commit: bool = True,
) -> list[str]:
    errors: list[str] = []
    ctx.last_duplicate_evidence = None

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
        if normalize_duplicate_focus(card.focus) in ctx.seen_focus:
            errors.append("duplicate_focus")

    if validations.get("no_duplicate_sentences"):
        duplicate_error, duplicate_evidence = _duplicate_sentence_error(card, ctx)
        if duplicate_error:
            errors.append(duplicate_error)
            ctx.last_duplicate_evidence = duplicate_evidence

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
        remember_accepted_card(ctx, card.focus, card.sentence)

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

    if any(pattern.search(sentence) for pattern in ARTIFICIAL_SENTENCE_PATTERNS):
        return "sentence_profile_invalid"

    return None


def _duplicate_sentence_error(
    card: CardData,
    ctx: ValidationContext,
) -> tuple[str | None, DuplicateDecisionEvidence | None]:
    focus_key = normalize_duplicate_focus(card.focus)
    sentence_key = normalize_duplicate_sentence(card.sentence)
    if not focus_key or not sentence_key:
        return None, None

    bucket_key = _duplicate_bucket_key(focus_key, sentence_key)
    matched_sentence = ctx.accepted_sentence_buckets.get(bucket_key)
    if matched_sentence is not None:
        return "duplicate_sentence_exact", DuplicateDecisionEvidence(
            kind="exact",
            focus=card.focus,
            candidate_sentence=card.sentence,
            matched_sentence=matched_sentence,
            normalized_sentence=sentence_key,
            bucket_key=bucket_key,
            similarity=1.0,
        )

    for shortlisted_sentence in _shortlist_duplicate_sentences(
        sentence_key,
        ctx.accepted_sentences_by_focus.get(focus_key, []),
    ):
        normalized_seen = normalize_duplicate_sentence(shortlisted_sentence)
        ratio = SequenceMatcher(None, sentence_key, normalized_seen).ratio()
        if ratio >= NEAR_DUPLICATE_SENTENCE_THRESHOLD:
            return "duplicate_sentence_near", DuplicateDecisionEvidence(
                kind="near",
                focus=card.focus,
                candidate_sentence=card.sentence,
                matched_sentence=shortlisted_sentence,
                normalized_sentence=sentence_key,
                bucket_key=_duplicate_bucket_key(focus_key, normalized_seen),
                similarity=round(ratio, 4),
            )

    return None, None


def _shortlist_duplicate_sentences(
    candidate_sentence: str,
    sentences: list[str],
    *,
    limit: int = DUPLICATE_SHORTLIST_LIMIT,
) -> list[str]:
    candidate_tokens = _duplicate_tokens(candidate_sentence)
    ranked: list[tuple[float, str]] = []
    for sentence in sentences:
        normalized_sentence = normalize_duplicate_sentence(sentence)
        if not normalized_sentence or normalized_sentence == candidate_sentence:
            continue
        overlap = _token_overlap(candidate_tokens, _duplicate_tokens(normalized_sentence))
        if overlap <= 0.0:
            continue
        ranked.append((overlap, sentence))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [sentence for _score, sentence in ranked[:limit]]


def _token_overlap(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / max(len(left), len(right))


def _duplicate_tokens(value: str) -> set[str]:
    return {token for token in value.split() if token}


def _duplicate_bucket_key(focus: str, sentence: str) -> str:
    return f"{focus}::{sentence}"


def _normalize_duplicate_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value or "")
    text = text.lower()
    text = _DUPLICATE_PUNCTUATION_RE.sub(" ", text)
    return re.sub(r"\s+", " ", text).strip()
