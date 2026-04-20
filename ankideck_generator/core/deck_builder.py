from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
import hashlib
import random
import re
import shutil
import threading
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import genanki
from tqdm import tqdm

from ..utils.config import load_config
from ..utils.definition_tools import (
    build_definition,
    build_definition_policy,
    definition_has_pos,
    normalize_definition,
    set_default_definition_policy,
    split_definition,
    trim_definition_body,
)
from ..utils.file_utils import atomic_write_json, ensure_dir, read_json
from ..utils.language_tools import (
    compact_audio_basename,
    content_tokens,
    filter_frequent_words,
    is_closed_class_word,
    score_sentence,
    semantic_definition_reason,
    token_overlap_score,
    text_matches_language,
    tokenize,
    unique_keep_order,
)
from ..utils.logger import JsonLogger
from .cache_manager import CacheManager
from .models import (
    ANKI_FIELD_ORDER_DEFAULT,
    CardData,
    CompatibilityFingerprint,
    LexicalReviewRequest,
    LogRecord,
    ProgressState,
    ProviderResult,
    RunConfig,
    STRUCTURED_SENTENCE_PROMPT_VERSION,
    STRUCTURED_SENTENCE_SCHEMA_VERSION,
    StructuredSentenceBatch,
)
from .lexical_review import LexicalReviewService
from .providers import ProviderManager
from .run_state import (
    build_compatibility_fingerprint,
    fingerprints_match,
    quarantine_name,
)
from .sentence_generation import (
    SENTENCE_GENERATION_POLICY_VERSION,
    SentenceGenerationService,
)
from .validators import ValidationContext, validate_card

try:
    from wordfreq import top_n_list, zipf_frequency
except Exception as exc:  # pragma: no cover - optional
    raise RuntimeError("wordfreq is required") from exc

DEFAULT_VALIDATIONS = {
    "definition_required": True,
    "definition_semantic": True,
    "definition_requires_pos": True,
    "definition_matches_translation_language": True,
    "source_definition_matches_language": True,
    "ipa_required": True,
    "translation_required": True,
    "no_duplicate_focus": True,
    "no_duplicate_sentences": True,
    "focus_in_sentence": True,
    "sentence_matches_language": True,
    "valid_characters": True,
    "ipa_format": True,
    "audio_generated": False,
    "word_audio_required": False,
    "sentence_audio_required": False,
    "definition_not_literal_translation": True,
    "sentence_length": {
        1: (5, 7),
        2: (5, 10),
        3: (6, 15),
    },
    "sentence_profile": {
        1: {"max_commas": 0, "forbid_clause_punctuation": True},
        2: {"max_commas": 1, "forbid_clause_punctuation": True},
        3: {"max_commas": 1, "forbid_clause_punctuation": True},
    },
    "sentence_difficulty_matches_level": True,
    "level_validation_mode": "profile_hard_zipf_soft",
    "ai_quality_check": False,
}

TEST_ACCEPT_ALL_SOFT_ERRORS = {
    "sentence_length_invalid",
    "sentence_profile_invalid",
    "sentence_too_hard_for_level1",
    "sentence_not_level2",
    "sentence_too_easy_for_level3",
}

DEFAULT_HARD_VALIDATION_ERRORS = {
    "function_word",
    "focus_not_in_lexicon",
    "definition_missing",
    "definition_missing_pos",
    "definition_nonsemantic",
    "definition_wrong_language",
    "translation_missing",
    "translation_same_as_source",
    "translation_wrong_language",
    "sentence_missing",
    "focus_not_in_sentence",
    "sentence_wrong_language",
    "invalid_focus_characters",
    "invalid_sentence_characters",
    "duplicate_focus",
    "duplicate_sentence",
    "ipa_missing",
    "invalid_ipa",
}

DEFAULT_SOFT_VALIDATION_ERRORS = {
    "sentence_length_invalid",
    "sentence_profile_invalid",
    "sentence_too_hard_for_level1",
    "sentence_not_level2",
    "sentence_too_easy_for_level3",
    "source_definition_wrong_language",
    "definition_too_similar_translation",
    "word_audio_missing",
    "sentence_audio_missing",
}

SENTENCE_CACHE_SELECTION_VERSION = 2
STRONG_TATOEBA_SELECTION_SCORE = 1.6
TATOEBA_SELECTION_MARGIN = 0.20
MAX_TATOEBA_REWRITE_CANDIDATES = 4
PROGRESS_SCHEMA_VERSION = 1


@dataclass
class SentenceSelectionCandidate:
    text: str
    provider_name: str
    source_kind: str
    selection_score: float
    seeded_from_tatoeba: bool = False
    query_mode: str = ""
    validation_errors: list[str] = field(default_factory=list)
    core_errors: list[str] = field(default_factory=list)
    level_errors: list[str] = field(default_factory=list)


@dataclass
class DefinitionSelectionCandidate:
    text: str
    expected_language: str
    provider_name: str
    source_kind: str
    selection_score: float
    pos: str = ""
    body: str = ""
    lemma: str = ""
    sense_note: str = ""
    alignment_score: float = 0.0
    specificity_score: float = 0.0
    review_notes: list[str] = field(default_factory=list)
    selection_reason: str = ""


