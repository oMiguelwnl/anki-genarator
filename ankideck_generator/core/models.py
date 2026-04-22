from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

ANKI_FIELD_ORDER_DEFAULT = [
    "SortIndex",
    "word",
    "Front of Card",
    "IPA",
    "Definitions",
    "Exemple Sentence",
    "Translation",
    "word_audio",
    "sentence_audio",
    "image",
]

ANKI_FIELD_ORDER_RU = [
    "SortIndex",
    "Spellings",
    "IPA",
    "Example Word",
    "Word Translation",
    "Exemple Sentence",
    "Translation",
    "letter_audio",
    "word_audio",
    "sentence_audio",
    "image",
]

# Backward-compatible alias used by existing tests/importers.
ANKI_FIELD_ORDER = ANKI_FIELD_ORDER_DEFAULT

STRUCTURED_SENTENCE_PROMPT_VERSION = "sentence-batch-v1"
STRUCTURED_SENTENCE_SCHEMA_VERSION = "sentence-batch-schema-v1"
LEXICAL_REVIEW_PROMPT_VERSION = "lexical-review-v1"
LEXICAL_REVIEW_SCHEMA_VERSION = "lexical-review-schema-v1"

CardLifecycleState = Literal["generated", "reviewed", "accepted", "rejected"]
LexicalReviewVerdict = Literal["accept", "correct", "reject"]


class CardData(BaseModel):
    focus: str = ""
    index: int = 0
    ipa: str = ""
    source_definition: str = ""
    definition: str = ""
    sentence: str = ""
    translation: str = ""
    translation_language: str = ""
    image: str = ""
    audio: str = ""
    word_audio: str = ""
    sentence_audio: str = ""
    spellings: str = ""
    example_word: str = ""
    word_translation: str = ""
    letter_audio: str = ""
    level: int = 1
    language: str = ""
    lifecycle_state: CardLifecycleState = "accepted"

    def _field_values(self) -> dict[str, str]:
        return {
            "SortIndex": str(self.index),
            "word": self.focus,
            "Front of Card": self.focus,
            "IPA": self.ipa,
            "Definitions": self.definition,
            "Exemple Sentence": self.sentence,
            "Translation": self.translation,
            "word_audio": self.word_audio,
            "sentence_audio": self.sentence_audio,
            "image": self.image,
            "Spellings": self.spellings,
            "Example Word": self.example_word,
            "Word Translation": self.word_translation,
            "letter_audio": self.letter_audio,
        }

    def genanki_fields(self, field_order: list[str] | None = None) -> list[str]:
        values = self._field_values()
        order = field_order or ANKI_FIELD_ORDER_DEFAULT
        return [values.get(name, "") for name in order]


class ProviderResult(BaseModel):
    value: str | None
    provider_name: str
    elapsed_ms: int
    error: str | None = None
    fallback_errors: dict[str, str] | None = None


class StructuredSentenceCandidate(BaseModel):
    sentence: str
    target_form: str
    requested_pos: str
    requested_sense: str
    validation_signals: list[str] = Field(default_factory=list)
    rationale: str


class StructuredSentenceBatch(BaseModel):
    prompt_version: str = STRUCTURED_SENTENCE_PROMPT_VERSION
    schema_version: str = STRUCTURED_SENTENCE_SCHEMA_VERSION
    focus_word: str
    language: str
    requested_pos: str
    requested_sense: str
    target_level: int
    candidates: list[StructuredSentenceCandidate] = Field(min_length=3, max_length=3)


class LexicalReviewRequest(BaseModel):
    prompt_version: str = LEXICAL_REVIEW_PROMPT_VERSION
    schema_version: str = LEXICAL_REVIEW_SCHEMA_VERSION
    focus_word: str
    language: str
    target_translation_language: str
    accepted_sentence: str
    current_definition: str = ""
    current_translation: str = ""
    source_definition: str = ""
    candidate_senses: list[str] = Field(default_factory=list)
    winning_sense: str | None = None
    losing_sense_candidates: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    selection_reasons: dict[str, str] = Field(default_factory=dict)


