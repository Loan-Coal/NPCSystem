# EXP-20 — Quest Status as Enum + Fail/Expire States

**Goal / business rationale**
`QuestStateRecord.status` is currently a raw `str` field and `quest_lifecycle_engine.py`
defines five raw-string constants (`STATUS_DRAFT`, `STATUS_OFFERED`, …). A typed enum
closes the open set, makes invalid transitions impossible at the type level, and adds
`failed`/`expired` states needed for richer quest storytelling.
BUSINESS_INTENT: correctness; enables `/v1/quests` to expose typed status values.

---

## First slice

1. Add `QuestStatus(str, enum.Enum)` to `models.py` with all valid states including
   `failed` and `expired`.
2. Change `QuestStateRecord.status` from `str` to `QuestStatus`.
3. Replace the five raw `STATUS_*` string constants in `quest_lifecycle_engine.py` with
   `QuestStatus` enum member references.
4. Do NOT add any transition logic for `failed`/`expired` yet — only the type exists
   in this slice. Transition logic is a follow-up (EXP-20 slice-2).

---

## Current state

**`src/npc_engine/engines/quest/models.py:67–79`**
```python
class QuestStateRecord(BaseModel):
    ...
    status: str   # ← raw string; target of this change
```

**`src/npc_engine/engines/quest/quest_lifecycle_engine.py:42–48`**
```python
STATUS_DRAFT = "draft"
STATUS_OFFERED = "offered"
STATUS_ACCEPTED = "accepted"
STATUS_IN_PROGRESS = "in_progress"
STATUS_COMPLETED = "completed"
```
These are used throughout `quest_lifecycle_engine.py` in comparisons and writes.
Callers of `QuestStateRecord` outside this module: check `api/` routes and other quest
helpers for raw-string references — they must be updated too if they instantiate the
model with a hardcoded string.

---

## Files

**Edit:**
- `src/npc_engine/engines/quest/models.py`
  - Add `import enum` (stdlib).
  - Add `class QuestStatus(str, enum.Enum)` with members:
    `DRAFT="draft"`, `OFFERED="offered"`, `ACCEPTED="accepted"`,
    `IN_PROGRESS="in_progress"`, `COMPLETED="completed"`,
    `FAILED="failed"`, `EXPIRED="expired"`.
  - Change `QuestStateRecord.status: str` → `QuestStateRecord.status: QuestStatus`.

- `src/npc_engine/engines/quest/quest_lifecycle_engine.py`
  - Replace raw `STATUS_*` constants with `QuestStatus` imports.
  - All comparisons and writes use `QuestStatus.DRAFT`, etc.
  - Remove the five `STATUS_*` module-level string constants.

**Do NOT touch:** `quest_engine_helpers.py`, graph writer/reader files, any API route
file, or any coordination file. If a route file references raw strings for status, log
it as an adjacent issue (do not fix it).

---

## Graph / API surface

No graph schema change (`status` is stored as a string in Neo4j — `QuestStatus` is
`str`-based so `.value` round-trips cleanly). No new route.

---

## Architecture fit

OCP seam: new `QuestStatus` enum added to `models.py`; existing engine file is edited
to use it. This is type-narrowing, not a new variant. Fully OCP-compatible.

Layer: `models.py` is in `engines` layer; `QuestStatus` has zero external dependencies.
No layer violation.

No schema change. No DECISIONS approval required.

---

## Test plan

**Failing test to write first** (`tests/unit/test_quest_models.py`):
```python
def test_quest_status_enum_members():
    assert QuestStatus.DRAFT.value == "draft"
    assert QuestStatus.FAILED.value == "failed"
    assert QuestStatus.EXPIRED.value == "expired"

def test_quest_state_record_rejects_invalid_status():
    with pytest.raises(Exception):  # ValidationError
        QuestStateRecord(
            quest_id="q1", player_id="p1", title="t", status="invalid",
            objectives=[], objective_progress={}, item_rewards=[],
        )

def test_quest_state_record_accepts_valid_status():
    rec = QuestStateRecord(
        quest_id="q1", player_id="p1", title="t", status=QuestStatus.OFFERED,
        objectives=[], objective_progress={}, item_rewards=[],
    )
    assert rec.status == QuestStatus.OFFERED
```

Unit test command: `pytest tests/unit/test_quest_models.py -v`

---

## Done when

1. `QuestStatus` enum exists in `models.py` with all 7 members.
2. `QuestStateRecord.status` is typed `QuestStatus`.
3. `quest_lifecycle_engine.py` uses `QuestStatus.*` everywhere; no raw `STATUS_*` constants remain.
4. Tests above pass; existing quest tests still pass.
5. Both files ≤ 300 lines.
