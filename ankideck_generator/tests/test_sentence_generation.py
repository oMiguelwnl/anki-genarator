import json
from pathlib import Path

from ankideck_generator.core.models import StructuredSentenceBatch
from ankideck_generator.core.providers import StructuredSentenceBatchResult
from ankideck_generator.core.sentence_generation import SentenceGenerationService


def _fixture_payload(name: str) -> dict[str, object]:
    path = (
        Path(__file__).resolve().parent
        / "fixtures"
        / "ai_sentence_candidates"
        / name
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_sentence_generation_service_rejects_focus_mismatch() -> None:
    payload = _fixture_payload("valid_batch.json")
    payload["candidates"][0]["target_form"] = "bueno"

    class FakeProviders:
        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=StructuredSentenceBatch.model_validate(payload),
                provider_name="ai",
                elapsed_ms=1,
            )

    service = SentenceGenerationService(FakeProviders())
    result = service.generate_candidates(
        focus_word="bien",
        language="es",
        level=1,
        requested_pos="adjective",
        requested_sense="in good condition or quality",
        min_words=4,
        max_words=10,
    )

    assert len(result.candidates) == 2
    assert result.rejected
    assert result.rejected[0].reason_codes == ["ai_target_form_mismatch"]


def test_sentence_generation_service_rejects_wrong_language_and_artificial_candidates() -> None:
    payload = _fixture_payload("valid_batch.json")
    payload["candidates"] = [
        {
            "sentence": "This word bien appears in this example.",
            "target_form": "bien",
            "requested_pos": "adjective",
            "requested_sense": "in good condition or quality",
            "validation_signals": ["meta_example"],
            "rationale": "meta_example",
        },
        {
            "sentence": "This sentence uses bien in English now.",
            "target_form": "bien",
            "requested_pos": "adjective",
            "requested_sense": "in good condition or quality",
            "validation_signals": ["wrong_language"],
            "rationale": "wrong_language",
        },
        {
            "sentence": "Hoy bien llego con Maria a Paris.",
            "target_form": "bien",
            "requested_pos": "adjective",
            "requested_sense": "in good condition or quality",
            "validation_signals": ["proper_nouns"],
            "rationale": "proper_noun_heavy",
        },
    ]

    class FakeProviders:
        def sentence_ai_candidates(self, *args, **kwargs):
            _ = (args, kwargs)
            return StructuredSentenceBatchResult(
                batch=StructuredSentenceBatch.model_validate(payload),
                provider_name="ai",
                elapsed_ms=1,
            )

    service = SentenceGenerationService(FakeProviders())
    result = service.generate_candidates(
        focus_word="bien",
        language="es",
        level=1,
        requested_pos="adjective",
        requested_sense="in good condition or quality",
        min_words=4,
        max_words=10,
    )

    assert result.candidates == []
    assert result.status == "low_yield"
    assert sorted(result.failure_reasons) == [
        "ai_meta_example",
        "ai_proper_noun_heavy",
        "ai_wrong_language",
    ]
