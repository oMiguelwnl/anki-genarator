from __future__ import annotations

import argparse
from pathlib import Path

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
    parser.add_argument("--mode", default="test", choices=["test", "full"], help="Generation mode")
    parser.add_argument("--interactive", action="store_true", help="Interactive mode")
    parser.add_argument("--output", default="output/deck.apkg", help="Output .apkg path")
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

    mode = args.mode
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
    strict_quality = runtime_cfg.get("strict_quality", True)
    exclude_closed_class_words = bool(runtime_cfg.get("exclude_closed_class_words", True))
    cache_validation_version = int(runtime_cfg.get("cache_validation_version", 3) or 3)
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
        seed=runtime_cfg.get("seed", 42),
        cache_path=config.get("cache", {}).get("path", "ankideck_generator/data/cache"),
        autosave_every=config.get("cache", {}).get("autosave_every", 10),
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
