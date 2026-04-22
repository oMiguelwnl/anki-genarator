# Phase 05: evaluation-and-runtime-controls - Pattern Map

**Mapped:** 2026-04-22
**Files analyzed:** 9
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `ankideck_generator/core/evaluation.py` | service | batch, transform, file-I/O | `ankideck_generator/core/run_state.py` | partial |
| `ankideck_generator/core/models.py` | model | transform | `ankideck_generator/core/models.py` | exact |
| `ankideck_generator/core/deck_builder.py` | service | batch, transform | `ankideck_generator/core/deck_builder.py` | exact |
| `ankideck_generator/core/lexical_review.py` | service | request-response, transform | `ankideck_generator/core/lexical_review.py` | exact |
| `ankideck_generator/core/providers.py` | service | request-response | `ankideck_generator/core/providers.py` | exact |
| `ankideck_generator/main.py` | config | request-response | `ankideck_generator/main.py` | exact |
| `ankideck_generator/tests/test_evaluation.py` | test | batch, file-I/O | `ankideck_generator/tests/test_deck_builder.py` | role-match |
| `ankideck_generator/tests/test_deck_builder.py` | test | batch | `ankideck_generator/tests/test_deck_builder.py` | exact |
| `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` | test | file-I/O, transform | `ankideck_generator/tests/fixtures/ai_sentence_candidates/valid_batch.json` | partial |

## Pattern Assignments

### `ankideck_generator/core/evaluation.py` (service, batch/transform/file-I/O)

**Analog:** `ankideck_generator/core/run_state.py`

**Imports + deterministic hashing pattern** from `ankideck_generator/core/run_state.py` lines 1-9, 12-37:
```python
from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from .models import CompatibilityFingerprint

def _canonicalize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (list, tuple, set)):
        items = [_canonicalize(item) for item in value]
        return sorted(items, key=_stable_json)
    return value

def _stable_json(value: Any) -> str:
    return json.dumps(_canonicalize(value), ensure_ascii=True, separators=(",", ":"), sort_keys=True, default=str)

def _digest(value: Any) -> str:
    return hashlib.sha1(_stable_json(value).encode("utf-8")).hexdigest()
```

**Report aggregation pattern** from `ankideck_generator/core/deck_builder.py` lines 3529-3566:
```python
average_definition_score = 0.0
if stats.definition_score_samples:
    average_definition_score = stats.definition_score_total / stats.definition_score_samples
total_attempted = sum(stats.attempted_by_level.values())
accepted_cards = len(stats.cards)
clean_accepts = max(accepted_cards - stats.corrected_accepted_count, 0)
accepted_card_rate = round(accepted_cards / total_attempted, 4) if total_attempted else 0.0
duplicate_reject_rate = round(duplicate_total / total_attempted, 4) if total_attempted else 0.0
```

**Artifact write pattern** from `ankideck_generator/core/deck_builder.py` lines 3659-3662 and `ankideck_generator/utils/file_utils.py` lines 23-29:
```python
ensure_dir(Path(run.quality_report_path).parent)
atomic_write_json(run.quality_report_path, report)

def atomic_write_json(path: str | Path, data: Any) -> None:
    path_obj = Path(path)
    ensure_dir(path_obj.parent)
    tmp_path = path_obj.with_suffix(path_obj.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp_path, path_obj)
```

**Copy for Phase 05:** deterministic fingerprint helpers from `run_state.py`; metric math and JSON report writing from `_write_quality_outputs()`.

---

### `ankideck_generator/core/models.py` (model, transform)

**Analog:** `ankideck_generator/core/models.py`

**Pydantic model style** from lines 6, 100-117, 175-217, 219-273:
```python
from pydantic import BaseModel, Field

class StructuredSentenceBatch(BaseModel):
    prompt_version: str = STRUCTURED_SENTENCE_PROMPT_VERSION
    schema_version: str = STRUCTURED_SENTENCE_SCHEMA_VERSION
    focus_word: str
    language: str
    requested_pos: str
    requested_sense: str
    target_level: int
    candidates: list[StructuredSentenceCandidate] = Field(min_length=3, max_length=3)

class RunConfig(BaseModel):
    language: str
    mode: str
    interactive: bool
    output_path: str
    ...
    review_queue_path: str = "output/review_queue.json"
    quality_report_path: str = "output/quality_report.json"

class LogRecord(BaseModel):
    focus: str
    level: int
    lifecycle_state: CardLifecycleState | None = None
    providers: dict[str, str] = Field(default_factory=dict)
    provider_errors: dict[str, str] = Field(default_factory=dict)
    stage_timings: dict[str, int] = Field(default_factory=dict)
    event_counts: dict[str, int] = Field(default_factory=dict)
    ...
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
```

