# Phase 3: Contextual Lexical Review - Research

**Researched:** 2026-04-20
**Status:** Complete

## Research Question

What must change to add sentence-anchored translation/definition review, AI-first correction with typed verdicts, and deterministic revalidation before acceptance or audio, while preserving the current CLI, output artifacts, and post-acceptance audio contract?

## Recommended Stack

- **Keep:** Python 3.11, Pydantic 2, current `ProviderManager`, current `DeckBuilder`, current `validate_card()` flow, current JSON audit artifacts.
- **Use for contracts:** Pydantic `BaseModel`, `Field`, `Literal`, `model_validate()`, `model_dump()`, and `model_json_schema()` for typed lexical-review request/response payloads.
- **Do not add:** external workflow engines, queue systems, or vendor-specific structured-output SDKs for this phase.

## Key Findings

### 1. The codebase already has most primitives for contextual lexical review

- `ankideck_generator/core/deck_builder.py::_process_word_textual()` already has the accepted sentence, source-language definitions, translated glosses, candidate previews, review notes, selection reasons, and before/after audit containers in one place.
- `ankideck_generator/core/models.py::LogRecord` already exposes `reason_codes`, `before`, `after`, `candidate_preview`, and `selection_reasons`, so Phase 3 should extend those structures instead of inventing a second audit channel.
- `output/review_queue.json` and `output/quality_report.json` already exist and match D-02/D-03 better than introducing a blocking runtime `human-review` state.

### 2. Provider transport should stay in `ProviderManager`, but review policy should not

- `ankideck_generator/core/providers.py` already owns `definition_from_context()`, `definition_candidates()`, `translation_ai()`, and `translation_web()`.
- That makes it the right place for a narrow AI transport such as `lexical_review()` / `_lexical_review_ai()`.
- The decision logic for accept vs correct vs reject, sentence anchoring, minimal-patch preference, and ambiguity handling belongs in a focused service layer, not in raw provider methods.

### 3. A dedicated lexical-review service fits repo conventions better than adding more inline branching

- `.planning/codebase/CONCERNS.md` flags `DeckBuilder` as the main hotspot.
- `.planning/codebase/CONVENTIONS.md` recommends narrow helper extraction around the large orchestrator.
- A new module such as `ankideck_generator/core/lexical_review.py` is the best place to centralize typed request/response contracts, best-sense selection, correction synthesis, and verdict normalization.

### 4. The accepted sentence must stay the anchor

- `config.yaml` keeps `runtime.definition_context_first: true`, and `DeckBuilder` already builds around sentence-first lexical selection.
- D-06, D-08, and the phase goal require keeping the accepted sentence and visible focus word fixed during lexical review.
- Phase 3 should therefore correct `definition` and `translation` against the sentence, not regenerate or rewrite the sentence as the default fix path.

### 5. Minimal patching is realistic with the current audit model

- Because `CardData` stores `definition` and `translation` independently and `LogRecord.before/after` already support snapshots, Phase 3 can patch one field without rebuilding the whole card.
- This aligns with D-07 and lowers regression risk versus whole-card regeneration.

### 6. Revalidation must move ahead of acceptance and audio for corrected flows

- `ankideck_generator/core/deck_builder.py::_process_word()` currently validates text, attaches audio, then allows `_interactive_edit()` to mutate fields without rerunning validators.
- `.planning/codebase/CONCERNS.md` already documents this as a known bug.
- Phase 3 must add a single deterministic revalidation seam that runs after AI corrections and after interactive/manual edits, before final acceptance, and before audio is attached to corrected cards.

### 7. Existing validator and error-policy code should remain the source of truth

- `ankideck_generator/core/validators.py::validate_card()` and `DeckBuilder._should_reject_errors()` already encode hard/soft acceptance policy.
- D-13, D-14, and D-15 require reusing that same validator stack after correction rather than creating looser review-only rules.
- New lexical-review reason codes can be added to logs/audit outputs, but final acceptance should still depend on the existing deterministic validator policy.

### 8. Context7 confirms Pydantic already supports the needed contract flow

- Context7 Pydantic docs confirm `model_validate()` / `model_validate_json()` are the right runtime validation APIs and `model_json_schema()` is the right schema publication API for typed structured payloads.
- That means typed lexical-review request/response contracts can stay fully in-repo with no new dependency.

## Architectural Responsibility Map

| Layer | File(s) | Responsibility | Must Not Own |
|------|---------|----------------|--------------|
| Typed lexical-review contracts | `ankideck_generator/core/models.py` | Verdict enums/literals, typed review request/response payloads, reason-code-bearing correction records | HTTP calls, acceptance policy |
| AI review transport | `ankideck_generator/core/providers.py` | Send lexical-review prompt, parse structured response, return `ProviderResult`/typed result objects | Sentence-anchor policy, queue routing |
| Lexical review domain logic | `ankideck_generator/core/lexical_review.py` | Sentence-anchored best-sense choice, minimal patch selection, ambiguity handling, verdict normalization | Raw HTTP/session code |
| Orchestration | `ankideck_generator/core/deck_builder.py` | Build review inputs from card context, apply corrections, preserve before/after audit data, rerun validators, gate audio and acceptance | Prompt text assembly, ad hoc validator copies |
| Deterministic validation | `ankideck_generator/core/validators.py` | Final hard/soft lexical validation after corrections | AI scoring, provider fallbacks |
| Regression tests | `ankideck_generator/tests/test_providers.py`, `ankideck_generator/tests/test_lexical_review.py`, `ankideck_generator/tests/test_deck_builder.py` | Verify transport, review-service behavior, orchestration/revalidation/audio ordering | Production routing logic |

