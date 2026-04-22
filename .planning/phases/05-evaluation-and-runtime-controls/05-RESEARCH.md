# Phase 05: evaluation-and-runtime-controls - Research

**Researched:** 2026-04-22
**Domain:** Reproducible evaluation, runtime metrics, and AI budget enforcement for the existing Python CLI pipeline [VERIFIED: ROADMAP.md, REQUIREMENTS.md]
**Confidence:** MEDIUM

## User Constraints

- No phase-specific `05-CONTEXT.md` exists, so there are no locked discuss-phase decisions to copy verbatim. [VERIFIED: phase init]
- Phase goal: add reproducible evaluation, acceptance thresholds, and operational guardrails without breaking accepted-only export behavior. [VERIFIED: ROADMAP.md]
- Phase requirements in scope: `QUAL-04`, `EVAL-01`, `EVAL-02`, `EVAL-04`. [VERIFIED: ROADMAP.md, REQUIREMENTS.md]
- Python `3.11` is required. [VERIFIED: AGENTS.md, local Python version]
- Main orchestration is in `ankideck_generator/core/deck_builder.py`; provider fallback / HTTP / TTS logic is in `ankideck_generator/core/providers.py`. [VERIFIED: AGENTS.md]
- `pytest` is the only verified automated check. [VERIFIED: AGENTS.md]
- Prefer policy/config edits over hardcoded cleanup rules when possible. [VERIFIED: AGENTS.md]
- Run from the repo root; generated artifacts under `output/` and `ankideck_generator/data/{audio,cache,logs,progress}` are runtime outputs, not hand-maintained source files. [VERIFIED: AGENTS.md]

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| QUAL-04 | Accepted-card rate improves above 60% on the defined benchmark or release dataset. [VERIFIED: REQUIREMENTS.md] | Define a typed benchmark dataset, deterministic run fingerprint, and release-gate report that computes accepted-card rate from the same accepted-only pipeline outputs. [VERIFIED: REQUIREMENTS.md, deck_builder.py] |
| EVAL-01 | Include a representative benchmark/gold set segmented by language, ambiguity, and frequency or difficulty slice. [VERIFIED: REQUIREMENTS.md] | Use a repo-stored JSON/JSONL fixture dataset plus pytest parametrization and per-slice aggregation. [VERIFIED: codebase read, pytest docs] |
| EVAL-02 | Prompt/model/validator changes must be comparable through reproducible quality and runtime metrics. [VERIFIED: REQUIREMENTS.md] | Extend existing compatibility fingerprinting, stage timings, run logs, and quality outputs with experiment metadata and stable metric summaries. [VERIFIED: deck_builder.py, logger.py, run_state.py] |
| EVAL-04 | Runtime enforces configurable AI call budgets or guardrails. [VERIFIED: REQUIREMENTS.md] | Extend current `ai_max_calls_per_word`, `ai_max_calls_per_field`, `sentence_ai_attempts`, and attempt-cap seams into explicit per-stage reporting and lexical-review coverage. [VERIFIED: config.yaml, main.py, deck_builder.py, providers.py] |

## Summary

The codebase already has most of the plumbing needed for Phase 05: deterministic run configuration via `RunConfig`, compatibility fingerprints for resume safety, structured per-card JSONL logging, per-stage elapsed timing aggregation, and artifact writers for `quality_report.json` and `review_queue.json`. [VERIFIED: main.py, deck_builder.py, logger.py, run_state.py] The missing layer is not a brand-new framework; it is a thin evaluation/reporting slice that turns those existing signals into benchmark-grade outputs and release gates. [VERIFIED: ROADMAP.md, deck_builder.py]

