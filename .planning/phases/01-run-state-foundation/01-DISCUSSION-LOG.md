# Phase 1: Run State Foundation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-15
**Phase:** 01-run-state-foundation
**Areas discussed:** Estados do card, Cache e resume, Auditoria e review queue, Profundidade do refactor

---

## Estados do card

| Option | Description | Selected |
|--------|-------------|----------|
| Generated -> Reviewed -> Accepted/Rejected/Human review | Explicit triage before a final decision | |
| Generated -> Accepted/Rejected | Leaner flow with no dedicated review stage | |
| Generated -> Validated -> Accepted/Rejected | Separate technical validation from semantic review | |
| Custom flow | AI generates and AI reviews | ✓ |

**User's choice:** AI generates, and AI reviews.
**Notes:** No human-review path in the main flow because the system must scale past 1000 words. Hard failures should still be reviewed/corrected by AI when possible; unresolved cases end as rejected with reason codes. `accepted` means semantically correct content, and the state model should stay small.

---

## Cache e resume

| Option | Description | Selected |
|--------|-------------|----------|
| Deterministic continuation | Restore exact saved position and RNG state when compatible | ✓ |
| Same final result | Allow some regeneration as long as accepted output stays stable | |
| Best-effort dedupe | Resume only avoids obvious repeats | |
| Let the agent decide | Delegate rigor choice | |

**User's choice:** Deterministic continuation, automatic invalidation of incompatibilities, quarantine for corrupt/incompatible files, and checkpoint only after final card decisions.
**Notes:** Compatibility should be driven by fingerprints across prompt/model/schema/validator compatibility, not by manual operator judgment.

---

## Auditoria e review queue

| Option | Description | Selected |
|--------|-------------|----------|
| Rejected + flagged/corrected | Keep rejected items and accepted-but-corrected items together | |
| Only rejected | Detailed queue only for items that stay out of the deck | ✓ |
| Everything non-clean | Include retries, warnings, corrections, and rejections | |
| Let the agent decide | Delegate the queue boundary | |

**User's choice:** `review_queue.json` should contain only rejected cards.
**Notes:** Per-card audit must still preserve before/after content plus provenance. Accepted cards corrected by AI should be reflected in aggregate metrics, not in the detailed queue. Output artifacts stay as per-run snapshots.

---

## Profundidade do refactor

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal but real seams | Extract only the foundation seams this phase needs | ✓ |
| Medium modularization | Separate several services now | |
| Aggressive refactor | Reorganize `DeckBuilder` heavily in Phase 1 | |
| Let the agent decide | Delegate refactor depth | |

**User's choice:** Minimal but real seams.
**Notes:** `ProviderManager` should stay mostly untouched for now. Old cache/progress compatibility should be opportunistic, not permanent baggage. Testing should focus on the behaviors touched in this phase.

---

## the agent's Discretion

- Exact state and fingerprint field naming.
- Exact helper boundaries for progress, final decision gating, and export filtering.
- Exact quarantine file layout and metadata shape.

## Deferred Ideas

- Broad `ProviderManager` split — later phase if foundation work shows it is necessary.
- Per-run archived audit artifact sets — later phase if snapshots plus logs are not enough.
