from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
    level: int = 1
    language: str = ""

    def genanki_fields(self) -> list[str]:
        return [
            self.focus,
            str(self.index),
            self.ipa,
            self.definition,
            self.sentence,
            self.translation,
            self.image,
            self.audio,
        ]


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
    error: str | None = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
