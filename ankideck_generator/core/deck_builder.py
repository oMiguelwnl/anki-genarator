from __future__ import annotations

from collections import Counter
import json
import random
from datetime import datetime
import re
from pathlib import Path

import genanki
from tqdm import tqdm

from ..utils.config import load_config
from ..utils.file_utils import atomic_write_json, ensure_dir, read_json
from ..utils.definition_tools import normalize_definition
from ..utils.language_tools import filter_frequent_words, sentence_is_acceptable, unique_keep_order
from ..utils.logger import JsonLogger
from .cache_manager import CacheManager
from .models import ANKI_FIELD_ORDER_DEFAULT, ANKI_FIELD_ORDER_RU, CardData, LogRecord, ProgressState, RunConfig
from .providers import ProviderManager
from .validators import ValidationContext, validate_card

try:
    from wordfreq import top_n_list
except Exception as exc:  # pragma: no cover - optional
    raise RuntimeError("wordfreq is required") from exc

DEFAULT_VALIDATIONS = {
    "definition_required": True,
    "ipa_required": True,
    "translation_required": True,
    "no_duplicate_focus": True,
    "no_duplicate_sentences": True,
    "focus_in_sentence": True,
    "valid_characters": True,
    "ipa_format": True,
    "audio_generated": False,
    "definition_not_literal_translation": True,
    "sentence_length": (5, 25),
    "sentence_difficulty_matches_level": False,
    "ai_quality_check": False,
}

