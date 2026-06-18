# EXP-11 — Player-Scoped Long-Term Memory Recall in Dialogue

**Phase:** 2 · **Effort:** M · **Deps:** EXP-30 (done)
**Touches:** `src/npc_engine/retrieval/context_builder.py`, new `tests/unit/test_player_relation_context.py`
**Does NOT touch:** `demo_game/`, any graph writer, any prompt YAML

---

## Purpose

When `player_id` is passed to `build_serialized_context`, the NPC should be aware of
its prior relationship with that specific player — trust, fear, affection,
interaction_count. This data is already stored in the `RELATES_TO` edge
(`npc_id → player_id`) by the dialogue engine after each turn. With EXP-30 landed,
Tier-A can accommodate the extra item. Without this, the LLM sees no history of the
player even after 20 prior conversations.

---

## What already exists

`graph_reader.py` already has:
- `CYPHER_GET_NPC_PLAYER_EDGE` Cypher constant (line 50-54): queries `RELATES_TO` from
  npc to player, returns edge properties.
- `get_npc_player_edge(session, npc_id, player_id) -> dict | None` (line 178-195): async
  function, returns properties dict or None.

`context_builder.py` already receives `player_id: str | None = None` and uses it for
`get_reputation_context_for_npc` and `get_active_quest_for_player`. This change adds one
more use.

---

## Change: `src/npc_engine/retrieval/context_builder.py`

### 1. Import

Add `get_npc_player_edge` to the existing import from `npc_engine.graph.graph_reader`:

```python
from npc_engine.graph.graph_reader import (
    get_character_with_relations,
    get_events_for_npc,
    get_known_event_ids_for_npc,
    get_location_context,
    get_npc_location_id,
    get_npc_player_edge,          # ADD
)
```

### 2. Stage 1 — sequential queries

In the block that runs sequential queries (after `get_active_quest_for_player`), add:

```python
player_relation_edge: dict | None = None
if player_id:
    player_relation_edge = await get_npc_player_edge(
        session, npc_id=npc_id, player_id=player_id
    )
```

### 3. Tier-A assembly

After the `if active_quest:` block (currently line ~308-309), add:

```python
if player_relation_edge is not None:
    tier_a_raw.append(
        ContextItem(
            key="player_relation",
            text=serialize_json(player_relation_edge),
            tier="tierA",
            priority=88,
        )
    )
```

Priority 88 — same as `beliefs`, intentionally NOT pinned (EXP-30 ranked pool will drop
it if budget is tight; the LLM can still work without it). The item is not pinned because
in a budget crunch, the persona + world + emotion + session must survive; the
relationship refinement is a bonus.

No other files need changing. The graph already writes the RELATES_TO edge; the LLM
prompt already expects relationship context (the `relations` array in the character
bundle). This adds the DIRECT player edge as a named, top-level context key so the LLM
can reference it without digging through the relations array.

---

## TDD

Write tests in `tests/unit/test_player_relation_context.py` FIRST.

Use the same monkeypatching pattern as `test_context_builder.py`. Add
`fake_npc_player_edge` that returns a test dict and patch
`npc_engine.retrieval.context_builder.get_npc_player_edge`.

### Tests to write

| Test | What it asserts |
|------|----------------|
| `test_player_relation_included_when_player_id_provided` | `player_id="player_demo"` + mock returns edge → serialized JSON contains `"player_relation"` key |
| `test_player_relation_excluded_when_no_player_id` | `player_id=None` → JSON does NOT contain `"player_relation"` key |
| `test_player_relation_excluded_when_edge_missing` | `player_id` set but `get_npc_player_edge` returns None → key absent |
| `test_player_relation_not_pinned_in_tier_a` | Verify the ContextItem `pinned=False` by inspecting tier_a_raw (monkeypatch assemble to capture items) |

For `test_player_relation_included_when_player_id_provided`:
- Use `_patch_graph_calls(monkeypatch)` helper from the existing test file (import or copy)
- Additionally patch `npc_engine.retrieval.context_builder.get_npc_player_edge` with an
  async function returning `{"trust": 60, "fear": 5, "affection": 40, "interaction_count": 3}`
- Call `build_serialized_context(..., player_id="player_demo", ...)`
- Parse result JSON, assert `"player_relation"` in payload

---

## Does NOT change

- `graph_reader.py` — already has the function
- Any prompt YAML — the LLM already handles arbitrary context keys
- Any schema / edge type — RELATES_TO already exists
- `context_budget_enforcer.py` — item is non-pinned, drops cleanly under EXP-30 policy

---

## Pre-merge checklist

- [ ] All new tests pass
- [ ] All existing `make check` tests still pass
- [ ] `context_builder.py` line count checked (already has waiver; note if further increased)
- [ ] Every new function has docstring
- [ ] No magic numbers (priority=88 follows the existing priority table in context_builder)
- [ ] No layer violations (retrieval → graph is allowed)
