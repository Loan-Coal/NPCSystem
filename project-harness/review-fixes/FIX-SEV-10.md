# SEV-10 — Per-engine declared timeouts are dead configuration for 4 of 5 engines

**HIGH** · Finding **L11-02** (llm) · Confidence: Confirmed · Evidence: `evidence/L11.md`
**Related:** ISSUE-298 is the *temperature* version of this same defect; this finding generalises it to
`timeouts_ms`, which ISSUE-298 does not mention.

## Problem

Four engines declare `timeouts_ms` in their `llm_config.yaml` that **no code path reads**. An engineer
setting `timeouts_ms.full: 30000` to give quest generation more headroom changes nothing — the call
still dies at the process-wide 10s.

Worse, the one engine that *does* read it is also defeated: dialogue's declared 200,000 ms tier timeout
(`degradation.py:124`, genuinely enforced via `asyncio.wait_for`) sits **behind** the same 10s HTTP
timeout one layer down. The HTTP layer raises `LLMTimeoutError` at 10s, long before `wait_for` would fire
at 200s. The 200s figure is asserted, not reachable.

This is systemic pattern §3.4 — asserted-not-measured — recurring for timeouts specifically.

## Current shape

`grep -rn "timeouts_ms" src/npc_engine --include="*.py"` returns exactly **two** non-model rows:
- `engines/llm_config_models.py:96` — the Pydantic field
- `engines/dialogue/dialogue_handler.py:248-249` — its only reader

Declared but unread:
- `engines/chapter/llm_config.yaml:16` — 30,000 ms
- `engines/memory_consolidation/llm_config.yaml:16` — 30,000 ms
- `engines/proactive_dialogue/llm_config.yaml:16-17` — 20,000 ms
- `engines/quest_generation/llm_config.yaml:16-17` — 30,000 ms

The actually-enforced ceiling for all five engines is one process-wide value:
`settings.LLM_TIMEOUT_SECONDS` (default **10.0**, `config.py:111`), passed to every `OllamaAdapter`
constructor uniformly at `engines/llm/factory.py:88,103`, regardless of which engine it serves.

## Steps

Pick **one** of these two and record the choice in `DECISIONS.md` — they are genuinely different products.

**(a) Make the YAML true.** Thread `EngineModelConfig.timeouts_ms.full` into
`create_llm_client_for_engine` as the per-adapter `timeout_seconds`, and drop
`settings.LLM_TIMEOUT_SECONDS` as a cross-engine default (or demote it to a fallback for engines that
declare nothing). More honest to the YAML's apparent intent; lets background engines have longer
ceilings than the interactive path, which is what you want alongside SEV-04.

**(b) Make the code true.** Delete `timeouts_ms` from the four engines that do not use it and document
that only dialogue has tiered timeouts. Smaller, and matches what ships today.

**Recommendation: (a)**, because SEV-04's admission control wants per-class ceilings anyway — a
background engine that may wait 30s and an interactive turn that must not are exactly the distinction
this field was reaching for.

Either way: reconcile dialogue's 200,000 ms tier with the underlying HTTP ceiling, so the tiered
degradation path can actually be reached rather than being pre-empted at 10s.

## Verification

Write the failing test first:

`tests/unit/llm/test_per_engine_timeout_wiring.py`
- For (a): an engine declaring `timeouts_ms.full: 30000` produces an adapter whose effective timeout is
  30s, not 10s. Fails today.
- For (b): assert no `llm_config.yaml` declares a field no code reads — a config/reader consistency
  check, which also prevents the defect recurring.
- Either way: assert dialogue's tiered timeout is reachable, i.e. the tier ceiling is **not** greater
  than the transport ceiling.

```
pytest tests/unit/llm/ tests/unit/engines/ -v
make check
```

Live: force a slow generation and confirm the failure surfaces at the *declared* ceiling for that engine,
by reading `duration_ms` on the `llm_prompt_eval` record.

## Blast radius

`engines/llm/factory.py` (every adapter is constructed there), `llm_config_models.py`, four YAML files,
and `dialogue_handler.py`. Under (a), engines currently dying at 10s will run longer — that interacts
directly with SEV-04's contention budget, so land SEV-04 first or size the new ceilings conservatively.

There is also a positive interaction with SEV-02: longer background timeouts are only safe once
background work can be shed.

**Sequencing:** independent of the other Block E items; **prefer after SEV-04** if taking option (a).
