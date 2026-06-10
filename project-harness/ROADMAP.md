# NPCSystem — Engine Roadmap (Phase 14 →)

**Status:** Phases 0–13 complete. This file is the **forward** roadmap only.

- Full history (Phases 0–13, engine audit, session log through S13.3) →
  `project-harness/proposals/archive/ROADMAP_through_phase13_2026-06-03.md`.
- The 2026-06-01 Munich hackathon roadmap → `project-harness/archive/ROADMAP_munich_demo_2026-06-06.md`.

**Sprint sequence:** the 2026-06-03 codebase review (BLOCK, 43 findings) means the
**review-remediation backlog likely precedes feature work** — see "Remediation backlog" below.
Default feature order if remediation is sequenced separately: **14 → 15 → 16**; Phase 17 (SDKs)
is a deferred commercial milestone.

---

## ⚠️ Remediation backlog (from the 2026-06-03 audit)

The audit returned **BLOCK**: 2 CRITICAL + 16 HIGH + 16 MEDIUM + 9 LOW. The actionable specs live in
`project-harness/review-fixes/` (FIX-SEV-01…18, organized into work Blocks A–F with a dependency-ordered
critical path in `review-fixes/INDEX.md`); the synthesis is `project-harness/REVIEW_FINDINGS.md`.

**This backlog is not yet phased.** Headline items that gate the product story:

- **SEV-01 (CRITICAL):** anti-hallucination guarantee unmeasured (matchers pass on empty/fallback/
  synonym/refusal; live eval 27/31). The moat is asserted, not proven.
- **SEV-02 (CRITICAL):** `demo_game` imports `npc_engine` internals — not a standalone client.
- **SEV-15/25 (HIGH):** `make lint` (38 ruff) + `make type` (254 mypy) red, not in CI.
- **SEV-04/03/14/12/11 (HIGH):** layer erosion, prompt-injection surface, `dict[Any,Any]` API boundary,
  no multi-tenant isolation, game cannot be won/lost.

**Decision owed (next session):** phase the remediation backlog vs. the feature phases below before building.

---

## Phase 14 — Proactive NPC-Initiated Dialogue ✅
**Goal:** NPCs open conversations on their own — the autonomous world feels agentic, not reactive.
**Sessions:** 4 completed (2026-06-09)
**Leverages:** Phase 1 tick driver + dialogue engine + S6.4 WS streaming.
**Note:** `agenda_engine.py` only resolves *political* agendas (vote tally → passed/failed). It does
**not** form conversational intent — S14.1 is net-new logic, not a wiring job.

- [x] **S14.1** Intent-formation tick step — `engines/agenda/conversation_intent_service.py` +
  `intent_formation_engine.py`: scores NPC need thresholds / unresolved goals / witnessed events;
  `graph/intent_queries.py` holds all Cypher. (DEC-079: `intent_queries.py` accepted over 300L.)
  - Exit: a hungry/threatened NPC produces a queued intent under autopilot. ✓
- [x] **S14.2** Intent queue + bounded backpressure — `graph/intent_queue_writer.py` +
  `intent_queue_reader.py`; per-NPC and global caps via `config.py`; `PendingIntent` node in
  `type_registry/base_nodes/pending_intent.yaml`.
  - Exit: intents survive a tick and never grow unbounded. ✓
- [x] **S14.3** Delivery channel — `GET /v1/dialogue/pending` poll endpoint in `api/routes/dialogue.py`;
  `EngineClient.get_pending_intents()` in `demo_game/client.py`.
  - Exit: the client receives an unsolicited NPC line. ✓
- [x] **S14.4** Demo integration — `demo_game/intent_ui.py` bubble overlay; `npc_initiative_poller.py`
  background thread; wired into `demo_game/ui/game_window.py`.
  - Exit: stand still in the demo → an NPC initiates a conversation. ✓

