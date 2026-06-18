# EXP-227 — Player-aware drama director engine (slice 1)

**Goal / rationale:** The world reacts but never *directs* — nothing notices when the player is idle or a
relationship has plateaued and injects a beat to re-engage. A drama director makes the experience feel
authored. Serves BUSINESS_INTENT "engagement / living world." No schema change (slice 1 infers from
signals; no new node).

**First slice (your scope):** A new `engines/director/` engine with a pure decision function that, given
engagement signals (player idle ticks, relationship plateau indicator), decides whether to inject a beat
and which kind — returning a typed `DirectorDecision` (or None). New-file-only — do NOT wire it into the
scheduler this slice (that's slice 2), and do NOT add a schema field (the optional `event.targets_player_id`
was rejected per OPEN_QUESTIONS OQ-11 — infer the target, don't store it).

**Current state (verified):**
- `src/npc_engine/engines/` — `events` and `story_pacing` engines exist (read their public surface to
  model the "beat" shape your decision references). The director composes signals; it does NOT edit them.
- Relationship phase (EXP-201, `RelationshipPhase`) is available as a plateau signal input if useful
  (pass it in as a param — keep the director pure; do not call the graph from inside the decision fn).

**Files:**
- NEW `src/npc_engine/engines/director/director_engine.py` — `DirectorDecision` (Pydantic v2: should_inject:
  bool, beat_kind: Literal[...], reason) + a pure `decide(*, player_idle_ticks, relationship_phase, ...)
  -> DirectorDecision | None`. Name thresholds as `UPPER_SNAKE` constants (idle threshold, plateau rule).
  Module docstring with `Does NOT:` + `Dependencies injected:`.
- NEW `src/npc_engine/engines/director/__init__.py` (package docstring).
- NEW test: `tests/unit/test_director_engine.py` — idle beyond threshold → inject; engaged → None;
  plateau → inject.

**Graph/API surface:** engine-internal. No schema, no route, no new node.

**Architecture fit:** pure new-file-add. Layer = engines. No schema. No scheduler wiring this slice.

**Test plan (RED first):** `test_director_injects_on_idle`, `test_director_silent_when_engaged`,
`test_director_injects_on_plateau`. Watch fail (engine missing), implement.
Run: `pytest tests/unit/test_director_engine.py -q`.

**Done when:** the director decides inject/skip from engagement signals deterministically; tests pass; no
schema; no existing engine edited; docstrings present; functions ≤40 lines; no `from src` imports.
