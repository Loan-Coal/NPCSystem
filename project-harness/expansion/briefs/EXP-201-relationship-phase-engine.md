# EXP-201 — Relationship affinity phase engine (slice 1)

**Goal / rationale:** Make relationships a queryable *arc*, not just trust/fear/affection scalars —
NPC relationships progress through named phases. Serves the BUSINESS_INTENT "persistent relationships"
moat. Keystone: soft-unblocks EXP-202/226/227/228.

**First slice (your scope):** A pure new engine that derives a relationship phase from the relation
scalars (+ current phase) and a new graph writer that persists it to the existing edge fields. **New
files only — do NOT edit any existing engine this slice** (call-site wiring is slice 2). Prove it with
unit tests.

**Current state (verified):**
- `src/npc_engine/type_registry/base_edges/relates_to.yaml:11-12` — `relationship_phase` (str, optional)
  and `phase_started_at_tick` (int, optional) already exist; **zero Python writes them** (grep-confirmed).
- `src/npc_engine/engines/relationship/standing.py:61` — `derive_standing(*, trust, fear, affection)
  -> Standing` (band enum) exists and is pure. Reuse it to map scalars → phase, or define phase bands
  as named `UPPER_SNAKE` constants.

**Files:**
- NEW `src/npc_engine/engines/relationship/affinity_engine.py` — `RelationshipPhase` enum (Literal/Enum,
  e.g. STRANGER/ACQUAINTANCE/FRIEND/CLOSE/RIVAL/HOSTILE — your call, named) + a pure function
  `derive_phase(*, trust, fear, affection, current_phase, tick) -> PhaseTransition | None` returning a
  transition (new phase + tick) only when the phase changes. Pydantic v2 `PhaseTransition` model.
- NEW `src/npc_engine/graph/relation_phase_writer.py` — `async write_relationship_phase(session, src_id,
  dst_id, phase, tick)` writing the two edge fields via a Cypher SET (no schema change — fields exist).
  Module docstring with `Does NOT:` + `Dependencies injected:` lines (arch-conformance test requires it).
- NEW tests: `tests/unit/test_affinity_engine.py`, `tests/unit/test_relation_phase_writer.py`.

**Graph/API surface:** engine-internal. No new node/edge, no route. Writes existing `relates_to` fields.

**Architecture fit:** pure new-file-add (OCP). No closed-engine edit. Layer: engine + graph writer.
No schema change (DEC-free). `relation_phase_writer.py` is the only file allowed to write these fields.

**Test plan (RED first):**
1. `tests/unit/test_affinity_engine.py::test_phase_changes_on_threshold_crossing` — assert `derive_phase`
   returns a transition when scalars cross a band and `None` when phase is unchanged. Write it, watch it
   fail (function missing), then implement.
2. `tests/unit/test_relation_phase_writer.py::test_writes_phase_fields` — with a mocked `AsyncSession`,
   assert the Cypher sets `relationship_phase` + `phase_started_at_tick`.
Run: `pytest tests/unit/test_affinity_engine.py tests/unit/test_relation_phase_writer.py -q`.

**Done when:** both unit tests pass; phase derivation + persistence exist as new files; no existing
engine edited; docstrings present; functions ≤40 lines.