## Phase 15 — Retrieval-Quality Evals ✅
**Goal:** Prove the embedding/rerank stack retrieves the *right* memories, not just that tone is right.
**Sessions:** 3 completed (2026-06-09)
**Leverages:** existing `embedding_index`, `cross_encoder_reranker`, `subgraph_retriever`,
`context_relevance_engine`, `context_scoring` — large stack, but only tone is currently evaluated.
**Tie-in:** overlaps SEV-01 (proving the moat) — sequence with the remediation backlog.

- [x] **S15.1** Retrieval-inspection surface — `GET /v1/debug/retrieval?npc_id&query` in
  `api/routes/debug_retrieval.py`; returns `DebugRetrievalResponse` with `context_items` +
  `total_tokens` (graph_admin scope).
  - Exit: endpoint returns deterministic ranked IDs for a seeded query. ✓
- [x] **S15.2** Precision matcher + cases — `evals/retrieval_runner.py` + `evals/retrieval_matchers.py`
  (`precision_at_k`, `recall_at_k`, `mrr` as pure functions); 20 labeled cases in
  `evals/cases/retrieval_demo.json`; `make eval-retrieval` target; `tests/unit/test_retrieval_eval.py`.
  - Exit: `make eval-retrieval` reports precision@k. ✓
- [x] **S15.3** Headline retrieval metric — `evals/retrieval_summary.py` (`RetrievalSummary` dataclass +
  `summarize_retrieval` + format helpers); `evals/retrieval_runner.py` prints headline block;
  `evals/report.py` gains optional `retrieval_summary` section; `make eval-combined` target;
  `tests/unit/test_retrieval_summary.py`.
  - Exit: a one-command run prints retrieval precision. ✓

## Phase 16 — Content Moderation / Rating Guardrails ✅
**Goal:** Configurable per-world content ceiling (ESRB/PEGI) — a buyer compliance checkbox.
**Sessions:** 3 completed (2026-06-10)
**Leverages:** the S0.1 input chokepoint (`MAX_PLAYER_MESSAGE_CHARS` + injection guard).

- [x] **S16.1** Config + schema — `CONTENT_RATING` setting (`everyone|teen|mature`, `Literal`) +
  `ContentRatingResolver` service; `services/` package created; DEC-080 (per-world override deferred).
  - Exit: rating is resolvable per world. ✓
- [x] **S16.2** Input moderation — `InputModerationService` with per-rating blocklist (regex, O(1) hot
  path); `ContentRatingViolationError` in `utils/errors.py`; 422 handler in `main.py`; wired into
  `DialogueHandler` and `dependencies.py`.
  - Exit: over-ceiling input rejected with 422. ✓
- [x] **S16.3** Output moderation — `content_ceiling_v1.yaml` prompt rule; `build_system_prompt()`
  gains `content_rating` param; `OutputModerationService` post-generation check with canned fallback;
  3 eval cases in `evals/cases/moderation_everyone_*.yaml`; DEC-081 (dialogue_handler.py 300-line waiver).
  - Exit: mature content suppressed under `everyone`; eval cases prove it. ✓

## Phase 17 — Demo Foundation + Missing Expansions
**Goal:** Complete the remaining non-schema-gated items from the expansion analysis, land
KE-6 stable-id seeding (enabler for replay + scenario features), and implement the location
hierarchy approved in DEC-071. Designed for parallel execution via `/expand-parallel`.
**Sessions:** estimated 6–8 (mix of S/M/L items; KE-6 + EXP-87 are M/L, others S/M).

Dependency order within the phase: **KE-6 first** (enables EXP-92, EXP-95 idempotent
re-seeding); **EXP-32 + EXP-87 can run in parallel with KE-6** (no conflict).

### Non-schema-gated (parallelizable after KE-6)

- [ ] **S17.1 KE-6** — Stable-ID idempotent seeding (ISSUE-055). Add optional `id` to
  `CreateBeliefRequest`, `CreateGoalRequest`, `CreateMemoryRequest`, `CreateSecretRequest`;
  MERGE on provided ID; update all seeders. Brief: `expansion/briefs/KE-6-stable-id-seeding.md`.
  - Exit: `make demo-seed` run twice produces zero duplicate nodes. ✓
