# SEV-06 — `max_tokens: 512` vs "1–3 sentences", and no structural cap on `npc_response`

**HIGH** · Finding **L12-12** (prompt) · Confidence: Confirmed · Evidence: `evidence/L12.md`

## Problem

The dialogue prompt asks for "1–3 sentences". `max_tokens` is **512** — roughly 3–4× headroom — and
**nothing structurally caps `npc_response` length**. Decode is the dominant cost of a warm turn and
scales directly with output tokens, so every token the model is permitted to emit beyond the intended
length is paid for on the interactive path.

**This fix is free.** It touches `llm_config.yaml` and `dialogue_models.py`, **not the prompt**, so
`dialogue_prompt_hash` is unchanged and eval comparability survives. L12 recommends it as the first move
ahead of any prompt rewrite, for exactly that reason.

Do **not** confuse this with schema trimming: DEC-273 measured that as a NULL result (decoded tokens
70.0 → 72.0). Trimming the *schema* does nothing; capping *length* is a different lever.

## Current shape

- `src/npc_engine/engines/dialogue/llm_config.yaml` — `max_tokens: 512`.
- `src/npc_engine/engines/dialogue/dialogue_models.py` — `npc_response` is an unconstrained `str` on the
  generation schema; no `max_length`.
- The prompt's length guidance ("1–3 sentences") is advisory prose with no structural backstop.
- Measured decode share of a warm turn, live: **68.7 / 87.4 / 84.4%** (L9-03 — note this contradicts
  DEC-273's ~97%, but decode still dominates, so the lever holds).

## Steps

1. Add `max_length` to `npc_response` in `dialogue_models.py`, sized to a genuine 1–3 sentence reply.
   Derive the number from observed good outputs — do not guess. Express it as a named constant.
2. Lower `max_tokens` in `dialogue/llm_config.yaml` to match that ceiling with a modest safety margin.
   Base it on the measured decoded-token counts (DEC-273 recorded ~70 tokens for a typical turn), not on
   the current 512.
3. Confirm the truncation path is graceful: a reply hitting the cap must still be valid JSON that
   validates against the schema. If Ollama truncation can produce invalid JSON at the cap, the retry
   path must handle it — check `dialogue/llm_client.py` before lowering the number.
4. **Do not edit any prompt file in this fix.** The moment you do, `dialogue_prompt_hash` changes and
   this stops being free. Prompt-side length wording is Decide item D5.

## Verification

Write the failing test first:

`tests/unit/engines/test_dialogue_response_length_cap.py`
- `DialogueResponse` rejects an `npc_response` longer than the cap.
- A reply at exactly the cap validates.
- The configured `max_tokens` is consistent with the schema cap (guard against the two drifting apart —
  that consistency assertion is the part that would otherwise rot).

```
pytest tests/unit/engines/test_dialogue_response_length_cap.py -v
make check
```

**Prove the hash did not move** — this is the claim that makes the fix free:
```
# capture dialogue_prompt_hash before and after; it MUST be identical
```
If it changed, you edited a prompt file — revert that part.

Then measure live (rebuild first, the image is not bind-mounted): drive several dialogue turns and
compare `eval_duration_ms` and decoded token counts from the `llm_prompt_eval` records against the
pre-fix numbers. Expect decode time down roughly in proportion to tokens saved. Report the delta.

## Blast radius

Two files: one YAML value, one Pydantic field. The risk is setting the cap too tight and truncating
legitimate replies — mitigate by deriving the number from observed outputs (step 1) and by checking the
truncation path (step 3). Eval comparability is preserved as long as no prompt file is touched.

**Sequencing:** fully independent — parallelisable. Good first candidate: small, measurable, no hash cost.
