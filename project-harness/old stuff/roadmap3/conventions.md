# Roadmap V3 Conventions

## Per-Phase Directory Structure

Each phase directory contains exactly four files:

```
README.md       Goal, scope, entry/exit criteria, affected modules, risks, effort
subphases.md    Detailed steps (Phase 0) or skeleton (Phases 1–4)
decisions.md    Phase-local decision log; accumulates during execution
handoff.md      Filled in at phase end; gates, what shipped, what deferred
```

---

## README.md Template

```markdown
## Goal
[One paragraph — what this phase achieves, framed as an outcome.]

## Why This Phase Exists
[What problem it solves and why it cannot be deferred or merged with another phase.]

## Scope (In)
- [Explicit list of what this phase does.]

## Scope (Out)
- [Explicit list of things tempting to add here but deferred. Name them so they
  don't silently creep in.]

## Entry Criteria
- [What must be true before this phase starts. Reference prior handoff.md.]

## Exit Criteria
[Six gates, made concrete for this phase. Example for gate 3: "scenario_war_breaks_out
and scenario_dialogue_reputation pass with no latency regression vs. Phase 0 baseline."]

## Affected Modules
- src/npc_engine/...  — what changes
- e2e/scenarios/...   — what scenarios run or are added
- tests/...           — where new tests live
- docs/...            — which docs evolve

## Docs to Evolve
- [List which existing docs this phase updates, e.g., docs/PROMPT_DESIGN.md]

## Demo Impact
[What a mentor will see or be able to do differently after this phase closes.]

## Risks
1. [Highest-probability risk] — mitigation: ...
2. ...

## Estimated Effort
[In half-day units. Include: "If I have to cut, cut these subphases first: [list]"]
```

---

## subphases.md — Detail Level

### Phase 0 only: full detail

Each subphase entry must contain:

```markdown
## P0.N — Title (X half-days)

**Goal:** One sentence.

**Steps:**
1. ...

**Files to read/write:**
- Read: ...
- Write: ...

**Expected output:**
[Artifact produced — a log dump, a decision in decisions.md, a saved baseline file, etc.]

**Exit check:**
[How you know this subphase is done. Must be falsifiable.]
```

### Phases 1–4: skeleton only

List subphases with one-line goals. No steps, no files, no exit checks.

**Protocol:** The first subphase of Phases 1–4 is always:

> **P{N}.0 — Flesh out subphases.md (0.5 day)**
> Read Phase {N-1} handoff.md and this phase's README.md. Expand each skeleton
> subphase into full-detail format (same template as Phase 0). Commit the
> expanded subphases.md before starting P{N}.1.

This means subphases are planned at the start of each phase with fresh context
from the prior phase's handoff, not speculatively at roadmap-write time.

---

## decisions.md Template

```markdown
# Phase N Decisions

<!-- Append entries here as decisions are made during execution. -->
<!-- Never edit or delete prior entries — this is an append-only log. -->

## [YYYY-MM-DD] [Short decision title]

**Context:** [1–2 sentences on what prompted the decision.]
**Options considered:** [Brief list.]
**Decision:** [What was chosen.]
**Consequences:** [What this commits to or forecloses.]
**Cross-phase?** [Yes — graduate to project/DECISIONS.md | No — stays here]
```

---

## handoff.md Template

```markdown
# Phase N Handoff

## Gate Status

1. Existing tests pass:
   [ ] YES  [ ] NO — details: ...

2. New tests pass:
   [ ] YES  [ ] NO — details: ...

3. E2E baseline:
   [ ] NO REGRESSION  [ ] REGRESSION  [ ] N/A (Phase 0 produces baseline)
   details: ...

4. Manual sign-off:
   [ ] SIGNED OFF by [name]
   Evidence: [link to scenario output, transcript, or screenshot]

5. LLM judge:
   [ ] PASS  [ ] FAIL  [ ] SOFT GATE (Phase 0)
   Verdict: [saved to e2e/baselines/...]

6. Coverage on new code:
   __% — [ ] PASS (≥78%)  [ ] SOFT FAIL — explanation: ...

## What Shipped
- [List each deliverable that closed during this phase.]

## What Was Deferred
- [item] → ISSUES.md [ISSUE-NNN] or explicitly accepted as out of scope

## What the Next Phase Needs to Know
- [Key findings, surprises, or constraints discovered during execution that the
  next phase's subphase planning must account for.]

## Decisions Graduated to project/DECISIONS.md
- [List entries from this phase's decisions.md that are cross-phase and should
  be copied by the human into project/DECISIONS.md.]

## NEXT_SESSION.md Update

[Paste the full replacement text for project/NEXT_SESSION.md here. Keep it
short — what phase is next, entry criteria status, and 3–5 bullets of context
needed to start cold.]
```

---

## NEXT_SESSION.md Protocol

At the end of each phase:

1. Open `project/NEXT_SESSION.md`.
2. **Replace its entire contents** — do not append. It contains only what is
   needed to start the next phase cold.
3. Contents: which phase is next, entry criteria status (pass/fail), 3–5 bullets
   of context that would take >5 minutes to re-derive from git log.
4. Long-form context (what was tried, decisions, failures) lives in the phase's
   `handoff.md`. NEXT_SESSION.md is a jump-start, not a history.

---

## ISSUES.md Protocol

- Every phase **begins** by reading `project/ISSUES.md`.
- Pull any newly-relevant open issues into this phase's scope (add to
  subphases.md or acknowledge in decisions.md with a rationale for deferral).
- At phase end, append any newly discovered issues that were deferred rather
  than fixed. Format: `ISSUE-NNN: [title] — deferred to [phase or backlog]`.
- Never delete ISSUES.md entries. Mark resolved items `[FIXED]`.

---

## DECISIONS.md Protocol

- Phase-local decisions accumulate in the phase's `decisions.md` (append-only).
- Decisions marked `Cross-phase? Yes` must be copied into `project/DECISIONS.md`
  by the human at phase end. Claude does not edit `project/DECISIONS.md` directly.
- Cross-phase criteria: affects data model, LLM adapter selection, training
  pipeline, API contract, or any decision that binds future phases.

---

## Hard Gate vs Soft Gate

**Hard gate:** Phase does not close until this passes. If a hard gate fails,
either fix the issue, or explicitly reduce scope (create an ISSUE, note in
handoff.md, and document the conscious tradeoff).

**Soft gate:** Record the result in handoff.md. Phase can close even if a
soft gate is not fully met, provided there is a written explanation.

| Gate | Hard/Soft | Notes |
|------|-----------|-------|
| 1. Existing tests pass | HARD | Always |
| 2. New tests pass | HARD | Always |
| 3. E2E baseline | HARD | Phase 0 produces the baseline; gates apply from Phase 1 |
| 4. Manual sign-off | HARD | Always |
| 5. LLM judge | SOFT in Phase 0; HARD from Phase 1 | |
| 6. Coverage ≥ 78% | SOFT | Always |
