# Skills Queue

_(Populated when a skill opportunity is identified during development. Append only.)_

## graph-node-field-migration
**Identified:** 2026-05-27 (R1.4)
**Pattern:** Adding a new optional field to a graph node type end-to-end: schema → seed → serialization → consumer → tests.
**Checklist:**
1. Add field to `type_registry/base_nodes/<type>.yaml` (schema source of truth).
2. Update all seed scripts — `build_*_payload()` function signature + returned dict + data tuples.
3. Confirm Cypher query uses `RETURN properties(c)` (all-fields pattern) — no change needed. If explicit RETURN, add the field.
4. Trace serialization: `subgraph_retriever` → `context_serializer` → confirm field appears at `npc.profile.<field>` in the context JSON.
5. Update consumer (e.g. `prompt_builder.py`) to read from context JSON.
6. Update tests: builder shape tests + consumer extraction tests.
7. **Docker note:** The app container has a baked copy of the YAML schemas. After updating `character.yaml`, run `docker cp <local_path> npcsystem-app-1:<container_path>` and `docker restart npcsystem-app-1` before re-seeding. Then wipe graph with `docker exec npcsystem-neo4j-1 cypher-shell -u neo4j -p password "MATCH (n) DETACH DELETE n"` and run `make demo-seed`.
**Reuse when:** Any Phase 3+ Character/Location node field addition (e.g. `schedule`, `mood_modifier`, `reputation_threshold`).


## context-driven-prompt-rule
**Identified:** 2026-05-27 (R2.1)
**Pattern:** When a new LLM behavioral rule must key off a specific context JSON field,
follow this workflow end-to-end:
1. Identify the context field and its value space (e.g. `knowledge_state: "rumor" | "knows"`).
2. Write a **paired** eval case: `keyword_none` (NPC must NOT do X when authoritative) +
   `keyword_any` (NPC MUST do Y when rumour-state). Both cases use `requires_world`.
3. Write the rule in `system_v1.yaml` referencing the field by exact JSON key name.
4. Bump `PROMPT_VERSION` in `prompt_builder.py`.
5. Delete `.cache/demo/` and run `make demo-run` to rebuild cache.
6. Verify: `make eval` all green, `make demo-run ARGS=--cached` completes clean.
**Reuse when:** Any Phase 3+ graph field needs to drive LLM behavior
(e.g. new Character fields, relationship-state flags, location conditions).
**Also applies to:** Generalizing an existing context-driven rule that has hardcoded
specifics (e.g. hardcoded location names, entity types, or domain references). Replace
the specific reference with the general context field. Same workflow: write paired evals,
edit YAML, bump version, cache rebuild.


## eval-case-authoring
**Identified:** 2026-05-27 (pre-Phase 3 cleanup)
**Pattern:** End-to-end workflow for adding a new eval YAML case to `evals/cases/`.
**Checklist:**
1. **Pick a seed world.** Which world has the NPC you need? Demo world: `mira_innkeeper`, `aldric_merchant`, `captain_sorn`, `lira_fence`, `old_henryk`. Village world: `vw_elder`, `vw_guard`. Tavern world: `tw_merchant`. If none fit, add the NPC to the relevant seed file first.
2. **Set `requires_world`** in the `seed` block. Omitting it means the case will fail with an HTTP error if the server doesn't have the NPC — not a helpful failure.
3. **Positive + negative pair discipline.** Every behavioral claim gets a positive case (`keyword_any`, `tone_judge`) AND a negative case (`keyword_none`). "Mira hedges gossip" must be paired with "Mira does NOT speak with military authority."
4. **`tone_judge` format.** Use `judge_prompt` (explicit YES/NO criteria) for nuanced behavioral tests. Use `description` only for simple sentiment checks. `judge_prompt` should end in "YES if …, NO if …." to force a binary verdict.
5. **Verify the case exercises the graph, not a fallback.** Run once with a wrong `npc_id` (e.g. `npc_id: doesnt_exist`). Expect the runner to show FAIL with an HTTP error. If you get a canned response instead, the server is returning a fallback — investigate `degradation_level` in the response.
6. **Wire a Makefile shortcut if needed.** Single-NPC voice sets don't need one. A new world's cases should have a `seed-<world>-world` target.
7. **Confirm all cases pass with `make eval`.** Voice/tone cases also require `make eval-llm-demo`.
**Reuse when:** Adding any new NPC to the eval harness, after a new world seed is created, or when a `context-driven-prompt-rule` skill run generates new behavioral constraints.


