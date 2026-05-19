# Next Session Instructions

## Current state

Roadmap V2 — **Phase 7 M/S implementation in progress (or just completed).**
Run tests before touching any code:

```bash
pytest tests/ -q
```

---

## Phase 7 M/S — What was done this session

| Step | Deliverable | Status |
|------|-------------|--------|
| 7.0 | YAML schema prep (event, faction, character, relates_to) | ✅ Done |
| 7.0 | `scripts/migrations/add_phase7_schema.py` | ✅ Done |
| 7.3.M | `MoodContagionEngine` + `mood_queries.py` | ✅ Done |
| 7.3.M | `EmotionStore` Neo4j persistence (`mood_intensity` field) | ✅ Done |
| 7.3.M | `MoodContagionEngine` wired into `TickScheduler` + singletons | ✅ Done |
| 7.4.S | `CONNECTS_TO` edge + `location_graph_queries.py` + API routes | ✅ Done |
| 7.5.M | `CHAPTER`, `CHOICE`, `NARRATIVE_BEAT` YAML nodes/edges | ✅ Done |
| 7.5.M | `IS_CANONICAL` gates in `gossip_distort.py` + `memory_consolidation_engine.py` | ✅ Done |
| 7.5.M | `chapter_writer.py` + `chapter_queries.py` | ✅ Done |
| 7.5.M | `chapter_engine.py` with rule-based detection + LLM labeling | ✅ Done |
| 7.5.M | `ChapterEngine` wired into `TickScheduler` + singletons | ✅ Done |

---

## Flaws identified in Phase 7 roadmap (all carry forward to L modules)

These were found during Phase 7 planning and must be applied when implementing the L modules:

| # | Flaw | Affected module | Fix |
|---|------|-----------------|-----|
| F1 | `DEDUCTION.supporting_evidence_ids` is string-array FK | 7.1 Detective | Use `SUPPORTED_BY: DEDUCTION → EVIDENCE` edge instead |
| F2 | `TITLE.current_holder_id` duplicates `HOLDS_TITLE` edge, will go stale | 7.2 Political | Remove field; query via edge + unique constraint |
| F3 | `LEVERAGE.secret_id` is string FK with no graph traversal | 7.2 Political | Add `GROUNDED_IN: LEVERAGE → Secret` edge at creation |
| F8 | `ARMY.composition` is untyped string | 7.4 full | Define as JSON with schema `{infantry, cavalry, siege}`; validate at write |

---

## Phase 7 L modules — deferred, next to implement

### 7.1 — Detective/Mystery

**Migration:** `scripts/migrations/add_investigation_schema.py`

**YAML nodes:** `evidence.yaml`, `deduction.yaml`

**YAML edges:** `implicates.yaml` (Evidence→Character), `suspects.yaml` (Char→Char),
`present_at.yaml` (Evidence→Location), `supported_by.yaml` (Deduction→Evidence) ← F1 fix

**New files:**
- `src/npc_engine/graph/investigation_service.py`
- `src/npc_engine/engines/investigation/investigation_engine.py`
- `tests/unit/test_investigation_engine.py`
- `e2e/scenarios/scenario_murder_mystery.py`

**Note:** `get_investigation_context` returns a structured inconsistency list for the dialogue engine to narrate. No direct LLM call in the investigation engine itself.

---

### 7.2 — Political Simulation

**Apply F2 fix:** No `current_holder_id` on TITLE node. Query current holder via `HOLDS_TITLE` edge.
**Apply F3 fix:** Add `GROUNDED_IN: LEVERAGE → Secret` edge at creation time.
**Apply event pattern:** Political events (AGENDA votes, power shifts) must use `faction_id`/`reputation_delta` on `EventTemplate`, same pattern as existing event wiring.

**Migration:** `scripts/migrations/add_political_schema.py`

**YAML nodes:** `title.yaml`, `agenda.yaml`

**YAML edges:** `leverage.yaml`, `holds_title.yaml`, `heir_of.yaml`,
`supports_agenda.yaml`, `opposes_agenda.yaml`, `grounded_in.yaml`

**Faction node update** (already prepped in YAML via 7.0): `power_score`, `treasury`, `military_strength`

**New files:**
- `src/npc_engine/engines/succession/succession_engine.py`
- `src/npc_engine/engines/agenda/agenda_engine.py`
- `src/npc_engine/graph/political_writer.py`
- `src/npc_engine/graph/political_queries.py`
- `tests/unit/test_succession_engine.py`
- `tests/unit/test_agenda_engine.py`
- `e2e/scenarios/scenario_succession_crisis.py`

---

### 7.3 (full) — Social Simulation

**Note:** Mood contagion engine already shipped. This step adds NEED + LIFE_EVENT + OUTRANKS.

**Apply F4 fix:** LIFE_EVENT is NOT a separate node type. Use `EVENT` node with `subkind` field
(already added to `event.yaml` in 7.0). Valid `subkind` values: `birth`, `death`, `marriage`, `illness`.

**`relates_to.yaml` already updated** (in 7.0): `relationship_phase`, `phase_started_at_tick` fields.

**Migration:** `scripts/migrations/add_social_schema.py`

**YAML nodes:** `need.yaml` (`kind`, `level: 0-100`, `decay_rate`, `character_id`)

**YAML edges:** `satisfies_need.yaml` (Action/Item/Location → Need), `outranks.yaml` (Char → Char, fields: `context`, `rank_delta`)

**New files:**
- `src/npc_engine/engines/need/need_decay_engine.py`
- `src/npc_engine/graph/need_writer.py`
- `src/npc_engine/graph/need_queries.py`
- `tests/unit/test_need_decay_engine.py`
- `e2e/scenarios/scenario_social_needs.py`

---

### 7.4 (full) — Strategy/4X

**Note:** `CONNECTS_TO` edge already shipped. This step adds RESOURCE_NODE, ARMY, OCCUPIES, COMMANDS.

**Apply F8 fix:** `ARMY.composition` must be stored as JSON string with validated schema
`{"infantry": int, "cavalry": int, "siege": int}`. Validate in graph writer.

**`controls.yaml` update:** Add `control_strength: {type: int, required: false}` and
`contested_by_faction_id: {type: str, required: false}`.

**Migration:** `scripts/migrations/add_strategy_schema.py`

**YAML nodes:** `resource_node.yaml` (kind, yield_per_tick, depletion), `army.yaml` (faction_id, strength, current_location_id, composition)

**YAML edges:** `produces.yaml` (Location→ResourceNode), `commands.yaml` (Char→Army), `occupies.yaml` (Army→Location)

**New files:**
- `src/npc_engine/engines/military/military_engine.py`
- `src/npc_engine/graph/military_writer.py`
- `src/npc_engine/graph/military_queries.py`
- `tests/unit/test_military_engine.py`
- `e2e/scenarios/scenario_territorial_war.py`

---

## Open follow-ups (not in Phase 7 roadmap)

1. **Two-pass reranking for memories** — Phase 6 applies it to beliefs/goals/secrets; memories would benefit equally.
2. **CROSS_ENCODER_ENABLED=true** — wired but defaulted off; enable in staging.
3. **OathEngine violation logic** — `check_pledge_violations` stub still returns `[]`.
4. **Treaty mechanical enforcement** — tribute condition checking detects due-dates but does not verify payment.
