# Architecture Research

**Domain:** AI-first multilingual Anki deck generation on an existing CLI pipeline
**Researched:** 2026-04-15
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLI / Runtime Layer                           │
├─────────────────────────────────────────────────────────────────────────────┤
│  main.py / RunConfig / preflight / config.yaml / language profile loading  │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Orchestration Layer (keep)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                              DeckBuilder                                   │
│  - level loop  - progress/resume  - logging  - report writing  - export    │
└──────┬──────────────────┬──────────────────┬──────────────────┬────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│Word Intake   │   │Text Pipeline │   │Audio Pipeline│   │Export        │
│wordfreq pool │   │(new center)  │   │existing      │   │existing      │
└──────┬───────┘   └──────┬───────┘   └──────────────┘   └──────────────┘
       │                  │
       │                  ▼
       │      ┌───────────────────────────────────────────────────────────┐
       │      │            Card Text Pipeline (new/expanded)             │
       │      ├───────────────────────────────────────────────────────────┤
       │      │ 1. CandidateContextBuilder                               │
       │      │ 2. SentenceGenerationService (AI-first)                  │
       │      │ 3. LexicalResolutionService                              │
       │      │ 4. AIReviewService                                       │
       │      │ 5. DuplicateGuard                                        │
       │      │ 6. QualityGateEngine                                     │
       │      └───────────────────────────────────────────────────────────┘
       │                  │
       ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Facades / Infrastructure                           │
├─────────────────────────────────────────────────────────────────────────────┤
│ ProviderFacade │ CacheManager │ ProgressStore │ JsonLogger │ Reports       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `DeckBuilder` (modified) | Own run lifecycle, batching, resume, artifact writing, export/audio ordering | Keep as orchestrator; remove field-level AI decision logic into services |
| `CandidateContextBuilder` (new) | Assemble per-word context: level, language profile, cache hits, prior duplicate fingerprints, provider budgets | Small service returning a typed context object |
| `SentenceGenerationService` (new) | Generate 1..N sentence candidates with AI as primary source, optional web seeds as fallback/rewrite input | Calls provider facade, returns typed candidates + metadata |
| `LexicalResolutionService` (new) | Resolve definition/translation candidates against the chosen sentence context | Reuse existing provider methods and definition policy |
| `AIReviewService` (new) | Judge/correct sentence, translation, and definition as a structured review pass | Single-purpose AI prompt returning a typed verdict |
| `DuplicateGuard` (new) | Fast exact + near-duplicate checks before and after review | Normalized hashes + shortlist fuzzy comparison |
| `QualityGateEngine` (new) | Run deterministic and multilingual gates, classify hard reject vs review-needed | Wraps existing validators plus new cross-field rules |
| `ProviderManager` / provider facade (modified) | Execute provider calls, retries, auth, and typed AI operations only | Should not own selection policy |
| `CacheManager` (modified) | Persist accepted artifacts and stage-level AI/review caches | Add namespaces; keep existing cache keys for final accepted values |
| `JsonLogger` / reports (modified) | Persist stage outcomes, model/provider usage, review reasons, gate failures | Extend existing `LogRecord` instead of inventing a second log format |

## Recommended Project Structure

```
ankideck_generator/
├── core/
│   ├── deck_builder.py              # keep run orchestration and export/audio wiring
│   ├── providers.py                 # keep facade; shrink business logic
│   ├── models.py                    # extend with candidate/review/gate models
│   ├── validators.py                # deterministic gates only
│   ├── pipeline/                    # NEW text-stage services
│   │   ├── context.py               # CandidateContextBuilder
│   │   ├── sentence_generation.py   # AI-first sentence generation
│   │   ├── lexical_resolution.py    # definition/translation candidate building
│   │   ├── review.py                # AI review/correction stage
│   │   ├── duplicates.py            # duplicate indexes + fuzzy shortlist logic
│   │   └── quality_gates.py         # hard/soft gate orchestration
│   └── reports/                     # optional extraction from deck_builder later
├── prompts/                         # NEW versioned AI prompts / schemas
│   ├── sentence_generation/
│   └── review/
├── policies/
│   ├── definition_policy.yaml       # existing rule-driven cleanup
│   └── language_quality_profiles.yaml # NEW per-language gate thresholds
└── utils/
    └── existing file/log/config helpers
```

