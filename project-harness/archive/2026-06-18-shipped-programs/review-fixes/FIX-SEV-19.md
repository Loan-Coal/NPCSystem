# FIX-SEV-19 — Refactor the worst >40-line functions; ratchet the gate down

**Severity:** MEDIUM (large) · **Decision:** DEC-117 (gate + fix worst, waive rest)

## Problem
The strict 40-line function rule (R006) is enforced via a grandfathered baseline, so ~15 pre-existing
violators are tolerated — including `advance()` at **373 lines / nesting depth 7**. DEC-117: refactor the
worst offenders below the limit, ratchet the baseline down, and log per-function DEC waivers for the few
that are genuinely cohesive.

## Current shape (verify against code now)
- `scripts/check_rules.py` R006 detects functions whose AST span > `MAX_FUNCTION_LINES` (40); accepted
  violations live in a baseline (`make check-rules-update` re-baselines).
- Worst offenders (from L5): `scheduler/tick_scheduler.py` `advance()` (~373, depth 7),
  `auth/middleware.py` `dispatch()` (~201), `data/api_seeder.py` `seed()` (~202),
  `retrieval/subgraph_retriever.py` `assemble_tier_a_context()` (~186), + ~11 more (79–200 lines).

## Steps
1. Refactor `advance()`, `dispatch()`, `seed()`, `assemble_tier_a_context()` by extracting named helpers so
   each top-level function is ≤40 lines and nesting ≤3. Behavior-preserving — lean on existing tests; add
   characterization tests first where coverage is thin.
2. Run `make check-rules-update` to ratchet the R006 baseline down to the new (smaller) set.
3. For any remaining function that is genuinely one cohesive unit (e.g. a dispatch table), add a
   `DECISIONS.md` per-function waiver rather than an artificial split.

## Verification
- `make check-rules` shows fewer R006 entries; the refactored functions pass; `pytest` for each touched
  module green; `make check`.

## Blast radius
`scheduler/tick_scheduler.py`, `auth/middleware.py`, `data/api_seeder.py`, `retrieval/subgraph_retriever.py`
(+ others), `scripts/check_rules.py` baseline, `DECISIONS.md`. **Refactor of hot paths — do incrementally,
one function per commit, tests green between each.**
