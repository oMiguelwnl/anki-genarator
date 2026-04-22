# Phase 3: contextual-lexical-review - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `03-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-20T18:55:47.153Z
**Phase:** 03-contextual-lexical-review
**Areas discussed:** Review routing, Correction scope, Ambiguous senses, Acceptance bar

---

## Review routing

**Question:** When the lexical reviewer sees a fixable issue, what should happen by default?

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-correct and continue | Keep long runs autonomous and let accepted cards carry correction audit data. | ✓ |
| Queue for human review | Do not auto-accept corrected cards; send them to later review instead. | |
| Accept or reject only | No correction step; the reviewer can only approve or discard. | |

**Question:** If the reviewer is still not confident after checking sentence context, what should the fallback be?

| Option | Description | Selected |
|--------|-------------|----------|
| Reject to queue | Record structured reason codes in `review_queue.json` and keep the run moving. | ✓ |
| Pause for edit | Stop the run and ask for interactive correction right away. | |
| Human-review state | Add a dedicated runtime state for later manual triage instead of treating it as rejected. | |

**Question:** Should uncertain cards interrupt the run?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep moving | Do not block long unattended runs; log the card for later handling. | ✓ |
| Only in interactive mode | Pause only when the operator already chose a hands-on run. | |
| Always pause | Every uncertain card stops the run until someone decides. | |

**Question:** How visible should accepted corrections be in audit data?

| Option | Description | Selected |
|--------|-------------|----------|
| Full before/after | Keep field snapshots plus reason codes for corrected accepts. | ✓ |
| Aggregate counts only | Count corrected accepts, but do not preserve field-level snapshots. | |
| Treat as clean accepts | Once accepted, corrected cards look the same as untouched cards. | |

**User's choice:** Autonomous correction when fixable, rejected queue fallback when not confident, no blocking review lane, full audit for corrected accepts.
**Notes:** Manual follow-up should happen after the run rather than by interrupting execution.

---

## Correction scope

**Question:** What fields should the reviewer be allowed to change?

| Option | Description | Selected |
|--------|-------------|----------|
| Definition + translation | Keep Phase 3 focused on lexical correction while treating the chosen sentence as the anchor. | ✓ |
| Definition only | Safer and narrower, but leaves more sentence-vs-translation mismatches unresolved. | |
| Definition + translation + sentence | More recovery power, but it starts to overlap the sentence-generation phase. | |

**Question:** If the accepted sentence and the current lexical meaning clash, what should win?

| Option | Description | Selected |
|--------|-------------|----------|
| Sentence is the anchor | Keep the accepted sentence fixed and realign definition/translation to match its usage. | ✓ |
| Reject the card | Do not try to repair a meaning mismatch once the sentence is chosen. | |
| Allow sentence rewrites | Let lexical review rewrite the sentence so the other fields can stay closer to the original target. | |

**Question:** When only one lexical field is wrong, should review patch minimally or regenerate the whole lexical bundle?

| Option | Description | Selected |
|--------|-------------|----------|
| Minimal patch | Change only the field that is wrong if the other field still matches the sentence context. | ✓ |
| Regenerate both together | Always rebuild translation and definition as one pair after any lexical issue. | |
| Reject instead | Do not do partial repair; either the bundle is already right or the card is discarded. | |

**Question:** Should the visible focus word stay locked once the sentence is accepted?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep focus locked | The card keeps the chosen target word; lexical review does not retarget it. | ✓ |
| Allow nearby form fixes | Review may change the visible focus only for obvious inflection or lemma mistakes. | |
| Allow any visible field | Review can freely change focus, sentence, definition, and translation if that salvages the card. | |

**User's choice:** Phase 3 corrects only lexical fields, keeps the sentence and visible focus anchored, and prefers minimal repair.
**Notes:** This keeps lexical review from reopening sentence-generation ownership.

---

## Ambiguous senses

**Question:** If several senses are plausible for the sentence, what should happen by default?

| Option | Description | Selected |
|--------|-------------|----------|
| Pick best match | Choose the sense that best fits the accepted sentence and keep the run moving. | ✓ |
| Queue for review | Do not auto-pick when more than one sense looks viable. | |
| Reject as ambiguous | Treat lexical ambiguity itself as a discard reason. | |

**Question:** How much meaning can the final learner-facing definition include?

| Option | Description | Selected |
|--------|-------------|----------|
| One sense only | Keep the final gloss concise and tied to one sentence-specific meaning. | ✓ |
| Up to two short senses | Allow a small dual-sense gloss when the sentence genuinely supports both. | |
| Multiple common senses | Show several meanings on one card when the word is broadly ambiguous. | |

**Question:** What ambiguity evidence should be preserved for later audit?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep losing candidates too | Store the chosen gloss, the other strong candidates, and reason codes for why one won. | ✓ |
| Chosen gloss + reasons | Keep only the selected sense plus a short rationale. | |
| Final gloss only | Once the winner is chosen, discard the rest of the ambiguity trail. | |

**Question:** When should ambiguity become manual follow-up instead of an auto-pick?

| Option | Description | Selected |
|--------|-------------|----------|
| Only when not justifiable | Escalate only if the reviewer cannot clearly justify one sense against the sentence. | ✓ |
| Any multi-sense case | If more than one good sense exists, push it out for later review. | |
| Never escalate | Always auto-pick the best available sense, even for close calls. | |

**User's choice:** Auto-pick a single sentence-matched sense, but keep strong losing candidates for audit and escalate only when the winner cannot be justified.
**Notes:** Final cards should stay precise and uncluttered even when internal ambiguity exists.

---

## Acceptance bar

**Question:** After AI or manual correction, what validation should rerun before acceptance?

| Option | Description | Selected |
|--------|-------------|----------|
| Full suite, same thresholds | Rerun the normal deterministic validators again, using the same hard-vs-soft policy as the rest of the pipeline. | ✓ |
| Lexical checks only | Recheck definition/translation correctness, but do not rerun the whole card gate. | |
| Light review gate | Use a looser post-correction check than a never-corrected card would face. | |

**Question:** Can a corrected card still be accepted with soft warnings?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, same policy | Corrected cards follow the same hard/soft threshold as other cards after revalidation. | ✓ |
| No, must be fully clean | Any corrected card must pass with zero warnings before it can be accepted. | |
| Only audio soft warnings | Allow only post-acceptance audio-related warnings to remain. | |

**Question:** Should manual interactive edits use the exact same acceptance gate as AI corrections?

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, same gate | Human edits do not bypass validation; they rerun the same deterministic checks. | ✓ |
| Slightly looser for humans | Manual edits get a softer acceptance threshold than AI edits. | |
| Humans can force accept | An operator may override validators and push an edited card through. | |

**Question:** If a correction fails revalidation, what should happen?

| Option | Description | Selected |
|--------|-------------|----------|
| Reject to queue | Keep before/after snapshots, attach reason codes, and send the card to follow-up. | ✓ |
| Roll back and try original | Discard the correction attempt and see if the pre-correction card can still pass. | |
| Pause for manual choice | Stop the run whenever a correction does not survive the gate. | |

**User's choice:** Revalidate corrected cards with the full existing gate, keep the normal hard/soft policy, and reject failed corrections into the queue instead of overriding or pausing.
**Notes:** Manual interactive edits should no longer have a bypass path after Phase 3.

---

## the agent's Discretion

- Exact verdict schema and reason-code naming.
- Exact service/helper extraction boundaries.
- Exact tie-break logic for sense selection, as long as it is explainable in audit data.
- Exact storage shape for losing-candidate evidence.

## Deferred Ideas

None — discussion stayed within phase scope.
