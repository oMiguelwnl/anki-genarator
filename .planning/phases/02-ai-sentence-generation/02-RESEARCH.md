# Phase 2: AI Sentence Generation - Research

**Researched:** 2026-04-20
**Status:** Complete

## Research Question

What must change to make sentence generation AI-first with structured contracts, early rejection, and bounded web fallback, while preserving the current CLI, `wordfreq` intake, and provider gateway shape?

## Recommended Stack

- **Keep:** Python 3.11, Pydantic 2, `requests`, current `ProviderManager`, current `DeckBuilder`, current validator helpers.
- **Use for structured contracts:** `BaseModel.model_json_schema()` and `BaseModel.model_validate_json()` / `model_validate(...)`.
- **Do not add:** provider-specific SDKs or vendor-locked structured-output dependencies for this phase.

## Key Findings

### 1. The repo already has the right primitives for typed structured output

- `ankideck_generator/core/models.py` already uses Pydantic 2, so sentence-candidate contracts can live beside `CardData`, `RunConfig`, and `ProgressState`.
- `ankideck_generator/core/run_state.py::build_compatibility_fingerprint(...)` already fingerprints prompt + schema + validator inputs. Phase 2 should extend those prompt/schema inputs instead of inventing a second versioning system.
- Context7 Pydantic docs confirm `model_json_schema()` is the correct way to publish a JSON schema and `model_validate_json()` / `model_validate(...)` are the correct ways to reject malformed JSON payloads at runtime.

### 2. Existing AI transport is almost reusable, but `first_line_only=True` blocks JSON payloads

- `ProviderManager._ai_request(...)` currently truncates responses to the first line by default.
- That is safe for one-line text outputs, but it will corrupt multi-line or fenced JSON.
- The safest brownfield extension is a dedicated helper that requests full response text, strips code fences via `_extract_json_payload(...)`, and validates against Pydantic models.

### 3. The current routing is web-first inside `DeckBuilder._process_word_textual()`

- `build_sentence()` currently tries cached sentence -> Tatoeba/web candidates -> optional AI rewrite -> AI generation.
- This conflicts with D-05/D-06 and AIG-04.
- Phase 2 must invert that routing so AI structured candidates run first, and web sources are used only when AI is empty, malformed, wrong-language, or low-yield.

### 4. Early rejection should happen before lexical work, but not inside raw HTTP code

- Existing validators are still useful for sentence language/length/profile checks.
- However D-03/D-04 require additional pre-lexical rules: exact target-form presence, requested POS/sense metadata present, exactly three candidates, and rejection of artificial/meta examples.
- Those rules belong in a focused sentence-generation service layer, not scattered through `DeckBuilder` or low-level HTTP transport.

### 5. Small helper extraction fits repo conventions better than a broad rewrite

- `.planning/codebase/CONCERNS.md` and `.planning/codebase/CONVENTIONS.md` both point toward narrow helper extraction around `DeckBuilder`.
- A new `ankideck_generator/core/sentence_generation.py` service is a good fit for prompt-building, schema validation, candidate normalization, and rejection reasons.
- `ProviderManager` should stay the HTTP/fallback boundary.

## Architectural Responsibility Map

| Layer | File(s) | Responsibility | Must Not Own |
|------|---------|----------------|--------------|
| Typed contracts | `ankideck_generator/core/models.py` | Pydantic models for structured AI sentence payloads, prompt/schema version metadata | HTTP calls, routing policy |
| AI transport | `ankideck_generator/core/providers.py` | Send chat request, parse JSON text, validate payload shape, return provider result objects | Routing between AI/web, candidate ranking |
| Sentence-generation domain logic | `ankideck_generator/core/sentence_generation.py` | Build prompt inputs, enforce exact-3 contract, early reject malformed/focus-missing/artificial candidates, map to selection candidates | Direct HTTP/session code |
| Orchestration | `ankideck_generator/core/deck_builder.py` | Decide cache vs AI vs bounded fallback, record event counters, continue lexical pipeline only after valid sentence chosen | Raw JSON parsing or prompt text assembly |
| Regression tests | `ankideck_generator/tests/test_providers.py`, `ankideck_generator/tests/test_sentence_generation.py`, `ankideck_generator/tests/test_deck_builder.py` | Verify transport parsing, contract validation, routing/fallback behavior | Production fallback logic |

