# EXP-12 — Relation-Delta Provenance & Audit Trail

**Goal / business rationale**
Every relation mutation (trust±, affinity±) should emit a structured log record so game
designers can trace why NPC relationships shifted. Currently `apply_dialogue_relation_deltas`
silently swallows `RelationEdgeNotFoundError` with no trace. Adds observability without
changing the graph schema.
BUSINESS_INTENT: debuggability for the Munich demo; studio licensing requires audit trail.

---

## First slice

Add structured `logger.info()` / `logger.warning()` calls to `relation_mutator.py`:
- **Before** the graph write: `logger.info("relation_delta_attempt", ...)` with all keys.
- **After** a successful write: `logger.info("relation_delta_applied", ...)`.
- **On `RelationEdgeNotFoundError`**: replace silent `return` with `logger.warning("relation_edge_missing", ...)`.

All entries must include: `npc_id`, `player_id`, `tick_id`, `cause_id`, `deltas` (field→value).

---

## Current state

**`src/npc_engine/engines/dialogue/relation_mutator.py`** (55 lines total)

```python
async def apply_dialogue_relation_deltas(
    session, settings, npc_id, player_id, relation_deltas, cause_id, tick_id,
) -> None:
    try:
        await apply_relation_delta(...)
    except RelationEdgeNotFoundError:
        return        # ← silent swallow — the target of this EXP
```

No import for `utils.logging` or `structlog` today. The project uses
`utils/logging.py` for structured logging (confirmed by CLAUDE.md pattern).

---

## Files

**Edit:**
- `src/npc_engine/engines/dialogue/relation_mutator.py`
  - Add `from npc_engine.utils import get_logger` (or project's equivalent import).
  - Add `_logger = get_logger(__name__)` module-level.
  - Emit `_logger.info(...)` before the write and after success.
  - Replace silent `except RelationEdgeNotFoundError: return` with a `_logger.warning(...)` then `return`.
  - Function must remain ≤ 40 lines; file must remain ≤ 300 lines.

**Do NOT touch:** `delta_log_manager.py`, `graph_writer.py`, `dialogue_handler.py`, or any
coordination file.

---

## Graph / API surface

Engine-internal. No routes, no schema change.

---

## Architecture fit

Pure observability addition inside one module. No new files, no layer change, no new
dependency beyond the existing `utils/logging.py` import pattern.

No schema change. No DECISIONS approval required.

---

## Structured log schema

Before write:
```
logger.info("relation_delta_attempt", npc_id=npc_id, player_id=player_id,
            tick_id=tick_id, cause_id=cause_id, deltas=relation_deltas.model_dump())
```
After success:
```
logger.info("relation_delta_applied", npc_id=npc_id, player_id=player_id,
            tick_id=tick_id, cause_id=cause_id)
```
On missing edge:
```
logger.warning("relation_edge_missing", npc_id=npc_id, player_id=player_id,
               tick_id=tick_id, cause_id=cause_id)
```

---

## Test plan

**Failing test to write first** (`tests/unit/test_relation_mutator.py`):
```python
@pytest.mark.asyncio
async def test_apply_delta_logs_attempt_and_success(mock_session, mock_settings, caplog):
    deltas = RelationDeltas(trust=5, affinity=3)
    with patch("npc_engine.engines.dialogue.relation_mutator.apply_relation_delta") as mock_ard:
        mock_ard.return_value = None
        await apply_dialogue_relation_deltas(
            mock_session, mock_settings, "npc_1", "player_1", deltas, "cause_A", 42
        )
    assert "relation_delta_attempt" in caplog.text
    assert "relation_delta_applied" in caplog.text

@pytest.mark.asyncio
async def test_apply_delta_logs_warning_on_missing_edge(mock_session, mock_settings, caplog):
    deltas = RelationDeltas(trust=5, affinity=3)
    with patch("npc_engine.engines.dialogue.relation_mutator.apply_relation_delta") as mock_ard:
        mock_ard.side_effect = RelationEdgeNotFoundError(src_id="npc_1", dst_id="player_1")
        await apply_dialogue_relation_deltas(
            mock_session, mock_settings, "npc_1", "player_1", deltas, "cause_A", 42
        )
    assert "relation_edge_missing" in caplog.text
```

Unit test command: `pytest tests/unit/test_relation_mutator.py -v`

---

## Done when

1. All three log events (`attempt`, `applied`, `edge_missing`) are emitted with correct keys.
2. Tests above pass; no existing tests regress.
3. File ≤ 300 lines, function ≤ 40 lines.
4. No `except: pass` or silent swallow remains.

**Note:** First check how the project logger is imported — look at another engines/ file
that already uses structured logging (e.g. `engines/gossip/gossip_handler.py`) and follow
the exact same import pattern.
