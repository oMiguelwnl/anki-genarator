import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ankideck_generator.core.evaluation import (
    BenchmarkCase,
    build_benchmark_bundle,
    build_experiment_fingerprint,
    evaluate_release_readiness,
    load_benchmark_cases,
    load_release_thresholds,
    run_release_benchmark,
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


def _quality_report_payload(*, accepted_card_rate: float = 0.75) -> dict[str, object]:
    return {
        "generated_at": "2026-04-22T19:30:00Z",
        "language": "es",
        "mode": "test",
        "cards": 3,
        "accepted_card_rate": accepted_card_rate,
        "duplicate_reject_rate": 0.25,
        "acceptance_quality": {
            "accepted_cards": 3,
            "accepted_card_rate": accepted_card_rate,
            "clean_accepts": 2,
            "corrected_accepts": 1,
        },
        "duplicate_diagnostics": {
            "overall": {"exact": 0, "near": 1, "total": 1},
            "by_level": {"1": {"exact": 0, "near": 1, "total": 1}},
            "exact_rejects": 0,
            "near_rejects": 1,
            "duplicate_reject_rate": 0.25,
        },
        "review_diagnostics": {
            "queue_items": 1,
            "top_reason_codes": {"duplicate_sentence_near": 1},
            "hard_validation_errors": {"duplicate_sentence_near": 1},
            "review_flags": {"definition_low_translation_alignment": 1},
        },
        "stage_latency_ms": {
            "sentence_generation": 240,
            "translation": 90,
            "lexical_review": 60,
        },
        "latency_per_accepted_card_ms": {
            "accepted_cards": 3,
            "total_runtime_ms": 390,
            "overall": 130.0,
            "by_stage": {
                "sentence_generation": 80.0,
                "translation": 30.0,
                "lexical_review": 20.0,
            },
        },
        "ai_budget_usage": {
            "total_ai_calls": 5,
            "by_stage": {
                "sentence_generation": 3,
                "lexical_review": 2,
            },
        },
        "runtime_guardrails": {
            "stage_budget_exhausted": {"lexical_review": 1},
            "preserve_evaluation_logs": True,
        },
    }


def _write_release_inputs(tmp_path: Path, *, accepted_card_rate: float = 0.75) -> tuple[Path, Path, Path]:
    fixtures_dir = Path(__file__).resolve().parent / "fixtures" / "evaluation"
    cases_path = fixtures_dir / "benchmark_cases.json"
    thresholds_path = fixtures_dir / "release_thresholds.json"
    report_path = tmp_path / "quality_report.json"
    report_path.write_text(
        json.dumps(_quality_report_payload(accepted_card_rate=accepted_card_rate)),
        encoding="utf-8",
    )
    return cases_path, thresholds_path, report_path


def test_release_threshold_fixture_requires_strict_accepted_card_rate() -> None:
    thresholds_path = Path(__file__).resolve().parent / "fixtures" / "evaluation" / "release_thresholds.json"

    thresholds = load_release_thresholds(thresholds_path)

    accepted_card_rate = next(
        threshold for threshold in thresholds["checks"] if threshold["metric"] == "accepted_card_rate"
    )
    assert accepted_card_rate["comparator"] == ">"
    assert accepted_card_rate["value"] == 0.6


def test_release_benchmark_runner_writes_reproducible_bundle(tmp_path: Path) -> None:
    cases_path, thresholds_path, report_path = _write_release_inputs(tmp_path)
    bundle_path = tmp_path / "benchmark_bundle.json"
    experiment = {
        "prompt_version": "evaluation-bundle-v1",
        "model": "offline-fixture",
        "run": {"language": "es", "mode": "test", "seed": 7},
        "validator": {"strict_quality": True},
    }

    result = run_release_benchmark(
        benchmark_cases_path=cases_path,
        quality_report_path=report_path,
        thresholds_path=thresholds_path,
        bundle_path=bundle_path,
        experiment=experiment,
    )

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert result["bundle_path"] == bundle_path.as_posix()
    assert bundle["schema_version"] == "evaluation-benchmark-bundle-v1"
    assert bundle["experiment_fingerprint"] == result["bundle"]["experiment_fingerprint"]
    assert bundle["runtime_metrics"]["latency_per_accepted_card_ms"]["overall"] == 130.0


def test_release_gate_fails_when_accepted_card_rate_is_not_strictly_above_threshold(tmp_path: Path) -> None:
    cases_path, thresholds_path, report_path = _write_release_inputs(
        tmp_path,
        accepted_card_rate=0.6,
    )
    bundle_path = tmp_path / "benchmark_bundle.json"
    report = run_release_benchmark(
        benchmark_cases_path=cases_path,
        quality_report_path=report_path,
        thresholds_path=thresholds_path,
        bundle_path=bundle_path,
        experiment={"model": "offline-fixture", "prompt_version": "evaluation-bundle-v1"},
    )["release_report"]

    assert report["release_ready"] is False
    assert report["failed_checks"][0]["metric"] == "accepted_card_rate"
    assert report["failed_checks"][0]["actual"] == 0.6


def test_release_gate_passes_and_preserves_fingerprint_and_latency(tmp_path: Path) -> None:
    cases_path, thresholds_path, report_path = _write_release_inputs(tmp_path, accepted_card_rate=0.61)
    thresholds = load_release_thresholds(thresholds_path)
    bundle = run_release_benchmark(
        benchmark_cases_path=cases_path,
        quality_report_path=report_path,
        thresholds_path=thresholds_path,
        bundle_path=tmp_path / "benchmark_bundle.json",
        experiment={
            "model": "offline-fixture",
            "prompt_version": "evaluation-bundle-v1",
            "run": {"language": "es", "mode": "test", "seed": 7},
        },
    )["bundle"]

    report = evaluate_release_readiness(bundle=bundle, thresholds=thresholds)

    assert report["release_ready"] is True
    assert report["experiment_fingerprint"] == bundle["experiment_fingerprint"]
    assert report["runtime_metrics"]["latency_per_accepted_card_ms"]["overall"] == 130.0
    assert report["slice_summary"]["by_language"]["es"]["coverage"] == 2


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload["checks"][0].pop("comparator"),
        lambda payload: payload["checks"][0].pop("value"),
    ],
)
def test_release_threshold_payload_validation_rejects_malformed_thresholds(
    tmp_path: Path,
    mutator,
) -> None:
    payload = _benchmark_fixture_payload("release_thresholds.json")
    mutator(payload)
    thresholds_path = tmp_path / "release_thresholds.json"
    thresholds_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_release_thresholds(thresholds_path)


@pytest.mark.parametrize(
    "mutator",
    [
        lambda payload: payload.pop("runtime_guardrails"),
        lambda payload: payload["latency_per_accepted_card_ms"].pop("overall"),
        lambda payload: payload["acceptance_quality"].pop("accepted_card_rate"),
    ],
)
def test_release_benchmark_rejects_malformed_quality_report_payloads(
    tmp_path: Path,
    mutator,
) -> None:
    cases_path, thresholds_path, report_path = _write_release_inputs(tmp_path)
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    mutator(payload)
    report_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        run_release_benchmark(
            benchmark_cases_path=cases_path,
            quality_report_path=report_path,
            thresholds_path=thresholds_path,
            bundle_path=tmp_path / "benchmark_bundle.json",
            experiment={"model": "offline-fixture", "prompt_version": "evaluation-bundle-v1"},
        )