RUSSIAN_VALIDATIONS = {
    "definition_required": False,
    "ipa_required": True,
    "translation_required": True,
    "spellings_required": True,
    "example_word_required": True,
    "word_translation_required": True,
    "letter_audio_required": True,
    "no_duplicate_focus": True,
    "no_duplicate_sentences": True,
    "focus_in_sentence": False,
    "example_word_in_sentence": True,
    "valid_characters": False,
    "ipa_format": True,
    "audio_generated": False,
    "definition_not_literal_translation": False,
    "sentence_length": (5, 25),
    "sentence_difficulty_matches_level": False,
    "ai_quality_check": False,
}


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

    def preflight(self, run: RunConfig) -> tuple[bool, str]:
        providers = ProviderManager(self.config, run.timeout_sec, run.retries)
        return providers.validate_ai_ready()

    def build(self, run: RunConfig) -> tuple[list[CardData], list[str]]:
        if run.language == "ru":
            return self._build_russian(run)
        provider_manager = ProviderManager(self.config, run.timeout_sec, run.retries)
        cache_manager = CacheManager(run.cache_path, run.language, run.autosave_every)
        progress_store = ProgressStore("ankideck_generator/data/progress")
        log_path = f"ankideck_generator/data/logs/run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jsonl"
        logger = JsonLogger(log_path)
        ctx = ValidationContext()

        level_size = run.level_size
        wordfreq_lang = run.wordfreq_language or run.language
        level_sets = self._prepare_levels(wordfreq_lang, level_size, run.seed, run.level_pool_multiplier)

        state = None
        if run.resume:
            state = progress_store.load(run.language, run.mode)
        processed_focus = set(state.processed_focus) if state else set()
        processed_sentences = set(state.processed_sentences) if state else set()
        next_sort_index = (state.created_cards + 1) if state and state.created_cards else 1
        ctx.seen_focus.update(processed_focus)
        ctx.seen_sentence.update(processed_sentences)

        cards: list[CardData] = []
        media_files: list[str] = []
        processed = 0
        accepted_by_level: Counter[int] = Counter()
        attempted_by_level: Counter[int] = Counter()
        validation_counter: Counter[str] = Counter()
        provider_counter: Counter[str] = Counter()

        for level, words in level_sets.items():
            accepted_in_level = 0
            level_target = level_size
            for index, word in enumerate(tqdm(words, desc=f"Level {level}", unit="word")):
                if accepted_in_level >= level_target:
                    break
                if word in processed_focus:
                    continue
                attempted_by_level[level] += 1
                try:
                    card, log_record = self._process_word(
                        word=word,
                        level=level,
                        index=index + 1,
                        run=run,
                        cache=cache_manager,
                        providers=provider_manager,
                        ctx=ctx,
                        media_files=media_files,
                    )
                except Exception as exc:  # pragma: no cover - safety net
                    log_record = LogRecord(
                        focus=word,
                        level=level,
                        providers={},
                        provider_errors={},
                        validations=[],
                        status="error",
                        error=str(exc),
                    )
                    card = None

                logger.log(log_record.model_dump())
                for field_name, provider_name in log_record.providers.items():
                    provider_counter[f"{field_name}:{provider_name}"] += 1
                for validation_error in log_record.validations:
                    validation_counter[validation_error] += 1
                if card:
                    card.index = next_sort_index
                    next_sort_index += 1
                    cards.append(card)
                    processed_focus.add(card.focus)
                    processed_sentences.add(card.sentence)
                    accepted_in_level += 1
                    accepted_by_level[level] += 1
                processed += 1

                if processed % run.autosave_every == 0:
                    cache_manager.save_all()
                    progress_store.save(
                        ProgressState(
                            language=run.language,
                            mode=run.mode,
                            level=level,
                            index=index,
                            rng_state=random.getstate(),
                            processed_focus=sorted(processed_focus),
                            processed_sentences=sorted(processed_sentences),
                            created_cards=next_sort_index - 1,
                        )
                    )

        cache_manager.save_all()
        progress_store.save(
            ProgressState(
                language=run.language,
                mode=run.mode,
                level=3,
                index=level_size,
                rng_state=random.getstate(),
                processed_focus=sorted(processed_focus),
                processed_sentences=sorted(processed_sentences),
                created_cards=next_sort_index - 1,
            )
        )
        self._print_summary(accepted_by_level, attempted_by_level, validation_counter, provider_counter)
        return cards, media_files

    def export_deck(self, run: RunConfig, cards: list[CardData], media_files: list[str]) -> None:
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
                    "qfmt": self._resolve_path(deck_cfg.get("front_template")).read_text(encoding="utf-8"),
                    "afmt": self._resolve_path(deck_cfg.get("back_template")).read_text(encoding="utf-8"),
                }
            ],
            css=self._resolve_path(deck_cfg.get("css_path")).read_text(encoding="utf-8"),
        )

        deck = genanki.Deck(deck_cfg.get("deck_id", default_deck_id), deck_cfg.get("name", "Anki Deck Generator"))
        for card in cards:
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

    def _prepare_levels(self, language: str, level_size: int, seed: int, pool_multiplier: int = 8) -> dict[int, list[str]]:
        random.seed(seed)
        pool_multiplier = max(1, int(pool_multiplier))
        target_total = max(level_size * 60, 6000)
        raw_top = top_n_list(language, target_total)
        filtered_top = filter_frequent_words(raw_top, language, min_length=3)
        if len(filtered_top) < level_size:
            raw_top = top_n_list(language, target_total * 2)
            filtered_top = filter_frequent_words(raw_top, language, min_length=3)
        level1_pool_size = min(len(filtered_top), max(level_size * pool_multiplier, level_size))
        level1 = filtered_top[:level1_pool_size]

        pool_raw = top_n_list(language, max(50000, target_total * 3))
        pool_filtered = filter_frequent_words(pool_raw, language, min_length=3)
        pool_filtered = [w for w in pool_filtered if w not in level1]

        level2_candidates = pool_filtered[:25000]
        random.shuffle(level2_candidates)
        level2_pool_size = min(len(level2_candidates), max(level_size * pool_multiplier, level_size))
        level2 = level2_candidates[:level2_pool_size]

        level3_candidates = pool_filtered[25000:50000] if len(pool_filtered) > 50000 else pool_filtered
        random.shuffle(level3_candidates)
        level3_pool_size = min(len(level3_candidates), max(level_size * pool_multiplier, level_size))
        level3 = level3_candidates[:level3_pool_size]

        return {
            1: unique_keep_order(level1),
            2: unique_keep_order(level2),
            3: unique_keep_order(level3),
        }

    def _deck_config_for_language(self, language: str) -> tuple[dict, list[str]]:
        deck_cfg = dict(self.config.get("deck", {}))
        field_order = ANKI_FIELD_ORDER_DEFAULT
        if language == "ru":
            ru_cfg = deck_cfg.get("russian", {})
            merged = dict(deck_cfg)
            if isinstance(ru_cfg, dict):
                for key, value in ru_cfg.items():
                    if value is not None:
                        merged[key] = value
            merged.setdefault("front_template", "ankideck_generator/templates/card_front_ru.html")
            merged.setdefault("back_template", "ankideck_generator/templates/card_back_ru.html")
            merged.setdefault("css_path", "ankideck_generator/templates/styles.css")
            deck_cfg = merged
            field_order = ANKI_FIELD_ORDER_RU
        return deck_cfg, field_order

    def _resolve_path(self, value: str | None) -> Path:
        if not value:
            raise ValueError("Missing template path in config")
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(self.config_path).resolve().parent / path

    def _build_russian(self, run: RunConfig) -> tuple[list[CardData], list[str]]:
        provider_manager = ProviderManager(self.config, run.timeout_sec, run.retries)
        cache_manager = CacheManager(run.cache_path, run.language, run.autosave_every)
        log_path = f"ankideck_generator/data/logs/run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jsonl"
        logger = JsonLogger(log_path)
        ctx = ValidationContext()

        inventory = self._load_russian_inventory(cache_manager, provider_manager, run)
        if run.mode == "test":
            inventory = inventory[: min(run.level_size, len(inventory))]

        cards: list[CardData] = []
        media_files: list[str] = []
        accepted_by_level: Counter[int] = Counter()
        attempted_by_level: Counter[int] = Counter()
        validation_counter: Counter[str] = Counter()
        provider_counter: Counter[str] = Counter()

        for sort_index, entry in enumerate(tqdm(inventory, desc="Russian phonemes", unit="entry"), start=1):
            attempted_by_level[1] += 1
            focus = entry.get("spellings") or entry.get("example_word") or ""
            try:
                card, log_record = self._process_russian_entry(
                    entry=entry,
                    index=sort_index,
                    run=run,
                    cache=cache_manager,
                    providers=provider_manager,
                    ctx=ctx,
                    media_files=media_files,
                )
            except Exception as exc:  # pragma: no cover - safety net
                log_record = LogRecord(
                    focus=focus,
                    level=1,
                    providers={},
                    provider_errors={},
                    validations=[],
                    status="error",
                    error=str(exc),
                )
                card = None

            logger.log(log_record.model_dump())
            for field_name, provider_name in log_record.providers.items():
                provider_counter[f"{field_name}:{provider_name}"] += 1
            for validation_error in log_record.validations:
                validation_counter[validation_error] += 1
            if card:
                card.index = len(cards) + 1
                cards.append(card)
                accepted_by_level[1] += 1

        cache_manager.save_all()
        self._print_summary(accepted_by_level, attempted_by_level, validation_counter, provider_counter)
        return cards, media_files

    def _load_russian_inventory(self, cache: CacheManager, providers: ProviderManager, run: RunConfig) -> list[dict[str, str]]:
        cached = cache.get("russian_inventory", "entries")
        normalized_cached = _normalize_russian_inventory(cached)
        if normalized_cached:
            return normalized_cached

        result = providers.russian_phoneme_inventory(run.language, allow_ai=True)
        raw_value = result.value
        payload: object
        if isinstance(raw_value, str):
            try:
                payload = json.loads(raw_value)
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"Invalid Russian inventory JSON from {result.provider_name}") from exc
        else:
            payload = raw_value
        normalized = _normalize_russian_inventory(payload)
        if not normalized:
            raise RuntimeError(
                f"Could not build Russian phoneme inventory. Provider={result.provider_name}, error={result.error}"
            )
        cache.set("russian_inventory", "entries", normalized)
        return normalized

    def _process_russian_entry(
        self,
        entry: dict[str, str],
        index: int,
        run: RunConfig,
        cache: CacheManager,
        providers: ProviderManager,
        ctx: ValidationContext,
        media_files: list[str],
    ) -> tuple[CardData | None, LogRecord]:
        providers_used: dict[str, str] = {}
        provider_errors: dict[str, str] = {}
        ai_calls_total = 0
        ai_calls_by_field: dict[str, int] = {}

        spellings = str(entry.get("spellings", "")).strip()
        ipa = _normalize_ipa(str(entry.get("ipa", "")).strip())
        example_word = str(entry.get("example_word", "")).strip()

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

        def trace_result(field: str, result, ai_field: str | None = None) -> None:
            providers_used[field] = result.provider_name
            if result.error:
                provider_errors[field] = result.error
            if ai_field and result.provider_name == "ai":
                mark_ai(ai_field)

        word_translation = cache.get("word_translations", example_word) or ""
        if not word_translation:
            result = providers.translation_web(example_word, run.language, run.target_translation)
            trace_result("word_translation", result)
            word_translation = result.value or ""
            if not word_translation and allow_ai("word_translation"):
                result = providers.translation_ai(example_word, run.language, run.target_translation)
                trace_result("word_translation", result, ai_field="word_translation")
                word_translation = result.value or ""
            if word_translation:
                cache.set("word_translations", example_word, word_translation)

        sentence = cache.get("sentences", example_word) or ""
        if sentence and not sentence_is_acceptable(sentence, example_word, 5, 25):
            sentence = ""
        if not sentence:
            sentence_attempts = 0
            while sentence_attempts < 2 and allow_ai("sentence") and not sentence:
                result = providers.sentence_ai(example_word, run.language)
                trace_result("sentence", result, ai_field="sentence")
                candidate = result.value or ""
                if candidate and sentence_is_acceptable(candidate, example_word, 5, 25):
                    sentence = candidate
                    cache.set("sentences", example_word, sentence)
                    break
                sentence_attempts += 1
            if not sentence:
                result = providers.sentence_web(example_word, run.language)
                trace_result("sentence", result)
                candidate = result.value or ""
                if candidate and sentence_is_acceptable(candidate, example_word, 5, 25):
                    sentence = candidate
                    cache.set("sentences", example_word, sentence)

        translation = ""
        if sentence:
            translation_key = f"{example_word}::{sentence}"
            translation = cache.get("translations", translation_key) or ""
            if not translation:
                result = providers.translation_web(sentence, run.language, run.target_translation)
                trace_result("translation", result)
                translation = result.value or ""
                if not translation and allow_ai("translation"):
                    result = providers.translation_ai(sentence, run.language, run.target_translation)
                    trace_result("translation", result, ai_field="translation")
                    translation = result.value or ""
                if translation:
                    cache.set("translations", translation_key, translation)

        letter_audio = self._load_or_generate_audio_tag(
            cache=cache,
            providers=providers,
            media_files=media_files,
            run=run,
            key=f"letter::{spellings}",
            text=spellings,
            filename_hint=f"ru_letter_{index}",
            field="letter_audio",
            providers_used=providers_used,
            provider_errors=provider_errors,
        )
        word_audio = self._load_or_generate_audio_tag(
            cache=cache,
            providers=providers,
            media_files=media_files,
            run=run,
            key=f"word::{example_word}",
            text=example_word,
            filename_hint=f"ru_word_{index}",
            field="word_audio",
            providers_used=providers_used,
            provider_errors=provider_errors,
        )
        sentence_audio = self._load_or_generate_audio_tag(
            cache=cache,
            providers=providers,
            media_files=media_files,
            run=run,
            key=f"sentence::{example_word}",
            text=sentence,
            filename_hint=f"ru_sentence_{index}",
            field="sentence_audio",
            providers_used=providers_used,
            provider_errors=provider_errors,
        )

        card = CardData(
            focus=spellings,
            index=index,
            ipa=ipa,
            definition="",
            sentence=sentence,
            translation=translation,
            translation_language=run.target_translation,
            image="",
            audio="",
            word_audio=word_audio,
            sentence_audio=sentence_audio,
            spellings=spellings,
            example_word=example_word,
            word_translation=word_translation,
            letter_audio=letter_audio,
            level=1,
            language=run.language,
        )

        errors = validate_card(card, ctx, _validations_for_language(run.language))
        if errors:
            discard_reason = _infer_discard_reason(errors, provider_errors)
            return None, LogRecord(
                focus=spellings,
                level=1,
                providers=providers_used,
                provider_errors=provider_errors,
                validations=errors,
                status="discarded",
                discard_reason=discard_reason,
            )

        return card, LogRecord(
            focus=spellings,
            level=1,
            providers=providers_used,
            provider_errors=provider_errors,
            validations=[],
            status="accepted",
        )

    def _load_or_generate_audio_tag(
        self,
        cache: CacheManager,
        providers: ProviderManager,
        media_files: list[str],
        run: RunConfig,
        key: str,
        text: str,
        filename_hint: str,
        field: str,
        providers_used: dict[str, str],
        provider_errors: dict[str, str],
    ) -> str:
        if not text.strip():
            return ""
        cached_path = cache.get("audio_files", key)
        if cached_path and Path(cached_path).exists():
            _append_media_file(media_files, str(cached_path))
            return _to_anki_sound(str(cached_path))

        result = providers.audio(text, run.language, "ankideck_generator/data/audio", filename_hint)
        providers_used[field] = result.provider_name
        if result.error:
            provider_errors[field] = result.error
        if not result.value:
            return ""
        cache.set("audio_files", key, result.value)
        _append_media_file(media_files, result.value)
        return _to_anki_sound(result.value)

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
        providers_used: dict[str, str] = {}
        provider_errors: dict[str, str] = {}
        ai_calls_total = 0
        ai_calls_by_field: dict[str, int] = {}

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

        def trace_result(field: str, result, ai_field: str | None = None) -> None:
            providers_used[field] = result.provider_name
            if result.error:
                provider_errors[field] = result.error
            if ai_field and result.provider_name == "ai":
                mark_ai(ai_field)

        definition_lang = run.language
        definition_key = f"{word}::{definition_lang}"
        definition = cache.get("definitions", definition_key)
        if not definition:
            result = providers.definition(
                word,
                run.language,
                allow_ai=allow_ai("definition"),
                definition_language=definition_lang,
            )
            trace_result("definition", result, ai_field="definition")
            definition = result.value or ""
            definition = normalize_definition(
                definition,
                definition_lang,
                pos_mode="auto",
                min_words=6,
                max_words=10,
            )
            if definition:
                cache.set("definitions", definition_key, definition)

        ipa = cache.get("ipa", word)
        if not ipa:
            result = providers.ipa(word, run.language, allow_ai=allow_ai("ipa"))
            trace_result("ipa", result, ai_field="ipa")
            ipa = result.value or ""
            # Fast fallback to prevent card loss and extra retries.
            if not ipa:
                ipa = f"/{word}/"
            cache.set("ipa", word, ipa)

        sentence = cache.get("sentences", word)
        if sentence and not sentence_is_acceptable(sentence, word, 5, 25):
            sentence = ""
        if not sentence:
            sentence_attempts = 0
            while sentence_attempts < 2 and allow_ai("sentence") and not sentence:
                result = providers.sentence_ai(word, run.language)
                trace_result("sentence", result, ai_field="sentence")
                candidate = result.value or ""
                if candidate and sentence_is_acceptable(candidate, word, 5, 25):
                    sentence = candidate
                    cache.set("sentences", word, sentence)
                    break
                sentence_attempts += 1
            if not sentence:
                result = providers.sentence_web(word, run.language)
                trace_result("sentence", result)
                candidate = result.value or ""
                if candidate and sentence_is_acceptable(candidate, word, 5, 25):
                    sentence = candidate
                    cache.set("sentences", word, sentence)

        translation = ""
        if sentence:
            translation_key = f"{word}::{sentence}"
            translation = cache.get("translations", translation_key)
            if not translation:
                result = providers.translation_web(sentence, run.language, run.target_translation)
                trace_result("translation", result)
                translation = result.value or ""
                if not translation and allow_ai("translation"):
                    result = providers.translation_ai(sentence, run.language, run.target_translation)
                    trace_result("translation", result, ai_field="translation")
                    translation = result.value or ""
                if translation:
                    cache.set("translations", translation_key, translation)

        audio_value = ""

        card = CardData(
            focus=word,
            index=index if level == 1 else 0,
            ipa=_normalize_ipa(ipa),
            definition=definition,
            sentence=sentence,
            translation=translation,
            translation_language=run.target_translation,
            image="",
            audio=audio_value,
            word_audio="",
            sentence_audio="",
            level=level,
            language=run.language,
        )

        errors = validate_card(card, ctx, _validations_for_language(run.language))
        if errors:
            discard_reason = _infer_discard_reason(errors, provider_errors)
            return None, LogRecord(
                focus=word,
                level=level,
                providers=providers_used,
                provider_errors=provider_errors,
                validations=errors,
                status="discarded",
                discard_reason=discard_reason,
            )

        if run.interactive:
            try:
                card = self._interactive_edit(card)
            except ValueError:
                return None, LogRecord(
                    focus=word,
                    level=level,
                    providers=providers_used,
                    provider_errors=provider_errors,
                    validations=["skipped_by_user"],
                    status="skipped",
                )

        return card, LogRecord(
            focus=word,
            level=level,
            providers=providers_used,
            provider_errors=provider_errors,
            validations=[],
            status="accepted",
        )

    def _print_summary(
        self,
        accepted_by_level: Counter[int],
        attempted_by_level: Counter[int],
        validation_counter: Counter[str],
        provider_counter: Counter[str],
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
        top_providers = provider_counter.most_common(8)
        if top_providers:
            print("- Provider hit-rate:")
            for name, count in top_providers:
                print(f"  {name}: {count}")

    def _interactive_edit(self, card: CardData) -> CardData:
        print("\n--- Review Card ---")
        print(card.model_dump())
        while True:
            choice = input("Accept (a), edit field (e), or skip (s)? ").strip().lower()
            if choice == "a":
                return card
            if choice == "s":
                raise ValueError("card skipped")
            if choice == "e":
                field = input(
                    "Field to edit (focus, definition, sentence, translation, ipa, image, "
                    "spellings, example_word, word_translation, letter_audio, word_audio, sentence_audio): "
                ).strip()
                if hasattr(card, field):
                    value = input("New value: ")
                    setattr(card, field, value)
                else:
                    print("Unknown field")


def _normalize_ipa(value: str) -> str:
    if not value:
        return ""
    text = value.strip()
    match = re.search(r"/[^/]+/", text)
    if match:
        return match.group(0)
    if text.startswith("/") and text.endswith("/"):
        return text
    return f"/{text}/"


def _infer_discard_reason(errors: list[str], provider_errors: dict[str, str]) -> str | None:
    sentence_related = {"focus_not_in_sentence", "example_word_not_in_sentence", "sentence_length_invalid"}
    if "sentence" in provider_errors or sentence_related.intersection(errors):
        return "sentence_generation_failed"
    if "translation" in provider_errors or "word_translation" in provider_errors or "translation_missing" in errors:
        return "translation_generation_failed"
    if "definition" in provider_errors or "definition_missing" in errors:
        return "definition_generation_failed"
    if "ipa" in provider_errors or "ipa_missing" in errors:
        return "ipa_generation_failed"
    if "letter_audio" in provider_errors or "word_audio" in provider_errors or "sentence_audio" in provider_errors:
        return "audio_generation_failed"
    return None


def _validations_for_language(language: str) -> dict[str, object]:
    return RUSSIAN_VALIDATIONS if language == "ru" else DEFAULT_VALIDATIONS


def _normalize_russian_inventory(raw_value: object) -> list[dict[str, str]]:
    if not isinstance(raw_value, list):
        return []
    entries: list[dict[str, str]] = []
    seen_keys: set[tuple[str, str]] = set()
    for raw_item in raw_value:
        if not isinstance(raw_item, dict):
            continue
        spellings = str(raw_item.get("spellings", "")).strip()
        ipa = _normalize_ipa(str(raw_item.get("ipa", "")).strip())
        example_word = str(raw_item.get("example_word", "")).strip()
        if not spellings or not ipa or not example_word:
            continue
        if not _contains_cyrillic(spellings) or not _contains_cyrillic(example_word):
            continue
        key = (spellings.casefold(), ipa)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        entries.append(
            {
                "spellings": spellings,
                "ipa": ipa,
                "example_word": example_word,
            }
        )
    return entries


def _contains_cyrillic(text: str) -> bool:
    return bool(re.search(r"[А-Яа-яЁё]", text))


def _to_anki_sound(path: str) -> str:
    return f"[sound:{Path(path).name}]"


def _append_media_file(media_files: list[str], path: str) -> None:
    if path not in media_files:
        media_files.append(path)
