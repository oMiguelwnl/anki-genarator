# Feature Research

**Domain:** AI-assisted multilingual vocabulary card generation for Anki decks
**Researched:** 2026-04-15
**Confidence:** MEDIUM

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Sense-correct AI sentence generation | A vocab deck is only useful if the target word appears in a natural, learnable context. Anki itself recommends learning language in context, not as isolated lists. | HIGH | Sentence must use the target lemma/inflection intentionally, fit the target language, and avoid bizarre or overly literary phrasing. Generation should be constrained by target sense, part of speech, level, and banned patterns. |
| Sentence-grounded translation | Users expect the translation to match the generated sentence, not just the dictionary headword. | HIGH | Translation should be produced or reviewed with the source sentence + target word + intended sense together. Reject literal-but-wrong translations that miss idiom, tense, polarity, or role. |
| Usage-matching definition/gloss | Users need a short meaning that matches the exact usage in the sentence, not a generic or neighboring sense. | HIGH | Definition should be concise, learner-facing, and aligned to the sentence sense. Prefer one good gloss over multi-sense dumps. |
| Structured generation contract | AI-first pipelines need predictable outputs or they become impossible to validate. | MEDIUM | Use strict structured outputs for fields like lemma, surface form, POS, sentence, translation, definition, confidence, and rejection reasons. This is now a standard way to make model output schema-safe. |
| Duplicate prevention across accepted cards | Repeated cards are a visible quality failure and already a known problem in this brownfield project. | MEDIUM | Do not rely only on exact-string duplicates. Normalize lemma, lowercase/Unicode forms, strip punctuation noise, and detect near-duplicates on sentence meaning or repeated target-sense pairs. |
| Quality-acceptance loop before export | AI output is probabilistic; users expect bad cards to be filtered out before deck export. | HIGH | Each candidate should go through validation/review, not direct acceptance. Acceptance should be based on semantic checks, duplicate checks, and minimum quality thresholds. |
| Explicit rejection and retry behavior | When AI fails, the system should try again or defer instead of silently accepting junk. | MEDIUM | Rejection reasons should be machine-readable: wrong sense, unnatural sentence, bad translation, vague definition, duplicate, malformed output. Retry budget should be bounded. |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Best-of-N candidate generation with ranking | Greatly improves final acceptance rate versus one-shot generation. | HIGH | Generate multiple candidates, then rank/select with a reviewer prompt or scorer. This matches current LLM reliability practice better than trusting the first answer. |
| Separate generator + reviewer roles | Improves semantic accuracy by making one model/output produce and another pass criticize or repair. | HIGH | Reviewer should be allowed to say “reject” or “insufficient confidence,” not forced to fix everything. Anthropic explicitly recommends allowing uncertainty to reduce hallucinated certainty. |
| Language-aware difficulty and register targeting | Makes the deck feel intentionally designed for learners instead of randomly AI-written. | MEDIUM | Control sentence length, vocabulary simplicity, idiom density, and formality by frequency band or learner level. |
| Sense diversity across the deck | Prevents decks from becoming repetitive and increases learning value for polysemous words. | HIGH | Useful after MVP: avoid generating the same semantic frame repeatedly for similar words; balance concrete vs abstract senses where appropriate. |
| Review artifacts for human audit | Helps explain why cards passed or failed and speeds manual spot-checking. | MEDIUM | Store reviewer verdict, confidence, normalized keys, and failure reasons in logs/review queue rather than only final text. |
| Adaptive retry strategy by failure mode | Cuts cost and improves yield by changing prompts based on what failed. | MEDIUM | Example: duplicate -> ask for new context; wrong sense -> reinforce gloss/POS; unnatural sentence -> simplify and shorten. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| One-shot “generate everything in a single prompt and trust it” | Simple to implement; feels fast | Produces brittle output, lower semantic accuracy, weak observability, and poor acceptance rates | Split into generation, validation, repair, and acceptance stages |
| Maximally creative example sentences | Feels impressive and “more human” | Creative outputs skew weird, rare, or culturally noisy; they hurt memorability and learner trust | Prefer short, natural, boring-in-a-good-way sentences tied to common usage |
| Multi-sense definitions dumped into one card | Looks comprehensive | Violates minimum-information learning principles and confuses what the sentence is actually teaching | Force one intended sense per card and one concise gloss |
| Literal translation as the source of truth | Easy to compare mechanically | Sentence translations can be grammatically valid yet semantically wrong for the target usage | Review translation against sentence meaning and intended sense, not word overlap |
| Accepting format-valid cards without semantic review | Easy to ship | Structured output alone prevents malformed JSON, not wrong language content | Treat schema validation as necessary but insufficient; require semantic acceptance |
| Generating many inflection variants of the same lexical item as separate cards by default | Inflates deck size quickly | Creates duplicate learning burden and noisy exports | Canonicalize to lemma-level uniqueness unless morphology is intentionally part of the curriculum |

## Feature Dependencies

```
[Structured generation contract]
    └──requires──> [Semantic validation / reviewer]
                           └──requires──> [Acceptance / rejection loop]
                                                  └──requires──> [Retry strategy]

[Sense-correct sentence generation]
    └──requires──> [Target sense/POS specification]

[Sentence-grounded translation]
    └──requires──> [Accepted sentence candidate]

[Usage-matching definition/gloss]
    └──requires──> [Accepted sentence candidate]

[Duplicate prevention]
    └──requires──> [Normalization keys + accepted-card registry]

[Best-of-N candidate generation]
    └──enhances──> [Acceptance / rejection loop]

[Language-aware difficulty/register targeting]
    └──enhances──> [Sense-correct sentence generation]

[Maximally creative sentences] ──conflicts──> [High acceptance rate]
[Multi-sense definition dumps] ──conflicts──> [Minimum-information cards]
```

