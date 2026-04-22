# Phase 4: Duplicate Guard and Review Workflow - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `04-CONTEXT.md`.

**Date:** 2026-04-22
**Phase:** 04-duplicate-guard-and-review-workflow
**Areas discussed:** Near-duplicate handling, Duplicate outcome, Review artifact depth, Accepted-card reporting

---

## Near-duplicate handling

### What should count as a near-duplicate worth a closer check?

| Option | Description | Selected |
|--------|-------------|----------|
| Same idea, reworded | Treat obvious paraphrases of an accepted card as near-duplicates. | ✓ |
| Almost same sentence only | Only catch very small wording or punctuation changes. | |
| Whole card overlap | Judge sentence plus lexical fields together. | |
| You decide | Leave the exact boundary to the agent. | |

**User's choice:** Same idea, reworded
**Notes:** Near-duplicate control should be paraphrase-aware, not just punctuation-aware.

### Which cards should new candidates be compared against for duplicate guarding?

| Option | Description | Selected |
|--------|-------------|----------|
| Accepted cards only | Match duplicate control to what would actually ship. | ✓ |
| Accepted and rejected cards | Also block repeats of rejected attempts inside the run. | |
| Accepted plus past artifacts | Broaden protection with prior-run artifacts. | |
| You decide | Leave comparison scope to the agent. | |

**User's choice:** Accepted cards only
**Notes:** Duplicate protection should stay aligned with the accepted-only export boundary.

### How aggressive should the near-duplicate matcher be once a candidate is in the shortlist?

| Option | Description | Selected |
|--------|-------------|----------|
| Balanced threshold | Catch obvious rewrites without crushing legitimate variety. | ✓ |
| Conservative threshold | Only reject very close rewrites. | |
| Aggressive threshold | Reject broader paraphrase families. | |
| You decide | Leave threshold posture to the agent. | |

**User's choice:** Balanced threshold
**Notes:** The user prefers bounded duplicate cleanup, not maximal suppression.

### What should trigger the shortlist before fuzzy comparison runs?

| Option | Description | Selected |
|--------|-------------|----------|
| Focus plus sentence | Key shortlist matching on target word plus normalized sentence. | ✓ |
| Sentence only | Shortlist purely on sentence wording. | |
| Full card bundle | Shortlist on focus, sentence, and lexical fields together. | |
| You decide | Leave shortlist shape to the agent. | |

**User's choice:** Focus plus sentence
**Notes:** The shortlist should be stronger than sentence-only matching without requiring full-card identity.

---

## Duplicate outcome

### What should happen when the pipeline finds an exact duplicate of an accepted card?

| Option | Description | Selected |
|--------|-------------|----------|
| Reject immediately | Keep exact duplicates out with a duplicate reason code. | ✓ |
| Reject to queue | Always surface exact duplicates as review items. | |
| Report only | Count it in diagnostics without blocking it. | |
| You decide | Leave exact-duplicate outcome to the agent. | |

**User's choice:** Reject immediately
**Notes:** Exact duplicates are a hard stop.

### What should happen when the pipeline finds a near-duplicate of an accepted card?

| Option | Description | Selected |
|--------|-------------|----------|
| Reject to queue | Reject the card and preserve evidence for post-run inspection. | ✓ |
| Reject immediately | Treat near-duplicates exactly like exact duplicates. | |
| Keep the best one automatically | Replace the earlier accepted card if the new one scores better. | |
| You decide | Leave near-duplicate disposition to the agent. | |

**User's choice:** Reject to queue
**Notes:** Borderline duplicate calls should stay inspectable without blocking the run.

### If a later candidate looks better but collides with an already accepted card, should it ever replace the earlier accepted one?

| Option | Description | Selected |
|--------|-------------|----------|
| No, keep first accepted | Keep the earlier winner stable for the run. | ✓ |
| Yes, replace if clearly better | Allow score-based winner swaps. | |
| Only exact duplicates replace | Allow limited replacement behavior. | |
| You decide | Leave replacement policy to the agent. | |

**User's choice:** No, keep first accepted
**Notes:** The user wants stable acceptance accounting and no winner-eviction churn.

### How visible should duplicate decisions be in the run outputs?

| Option | Description | Selected |
|--------|-------------|----------|
| Queue plus report | Show duplicate outcomes in both queue artifacts and aggregate reporting. | ✓ |
| Report only | Keep duplicate diagnostics aggregate-only. | |
| Queue-heavy | Put every duplicate case into the queue artifact. | |
| You decide | Leave output visibility to the agent. | |