### Structure Rationale

- **`core/pipeline/`:** extract the new AI-first text flow from the 3314-line `DeckBuilder` without changing CLI, export, or audio entrypoints.
- **`prompts/`:** prompt versions must be explicit and cacheable; prompt text should not stay hidden in provider methods.
- **`policies/`:** multilingual quality rules should be config-driven like `definition_policy.yaml`, not hardcoded into prompts.

## Architectural Patterns

### Pattern 1: Orchestrator + Stage Services

**What:** Keep one central run coordinator, but move per-card text generation/review into focused services.
**When to use:** Brownfield CLI that already depends on one orchestrator for progress, export, and cleanup.
**Trade-offs:** Lowest migration risk; still somewhat centralized until more extraction happens.

**Example:**
```python
card_ctx = context_builder.build(word, level, run, cache, seen_index)
sentence_result = sentence_service.generate(card_ctx)
lexical_result = lexical_service.resolve(card_ctx, sentence_result)
review_result = review_service.review(card_ctx, sentence_result, lexical_result)
gate_result = quality_gates.evaluate(card_ctx, review_result.card, duplicate_guard)
```

### Pattern 2: Typed AI Contracts, Not Free-Text AI Calls

**What:** Every AI stage returns a Pydantic model such as `SentenceCandidateSet` or `ReviewVerdict`.
**When to use:** Any stage whose output feeds validation, caching, or downstream generation.
**Trade-offs:** Slightly more schema work, much less parsing drift and retry noise.

**Example:**
```python
class ReviewVerdict(BaseModel):
    approved: bool
    corrected_sentence: str = ""
    corrected_translation: str = ""
    corrected_definition: str = ""
    hard_fail_reasons: list[str] = []
    soft_flags: list[str] = []
    confidence: float
```

### Pattern 3: Hard Gates Then Soft Review Queue

**What:** Split quality checks into export-blocking gates and review-only flags.
**When to use:** Multilingual content pipelines where some issues are objective and others are judgment calls.
**Trade-offs:** More explicit gate taxonomy, but far better approval behavior than one giant reject bucket.

**Recommended split:**
- **Hard gates:** missing fields, wrong language, focus absent from sentence, exact duplicate, near-duplicate above threshold, broken IPA/audio requirements.
- **Soft gates:** slightly awkward phrasing, low semantic confidence, possible polysemy ambiguity, low definition/translation alignment.

## Data Flow

### Request Flow

```
CLI run
    ↓
main.py builds RunConfig
    ↓
DeckBuilder.build()
    ↓
Word selected from wordfreq pool
    ↓
CandidateContextBuilder
    ↓
SentenceGenerationService ──→ cache(raw sentence candidates)
    ↓
LexicalResolutionService  ──→ cache(definition/translation candidates)
    ↓
AIReviewService          ──→ cache(review verdict / prompt version / model)
    ↓
DuplicateGuard pre-export checks
    ↓
QualityGateEngine
    ├── hard fail → discard + log + review_queue entry if useful
    ├── soft fail → accept-with-review flag or send to review queue
    └── pass → accepted text card
    ↓
Audio attachment (unchanged ordering: after text acceptance)
    ↓
Final audio-aware gates
    ↓
Export to .apkg + metadata + quality_report + review_queue
```

### Quality-Gate Flow

