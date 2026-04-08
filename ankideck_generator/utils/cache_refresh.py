from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..core.deck_builder import DeckBuilder
from ..core.providers import ProviderManager
from .definition_tools import (
    MetaDefinition,
    build_definition_policy,
    compose_resolved_meta_definition,
    extract_meta_definition,
    normalize_definition,
)
from .file_utils import atomic_write_json, read_json
from .language_tools import semantic_definition_reason, text_contains_focus

DEFINITION_KEY_RE = re.compile(r"^(?P<word>.+?)::(?P<lang>[a-z]{2})::v\d+$")
TRANSLATION_KEY_RE = re.compile(r"^(?P<sentence>.+?)::(?P<src>[a-z]{2})->(?P<dest>[a-z]{2})::v\d+$")
SYNTHETIC_DEFINITION_TRANSLATION_PREFIX = "this sentence uses a word that means "


@dataclass
class CacheRefreshStats:
    definitions_refreshed: int = 0
    definition_entries_removed: int = 0
    definitions_normalized: int = 0
    translations_refreshed: int = 0
    translations_removed: int = 0


def refresh_russian_caches(
    definitions: dict[str, str],
    translations: dict[str, str],
    sentences: dict[str, str],
    *,
    resolve_definition: Callable[[str, str | None], str | None],
    resolve_translation: Callable[[str], str | None],
    policy: dict | None = None,
) -> CacheRefreshStats:
    resolved_policy = build_definition_policy(policy)
    stats = CacheRefreshStats()
    keys_by_word: dict[str, list[str]] = {}

    for key, value in list(definitions.items()):
        match = DEFINITION_KEY_RE.match(key)
        if not match:
            continue
        word = match.group("word")
        normalized = normalize_semantic_definition(value, policy=resolved_policy)
        if normalized and normalized != value.strip().rstrip("."):
            definitions[key] = normalized
            stats.definitions_normalized += 1
            value = normalized
        if definition_needs_refresh(value, policy=resolved_policy):
            keys_by_word.setdefault(word, []).append(key)

    for word, keys in keys_by_word.items():
        context_sentence = select_context_sentence(word, sentences)
        improved = resolve_definition(word, context_sentence) or ""
        improved = normalize_semantic_definition(improved, policy=resolved_policy)
        if not improved:
            for key in list(keys):
                if definition_needs_refresh(definitions.get(key, ""), policy=resolved_policy):
                    definitions.pop(key, None)
                    stats.definition_entries_removed += 1
            continue

        en_key_written = False
        for key in list(keys):
            match = DEFINITION_KEY_RE.match(key)
            if not match:
                continue
            entry_lang = match.group("lang")
            if entry_lang == "en":
                if definitions.get(key) != improved:
                    definitions[key] = improved
                    stats.definitions_refreshed += 1
                en_key_written = True
            elif definition_needs_refresh(definitions.get(key, ""), policy=resolved_policy):
                definitions.pop(key, None)
                stats.definition_entries_removed += 1

        if not en_key_written and keys:
            seed_key = keys[0]
            new_key = re.sub(r"::[a-z]{2}::", "::en::", seed_key, count=1)
            definitions[new_key] = improved
            stats.definitions_refreshed += 1

    for key, value in list(translations.items()):
        match = TRANSLATION_KEY_RE.match(key)
        if not match or match.group("src") != "ru" or match.group("dest") != "en":
            continue
        if not is_synthetic_definition_translation(value):
            continue
        sentence = match.group("sentence")
        refreshed = (resolve_translation(sentence) or "").strip()
        if refreshed and not is_synthetic_definition_translation(refreshed):
            if translations.get(key) != refreshed:
                translations[key] = refreshed
                stats.translations_refreshed += 1
            continue
        translations.pop(key, None)
        stats.translations_removed += 1

    return stats


