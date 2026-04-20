# Pitfalls Research

**Domain:** AI-first multilingual Anki deck generation on top of an existing brownfield vocabulary pipeline
**Researched:** 2026-04-15
**Confidence:** MEDIUM

## Critical Pitfalls

### Pitfall 1: Treating the LLM as the source of truth

**What goes wrong:**
Definitions, translations, and example sentences look fluent enough to pass casual inspection, but are semantically wrong for the target lemma, wrong sense, or subtly incompatible with the card's intended meaning.

**Why it happens:**
Teams replace low-quality providers with an LLM and assume fluency equals correctness. They validate syntax and formatting, but not lexical sense, register, morphology, or source-to-target semantic alignment.

**How to avoid:**
- Separate generation from acceptance.
- Require schema-constrained outputs for AI fields so the pipeline can demand explicit fields like `sense`, `confidence`, `reason`, `literal_translation`, and `used_word_form` rather than free text only.
- Add deterministic validators before acceptance: lemma present, target word form present, banned placeholders absent, length bounds, language detection, and source/target non-identity checks where appropriate.
- Add a second-pass semantic review step that can reject or send to review queue instead of silently accepting.
- Preserve provenance per field: provider, prompt version, model, temperature, source evidence, reviewer outcome.

**Warning signs:**
- Acceptance rate improves but user review complaints stay high.
- Definitions sound generic across many unrelated lemmas.
- Cards pass formatting checks but fail human spot checks on meaning.
- Same word gets conflicting definitions across reruns.

**Phase to address:**
Phase 2 - Structured AI output + deterministic validation, then Phase 3 - semantic review gating.

---

### Pitfall 2: Using one-pass generation instead of generation plus acceptance gating

**What goes wrong:**
The pipeline accepts first-pass AI output directly into cache/export. Bad sentences, hallucinated glosses, and mistranslations become sticky because resume/cache treat them as completed work.

**Why it happens:**
Brownfield systems already have "provider returned data => continue pipeline" control flow. Teams bolt AI onto the provider layer but never redesign acceptance states.

**How to avoid:**
- Introduce explicit card states such as `generated`, `validated`, `semantically_reviewed`, `accepted`, `rejected`, `needs_human_review`.
- Cache raw attempts separately from accepted artifacts.
- Never let resume treat "has any AI output" as equivalent to "ready for export".
- Re-run full validation after any interactive or AI-assisted edit.
- Make export consume only accepted cards.

**Warning signs:**
- Resume skips cards that were never actually approved.
- Manual edits or review changes do not trigger revalidation.
- Cache hit rate looks good but final deck quality does not improve.
- Review queue and exported deck disagree.

**Phase to address:**
Phase 1 - pipeline state model and brownfield refactor; Phase 3 - acceptance gate wiring.

---

### Pitfall 3: Weak duplicate control that only catches exact string matches

**What goes wrong:**
Decks ship with near-duplicate cards: same meaning with different punctuation, same sentence with minor inflection changes, or multiple cards generated from different words that collapse to the same learning value.

**Why it happens:**
Existing dedupe often uses exact text or expensive fuzzy comparison at the wrong stage. AI generation increases paraphrase diversity, so duplicate meaning grows faster than duplicate strings.

**How to avoid:**
- Split dedupe into tiers: normalized exact hash, token-normalized fingerprint, then limited fuzzy/semantic comparison on a small candidate set.
- Deduplicate at multiple levels: source lemma, accepted sentence, translated sentence, definition gloss, and final card signature.
- Store reusable normalized forms in cache/indexes instead of recomputing pairwise across the whole run.
- Prefer rejection or regeneration before review when a candidate collides with existing accepted content.

**Warning signs:**
- Many accepted cards differ only by punctuation, articles, or word order.
- Runtime grows superlinearly as seen-sentence count increases.
- Human reviewers keep flagging "already saw this card" despite low exact-match duplicate counts.
- Dedupe logic is concentrated in one expensive validator pass.

**Phase to address:**
Phase 2 - duplicate signature/index redesign; verify again in Phase 4 with dataset-level duplicate audits.

---

### Pitfall 4: Translating snippets without context or terminology controls

**What goes wrong:**
Short sentences and isolated definitions get mistranslated because the translation stage lacks surrounding context, sense hints, term constraints, or formality/style controls.