@dataclass
class BuildStats:
    cards: list[CardData] = field(default_factory=list)
    media_files: list[str] = field(default_factory=list)
    needs_review_items: list[dict[str, object]] = field(default_factory=list)
    processed: int = 0
    next_sort_index: int = 1
    accepted_by_level: Counter[int] = field(default_factory=Counter)
    attempted_by_level: Counter[int] = field(default_factory=Counter)
    validation_counter: Counter[str] = field(default_factory=Counter)
    provider_counter: Counter[str] = field(default_factory=Counter)
    provider_success_counter: Counter[str] = field(default_factory=Counter)
    provider_error_counter: Counter[str] = field(default_factory=Counter)
    definition_source_counter: Counter[str] = field(default_factory=Counter)
    ambiguous_focus_counter: Counter[str] = field(default_factory=Counter)
    event_counter: Counter[str] = field(default_factory=Counter)
    event_counter_by_level: dict[int, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    stage_counter: Counter[str] = field(default_factory=Counter)
    stage_samples: Counter[str] = field(default_factory=Counter)
    stage_counter_by_level: dict[int, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    stage_samples_by_level: dict[int, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    discard_counter: Counter[str] = field(default_factory=Counter)
    discard_by_level: dict[int, Counter[str]] = field(
        default_factory=lambda: defaultdict(Counter)
    )
    definition_score_total: float = 0.0
    definition_score_samples: int = 0
    corrected_accepted_count: int = 0
    checkpoint_level: int = 1
    checkpoint_index: int = -1


@dataclass
class DecisionCursor:
    contiguous_index: int = -1
    finalized_indexes: set[int] = field(default_factory=set)

    def mark_finalized(self, index: int) -> int:
        self.finalized_indexes.add(index)
        while self.contiguous_index + 1 in self.finalized_indexes:
            self.finalized_indexes.remove(self.contiguous_index + 1)
            self.contiguous_index += 1
        return self.contiguous_index


@dataclass
class TextTaskResult:
    candidate_index: int
    card: CardData | None
    log_record: LogRecord


@dataclass
class AudioTaskResult:
    accepted_index: int
    card: CardData
    log_record: LogRecord
    media_files: list[str] = field(default_factory=list)


def _count_focus_mentions(text: str, focus: str) -> int:
    sentence_tokens = [token.lower() for token in tokenize(text)]
    focus_tokens = [token.lower() for token in tokenize(focus)]
    if not sentence_tokens or not focus_tokens:
        return 0
    if len(focus_tokens) == 1:
        return sentence_tokens.count(focus_tokens[0])
    matches = 0
    window = len(focus_tokens)
    for index in range(0, len(sentence_tokens) - window + 1):
        if sentence_tokens[index : index + window] == focus_tokens:
            matches += 1
    return matches


def _sentence_selection_score(
    sentence: str,
    focus: str,
    language: str,
    level: int,
    min_words: int,
    max_words: int,
) -> float:
    base_score = score_sentence(
        sentence,
        focus,
        language,
        min_words=min_words,
        max_words=max_words,
    )
    if base_score <= 0:
        relaxed_min = max(1, min_words - 2)
        relaxed_max = max(max_words + 6, max_words)
        base_score = score_sentence(
            sentence,
            focus,
            language,
            min_words=relaxed_min,
            max_words=relaxed_max,
        ) * 0.9
    if base_score <= 0:
        return 0.0

    penalty = 0.0
    focus_mentions = _count_focus_mentions(sentence, focus)
    if focus_mentions > 1:
        penalty += min(0.36, float(focus_mentions - 1) * 0.12)

    structural_punctuation = sum(1 for ch in sentence if ch in {",", ";", ":", "—", "–"})
    penalty += min(0.24, float(structural_punctuation) * 0.06)

    quote_or_paren_count = sum(1 for ch in sentence if ch in {'"', "“", "”", "(", ")"})
    penalty += min(0.18, float(quote_or_paren_count) * 0.06)

    if any(ch.isdigit() for ch in sentence):
        penalty += 0.2

    if level <= 2 and any(ch in sentence for ch in {",", ";", ":", "—", "–", "(", ")"}):
        penalty += 0.12 if level == 1 else 0.06

    return max(0.0, base_score - penalty)


class ProgressStore:
    def __init__(self, base_dir: str | Path) -> None:
        self.base_dir = Path(base_dir)
        ensure_dir(self.base_dir)

    def path_for(self, language: str, mode: str) -> Path:
        return self.base_dir / f"{language}_{mode}.json"

    def load(self, language: str, mode: str) -> ProgressState | None:
        path = self.path_for(language, mode)
        if not path.exists():
            return None
        data = read_json(path, default={})
        return ProgressState(**data)

    def save(self, state: ProgressState) -> None:
        state.updated_at = datetime.utcnow().isoformat()
        atomic_write_json(self.path_for(state.language, state.mode), state.model_dump())


class DeckBuilder:
    def __init__(self, config_path: str) -> None:
        self.config_path = config_path
        self.config = load_config(config_path)
        self.definition_policy = self._load_definition_policy()
        definitions_cfg = self.config.setdefault("definitions", {})
        if isinstance(definitions_cfg, dict):
            definitions_cfg["_resolved_policy"] = self.definition_policy
        set_default_definition_policy(self.definition_policy)
        self._text_provider_local = threading.local()
        self._audio_provider_local = threading.local()
        self._last_run_log_path: str | None = None

    def preflight(self, run: RunConfig) -> tuple[bool, str]:
        providers = ProviderManager(
            self.config,
            run.timeout_sec,
            run.retries,
            timeout_overrides=run.provider_timeout_overrides,
            retry_overrides=run.provider_retry_overrides,
        )
        return providers.validate_ai_ready()

    def _build_compatibility_fingerprint(
        self, run: RunConfig
    ) -> CompatibilityFingerprint:
        runtime_cfg = self.config.get("runtime", {}) if isinstance(self.config, dict) else {}
        return build_compatibility_fingerprint(
            model={
                "language": run.language,
                "mode": run.mode,
                "providers": self.config.get("providers", {}) if isinstance(self.config, dict) else {},
            },
            prompt={
                "definition_policy": self.definition_policy,
                "sentence_cache_selection_version": SENTENCE_CACHE_SELECTION_VERSION,
                "structured_sentence_prompt_version": STRUCTURED_SENTENCE_PROMPT_VERSION,
            },
            schema={
                "card_data": CardData.model_json_schema(),
                "progress_state": ProgressState.model_json_schema(),
                "structured_sentence_batch": StructuredSentenceBatch.model_json_schema(),
                "structured_sentence_schema_version": STRUCTURED_SENTENCE_SCHEMA_VERSION,
            },
            validator={
                "default_validations": DEFAULT_VALIDATIONS,
                "hard_validation_errors": sorted(DEFAULT_HARD_VALIDATION_ERRORS),
                "soft_validation_errors": sorted(DEFAULT_SOFT_VALIDATION_ERRORS),
                "error_policy": runtime_cfg.get("error_policy", {}),
                "cache_validation_version": run.cache_validation_version,
                "enforce_translation_language": run.enforce_translation_language,
                "level_validation_mode": run.level_validation_mode,
                "strict_quality": run.strict_quality,
                "target_translation": run.target_translation,
                "sentence_generation_policy_version": SENTENCE_GENERATION_POLICY_VERSION,
            },
        )

    def _coerce_random_state(self, value: object) -> object:
        if isinstance(value, list):
            return tuple(self._coerce_random_state(item) for item in value)
        return value

    def _quarantine_progress_file(self, progress_path: Path, reason: str) -> None:
        if not progress_path.exists():
            return
        progress_path.replace(quarantine_name(progress_path, reason))

    def _load_resume_state(
        self,
        progress_store: ProgressStore,
        run: RunConfig,
        compatibility_fingerprint: CompatibilityFingerprint,
    ) -> ProgressState | None:
        progress_path = progress_store.path_for(run.language, run.mode)
        if not progress_path.exists():
            return None
        try:
            data = read_json(progress_path, default={})
            if not isinstance(data, dict):
                raise ValueError("progress state must be a JSON object")
            state = ProgressState(**data)
        except Exception:
            self._quarantine_progress_file(progress_path, "corrupt")
            return None
        if state.schema_version != PROGRESS_SCHEMA_VERSION or not fingerprints_match(
            compatibility_fingerprint, state.compatibility_fingerprint
        ):
            self._quarantine_progress_file(progress_path, "incompatible")
            return None
        if state.rng_state is not None:
            try:
                random.setstate(self._coerce_random_state(state.rng_state))
            except Exception:
                self._quarantine_progress_file(progress_path, "corrupt")
                return None
        return state

    def _restored_accepted_count(
        self,
        words: list[str],
        processed_focus: set[str],
        *,
        stop_index: int,
    ) -> int:
        processed_focus_lower = {focus.lower() for focus in processed_focus}
        return sum(1 for word in words[:stop_index] if word.lower() in processed_focus_lower)

    def build(self, run: RunConfig) -> tuple[list[CardData], list[str]]:
        cache_manager = CacheManager(run.cache_path, run.language, run.autosave_every)
        progress_store = ProgressStore("ankideck_generator/data/progress")
        log_path = f"ankideck_generator/data/logs/run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jsonl"
        self._last_run_log_path = log_path
        logger = JsonLogger(log_path)
        ctx = ValidationContext()
        compatibility_fingerprint = self._build_compatibility_fingerprint(run)
        random.seed(run.seed)

        level_size = run.level_size
        wordfreq_lang = run.wordfreq_language or run.language
        effective_pool_multiplier = max(1, int(run.level_pool_multiplier))
        level_sets = self._prepare_levels(
            wordfreq_lang,
            level_size,
            run.seed,
            effective_pool_multiplier,
            exclude_closed_class_words=bool(run.exclude_closed_class_words),
            attempt_budget=int(run.max_attempts_per_level or 0),
        )

        state = None
        if run.resume:
            state = self._load_resume_state(
                progress_store,
                run,
                compatibility_fingerprint,
            )
        processed_focus = set(state.processed_focus) if state else set()
        processed_sentences = set(state.processed_sentences) if state else set()
        stats = BuildStats(
            next_sort_index=(state.created_cards + 1) if state and state.created_cards else 1,
            checkpoint_level=state.level if state else 1,
            checkpoint_index=state.index if state else -1,
        )
        ctx.seen_focus.update(focus.lower() for focus in processed_focus)
        ctx.seen_sentence.update(sentence.lower() for sentence in processed_sentences)

        parallel_enabled = (
            not run.interactive
            and max(int(run.concurrency), int(run.audio_concurrency)) > 1
        )

        for level, words in level_sets.items():
            if state and level < state.level:
                stats.accepted_by_level[level] = self._restored_accepted_count(
                    words,
                    processed_focus,
                    stop_index=len(words),
                )
                continue
            start_index = 0
            if state and level == state.level:
                start_index = max(0, int(state.index) + 1)
            stats.accepted_by_level[level] = self._restored_accepted_count(
                words,
                processed_focus,
                stop_index=min(len(words), start_index),
            )
            decision_cursor = DecisionCursor(contiguous_index=start_index - 1)
            if start_index >= len(words):
                stats.checkpoint_level = level
                stats.checkpoint_index = max(stats.checkpoint_index, start_index - 1)
                continue
            if parallel_enabled:
                self._build_level_parallel(
                    level=level,
                    words=words,
                    start_index=start_index,
                    run=run,
                    cache=cache_manager,
                    ctx=ctx,
                    processed_focus=processed_focus,
                    processed_sentences=processed_sentences,
                    stats=stats,
                    logger=logger,
                    progress_store=progress_store,
                    decision_cursor=decision_cursor,
                    compatibility_fingerprint=compatibility_fingerprint,
                )
            else:
                self._build_level_serial(
                    level=level,
                    words=words,
                    start_index=start_index,
                    run=run,
                    cache=cache_manager,
                    ctx=ctx,
                    processed_focus=processed_focus,
                    processed_sentences=processed_sentences,
                    stats=stats,
                    logger=logger,
                    progress_store=progress_store,
                    decision_cursor=decision_cursor,
                    compatibility_fingerprint=compatibility_fingerprint,
                )

        cache_manager.save_all()
        self._save_progress(
            progress_store,
            run,
            compatibility_fingerprint=compatibility_fingerprint,
            level=stats.checkpoint_level,
            index=stats.checkpoint_index,
            processed_focus=processed_focus,
            processed_sentences=processed_sentences,
            next_sort_index=stats.next_sort_index,
        )
        self._print_summary(
            stats.accepted_by_level,
            stats.attempted_by_level,
            stats.validation_counter,
            stats.provider_counter,
            stats.event_counter,
            stats.event_counter_by_level,
            stats.stage_counter,
            stats.stage_samples,
            stats.stage_counter_by_level,
            stats.stage_samples_by_level,
            stats.discard_counter,
            stats.discard_by_level,
        )
        self._write_quality_outputs(run, stats)
        return stats.cards, stats.media_files

    def _build_level_serial(
        self,
        *,
        level: int,
        words: list[str],
        start_index: int,
        run: RunConfig,
        cache: CacheManager,
        ctx: ValidationContext,
        processed_focus: set[str],
        processed_sentences: set[str],
        stats: BuildStats,
        logger: JsonLogger,
        progress_store: ProgressStore,
        decision_cursor: DecisionCursor,
        compatibility_fingerprint: CompatibilityFingerprint,
    ) -> None:
        provider_manager = self._make_provider_manager(run)
        accepted_in_level = stats.accepted_by_level[level]
        level_target = run.level_size
        attempt_cap = int(run.max_attempts_per_level or 0)
        if attempt_cap <= 0:
            attempt_cap = len(words)
        initial_attempt_cap = max(1, attempt_cap)
        progress = tqdm(total=level_target, desc=f"Level {level}", unit="card")
        if accepted_in_level:
            progress.update(min(level_target, accepted_in_level))
        try:
            for index, word in enumerate(words[start_index:], start=start_index):
                if self._is_low_yield_level(level, run, stats):
                    attempted = stats.attempted_by_level[level]
                    accepted = stats.accepted_by_level[level]
                    progress.write(
                        f"Level {level}: stopping by low yield ({accepted}/{attempted})"
                    )
                    break
                if accepted_in_level >= level_target:
                    break
                if stats.attempted_by_level[level] >= attempt_cap:
                    expanded_cap = self._expanded_attempt_cap(
                        current_cap=attempt_cap,
                        initial_cap=initial_attempt_cap,
                        accepted=stats.accepted_by_level[level],
                        target=level_target,
                        words_available=len(words),
                    )
                    if expanded_cap <= attempt_cap:
                        break
                    attempt_cap = expanded_cap
                if word in processed_focus:
                    continue
                blocked_reason = cache.get("invalid_focus", self._invalid_focus_key(word, run))
                if blocked_reason:
                    continue
                stats.attempted_by_level[level] += 1
                try:
                    card, log_record = self._process_word(
                        word=word,
                        level=level,
                        index=index + 1,
                        run=run,
                        cache=cache,
                        providers=provider_manager,
                        ctx=ctx,
                        media_files=stats.media_files,
                    )
                except Exception as exc:  # pragma: no cover - safety net
                    log_record = LogRecord(
                        focus=word,
                        level=level,
                        lifecycle_state="rejected",
                        providers={},
                        provider_errors={},
                        validations=[],
                        status="error",
                        error=str(exc),
                    )
                    card = None

                if self._finalize_card_decision(
                    logger=logger,
                    stats=stats,
                    log_record=log_record,
                    card=card,
                    level=level,
                    word_index=index,
                    progress=progress,
                    cache=cache,
                    run=run,
                    progress_store=progress_store,
                    processed_focus=processed_focus,
                    processed_sentences=processed_sentences,
                    decision_cursor=decision_cursor,
                    compatibility_fingerprint=compatibility_fingerprint,
                ):
                    accepted_in_level += 1
        finally:
            progress.close()

    def _build_level_parallel(
        self,
        *,
        level: int,
        words: list[str],
        start_index: int,
        run: RunConfig,
        cache: CacheManager,
        ctx: ValidationContext,
        processed_focus: set[str],
        processed_sentences: set[str],
        stats: BuildStats,
        logger: JsonLogger,
        progress_store: ProgressStore,
        decision_cursor: DecisionCursor,
        compatibility_fingerprint: CompatibilityFingerprint,
    ) -> None:
        level_target = run.level_size
        attempt_cap = int(run.max_attempts_per_level or 0)
        if attempt_cap <= 0:
            attempt_cap = len(words)
        initial_attempt_cap = max(1, attempt_cap)
        text_workers = max(1, int(run.concurrency))
        audio_workers = max(1, int(run.audio_concurrency))
        reserved_focus: set[str] = set()
        reserved_sentences: set[str] = set()
        word_cursor = start_index
        submit_index = start_index
        next_consume = start_index
        accepted_index = 0
        next_audio_commit = 0
        text_futures: dict[object, int] = {}
        ready_text: dict[int, TextTaskResult] = {}
        audio_futures: dict[object, tuple[int, int]] = {}
        ready_audio: dict[int, tuple[AudioTaskResult, int]] = {}
        progress = tqdm(total=level_target, desc=f"Level {level}", unit="card")
        if stats.accepted_by_level[level]:
            progress.update(min(level_target, stats.accepted_by_level[level]))

        with ThreadPoolExecutor(max_workers=text_workers) as text_executor, ThreadPoolExecutor(max_workers=audio_workers) as audio_executor:
            try:
                while True:
                    if self._is_low_yield_level(level, run, stats):
                        attempted = stats.attempted_by_level[level]
                        accepted = stats.accepted_by_level[level]
                        progress.write(
                            f"Level {level}: stopping by low yield ({accepted}/{attempted})"
                        )
                        break
                    if stats.attempted_by_level[level] >= attempt_cap:
                        attempt_cap = self._expanded_attempt_cap(
                            current_cap=attempt_cap,
                            initial_cap=initial_attempt_cap,
                            accepted=stats.accepted_by_level[level],
                            target=level_target,
                            words_available=len(words),
                        )
                    pending_text_attempts = len(text_futures) + len(ready_text)
                    while (
                        word_cursor < len(words)
                        and len(text_futures) < text_workers
                        and stats.accepted_by_level[level] + len(reserved_focus) < level_target
                        and stats.attempted_by_level[level] + pending_text_attempts
                        < attempt_cap
                    ):
                        word = words[word_cursor]
                        word_cursor += 1
                        if word in processed_focus:
                            continue
                        blocked_reason = cache.get(
                            "invalid_focus", self._invalid_focus_key(word, run)
                        )
                        if blocked_reason:
                            continue
                        future = text_executor.submit(
                            self._process_word_textual_task,
                            word,
                            level,
                            submit_index + 1,
                            run,
                            cache,
                        )
                        text_futures[future] = submit_index
                        submit_index += 1
                        pending_text_attempts += 1
                    cap_reached = stats.attempted_by_level[level] >= attempt_cap

                    if (
                        stats.accepted_by_level[level] >= level_target
                        or (
                            (word_cursor >= len(words) or cap_reached)
                            and not text_futures
                            and not ready_text
                            and not audio_futures
                            and not ready_audio
                        )
                    ):
                        break

                    if not ready_text and not ready_audio and (text_futures or audio_futures):
                        done, _ = wait(
                            list(text_futures.keys()) + list(audio_futures.keys()),
                            timeout=0.2,
                            return_when=FIRST_COMPLETED,
                        )
                        for future in done:
                            if future in text_futures:
                                ready_text[text_futures.pop(future)] = future.result()
                            elif future in audio_futures:
                                accepted_order, candidate_index = audio_futures.pop(future)
                                ready_audio[accepted_order] = (future.result(), candidate_index)
                    else:
                        for future in [f for f in list(text_futures.keys()) if f.done()]:
                            ready_text[text_futures.pop(future)] = future.result()
                        for future in [f for f in list(audio_futures.keys()) if f.done()]:
                            accepted_order, candidate_index = audio_futures.pop(future)
                            ready_audio[accepted_order] = (future.result(), candidate_index)

                    progressed = False

                    while next_consume in ready_text:
                        progressed = True
                        text_result = ready_text.pop(next_consume)
                        next_consume += 1
                        stats.attempted_by_level[level] += 1

                        card = text_result.card
                        log_record = text_result.log_record
                        if not card:
                            self._finalize_card_decision(
                                logger=logger,
                                stats=stats,
                                log_record=log_record,
                                card=None,
                                level=level,
                                word_index=text_result.candidate_index,
                                progress=progress,
                                cache=cache,
                                run=run,
                                progress_store=progress_store,
                                processed_focus=processed_focus,
                                processed_sentences=processed_sentences,
                                decision_cursor=decision_cursor,
                                compatibility_fingerprint=compatibility_fingerprint,
                            )
                            continue

                        text_errors = unique_keep_order(
                            log_record.validations
                            + self._validate_text_candidate(
                                card,
                                ctx,
                                run,
                                reserved_focus,
                                reserved_sentences,
                            )
                        )
                        if self._should_reject_errors(text_errors, run):
                            log_record.validations = text_errors
                            log_record.status = "discarded"
                            log_record.discard_reason = _infer_discard_reason(
                                text_errors, log_record.provider_errors
                            )
                            self._finalize_card_decision(
                                logger=logger,
                                stats=stats,
                                log_record=log_record,
                                card=None,
                                level=level,
                                word_index=text_result.candidate_index,
                                progress=progress,
                                cache=cache,
                                run=run,
                                progress_store=progress_store,
                                processed_focus=processed_focus,
                                processed_sentences=processed_sentences,
                                decision_cursor=decision_cursor,
                                compatibility_fingerprint=compatibility_fingerprint,
                            )
                            continue

                        log_record.validations = text_errors
                        log_record.lifecycle_state = "reviewed"
                        reserved_focus.add(card.focus.lower())
                        reserved_sentences.add(card.sentence.lower())
                        future = audio_executor.submit(
                            self._attach_audio_task,
                            accepted_index,
                            card,
                            log_record,
                            run,
                            cache,
                        )
                        audio_futures[future] = (accepted_index, text_result.candidate_index)
                        accepted_index += 1

                    while next_audio_commit in ready_audio:
                        progressed = True
                        audio_result, candidate_index = ready_audio.pop(next_audio_commit)
                        next_audio_commit += 1
                        card = audio_result.card
                        log_record = audio_result.log_record
                        reserved_focus.discard(card.focus.lower())
                        reserved_sentences.discard(card.sentence.lower())

                        final_errors = unique_keep_order(
                            log_record.validations + self._audio_validation_errors(card, run)
                        )
                        if self._should_reject_errors(final_errors, run):
                            log_record.validations = final_errors
                            log_record.status = "discarded"
                            log_record.discard_reason = _infer_discard_reason(
                                final_errors, log_record.provider_errors
                            )
                            self._finalize_card_decision(
                                logger=logger,
                                stats=stats,
                                log_record=log_record,
                                card=None,
                                level=level,
                                word_index=candidate_index,
                                progress=progress,
                                cache=cache,
                                run=run,
                                progress_store=progress_store,
                                processed_focus=processed_focus,
                                processed_sentences=processed_sentences,
                                decision_cursor=decision_cursor,
                                compatibility_fingerprint=compatibility_fingerprint,
                            )
                            continue

                        for path in audio_result.media_files:
                            if path and path not in stats.media_files:
                                stats.media_files.append(path)

                        log_record.status = "accepted"
                        log_record.discard_reason = None
                        log_record.validations = final_errors if final_errors else []
                        self._finalize_card_decision(
                            logger=logger,
                            stats=stats,
                            log_record=log_record,
                            card=card,
                            level=level,
                            word_index=candidate_index,
                            progress=progress,
                            cache=cache,
                            run=run,
                            progress_store=progress_store,
                            processed_focus=processed_focus,
                            processed_sentences=processed_sentences,
                            decision_cursor=decision_cursor,
                            compatibility_fingerprint=compatibility_fingerprint,
                            ctx=ctx,
                        )
                        if stats.accepted_by_level[level] >= level_target:
                            break

                    if not progressed and (text_futures or audio_futures):
                        continue
            finally:
                for future in list(text_futures.keys()):
                    future.cancel()
                for future in list(audio_futures.keys()):
                    future.cancel()
                progress.close()

    def _finalize_card_decision(
        self,
        *,
        logger: JsonLogger,
        stats: BuildStats,
        log_record: LogRecord,
        card: CardData | None,
        level: int,
        word_index: int,
        progress: tqdm,
        cache: CacheManager,
        run: RunConfig,
        progress_store: ProgressStore,
        processed_focus: set[str],
        processed_sentences: set[str],
        decision_cursor: DecisionCursor,
        compatibility_fingerprint: CompatibilityFingerprint,
        ctx: ValidationContext | None = None,
    ) -> bool:
        accepted = card is not None and str(log_record.status) == "accepted"
        if accepted:
            card.lifecycle_state = "accepted"
            card.index = stats.next_sort_index
            stats.next_sort_index += 1
            stats.cards.append(card)
            processed_focus.add(card.focus)
            processed_sentences.add(card.sentence)
            if ctx is not None:
                ctx.seen_focus.add(card.focus.lower())
                ctx.seen_sentence.add(card.sentence.lower())
            stats.accepted_by_level[level] += 1
            log_record.lifecycle_state = "accepted"
            log_record.after = log_record.after or card.model_dump()
            progress.update(1)
        else:
            log_record.lifecycle_state = "rejected"

        if log_record.discard_reason and log_record.discard_reason not in log_record.reason_codes:
            log_record.reason_codes.append(log_record.discard_reason)
        for validation_error in log_record.validations:
            if validation_error not in log_record.reason_codes:
                log_record.reason_codes.append(validation_error)

        self._record_log(logger, stats, log_record)
        checkpoint_index = decision_cursor.mark_finalized(word_index)
        stats.checkpoint_level = level
        stats.checkpoint_index = checkpoint_index
        self._maybe_checkpoint(
            stats=stats,
            run=run,
            cache=cache,
            progress_store=progress_store,
            compatibility_fingerprint=compatibility_fingerprint,
            level=level,
            index=checkpoint_index,
            processed_focus=processed_focus,
            processed_sentences=processed_sentences,
        )
        return accepted

    def _record_log(self, logger: JsonLogger, stats: BuildStats, log_record: LogRecord) -> None:
        logger.log(log_record.model_dump())
        level = int(log_record.level or 0)
        for field_name, provider_name in log_record.providers.items():
            key = f"{field_name}:{provider_name}"
            stats.provider_counter[key] += 1
            if provider_name and provider_name != "none" and not (log_record.provider_errors or {}).get(field_name):
                stats.provider_success_counter[key] += 1
        for field_name, error in (log_record.provider_errors or {}).items():
            if error:
                stats.provider_error_counter[field_name] += 1
        definition_reason = (log_record.selection_reasons or {}).get("definition", "")
        if definition_reason:
            source_kind = definition_reason.split(";", 1)[0].strip()
            if source_kind:
                stats.definition_source_counter[source_kind] += 1
        for event_name, count in (log_record.event_counts or {}).items():
            stats.event_counter[event_name] += int(count or 0)
            stats.event_counter_by_level[level][event_name] += int(count or 0)
        if "definition_polysemy_detected" in (log_record.review_notes or []):
            stats.ambiguous_focus_counter[log_record.focus] += 1
        for validation_error in log_record.validations:
            stats.validation_counter[validation_error] += 1
        if log_record.discard_reason:
            stats.discard_counter[log_record.discard_reason] += 1
            stats.discard_by_level[level][log_record.discard_reason] += 1
        definition_score = (log_record.quality_scores or {}).get("definition")
        if isinstance(definition_score, (int, float)):
            stats.definition_score_total += float(definition_score)
            stats.definition_score_samples += 1
        if log_record.lifecycle_state == "accepted" and (
            log_record.review_notes or log_record.before
        ):
            stats.corrected_accepted_count += 1
        if log_record.lifecycle_state == "rejected":
            stats.needs_review_items.append(
                {
                    "focus": log_record.focus,
                    "level": level,
                    "status": log_record.status,
                    "lifecycle_state": log_record.lifecycle_state,
                    "discard_reason": log_record.discard_reason,
                    "reason_codes": list(log_record.reason_codes or []),
                    "before": dict(log_record.before or {}),
                    "after": dict(log_record.after or {}),
                    "provider": log_record.provider,
                    "model": log_record.model,
                    "providers": dict(log_record.providers or {}),
                    "provider_errors": dict(log_record.provider_errors or {}),
                    "event_counts": dict(log_record.event_counts or {}),
                    "stage_timings": dict(log_record.stage_timings or {}),
                    "review_notes": list(log_record.review_notes or []),
                    "validations": list(log_record.validations or []),
                    "definition_candidates": list(
                        (log_record.candidate_preview or {}).get("definitions", [])
                    ),
                    "source_definition_candidates": list(
                        (log_record.candidate_preview or {}).get("source_definitions", [])
                    ),
                    "quality_scores": dict(log_record.quality_scores or {}),
                    "selection_reasons": dict(log_record.selection_reasons or {}),
                }
            )
        for stage_name, elapsed_ms in (log_record.stage_timings or {}).items():
            stats.stage_counter[stage_name] += int(elapsed_ms or 0)
            stats.stage_samples[stage_name] += 1
            stats.stage_counter_by_level[level][stage_name] += int(elapsed_ms or 0)
            stats.stage_samples_by_level[level][stage_name] += 1
        stats.processed += 1

    def _maybe_checkpoint(
        self,
        *,
        stats: BuildStats,
        run: RunConfig,
        cache: CacheManager,
        progress_store: ProgressStore,
        compatibility_fingerprint: CompatibilityFingerprint,
        level: int,
        index: int,
        processed_focus: set[str],
        processed_sentences: set[str],
    ) -> None:
        if run.autosave_every <= 0:
            return
        if stats.processed <= 0:
            return
        if stats.processed % run.autosave_every != 0:
            return
        cache.save_all()
        self._save_progress(
            progress_store,
            run,
            compatibility_fingerprint=compatibility_fingerprint,
            level=level,
            index=index,
            processed_focus=processed_focus,
            processed_sentences=processed_sentences,
            next_sort_index=stats.next_sort_index,
        )

    def _save_progress(
        self,
        progress_store: ProgressStore,
        run: RunConfig,
        *,
        compatibility_fingerprint: CompatibilityFingerprint,
        level: int,
        index: int,
        processed_focus: set[str],
        processed_sentences: set[str],
        next_sort_index: int,
    ) -> None:
        progress_store.save(
            ProgressState(
                language=run.language,
                mode=run.mode,
                schema_version=PROGRESS_SCHEMA_VERSION,
                compatibility_fingerprint=compatibility_fingerprint,
                level=level,
                index=index,
                rng_state=random.getstate(),
                processed_focus=sorted(processed_focus),
                processed_sentences=sorted(processed_sentences),
                created_cards=next_sort_index - 1,
            )
        )

    def _make_provider_manager(self, run: RunConfig) -> ProviderManager:
        return ProviderManager(
            self.config,
            run.timeout_sec,
            run.retries,
            timeout_overrides=run.provider_timeout_overrides,
            retry_overrides=run.provider_retry_overrides,
        )

    def _sentence_generation_service(
        self,
        providers: ProviderManager,
        *,
        strict_quality: bool,
    ) -> SentenceGenerationService:
        return SentenceGenerationService(providers, strict_quality=strict_quality)

    def _thread_provider_manager(
        self,
        run: RunConfig,
        *,
        kind: str,
    ) -> ProviderManager:
        local = self._text_provider_local if kind == "text" else self._audio_provider_local
        signature = (
            int(run.timeout_sec),
            int(run.retries),
            tuple(sorted((run.provider_timeout_overrides or {}).items())),
            tuple(sorted((run.provider_retry_overrides or {}).items())),
        )
        provider = getattr(local, "provider", None)
        cached_signature = getattr(local, "signature", None)
        if provider is None or cached_signature != signature:
            provider = self._make_provider_manager(run)
            local.provider = provider
            local.signature = signature
        return provider

    def export_deck(
        self, run: RunConfig, cards: list[CardData], media_files: list[str]
    ) -> None:
        audio_cfg = self.config.get("audio") if isinstance(self.config, dict) else {}
        audio_cfg = audio_cfg if isinstance(audio_cfg, dict) else {}
        cleanup_audio = bool(audio_cfg.get("cleanup_after_export", False))
        cleanup_dir = audio_cfg.get("output_dir", "ankideck_generator/data/audio")
        deck_cfg, field_order = self._deck_config_for_language(run.language)
        default_model_id = 1607392337 if run.language == "ru" else 1607392319
        default_deck_id = 2059400127 if run.language == "ru" else 2059400110
        model = genanki.Model(
            deck_cfg.get("model_id", default_model_id),
            deck_cfg.get("name", "Anki Deck Generator"),
            fields=[{"name": field_name} for field_name in field_order],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": self._resolve_path(
                        deck_cfg.get("front_template")
                    ).read_text(encoding="utf-8"),
                    "afmt": self._resolve_path(deck_cfg.get("back_template")).read_text(
                        encoding="utf-8"
                    ),
                }
            ],
            css=self._resolve_path(deck_cfg.get("css_path")).read_text(
                encoding="utf-8"
            ),
        )

        deck = genanki.Deck(
            deck_cfg.get("deck_id", default_deck_id),
            deck_cfg.get("name", "Anki Deck Generator"),
        )
        accepted_cards = [card for card in cards if card.lifecycle_state == "accepted"]
        for card in accepted_cards:
            note = genanki.Note(
                model=model,
                fields=card.genanki_fields(field_order),
                tags=[f"level{card.level}", card.language],
            )
            deck.add_note(note)

        package = genanki.Package(deck)
        package.media_files = media_files
        ensure_dir(Path(run.output_path).parent)
        package.write_to_file(run.output_path)

        metadata = {
            "generated_at": datetime.utcnow().isoformat(),
            "language": run.language,
            "mode": run.mode,
            "cards": len(cards),
            "output": run.output_path,
        }
        atomic_write_json("output/metadata.json", metadata)
        self._cleanup_run_artifacts(
            run,
            cleanup_audio=cleanup_audio,
            audio_dir=cleanup_dir,
            media_files=media_files,
        )

    def _prepare_levels(
        self,
        language: str,
        level_size: int,
        seed: int,
        pool_multiplier: int = 8,
        *,
        exclude_closed_class_words: bool = True,
        attempt_budget: int = 0,
    ) -> dict[int, list[str]]:
        pool_multiplier = max(1, int(pool_multiplier))
        attempt_budget = max(0, int(attempt_budget))
        pool_size = max(level_size * pool_multiplier, level_size)
        if attempt_budget:
            pool_size = max(
                pool_size,
                min(50000, max(level_size * pool_multiplier * 2, attempt_budget * 2)),
            )
        required_total = pool_size * 3
        target_total = max(required_total, 6000)
        filtered_top: list[str] = []

        while len(filtered_top) < required_total:
            raw_top = top_n_list(language, target_total)
            filtered_top = filter_frequent_words(
                raw_top,
                language,
                min_length=3,
                exclude_closed_class_words=exclude_closed_class_words,
            )
            if len(filtered_top) >= required_total or target_total >= 200000:
                break
            target_total *= 2

        band_size = max(
            pool_size,
            min(len(filtered_top) // 3, max(pool_size * 4, level_size * 12)),
        )

        def ordered_pool(words: list[str]) -> list[str]:
            unique_words = unique_keep_order(words)
            return unique_words[:pool_size]

        level1 = ordered_pool(filtered_top[:band_size])
        level2 = ordered_pool(filtered_top[band_size : band_size * 2])
        level3 = ordered_pool(filtered_top[band_size * 2 : band_size * 3])

        return {
            1: level1,
            2: level2,
            3: level3,
        }

    def _expanded_attempt_cap(
        self,
        *,
        current_cap: int,
        initial_cap: int,
        accepted: int,
        target: int,
        words_available: int,
    ) -> int:
        if accepted >= target or current_cap >= words_available:
            return current_cap
        step = max(1, initial_cap, target)
        return min(words_available, current_cap + step)

    def _deck_config_for_language(self, language: str) -> tuple[dict, list[str]]:
        deck_cfg = dict(self.config.get("deck", {}))
        field_order = ANKI_FIELD_ORDER_DEFAULT
        return deck_cfg, field_order

    def _lexicon_zipf_fallback_ok(self, word: str, run: RunConfig) -> bool:
        threshold = max(0.0, float(run.lexicon_zipf_fallback_min or 0.0))
        if threshold <= 0.0:
            return False
        try:
            score = float(zipf_frequency(word, run.wordfreq_language or run.language))
        except Exception:
            return False
        return score >= threshold

    def _invalid_focus_key(self, word: str, run: RunConfig) -> str:
        return f"{word.lower()}::v{int(run.cache_validation_version or 0)}"

    def _is_low_yield_level(self, level: int, run: RunConfig, stats: BuildStats) -> bool:
        if int(run.low_yield_start_level or 1) > level:
            return False
        min_attempts = max(0, int(run.low_yield_min_attempts or 0))
        min_rate = max(0.0, float(run.low_yield_min_acceptance_rate or 0.0))
        if min_attempts <= 0 or min_rate <= 0.0:
            return False
        attempted = int(stats.attempted_by_level.get(level, 0))
        if attempted < min_attempts:
            return False
        accepted = int(stats.accepted_by_level.get(level, 0))
        max_accepted = max(0, int(run.low_yield_max_accepted or 0))
        if max_accepted > 0 and accepted > max_accepted:
            return False
        return (accepted / attempted) < min_rate

    def _resolve_path(self, value: str | None) -> Path:
        if not value:
            raise ValueError("Missing template path in config")
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(self.config_path).resolve().parent / path

    def _load_definition_policy(self) -> dict[str, object]:
        definitions_cfg = (
            self.config.get("definitions", {}) if isinstance(self.config, dict) else {}
        )
        definitions_cfg = definitions_cfg if isinstance(definitions_cfg, dict) else {}
        policy_path = definitions_cfg.get("policy_path")
        if not policy_path:
            return build_definition_policy()
        try:
            raw_policy = load_config(self._resolve_path(str(policy_path)))
        except FileNotFoundError:
            raw_policy = {}
        return build_definition_policy(raw_policy if isinstance(raw_policy, dict) else {})

    def _process_word(
        self,
        word: str,
        level: int,
        index: int,
        run: RunConfig,
        cache: CacheManager,
        providers: ProviderManager,
        ctx: ValidationContext,
        media_files: list[str],
    ) -> tuple[CardData | None, LogRecord]:
        card, log_record = self._process_word_textual(
            word=word,
            level=level,
            index=index,
            run=run,
            cache=cache,
            providers=providers,
        )
        if not card:
            return None, log_record

        card, log_record = self._revalidate_card_before_acceptance(
            card=card,
            log_record=log_record,
            ctx=ctx,
            run=run,
        )
        if not card:
            return None, log_record

        card, log_record, generated_media = self._attach_audio_to_card(
            card=card,
            log_record=log_record,
            run=run,
            cache=cache,
            providers=providers,
        )
        for path in generated_media:
            if path and path not in media_files:
                media_files.append(path)

        final_errors = unique_keep_order(
            log_record.validations + self._audio_validation_errors(card, run)
        )
        if self._should_reject_errors(final_errors, run):
            log_record.validations = final_errors
            log_record.status = "discarded"
            log_record.lifecycle_state = "rejected"
            log_record.discard_reason = _infer_discard_reason(
                final_errors, log_record.provider_errors
            )
            return None, log_record

        if run.interactive:
            try:
                before_edit = self._review_snapshot(card)
                card = self._interactive_edit(card, log_record)
            except ValueError:
                return None, LogRecord(
                    focus=word,
                    level=level,
                    lifecycle_state="rejected",
                    providers=log_record.providers,
                    provider_errors=log_record.provider_errors,
                    stage_timings=log_record.stage_timings,
                    event_counts=log_record.event_counts,
                    validations=["skipped_by_user"],
                    review_notes=log_record.review_notes,
                    candidate_preview=log_record.candidate_preview,
                    quality_scores=log_record.quality_scores,
                    selection_reasons=log_record.selection_reasons,
                    status="skipped",
                )
            after_edit = self._review_snapshot(card)
            if after_edit != before_edit:
                self._merge_review_evidence(
                    log_record,
                    before=before_edit,
                    after=after_edit,
                )
                card, log_record = self._revalidate_card_before_acceptance(
                    card=card,
                    log_record=log_record,
                    ctx=ctx,
                    run=run,
                )
                if not card:
                    return None, log_record

        ctx.seen_focus.add(card.focus.lower())
        ctx.seen_sentence.add(card.sentence.lower())
        card.lifecycle_state = "accepted"
        log_record.status = "accepted"
        log_record.lifecycle_state = "accepted"
        log_record.discard_reason = None
        log_record.validations = final_errors if final_errors else []
        return card, log_record

    def _process_word_textual_task(
        self,
        word: str,
        level: int,
        index: int,
        run: RunConfig,
        cache: CacheManager,
    ) -> TextTaskResult:
        providers = self._thread_provider_manager(run, kind="text")
        try:
            card, log_record = self._process_word_textual(
                word=word,
                level=level,
                index=index,
                run=run,
                cache=cache,
                providers=providers,
            )
        except Exception as exc:  # pragma: no cover - safety net
            card = None
            log_record = LogRecord(
                focus=word,
                level=level,
                lifecycle_state="rejected",
                providers={},
                provider_errors={},
                validations=[],
                status="error",
                error=str(exc),
            )
        return TextTaskResult(candidate_index=index - 1, card=card, log_record=log_record)

    def _attach_audio_task(
        self,
        accepted_index: int,
        card: CardData,
        log_record: LogRecord,
        run: RunConfig,
        cache: CacheManager,
    ) -> AudioTaskResult:
        providers = self._thread_provider_manager(run, kind="audio")
        try:
            card, log_record, media_files = self._attach_audio_to_card(
                card=card,
                log_record=log_record,
                run=run,
                cache=cache,
                providers=providers,
            )
        except Exception as exc:  # pragma: no cover - safety net
            log_record.provider_errors["audio"] = str(exc)
            media_files = []
        return AudioTaskResult(
            accepted_index=accepted_index,
            card=card,
            log_record=log_record,
            media_files=media_files,
        )

    def _review_snapshot(self, card: CardData) -> dict[str, object]:
        return {
            "focus": card.focus,
            "definition": card.definition,
            "sentence": card.sentence,
            "translation": card.translation,
            "ipa": card.ipa,
            "source_definition": card.source_definition,
        }

    def _merge_review_evidence(
        self,
        log_record: LogRecord,
        *,
        before: dict[str, object],
        after: dict[str, object],
    ) -> None:
        merged_before = dict(log_record.before or {})
        merged_after = dict(log_record.after or {})
        for field_name, before_value in before.items():
            after_value = after.get(field_name)
            if before_value == after_value:
                continue
            merged_before.setdefault(field_name, before_value)
            merged_after[field_name] = after_value
        log_record.before = merged_before
        log_record.after = merged_after

    def _revalidate_card_before_acceptance(
        self,
        *,
        card: CardData,
        log_record: LogRecord,
        ctx: ValidationContext,
        run: RunConfig,
        reserved_focus: set[str] | None = None,
        reserved_sentences: set[str] | None = None,
    ) -> tuple[CardData | None, LogRecord]:
        text_errors = unique_keep_order(
            log_record.validations
            + self._validate_text_candidate(
                card,
                ctx,
                run,
                reserved_focus,
                reserved_sentences,
            )
        )
        log_record.validations = text_errors
        if self._should_reject_errors(text_errors, run):
            log_record.status = "discarded"
            log_record.lifecycle_state = "rejected"
            log_record.discard_reason = _infer_discard_reason(
                text_errors, log_record.provider_errors
            )
            for reason_code in text_errors:
                if reason_code not in log_record.reason_codes:
                    log_record.reason_codes.append(reason_code)
            return None, log_record
        return card, log_record

    def _process_word_textual(
        self,
        *,
        word: str,
        level: int,
        index: int,
        run: RunConfig,
        cache: CacheManager,
        providers: ProviderManager,
    ) -> tuple[CardData | None, LogRecord]:
        providers_used: dict[str, str] = {}
        provider_errors: dict[str, str] = {}
        stage_timings: dict[str, int] = {}
        event_counts: Counter[str] = Counter()
        ai_calls_total = 0
        ai_calls_by_field: dict[str, int] = {}
        quality_errors: list[str] = []
        review_notes: list[str] = []
        candidate_preview: dict[str, list[str]] = {}
        quality_scores: dict[str, float] = {}
        selection_reasons: dict[str, str] = {}
        strict_quality = bool(run.strict_quality)
        validation_rules = _validations_for_language(
            run.language,
            audio_required=False,
            strict_quality=strict_quality,
            level_validation_mode=run.level_validation_mode,
        )
        sentence_min_words, sentence_max_words = _sentence_length_bounds(
            validation_rules.get("sentence_length"),
            level,
        )
        cache_version = max(1, int(run.cache_validation_version or 1))
        normalized_word = word.strip().lower()
        sentence_cache_key = (
            f"{normalized_word}::lvl{level}::{sentence_min_words}-{sentence_max_words}::sv{SENTENCE_CACHE_SELECTION_VERSION}::v{cache_version}"
        )
        refresh_text_kinds = {"sentences", "definitions", "translations", "word_translations"}

        def cache_get(kind: str, key: str) -> object | None:
            if run.refresh_text_cache and kind in refresh_text_kinds:
                return None
            return cache.get(kind, key)

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

        def trace_result(
            field: str,
            result: ProviderResult,
            *,
            ai_field: str | None = None,
            stage_key: str | None = None,
        ) -> None:
            providers_used[field] = result.provider_name
            if result.error:
                provider_errors[field] = result.error
            fallback_errors = getattr(result, "fallback_errors", None)
            if isinstance(fallback_errors, dict):
                for name, error in fallback_errors.items():
                    if error:
                        provider_errors[f"{field}:{name}"] = str(error)
            if ai_field and result.provider_name == "ai":
                mark_ai(ai_field)
            if stage_key:
                stage_timings[stage_key] = stage_timings.get(stage_key, 0) + int(
                    getattr(result, "elapsed_ms", 0) or 0
                )

        def trace_candidates_result(
            field: str,
            result: object,
            *,
            ai_field: str | None = None,
            stage_key: str | None = None,
        ) -> None:
            provider_name = str(getattr(result, "provider_name", "none") or "none")
            providers_used[field] = provider_name
            error = getattr(result, "error", None)
            if error:
                provider_errors[field] = str(error)
            fallback_errors = getattr(result, "fallback_errors", None)
            if isinstance(fallback_errors, dict):
                for name, item_error in fallback_errors.items():
                    if item_error:
                        provider_errors[f"{field}:{name}"] = str(item_error)
            if ai_field:
                used_ai = provider_name == "ai"
                if not used_ai and isinstance(getattr(result, "candidates", None), list):
                    used_ai = any(
                        getattr(candidate, "provider_name", "") == "ai"
                        for candidate in getattr(result, "candidates", [])
                    )
                if used_ai:
                    mark_ai(ai_field)
            if stage_key:
                stage_timings[stage_key] = stage_timings.get(stage_key, 0) + int(
                    getattr(result, "elapsed_ms", 0) or 0
                )

        def remember_quality_error(name: str | None) -> None:
            if name and name not in quality_errors:
                quality_errors.append(name)

        def remember_review_note(name: str | None) -> None:
            if name and name not in review_notes:
                review_notes.append(name)

        def set_candidate_preview(name: str, values: list[str]) -> None:
            previews = [str(value).strip() for value in values if str(value).strip()]
            if previews:
                candidate_preview[name] = previews[: max(1, int(run.definition_candidates_limit or 5))]

        def count_event(name: str) -> None:
            if name:
                event_counts[name] += 1

        def normalize_definition_candidate(text: str, language: str) -> str:
            return normalize_definition(
                text,
                language,
                pos_mode="auto",
                min_words=1,
                max_words=12,
                policy=self.definition_policy,
            )

        def definition_issue(text: str, expected_language: str) -> str | None:
            if not text:
                return "definition_missing"
            if not definition_has_pos(text, policy=self.definition_policy):
                return "definition_missing_pos"
            if strict_quality:
                _pos_label, body = split_definition(text, policy=self.definition_policy)
                alpha_tokens = [
                    token for token in tokenize(body or text) if any(char.isalpha() for char in token)
                ]
                if len(alpha_tokens) >= 2:
                    if not text_matches_language(
                        body or text,
                        expected_language,
                        min_score=0.25,
                        min_tokens=min(2, len(alpha_tokens)),
                    ):
                        return "definition_wrong_language"
                elif expected_language not in {run.target_translation, "en"}:
                    return "definition_wrong_language"
            semantic_issue = semantic_definition_reason(text, word)
            if semantic_issue:
                if semantic_issue == "definition_mentions_other_language":
                    return "definition_wrong_language"
                return "definition_nonsemantic"
            return None

        level_only_sentence_errors = {
            "sentence_length_invalid",
            "sentence_profile_invalid",
            "sentence_too_hard_for_level1",
            "sentence_not_level2",
            "sentence_too_easy_for_level3",
        }

        def analyze_sentence(
            candidate: str,
        ) -> tuple[str, list[str], list[str], list[str]]:
            text = (candidate or "").strip()
            if not text:
                return "", ["sentence_missing"], ["sentence_missing"], []
            sentence_validations = {
                "focus_in_sentence": True,
                "sentence_matches_language": strict_quality,
                "valid_characters": True,
                "sentence_length": validation_rules.get("sentence_length"),
                "sentence_profile": validation_rules.get("sentence_profile"),
                "sentence_difficulty_matches_level": bool(
                    validation_rules.get("sentence_difficulty_matches_level")
                ),
                "level_validation_mode": run.level_validation_mode,
            }
            errors = unique_keep_order(
                validate_card(
                    CardData(
                        focus=word,
                        sentence=text,
                        level=level,
                        language=run.language,
                        translation_language=run.target_translation,
                    ),
                    ValidationContext(),
                    sentence_validations,
                    commit=False,
                )
            )
            core_errors = [
                error for error in errors if error not in level_only_sentence_errors
            ]
            level_errors = [error for error in errors if error in level_only_sentence_errors]
            return text, errors, core_errors, level_errors

        def finalize_definition(
            candidate: str, expected_language: str
        ) -> tuple[str, str | None]:
            text = normalize_definition_candidate(candidate, expected_language)
            issue = definition_issue(text, expected_language)
            return (text, None) if not issue else ("", issue)

        def definition_specificity_score(text: str) -> float:
            _pos_label, body = split_definition(text, policy=self.definition_policy)
            alpha_tokens = [token for token in tokenize(body) if any(char.isalpha() for char in token)]
            if not alpha_tokens:
                return 0.0
            target_min, target_max = {
                1: (2, 6),
                2: (3, 8),
                3: (4, 10),
            }.get(level, (3, 8))
            count = len(alpha_tokens)
            if count < target_min:
                return max(0.0, count / max(1, target_min))
            if count > target_max:
                overflow = min(1.0, (count - target_max) / max(1, target_max))
                return max(0.2, 1.0 - overflow)
            return 1.0

        def definition_alignment_score(
            text: str,
            expected_language: str,
            *,
            inherited_alignment: float = 0.0,
            translation_reference: str = "",
        ) -> float:
            _pos_label, body = split_definition(text, policy=self.definition_policy)
            if not body:
                return inherited_alignment
            reference = ""
            reference_language = expected_language
            if expected_language == run.language:
                reference = sentence
                reference_language = run.language
            elif translation_reference and expected_language == run.target_translation:
                reference = translation_reference
                reference_language = run.target_translation
            if not reference:
                return inherited_alignment
            overlap = token_overlap_score(
                body,
                reference,
                reference_language,
                drop=tokenize(word),
            )
            return max(inherited_alignment, overlap)

        def make_definition_selection_reason(
            source_kind: str,
            provider_name: str,
            alignment: float,
            specificity: float,
        ) -> str:
            parts = [source_kind, provider_name]
            if alignment > 0:
                parts.append(f"align={alignment:.2f}")
            parts.append(f"specificity={specificity:.2f}")
            return "; ".join(parts)

        def make_definition_candidate(
            candidate: str,
            expected_language: str,
            *,
            provider_name: str,
            source_kind: str,
            inherited_alignment: float = 0.0,
            lemma_value: str = "",
            sense_note_value: str = "",
            translation_reference: str = "",
        ) -> DefinitionSelectionCandidate | None:
            text, issue = finalize_definition(candidate, expected_language)
            if issue:
                return None
            pos_label, body = split_definition(text, policy=self.definition_policy)
            specificity = definition_specificity_score(text)
            alignment = definition_alignment_score(
                text,
                expected_language,
                inherited_alignment=inherited_alignment,
                translation_reference=translation_reference,
            )
            selection_score = specificity + alignment * 1.8
            if source_kind in {"cache_context", "context", "translated_context"}:
                selection_score += 0.3
            elif source_kind.startswith("cache"):
                selection_score += 0.15
            elif source_kind.startswith("translated"):
                selection_score += 0.1
            if provider_name == "ai" and sentence:
                selection_score += 0.08
            review_flags: list[str] = []
            if sentence and alignment < 0.08:
                review_flags.append("definition_low_context_alignment")
            if specificity < 0.55:
                review_flags.append("definition_low_specificity")
            return DefinitionSelectionCandidate(
                text=text,
                expected_language=expected_language,
                provider_name=provider_name,
                source_kind=source_kind,
                selection_score=selection_score,
                pos=pos_label,
                body=body,
                lemma=lemma_value,
                sense_note=sense_note_value,
                alignment_score=alignment,
                specificity_score=specificity,
                review_notes=review_flags,
                selection_reason=make_definition_selection_reason(
                    source_kind,
                    provider_name,
                    alignment,
                    specificity,
                ),
            )

        def definition_variants(
            pos_label: str,
            body: str,
        ) -> tuple[str, str]:
            precise_body = trim_definition_body(
                body,
                2 if level <= 2 else 3,
                10 if level == 1 else 12,
            ) or body.strip().rstrip(".")
            short_body = trim_definition_body(
                body,
                2,
                5 if level == 1 else 7,
            )
            precise = build_definition(pos_label, precise_body, policy=self.definition_policy)
            short = build_definition(pos_label, short_body, policy=self.definition_policy)
            if short == precise:
                short = ""
            return short, precise

        def should_cache_definition_candidate(
            candidate: DefinitionSelectionCandidate | None,
        ) -> bool:
            if candidate is None:
                return False
            if candidate.review_notes:
                return False
            if candidate.source_kind in {"word_fallback", "ai"}:
                return False
            return candidate.selection_score >= 1.0

        def translation_issue(text: str, source_sentence: str) -> str | None:
            value = (text or "").strip()
            if not value:
                return "translation_missing"
            if (
                run.language != run.target_translation
                and value.lower() == source_sentence.strip().lower()
            ):
                return "translation_same_as_source"
            if run.enforce_translation_language and strict_quality:
                alpha_tokens = [
                    token for token in value.split() if any(char.isalpha() for char in token)
                ]
                if len(alpha_tokens) >= 3 and not text_matches_language(
                    value, run.target_translation, min_score=0.2, min_tokens=2
                ):
                    return "translation_wrong_language"
            return None

        def finalize_translation(
            candidate: str, source_sentence: str
        ) -> tuple[str, str | None]:
            text = (candidate or "").strip()
            issue = translation_issue(text, source_sentence)
            return (text, None) if not issue else ("", issue)

        def discard_log(validations: list[str]) -> tuple[CardData | None, LogRecord]:
            return None, LogRecord(
                focus=word,
                level=level,
                lifecycle_state="rejected",
                providers=providers_used,
                provider_errors=provider_errors,
                stage_timings=stage_timings,
                event_counts=dict(event_counts),
                validations=validations,
                review_notes=review_notes,
                candidate_preview=candidate_preview,
                quality_scores=quality_scores,
                selection_reasons=selection_reasons,
                status="discarded",
                discard_reason=_infer_discard_reason(validations, provider_errors),
            )

        def request_definition_ai(language: str) -> ProviderResult:
            definition_ai = getattr(providers, "definition_ai", None)
            if callable(definition_ai):
                return definition_ai(word, language, semantic_only=True)
            return providers.definition(
                word,
                run.language,
                allow_ai=True,
                definition_language=language,
            )

        def request_definition_from_context(
            language: str, sentence_value: str
        ) -> ProviderResult:
            definition_from_context = getattr(providers, "definition_from_context", None)
            if callable(definition_from_context):
                return definition_from_context(
                    word,
                    sentence_value,
                    run.language,
                    definition_language=language,
                )
            return request_definition_ai(language)

        sentence = ""
        last_sentence_issue: str | None = None
        valid_sentence_candidates: dict[str, SentenceSelectionCandidate] = {}
        rewrite_seed_candidates: dict[str, SentenceSelectionCandidate] = {}
        best_invalid_sentence_candidate: SentenceSelectionCandidate | None = None

        def remember_valid_sentence_candidate(
            candidate: SentenceSelectionCandidate,
        ) -> None:
            key = candidate.text.casefold()
            existing = valid_sentence_candidates.get(key)
            if existing is None or candidate.selection_score > existing.selection_score:
                valid_sentence_candidates[key] = candidate

        def remember_rewrite_seed(candidate: SentenceSelectionCandidate) -> None:
            key = candidate.text.casefold()
            existing = rewrite_seed_candidates.get(key)
            if existing is None or candidate.selection_score > existing.selection_score:
                rewrite_seed_candidates[key] = candidate

        def remember_invalid_sentence_candidate(
            candidate: SentenceSelectionCandidate,
        ) -> None:
            nonlocal last_sentence_issue, best_invalid_sentence_candidate
            if not candidate.validation_errors:
                return
            if (
                best_invalid_sentence_candidate is None
                or candidate.selection_score
                > best_invalid_sentence_candidate.selection_score
            ):
                best_invalid_sentence_candidate = candidate
                last_sentence_issue = candidate.validation_errors[0]

        def evaluate_sentence_candidate(
            candidate_text: str,
            *,
            provider_name: str,
            source_kind: str,
            seeded_from_tatoeba: bool = False,
            query_mode: str = "",
        ) -> SentenceSelectionCandidate:
            text, errors, core_errors, level_errors = analyze_sentence(candidate_text)
            final_text = text or (candidate_text or "").strip()
            return SentenceSelectionCandidate(
                text=final_text,
                provider_name=provider_name,
                source_kind=source_kind,
                selection_score=_sentence_selection_score(
                    final_text,
                    word,
                    run.language,
                    level,
                    sentence_min_words,
                    sentence_max_words,
                ),
                seeded_from_tatoeba=seeded_from_tatoeba,
                query_mode=query_mode,
                validation_errors=errors,
                core_errors=core_errors,
                level_errors=level_errors,
            )

        def submit_sentence_candidate(
            candidate: SentenceSelectionCandidate,
        ) -> None:
            if not candidate.text:
                remember_invalid_sentence_candidate(candidate)
                return
            if not candidate.validation_errors:
                remember_valid_sentence_candidate(candidate)
                return
            if (
                candidate.source_kind == "tatoeba"
                and candidate.level_errors
                and not candidate.core_errors
            ):
                remember_rewrite_seed(candidate)
            remember_invalid_sentence_candidate(candidate)

        def ranked_sentence_candidates(
            candidates: dict[str, SentenceSelectionCandidate],
        ) -> list[SentenceSelectionCandidate]:
            return sorted(
                candidates.values(),
                key=lambda candidate: candidate.selection_score,
                reverse=True,
            )

        def choose_sentence_candidate() -> SentenceSelectionCandidate | None:
            ranked = ranked_sentence_candidates(valid_sentence_candidates)
            if not ranked:
                return None
            best_tatoeba = next(
                (candidate for candidate in ranked if candidate.source_kind == "tatoeba"),
                None,
            )
            best_other = next(
                (candidate for candidate in ranked if candidate.source_kind != "tatoeba"),
                None,
            )
            if best_tatoeba and best_other:
                if (
                    best_tatoeba.selection_score + TATOEBA_SELECTION_MARGIN
                    >= best_other.selection_score
                ):
                    return best_tatoeba
                return best_other
            return best_tatoeba or best_other or ranked[0]

        def finalize_selected_sentence(
            candidate: SentenceSelectionCandidate,
        ) -> str:
            nonlocal sentence, last_sentence_issue
            sentence = candidate.text
            last_sentence_issue = None
            if candidate.source_kind == "tatoeba":
                count_event("sentence_tatoeba_hit")
            elif candidate.source_kind == "rewrite":
                count_event("sentence_ai_rewrite_hit")
            elif candidate.source_kind == "ai":
                count_event("sentence_ai_generate_hit")
            if candidate.seeded_from_tatoeba:
                count_event("sentence_tatoeba_seeded_hit")
            if candidate.query_mode == "relaxed" and (
                candidate.source_kind == "tatoeba" or candidate.seeded_from_tatoeba
            ):
                count_event("sentence_tatoeba_relaxed_query_hit")
            cache.set("sentences", sentence_cache_key, sentence)
            return sentence

        def is_hard_ai_sentence_error(error: str | None) -> bool:
            text = str(error or "").lower()
            return any(
                token in text
                for token in (
                    "provider_disabled",
                    "http 401",
                    "http 403",
                    "http 429",
                    "missing api_key",
                )
            )

        def build_sentence() -> str:
            nonlocal sentence, last_sentence_issue
            if sentence:
                return sentence
            cached_sentence = cache_get("sentences", sentence_cache_key) or ""
            cached_text, cached_errors, _cached_core, _cached_level = analyze_sentence(
                cached_sentence
            )
            if not cached_errors:
                sentence = cached_text
                last_sentence_issue = None
                return sentence
            last_sentence_issue = cached_errors[0] if cached_errors else None

            sentence_service = self._sentence_generation_service(
                providers,
                strict_quality=strict_quality,
            )
            ai_status = "skipped"
            ai_should_allow_web_fallback = False
            max_sentence_ai_attempts = max(0, int(run.sentence_ai_attempts or 0))
            sentence_attempts = 0
            while sentence_attempts < max_sentence_ai_attempts and allow_ai("sentence"):
                mark_ai("sentence")
                count_event("sentence_ai_generate_attempted")
                ai_result = sentence_service.generate_candidates(
                    focus_word=word,
                    language=run.language,
                    level=level,
                    requested_pos="",
                    requested_sense="",
                    min_words=sentence_min_words,
                    max_words=sentence_max_words,
                )
                ai_status = ai_result.status
                providers_used["sentence_ai_batch"] = ai_result.provider_name
                if ai_result.error:
                    provider_errors["sentence_ai_batch"] = ai_result.error
                if ai_result.status == "malformed":
                    count_event("sentence_ai_malformed_batch")
                elif ai_result.status == "provider_error":
                    count_event("sentence_ai_provider_error")

                for rejected_candidate in ai_result.rejected:
                    for reason_code in rejected_candidate.reason_codes:
                        count_event(reason_code)

                for generated_candidate in ai_result.candidates:
                    submit_sentence_candidate(
                        evaluate_sentence_candidate(
                            generated_candidate.sentence,
                            provider_name=ai_result.provider_name,
                            source_kind="ai",
                        )
                    )

                selected_candidate = choose_sentence_candidate()
                if selected_candidate is not None:
                    return finalize_selected_sentence(selected_candidate)

                if ai_result.status == "provider_error" and is_hard_ai_sentence_error(
                    ai_result.error
                ):
                    last_sentence_issue = "sentence_generation_failed"
                    return sentence

                if (
                    ai_result.status in {"malformed", "low_yield"}
                    or ai_result.candidates
                    or ai_result.status == "provider_error"
                ):
                    ai_should_allow_web_fallback = True
                sentence_attempts += 1

            if ai_should_allow_web_fallback:
                count_event("sentence_ai_low_yield_fallback")
                count_event("sentence_web_salvage_attempted")
                count_event("sentence_tatoeba_attempted")
                sentence_web_candidates = getattr(providers, "sentence_web_candidates", None)
                if callable(sentence_web_candidates):
                    result = sentence_web_candidates(
                        word,
                        run.language,
                        min_words=sentence_min_words,
                        max_words=sentence_max_words,
                    )
                    trace_result("sentence", result, stage_key="sentence_web_ms")
                    for web_candidate in list(getattr(result, "candidates", []) or []):
                        source_kind = (
                            "tatoeba"
                            if getattr(web_candidate, "source", "") == "tatoeba"
                            or web_candidate.provider_name == "tatoeba"
                            else getattr(web_candidate, "source", web_candidate.provider_name)
                        )
                        submit_sentence_candidate(
                            evaluate_sentence_candidate(
                                web_candidate.text,
                                provider_name=web_candidate.provider_name,
                                source_kind=source_kind,
                                query_mode=getattr(web_candidate, "query_mode", ""),
                            )
                        )
                else:
                    result = providers.sentence_web(
                        word,
                        run.language,
                        min_words=sentence_min_words,
                        max_words=sentence_max_words,
                    )
                    trace_result("sentence", result, stage_key="sentence_web_ms")
                    if result.value:
                        source_kind = (
                            "tatoeba"
                            if result.provider_name == "tatoeba"
                            else result.provider_name
                        )
                        submit_sentence_candidate(
                            evaluate_sentence_candidate(
                                result.value or "",
                                provider_name=result.provider_name,
                                source_kind=source_kind,
                            )
                        )

            sentence_rewrite = getattr(providers, "sentence_rewrite", None)
            best_tatoeba_candidate = next(
                (
                    candidate
                    for candidate in ranked_sentence_candidates(valid_sentence_candidates)
                    if candidate.source_kind == "tatoeba"
                ),
                None,
            )
            strong_tatoeba_available = bool(
                best_tatoeba_candidate
                and best_tatoeba_candidate.selection_score >= STRONG_TATOEBA_SELECTION_SCORE
            )
            if strong_tatoeba_available:
                count_event("sentence_ai_skipped_good_tatoeba")
            elif run.sentence_rewrite_from_web and callable(sentence_rewrite):
                rewrite_candidates = ranked_sentence_candidates(rewrite_seed_candidates)[
                    :MAX_TATOEBA_REWRITE_CANDIDATES
                ]
                for rewrite_candidate in rewrite_candidates:
                    if not allow_ai("sentence"):
                        break
                    count_event("sentence_ai_rewrite_attempted")
                    result = sentence_rewrite(
                        rewrite_candidate.text,
                        word,
                        run.language,
                        level=level,
                        min_words=sentence_min_words,
                        max_words=sentence_max_words,
                    )
                    trace_result(
                        "sentence_rewrite",
                        result,
                        ai_field="sentence",
                        stage_key="sentence_rewrite_ms",
                    )
                    submit_sentence_candidate(
                        evaluate_sentence_candidate(
                            result.value or "",
                            provider_name=result.provider_name,
                            source_kind="rewrite",
                            seeded_from_tatoeba=True,
                            query_mode=rewrite_candidate.query_mode,
                        )
                    )

            has_valid_rewrite_candidate = any(
                candidate.source_kind == "rewrite"
                for candidate in valid_sentence_candidates.values()
            )
            sentence_attempts = 0
            max_sentence_ai_attempts = max(0, int(run.sentence_ai_attempts or 0))
            while (
                not strong_tatoeba_available
                and not has_valid_rewrite_candidate
                and sentence_attempts < max_sentence_ai_attempts
                and allow_ai("sentence")
            ):
                count_event("sentence_ai_generate_attempted")
                result = providers.sentence_ai(
                    word,
                    run.language,
                    min_words=sentence_min_words,
                    max_words=sentence_max_words,
                )
                trace_result(
                    "sentence",
                    result,
                    ai_field="sentence",
                    stage_key="sentence_ai_ms",
                )
                generated_candidate = evaluate_sentence_candidate(
                    result.value or "",
                    provider_name=result.provider_name,
                    source_kind="ai",
                )
                submit_sentence_candidate(generated_candidate)
                if not generated_candidate.validation_errors:
                    break
                error_text = (result.error or "").lower()
                if error_text and any(
                    token in error_text
                    for token in (
                        "provider_disabled",
                        "http 401",
                        "http 403",
                        "http 429",
                        "missing api_key",
                    )
                ):
                    break
                sentence_attempts += 1

            selected_candidate = choose_sentence_candidate()
            set_candidate_preview(
                "sentences",
                [candidate.text for candidate in ranked_sentence_candidates(valid_sentence_candidates)],
            )
            if selected_candidate is not None:
                return finalize_selected_sentence(selected_candidate)

            if ai_status in {"malformed", "low_yield"}:
                last_sentence_issue = "sentence_generation_low_yield"

            return sentence

        source_definition_candidates: dict[str, DefinitionSelectionCandidate] = {}
        final_definition_candidates: dict[str, DefinitionSelectionCandidate] = {}
        chosen_definition_candidate: DefinitionSelectionCandidate | None = None
        definition_ambiguity_detected = False

        def remember_source_definition_candidate(
            candidate: DefinitionSelectionCandidate,
        ) -> None:
            key = candidate.text.casefold()
            existing = source_definition_candidates.get(key)
            if existing is None or candidate.selection_score > existing.selection_score:
                source_definition_candidates[key] = candidate

        def remember_final_definition_candidate(
            candidate: DefinitionSelectionCandidate,
        ) -> None:
            key = candidate.text.casefold()
            existing = final_definition_candidates.get(key)
            if existing is None or candidate.selection_score > existing.selection_score:
                final_definition_candidates[key] = candidate

        if run.exclude_closed_class_words and is_closed_class_word(word, run.language):
            cache.set(
                "invalid_focus",
                self._invalid_focus_key(word, run),
                "function_word",
            )
            remember_quality_error("function_word")
            return discard_log(quality_errors)

        if strict_quality:
            if self._lexicon_zipf_fallback_ok(word, run):
                count_event("focus_lexicon_zipf_precheck_hit")
            else:
                word_exists = getattr(providers, "word_exists", None)
                if callable(word_exists):
                    result = word_exists(word, run.language)
                    trace_result("focus_lexicon", result, stage_key="lexicon_ms")
                    lexicon_missing = not result.value and (result.error or "") in {
                        "",
                        "empty result",
                    }
                    if lexicon_missing:
                        if self._lexicon_zipf_fallback_ok(word, run):
                            count_event("focus_lexicon_zipf_fallback_hit")
                        else:
                            cache.set(
                                "invalid_focus",
                                self._invalid_focus_key(word, run),
                                "focus_not_in_lexicon",
                            )
                            remember_quality_error("focus_not_in_lexicon")
                            return discard_log(quality_errors)

        if run.definition_context_first:
            build_sentence()

        definition_lang = "en"
        definition_key = f"{normalized_word}::{definition_lang}::v{cache_version}"
        source_key = f"{normalized_word}::{run.language}::v{cache_version}"
        context_definition_key = _definition_cache_key(
            normalized_word,
            level,
            sentence,
            definition_lang,
            cache_version,
        )
        context_source_key = _definition_cache_key(
            normalized_word,
            level,
            sentence,
            run.language,
            cache_version,
        )

        source_definition = ""
        definition = ""
        source_definition_issue: str | None = None
        final_definition_issue: str | None = None
        pos = ""
        lemma = word
        sense_note = ""
        definition_selection_reason = ""

        def load_cached_definition_candidate(
            key: str,
            expected_language: str,
            *,
            source_kind: str,
        ) -> DefinitionSelectionCandidate | None:
            cached_value = (cache_get("definitions", key) or "").strip()
            if not cached_value:
                return None
            return make_definition_candidate(
                cached_value,
                expected_language,
                provider_name="cache",
                source_kind=source_kind,
            )

        def collect_provider_definition_candidates(
            expected_language: str,
            *,
            stage_key: str,
            field_name: str,
        ) -> list[DefinitionSelectionCandidate]:
            provider_method = getattr(providers, "definition_candidates", None)
            collected: list[DefinitionSelectionCandidate] = []
            if callable(provider_method):
                result = provider_method(
                    word,
                    run.language,
                    allow_ai=allow_ai("definition"),
                    definition_language=expected_language,
                    sentence=sentence or None,
                )
                trace_candidates_result(
                    field_name,
                    result,
                    ai_field="definition",
                    stage_key=stage_key,
                )
                for raw_candidate in list(getattr(result, "candidates", []) or []):
                    candidate = make_definition_candidate(
                        getattr(raw_candidate, "text", ""),
                        expected_language,
                        provider_name=getattr(raw_candidate, "provider_name", result.provider_name),
                        source_kind=str(getattr(raw_candidate, "source", "provider") or "provider"),
                    )
                    if candidate is not None:
                        collected.append(candidate)
                        continue
                    if expected_language != definition_lang:
                        english_candidate = make_definition_candidate(
                            getattr(raw_candidate, "text", ""),
                            definition_lang,
                            provider_name=getattr(raw_candidate, "provider_name", result.provider_name),
                            source_kind="provider_gloss",
                        )
                        if english_candidate is not None:
                            remember_final_definition_candidate(english_candidate)
                return collected

            result = providers.definition(
                word,
                run.language,
                allow_ai=allow_ai("definition"),
                definition_language=expected_language,
            )
            trace_result(
                field_name,
                result,
                ai_field="definition",
                stage_key=stage_key,
            )
            candidate = make_definition_candidate(
                result.value or "",
                expected_language,
                provider_name=result.provider_name,
                source_kind="provider",
            )
            if candidate is None and expected_language != definition_lang:
                english_candidate = make_definition_candidate(
                    result.value or "",
                    definition_lang,
                    provider_name=result.provider_name,
                    source_kind="provider_gloss",
                )
                if english_candidate is not None:
                    remember_final_definition_candidate(english_candidate)
            return [candidate] if candidate is not None else []

        cached_final_candidates = [
            load_cached_definition_candidate(
                context_definition_key,
                definition_lang,
                source_kind="cache_context",
            ),
            load_cached_definition_candidate(
                definition_key,
                definition_lang,
                source_kind="cache_word",
            ),
        ]
        for cached_candidate in cached_final_candidates:
            if cached_candidate is not None:
                remember_final_definition_candidate(cached_candidate)

        cached_source_candidates = [
            load_cached_definition_candidate(
                context_source_key,
                run.language,
                source_kind="cache_context",
            ),
            load_cached_definition_candidate(
                source_key,
                run.language,
                source_kind="cache_word",
            ),
        ]
        for cached_candidate in cached_source_candidates:
            if cached_candidate is not None:
                remember_source_definition_candidate(cached_candidate)

        if run.language == "en":
            if not final_definition_candidates:
                for candidate in collect_provider_definition_candidates(
                    "en",
                    stage_key="definition_source_ms",
                    field_name="definition",
                ):
                    remember_final_definition_candidate(candidate)
        else:
            if not source_definition_candidates and not final_definition_candidates:
                for candidate in collect_provider_definition_candidates(
                    run.language,
                    stage_key="definition_source_ms",
                    field_name="definition_source",
                ):
                    remember_source_definition_candidate(candidate)

            ranked_source_candidates = sorted(
                source_definition_candidates.values(),
                key=lambda item: item.selection_score,
                reverse=True,
            )
            unique_source_bodies = {candidate.body.casefold() for candidate in ranked_source_candidates if candidate.body}
            definition_ambiguity_detected = len(unique_source_bodies) > 1
            if definition_ambiguity_detected:
                count_event("definition_polysemy_detected")
                remember_review_note("definition_polysemy_detected")

            if ranked_source_candidates:
                source_definition = ranked_source_candidates[0].text
                source_definition_issue = None
                if (
                    not definition_ambiguity_detected
                    and should_cache_definition_candidate(ranked_source_candidates[0])
                ):
                    cache.set("definitions", source_key, source_definition)
                    if context_source_key and ranked_source_candidates[0].alignment_score > 0:
                        cache.set("definitions", context_source_key, source_definition)

            if not final_definition_candidates:
                for source_candidate in ranked_source_candidates[: max(1, int(run.definition_candidates_limit or 5))]:
                    result = providers.translation_web(source_candidate.text, run.language, "en")
                    trace_result("definition", result, stage_key="definition_translate_ms")
                    translated_candidate = make_definition_candidate(
                        result.value or "",
                        "en",
                        provider_name=result.provider_name,
                        source_kind=(
                            "translated_context"
                            if source_candidate.alignment_score > 0
                            else "translated_source"
                        ),
                        inherited_alignment=source_candidate.alignment_score,
                        lemma_value=source_candidate.lemma or word,
                        sense_note_value=source_candidate.sense_note,
                    )
                    if translated_candidate is not None:
                        remember_final_definition_candidate(translated_candidate)
                        continue
                    if allow_ai("definition"):
                        result = providers.translation_ai(source_candidate.text, run.language, "en")
                        trace_result(
                            "definition",
                            result,
                            ai_field="definition",
                            stage_key="definition_translate_ms",
                        )
                        translated_candidate = make_definition_candidate(
                            result.value or "",
                            "en",
                            provider_name=result.provider_name,
                            source_kind=(
                                "translated_context"
                                if source_candidate.alignment_score > 0
                                else "translated_source"
                            ),
                            inherited_alignment=source_candidate.alignment_score,
                            lemma_value=source_candidate.lemma or word,
                            sense_note_value=source_candidate.sense_note,
                        )
                        if translated_candidate is not None:
                            remember_final_definition_candidate(translated_candidate)

            if (
                sentence
                and allow_ai("definition")
                and run.definition_context_fallback
                and (not final_definition_candidates or definition_ambiguity_detected)
            ):
                context_ai = request_definition_from_context("en", sentence)
                trace_result(
                    "definition",
                    context_ai,
                    ai_field="definition",
                    stage_key="definition_context_ms",
                )
                context_candidate = make_definition_candidate(
                    context_ai.value or "",
                    "en",
                    provider_name=context_ai.provider_name,
                    source_kind="context",
                )
                if context_candidate is not None:
                    remember_final_definition_candidate(context_candidate)
            if not final_definition_candidates and allow_ai("definition"):
                direct_ai = request_definition_ai("en")
                trace_result(
                    "definition",
                    direct_ai,
                    ai_field="definition",
                    stage_key="definition_context_ms",
                )
                direct_candidate = make_definition_candidate(
                    direct_ai.value or "",
                    "en",
                    provider_name=direct_ai.provider_name,
                    source_kind="ai",
                )
                if direct_candidate is not None:
                    remember_final_definition_candidate(direct_candidate)

        if not final_definition_candidates and sentence and run.language == "en" and allow_ai("definition"):
            context_ai = request_definition_from_context("en", sentence)
            trace_result(
                "definition",
                context_ai,
                ai_field="definition",
                stage_key="definition_context_ms",
            )
            context_candidate = make_definition_candidate(
                context_ai.value or "",
                "en",
                provider_name=context_ai.provider_name,
                source_kind="context",
            )
            if context_candidate is not None:
                remember_final_definition_candidate(context_candidate)

        ranked_final_candidates = sorted(
            final_definition_candidates.values(),
            key=lambda item: item.selection_score,
            reverse=True,
        )
        set_candidate_preview(
            "definitions",
            [candidate.text for candidate in ranked_final_candidates],
        )
        set_candidate_preview(
            "source_definitions",
            [candidate.text for candidate in source_definition_candidates.values()],
        )

        if ranked_final_candidates:
            chosen_definition_candidate = ranked_final_candidates[0]
            definition = chosen_definition_candidate.text
            definition_selection_reason = chosen_definition_candidate.selection_reason
            final_definition_issue = None
            pos = chosen_definition_candidate.pos
            lemma = chosen_definition_candidate.lemma or lemma
            sense_note = chosen_definition_candidate.sense_note
            quality_scores["definition"] = round(chosen_definition_candidate.selection_score, 4)
            selection_reasons["definition"] = definition_selection_reason
            for note in chosen_definition_candidate.review_notes:
                remember_review_note(note)

        if not definition and run.definition_word_fallback:
            fallback_translation_key = f"{normalized_word}::{run.language}->en::v{cache_version}"
            fallback_translation = (
                cache_get("word_translations", fallback_translation_key) or ""
            ).strip()
            if not fallback_translation:
                result = providers.translation_web(word, run.language, "en")
                trace_result("word_translation", result, stage_key="word_translation_ms")
                fallback_translation = (result.value or "").strip()
                if not fallback_translation and allow_ai("translation"):
                    result = providers.translation_ai(word, run.language, "en")
                    trace_result(
                        "word_translation",
                        result,
                        ai_field="translation",
                        stage_key="word_translation_ms",
                    )
                    fallback_translation = (result.value or "").strip()
                if fallback_translation:
                    cache.set(
                        "word_translations", fallback_translation_key, fallback_translation
                    )
            fallback_definition = _definition_from_word_translation(
                fallback_translation,
                pos_hint=pos,
                level=level,
            )
            fallback_candidate = make_definition_candidate(
                fallback_definition,
                "en",
                provider_name="template",
                source_kind="word_fallback",
            )
            if fallback_candidate is not None:
                chosen_definition_candidate = fallback_candidate
                definition = fallback_candidate.text
                pos = fallback_candidate.pos
                definition_selection_reason = fallback_candidate.selection_reason
                quality_scores["definition"] = round(fallback_candidate.selection_score, 4)
                selection_reasons["definition"] = definition_selection_reason
                count_event("definition_word_fallback_hit")
                remember_review_note("definition_word_fallback_used")

        if definition:
            if should_cache_definition_candidate(chosen_definition_candidate):
                cache.set("definitions", definition_key, definition)
                if context_definition_key and chosen_definition_candidate and chosen_definition_candidate.alignment_score > 0:
                    cache.set("definitions", context_definition_key, definition)

        if not definition:
            remember_quality_error(
                final_definition_issue or source_definition_issue or "definition_missing"
            )
            return discard_log(quality_errors)

        sentence = build_sentence()
        if not sentence:
            remember_quality_error(last_sentence_issue or "sentence_missing")
            return discard_log(quality_errors)

        translation = ""
        translation_issue_name: str | None = None
        translation_key = (
            f"{sentence}::{run.language}->{run.target_translation}::v{cache_version}"
        )
        cached_translation = cache_get("translations", translation_key) or ""
        translation, translation_issue_name = finalize_translation(
            cached_translation, sentence
        )
        if not translation:
            result = providers.translation_web(
                sentence, run.language, run.target_translation
            )
            trace_result("translation", result, stage_key="translation_ms")
            translation, translation_issue_name = finalize_translation(
                result.value or "", sentence
            )
            if not translation and allow_ai("translation"):
                result = providers.translation_ai(
                    sentence, run.language, run.target_translation
                )
                trace_result(
                    "translation",
                    result,
                    ai_field="translation",
                    stage_key="translation_ms",
                )
                translation, translation_issue_name = finalize_translation(
                    result.value or "", sentence
                )
            if not translation and run.definition_word_fallback:
                fallback_translation = _translation_from_definition(definition)
                if fallback_translation:
                    translation, translation_issue_name = finalize_translation(
                        fallback_translation,
                        sentence,
                    )
                    if translation:
                        count_event("translation_definition_fallback_hit")
                fallback_translation_key = (
                    f"{normalized_word}::{run.language}->en::v{cache_version}"
                )
                fallback_word_translation = (
                    cache_get("word_translations", fallback_translation_key) or ""
                ).strip()
                if not fallback_word_translation:
                    result = providers.translation_web(word, run.language, "en")
                    trace_result(
                        "word_translation",
                        result,
                        stage_key="word_translation_ms",
                    )
                    fallback_word_translation = (result.value or "").strip()
                    if fallback_word_translation:
                        cache.set(
                            "word_translations",
                            fallback_translation_key,
                            fallback_word_translation,
                        )
                fallback_translation = _translation_from_word(fallback_word_translation)
                if fallback_translation:
                    translation, translation_issue_name = finalize_translation(
                        fallback_translation,
                        sentence,
                    )
                    if translation:
                        count_event("translation_template_fallback_hit")
        if translation:
            cache.set("translations", translation_key, translation)
        else:
            remember_quality_error(translation_issue_name or "translation_missing")
            return discard_log(quality_errors)

        candidate_senses = unique_keep_order(
            [
                source_definition,
                definition,
                *candidate_preview.get("source_definitions", []),
                *candidate_preview.get("definitions", []),
            ]
        )
        lexical_review = LexicalReviewService(providers).review(
            LexicalReviewRequest(
                focus_word=word,
                language=run.language,
                target_translation_language=run.target_translation,
                accepted_sentence=sentence,
                current_definition=definition,
                current_translation=translation,
                source_definition=source_definition,
                candidate_senses=candidate_senses,
                winning_sense=source_definition or None,
                before={
                    "definition": definition,
                    "translation": translation,
                },
                selection_reasons=dict(selection_reasons),
            )
        )
        review_reason_codes = unique_keep_order(list(lexical_review.reason_codes or []))
        selection_reasons.update(dict(lexical_review.selection_reasons or {}))
        if lexical_review.winning_sense and not selection_reasons.get("winning_sense"):
            selection_reasons["winning_sense"] = lexical_review.winning_sense
        set_candidate_preview(
            "lexical_review_losing_senses",
            list(lexical_review.losing_sense_candidates or []),
        )
        if lexical_review.verdict == "correct":
            corrected_definition = (lexical_review.corrected_definition or "").strip()
            corrected_translation = (lexical_review.corrected_translation or "").strip()
            review_before = dict(lexical_review.before or {}) or {
                "definition": definition,
                "translation": translation,
            }
            review_after = dict(lexical_review.after or {})
            if corrected_definition:
                definition = corrected_definition
                review_after.setdefault("definition", corrected_definition)
            if corrected_translation:
                translation = corrected_translation
                review_after.setdefault("translation", corrected_translation)
            review_notes.append("lexical_review_corrected")
        elif lexical_review.verdict == "reject":
            review_notes.append("lexical_review_rejected")
            review_before = dict(lexical_review.before or {}) or {
                "definition": definition,
                "translation": translation,
            }
            review_after = dict(lexical_review.after or {})
            if not review_after:
                review_after = {
                    "definition": definition,
                    "translation": translation,
                }
            if lexical_review.winning_sense:
                review_after.setdefault("winning_sense", lexical_review.winning_sense)
            if lexical_review.losing_sense_candidates:
                review_after.setdefault(
                    "losing_sense_candidates",
                    list(lexical_review.losing_sense_candidates),
                )
            return None, LogRecord(
                focus=word,
                level=level,
                lifecycle_state="rejected",
                providers=providers_used,
                provider_errors=provider_errors,
                stage_timings=stage_timings,
                event_counts=dict(event_counts),
                validations=[],
                review_notes=review_notes,
                reason_codes=review_reason_codes,
                before=review_before,
                after=review_after,
                candidate_preview=candidate_preview,
                quality_scores=quality_scores,
                selection_reasons=selection_reasons,
                status="discarded",
                discard_reason="lexical_review_rejected",
            )
        else:
            review_before = {}
            review_after = {}

        definition_translation_alignment = definition_alignment_score(
            definition,
            definition_lang,
            translation_reference=translation,
        )
        quality_scores["definition_translation_alignment"] = round(
            definition_translation_alignment,
            4,
        )
        if run.language != "en" and definition_translation_alignment < 0.08:
            remember_review_note("definition_low_translation_alignment")

        selected_pos, selected_body = split_definition(
            definition,
            policy=self.definition_policy,
        )
        pos = pos or selected_pos
        if definition_ambiguity_detected and not sense_note:
            sense_note = "Chosen for the example sentence context."
        if not sense_note and chosen_definition_candidate and chosen_definition_candidate.source_kind.startswith("translated"):
            sense_note = "Built from the best source-language sense."
        _short_definition, precise_definition = definition_variants(pos, selected_body)

        ipa = cache.get("ipa", normalized_word)
        if not ipa:
            result = providers.ipa(word, run.language, allow_ai=allow_ai("ipa"))
            trace_result("ipa", result, ai_field="ipa", stage_key="ipa_ms")
            ipa = result.value or ""
            if not ipa:
                ipa = f"/{word}/"
        ipa = _normalize_ipa(ipa)
        if ipa and not _ipa_has_pronunciation(ipa) and allow_ai("ipa"):
            result = providers.phonetic_spelling(ipa, run.language, allow_ai=True)
            trace_result(
                "ipa_pronunciation",
                result,
                ai_field="ipa",
                stage_key="ipa_ms",
            )
            phonetic = _sanitize_phonetic(result.value or "")
            if phonetic:
                ipa = f"{ipa} ({phonetic})"
        cache.set("ipa", normalized_word, ipa)

        card = CardData(
            focus=word,
            index=index if level == 1 else 0,
            ipa=_normalize_ipa(ipa),
            source_definition=source_definition,
            definition=precise_definition or definition,
            sentence=sentence,
            translation=translation,
            translation_language=run.target_translation,
            image="",
            audio="",
            word_audio="",
            sentence_audio="",
            level=level,
            language=run.language,
            lifecycle_state="generated",
        )

        return card, LogRecord(
            focus=word,
            level=level,
            lifecycle_state="generated",
            providers=providers_used,
            provider_errors=provider_errors,
            stage_timings=stage_timings,
            event_counts=dict(event_counts),
            validations=quality_errors,
            review_notes=review_notes,
            reason_codes=review_reason_codes,
            before=review_before,
            after=review_after,
            candidate_preview=candidate_preview,
            quality_scores=quality_scores,
            selection_reasons=selection_reasons,
            status="candidate",
        )

    def _attach_audio_to_card(
        self,
        *,
        card: CardData,
        log_record: LogRecord,
        run: RunConfig,
        cache: CacheManager,
        providers: ProviderManager,
    ) -> tuple[CardData, LogRecord, list[str]]:
        audio_cfg = self.config.get("audio") if isinstance(self.config, dict) else {}
        audio_cfg = audio_cfg if isinstance(audio_cfg, dict) else {}
        audio_enabled = bool(audio_cfg.get("enabled", False))
        audio_output_dir = audio_cfg.get("output_dir", "ankideck_generator/data/audio")
        provider_order = _normalize_provider_order(audio_cfg.get("provider_order"))
        if not provider_order:
            provider_order = ["gtts", "responsivevoice", "pyttsx3"]
        filename_style = (
            str(audio_cfg.get("filename_style", "slug_hash")).strip() or "slug_hash"
        )
        filename_slug_words = int(audio_cfg.get("filename_slug_words", 4) or 4)
        language_overrides = audio_cfg.get("language_overrides") or {}
        lang_override = (
            language_overrides.get(run.language, {})
            if isinstance(language_overrides, dict)
            else {}
        )
        voice_override = None
        if isinstance(lang_override, dict):
            override_order = _normalize_provider_order(
                lang_override.get("provider_order")
            )
            if override_order:
                provider_order = override_order
            voice_override = lang_override.get("voice")
        providers_cfg = (
            self.config.get("providers", {}) if isinstance(self.config, dict) else {}
        )
        azure_cfg = (
            providers_cfg.get("azure_tts", {})
            if isinstance(providers_cfg, dict)
            else {}
        )
        azure_voice_map = azure_cfg.get("voice_map") or {}
        azure_voice = (
            voice_override
            or azure_voice_map.get(run.language)
            or azure_cfg.get("voice")
        )
        eleven_cfg = (
            providers_cfg.get("elevenlabs", {})
            if isinstance(providers_cfg, dict)
            else {}
        )
        voice_gender_preference = eleven_cfg.get("voice_gender_preference") or "male"
        voice_key = _audio_voice_key(
            str(
                azure_voice
                or eleven_cfg.get("voice_id")
                or eleven_cfg.get("voice_name")
                or voice_gender_preference
                or "default"
            )
        )
        use_legacy_cache = bool(audio_cfg.get("use_legacy_cache", False))
        media_files: list[str] = []

        def trace_result(field: str, result: ProviderResult) -> None:
            log_record.providers[field] = result.provider_name
            if result.error:
                log_record.provider_errors[field] = result.error
            fallback_errors = getattr(result, "fallback_errors", None)
            if isinstance(fallback_errors, dict):
                for name, error in fallback_errors.items():
                    if error:
                        log_record.provider_errors[f"{field}:{name}"] = str(error)
            stage_key = "audio_sentence_ms" if field == "sentence_audio" else "audio_word_ms"
            log_record.stage_timings[stage_key] = log_record.stage_timings.get(
                stage_key, 0
            ) + int(getattr(result, "elapsed_ms", 0) or 0)

        def add_media(path: str) -> None:
            if path and path not in media_files:
                media_files.append(path)

        def cached_audio(kind: str, text_value: str) -> ProviderResult | None:
            cache_kind = "audio_files"
            for provider_name in provider_order:
                cache_key = f"{kind}::{text_value}::{provider_name}::{voice_key}"
                cached = cache.get(cache_kind, cache_key)
                if cached and Path(cached).exists():
                    add_media(cached)
                    return ProviderResult(
                        value=cached,
                        provider_name=provider_name,
                        elapsed_ms=0,
                        error=None,
                    )
            if use_legacy_cache:
                legacy_key = f"{kind}::{text_value}"
                cached = cache.get(cache_kind, legacy_key)
                if cached and Path(cached).exists():
                    add_media(cached)
                    return ProviderResult(
                        value=cached,
                        provider_name="cache",
                        elapsed_ms=0,
                        error=None,
                    )
            return None

        def audio_for(kind: str, text_value: str) -> tuple[str, ProviderResult | None]:
            if not audio_enabled or not text_value:
                return "", None
            cached = cached_audio(kind, text_value)
            if cached and cached.value:
                return _sound_tag(cached.value), cached
            if filename_style == "slug_hash":
                filename_hint = compact_audio_basename(
                    run.language,
                    kind,
                    text_value,
                    slug_words=filename_slug_words,
                    extra=voice_key,
                )
            else:
                filename_hint = f"{run.language}_{kind}_{text_value}_{voice_key}"
            result = providers.audio(
                text_value,
                run.language,
                audio_output_dir,
                filename_hint,
                provider_order=provider_order,
                voice=azure_voice,
                voice_gender_preference=voice_gender_preference,
            )
            provider_name = getattr(result, "provider_name", "unknown")
            value = getattr(result, "value", None)
            error = getattr(result, "error", None)
            elapsed_ms = getattr(result, "elapsed_ms", 0)
            if value and Path(value).exists():
                cache_key = f"{kind}::{text_value}::{provider_name}::{voice_key}"
                cache.set("audio_files", cache_key, value)
                add_media(value)
                return _sound_tag(value), result
            if value and not Path(value).exists():
                result = ProviderResult(
                    value=None,
                    provider_name=provider_name,
                    elapsed_ms=elapsed_ms,
                    error=error or "audio_file_missing",
                )
            return "", result

        if not audio_enabled:
            return card, log_record, media_files
        if not run.generate_audio:
            return card, log_record, media_files

        word_audio, result = audio_for("word", card.focus)
        if result:
            trace_result("word_audio", result)
        sentence_audio = ""
        if card.sentence:
            sentence_audio, result = audio_for("sentence", card.sentence)
            if result:
                trace_result("sentence_audio", result)

        card.word_audio = word_audio
        card.sentence_audio = sentence_audio
        card.audio = word_audio or sentence_audio
        return card, log_record, media_files

    def _validate_text_candidate(
        self,
        card: CardData,
        ctx: ValidationContext,
        run: RunConfig,
        reserved_focus: set[str] | None = None,
        reserved_sentences: set[str] | None = None,
    ) -> list[str]:
        temp_ctx = ValidationContext(
            seen_focus=set(ctx.seen_focus),
            seen_sentence=set(ctx.seen_sentence),
        )
        if reserved_focus:
            temp_ctx.seen_focus.update(reserved_focus)
        if reserved_sentences:
            temp_ctx.seen_sentence.update(reserved_sentences)
        validations = _validations_for_language(
            run.language,
            audio_required=False,
            strict_quality=bool(run.strict_quality),
            level_validation_mode=run.level_validation_mode,
        )
        return validate_card(card, temp_ctx, validations, commit=False)

    def _audio_validation_errors(self, card: CardData, run: RunConfig) -> list[str]:
        if not run.generate_audio:
            return []
        audio_cfg = self.config.get("audio") if isinstance(self.config, dict) else {}
        audio_cfg = audio_cfg if isinstance(audio_cfg, dict) else {}
        if not bool(audio_cfg.get("enabled", False)):
            return []
        if not bool(audio_cfg.get("required", False)):
            return []
        errors: list[str] = []
        if not card.word_audio:
            errors.append("word_audio_missing")
        if not card.sentence_audio:
            errors.append("sentence_audio_missing")
        return errors

    def _error_policy(self, run: RunConfig) -> tuple[set[str], set[str], int]:
        runtime_cfg = self.config.get("runtime", {}) if isinstance(self.config, dict) else {}
        policy_cfg = runtime_cfg.get("error_policy", {}) if isinstance(runtime_cfg, dict) else {}
        mode_policy = policy_cfg.get(run.mode, {}) if isinstance(policy_cfg, dict) else {}

        hard = set(DEFAULT_HARD_VALIDATION_ERRORS)
        soft = set(DEFAULT_SOFT_VALIDATION_ERRORS)
        max_soft_errors = 999 if run.mode == "test" else 1

        if run.mode == "test" and bool(runtime_cfg.get("test_accept_all", False)):
            soft.update(TEST_ACCEPT_ALL_SOFT_ERRORS)
            max_soft_errors = 999

        if isinstance(mode_policy, dict):
            configured_hard = mode_policy.get("hard")
            if isinstance(configured_hard, list) and configured_hard:
                hard = {str(item).strip() for item in configured_hard if str(item).strip()}
            configured_soft = mode_policy.get("soft")
            if isinstance(configured_soft, list) and configured_soft:
                soft = {str(item).strip() for item in configured_soft if str(item).strip()}
            configured_max_soft = mode_policy.get("max_soft_errors")
            if configured_max_soft is not None:
                max_soft_errors = max(0, int(configured_max_soft))

        return hard, soft, max_soft_errors

    def _should_reject_errors(self, errors: list[str], run: RunConfig) -> bool:
        if not errors:
            return False
        hard_errors, soft_errors, max_soft_errors = self._error_policy(run)
        unknown_errors = [error for error in errors if error not in hard_errors and error not in soft_errors]
        if unknown_errors:
            return True
        if any(error in hard_errors for error in errors):
            return True
        soft_count = sum(1 for error in errors if error in soft_errors)
        return soft_count > max_soft_errors

    def _print_summary(
        self,
        accepted_by_level: Counter[int],
        attempted_by_level: Counter[int],
        validation_counter: Counter[str],
        provider_counter: Counter[str],
        event_counter: Counter[str],
        event_counter_by_level: dict[int, Counter[str]],
        stage_counter: Counter[str],
        stage_samples: Counter[str],
        stage_counter_by_level: dict[int, Counter[str]],
        stage_samples_by_level: dict[int, Counter[str]],
        discard_counter: Counter[str],
        discard_by_level: dict[int, Counter[str]],
    ) -> None:
        print("\nRun summary:")
        for level in sorted(attempted_by_level.keys() | accepted_by_level.keys()):
            attempted = attempted_by_level.get(level, 0)
            accepted = accepted_by_level.get(level, 0)
            rate = (accepted / attempted * 100.0) if attempted else 0.0
            print(f"- Level {level}: accepted {accepted}/{attempted} ({rate:.1f}%)")
        top_validations = validation_counter.most_common(5)
        if top_validations:
            print("- Top validation errors:")
            for name, count in top_validations:
                print(f"  {name}: {count}")
        top_discards = discard_counter.most_common(6)
        if top_discards:
            print("- Top discard reasons:")
            for name, count in top_discards:
                print(f"  {name}: {count}")
            for level in sorted(discard_by_level.keys()):
                level_discards = discard_by_level.get(level, Counter())
                if not level_discards:
                    continue
                summary = ", ".join(
                    f"{name}={count}" for name, count in level_discards.most_common(4)
                )
                print(f"  level{level}: {summary}")
        sentence_event_keys = [
            "sentence_tatoeba_attempted",
            "sentence_tatoeba_hit",
            "sentence_tatoeba_seeded_hit",
            "sentence_tatoeba_relaxed_query_hit",
            "sentence_ai_rewrite_attempted",
            "sentence_ai_rewrite_hit",
            "sentence_ai_generate_attempted",
            "sentence_ai_generate_hit",
            "sentence_ai_skipped_good_tatoeba",
        ]
        sentence_events = [
            (name, event_counter.get(name, 0))
            for name in sentence_event_keys
            if event_counter.get(name, 0)
        ]
        if sentence_events:
            print("- Sentence source stats:")
            for name, count in sentence_events:
                print(f"  {name}: {count}")
            attempts = event_counter.get("sentence_tatoeba_attempted", 0)
            tatoeba_hits = event_counter.get("sentence_tatoeba_hit", 0)
            tatoeba_seeded_hits = event_counter.get("sentence_tatoeba_seeded_hit", 0)
            rewrite_hits = event_counter.get("sentence_ai_rewrite_hit", 0)
            ai_hits = event_counter.get("sentence_ai_generate_hit", 0)
            total_hits = tatoeba_hits + rewrite_hits + ai_hits
            if attempts:
                print(f"  tatoeba_hit_rate: {tatoeba_hits / attempts * 100.0:.1f}%")
                print(
                    "  tatoeba_effective_rate: "
                    f"{(tatoeba_hits + tatoeba_seeded_hits) / attempts * 100.0:.1f}%"
                )
                print(
                    f"  sentence_reject_rate: {max(0, attempts - total_hits) / attempts * 100.0:.1f}%"
                )
            if total_hits:
                print(
                    "  source_mix: "
                    f"tatoeba={tatoeba_hits / total_hits * 100.0:.1f}%, "
                    f"rewrite={rewrite_hits / total_hits * 100.0:.1f}%, "
                    f"ai={ai_hits / total_hits * 100.0:.1f}%"
                )
                print(
                    "  tatoeba_seeded_share: "
                    f"{(tatoeba_hits + tatoeba_seeded_hits) / total_hits * 100.0:.1f}%"
                )
            for level in sorted(event_counter_by_level.keys()):
                level_events = event_counter_by_level.get(level, Counter())
                level_total_hits = (
                    level_events.get("sentence_tatoeba_hit", 0)
                    + level_events.get("sentence_ai_rewrite_hit", 0)
                    + level_events.get("sentence_ai_generate_hit", 0)
                )
                if not level_total_hits:
                    continue
                print(
                    f"  level{level}_source_mix: "
                    f"tatoeba={level_events.get('sentence_tatoeba_hit', 0) / level_total_hits * 100.0:.1f}%, "
                    f"rewrite={level_events.get('sentence_ai_rewrite_hit', 0) / level_total_hits * 100.0:.1f}%, "
                    f"ai={level_events.get('sentence_ai_generate_hit', 0) / level_total_hits * 100.0:.1f}%"
                )
        top_providers = provider_counter.most_common(8)
        if top_providers:
            print("- Provider hit-rate:")
            for name, count in top_providers:
                print(f"  {name}: {count}")
        ordered_stage_keys = [
            "lexicon_ms",
            "sentence_web_ms",
            "sentence_rewrite_ms",
            "sentence_ai_ms",
            "definition_source_ms",
            "definition_translate_ms",
            "definition_context_ms",
            "word_translation_ms",
            "translation_ms",
            "ipa_ms",
            "audio_word_ms",
            "audio_sentence_ms",
        ]
        available_stage_keys = [key for key in ordered_stage_keys if stage_samples.get(key)]
        if available_stage_keys:
            print("- Stage timings:")
            for key in available_stage_keys:
                total_ms = stage_counter.get(key, 0)
                samples = stage_samples.get(key, 0)
                avg_ms = (total_ms / samples) if samples else 0.0
                print(f"  {key}: total {total_ms} ms, avg {avg_ms:.1f} ms")
            for level in sorted(stage_samples_by_level.keys()):
                level_samples = stage_samples_by_level.get(level, Counter())
                level_totals = stage_counter_by_level.get(level, Counter())
                if not level_samples:
                    continue
                for key in available_stage_keys:
                    samples = level_samples.get(key, 0)
                    if not samples:
                        continue
                    total_ms = level_totals.get(key, 0)
                    avg_ms = total_ms / samples
                    print(
                        f"  level{level}_{key}: total {total_ms} ms, avg {avg_ms:.1f} ms"
                    )

    def _write_quality_outputs(self, run: RunConfig, stats: BuildStats) -> None:
        average_definition_score = 0.0
        if stats.definition_score_samples:
            average_definition_score = (
                stats.definition_score_total / stats.definition_score_samples
            )
        sentence_attempts = stats.event_counter.get("sentence_tatoeba_attempted", 0)
        sentence_tatoeba_hits = stats.event_counter.get("sentence_tatoeba_hit", 0)
        sentence_tatoeba_seeded_hits = stats.event_counter.get("sentence_tatoeba_seeded_hit", 0)
        sentence_rewrite_hits = stats.event_counter.get("sentence_ai_rewrite_hit", 0)
        sentence_ai_hits = stats.event_counter.get("sentence_ai_generate_hit", 0)
        sentence_total_hits = sentence_tatoeba_hits + sentence_rewrite_hits + sentence_ai_hits
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "language": run.language,
            "mode": run.mode,
            "cards": len(stats.cards),
            "attempted_by_level": dict(stats.attempted_by_level),
            "accepted_by_level": dict(stats.accepted_by_level),
            "discard_reasons": dict(stats.discard_counter),
            "top_validation_errors": dict(stats.validation_counter.most_common(10)),
            "definition_sources": dict(stats.definition_source_counter),
            "ambiguous_focuses": dict(stats.ambiguous_focus_counter.most_common(20)),
            "needs_review": len(stats.needs_review_items),
            "accepted_with_corrections": stats.corrected_accepted_count,
            "definition_score": {
                "average": round(average_definition_score, 4),
                "samples": stats.definition_score_samples,
            },
            "provider_counter": dict(stats.provider_counter),
            "provider_success_counter": dict(stats.provider_success_counter),
            "provider_error_counter": dict(stats.provider_error_counter),
            "event_counter": dict(stats.event_counter),
            "sentence_source_stats": {
                "attempted": sentence_attempts,
                "tatoeba_hits": sentence_tatoeba_hits,
                "tatoeba_seeded_hits": sentence_tatoeba_seeded_hits,
                "rewrite_hits": sentence_rewrite_hits,
                "ai_hits": sentence_ai_hits,
                "tatoeba_hit_rate": round(
                    sentence_tatoeba_hits / sentence_attempts, 4
                )
                if sentence_attempts
                else 0.0,
                "tatoeba_effective_rate": round(
                    (sentence_tatoeba_hits + sentence_tatoeba_seeded_hits)
                    / sentence_attempts,
                    4,
                )
                if sentence_attempts
                else 0.0,
                "source_mix": {
                    "tatoeba": round(sentence_tatoeba_hits / sentence_total_hits, 4)
                    if sentence_total_hits
                    else 0.0,
                    "rewrite": round(sentence_rewrite_hits / sentence_total_hits, 4)
                    if sentence_total_hits
                    else 0.0,
                    "ai": round(sentence_ai_hits / sentence_total_hits, 4)
                    if sentence_total_hits
                    else 0.0,
                },
            },
        }
        ensure_dir(Path(run.quality_report_path).parent)
        atomic_write_json(run.quality_report_path, report)
        ensure_dir(Path(run.review_queue_path).parent)
        atomic_write_json(run.review_queue_path, stats.needs_review_items)

    def _interactive_edit(self, card: CardData, log_record: LogRecord) -> CardData:
        print("\n--- Review Card ---")
        print(card.model_dump())
        definition_options = list((log_record.candidate_preview or {}).get("definitions", []))
        sentence_options = list((log_record.candidate_preview or {}).get("sentences", []))
        if definition_options:
            print("Definition options:")
            for index, value in enumerate(definition_options, start=1):
                print(f"  {index}. {value}")
        if sentence_options:
            print("Sentence options:")
            for index, value in enumerate(sentence_options, start=1):
                print(f"  {index}. {value}")
        if log_record.selection_reasons:
            print(f"Selection reasons: {log_record.selection_reasons}")
        if log_record.review_notes:
            print(f"Review notes: {', '.join(log_record.review_notes)}")

        def apply_definition_choice(value: str) -> None:
            card.definition = value

        while True:
            choice = input(
                "Accept (a), choose definition (d), choose sentence (n), edit field (e), or skip (s)? "
            ).strip().lower()
            if choice == "a":
                return card
            if choice == "s":
                raise ValueError("card skipped")
            if choice == "d":
                selected = input("Definition option number: ").strip()
                if selected.isdigit():
                    index = int(selected) - 1
                    if 0 <= index < len(definition_options):
                        apply_definition_choice(definition_options[index])
                continue
            if choice == "n":
                selected = input("Sentence option number: ").strip()
                if selected.isdigit():
                    index = int(selected) - 1
                    if 0 <= index < len(sentence_options):
                        card.sentence = sentence_options[index]
                continue
            if choice == "e":
                field = input(
                    "Field to edit (focus, definition, sentence, translation, ipa, image, spellings, example_word, word_translation, letter_audio, word_audio, sentence_audio): "
                ).strip()
                if hasattr(card, field):
                    value = input("New value: ")
                    setattr(card, field, value)
                else:
                    print("Unknown field")
                continue

    def _cleanup_run_artifacts(
        self,
        run: RunConfig,
        *,
        cleanup_audio: bool,
        audio_dir: str | Path,
        media_files: list[str],
    ) -> None:
        runtime_cfg = self.config.get("runtime", {}) if isinstance(self.config, dict) else {}
        if not bool(runtime_cfg.get("cleanup_generated_artifacts", False)):
            return
        if cleanup_audio:
            self._cleanup_audio_files(media_files, audio_dir)
        self._cleanup_generated_directory(run.cache_path)
        self._cleanup_generated_directory("ankideck_generator/data/progress")
        if self._last_run_log_path:
            self._cleanup_generated_directory(Path(self._last_run_log_path).parent)
            self._last_run_log_path = None

    def _cleanup_generated_directory(self, target: str | Path) -> None:
        path = Path(target)
        if not path.exists():
            return
        try:
            resolved = path.resolve()
        except OSError:
            return
        if not self._is_safe_cleanup_target(resolved):
            return
        shutil.rmtree(resolved, ignore_errors=True)

    def _is_safe_cleanup_target(self, path: Path) -> bool:
        allowed_roots: list[Path] = []
        for candidate in (Path.cwd(), Path(self.config_path).resolve().parent):
            try:
                resolved_root = candidate.resolve()
            except OSError:
                continue
            if resolved_root not in allowed_roots:
                allowed_roots.append(resolved_root)
        for root in allowed_roots:
            if path == root:
                return False
            try:
                path.relative_to(root)
            except ValueError:
                continue
            return True
        return False

    def _cleanup_audio_files(
        self, media_files: list[str], audio_dir: str | Path
    ) -> None:
        _ = media_files
        self._cleanup_generated_directory(audio_dir)