The most important planning fact is that runtime guardrails already exist, but only partially. The pipeline already limits AI usage with `ai_max_calls_per_word`, `ai_max_calls_per_field`, `sentence_ai_attempts`, and `max_attempts_per_level`; however, those limits are not yet surfaced as a first-class evaluation story, and lexical review is not routed through the same `allow_ai(...)` budget gate or a dedicated `lexical_review_ms` timing bucket. [VERIFIED: config.yaml, main.py, deck_builder.py, providers.py, lexical_review.py] Phase 05 should therefore extend current seams instead of introducing a second budget subsystem. [VERIFIED: codebase read]

The other major planning constraint is artifact lifecycle. The repo writes JSONL run logs under `ankideck_generator/data/logs`, but `runtime.cleanup_generated_artifacts: true` removes generated logs, cache, progress, and audio after export. [VERIFIED: AGENTS.md, config.yaml, deck_builder.py] A benchmark harness that wants reproducible runtime metrics must either harvest logs before export cleanup or run in a mode/config that preserves them. [VERIFIED: deck_builder.py]

**Primary recommendation:** Build Phase 05 as a typed benchmark/evaluation module plus targeted `deck_builder`/`main` extensions that reuse existing run logs, quality-report artifacts, and budget seams instead of inventing a parallel harness. [VERIFIED: codebase read]

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Benchmark dataset definition | Filesystem / repo fixtures | API / Backend | The benchmark should live as versioned repo data so results are reproducible across runs. [VERIFIED: REQUIREMENTS.md, pytest tmp_path docs] |
| Evaluation harness | API / Backend | Filesystem / repo fixtures | The harness must call Python orchestration code and aggregate outputs from runtime artifacts. [VERIFIED: main.py, deck_builder.py] |
| Runtime metric capture | API / Backend | Filesystem / logs | Stage timings, event counters, and provider outcomes are recorded inside `DeckBuilder` and serialized to JSON/JSONL. [VERIFIED: deck_builder.py, logger.py] |
| AI budget enforcement | API / Backend | Config | AI call caps are enforced inside text-generation orchestration and `RunConfig`/`config.yaml` today. [VERIFIED: config.yaml, main.py, deck_builder.py, providers.py] |
| Release-readiness reporting | API / Backend | Filesystem / output artifacts | `quality_report.json` is already the quality artifact surface and should remain the main machine-readable gate output. [VERIFIED: deck_builder.py, ROADMAP.md] |

## Project Constraints (from AGENTS.md)

- Use Python `3.11`. [VERIFIED: AGENTS.md]
- Install deps with `python -m pip install -r requirements.txt`. [VERIFIED: AGENTS.md]
- Run the CLI from the repo root. [VERIFIED: AGENTS.md]
- Verified automated commands are `python -m pytest -q`, `python -m pytest ankideck_generator/tests/test_main.py -q`, and `python -m pytest ankideck_generator/tests/test_deck_export.py::test_deck_export -q`. [VERIFIED: AGENTS.md]
- No repo-local lint/typecheck/formatter/pre-commit contract exists; `pytest` is the only verified automation surface. [VERIFIED: AGENTS.md]
- Preserve provider fallback order. [VERIFIED: AGENTS.md]
- Prefer definition-policy/config edits over hardcoded cleanup rules when possible. [VERIFIED: AGENTS.md]
- Treat `output/` and `ankideck_generator/data/{audio,cache,logs,progress}` as generated artifacts. [VERIFIED: AGENTS.md]
- `runtime.strict_quality` defaults to `true`, and preflight fails without AI provider endpoint/model/key configuration. [VERIFIED: AGENTS.md, config.yaml, main.py, providers.py]
- `runtime.cleanup_generated_artifacts: true` deletes generated cache/progress/log/audio after export. [VERIFIED: AGENTS.md, config.yaml, deck_builder.py]

## Standard Stack

