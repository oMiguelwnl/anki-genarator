import json
import sqlite3
import zipfile
from pathlib import Path

from ankideck_generator.core.deck_builder import DeckBuilder
from ankideck_generator.core.models import ANKI_FIELD_ORDER, CardData, RunConfig


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
    assert field_names == ANKI_FIELD_ORDER

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
