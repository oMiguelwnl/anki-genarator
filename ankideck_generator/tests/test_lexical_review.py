from __future__ import annotations

import pytest
from pydantic import ValidationError

from ankideck_generator.core.models import LexicalReviewResult


def _base_payload() -> dict[str, object]:
    return {
        "focus_word": "banco",
        "language": "es",
        "target_translation_language": "en",
        "accepted_sentence": "Me senté en el banco del parque.",
        "current_definition": "financial institution",
        "current_translation": "bank",
        "source_definition": "bench in a park or public place",
        "candidate_senses": [
            "financial institution",
            "bench in a park or public place",
        ],
        "winning_sense": "bench in a park or public place",
        "losing_sense_candidates": ["financial institution"],
        "reason_codes": ["definition_sentence_mismatch"],
        "confidence": 0.91,
        "before": {
            "definition": "financial institution",
            "translation": "bank",
        },
        "after": {
            "definition": "bench in a park or public place",
            "translation": "bench",
        },
        "selection_reasons": {
            "winning_sense": "park sentence context favors the seating sense"
        },
    }


def test_lexical_review_result_rejects_invalid_verdict() -> None:
    payload = _base_payload()
    payload["verdict"] = "human_review"

    with pytest.raises(ValidationError):
        LexicalReviewResult.model_validate(payload)


def test_lexical_review_contract_allows_correction_payload() -> None:
    payload = _base_payload()
    payload["verdict"] = "correct"
    payload["corrected_definition"] = "bench in a park or public place"
    payload["corrected_translation"] = "bench"

    result = LexicalReviewResult.model_validate(payload)

    assert result.verdict == "correct"
    assert result.corrected_definition == "bench in a park or public place"
    assert result.corrected_translation == "bench"
    assert result.winning_sense == "bench in a park or public place"
    assert result.losing_sense_candidates == ["financial institution"]
    assert result.reason_codes == ["definition_sentence_mismatch"]
    assert result.selection_reasons["winning_sense"].startswith("park sentence context")