## llm-eval-as-e2e
**Identified:** 2026-05-28 (S3.0)
**Pattern:** Integrating YAML eval cases into the pytest e2e suite as parametrized tests.
**When to use:** Any time you want pytest reporting, skip semantics, or CI integration for YAML eval cases.
**Key files:** `e2e/scenarios/scenario_yaml_evals.py`, `evals/matchers.py`, `evals/cases/*.yaml`
**Checklist:**
1. YAML cases load at module level via `_load_cases()` for `@pytest.mark.parametrize` to see all IDs at collection time.
2. Add `evals/` to `sys.path` at the top of the scenario file — `matchers.py` uses bare imports. Pattern:
   ```python
   _EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
   if str(_EVALS_DIR) not in sys.path:
       sys.path.insert(0, str(_EVALS_DIR))
   from matchers import evaluate
   ```
3. **Skip semantics (not failure):** NPC 404 → wrong world seeded → skip with `requires_world` hint. Connection error → skip. Only fail on assertion failure after 200 OK.
4. **Do NOT duplicate matchers logic.** Import `evaluate()` from `evals/matchers.py` directly.
5. **Run:** `make eval-e2e` (pytest) or `make eval` (CLI runner — faster, no pytest overhead).
6. Both systems must stay green. Never remove a YAML case to fix a failing test — fix the evaluation.
**Reuse when:** Adding new eval cases, wiring evals to CI, or onboarding to test infrastructure.


## multi-demo-scenario
**Identified:** 2026-05-28 (S3.0)
**Pattern:** Building a new storyline demo script in `demo_game/scenarios/`.
**When to use:** Adding a 3rd or 4th story arc demo; or adapting an existing arc to a new world.
**Checklist:**
1. **Pick a seed world** with NPCs and events that showcase different features than existing demos. Each demo should highlight 2-3 features the others don't prominently show.
2. **Outline 5-7 beats** with a narrative arc: establish world state → introduce event → show knowledge propagation → contrast voices. At least one beat should show gossip hedging (Rule 9).
3. **Create `demo_game/scenarios/run_<name>.py`** modelled on `run_village_crisis.py`. Each script is self-contained — its own `LLMCache`, `Scene` dataclasses, and `DemoRunner`. `_CACHE_DIR` must be unique (`.cache/<name>/`).
4. **Add Makefile targets:**
   ```makefile
   demo-<name>:
       $(PYTHON) -m demo_game.scenarios.run_<name> $(ARGS)
   ```
   Add to `.PHONY` list.
5. **Build cache:** Run `make demo-<name>` (live) to warm the LLM cache. Then verify `make demo-<name> ARGS=--cached` completes in < 5s.
6. **Dry-run check first:** `make demo-<name> ARGS=--dry-run` must print the full beat sequence cleanly before any live run.
**Feature coverage matrix** (update when adding new demos):
| Feature | Gossip chain demo | Village crisis | Tavern intrigue |
|---------|-------------------|----------------|-----------------|
| epoch=war | ✅ | — | — |
| active_conditions (non-war) | — | ✅ crop_blight | ✅ theft_at_market |
| gossip hedging Rule 9 | ✅ Henryk | ✅ Farmer Jorin | ✅ Wanderer |
| voice distinctiveness | ✅ Sorn/Mira | ✅ Elder/Healer/Guard | ✅ Innkeeper/Bard/Merchant |
| knowledge guards | ✅ Mira/Henryk | ✅ Guard/Farmer | ✅ Wanderer |
| event propagation | ✅ war/market fire | ✅ bandit raid | ✅ theft |


## eval-harness
**Identified:** 2026-05-26 (R1.1)
**Pattern:** YAML-driven eval cases + synchronous runner + matcher library + markdown reports.
**Key files:** `evals/runner.py`, `evals/matchers.py`, `evals/cases/*.yaml`, `evals/report.py`
**Reuse when:** Adding new matcher kinds, new case categories, wiring the harness to CI, or onboarding to the eval structure from a cold start.
**Updated (R1.2):** `keyword_none` matcher added — mirrors `keyword_any`/`keyword_all`; checks that forbidden substrings do NOT appear in `npc_response`. Symmetric design: same field path, same case-insensitive substring logic. Use for behavioral constraint tests (voice bleed, role bleed, knowledge hallucination, self-incrimination).
