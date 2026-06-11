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

## Phase 17 — Demo Foundation + Missing Expansions ✅ (2026-06-11)
**Goal:** Complete the remaining non-schema-gated items from the expansion analysis, land
KE-6 stable-id seeding (enabler for replay + scenario features), and implement the location
hierarchy approved in DEC-071. Designed for parallel execution via `/expand-parallel`.
**Sessions:** estimated 6–8 (mix of S/M/L items; KE-6 + EXP-87 are M/L, others S/M).
**Reconciliation note (2026-06-11):** all steps landed under the EXP-14/51/19 + EXP-32/87/92/95
expansion slices ("Phase 18/19" batches); the schema gates for S17.6–S17.8 were approved
(DEC-083 GOAL_TARGETS, DEC-084 emotion write-through, DEC-085/086 UNLOCKS). Checkboxes were
ticked retroactively after verifying the landed code. S17.9 remains deprioritized (no active dev).

Dependency order within the phase: **KE-6 first** (enables EXP-92, EXP-95 idempotent
re-seeding); **EXP-32 + EXP-87 can run in parallel with KE-6** (no conflict).

### Non-schema-gated (parallelizable after KE-6)

- [x] **S17.1 KE-6** — Stable-ID idempotent seeding (ISSUE-055). Add optional `id` to
  `CreateBeliefRequest`, `CreateGoalRequest`, `CreateMemoryRequest`, `CreateSecretRequest`;
  MERGE on provided ID; update all seeders. Brief: `expansion/briefs/KE-6-stable-id-seeding.md`.
  - Exit: `make demo-seed` run twice produces zero duplicate nodes. ✓
- [x] **S17.2 EXP-32** — Measured anti-hallucination eval harness. Fixture now exists at
  `evals/cases/anti_hallucination_demo.json` (41 labeled cases, all 5 demo NPCs, 3 categories).
  This session adds the runner extension that consumes the JSON format and reports grounded /
  refusal / hallucination aggregate rates. Also wire into `make eval-anti-hallucination`.
  - Exit: `make eval-anti-hallucination` reports a hallucination rate number. ✓
- [x] **S17.3 EXP-87** — Location hierarchy `PART_OF` edge (DEC-071 approved).
  `type_registry/base_edges/part_of.yaml` + `graph/location_writer.py` + `location_graph_queries`
  ancestor/descendant helpers + admin routes + demo seed wiring (`loc_city` parent node).
  Brief: `expansion/briefs/EXP-87-location-hierarchy.md`.
  - Exit: `loc_tavern -[:PART_OF]-> loc_city` exists in demo graph after `make demo-seed`. ✓
- [x] **S17.4 EXP-92** — Determinism / replay toggle (demo). Needs KE-6.
  Brief: `expansion/briefs/` (to be created). Stable IDs from KE-6 make repeated demo runs
  produce the same graph state — surfaces EXP-15/16 gossip replay in the demo.
  - Exit: `make demo-seed && make demo-run ARGS=--cached` produces identical dialogue twice. ✓
- [x] **S17.5 EXP-95** — In-window scenario picker (demo). Needs KE-6.
  Brief: `expansion/briefs/` (to be created). Unifies the arcs + free-play modes into a
  single in-window menu so the demo can switch between the village, tavern, and demo worlds.
  - Exit: demo window shows a scenario selection screen at launch. ✓

### Schema-gated (DECISIONS call needed before implementation)

- [x] **S17.6 EXP-51** — NPC GOAP goal-formation / action-selection (`GOAL_TARGETS` edge).
  ✅ Schema approved in DEC-083 (GOAL_TARGETS edge + 0–100 action priority); `engines/planning/`.
- [x] **S17.7 EXP-14** — Persistent emotion state (survive restart). ✅ Schema approved in
  DEC-084 (emotion write-through to character node; Redis deferred); `engines/emotion/`.
- [x] **S17.8 EXP-19** — Branching quests & consequence chains. ✅ Schema approved in
  DEC-085 (UNLOCKS edge) + DEC-086 (lifecycle waiver); `QuestChainResolver`.

### Deprioritized

- [ ] **S17.9 EXP-42** — Niche-engine expansions + demo integration (succession, clique,
  investigation, skill, military, treaty). Low commercial value for demo audience; keep in
  code, no active development.

---

