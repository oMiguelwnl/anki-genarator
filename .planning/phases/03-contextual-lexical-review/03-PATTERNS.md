# Phase 3: Contextual Lexical Review - Patterns

**Mapped:** 2026-04-20
**Status:** Complete

## Target Files And Closest Analogs

| Planned file | Role | Closest analog | Reuse pattern |
|---|---|---|---|
| `ankideck_generator/core/models.py` | typed review contracts | existing `StructuredSentenceBatch`, `LogRecord`, `CardData` | add new Pydantic models beside current pipeline contracts |
| `ankideck_generator/core/providers.py` | AI transport | `sentence_ai_candidates()`, `definition_from_context()` | keep HTTP/parsing logic in `ProviderManager` |
| `ankideck_generator/core/lexical_review.py` | new domain service | `ankideck_generator/core/sentence_generation.py` | narrow helper/service extracted from `DeckBuilder` |
| `ankideck_generator/core/deck_builder.py` | orchestration integration | `_process_word_textual()`, `_process_word()`, `_interactive_edit()` | wire service + audit + validation, avoid raw transport logic |
| `ankideck_generator/tests/test_lexical_review.py` | service tests | `ankideck_generator/tests/test_sentence_generation.py` | local fake providers, per-file helpers |
| `ankideck_generator/tests/test_deck_builder.py` | routing/regression tests | existing sentence-routing and review-queue tests | fake providers + concrete log/card assertions |

## Code Excerpts To Follow

### 1. Typed contracts live in `core/models.py`

```python
class StructuredSentenceCandidate(BaseModel):
    sentence: str
    target_form: str
    requested_pos: str
    requested_sense: str
    validation_signals: list[str] = Field(default_factory=list)
    rationale: str

class LogRecord(BaseModel):
    review_notes: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    candidate_preview: dict[str, list[str]] = Field(default_factory=dict)
    selection_reasons: dict[str, str] = Field(default_factory=dict)
```

Pattern: extend existing Pydantic contracts; do not create parallel untyped dict schemas.

### 2. Provider transport stays in `ProviderManager`

```python
def definition_from_context(
    self,
    word: str,
    sentence: str,
    language: str,
    definition_language: str | None = None,
) -> ProviderResult:
    return self._wrap(
        "ai",
        lambda: self._definition_from_context_ai(...),
    )
```

```python
def sentence_ai_candidates(...) -> StructuredSentenceBatchResult:
    return self._wrap_structured_sentence_batch(
        "ai",
        lambda: self._sentence_ai_candidates(...),
    )
```

Pattern: provider methods wrap transport + parsing only; orchestration policy lives elsewhere.

### 3. `DeckBuilder` uses nested helpers and audit accumulation

```python
providers_used: dict[str, str] = {}
provider_errors: dict[str, str] = {}
review_notes: list[str] = []
candidate_preview: dict[str, list[str]] = {}
selection_reasons: dict[str, str] = {}

def remember_review_note(name: str | None) -> None:
    if name and name not in review_notes:
        review_notes.append(name)
```

Pattern: accumulate audit fields locally, then emit them through `LogRecord` once.

### 4. Deterministic validation already has a single entry point

```python
def _validate_text_candidate(
    self,
    card: CardData,
    ctx: ValidationContext,
    run: RunConfig,
    reserved_focus: set[str] | None = None,
    reserved_sentences: set[str] | None = None,
) -> list[str]:
    ...
    return validate_card(card, temp_ctx, validations, commit=False)
```

Pattern: reuse this seam after AI/manual edits instead of adding separate lexical-only acceptance rules.

### 5. Tests use inline fakes and direct assertions

```python
class FakeProviders:
    def translation_web(self, text, src, dest):
        ...

card, log = builder._process_word(...)

assert card is not None
assert log.event_counts["sentence_ai_malformed_batch"] == 1
```

Pattern: per-file fake providers, no shared fixture package, assert on concrete fields/event counters.

## Phase-Specific Notes

- Prefer `LogRecord.before` / `after` / `reason_codes` over inventing another audit structure.
- Preserve `review_queue.json` as rejected-only output; uncertain lexical cases should be represented there.
- Keep `DeckBuilder` changes narrow: add one lexical-review seam and one post-correction revalidation seam.
