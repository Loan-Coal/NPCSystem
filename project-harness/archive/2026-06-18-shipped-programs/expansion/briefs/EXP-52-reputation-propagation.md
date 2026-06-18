# EXP-52 — Personal Reputation Propagation Engine (first slice: 1-hop)

**Phase:** 3 · **Effort:** M · **Deps:** EXP-50 (done — `Standing` enum + `RelationReader` available)
**Touches:** new `src/npc_engine/engines/reputation/` package, `src/npc_engine/engines/reputation/reputation_rules.yaml`
**Does NOT touch:** `demo_game/`, any existing engine, any schema YAML (`relates_to` schema unchanged), `EXPANSION_INDEX.md`
**Scope constraint:** 1-hop propagation ONLY. No `player_reputation_baseline` cached field (that is the schema-gated part — STOP if you think you need it). Write nudges to existing `relates_to` edges only; if no edge exists between B and player, skip B silently in this slice.

---

## Purpose

Gossip spreads facts; faction_politics drifts faction standing; but a player's **personal**
reputation never propagates through the social graph. If NPC-A trusts the player and
NPC-A trusts NPC-B, NPC-B should develop a small baseline disposition toward the player
*before* they ever meet. This per-tick engine implements that 1-hop diffusion.

---

## What already exists (build on these)

- `engines/relationship/standing.py`: `Standing` enum + `derive_standing(trust, fear, affection)`.
  Use `derive_standing` to determine the source NPC's standing toward the player before
  propagating; only propagate if standing ≥ FRIENDLY.
- `graph/relation_reader.py:RelationReader.get_relation_scalars(src_id, dst_id)` — reads
  `trust, fear, affection` for a directed `RELATES_TO` edge. Use this to read:
  (a) source NPC's standing toward player, (b) source NPC's standing toward target NPC,
  (c) target NPC's existing edge toward player (if any).
- `graph/relation_writer.py:set_relation_values(tx, src_id, dst_id, trust, fear, affection)`
  — writes updated scalars. Use this as the write path for the nudge.
- `graph/graph_writer.py` — opens and commits transactions; the reputation engine should
  NOT open its own transactions; it must receive an `AsyncSession` and call
  `graph_writer.apply_relation_nudge(session, ...)` OR open a single transaction per
  propagation step (see mutation discipline below).

---

## Mutation discipline (CRITICAL)

CLAUDE.md §Session ownership: `graph_writer.py` is the only file that opens and commits
transactions. The engine must either:
1. Inject an `AsyncSession` and call a new thin helper in `graph/reputation_nudge.py`
   (the correct path — graph-layer write stays in `graph/`), OR
2. Accept a factory callable that yields a transaction (acceptable if already established
   by a graph_writer helper).

Write a new `graph/reputation_nudge.py` with:
```python
async def apply_trust_nudge(session, *, src_id, dst_id, delta_trust, delta_affection): ...
```
that opens a single transaction, reads existing `RELATES_TO` edge scalars (if it exists),
applies the delta (clamped ±100), and writes back. If no edge exists between `src_id` and
`dst_id`, return without creating one (first-slice constraint).

Nudge deltas must be small and bounded: `|delta_trust| ≤ MAX_NUDGE_PER_TICK`,
`|delta_affection| ≤ MAX_NUDGE_PER_TICK` — make these config constants, loaded from
`reputation_rules.yaml`.

---

## Files

**New:**
- `src/npc_engine/engines/reputation/__init__.py` — package docstring.
- `src/npc_engine/engines/reputation/reputation_engine.py` — `ReputationEngine` class;
  `run_tick(session, player_id, npc_ids)` async method.
- `src/npc_engine/engines/reputation/propagation_config.py` — `PropagationConfig`
  Pydantic model + `load_propagation_config()` loader from `reputation_rules.yaml`.
- `src/npc_engine/engines/reputation/reputation_rules.yaml` — tunable constants:
  ```yaml
  max_nudge_per_tick: 2
  min_source_standing: "FRIENDLY"   # propagate only if source→player standing >= this
  min_bridge_standing: "NEUTRAL"    # propagate via intermediary only if their mutual standing >= this
  enabled: false                    # off by default (flag)
  ```
- `src/npc_engine/graph/reputation_nudge.py` — `apply_trust_nudge` thin writer (graph layer).
- `tests/unit/test_reputation_engine.py` — unit tests (all mocked, no DB).

---

## Algorithm (first slice — 1-hop)

```
for each candidate source NPC S in npc_ids:
    scalars_S_player = get_relation_scalars(S, player_id)  # S→player edge
    if not exists or derive_standing(**scalars_S_player) < min_source_standing: skip
    
    for each NPC B in npc_ids where B != S and B != player:
        scalars_S_B = get_relation_scalars(S, B)  # S→B edge
        if not exists or derive_standing(**scalars_S_B) < min_bridge_standing: skip
        
        # B has no direct meeting with player yet (or has one — apply nudge either way)
        scalars_B_player = get_relation_scalars(B, player_id)
        if not exists: skip (first-slice constraint — do not create new edges)
        
        nudge = min(max_nudge_per_tick, scalars_S_player.trust // 10)
        await apply_trust_nudge(session, src_id=B, dst_id=player_id,
                                 delta_trust=nudge, delta_affection=0)
```

Log: `logger.info("reputation_nudge", src_npc=S, bridge=B, player=player_id, delta_trust=nudge)`
RNG seed logging: this algorithm is deterministic (no randomness in first slice) — no
seed logging required.

---

## TDD

Write `tests/unit/test_reputation_engine.py` FIRST. All mocked — no DB, no graph.

| Test | What it asserts |
|------|-----------------|
| `test_nudge_applied_when_source_friendly` | source→player FRIENDLY, source→B NEUTRAL, B→player edge exists → `apply_trust_nudge` called |
| `test_nudge_not_applied_when_source_wary` | source→player WARY → `apply_trust_nudge` NOT called |
| `test_nudge_not_applied_when_no_B_player_edge` | B→player edge missing → skipped silently |
| `test_nudge_not_applied_when_disabled` | `enabled=false` in config → no nudges |
| `test_nudge_bounded_by_max` | nudge never exceeds `max_nudge_per_tick` |
| `test_nudge_scales_with_trust` | higher source trust → larger nudge (up to cap) |
| `test_propagation_config_loads` | `load_propagation_config()` with test YAML parses correctly |

Run only: `pytest tests/unit/test_reputation_engine.py -v`

---

## Done when

- `pytest tests/unit/test_reputation_engine.py` green.
- `ReputationEngine.run_tick(session, player_id, npc_ids)` exists and is async.
- `reputation_rules.yaml` has `enabled: false` (off by default — no tick scheduler wire in
  this slice; that is a follow-up).
- `graph/reputation_nudge.py` has `apply_trust_nudge` with module docstring.
- No existing schema YAML touched; no `player_reputation_baseline` field.
- No file exceeds 300 lines.
- Layer rules respected: engine → graph (via new graph helper); no Cypher in `engines/`.
- Any adjacent issues spotted (do not fix) reported back.
