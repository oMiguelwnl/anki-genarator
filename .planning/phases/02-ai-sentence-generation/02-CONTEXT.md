# Phase 2: AI Sentence Generation - Context

**Gathered:** 2026-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Move sentence generation to a structured AI-first flow that produces constrained candidate sets, rejects malformed outputs early, and keeps web sources as bounded fallback rather than the default path.

</domain>

<decisions>
## Implementation Decisions

### Candidate Contract
- **D-01:** AI sentence generation must return exactly 3 structured candidates per focus word rather than one free-text sentence or a large bundle.
- **D-02:** Each candidate must carry the sentence plus essential metadata: target form used, target POS/sense inputs, level or validation signals, and a short machine-readable rationale for ranking or rejection.

### Constraint Strictness
- **D-03:** Sentence generation uses a hard contract up front: exact target form, intended POS/sense, and level target are explicit prompt/schema inputs.
- **D-04:** Candidates that violate the hard contract should be rejected before downstream lexical resolution instead of relying on late salvage through validators.

### Fallback Policy
- **D-05:** AI generation is the primary sentence path and must exhaust its bounded candidate attempt flow before web sources are considered.
- **D-06:** Web sentence sources remain salvage-only fallback, invoked late and narrowly when AI output is empty, malformed, wrong-language, or low-yield.

### Sentence Style
- **D-07:** Optimize for natural everyday speech rather than teaching sentences, dictionary-like phrasing, or obviously synthetic examples.
- **D-08:** Candidate prompts and validation should actively bias against proper nouns, meta-example phrasing, and other artificial-but-grammatical sentence patterns.

### the agent's Discretion
- Exact schema field names for sentence candidate payloads.
- Exact prompt versioning shape and where prompt versions are stored.
- Exact retry counts, score thresholds, and rejection heuristics, as long as they preserve the AI-first, bounded-fallback policy above.
- Whether candidate ranking remains in `DeckBuilder` initially or moves into an extracted sentence-generation service during Phase 2 planning.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope
- `.planning/PROJECT.md` — Product direction, the AI-first shift, and the requirement to preserve the CLI deck pipeline.
- `.planning/REQUIREMENTS.md` — Phase 2 requirements `AIG-01` through `AIG-04` plus compatibility constraints.
- `.planning/ROADMAP.md` — Phase 2 goal, success criteria, and plan breakdown.
- `.planning/STATE.md` — Current project position and prior milestone decisions.

### Prior phase decisions
- `.planning/phases/01-run-state-foundation/01-CONTEXT.md` — Locks the AI-first lifecycle, bounded refactor posture, and accepted-only runtime behavior that Phase 2 must build on.

### Codebase analysis
- `.planning/codebase/ARCHITECTURE.md` — Explains the current orchestration, provider gateway, and validation layers that Phase 2 must extend.
- `.planning/codebase/CONCERNS.md` — Flags the monolithic `DeckBuilder` and `ProviderManager` hotspots that constrain how far Phase 2 should refactor.
- `.planning/codebase/CONVENTIONS.md` — Repo-specific guidance on helper extraction, typed models, and focused regression coverage.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ankideck_generator/core/providers.py::sentence_ai()` and `_sentence_ai()` — Existing AI sentence path that can be upgraded from single free-text output to a structured candidate contract.
- `ankideck_generator/core/providers.py::sentence_rewrite()` and `sentence_web_candidates()` — Existing rewrite and web-candidate seams that already support bounded salvage behavior.
- `ankideck_generator/core/deck_builder.py::SentenceSelectionCandidate` and `_sentence_selection_score()` — Existing candidate model and ranking logic that can be aligned to structured AI candidates.
- `ankideck_generator/core/deck_builder.py::_process_word_textual()` / `build_sentence()` — Natural integration point for flipping sentence routing from web-first to AI-first.
- `vocabGenarator.py::_create_prompt()` plus its multi-provider rotation logic — Useful reference for prompt tone and provider calling strategy, though it is currently standalone and single-shot.

### Established Patterns
- Provider-specific logic lives behind `ProviderManager`; Phase 2 should extend that gateway rather than scattering AI HTTP logic through `DeckBuilder`.
- The repo prefers small helper extraction around the large orchestrator instead of sweeping rewrites.
- Validation and reporting already use named error codes, candidate previews, and structured event counters; sentence generation should plug into those existing observability seams.

### Integration Points
- `ankideck_generator/core/deck_builder.py::_process_word_textual()` currently chooses between cached sentence, Tatoeba candidates, rewrite salvage, and AI generation.
- `ankideck_generator/core/providers.py` is where structured prompt execution, parsing, and fallback provider behavior must live.
- `ankideck_generator/core/models.py` is the place to add typed sentence-candidate contracts and prompt-version metadata.
- `ankideck_generator/tests/test_deck_builder.py` already covers retry, rewrite, strong-Tatoeba skip, and sentence selection behavior, making it the right base for Phase 2 regression tests.

</code_context>

<specifics>
## Specific Ideas

- Use `vocabGenarator.py` as a reference for prompt tone and provider-calling behavior, but evolve it from one free-text sentence to 3 structured AI candidates.
- Keep the result learner-facing and believable in ordinary speech, not a "this is an example" sentence.

</specifics>

<deferred>
## Deferred Ideas

- Large 5+ candidate bundles with richer confidence payloads — defer to a later optimization/evaluation phase.
- Translation and definition review/correction remain Phase 3 work, not part of Phase 2 sentence generation scope.

</deferred>

---

*Phase: 02-ai-sentence-generation*
*Context gathered: 2026-04-20*