**Why it happens:**
Teams treat each field as an independent string. Official translation docs explicitly warn that separate texts do not share context and that ambiguous short texts need context or glossary/style features.

**How to avoid:**
- Pass contextual information into translation/review: source lemma, intended sense, generated example sentence, part of speech, register, and optionally a literal gloss.
- Keep related content together when beneficial instead of translating micro-fields in isolation.
- Use glossary/terminology controls where provider supports them; use context for ambiguity, not instruction abuse.
- Record source and target language explicitly when known.
- Add bilingual validation checks for named entities, copied source text, and suspiciously literal word-by-word translations.

**Warning signs:**
- Ambiguous words flip meaning between runs.
- Headlines/snippets translate worse than longer sentences.
- Same proper name or term is transliterated inconsistently.
- Reviewers repeatedly fix tone/register or obvious sense choice errors.

**Phase to address:**
Phase 2 - translation contract redesign; Phase 3 - bilingual review heuristics.

---

### Pitfall 5: No gold set, no eval harness, no calibrated acceptance thresholds

**What goes wrong:**
The team ships prompt/model changes based on vibes. Quality appears improved on a few sample words, but regressions appear later by language, POS, or frequency band.

**Why it happens:**
Brownfield pipelines usually have tests for code behavior, not content quality. AI migration adds stochastic outputs, but teams do not add eval datasets, graders, or release thresholds.

**How to avoid:**
- Build a small but representative gold set segmented by language, part of speech, frequency tier, morphology difficulty, and ambiguity class.
- Score the pipeline at field and card levels: sentence naturalness, sense accuracy, translation adequacy, definition correctness, duplicate rate, acceptance rate, and cost per accepted card.
- Keep frozen prompt/model versions for benchmark runs.
- Gate major changes on eval deltas, not anecdotal spot checks.
- Track both offline metrics and reviewer disagreement rates.

**Warning signs:**
- Teams cannot answer whether quality improved for verbs vs nouns or Spanish vs Russian.
- Prompt tweaks are merged without before/after numbers.
- Acceptance rate rises while review queue severity also rises.
- Different reviewers disagree often but there is no adjudicated benchmark.

**Phase to address:**
Phase 4 - evaluation harness and release gates, with minimal benchmark scaffolding started in Phase 1.

---

### Pitfall 6: Cache/resume poisoning from non-deterministic AI outputs

**What goes wrong:**
Old low-quality generations remain cached after prompt changes, model changes, or validation rule changes. Resume mixes incompatible generations, making debugging and quality attribution impossible.

**Why it happens:**
Brownfield cache keys were designed for deterministic provider fallbacks, not stochastic multi-stage AI generation plus review. Existing codebase already has resume limitations and JSON single-point-of-failure concerns.

**How to avoid:**
- Version cache entries by model, prompt version, schema version, validator version, and review-policy version.
- Separate raw provider cache from accepted card cache.
- Add invalidation/migration rules when prompts or validators change.
- Make progress state restore exact acceptance state, not just "processed" status.
- Quarantine corrupt JSON/cache files instead of failing the whole run.

**Warning signs:**
- After prompt edits, reruns still show old behavior.
- Two cards with identical inputs but different run dates have incompatible field shapes.
- Resume produces inconsistent approval counts.
- Debugging requires deleting the whole cache to get trustworthy results.

**Phase to address:**
Phase 1 - cache/progress model hardening before broad AI rollout.

---

### Pitfall 7: Cost and latency optimization only after quality work is “done” 

**What goes wrong:**
The new AI pipeline is qualitatively better but too slow or expensive to run at deck scale. Serial provider/model fallbacks multiply latency and spend, especially when many candidates are later rejected.

**Why it happens:**
Teams optimize for first visible quality win. In a brownfield generator with thousands of words, unbounded retries and serial calls turn per-card inefficiency into project-level failure.

**How to avoid:**
- Put hard budgets on calls per word, per field, and per accepted card.
- Use cheap deterministic filters before expensive AI review.
- Cache stable prompt prefixes; structure prompts with static content first.
- Use async batch processing for offline generation/evals where SLAs allow.
- Instrument end-to-end metrics: p50/p95 latency, cache-hit rate, token spend, rejection rate after expensive stages, and cost per accepted card.
- Stop early when a candidate is clearly unacceptable instead of completing all downstream stages.

