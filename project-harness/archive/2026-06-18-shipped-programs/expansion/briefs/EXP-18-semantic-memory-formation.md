# EXP-18 — Semantic Memory Formation Beyond Arousal

**Goal / business rationale**
Currently memories only form when NPC arousal > 70. Some game events are semantically
important regardless of arousal (betrayal, death, war, major world events). EXP-18 adds
a keyword-triggered pathway so NPCs always remember semantically significant moments.
BUSINESS_INTENT: richer long-term memory for demo storytelling.

---

## First slice

Add `create_from_semantic_triggers()` method to `MemoryEngine`. The method checks content
against a fixed `_SEMANTIC_KEYWORDS` tuple; if any keyword matches, it creates a memory
at a fixed `_SEMANTIC_VIVIDNESS` level (60). Reuses the existing `create_memory()` from
`memory_service.py` — no new Cypher needed.

---

## Current state

**`src/npc_engine/engines/memory/memory_engine.py`**

`MemoryEngine.create_from_arousal()` (line 36–70): sole formation pathway today.
Constants at lines 22–25:
```python
_HIGH_AROUSAL_THRESHOLD = 70
_HIGH_AROUSAL_VIVIDNESS = 80
_DECAY_BASE_RATE = 5
_DECAY_CHARGE_DIVISOR = 20
```

`create_memory()` is imported from `graph.memory_service` (line 16). It accepts
`character_id`, `content`, `vividness`, `emotional_charge`, `game_time` — all available
at formation time.

**`src/npc_engine/graph/memory_service.py:27`** — `create_memory()` signature confirmed above.

No schema change required (reuses `Memory` node as-is).

---

## Files

**Edit:**
- `src/npc_engine/engines/memory/memory_engine.py`
  - Add `_SEMANTIC_KEYWORDS: tuple[str, ...]` constant (death, betrayal, war, assassination,
    plague, execution, exile, coup).
  - Add `_SEMANTIC_VIVIDNESS: int = 60` constant.
  - Add `create_from_semantic_triggers()` async method that calls `create_memory()` when any
    keyword appears (case-insensitive substring match).
  - Keep all functions ≤ 40 lines; keep file ≤ 300 lines.

**Do NOT touch:** `memory_service.py`, `memory_queries.py`, or any coordination file.

---

## Graph / API surface

Engine-internal. No new routes, no graph schema change.

---

## Architecture fit

OCP seam: `MemoryEngine` gains a new method (not a new variant replacing an old one).
No existing method is modified. This is a pure addition — fully OCP-compliant.

Layer: `engines` (delegates to `graph.memory_service`, which is below it in the layer
hierarchy). No layer violation.

No schema change. No DECISIONS approval required.

---

## Test plan

**Failing test to write first** (`tests/unit/test_memory_engine.py`, new test):
```python
@pytest.mark.asyncio
async def test_create_from_semantic_triggers_fires_on_keyword(mock_session):
    engine = MemoryEngine()
    with patch("npc_engine.engines.memory.memory_engine.create_memory") as mock_cm:
        mock_cm.return_value = "mem-001"
        result = await engine.create_from_semantic_triggers(
            mock_session,
            character_id="npc_1",
            content="The king ordered an execution at dawn",
            emotional_charge=10,
            game_time=TimePoint(year=1, season="spring", day=1, time_of_day="morning"),
        )
    assert result == "mem-001"
    mock_cm.assert_called_once()

@pytest.mark.asyncio
async def test_create_from_semantic_triggers_skips_mundane(mock_session):
    engine = MemoryEngine()
    with patch("npc_engine.engines.memory.memory_engine.create_memory") as mock_cm:
        result = await engine.create_from_semantic_triggers(
            mock_session,
            character_id="npc_1",
            content="The merchant sold bread in the market",
            emotional_charge=5,
            game_time=TimePoint(year=1, season="spring", day=1, time_of_day="morning"),
        )
    assert result is None
    mock_cm.assert_not_called()
```

Unit test command: `pytest tests/unit/test_memory_engine.py -v`

---

## Done when

1. `MemoryEngine` has `create_from_semantic_triggers()` with full type annotations and docstring.
2. `_SEMANTIC_KEYWORDS` and `_SEMANTIC_VIVIDNESS` are module-level constants (no magic literals).
3. Tests above pass; existing arousal tests still pass.
4. File stays ≤ 300 lines.
