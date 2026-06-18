# EXP-53 — Dialogue-Driven Knowledge Learning (first slice)

**Goal / rationale:** NPCs currently forget what the player tells them between sessions because
the dialogue engine only writes memory-from-arousal, never belief facts.  EXP-53 closes the
learn→ground→answer anti-hallucination loop: when the player asserts a fact, the NPC writes a
`belief` node + `BELIEVES` edge with provenance so future context retrieval can surface it.
BUSINESS_INTENT: anti-hallucination moat, Success Criterion 1 (`BUSINESS_INTENT.md:74`).
DEC-072 approved: single-pass `learned_facts` output, reuse `BELIEVES` edge, 3 optional provenance
fields — no second LLM pass, no new edge type.

---

## First slice (worker scope)

Add `learned_facts: list[str]` to the dialogue LLM output schema (one YAML + one model edit),
write those facts to `belief` nodes via a new `KnowledgeExtractionEngine`, gated by
`KNOWLEDGE_LEARNING_ENABLED` config flag (default `False`).  Player-sourced facts only
(self-assertions or direct statements — no NPC-to-NPC in this slice).

---

## Current state (verified)

- `src/npc_engine/engines/dialogue/dialogue_models.py:86–117` — `DialogueResponse` is the LLM output
  model; add `learned_facts: list[str] = Field(default_factory=list)`.
- `src/npc_engine/engines/dialogue/dialogue_handler.py:179` — `create_from_arousal` is the only
  post-dialogue graph write; add the knowledge-engine call after this block, guarded by config flag.
- `src/npc_engine/type_registry/base_edges/believes.yaml:4` — `fields: {}` (add 3 optional fields).
- `src/npc_engine/type_registry/base_nodes/belief.yaml` — `belief` node exists with `id, content,
  confidence, created_at_game_time`.
- `src/npc_engine/prompts/dialogue/system_v1.yaml:243` — describes LLM output schema; add
  `learned_facts` instruction here.
- `grep -r "knowledge_learning"` → 0 hits (entirely new package).
- No existing `graph/knowledge_writer.py`.

---

## Files

**New:**
- `src/npc_engine/engines/knowledge_learning/__init__.py`
- `src/npc_engine/engines/knowledge_learning/models.py` — `LearnedFact(BaseModel)`,
  `KnowledgeExtractionResult(BaseModel)`.
- `src/npc_engine/engines/knowledge_learning/knowledge_extraction_engine.py` —
  `KnowledgeExtractionEngine`.  Public method:
  `async process(session, *, npc_id, player_id, tick, learned_facts: list[str]) → KnowledgeExtractionResult`.
- `src/npc_engine/graph/knowledge_writer.py` — `write_belief(session, *, npc_id, content, confidence,
  source_character_id, learned_at_tick, game_time_str) → str`.  Opens a single transaction, merges a
  `belief` node (uuid id), creates `BELIEVES` edge with provenance fields, commits.
- `tests/unit/test_knowledge_extraction_engine.py`

**Edited:**
- `src/npc_engine/type_registry/base_edges/believes.yaml` — add DEC-072 provenance fields:
  ```yaml
  fields:
    source_character_id: { type: str, required: false }
    learned_at_tick:     { type: int, required: false }
    confidence:          { type: int, required: false, range: [0, 100] }
  ```
- `src/npc_engine/engines/dialogue/dialogue_models.py` — add to `DialogueResponse`:
  `learned_facts: list[str] = Field(default_factory=list)`
- `src/npc_engine/engines/dialogue/dialogue_handler.py` — after `create_from_arousal` block (line ≈185):
  ```python
  if (
      self._knowledge_engine is not None
      and getattr(self._settings, "KNOWLEDGE_LEARNING_ENABLED", False)
      and final_response.learned_facts
  ):
      await self._knowledge_engine.process(
          session=self._session,
          npc_id=request.npc_id,
          player_id=request.player_id,
          tick=tick_id,
          learned_facts=final_response.learned_facts,
      )
  ```
  Add `knowledge_engine: KnowledgeExtractionEngine | None = None` to `__init__` params
  (after existing params, keyword-only, default `None`).
