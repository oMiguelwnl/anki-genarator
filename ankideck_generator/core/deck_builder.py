from __future__ import annotations

import random
from datetime import datetime
import re
from pathlib import Path

import genanki
from tqdm import tqdm

from ..utils.config import load_config
from ..utils.file_utils import atomic_write_json, ensure_dir, read_json
from ..utils.language_tools import filter_frequent_words, sentence_is_acceptable, unique_keep_order
from ..utils.logger import JsonLogger
from .cache_manager import CacheManager
from .models import CardData, LogRecord, ProgressState, RunConfig
from .providers import ProviderManager
from .validators import ValidationContext, validate_card

try:
    from wordfreq import top_n_list
except Exception as exc:  # pragma: no cover - optional
    raise RuntimeError("wordfreq is required") from exc

VALIDATIONS = {
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

    def build(self, run: RunConfig) -> tuple[list[CardData], list[str]]:
        provider_manager = ProviderManager(self.config, run.timeout_sec, run.retries)
        cache_manager = CacheManager(run.cache_path, run.language, run.autosave_every)
        progress_store = ProgressStore("ankideck_generator/data/progress")
        log_path = f"ankideck_generator/data/logs/run-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.jsonl"
        logger = JsonLogger(log_path)
        ctx = ValidationContext()

        level_size = run.level_size
        wordfreq_lang = run.wordfreq_language or run.language
        level_sets = self._prepare_levels(wordfreq_lang, level_size, run.seed)

        state = None
        if run.resume:
            state = progress_store.load(run.language, run.mode)
        processed_focus = set(state.processed_focus) if state else set()
        processed_sentences = set(state.processed_sentences) if state else set()
        ctx.seen_focus.update(processed_focus)
        ctx.seen_sentence.update(processed_sentences)

        cards: list[CardData] = []
        media_files: list[str] = []
        processed = 0

        for level, words in level_sets.items():
            for index, word in enumerate(tqdm(words, desc=f"Level {level}", unit="word")):
                if word in processed_focus:
                    continue
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
                if card:
                    cards.append(card)
                    processed_focus.add(card.focus)
                    processed_sentences.add(card.sentence)
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
                            created_cards=len(cards),
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
                created_cards=len(cards),
            )
        )
        return cards, media_files

    def export_deck(self, run: RunConfig, cards: list[CardData], media_files: list[str]) -> None:
        deck_cfg = self.config.get("deck", {})
        model = genanki.Model(
            deck_cfg.get("model_id", 1607392319),
            deck_cfg.get("name", "Anki Deck Generator"),
            fields=[
                {"name": "SortIndex"},
                {"name": "word"},
                {"name": "Front of Card"},
                {"name": "Definitions"},
                {"name": "Exemple Sentence"},
                {"name": "Translation"},
                {"name": "word_audio"},
                {"name": "sentence_audio"},
                {"name": "image"},
            ],
            templates=[
                {
                    "name": "Card 1",
                    "qfmt": self._resolve_path(deck_cfg.get("front_template")).read_text(encoding="utf-8"),
                    "afmt": self._resolve_path(deck_cfg.get("back_template")).read_text(encoding="utf-8"),
                }
            ],
            css=self._resolve_path(deck_cfg.get("css_path")).read_text(encoding="utf-8"),
        )

        deck = genanki.Deck(deck_cfg.get("deck_id", 2059400110), deck_cfg.get("name", "Anki Deck Generator"))
        for card in cards:
            note = genanki.Note(
                model=model,
                fields=card.genanki_fields(),
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

    def _prepare_levels(self, language: str, level_size: int, seed: int) -> dict[int, list[str]]:
        random.seed(seed)
        target_total = max(level_size * 60, 6000)
        raw_top = top_n_list(language, target_total)
        filtered_top = filter_frequent_words(raw_top, language, min_length=3)
        if len(filtered_top) < level_size:
            raw_top = top_n_list(language, target_total * 2)
            filtered_top = filter_frequent_words(raw_top, language, min_length=3)
        level1 = filtered_top[:level_size]

        pool_raw = top_n_list(language, max(50000, target_total * 3))
        pool_filtered = filter_frequent_words(pool_raw, language, min_length=3)
        pool_filtered = [w for w in pool_filtered if w not in level1]

        level2_candidates = pool_filtered[:15000]
        random.shuffle(level2_candidates)
        level2 = level2_candidates[:level_size]

        level3_candidates = pool_filtered[15000:40000] if len(pool_filtered) > 40000 else pool_filtered
        random.shuffle(level3_candidates)
        level3 = level3_candidates[:level_size]

        return {
            1: unique_keep_order(level1),
            2: unique_keep_order(level2),
            3: unique_keep_order(level3),
        }

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

        definition_key = f"{word}::{run.target_translation}"
        definition = cache.get("definitions", definition_key)
        if not definition:
            result = providers.definition(
                word,
                run.language,
                allow_ai=allow_ai("definition"),
                definition_language=run.target_translation,
            )
            providers_used["definition"] = result.provider_name
            if result.error:
                provider_errors["definition"] = result.error
            if result.provider_name == "ai":
                mark_ai("definition")
            definition = result.value or ""
            if definition:
                cache.set("definitions", definition_key, definition)

        ipa = cache.get("ipa", word)
        if not ipa:
            result = providers.ipa(word, run.language, allow_ai=allow_ai("ipa"))
            providers_used["ipa"] = result.provider_name
            if result.error:
                provider_errors["ipa"] = result.error
            if result.provider_name == "ai":
                mark_ai("ipa")
            ipa = result.value or ""
            if ipa:
                cache.set("ipa", word, ipa)

        sentence = cache.get("sentences", word)
        if not sentence:
            result = providers.sentence(word, run.language, allow_ai=allow_ai("sentence"))
            providers_used["sentence"] = result.provider_name
            if result.error:
                provider_errors["sentence"] = result.error
            if result.provider_name == "ai":
                mark_ai("sentence")
            sentence = result.value or ""
            if sentence:
                cache.set("sentences", word, sentence)
        if sentence and not sentence_is_acceptable(sentence, word, 5, 25):
            sentence = ""
        if not sentence:
            if allow_ai("sentence"):
                result = providers.sentence_ai(word, run.language)
                providers_used["sentence"] = result.provider_name
                if result.error:
                    provider_errors["sentence"] = result.error
                if result.provider_name == "ai":
                    mark_ai("sentence")
                sentence = result.value or ""
                if sentence:
                    cache.set("sentences", word, sentence)

        translation = ""
        if level in {1, 2} and sentence:
            translation_key = f"{word}::{sentence}"
            translation = cache.get("translations", translation_key)
            if not translation:
                result = providers.translation(
                    sentence, run.language, run.target_translation, allow_ai=allow_ai("translation")
                )
                providers_used["translation"] = result.provider_name
                if result.error:
                    provider_errors["translation"] = result.error
                if result.provider_name == "ai":
                    mark_ai("translation")
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
            translation=translation if level in {1, 2} else "",
            translation_language=run.target_translation,
            image="",
            audio=audio_value,
            word_audio="",
            sentence_audio="",
            level=level,
            language=run.language,
        )

        errors = validate_card(card, ctx, VALIDATIONS)
        if errors:
            return None, LogRecord(
                focus=word,
                level=level,
                providers=providers_used,
                provider_errors=provider_errors,
                validations=errors,
                status="discarded",
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
                field = input("Field to edit (focus, definition, sentence, translation, ipa, image, audio): ").strip()
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
