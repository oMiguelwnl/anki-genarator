from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from .models import CompatibilityFingerprint


def _canonicalize(value: Any) -> Any:
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


def build_compatibility_fingerprint(
    *,
    model: Any,
    prompt: Any,
    schema: Any,
    validator: Any,
) -> CompatibilityFingerprint:
    return CompatibilityFingerprint(
        model=_digest(model),
        prompt=_digest(prompt),
        schema_digest=_digest(schema),
        validator=_digest(validator),
        digest=_digest(
            {
                "model": model,
                "prompt": prompt,
                "schema": schema,
                "validator": validator,
            }
        ),
    )


def fingerprints_match(
    expected: CompatibilityFingerprint | dict[str, Any] | None,
    actual: CompatibilityFingerprint | dict[str, Any] | None,
) -> bool:
    if expected is None or actual is None:
        return False
    expected_fp = (
        expected
        if isinstance(expected, CompatibilityFingerprint)
        else CompatibilityFingerprint(**expected)
    )
    actual_fp = (
        actual if isinstance(actual, CompatibilityFingerprint) else CompatibilityFingerprint(**actual)
    )
    return expected_fp.model_dump() == actual_fp.model_dump()


def quarantine_name(path: str | Path, reason: str = "incompatible") -> Path:
    target = Path(path)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    suffix = target.suffix
    stem = target.name[: -len(suffix)] if suffix else target.name
    return target.with_name(f"{stem}.{reason}.{timestamp}{suffix}.quarantine")