### Dependency Notes

- **Structured generation contract requires semantic validation:** schema safety makes the output parseable, but not correct.
- **Translation and definition require an accepted sentence candidate:** otherwise downstream fields optimize around unstable or wrong context.
- **Duplicate prevention requires normalization keys:** exact-string checks miss duplicates caused by casing, Unicode variants, paraphrases, and repeated lemma-sense pairs.
- **Best-of-N enhances acceptance:** multiple constrained candidates are more reliable than trying to repair a single bad first draft.
- **Creative sentence generation conflicts with acceptance targets:** creativity increases novelty faster than it increases pedagogy.

## Expected Acceptance / Quality Behavior

### Sentence acceptance

- Accept only if the sentence is grammatical, natural enough for a native speaker, and centered on the target word’s intended sense.
- Accept only if the target appears in an expected surface form for the language and POS.
- Reject sentences that are too long, overly idiomatic, culturally opaque, nonsensical, or depend on rare context to make sense.
- Reject if the sentence teaches a different sense than the definition/gloss.

### Translation acceptance

- Accept only if the translation preserves sentence meaning, not just word-level correspondence.
- Reject literal translations that distort tense, negation, register, agency, or idiomatic meaning.
- Reject if the translation implies a different sense of the target word than the source sentence does.

### Definition acceptance

- Accept only if the gloss matches the specific usage in the sentence.
- Prefer short learner-facing definitions over dictionary dumps.
- Reject if the gloss is broader, narrower, or semantically adjacent but not actually correct for the sentence.

### Duplicate / uniqueness acceptance

- Reject exact duplicates.
- Reject near-duplicates where the lemma, intended sense, and sentence meaning are materially the same as an already accepted card.
- Flag borderline duplicates for review rather than auto-accepting.

### Quality loop behavior

- Candidate generation should be multi-pass: generate -> validate -> repair or reject.
- A model/reviewer must be allowed to say “I don’t know” / “insufficient confidence” rather than fabricate certainty.
- Stop retrying after a bounded budget; unresolved items should move to review queue or fail cleanly.
- Export should include only accepted cards; rejected cards should leave traceable reasons in logs/reporting.

## MVP Definition

### Launch With (v1)

Minimum viable product — what's needed to validate the concept.

- [ ] Sense-correct AI sentence generation — core product change; directly addresses current low-quality example problem
- [ ] Sentence-grounded translation + usage-matching definition review — needed to fix semantic errors that currently sink acceptance
- [ ] Acceptance/rejection loop with duplicate prevention — needed to raise final approval above 60% instead of exporting junk faster

### Add After Validation (v1.x)

Features to add once core is working.

- [ ] Best-of-N generation with ranking — add once single-path validation is stable and measured
- [ ] Language-aware difficulty/register controls — add when baseline semantic accuracy is reliable across languages
- [ ] Review artifacts and richer failure taxonomies — add when tuning prompts and auditing production quality becomes the bottleneck

### Future Consideration (v2+)

Features to defer until product-market fit is established.

- [ ] Sense diversity optimization across whole deck — valuable, but only after per-card correctness is dependable
- [ ] Personalized examples or learner-profile adaptation — high value later, but premature before generic multilingual quality is solved

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Sense-correct AI sentence generation | HIGH | HIGH | P1 |
| Sentence-grounded translation review | HIGH | HIGH | P1 |
| Usage-matching definition review | HIGH | HIGH | P1 |
| Acceptance/rejection loop | HIGH | MEDIUM | P1 |
| Duplicate prevention | HIGH | MEDIUM | P1 |
| Structured generation contract | HIGH | MEDIUM | P1 |
| Best-of-N candidate ranking | HIGH | HIGH | P2 |
| Language-aware difficulty/register targeting | MEDIUM | MEDIUM | P2 |
| Review artifacts for audit | MEDIUM | MEDIUM | P2 |
| Sense diversity optimization | MEDIUM | HIGH | P3 |

**Priority key:**
- P1: Must have for launch
- P2: Should have, add when possible
- P3: Nice to have, future consideration

## Competitor / Pattern Analysis

| Feature | Traditional dictionary + corpus pipeline | Generic one-shot AI generator | Our Approach |
|---------|------------------------------------------|-------------------------------|--------------|
| Sentence quality | Often limited by source availability and sentence mismatch | Often fluent but semantically unreliable | AI-generated, but only accepted after review against target sense |
| Translation quality | Often literal or service-dependent | Often plausible but inconsistent | Review translation in context of sentence + intended sense |
| Definition quality | Often safe but generic | Often polished but may drift semantically | Prefer short usage-matching gloss with rejection if mismatched |
| Duplicate handling | Usually exact-match only | Often absent | Normalize + detect exact and near duplicates before acceptance |
| Observability | Moderate | Low | Store machine-readable verdicts, reasons, and review traces |

## Sources

- `.planning/PROJECT.md` — project-specific requirements, constraints, and current failure modes (HIGH)
- Anki Manual, “Adding/Editing” and “Duplicate Check”: https://docs.ankiweb.net/editing.html (HIGH)
- Anki Manual, “Effective Learning”: https://docs.ankiweb.net/editing.html#effective-learning (HIGH)
- SuperMemo, “20 rules of formulating knowledge”: https://super-memory.com/articles/20rules.htm (MEDIUM; older but still foundational and cited by Anki)
- OpenAI, “Structured model outputs”: https://platform.openai.com/docs/guides/structured-outputs (HIGH)
- Anthropic, “Reduce hallucinations”: https://docs.anthropic.com/en/docs/test-and-evaluate/strengthen-guardrails/reduce-hallucinations (HIGH)

---
*Feature research for: AI-first multilingual vocabulary card generation*
*Researched: 2026-04-15*