def refresh_russian_cache_files(config_path: str | Path = "config.yaml") -> CacheRefreshStats:
    builder = DeckBuilder(str(config_path))
    config = builder.config
    cache_dir = Path(config.get("cache", {}).get("path", "ankideck_generator/data/cache"))
    definitions_path = cache_dir / "ru_definitions.json"
    translations_path = cache_dir / "ru_translations.json"
    sentences_path = cache_dir / "ru_sentences.json"

    definitions = read_json(definitions_path, default={})
    translations = read_json(translations_path, default={})
    sentences = read_json(sentences_path, default={})

    providers = ProviderManager(
        config,
        timeout_sec=int(config.get("runtime", {}).get("timeout_sec", 10) or 10),
        retries=int(config.get("runtime", {}).get("retries", 2) or 2),
    )
    policy = builder.definition_policy or build_definition_policy()

    def resolve_definition(word: str, sentence: str | None) -> str | None:
        cached = resolve_definition_from_cache(word, definitions, policy=policy)
        if cached:
            return cached

        initial = providers.definition(word, "ru", allow_ai=False, definition_language="ru")
        normalized = normalize_semantic_definition(initial.value or "", policy=policy)
        if normalized and not definition_needs_refresh(normalized, policy=policy):
            return normalized

        if sentence:
            contextual = providers.definition_from_context(
                word,
                sentence,
                "ru",
                definition_language="en",
            )
            normalized = normalize_semantic_definition(contextual.value or "", policy=policy)
            if normalized and not definition_needs_refresh(normalized, policy=policy):
                return normalized

        semantic = providers.definition_ai(word, "en", semantic_only=True)
        normalized = normalize_semantic_definition(semantic.value or "", policy=policy)
        return normalized or None

    def resolve_translation(sentence: str) -> str | None:
        web_result = providers.translation_web(sentence, "ru", "en")
        if web_result.value and not is_synthetic_definition_translation(web_result.value):
            return web_result.value.strip()
        ai_result = providers.translation_ai(sentence, "ru", "en")
        if ai_result.value and not is_synthetic_definition_translation(ai_result.value):
            return ai_result.value.strip()
        return None

    stats = refresh_russian_caches(
        definitions,
        translations,
        sentences,
        resolve_definition=resolve_definition,
        resolve_translation=resolve_translation,
        policy=policy,
    )
    atomic_write_json(definitions_path, definitions)
    atomic_write_json(translations_path, translations)
    return stats


def definition_needs_refresh(value: str, *, policy: dict | None = None) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if ".mw-parser-output" in lowered or "with accusative" in lowered or "with genitive" in lowered:
        return True
    return extract_meta_definition(text, policy=policy) is not None


def normalize_semantic_definition(value: str, *, policy: dict | None = None) -> str:
    normalized = normalize_definition(
        value,
        "en",
        min_words=1,
        max_words=12,
        policy=policy,
    )
    if not normalized or semantic_definition_reason(normalized) is not None:
        return ""
    return normalized.rstrip(".")


def is_synthetic_definition_translation(value: str) -> bool:
    return (value or "").strip().lower().startswith(SYNTHETIC_DEFINITION_TRANSLATION_PREFIX)


def select_context_sentence(word: str, sentences: dict[str, str]) -> str | None:
    candidates: list[str] = []
    for sentence in sentences.values():
        text = str(sentence or "").strip()
        if not text:
            continue
        if text_contains_focus(text, word) or word.lower() in text.lower():
            candidates.append(text)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (len(item.split()) > 4, len(item)), reverse=True)
    return candidates[0]


def resolve_definition_from_cache(
    word: str,
    definitions: dict[str, str],
    *,
    policy: dict | None = None,
    _seen: set[str] | None = None,
) -> str:
    resolved_policy = build_definition_policy(policy)
    seen = set(_seen or set())
    normalized_word = _normalize_lookup_word(word)
    if not normalized_word or normalized_word in seen:
        return ""
    seen.add(normalized_word)

    for key, value in definitions.items():
        match = DEFINITION_KEY_RE.match(key)
        if not match or _normalize_lookup_word(match.group("word")) != normalized_word:
            continue
        normalized = normalize_semantic_definition(value, policy=resolved_policy)
        if normalized and not definition_needs_refresh(normalized, policy=resolved_policy):
            return normalized

    for key, value in definitions.items():
        match = DEFINITION_KEY_RE.match(key)
        if not match or _normalize_lookup_word(match.group("word")) != normalized_word:
            continue
        meta = extract_meta_definition(value, policy=resolved_policy)
        if meta is None or not meta.lemma:
            continue
        lemma_definition = resolve_definition_from_cache(
            meta.lemma,
            definitions,
            policy=resolved_policy,
            _seen=seen,
        )
        if not lemma_definition:
            continue
        composed = compose_resolved_meta_definition(
            lemma_definition,
            MetaDefinition(
                pos_label=meta.pos_label,
                lemma=meta.lemma,
                tags=meta.tags,
                raw_body=meta.raw_body,
            ),
            policy=resolved_policy,
        )
        if composed:
            return composed
    return ""


def _normalize_lookup_word(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or "").strip().lower())
    return "".join(char for char in normalized if not unicodedata.combining(char))