```
Raw candidates
    ↓
[Gate 0] schema validation
    ↓
[Gate 1] deterministic field validation
    - required fields
    - language match
    - focus in sentence
    - sentence length/profile/level
    ↓
[Gate 2] AI review / correction
    - sentence naturalness
    - translation accuracy
    - definition sense correctness
    ↓
[Gate 3] duplicate prevention
    - exact normalized hash
    - shortlist fuzzy comparison
    ↓
[Gate 4] cross-field multilingual alignment
    - sentence ↔ translation
    - sentence ↔ definition
    - definition language / translation language
    ↓
[Gate 5] audio-required checks
    ↓
accepted card | review queue | discard
```

### Key Data Flows

1. **Generation flow:** word → context → AI-first sentence candidates → chosen sentence → contextual lexical candidates.
2. **Review flow:** provisional card → AI verdict/corrections → deterministic revalidation → acceptance or rejection.
3. **Duplicate flow:** accepted/reviewed card text → normalized signatures/indexes → exact/fuzzy checks → seen sets update only on final acceptance.
4. **Artifact flow:** accepted text card → audio generation → export/report artifacts; rejected cards never consume audio budget.

## Brownfield Integration Plan

### New vs Modified Components

| Area | New | Modified | Why |
|------|-----|----------|-----|
| Orchestration | `core/pipeline/*` services | `DeckBuilder` | Preserve run shape while shrinking hot spots |
| AI contracts | `SentenceCandidate`, `ReviewVerdict`, `GateResult` models | `models.py`, `LogRecord` | Needed for structured outputs and observability |
| Provider facade | — | `ProviderManager` | Add typed AI methods; remove selection/business policy from facade |
| Validation | `QualityGateEngine`, `DuplicateGuard` | `validators.py` | Current validator is too flat for AI-review + multilingual gates |
| Persistence | new cache namespaces | `CacheManager`, review/report writers | Preserve existing final caches, add stage caches |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `DeckBuilder` ↔ `pipeline/*` | direct service calls | Synchronous is fine; no event bus needed in CLI |
| `pipeline/*` ↔ `ProviderManager` | typed method calls | Provider layer returns raw provider results, not acceptance decisions |
| `AIReviewService` ↔ `validators.py` | `ReviewVerdict` into deterministic revalidation | AI review cannot bypass deterministic validation |
| `DuplicateGuard` ↔ `ValidationContext` | replace/extend current seen sets | Existing `seen_focus`/`seen_sentence` become indexes, not just sets |
| `DeckBuilder` ↔ audio/export | existing direct calls | Keep post-acceptance audio and final export unchanged |

## Recommended Integration Decisions

### 1) Put AI review **inside** the text pipeline, not after export

The new AI review stage should run after provisional sentence/definition/translation assembly and before audio/export. That preserves existing `.apkg` and TTS behavior while preventing bad cards from consuming audio budget.

### 2) Make review a **judge/corrector**, not the source of truth for orchestration

`AIReviewService` should return a verdict plus optional corrected fields. `DeckBuilder` decides whether to accept corrections and always re-runs deterministic gates. This prevents the current anti-pattern where interactive edits can bypass final validation.

### 3) Separate **candidate generation** from **candidate selection**

`ProviderManager` may fetch candidates; `SentenceGenerationService` and `LexicalResolutionService` decide ranking/selection. Today those responsibilities are mixed inside `DeckBuilder` and `ProviderManager`.

### 4) Replace O(n²) duplicate checks with an indexed guard

Current `SequenceMatcher` across all prior sentences does not scale. Recommended guard:
- exact key: normalized sentence text
- coarse key: token fingerprint / n-gram signature
- fuzzy check: run `SequenceMatcher` only on coarse-key shortlist

Do this both **before** AI review (avoid wasted spend on obvious duplicates) and **after** correction (AI may rewrite into a duplicate).

### 5) Make multilingual gates config-driven

Per-language rules belong in profiles, not prompts:
- minimum token counts
- allowed punctuation / clause complexity
- language-detection thresholds
- level-specific length bounds
- optional scripts/orthography rules

This is the architecture equivalent of the current `definition_policy.yaml` approach and fits the project’s existing style.

## Suggested Build Order