## Recommended Contracts

### Structured batch contract

Use a top-level typed payload with:

- prompt version
- schema version
- focus word
- language
- requested POS / requested sense / target level inputs
- exactly **3** candidates

Each candidate should include at minimum:

- `sentence`
- `target_form`
- `requested_pos`
- `requested_sense`
- `validation_signals` (list[str] or similar)
- `rationale` (short machine-readable string or compact reason code)

### Early rejection rules

Reject a candidate before lexical resolution when any of these are true:

- sentence missing/blank
- batch does not contain exactly 3 candidates
- `target_form` does not match the requested focus form
- focus word not present in the sentence
- sentence fails language validation
- sentence is obviously meta/artificial (proper-noun heavy, “this word”, grammar-note style, label text)

## Recommended Routing Policy

1. Reuse cached valid sentence if present and still valid.
2. Request structured AI batch first.
3. Keep only candidates that pass schema + early rejection + existing sentence validators.
4. If AI yields no valid candidates, only then try web/Tatoeba salvage.
5. Keep rewrite salvage limited to web candidates that fail only level/profile checks.
6. Stop fallback early on hard provider failures like auth/rate-limit/provider-disabled.

This preserves D-05/D-06 without deleting the existing salvage seam.

## Compatibility Guidance

- Preserve `wordfreq` intake and level preparation in `DeckBuilder.build()` unchanged.
- Preserve provider fallback behavior for non-sentence fields.
- Extend `DeckBuilder._build_compatibility_fingerprint(...)` so prompt/schema digests include the Phase 2 sentence contract versions.
- Avoid changing CLI flags for this phase unless a test requires explicit runtime wiring.

## Common Pitfalls

- **Do not keep using first-line-only parsing** for structured sentence responses.
- **Do not hand-roll schema validation** with ad hoc dict checks when Pydantic already exists in-repo.
- **Do not move AI HTTP logic into `DeckBuilder`**.
- **Do not let malformed AI payloads fall through to lexical resolution**.
- **Do not make web candidates co-equal with AI again**; fallback must stay bounded and late.
- **Do not expand to 5+ candidates**; D-01 locks exactly 3.

## Validation Architecture

### Automated checks

- `python -m pytest ankideck_generator/tests/test_providers.py -q -k "structured_sentence or sentence_ai_candidates"`
- `python -m pytest ankideck_generator/tests/test_sentence_generation.py -q`
- `python -m pytest ankideck_generator/tests/test_deck_builder.py -q -k "sentence_ai or sentence_rewrite or tatoeba or structured"`

### Coverage expectations by area

- **Providers:** JSON extraction, exact-three contract enforcement, malformed payload rejection, prompt/schema version propagation.
- **Sentence service:** focus-form enforcement, wrong-language/artificial rejection, low-yield detection, conversion into selection candidates.
- **DeckBuilder routing:** AI-first ordering, bounded fallback, strong-candidate short-circuit, rewrite-only-for-level-errors behavior.

## Planning Implications

- Create one contract/transport plan first.
- Extract the sentence-generation service next.
- Re-route `DeckBuilder` after contracts exist.
- Finish with fixture-based regression coverage so malformed payload cases stay reproducible.

## Decision Alignment

- **D-01 / AIG-01:** exact-three structured candidates must be a hard schema rule.
- **D-02 / AIG-02:** candidate metadata must be carried in typed models, not loose dicts.
- **D-03 / D-04:** hard constraints and early rejection belong before lexical resolution.
- **D-05 / D-06 / AIG-04:** AI first, web fallback late and bounded.
- **D-07 / D-08:** prompt text and validators should penalize synthetic/meta sentences and proper nouns.

## Recommendation

Proceed with planning around a new sentence-generation service plus typed Pydantic contracts, reusing the current provider transport and validator stack.
