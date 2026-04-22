from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


BenchmarkAmbiguitySlice = Literal["low", "medium", "high"]
BenchmarkDifficultySlice = Literal["beginner", "intermediate", "advanced"]
BenchmarkQualityDimension = Literal[
    "sentence_quality",
    "lexical_accuracy",
    "duplicate_handling",
    "acceptance",
]
BenchmarkExpectedOutcome = Literal["accept", "reject"]

BENCHMARK_BUNDLE_SCHEMA_VERSION = "evaluation-benchmark-bundle-v1"


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


def load_benchmark_cases(path: str | Path) -> list[BenchmarkCase]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise TypeError("benchmark fixture must be a list of rows")
    return [BenchmarkCase.model_validate(item) for item in payload]


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
