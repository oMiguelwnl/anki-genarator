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
    parser.add_argument("--resume", action="store_true", default=True, help="Resume from progress")
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
    test_level_size = runtime_cfg.get("test_level_size", 100)
    full_level_size = runtime_cfg.get("full_level_size", 1000)
    level_size = test_level_size if mode == "test" else full_level_size

    lang_cfg = languages[args.language]
    run = RunConfig(
        language=lang_cfg.get("code", args.language),
        mode=mode,
        interactive=args.interactive,
        output_path=args.output,
        resume=args.resume,
        level_size=level_size,
        target_translation=lang_cfg.get("target_translation_code", "en"),
        wordfreq_language=lang_cfg.get("wordfreq_code", args.language),
        timeout_sec=runtime_cfg.get("timeout_sec", 10),
        retries=runtime_cfg.get("retries", 2),
        seed=runtime_cfg.get("seed", 42),
        cache_path=config.get("cache", {}).get("path", "ankideck_generator/data/cache"),
        autosave_every=config.get("cache", {}).get("autosave_every", 10),
        ai_max_calls_per_word=runtime_cfg.get("ai_max_calls_per_word", 6),
        ai_max_calls_per_field=runtime_cfg.get("ai_max_calls_per_field", 2),
    )

    builder = DeckBuilder(args.config)
    print(Style.BRIGHT + f"Generating deck for {lang_cfg.get('display_name', args.language)}...")
    cards, media_files = builder.build(run)
    builder.export_deck(run, cards, media_files)

    print(Style.BRIGHT + Fore.GREEN + f"Done. Cards: {len(cards)}")
    print(Style.BRIGHT + Fore.GREEN + f"Output: {Path(args.output).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
