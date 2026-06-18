# EXP-92: Determinism / Replay Proof Toggle

**Goal / business rationale**
Surface the gossip tick's deterministic RNG seed in the API response so the demo can prove —
concretely — that the same `tick_override` always produces the same distortion outcome.
Traces to BUSINESS_INTENT §2 "deterministic, replayable gossip distortion (seeded RNG logged)"
and §4 criterion 7 (QA/studio reliability sell: "same seed → same gossip").

**First slice**
Add `seeds_used: dict[str, int]` (pair-key → seed) to the gossip tick response; build a
`DeterminismBeat` that calls `POST /v1/batch/gossip_tick` twice with the same `tick_override`
and displays matching seed + distortion results side-by-side in the demo terminal.

---

## Current state (verified against codebase)

| Location | What's there |
|---|---|
| `src/npc_engine/engines/gossip/gossip_distort.py:74` | `compute_seed_value(summary, honesty, trust, tick_id) -> int` — deterministic SHA-256 seed; public |
| `src/npc_engine/engines/gossip/gossip_handler.py:188` | `run_tick()` returns `{"tick_id": N, "pairs": N, "propagated": N}` — seed **not exposed** |
| `src/npc_engine/engines/gossip/gossip_handler.py:225–238` | Seed computed and logged per pair (`logger.debug("distortion_probability=%.3f seed=%d", ...)`) but discarded from return |
| `src/npc_engine/api/routes/batch.py:23–28` | `GossipTickRequest.tick_override: int ge=0` accepted; passed straight to `run_tick(session, tick_id=tick_override, ...)` — **replay already works at the engine layer** |
| `demo_game/run.py:496` | `main()` entry; scenes imported from `demo_game.run_scenes` |

---

## Files

**Edit (existing):**
- `src/npc_engine/engines/gossip/gossip_handler.py` — in `_build_write_params`, collect
  `seeds_used: dict[str, int]` keyed by `f"{sharer_id}→{receiver_id}"`; return it from
  `run_tick()` as `"seeds_used": seeds_used`. This is additive — existing callers ignore the
  new key.

**New (demo-only, no `src/` imports):**
- `demo_game/determinism_beat.py` — `DeterminismBeat` dataclass / scene; calls
  `POST /v1/batch/gossip_tick` twice with `tick_override=42` and fixed NPC pair
  `["captain_sorn", "mira_innkeeper"]`; asserts `seeds_used` are equal across both calls;
  prints a two-column table (`run 1 seed | run 2 seed | match?`).

**Edit (demo wiring):**
- `demo_game/run.py` — import `DeterminismBeat`; insert it as an optional scene near the
  gossip-telephone block (after `SpreadRumorScene`).

---

## Graph / API surface

No schema change. Gossip tick response extended — additive only:

```json
{
  "tick_id": 42,
  "pairs": 1,
  "propagated": 1,
  "seeds_used": {
    "captain_sorn→mira_innkeeper": 982341209
  }
}
```

No new type_registry YAML. No new route. No base node/edge.

---

## Architecture fit

OCP add-by-new-file for the demo beat. `gossip_handler.py` edit is purely additive
(new dict key in return value) — closed to behavior change, open to surface extension.
`gossip_handler.py` stays in `engines/` layer; no Cypher outside `graph/`, no LLM outside
`engines/`. No DECISIONS entry needed (additive API extension; no schema; no layer change).

---

## Test plan

Write `tests/unit/test_gossip_determinism.py` **first** (failing):

```python
# test 1 — new key present
async def test_seeds_used_key_in_run_tick_result():
    # mock session + pair reader → assert "seeds_used" in result

# test 2 — same tick_id → same seeds
async def test_same_tick_override_produces_same_seeds():
    # call handler twice with tick_id=42, same pair data → assert seeds_used equal

# test 3 — different tick_id → different seeds
async def test_different_tick_id_produces_different_seeds():
    # tick_id=42 vs tick_id=43 → assert seeds differ
```

Run: `pytest tests/unit/test_gossip_determinism.py -v`

Then implement the minimal handler change. Green. Then add `DeterminismBeat` with its own
tests in `demo_game/tests/test_determinism_beat.py` (mock httpx, no live engine).

---

## Done when

- `pytest tests/unit/test_gossip_determinism.py` passes (3 tests)
- `pytest demo_game/tests/test_determinism_beat.py` passes
- `make demo-run` (or `--dry-run`) shows a "determinism check" scene with two side-by-side
  gossip tick results and a visible `seeds_match=True` line
- `make check` and `make test-demo` both green