## Recommended Contracts

### Lexical review request

Use a typed payload carrying at least:

- focus word
- language
- accepted sentence
- current translation
- current learner-facing definition
- source-language definition or candidate senses
- requested target translation language
- optional candidate-sense evidence used for ambiguity resolution

### Lexical review result

Use a typed result with:

- `verdict`: `accept`, `correct`, or `reject`
- `reason_codes`: list of machine-readable reasons
- `confidence`: normalized numeric or bucketed score
- `corrected_definition` and `corrected_translation` as optional fields
- `winning_sense` summary plus `losing_sense_candidates`
- before/after-ready evidence fields so `LogRecord` can persist audit snapshots without reconstruction

Avoid a runtime verdict/state named `human_review`; route low-confidence cases to reject + queue artifact instead, per D-02/D-03.

## Recommended Review Policy

1. Build lexical review inputs from the accepted sentence, fixed focus word, current translation, current definition, and sense candidates.
2. Prefer the current lexical fields when they already align with the sentence.
3. If exactly one lexical field is wrong, patch only that field per D-07.
4. If multiple senses are plausible, auto-pick the best sentence-matched sense when evidence is sufficient per D-09.
5. Persist losing candidates and rationale in audit data per D-11.
6. If evidence is still weak, reject to `review_queue.json` with structured reason codes per D-02/D-12.
7. After any AI/manual correction, rerun deterministic validators before acceptance.

## Compatibility Guidance

- Preserve current non-lexical provider fallback order from `AGENTS.md`.
- Preserve `review_queue.json` as the rejected follow-up artifact; do not introduce a blocking runtime queue.
- Preserve `quality_report.json` as the aggregate accepted/rejected snapshot surface.
- Preserve audio/TTS integration, but move corrected-card audio behind successful revalidation and acceptance gating.
- Prefer policy/config-driven definition cleanup through `definition_policy.yaml` rather than hardcoding new cleanup heuristics in multiple places.

## Common Pitfalls

- **Do not add a mainline `human-review` lifecycle state**; Phase 3 routes uncertain cards to reject + queue artifacts instead.
- **Do not rewrite the accepted sentence** to fit a lexical correction by default.
- **Do not regenerate the entire lexical bundle** when one field can be patched safely.
- **Do not bypass `validate_card()` after AI or manual edits**.
- **Do not attach audio before corrected text has passed revalidation**.
- **Do not drop ambiguity evidence**; keep losing senses and rationale in audit data.
- **Do not change non-lexical fallback order** for definitions/translations outside the review seam.

## Validation Architecture

### Automated checks

- `python -m pytest ankideck_generator/tests/test_providers.py -q -k "lexical_review or contextual_definition or translation"`
- `python -m pytest ankideck_generator/tests/test_lexical_review.py -q`
- `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "lexical_review or revalidation or interactive_edit or review_queue or audio"`

### Coverage expectations by area

- **Providers:** lexical-review transport request/response validation and malformed-result rejection.
- **Lexical review service:** best-sense selection, minimal patching, reject-on-ambiguity, and reason-code preservation.
- **DeckBuilder orchestration:** sentence-anchored corrections, before/after audit snapshots, queue routing, revalidation after correction/manual edit, and audio-after-acceptance ordering.

## Planning Implications

- Define typed review contracts and provider transport first.
- Integrate the sentence-anchored lexical-review service next.
- Rework acceptance/audio ordering and post-edit revalidation last.
- Keep changes concentrated in `models.py`, `providers.py`, a new `lexical_review.py`, and targeted `DeckBuilder` seams with focused pytest coverage.

## Decision Alignment

- **D-01 / D-02 / D-03 / LEX-03:** fixable issues auto-correct; unresolved low-confidence cases reject into `review_queue.json` with reason codes.
- **D-04 / D-11:** preserve before/after snapshots plus losing-sense evidence in audit data.
- **D-05 / D-06 / D-07 / D-08 / LEX-01 / LEX-02:** review only lexical fields, keep the sentence/focus anchored, and prefer minimal patching.
- **D-09 / D-10 / D-12:** auto-pick one explainable winning sense when possible; final learner-facing definition stays concise and single-sense.
- **D-13 / D-14 / D-15 / D-16 / LEX-04 / COMP-04:** rerun deterministic validators after any correction, reject failed corrections, and keep audio post-acceptance.

## Recommendation

Proceed with three sequential plans: (1) typed lexical-review contracts + transport, (2) sentence-anchored review/correction integration + audit routing, and (3) deterministic revalidation + audio-after-acceptance enforcement.