- [ ] **S17.2 EXP-32** — Measured anti-hallucination eval harness. Fixture now exists at
  `evals/cases/anti_hallucination_demo.json` (41 labeled cases, all 5 demo NPCs, 3 categories).
  This session adds the runner extension that consumes the JSON format and reports grounded /
  refusal / hallucination aggregate rates. Also wire into `make eval-anti-hallucination`.
  - Exit: `make eval-anti-hallucination` reports a hallucination rate number. ✓
- [ ] **S17.3 EXP-87** — Location hierarchy `PART_OF` edge (DEC-071 approved).
  `type_registry/base_edges/part_of.yaml` + `graph/location_writer.py` + `location_graph_queries`
  ancestor/descendant helpers + admin routes + demo seed wiring (`loc_city` parent node).
  Brief: `expansion/briefs/EXP-87-location-hierarchy.md`.
  - Exit: `loc_tavern -[:PART_OF]-> loc_city` exists in demo graph after `make demo-seed`. ✓
- [ ] **S17.4 EXP-92** — Determinism / replay toggle (demo). Needs KE-6.
  Brief: `expansion/briefs/` (to be created). Stable IDs from KE-6 make repeated demo runs
  produce the same graph state — surfaces EXP-15/16 gossip replay in the demo.
  - Exit: `make demo-seed && make demo-run ARGS=--cached` produces identical dialogue twice. ✓
- [ ] **S17.5 EXP-95** — In-window scenario picker (demo). Needs KE-6.
  Brief: `expansion/briefs/` (to be created). Unifies the arcs + free-play modes into a
  single in-window menu so the demo can switch between the village, tavern, and demo worlds.
  - Exit: demo window shows a scenario selection screen at launch. ✓

### Schema-gated (DECISIONS call needed before implementation)

- [ ] **S17.6 EXP-51** — NPC GOAP goal-formation / action-selection (`GOAL_TARGETS` edge).
  🔶 Needs a DECISIONS call for the new edge type and precedence rules. Deferred until
  human approves the schema.
- [ ] **S17.7 EXP-14** — Persistent emotion state (survive restart). 🔶 Needs emotion
  node/field schema change. Deferred.
- [ ] **S17.8 EXP-19** — Branching quests & consequence chains. 🔶 Schema-gated. Deferred.

### Deprioritized

- [ ] **S17.9 EXP-42** — Niche-engine expansions + demo integration (succession, clique,
  investigation, skill, military, treaty). Low commercial value for demo audience; keep in
  code, no active development.

---

## Phase X — Engine SDKs (Unity / Unreal) — DEFERRED COMMERCIAL MILESTONE
**Goal:** Drop-in plugins wrapping the REST/WS API — highest commercial ROI.
**Sessions:** 8+ (its own milestone, not a sprint task). Own-game milestone (Phase 7) is complete, so
this is now unblocked, but sequenced after the sprint above and after OpenAPI contract is frozen.

- [ ] **SX.1** OpenAPI contract freeze + versioned client spec.
- [ ] **SX.2** Unity C# package (REST + WS, auth, models).
- [ ] **SX.3** Unreal plugin (parity).
- [ ] **SX.4** Sample integration scene per engine + docs.

---

## Engine Scope Decisions (reference)

| Engine | Status | Decision |
|--------|--------|----------|
| gossip, emotion, need, mood, routine, agenda | works, ticks | Showcased (Phases 1, 6) |
| quest_generation, quest (lifecycle) | works | Showcased (Phases 2–3) |
| memory_consolidation | works | Showcased (S6.3 — headline feature) |
| chapter, story_pacing | works | Promoted to gameplay (Phase 7) |
| faction_politics, oath, treaty | complete | Completed + showcased (S2.3, S2.4, S6.2) |
| military | implemented | Implemented S6.5 (ISSUE-031) |
| reputation + gossip | works | Productized (Phase 8 networked reputation) |
| secrets, leverage, pledges, beliefs | works | One consequence surfaced (S6.2) |
| succession, clique | works, niche | Graveyard — kept in code |
| investigation, skill | works, niche | Graveyard — out of scope |