**Warning signs:**
- Cost per accepted card is unknown.
- Most spend happens on cards that are later rejected.
- Queue time grows faster than accepted output count.
- Model/prompt prefixes are mostly identical but cache-hit metrics stay low.

**Phase to address:**
Phase 5 - cost/latency controls, but budget instrumentation should begin in Phase 1.

---

### Pitfall 8: Reviewer workflows that are not auditable or reproducible

**What goes wrong:**
Human review helps temporarily, but decisions are not captured in a reusable way. The same failures return, and acceptance criteria drift between runs or reviewers.

**Why it happens:**
Teams add an ad hoc review queue without normalized rejection reasons, field-level annotations, or replayable fixtures.

**How to avoid:**
- Capture structured reviewer outcomes: accepted/rejected, reason codes, corrected fields, severity, and language pair.
- Feed reviewer outcomes back into eval slices and prompt/validator tuning.
- Preserve before/after card snapshots.
- Use a stable review rubric focused on sense correctness, naturalness, level appropriateness, and duplicate value.

**Warning signs:**
- Review notes are free-text only.
- Same mistake is fixed repeatedly with no systemic rule added.
- Reviewer agreement is low and unmeasured.
- There is no way to sample "all cards rejected for hallucinated definition".

**Phase to address:**
Phase 3 - review queue and taxonomy; Phase 4 - reviewer-driven eval calibration.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Add AI generation directly inside existing `DeckBuilder`/`ProviderManager` branches | Fastest path to demo | Deepens already-concentrated code, makes retries/cache/review logic inseparable | Only for a spike branch, not for milestone implementation |
| Treat `processed` as a single boolean | Simple control flow | Cannot distinguish generated vs accepted vs reviewed; resume becomes unsafe | Never for the new AI pipeline |
| Cache only final field text | Easy reuse | No provenance, no replay, no validator migration path | Only for deterministic legacy providers |
| Free-text reviewer notes only | Faster manual review | No analytics, no threshold tuning, no automated learning | Acceptable only for initial rubric discovery |
| Exact-string dedupe only | Cheap to implement | Near-duplicate decks and reviewer fatigue | Acceptable only as tier-0 dedupe, never as sole dedupe |

## Integration Gotchas