**User's choice:** Queue plus report
**Notes:** Duplicate outcomes should be visible both per-card and in rollups.

---

## Review artifact depth

### What overall posture should the rejected-item artifacts take in Phase 04?

| Option | Description | Selected |
|--------|-------------|----------|
| Audit-ready and readable | Preserve enough evidence to explain the decision without making the file unworkable. | ✓ |
| Triage-first concise | Keep the queue short and lightweight. | |
| Maximum forensic detail | Put as much evidence as possible directly in the artifact. | |
| You decide | Leave artifact posture to the agent. | |

**User's choice:** Audit-ready and readable
**Notes:** The queue should stay inspectable by humans, not just machines.

### How much before/after content should each rejected or duplicate-queued item carry?

| Option | Description | Selected |
|--------|-------------|----------|
| Relevant card state | Keep the textual state needed to explain the decision. | ✓ |
| Only changed fields | Keep the artifact smaller, with less reconstruction help. | |
| Full card plus candidate dump | Store the heaviest possible local evidence. | |
| You decide | Leave before/after scope to the agent. | |

**User's choice:** Relevant card state
**Notes:** Enough context to explain the decision matters more than minimal file size.

### How much provider provenance should the queue preserve per rejected or duplicate-queued card?

| Option | Description | Selected |
|--------|-------------|----------|
| Field providers plus winning model | Preserve per-field source plus decisive model or provider. | ✓ |
| Final provider only | Preserve only the final provider. | |
| Full provider trace | Preserve provider chain, errors, and timings for every field. | |
| You decide | Leave provenance depth to the agent. | |

**User's choice:** Field providers plus winning model
**Notes:** Provenance should answer who supplied what and who made the final call.

### How detailed should the review reason taxonomy be for Phase 04?

| Option | Description | Selected |
|--------|-------------|----------|
| Specific duplicate and review codes | Distinguish duplicate classes and review-failure families. | ✓ |
| Broad buckets only | Collapse reasons into a small set of groups. | |
| Very fine-grained subcodes | Track every branch with deep subcodes. | |
| You decide | Leave reason-code detail to the agent. | |

**User's choice:** Specific duplicate and review codes
**Notes:** The user wants reporting detail without exploding the taxonomy.

---

## Accepted-card reporting

### Which acceptance metrics should become top-line in `quality_report.json`?

| Option | Description | Selected |
|--------|-------------|----------|
| Acceptance plus duplicate quality | Make accepted-card rate, duplicate reject rate, and corrected accepts the primary story. | ✓ |
| Acceptance rate only | Focus on raw throughput. | |
| Ops-heavy summary | Put provider and error counters on equal footing with acceptance. | |
| You decide | Leave top-line metrics to the agent. | |

**User's choice:** Acceptance plus duplicate quality
**Notes:** The report should answer quality, not only throughput.

### How should duplicate diagnostics be broken down in the report?

| Option | Description | Selected |
|--------|-------------|----------|
| Exact vs near by level | Split exact and near-duplicate counts by level and overall. | ✓ |
| Exact vs near overall only | Keep the split only at the run-summary level. | |
| One duplicate bucket | Collapse all duplicate counts together. | |
| You decide | Leave duplicate-report granularity to the agent. | |

**User's choice:** Exact vs near by level
**Notes:** Duplicate reporting should support later tuning and evaluation.

### How should accepted cards be classified in the report?

| Option | Description | Selected |
|--------|-------------|----------|
| Clean vs corrected | Preserve a split between untouched accepts and corrected accepts. | ✓ |
| Single accepted pool | Treat all accepted cards the same once shipped. | |
| Add quality bands | Add a new accepted-card tiering scheme. | |
| You decide | Leave accepted-card classification to the agent. | |

**User's choice:** Clean vs corrected
**Notes:** Accepted-with-corrections should remain visible in reporting, not move into the queue.

### How should these Phase 04 metrics be organized inside `quality_report.json`?

| Option | Description | Selected |
|--------|-------------|----------|
| Dedicated sections | Give duplicate, acceptance-quality, and review metrics their own sections. | ✓ |
| Flat counters only | Keep metrics in a flatter shape. | |
| Sections plus sample focuses | Add dedicated sections plus sample focus words. | |
| You decide | Leave report organization to the agent. | |

**User's choice:** Dedicated sections
**Notes:** The report should be easier for downstream agents and humans to consume directly.

---

## the agent's Discretion

- Exact duplicate-signature implementation details.
- Exact fuzzy threshold values and shortlist size.
- Exact JSON field names and nesting.
- Exact reason-code names under the chosen taxonomy.

## Deferred Ideas

None.
