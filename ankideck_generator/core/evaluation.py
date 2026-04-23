from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, model_validator

from ..utils.file_utils import atomic_write_json


BenchmarkAmbiguitySlice = Literal["low", "medium", "high"]
BenchmarkDifficultySlice = Literal["beginner", "intermediate", "advanced"]
BenchmarkQualityDimension = Literal[
    "sentence_quality",
    "lexical_accuracy",
    "duplicate_handling",
    "acceptance",
]
BenchmarkExpectedOutcome = Literal["accept", "reject"]
ReleaseComparator = Literal[">", ">=", "<", "<=", "=="]

BENCHMARK_BUNDLE_SCHEMA_VERSION = "evaluation-benchmark-bundle-v1"
RELEASE_THRESHOLDS_SCHEMA_VERSION = "evaluation-release-thresholds-v1"


class BenchmarkCase(BaseModel):
    case_id: str
    language: str
    focus: str
    ambiguity_slice: BenchmarkAmbiguitySlice
    difficulty_slice: BenchmarkDifficultySlice
    quality_dimensions: list[BenchmarkQualityDimension] = Field(min_length=1)
    expected_outcome: BenchmarkExpectedOutcome
    expected_reject_reason: str | None = None
    notes: str | None = None


class ReleaseThresholdCheck(BaseModel):
    metric: str
    comparator: ReleaseComparator
    value: float
    description: str | None = None


class ReleaseThresholds(BaseModel):
    schema_version: str = RELEASE_THRESHOLDS_SCHEMA_VERSION
    milestone: str
    checks: list[ReleaseThresholdCheck] = Field(min_length=1)
    required_report_fields: list[str] = Field(min_length=1)


class AcceptanceQualityReport(BaseModel):
    accepted_cards: int
    accepted_card_rate: float
    clean_accepts: int | None = None
    corrected_accepts: int | None = None


class LatencyPerAcceptedCardReport(BaseModel):
    accepted_cards: int
    total_runtime_ms: int
    overall: float
    by_stage: dict[str, float] = Field(default_factory=dict)


class AIBudgetUsageReport(BaseModel):
    total_ai_calls: int
    by_stage: dict[str, int] = Field(default_factory=dict)


class RuntimeGuardrailsReport(BaseModel):
    stage_budget_exhausted: dict[str, int] = Field(default_factory=dict)
    preserve_evaluation_logs: bool


class QualityReportAdapter(BaseModel):
    generated_at: str | None = None
    language: str
    mode: str
    cards: int
    accepted_card_rate: float
    duplicate_reject_rate: float
    acceptance_quality: AcceptanceQualityReport
    duplicate_diagnostics: dict[str, Any]
    review_diagnostics: dict[str, Any]
    stage_latency_ms: dict[str, int] = Field(default_factory=dict)
    latency_per_accepted_card_ms: LatencyPerAcceptedCardReport
    ai_budget_usage: AIBudgetUsageReport
    runtime_guardrails: RuntimeGuardrailsReport

    @model_validator(mode="after")
    def validate_accepted_rate_alignment(self) -> "QualityReportAdapter":
        if round(self.acceptance_quality.accepted_card_rate, 4) != round(self.accepted_card_rate, 4):
            raise ValueError("accepted_card_rate must match acceptance_quality.accepted_card_rate")
        return self


def _canonicalize(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return _canonicalize(value.model_dump(mode="json", exclude_none=True))
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, (list, tuple, set)):
        items = [_canonicalize(item) for item in value]
        return sorted(items, key=_stable_json)
    return value