**Copy for Phase 05:** add new benchmark/result/budget report models in this same `BaseModel` + `Field(default_factory=...)` style; keep versioned schema fields where artifacts are persisted.

---

### `ankideck_generator/core/deck_builder.py` (service, batch/transform)

**Analog:** `ankideck_generator/core/deck_builder.py`

**Imports + typed dependency pattern** from lines 17-73:
```python
from ..utils.file_utils import atomic_write_json, ensure_dir, read_json
from ..utils.logger import JsonLogger
from .models import (
    CardData,
    CompatibilityFingerprint,
    LexicalReviewRequest,
    LogRecord,
    ProgressState,
    ProviderResult,
    RunConfig,
)
from .lexical_review import LexicalReviewService
from .providers import ProviderManager
from .run_state import build_compatibility_fingerprint, fingerprints_match, quarantine_name
```

**Run setup pattern** from lines 449-457, 471-480:
```python
cache_manager = CacheManager(run.cache_path, run.language, run.autosave_every)
progress_store = ProgressStore("ankideck_generator/data/progress")
log_path = f"ankideck_generator/data/logs/run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jsonl"
self._last_run_log_path = log_path
logger = JsonLogger(log_path)
ctx = ValidationContext()
compatibility_fingerprint = self._build_compatibility_fingerprint(run)
random.seed(run.seed)

state = None
if run.resume:
    state = self._load_resume_state(progress_store, run, compatibility_fingerprint)
processed_focus = set(state.processed_focus) if state else set()
processed_sentences = set(state.processed_sentences) if state else set()
stats = BuildStats(...)
```

**Budget + timing seam** from lines 1669-1733:
```python
def allow_ai(field: str) -> bool:
    if ai_calls_total >= run.ai_max_calls_per_word:
        return False
    if ai_calls_by_field.get(field, 0) >= run.ai_max_calls_per_field:
        return False
    return True

def mark_ai(field: str) -> None:
    nonlocal ai_calls_total
    ai_calls_total += 1
    ai_calls_by_field[field] = ai_calls_by_field.get(field, 0) + 1

def trace_result(field: str, result: ProviderResult, *, ai_field: str | None = None, stage_key: str | None = None) -> None:
    providers_used[field] = result.provider_name
    if result.error:
        provider_errors[field] = result.error
    ...
    if ai_field and result.provider_name == "ai":
        mark_ai(ai_field)
    if stage_key:
        stage_timings[stage_key] = stage_timings.get(stage_key, 0) + int(getattr(result, "elapsed_ms", 0) or 0)
```

**Metrics/log accumulation pattern** from lines 1009-1052:
```python
def _record_log(self, logger: JsonLogger, stats: BuildStats, log_record: LogRecord) -> None:
    logger.log(log_record.model_dump())
    ...
    for event_name, count in (log_record.event_counts or {}).items():
        stats.event_counter[event_name] += int(count or 0)
        stats.event_counter_by_level[level][event_name] += int(count or 0)
    ...
    for stage_name, elapsed_ms in (log_record.stage_timings or {}).items():
        stats.stage_counter[stage_name] += int(elapsed_ms or 0)
        stats.stage_samples[stage_name] += 1
```

**Quality artifact pattern** from lines 3582-3662:
```python
report = {
    "generated_at": datetime.utcnow().isoformat(),
    "language": run.language,
    "mode": run.mode,
    "cards": len(stats.cards),
    "accepted_card_rate": accepted_card_rate,
    "duplicate_reject_rate": duplicate_reject_rate,
    "provider_counter": dict(stats.provider_counter),
    "provider_success_counter": dict(stats.provider_success_counter),
    "provider_error_counter": dict(stats.provider_error_counter),
    "event_counter": dict(stats.event_counter),
}
ensure_dir(Path(run.quality_report_path).parent)
atomic_write_json(run.quality_report_path, report)
```

