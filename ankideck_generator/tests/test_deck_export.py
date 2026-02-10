from pathlib import Path

from ankideck_generator.core.deck_builder import DeckBuilder
from ankideck_generator.core.models import CardData, RunConfig


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
    assert Path(run.output_path).exists()