## Phase 20 — API Exit Contract: `response_model` on all routes (BATCH5, ISSUE-052 side-effect) ✅ (2026-06-11)
**Goal:** Every route emits a typed OpenAPI schema body. Game studios generating a client from `/openapi.json` get real stubs, not empty `{}`. Closes ISSUE-052 (mypy `no-any-return` from dict returns) as a side-effect.
**Completion note (2026-06-11):** all ~125 routes now declare `response_model` (`OkEnvelope[dict|list]`; bare `action` route uses `dict[str, Any]`). `NPCStateResponse` typed via `api/response_models/`. Generic graph services kept `dict[str, Any]` per DEC-088. FA102 sweep was a no-op (codebase already has `from __future__ import annotations`). `make type` = 0; ISSUE-052 [FIXED].
**Effort:** L (120 routes, ~30 files). No runtime behaviour changes — schema + exit-validation only.
**Constraint:** 300-line file limit. If adding models pushes a route file over 300 lines, extract models into `api/response_models/<module>.py` rather than waiving. `api/schemas.py` is already near the limit — extract, do not waive.
**Notes:**
- Write S20.6's contract test (zero routes missing `response_model`, excluding `/health` + WS) **first** — it is the phase's RED and will fail with ~120 routes.
- `OkEnvelope[T]` lives in `api/route_helpers.py`. Keep the runtime `ok_response()` dict-returning path unchanged — FastAPI validates on the way out. No runtime behaviour change.
- Dynamic graph routes may use `OkEnvelope[dict[str, Any]]` where a tighter model is impractical (the registry is dynamic). Document the choice with an inline comment; no DECISIONS entry unless a reviewer flags it.
- Run the FA102 future-annotations `--fix` sweep as its own separate commit (`chore(types): add future-annotations to all src files`).

- [x] **S20.1** Envelope — add `OkEnvelope[T](BaseModel, Generic[T])` with `success: bool`, `data: T`, `meta: dict | None` to `api/route_helpers.py`; annotate `ok_response()` return type. Add `ErrEnvelope` for documented error responses.
  - Exit: `make type` still 0; `OkEnvelope` importable.
- [x] **S20.2** Typed sub-models — replace raw `dict`/`list[dict]` in `NPCStateResponse` (`character`, `relations`, `events` fields → `CharacterNode`, `RelationEdge`, `EventNode`); type `generic_node_service.upsert_node/patch_node` and `generic_edge_service.upsert_edge` against registry-validated Pydantic models instead of `dict[str, Any]`.
  - Exit: `NPCStateResponse` fields are typed Pydantic models; `make type` 0.
- [x] **S20.3** Route sweep batch A — add `response_model=OkEnvelope[X]` to: `action`, `batch`, `beliefs`, `causality`, `clock`, `debts`, `economy`, `factions`, `goals`.
  - Exit: `make check` green after each commit.
- [x] **S20.4** Route sweep batch B — `gossip_spread`, `graph`, `graph_admin`, `groups`, `interaction`, `items`, `location_graph`, `location_history`, `memories`, `pledges`.
  - Exit: `make check` green.
- [x] **S20.5** Route sweep batch C — `quest`, `quest_generation`, `rumor_trace`, `rumors`, `schedules`, `secrets`, `skills`, `system`, `traits`, `treaties`, `witnessed`. Exempt: `/health` (bare 200), WebSocket route.
  - Exit: `make check` green.
- [x] **S20.6** Verification — add test asserting zero routes are missing `response_model` (excluding `/health` + WS). Run `curl /openapi.json` spot-check; assert no route body is `{}`. Ruff FA102 `future-annotations` sweep (automated `--fix`).
  - Exit: `make check` green; OpenAPI non-empty assertion passes; ISSUE-052 closed.

---

## Phase 21 — Architectural debt: rule violations + Cypher migration (ISSUE-053, ISSUE-058) ✅ (2026-06-11, src scope; demo_game S21.6 deprioritized)
**Goal:** Drain the `scripts/rules_baseline.txt` down to zero and relocate remaining raw Cypher outside `graph/`. Both tracks touch different files and can run in parallel.
**Constraints:** After each cluster, run `make check-rules-update` to shrink the baseline. No new violations may be introduced. Each Cypher relocation needs a new `graph/<domain>_queries.py` file — no editing existing query files, add-by-new-file (OCP).
**Notes:** Work the two tracks (rule violations and Cypher migration) as separate commits — they touch different files and must not be mixed.
**Reconciliation note (2026-06-11):** S21.2, S21.3, S21.5 were found **already satisfied** against the current `rules_baseline.txt` — the baseline carries **no** R002 (print), R003 (swallow), R004 (`raise Exception`), or R007 (demo import) entries, and `engines/interaction/quest_verifier.py` has **zero** Cypher. Verified and ticked (no code change). S21.1 is scoped this session to **src/npc_engine engine+api files only** (demo_game monsters deferred). Discovery: **most R001 baseline files already carry approved 300-line waivers** and are excluded from the split set — `context_builder` (DEC-016), `tick_scheduler` (DEC-042), `quest_lifecycle_engine` (DEC-044/078/086), `quest_generation_engine` (DEC-046), `gossip_handler` (DEC-061), `chapter_engine` (DEC-062), `api_seeder` (DEC-066), `dialogue_handler` (DEC-067/081), `context_budget_enforcer` (DEC-073), `dependencies_engines` (DEC-076), `config` (DEC-077), `intent_queries` (DEC-079), plus all `demo_game/*` (DEC-029/032/034/049/074/075). The only genuinely **unwaived** src targets are `main.py` (DEC-060 grandfather explicitly says *"resolved when SEV-23 executes"* = this step), `errors.py`, and `middleware_helpers.py`. S21.4 is **blocked** pending DEC-087 approval.

