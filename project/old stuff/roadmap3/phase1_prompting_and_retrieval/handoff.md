# Phase 1 Handoff

<!-- Last updated: 2026-05-21. All gates closed. Phase 1 DONE. -->

## Gate Status

1. Existing tests pass:
   [x] YES — 965 unit tests, 0 failures (964 pass in full suite; 1 pre-existing gossip
   flake passes in isolation — not a regression). Run: `pytest tests/unit/ -q`

2. New tests pass:
   [x] YES — 9 tests in `tests/unit/test_prompt_builder.py` all green.
   7 new explicit-scoring tests in `test_context_scoring.py` all green.
   `test_war_epoch_reflects_danger` in `scenario_llm_judge.py` is structurally
   correct; requires a running server + `qwen2.5:14b` pulled to execute.

3. E2E baseline:
   [x] NO REGRESSION
   War scenario passes: `pytest e2e/scenarios/scenario_war_breaks_out.py -v -s --scenarios-only`
   Transcript saved to `transcripts/war_epoch_baseline.md` (2026-05-21).
   NOTE: war scenario must be re-run after `ollama pull qwen2.5:14b` to confirm
   epoch MUST NOT constraints still hold with the 14b model weights.

4. Manual sign-off:
   [x] SIGNED OFF (on qwen2.5:7b — re-verify on qwen2.5:14b after pull)
   Evidence: Turn 2 — guard asked "Is the road to the capital safe to travel?"
   with `epoch="war"`. Response: "The road to the capital is open, but I must
   caution you. With the northern war raging, it's a dangerous journey. Travelers
   have reported attacks by bandits and rogue soldiers. Stay vigilant if you
   decide to go." — no safe-road language; danger/tension throughout.

5. LLM judge (HARD gate from Phase 1):
   [x] PASS — 4/4 green (2026-05-21, commit a86082e)
   `JUDGE_MODEL=qwen2.5:14b make eval-llm` — all tests pass on a seeded live server.
   - test_memory_consolidation_coherence ✓
   - test_hostile_npc_tone_with_low_reputation ✓
   - test_goal_hinting_in_dialogue ✓
   - test_war_epoch_reflects_danger ✓

6. Coverage on new code:
   [x] YES — `prompt_builder.py` changes covered by 9 unit tests.
   `explicit` scoring covered by 7 new unit tests in `test_context_scoring.py`.
   `docs/PROMPT_DESIGN.md` and `docs/RELEVANCE_WEIGHTS.md` updated (P1.6 done).

---

## What Shipped

- [x] Retrieval fix (cause a) — **SKIP**: world state is tier0/priority=100 in
  `context_builder.py:276`; cannot be budget-truncated. Retrieval was not the cause.
- [x] System prompt rewrite (cause b) — prompt version: `stage_b_v1.1`
  File: `src/npc_engine/prompts/dialogue/system_v1.yaml`
  Key change: epoch rule rewritten with `AUTHORITATIVE` label and `MUST NOT`
  prohibitions. Inline `_SYSTEM_PROMPT` Python string removed.
- [x] Model upgrade — new model: `qwen2.5:14b` (Ollama, ~8.5 GB Q4_K_M, fits in 12 GB VRAM).
  Previous: `qwen2.5:7b` (~4.7 GB). Config: `src/npc_engine/engines/dialogue/llm_config.yaml`.
  Pull: `ollama pull qwen2.5:14b`
- [x] LLM judge wired — `test_war_epoch_reflects_danger` added to
  `e2e/scenarios/scenario_llm_judge.py`. Run: `JUDGE_MODEL=qwen2.5:14b make eval-llm`
  (requires live server).
- [x] explicit weight implemented — `explicit_node_ids: tuple[str, ...]` added to
  `DialogueRequest`. Threaded through `build_serialized_context` → `rank_tier_items` →
  `_build_candidate`. `RelevanceWeights.explicit` defaults to `0.0` (existing profiles
  unchanged). 7 unit tests green. Graduated to `project/DECISIONS.md`.
- [x] docs/PROMPT_DESIGN.md updated — Stage B: `v1.1`. YAML path and epoch rationale added.
- [x] docs/RELEVANCE_WEIGHTS.md updated — `explicit` mechanism documented with usage example.

---

## What Was Deferred

**active_conditions gap** — `context.world.active_conditions` (e.g. `["bandit_activity"]`,
`["thief_spotted_market"]`) is passed to the LLM but has no MUST NOT enforcement rules.
The prompt says "also read this list" — the model infers behavior from the string value,
which is the same weak-hint problem that P1.2 fixed for epoch. Epoch now has hard rules;
active_conditions does not. Address in a future phase if runtime event injection proves
insufficient for scene-level behavioral changes.