- `src/npc_engine/prompts/dialogue/system_v1.yaml` — add after the `facial_expression` field description:
  > - `learned_facts`: optional list of strings — facts the player explicitly stated about themselves
  >   or the world (e.g., "I am the new captain", "the bandits moved to the old mill").  Omit or
  >   leave empty if the player stated no new facts.  Include ONLY facts the player explicitly asserted,
  >   NOT inferences, NPC beliefs, or narration.

---

## Algorithm (`KnowledgeExtractionEngine.process`)

```
for each fact_str in learned_facts:
    if len(fact_str) < 5 or len(fact_str) > 300: skip (bounds check)
    await knowledge_writer.write_belief(
        session,
        npc_id=npc_id,
        content=fact_str,
        confidence=70,               # default confidence for player-stated facts
        source_character_id=player_id,
        learned_at_tick=tick,
        game_time_str=...,           # pass from caller (use world_state.game_time)
    )
    logger.info("belief_written", npc_id=npc_id, player_id=player_id, tick=tick)
return KnowledgeExtractionResult(written=count, skipped=skipped)
```

Contradiction handling (first slice): write regardless — `CONTRADICTS` edge linking is slice-3.
Dedup (first slice): no dedup — same content can be written twice; dedup is slice-3.

---

## Graph / API surface

No new HTTP route in first slice (admin `GET /v1/admin/characters/{id}/beliefs` is deferred).
`believes.yaml` gains 3 optional fields (DEC-072 approved schema touch).

---

## Architecture fit

New engine dir `engines/knowledge_learning/`.  New graph sub-writer `graph/knowledge_writer.py`
(graph-owned, `AsyncSession`-injected — session-ownership rule honored).  Minimal edit to
`dialogue_handler.py`: one optional injected dependency + 8-line guarded call block.  No second
LLM call.  No new prompt file — `learned_facts` field rides the existing dialogue YAML.

**OCP note:** editing `dialogue_handler.py` adds a new injected dependency, not a new type-dispatch
variant.  This is DI wiring, not an OCP violation.

---

## Test plan

Write `tests/unit/test_knowledge_extraction_engine.py` FIRST.

| Test | Asserts |
|------|---------|
| `test_writes_belief_for_each_fact` | 2 facts in `learned_facts` → `write_belief` called twice |
| `test_skips_empty_or_too_short_facts` | `""`, `"ab"` → skipped, count=0 |
| `test_skips_too_long_facts` | >300 chars → skipped |
| `test_returns_correct_written_count` | 3 valid facts → `result.written == 3` |
| `test_knowledge_writer_merges_belief_node` | unit-test graph write with mocked session (assert run called with correct Cypher params) |
| `test_handler_calls_engine_when_enabled` | mock engine injected; `KNOWLEDGE_LEARNING_ENABLED=True`; `learned_facts=["I am X"]` → `process` called once |
| `test_handler_skips_engine_when_disabled` | `KNOWLEDGE_LEARNING_ENABLED=False` → `process` never called |
| `test_handler_skips_when_engine_none` | `knowledge_engine=None` → no AttributeError |

Run: `pytest tests/unit/test_knowledge_extraction_engine.py -q`

---

## Done when

- Tests green.
- `KnowledgeExtractionEngine.process()` exists and is async.
- `DialogueResponse.learned_facts` field present (Pydantic v2, `list[str]`, default empty).
- `believes.yaml` has 3 optional provenance fields.
- `graph/knowledge_writer.py` has `write_belief` with module docstring.
- `dialogue_handler.py` optional `knowledge_engine` kwarg; call is guarded by config flag.
- `system_v1.yaml` documents `learned_facts` output field.
- No file > 300 lines; all Cypher in `graph/`; no prompt string in Python.
- `KNOWLEDGE_LEARNING_ENABLED` defaults to `False` (existing `config.py` / `Settings`).
- Adjacent issues spotted: report, do NOT fix.
