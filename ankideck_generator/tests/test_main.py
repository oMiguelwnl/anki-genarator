import argparse
from typing import Any

import ankideck_generator.main as main_module
from ankideck_generator.main import build_arg_parser


def test_arg_parser_resume_defaults_to_false() -> None:
    parser = build_arg_parser()
    args = parser.parse_args([])
    assert args.resume is False


def test_arg_parser_resume_opt_in() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--resume"])
    assert args.resume is True


def test_arg_parser_no_resume_overrides_resume() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--resume", "--no-resume"])
    assert args.resume is False


def test_arg_parser_accepts_build_mode() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--mode", "build"])
    assert args.mode == "build"


def test_arg_parser_accepts_seed_override() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--seed", "99"])
    assert args.seed == 99


def test_arg_parser_accepts_refresh_text_cache() -> None:
    parser = build_arg_parser()
    args = parser.parse_args(["--refresh-text-cache"])
    assert args.refresh_text_cache is True


def test_main_uses_full_mode_concurrency_overrides(monkeypatch, tmp_path) -> None:
    args = argparse.Namespace(
        language="es",
        mode="full",
        interactive=False,
        output=str(tmp_path / "deck.apkg"),
        seed=None,
        refresh_text_cache=False,
        resume=False,
        config=str(tmp_path / "config.yaml"),
    )
    config = {
        "languages": {
            "es": {
                "code": "es",
                "target_translation_code": "en",
                "wordfreq_code": "es",
                "display_name": "Spanish",
            }
        },
        "runtime": {
            "timeout_sec": 10,
            "retries": 2,
            "concurrency": 1,
            "full_concurrency": 4,
            "audio_concurrency": 1,
            "full_audio_concurrency": 2,
            "seed": 42,
            "test_level_size": 10,
            "full_level_size": 1000,
            "strict_quality": False,
            "profiles": {"full": {"timeout_sec": 10, "retries": 1}},
        },
        "cache": {
            "path": str(tmp_path / "cache"),
            "autosave_every": 1,
        },
    }
    captured: dict[str, Any] = {}

    class FakeParser:
        def parse_args(self):
            return args

    class FakeBuilder:
        def __init__(self, config_path):
            captured["config_path"] = config_path

        def build(self, run):
            captured["run"] = run
            return [], []

        def export_deck(self, run, cards, media_files):
            _ = (run, cards, media_files)

    monkeypatch.setattr(main_module, "build_arg_parser", lambda: FakeParser())
    monkeypatch.setattr(main_module, "load_config", lambda path: config)
    monkeypatch.setattr(main_module, "DeckBuilder", FakeBuilder)

    exit_code = main_module.main()

    assert exit_code == 0
    run = captured["run"]
    assert run.concurrency == 4
    assert run.audio_concurrency == 2


def test_main_build_mode_alias_uses_full_mode_overrides(monkeypatch, tmp_path) -> None:
    args = argparse.Namespace(
        language="es",
        mode="build",
        interactive=False,
        output=str(tmp_path / "deck.apkg"),
        seed=None,
        refresh_text_cache=False,
        resume=False,
        config=str(tmp_path / "config.yaml"),
    )
    config = {
        "languages": {
            "es": {
                "code": "es",
                "target_translation_code": "en",
                "wordfreq_code": "es",
                "display_name": "Spanish",
            }
        },
        "runtime": {
            "timeout_sec": 10,
            "retries": 2,
            "concurrency": 1,
            "full_concurrency": 4,
            "audio_concurrency": 1,
            "full_audio_concurrency": 2,
            "seed": 42,
            "test_level_size": 10,
            "full_level_size": 1000,
            "strict_quality": False,
            "profiles": {"full": {"timeout_sec": 10, "retries": 1}},
        },
        "cache": {
            "path": str(tmp_path / "cache"),
            "autosave_every": 1,
        },
    }
    captured: dict[str, Any] = {}

    class FakeParser:
        def parse_args(self):
            return args

    class FakeBuilder:
        def __init__(self, config_path):
            captured["config_path"] = config_path

        def build(self, run):
            captured["run"] = run
            return [], []

        def export_deck(self, run, cards, media_files):
            _ = (run, cards, media_files)

    monkeypatch.setattr(main_module, "build_arg_parser", lambda: FakeParser())
    monkeypatch.setattr(main_module, "load_config", lambda path: config)
    monkeypatch.setattr(main_module, "DeckBuilder", FakeBuilder)

    exit_code = main_module.main()

    assert exit_code == 0
    run = captured["run"]
    assert run.mode == "full"
    assert run.concurrency == 4
    assert run.audio_concurrency == 2


def test_main_seed_override_replaces_config_seed(monkeypatch, tmp_path) -> None:
    args = argparse.Namespace(
        language="es",
        mode="test",
        interactive=False,
        output=str(tmp_path / "deck.apkg"),
        seed=99,
        refresh_text_cache=False,
        resume=False,
        config=str(tmp_path / "config.yaml"),
    )
    config = {
        "languages": {
            "es": {
                "code": "es",
                "target_translation_code": "en",
                "wordfreq_code": "es",
                "display_name": "Spanish",
            }
        },
        "runtime": {
            "timeout_sec": 10,
            "retries": 2,
            "concurrency": 1,
            "audio_concurrency": 1,
            "seed": 42,
            "test_level_size": 10,
            "full_level_size": 1000,
            "strict_quality": False,
            "profiles": {},
        },
        "cache": {
            "path": str(tmp_path / "cache"),
            "autosave_every": 1,
        },
    }
    captured: dict[str, Any] = {}

    class FakeParser:
        def parse_args(self):
            return args

    class FakeBuilder:
        def __init__(self, config_path):
            captured["config_path"] = config_path

        def build(self, run):
            captured["run"] = run
            return [], []

        def export_deck(self, run, cards, media_files):
            _ = (run, cards, media_files)

    monkeypatch.setattr(main_module, "build_arg_parser", lambda: FakeParser())
    monkeypatch.setattr(main_module, "load_config", lambda path: config)
    monkeypatch.setattr(main_module, "DeckBuilder", FakeBuilder)

    exit_code = main_module.main()

    assert exit_code == 0
    assert captured["run"].seed == 99
