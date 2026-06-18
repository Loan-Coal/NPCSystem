# EXP-19: Branching Quests & Consequence Chains — slice 1

**Goal / business rationale**
Quests are currently isolated linear records: completing one has no effect on any other.
Slice-1 adds `Quest -[:UNLOCKS]-> Quest` edges so completing (or failing) quest A
automatically offers quest B — the "win AND lose reachable game loop" requirement
(BUSINESS_INTENT §3) and the first step toward a living narrative system.
DEC-085 approved: `UNLOCKS` edge + hand-authored chains for slice-1; LLM-generated
chains (with `SlotValidator` grounding) are slice-2.

**First slice**
1. New `UNLOCKS` base edge.
2. New `graph/quest_chain_queries.py` — Cypher: find outgoing UNLOCKS edges for a quest.
3. New `engines/quest/quest_chain_resolver.py` — `QuestChainResolver`; on COMPLETED/FAILED,
   queries UNLOCKS edges and calls `quest_offer_service.offer_quest` for each match.
4. Edit `QuestLifecycleEngine.__init__` to accept optional injected `QuestChainResolver`.
5. Edit `demo_game/seed.py` — seed 2 hand-authored UNLOCKS chains as demo evidence.

---

## Current state (verified against codebase)

| Location | What's there |
|---|---|
| `src/npc_engine/engines/quest/quest_lifecycle_engine.py:125` | `accept_quest(session, quest_id, player_id)` |
| `src/npc_engine/engines/quest/quest_lifecycle_engine.py:236` | `evaluate_completion(session, quest_id, player_id, ...)` — transitions to `COMPLETED` or `IN_PROGRESS`; calls `update_quest_node_status`; does **not** check for downstream quests |
| `src/npc_engine/engines/quest/models.py:21` | `QuestStatus` enum: `DRAFT/OFFERED/ACCEPTED/IN_PROGRESS/COMPLETED/FAILED/EXPIRED` — already complete ✅ |
| `src/npc_engine/engines/quest/models.py:106` | `QuestStateRecord.status: QuestStatus` |
| `src/npc_engine/engines/quest/quest_offer_service.py` | `QuestOfferService.offer_quest(session, quest_id, player_id)` — the seam the resolver calls |
| `src/npc_engine/graph/quest_writer.py` | `get_quest_state`, `update_quest_node_status`, `upsert_quest_state` |
| `src/npc_engine/graph/quest_node_queries.py` | Quest node Cypher queries — reference for new chain query |
| `src/npc_engine/engines/quest_generation/slot_validator.py:29` | `SlotValidator.validate(fills, slot_definitions)` — used in slice-2 for LLM-generated chains |
| `demo_game/seed.py` | World seeder — seam for adding 2 manually authored UNLOCKS edges |
| `src/npc_engine/type_registry/base_edges/has_quest.yaml` | `HAS_QUEST` edge — reference YAML format |

---

## Files

**New base schema (one file):**
- `src/npc_engine/type_registry/base_edges/unlocks.yaml`

```yaml
edge_type: UNLOCKS
src_type: quest
dst_type: quest
fields:
  on_outcome:
    type: str
    required: true   # enforced as Literal["complete","fail","expire"] in Python models
```

**New graph support:**
- `src/npc_engine/graph/quest_chain_queries.py` — one function:
  `async def get_unlocked_quests(session, quest_id, outcome) -> list[str]`
  returns a list of next quest IDs where `r.on_outcome == outcome`.

**New engine file:**
- `src/npc_engine/engines/quest/quest_chain_resolver.py` — `QuestChainResolver` class:
  `async def resolve(session, quest_id, player_id, outcome)`.
  Calls `quest_chain_queries.get_unlocked_quests(session, quest_id, outcome)`;
  for each result, calls `self._offer_service.offer_quest(session, next_id, player_id)`.
  Logs each chain resolution: `logger.info("quest_chain_resolved", ...)`.
  Constructor: `__init__(self, offer_service: QuestOfferService)`.

