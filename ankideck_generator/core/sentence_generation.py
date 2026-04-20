from __future__ import annotations

from dataclasses import dataclass, field
import re

from ..utils.language_tools import text_contains_focus, text_matches_language
from .models import (
    STRUCTURED_SENTENCE_PROMPT_VERSION,
    STRUCTURED_SENTENCE_SCHEMA_VERSION,
    StructuredSentenceCandidate,
)
from .providers import ProviderManager, StructuredSentenceBatchResult
from .validators import ARTIFICIAL_SENTENCE_PATTERNS

SENTENCE_GENERATION_POLICY_VERSION = "sentence-generation-policy-v1"


@dataclass
class SentenceGenerationCandidate:
    sentence: str
    target_form: str
    requested_pos: str
    requested_sense: str
    validation_signals: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class SentenceGenerationRejection:
    sentence: str
    reason_codes: list[str] = field(default_factory=list)
    validation_signals: list[str] = field(default_factory=list)
    rationale: str = ""


@dataclass
class SentenceGenerationResult:
    candidates: list[SentenceGenerationCandidate] = field(default_factory=list)
    rejected: list[SentenceGenerationRejection] = field(default_factory=list)
    provider_name: str = "ai"
    status: str = "ok"
    error: str | None = None
    failure_reasons: list[str] = field(default_factory=list)
    prompt_version: str = STRUCTURED_SENTENCE_PROMPT_VERSION
    schema_version: str = STRUCTURED_SENTENCE_SCHEMA_VERSION
    validation_policy_version: str = SENTENCE_GENERATION_POLICY_VERSION


