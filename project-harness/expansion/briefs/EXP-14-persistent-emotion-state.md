# EXP-14: Persistent Emotion State — Neo4j write-through + label inertia

**Goal / business rationale**
The business thesis claims "persistent … emotional state per NPC." Today `EmotionStore`
is pure in-memory: a process restart resets every NPC to neutral VAD and an empty mood
label. This brief adds (1) write-through persistence to the Neo4j `character` node so
state survives restarts, and (2) label inertia so moods don't flip every dialogue turn.
DEC-084 approved: 4 optional fields added to `character.yaml`; Redis deferred.

**First slice**
1. Add 4 optional emotion fields to `base_nodes/character.yaml`.
2. New `graph/emotion_writer.py` — writes emotion scalars to the character node.
3. Extend `EmotionUpdater` with optional `EmotionGraphWriter` DI; write through on every update.
4. New `engines/emotion/emotion_bootstrap.py` — reads emotion fields from graph at boot, seeds the store.
5. Add `_MIN_AROUSAL_TO_SHIFT_LABEL` constant to `VadEmotionModel` — label only changes when arousal ≥ threshold.

---

## Current state (verified against codebase)

| Location | What's there |
|---|---|
| `src/npc_engine/engines/emotion/emotion_store.py:18` | `EmotionStore` — `_states: dict[str, EmotionState]`, pure in-memory, `asyncio.Lock` protected. Docstring explicitly says "Does NOT: synchronize state to external systems." |
| `src/npc_engine/engines/emotion/emotion_updater.py:26` | `EmotionUpdater.__init__(emotion_store, decay_rate, model)` — three injected deps. `apply_dialogue_mood` + `apply_event_shock` are the two write paths. |
| `src/npc_engine/engines/emotion/vad_emotion_model.py` | `VadEmotionModel` — implements `EmotionModelProtocol`; `compute_new_state` returns `EmotionState`. Label derived from valence/arousal bands. |
| `src/npc_engine/engines/emotion/emotion_state.py` | `EmotionState(valence: int, arousal: int, mood_label: str)` — immutable Pydantic model. |
| `src/npc_engine/type_registry/base_nodes/character.yaml` | Character node — no emotion fields today. |
| `src/npc_engine/graph/character_writer.py` | Existing character write operations — reference for Cypher MERGE pattern. |
| `src/npc_engine/graph/character_reader.py` | Existing character reads — reference for how optional fields are handled. |
| `src/npc_engine/main.py` lifespan | Startup sequence — seam for `emotion_bootstrap`. |

---

## Files

**Edit (schema — one field addition per row):**
- `src/npc_engine/type_registry/base_nodes/character.yaml` — append 4 optional fields:

```yaml
  emotion_valence: { type: int, required: false, range: [-100, 100] }
  emotion_arousal: { type: int, required: false, range: [0, 100] }
  emotion_mood_label: { type: str, required: false }
  emotion_updated_at_tick: { type: int, required: false }
```

**New (graph layer):**
- `src/npc_engine/graph/emotion_writer.py` — `EmotionGraphWriter` class:
  one public method `async def write_emotion(session, npc_id, state, tick)`.
  Uses `MERGE (c:character {id: $npc_id}) SET c.emotion_valence = $v, ...`.
  Layer: `graph/`. No LLM calls, no engine logic.

**New (engine bootstrap):**
- `src/npc_engine/engines/emotion/emotion_bootstrap.py` — `EmotionBootstrapper` class:
  `async def load_from_graph(session, store, npc_ids)` — reads emotion fields from
  character nodes, calls `store.set(npc_id, EmotionState(...))` for each.
  Called once in the lifespan startup after graph connection established.

