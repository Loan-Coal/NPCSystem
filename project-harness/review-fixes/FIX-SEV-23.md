# FIX-SEV-23 — Split unwaived files exceeding the 300-line hard limit

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** L
**Category:** architecture · **Absorbs:** ARCH-05, HARN-04, DEMO-03, DEMO-04

## Problem
11 src files (and ~12 demo files) exceed 300 lines without a valid waiver. The six worst unwaived src files:

| File | Lines | Notes |
|------|-------|-------|
| `api/dependency_singletons.py` | 620 | Composition root, no waiver |
| `retrieval/context_builder.py` | 486 | DEC-016 waiver says "367 lines" — now 486, waiver stale |
| `data/api_seeder.py` | 449 | No waiver |
| `engines/chapter/chapter_engine.py` | 347 | No waiver |
| `graph/political_writer.py` | 329 | No waiver |
| `api/routes/quest.py` | 327 | No waiver |

## Split plans

### `api/dependency_singletons.py` (620 → ~4 files, each ~80-150 lines)
Group the ~40 `@lru_cache` factory functions by domain. Each new file imports only from files below it in the dependency hierarchy to avoid circular imports.

**`api/dependencies_infra.py`** (~120 lines) — zero cross-singleton deps:
- `get_graph_db`, `get_redis_runtime`, `get_game_schema`, `get_llm_config`, `get_type_registry`, `get_dialogue_engine_model_config`
- `_register_adapter`, `close_registered_llm_adapters`, `_llm_adapters_to_close` list

**`api/dependencies_stores.py`** (~130 lines) — depends on infra only:
- `get_session_store`, `get_emotion_store`, `get_emotion_updater`, `get_embedding_index`, `get_engine_status_store`, `get_game_clock`, `get_idempotency_store`, `get_idempotency_service`, `get_context_cache`, `get_reindex_job_service`

**`api/dependencies_engines.py`** (~180 lines) — depends on infra + stores:
- `get_gossip_handler`, `get_event_handler`, `get_quest_lifecycle_engine`, `get_quest_generation_engine`, `get_event_quest_trigger`, `get_need_quest_trigger`, `get_pricing_engine`, `get_trade_engine`, `get_faction_politics_engine`, `get_story_pacing_engine`, `get_routine_engine`, `get_tick_scheduler`

**`api/dependencies_advanced.py`** (~180 lines) — optional/advanced engines:
- `get_clique_formation_engine`, `get_treaty_engine`, `get_oath_engine`, `get_skill_progression_engine`, `get_chapter_engine`, `get_mood_contagion_engine`, `get_succession_engine`, `get_agenda_engine`, `get_investigation_engine`, `get_military_engine`, `get_need_decay_engine`, `get_memory_consolidation_engine`, `get_negotiation_store`

**`api/dependency_singletons.py`** (kept as thin re-exporter, ~30 lines):
- `from .dependencies_infra import *` etc. — preserves all existing import paths.

### `retrieval/context_builder.py` (486 → ~2-3 files)
- **`retrieval/context_protocols.py`** (~30 lines): extract `EmbeddingIndexProtocol` (if not already in a protocols file).
- **`retrieval/context_serializer.py`** (~100 lines): extract private helpers `_to_json_safe`, `_enforce_final_serialized_budget_with_context`, `_enforce_final_serialized_budget`, `_normalize_ratio`, `_estimate_tokens`.
- **`retrieval/context_builder.py`** (remaining ~350 lines): `build_serialized_context` and the tier-assembly logic. Update DEC-016 with new line count.

### `data/api_seeder.py` (449 → 3 files)
- **`data/seed_data.py`** (~170 lines): data-definition functions `_locations(now)`, `_characters(now)`, `_events(now)`.
- **`data/seed_http.py`** (~80 lines): HTTP helpers `_call`, `_post_node`, `_post_edge`, `_Counter`.
- **`data/api_seeder.py`** (remaining ~100 lines): `seed()` main function + `_parse_args()` + `__main__` block. Imports from the two new files.

### `engines/chapter/chapter_engine.py` (347 → 2 files)
- **`engines/chapter/chapter_labeler.py`** (~30 lines): extract `_rule_based_label` → rename to `label_chapter_by_rules(events)` (public, one caller).
- **`engines/chapter/chapter_engine.py`** (remaining ~310 lines): `ChapterEngine` class only. Import `label_chapter_by_rules` from the new file.
  *(Still ~310 lines — if the class has natural internal groupings, extract additional helpers in a follow-up.)*

### `graph/political_writer.py` (329 → 3 files)
- **`graph/political_title_writer.py`** (~100 lines): `create_title`, `grant_title`, `add_heir`.
- **`graph/political_agenda_writer.py`** (~120 lines): `create_agenda`, `set_agenda_status`, `vote_on_agenda`.
- **`graph/political_leverage_writer.py`** (~100 lines): `create_leverage`, `use_leverage`.
- Remove original `graph/political_writer.py` and update all import sites.

### `api/routes/quest.py` (327 → 2 files)
- **`api/quest_helpers.py`** (~80 lines): private helpers `_quest_error_status`, `_quest_error_to_http`, `_build_transition_meta`, `_to_objective_inputs`.
- **`api/routes/quest.py`** (remaining ~240 lines): route handlers only (`offer_draft_quest`, `offer_quest`, `accept_quest`, `update_objective`, `evaluate_completion`, `apply_rewards`). Import helpers from `api/quest_helpers.py`.

## Steps (execute file by file)
For each split:
1. Create the new file(s) with correct module docstrings and layer annotations.
2. Move the target functions/classes to the new file.
3. Update all `import` sites (use `rg` to find all callers).
4. Run `make type` after each split to catch any import issues immediately.
5. Run `make test` after all splits.

## Verification
- `rg "dependency_singletons\|context_builder\|api_seeder\|chapter_engine\|political_writer\|routes/quest" src/ --count` — same coverage as before.
- `make type` passes.
- `make test` passes.
- `wc -l` on each new file: all under 300.

## Blast radius
Large — touches the composition root and several high-traffic modules. Execute one file at a time; commit after each split so rollback is clean.
