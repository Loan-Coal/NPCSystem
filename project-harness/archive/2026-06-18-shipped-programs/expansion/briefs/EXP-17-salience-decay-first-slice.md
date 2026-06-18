# EXP-17 (first slice) — Charge-Weighted Vividness Decay

**Phase:** 2 · **Effort:** M (first slice only) · **Deps:** EXP-30 (done)
**Touches:** `src/npc_engine/engines/memory/memory_engine.py`, `src/npc_engine/graph/memory_queries.py`, `src/npc_engine/graph/memory_service.py`
**Does NOT touch:** `demo_game/`, prompt YAML, `retrieval/context_builder.py`, schema YAML, `EXPANSION_INDEX.md`
**Scope constraint:** first slice = charge-weighted decay rate using EXISTING `emotional_charge` field ONLY. No new graph fields (`recall_count`, `never_forget`, `salience`). Those are the full-version schema gates — NOT in scope here.

---

## Purpose

`memory_engine.py:62` calls `decay_all_vividness(session)` which uses
`CYPHER_DECAY_VIVIDNESS` — a flat query that subtracts a fixed `decay` amount from ALL
Memory nodes equally (`memory_queries.py:44-50`). High-intensity traumatic memories
(high `emotional_charge`) should decay slower; trivial ones faster. This is the minimum
behavioral improvement that requires zero schema change.

---

## What already exists

- `memory_engine.py:18-19`: `_HIGH_AROUSAL_THRESHOLD = 70`, `_HIGH_AROUSAL_VIVIDNESS = 80`.
- `memory_engine.py:62-71`: `decay_vividness(session)` → calls `decay_all_vividness(session)`.
- `memory_service.py:92-109`: `decay_all_vividness(session, *, decay_per_day=5)` — uniform decay.
- `memory_queries.py:44-50`: `CYPHER_DECAY_VIVIDNESS` — `MATCH (m:Memory) WHERE m.vividness > 0 SET m.vividness = CASE WHEN m.vividness - $decay < 0 THEN 0 ELSE m.vividness - $decay END`.
- `create_memory` already writes `emotional_charge` to every Memory node (`memory_service.py:66`).

---

## Change plan

### 1. `memory_queries.py` — new Cypher constant

Add `CYPHER_DECAY_VIVIDNESS_WEIGHTED` that uses each memory's own `emotional_charge` to
compute a per-node decay rate:

```python
CYPHER_DECAY_VIVIDNESS_WEIGHTED = """
MATCH (m:Memory)
WHERE toInteger(m.vividness) > 0
WITH m,
     $base_decay - (toInteger(coalesce(m.emotional_charge, 0)) / $charge_divisor) AS node_decay
WITH m, CASE WHEN node_decay < 1 THEN 1 ELSE node_decay END AS clamped_decay
SET m.vividness = CASE
    WHEN toInteger(m.vividness) - clamped_decay < 0 THEN 0
    ELSE toInteger(m.vividness) - clamped_decay
END
RETURN count(m) AS affected
"""
```

Parameters: `$base_decay` (int, e.g. 5), `$charge_divisor` (int, e.g. 20).
Formula: `decay_rate = max(1, base_decay - floor(|emotional_charge| / charge_divisor))`.
At `charge=0` → rate=5; at `charge=80` → rate=1; at `charge=100` → rate=0 → clamped to 1.

Do NOT remove `CYPHER_DECAY_VIVIDNESS` — existing callers stay on the old flat query
until the engine switches over.

### 2. `memory_service.py` — new function

Add alongside `decay_all_vividness`:

```python
async def decay_all_vividness_weighted(
    session: AsyncSession,
    *,
    base_decay: int = 5,
    charge_divisor: int = 20,
) -> int:
    """Reduce vividness using a charge-weighted rate (high emotional_charge → slower decay).

    Args:
        session: Active Neo4j async session.
        base_decay: Maximum decay per day (low-charge memories).
        charge_divisor: Divisor applied to emotional_charge to compute rate reduction.

    Returns:
        Number of Memory nodes whose vividness was reduced.
    """
```

### 3. `memory_engine.py` — new method + constants

Add two new module-level constants:
```python
_DECAY_BASE_RATE = 5
_DECAY_CHARGE_DIVISOR = 20
```

Add a new method `decay_vividness_weighted` that calls
`decay_all_vividness_weighted(session, base_decay=_DECAY_BASE_RATE, charge_divisor=_DECAY_CHARGE_DIVISOR)`.

Keep the existing `decay_vividness` method unchanged (callers of the old path — e.g. clock
route — can be migrated in a later slice once weighted decay is validated).

---

## TDD

Write `tests/unit/test_memory_engine_weighted_decay.py` FIRST.

No I/O, no DB — mock `decay_all_vividness_weighted` from `npc_engine.graph.memory_service`.

| Test | What it asserts |
|------|-----------------|
| `test_weighted_decay_calls_weighted_service` | `decay_vividness_weighted(session)` calls `decay_all_vividness_weighted` (not `decay_all_vividness`) |
| `test_weighted_decay_uses_correct_defaults` | called with `base_decay=5, charge_divisor=20` |
| `test_weighted_decay_returns_count` | returns the int returned by the mock |
| `test_flat_decay_unchanged` | `decay_vividness(session)` still calls `decay_all_vividness` — old path not broken |

Additionally write `tests/unit/test_memory_queries_weighted.py` (pure Python, no DB):

| Test | What it asserts |
|------|-----------------|
| `test_charge_divisor_formula_high_charge` | `max(1, 5 - 80//20) == 1` |
| `test_charge_divisor_formula_zero_charge` | `max(1, 5 - 0//20) == 5` |
| `test_charge_divisor_formula_mid_charge` | `max(1, 5 - 40//20) == 3` |
| `test_cypher_constant_exists` | `CYPHER_DECAY_VIVIDNESS_WEIGHTED` is a non-empty string |

Run only: `pytest tests/unit/test_memory_engine_weighted_decay.py tests/unit/test_memory_queries_weighted.py -v`

---

## Done when

- Both new test files are green.
- Existing `pytest tests/unit/test_memory_engine.py` (if present) still green.
- `memory_engine.py` has `decay_vividness_weighted` + the two new constants.
- `memory_service.py` has `decay_all_vividness_weighted` (does not remove old function).
- `memory_queries.py` has `CYPHER_DECAY_VIVIDNESS_WEIGHTED` (does not remove old constant).
- No file exceeds 300 lines of non-test code.
- No schema YAML touched.
- No layer violations.