def _normalize_ipa(value: str) -> str:
    if not value:
        return ""
    text = value.strip()
    match = re.search(r"(/[^/]+/)(?:\s*\(([^()]+)\))?", text)
    if match:
        ipa = match.group(1)
        suffix = match.group(2)
        if suffix:
            return f"{ipa} ({suffix.strip()})"
        return ipa
    if text.startswith("/") and text.endswith("/"):
        return text
    return f"/{text}/"


def _ipa_has_pronunciation(value: str) -> bool:
    return bool(re.search(r"/[^/]+/\s*\([^()]+\)", value or ""))


def _sanitize_phonetic(value: str) -> str:
    if not value:
        return ""
    text = value.strip().strip('"').strip("'")
    text = re.sub(r"/[^/]+/", "", text).strip()
    text = text.replace("(", "").replace(")", "").strip()
    text = re.sub(r"\s+", " ", text)
    return text


def _definition_context_signature(sentence: str) -> str:
    normalized = re.sub(r"\s+", " ", (sentence or "").strip().lower())
    if not normalized:
        return ""
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:10]


def _definition_cache_key(
    word: str,
    level: int,
    sentence: str,
    target_language: str,
    cache_version: int,
) -> str:
    signature = _definition_context_signature(sentence)
    if not signature:
        return ""
    return f"{word}::lvl{level}::{signature}::{target_language}::v{cache_version}"