class LexicalReviewCorrection(BaseModel):
    corrected_definition: str | None = None
    corrected_translation: str | None = None
    winning_sense: str | None = None
    losing_sense_candidates: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    selection_reasons: dict[str, str] = Field(default_factory=dict)


class LexicalReviewResult(BaseModel):
    prompt_version: str = LEXICAL_REVIEW_PROMPT_VERSION
    schema_version: str = LEXICAL_REVIEW_SCHEMA_VERSION
    verdict: LexicalReviewVerdict
    focus_word: str
    language: str
    target_translation_language: str
    accepted_sentence: str
    current_definition: str = ""
    current_translation: str = ""
    source_definition: str = ""
    candidate_senses: list[str] = Field(default_factory=list)
    winning_sense: str | None = None
    losing_sense_candidates: list[str] = Field(default_factory=list)
    corrected_definition: str | None = None
    corrected_translation: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    selection_reasons: dict[str, str] = Field(default_factory=dict)


class RunConfig(BaseModel):
    language: str
    mode: str
    interactive: bool
    output_path: str
    resume: bool = True
    level_size: int
    target_translation: str
    wordfreq_language: str = ""
    timeout_sec: int
    retries: int
    seed: int
    cache_path: str
    autosave_every: int
    refresh_text_cache: bool = False
    ai_max_calls_per_word: int = 6
    ai_max_calls_per_field: int = 2
    level_pool_multiplier: int = 8
    concurrency: int = 1
    audio_concurrency: int = 1
    strict_quality: bool = True
    max_attempts_per_level: int = 0
    exclude_closed_class_words: bool = True
    cache_validation_version: int = 4
    enforce_translation_language: bool = True
    generate_audio: bool = True
    sentence_rewrite_from_web: bool = True
    level_validation_mode: str = "profile_hard_zipf_soft"
    provider_timeout_overrides: dict[str, int] = Field(default_factory=dict)
    provider_retry_overrides: dict[str, int] = Field(default_factory=dict)
    lexicon_zipf_fallback_min: float = 0.0
    sentence_ai_attempts: int = 2
    definition_context_fallback: bool = True
    low_yield_min_attempts: int = 0
    low_yield_min_acceptance_rate: float = 0.0
    low_yield_max_accepted: int = 0
    low_yield_start_level: int = 1
    definition_word_fallback: bool = False
    definition_context_first: bool = True
    definition_candidates_limit: int = 5
    review_queue_path: str = "output/review_queue.json"
    quality_report_path: str = "output/quality_report.json"


class CompatibilityFingerprint(BaseModel):
    model: str
    prompt: str
    schema_digest: str
    validator: str
    digest: str


class ProgressState(BaseModel):
    language: str
    mode: str
    schema_version: int = 1
    compatibility_fingerprint: CompatibilityFingerprint | None = None
    level: int = 1
    index: int = 0
    rng_state: Any | None = None
    processed_focus: list[str] = Field(default_factory=list)
    processed_sentences: list[str] = Field(default_factory=list)
    created_cards: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class DuplicateDecisionEvidence(BaseModel):
    kind: Literal["exact", "near"]
    focus: str
    candidate_sentence: str
    matched_sentence: str
    normalized_sentence: str
    bucket_key: str
    similarity: float


class LogRecord(BaseModel):
    focus: str
    level: int
    lifecycle_state: CardLifecycleState | None = None
    providers: dict[str, str] = Field(default_factory=dict)
    provider_errors: dict[str, str] = Field(default_factory=dict)
    stage_timings: dict[str, int] = Field(default_factory=dict)
    event_counts: dict[str, int] = Field(default_factory=dict)
    validations: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    provider: str | None = None
    model: str | None = None
    candidate_preview: dict[str, list[str]] = Field(default_factory=dict)
    quality_scores: dict[str, float] = Field(default_factory=dict)
    selection_reasons: dict[str, str] = Field(default_factory=dict)
    duplicate_evidence: DuplicateDecisionEvidence | None = None
    status: str
    discard_reason: str | None = None
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
