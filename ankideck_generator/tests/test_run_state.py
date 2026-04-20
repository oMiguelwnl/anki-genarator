import pytest
from pydantic import ValidationError

from ankideck_generator.core.models import CompatibilityFingerprint, LogRecord, ProgressState
from ankideck_generator.core.run_state import (
    build_compatibility_fingerprint,
    fingerprints_match,
    quarantine_name,
)


def test_log_record_rejects_unsupported_lifecycle_state() -> None:
    with pytest.raises(ValidationError):
        LogRecord(
            focus="bien",
            level=1,
            status="candidate",
            lifecycle_state="human-review",
        )


def test_progress_and_audit_models_preserve_reason_codes_and_snapshots() -> None:
    fingerprint = CompatibilityFingerprint(
        model="model-digest",
        prompt="prompt-digest",
        schema_digest="schema-digest",
        validator="validator-digest",
        digest="overall-digest",
    )
    state = ProgressState(
        language="es",
        mode="test",
        schema_version=1,
        compatibility_fingerprint=fingerprint,
    )
    log_record = LogRecord(
        focus="bien",
        level=1,
        status="accepted",
        lifecycle_state="accepted",
        reason_codes=["definition_corrected"],
        before={"definition": "old gloss"},
        after={"definition": "new gloss"},
        provider="openrouter",
        model="meta-llama/llama-3.1-8b-instruct",
    )

    assert state.compatibility_fingerprint == fingerprint
    assert log_record.reason_codes == ["definition_corrected"]
    assert log_record.before == {"definition": "old gloss"}
    assert log_record.after == {"definition": "new gloss"}
    assert log_record.provider == "openrouter"
    assert log_record.model == "meta-llama/llama-3.1-8b-instruct"


def test_build_compatibility_fingerprint_is_stable_for_equivalent_inputs() -> None:
    fingerprint_one = build_compatibility_fingerprint(
        model={"providers": ["groq", "openrouter"], "seed": 42},
        prompt={"versions": [2, 1], "policy": {"tone": "strict", "mode": "compact"}},
        schema={"card": {"required": ["definition", "sentence"]}},
        validator={"errors": ["b", "a"], "strict": True},
    )
    fingerprint_two = build_compatibility_fingerprint(
        model={"seed": 42, "providers": ["openrouter", "groq"]},
        prompt={"policy": {"mode": "compact", "tone": "strict"}, "versions": [1, 2]},
        schema={"card": {"required": ["sentence", "definition"]}},
        validator={"strict": True, "errors": ["a", "b"]},
    )

    assert fingerprints_match(fingerprint_one, fingerprint_two)


def test_build_compatibility_fingerprint_changes_when_versions_change() -> None:
    baseline = build_compatibility_fingerprint(
        model={"provider": "groq", "model": "llama-3.1-8b-instant"},
        prompt={"version": 1},
        schema={"version": 1},
        validator={"cache_validation_version": 4},
    )
    changed = build_compatibility_fingerprint(
        model={"provider": "groq", "model": "llama-3.1-8b-instant"},
        prompt={"version": 1},
        schema={"version": 2},
        validator={"cache_validation_version": 4},
    )

    assert not fingerprints_match(baseline, changed)


def test_quarantine_name_adds_reason_suffix() -> None:
    quarantined = quarantine_name("ankideck_generator/data/progress/es_test.json", "corrupt")

    assert quarantined.parent.as_posix().endswith("ankideck_generator/data/progress")
    assert quarantined.name.startswith("es_test.corrupt.")
    assert quarantined.name.endswith(".json.quarantine")
