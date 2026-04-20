# Stack Research

**Domain:** AI-first multilingual Anki deck enrichment on an existing Python CLI pipeline
**Researched:** 2026-04-15
**Confidence:** MEDIUM-HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| LiteLLM | 1.83.x | Unified LLM transport, routing, retries, cooldowns, provider/model fallback | Replace the current hand-rolled OpenAI-compatible request loop only for AI stages. It fits the brownfield shape: Python, OpenAI-style payloads, multi-provider fallback, and structured output support without touching wordfreq, export, audio, or file cache. |
| Pydantic | 2.x (keep existing) | Typed schemas for sentence generation output, review verdicts, correction payloads, and quality reasons | The repo already uses Pydantic. Lean into it instead of inventing ad-hoc JSON parsing. It gives one canonical contract for prompts, validation, cache payloads, and review queue items. |
| Tenacity | 9.1.x | Retry policy around schema failures, empty outputs, rate limits, and transient provider faults | LiteLLM handles provider-level retries well, but you still need application-level retries when the model returns syntactically valid yet unusable content. This is the cleanest way to separate transport retry from quality retry. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| RapidFuzz | 3.14.x | Fuzzy duplicate detection for focus words, sentences, translations, and normalized definitions | Use inside the acceptance/gating layer after normalization and exact hashing. It is the right first step before adding embeddings or vector infrastructure. |
| unicodedata + hashlib (stdlib) | built-in | Canonical normalization and stable content fingerprints | Use for exact duplicate prevention across reruns: lowercase, accent folding where appropriate, whitespace collapse, punctuation normalization, then hash. |
| dataclasses / existing JSON cache layer | existing | Persist AI candidates, review results, and dedupe fingerprints in the current file-based cache | Reuse the current cache/progress/log/output shape instead of adding a DB. Add new cache namespaces like `sentence_ai_v1`, `field_review_v1`, and `dedupe_v1`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | Golden tests for prompt contracts, schema parsing, duplicate thresholds, and provider fallback behavior | Keep the current test runner. Add fixture-driven tests around structured AI payloads rather than live-provider tests. |
| requests-mock | Mock non-AI providers and preserve current integration behavior | Keep current coverage for web/TTS/export behavior while isolating new AI stack changes. |

## Installation

```bash
# Core AI additions
python -m pip install "litellm>=1.83,<1.84" "tenacity>=9.1,<10" "rapidfuzz>=3.14,<4"

# Existing stack stays in place
python -m pip install -r requirements.txt
```

## Recommended Provider / Model Pattern

Use **role-based model aliases**, not one generic `ai.model` setting.

### Add three AI roles

1. **`sentence_generator`**
   - Primary job: generate 2-4 candidate example sentences in the source language.
   - Optimize for: low latency, low cost, strong multilingual fluency, structured output compliance.
   - Output schema should include: `sentence`, `literal_gloss` or `english_translation`, `register`, `confidence`, `contains_focus_exact`.

2. **`field_reviewer`**
   - Primary job: review and correct translation + definition against the chosen sentence.
   - Optimize for: accuracy over speed.
   - Output schema should include: corrected `translation`, corrected `definition`, `accept/reject`, `reasons`, `confidence`, `needs_human_review`.

3. **`fallback_general`**
   - Primary job: emergency fallback when the preferred role-specific model is unavailable.
   - Optimize for: uptime, not ideal quality.

### Provider pattern

- Put **LiteLLM Router** in front of OpenRouter/Groq/other future providers.
- Configure **ordered deployments** per role rather than a single flat provider list.
- Prefer providers/models that reliably support **JSON schema / structured output**.
- Keep Groq or other fast providers as **burst/fallback capacity**, but do not make them the sole correctness gate unless they pass schema/gating tests consistently.

### Practical starting configuration for this brownfield repo

- Keep the current providers (`openrouter`, `groq`) available.
- Replace the current `_ai_request()` loop with a LiteLLM-backed role router.
- Start with:
  - `sentence_generator`: cheaper fast multilingual model
  - `field_reviewer`: stronger multilingual model
  - `fallback_general`: any currently configured model that still returns usable text
- Store the chosen role and model name in structured logs and cache metadata so quality regressions are traceable.

## Implementation Approach

### 1) Make AI sentence generation primary, not fallback

Current state: web sentences first, AI second.

Recommended change:
- `AI generate candidates` → `validate/gate` → `optional web seed/rewrite fallback`
- Keep Tatoeba only as a salvage source when AI is unavailable or low-yield.

Why: the milestone is explicitly AI-first, and the current low approval rate is tied to weak sentence sourcing.

### 2) Generate structured candidates, not one raw string

Do **one AI call that returns multiple sentence candidates** in a strict schema, instead of repeated one-line free-text calls.

Use a Pydantic schema like:

```python
class SentenceCandidate(BaseModel):
    sentence: str
    english_translation: str
    confidence: float = Field(ge=0, le=1)
    contains_focus_exact: bool

class SentenceGenerationResult(BaseModel):
    candidates: list[SentenceCandidate] = Field(min_length=2, max_length=4)
```

Why:
- fewer provider round-trips
- easier scoring and caching
- better review queue visibility
- easier multilingual generalization than prompt-parsing free text

### 3) Add an explicit AI review/correction stage

For each accepted sentence candidate:
- obtain translation/definition using existing sources as today
- then run a **review schema** that can accept, fix, or reject