**Edit (lifecycle engine — DI addition only):**
- `src/npc_engine/engines/quest/quest_lifecycle_engine.py` — add optional fifth init param:
  `chain_resolver: QuestChainResolver | None = None`.
  In `evaluate_completion`, after transitioning to `COMPLETED`:
  `if self._chain_resolver: await self._chain_resolver.resolve(session, quest_id, player_id, "complete")`.
  Likewise for `FAILED` with `"fail"` (when FAILED transition is added in slice-2).
  Existing callers that pass `None` are unaffected.

**Edit (demo seeder — 2 authored chains):**
- `demo_game/seed.py` — after existing quest seeds, add 2 `UNLOCKS` edges:
  - Quest A (`demo_patrol_duty`) UNLOCKS Quest B (`demo_captain_report`) `on_outcome: "complete"`
  - Quest C (`demo_missing_goods`) UNLOCKS Quest D (`demo_fence_confrontation`) `on_outcome: "complete"`
  These are authored inline in the seeder via `client.post("/v1/admin/graph/edges", ...)` using
  the existing generic edge admin endpoint.

**New tests (two files):**
- `tests/unit/test_quest_chain_resolver.py` — mock `get_unlocked_quests` + `offer_service`; test happy path, fail path, empty chain.
- `demo_game/tests/test_quest_chain_seed.py` — mock client; assert 2 UNLOCKS edge POST calls made.

---

## Graph / API surface

No new route. Example post-seed graph:
```
(:quest {id:"demo_patrol_duty"}) -[:UNLOCKS {on_outcome:"complete"}]-> (:quest {id:"demo_captain_report"})
```

When `evaluate_completion("demo_patrol_duty", player_id)` → COMPLETED:
resolver fires → `offer_quest("demo_captain_report", player_id)` → player sees new quest in their log.

---

## Architecture fit

OCP add-by-new-file: `quest_chain_resolver.py` and `quest_chain_queries.py` are new.
`QuestLifecycleEngine` edit is one optional param + a two-line conditional — no existing logic replaced.
`quest_offer_service.QuestOfferService` is the existing offer seam; `quest_chain_resolver` wraps it.
Layer: `engines/quest` → `graph/quest_chain_queries` (new) → `graph/quest_writer` (existing). ✅
No LLM in slice-1. No schema beyond `unlocks.yaml`. DECISIONS: DEC-085.

Note on slice-2 (LLM-generated chains): when no UNLOCKS edge exists, resolver will call
`quest_generation_engine.generate(session, llm, context)` then `SlotValidator.validate` before
calling `offer_quest`. That expansion is a separate brief.

---

## Test plan

Write `tests/unit/test_quest_chain_resolver.py` **first** (failing):

```python
# test 1 — happy path: UNLOCKS edge found → offer_quest called
async def test_resolver_offers_next_quest_on_complete():
    # mock get_unlocked_quests → ["quest_b"]
    # assert offer_service.offer_quest called with ("quest_b", player_id)

# test 2 — no chain: empty list → offer_quest not called
async def test_resolver_no_op_when_no_chain():
    # mock get_unlocked_quests → []
    # assert offer_service.offer_quest NOT called

# test 3 — fail outcome: correct on_outcome passed
async def test_resolver_passes_fail_outcome():
    # call resolve(..., outcome="fail"); assert get_unlocked_quests called with outcome="fail"

# test 4 — lifecycle engine calls resolver on COMPLETED
async def test_lifecycle_engine_calls_resolver_on_completion():
    # inject mock chain_resolver; call evaluate_completion to COMPLETED
    # assert chain_resolver.resolve called
```

Run: `pytest tests/unit/test_quest_chain_resolver.py -v`

---

## Done when

- 4 unit tests pass
- `demo_game/seed.py` seeds 2 UNLOCKS edges without error
- Completing `demo_patrol_duty` via the API auto-offers `demo_captain_report` to the player
- `make check` and `make test-demo` both green