Common mistakes when connecting to external services.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| LLM generation APIs | Free-form outputs parsed with regex/string hacks | Use schema-constrained outputs and typed parsing |
| Translation APIs | Sending isolated short texts without context or glossary support | Send context/sense hints; keep related text together where needed |
| Batch APIs | Assuming output order matches input order | Always join results by custom/request ID |
| Prompt caching | Caching prompts whose changing suffix is inside the cached prefix | Put stable instructions/examples first and variable content last |
| Human review | Letting interactive edits bypass validation | Re-run the same acceptance validators after any edit |

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| O(n²) duplicate comparison over accepted sentences | Runtime degrades sharply as seen-card set grows | Pre-index normalized fingerprints; restrict fuzzy comparisons to candidate subsets | Hundreds to low-thousands of candidates per run |
| Serial fallback across provider -> key -> model -> review stages | Long wall-clock time, high p95 latency | Add budget caps, early exits, and batch/offline processing for non-interactive stages | Full deck builds |
| Re-reviewing uncached static prompt/context on every call | High input token spend with similar prompts | Use prompt caching and stable prompt prefixes | Any large multilingual batch run |
| Expensive semantic review on obviously invalid candidates | Spend concentrated on trash outputs | Run cheap deterministic validators first | Immediately once acceptance rate is below target |

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Storing provider keys in tracked config during AI rollout | Credential leakage across translation/LLM vendors | Standardize env-var secret loading for all providers |
| Logging full prompts/responses with live user/provider secrets or copyrighted context | Sensitive data leakage in generated logs and artifacts | Redact secrets, separate debug logging, and cap retained raw payloads |
| Blindly feeding downloaded examples/web text into prompts | Prompt contamination and licensing ambiguity | Track source provenance and keep imported context reviewable |

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Exporting low-confidence cards because they "look fluent" | Learners memorize wrong meanings or unnatural phrasing | Export accepted-only cards and surface confidence/review queues separately |
| Hiding why a card was rejected | Operators cannot tune prompts or validators | Show normalized rejection reasons and field-level failures |
| Mixing review-only and export-ready content in one output folder | Hard to trust artifacts | Separate raw attempts, review queue, accepted deck, and quality report |

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **AI sentence generation:** Verify accepted sentences are revalidated after manual or model-assisted edits.
- [ ] **Translation upgrade:** Verify short snippets are translated with context/sense support, not isolated strings only.
- [ ] **Duplicate prevention:** Verify near-duplicate audits on accepted cards, not just exact text checks during generation.
- [ ] **Review queue:** Verify rejection reasons are structured and queryable by language, POS, and failure type.
- [ ] **Cache/resume:** Verify prompt/model/validator versioning invalidates stale accepted artifacts.
- [ ] **Cost control:** Verify you can report cost per accepted card and spend by stage.
- [ ] **Evaluation:** Verify prompt/model changes run against a frozen multilingual benchmark before release.

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Hallucinated or wrong-semantic cards accepted into deck | HIGH | Invalidate accepted-card cache for affected prompt/model versions, rerun semantic review, rebuild deck and review queue |
| Duplicate-rich export | MEDIUM | Run dataset-level duplicate audit, create rejection list by card signature, regenerate only collided items |
| Cache/resume poisoning after prompt change | HIGH | Add versioned cache keys, quarantine legacy cache, replay from raw inputs with new acceptance rules |
| Cost blowout from serial AI stages | MEDIUM | Add stage budgets, disable expensive review on obvious failures, switch bulk stages to batch mode, re-baseline cost per accepted card |
| Reviewer inconsistency | MEDIUM | Freeze rubric, backfill reason taxonomy, sample adjudication set, retrain thresholds on adjudicated data |

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Treating the LLM as source of truth | Phase 2 | Sample accepted cards include schema fields, provenance, and deterministic validation results |
| One-pass generation without gating | Phase 1-3 | Export contains only `accepted` cards; resume distinguishes generated vs approved |
| Weak duplicate control | Phase 2 | Duplicate audit on accepted set shows low exact and near-duplicate rates |
| Snippet translation without context | Phase 2 | Ambiguous-word benchmark improves with context-aware translation contract |
| No eval harness | Phase 4 | Prompt/model changes require benchmark report before merge/release |
| Cache/resume poisoning | Phase 1 | Cache keys encode prompt/model/schema/validator versions and resume restores acceptance state |
| Cost/latency neglected | Phase 5 | Dashboard/report shows p50/p95 latency, cache-hit rate, and cost per accepted card |
| Review workflow not auditable | Phase 3 | Rejection reasons and reviewer corrections are queryable and replayable |

## Sources

- Project context: `.planning/PROJECT.md` and `.planning/codebase/CONCERNS.md` — HIGH confidence for brownfield constraints and current failure modes.
- OpenAI Structured Outputs: https://platform.openai.com/docs/guides/structured-outputs — HIGH confidence for schema-constrained output recommendations.
- OpenAI Working with evals: https://platform.openai.com/docs/guides/evals — HIGH confidence for eval/gold-set/release-gate guidance.
- OpenAI Batch API: https://platform.openai.com/docs/guides/batch — HIGH confidence for async cost/throughput controls.
- OpenAI Prompt caching: https://platform.openai.com/docs/guides/prompt-caching — HIGH confidence for prefix-stability and cache metrics guidance.
- Anthropic Prompt caching: https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching — HIGH confidence for cache breakpoint/invalidation pitfalls and cache metrics.
- Anthropic Batch processing: https://docs.anthropic.com/en/docs/build-with-claude/batch-processing — HIGH confidence for asynchronous batch behavior, result ordering, and cost tradeoffs.
- DeepL Translate Text API: https://developers.deepl.com/api-reference/translate — HIGH confidence for "texts are translated independently" and context/model-type caveats.
- DeepL Context parameter guide: https://developers.deepl.com/docs/best-practices/working-with-context — HIGH confidence for ambiguity-resolution and glossary/style-vs-context distinctions.

---
*Pitfalls research for: AI-first multilingual Anki deck generation (brownfield)*
*Researched: 2026-04-15*