- [x] **S21.1** Rule violations — file-size cluster (SEV-23), **src/ scope**: split any remaining src/npc_engine files > 300 lines that are in the baseline. DECISIONS entry required for each split boundary.
  - Exit: `make check-rules` baseline shrunken for R001. ✓
  - **Done (2026-06-11):** src/ engine+api portion complete — `main.py` split (DEC-089) and
    `middleware_helpers.py` split (DEC-090) removed from baseline; every other src `>300` file now
    carries a documented waiver (DEC-016/042/044/046/061/062/066/067/073/076/077/079/081/091).
    **Every src R001 entry is now split-or-waived.** The `demo_game/*` file-size cluster is split out
    as deprioritized **S21.6** (below) per the scope decision.
- [x] **S21.2** Rule violations — error-swallowing cluster (SEV-18): replace `except: pass` and bare `except Exception: pass` with typed re-raises or `log-and-re-raise`. `utils/errors.py` typed exceptions only.
  - Exit: R003 hits in baseline gone. ✓ (found already satisfied — 0 R003 in baseline/src, 2026-06-11)
- [x] **S21.3** Rule violations — print/Cypher-outside-graph cluster (SEV-40 + SEV-04 partial): replace `print()` with structured logger calls; move `engines/interaction/quest_verifier.py` Cypher to new `graph/quest_verification_queries.py`.
  - Exit: R004 (prints) + partial R005 (Cypher) baseline entries removed. ✓ (found already satisfied — 0 R002/R004 in src, `quest_verifier.py` has 0 Cypher, 2026-06-11)
- [x] **S21.4** Cypher migration — transaction ownership (SEV-04 / ISSUE-058): create `graph/` coordinator for engine-owned `begin_transaction`/`commit` calls in `event_handler.py`, `quest_lifecycle_engine.py`, `faction_politics_engine.py`. Write DECISIONS entry first (DEC-087) proposing the coordinator boundary; implement only after approved.
  - Exit: engine-owned transactions behind a single `graph/`-owned coordinator; `rg "begin_transaction|\.commit\("` in `src/npc_engine/engines/` returns 0 hits; baseline shrunk. ✓
  - **Done (2026-06-11):** DEC-087 approved (Option 1). New `graph/transaction_coordinator.py` `run_in_tx(session, work)` owns begin/commit/rollback. All **5** engine files (`event_handler`, `faction_politics_engine`, `quest_lifecycle_engine`, `quest_offer_service`, `quest_reward_router`) refactored to closures — zero `begin_transaction(`/`commit(` calls remain in `engines/`; R005 baseline shrunk 5 (149→144). The two residual textual `begin_transaction` hits are the `ensure_transaction_session` capability guard (`hasattr`) kept engine-side per DEC-087 Q2, not transaction ownership. Closes ISSUE-058 item (2).
- [x] **S21.5** Rule violations — demo-imports cluster (SEV-02): ensure `demo_game/` has zero imports from `src/npc_engine/`; any remaining `npc_engine` imports in demo replaced with equivalent `EngineClient` REST calls.
  - Exit: `rg "from npc_engine\|import npc_engine" demo_game/` returns 0; baseline empty. ✓ (found already satisfied — 0 R007 in baseline/demo_game, 2026-06-11)

### Deprioritized

