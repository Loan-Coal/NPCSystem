# SEV-07 — The gossip tick costs 24.25s: a full corpus reconciliation per propagated pair

**HIGH** · Finding **L13-07** (runtime) · Confidence: Confirmed · Evidence: `evidence/L13.md`

## Problem

The tick landing on the gossip cadence took **24,252 ms**. The five surrounding non-gossip ticks took
433, 455, 486, 493 and 570 ms. Payload: `{'tick_id': 10, 'pairs': 20, 'propagated': 10}`.

That is **~6× the entire interactive dialogue budget**, it recurs on a fixed cadence, and — because
gossip makes **zero LLM calls** — none of the LLM budgeting in SEV-02 or the admission control in SEV-04
would ever shed it. It also contends for the same GPU as the resident model, degrading interactive
dialogue by a path DEC-273 never instrumented.

This is the largest single measured cost in the tick, and nothing in the repo mentions it.

## Current shape

- `gossip` is not an LLM engine: `grep "uses_llm: true" src/npc_engine/engines/contracts/*.yaml` returns
  only `chapter_engine`, `dialogue_engine`, `memory_consolidation_engine`, `quest_generation_engine`.
- The cost is in `_run_side_effects` — `engines/gossip/gossip_handler.py:310-372`: a **serial `for` loop
  over propagated pairs**, issuing up to 6 awaits each, including `refresh_embedding_safely` at `:359`.
- That call reaches `retrieval/embedding/corpus_refresher.py:52-62` → `retrieval/embedding/corpus.py:266`
  → `await reconciler.reconcile_in_session(session)` — **a full reconciliation pass, per pair.**
- Ten propagated pairs ⇒ **ten full reconciliation passes in one tick**, sequentially, each re-embedding
  via `EMBEDDING_MODEL=all-MiniLM-L6-v2` on the same GPU as the resident LLM.
- `gossip_handler.py:120` docstring claims *"a single batch read … and a single batch write"* — true of
  the propagation, **false of the tick**.

## Steps

1. **Hoist the reconciliation out of the per-pair loop.** Run `reconcile_in_session` **once per tick,
   after** the loop, then upsert the affected node ids in a batch. `refresh_corpus_node` already
   separates the two halves (`corpus.py:266-270`), so this is a restructuring, not a redesign — it turns
   10 passes into 1.
2. Batch the remaining per-pair writes (`create_rumor` / `believe_rumor` / `log_gossip`) the way the
   propagation write already is.
3. Fix the `gossip_handler.py:120` docstring to describe what the tick actually does — the current text
   is part of why this went unnoticed for so long (systemic pattern §3.6).
4. Add a wall-clock ceiling assertion on the gossip path. `last_duration_ms` is already recorded per
   engine, so the gate has its input for free.

## Verification

Write the failing test first:

`tests/unit/engines/test_gossip_reconciles_once_per_tick.py` — with N propagated pairs, assert
`reconcile_in_session` is called **exactly once**, not N times. On the current tree this fails with N=10.

Add `tests/unit/engines/test_gossip_tick_duration_ceiling.py` asserting `last_duration_ms` stays under a
named ceiling for a representative pair count.

```
pytest tests/unit/engines/ -v
make check
```

**Measure live — this fix exists for a wall-clock number, so prove the wall-clock number.** Rebuild (the
image is not bind-mounted), advance the clock across a gossip-cadence tick, and read `last_duration_ms`
for `gossip` from `GET /v1/admin/system/engines`. Baseline is **24,252 ms**; surrounding ticks are
433–570 ms. Report the new figure. Timing data only — per invariant 6, cite no judged score.

## Blast radius

`engines/gossip/gossip_handler.py` and its use of the embedding refresher. Correctness risk: the
reconciliation currently runs *between* pair writes, so hoisting it after the loop changes what state
each pass observes. Verify that a rumor created in pair *i* is still correctly embedded when
reconciliation runs once at the end — that is the one behavioural question this fix must answer, and it
belongs in the test from step 1.

Gossip is also the repo's in-house precedent for deterministic (no-model) behaviour, so keep it
deterministic: do not introduce a model call while restructuring.

**Sequencing:** fully independent — parallelisable.
