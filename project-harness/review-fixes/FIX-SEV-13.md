# SEV-13 — Amend DEC-273: its constants are contradicted on 3 of 5 claims

**HIGH** · Finding **L9-03** + **L9-04** (live) · Confidence: Confirmed · Evidence: `evidence/L9.md`

## Problem

DEC-273 is three days old and already being cited as settled fact — this review's own brief instructed
workers to "build on rather than repeat" its numbers. Re-measured live over four turns, **three of its
five claims do not reproduce.**

The mechanism DEC-273 describes is right. Its constants are wrong, and they are wrong in the optimistic
direction, which is the dangerous one: they under-state how little headroom the interactive budget has.

## Current shape — measured vs recorded

| DEC-273 claim | Measured live (4 turns) | Verdict |
|---|---|---|
| decode ≈ 97% of a warm turn | **68.7% / 87.4% / 84.4%** | **CONTRADICTED** |
| prefill prefix-cached, effectively free (~0.05s) | **1,779 / 540 / 670 ms** — 11–30% of the turn | **CONTRADICTED** |
| warm dialogue 3.5–4.2s | **4.79–5.95s** backend, **5.26–6.39s** end-to-end | **CONTRADICTED** |
| cold load 10.3s | **10.515s** | CONFIRMED |
| fixed by `keep_alive=30m` | 2nd load fixed (7.9/10.3/10.1 ms); **1st untouched** | **HALF TRUE** |

Warm dialogue is still inside the 3–7s budget — but at 5.26–6.39s end-to-end it sits near the top of it,
not comfortably in the middle. And the *first* turn costs **20.1s** because there is no warm-up (SEV-05).

Not the fallback path: real world-grounded prose, `llm_calls_total`=4, no `fallback=` label. ISSUE-265 did
not fire, so these are genuine model numbers.

## Steps

1. **Amend DEC-273 in place — do not retract it.** Its mechanism (decode-dominated, prefix-cached
   prefill, keep_alive fixes eviction) holds; replace the constants and mark the amendment with today's
   date and this review's HEAD.
2. State the measurement conditions explicitly, which the original omits: idle backend, single session,
   no concurrent tick. Add the caveat that **these are best-case numbers** — L13-06 shows a background
   tick can push an interactive turn past its 60s timeout into `canned`, so the warm-turn figure is not a
   guarantee under load.
3. Record the `keep_alive` result precisely: it prevents the **second** cold load, not the first. Point
   at SEV-05.
4. Preserve DEC-273's NULL result verbatim — schema trimming moved decoded tokens 70.0 → 72.0. It remains
   true and remains a reason not to re-propose schema trimming.
5. **Archive ISSUE-273 while here** — it is fixed but still open. The `has_draft_quest` guard exists at
   `engines/quest/world_state_quest_trigger.py:150`, and `:Quest` held steady at 18 across 6 advances.
   Mark `## [FIXED] ISSUE-273:`, add the `**Fixed:**` line, and move it verbatim into
   `archive/ISSUES_RESOLVED.md` per the CLAUDE.md procedure.
6. Note in the amendment that `llm_backend_latency_seconds` is a count/sum/min/max summary with **no
   buckets**, so no p50/p95 is derivable from the endpoint (that is L9-06, logged separately).

## Verification

Documentation change — no unit test. Verify by:

```
make check-ledger-ids     # ISSUE-273 move must not break id monotonicity
make check
```

Confirm ISSUE-273 appears in exactly one file after the move, and that nothing still cites it as open.

**Re-measure before writing the numbers.** Do this after SEV-05 lands so the figures describe a system
that warms up. Rebuild first — the app image is not bind-mounted, so measuring without a rebuild
re-records stale numbers, which is precisely how DEC-273 acquired its wrong constants.

## Blast radius

`project-harness/DECISIONS.md` and `ISSUES.md` / `archive/ISSUES_RESOLVED.md`. No source change.

The real risk is doing it too early: if SEV-04 (admission control) or SEV-06 (token cap) land after this,
the constants move again. Sequence it late, and say in the entry which fixes were in the tree when the
numbers were taken — that single line is what would have prevented this finding.

**Sequencing:** after SEV-05. Ideally after SEV-06 too, since that changes decoded token counts directly.