1. **Add typed models for candidates, review verdicts, and gate results**
   - Safe first step.
   - No change to export/audio/cache behavior.

2. **Extract `QualityGateEngine` around existing validators**
   - Wrap current `validate_card()` behavior in a stage object.
   - Add explicit hard vs soft outcomes.

3. **Extract `DuplicateGuard` from current seen-set logic**
   - Preserve current duplicate semantics first.
   - Then optimize shortlist fuzzy checking.

4. **Extract `SentenceGenerationService` from `_process_word_textual()`**
   - Keep current provider calls and caching behavior.
   - Flip policy to AI-first behind the new service, not in `DeckBuilder`.

5. **Extract `LexicalResolutionService` for definition/translation assembly**
   - Reuse existing candidate logic and `definition_policy.yaml`.
   - Keep current cache keys for accepted definition/translation outputs.

6. **Introduce `AIReviewService` with structured outputs**
   - Run on provisional cards only.
   - Revalidate corrected output through `QualityGateEngine` and `DuplicateGuard`.

7. **Extend logs, review queue, and quality report**
   - Persist prompt version, model, review verdict, correction source, gate failures.
   - This is required to tune approval rate above 60% without blind prompting.

8. **Only then refactor `DeckBuilder` wiring further**
   - Keep `export_deck()` and `_attach_audio_to_card()` order stable until text pipeline proves out.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| single-user CLI / current state | Monolith + stage services is correct; do not split into separate processes |
| larger local runs | Add better duplicate indexes, per-stage cache reuse, AI budget caps, provider metrics |
| very large corpus generation | Consider batch review/generation jobs, but only after logs show provider cost/latency dominates |

### Scaling Priorities

1. **First bottleneck:** AI call volume and retries. Fix with candidate caching, pre-review duplicate checks, and hard budgets per field/word.
2. **Second bottleneck:** duplicate detection cost. Fix with indexed coarse matching before `SequenceMatcher`.

## Anti-Patterns

### Anti-Pattern 1: Letting the provider facade own card policy

**What people do:** keep adding ranking, review, and acceptance logic inside `ProviderManager`.
**Why it's wrong:** the provider layer becomes another monolith and mixes transport with product rules.
**Do this instead:** provider facade fetches typed raw candidates; pipeline services own scoring and acceptance.

### Anti-Pattern 2: Treating AI review as final truth

**What people do:** accept AI-corrected text without re-running deterministic gates.
**Why it's wrong:** duplicates, wrong-language output, and malformed fields slip through.
**Do this instead:** all corrected content must re-enter deterministic validation and duplicate checks before acceptance.

### Anti-Pattern 3: Generating audio before text acceptance

**What people do:** attach TTS during candidate generation.
**Why it's wrong:** wastes cost/time and breaks current artifact assumptions.
**Do this instead:** preserve today’s ordering: accept text first, then attach audio, then run final audio gates.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| LLM provider(s) | Through `ProviderManager` typed methods | Prefer structured outputs for sentence/review payloads |
| Dictionary/translation/web sentence providers | Existing fallback facade | Keep as lexical evidence and fallback, not primary sentence source |
| TTS providers | Existing post-acceptance audio stage | No architecture change needed beyond stable card contract |

### Sources

- Internal: `.planning/PROJECT.md`
- Internal: `.planning/codebase/ARCHITECTURE.md`
- Internal: `.planning/codebase/CONCERNS.md`
- Code: `ankideck_generator/core/deck_builder.py`
- Code: `ankideck_generator/core/providers.py`
- Code: `ankideck_generator/core/validators.py`
- Code: `ankideck_generator/core/models.py`
- Official docs: OpenAI Structured Outputs — https://platform.openai.com/docs/guides/structured-outputs
- Official docs: Pydantic Models — https://docs.pydantic.dev/latest/concepts/models/

---
*Architecture research for: AI-first multilingual Anki deck generation*
*Researched: 2026-04-15*