- [ ] **S21.6** Rule violations — file-size cluster, **demo_game/ scope** (SEV-23 remainder): split the
  remaining `demo_game/*` files > 300 lines in `rules_baseline.txt` (`client.py` 1524L, `seed.py` 1265L,
  `run.py`, `run_scenes.py`, `game_controller.py`, `ui/*`, `scenarios/*`). **Deprioritized — no active
  development.** Demo code, not the licensed engine; high split risk (`make demo` breakage), low value,
  and several already carry waivers (DEC-029/032/034/049/074/075). Pick up only if the demo is being
  reworked anyway. Does not gate any feature phase.
  - Exit: `make check-rules` R001 `demo_game/*` entries split or explicitly waived.

---

## Phase 22 — Runtime correctness (ISSUE-056, ISSUE-064, ISSUE-068, ISSUE-071, ISSUE-082) ✅ (2026-06-11)
**Goal:** Fix the remaining P2 correctness issues. All items are independent and conflict-free — parallelizable.
**Completion note (2026-06-11):** all 5 steps landed; `make check` green (1937 passed, 85.65%),
`make test-demo` green (618). ISSUE-056 fixed (label filter in `graph_rag_queries.py` per DEC-093),
ISSUE-064 fixed (rerank offloaded), ISSUE-068 [FIXED] (found already resolved). ISSUE-071 grounded
via the `active_negotiation` context inject. ISSUE-082 prompt hardening shipped (`stage_b_v2.10`) but
kept OPEN — the two henryk cases need a live `make eval-llm-demo` (Ollama) run to confirm reduction.
**Notes:**
- S22.2: mirror `tests/unit/test_embedding_index_offload.py` exactly — same pattern, different class.
- S22.4: pass `NegotiationStore` as an optional constructor param (`negotiation_store: NegotiationStore | None = None`); do **not** import it at module level in `dialogue_handler.py`. The no-store path must behave identically to today — no regression for callers that don't pass it.
- S22.5: YAML-only edit; bump the `PROMPT_VERSION` constant. Do not touch other `.py` files.

- [x] **S22.1** graph_rag label filter (ISSUE-056) — add label filter to `_CYPHER_EXPAND_SEEDS`.
  Cypher relocated to `graph/graph_rag_queries.py` in Phase 21 (S21.4), so the fix landed there, not
  `retrieval/graph_rag.py`. Filter is `:Event` only (DEC-093: no `:Knowledge` label in schema; seeds
  are `KNOWS_ABOUT`→Event). Test `tests/unit/test_graph_rag_queries.py` asserts the label filter.
  - Exit: `_CYPHER_EXPAND_SEEDS` matches `(seed:Event)`, not bare `MATCH (seed)`; `make check` green. ✓
- [x] **S22.2** Reranker off event loop (ISSUE-064) — `_maybe_cross_encode` is now `async` and offloads
  `cross_encoder_reranker.rerank()` via `await asyncio.to_thread(...)`; call site in `build_serialized_context`
  awaits it. Regression test `tests/unit/test_cross_encode_offload.py` asserts rerank runs off the
  main thread (+ disabled/empty short-circuits).
  - Exit: `make check` green; test passes. ✓
- [x] **S22.3** Game-window test mock (ISSUE-068) — **found already resolved.** `GameWindow` both
  imports (`game_window.py:44`) and uses (`game_window.py:134`) `WorldStatePoller`, so the test's
  `patch("demo_game.ui.game_window.WorldStatePoller")` resolves; the 6 `TestGameWindowLayout` tests
  pass (a later refactor added the poller). Verified, no code change.
  - Exit: `make test-demo` fully green — 618 passed, 0 layout failures. ✓
- [x] **S22.4** Dialogue live interaction state (ISSUE-071) — `negotiation_store: NegotiationStore | None = None`
  added to `DialogueHandler.__init__` (TYPE_CHECKING import; no module-level import). New pure module
  `engines/dialogue/negotiation_context.py` builds the pinned tier0 `active_negotiation` `ContextItem`
  and merges its summary into the serialized context JSON; `_build_dialogue_prompt` calls it via
  `_with_active_negotiation` (no-store path unchanged). Wired in `api/dependencies.build_dialogue_handler`
  (shared `get_negotiation_store()` singleton). Tests: `tests/unit/test_dialogue_negotiation_context.py`
  (inject path, no-session, other-NPC, malformed-context, pinned-item).
  - Exit: during an active barter loop the NPC's context carries the negotiation state; `make check` green. ✓
