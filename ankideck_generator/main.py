from __future__ import annotations

import argparse
from pathlib import Path
import sys

from colorama import Fore, Style, init as colorama_init

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional
    load_dotenv = None

from .core.deck_builder import DeckBuilder
from .core.models import RunConfig
from .utils.config import load_config


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Anki Deck Generator")
    parser.add_argument("--language", default="en", help="Language code (en, es, fr, it, de, ru)")
    parser.add_argument(
        "--mode",
        default="test",
        choices=["test", "full", "build"],
        help="Generation mode (build is an alias of full)",
    )
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--output", default="output/deck.apkg", help="Output .apkg path")
    parser.add_argument("--seed", type=int, default=None, help="Override random seed")
    parser.add_argument(
        "--refresh-text-cache",
        action="store_true",
        help="Ignore cached sentences, definitions, and translations for this run",
    )
    parser.add_argument("--resume", action="store_true", default=False, help="Resume from progress")
    parser.add_argument("--no-resume", action="store_false", dest="resume", help="Disable resume")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    return parser


def main() -> int:
    colorama_init(autoreset=True)
    if load_dotenv:
        load_dotenv()
    parser = build_arg_parser()
    args = parser.parse_args()

    config = load_config(args.config)
    languages = config.get("languages", {})

    if args.language not in languages:
        print(Fore.RED + f"Unsupported language: {args.language}")
        print("Available: " + ", ".join(sorted(languages.keys())))
        return 1

    mode_input = args.mode
    mode = "full" if mode_input == "build" else mode_input
    if mode == "full" and sys.version_info[:2] != (3, 11):
        print(
            Fore.YELLOW
            + "Warning: Python 3.11 is recommended for full generation (googletrans is unstable on newer versions)."
        )
    runtime_cfg = config.get("runtime", {})
    profiles = runtime_cfg.get("profiles", {})
    mode_profile = profiles.get(mode, {})
    test_level_size = runtime_cfg.get("test_level_size", 100)
    full_level_size = runtime_cfg.get("full_level_size", 1000)
    level_size = test_level_size if mode == "test" else full_level_size

    lang_cfg = languages[args.language]
    timeout_sec = mode_profile.get("timeout_sec", runtime_cfg.get("timeout_sec", 10))
    retries = mode_profile.get("retries", runtime_cfg.get("retries", 2))
    ai_max_calls_per_word = mode_profile.get("ai_max_calls_per_word", runtime_cfg.get("ai_max_calls_per_word", 6))
    ai_max_calls_per_field = mode_profile.get("ai_max_calls_per_field", runtime_cfg.get("ai_max_calls_per_field", 2))
    level_pool_multiplier = runtime_cfg.get("level_pool_multiplier", 8)
    concurrency = runtime_cfg.get("concurrency", 1)
    audio_concurrency = runtime_cfg.get("audio_concurrency", 1)
    max_attempts_per_level = runtime_cfg.get("max_attempts_per_level_full", 0)
    if mode == "test":
        level_pool_multiplier = runtime_cfg.get("test_level_pool_multiplier", level_pool_multiplier)
        concurrency = runtime_cfg.get("test_concurrency", concurrency)
        audio_concurrency = runtime_cfg.get("test_audio_concurrency", audio_concurrency)
        max_attempts_per_level = runtime_cfg.get(
            "max_attempts_per_level_test", max_attempts_per_level
        )
    else:
        concurrency = runtime_cfg.get("full_concurrency", concurrency)
        audio_concurrency = runtime_cfg.get(
            "full_audio_concurrency", audio_concurrency
        )
    strict_quality = runtime_cfg.get("strict_quality", True)
    exclude_closed_class_words = bool(runtime_cfg.get("exclude_closed_class_words", True))
    cache_validation_version = int(runtime_cfg.get("cache_validation_version", 4) or 4)
    enforce_translation_language = bool(
        runtime_cfg.get("enforce_translation_language", True)
    )
    sentence_rewrite_from_web = bool(
        runtime_cfg.get("sentence_rewrite_from_web", True)
    )
    level_validation_mode = str(
        runtime_cfg.get("level_validation_mode", "profile_hard_zipf_soft")
    ).strip() or "profile_hard_zipf_soft"
    generate_audio = not (mode == "test" and bool(runtime_cfg.get("test_disable_audio", False)))
    provider_timeout_overrides = dict(runtime_cfg.get("provider_timeout_overrides", {}) or {})
    provider_timeout_overrides.update(dict(mode_profile.get("provider_timeout_overrides", {}) or {}))
    provider_retry_overrides = dict(runtime_cfg.get("provider_retry_overrides", {}) or {})
    provider_retry_overrides.update(dict(mode_profile.get("provider_retry_overrides", {}) or {}))
    sentence_ai_attempts = int(runtime_cfg.get("sentence_ai_attempts", 2) or 2)
    definition_context_fallback = bool(runtime_cfg.get("definition_context_fallback", True))
    low_yield_min_attempts = int(runtime_cfg.get("low_yield_min_attempts", 0) or 0)
    low_yield_min_acceptance_rate = float(
        runtime_cfg.get("low_yield_min_acceptance_rate", 0.0) or 0.0
    )
    low_yield_max_accepted = int(runtime_cfg.get("low_yield_max_accepted", 0) or 0)
    low_yield_start_level = int(runtime_cfg.get("low_yield_start_level", 1) or 1)
    definition_word_fallback = bool(runtime_cfg.get("definition_word_fallback", False))
    definition_context_first = bool(runtime_cfg.get("definition_context_first", True))
    definition_candidates_limit = int(runtime_cfg.get("definition_candidates_limit", 5) or 5)
    review_queue_path = str(
        runtime_cfg.get("review_queue_path", "output/review_queue.json")
        or "output/review_queue.json"
    )
    quality_report_path = str(
        runtime_cfg.get("quality_report_path", "output/quality_report.json")
        or "output/quality_report.json"
    )
    if mode == "test":
        sentence_ai_attempts = int(
            runtime_cfg.get("sentence_ai_attempts_test", sentence_ai_attempts)
            or sentence_ai_attempts
        )
        definition_context_fallback = bool(
            runtime_cfg.get(
                "definition_context_fallback_test", definition_context_fallback
            )
        )
        low_yield_min_attempts = int(
            runtime_cfg.get("low_yield_min_attempts_test", low_yield_min_attempts)
            or low_yield_min_attempts
        )
        low_yield_min_acceptance_rate = float(
            runtime_cfg.get(
                "low_yield_min_acceptance_rate_test", low_yield_min_acceptance_rate
            )
            or low_yield_min_acceptance_rate
        )
        low_yield_max_accepted = int(
            runtime_cfg.get("low_yield_max_accepted_test", low_yield_max_accepted)
            or low_yield_max_accepted
        )
        low_yield_start_level = int(
            runtime_cfg.get("low_yield_start_level_test", low_yield_start_level)
            or low_yield_start_level
        )
        definition_word_fallback = bool(
            runtime_cfg.get("definition_word_fallback_test", definition_word_fallback)
        )
    else:
        sentence_ai_attempts = int(
            runtime_cfg.get("sentence_ai_attempts_full", sentence_ai_attempts)
            or sentence_ai_attempts
        )
        definition_context_fallback = bool(
            runtime_cfg.get(
                "definition_context_fallback_full", definition_context_fallback
            )
        )
        low_yield_min_attempts = int(
            runtime_cfg.get("low_yield_min_attempts_full", low_yield_min_attempts)
            or low_yield_min_attempts
        )
        low_yield_min_acceptance_rate = float(
            runtime_cfg.get(
                "low_yield_min_acceptance_rate_full", low_yield_min_acceptance_rate
            )
            or low_yield_min_acceptance_rate
        )
        low_yield_max_accepted = int(
            runtime_cfg.get("low_yield_max_accepted_full", low_yield_max_accepted)
            or low_yield_max_accepted
        )
        low_yield_start_level = int(
            runtime_cfg.get("low_yield_start_level_full", low_yield_start_level)
            or low_yield_start_level
        )
        definition_word_fallback = bool(
            runtime_cfg.get("definition_word_fallback_full", definition_word_fallback)
        )
    lexicon_zipf_fallback_min = float(runtime_cfg.get("lexicon_zipf_fallback_min", 0.0) or 0.0)
    lexicon_zipf_fallback_by_language = dict(
        runtime_cfg.get("lexicon_zipf_fallback_min_by_language", {}) or {}
    )
    lexicon_zipf_fallback_min = float(
        lexicon_zipf_fallback_by_language.get(args.language, lexicon_zipf_fallback_min)
        or lexicon_zipf_fallback_min
    )

    run = RunConfig(
        language=lang_cfg.get("code", args.language),
        mode=mode,
        interactive=args.interactive,
        output_path=args.output,
        resume=args.resume,
        level_size=level_size,
        target_translation=lang_cfg.get("target_translation_code", "en"),
        wordfreq_language=lang_cfg.get("wordfreq_code", args.language),
        timeout_sec=timeout_sec,
        retries=retries,
        seed=args.seed if args.seed is not None else runtime_cfg.get("seed", 42),
        cache_path=config.get("cache", {}).get("path", "ankideck_generator/data/cache"),
        autosave_every=config.get("cache", {}).get("autosave_every", 10),
        refresh_text_cache=bool(args.refresh_text_cache),
        ai_max_calls_per_word=ai_max_calls_per_word,
        ai_max_calls_per_field=ai_max_calls_per_field,
        level_pool_multiplier=level_pool_multiplier,
        concurrency=concurrency,
        audio_concurrency=audio_concurrency,
        strict_quality=strict_quality,
        max_attempts_per_level=int(max_attempts_per_level or 0),
        exclude_closed_class_words=exclude_closed_class_words,
        cache_validation_version=cache_validation_version,
        enforce_translation_language=enforce_translation_language,
        generate_audio=generate_audio,
        sentence_rewrite_from_web=sentence_rewrite_from_web,
        level_validation_mode=level_validation_mode,
        provider_timeout_overrides={
            str(key): int(value)
            for key, value in provider_timeout_overrides.items()
            if value is not None
        },
        provider_retry_overrides={
            str(key): int(value)
            for key, value in provider_retry_overrides.items()
            if value is not None
        },
        lexicon_zipf_fallback_min=max(0.0, float(lexicon_zipf_fallback_min)),
        sentence_ai_attempts=max(0, int(sentence_ai_attempts)),
        definition_context_fallback=bool(definition_context_fallback),
        low_yield_min_attempts=max(0, int(low_yield_min_attempts)),
        low_yield_min_acceptance_rate=max(0.0, float(low_yield_min_acceptance_rate)),
        low_yield_max_accepted=max(0, int(low_yield_max_accepted)),
        low_yield_start_level=max(1, int(low_yield_start_level)),
        definition_word_fallback=bool(definition_word_fallback),
        definition_context_first=bool(definition_context_first),
        definition_candidates_limit=max(1, int(definition_candidates_limit)),
        review_queue_path=review_queue_path,
        quality_report_path=quality_report_path,
    )

    builder = DeckBuilder(args.config)
    if args.resume:
        print(
            Fore.YELLOW
            + "Warning: resume mode is not recommended for final deck export. Prefer --no-resume for full consistency."
        )
    if run.strict_quality:
        ok, preflight_msg = builder.preflight(run)
        if not ok:
            print(Fore.RED + preflight_msg)
            return 1
    print(Style.BRIGHT + f"Generating deck for {lang_cfg.get('display_name', args.language)}...")
    cards, media_files = builder.build(run)
    builder.export_deck(run, cards, media_files)

    print(Style.BRIGHT + Fore.GREEN + f"Done. Cards: {len(cards)}")
    print(Style.BRIGHT + Fore.GREEN + f"Output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