**Edit (engine layer — DI addition only):**
- `src/npc_engine/engines/emotion/emotion_updater.py` — add optional fourth init param:
  `writer: EmotionGraphWriter | None = None`. After every `store.set()` call, if writer
  is not None, call `await self._writer.write_emotion(session, npc_id, new_state, tick)`.
  Two methods affected: `apply_dialogue_mood` and `apply_event_shock`.
  Both must accept an optional `session: AsyncSession | None = None` and `tick: int = 0`
  argument passed through to the writer. Existing callers that pass neither continue to work.

**Edit (emotion model — label inertia):**
- `src/npc_engine/engines/emotion/vad_emotion_model.py` — add:
  `_MIN_AROUSAL_TO_SHIFT_LABEL: int = 20` (module-level named constant).
  In `compute_new_state`: if `new_state.arousal < _MIN_AROUSAL_TO_SHIFT_LABEL`, keep
  `previous.mood_label` instead of replacing it. Prevents label flip on low-intensity events.

**New tests (two files):**
- `tests/unit/test_emotion_writer.py` — mock session; assert correct Cypher params; assert call made.
- `tests/unit/test_emotion_persistence.py` — mock `EmotionGraphWriter`; assert `write_emotion` called after `apply_dialogue_mood`; assert `EmotionBootstrapper.load_from_graph` seeds the store correctly.

---

## Graph / API surface

No new route. No new node type. 4 optional fields on character node — all pre-existing Cypher queries are unaffected (Neo4j ignores unknown properties; reads return them as None if absent).

Existing `GET /v1/npc/{id}/state` already surfaces `current_mood` + `mood_intensity` from `character_reader` — the new emotion fields will be visible there once written.

---

## Architecture fit

- `graph/emotion_writer.py` — new file in `graph/` layer. ✅
- `engines/emotion/emotion_bootstrap.py` — new file in `engines/` layer. Reads graph via session (passed in from `main.py` lifespan). ✅
- `EmotionUpdater` edit is purely additive (optional new param, existing callers unaffected). ✅
- `VadEmotionModel` edit is a single constant + one conditional — no new behavior path, only guards label replacement. ✅
- No new dependencies. No new routes. No LLM calls. Layer compliance: `engines/emotion` → `graph/`, `config`. ✅
- DECISIONS: DEC-084.

---

## Test plan

Write `tests/unit/test_emotion_writer.py` **first** (failing):

```python
# test 1 — write_emotion issues correct Cypher params
async def test_write_emotion_sets_all_four_fields():
    # mock session.run; assert called with valence/arousal/mood_label/tick params

# test 2 — write_emotion is idempotent (MERGE not CREATE)
async def test_write_emotion_uses_merge_not_create():
    # assert MERGE keyword in Cypher, not CREATE
```

Write `tests/unit/test_emotion_persistence.py` **first** (failing):

```python
# test 3 — apply_dialogue_mood calls writer when injected
async def test_apply_dialogue_mood_writes_through():
    # inject mock writer; call apply_dialogue_mood; assert writer.write_emotion called

# test 4 — apply_dialogue_mood does NOT call writer when not injected
async def test_apply_dialogue_mood_no_writer_no_crash():
    # no writer injected; call apply_dialogue_mood; no AttributeError

# test 5 — label inertia: low arousal preserves previous label
async def test_label_not_replaced_below_arousal_threshold():
    # previous state arousal=5 (< 20); mood_label="neutral"
    # new computation would produce "happy" but arousal < threshold → label stays "neutral"

# test 6 — bootstrap seeds store from graph dict
async def test_emotion_bootstrapper_populates_store():
    # mock character reader returns emotion fields; assert store.get(npc_id).valence == expected
```

Run: `pytest tests/unit/test_emotion_writer.py tests/unit/test_emotion_persistence.py -v`

---

## Done when

- 6 unit tests pass
- Process restart: character node has `emotion_valence`, `emotion_arousal`, `emotion_mood_label` fields set after first dialogue turn
- On next boot, `EmotionBootstrapper` loads those values — store is not neutral
- `make check` green
- Redis deferred: logged as ISSUE-092 (deferred to Unity/Unreal integration phase)
