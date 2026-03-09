from __future__ import annotations

from datetime import datetime
from typing import Any

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


class CardData(BaseModel):
    focus: str = ""
    index: int = 0
    ipa: str = ""
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
    ai_max_calls_per_word: int = 6
    ai_max_calls_per_field: int = 2
    level_pool_multiplier: int = 8
    strict_quality: bool = True


class ProgressState(BaseModel):
    language: str
    mode: str
    level: int = 1
    index: int = 0
    rng_state: Any | None = None
    processed_focus: list[str] = Field(default_factory=list)
    processed_sentences: list[str] = Field(default_factory=list)
    created_cards: int = 0
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class LogRecord(BaseModel):
    focus: str
    level: int
    providers: dict[str, str] = Field(default_factory=dict)
    provider_errors: dict[str, str] = Field(default_factory=dict)
    validations: list[str] = Field(default_factory=list)
    status: str
    discard_reason: str | None = None
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