Recommended review contract:
- sentence
- source word
- proposed translation
- proposed definition
- corrected translation
- corrected definition
- verdict (`accept`, `corrected`, `reject`)
- machine-readable reasons
- confidence

This is the single most important stack change for raising acceptance rate above the current baseline.

### 4) Add layered duplicate prevention

Use three levels, in this order:

1. **Exact canonical hash**
   - normalized focus
   - normalized sentence
   - normalized definition body

2. **In-run fuzzy duplicate check with RapidFuzz**
   - sentence similarity threshold for near-duplicates
   - definition similarity threshold for repeated senses
   - focus+translation pair similarity threshold for redundant cards

3. **Semantic escalation only if needed later**
   - do **not** start with embeddings or a vector DB
   - only revisit if fuzzy matching misses too many multilingual paraphrase duplicates

### 5) Preserve the existing product shape

Do **not** replace:
- `wordfreq` candidate selection
- `.apkg` export via `genanki`
- current TTS/audio chain
- current JSON cache/progress/log/report outputs

Instead, insert the new AI stack between `candidate word selected` and `CardData finalized`.

That means:
- same CLI entrypoint
- same deck export pipeline
- same audio generation stage
- same file-based artifacts
- richer card validation and richer review metadata

### 6) Make multilingual behavior config-driven

Add a small language capability registry in config, not language-specific branches scattered through code.

Per language, define:
- display name
- wordfreq code
- target translation language
- prompt examples/few-shot snippets if needed
- normalization exceptions
- sentence length bounds
- duplicate normalization rules for clitics/articles where appropriate

This preserves the existing configured-language model while making the AI stages generic.

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| LiteLLM + Pydantic + Tenacity | Keep custom `requests` AI client | Only if the project will stay permanently limited to one or two OpenAI-compatible endpoints and you do not need role-based routing, structured output helpers, cooldowns, or cleaner fallback management. That is not the direction of this milestone. |
| RapidFuzz dedupe | sentence-transformers + FAISS/vector DB | Only if later evidence shows canonical + fuzzy matching misses too many semantic duplicates. For this CLI, that is premature complexity. |
| File cache extensions | SQLite/Postgres/Redis | Only if the tool becomes multi-user, long-running, or needs cross-process shared state. Today it is a local CLI and the current JSON artifact model is a strength. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| LangChain / LlamaIndex | Too much framework weight for a small CLI pipeline. They add abstractions the repo does not need and make brownfield integration harder. | LiteLLM for transport + Pydantic schemas + local orchestration in `deck_builder.py`. |
| Instructor as a first addition | Good library, but overlaps with Pydantic + LiteLLM + Tenacity. For this repo it is one abstraction layer too many on day one. | Keep validation contracts in repo-owned Pydantic models; revisit Instructor later if schema re-ask boilerplate grows. |
| Embeddings/vector infrastructure now | Heavy runtime, larger installs, and unclear ROI before simpler duplicate rules are exhausted. | Canonical normalization + hashes + RapidFuzz thresholds. |
| Replacing `wordfreq` with an AI-picked vocabulary source | Violates milestone scope and removes a validated part of the pipeline. | Keep `wordfreq` as the front door; improve only sentence/definition/translation quality downstream. |

## Stack Patterns by Variant

**If cost is the top constraint:**
- Use a cheaper multilingual model for `sentence_generator`
- Use a stronger model only for `field_reviewer`
- Because review accuracy matters more than generation creativity, and this keeps total AI spend bounded

**If approval rate is the top constraint:**
- Use structured outputs for both generation and review
- Allow the reviewer to correct, not just score
- Because the biggest failure mode is semantically wrong cards surviving too far into the pipeline

**If a provider lacks reliable structured output:**
- Use it only as `fallback_general`
- Run strict local Pydantic validation and reject on parse/schema failure
- Because low-cost text is useful, but only behind a hard gate

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| `litellm>=1.83,<1.84` | Python 3.11 | Fits the repo runtime and modern multi-provider routing use case. |
| `tenacity>=9.1,<10` | Python 3.11 | Safe application-level retry layer around schema/quality failures. |
| `rapidfuzz>=3.14,<4` | Python 3.11 | Good fit for fast local duplicate checks without heavy ML dependencies. |
| `pydantic>=2` | LiteLLM structured output flow / local validation | Reuse existing models rather than adding a second schema system. |

## Sources

- `.planning/PROJECT.md` — milestone scope and brownfield constraints
- `.planning/codebase/STACK.md` — existing Python/Pydantic/requests/genanki stack
- `.planning/codebase/INTEGRATIONS.md` — current provider endpoints and file-based runtime shape
- `/berriai/litellm` via Context7 CLI — router, retries, cooldowns, structured output support
- https://docs.litellm.ai/docs/routing — verified provider routing, retries, cooldowns, deployment ordering
- https://platform.openai.com/docs/guides/structured-outputs — verified JSON schema structured outputs and Pydantic parsing guidance
- `/instructor-ai/instructor` via Context7 CLI — reviewed as an alternative for validation/retry abstraction
- https://python.useinstructor.com/ — verified Instructor capabilities and overlap with this stack
- https://rapidfuzz.github.io/RapidFuzz/ — verified fuzzy matching purpose and performance profile
- `python -m pip index versions litellm instructor rapidfuzz tenacity sentence-transformers` — current package versions checked on 2026-04-15

---
*Stack research for: AI-first multilingual Anki deck generation (stack dimension)*
*Researched: 2026-04-15*
