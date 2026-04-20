# Phase 2: AI Sentence Generation - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-20
**Phase:** 02-ai-sentence-generation
**Areas discussed:** Candidate Contract, Constraint Strictness, Fallback Policy, Sentence Style

---

## Candidate Contract

| Option | Description | Selected |
|--------|-------------|----------|
| 3 candidatos | Small, rankable set; enough room for selection without large cost growth. | ✓ |
| 1 candidato | Closest to current flow and cheapest, but leaves little room for ranking or recovery. | |
| 5+ candidatos | More coverage and comparison, but increases cost, latency, and validation load. | |

**User's choice:** 3 structured candidates per word.
**Notes:** Follow-up clarified that each candidate should include sentence text plus essential metadata, not a rich audit-heavy payload.

---

## Constraint Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Contrato duro | Prompt/schema enforce target form, POS, sense, and level up front; mismatches are rejected early. | ✓ |
| Meio-termo | Target form and level are hard; POS/sense act as strong guidance. | |
| Mais solto | Prioritize naturality and rely on downstream validators to recover later. | |

**User's choice:** Hard generation contract.
**Notes:** This locks Phase 2 toward early rejection instead of late salvage.

---

## Fallback Policy

| Option | Description | Selected |
|--------|-------------|----------|
| Salvage tardio | AI tries first; web sources only enter late and in a bounded way. | ✓ |
| Fallback por falha | Web sources enter earlier, but only for specific failure modes. | |
| AI quase sem web | Web remains an extreme last resort, favoring purity over coverage. | |

**User's choice:** Late bounded salvage.
**Notes:** Preserves AI-first behavior without fully dropping bounded non-AI recovery.

---

## Sentence Style

| Option | Description | Selected |
|--------|-------------|----------|
| Natural cotidiana | Everyday plausible speech, not didactic or meta-example phrasing. | ✓ |
| Learner-first curta | Shorter and simpler, even if somewhat repetitive. | |
| Natural mais variada | Still natural, but with broader structures and register variety. | |

**User's choice:** Natural everyday sentences.
**Notes:** The desired tone stays learner-friendly but should sound like real speech, not a teaching sentence.

## the agent's Discretion

- Exact schema field names.
- Exact prompt versioning structure.
- Exact retry and ranking thresholds.

## Deferred Ideas

- 5+ candidate packs with richer confidence payloads.
- Translation/definition review work belongs to Phase 3.
