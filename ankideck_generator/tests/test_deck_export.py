import json
import sqlite3
import zipfile
from pathlib import Path

from ankideck_generator.core.deck_builder import DeckBuilder
from ankideck_generator.core.models import ANKI_FIELD_ORDER_DEFAULT, CardData, RunConfig


def _read_model_from_apkg(apkg_path: Path, work_dir: Path) -> dict:
    with zipfile.ZipFile(apkg_path, "r") as archive:
        db_bytes = archive.read("collection.anki2")

    db_path = work_dir / "collection.extracted.anki2"
    db_path.write_bytes(db_bytes)
    with sqlite3.connect(str(db_path)) as conn:
        models = json.loads(conn.execute("select models from col").fetchone()[0])

    return next(iter(models.values()))


def test_deck_export(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = RunConfig(
        language="en",
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        wordfreq_language="en",
        timeout_sec=1,
        retries=0,
        seed=1,
        cache_path=str(tmp_path / "cache"),
        autosave_every=1,
    )
    card = CardData(
        focus="hello",
        index=1,
        ipa="",
        definition="greeting",
        sentence="hello there",
        translation="hello there",
        image="",
        audio="",
        level=1,
        language="en",
    )
    builder.export_deck(run, [card], [])

    output_path = Path(run.output_path)
    assert output_path.exists()

    model = _read_model_from_apkg(output_path, tmp_path)
    field_names = [field["name"] for field in model["flds"]]
    assert field_names == ANKI_FIELD_ORDER_DEFAULT

    qfmt = model["tmpls"][0]["qfmt"]
    afmt = model["tmpls"][0]["afmt"]
    css = model["css"]

    assert "{{Definitions}}" in qfmt
    assert "{{Exemple Sentence}}" in qfmt
    assert "{{#image}}" in qfmt
    assert "{{image}}" in qfmt
    assert "{{FrontSide}}" in afmt
    assert "document.getElementById(\"translation\").style.display = \"block\";" in afmt
    assert ".wordBlock" in css
    assert ".ipa" in css
    assert "_Inter-" not in css

    assert "{{Definitions 1}}" not in qfmt
    assert "{{Example Sentence}}" not in qfmt
    assert "{{#Image}}" not in qfmt
    assert "{{Image}}" not in qfmt


def test_deck_export_russian_uses_default_model(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    run = RunConfig(
        language="ru",
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck-ru.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        wordfreq_language="ru",
        timeout_sec=1,
        retries=0,
        seed=1,
        cache_path=str(tmp_path / "cache"),
        autosave_every=1,
    )
    card = CardData(
        focus="??????",
        index=1,
        ipa="/privet/",
        definition="greeting",
        sentence="??????, ??? ????",
        translation="hello, how are you",
        image="",
        audio="",
        level=1,
        language="ru",
    )
    builder.export_deck(run, [card], [])

    output_path = Path(run.output_path)
    assert output_path.exists()

    model = _read_model_from_apkg(output_path, tmp_path)
    field_names = [field["name"] for field in model["flds"]]
    assert field_names == ANKI_FIELD_ORDER_DEFAULT

    qfmt = model["tmpls"][0]["qfmt"]
    afmt = model["tmpls"][0]["afmt"]

    assert "{{Definitions}}" in qfmt
    assert "{{Spellings}}" not in qfmt
    assert "{{Example Word}}" not in qfmt
    assert "{{FrontSide}}" in afmt
    assert "document.getElementById(\"translation\").style.display = \"block\";" in afmt


def test_deck_export_cleans_generated_artifacts_after_export(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"] = {
        "enabled": True,
        "required": False,
        "output_dir": str(tmp_path / "audio"),
        "cleanup_after_export": True,
    }
    builder.config.setdefault("runtime", {})["cleanup_generated_artifacts"] = True
    builder._last_run_log_path = str(
        tmp_path / "ankideck_generator" / "data" / "logs" / "run-test.jsonl"
    )

    run = RunConfig(
        language="en",
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck-clean.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        wordfreq_language="en",
        timeout_sec=1,
        retries=0,
        seed=1,
        cache_path=str(tmp_path / "cache"),
        autosave_every=1,
    )
    card = CardData(
        focus="hello",
        index=1,
        ipa="",
        definition="greeting",
        sentence="hello there",
        translation="hello there",
        image="",
        audio="",
        level=1,
        language="en",
    )

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    media_path = audio_dir / "hello.mp3"
    media_path.write_bytes(b"audio")
    stale_audio_path = audio_dir / "stale.mp3"
    stale_audio_path.write_bytes(b"audio")

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "en_definitions.json").write_text("{}", encoding="utf-8")
    (cache_dir / "ru_definitions.json").write_text("{}", encoding="utf-8")

    progress_dir = tmp_path / "ankideck_generator" / "data" / "progress"
    progress_dir.mkdir(parents=True, exist_ok=True)
    (progress_dir / "en_test.json").write_text("{}", encoding="utf-8")

    log_path = Path(builder._last_run_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("{}", encoding="utf-8")

    builder.export_deck(run, [card], [str(media_path)])

    assert Path(run.output_path).exists()
    assert not audio_dir.exists()
    assert not cache_dir.exists()
    assert not progress_dir.exists()
    assert not log_path.parent.exists()


def test_deck_export_keeps_generated_artifacts_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)
    builder = DeckBuilder(str(Path(__file__).resolve().parents[2] / "config.yaml"))
    builder.config["audio"] = {
        "enabled": True,
        "required": False,
        "output_dir": str(tmp_path / "audio"),
        "cleanup_after_export": True,
    }
    builder.config.setdefault("runtime", {}).pop("cleanup_generated_artifacts", None)
    builder._last_run_log_path = str(
        tmp_path / "ankideck_generator" / "data" / "logs" / "run-test.jsonl"
    )

    run = RunConfig(
        language="en",
        mode="test",
        interactive=False,
        output_path=str(tmp_path / "deck-keep.apkg"),
        resume=False,
        level_size=1,
        target_translation="en",
        wordfreq_language="en",
        timeout_sec=1,
        retries=0,
        seed=1,
        cache_path=str(tmp_path / "cache"),
        autosave_every=1,
    )
    card = CardData(
        focus="hello",
        index=1,
        ipa="",
        definition="greeting",
        sentence="hello there",
        translation="hello there",
        image="",
        audio="",
        level=1,
        language="en",
    )

    audio_dir = tmp_path / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    media_path = audio_dir / "hello.mp3"
    media_path.write_bytes(b"audio")

    cache_dir = tmp_path / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / "en_definitions.json").write_text("{}", encoding="utf-8")

    progress_dir = tmp_path / "ankideck_generator" / "data" / "progress"
    progress_dir.mkdir(parents=True, exist_ok=True)
    (progress_dir / "en_test.json").write_text("{}", encoding="utf-8")

    log_path = Path(builder._last_run_log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("{}", encoding="utf-8")

    builder.export_deck(run, [card], [str(media_path)])

    assert Path(run.output_path).exists()
    assert audio_dir.exists()
    assert cache_dir.exists()
    assert progress_dir.exists()
    assert log_path.parent.exists()
