# Next Session Instructions

## Current state

Roadmap V3 — **Phase 2: Demo Game Skeleton + Graph Visualization.**

Run tests before touching any code:

```bash
pytest tests/unit/ -q
```

965 tests, 964 pass in full suite (1 pre-existing gossip flake passes in isolation).

---

## Entry criteria

| Criterion | Status |
|---|---|
| Phase 1 handoff signed off | YES |
| War scenario manual sign-off | YES (2026-05-21, on qwen2.5:7b) |
| War scenario re-verified on qwen2.5:14b | ⏳ PENDING — run after `ollama pull qwen2.5:14b` |
| `make eval-llm` passes (JUDGE_MODEL=qwen2.5:14b) | ✅ YES — 4/4 green (2026-05-21, a86082e) |
| docs/PROMPT_DESIGN.md reflects stage_b_v1.1 | YES |
| docs/RELEVANCE_WEIGHTS.md reflects explicit implementation | YES |

---

## Key context for the session

- **Model:** `qwen2.5:14b` via Ollama. Pull if not present: `ollama pull qwen2.5:14b`
- **Prompt version:** `stage_b_v1.1` (`PROMPT_VERSION` constant in `prompt_builder.py`)
- **Prompt file:** `src/npc_engine/prompts/dialogue/system_v1.yaml`
- **LLM judge:** `make eval-llm` — requires running server + `JUDGE_MODEL=qwen2.5:14b`
- **War baseline transcript:** `transcripts/war_epoch_baseline.md` (recorded on qwen2.5:7b)
- **explicit_node_ids:** New field on `POST /v1/dialogue` — pass graph node IDs to pin
  specific context nodes for a turn. Weight controlled by `RelevanceWeights.explicit`
  (default `0.0` — inert unless set in a weight profile). See `docs/RELEVANCE_WEIGHTS.md`.
- **Known gap:** `active_conditions` has no MUST NOT enforcement (only `epoch` does).
  Not blocking Phase 2 but relevant if scene-level behavioral events are needed.
- **Memory consolidation:** `POST /v1/admin/memories/consolidate/{char_id}` is working
  (500 bug fixed in a86082e — asyncio.gather on shared session).
- **Context now includes NPC inner life:** `context.npc.goals`, `context.npc.beliefs`,
  `context.npc.memories` are serialized into every prompt. System prompt Rule 7
  instructs the LLM to hint at high-urgency goals in open-ended responses.
- **Reputation:** structured dicts in `context.player_reputation`; Rule 2 uses MUST
  language for hostile standings.
- **Seeder:** `make seed-api` uses typed admin endpoints for all Phase 3 resources.
  Re-seeding duplicates beliefs/goals/etc — wipe DB first.

---

## Phase 1 open items

1. **War scenario re-verify on qwen2.5:14b** — low priority, informational only:
   ```bash
   ollama pull qwen2.5:14b
   pytest e2e/scenarios/scenario_war_breaks_out.py -v -s --scenarios-only
   ```
   War scenario passed manually on qwen2.5:7b (2026-05-21). The eval judge test
   `test_war_epoch_reflects_danger` also passes on 14b, so risk here is low.

**Phase 1 is otherwise closed. Phase 2 can begin.**

---

## Phase 2 entry point

Phase 2: Demo Game Skeleton + Graph Visualization.

Goals:
- Build a minimal playable demo scenario driven by `POST /v1/dialogue`.
- Visualize the NPC knowledge graph (events, beliefs, goals, relations) in real time.
- Exercise `explicit_node_ids` to demonstrate scene-critical context pinning.

Relevant files from Phase 1:
- `e2e/scenarios/scenario_war_breaks_out.py` — template for scenario structure.
- `src/npc_engine/engines/dialogue/dialogue_models.py` — `DialogueRequest` (now has `explicit_node_ids`).
- `docs/RELEVANCE_WEIGHTS.md` — how to configure and use explicit context pinning.
- `project/DECISIONS.md` — model and API field decisions Phase 2 must respect.