class SentenceGenerationService:
    def __init__(
        self,
        providers: ProviderManager,
        *,
        strict_quality: bool = True,
    ) -> None:
        self.providers = providers
        self.strict_quality = strict_quality

    def generate_candidates(
        self,
        *,
        focus_word: str,
        language: str,
        level: int,
        requested_pos: str = "",
        requested_sense: str = "",
        min_words: int = 5,
        max_words: int = 25,
    ) -> SentenceGenerationResult:
        structured_loader = getattr(self.providers, "sentence_ai_candidates", None)
        if not callable(structured_loader):
            return self._generate_candidates_from_legacy_ai(
                focus_word=focus_word,
                language=language,
                requested_pos=requested_pos,
                requested_sense=requested_sense,
                min_words=min_words,
                max_words=max_words,
            )

        batch_result = structured_loader(
            focus_word,
            language,
            requested_pos=requested_pos,
            requested_sense=requested_sense,
            target_level=level,
            min_words=min_words,
            max_words=max_words,
            system_prompt=self._system_prompt(),
            user_prompt=self._user_prompt(
                focus_word=focus_word,
                language=language,
                level=level,
                requested_pos=requested_pos,
                requested_sense=requested_sense,
                min_words=min_words,
                max_words=max_words,
            ),
        )
        if batch_result.batch is None:
            return self._result_from_batch_error(batch_result)

        accepted: list[SentenceGenerationCandidate] = []
        rejected: list[SentenceGenerationRejection] = []
        for candidate in batch_result.batch.candidates:
            reason_codes = self._candidate_rejection_reasons(
                candidate,
                focus_word=focus_word,
                language=language,
            )
            if reason_codes:
                rejected.append(
                    SentenceGenerationRejection(
                        sentence=(candidate.sentence or "").strip(),
                        reason_codes=reason_codes,
                        validation_signals=list(candidate.validation_signals or []),
                        rationale=candidate.rationale,
                    )
                )
                continue
            accepted.append(
                SentenceGenerationCandidate(
                    sentence=candidate.sentence.strip(),
                    target_form=candidate.target_form.strip(),
                    requested_pos=candidate.requested_pos,
                    requested_sense=candidate.requested_sense,
                    validation_signals=list(candidate.validation_signals or []),
                    rationale=candidate.rationale,
                )
            )

        if accepted:
            return SentenceGenerationResult(
                candidates=accepted,
                rejected=rejected,
                provider_name=batch_result.provider_name,
                status="ok",
            )

        failure_reasons = sorted(
            {
                reason
                for item in rejected
                for reason in item.reason_codes
            }
        ) or ["ai_low_yield"]
        return SentenceGenerationResult(
            candidates=[],
            rejected=rejected,
            provider_name=batch_result.provider_name,
            status="low_yield",
            failure_reasons=failure_reasons,
        )

    def _system_prompt(self) -> str:
        return (
            "You generate flashcard sentence candidates as strict JSON. "
            "Return only valid JSON with exactly three candidates and no markdown, code fences, or commentary."
        )

    def _user_prompt(
        self,
        *,
        focus_word: str,
        language: str,
        level: int,
        requested_pos: str,
        requested_sense: str,
        min_words: int,
        max_words: int,
    ) -> str:
        return (
            f"Generate exactly 3 candidate sentences in language '{language}' for the focus word '{focus_word}'. "
            f"Target level: {level}. Requested POS: '{requested_pos}'. Requested sense: '{requested_sense}'. "
            f"Each sentence must use {min_words} to {max_words} words, contain the exact focus word '{focus_word}', and sound natural in everyday speech. "
            "Avoid proper nouns, labels, teaching phrases, grammar explanations, and meta-example wording. "
            "Return one JSON object with keys: prompt_version, schema_version, focus_word, language, requested_pos, requested_sense, target_level, candidates. "
            "Each candidate object must include: sentence, target_form, requested_pos, requested_sense, validation_signals, rationale."
        )

    def _result_from_batch_error(
        self,
        batch_result: StructuredSentenceBatchResult,
    ) -> SentenceGenerationResult:
        error_text = str(batch_result.error or "")
        if "structured_sentence_" in error_text:
            return SentenceGenerationResult(
                provider_name=batch_result.provider_name,
                status="malformed",
                error=error_text,
                failure_reasons=["ai_malformed_batch"],
            )
        return SentenceGenerationResult(
            provider_name=batch_result.provider_name,
            status="provider_error",
            error=error_text,
            failure_reasons=["ai_provider_error"],
        )

    def _generate_candidates_from_legacy_ai(
        self,
        *,
        focus_word: str,
        language: str,
        requested_pos: str,
        requested_sense: str,
        min_words: int,
        max_words: int,
    ) -> SentenceGenerationResult:
        legacy_loader = getattr(self.providers, "sentence_ai", None)
        if not callable(legacy_loader):
            return SentenceGenerationResult(
                provider_name="ai",
                status="provider_error",
                error="structured_sentence_provider_missing",
                failure_reasons=["ai_provider_error"],
            )
        result = legacy_loader(
            focus_word,
            language,
            min_words=min_words,
            max_words=max_words,
        )
        sentence = str(getattr(result, "value", "") or "").strip()
        if not sentence:
            return SentenceGenerationResult(
                provider_name=str(getattr(result, "provider_name", "ai") or "ai"),
                status="low_yield",
                error=getattr(result, "error", None),
                failure_reasons=["ai_low_yield"],
            )
        return SentenceGenerationResult(
            candidates=[
                SentenceGenerationCandidate(
                    sentence=sentence,
                    target_form=focus_word,
                    requested_pos=requested_pos,
                    requested_sense=requested_sense,
                    validation_signals=[],
                    rationale="legacy_sentence_ai",
                )
            ],
            provider_name=str(getattr(result, "provider_name", "ai") or "ai"),
            status="ok",
        )

    def _candidate_rejection_reasons(
        self,
        candidate: StructuredSentenceCandidate,
        *,
        focus_word: str,
        language: str,
    ) -> list[str]:
        sentence = (candidate.sentence or "").strip()
        target_form = (candidate.target_form or "").strip()
        reasons: list[str] = []
        if not sentence:
            reasons.append("ai_sentence_blank")
            return reasons
        if target_form.casefold() != focus_word.strip().casefold():
            reasons.append("ai_target_form_mismatch")
        if not text_contains_focus(sentence, focus_word):
            reasons.append("ai_focus_missing")
        if self.strict_quality and not text_matches_language(
            sentence,
            language,
            min_score=0.55,
            min_tokens=3,
        ):
            reasons.append("ai_wrong_language")
        if self._looks_meta_example(sentence):
            reasons.append("ai_meta_example")
        if self._is_proper_noun_heavy(sentence):
            reasons.append("ai_proper_noun_heavy")
        return reasons

    def _looks_meta_example(self, sentence: str) -> bool:
        return any(pattern.search(sentence) for pattern in ARTIFICIAL_SENTENCE_PATTERNS)

    def _is_proper_noun_heavy(self, sentence: str) -> bool:
        tokens = re.findall(r"\b[^\W\d_]+\b", sentence, flags=re.UNICODE)
        if not tokens:
            return False
        proper_like = 0
        for index, token in enumerate(tokens):
            if not token:
                continue
            if index == 0:
                continue
            if token[0].isupper() and any(char.islower() for char in token[1:]):
                proper_like += 1
        return proper_like >= 2