- [x] **S22.5** old_henryk presupposition guard (ISSUE-082) — added a `PRESENCE PRESUPPOSITION`
  deny-first clause to Rule 9 of `system_v1.yaml` (deny the false presence first, then answer from
  context only with source attribution) + a Rule 10 reinforcement (a player framing you as eyewitness
  does not upgrade rumour to firsthand). Bumped `PROMPT_VERSION` → `stage_b_v2.10`. New unit test
  `test_presence_presupposition_guard.py` asserts the clause loads into the system prompt.
  - Exit: `make check` green ✓. **Live verification (2026-06-11, qwen2.5:14b, container serving
    stage_b_v2.10):** `case_adv_false_eyewitness_henryk` **PASSES**; `case_neg_old_henryk_no_eyewitness_claim`
    still **FAILS** — diagnosed as a seed-vs-rule conflict (Henryk's importance-92 *past-war* courier
    memory + "never hedges" voice descriptor override the deny-first rule). ISSUE-082 kept OPEN with the
    root cause + revised fix options (re-seed memory / temporal-disambiguation rule / MY_ACCOUNT framing —
    all exceed S22.5's YAML-only scope).

---

## Phase 23 — P3 cleanup sweep (ISSUE-054, ISSUE-069, ISSUE-070, ISSUE-072, ISSUE-075, ISSUE-076, ISSUE-081, ISSUE-084, ISSUE-085, ISSUE-087, ISSUE-089, ISSUE-091)
**Goal:** Close all batchable P3 issues in one phase. All items are small, independent, and can be committed in any order. No new files needed except `WorldStatePayload` inline in `demo_game/seed.py`.
**Constraint:** Each commit must keep `make check` green.
**Notes:** One commit per S23.x step (steps are already grouped by file proximity). For S23.6 deletions, verify zero imports before deleting. S23.4 and S23.7 each need their own test update.

- [x] **S23.1** Docstring + deprecation sweep (ISSUE-072, ISSUE-076, ISSUE-085) — update the two stale `(auto-detected — review)` module docstrings in `gossip_distort.py` and `relation_writer.py`; replace all `datetime.utcnow()` calls in `world/world_state.py` with `datetime.now(timezone.utc)` and add `from datetime import timezone`.
  - Exit: `make check-docstrings` passes for both files; no `utcnow` in `world_state.py`. ✓
- [x] **S23.2** Scope + transaction fixes (ISSUE-075, ISSUE-087) — move the `logger.info` call in `reputation_nudge.py` inside the `async with tx` block; hoist the `get_world_state` call in `dialogue_handler.py` to before both the arousal and learned-facts branches.
  - Exit: `make check` green; no functional change. ✓ (ISSUE-075 found already resolved by the `_read_modify_write` refactor; ISSUE-087 hoisted via `_maybe_load_world_state`, single conditional fetch preserves common-path zero-read.)
- [x] **S23.3** Error handling (ISSUE-069, ISSUE-070) — broaden `except EngineClientError` in `action_workers._get_current_tick` to `except Exception` with structured logging; confirm `subgraph_retriever`'s `relation:player` priority is lower than EXP-11's (88) so dedup is deterministic — add a comment if so, rename the key if not.
  - Exit: `make test-demo` green. ✓ (priorities are 95 vs 88 — distinct, so merge_context dedup is deterministic; documented, no rename.)
- [x] **S23.4** Write-belief dedup (ISSUE-089) — replace `str(uuid.uuid4())` in `knowledge_writer.write_belief` with a stable `hashlib.sha256(f"{npc_id}:{content}".encode()).hexdigest()[:16]` so MERGE deduplicates repeated facts. Add unit test asserting two identical fact writes produce one node.
  - Exit: `make check` green; duplicate belief test passes. ✓
- [x] **S23.5** WorldStatePayload model (ISSUE-084) — define `WorldStatePayload(BaseModel)` inline in `demo_game/seed.py` (4 fields); return it from `build_world_state_payload`; update the two callers.
  - Exit: `rg "build_world_state_payload" demo_game/seed.py` shows typed return; `make test-demo` green. ✓ (call site passes `.model_dump()` to the generic `_seed_node`; test_seed + test_sev13 updated to attribute access.)
- [x] **S23.6** Dead code + lazy import (ISSUE-054, ISSUE-091) — delete `src/npc_engine/retrieval/token_budget_enforcer.py` and its test `tests/unit/test_context_pipeline.py` (confirm zero imports first); make the `game_window` import in `demo_game/__init__.py` lazy (inside `_dispatch` body only).
  - Exit: `rg "token_budget_enforcer" src/` returns 0; `make check` green; `make test-demo` green. ✓
- [ ] **S23.7** Archetype in fallback (ISSUE-081) — thread the NPC archetype from `request.npc_id`→profile into `execute_with_degradation` and `DialogueLLMClient._load_fallback_dialogue` so the archetype-keyed fallback line is used instead of hardcoded `"default"`. Update unit test for the degradation path.
  - Exit: a non-default-archetype NPC in degradation mode returns its archetype line; `make check` green.

---

## Phase 24 — Eval fixture completion (ISSUE-090)
**Goal:** Wire the `learned_from_player` category into the anti-hallucination runner so the stub eval case is no longer silently skipped.
**Dependency:** EXP-53 slice-3 (contradiction/dedup handling) should land before or concurrently.
**Notes:** Small — a single commit.

- [ ] **S24.1** Runner support for `learned_from_player` — add `learned_from_player` category handling to `evals/anti_hallucination_runner.py`: treat like `grounded` but add a pre-flight check that `write_belief()` has persisted the fact for the NPC before running the case. Update `ah_demo_stub_mira_player_taught` to remove `stub` from the ID once EXP-53 slice-3 is confirmed. Add unit test for the new category path.
  - Exit: `make eval-anti-hallucination` no longer skips the player-taught case; `make check` green.

---

## Phase 25 — Voice polish: ECHO_GUARD A/B (ISSUE-083) + prompt-only (no .py)
**Goal:** Determine whether ECHO_GUARD hurts voice colour and tune the prompt accordingly. YAML-only — no Python changes.
**Notes:** Single commit. YAML-only — if you find yourself editing a `.py` file, stop and reconsider.

- [ ] **S25.1** ECHO_GUARD A/B (ISSUE-083) — run `make eval-llm-demo` twice: once with the current ECHO_GUARD clause in `system_v1.yaml` and once with it softened to scope only to explicit player-presupposition patterns. Record pass rates for `case_voice_captain_sorn_001` and `case_voice_mira_innkeeper_001` in both runs. If softened version recovers both cases without regressing anti-hallucination scores, commit the softened wording and bump `PROMPT_VERSION`.
  - Exit: both voice cases pass; anti-hallucination score does not drop; or decision to accept the current trade-off is documented in DECISIONS.md.

---

## Phase 26 — Temporal knowledge framing: stop NPCs conflating past memory with current events (ISSUE-093, closes ISSUE-082) ✅ (2026-06-11)
**Goal:** Give NPC knowledge a timeline. Today everything an NPC knows is a flat, present-tense,
authoritative bag, so a long-past first-hand memory and a current 2-hop rumour are indistinguishable —
NPCs recount old experiences as the current situation and accept false-eyewitness presuppositions.
**Root cause (3 layers):** (1) `Memory`/`Event` carry only record-time, no event-time/era; the seeder
stamps every memory at "now". (2) `subgraph_retriever._flatten_event_row` drops `knowledge_state` when a
`distorted_summary` exists, and `_extract_personal_accounts` renders every distorted summary as an
authoritative verbatim `MY_ACCOUNT_N` — a rumour becomes firsthand (Rule 5 vs Rule 10 contradiction).
(3) the prompt has no past-vs-present axis.
**Constraint:** Preserve the gossip-telephone feature — NPCs must still *confidently repeat distorted
rumour content*; we only strip the *firsthand framing*, not the distortion. Schema steps gated on DEC-094.
**Notes:** Phases A/B/D need no approval. C is a graph-schema change → DEC-094 must be approved first.
Each step bumps `PROMPT_VERSION` when it touches the prompt; one commit per step.

- [x] **S26.1 (A)** Rumour vs firsthand channel split — restore `knowledge_state` in
  `subgraph_retriever._flatten_event_row` (keep `distorted_summary` AND `knowledge_state`); in
  `prompt_builder._extract_personal_accounts`, route `knowledge_state=="rumor"` distorted summaries to a
  new `HEARSAY_N=` channel and the rest to `MY_ACCOUNT_N=`. Add Rule 5b to `system_v1.yaml`: HEARSAY lines
  keep their named details (gossip distortion preserved) but MUST be attributed ("word reached me", "they
  say") and NEVER claimed as firsthand/eyewitness. Bump `PROMPT_VERSION`.
  - Exit: a rumour-state event yields a HEARSAY line, not MY_ACCOUNT; gossip-spread unit tests green; `make check` green.
- [x] **S26.2 (B)** Memory temporal framing — compute each memory's age from `created_at_game_time` vs the
  current `world` game-time (via `world.time_utils.total_days`) and surface a coarse `age` hint
  ("recent"/"long_past") on serialized `npc.memories`; add a Rule to `system_v1.yaml`: `npc.memories` are
  recollections of *past* events — never present a past experience as the current situation, and never
  assume a past event is the same as one the player asks about now. Bump `PROMPT_VERSION`.
  - Exit: serialized memories carry an `age` hint; prompt rule present; `make check` green.
- [x] **S26.3 (C) [SCHEMA — DEC-094 APPROVED]** Event-time model — add `occurred_at_game_time`
  (event time, distinct from `created_at_game_time`) + `is_historical: bool` to `Memory` (and `Event`)
  type-registry nodes + write path; update `demo_game/seed.py` so Henryk's "ran dispatches in the last war"
  memory is `is_historical=true` and is **removed from** the current-war `KNOWS_ABOUT` distorted_summary
  (split the conflated string). Make Phase B's `age` read the real event-time when present.
  - Exit: Henryk's past-war memory is tagged historical and absent from the current rumour string; `make check` green.
- [x] **S26.4 (D)** Temporal-conflation evals — added `case_neg_old_henryk_past_war_not_current.yaml`
  (`affirms_judge` — fails if he fuses his historical service with the current war or reports the
  front firsthand). Live verification (qwen2.5:14b, stage_b_v2.12 + Phase C seed):
  `case_neg_old_henryk_no_eyewitness_claim` **PASS**, `case_adv_false_eyewitness_henryk` **PASS**,
  `case_neg_old_henryk_past_war_not_current` **PASS**, `case_pos_old_henryk_war_rumor_tokens` **PASS**
  (gossip tokens preserved). Earlier A+B regression sweep: 6/6 (both sides of the split, no over-hedge).
  - Exit: new case defined + passes live; ISSUE-082 + ISSUE-093 [FIXED]. ✓

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
| 12 | 2026-06-11 | Phase 17 reconcile | Verified all S17.1–S17.8 landed (EXP-14/32/51/87/92/95 + EXP-19 slices); schema gates approved DEC-083/084/085/086; ticked checkboxes + cleared stale 🔶 notes. S17.9 stays deprioritized | Phase 17 marked ✅; next target is Phase 20 |
| 13 | 2026-06-11 | S20.1–S20.2 | `OkEnvelope[T]` + `ErrEnvelope` in `route_helpers.py` (`test_route_helpers.py`); `NPCStateResponse` typed via new `api/response_models/npc_state.py` (CharacterNode/RelationEdge/EventNode); DEC-088 (generic services stay dynamic) | Envelope importable; NPCStateResponse typed; `make type` 0 |
| 14 | 2026-06-11 | S20.3–S20.5 | `response_model` swept across all ~125 routes (batches A/B/C + locations/reputation); `OkEnvelope[dict\|list]`, bare `action` route `dict[str, Any]` | Every route declares a typed body; gate green each batch |
| 15 | 2026-06-11 | S20.6 | `test_route_response_model_contract.py` (zero routes missing `response_model`; non-empty OpenAPI bodies; OkEnvelope component present); FA102 sweep no-op; ISSUE-052 [FIXED] | Phase 20 ✅; 1924 tests green, mypy 0 |
| 16 | 2026-06-11 | S21.2/S21.3/S21.5 | Reconcile: verified the current `rules_baseline.txt` carries 0 R002/R003/R004/R007 entries and `quest_verifier.py` has 0 Cypher; ticked the three already-satisfied steps (no code change) | S21.2/S21.3/S21.5 ✅ (found satisfied); S21.1 + S21.4 remain |
| 17 | 2026-06-11 | S21.1 (main.py) | Split `main.py` 400→217L into `api/router_registry.py` (`register_routers`, public/admin helpers) + `api/exception_handlers.py` (4 handlers + `register_exception_handlers`); `lifespan` kept in `main` (test monkeypatch surface); DEC-089 resolves DEC-060; `test_error_envelope_sev33` import updated; baseline 152→150 | R001 main.py removed; `make check` green (1924 passed, 85.56%) |
| 18 | 2026-06-11 | S21.1 (auth+errors) | Split `middleware_helpers.py` 333→229L: observability helpers → new `auth/request_observability.py` (118L), `middleware.py` import updated (DEC-090); `errors.py` (329L) kept with documented waiver (DEC-091, flat exception catalog). src/ R001 cluster now fully split-or-waived; `demo_game/*` deferred | baseline 150→149; `make check` green (1924 passed, 85.57%) |
| 19 | 2026-06-11 | S21.4 (proposal) | Wrote DEC-087 🔶 PROPOSED (graph/ transaction coordinator); inspected the 5 engine files with engine-owned `begin_transaction`/`commit`; recommended callback unit-of-work boundary. **No code change — blocked on human approval** | S21.4 gated; awaiting approval |
| 20 | 2026-06-11 | S21.4 | DEC-087 approved (Option 1). New `graph/transaction_coordinator.py` `run_in_tx` (TDD, `test_transaction_coordinator.py`); migrated all 5 engines to closures; `faction_politics` test fake tx gained `commit` (LSP); R005 baseline 149→144 | S21.4 ✅; engine tx ownership gone; ISSUE-058(2) closed; 1926 passed, 85.59% |
| 21 | 2026-06-11 | S21.4 follow-up | Relocated world-state DB access `world/world_reader.py`+`world/world_writer.py` → `graph/world_state_reader.py`+`graph/world_state_writer.py` (DEC-092); repointed 13 callers; deleted old files + renamed test; refactored `upsert_world_state` under 40L via shared param/record helpers; R005 baseline 144→141 | **R005 baseline empty**; ISSUE-058 [FIXED]; 1926 passed, 85.59% |
| 22 | 2026-06-11 | S22.1 | `:Event` label filter on `_CYPHER_EXPAND_SEEDS` in `graph/graph_rag_queries.py` (Cypher relocated there in S21.4; DEC-093 — no `:Knowledge` label); `test_graph_rag_queries.py` | Full-node scan removed; ISSUE-056 fixed; 1928 passed |
| 23 | 2026-06-11 | S22.2 | `_maybe_cross_encode` → async, offloads rerank via `asyncio.to_thread`; call site awaits; `test_cross_encode_offload.py` (thread-name spy) | Reranker off the event loop; ISSUE-064 fixed; 1931 passed |
| 24 | 2026-06-11 | S22.3 | Reconcile — `GameWindow` imports+uses `WorldStatePoller`; 6 `TestGameWindowLayout` tests already green (no code change); ISSUE-068 [FIXED] | `make test-demo` 618 passed |
| 25 | 2026-06-11 | S22.4 | New `engines/dialogue/negotiation_context.py` (pinned tier0 `active_negotiation` inject); optional `negotiation_store` on `DialogueHandler` (TYPE_CHECKING, no-store path unchanged); wired in `dependencies`; `test_dialogue_negotiation_context.py` | NPC dialogue grounded in live barter state; ISSUE-071 addressed; 1936 passed |
| 26 | 2026-06-11 | S22.5 | `PRESENCE PRESUPPOSITION` deny-first clause in `system_v1.yaml` Rule 9 + Rule 10 reinforcement; `PROMPT_VERSION`→`stage_b_v2.10`; `test_presence_presupposition_guard.py` | Prompt hardened; ISSUE-082 OPEN (live eval verification pending); 1937 passed |
| 27 | 2026-06-11 | S22.5 verify | Live eval (container rebuilt on v2.10): `case_adv` PASS, `case_neg` FAIL — diagnosed as a seed-vs-rule conflict (Henryk's importance-92 past-war memory), not prompt weakness → ISSUE-093 + Phase 26 + DEC-094 | S22.5 1/2 live; deeper issue scoped |
| 28 | 2026-06-11 | S26.1 (A) | `_flatten_event_row` keeps `knowledge_state`; `_extract_personal_accounts` splits MY_ACCOUNT vs HEARSAY by rumour state; Rule 5b; `PROMPT_VERSION`→`stage_b_v2.11`; tests rewritten | Rumour no longer recast firsthand; gossip content kept; 1940 passed |
| 29 | 2026-06-11 | S26.2 (B) | `retrieval/memory_temporal.py` (`annotate_memory_ages`, recent|long_past); `context_builder` threads game-time into memories; Rule 15 (memories are past); `PROMPT_VERSION`→`stage_b_v2.12` | Memories framed as past recollections; 1947 passed |
| 30 | 2026-06-11 | S26.1+B verify | Rebuilt container (v2.12); **both** henryk eyewitness cases PASS live; 6/6 regression sweep (gossip tokens kept, firsthand confident, no over-hedge) — A+B fix the bug without schema | A+B verified clean; Phase C → hardening |
| 31 | 2026-06-11 | S26.3 (C) | DEC-094 APPROVED; `occurred_at_game_time` + `is_historical` on Memory (registry+Cypher+service+request+client, all optional); seed split Henryk past-war memory (`is_historical`) from current-war hearsay rumour | Event-time model landed; 1952 passed, demo 619 |
| 32 | 2026-06-11 | S26.4 (D) | `case_neg_old_henryk_past_war_not_current.yaml` (affirms_judge); live with Phase C seed: 4/4 henryk cases PASS (incl. gossip-token case); Phase 26 ✅ | ISSUE-082 + ISSUE-093 [FIXED]; conflation resolved |
