# Next Session Handoff

**Branch:** `munich-demo`
**Last completed:** S3.0 — Phase 3 prep (test consolidation + multi-demo)
**Next task:** S3.1 — Flesh out scripted demo scenario with remaining scenes from `docs/DEMO_SCRIPT.md`

---

## What was completed this session (S3.0)

### ROADMAP fixed
- R2.1, R2.2 checkboxes updated to `[x]` in ROADMAP.md (both were already implemented in system_v1.yaml)
- Phase 2.5 marked COMPLETE
- Session log rows corrected (duplicate rows removed, session 7 + 8 added)
- S3.0 entry added to Phase 3 in ROADMAP.md

### E2E coverage gaps filled (Phase 2/2.5)

**`e2e/scenarios/scenario_voice_from_graph.py`** (new)
- `test_captain_sorn_voice_from_graph` — LLM judge: military/direct tone from voice_descriptor
- `test_mira_innkeeper_voice_from_graph` — LLM judge: warm/observant tone from voice_descriptor
- Mark: `@pytest.mark.llm_eval` — requires demo world + Ollama

**`e2e/scenarios/scenario_active_conditions.py`** (new)
- `test_npc_acknowledges_active_condition_blight` — keyword check: vw_elder refs blight/harvest
- `test_multiple_npcs_share_active_condition_awareness` — keyword check: vw_healer refs concern/illness
- No LLM judge needed (keyword_any sufficient)
- Requires village world: `make seed-village-world`

### YAML evals → pytest migration

**`e2e/scenarios/scenario_yaml_evals.py`** (new)
- Loads all 19 YAML cases from `evals/cases/` as parametrized pytest tests
- `@pytest.mark.eval` — run with `make eval-e2e`
- Skip semantics: 404 → wrong world seeded (not a failure), connection error → skip
- Reuses `evals/matchers.evaluate()` directly — no duplication
- `evals/runner.py` CLI still works unchanged (`make eval`)

**Makefile additions:**
- `make eval-e2e` — runs scenario_yaml_evals.py via pytest
- `make demo-village` / `make demo-village ARGS=--cached`
- `make demo-tavern` / `make demo-tavern ARGS=--cached`

### Multiple demo storylines

**`demo_game/scenarios/run_village_crisis.py`** (new)
- World: village world (vw_ prefix)
- 5 beats: Elder → Healer (world state) → bandit raid event → Guard (direct) → Farmer (rumour hedged) → Fence (evasive)
- Features: active_conditions, event propagation, Rule 9 gossip hedging, voice variety
- Cache: `.cache/village/`

**`demo_game/scenarios/run_tavern_intrigue.py`** (new)
- World: tavern world (tw_ prefix)
- 5 beats: Innkeeper before/after theft, Wanderer before/after, Merchant (distorted rumour)
- Features: voice distinctiveness contrast, event reshapes knowledge, knowledge_state=rumour hedging
- Cache: `.cache/tavern/`

### Skills added
- `llm-eval-as-e2e` — pattern for YAML eval → pytest parametrized integration
- `multi-demo-scenario` — pattern for new storyline demo script (with feature coverage matrix)

---

## Current test state

| Suite | Status |
|-------|--------|
| Unit tests (`make test`) | 984 passing, 1 pre-existing isolation failure |
| YAML evals (`make eval`) | 19 cases (some skip if wrong world active) |
| YAML evals as pytest (`make eval-e2e`) | Same 19 cases; skip semantics instead of fail |
| LLM judge (`make eval-llm-demo`) | 5/5 passing |
| Voice from graph (`pytest scenario_voice_from_graph.py -m llm_eval`) | 2 new tests — run after demo-seed + Ollama |
| Active conditions (`pytest scenario_active_conditions.py`) | 2 new tests — run after seed-village-world |

---

## S3.1 — Flesh out scripted demo scenario (next task)

`demo_game/run.py` is the primary demo runner for the hackathon. The current scene list has 4 dialogue beats cached. S3.1 adds the remaining scenes per `docs/DEMO_SCRIPT.md`.

### How to implement S3.1

1. Read `docs/DEMO_SCRIPT.md` — it defines the complete 5-minute scene sequence.
2. Compare against current `demo_game/run.py` SCENES list to identify missing beats.
3. Add missing dialogue beats and narration blocks to `run.py`.
4. After editing `run.py`:
   - Delete `.cache/demo/` and run `make demo-run` to rebuild cache with live LLM calls
   - Verify: `make demo-run ARGS=--cached` completes in < 1s
5. No seed changes for S3.1 — scripted runner expansion only.

### Important
- Do NOT change demo seed NPCs or graph structure. Demo world is locked.
- Do NOT change `demo_game/client.py` unless a missing API call is blocking a scene.
- If a planned scene requires a missing API feature, log in `project-harness/ISSUES.md` and use a NARRATION fallback.

---

## Available demos (post-S3.0)

| Demo | World | Make target | Features shown |
|------|-------|-------------|----------------|
| Gossip chain | demo | `make demo-run` | War epoch, 3-hop gossip distortion, knowledge guards |
| Village crisis | village | `make demo-village` | active_conditions, event propagation, voice variety, Rule 9 hedging |
| Tavern intrigue | tavern | `make demo-tavern` | Voice distinctiveness contrast, event reshapes knowledge, rumour hedging |

Each demo has `--dry-run` and `--cached` flags.

---

## Gotcha: demo scenarios use `client._http` for seed checks

`run_village_crisis.py` and `run_tavern_intrigue.py` call `runner.client._http.get(...)` for seed checks. If `EngineClient` renames or changes `_http`, update the `SeedCheck.execute()` method in both files.

---

## Gotcha: Docker prompt reload

After any edit to `system_v1.yaml`:
1. `docker cp src/npc_engine/prompts/dialogue/system_v1.yaml npcsystem-app-1:/app/src/npc_engine/prompts/dialogue/system_v1.yaml`
2. `docker restart npcsystem-app-1`
3. Delete `.cache/demo/` and run `make demo-run` to rebuild LLM cache
4. Verify: `make demo-run ARGS=--cached`

No graph wipe needed for prompt-only changes.

---

## Gotcha: Village world seed sets WorldState

`seeds/worlds/seed_village_world.py` upserts `WorldState {id:"world", active_conditions:["crop_blight"]}`.
If you run village seed before demo evals, blight is in world context. Demo evals are unaffected (they don't ask about crops), but to restore clean state: POST to `/v1/world/state` with `active_conditions: []`.

---

## Gotcha: Re-seed required after WorldState ID fix

Any Neo4j instance seeded with OLD demo seed (where `ws_main` was used) needs full re-seed:
1. `docker exec npcsystem-neo4j-1 cypher-shell -u neo4j -p password "MATCH (n:world_state {id:'ws_main'}) DETACH DELETE n"`
2. `make demo-seed`

---

See `project-harness/SKILLS_QUEUE.md` for available skill workflows:
- `eval-case-authoring` — adding new eval YAML cases
- `context-driven-prompt-rule` — adding/generalizing LLM rules keyed on context fields
- `graph-node-field-migration` — schema-level graph changes
- `llm-eval-as-e2e` — integrating YAML cases into pytest (NEW — S3.0)
- `multi-demo-scenario` — adding new storyline demo scripts (NEW — S3.0)
