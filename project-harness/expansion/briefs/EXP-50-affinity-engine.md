# EXP-50 — Relationship / Affinity engine (first slice)

**Goal / rationale:** A studio buying "persistent relationships" expects more than three clamped integers.
Derive a named relationship **standing** from the trust/fear/affection vector so behavior can gate on it
(who an NPC trades with, shares secrets with, defends) and kill `if trust > N` magic numbers. BUSINESS_INTENT
headline "persistent relationships per NPC."

**First slice (this worker's scope):** A pure, well-typed `derive_standing(trust, fear, affection) -> Standing`
plus a read route. **No consumer refactor yet** (that's a later slice — keeps this conflict-free). 5 bands on a
composite score (named config constants — the goal is to *have* bands and test them, not tune them):
`standing = clamp(trust + affection - fear, -100, 100)` →
`HOSTILE [-100,-50) · WARY [-50,-15) · NEUTRAL [-15,15] · FRIENDLY (15,50] · ALLIED (50,100]`.

**Current state (verify):**
- `src/npc_engine/engines/dialogue/dialogue_models.py:48-53` — `RelationDeltas` carries `trust/fear/affection`
  (each clamped); applied raw via `relation_mutator`. No engine derives standing today (`grep affinity|Standing` → none).
- `relates_to.yaml` already declares `relationship_phase`/`phase_started_at_tick` (currently dead) — out of
  scope for this first slice, but note them for a later persistence slice.
- DI composition root: `api/dependencies.py` (engines injected there). Mirror an existing small engine's shape.

**Files (all NEW → zero conflict):**
- NEW `src/npc_engine/engines/relationship/__init__.py` (package docstring).
- NEW `src/npc_engine/engines/relationship/standing.py` — `Standing` enum (`Literal`/`enum.Enum`),
  `UPPER_SNAKE` band cutoffs as module constants, pure `derive_standing(...)`.
- NEW `src/npc_engine/api/routes/relationship.py` — `GET /v1/npc/{npc_id}/relationship/{other_id}` returning
  the derived standing + raw scalars (typed Pydantic response model, not raw dict). Register in `main.py`
  include_router (EDIT — see conflict note) OR expose via an existing router; prefer a new router file +
  one include_router line.
- NEW `tests/unit/test_relationship_standing.py`.

**Conflict note:** the only existing-file edit is one `app.include_router(...)` line in `src/npc_engine/main.py`.
If another item in the batch also edits `main.py`, sequence this one after it (or the orchestrator adds the line
at fan-in). Otherwise it's a clean new-file add.

**Graph/API surface:** new read route `GET /v1/npc/{npc_id}/relationship/{other_id}` (auth-gated like all routes).
No schema change.

**Architecture fit:** OCP new-file engine + new route. Reads relation scalars via the existing graph reader/
service (do NOT put Cypher in the engine — use a reader). Pydantic-typed boundary.

**Test plan (write FIRST):** `tests/unit/test_relationship_standing.py` — parametrize `derive_standing` across
the 5 bands incl. exact boundary values (e.g. `(trust=60,affection=0,fear=0)`→`ALLIED`,
`(0,0,20)`→`WARY`, `(0,0,0)`→`NEUTRAL`), and assert cutoffs come from named constants (no magic numbers in the
function body). Run: `pytest tests/unit/test_relationship_standing.py -q`.

**Done when:** `derive_standing` returns the correct band for representative + boundary inputs, the read route
returns the typed standing for a seeded pair, and the test is green. (Carry-forward: `Standing` + cutoffs are now
the seam for the gossip secret-share gate and dialogue tone — wire those consumers in a follow-up slice.)