def _stable_json(value: Any) -> str:
    return json.dumps(
        _canonicalize(value),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def _digest(value: Any) -> str:
    return hashlib.sha1(_stable_json(value).encode("utf-8")).hexdigest()


def _read_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _get_path_value(payload: dict[str, Any], dotted_path: str) -> Any:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(dotted_path)
        current = current[part]
    return current


def _compare_threshold(actual: float, comparator: ReleaseComparator, expected: float) -> bool:
    if comparator == ">":
        return actual > expected
    if comparator == ">=":
        return actual >= expected
    if comparator == "<":
        return actual < expected
    if comparator == "<=":
        return actual <= expected
    if comparator == "==":
        return actual == expected
    raise ValueError(f"unsupported comparator: {comparator}")


def load_benchmark_cases(path: str | Path) -> list[BenchmarkCase]:
    payload = _read_json(path)
    if not isinstance(payload, list):
        raise TypeError("benchmark fixture must be a list of rows")
    return [BenchmarkCase.model_validate(item) for item in payload]


def load_release_thresholds(path: str | Path) -> dict[str, Any]:
    payload = ReleaseThresholds.model_validate(_read_json(path))
    return payload.model_dump(mode="json", exclude_none=True)


def load_quality_report(path: str | Path) -> dict[str, Any]:
    payload = QualityReportAdapter.model_validate(_read_json(path))
    return payload.model_dump(mode="json", exclude_none=True)


def summarize_benchmark_metrics(*, cases: list[BenchmarkCase], metrics: dict[str, Any]) -> dict[str, Any]:
    ordered_cases = sorted(cases, key=lambda case: case.case_id)

    def summarize_slice(attribute: str) -> dict[str, dict[str, int]]:
        summary: dict[str, dict[str, int]] = {}
        for case in ordered_cases:
            key = str(getattr(case, attribute))
            entry = summary.setdefault(
                key,
                {"coverage": 0, "accept_expected": 0, "reject_expected": 0},
            )
            entry["coverage"] += 1
            if case.expected_outcome == "accept":
                entry["accept_expected"] += 1
            else:
                entry["reject_expected"] += 1
        return {key: summary[key] for key in sorted(summary)}

    quality_dimensions: dict[str, int] = {}
    for case in ordered_cases:
        for dimension in case.quality_dimensions:
            quality_dimensions[str(dimension)] = quality_dimensions.get(str(dimension), 0) + 1

    return {
        "coverage": len(ordered_cases),
        "by_language": summarize_slice("language"),
        "by_ambiguity_slice": summarize_slice("ambiguity_slice"),
        "by_difficulty_slice": summarize_slice("difficulty_slice"),
        "quality_dimensions": {
            key: quality_dimensions[key] for key in sorted(quality_dimensions)
        },
        "metrics_snapshot": _canonicalize(metrics),
    }


def build_experiment_fingerprint(*, experiment: dict[str, Any], benchmark_cases: list[BenchmarkCase]) -> dict[str, str]:
    normalized_cases = [case.model_dump(mode="json", exclude_none=True) for case in benchmark_cases]
    return {
        "benchmark_cases": _digest(normalized_cases),
        "experiment": _digest(experiment),
        "digest": _digest(
            {
                "benchmark_cases": normalized_cases,
                "experiment": experiment,
            }
        ),
    }


def build_benchmark_bundle(*, cases: list[BenchmarkCase], metrics: dict[str, Any], experiment: dict[str, Any]) -> dict[str, Any]:
    normalized_cases = [case.model_dump(mode="json", exclude_none=True) for case in sorted(cases, key=lambda case: case.case_id)]
    return {
        "schema_version": BENCHMARK_BUNDLE_SCHEMA_VERSION,
        "benchmark_cases": len(normalized_cases),
        "coverage": normalized_cases,
        "experiment": _canonicalize(experiment),
        "experiment_fingerprint": build_experiment_fingerprint(
            experiment=experiment,
            benchmark_cases=cases,
        ),
        "slice_summary": summarize_benchmark_metrics(cases=cases, metrics=metrics),
        "metrics": _canonicalize(metrics),
    }


def evaluate_release_readiness(*, bundle: dict[str, Any], thresholds: dict[str, Any]) -> dict[str, Any]:
    threshold_model = ReleaseThresholds.model_validate(thresholds)
    runtime_metrics = dict(bundle.get("runtime_metrics") or {})
    metrics = dict(bundle.get("metrics") or {})
    required_surface = {**metrics, **runtime_metrics}

    missing_fields: list[str] = []
    for field_name in threshold_model.required_report_fields:
        try:
            _get_path_value(required_surface, field_name)
        except KeyError:
            missing_fields.append(field_name)

    if missing_fields:
        raise ValidationError.from_exception_data(
            "ReleaseReadinessReport",
            [
                {
                    "type": "missing",
                    "loc": (field_name,),
                    "msg": "required report field missing",
                    "input": required_surface,
                }
                for field_name in missing_fields
            ],
        )

    failed_checks: list[dict[str, Any]] = []
    passed_checks: list[dict[str, Any]] = []
    for check in threshold_model.checks:
        actual = _get_path_value(required_surface, check.metric)
        if not isinstance(actual, (int, float)):
            raise TypeError(f"threshold metric '{check.metric}' must resolve to a number")
        result = {
            "metric": check.metric,
            "comparator": check.comparator,
            "expected": check.value,
            "actual": float(actual),
            "description": check.description,
        }
        if _compare_threshold(float(actual), check.comparator, check.value):
            passed_checks.append(result)
        else:
            failed_checks.append(result)

    return {
        "generated_at": datetime.utcnow().isoformat(),
        "release_ready": not failed_checks,
        "threshold_source": bundle.get("threshold_source"),
        "experiment_fingerprint": bundle.get("experiment_fingerprint"),
        "metrics": metrics,
        "runtime_metrics": runtime_metrics,
        "slice_summary": bundle.get("slice_summary"),
        "passed_checks": passed_checks,
        "failed_checks": failed_checks,
        "missing_required_fields": missing_fields,
    }


def run_release_benchmark(
    *,
    benchmark_cases_path: str | Path,
    quality_report_path: str | Path,
    thresholds_path: str | Path,
    bundle_path: str | Path,
    experiment: dict[str, Any],
) -> dict[str, Any]:
    cases = load_benchmark_cases(benchmark_cases_path)
    thresholds = load_release_thresholds(thresholds_path)
    quality_report = load_quality_report(quality_report_path)

    metrics = {
        "accepted_card_rate": quality_report["accepted_card_rate"],
        "duplicate_reject_rate": quality_report["duplicate_reject_rate"],
        "acceptance_quality": quality_report["acceptance_quality"],
        "duplicate_diagnostics": quality_report["duplicate_diagnostics"],
        "review_diagnostics": quality_report["review_diagnostics"],
    }
    runtime_metrics = {
        "stage_latency_ms": quality_report["stage_latency_ms"],
        "latency_per_accepted_card_ms": quality_report["latency_per_accepted_card_ms"],
        "ai_budget_usage": quality_report["ai_budget_usage"],
        "runtime_guardrails": quality_report["runtime_guardrails"],
    }
    bundle = build_benchmark_bundle(cases=cases, metrics=metrics, experiment=experiment)
    bundle["runtime_metrics"] = _canonicalize(runtime_metrics)
    bundle["thresholds"] = _canonicalize(thresholds)
    bundle["threshold_source"] = Path(thresholds_path).as_posix()
    bundle["quality_report_source"] = Path(quality_report_path).as_posix()

    atomic_write_json(bundle_path, bundle)
    release_report = evaluate_release_readiness(bundle=bundle, thresholds=thresholds)

    return {
        "bundle_path": Path(bundle_path).as_posix(),
        "bundle": bundle,
        "release_report": release_report,
    }