**Copy for Phase 05:** extend existing `allow_ai`, `stage_timings`, `event_counts`, and `quality_report` instead of adding a second metrics/budget pipeline.

---

### `ankideck_generator/core/lexical_review.py` (service, request-response/transform)

**Analog:** `ankideck_generator/core/lexical_review.py`

**Request -> provider -> normalized result pattern** from lines 10-20, 43-57, 76-120:
```python
def review(self, request: LexicalReviewRequest) -> LexicalReviewResult:
    candidate_senses = [sense for sense in request.candidate_senses if str(sense).strip()]
    transport = getattr(self.providers, "lexical_review", None)
    provider_result = transport(request) if callable(transport) else None
    base = provider_result.review if provider_result and provider_result.review else None
    ...
    winning_sense, reason = self._resolve_winning_sense(request, base, candidate_senses)
    ...
    return LexicalReviewResult(
        verdict=verdict,
        focus_word=request.focus_word,
        ...
        selection_reasons=selection_reasons,
    )
```

**Fallback/error classification pattern** from lines 51-74:
```python
if winning_sense is None:
    ...
    return LexicalReviewResult(
        verdict="reject",
        ...
        reason_codes=reason_codes,
        confidence=(base.confidence if base else request.confidence),
        before=dict(request.before),
        after=dict(request.after),
    )
```

**Copy for Phase 05:** if lexical review gets budget/timing/report seams, keep this “normalize provider output into a typed result” structure.

---

### `ankideck_generator/core/providers.py` (service, request-response)

**Analog:** `ankideck_generator/core/providers.py`

**Dataclass result contract pattern** from lines 99-140:
```python
@dataclass
class SentenceCandidatesResult:
    candidates: list[SentenceCandidate]
    provider_name: str
    elapsed_ms: int
    error: str | None = None
    fallback_errors: dict[str, str] | None = None

@dataclass
class LexicalReviewTransportResult:
    review: LexicalReviewResult | None
    provider_name: str
    elapsed_ms: int
    error: str | None = None
    fallback_errors: dict[str, str] | None = None
```

**Retry/error wrapper pattern** from lines 212-241:
```python
def _wrap(self, provider_name: str, fn: Callable[[], str | None]) -> ProviderResult:
    if provider_name in self._disabled_providers:
        return ProviderResult(value=None, provider_name=provider_name, elapsed_ms=0, error="provider_disabled")
    start = time.time()
    ...
    try:
        value = fn()
        if value is None or value == "":
            raise ProviderError("empty result")
        self._register_provider_success(provider_name)
        elapsed = int((time.time() - start) * 1000)
        return ProviderResult(value=value, provider_name=provider_name, elapsed_ms=elapsed)
    except Exception as exc:
        ...
        return ProviderResult(value=None, provider_name=provider_name, elapsed_ms=elapsed, error=str(last_exc))
```

**Lexical review transport pattern** from lines 681-711:
```python
def lexical_review(self, request: LexicalReviewRequest, *, system_prompt: str | None = None, user_prompt: str | None = None) -> LexicalReviewTransportResult:
    start = time.time()
    try:
        review = self._lexical_review_ai(request, system_prompt=system_prompt, user_prompt=user_prompt)
        self._register_provider_success("ai")
        elapsed = int((time.time() - start) * 1000)
        return LexicalReviewTransportResult(review=review, provider_name="ai", elapsed_ms=elapsed)
    except Exception as exc:
        ...
        return LexicalReviewTransportResult(review=None, provider_name="ai", elapsed_ms=elapsed, error=message)
```

**Copy for Phase 05:** keep provider-layer timing/error collection in return objects; do not bury budget/report fields in side effects.

---

### `ankideck_generator/main.py` (config, request-response)

**Analog:** `ankideck_generator/main.py`

