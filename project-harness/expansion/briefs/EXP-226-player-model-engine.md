# EXP-226 — Player-model / theory-of-mind engine (slice 1, DEC-102)

**Goal / rationale:** NPCs have no model of *the player* — what the NPC believes about the player's
trustworthiness/intent. A player-model engine gives each NPC a second-order belief node it can update and
read, the foundation of emergent cognition (deception, scheming build on it). Serves BUSINESS_INTENT
"NPCs with theory-of-mind." The `player_model` node + `HAS_PLAYER_MODEL` edge are ALREADY ADDED (DEC-102)
— do NOT change the schema.

**First slice (your scope):** A new `engines/player_model/` engine + a graph writer/reader for the
`player_model` node: derive/update an NPC's model of the player (perceived_trust, perceived_intent) from
the relation scalars + recent interaction, and persist/read it via `HAS_PLAYER_MODEL`. Prove with unit
tests. Keep it small — derivation can be simple this slice.

**Current state (verified):**
- `src/npc_engine/type_registry/base_nodes/player_model.yaml` — fields: id, npc_id, player_id,
  perceived_trust (int 0-100, optional), perceived_intent (str, optional), last_updated_at (optional).
  `src/npc_engine/type_registry/base_edges/has_player_model.yaml` — `HAS_PLAYER_MODEL: character →
  player_model`. Both applied; do NOT touch.
- Model your graph writer on an existing simple node writer (e.g. `graph/emotion_writer.py` or
  `graph/relation_phase_writer.py` from EXP-201) — raw Cypher SET/MERGE, no engine import in the graph layer.
- `derive_standing` (`engines/relationship/standing.py`) is available if you want to seed perceived_trust
  from the relation scalars (optional).

**Files:**
- NEW `src/npc_engine/engines/player_model/player_model_engine.py` — pure-ish engine that computes a
  `PlayerModelUpdate` (Pydantic v2) from inputs (relation scalars / interaction signal). Module docstring
  with `Does NOT:` + `Dependencies injected:`.
- NEW `src/npc_engine/graph/player_model_writer.py` — `async upsert_player_model(session, npc_id,
  player_id, perceived_trust, perceived_intent, tick)` MERGE on the `player_model` node + `HAS_PLAYER_MODEL`
  edge. Also a reader `get_player_model(session, npc_id, player_id)`. Graph layer; `Does NOT:`/`Dependencies
  injected:` docstring lines.
- NEW `src/npc_engine/engines/player_model/__init__.py` (package docstring).
- NEW tests: `tests/unit/test_player_model_engine.py` + `tests/unit/test_player_model_writer.py`
  (writer with a mocked AsyncSession asserts the Cypher targets `player_model` + `HAS_PLAYER_MODEL`).

**Graph/API surface:** engine + graph internal (no route this slice). Uses the new node/edge — no schema change.

**Architecture fit:** new-file-add (engine + graph writer). Layer engines→graph (no LLM in graph). No
composition-root wiring this slice (scheduler wiring is slice 2).

**Test plan (RED first):** `test_player_model_update_from_scalars` (engine derives perceived_trust) +
`test_upsert_targets_player_model_node` (writer Cypher). Watch fail, implement.
Run: `pytest tests/unit/test_player_model_engine.py tests/unit/test_player_model_writer.py -q`.

**Done when:** an NPC's player-model can be computed + persisted/read via the new node/edge; unit tests
pass; no schema change; docstrings present; functions ≤40 lines; no `from src` imports.