---

## Testing Strategy (forward)

`make test` + `make test-demo` green before every merge. New retrieval/moderation work ships with tests.
`make check` (lint + check-rules + check-layers + check-docstrings + type + test-cov) is the canonical
health gate and is green as of Phase 16 completion (1837 passed, 22 skipped, 98%+ coverage).

---

## Session Log (Phase 14 →)

| # | Date | Phase | What was done | Exit state |
|---|------|-------|---------------|------------|
| — | — | — | (Phases 0–13 log archived in `proposals/archive/ROADMAP_through_phase13_2026-06-03.md`) | — |
| 1 | 2026-06-09 | S14.1 | `conversation_intent_service.py` + `intent_formation_engine.py`; `intent_queries.py` (Cypher); unit tests `test_conversation_intent_service.py` | Intent-formation tick produces queued PendingIntent nodes |
| 2 | 2026-06-09 | S14.2 | `intent_queue_writer.py` + `intent_queue_reader.py`; `pending_intent.yaml` type node; per-NPC + global caps in config; unit tests | Intent queue survives tick; bounded by config |
| 3 | 2026-06-09 | S14.3 | `GET /v1/dialogue/pending` in `api/routes/dialogue.py`; `EngineClient.get_pending_intents()` in `demo_game/client.py`; unit test `test_dialogue_pending_route.py` | Client poll receives unsolicited NPC intent |
| 4 | 2026-06-09 | S14.4 | `demo_game/intent_ui.py` bubble overlay; `npc_initiative_poller.py` background thread; wired into `ui/game_window.py` | Stand still in demo → NPC hails player |
| 5 | 2026-06-09 | S15.1 | `api/routes/debug_retrieval.py` — `GET /v1/debug/retrieval`; `DebugRetrievalResponse` schema | Endpoint returns ranked context-item IDs deterministically |
| 6 | 2026-06-09 | S15.2 | `evals/retrieval_runner.py` + `evals/retrieval_matchers.py`; 20 labeled cases in `evals/cases/retrieval_demo.json`; `make eval-retrieval`; `tests/unit/test_retrieval_eval.py` | `make eval-retrieval` reports P@k / R@k / MRR |
| 7 | 2026-06-09 | S15.3 | `evals/retrieval_summary.py` (`RetrievalSummary` + helpers); `eval-combined` Makefile target; `evals/report.py` optional retrieval section; `tests/unit/test_retrieval_summary.py` | One-command run prints both headline metrics |
| 8 | 2026-06-10 | S16.1 | `ContentRating` Literal + `CONTENT_RATING` setting; `services/` package; `ContentRatingResolver`; `get_content_rating_resolver()` factory; DEC-080 | Rating resolvable per deployment |
| 9 | 2026-06-10 | S16.2 | `ContentRatingViolationError`; `InputModerationService` (per-rating blocklist + regex); 422 handler in `main.py`; wired into `DialogueHandler` + `dependencies.py` | Over-ceiling input rejected with 422 |
| 10 | 2026-06-10 | S16.3 | `content_ceiling_v1.yaml`; `build_system_prompt(content_rating=)`; `OutputModerationService`; canned fallback on violation; 3 eval cases; `_build_llm_client` + `_apply_output_ceiling` helpers; DEC-081 | NPC output capped under `everyone`; `make check` green (1837 passed) |
| 11 | 2026-06-10 | Phase 17 planning | `evals/cases/anti_hallucination_demo.json` (41 labeled cases, EXP-32 fixture); `expansion/briefs/KE-6-stable-id-seeding.md`; `expansion/briefs/EXP-87-location-hierarchy.md`; ROADMAP Phase 17 + Phase X restructure; EXPANSION_INDEX Phase 17 items | Phase 17 scoped and ready for `/expand-parallel`; EXP-32 unblocked |
