# Phase 1: Run State Foundation - Context

**Gathered:** 2026-04-15
**Status:** Ready for planning

<domain>
## Phase Boundary

Introduce explicit pipeline states, versioned cache and progress contracts, accepted-only export gating, and minimal orchestration seams that let later AI-first phases land without destabilizing the existing CLI foundation.

</domain>

<decisions>
## Implementation Decisions

### Card lifecycle
- **D-01:** AI is the primary generator and the primary reviewer in the new pipeline foundation.
- **D-02:** The canonical flow is `AI-generated -> AI-reviewed -> accepted/rejected`; there is no `human-review` state in the main execution path.
- **D-03:** `accepted` means the card content is semantically correct, not merely export-prepared.
- **D-04:** Hard technical failures should still pass through AI review/correction when feasible before final rejection.
- **D-05:** If AI review cannot correct the card with confidence, finalize it as `rejected` with machine-readable reason codes.
- **D-06:** Keep the canonical state model small; detailed nuance belongs in reason codes, flags, and per-stage history rather than many top-level states.

### Cache and resume
- **D-07:** Resume must be deterministic when the saved state is compatible, restoring execution position and random state rather than only deduping processed items.
- **D-08:** Cache and progress artifacts must carry compatibility fingerprints derived from model, prompt, schema, and validator compatibility so stale artifacts can be invalidated automatically.
- **D-09:** Corrupt or incompatible cache/progress files should be quarantined, logged, and bypassed so the runtime can continue with clean regeneration.
- **D-10:** Progress checkpoints should be written only after a card reaches a final decision (`accepted` or `rejected`), not at arbitrary intermediate steps.

### Audit outputs
- **D-11:** `review_queue.json` should contain only `rejected` cards.
- **D-12:** Per-card audit data must preserve before/after content, reason codes, and model/provider provenance for later analysis.
- **D-13:** Accepted cards that required AI correction stay out of `review_queue.json`; they should be counted through aggregate metrics in `quality_report.json`.
- **D-14:** `review_queue.json` and `quality_report.json` should remain per-run snapshots in the current output contract.

### Refactor scope
- **D-15:** Phase 1 should introduce minimal but real seams around progress/state handling, final card decision gating, and accepted-only export filtering.
- **D-16:** `ProviderManager` should stay mostly intact in this phase, aside from the minimum hooks or metadata needed for fingerprints and state decisions.
- **D-17:** Migration of old cache/progress artifacts should be opportunistic: reuse what is safe, quarantine/invalidate what is not, and regenerate cleanly.
- **D-18:** Add targeted tests for the touched foundation behavior instead of trying to characterize the entire pipeline before refactoring.

### the agent's Discretion
- Exact naming of state enums, reason-code fields, and fingerprint structures.
- Whether `AI-reviewed` is persisted as an explicit state or represented through stage history plus final status, as long as the canonical flow remains clear.
- Exact quarantine file naming and storage layout.
- Exact helper/service boundaries, as long as the refactor stays minimal and preserves the existing CLI contract.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone scope
- `.planning/PROJECT.md` — Product direction, non-negotiables, and the AI-first transition constraints.
- `.planning/REQUIREMENTS.md` — Phase 1 requirements for state, compatibility, and export behavior.
- `.planning/ROADMAP.md` — Phase 1 goal, success criteria, and plan breakdown.
- `.planning/STATE.md` — Current milestone position and carried decisions.

### Codebase analysis
- `.planning/codebase/ARCHITECTURE.md` — Current runtime layers, state flow, and export boundaries.
- `.planning/codebase/CONCERNS.md` — Known resume bug, JSON fragility, and orchestration concentration risks.
- `.planning/codebase/STRUCTURE.md` — Where progress, export, tests, and runtime artifacts currently live.
- `.planning/codebase/CONVENTIONS.md` — Repo-specific guidance for helper extraction, JSON/file handling, and focused tests.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ankideck_generator/core/models.py::ProgressState` — Already stores `level`, `index`, `rng_state`, processed focus/sentences, and card count; good base for deterministic resume metadata.
- `ankideck_generator/core/deck_builder.py::ProgressStore` — Existing load/save seam for progress JSON; natural place for compatibility checks and quarantine handling.
- `ankideck_generator/core/models.py::LogRecord` and `ankideck_generator/core/deck_builder.py::BuildStats.needs_review_items` — Existing structured audit payloads that can back richer rejected-card reporting.
- `ankideck_generator/core/deck_builder.py::_write_quality_outputs()` — Central place to keep snapshot outputs while refining what goes into `review_queue.json` and `quality_report.json`.
- `ankideck_generator/core/deck_builder.py::export_deck()` — Natural gate for accepted-only export behavior.

### Established Patterns
- Runtime durability is file-based: cache, progress, logs, and output reports are all JSON artifacts on disk.
- Validation already distinguishes hard and soft failures through existing error sets and `validate_card()` behavior.
- The codebase favors small helper extractions around large orchestration methods instead of sweeping rewrites.

### Integration Points
- `ankideck_generator/core/deck_builder.py::DeckBuilder.build()` currently loads progress and seeds validation context; deterministic resume needs to be restored here.
- `ankideck_generator/core/deck_builder.py::_save_progress()` is the current checkpoint writer and should align with final-card decisions.
- `ankideck_generator/core/deck_builder.py::_record_log()` is the current path that builds per-card audit records and rejected-item payloads.
- `ankideck_generator/core/deck_builder.py::export_deck()` and `_write_quality_outputs()` preserve the current output contract and must stay compatible.

</code_context>

<specifics>
## Specific Ideas

- Mainline execution must stay autonomous because runs can exceed 1000 words.
- AI both generates and reviews cards in the new foundation.
- The planner should treat "keep the state model small" as a real constraint, not just a preference.

</specifics>

<deferred>
## Deferred Ideas

- Broad `ProviderManager` decomposition — defer to a later phase unless Phase 1 reveals a hard blocker.
- Fully versioned audit artifact archives per run — defer unless snapshots plus JSONL logs prove insufficient.

</deferred>

---

*Phase: 01-run-state-foundation*
*Context gathered: 2026-04-15*