### Core
| Library / Module | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11.9 local / `3.11` required | Runtime for the CLI and any evaluation helpers | Required by project instructions and already installed. [VERIFIED: AGENTS.md, local Python version] |
| `pytest` | 9.0.2 local / `>=7.4.0` in requirements | Benchmark harness execution, fixture parametrization, artifact assertions | It is the repo's only verified automated test surface, and official docs support parametrized cases plus temporary directories. [VERIFIED: AGENTS.md, requirements.txt, local pytest version, pytest docs] |
| `pydantic` | 2.12.5 local / `>=2.0.0` in requirements | Typed benchmark case/result models and reproducible validation of evaluation inputs/outputs | The repo already uses `BaseModel`, `model_validate()`, and `model_json_schema()` for runtime contracts and fingerprints. [VERIFIED: requirements.txt, local pydantic version, models.py, deck_builder.py, pydantic docs] |
| Existing JSON/JSONL artifact flow (`atomic_write_json`, `JsonLogger`) | repo-local | Machine-readable outputs for benchmark results, quality reports, and per-card logs | The codebase already serializes `quality_report.json`, `review_queue.json`, `metadata.json`, and JSONL run logs this way. [VERIFIED: deck_builder.py, logger.py] |

### Supporting
| Library / Module | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pathlib` / stdlib JSON tooling | Python 3.11 stdlib | File-backed benchmark fixtures and report paths | Use for repo fixtures and deterministic output paths; `tmp_path` also returns `pathlib.Path`. [VERIFIED: main.py, logger.py, pytest tmp_path docs] |
| Existing `RunConfig` + compatibility fingerprinting | repo-local | Stable experiment identity for prompt/model/validator comparisons | Use whenever a report needs to say exactly which runtime/prompt/schema/validator combination produced a result. [VERIFIED: main.py, deck_builder.py, run_state.py] |
| Existing `BuildStats` / `LogRecord` counters | repo-local | Runtime metrics aggregation and per-card provenance | Use for extending metrics instead of adding a second in-memory metrics object. [VERIFIED: models.py, deck_builder.py] |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pytest`-driven benchmark harness | A custom standalone benchmark runner script | A custom runner would duplicate fixture selection, tmp directories, and assertion/report ergonomics that `pytest` already provides here. [VERIFIED: AGENTS.md, pytest docs] |
| JSON/JSONL benchmark fixtures | CSV or ad-hoc text files | JSON aligns with existing artifact formats and Pydantic validation; CSV would need extra normalization for nested evidence and slice labels. [VERIFIED: deck_builder.py, logger.py, models.py] |
| Extending existing budget seams | A new external quota manager | Existing call caps already live in `RunConfig`, `main.py`, and `_process_word_textual()`, so a second system would drift. [VERIFIED: config.yaml, main.py, deck_builder.py] |

**Installation:**
```bash
python -m pip install -r requirements.txt
```

**Version verification:** Local environment verification found Python `3.11.9`, `pytest 9.0.2`, `pydantic 2.12.5`, `requests 2.32.5`, `genanki 0.13.1`, `wordfreq 3.1.1`, `googletrans 4.0.0-rc.1`, and `requests-mock 1.12.1`. [VERIFIED: local Python metadata and version commands]

## Architecture Patterns

### System Architecture Diagram

```text
Benchmark fixture JSON/JSONL
        |
        v
Typed BenchmarkCase model (Pydantic)
        |
        v
Evaluation runner / pytest parametrization
        |
        +--> RunConfig override set (seed, mode, budgets, output paths)
        |
        v
DeckBuilder / ProviderManager pipeline
        |
        +--> per-card JSONL log records
        +--> BuildStats counters
        +--> quality_report.json / review_queue.json / metadata.json
        |
        v
Metric aggregator
        |
        +--> per-slice quality metrics
        +--> runtime metrics per accepted card
        +--> release-readiness verdict vs thresholds
```

### Recommended Project Structure
```text
ankideck_generator/
├── core/
│   ├── evaluation.py          # benchmark runner + metric aggregation
│   ├── models.py              # BenchmarkCase / BenchmarkResult / BudgetReport models
│   └── deck_builder.py        # extra timings, provenance, guardrail hooks
tests/
├── fixtures/
│   └── evaluation/
│       └── benchmark_cases.json
├── test_evaluation.py         # fixture-backed benchmark and threshold tests
└── test_deck_builder.py       # budget/report regression tests
```