**CLI arg pattern** from lines 19-39:
```python
def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Anki Deck Generator")
    parser.add_argument("--language", default="en", ...)
    parser.add_argument("--mode", default="test", choices=["test", "full", "build"], ...)
    parser.add_argument("--interactive", action="store_true", ...)
    parser.add_argument("--output", default="output/deck.apkg", ...)
    parser.add_argument("--seed", type=int, default=None, ...)
    parser.add_argument("--refresh-text-cache", action="store_true", ...)
    parser.add_argument("--resume", action="store_true", default=False, ...)
    parser.add_argument("--no-resume", action="store_false", dest="resume", ...)
    parser.add_argument("--config", default="config.yaml", ...)
    return parser
```

**Runtime config -> `RunConfig` mapping pattern** from lines 64-127, 199-249:
```python
runtime_cfg = config.get("runtime", {})
profiles = runtime_cfg.get("profiles", {})
mode_profile = profiles.get(mode, {})
...
review_queue_path = str(runtime_cfg.get("review_queue_path", "output/review_queue.json") or "output/review_queue.json")
quality_report_path = str(runtime_cfg.get("quality_report_path", "output/quality_report.json") or "output/quality_report.json")

run = RunConfig(
    language=lang_cfg.get("code", args.language),
    mode=mode,
    interactive=args.interactive,
    output_path=args.output,
    ...
    review_queue_path=review_queue_path,
    quality_report_path=quality_report_path,
)
```

**Execution/preflight pattern** from lines 251-268:
```python
builder = DeckBuilder(args.config)
if args.resume:
    print(Fore.YELLOW + "Warning: resume mode is not recommended ...")
if run.strict_quality:
    ok, preflight_msg = builder.preflight(run)
    if not ok:
        print(Fore.RED + preflight_msg)
        return 1
cards, media_files = builder.build(run)
builder.export_deck(run, cards, media_files)
```

**Copy for Phase 05:** if new evaluation/budget flags are added, thread them through parser -> `runtime_cfg` -> `RunConfig` in this exact style.

---

### `ankideck_generator/tests/test_evaluation.py` (test, batch/file-I/O)

**Analog:** `ankideck_generator/tests/test_deck_builder.py`

**Fixture loading pattern** from `ankideck_generator/tests/test_deck_builder.py` lines 48-55:
```python
def _ai_sentence_fixture_payload(name: str) -> dict[str, object]:
    path = Path(__file__).resolve().parent / "fixtures" / "ai_sentence_candidates" / name
    return json.loads(path.read_text(encoding="utf-8"))
```

**Tmp-path artifact assertion pattern** from lines 3308-3376:
```python
run.review_queue_path = str(tmp_path / "output" / "review_queue.json")
run.quality_report_path = str(tmp_path / "output" / "quality_report.json")
...
builder._write_quality_outputs(run, stats)

report = json.loads(Path(run.quality_report_path).read_text(encoding="utf-8"))
review_queue = json.loads(Path(run.review_queue_path).read_text(encoding="utf-8"))

assert report["needs_review"] == 1
assert [item["focus"] for item in review_queue] == ["mal"]
```

**Typed/fingerprint assertion pattern** from `ankideck_generator/tests/test_run_state.py` lines 56-87:
```python
fingerprint_one = build_compatibility_fingerprint(...)
fingerprint_two = build_compatibility_fingerprint(...)
assert fingerprints_match(fingerprint_one, fingerprint_two)

baseline = build_compatibility_fingerprint(...)
changed = build_compatibility_fingerprint(...)
assert not fingerprints_match(baseline, changed)
```

**Copy for Phase 05:** use helper fixture loaders, `tmp_path` output directories, and direct JSON assertions against evaluation artifacts.

---

### `ankideck_generator/tests/test_deck_builder.py` (test, batch)

**Analog:** `ankideck_generator/tests/test_deck_builder.py`

**Local `RunConfig` factory pattern** from lines 30-45:
```python
def _run_config(tmp_path: Path, language: str = "es") -> RunConfig:
    return RunConfig(
        language=language,
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        ...
        autosave_every=1,
    )
```

**Regression-test style for report fields** from lines 3378-3455:
```python
builder._record_log(logger, stats, LogRecord(...))
builder._write_quality_outputs(run, stats)

review_queue = json.loads(Path(run.review_queue_path).read_text(encoding="utf-8"))
item = review_queue[0]

assert item["card_snapshot"] == {...}
assert item["hard_validation_errors"] == ["duplicate_sentence_near"]
assert item["decision_source"] == {
    "stage": "duplicate_guard",
    "provider": "duplicate_guard",
    "model": "sequence_matcher@0.90",
}
```

