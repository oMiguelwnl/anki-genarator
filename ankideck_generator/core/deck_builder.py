from __future__ import annotations

import random
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import genanki
from tqdm import tqdm

from ..utils.config import load_config
from ..utils.definition_tools import normalize_definition
from ..utils.file_utils import atomic_write_json, ensure_dir, read_json
from ..utils.language_tools import (
    filter_frequent_words,
    sentence_is_acceptable,
    unique_keep_order,
)
from ..utils.logger import JsonLogger
from .cache_manager import CacheManager
from .models import (
    ANKI_FIELD_ORDER_DEFAULT,
    CardData,
    LogRecord,
    ProviderResult,
    ProgressState,
    RunConfig,
)
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
    "word_audio_required": False,
    "sentence_audio_required": False,
    "definition_not_literal_translation": True,
    "sentence_length": {
        1: (5, 10),
        2: (8, 14),
        3: (8, 16),
    },
    "sentence_difficulty_matches_level": True,
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
        provider_manager = ProviderManager(self.config, run.timeout_sec, run.retries)
        cache_manager = CacheManager(run.cache_path, run.language, run.autosave_every)
        progress_store = ProgressStore("ankideck_generator/data/progress")
        log_path = f"ankideck_generator/data/logs/run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jsonl"
        logger = JsonLogger(log_path)
        ctx = ValidationContext()

        level_size = run.level_size
        wordfreq_lang = run.wordfreq_language or run.language
        level_sets = self._prepare_levels(
            wordfreq_lang, level_size, run.seed, run.level_pool_multiplier
        )

        state = None
        if run.resume:
            state = progress_store.load(run.language, run.mode)
        processed_focus = set(state.processed_focus) if state else set()
        processed_sentences = set(state.processed_sentences) if state else set()
        next_sort_index = (
            (state.created_cards + 1) if state and state.created_cards else 1
        )
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
            attempted_in_level = 0
            level_target = level_size
            runtime_cfg = self.config.get("runtime") if isinstance(self.config, dict) else {}
            runtime_cfg = runtime_cfg if isinstance(runtime_cfg, dict) else {}
            test_attempts_cap = bool(runtime_cfg.get("test_attempts_cap", False)) and run.mode == "test"
            attempts_cap = level_target if test_attempts_cap else None
            for index, word in enumerate(
                tqdm(words, desc=f"Level {level}", unit="word")
            ):
                if accepted_in_level >= level_target:
                    break
                if attempts_cap is not None and attempted_in_level >= attempts_cap:
                    break
                if word in processed_focus:
                    continue
                attempted_in_level += 1
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
        self._print_summary(
            accepted_by_level, attempted_by_level, validation_counter, provider_counter
        )
        return cards, media_files

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

        if cleanup_audio:
            self._cleanup_audio_files(media_files, cleanup_dir)

        metadata = {
            "generated_at": datetime.utcnow().isoformat(),
            "language": run.language,
            "mode": run.mode,
            "cards": len(cards),
            "output": run.output_path,
        }
        atomic_write_json("output/metadata.json", metadata)

    def _prepare_levels(
        self, language: str, level_size: int, seed: int, pool_multiplier: int = 8
    ) -> dict[int, list[str]]:
        random.seed(seed)
        pool_multiplier = max(1, int(pool_multiplier))
        target_total = max(level_size * 60, 6000)
        raw_top = top_n_list(language, target_total)
        filtered_top = filter_frequent_words(raw_top, language, min_length=3)
        if len(filtered_top) < level_size:
            raw_top = top_n_list(language, target_total * 2)
            filtered_top = filter_frequent_words(raw_top, language, min_length=3)
        level1_pool_size = min(
            len(filtered_top), max(level_size * pool_multiplier, level_size)
        )
        level1 = filtered_top[:level1_pool_size]

        pool_raw = top_n_list(language, max(50000, target_total * 3))
        pool_filtered = filter_frequent_words(pool_raw, language, min_length=3)
        pool_filtered = [w for w in pool_filtered if w not in level1]

        level2_candidates = pool_filtered[:25000]
        random.shuffle(level2_candidates)
        level2_pool_size = min(
            len(level2_candidates), max(level_size * pool_multiplier, level_size)
        )
        level2 = level2_candidates[:level2_pool_size]

        level3_candidates = (
            pool_filtered[25000:50000] if len(pool_filtered) > 50000 else pool_filtered
        )
        random.shuffle(level3_candidates)
        level3_pool_size = min(
            len(level3_candidates), max(level_size * pool_multiplier, level_size)
        )
        level3 = level3_candidates[:level3_pool_size]

        return {
            1: unique_keep_order(level1),
            2: unique_keep_order(level2),
            3: unique_keep_order(level3),
        }

    def _deck_config_for_language(self, language: str) -> tuple[dict, list[str]]:
        deck_cfg = dict(self.config.get("deck", {}))
        field_order = ANKI_FIELD_ORDER_DEFAULT
        return deck_cfg, field_order

    def _resolve_path(self, value: str | None) -> Path:
        if not value:
            raise ValueError("Missing template path in config")
        path = Path(value)
        if path.is_absolute():
            return path
        return Path(self.config_path).resolve().parent / path

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
            fallback_errors = getattr(result, "fallback_errors", None)
            if isinstance(fallback_errors, dict):
                for name, error in fallback_errors.items():
                    if error:
                        provider_errors[f"{field}:{name}"] = str(error)
            if ai_field and result.provider_name == "ai":
                mark_ai(ai_field)

        definition_lang = "en"
        definition_key = f"{word}::{definition_lang}"
        definition = cache.get("definitions", definition_key)
        if not definition:
            if run.language == "en":
                result = providers.definition(
                    word,
                    run.language,
                    allow_ai=allow_ai("definition"),
                    definition_language="en",
                )
                trace_result("definition", result, ai_field="definition")
                definition = result.value or ""
                definition = normalize_definition(
                    definition,
                    "en",
                    pos_mode="auto",
                    min_words=6,
                    max_words=10,
                )
                if definition:
                    cache.set("definitions", definition_key, definition)
            else:
                source_key = f"{word}::{run.language}"
                source_def = cache.get("definitions", source_key) or ""
                if not source_def:
                    result = providers.definition(
                        word,
                        run.language,
                        allow_ai=allow_ai("definition"),
                        definition_language=run.language,
                    )
                    trace_result("definition_source", result, ai_field="definition")
                    source_def = result.value or ""
                    source_def = normalize_definition(
                        source_def,
                        run.language,
                        pos_mode="auto",
                        min_words=6,
                        max_words=10,
                    )
                    if source_def:
                        cache.set("definitions", source_key, source_def)

                definition_en = ""
                if source_def:
                    result = providers.translation_web(source_def, run.language, "en")
                    trace_result("definition", result)
                    definition_en = result.value or ""
                    if not definition_en and allow_ai("definition"):
                        result = providers.translation_ai(
                            source_def, run.language, "en"
                        )
                        trace_result("definition", result, ai_field="definition")
                        definition_en = result.value or ""
                if not definition_en and allow_ai("definition"):
                    result = providers.definition(
                        word,
                        run.language,
                        allow_ai=True,
                        definition_language="en",
                    )
                    trace_result("definition", result, ai_field="definition")
                    definition_en = result.value or ""

                definition = normalize_definition(
                    definition_en,
                    "en",
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
        ipa = _normalize_ipa(ipa)
        if ipa and not _ipa_has_pronunciation(ipa) and allow_ai("ipa"):
            result = providers.phonetic_spelling(ipa, run.language, allow_ai=True)
            trace_result("ipa_pronunciation", result, ai_field="ipa")
            phonetic = _sanitize_phonetic(result.value or "")
            if phonetic:
                ipa = f"{ipa} ({phonetic})"
        cache.set("ipa", word, ipa)

        sentence = cache.get("sentences", word)
        if sentence and not sentence_is_acceptable(sentence, word, 5, 25):
            sentence = ""
        if not sentence:
            result = providers.sentence_web(word, run.language)
            trace_result("sentence", result)
            candidate = result.value or ""
            if candidate and sentence_is_acceptable(candidate, word, 5, 25):
                sentence = candidate
                cache.set("sentences", word, sentence)
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

        translation = ""
        if sentence:
            result = providers.translation_web(
                sentence, run.language, run.target_translation
            )
            trace_result("translation", result)
            translation = result.value or ""
            if not translation and allow_ai("translation"):
                result = providers.translation_ai(
                    sentence, run.language, run.target_translation
                )
                trace_result("translation", result, ai_field="translation")
                translation = result.value or ""

        audio_cfg = self.config.get("audio") if isinstance(self.config, dict) else {}
        audio_cfg = audio_cfg if isinstance(audio_cfg, dict) else {}
        audio_enabled = bool(audio_cfg.get("enabled", False))
        audio_required = bool(audio_cfg.get("required", False)) and audio_enabled
        audio_output_dir = audio_cfg.get("output_dir", "ankideck_generator/data/audio")
        provider_order = _normalize_provider_order(audio_cfg.get("provider_order"))
        if not provider_order:
            provider_order = ["gtts", "responsivevoice", "pyttsx3"]
        language_overrides = audio_cfg.get("language_overrides") or {}
        lang_override = (
            language_overrides.get(run.language, {})
            if isinstance(language_overrides, dict)
            else {}
        )
        voice_override = None
        if isinstance(lang_override, dict):
            override_order = _normalize_provider_order(lang_override.get("provider_order"))
            if override_order:
                provider_order = override_order
            voice_override = lang_override.get("voice")
        providers_cfg = self.config.get("providers", {}) if isinstance(self.config, dict) else {}
        azure_cfg = providers_cfg.get("azure_tts", {}) if isinstance(providers_cfg, dict) else {}
        azure_voice_map = azure_cfg.get("voice_map") or {}
        azure_voice = voice_override or azure_voice_map.get(run.language) or azure_cfg.get("voice")
        eleven_cfg = providers_cfg.get("elevenlabs", {}) if isinstance(providers_cfg, dict) else {}
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

        def _add_media(path: str) -> None:
            if path and path not in media_files:
                media_files.append(path)

        def _cached_audio(kind: str, text_value: str) -> ProviderResult | None:
            cache_kind = "audio_files"
            for provider_name in provider_order:
                cache_key = f"{kind}::{text_value}::{provider_name}::{voice_key}"
                cached = cache.get(cache_kind, cache_key)
                if cached and Path(cached).exists():
                    _add_media(cached)
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
                    _add_media(cached)
                    return ProviderResult(
                        value=cached,
                        provider_name="cache",
                        elapsed_ms=0,
                        error=None,
                    )
            return None

        def _audio_for(kind: str, text_value: str) -> tuple[str, ProviderResult | None]:
            if not audio_enabled or not text_value:
                return "", None
            cached = _cached_audio(kind, text_value)
            if cached and cached.value:
                return _sound_tag(cached.value), cached
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
                _add_media(value)
                return _sound_tag(value), result
            if value and not Path(value).exists():
                result = ProviderResult(
                    value=None,
                    provider_name=provider_name,
                    elapsed_ms=elapsed_ms,
                    error=error or "audio_file_missing",
                )
            return "", result

        audio_value = ""
        word_audio = ""
        sentence_audio = ""
        if audio_enabled:
            word_audio, result = _audio_for("word", word)
            if result:
                trace_result("word_audio", result)
            if word_audio:
                audio_value = word_audio
            if sentence:
                sentence_audio, result = _audio_for("sentence", sentence)
                if result:
                    trace_result("sentence_audio", result)
                if not audio_value and sentence_audio:
                    audio_value = sentence_audio

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
            word_audio=word_audio,
            sentence_audio=sentence_audio,
            level=level,
            language=run.language,
        )

        errors = validate_card(
            card,
            ctx,
            _validations_for_language(run.language, audio_required=audio_required),
        )
        runtime_cfg = self.config.get("runtime") if isinstance(self.config, dict) else {}
        runtime_cfg = runtime_cfg if isinstance(runtime_cfg, dict) else {}
        test_accept_all = bool(runtime_cfg.get("test_accept_all", False)) and run.mode == "test"
        if errors and not test_accept_all:
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
        if errors and test_accept_all:
            return card, LogRecord(
                focus=word,
                level=level,
                providers=providers_used,
                provider_errors=provider_errors,
                validations=errors,
                status="accepted",
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

    def _cleanup_audio_files(self, media_files: list[str], audio_dir: str | Path) -> None:
        base_dir = Path(audio_dir).resolve()
        removed = set()
        for path_str in media_files:
            path = Path(path_str)
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if base_dir not in resolved.parents and resolved != base_dir:
                continue
            if resolved.suffix.lower() not in {".mp3", ".wav", ".ogg", ".opus"}:
                continue
            if resolved in removed:
                continue
            try:
                resolved.unlink()
                removed.add(resolved)
            except OSError:
                continue
        # Remove empty directories under the audio dir
        for folder in sorted(base_dir.rglob("*"), reverse=True):
            if folder.is_dir():
                try:
                    folder.rmdir()
                except OSError:
                    continue


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


def _normalize_provider_order(value: object) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def _audio_voice_key(value: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value)
    return cleaned[:80] if cleaned else "default"


def _sound_tag(path: str) -> str:
    return f"[sound:{Path(path).name}]"


def _infer_discard_reason(
    errors: list[str], provider_errors: dict[str, str]
) -> str | None:
    sentence_related = {
        "focus_not_in_sentence",
        "example_word_not_in_sentence",
        "sentence_length_invalid",
    }
    if "sentence" in provider_errors or sentence_related.intersection(errors):
        return "sentence_generation_failed"
    if (
        "translation" in provider_errors
        or "word_translation" in provider_errors
        or "translation_missing" in errors
    ):
        return "translation_generation_failed"
    if "definition" in provider_errors or "definition_missing" in errors:
        return "definition_generation_failed"
    if "ipa" in provider_errors or "ipa_missing" in errors:
        return "ipa_generation_failed"
    if (
        "letter_audio" in provider_errors
        or "word_audio" in provider_errors
        or "sentence_audio" in provider_errors
    ):
        return "audio_generation_failed"
    return None


def _validations_for_language(language: str, audio_required: bool = False) -> dict[str, object]:
    _ = language
    validations = dict(DEFAULT_VALIDATIONS)
    if audio_required:
        validations["word_audio_required"] = True
        validations["sentence_audio_required"] = True
    return validations