### Pattern 1: Fixture-backed benchmark slices
**What:** Store benchmark cases in repo fixtures and run them through parametrized pytest tests so language, ambiguity, and level slices are explicit and reproducible. [VERIFIED: REQUIREMENTS.md, pytest docs]
**When to use:** For `EVAL-01`, release gates, and prompt/model regression comparisons. [VERIFIED: REQUIREMENTS.md]
**Example:**
```python
# Source: https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest

@pytest.mark.parametrize("test_input,expected", [("3+5", 8), ("2+4", 6)])
def test_eval(test_input, expected):
    assert eval(test_input) == expected
```

### Pattern 2: Typed evaluation contracts
**What:** Validate benchmark rows and result payloads with Pydantic models before the harness uses them. [VERIFIED: models.py, pydantic docs]
**When to use:** For benchmark case loading, threshold config parsing, and persisted report schema. [VERIFIED: codebase read]
**Example:**
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel

class User(BaseModel):
    id: int
    name: str = 'Jane Doe'

user = User.model_validate({'id': 123, 'name': 'James'})
assert user.model_dump() == {'id': 123, 'name': 'James'}
```

### Pattern 3: Reuse `BuildStats`/`LogRecord` as the metrics backbone
**What:** Extend current counters and stage timings, then aggregate from those same records into evaluation output. [VERIFIED: models.py, deck_builder.py]
**When to use:** For latency, provider error rate, discard reasons, and accepted-card-rate reporting. [VERIFIED: deck_builder.py]

### Anti-Patterns to Avoid
- **Second metrics pipeline:** Do not create a separate runtime-metrics collector disconnected from `LogRecord`, `BuildStats`, and `quality_report.json`. [VERIFIED: deck_builder.py]
- **Benchmark data hidden in generated outputs:** Do not treat `output/quality_report.json` from ad-hoc runs as the canonical gold set; keep benchmark cases versioned in the repo. [VERIFIED: REQUIREMENTS.md, AGENTS.md]
- **Live-log dependency after export:** Do not assume `ankideck_generator/data/logs/run-*.jsonl` will survive export when cleanup is enabled. [VERIFIED: AGENTS.md, config.yaml, deck_builder.py]
- **New budget system for one stage:** Do not bolt lexical review onto a separate quota implementation; bring it under the same budget/reporting shape as other AI stages. [VERIFIED: deck_builder.py, providers.py, lexical_review.py]

## Likely Touchpoints

- `ankideck_generator/core/deck_builder.py` — current metrics aggregation, `LogRecord` recording, accepted-only export filter, review queue serialization, and quality report writing all live here. [VERIFIED: deck_builder.py]
- `ankideck_generator/core/providers.py` — provider timings, AI request rotation, and `ai_budget_exceeded` behavior originate here. [VERIFIED: providers.py]
- `ankideck_generator/core/lexical_review.py` — lexical review consumes transport results but currently does not surface a dedicated timing/budget seam. [VERIFIED: lexical_review.py, deck_builder.py]
- `ankideck_generator/core/models.py` — best place to add typed benchmark and threshold models because runtime contracts already live here. [VERIFIED: models.py]
- `ankideck_generator/main.py` — current place where runtime config becomes `RunConfig`; any new evaluation/budget flags or profile plumbing must pass through here. [VERIFIED: main.py]
- `ankideck_generator/tests/test_deck_builder.py` and a new `ankideck_generator/tests/test_evaluation.py` — current artifact/report regressions already live in the former, and Phase 05 needs dedicated evaluation regressions. [VERIFIED: test_deck_builder.py, AGENTS.md]

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Benchmark runner orchestration | A bespoke mini test framework | `pytest` parametrization + `tmp_path` + targeted assertions | The repo already relies on `pytest`, and official docs cover exactly the needed patterns. [VERIFIED: AGENTS.md, pytest docs] |
| Benchmark row validation | Loose dict parsing scattered across the harness | Pydantic models with `model_validate()` | The codebase already treats runtime contracts this way, which keeps schema drift visible. [VERIFIED: models.py, pydantic docs] |
| Runtime metrics storage | A second report file unrelated to existing outputs | Extend `quality_report.json`, `review_queue.json`, and JSONL logs | Existing downstream artifacts already carry quality/provenance data. [VERIFIED: deck_builder.py, logger.py] |
| AI guardrails | A new quota service divorced from `RunConfig` | Extend existing call caps and attempt caps | Budgets already exist in config and orchestration, so reuse reduces drift. [VERIFIED: config.yaml, main.py, deck_builder.py] |

**Key insight:** Phase 05 is mostly an integration-and-observability phase, not a net-new algorithm phase. [VERIFIED: ROADMAP.md, codebase read]

## Common Pitfalls

### Pitfall 1: Losing the evidence you meant to measure
**What goes wrong:** The harness exports a deck, then tries to read JSONL logs that cleanup has already deleted. [VERIFIED: deck_builder.py, AGENTS.md]
**Why it happens:** `export_deck()` triggers `_cleanup_run_artifacts()` when `runtime.cleanup_generated_artifacts` is true. [VERIFIED: deck_builder.py, config.yaml]
**How to avoid:** Either disable cleanup for evaluation runs, or aggregate/copy runtime logs before export cleanup executes. [VERIFIED: deck_builder.py]
**Warning signs:** `quality_report.json` exists, but `ankideck_generator/data/logs` is missing after the run. [VERIFIED: deck_builder.py]

### Pitfall 2: Reporting only partial runtime cost
**What goes wrong:** The report claims per-stage latency/cost coverage, but lexical review is absent from stage timings and AI budget counters. [VERIFIED: deck_builder.py, lexical_review.py]
**Why it happens:** Sentence/translation/IPA stages flow through `trace_result(...)`, while lexical review is called via `LexicalReviewService(providers).review(...)` without a dedicated `stage_key` or `allow_ai(...)` gate. [VERIFIED: deck_builder.py, lexical_review.py]
**How to avoid:** Add explicit lexical-review stage timing, AI-call accounting, and report fields before defining milestone thresholds. [VERIFIED: deck_builder.py, lexical_review.py]
**Warning signs:** `quality_report.json` shows stage timings, but no lexical-review bucket, and budget exhaustions never mention review. [VERIFIED: deck_builder.py]

### Pitfall 3: Declaring reproducibility without stable experiment identity
**What goes wrong:** Two benchmark runs are compared even though prompt/model/validator inputs changed invisibly. [VERIFIED: REQUIREMENTS.md, deck_builder.py, run_state.py]
**Why it happens:** The project has compatibility fingerprints for resume safety, but current user-facing outputs do not include that fingerprint or a complete model/prompt provenance story for all AI stages. [VERIFIED: deck_builder.py, models.py, providers.py]
**How to avoid:** Emit an experiment fingerprint and the relevant prompt/schema/runtime version fields into the evaluation report. [VERIFIED: deck_builder.py, run_state.py]
**Warning signs:** The harness can compute acceptance rate deltas, but cannot answer “what changed?” from the artifact alone. [VERIFIED: codebase read]

### Pitfall 4: Gold-set leakage
**What goes wrong:** The benchmark rewards whatever the current validator already likes instead of independently checking quality. [ASSUMED]
**Why it happens:** If expected labels are derived only from current outputs, the evaluation becomes self-confirming. [ASSUMED]
**How to avoid:** Keep benchmark annotations human-authored or at least review-seeded, and separate expected labels from runtime-generated artifacts. [ASSUMED]
**Warning signs:** Every benchmark “improvement” exactly mirrors a validator tweak with no external review step. [ASSUMED]

## Code Examples

Verified patterns from official sources:

### Parametrized benchmark cases
```python
# Source: https://docs.pytest.org/en/stable/how-to/parametrize.html
import pytest