**Copy for Phase 05:** add budget/timing regressions as focused artifact-shape assertions, not end-to-end live-provider tests.

---

### `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` (test fixture, file-I/O/transform)

**Analog:** `ankideck_generator/tests/fixtures/ai_sentence_candidates/valid_batch.json`

**JSON fixture shape pattern** from lines 1-35:
```json
{
  "prompt_version": "sentence-batch-v1",
  "schema_version": "sentence-batch-schema-v1",
  "focus_word": "bien",
  "language": "es",
  "requested_pos": "adjective",
  "requested_sense": "in good condition or quality",
  "target_level": 1,
  "candidates": [
    {
      "sentence": "Hoy me siento bien en casa.",
      "target_form": "bien",
      "validation_signals": ["natural_everyday", "focus_present"],
      "rationale": "natural_everyday"
    }
  ]
}
```

**Copy for Phase 05:** keep repo-stored UTF-8 JSON fixtures, include explicit schema/version fields, and make slice labels/data explicit rather than implied.

## Shared Patterns

### Deterministic experiment identity
**Sources:** `ankideck_generator/core/run_state.py` lines 40-60; `ankideck_generator/core/deck_builder.py` lines 364-368, 456-476
**Apply to:** `core/evaluation.py`, `core/models.py`, `core/deck_builder.py`, tests
```python
def build_compatibility_fingerprint(*, model: Any, prompt: Any, schema: Any, validator: Any) -> CompatibilityFingerprint:
    return CompatibilityFingerprint(
        model=_digest(model),
        prompt=_digest(prompt),
        schema_digest=_digest(schema),
        validator=_digest(validator),
        digest=_digest({"model": model, "prompt": prompt, "schema": schema, "validator": validator}),
    )
```

### Metrics/logging backbone
**Sources:** `ankideck_generator/core/models.py` lines 251-273; `ankideck_generator/core/deck_builder.py` lines 1009-1052; `ankideck_generator/utils/logger.py` lines 11-21
**Apply to:** `core/evaluation.py`, `core/deck_builder.py`, `tests/test_evaluation.py`
```python
class LogRecord(BaseModel):
    providers: dict[str, str] = Field(default_factory=dict)
    provider_errors: dict[str, str] = Field(default_factory=dict)
    stage_timings: dict[str, int] = Field(default_factory=dict)
    event_counts: dict[str, int] = Field(default_factory=dict)

def log(self, record: dict[str, Any]) -> None:
    record = dict(record)
    record.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    line = json.dumps(record, ensure_ascii=False)
```

### AI budget + per-stage timing
**Source:** `ankideck_generator/core/deck_builder.py` lines 1669-1733
**Apply to:** `core/deck_builder.py`, `core/providers.py`, lexical-review instrumentation
```python
def allow_ai(field: str) -> bool:
    if ai_calls_total >= run.ai_max_calls_per_word:
        return False
    if ai_calls_by_field.get(field, 0) >= run.ai_max_calls_per_field:
        return False
    return True

if stage_key:
    stage_timings[stage_key] = stage_timings.get(stage_key, 0) + int(getattr(result, "elapsed_ms", 0) or 0)
```

### Atomic JSON artifacts
**Source:** `ankideck_generator/utils/file_utils.py` lines 23-29
**Apply to:** evaluation report writes, benchmark report writes, quality-report extensions
```python
tmp_path = path_obj.with_suffix(path_obj.suffix + ".tmp")
with tmp_path.open("w", encoding="utf-8") as handle:
    json.dump(data, handle, ensure_ascii=False, indent=2)
os.replace(tmp_path, path_obj)
```

## No Analog Found

None. Every Phase 05 touchpoint has at least a partial analog in the current codebase.

## Metadata

**Analog search scope:** `ankideck_generator/core`, `ankideck_generator/utils`, `ankideck_generator/tests`, `ankideck_generator/tests/fixtures`
**Files scanned:** 12
**Pattern extraction date:** 2026-04-22
