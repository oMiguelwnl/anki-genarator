import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ankideck_generator.core.evaluation import (
    BenchmarkCase,
    build_benchmark_bundle,
    build_experiment_fingerprint,
    load_benchmark_cases,
    summarize_benchmark_metrics,
)


def _benchmark_fixture_payload(name: str) -> list[dict[str, object]]:
    path = Path(__file__).resolve().parent / "fixtures" / "evaluation" / name
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    ("slice_name", "expected_values"),
    [
        ("language", {"es", "fr"}),
        ("ambiguity_slice", {"low", "medium", "high"}),
        ("difficulty_slice", {"beginner", "intermediate", "advanced"}),
    ],
)
def test_benchmark_fixture_coverage(slice_name: str, expected_values: set[str]) -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "evaluation" / "benchmark_cases.json"

    cases = load_benchmark_cases(fixture_path)

    assert all(isinstance(case, BenchmarkCase) for case in cases)
    assert {getattr(case, slice_name) for case in cases} >= expected_values
    assert all(case.quality_dimensions for case in cases)


def test_benchmark_fixture_malformed_payload_rejection(tmp_path: Path) -> None:
    payload = _benchmark_fixture_payload("benchmark_cases.json")
    payload[0].pop("ambiguity_slice")
    fixture_path = tmp_path / "benchmark_cases.json"
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_benchmark_cases(fixture_path)


def test_experiment_fingerprint_and_slice_summary_are_deterministic() -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "evaluation" / "benchmark_cases.json"
    cases = load_benchmark_cases(fixture_path)
    metrics = {
        "accepted_card_rate": 0.75,
        "duplicate_reject_rate": 0.25,
        "acceptance_quality": {
            "accepted_cards": 3,
            "clean_accepts": 2,
            "corrected_accepts": 1,
        },
        "duplicate_diagnostics": {"overall": {"exact": 0, "near": 1, "total": 1}},
        "review_diagnostics": {"queue_items": 1},
        "provider_counter": {"ai": 3, "googletrans": 2},
        "event_counter": {"sentence_ai_generate_hit": 2},
    }
    experiment = {
        "prompt_version": "evaluation-bundle-v1",
        "model": "offline-fixture",
        "run": {"language": "es", "mode": "test", "seed": 7},
        "validator": {"strict_quality": True},
    }

    fingerprint_one = build_experiment_fingerprint(experiment=experiment, benchmark_cases=cases)
    fingerprint_two = build_experiment_fingerprint(
        experiment={
            "validator": {"strict_quality": True},
            "run": {"seed": 7, "mode": "test", "language": "es"},
            "model": "offline-fixture",
            "prompt_version": "evaluation-bundle-v1",
        },
        benchmark_cases=list(reversed(cases)),
    )
    summary_one = summarize_benchmark_metrics(cases=cases, metrics=metrics)
    summary_two = summarize_benchmark_metrics(cases=list(reversed(cases)), metrics=metrics)

    assert fingerprint_one == fingerprint_two
    assert summary_one == summary_two
    assert summary_one["by_language"]["es"]["coverage"] == 2
    assert summary_one["by_ambiguity_slice"]["high"]["coverage"] == 1
    assert summary_one["quality_dimensions"]["duplicate_handling"] == 1


def test_benchmark_bundle_assembly_is_reproducible() -> None:
    fixture_path = Path(__file__).resolve().parent / "fixtures" / "evaluation" / "benchmark_cases.json"
    cases = load_benchmark_cases(fixture_path)
    metrics = {
        "accepted_card_rate": 0.75,
        "duplicate_reject_rate": 0.25,
        "acceptance_quality": {
            "accepted_cards": 3,
            "clean_accepts": 2,
            "corrected_accepts": 1,
        },
        "duplicate_diagnostics": {"overall": {"exact": 0, "near": 1, "total": 1}},
        "review_diagnostics": {"queue_items": 1},
        "provider_counter": {"ai": 3, "googletrans": 2},
        "event_counter": {"sentence_ai_generate_hit": 2},
    }
    experiment = {
        "prompt_version": "evaluation-bundle-v1",
        "model": "offline-fixture",
        "run": {"language": "es", "mode": "test", "seed": 7},
        "validator": {"strict_quality": True},
    }

    bundle_one = build_benchmark_bundle(cases=cases, metrics=metrics, experiment=experiment)
    bundle_two = build_benchmark_bundle(cases=list(cases), metrics=dict(metrics), experiment=dict(experiment))

    assert bundle_one == bundle_two
    assert bundle_one["benchmark_cases"] == len(cases)
    assert bundle_one["slice_summary"]["by_difficulty_slice"]["advanced"]["coverage"] == 1
    assert bundle_one["metrics"]["accepted_card_rate"] == 0.75
    assert bundle_one["experiment_fingerprint"]