@pytest.mark.parametrize("n,expected", [(1, 2), (3, 4)])
def test_simple_case(n, expected):
    assert n + 1 == expected
```

### Isolated runtime artifact directories
```python
# Source: https://docs.pytest.org/en/stable/how-to/tmp_path.html
def test_create_file(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    p = d / "hello.txt"
    p.write_text("content", encoding="utf-8")
    assert p.read_text(encoding="utf-8") == "content"
```

### Typed result validation
```python
# Source: https://docs.pydantic.dev/latest/concepts/models/
from pydantic import BaseModel

class Result(BaseModel):
    accepted_card_rate: float
    duplicate_reject_rate: float

payload = Result.model_validate({"accepted_card_rate": 0.61, "duplicate_reject_rate": 0.08})
assert payload.model_dump() == {"accepted_card_rate": 0.61, "duplicate_reject_rate": 0.08}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Manual or ad-hoc run inspection | Repo-stored benchmark cases plus machine-readable release thresholds | Planned in Phase 05. [VERIFIED: ROADMAP.md] | Makes `QUAL-04` auditable instead of anecdotal. [VERIFIED: REQUIREMENTS.md] |
| Raw prompt changes with partial provenance | Fingerprinted experiment reports tied to prompt/schema/validator/runtime inputs | Compatibility fingerprinting already exists; report surfacing is still missing. [VERIFIED: deck_builder.py, run_state.py] | Makes prompt/model comparisons reproducible. [VERIFIED: REQUIREMENTS.md, deck_builder.py] |
| Call caps enforced silently inside orchestration | Guardrails reported per stage and included in evaluation output | Current caps exist now; reporting is the missing piece. [VERIFIED: config.yaml, main.py, deck_builder.py] | Lets planners set budgets using observed behavior instead of guesses. [VERIFIED: codebase read] |

**Deprecated/outdated:**
- Treating acceptance-rate progress as a human-read console summary is insufficient for the milestone gate because Phase 05 explicitly requires benchmark-driven reproducible metrics. [VERIFIED: ROADMAP.md, REQUIREMENTS.md, deck_builder.py]

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Gold-set leakage is a material risk for this project and needs an explicit separation between expected labels and runtime outputs. | Common Pitfalls | Could over-design annotation workflow if the team is comfortable with validator-relative benchmarks. |

## Open Questions (RESOLVED)

1. **Resolved: Phase 05 stays test-driven/module-driven unless a lightweight CLI wrapper proves necessary later.**
   - What we know: `main.py` currently exposes only `test/full/build` generation flows and no evaluation subcommand. [VERIFIED: main.py]
   - Resolved decision: Keep Wave 1 implementation test/module-driven first; add CLI exposure only if a real operator workflow requires it. [VERIFIED: main.py]

2. **Resolved: The canonical benchmark label source should be a repo-backed benchmark fixture.**
   - What we know: Requirements demand slices by language, ambiguity, and difficulty/frequency, but do not define annotation format. [VERIFIED: REQUIREMENTS.md]
   - Resolved decision: Store labels in a versioned repo fixture such as `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` so threshold wiring and reproducibility share one source of truth. [VERIFIED: REQUIREMENTS.md]

3. **Resolved: Live-provider evaluation is a manual follow-up in a credentialed environment; local work stays offline-first.**
   - What we know: local `ANKI_AI_KEY`, `GROQ_API_KEY_1`, and `GROQ_API_KEY_2` are unset, while strict-quality preflight requires configured AI credentials. [VERIFIED: local env check, AGENTS.md, providers.py, main.py]
   - Resolved decision: Plan for two layers: offline fixture/unit verification now, and live benchmark execution only where credentials exist. [VERIFIED: local env check, providers.py]

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python | CLI + evaluation helpers | ✓ | 3.11.9 | — |
| `pytest` | Verified automation and benchmark harness | ✓ | 9.0.2 | — |
| `pydantic` | Typed benchmark/result contracts | ✓ | 2.12.5 | — |
| AI provider credentials (`ANKI_AI_KEY` / `GROQ_API_KEY_*`) | Strict-quality live benchmark runs | ✗ in this local shell | — | Offline fake-provider tests only |

**Missing dependencies with no fallback:**
- None for offline implementation and test work. [VERIFIED: local env check, AGENTS.md]

**Missing dependencies with fallback:**
- Live AI credentials are missing locally; planner should use stubbed/provider-fake tests for harness logic and reserve true end-to-end benchmark execution for a credentialed environment. [VERIFIED: local env check, AGENTS.md, providers.py]

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | `pytest 9.0.2` [VERIFIED: local pytest version] |
| Config file | none found; rely on direct `pytest` invocation. [VERIFIED: AGENTS.md] |
| Quick run command | `python -m pytest ankideck_generator/tests/test_evaluation.py -q` [ASSUMED] |
| Full suite command | `python -m pytest -q` [VERIFIED: AGENTS.md] |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| QUAL-04 | Benchmark report computes accepted-card rate and enforces `> 0.60` milestone threshold | unit / artifact | `python -m pytest ankideck_generator/tests/test_evaluation.py -q -k accepted_card_rate` [ASSUMED] | ❌ Wave 0 |
| EVAL-01 | Benchmark fixture covers language, ambiguity, and level slices | unit | `python -m pytest ankideck_generator/tests/test_evaluation.py -q -k benchmark_fixture` [ASSUMED] | ❌ Wave 0 |
| EVAL-02 | Prompt/model/validator changes produce reproducible metric bundles with stable experiment identity | unit | `python -m pytest ankideck_generator/tests/test_evaluation.py -q -k fingerprint` [ASSUMED] | ❌ Wave 0 |
| EVAL-04 | AI budgets stop runaway calls and are visible in reports | unit | `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k budget` [ASSUMED] | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest ankideck_generator/tests/test_evaluation.py -q` [ASSUMED]
- **Per wave merge:** `python -m pytest -q` [VERIFIED: AGENTS.md]
- **Phase gate:** Full suite green before `/gsd-verify-work`. [VERIFIED: .planning/config.json]

### Wave 0 Gaps
- [ ] `ankideck_generator/tests/test_evaluation.py` — benchmark fixture loading, slice aggregation, threshold gating. [VERIFIED: codebase glob]
- [ ] `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` — representative gold-set fixture. [VERIFIED: codebase glob]
- [ ] `ankideck_generator/tests/test_deck_builder.py` budget-specific regressions for lexical review timing/budget surfacing. [VERIFIED: codebase grep]
- [ ] Evaluation report schema tests if a new artifact file is added beyond `quality_report.json`. [ASSUMED]

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | CLI evaluation/reporting phase does not add user auth. [ASSUMED] |
| V3 Session Management | no | CLI evaluation/reporting phase does not add session state. [ASSUMED] |
| V4 Access Control | no | This phase is local-process/reporting scoped, not multi-user authorization scoped. [ASSUMED] |
| V5 Input Validation | yes | Validate benchmark fixtures, threshold config, and report payloads with Pydantic models. [VERIFIED: models.py, pydantic docs] |
| V6 Cryptography | no | No phase requirement introduces new cryptographic handling. [ASSUMED] |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Runaway AI retries / quota exhaustion | Denial of Service | Reuse and extend `ai_max_calls_per_word`, `ai_max_calls_per_field`, `sentence_ai_attempts`, and `max_attempts_per_level`; report exhaustions explicitly. [VERIFIED: config.yaml, main.py, deck_builder.py, providers.py] |
| Malformed benchmark/report payloads | Tampering | Validate file-backed inputs/outputs with Pydantic before execution or persistence. [VERIFIED: models.py, pydantic docs] |
| Prompt/report provenance ambiguity | Repudiation | Emit compatibility fingerprint plus prompt/schema/runtime identifiers into evaluation artifacts. [VERIFIED: deck_builder.py, run_state.py] |

## Sources

### Primary (HIGH confidence)
- Codebase inspection — `ankideck_generator/core/deck_builder.py`, `providers.py`, `lexical_review.py`, `models.py`, `run_state.py`, `main.py`, `utils/logger.py`, `tests/test_deck_builder.py`, `tests/test_main.py`.
- `AGENTS.md` — project commands, runtime gotchas, tested behavior.
- `config.yaml` and `requirements.txt` — runtime caps, paths, dependency floors.
- Official pytest docs — https://docs.pytest.org/en/stable/how-to/parametrize.html ; https://docs.pytest.org/en/stable/how-to/tmp_path.html
- Official Pydantic docs — https://docs.pydantic.dev/latest/concepts/models/

### Secondary (MEDIUM confidence)
- Local environment commands — `python --version`, `python -m pytest --version`, package metadata queries, and env-presence checks.

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - existing stack and installed versions were directly verified. [VERIFIED: AGENTS.md, requirements.txt, local version commands]
- Architecture: HIGH - touchpoints and current seams are explicit in `deck_builder.py`, `providers.py`, `main.py`, and tests. [VERIFIED: codebase read]
- Pitfalls: MEDIUM - the cleanup/logging and lexical-review gaps are verified, but benchmark-leakage risk is still partly assumption-driven. [VERIFIED: codebase read, ASSUMED]

**Research date:** 2026-04-22
**Valid until:** 2026-05-22

## RESEARCH COMPLETE

**Phase:** 05 - evaluation-and-runtime-controls
**Confidence:** MEDIUM

### Key Findings
- The repo already has reusable metrics seams: `LogRecord`, `BuildStats`, stage timings, event counters, JSONL logs, and `quality_report.json`. [VERIFIED: deck_builder.py, logger.py, models.py]
- AI guardrails already exist for several stages, but lexical review is currently outside the shared `allow_ai(...)`/stage-timing story. [VERIFIED: deck_builder.py, providers.py, lexical_review.py]
- `runtime.cleanup_generated_artifacts: true` will delete run logs after export, so evaluation runs must preserve or harvest logs deliberately. [VERIFIED: AGENTS.md, config.yaml, deck_builder.py]
- The codebase already fingerprints model/prompt/schema/validator inputs for resume safety, but current artifacts do not surface a full experiment identity for evaluation reporting. [VERIFIED: deck_builder.py, run_state.py]
- Local Python/pytest/pydantic tooling is ready, but live AI credentials are unset in this shell, so true end-to-end benchmark execution needs a credentialed environment. [VERIFIED: local env check]

### File Created
`.planning/phases/05-evaluation-and-runtime-controls/05-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | Existing dependencies, versions, and test tooling were directly verified. |
| Architecture | HIGH | Core seams and touchpoints are explicit in the codebase. |
| Pitfalls | MEDIUM | Main runtime/logging gaps were verified, but some benchmark-design risks remain judgment-based. |

### Open Questions (RESOLVED)
- Evaluation entrypoint: keep the benchmark harness module- and pytest-driven in this phase, with any CLI exposure deferred unless implementation proves a lightweight wrapper is needed.
- Benchmark annotation source: store the canonical benchmark dataset in a repo-backed fixture such as `ankideck_generator/tests/fixtures/evaluation/benchmark_cases.json` so runs stay versioned and reproducible.
- Credentialed milestone benchmarking: treat live-provider benchmark execution as a manual verification step in a credentialed environment; local offline work should use stubbed or fake-provider tests.

### Ready for Planning
Research complete. Planner can now create PLAN.md files.
