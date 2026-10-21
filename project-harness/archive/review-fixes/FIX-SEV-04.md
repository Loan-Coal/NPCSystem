# SEV-04 — No admission control in front of the single resident model

🔴 **CRITICAL** · Finding **L13-06** (runtime) · Confidence: Confirmed · Evidence: `evidence/L13.md`

## Problem

Nothing arbitrates access to the one resident model. There is no queue, no priority, no semaphore and no
way to distinguish an interactive dialogue turn from background tick work. A player's turn arriving
mid-tick either lands tens of seconds late or **silently downgrades to a canned line** — and that
downgrade has no attributable cause in any log, because contention is not measured.

**This is the central finding for the small-model goal.** The reason a small local model looks bad here
is not the model — it is that the game's own background work is queued in front of the player. Swapping
to a 3B without admission control just makes 84 fast calls collide with one interactive turn instead of
84 slow ones. **Admission control is the prerequisite for the model swap, not a follow-up to it.**

## Current shape

- `grep -rn "Semaphore\|asyncio.Lock\|queue" src/npc_engine/engines/llm/*.py` → **no matches** across
  `ollama_adapter.py`, `factory.py`, `protocols.py`, `openai_adapter.py`, `ollama_payload.py`.
- Nothing distinguishes interactive from background. DEC-273's `engine` metric label is the only
  per-caller signal and it is purely observational — **but it already carries the class distinction, so
  classification costs nothing.**
- `engines/memory_consolidation/memory_consolidation_engine.py:214` fans out up to `MAX_CONCURRENT_TICKS`
  (20 on the eval stack) simultaneous generations at the backend.
- One model fits (DEC-273: `qwen2.5:14b` evicts `qwen2.5:7b`; only one resident).
- `LLM_TIMEOUT_SECONDS=60.0` on the eval stack; dialogue degrades `full → graph_only → canned` on timeout.
- Measured: a single tick containing one consolidation cost **3.2–5.7s** wall-clock for one NPC
  (`memory_consolidation.last_duration_ms: 3202.6`). Saturated case ≈ **84s–220s**.

## Steps

1. Add a **two-class admission gate** in the LLM layer (`engines/llm/`): a semaphore with a slot reserved
   for the interactive class, or a small priority queue. Classify from the existing `engine` label —
   `dialogue` (and proactive-to-player) is interactive; everything tick-originated is background.
2. **Interactive pre-empts.** A dialogue call must never wait behind tick work.
3. **Shed, do not queue.** While an interactive call is active or pending, tick-originated calls are
   *rejected* and fall through to their deterministic/fallback path rather than queueing. Queueing just
   moves the latency; shedding removes it. Pair with SEV-02 step 1 so the shed actually reaches the
   quest triggers.
4. Instrument **`llm_backend_queue_wait_seconds`** alongside the existing DEC-273 latency histogram, so
   contention is visible before it becomes a support ticket.
5. Keep the gate in the LLM layer, not in each engine — one arbitration point, per SRP.

## Verification

Write the failing test first:

`tests/unit/llm/test_admission_control.py`
- With N background calls in flight, an interactive call acquires within a bounded wait (assert on a
  fake clock, not wall time).
- With an interactive call active, a background call is **shed** (returns the fallback path), not queued.
- `llm_backend_queue_wait_seconds` is observed for both classes.

```
pytest tests/unit/llm/ -v
make check
```

**Live verification is the point of this fix.** Rebuild (the image is not bind-mounted), then: drive a
dialogue turn *while* a saturated tick is running, and confirm from the `llm_prompt_eval` records that
the turn's `duration_ms` stays inside the 3–7s budget and the response is **not** `canned`. Compare
against the same scenario before the fix. Use latency stats and `engine_status` timing only — per
invariant 6, do not cite any judged score.

## Blast radius

`engines/llm/` — adapter and factory. Every LLM call site passes through it, so a defect here degrades
everything; keep the gate small and well-tested. No graph schema change, no HTTP contract change. Adds
one metric to the existing metrics endpoint.

**Sequencing:** after SEV-02 and SEV-03, which reduce the offered load this gate then has to arbitrate.
Note this fix invalidates DEC-273's under-load assumptions again — coordinate with SEV-13.
