# SEV-05 — No startup warm-up: the demo's opening line costs 20 seconds

**HIGH** · Finding **L9-04** (live) · Confidence: Confirmed · Evidence: `evidence/L9.md`

## Problem

`keep_alive=30m` (DEC-273) prevents the **second** cold load. It does nothing about the **first**. There
is no startup warm-up, so the model is loaded lazily by the first real dialogue turn — and the first
thing a studio evaluator sees costs **20.1 seconds end-to-end**.

This is the cheapest user-visible win in the review.

## Current shape

Measured live over 4 turns on a freshly booted stack (`/api/ps` empty at boot):

| Turn | `load_duration_ms` |
|---|---:|
| 1 (cold) | **10,515.194** |
| 2 | 7.863 |
| 3 | 10.272 |
| 4 | 10.065 |

`llm_backend_load_latency_seconds` = `{count 4, sum 10.543394, min 0.007863, max 10.515195}`.

So `keep_alive` is verifiably working — min ≈ 0, and Ollama's `/api/ps` showed `qwen2.5:7b` resident with
`expires_at` 29.5 minutes out, every log record carrying `"keep_alive": "30m"`. The residual cost is
entirely the **first** load, which nothing pre-pays. End-to-end that first turn was **20.1s**, against a
3–7s budget.

## Steps

1. Add a startup warm-up: after the app is ready, issue one minimal generation against the configured
   model to force the load, before any player traffic.
2. Put it on the **startup path**, not in the request path — `src/npc_engine/main.py` lifespan, or a
   small module under `setup/`. Keep it async and non-blocking for readiness where possible.
3. Make it **configurable and default-on** (`LLM_WARMUP_ON_STARTUP`), with a named constant for the
   warm-up prompt — no hardcoded literal, and **the prompt must live under `prompts/`**, per CLAUDE.md's
   "no prompt strings outside `prompts/`" rule. A trivial one-token prompt is fine.
4. Fail **soft**: if the warm-up errors (Ollama not up yet), log it structurally via `utils/logging.py`
   and continue. Never let warm-up failure block boot.
5. Consider gating readiness on warm-up completion — but only if it does not deadlock a compose start
   order. If unsure, do not; log-and-continue is the safe default.

## Verification

Write the failing test first:

`tests/unit/setup/test_llm_warmup_on_startup.py`
- With `LLM_WARMUP_ON_STARTUP=True`, app startup issues exactly one generation against a mock adapter.
- With it `False`, zero.
- An adapter raising during warm-up does **not** propagate — the app still starts.

```
pytest tests/unit/setup/test_llm_warmup_on_startup.py -v
make check
```

Live confirmation (this is the real test — rebuild first, the image is not bind-mounted):
```
make eval-stack-up
# then drive the FIRST dialogue turn and read its llm_prompt_eval record
```
Expect `load_duration_ms` on the first *player* turn to be ~0 rather than ~10,515, and end-to-end well
under 20.1s. Also check `llm_backend_load_latency_seconds` — the large `max` should now belong to the
warm-up, not to a player turn.

## Blast radius

Startup path only. No schema, no route, no engine logic. One new config field and one new prompt file.
Risk is boot ordering: if Ollama is not reachable at app start the warm-up must degrade quietly — that
is what step 4 covers, and the test in step 3 of Verification pins it.

**Sequencing:** independent — parallelisable. But land it **before SEV-13**, so DEC-273's amended
constants are measured against a system that warms up.
