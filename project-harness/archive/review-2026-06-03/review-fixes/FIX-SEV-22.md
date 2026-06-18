# FIX-SEV-22 — Seed + log RNG on content-emitting gossip/quest paths

**Severity:** MEDIUM · **Effort:** S · **Category:** correctness / observability
**Absorbs:** ENG-07, ENG-12, GRAPH-08

## Problem
Several content-emitting paths use the unseeded module-global `random.*`, violating the
RNG-seed-logging rule and breaking `--cached`/eval reproducibility (the rest of the gossip
pipeline is deterministically hash-seeded).

## Current shape (verified — line numbers updated post SEV-04/23/36)
- `src/npc_engine/engines/gossip/gossip_handler.py:21` `import random`;
  `:338` `if random.random() < SECRET_BASE_PROBABILITY:` and
  `:341` `distorted = random.random() < SECRET_DISTORTION_CHANCE` (secret propagation,
  inside `_run_side_effects`, per (sharer, receiver) pair, `tick_id` in scope).
- `src/npc_engine/engines/quest_generation/quest_generation_engine.py:24` `import random`;
  `:122` `random.random() > world_state.quest_generation_rate` (gate);
  `:236` `random.choice(pool)` (template pick);
  `:394` `random.choice(pool)` (slot fill).
- **Pattern to mirror:** `engines/events/event_handler.py:72,104` already does
  `rng = self._rng or random.Random(tick_id)` and logs — copy this approach.

## Steps
1. **Gossip secret path:** derive a deterministic `rng = random.Random(seed)` where the
   seed is built from the pair + tick (e.g. hash of `f"{sharer_id}|{receiver_id}|{tick_id}|secret"`).
   Replace both `random.random()` calls with `rng.random()`. Log the seed once
   (`LOGGER.debug("gossip_secret_rng seed=%d sharer=%s receiver=%s tick=%d", ...)`).
2. **Quest generation:** derive `rng = random.Random(seed)` from a deterministic input
   available at that scope (e.g. world tick / candidate ids). Replace the three
   `random.*` calls with `rng.*`. Log the seed at the start of the generation pass.
3. Do **not** add new config keys (avoids touching `config.py`). Reuse existing constants;
   if a seed-namespace string is needed, define it as a module-level `UPPER_SNAKE` constant
   in the same file.
4. Keep functions ≤40 lines; extract a small `_seed_from(...)` helper if needed.

## Verification
- `tests/unit/test_sev22_rng_determinism.py`:
  - Two runs of the gossip secret decision with the same (ids, tick) yield identical
    outcomes; different tick → may differ. Seed is logged (assert via patched LOGGER).
  - Quest-generation gate/choice is reproducible for a fixed seed input; seed logged.
- Run: `<MAIN_VENV_PYTHON> -m pytest tests/unit/test_sev22_rng_determinism.py -q`

## Blast radius
Gossip secret propagation and quest-generation sampling become reproducible. Output
distribution unchanged in aggregate; specific picks become deterministic per seed.
