# Requirements: Anki Deck Generator

**Defined:** 2026-04-15
**Core Value:** Gerar cards de vocabulario uteis e semanticamente corretos a partir de palavras frequentes, com qualidade suficiente para exportar o deck final sem grande retrabalho manual.

## v1 Requirements

Requirements for the current milestone. Each requirement maps to a roadmap phase.

### Foundation and State

- [ ] **FOUND-01**: The pipeline distinguishes generated, reviewed, accepted, rejected, and human-review states instead of treating all processed cards as equivalent.
- [ ] **FOUND-02**: Resume/progress restores phase-safe execution state and never exports cards that were only generated but not accepted.
- [ ] **FOUND-03**: AI-backed cache entries are versioned by model, prompt, schema, and validator policy so stale generations can be invalidated safely.
- [ ] **FOUND-04**: Export consumes only accepted cards while preserving machine-readable rejection and review artifacts.

### AI Sentence Generation

- [ ] **AIG-01**: The system generates example sentence candidates with AI as the primary source using structured output contracts instead of raw free text.
- [ ] **AIG-02**: Sentence generation constrains target lemma, sense, and part of speech, and rejects malformed or focus-missing candidates before downstream use.
- [ ] **AIG-03**: AI sentence generation remains compatible with the existing configured-language model and `wordfreq`-driven intake.
- [ ] **AIG-04**: Existing non-AI sentence sources remain available only as bounded fallback or salvage paths when AI generation is unavailable or low-yield.

### Lexical Resolution and Review

- [x] **LEX-01**: Translation is generated or reviewed with the accepted sentence context, target word, and intended sense together.
- [x] **LEX-02**: Definition or gloss is concise, learner-facing, and validated against the exact usage in the accepted sentence.
- [x] **LEX-03**: A review stage can accept, correct, reject, or route a card to human review with machine-readable reasons.
- [x] **LEX-04**: Deterministic validators rerun after any AI or human correction before a card can be accepted.

### Quality, Duplicates, and Reporting

- [x] **QUAL-01**: The system blocks exact duplicates and near-duplicates across accepted cards using normalized signatures plus bounded fuzzy comparison.
- [x] **QUAL-02**: Hard validation failures and soft review flags are tracked separately and surfaced in structured outputs.
- [x] **QUAL-03**: Review artifacts preserve before and after context, rejection reasons, and provider or model provenance sufficient for audit.
- [ ] **QUAL-04**: The accepted-card rate improves above 60% on the defined benchmark or release dataset before the milestone is considered complete.

### Compatibility and Runtime

- [ ] **COMP-01**: The existing CLI entrypoint remains usable from the repo root for configured languages.
- [ ] **COMP-02**: `wordfreq` and frequency-level selection remain the front door for vocabulary intake.
- [x] **COMP-03**: `.apkg` export plus `output/metadata.json`, `output/quality_report.json`, and `output/review_queue.json` continue to be produced.
- [x] **COMP-04**: Audio or TTS generation remains post-acceptance and continues to integrate with deck export.
- [ ] **COMP-05**: Existing provider fallback behavior for non-AI fields remains compatible unless a later phase explicitly replaces it.

### Evaluation and Operations

- [x] **EVAL-01**: The project includes a representative benchmark or gold set segmented by language, ambiguity, and frequency or difficulty slice.
- [x] **EVAL-02**: Prompt, model, or validator changes can be evaluated against reproducible metrics for sentence quality, lexical accuracy, duplicate rate, acceptance rate, and cost or latency per accepted card.
- [x] **EVAL-03**: Runtime logs and reports capture stage, model or provider, confidence or reason codes, and rejection paths needed to tune the pipeline.
- [x] **EVAL-04**: Runtime enforces configurable AI call budgets or guardrails so deck builds remain operationally viable.

## v2 Requirements

Deferred for a later milestone. Tracked, but not in the current roadmap.

### Quality Optimization

- **OPT-01**: The system generates best-of-N sentence candidates and ranks them before lexical review.
- **OPT-02**: Retry strategy adapts to failure mode instead of reusing the same prompt path for every rejection.

### Pedagogy Controls

- **PED-01**: Sentence difficulty and register can be tuned per language or frequency band.
- **PED-02**: The deck balances sense diversity so accepted cards do not cluster around the same semantic frame.

## Out of Scope

Explicitly excluded from the current milestone to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Replacing `wordfreq` with AI-selected vocabulary | Violates the validated product baseline and current project constraints |
| Rebuilding the product as a web app or hosted service | The current milestone is constrained to the existing CLI product shape |
| Embeddings or vector infrastructure for first-pass duplicate control | Canonical normalization plus bounded fuzzy matching should be exhausted first |
| One-shot free-text AI generation without review or gating | Low observability and poor semantic reliability for this brownfield pipeline |
| Multi-sense dictionary dumps on a single card | Conflicts with learner-facing, usage-specific card quality goals |

## Traceability

Which phases cover which requirements.

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 | Pending |
| FOUND-02 | Phase 1 | Pending |
| FOUND-03 | Phase 1 | Pending |
| FOUND-04 | Phase 1 | Pending |
| COMP-01 | Phase 1 | Pending |
| COMP-02 | Phase 1 | Pending |
| COMP-05 | Phase 1 | Pending |
| AIG-01 | Phase 2 | Pending |
| AIG-02 | Phase 2 | Pending |
| AIG-03 | Phase 2 | Pending |
| AIG-04 | Phase 2 | Pending |
| LEX-01 | Phase 3 | Complete |
| LEX-02 | Phase 3 | Complete |
| LEX-03 | Phase 3 | Complete |
| LEX-04 | Phase 3 | Complete |
| COMP-04 | Phase 3 | Complete |
| QUAL-01 | Phase 4 | Complete |
| QUAL-02 | Phase 4 | Complete |
| QUAL-03 | Phase 4 | Complete |
| COMP-03 | Phase 4 | Complete |
| EVAL-03 | Phase 4 | Complete |
| QUAL-04 | Phase 5 | Pending |
| EVAL-01 | Phase 5 | Complete |
| EVAL-02 | Phase 5 | Complete |
| EVAL-04 | Phase 5 | Complete |

**Coverage:**
- v1 requirements: 25 total
- Mapped to phases: 25
- Unmapped: 0

---
*Requirements defined: 2026-04-15*
*Last updated: 2026-04-15 after resume-state reconstruction*