def _definition_from_word_translation(
    value: str,
    *,
    pos_hint: str = "",
    level: int = 1,
) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    cleaned = re.sub(r"[^A-Za-z0-9\s'\-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    tokens = cleaned.split()
    phrase = " ".join(tokens[:8]).strip()
    if not phrase:
        return ""
    pos_label = (pos_hint or "noun").strip().lower() or "noun"
    if pos_label in {"verb", "auxiliary verb"}:
        body = f"to use or express {phrase}"
    elif pos_label == "adjective":
        body = f"having a quality related to {phrase}"
    elif pos_label == "adverb":
        body = f"in a way related to {phrase}"
    elif pos_label == "expression":
        body = f"expression related to {phrase}"
    else:
        prefix = "basic idea" if int(level or 1) == 1 else "concept"
        body = f"{prefix} related to {phrase}"
    return build_definition(pos_label, body)


def _translation_from_word(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", (value or "").strip())
    cleaned = re.sub(r"[^A-Za-z0-9\s'\-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    tokens = cleaned.split()
    phrase = " ".join(tokens[:8]).strip()
    if not phrase:
        return ""
    return f"This sentence uses the word {phrase}."


def _translation_from_definition(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    _pos_label, cleaned = split_definition(text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    cleaned = re.sub(r"[^A-Za-z0-9\s'\-]", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return ""
    return f"This sentence uses a word that means {cleaned}."


def _normalize_provider_order(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _audio_voice_key(value: str) -> str:
    cleaned = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in value
    )
    return cleaned[:80] if cleaned else "default"


def _sound_tag(path: str) -> str:
    return f"[sound:{Path(path).name}]"


def _infer_discard_reason(
    errors: list[str], provider_errors: dict[str, str]
) -> str | None:
    error_set = set(errors)
    if "focus_not_in_lexicon" in error_set:
        return "focus_not_in_lexicon"
    if "function_word" in error_set:
        return "function_word"
    if "definition_missing" in error_set:
        return "definition_generation_failed"
    if "definition_missing_pos" in error_set:
        return "definition_missing_pos"
    if "definition_nonsemantic" in error_set:
        return "definition_nonsemantic"
    if "definition_wrong_language" in error_set or "source_definition_wrong_language" in error_set:
        return "definition_wrong_language"
    if {
        "sentence_missing",
        "focus_not_in_sentence",
        "example_word_not_in_sentence",
        "sentence_length_invalid",
        "sentence_profile_invalid",
        "sentence_wrong_language",
        "sentence_too_hard_for_level1",
        "sentence_not_level2",
        "sentence_too_easy_for_level3",
    }.intersection(error_set):
        return "sentence_generation_failed"
    if {
        "translation_missing",
        "translation_wrong_language",
        "translation_same_as_source",
    }.intersection(error_set):
        return "translation_generation_failed"
    if {"ipa_missing", "invalid_ipa"}.intersection(error_set):
        return "ipa_generation_failed"
    if {"letter_audio_missing", "word_audio_missing", "sentence_audio_missing"}.intersection(
        error_set
    ):
        return "audio_generation_failed"
    if "definition" in provider_errors or "definition_source" in provider_errors:
        return "definition_generation_failed"
    if "sentence" in provider_errors or "sentence_rewrite" in provider_errors:
        return "sentence_generation_failed"
    if "translation" in provider_errors or "word_translation" in provider_errors:
        return "translation_generation_failed"
    if "ipa" in provider_errors:
        return "ipa_generation_failed"
    if "letter_audio" in provider_errors or "word_audio" in provider_errors or "sentence_audio" in provider_errors:
        return "audio_generation_failed"
    return None


def _sentence_length_bounds(
    length_config: object, level: int, default: tuple[int, int] = (2, 15)
) -> tuple[int, int]:
    if isinstance(length_config, dict):
        value = length_config.get(level)
        if isinstance(value, (list, tuple)) and len(value) == 2:
            min_len, max_len = int(value[0]), int(value[1])
            return max(5, min_len), max(max_len, max(5, min_len))
    if isinstance(length_config, (list, tuple)) and len(length_config) == 2:
        min_len, max_len = int(length_config[0]), int(length_config[1])
        return max(5, min_len), max(max_len, max(5, min_len))
    min_len, max_len = default
    return max(5, min_len), max(max_len, max(5, min_len))


def _validations_for_language(
    language: str,
    audio_required: bool = False,
    strict_quality: bool = True,
    level_validation_mode: str = "profile_hard_zipf_soft",
) -> dict[str, object]:
    _ = language
    validations = dict(DEFAULT_VALIDATIONS)
    validations["level_validation_mode"] = level_validation_mode
    if not strict_quality:
        validations["definition_semantic"] = False
        validations["definition_requires_pos"] = False
        validations["definition_matches_translation_language"] = False
        validations["source_definition_matches_language"] = False
        validations["sentence_matches_language"] = False
    if audio_required:
        validations["word_audio_required"] = True
        validations["sentence_audio_required"] = True
    return validations