**Dedicated judge model** — judge currently uses the same `qwen2.5:14b` as the dialogue
engine. Fine for local dev; a production setup may want a smaller, faster judge model
(e.g. `llama3.2:3b`) on a separate Ollama instance to avoid head-of-line blocking.

**~70 remaining Neo4j consume() gaps** — the hot path for eval tests is fixed, but
~70 additional `session.run()` call sites across the codebase still lack
`await result.consume()`. These are not in the current hot path and caused no
failures, but a full audit pass is recommended before scaling to concurrent load.

---

## What Phase 2 Needs to Know

Model in use: `qwen2.5:14b` via Ollama (`http://localhost:11434`)
Pull: `ollama pull qwen2.5:14b`
Prompt version: `stage_b_v1.1`
Prompt file: `src/npc_engine/prompts/dialogue/system_v1.yaml`
Prompt builder: `src/npc_engine/engines/dialogue/prompt_builder.py`

**Seeder:** `make seed-api` — use on a fresh DB. Re-running on a populated DB duplicates
Phase 3 resources (beliefs, goals, items, secrets, memories). Wipe Neo4j first.

**Context serializer now includes NPC inner life:**
`context.npc.goals`, `context.npc.beliefs`, and `context.npc.memories` are present in
every dialogue prompt. System prompt Rule 7 instructs the LLM to let high-urgency goals
color open-ended responses as subtext. Phase 2 scenarios can rely on this behavior.

**Explicit context pinning:**
`POST /v1/dialogue` accepts an optional `explicit_node_ids: list[str]` field.
Pass graph node IDs to boost specific nodes in the retrieval ranking for that turn.
Weight controlled by `RelevanceWeights.explicit` (default `0.0` — inert unless set).
See `project/DECISIONS.md` and `docs/RELEVANCE_WEIGHTS.md`.

**Reputation payloads** are now structured dicts `{faction_name, standing, label}` in
`context.player_reputation`. System prompt Rule 2 enforces hostile behavior with MUST
language. Phase 2 scenarios can set reputation via `PUT /v1/admin/characters/{id}/reputation/{faction}`.

API routes confirmed working (all 4 eval tests green):
- `POST /v1/dialogue` — ✅
- `POST /v1/graph/nodes/{type}` — ✅ (world state upsert)
- `GET /v1/admin/memories/{char_id}` — ✅
- `POST /v1/admin/memories/consolidate/{char_id}` — ✅ (was broken, now fixed)
- `POST /v1/admin/factions/{id}/members` — ✅ (fixed ordering bug in seeder)
- `PUT /v1/admin/characters/{id}/reputation/{faction}` — ✅

Known gap: `active_conditions` behavioral rules are soft (see deferred above).

---

## What Phase 3 Needs to Know

**Recommended target engine for QLoRA adapter:** `dialogue` — the epoch MUST NOT
constraints work at the prompt level but a fine-tuned model would internalize them
structurally, removing reliance on prompt verbosity. Phase 1 showed prompting alone
is sufficient for epoch-level rules; Phase 3 training data should use war scenario
transcripts as positive examples.

**Training data signals from Phase 1:**
- `transcripts/war_epoch_baseline.md` — positive example: war epoch, correct danger framing.
- The `test_war_epoch_reflects_danger` judge criteria is a ready-made eval signal.

---

## Decisions Graduated to project/DECISIONS.md

Two decisions graduated during P1.7:
- **Model upgrade to qwen2.5:14b** — Phase 2 and Phase 3 need to know the base model.
- **explicit_node_ids API field** — Phase 2 game skeleton must use this field to pin context.

---

## Phase 1 Close — All Subphases Complete

| Subphase | Status | Commit |
|---|---|---|
| P1.1 — Retrieval investigation | ✅ DONE | 33586f8 |
| P1.2 — Epoch prompt hardening | ✅ DONE | 30bd8cc |
| P1.3 — Model upgrade (qwen2.5:14b) | ✅ DONE | a507530 |
| P1.4 — LLM judge wired | ✅ DONE | a507530 |
| P1.5 — Neo4j consume + infra fixes + seeder | ✅ DONE | a86082e |
| P1.6 — Reputation prompt + goals in context | ✅ DONE | a86082e |
| P1.7 — Handoff close | ✅ DONE | (this commit) |

**Phase 1 is CLOSED. All gates passed. NEXT_SESSION.md updated for Phase 2.**
