# Decisions Log

Non-obvious architectural choices. Each entry explains what was decided and why,
so future maintainers can judge edge cases without re-deriving the rationale.

## DEC-076: `dependencies_engines.py` accepted at 333 lines (300-line exception)
**Date:** 2026-06-09
**Context:** EXP-10 s2 and EXP-52 s2 added `get_proactive_dialogue_engine()`, `get_reputation_engine()`,
`_CharacterReaderWrapper`, and corresponding wiring in `get_tick_scheduler()`. The file was 243 lines
before; it is now 333.
**Options considered:**
  1. Split into `dependencies_engines_advanced.py` — would create two composition roots with unclear
     ownership boundary; `get_tick_scheduler()` must import from both, defeating the split.
  2. Accept with this entry.
**Decision:** Option 2. This is the sole composition root for engine singletons (DEC-042 rationale).
Every new engine that wires into the scheduler must touch this file. Splitting it creates indirection
without real encapsulation. Do not grow past 400 lines without creating a per-engine submodule pattern.

## DEC-077: `config.py` accepted at 309 lines (300-line exception)
**Date:** 2026-06-09
**Context:** EXP-53 added `KNOWLEDGE_LEARNING_ENABLED: bool = False` to `Settings`. The file was just
at the limit before; it is now 9 lines over.
**Options considered:**
  1. Extract domain-specific flags into sub-Settings classes — changes the import path for all callers;
     high disruption for 9 lines.
  2. Accept with this entry.
**Decision:** Option 2. Config is a flat-settings file by convention; splitting it would require
updating every `get_settings()` call site. Do not add more than ~5 new flags before refactoring.

## DEC-075: quest_trade_controller.py accepted at 312 lines (300-line exception)
**Date:** 2026-06-06
**Context:** `demo_game/quest_trade_controller.py` grew to 312 lines when `fix(demo): substitute empty item_type in confirm-trade` (ISSUE-067) added input-sanitization helpers. The file handles quest + trade controller logic for the demo layer.
**Options considered:**
  1. Extract trade sanitization helpers to `quest_trade_sanitizer.py` — the 3 helper functions are only ~20 lines combined; creating a peer module for them adds indirection without real encapsulation.
  2. Accept the overrun with this entry.
**Decision:** Option 2. The overrun is small (12 lines) and the helpers are cohesive with the controller. No further growth without extracting either the trade or quest side into a dedicated controller.
**Limit:** Do not grow this file further. If new trade or quest demo logic is added, extract to `demo_game/trade_controller.py` and `demo_game/quest_controller.py`.

## DEC-073: context_budget_enforcer.py accepted at 323 lines (300-line exception)
**Date:** 2026-06-05
**Context:** EXP-30 added `_fit_tier_a_pinned_pool` (38 lines) to replace the hard-raise
tier-A overflow path. The file was ~290 lines before; it is now 323.
**Options considered:**
  1. Extract `_fit_tier_a_pinned_pool` to a separate `context_tier_a_policy.py` (saves 38 lines here; adds a single-function module with a 12-param signature).
  2. Accept the overrun with this DECISIONS entry and a comment at the module top.
**Decision:** Option 2. `context_budget_enforcer.py` is a cohesive enforcement module; splitting off one policy function into a peer module adds indirection with no encapsulation gain. 323 lines is close to the 300 limit and does not warrant a structural split.
**Limit:** Do not grow this file further without splitting. If new tier policies are added, extract the policy functions first.

## DEC-074: game_window.py accepted at 350 lines (pre-existing 300-line exception)
**Date:** 2026-06-05
**Context:** `demo_game/ui/game_window.py` was already ~327 lines before EXP-80 (a pre-existing condition, no prior DECISIONS entry). EXP-80 added 23 lines (sandbox toggle + status line + DI param). The file is now 350 lines.
**Options considered:**
  1. Extract sandbox-related methods into a `GameWindowSandboxMixin` — artificial; the toggle is 4 lines.
  2. Split into `game_window_input.py` + `game_window_render.py` — possible but would split a single coherent game loop across files, increasing coupling.
  3. Accept the overrun (demo file, cohesive single class).
**Decision:** Option 3. `GameWindow` is a single pygame window class; splitting it is artificial. No further growth should be allowed without a real extraction (e.g. a dedicated `RenderLayer`).
**Limit:** Do not grow this file further without extracting a cohesive subsystem (e.g. `demo_game/ui/poller_registry.py` for the 9 pollers).

Rules:
- Append-only. Never delete entries.
- Monotonic DEC-NNN IDs. Never reuse.
- Context, options considered, decision, why. No essays.

**Canonical location:** This file lives at `project-harness/DECISIONS.md`. Never create or edit a root-level copy.

---

## DEC-057: `fill_to_budget` is the canonical token-budget enforcer; Tier0+TierA are non-droppable
**Date:** 2026-06-03
**Context:** SEV-07 — two enforcers existed: `context_budget_enforcer.fill_to_budget` (wired into `context_builder`, but it silently dropped mandatory Tier-A items when budget was tight) and `token_budget_enforcer.enforce_budget` (not wired; also dropped Tier-A). The strict rule requires raising `TokenBudgetExceededError` when Tier0+TierA alone exceed the budget — only Tier B/C may be trimmed.
**Options considered:**
- (A) Fix `fill_to_budget` to raise on mandatory overflow and delete `token_budget_enforcer.py`.
- (B) Fix `fill_to_budget` only; leave the unused `token_budget_enforcer.py` in place.
**Decision:** Option B for now. `fill_to_budget` is the canonical enforcer: it sums Tier0+TierA up front and raises `TokenBudgetExceededError` if they exceed `prompt_token_budget`; all Tier-A is included in full (no soft-cap dropping); only Tier B/C are greedily filled/trimmed, including the post-serialization overhead trim. `token_budget_enforcer.py` is left untouched because deleting a non-temporary file requires human approval per CLAUDE.md.
**Why:** Mandatory identity/session context must never be silently truncated — silent loss drives hallucination and is near-undiagnosable (a SEV-01 contributor).
**Consequence:** `token_budget_enforcer.py` (and its `test_context_pipeline.py` tests) is now redundant; logged as ISSUE-054 for deletion once approved.

## DEC-056: anti-hallucination guards auto-injected in the eval runner, not duplicated per-case
**Date:** 2026-06-03
**Context:** SEV-01 — every guard case (`case_adv_*`, `case_neg_*`) must PASS only when the NPC gives a substantive, non-canned, in-character answer. The brief listed adding `min_length`, a fallback `keyword_none`, and a positive `tone_judge` to all 23 guard cases.
**Decision:** Inject those three universal expectations centrally in `evals/runner.py` (`_guard_expectations` / `_expected_with_guards`) for any `case_adv_`/`case_neg_` case, instead of copying identical blocks into 23 YAML files. Each case keeps its own hand-tuned `keyword_none` (the case-specific false-premise tokens); the runner adds the universal guards on top.
**Why:** One source of truth means a newly added guard case cannot silently forget the protection, and the fallback-line list stays derived from `fallback_responses.json` rather than hand-copied. Avoids 23 near-identical diffs.
**Consequence:** The injected `tone_judge` requires the judge LLM; without Ollama every guard case fails closed (correct — the guarantee is undemonstrated, not green). If a specific guard case ever needs a bespoke positive rubric, add it in the case YAML; the universal one still applies.

## DEC-053: Phase 12 designer dashboard is a static SPA served by FastAPI
**Date:** 2026-06-03
**Context:** Phase 12 (S12.1–S12.5) needs a non-code web UI for narrative designers (graph viewer, NPC authoring, draft approval, engine inspector, analytics). The only existing UI is the pygame demo, which is not web.
**Options considered:**
- (A) Static SPA (vanilla HTML/CSS/JS) in `dashboard/`, served by the existing FastAPI app via a `StaticFiles` mount; graph via CDN Cytoscape. Zero npm/build toolchain, no new Python deps, testable with pytest against the new read routes.
- (B) React + Vite separate app — most capable but adds a Node/npm toolchain and a separate build/deploy story outside the Python conventions.
- (C) Server-rendered Jinja2 + HTMX — minimal JS, but awkward for the live interactive graph (S12.1) which wants client-side rendering and still needs a JS graph lib.
**Decision:** Option A (chosen with the user). New `dashboard/` dir mounted at `/dashboard` (auth-exempt static assets; API calls carry their own Bearer token). Added two read-only routes `GET /v1/system/config` and `GET /v1/system/metrics` for the Engines/Analytics tabs.
**Why:** Fits the repo's "many small files, minimal deps, Python backend" conventions; same-origin (no CORS); no toolchain to maintain for a hackathon-stage buyer tool.
**Consequence:** Pure-JS modules are not covered by a JS unit runner; backend additions are pytest-covered and the SPA assets are asserted present + endpoint-correct. If the dashboard grows into a real product surface, revisit (B).

## DEC-054: S12.4 engine cadence/cost tab ships read-only; live mutation deferred
**Date:** 2026-06-03
**Context:** S12.4 calls for "engine cadence + cost controls (tick interval, per-engine model/budget) over config endpoints." `Settings` is a frozen `lru_cache` singleton, and the autopilot captures `interval_seconds` + `budget_guard` at construction time in the lifespan — runtime mutation would require threading a mutable runtime-config store through the scheduler (a public-interface change requiring approval per CLAUDE.md).
**Decision:** Ship S12.4 as a read-only inspector: `GET /v1/system/config` (curated cadence/cost view) + the existing `GET /v1/system/engines` per-engine status. Live mutation is deferred and logged as ISSUE-051.
**Why:** Delivers the visible, buyer-facing surface now without a risky scheduler refactor mid-phase. Read-only config + live status is a legitimate first implementation of the tab.
**Consequence:** When a customer needs live tuning, design a `RuntimeConfigStore` injected into the autopilot + a guarded `PATCH /v1/system/config` (admin scope), then wire the dashboard inputs to it.

## DEC-055: S13.2 dropped; roadmap slimmed to Phase 14+ after the 2026-06-03 review
**Date:** 2026-06-03
**Context:** Phase 13 hygiene committed the finished Phase 11/12 work and surfaced `REVIEW_FINDINGS.md` (multi-agent audit, **BLOCK**, 43 findings incl. 2 CRITICAL). Two decisions followed.
**Decisions:**
- (1) **Drop S13.2** (runtime config mutation / ISSUE-051). It is a P3 scheduler-loop + public-`PATCH` change that needs sign-off, and it ranks below the CRITICAL/HIGH review-remediation backlog. ISSUE-051 closed won't-fix; dashboard controls stay read-only.
- (2) **Archive + slim the roadmap.** Phases 0–13 (full history, audit, session log) snapshotted to `proposals/archive/ROADMAP_through_phase13_2026-06-03.md`; live `ROADMAP.md` reduced to Phase 14 onward + a remediation-backlog pointer to `review-fixes/`.
**Why:** Keep the live roadmap a clean forward-planning surface; avoid building features (or a risky scheduler refactor) on a BLOCK-verdict base without first deciding remediation sequencing.
**Consequence:** The `review-fixes/` backlog (FIX-SEV-01…18) is not yet phased — the next session owes a remediation-vs-feature sequencing decision before Phase 14 work begins.

## DEC-049: run.py split into run.py + run_scenes.py
**Date:** 2026-06-03
**Context:** S6.6 added 7 new scene classes and a fuller SCENES list. `run.py` was already ~353 lines (over the 300-line hard limit). Adding ~180 lines would push it to ~530.
**Decision:** Extracted all `Scene` subclasses (NarratorCue, SeedCheck, EventFire, ClockTick, DialogueBeat, StreamingDialogueBeat, BribeScene, ReputationDisplay, EmotionDisplay, QuestDisplay, MemoryConsolidate, WorldFeed) plus the base `Scene` dataclass into `demo_game/run_scenes.py`. `run.py` now holds LLMCache, SCENES list, DemoRunner, and main().
**Why:** Natural seam — the scene type definitions are pure data-class behaviour with no dependency on LLMCache or DemoRunner state. Moving them removes a circularity and keeps both files under 300 lines.

## DEC-050: put_world_state hardcoded "world" → "world_demo"
**Date:** 2026-06-03
**Context:** ISSUE-044 fix (S0.4) changed the canonical WorldState ID from "world" to "world_demo" in seed.py and Settings. However `EngineClient.put_world_state` still wrote to `id="world"`, so all EventFire scenes in the demo runner wrote to a node the engine never read.
**Decision:** Changed the hardcoded `"world"` to `"world_demo"` in `put_world_state`. All callers (run.py, game_window.py, scenario runners) now update the correct node.
**Why:** The world ID is a demo-world constant, not a general configuration value. Adding an injection point would be over-engineering; the demo is always `world_demo`.
**Future:** If multi-world support is added, `EngineClient` should accept a `world_id` parameter on all world-state mutating methods.

## DEC-051: S10.3 correct rumor marks 'corrected' rather than deleting the edge
**Date:** 2026-06-03
**Context:** When the player corrects a planted rumor at an NPC, the KNOWS_ABOUT edge
could either be deleted or marked with `knowledge_state='corrected'`.
**Decision:** Set `knowledge_state='corrected'` and filter it in `CYPHER_GET_EVENTS_FOR_NPC`
(`WHERE k.knowledge_state IS NULL OR k.knowledge_state <> 'corrected'`).
**Why:** Retaining the edge preserves audit history (who heard the rumor, at what tick) and
enables future "trace what was corrected and where" queries without re-propagation. Deletion
would be irreversible and prevent later investigation. The filter is O(1) Cypher predicate.

## DEC-052: game_controller.py ~535 lines — continued DEC-048 exception
**Date:** 2026-06-03
**Context:** S10.3 added correct-rumor queue/spawn/poll and event_id tracking (~35 lines).
**Decision:** Accept the over-limit size rather than split. DEC-048 rationale stands —
GameController is a single cohesive class managing all action queues. Each new demo action
adds one queue, one spawn, one poll; these are repetitive but inseparable from the class.
**Future:** If a 5th+ phase adds more actions, consider extracting a `RumorController` analogous
to `QuestTradeController`.

## DEC-001: LEVERAGE is a reified node, not an edge
**Date:** 2026-05-19
**Context:** Phase 7.2 Political Simulation adds a leverage mechanic where one character holds leverage over another, grounded in a shared secret.
**Decision:** LEVERAGE is implemented as a node (`Leverage`) rather than a `Character→Character` edge.
**Schema:** `Character -[HAS_LEVERAGE]→ Leverage -[AGAINST]→ Character`, with `Leverage -[GROUNDED_IN]→ Secret`.
**Why:** Neo4j edges cannot have outgoing edges — only nodes can. F3 fix requires `GROUNDED_IN: LEVERAGE → Secret` for graph traversal. A reified node is the correct solution. It also makes leverage queryable as a first-class entity (e.g., find all leverage nodes with status=held).
**Alternative rejected:** Keep LEVERAGE as an edge with `secret_id` string FK and skip F3. Rejected because it defeats the graph-traversal benefit and was explicitly called out as a flaw in the roadmap.

---

## DEC-002: Military engine run_tick is a stub
**Date:** 2026-05-19
**Context:** Phase 7.4 Strategy/4X adds ARMY, RESOURCE_NODE, and military infrastructure. The tick logic (battle resolution, resource yield, depletion) is complex and was not specified in detail.
**Decision:** `MilitaryEngine.run_tick` is a stub returning `{"skipped": True}`. The engine is wired into TickScheduler to enable future expansion without schema changes.
**Why:** User explicitly confirmed military logic should be deferred. Wiring the stub now means the scheduler interface does not need to change when logic is added.

---

## DEC-003: Succession engine queries HOLDS_TITLE edge (F2 fix)
**Date:** 2026-05-19
**Context:** The roadmap originally defined `TITLE.current_holder_id` as a string field. F2 identifies this as a staleness risk.
**Decision:** `title.yaml` does NOT include `current_holder_id`. The current holder is always determined by querying the `HOLDS_TITLE` edge in Neo4j.
**Why:** A denormalized `current_holder_id` field goes stale whenever a title is transferred. Graph edges are the authoritative, always-consistent source. The succession engine and any code needing the current holder must use `political_queries.get_current_title_holder`.

---

## DEC-004: SATISFIES_NEED uses location src_type only (ISSUE-034)
**Date:** 2026-05-19
**Context:** SATISFIES_NEED should accept both Item and Location as source nodes per the roadmap.
**Decision:** Initial implementation registers `satisfies_need.yaml` with `src_type: location` only. Item→Need satisfaction is deferred to ISSUE-034.
**Why:** The type registry YAML format supports a single `src_type` string. Adding multi-type support requires registry changes out of scope for this phase. Location-based satisfaction covers the primary use case (a tavern satisfies the social need).

---

## DEC-005: controls.yaml gains optional fields (schema extension)
**Date:** 2026-05-19
**Context:** Phase 7.4 roadmap specifies adding `control_strength` (0–100) and `contested_by_faction_id` to the existing `CONTROLS` edge.
**Decision:** Both fields added as `required: false` to `controls.yaml`. Existing CONTROLS edges without these fields remain valid.
**Why:** Making them optional preserves backward compatibility — existing graph data does not need migration. Military engine can write these fields when it sets control state; political and faction engines can read them without breaking if absent.

---

## DEC-006: Demo gossip chain is pre-seeded, not live-propagated
**Date:** 2026-05-22
**Context:** Roadmap V3 Phase 1. The gossip propagation engine selects pairs by co-location (`LOCATED_AT`). Captain Sorn is alone at `loc_guard_barracks`, so the engine cannot propagate northern_war_begins to Mira (tavern) or Henryk (market_square) in the 3 ticks the demo script fires.
**Decision:** Pre-seed distorted KNOWS_ABOUT edges for `mira_innkeeper` and `old_henryk` in the demo world seed. The 3 ClockTick scenes in `demo_game/run.py` advance the tick counter (for visual pacing) but are not the source of the demo-path knowledge. LOCATED_AT edges are also now seeded for all 5 NPCs; live gossip will work between co-located pairs in the interactive game.
**Why:** Demo reliability requires the same gossip chain on every run. Pre-seeding is the explicit contingency in ROADMAP.md and avoids randomness from propagation timing or ordering. The distorted summaries are authored to demonstrate the feature clearly.

---

## DEC-007: `--cached` mode skips scene delays
**Date:** 2026-05-22
**Context:** `make demo-run ARGS=--cached` exit criterion is < 10 seconds. With 23 s of `delay_before_ms` sleeps across all scenes, the cached run was timing out at ~33 s.
**Decision:** `DemoRunner.run()` skips delays when `self.cache.readonly` is True (i.e. `--cached` mode), matching the existing `--dry-run` behavior. Live mode (`make demo-run`) retains all delays for pacing during recording.
**Why:** `--cached` mode is used to verify the cache is warm before recording, not to actually drive the recorded video. The recording uses live mode where delays create natural pacing for the narrator.

---

## DEC-008: No `services/` layer — `mutation/` is the services layer
**Date:** 2026-04-30
**Context:** The refactor prompt specifies a `services/` layer between `engines/` and `retrieval/`, but the actual codebase has no such directory. The `mutation/` directory partially fills this role.
**Options considered:**
  1. Create a `services/` directory and move `mutation/` into it.
  2. Treat `mutation/` as the `services/` layer with its current name — less churn.
**Decision:** Option 2. Will revisit if a service explicitly needs to live in `services/` and `mutation/` is the wrong home.
**Why:** Renaming a directory mid-refactor touches every import. Zero benefit given the scope.

---

## DEC-009: Layer violations V1–V6 fixed during owning service sessions
**Date:** 2026-04-30
**Context:** Six pre-existing layer violations detected during audit. Fixing all upfront would require touching many files outside the scheduled service.
**Options considered:**
  1. Fix all violations immediately before starting the refactor.
  2. Fix each violation when we reach the owning service.
**Decision:** Option 2. All V1–V6 resolved by end of refactor (see STATUS.md).
**Why:** Lower blast radius, tests stayed green throughout.

---

## DEC-010: Misplaced domain exceptions moved to owning services
**Date:** 2026-05-01
**Context:** `RelationDeltaExceededError`, `TokenBudgetExceededError`, and `ContextBudgetError` live inside `mutation/` and `retrieval/` rather than `utils/errors.py`, violating ERR-02.
**Decision:** Defer migration to when each owning service is refactored. Each deferred migration was tracked in STATUS.md and completed during the relevant service session.
**Why:** Moving them before the owning service is scheduled increases merge conflict risk.
**Outcome:** All three exceptions are now in `utils/errors.py`; re-exported via `__all__` in their original modules for backward compat.

---

## DEC-011: config_validators.py extracted from config.py (STRUCT-01)
**Date:** 2026-05-01
**Context:** Adding full docstrings to `config.py` validators would push it past 200 non-blank lines (STRUCT-01). Pydantic `@field_validator` classmethods cannot move to a different class.
**Options considered:**
  1. Skip Args/Returns on validator classmethods.
  2. Extract validator logic into standalone functions in `config_validators.py`; keep thin-delegate classmethods in `config.py`.
**Decision:** Option 2. `config.py` is now ~130 non-blank lines; validators are independently testable.
**Why:** Extraction preserves docstring completeness and enables unit-testing validators in isolation.

---

## DEC-012: No separate gateway service (Feature 0.3 scope reduction)
**Date:** 2026-05-05
**Context:** ROADMAP Feature 0.3 specified building a `gateway/` package in front of internal services. During route inventory, we found `main.py` already mounts all routes in a single FastAPI app with global `ApiKeyMiddleware` — the app already is what a gateway would be.
**Options considered:**
  1. Build `src/npc_engine/gateway/` as a second FastAPI app re-mounting existing routers. Cons: pure duplication, two apps for one process, double middleware overhead.
  2. Harden `main.py` as the canonical public entry point — rate limiting, request logging — without a separate gateway package.
**Decision:** Option 2.
**Why:** A separate gateway is justified when there are multiple processes to unify. We have one process. Adding architectural ceremony for a pattern that doesn't fit the topology is overengineering.

---

## DEC-013: Route audience split — /v1/ vs /v1/admin/
**Date:** 2026-05-05
**Context:** All routes previously lived under a single `/v1/` prefix. Game-engine clients and designer tooling used the same surface with different auth scopes.
**Options considered:**
  1. Keep everything under `/v1/` and rely on scope-based access control alone.
  2. Split into `/v1/` (game engine) and `/v1/admin/` (designer tooling) so the audience split is visible in the URL structure and enforceable at the network layer.
**Decision:** Option 2.
**Why:** The URL split makes it possible to restrict admin routes in a Docker network or nginx config without enumerating individual paths. It also makes the intended consumer of each route visible in the URL.
**Consequence:** Any existing client targeting `/v1/batch/*`, `/v1/graph/admin/*`, or `/v1/schema` must update to `/v1/admin/*`.

---

## DEC-014: Defer `src/` layout move — use pyproject.toml when it happens
**Date:** 2026-05-05
**Context:** Moving source to `src/npc_engine/` with standard pythonpath would require updating ~800 bare imports across ~130 files. No pyproject.toml exists.
**Options considered:**
  1. Do the src/ move now with full import rename (~800 changes).
  2. Move to src/npc_engine/ but use `pythonpath = ["src/npc_engine"]` in pytest.ini (zero import changes, non-standard).
  3. Defer the src/ move entirely.
**Decision:** Option 3. All other Phase 0.2 tasks proceed without touching source. When the move happens, a proper `pyproject.toml` will be written (setuptools or hatchling) and all bare imports renamed to `npc_engine.xxx`.

---

## DEC-015: `how_long_ago` 7–27 day gap treated as "a few days ago"
**Date:** 2026-05-11
**Context:** The ROADMAP spec defines named buckets for 0, 1, 2–6 days, 28 days (one season), and >28 days, but leaves 7–27 days undefined.
**Options considered:**
  1. Add a new bucket "a week or two ago" for 7–27 days.
  2. Extend "a few days ago" to cover 2–27 days.
**Decision:** Option 2. "a few days ago" covers delta_days 2–27. Logged as ISSUE-013 for future refinement.
**Why:** Spec-compatible. Slightly imprecise at the 7-day boundary but not misleading.

---

## DEC-016: context_builder.py accepted at ~464 lines (300-line limit exception, updated SEV-23)
**Date:** 2026-05-18, updated 2026-06-04 (SEV-23)
**Context:** After Phase 6 additions (two-pass reranking, query expansion, trust scoring, second-hop events, quest state, cross-encoder gating), `context_builder.py` was 367 lines. SEV-23 extracted `EmbeddingIndexProtocol` to `context_protocols.py` and removed backward-compat shims, but the file grew to ~464 lines due to accumulated context features. CLAUDE.md hard limit is 300 lines.
**Options considered:**
  1. Split `_build_secondary_tier_a_items(...)` — saves ~30 lines, adds helper with 12 parameters.
  2. Extract Stage 4 gather into `_fetch_enrichment(...)` — saves ~12 lines.
  3. Accept the overrun with a justifying comment and this entry.
**Decision:** Option 3. `build_serialized_context` is a single async orchestration pipeline: every line is part of one logical flow. Splitting distributes one function across two modules with no encapsulation benefit.
**Limit:** If it grows to 500 lines, split then — 464 is at the boundary; do not allow further growth.

---

## DEC-017: World-state non-compliance root cause is weak prompt instruction, not retrieval
**Date:** 2026-05-20
**Context:** Phase 0 audit ran `scenario_war_breaks_out.py`. WorldState epoch changed from `age_of_peace` to `war` mid-session. LLM acknowledged the epoch in language but kept the same threat assessment, ignoring the behavioral rule.
**Options considered:**
  1. WorldState not reaching the prompt — ruled out; `context_builder.py:276` injects it as tier0/priority=100.
  2. System prompt instruction too weak for Mixtral 8x7b to act on materially — confirmed.
  3. RAG retrieval filling context with wrong events — not relevant; world state is direct-injected.
  4. Model capability limit — possible co-cause; cannot distinguish from (b) without model swap.
**Decision:** Treat (b) as primary cause. Phase 2 first lever: rewrite epoch instruction as an authoritative prohibitive constraint, not a descriptive hint.
**Consequence:** Phase 2 must move `_SYSTEM_PROMPT` from inline Python to a versioned YAML under `prompts/` (CLAUDE.md rule: no prompt strings outside prompts/).

---

## DEC-018: Dialogue model upgraded to qwen2.5:14b
**Date:** 2026-05-21
**Context:** Previous model was `qwen2.5:7b` (~4.7 GB Q4). Phase 2 demo skeleton drives more varied dialogue; a stronger base model reduces prompt-engineering effort. Constraint: 12 GB VRAM.
**Options considered:**
  1. `qwen2.5:14b` (~8.5 GB Q4_K_M) — best instruction-following in class; direct lineage upgrade.
  2. `gemma3:12b` (~8 GB) — weaker strict-JSON adherence.
  3. `phi4:14b` (~9.8 GB) — tight on 12 GB; less proven for roleplay.
**Decision:** `qwen2.5:14b`. Single-line change in `llm_config.yaml`; engine is model-agnostic via Ollama backend.
**Consequence:** War scenario re-verified after pull. Phase 3 QLoRA adapter targets this base.

---

## DEC-019: explicit_node_ids field added for per-turn context pinning
**Date:** 2026-05-21
**Context:** `RelevanceWeights` documented an `explicit` scoring component but it was unimplemented. The game engine needed a mechanism to signal which graph nodes are scene-critical for the current turn without relying on vector similarity alone.
**Options considered:**
  1. `explicit_node_ids: tuple[str, ...]` in `DialogueRequest` — per-request, deterministic, testable.
  2. Graph node property flag — persistent but stale-flag risk.
  3. Keyword-match automatic — fuzzy, duplicates vector similarity.
  4. Topic classifier extension — coarse (type-level, not node-level).
**Decision:** Option 1. Mirrors the existing `active_quest` per-request signal pattern. Nodes in the set score `explicit=1.0`; all others score `0.0`. `RelevanceWeights.explicit` defaults to `0.0` so existing profiles are unchanged.
**Consequence:** Game client must populate `explicit_node_ids` in `POST /v1/dialogue` requests to use it; inert otherwise.

---

## DEC-020: Standalone seeder pattern for demo and test worlds
**Date:** 2026-05-22
**Context:** Phase 2 needed a seeder for a demo world distinct from the engine baseline world.
**Options considered:**
  1. Extend `api_seeder.py` with demo-world data — couples the engine baseline seed to a demo artefact.
  2. Standalone `demo_game/seed.py` — separate script, HTTP-only, zero `src/npc_engine/` imports.
**Decision:** Option 2. The demo world is a Phase 2 artefact; its seeder lives in `demo_game/`.
**Pattern for future phases:** Any phase that needs a self-contained world (eval harness, QLoRA training data, integration fixture) should follow the same pattern: standalone seeder in its own directory, HTTP-only, idempotent.
**Consequence:** `make demo-seed` invokes `demo_game/seed.py` directly. `make seed-api` is unchanged. The two seeders share no code.
**Superseded by DEC-021 (2026-05-27):** Seed files consolidated under `seeds/worlds/`. DEC-020's "own directory" rationale is preserved but the directory is now always a subdirectory of `seeds/`, not the owning app.

---

## DEC-021: Seed files consolidated under seeds/worlds/
**Date:** 2026-05-27
**Context:** `demo_game/seed.py` lived inside the demo app but its purpose is seeding world state for tests, evals, and demos. `seeds/world/` already held two other seed worlds. Having seed files in multiple top-level directories made it hard to see all available worlds at a glance.
**Decision:** Move `demo_game/seed.py` → `seeds/worlds/seed_demo_world.py`. Rename `seeds/world/` → `seeds/worlds/`. All world seed scripts now live under `seeds/worlds/`. Naming convention: `seed_<world_name>_world.py`.
**Why:** Single folder for all seed data means a new developer or a future session can enumerate available worlds with one `ls seeds/worlds/`. The "app owns its data" principle from DEC-020 is superseded — data that serves multiple consumers (evals, demo, e2e) should not live inside one consumer's directory.
**Consequence:** `make demo-seed` updated to invoke `seeds/worlds/seed_demo_world.py`. `demo_game/tests/test_seed.py` import path updated. `src/npc_engine/data/api_seeder.py` is not moved — it serves the engine baseline, not a test world.

---

## DEC-022: WorldState node uses id="world" as the canonical identifier
**Date:** 2026-05-27
**Context:** The demo world seed used `_WORLD_STATE_ID = "ws_main"` but `world_reader.py` defaults to `world_id: str = "world"`. The mismatch meant epoch and active_conditions were never read during dialogue — a silent content assumption baked into the seeder that violated engine content-agnosticism.
**Decision:** All seed scripts must create the WorldState node with `id="world"`. The reader default is the source of truth; seeders conform to it.
**Why:** The engine must not depend on knowing a world-specific ID. Any seed using a custom ID would silently break world-state-dependent rules (Rule 1 epoch constraints, active_conditions checks) without raising an error. The reader default `"world"` is the contractual ID.
**Consequence:** Demo world seed changed from `_WORLD_STATE_ID = "ws_main"` to `_WORLD_STATE_ID = "world"`. Any live Neo4j database seeded with `ws_main` must be re-seeded or the node manually renamed. ISSUE-041 closed.

---

## DEC-023: Project management files live exclusively in project-harness/
**Date:** 2026-05-27
**Context:** ISSUES.md, DECISIONS.md, and ROADMAP.md existed at both the project root and in `project-harness/`. The two copies diverged: root had different issue IDs for the same problems, and `project-harness/DECISIONS.md` redirected back to root. Two sources of truth means both are wrong.
**Decision:** All three files live in `project-harness/` only. Root-level copies are deleted. CLAUDE.md enforces this with an explicit rule.
**Why:** `project-harness/` is already loaded into every Claude Code session via the system reminder. Centralising here means every session reads the latest state without hunting for the root copy. The root is for code; session-context files belong in the harness.
**Consequence:** Any script or doc that references root-level `DECISIONS.md` or `ISSUES.md` must be updated to point to `project-harness/`.

## DEC-024: game_window.py exempt from 300-line hard limit
**Date:** 2026-05-28
**Context:** `game_window.py` is 372 lines after the S3.1 per-NPC dialogue log changes. The 300-line rule exists to prevent monolithic files.
**Decision:** Accept the exception. Do not split `GameWindow` across files.
**Why:** `GameWindow` owns the pygame event loop, rendering pipeline (two panels), and threading model (dialogue worker + graph poller). Every draw method references `self._screen`, `self._client`, `self._logs`, `self._badge`, and shared layout constants. Splitting across files would require either passing the screen surface and all state around as arguments, or a second class that's a thin wrapper — both are more complex than the current flat structure. The left-panel rendering is extracted into `_draw_left_panel()` to keep individual methods readable.
**Consequence:** If game_window.py grows past ~450 lines (Phase 4 polish work), revisit splitting into `DialoguePanel` + `GraphPanel` classes with a thin `GameWindow` coordinator.

---

## DEC-026: Sidebar fetch wired in S3.3; rendering deferred to S3.4
**Date:** 2026-05-28
**Context:** S3.3 builds `KnowledgeSidebarWidget` and the `knowledge_sidebar_fetcher`. The Tab-key
toggle that makes the sidebar visible in the right panel is S3.4.
**Decision:** Wire the background fetch on NPC-click in `game_window.py` during S3.3. Do not add
the draw call or Tab keypress until S3.4.
**Why:** The fetch and the render are independent concerns. Threading must be in place before the
Tab key can show anything meaningful. Keeping the render out of S3.3 avoids a half-visible UI that
isn't wired to a toggle yet. S3.4 adds exactly: `_show_sidebar` flag, Tab handler, header strip, and
`self._sidebar.draw(...)` in `_draw_right_panel`.
**Consequence:** After S3.3, clicking an NPC triggers a silent background fetch. `self._sidebar` holds
the data but is never drawn. This is correct exit state for S3.3.

---

## DEC-027: Exclusive scroll routing when sidebar panel is active
**Date:** 2026-05-28
**Context:** `MOUSEWHEEL` events in pygame are global — not scoped to the widget under the cursor. Both `ScrollableLog` (dialogue, left panel) and `KnowledgeSidebarWidget` (right panel) have `handle_event` scroll handlers. When Tab shows the sidebar, both could receive wheel events simultaneously.
**Decision:** In `_handle_event`, use exclusive routing: `if self._show_sidebar: self._sidebar.handle_event(event) elif self._active_npc_id: log.handle_event(event)`. Never additive.
**Why:** Additive routing (routing to both unconditionally) causes hidden scroll-state drift — the non-visible panel accumulates scroll offset while invisible, so switching back surprises the user. Exclusive routing eliminates that class of bug with no downside for the demo.
**Tradeoff:** User cannot scroll the dialogue log while the sidebar is shown. Acceptable for demo use; Phase 4 `DialoguePanel` / `GraphPanel` refactor can revisit if mouse-position-aware routing is desired.

---

## DEC-025: Demo seed reverted to demo_game/seed.py (S3.2 — reversal of DEC-021)
**Date:** 2026-05-28
**Context:** DEC-021 moved the demo world seed from `demo_game/seed.py` → `seeds/worlds/seed_demo_world.py` for consolidation. S3.1 reversed this: the demo seed moved back to `demo_game/seed.py`.
**Decision:** `demo_game/seed.py` is the authoritative demo world seed. `seeds/worlds/seed_demo_world.py` is deleted. The DEC-021 "single folder" rationale is superseded for the demo seed specifically.
**Why:** The demo game must be self-contained and fully decoupled from the NPC engine source — as if a third-party studio built it on top of the shipped SDK. Its seed data belongs inside `demo_game/`, not alongside eval world seeds. Naming convention going forward: `seeds/worlds/seed_*.py` = eval harness worlds only; `demo_game/seed.py` = demo app seed.
**Consequence:** `seeds/worlds/` contains only `seed_tavern_world.py` and `seed_village_world.py`. Any reference to `seeds/worlds/seed_demo_world.py` in historical docs is stale but preserved for audit trail.

---

## DEC-028: NPC_FACTIONS hardcoded in constants.py rather than fetched from graph
**Date:** 2026-05-28
**Context:** S3.5b adds a faction-coloured dot to each NPC row in NpcListWidget. Faction data exists in the graph: each Character node has a faction field. An alternative is to call `get_npc_state(npc_id)` for each NPC at list-draw time, or once on NPC click.
**Decision:** `NPC_FACTIONS` is a static dict in `demo_game/constants.py` mapping each NPC ID to its faction string.
**Why:** The demo world has exactly 5 NPCs whose faction membership never changes during a session. The seed is stable for the Munich June 6 demo. Fetching from the graph would require either (a) blocking list-draw, or (b) a background fetch + per-NPC cache, for data that never changes. The cost/benefit is entirely negative. If faction becomes dynamic (e.g., NPCs can switch factions at runtime), this constant should be replaced with a graph-backed `FactionPoller`.
**Consequence:** Adding a sixth NPC or changing faction membership requires a manual update to both `seed.py` and `NPC_FACTIONS` in `constants.py`. The invariant test `test_npc_factions_keys_match_display_names` guards against drift.

---

## DEC-029: widgets.py exempt from 300-line hard limit
**Date:** 2026-05-28
**Context:** `demo_game/ui/widgets.py` reached 317 lines before S3.5 changes and grew further during S3.5 (DegradationBadge split rendering + NpcListWidget faction dot). The 300-line limit applies to non-test code.
**Decision:** Accept the exception. Do not split `widgets.py` across files at this time.
**Why:** All four widget classes (`InputBox`, `ScrollableLog`, `NpcListWidget`, `DegradationBadge`) share the private colour constants (`_CLR_*`) and the `_emotion_colour` / `_wrap_text` helpers defined at module level. Splitting into multiple files would require either duplicating the colour block or extracting a `_widget_colours.py` module with no cohesion benefit. The natural split (one class per file) would also break the `_MockFont` test pattern used across all widget tests in `test_widgets.py`.
**Consequence:** If `widgets.py` grows past ~450 lines (Phase 4 polish), revisit splitting into `input_box.py`, `scrollable_log.py`, `npc_list_widget.py`, and `degradation_badge.py` with a shared `_colours.py`.

---

## DEC-030: S4.6 (layout refactor) reordered to execute before S4.0–S4.5
**Date:** 2026-05-28
**Context:** ROADMAP Phase 4 originally placed the layout audit / `--size` CLI arg as step S4.6 (after 5 polish steps). Steps S4.0–S4.5 each add new UI elements with specific pixel positions. Doing the layout refactor last would require re-deriving all new positions twice — once for the initial implementation and once during the refactor.
**Decision:** Execute S4.6 first in the Phase 4 sequence. All subsequent polish steps build on layout constants derived from `window_w, window_h` instance attrs.
**Why:** Single pass on pixel math. No rework. All Phase 4 widgets are built on the flexible foundation from day one.
**Consequence:** ROADMAP updated with plan note. Implementation starts with S4.6, then S4.0, then S4.1–S4.5 in original order.

---

## DEC-031: Right panel extended from 2-tab bool to 3-tab RightPanel enum
**Date:** 2026-05-28
**Context:** S3.4 implemented a 2-tab boolean toggle (`_show_sidebar: bool`) for GRAPH vs KNOWLEDGE. S4.0 adds a third panel (PLAYER STATUS) for quests, inventory, and future player-facing data. The boolean cannot extend gracefully to 3+ values.
**Decision:** Replace `_show_sidebar: bool` with `_active: RightPanel` where `RightPanel(enum.Enum)` has values GRAPH, KNOWLEDGE, PLAYER_STATUS. Tab key cycles using index arithmetic. Adding a 4th tab (S4.9 CHAIN) requires only appending an enum value.
**Why:** Enum cycle is O(n) to extend (append value + add elif branch), vs boolean which requires refactoring the entire toggle to a tri-state. Enum value strings also serve as self-documenting header labels.
**Consequence:** `_show_sidebar` removed. All code that branched on `_show_sidebar` updated to branch on `_active`. Exclusive scroll routing (DEC-027) preserved as elif chain.

---

## DEC-032: game_window.py split into left_panel.py + right_panel.py + thin GameWindow
**Date:** 2026-05-28
**Context:** DEC-024 set a 450-line trigger for splitting `game_window.py`. It reached 472 lines after S3.5. Phase 4 adds ~250+ lines of new rendering logic (tab enum, portrait zone, preset buttons, event banner, trade overlay, quest panel integration) — projecting to ~730 lines without a split.
**Decision:** During S4.6, split game_window.py into three files:
- `demo_game/ui/left_panel.py` — `LeftPanelRenderer`: NPC list, dialogue log, input box, portrait zone, preset buttons, event banner, trade overlay (~200 lines)
- `demo_game/ui/right_panel.py` — `RightPanelRenderer`: `RightPanel` enum, 3-tab state, GRAPH / KNOWLEDGE / PLAYER STATUS rendering (~180 lines)
- `demo_game/ui/game_window.py` — thin `GameWindow`: pygame event loop, thread ownership, routes events to both renderers (~150 lines)
**Why:** Single-responsibility. Each renderer owns its rect and its widget instances. GameWindow owns threads and the pygame main loop only. File sizes stay within 300-line limit without exceptions.
**Consequence:** DEC-024 exception is resolved. All tests importing `GameWindow` from `game_window` remain valid; renderer classes are internal. Test suite must be green before any S4.0 work begins.

---

## DEC-034: client.py exempt from 300-line hard limit
**Date:** 2026-05-29
**Context:** `demo_game/client.py` is 680 lines after adding `post_quest_generate` and `get_quest` in S4.0.
**Decision:** Accept the exception. Do not split client.py.
**Why:** client.py is a single-class HTTP client wrapper. Every method maps 1:1 to one engine API endpoint — no branching logic, no domain knowledge, no state other than connection settings. Splitting it (e.g. `quest_client.py`, `graph_client.py`) would require callers to import from multiple modules for unrelated operations and would obscure the complete API surface. The 300-line rule targets mixed-concern modules; this is one class with one concern.
**Limit:** If client.py exceeds ~900 lines, extract a `QuestClient` and `EconomyClient` mixin approach, with `EngineClient` inheriting both.
**Consequence:** client.py will grow to ~750 lines by end of Phase 4 (trade, quest lifecycle). Acceptable under this exception.

---

## DEC-036: left_panel.py exempt from 300-line hard limit
**Date:** 2026-05-29
**Context:** `demo_game/ui/left_panel.py` reached 322 lines after S4.4 added `ActionBarWidget` integration, trade-price overlay state, and two new public methods.
**Decision:** Accept the exception. Do not split left_panel.py.
**Why:** `left_panel.py` is a single-class renderer for one panel. Splitting it (e.g. `left_panel_widgets.py` for drawing helpers) would scatter closely related rendering logic with no encapsulation benefit — the helpers only make sense in the context of `LeftPanelRenderer`'s state. The DEC-024 line-limit rule targets mixed-concern modules; this is one class with one concern.
**Limit:** If `left_panel.py` grows past ~400 lines, extract widget-draw helpers into `demo_game/ui/left_panel_draw.py` as free functions receiving explicit arguments.
**Consequence:** left_panel.py may reach ~340 lines by end of Phase 4. Acceptable under this exception.

---

## DEC-035: PALETTE dict in constants.py is the single source of truth for UI colours
**Date:** 2026-05-29
**Context:** S4.2 introduced a unified colour palette. Before this, each UI file had its own hardcoded `_CLR_*` tuples, causing colour drift across panels.
**Decision:** All UI colours must be defined in `PALETTE` (or `LOCATION_TINTS`) in `demo_game/constants.py`. Module-level `_CLR_*` aliases in widget/renderer files are allowed as thin wrappers (`_CLR_AMBER = PALETTE["amber"]`) to minimise diffs, but must not introduce new hardcoded colour tuples. Widget-specific colours with no semantic equivalent in PALETTE (e.g. `_CLR_INPUT_BG`) may remain hardcoded in their own file until a natural refactor opportunity arises.
**Why:** Centralised palette makes re-theming or adjusting any colour a one-line change. The alternative (each file owns its colours) caused `(212, 160, 23)` and `(200, 160, 80)` amber variants to coexist with no way to tell which was canonical.
**Consequence:** Adding a new colour requires editing constants.py first. Reviewers should reject any PR that introduces a new hardcoded colour tuple in a UI file if a PALETTE key would serve.

---

## DEC-033: seed.py exempt from 300-line hard limit
**Date:** 2026-05-28
**Context:** `demo_game/seed.py` is 671 lines. Phase 4 adds quest generation (~25 lines) and item seeding (~20 lines), pushing it toward ~720 lines.
**Decision:** Accept the exception. Do not split seed.py.
**Why:** seed.py is a pure data seeder: it contains zero algorithmic logic, no classes, no branching beyond HTTP error checks. Every line is a data definition or an API call. The 300-line rule targets monolithic modules mixing concerns; seed.py has exactly one concern. Splitting it (e.g. `_seed_npcs.py`, `_seed_events.py`) would scatter the definition of a single world state across multiple files with no encapsulation benefit.
**Limit:** If seed.py grows past ~800 lines, extract helpers into `demo_game/_seed_helpers.py` (shared payload builders) while keeping the main seeding orchestration in seed.py.
**Consequence:** seed.py will reach ~720 lines after Phase 4. Acceptable under this exception.

---

## DEC-038: NegotiationSession is frozen; route layer owns graph side-effects
**Date:** 2026-05-30
**Context:** Phase 3 trade. `trade_handler.py` must update the in-memory NegotiationSession for `defer_payment` but also needs a HAS_DEBT edge written to Neo4j.
**Decision:** `trade_handler` is pure in-memory Python. It returns `InteractionState(status="accepted")` for `defer_payment`. The route layer (`api.routes.interaction`) is responsible for calling `write_debt_edge` before returning the response. The handler sets `status=accepted` in the in-memory session regardless.
**Why:** Keeping `trade_handler` free of graph I/O makes it synchronously testable without any Neo4j fixture. The route layer already has a DB session injected. This mirrors the pattern used by `quest_engine_helpers` — handlers are pure, routes orchestrate persistence.
**Consequence:** If the route crashes after `trade_handler` sets `accepted` but before `write_debt_edge`, the in-memory session is accepted but no DB record exists. Acceptable for PoC single-player demo; a distributed deployment would need a compensation log.

---

## DEC-039: TRADE tab switch — switch_to() not cycle_tab() loop
**Date:** 2026-05-30
**Context:** Phase 3 demo. When `propose_trade` arrives in `_poll_response_queue`, the UI must jump directly to the TRADE tab regardless of which tab is currently active.
**Decision:** Added `RightPanelRenderer.switch_to(tab: RightPanel)` for direct tab navigation. `game_window` calls `switch_to(RightPanel.TRADE)` rather than cycling until it lands on TRADE.
**Why:** A cycle loop is O(n) and order-dependent. A direct switch is O(1) and order-independent. Adding tabs in the future would not break the jump logic.
**Consequence:** `switch_to` bypasses the cycling invariant but does not violate it — it simply sets `_active` directly. `cycle_tab` remains unchanged.

---

## DEC-037: Two-layer InteractionProposal — demo_game local type and engine type coexist
**Date:** 2026-05-30
**Context:** Phase 1 interaction dispatch. `demo_game/dialogue.py` needed a local `InteractionProposal` dataclass (parse layer only, no engine import). `npc_engine.engines.interaction.models` owns the engine-layer version with `is_interaction_kind()`. `game_window.py` needs to bridge them when routing to `dispatch_interaction`.
**Decision:** Keep both types. `demo_game.dialogue.InteractionProposal` is a frozen dataclass used purely for parse output within the demo layer — it has no engine dependency and stays serializable. `npc_engine.engines.interaction.models.InteractionProposal` is the authoritative engine type. `game_window._poll_response_queue` does the translation (3-line inline construction, no dedicated converter function).
**Why:** Importing `npc_engine` from `demo_game/dialogue.py` would couple the parse layer to the engine package; the parse module's header rule forbids this (`demo_game` layer zero engine imports). The bridge in `game_window` is the single callsite, so a dedicated converter would be premature abstraction.
**Consequence:** The two types must be kept structurally in sync (kind, target_id, payload). If a third field is added to either, it must be mirrored. Log any divergence as a P2 issue.

---

## DEC-040: is_trusted_reward_source accepts any non-empty string (NPC purse)
**Date:** 2026-05-30
**Context:** Phase 4 quest rewards. The plan requires quest rewards to source from the NPC's purse (not just from the system). `is_trusted_reward_source` was hardcoded to `return reward_source_id == "system"`, blocking all NPC-sourced rewards.
**Decision:** Changed `is_trusted_reward_source` to `return bool(reward_source_id) and reward_source_id != ""`. This accepts `"system"` and any non-empty character ID. Affordability protection is enforced separately in `apply_rewards` via `get_character_balance` before currency transfer.
**Why:** The previous guard mixed two concerns: identity validation (is this a known source?) and affordability (can the source pay?). Splitting them makes each concern independently testable and allows NPC IDs without maintaining an allowlist that would require seeder changes on every new NPC.
**Consequence:** Callers must not assume that `is_trusted_reward_source=True` implies sufficient balance. `apply_rewards` always checks balance for non-system sources. Any caller that skips the affordability check for a non-system source is a bug.

---

## DEC-041: Quest.status denormalised back-write at lifecycle transitions
**Date:** 2026-05-30
**Context:** Phase 4 NPC context injection. `get_active_quest_for_player` and `get_offered_quests_for_npc` query `QuestState` nodes (lifecycle state) and `Quest` nodes (definition) respectively. The Quest node has its own `status` field used by `get_offered_quests_for_npc` (filters `['offered', 'accepted', 'in_progress']`), but the lifecycle engine only writes to `QuestState` nodes. Quest node `status` was never updated, so the NPC could never see a quest as accepted in its context.
**Decision:** Added `update_quest_node_status` in `quest_writer.py` and call it from `quest_lifecycle_engine` after `accept_quest` and `evaluate_completion` transitions. This keeps the Quest node status field in sync as a denormalised read field.
**Why:** Option A (back-write) is safe because `Quest.status` is read-only for context injection — no lifecycle decision depends on it. Option B (changing context queries to join QuestState) requires schema changes and complicates the existing context builder. Option A is the minimal-change path.
**Consequence:** `Quest.status` may lag `QuestState.status` by one lifecycle call if the back-write fails (e.g., network issue between transactions). This is acceptable for demo context injection (stale by one turn at worst).

---

## DEC-043: TalkVerifier uses co-location proxy (no SPOKE_TO edge exists)
**Date:** 2026-06-02
**Context:** S2.1 — implementing `talk` objective verifier. No graph edge records that a player has spoken with a specific NPC. The dialogue handler writes relation deltas (trust/etc.) but does NOT write a SPOKE_TO or PARTICIPATED_IN edge per dialogue exchange.
**Decision:** `TalkVerifier` checks that the player and target NPC are both `LOCATED_AT` the same Location node. This is a co-location proxy: if two characters share a location they have the *opportunity* to talk.
**Why:** Adding a `SPOKE_TO` edge requires changes to the dialogue handler (a new graph write per dialogue turn) — out of S2.1 scope. Co-location is the strongest available graph signal without schema changes. It matches the game mechanic: you can only speak with NPCs in your current location.
**Consequence:** A player standing in the same room as an NPC satisfies a `talk` objective even without initiating dialogue. Upgrade path: add `SPOKE_TO { at_tick: int }` to the character schema, write it in `dialogue_handler.py` after each completed turn, and update `TalkVerifier` to query it.

## DEC-042: tick_scheduler.py accepted over 300-line hard limit
**Date:** 2026-06-02
**Context:** S1.3 — per-engine error isolation. Adding `_run_engine_safe` and wrapping 16 engine calls pushed `tick_scheduler.py` from 434 to ~480 lines — well above the 300-line hard limit.
**Decision:** Accepted the overrun. The `advance()` loop is a single cohesive sequential orchestration of 16 independent engines. Splitting it would require either (a) a separate `EngineRunner` class that still needs all 16 engine references injected, or (b) extracting per-engine blocks that share loop state (tick_id, unresolved, response dict) — both artificial splits that would reduce readability without improving cohesion.
**Why:** The 300-line limit prevents God-objects and functions that are too complex to reason about. This file is long because it has 16 engine dependencies, not because of logic complexity. Each engine block is 3-5 lines; the orchestration is a mechanical sequential list.
**Consequence:** Future engines added to the scheduler will extend the file further. The natural refactor trigger is when Phase 6 adds a `GET /v1/system/engines` endpoint that needs engine metadata (cadence, name) — at that point an `EngineDescriptor` list would replace the 16 individual `if engine is not None:` blocks.

## DEC-045: S3.1 expands _get_giver_context() rather than calling build_serialized_context()
**Date:** 2026-06-02
**Context:** S3.1 spec says "consume `retrieval/context_builder.py → build_serialized_context()` (needs, goals, inventory, location, faction, world state)". Two interpretations: (a) call `build_serialized_context()` directly; (b) pull the same graph data that function pulls.
**Decision:** Option (b) — expand `_get_giver_context()` with four new graph queries (needs, items, location, groups) and merge world_state at the call site in `generate()`. `build_serialized_context()` was NOT called directly.
**Why:** `build_serialized_context()` is dialogue-oriented. It requires `player_message`, `session_turns`, and `EmbeddingIndexProtocol` — all concepts that have no meaning in quest generation. Calling it with dummy values would couple quest generation to dialogue infrastructure. The function also runs RAG, cross-encoder reranking, and compression — all overkill for context injection at the slot-fill stage.
**Consequence:** If a future sprint wants to share context caching between dialogue and quest generation, `build_serialized_context()` can be refactored to accept an optional EmbeddingIndex and skip RAG when not provided. That refactor belongs to a Phase 5+ caching task.

## DEC-046: quest_generation_engine.py accepted over 300-line hard limit
**Date:** 2026-06-02
**Context:** S3.1 adds 4 graph imports, expands `_get_giver_context()` by ~15 lines, adds `_format_npc_context()` helper (~10 lines), and updates `_generate_flavor()` signature — bringing the file to ~400 lines.
**Decision:** Accepted. All additions are part of the NPC context assembly pipeline, a single cohesive responsibility. Extracting `_get_giver_context` + `_format_npc_context` into a `QuestContextAssembler` is the natural next step but premature with only two methods.
**Why:** See DEC-042 rationale. The natural refactor trigger is when Phase 4+ adds another NPC context dimension (e.g. relationship graph, emotional history) — that's when `QuestContextAssembler` earns its own file.
**Consequence:** The `_format_npc_context` helper is the seed of the future assembler. Keep it pure (no I/O, no session) so it can be moved without change.

## DEC-047: right_panel.py accepted over 300-line hard limit (~405 lines, updated S6.1)
**Date:** 2026-06-02 (updated 2026-06-03)
**Context:** Originally ~323 lines after ISSUE-049 fix. S6.1 adds EMOTION, NEEDS, and GOALS tabs — 3 imports, 3 widget instantiations, 6 setters, 3 properties, 6 draw/scroll branches — ~48 additional lines, bringing total to ~405 lines.
**Decision:** Accepted. `RightPanelRenderer` is a single-class module whose sole concern is coordinating right-panel tab state and delegating to widget instances. Every new tab adds the same narrow delegate pattern (setter, property, draw branch); there is no natural seam to split at fewer than 3 tabs.
**Why:** Splitting EMOTION/NEEDS/GOALS into a second renderer would add an artificial seam and a routing layer. The file remains structurally uniform — no function exceeds 10 lines.
**Split trigger:** Total > 500 lines OR a second stateful overlay workflow (like give-mode) is added.

## DEC-048: game_controller.py accepted over 300-line hard limit (~318 lines)
**Date:** 2026-06-02
**Context:** S4.3 adds `spawn_travel`, `poll_travel_queue`, and `_travel_q` (~20 lines net). File goes from 298 → ~318 lines.
**Decision:** Accepted. `GameController` is a single cohesive class whose sole responsibility is managing background threads and result queues for all demo actions. Each new action (travel, inspect, generate-quest) follows the same spawn+poll pattern and belongs here.
**Why:** Extracting travel into a `TravelController` would add an artificial seam at the cost of a second delegation layer with two methods. The natural split trigger would be if GameController grew a second stateful concern (e.g., a streaming event log) rather than just a new action of the same shape.
**Consequence:** When Phase 4+ adds Bribe (spawns a faction-politics call), it follows the same spawn+poll pattern and stays in this file. If a fifth or sixth action makes the class unwieldy, extract a generic `ActionQueueManager` base.

## DEC-051: run_scenes.py accepted over 300-line hard limit (~420 lines after S8.3)
**Date:** 2026-06-03
**Context:** S8.3 — adding `PropagatedReputationAct` brings `run_scenes.py` to ~420 lines. The file was already ~365 lines before this task (extracted from run.py in DEC-049).
**Decision:** Accepted. All scene classes are tightly coupled by the `DemoRunner` protocol and the `Scene` base class; splitting them across two files would require a second import barrel and create artificial separation with no cohesion benefit. Each class is a leaf dataclass with a single `execute` method. The file's length is proportional to the number of demo beats, not to any violation of SRP.
**Why:** The 300-line limit targets wide, sprawling modules. This file contains N small dataclasses, each independently testable, all serving one purpose: typed scripted-demo actions.
**Consequence:** If the demo grows beyond ~6 more scene types, split by act group (world_scenes.py, dialogue_scenes.py, reputation_scenes.py).

## DEC-052: S9.3 TTS audio delivered as base64 in WS done JSON, not as a binary frame
**Date:** 2026-06-03
**Context:** S9.3 — streaming audio bytes from the server to the demo UI over the existing dialogue WebSocket.
**Options considered:**
- (A) Binary WebSocket frame before the `done` JSON message — no encoding overhead, but requires the client to handle mixed-type frames and maintain sequence state.
- (B) Base64 field inside the `done` JSON message — slight size overhead (~33%), but keeps the protocol single-message-type and requires no frame-type dispatch in the client.
- (C) Separate HTTP endpoint for audio after WS completes — cleanest separation, but adds a round-trip and couples the client to two channels.
**Decision:** Option B. The demo produces short NPC utterances (< 5 s); WAV payload is typically < 200 KB. The 33% base64 overhead is negligible, and keeping a single JSON protocol layer simplifies the demo client and all tests significantly.
**Why:** Option A is correct for production high-throughput streaming (e.g., word-aligned lip-sync). For the Munich demo the priority is simplicity and test coverage.
**Consequence:** If audio clips grow beyond ~500 KB or we need word-level timing, revisit binary frames (A) with a typed frame envelope.

## DEC-044: quest_lifecycle_engine.py accepted over 300-line hard limit
**Date:** 2026-06-03
**Context:** S2.2 — adding `offer_draft_quest()` to `QuestLifecycleEngine` brings the file to ~560 lines. The class was already pre-existing at ~495 lines before this task.
**Decision:** Accepted. `QuestLifecycleEngine` is a single-class module (SRP satisfied). Its length comes from five distinct lifecycle methods (`offer_draft_quest`, `offer_quest`, `accept_quest`, `update_objective`, `evaluate_completion`, `apply_rewards`) each with full docstrings and narrow logic. Each method is under 40 lines. Splitting into two classes would require coordinating shared constants (`STATUS_*`) and dependencies across modules with no gain in cohesion.
**Why:** The 300-line limit targets wide classes with unrelated responsibilities. This class has one responsibility (quest lifecycle state machine) and is long due to the number of transitions in that machine, not due to sprawl.
**Consequence:** Acceptable until Phase 3 requires adding quest-type-specific transition logic — at that point extract per-type handlers via the Strategy pattern.

## DEC-058: Delete nested infra copies under src/npc_engine/
**Date:** 2026-06-04
**Context:** Six infra files under `src/npc_engine/` (docker-compose.yml, Dockerfile, mypy.ini, requirements.txt, game_schema.yaml, README.md) had drifted from root canonical copies and were actively harmful.
**Decision:** Root-level copies are canonical. Nested copies under `src/npc_engine/` deleted via `git rm`.
**Why:** The nested mypy.ini pinned `python_version = 3.11` (stack is 3.14), silently inflating error counts. The nested docker-compose.yml used a module path that no longer exists. All copies had diverged from root versions.
**Consequence:** None — no Makefile or CI reference pointed to these paths.

## DEC-060: main.py grandfathered at 361 lines pending SEV-23 split
**Date:** 2026-06-04
**Context:** SEV-33 added 77 lines to `src/npc_engine/main.py` (284 → 361), pushing it over the 300-line hard limit. This was not caught in that session. SEV-23 tracks splitting all over-300 files.
**Decision:** Waiver granted. `main.py` added to the rules baseline as a grandfathered violation. Will be resolved when SEV-23 executes.
**Why:** Splitting `main.py` mid-session during SEV-04 would expand scope and risk regressions in unrelated code. The violation was introduced by a committed prior fix, not by the current change.
**Consequence:** `make check-rules` passes with a baselined exception. SEV-23 must un-grandfather this when it splits the file.
**Resolved:** 2026-06-11 (Phase 21 S21.1) — superseded by DEC-089; `main.py` split to 217 lines, R001 baseline entry removed.

## DEC-061: gossip_handler.py waived at ~310→351 lines (soft 300-line limit)
**Date:** 2026-06-04
**Context:** SEV-29 batch N+1 fix pushed the file from ~198 to ~310 lines. SEV-36 added distortion_probability + seed logging and `compute_confidence` plumbing, pushing it to ~351 lines.
**Decision:** Waive extended. The file remains one cohesive orchestration class.
**Why:** All content is tightly coupled phases of a single gossip-tick orchestration. Splitting would scatter the flow with no independent reuse value.
**Consequence:** `make check-rules` must baseline gossip_handler.py. SEV-23 may revisit.

## DEC-059: MemoryConsolidationEngine.run_tick opens per-task Neo4j sessions from GraphDB
**Date:** 2026-06-04
**Context:** SEV-06 — `run_tick` previously iterated NPCs sequentially with a single shared `AsyncSession`. Neo4j `AsyncSession` objects are not concurrency-safe.
**Options considered:**
- (A) Parallelize LLM calls only; serialize Neo4j writes behind an `asyncio.Lock`. Complex because `consolidate()` interleaves read and write Neo4j calls.
- (B) Inject `GraphDB` into the engine constructor; open one fresh `AsyncSession` per NPC task via `GraphDB.get_session()`. Each session is isolated and concurrency-safe.
- (C) Keep `run_tick(session, ...)` signature and reuse the passed session under a lock — effectively keeping it serial.
**Decision:** Option B. `GraphDB` and `Settings` are injected at construction. `run_tick` ignores the caller-supplied `_session` (kept for `BaseEngine` interface compatibility) and opens per-task sessions. `asyncio.Semaphore(settings.MAX_CONCURRENT_TICKS)` bounds concurrent open sessions.
**Why:** Neo4j connection pools are designed for this pattern. Option A would violate SRP. Option C yields no speedup.
**Consequence:** `dependency_singletons.get_memory_consolidation_engine` now passes `graph_db` and `settings`. Callers in `tick_scheduler` that pass a session continue to work.

## DEC-058: currency_writer.py waived at 327 lines (SEV-08 atomicity)
**Date:** 2026-06-04
**Context:** SEV-08 added execute_currency_transfer_in_tx (~90 lines) to currency_writer.py, pushing it from ~233 to 327 lines.
**Decision:** Waiver granted. Splitting is artificial.
**Why:** execute_currency_transfer_in_tx shares _try_replay and _raise_transfer_failure private helpers with transfer_currency_atomic. Extracting it to a new module would require exposing those helpers or duplicating 40 lines of error-handling logic. The cohesion is high — all three functions implement the same atomic-write contract, differing only in who owns the transaction boundary. SEV-23 may revisit.
**Consequence:** make check-rules-update must baseline currency_writer.py. SEV-23 may split if a natural boundary is found.

## DEC-063: Canonical module docstring format — Layer/Purpose/Dependencies/Used by (SEV-32)
**Date:** 2026-06-04
**Context:** 154/336 src files lacked the mandatory `Layer:` field; 25 `__init__.py` lacked `Public surface:`. Old format used "Does NOT:" and "Dependencies injected:" without an explicit layer tag.
**Decision:** All src/ files now carry the canonical format (`Module:/Package:`, `Layer:`, `Purpose:`, `Dependencies:`, `Used by:`, `Public surface:` for __init__.py). `scripts/docstring_audit.py` enforces this as a CI gate; added to `make check` after `check-layers`.
**Why:** `Layer:` makes architectural membership explicit in every file header without parsing imports. LLM context retrieval carries layer/coupling context per chunk.
**Consequence:** `scripts/migrate_docstrings.py` ran a one-shot migration 2026-06-04. Placeholder values `(auto-detected — review)` in `Purpose:` / `Dependencies:` / `Used by:` for migrated files should be filled in over time. `check-docstrings` now blocks any new file that omits the fields.

## DEC-062: chapter_engine.py waived at ~322 lines (SEV-23 split)
**Date:** 2026-06-04
**Context:** SEV-23 extracted `_rule_based_label` → `chapter_labeler.py`, reducing chapter_engine.py from 347 to 322 lines. Still 22 lines over the 300-line limit.
**Decision:** Waiver. The remaining 322 lines are a single cohesive `ChapterEngine` class; all six async methods share injected state (`_llm`, thresholds). Further splitting (e.g., extracting `_link_recent_events`) would move methods into module-level helpers that need to accept `self`-equivalent arguments, adding noise without encapsulation benefit.
**Consequence:** `make check-rules` baseline must include chapter_engine.py. Will revisit if the class grows.

## DEC-064: Quest `completed` terminal state — owner decision required (SEV-36 deferred)
**Date:** 2026-06-04
**Context:** SEV-36 deferred this question: is the `completed` quest state irreversible? Some designs allow quest chains where a "completed" sub-quest can be re-entered (e.g., repeatable quests), while others treat completion as a terminal, one-way state.
**Decision:** Deferred — owner decision required before implementation. Do not gate any logic on `completed` finality until this is resolved.
**Why:** Changing the semantics post-implementation would require graph migrations and engine rework; better to decide up front.
**Consequence:** `quest_generation_engine.py` should not add `completed → terminal` constraints until this is answered. Log a follow-up task when owner decision is received.

## DEC-065: `BASE_DISTORTION_RATE` alias skipped — use existing `GOSSIP_DISTORTION_BASE` (SEV-36)
**Date:** 2026-06-04
**Context:** SEV-36 brief asked to add `BASE_DISTORTION_RATE: float = 0.3` to `config.py`. `GOSSIP_DISTORTION_BASE: float = 0.3` already exists with identical semantics.
**Decision:** No new field added. `compute_distortion_probability` takes a `base: float` parameter; callers pass `settings.GOSSIP_DISTORTION_BASE`.
**Why:** Adding a duplicate config key with a different name would create ambiguity and require migration of all callers.
**Consequence:** Future callers must use `settings.GOSSIP_DISTORTION_BASE`, not `BASE_DISTORTION_RATE`.

## DEC-066: api_seeder.py waived at 306 lines (SEV-40)
**Date:** 2026-06-04
**Context:** SEV-40 added resolve_api_key() + get_logger import to api_seeder.py, pushing it from ~280 to 306 lines. The R002 baseline entry (pre-existing over-300) is now an R001 NEW violation because those 2 baseline resolutions were also counted.
**Decision:** Waiver. All content is cohesive CLI seeder logic (seed data wiring, HTTP orchestration, key resolution). Splitting resolve_api_key to a new module is artificial — it directly uses the same logger and is called only once.
**Consequence:** make check-rules-update must baseline api_seeder.py.

## DEC-068: Multi-tenant isolation is deployment-level, not graph-level (SEV-12 closed)
**Date:** 2026-06-04
**Context:** SEV-12 flagged the absence of `world_id` on every Neo4j node as a multi-tenant data-integrity risk. The proposed fix was to add a composite key `(world_id, id)` to every node and thread `world_id` through all Cypher and auth.
**Decision:** Do not add `world_id` to the graph schema. The intended deployment model is one NPC Engine instance (Docker stack + Neo4j) per game studio / per game installation. Isolation is infrastructure-level: each studio runs their own container stack locally as part of their game distribution. A single graph contains exactly one game world.
**Why:** Adding `world_id` everywhere solves a problem that doesn't exist in the target deployment model and would add blast-radius changes to every query, route, and seeder for no benefit.
**Consequence:** SEV-12 is closed as N/A. ISSUE-055 (client-supplied stable ids) dependency on SEV-12 is also resolved — the multi-tenant coupling no longer applies.

## DEC-067: dialogue_handler.py waived at 312 lines (SEV-19)
**Date:** 2026-06-04
**Context:** SEV-19 added resolve_log_prompts() (6-line helper) to dialogue_handler.py, pushing it from ~306 to 312 lines. All content is the single DialogueHandler orchestration class and its helpers.
**Decision:** Waiver. Extracting a 6-line helper into a separate module creates more indirection than value. The cohesion is high — resolve_log_prompts reads Settings fields used throughout the same file.
**Consequence:** make check-rules-update must baseline dialogue_handler.py.

## DEC-069: `observability/` is a non-code asset directory, excluded from the layer-rank model (L2-02)
**Date:** 2026-06-04
**Context:** `src/npc_engine/observability/` is absent from the CLAUDE.md layer model. The final review (L2-02) found it contains zero Python — only `README.md`, `staging_alert_rules.yaml`, `staging_dashboard.json`. It imports nothing and is imported by nothing, so `scripts/check_layers.py` (which walks `*.py`) never sees it and it cannot produce a layer violation.
**Decision:** Treat `observability/` as a non-code asset directory (dashboards/alert rules), explicitly outside the import-rank layer model — the same status as `prompts/`. No rank is assigned because it ships no Python. If Python ever lands there (e.g. a metrics exporter), assign it rank 1 (config/utils peer) and revisit.
**Consequence:** The layer model need not enumerate `observability/`. A reviewer finding an unranked `src/npc_engine/` subdir should consult this entry.

## DEC-070: Dialogue context = pinned-core + ranked pool (supersedes the tier-A/B/C budget model)
**Date:** 2026-06-05
**Context:** ISSUE-059 — tier-A "mandatory" context is unbounded, so a knowledge-rich NPC overflows `prompt_token_budget` and `context_budget_enforcer.py:76-83` raises → dialogue silently degrades to canned. Root cause: unbounded, accumulating categories (memories, beliefs, secrets, knows_about facts) were placed inside a never-trim tier. Decided during the expansion review (EXP-30).
**Decision:** Replace the tier-A/B/C model with two classes. (1) A **pinned set**, never dropped: `world`, `emotion`, persona, the **session window** (bounded, last-N turns), and `active_quest` — each carrying an explicit `pinned: bool` flag on `ContextItem`. (2) A single **ranked pool** of everything else, filled by `priority × relevance` until the budget is hit, dropping from the bottom. Every context item already carries a `priority` (`context_builder.py:272-359`); the tiers were only coarse priority bands.
**Why:** The only un-droppable set is now small and **bounded by construction** (persona + windowed session, not an accumulating fact list), so a "Tier-A exceeded" failure cannot occur. Graceful degradation = dropping the lowest `priority × relevance` pool items, never collapsing the whole turn to canned. The guarantee is explicit in the model (the `pinned` flag), not implied by a tier label.
**Consequence:** EXP-30 reframed; edits `retrieval/context_builder.py` + `retrieval/context_budget_enforcer.py`. No graph schema change (`pinned` is an in-memory model field). The session window must stay bounded so even the pinned set cannot exceed budget. Closes the design question in ISSUE-059; implementation pending.

## DEC-071: Add `PART_OF` location edge + `location_writer.py` (ISSUE-057 approved)
**Date:** 2026-06-05
**Context:** Locations are flat nodes; there is no `PART_OF` edge and no `location_writer.py` (only `location_graph_queries.py`). ISSUE-057 / L7-02 flagged this as the blocker for nested geography (market → village → duchy → … → world), region-scoped gossip, travel time, and area-of-effect events. Reviewed under EXP-87.
**Decision:** Approved. Add a `PART_OF` directed base edge (`location → location`) to `type_registry/base_edges/`, and add the missing `graph/location_writer.py` (graph-owned, `AsyncSession`-injected, accepting an optional `parent_id`). Update `demo_game/seed.py` + eval seeders to wire the hierarchy and add retrieval helpers for ancestor/descendant traversal.
**Why:** A real, growable world (a near-term demo/product ambition) needs nested geography; flat locations cap the world's richness and block region-scoped features. This is the standard pure-additive `type_registry` extension + the missing writer module.
**Consequence:** Graph schema gains one base edge. ISSUE-057 unblocked (implementation pending). EXP-87 hierarchy half is greenlit; flat NPC/location demo expansion does not depend on it.

## DEC-072: NPCs learn facts via a single-pass `learned_facts` output written to `belief` nodes (no `LEARNED_FROM` edge, no second LLM pass)
**Date:** 2026-06-05
**Context:** EXP-53 (dialogue-driven knowledge learning) originally proposed a second LLM extraction pass and a new `LEARNED_FROM` base edge. Both were challenged in review as too costly / redundant with existing vocabulary.
**Decision (three parts):** (1) **No second LLM pass** — extend the *existing* dialogue structured-output schema with an optional `learned_facts` list so the model emits learned facts in the same single pass (parsed by `response_parser`). (2) **No new edge** — player-taught facts land on `belief` nodes via the existing `BELIEVES` edge; add only optional provenance fields `source_character_id`, `learned_at_tick`, `confidence` to `believes.yaml`. Events stay reserved for world-happenings (`event.yaml` already has `event_type`/`src_character_id`). (3) **Player-sourced knowledge is legitimate** — the anti-hallucination eval (EXP-32) must score a repeated player-taught fact as *grounded*, authorized by `source_character_id = player_demo`.
**Why:** A second pass would be a per-turn latency/cost hit on the gameplay path; the graph already models provenance on `KNOWS_ABOUT`/`KNOWS_SECRET`/`BELIEVES_RUMOR`, so a dedicated `LEARNED_FROM` edge is redundant. Routing arbitrary asserted facts to `belief` (not `event`) keeps the world-event model clean.
**Consequence:** EXP-53 drops from L to M. The only schema touch is 3 optional fields on `believes.yaml`. A new `graph/knowledge_writer.py` (graph-owned) does the write. Implementation pending; gate behind EXP-32 so the loop is measured.
**Fact visibility & contradictions (resolved 2026-06-05):** (a) learned facts **CAN be gossiped onward** — a player-taught `belief` is a valid gossip source and propagates through the gossip engine with normal per-pair distortion (the player can seed a rumor by telling one NPC). (b) When a player-taught fact **contradicts** a known one, **keep both** and link with the existing `CONTRADICTS` edge (`contradicts.yaml`); at answer time prefer the higher-confidence / higher-trust-source belief, but never overwrite — an NPC may voice the conflict. This binds EXP-53 to the gossip expansion (EXP-15/16).

## DEC-073: EXP-10 proactive dialogue WS `proactive_line` message shape approved
**Date:** 2026-06-09
**Context:** EXP-10 (proactive NPC-initiated dialogue) requires the NPC to push an unsolicited line
over the existing WebSocket dialogue path. The message type and shape were "pending DECISIONS" in
the EXPANSION_INDEX carry-forward notes before dispatch could be authorized.
**Decision:** The new WS server-push message type `proactive_line` is approved with this shape:
```json
{"type": "proactive_line", "npc_id": "<str>", "content": "<str>", "reason": "<str>", "tick": <int>}
```
The client receives it on the same NPC dialogue socket. It is additive — no existing message types
are changed. `reason` is one of `["unshared_memory", "unmet_need", "pending_rumor"]` (a `Literal`).
**Why:** A new message type on an existing socket is the smallest viable API surface for proactive
push. Reusing the existing socket avoids a new WebSocket route. The shape mirrors `dialogue_response`
(npc_id + content) with an added `reason` field so clients can display or ignore the trigger.
**Consequence:** EXP-10 is unblocked for dispatch. `engines/proactive_dialogue/` is a new module;
no edits to `dialogue_handler.py`. The scheduler registration edits `tick_scheduler.py`. The WS
push edits `api/routes/dialogue_ws.py` — that is the one existing file EXP-10 must touch.
EXP-10 conflicts with EXP-33 on `main.py` (both add router registration); they must be sequenced
(EXP-33 first, then EXP-10 in the next batch after EXP-33 is merged).

## DEC-078: quest_lifecycle_engine.py split into 3 classes (supersedes DEC-044, fixes ISSUE-077)
**Date:** 2026-06-09
**Context:** `quest_lifecycle_engine.py` is 645 lines — the DEC-044 waiver said "acceptable until
Phase 3 requires adding quest-type-specific transition logic." Batch D tech-debt pass (ISSUE-077)
authorises the split. Analysis shows a simple 2-file split (lifecycle + rewards) leaves the
lifecycle file at ~447 lines — still over 300 — because 6 public methods with mandatory
Args/Returns/Raises docstrings and keyword-only signatures each consume 50+ lines. A 3-file
split is required.
**Split boundary:**
- `quest_lifecycle_engine.py` — `QuestLifecycleEngine`: `accept_quest`, `update_objective`,
  `evaluate_completion` + private helpers (`_require_state`, `_emit_lifecycle_event`,
  `_persist_state_and_event`). ~290 lines. Callers in `quest_handler.py` and `interaction.py`
  use only these methods and need no changes.
- `quest_offer_service.py` — `QuestOfferService`: `offer_draft_quest`, `offer_quest`. ~210 lines.
- `quest_reward_router.py` — `QuestRewardRouter`: `apply_rewards`, `_apply_rewards_in_tx`,
  `_collect_delivery_items_in_tx`. ~250 lines.
**Callers updated:** `api/routes/quest.py` offer routes inject `QuestOfferService`; reward route
injects `QuestRewardRouter`. `api/dependencies_engines.py` gains two new factory functions.
`quest_handler.py` and `api/routes/interaction.py` are unchanged.
**Why:** Three independent classes with SRP: offer = state creation, transitions = state machine,
rewards = economic settlement. Each is independently testable. No delegation indirection.
**Consequence:** DEC-044 superseded. ISSUE-077 closed. Test imports updated for offer and reward
test modules.

## DEC-080: per-world content-rating override deferred (Phase 16 S16.1)
**Context:** Phase 16 introduces a configurable content ceiling (`ContentRating = Literal["everyone", "teen", "mature"]`).
The plan called for per-world overrides so different game worlds can have different ceilings.
**Decision:** Defer per-world override. `ContentRatingResolver.resolve()` always returns the global
`Settings.CONTENT_RATING` value. The two viable override mechanisms are: (a) store the ceiling as a
property on the world Neo4j node (requires graph schema change + migration), or (b) declare it in the
game schema YAML (requires schema extension and a loader change). Neither is trivially safe.
**Why:** Adding a new Neo4j property requires a schema bootstrap change and a migration run against
all existing world nodes. Adding it to the YAML schema requires changes to `schema/game_schema_loader.py`
and the context pipeline. Both touch more than the services layer and risk regressions during a demo sprint.
**Consequence:** Studios set one ceiling per deployment via the `CONTENT_RATING` env var. Per-world
differentiation deferred to a follow-up session once the schema decision is confirmed.

## DEC-079: intent_queries.py accepted over 300-line limit (~334 lines, Phase 14 S14.1+S14.2)
**Context:** `graph/intent_queries.py` contains all Cypher constants and async query functions
for Phase 14 intent operations: location reads (S14.1) and queue operations (S14.2). At 334 lines
it exceeds the 300-line hard limit.
**Why:** The 300-line limit targets wide modules with unrelated concerns. This file has one
concern — PendingIntent Cypher — and is long because it hosts 12 async query functions each
with mandatory docstrings and try/finally consume patterns. Splitting into
`intent_read_queries.py` + `intent_queue_queries.py` would create artificial separation of
functions that share no state and have identical structural patterns. All existing Cypher-only
files in the codebase (e.g., `quest_verification_queries.py`) follow this single-file pattern.
**Consequence:** R001 baseline entry added for `intent_queries.py`. No callers need changes.


## DEC-081: dialogue_handler.py accepted over 300-line limit (~321 lines, Phase 16 S16.3)
**Context:** Phase 16 S16.3 added output moderation wiring (`_apply_output_ceiling`, `_build_llm_client`)
and the associated `effective_rating` parameter, growing the file from ~303 to ~321 lines.
**Decision:** Accept the R001 baseline entry for `dialogue_handler.py`. A 300-line waiver already
existed since DEC-072. The two new private helpers extracted to satisfy R006 are cohesive with the
handler and would harm readability if split to a separate module.
**Why:** `DialogueHandler` is the central orchestrator for the dialogue turn pipeline. Every method
belongs to the same class and concerns the same single responsibility: executing a dialogue turn.
Splitting across files would require dependency injection of the sub-object, adding indirection with no
architectural benefit. All growth since DEC-072 is justified dialogue-pipeline code.
**Consequence:** R001 baseline entry added for `dialogue_handler.py`. No callers need changes.


## DEC-082: anti_hallucination_runner.py accepted at 314 lines (300-line exception)
**Date:** 2026-06-10
**Context:** EXP-32 runner is 314 lines total; 266 non-blank/non-comment lines. The extra lines are
mandatory module + function docstrings (per CLAUDE.md), the `_REFUSAL_KEYWORDS` constant tuple, and
blank-line separation between the 8 public/private functions.
**Decision:** Accept the overage. Splitting would require a separate `_classifiers.py` or `_models.py`
with no shared state — purely artificial separation.
**Why:** The file has one concern (run the anti-hallucination fixture and aggregate results) and all
14 extra lines are either blank separators or docstring content required by CLAUDE.md. No callers
need changes.
**Consequence:** R001 baseline entry added for `evals/anti_hallucination_runner.py`.


## DEC-083: EXP-51 — GOAL_TARGETS base edge approved + action priority system (0-100 scale)
**Date:** 2026-06-10
**Context:** EXP-51 NPC goal-formation engine needs to record which entity a goal is aimed at.
User approved a new base edge. User also specified a general priority system applicable to all
action-dispatching engines (routine, planning, quests).
**Decision:**
1. New `base_edges/goal_targets.yaml`: `edge_type: GOAL_TARGETS`, `src_type: goal`,
   `dst_type: [character, location, faction, item]`, `fields: priority: {type: int, required: true, range: [0,100]}`.
   Priority is the weight of this target *relative to other targets of the same goal* — separate from goal urgency.
2. Action priority system lives in `engines/planning/action_priority.py` as named integer constants
   (`ROUTINE_PRIORITY = 50`; any goal with `urgency > ROUTINE_PRIORITY` overrides routine; goals with
   `urgency <= ROUTINE_PRIORITY` only fire in unscheduled windows). Range is 0-100; no hidden magic numbers.
   The same scale is available to quest-trigger engines and future dispatchers.
**Why:** Goals that target multiple entities (e.g. "make allies") need a queryable, Cypher-traversable
link, not a string field. The existing `goal.target_id: str` field is not a graph edge and cannot express
multi-target or edge-level priority. The priority system makes routine/planning precedence explicit and
reusable rather than encoded as an opaque comparison inside one engine.
**Consequence:** One new YAML file in `base_edges/`. `goal.target_id` field remains but is deprecated
in favor of GOAL_TARGETS edges; will be removed in a future clean-up pass.


## DEC-084: EXP-14 — Persist NPC emotion to character node (Neo4j write-through); Redis deferred
**Date:** 2026-06-10
**Context:** `EmotionStore` is in-memory only. User approved persisting to Neo4j via additive fields on
`character.yaml`. User also flagged that emotions are too volatile (label flip every dialogue turn).
Redis deferred to same phase as Unity/Unreal SDK integration.
**Decision:**
1. Add 4 optional fields to `base_nodes/character.yaml`:
   `emotion_valence: {type: int, required: false, range: [-100, 100]}`,
   `emotion_arousal: {type: int, required: false, range: [0, 100]}`,
   `emotion_mood_label: {type: str, required: false}`,
   `emotion_updated_at_tick: {type: int, required: false}`.
   All optional — existing character nodes without these fields continue to work.
2. New `graph/emotion_writer.py` writes emotion state to the character node after each update.
   `EmotionUpdater` accepts an optional `EmotionGraphWriter` via DI; only injects in production.
3. New `engines/emotion/emotion_bootstrap.py` reads emotion fields from graph on boot, populates store.
4. Add `_MIN_AROUSAL_TO_SHIFT_LABEL = 20` constant to `VadEmotionModel`: label only changes when
   arousal >= this threshold, preventing flip-flopping on low-intensity events.
5. Redis: deferred — log ISSUE for the same phase as Unity/Unreal integration.
**Why:** Additive optional fields are zero-risk for existing Cypher queries (Neo4j ignores unknown fields
on existing nodes). Write-through rather than snapshot-on-shutdown gives live persistence without crash-
state loss. Label-inertia via arousal threshold is the minimal, testable fix for the volatility concern.
**Consequence:** `character.yaml` grows by 4 optional fields. No existing queries need changes. Redis
tracked as deferred in ISSUES.md.


## DEC-085: EXP-19 — UNLOCKS base edge + LLM-generated quest chains, slot-validator grounded
**Date:** 2026-06-10
**Context:** Quests are isolated and linear. User approved a new edge type to chain quests.
User also approved LLM-generated follow-on quests grounded by existing slot_validator.
**Decision:**
1. New `base_edges/unlocks.yaml`: `edge_type: UNLOCKS`, `src_type: quest`, `dst_type: quest`,
   `fields: on_outcome: {type: str, required: true}`. `on_outcome` is enforced as
   `Literal["complete", "fail", "expire"]` in the Python model (YAML stores str for registry compat).
2. New `engines/quest/quest_chain_resolver.py` injected into `QuestLifecycleEngine.__init__`.
   After evaluate_completion transitions to COMPLETED or FAILED, the resolver queries UNLOCKS edges
   and calls `quest_offer_service.offer_quest` for each matching next quest.
   Slice-1 uses only hand-authored UNLOCKS edges (seeded via `demo_game/seed.py` for 2 demo chains).
   Slice-2 (separate brief): if no UNLOCKS edge exists, call `quest_generation_engine` with chain context,
   validate slots, offer on success.
3. New `graph/quest_chain_queries.py` — Cypher query for outgoing UNLOCKS edges.
**Why:** Edge-modeled chains are Cypher-traversable ("find all quests reachable from A"). String fields
cannot express multi-outcome branches. LLM generation deferred to slice-2 to keep slice-1 scope clean
and testable deterministically.
**Consequence:** One new YAML file in `base_edges/`. `QuestLifecycleEngine` accepts an optional
`QuestChainResolver` via constructor — existing callers pass `None` (no chains); demo seed wires chains.

## DEC-086: EXP-19 — quest_lifecycle_engine.py 300-line waiver
**Date:** 2026-06-10
**Context:** After EXP-19 added the optional chain_resolver param and resolver call,
`quest_lifecycle_engine.py` reached 305 lines. The file was 285 lines at HEAD before
this batch; splitting it would require extracting the `evaluate_completion` body into a
helper module with no natural cohesion boundary — the state machine reads better as one unit.
**Decision:** Accept 305-line overage under the established split-would-be-artificial
exception (CLAUDE.md). No further line additions without a re-split.
**Consequence:** File remains as-is. Next editor must split before adding anything new.

## DEC-088: S20.2 — generic node/edge services stay `dict[str, Any]`; only NPCStateResponse is typed
**Date:** 2026-06-11
**Context:** Phase 20 S20.2 asks to (a) replace raw `dict`/`list[dict]` in `NPCStateResponse`
with typed sub-models and (b) type `generic_node_service.upsert_node/patch_node` and
`generic_edge_service.upsert_edge` against registry-validated Pydantic models instead of
`dict[str, Any]`.
**Options considered:**
  1. Type the generic services' payload/return as a fixed Pydantic model. The registry is
     dynamic — node/edge property sets are defined at runtime from YAML contracts via
     `create_model`, and the write path validates through `validate_node_payload` (returns a
     mutated `dict`, not a model). A single fixed model cannot describe an open registry; a
     per-type generated model would change the return contract of every dynamic graph route.
  2. Keep `dict[str, Any]` for the generic services (registry-dynamic boundary) and deliver
     only the NPCStateResponse typing, which has a stable, known shape.
**Decision:** Option 2. NPCStateResponse gains `CharacterNode`/`RelationEdge`/`EventNode`
sub-models (`api/response_models/npc_state.py`). The generic graph services remain
`dict[str, Any]` — consistent with the Phase 20 Notes allowance ("dynamic graph routes may use
`OkEnvelope[dict[str, Any]]` where a tighter model is impractical; the registry is dynamic").
**Why:** Forcing a static model onto an intentionally-dynamic registry trades a real schema for
a false one and churns every graph-route signature for no client benefit. The dynamic routes
already document their payloads via the registry's own contract YAML.
**Consequence:** `graph_admin`/`graph` dynamic routes use `OkEnvelope[dict[str, Any]]` in the
S20.4 sweep. If the registry ever freezes to a closed node set, revisit and generate typed models.

## DEC-089: S21.1 — main.py split into main + router_registry + exception_handlers (resolves DEC-060)
**Date:** 2026-06-11
**Context:** Phase 21 S21.1 (SEV-23, file-size cluster) un-grandfathers `main.py`, which DEC-060
parked in the R001 baseline at 361 lines "pending SEV-23". It had since grown to 400 lines.
The file mixed three responsibilities: the FastAPI app factory + lifespan (startup/shutdown
orchestration), four ErrorEnvelope exception handlers, and the registration of ~40 route routers.
**Options considered:**
  1. Waiver (keep over 300). Rejected — DEC-060 explicitly deferred to this step; a waiver would
     defeat the purpose and leave R001 in the baseline.
  2. Extract the `lifespan` context manager to its own module. Rejected — `lifespan` resolves many
     module-global names (`get_graph_db`, `EmbeddingReconciler`, …) that `test_main_reconciler_lifespan.py`
     monkeypatches via the `main` namespace; moving it would silently break those patches.
  3. Extract the two zero-entanglement seams: route-router imports + `include_router` calls →
     `api/router_registry.py` (`register_routers(app, settings)`, split into public/admin helpers to
     stay under the 40-line function limit); and the four exception handlers + their registration →
     `api/exception_handlers.py` (`register_exception_handlers(app)`). `lifespan` stays in `main.py`.
**Decision:** Option 3. `main.py` drops from 400 → 217 lines; both new files are well under 300.
The split boundary is by responsibility (app assembly vs. routing table vs. error mapping), each
new module is single-purpose, and no test monkeypatch targets move.
**Why:** Route registration and error-envelope mapping are mechanical tables with no dependency on
lifespan state — the cleanest natural seams. Keeping `lifespan` in `main` preserves the existing
`main.<name>` monkeypatch surface (no test behaviour change).
**Consequence:** `R001|src/npc_engine/main.py` and `R006|…main.py::create_app` removed from the
baseline. `test_error_envelope_sev33.py` now imports the handlers from `api/exception_handlers.py`
(their new home). DEC-060 resolved.

## DEC-090: S21.1 — middleware_helpers.py split; observability helpers → auth/request_observability.py
**Date:** 2026-06-11
**Context:** Phase 21 S21.1 (SEV-23). `auth/middleware_helpers.py` was 333 lines and mixed two
concerns: (a) auth/routing/idempotency-key validation helpers and (b) request observability
(correlation-id resolution, metrics, structured request logging).
**Options considered:**
  1. Waiver. Rejected — unlike a flat catalog, this file has a real SRP seam.
  2. Extract the observability group (`_resolve_request_id`, `_record_request_observability`,
     `_finalize_validation_failure_response` + their metric/request-id constants and LOGGER) into a
     new `auth/request_observability.py`. The two groups share no symbols; the only importer of the
     moved functions is `middleware.py` (no test imports the privates), so the blast radius is one
     import statement.
**Decision:** Option 2. `middleware_helpers.py` drops from 333 → 229 lines; `request_observability.py`
is 118 lines. `middleware.py` now imports the three observability functions from the new module.
**Why:** Observability (metrics/logging) and auth/idempotency validation are independent
responsibilities with no shared state — a clean, low-risk cut that genuinely shrinks R001.
**Consequence:** `R001|src/npc_engine/auth/middleware_helpers.py` removed from the baseline.

## DEC-091: S21.1 — errors.py kept at 329 lines (split would be artificial; waiver)
**Date:** 2026-06-11
**Context:** Phase 21 S21.1 (SEV-23). `utils/errors.py` is 329 lines: a flat catalog of ~35
`@dataclass(frozen=True)` exception types all subclassing `StructuredNPCSystemError`, imported as
`from npc_engine.utils.errors import X` across nearly every package.
**Options considered:**
  1. Split by domain (graph / llm / quest / economy / schema errors) into peer modules, with
     `errors.py` re-exporting all names. Adds ~5 files plus an exhaustive re-export hub; every error
     class must stay importable from `utils.errors`, so the public surface is unchanged but the file
     count and an error-prone re-export list grow for no encapsulation gain. Highest blast radius in
     the codebase (every importer of any error).
  2. Keep the flat catalog and accept the overage with a documented waiver (CLAUDE.md "if a split
     would be artificial, write a justifying comment + DECISIONS entry").
**Decision:** Option 2, consistent with DEC-077 (config.py flat-settings) and DEC-073
(context_budget_enforcer). One class per error, one shared base, one import path — splitting trades a
cohesive registry for indirection.
**Why:** The exception catalog is a single conceptual unit; the 300-line rule exists to prevent
monolithic *logic*, not to fragment a flat list of 3-field dataclasses.
**Limit:** Do not grow further without a real split. If a new error *family* with shared behaviour
(not just fields) appears, extract that family to its own module then.

## DEC-087: ✅ APPROVED — graph/-owned transaction coordinator for engine-owned writes (S21.4 / SEV-30 / ISSUE-058)
**Status:** ✅ APPROVED 2026-06-11 — Option 1 (callback unit-of-work coordinator).
**Resolved open questions:** (1) standardize on the callback coordinator `run_in_tx`. (2) keep the
existing `quest_engine_helpers` `hasattr(session, "begin_transaction")` guard engine-side — not folded
into the coordinator. (3) rollback semantics: coordinator rolls back on any exception and re-raises the
**original, unwrapped** exception, mirroring today's `async with tx:` behaviour.
**Date:** 2026-06-11
**Context:** CLAUDE.md (strict): *"`graph_writer.py` is the only file that opens and commits
transactions"* and *"No Neo4j queries outside `graph/`."* Five engine files currently own the
transaction lifecycle directly — `session.begin_transaction()` … N `graph/` writer calls on `tx` …
`tx.commit()`:
  - `engines/events/event_handler.py` (1 tx: upsert_event + awareness + reputation + routine overrides + world-state)
  - `engines/faction_politics/faction_politics_engine.py` (2 tx sites)
  - `engines/quest/quest_lifecycle_engine.py` (2 tx sites)
  - `engines/quest/quest_offer_service.py` (1 tx site)
  - `engines/quest/quest_reward_router.py` (2 tx sites)
(The step text named only the first three; `quest_offer_service` + `quest_reward_router` also qualify
and must be in scope.) These are grandfathered as R005 in `rules_baseline.txt`. The transactions are
**multi-statement units of work**: each wraps several `graph/` writer calls that must commit atomically,
often interleaved with engine-side decisions (rule matching, severity branches, per-character loops).
**Options considered:**
  1. **Callback unit-of-work coordinator** (recommended). Add `graph/transaction_coordinator.py`
     exposing `async def run_in_tx(session, work: Callable[[AsyncTransaction], Awaitable[T]]) -> T`
     that owns `begin_transaction()` / `commit()` / rollback-on-error. Each engine passes an
     `async def _work(tx): …` closure containing only the existing writer calls; the engine no longer
     touches `begin_transaction`/`commit`. Minimal behaviour change, preserves atomic boundaries,
     keeps engine decision logic where it is.
  2. **Per-use-case named coordinators in `graph/`** (e.g. `graph/event_emit_coordinator.py`,
     `graph/quest_reward_coordinator.py`). Moves the whole unit of work into `graph/`. Cleaner layering
     but relocates engine decision logic (rule matching, severity branches) into `graph/`, which would
     itself violate "no domain logic in graph/" — large, invasive, and blurs the layer it intends to fix.
  3. **Waiver** (carve-out permitting engine-owned tx for multi-writer units). Cheapest, but concedes a
     strict layer rule permanently and leaves `tx` plumbing scattered across engines.
**Recommendation:** Option 1. It satisfies the strict rule (`begin_transaction`/`commit` live only in
`graph/`), is mechanical and low-risk (closure extraction, no logic moves), and the atomic boundary of
each existing `async with tx:` block maps 1:1 to one `run_in_tx(...)` call. The R005 baseline entries for
the five engine files are then removed after `rg "begin_transaction|\.commit\(" src/npc_engine/engines`
returns 0.
**Open questions for the approver:**
  - OK to standardize on the callback coordinator (Option 1), or prefer named per-use-case coordinators?
  - Is `quest_engine_helpers._require_tx_capable_session` (the `hasattr(session, "begin_transaction")`
    guard) folded into the coordinator, or kept engine-side?
  - Rollback semantics: coordinator rolls back on any exception and re-raises the original (vs. wrapping
    in a domain error)?
**Consequence if approved:** new `graph/transaction_coordinator.py`; five engine files refactored to
closures; R005 baseline shrunk by 5; ISSUE-058 item (2) closed. **Not started** — this entry is the gate.

## DEC-092: world-state DB access relocated from `world/` into `graph/` (S21.4 follow-up, ISSUE-058 item 3)
**Date:** 2026-06-11
**Context:** `world/world_reader.py` (`get_world_state`) and `world/world_writer.py`
(`upsert_world_state`, `upsert_world_state_tx`) held raw Cypher (`MATCH`/`MERGE` on `WorldState`),
the last two R005 (Cypher-outside-`graph/`) baseline entries. ISSUE-058 item (3) offered two paths:
relocate, or add a carve-out permitting each graph-peer package its own-label Cypher.
**Options considered:**
  1. Carve-out waiver: document that `world/` (a rank-2 graph-peer) may own its world-state Cypher.
     Inconsistent — every other domain's node access already lives in `graph/<x>_reader|writer.py`
     (e.g. `graph/character_reader.py`, `graph/event_writer.py`); `world/` was the lone exception.
  2. Relocate the DB access into `graph/`, leaving `world/` with only the model + time utils.
**Decision:** Option 2 (per user direction). New `graph/world_state_reader.py` (`get_world_state`) and
`graph/world_state_writer.py` (`upsert_world_state`, `upsert_world_state_tx`); moved verbatim, then the
13 call sites repointed and `world/world_reader.py` + `world/world_writer.py` deleted. `world/` now holds
only `world_state.py` (model), `time_utils.py`, `world_time_service.py`. The relocated `upsert_world_state`
(previously R006-baselined and grandfathered) was refactored under the 40-line limit by extracting shared
`_world_state_write_params` / `_world_state_from_record` helpers (also de-duplicating the two writers),
so no R006 debt was relocated.
**Why:** Node read/write is `graph/` responsibility ("Neo4j write operations, schema enforcement");
`world/` is "world-state data model + time utils". The split now matches every other domain.
**Consequence:** **R005 baseline is empty** (all Cypher-outside-`graph/` debt cleared). Imports of
`get_world_state`/`upsert_world_state*` now come from `graph.world_state_*`. ISSUE-058 fully resolved.

---

## DEC-093: S22.1 — GraphRAG seed label filter is `:Event` only (no `:Knowledge` label exists)
**Date:** 2026-06-11
**Status:** ✅ ACCEPTED (small choice, noted per CLAUDE.md token-efficiency rule)
**Context:** ISSUE-056 / roadmap S22.1 asked for a `(seed:Event|Knowledge)` label filter on
`_CYPHER_EXPAND_SEEDS` to stop the GraphRAG expansion full-node scan. Two deviations from the
literal roadmap text surfaced during implementation:
  1. **No `:Knowledge` label exists** in the schema. The node labels are enumerated in
     `graph/labels.py` (Character, Event, Secret, Location, Faction, Quest, Item, WorldState);
     `grep -r ":Knowledge"` across `src/` returns zero. GraphRAG seeds come exclusively from
     `graph_reader.get_known_event_ids_for_npc` (the NPC's `KNOWS_ABOUT` → **Event** set), so the
     only real seed label is `:Event`.
  2. **The Cypher no longer lives in `retrieval/graph_rag.py`.** It was relocated to
     `graph/graph_rag_queries.py` in Phase 21 (S21.4 Cypher migration, DEC-087/092). The roadmap's
     exit string `rg "MATCH \(seed\)" src/npc_engine/retrieval/graph_rag.py` is therefore stale.
**Decision:** Filter the seed match to `:Event` only, using the `EVENT` constant from
`graph/labels.py` (no raw label string). Apply the fix in `graph/graph_rag_queries.py` (the
correct post-S21.4 location). Adding a non-existent `:Knowledge` alternation would be a misleading
magic label that matches nothing.
**Why:** Seeds are provably Event-only; an `Event|Knowledge` filter would imply a node type the
schema does not have. If a `Knowledge` label is introduced later, extend the filter then.
**Consequence:** Expansion anchors only on `:Event` seeds; full-node scan eliminated. The roadmap
S22.1 exit is reinterpreted to target `graph/graph_rag_queries.py` (noted in the ROADMAP step).

---

## DEC-094: ✅ APPROVED — event-time fields on Memory/Event (`occurred_at_game_time` + `is_historical`)
**Date:** 2026-06-11
**Status:** ✅ APPROVED (2026-06-11, Option A) — gates ROADMAP S26.3 (Phase C). Approved even though A+B
already fixed both henryk cases live, because the data-model gap remains (the seeder stamps every memory
at "now" and `recency_score` mis-ranks ancient memories as fresh). Implementing as hardening.
**Context (ISSUE-093):** `Memory` and `Event` nodes carry only `created_at_game_time` (when the memory
was *recorded*). There is no field for *when the remembered event actually happened*. The seeder stamps
every memory at the current world time, so a decades-old war memory and a fresh one are indistinguishable,
and the GraphRAG `recency_score` ranks the ancient one as fresh. This is one of the three layers behind
NPCs presenting past experiences as the current situation (the others — the MY_ACCOUNT/knowledge_state
seam and the missing prompt past-vs-present axis — are fixed in S26.1/S26.2 without schema change).
**Proposed change (graph schema — needs approval per CLAUDE.md "ask before changing a node/edge schema"):**
  1. Add `occurred_at_game_time: GameTime | null` to the `Memory` node (and optionally `Event`) — the
     in-world time the remembered/recorded event happened, distinct from `created_at_game_time` (record time).
  2. Add `is_historical: bool = false` — a coarse flag for "this happened in a prior era / long before now",
     used by the prompt's past-recollection framing and to exclude such nodes from recency-as-fresh ranking.
  3. `CreateMemoryRequest` / `CYPHER_CREATE_MEMORY` accept and persist both fields (optional; default
     `occurred_at_game_time = created_at_game_time`, `is_historical = false` → no behaviour change for
     existing callers).
  4. Seeder: stamp Henryk's "ran dispatches in the last war" memory `is_historical=true` and split it out of
     the current-war `KNOWS_ABOUT` distorted_summary (which currently fuses past memory + current rumour in
     one first-person string).
**Options considered:**
  - **A (proposed):** explicit `occurred_at_game_time` + `is_historical` on the node. Clean, queryable,
    lets `recency_score` and the prompt treat historical knowledge correctly. Additive + optional → backward compatible.
  - **B:** encode era in `content` text only (no schema). Zero migration but unqueryable; the recency mis-rank
    and any future region/era features stay broken; relies entirely on the LLM parsing prose.
  - **C:** a separate `:HistoricalMemory` label. More invasive; fragments the Memory type for one flag.
**Recommendation:** Option A. Additive, optional, backward-compatible; unblocks both the prompt framing
(S26.2/S26.3) and correct recency ranking.
**Consequence if approved:** S26.3 implements the fields + seed split; S26.2's `age` hint reads real
event-time when present. If declined, S26.2 falls back to inferring age from `created_at_game_time` only
(weaker, since the seed stamps everything "now"), and Henryk's specific case needs a manual seed-string
split without a temporal tag.

---

## DEC-095: anti-hallucination runner verifies player-taught facts via a REST pre-flight (not a DB read)
**Date:** 2026-06-11
**Status:** ✅ ACCEPTED (small eval-harness choice; logged per the "note non-obvious choices" rule)
**Context:** S24.1 wires the `learned_from_player` category into `evals/anti_hallucination_runner.py`.
The runner's contract is `Does NOT: import from src/npc_engine/` — so it cannot call `write_belief()` or
read Neo4j directly to confirm a player-taught fact (DEC-072 BELIEVES provenance) was persisted before
scoring the case as `grounded`.
**Decision:** Pre-flight over REST. Before the dialogue call, a `learned_from_player` case issues
`GET /v1/admin/beliefs/{npc_id}` and checks that at least one persisted belief's `content` contains one of
the case's `preflight_belief_substrings` (falling back to `expected_fact_substrings`). If no matching belief
exists — or the query errors — the case is **skipped** (counts unaffected), not false-failed. This mirrors
the existing 404-skip path: a `learned_from_player` case is a no-op until `KNOWLEDGE_LEARNING_ENABLED=True`
and a prior session has seeded the belief.
**Options considered:**
  - **A (chosen):** content-substring match against `GET /admin/beliefs`. Stays inside the runner's
    REST-only contract; deterministic; testable with mocked httpx.
  - **B:** check BELIEVES-edge provenance (`source_character_id == player`). The list endpoint returns
    Belief-node fields, not edge provenance, so it would need a new/extended endpoint — more surface for
    a one-case pre-flight.
  - **C:** import `write_belief`/graph reader directly. Violates the runner's `Does NOT import from src/`
    contract.
**Consequence:** `make eval-anti-hallucination` no longer silently skips the player-taught case on the
classification path — it is now explicitly gated on a persisted belief. Closes ISSUE-090.

## DEC-096: S25.1 — ECHO_GUARD softened in prompt_builder.py (not YAML); kept on a partial-recovery A/B
**Date:** 2026-06-11
**Status:** ✅ ACCEPTED (prompt-wording tuning; logged per the "note non-obvious choices" rule)
**Context:** Phase 25 (ISSUE-083) is specced as "YAML-only — run `make eval-llm-demo` twice with the
ECHO_GUARD clause in `system_v1.yaml` softened." Two facts made the spec un-followable as written:
  1. **ECHO_GUARD does not live in YAML.** The literal `ECHO_GUARD=` reinforcement token is built from
     `_ECHO_GUARD_TEXT`, a Python string constant in `engines/dialogue/prompt_builder.py` (a pre-existing
     prompt-string-outside-`prompts/` smell, separate issue). `system_v1.yaml` has a related but distinct
     "ECHO PROHIBITION" clause (Rule 9). ISSUE-083 correctly fingers the `prompt_builder.py` line.
  2. The two voice cases run via `make eval` (`scenario_yaml_evals.py`, which loads `evals/cases/*.yaml`),
     not `make eval-llm-demo` (a separate inline runner). The A/B was driven through the named yaml cases.
**Decision:** Softened `_ECHO_GUARD_TEXT` (ISSUE-083's own sanctioned fix #1: "soften the guard wording so
it constrains echoing without flattening voice"). Dropped the always-on flatteners "answer only in your own
general terms" / "speak only from the knowledge in your context" and rephrased each directive as conditional
on an explicit player plant (number/price/name, or false-presence presupposition), adding "when the player
plants no such figure or presupposition, answer freely in your own voice and full character." Bumped
`PROMPT_VERSION` → `stage_b_v2.13`. This is a single-module prompt-constant edit (allowed without asking);
the "YAML-only" note is honoured in spirit (no dialogue logic changed). Branches/conditional injection
(fix #2) were rejected as higher anti-hallucination-regression risk (a missed plant pattern drops the guard).
**A/B result (live, qwen2.5:14b, demo seed):**
  - **Baseline v2.12:** voice cases **0/2** — deterministic fail across 3 reps (captain hedged "nothing major
    has shifted the balance"; mira read as a dry war report).
  - **Softened v2.13:** voice cases **~1/2** — 3 passes + 3 fails across a 3-rep batch (mira recovers gossip
    framing "rumors suggest…"; captain still borderline-fails on "Reports… our scouts keep us informed").
  - **Anti-hallucination guards: 5/5 PASS** on v2.13 — `aldric_fed_price` (number-echo), `false_eyewitness_henryk`,
    `false_premise_peace`, `old_henryk_no_eyewitness_claim`, `old_henryk_past_war_not_current` (Phase 26 cases).
    No moat regression.
**Why kept (not reverted):** strict phase exit ("commit only if BOTH voice cases recover") was not met, so this
is taken via the documented-decision branch. v2.13 is a strict improvement: it removes a confirmed
voice-flattener, lifts voice 0/2→~1/2, and costs nothing on anti-hallucination. The residual captain failure
is voice-judge strictness + a "reports/scouts" secondary-source habit — a voice-tuning axis, no longer the
ECHO_GUARD. ISSUE-083 stays OPEN with that narrowed residual.
**Consequence:** ECHO_GUARD reinforcement is now plant-scoped; NPC voice is freed on neutral questions while
the number-echo and false-presence guards remain. Residual voice gap tracked under ISSUE-083.

---

# Expansion program grants (2026-06-11)

> The 2026-06-11 EXPANSION_ANALYSIS produced `project-harness/expansion/OPEN_QUESTIONS.md` with an
> educated-guess Default per human decision. The project owner authorized **auto-approve everything**
> for the autonomous overnight expansion run. DEC-097..104 record those grants so the
> `/expand-parallel` loop is not blocked. Every grant is **additive / back-compatible / git-reversible**.
> Schema changes are applied by the orchestrator (never by parallel workers) just-in-time before the
> batch that needs them; if the type-registry gate cannot be made green, the loop STOPs and surfaces.
> NOTE on ids: the "Unlocks EXP-NN" references below use the **analysis** ids. After reconciliation
> against code, the execution ids are **EXP-201..230** in `EXPANSION_INDEX.md`. Map: EXP-11→EXP-211,
> EXP-17→EXP-212, EXP-18→EXP-214, EXP-19→EXP-218, EXP-34→EXP-204, EXP-35→EXP-210, EXP-41→EXP-226,
> EXP-43→EXP-228, EXP-44→EXP-229 (full map in EXPANSION_INDEX.md §mapping).

## DEC-097: Memory node — additive player-scope + salience fields (`subject_player_id`, `recall_count`, `never_forget`)
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-1)
**Decision:** Add to `src/npc_engine/type_registry/base_nodes/memory.yaml` three optional, back-compat
fields: `subject_player_id: str|None` (null = world/un-scoped memory), `recall_count: int` (default 0),
`never_forget: bool` (default false). Define `MEMORY_FORGET_THRESHOLD` as a named `config.py` constant;
forgetting is gated behind `never_forget == false`. Unlocks EXP-11, EXP-17.
**Consequence:** existing memories remain valid (defaults apply). Player-scoped recall + salience-decay
become buildable as code-only changes against the extended node.

## DEC-098: Scheduler→API proactive delivery via in-process async queue
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-2)
**Decision:** Deliver tick-scheduler-generated proactive lines to the WS layer through a new
`engines/proactive_dialogue/proactive_queue.py` (`asyncio.Queue` owned in `engines`); the `api` WS
handler drains it (`api`→`engines` is an allowed downward dependency — no upward import). Rejected:
callback injection (layer-violating) and polling (latency). Unlocks EXP-35.
**Consequence:** no layer-rule violation; proactive lines reach connected players.

## DEC-099: Canonical NPC emotion source = in-memory `EmotionStore` (graph mood = durable snapshot)
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-3)
**Decision:** `EmotionStore` is the source of truth for the current tick and what dialogue reads; the
`MoodContagionEngine` writes **through** the store rather than around it; graph mood is the durable
end-of-tick snapshot. Resolves the EmotionStore/graph divergence. Unlocks EXP-34, de-risks EXP-42.
**Consequence:** dialogue context and director read one consistent emotion source.

## DEC-100: Memory node — additive `kind` discriminator
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ — EXP-18)
**Decision:** Add `kind: Literal["episodic","commitment","fact"]|None` to `memory.yaml` (null =
episodic, back-compat). Unlocks EXP-18 commitment/fact memory formation.
**Consequence:** promises and learned facts form distinct, retrievable memory kinds.

## DEC-101: UNLOCKS edge — additive `on_choice_id`
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-4)
**Decision:** Add `on_choice_id: str|None` to `base_edges/unlocks.yaml` (null = auto-unlock, preserving
current behaviour; set = player choice selects the branch). Unlocks EXP-19 quest branching.
**Consequence:** quest chains gain single-choice consequence branching without breaking existing chains.

## DEC-102: New type — `player_model` node + `HAS_PLAYER_MODEL` edge
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-5; Phase E)
**Decision:** Approve `base_nodes/player_model.yaml` + `base_edges/has_player_model.yaml` for NPC
theory-of-mind of the player (second-order belief, per-player provenance). Applied just-in-time before
the Phase-E batch that builds EXP-41, landed together with its first reader to avoid an unused-type gate
failure. Unlocks EXP-41 → EXP-42/43.
**Consequence:** opens the emergent-cognition schema territory; gated behind A–D landing first.

## DEC-103: BELIEVES edge — additive deception fields (`is_deception`, `deception_goal_id`)
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-6; Phase E)
**Decision:** Add `is_deception: bool` (default false) + `deception_goal_id: str|None` to
`base_edges/believes.yaml`. **Coupling requirement:** the EXP-32 anti-hallucination eval must treat
`is_deception == true` beliefs as *intended* behaviour, not guard failures — EXP-43 must not ship before
EXP-32 can distinguish them. Unlocks EXP-43.
**Consequence:** NPCs can hold deliberate false beliefs the moat eval will not flag.

## DEC-104: New type — `scheme` node + `EXECUTES_SCHEME` / `SCHEME_STEP` edges + active-scheme cap
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-7 + OQ-12; Phase E capstone)
**Decision:** Approve `base_nodes/scheme.yaml` + `base_edges/executes_scheme.yaml` +
`base_edges/scheme_step.yaml` for long-horizon covert NPC goals; define
`MAX_ACTIVE_SCHEMES_PER_NPC = 2` (named config constant). Detection (so schemes surface to the player)
revives the graveyard `investigation` engine as EXP-44's detection half (OQ-12), scoped inside EXP-44.
Applied just-in-time before the EXP-44 batch. Unlocks EXP-44.
**Consequence:** the flagship emergent-drama capability; XL, sequenced last; STOP + surface if the
type-registry gate cannot be made green.

## DEC-105: `demo_game/ui/emotion_panel.py` 300-line waiver (mood-contagion pair view, EXP-224)
**Date:** 2026-06-12 · **Status:** ✅ ACCEPTED (demo UI file-size waiver, consistent with DEC-029/032/034/036/049/074/075)
**Context:** EXP-224 added the mood-contagion pair view (`set_pair_emotion`/`clear_pair_emotion`/
`_draw_pair_section`) to `emotion_panel.py`, taking it to ~335 lines. The file is a single cohesive
pygame panel widget; the pair section shares the widget's render state and fonts. Splitting it into a
sibling module would scatter one renderer's logic across two files for no cohesion benefit — the same
rationale as the `left_panel.py` waiver (DEC-036).
**Decision:** Waive the 300-line rule for `demo_game/ui/emotion_panel.py`; re-baseline via
`make check-rules-update`. Each function remains ≤40 lines / ≤3 nesting; only the file-size rule is waived.
**Consequence:** demo emotion panel can render a contagion pair without an artificial split.

## DEC-107: F1.6 scheme auto-advance — what Event does a per-tick SCHEME_STEP reference? (RESOLVED → A)
**Date:** 2026-06-12 · **Resolved:** 2026-06-13 · **Status:** ✅ ACCEPTED — **Option A** (human call, 2026-06-13).
**Resolution (A):** Each scheme advance mints a **registry-valid covert Event** and links it as the next
`SCHEME_STEP`. Sub-decisions made on implementation: (1) `event_type = "scheme_advance"` — a dedicated free
string (the `event` contract's `event_type` is required but unconstrained), chosen over the originally-floated
`"discovery"` so covert steps do NOT collide with public disruption/witness rules that key on real event
types. (2) `is_public = False`, low `severity` (`COVERT_SCHEME_EVENT_SEVERITY`, below the 80 witness/disruption
thresholds) — covert by construction. (3) Events are created via the validated path
(`validate_node_write` → `node_models["event"]` → `upsert_event`) **directly**, NOT via `EventHandler.run_tick`,
so none of run_tick's public side effects (awareness seeding, reputation, world-state conditions, witnessing)
fire for a covert step. (4) Location = the schemer's current location via `get_npc_location_id`; schemes with
no locatable owner are skipped that tick. (5) Cadence/caps: `SCHEME_ADVANCE_TICK_INTERVAL` +
`MAX_SCHEME_STEPS` per scheme + a per-tick advance cap. (6) **Detection-half** stays schema-free: investigation
flips `Scheme.status` `active`→`discovered` (no new node/edge field). Unblocks F2.3 + G2.2.
**Original (OPEN) analysis retained below for context.**
**Date:** 2026-06-12 · **Status:** ⏸ OPEN — needs human design call; F1.6 advance-half DEFERRED until resolved.
**Context:** F1.6 wants the scheduler to "advance active scheme steps per tick." But `SCHEME_STEP` is an
edge `(:Scheme)-[:SCHEME_STEP]->(:Event)`, and `graph/scheme_writer.add_scheme_step` does
`MERGE (ev:Event {id})` — so calling it per tick with a fresh `event_id` **creates a bare Event node with
no `event_type`**, silently violating the registry `event` contract (`event_type` required). There is no
defined source for a scheme step's Event, so naive per-tick advancement is unsafe.
**Options:** (A) each advance creates a real, registry-valid covert Event (`event_type="discovery"`, a
valid base type) via the EventHandler/validate_node_write path, then links it as the next SCHEME_STEP —
schemes manifest as a sequence of in-world events; richer but couples the scheme tick to event creation.
(B) advancement is status/step-counter progression only (reuse the free-string `status` field +
step_order on steps that point to *existing* scheme-related events), creating no new Events — simpler, no
registry coupling, but "steps" become metadata not world events. (C) defer auto-advance entirely; schemes
advance only via explicit engine calls (current EXP-229 behaviour).
**Recommendation:** (A) for fidelity, but it is L-sized and event-coupled. **Detection half** is
independent and schema-free: reuse the `status` field (e.g. `active`→`discovered`) — no new node/edge field
(avoids a schema change; DEC-104 already blessed reviving `investigation`).
**Consequence:** until resolved, F1.6 stays `[ ]`; its only downstream dependents are F2.3 (GET schemes +
discovered flag) and G2.2 (scheme board) — both deferred with it. F1.7+ and the rest of F/G/H proceed.

## DEC-106: New node type — `dialogue_turn` (session persistence migration, F3.5/EXP-230 s2)
**Date:** 2026-06-12 · **Status:** ✅ ACCEPTED (pre-approved in DEMO_BUILD_LOOP §Schema recipes; orchestrator-applied just-in-time)
**Context:** Session turns were persisted as per-player JSON blobs on dynamic Character
properties (`session_turns_<player>`), which (a) collides distinct player ids through key
sanitisation (OQ-9), (b) sprawls per-player properties on the Character node, and (c) is not
queryable / orderable / prunable.
**Decision:** Add `base_nodes/dialogue_turn.yaml` (fields: `id`, `npc_id`, `player_id`,
`turn_index`, `role`, `content`, `occurred_at_game_time?`, `tick?`) — one node per turn,
**property-anchored** by `(npc_id, player_id)` (no new edge; matches the `player_model` node
pattern, keeps the schema surface minimal and the §Schema recipe which lists only the node).
Reuse the existing temporal convention (`occurred_at_game_time` + integer `tick`); `turn_index`
is the canonical per-pair order. Migrate `graph/session_persistence` write/read to these nodes
(replace-on-save: delete the pair's turns then re-create the capped list), add an index on
`:DialogueTurn(npc_id, player_id, tick)` via `schema_bootstrap`. Landed WITH the engine change in
one batch so the type is used immediately (no unused-type gate fail).
**Explicitly NOT this task:** a unified reified `GameTime` node (time-as-a-node). That is a
separate repo-wide decision, valuable only if cross-entity temporal correlation becomes a feature,
and must be per-day bucketed to avoid supernodes.
**Consequence:** distinct player ids never collide; turns are queryable/orderable/prunable;
`SessionStore` round-trips via the nodes on restart.

## DEC-108: `demo_game/game_end_checker.py` 300-line waiver (H1 multi-objective economy)
**Date:** 2026-06-12 · **Status:** ✅ ACCEPTED (demo UI/logic file-size waiver, consistent with DEC-029/032/034/036/049/074/075/105)
**Context:** H1 rewrote `game_end_checker.py` from a single-win/single-lose evaluator into the
multi-objective economy (faction/wealth/quest-chain/treaty win paths; legion/bankruptcy/deadline/
overreach failures; grade scoring; priority failure-selection). The file is one cohesive PURE
evaluator (no I/O) — every predicate + the `_select_failure` priority chain + `compute_grade` +
`ObjectiveState`/subtitle maps share the single concern of deciding the game outcome and change
together. It is ~343 non-blank lines.
**Decision:** Waive the 300-line rule for `demo_game/game_end_checker.py`; re-baseline via
`make check-rules-update`. `evaluate_game_end` itself stays ≤40 lines / ≤3 nesting (all logic
extracted into named `check_win_multi`/`check_lose_*`/`check_overreach`/`compute_grade`/`_select_failure`
helpers). Splitting the predicates into a sibling module would scatter one decision across files.
**Consequence:** the demo's win/lose economy lives in one readable evaluator; the function-size and
nesting rules remain enforced.

## DEC-109: `demo_game/seed_npc_data.py` 300-line waiver (H2 content data module)
**Date:** 2026-06-12 · **Status:** ✅ ACCEPTED (demo data-module file-size waiver, consistent with DEC-029/.../108)
**Context:** H2.2–H2.5 expanded the demo world (8→14 NPCs, +4 venues + 2 districts, 3→5 factions,
6→18 quests/6 chains). Per the H2.2 spec the new NPC/location/faction/quest payload data was split
into a new DATA-ONLY module `demo_game/seed_npc_data.py` specifically to keep `seed.py` smaller. The
data module is ~465 lines of pure lists/dicts (no logic).
**Decision:** Waive the 300-line rule for `demo_game/seed_npc_data.py`; re-baseline via
`make check-rules-update`. It is data with zero branching/functions; splitting one cohesive content
set across more files for no logic reason would be artificial (and the module exists to keep `seed.py`
under the limit in the first place).
**Consequence:** demo content lives in one readable data module; `seed.py` stays the orchestration file.

## DEC-110: `demo_game/ui/branch_panel.py` 300-line waiver (H2.1 modal branch widget)
**Date:** 2026-06-12 · **Status:** ✅ ACCEPTED (demo UI file-size waiver, consistent with DEC-029/032/036/108/109)
**Context:** H2.1's `BranchPanelWidget` is a single cohesive pygame modal (prompt + numbered options +
keyboard selection + the draw constants/layout for the overlay), ~346 lines. It mirrors the existing
panel widgets (`actions_panel.py`, `game_window.py` overlays).
**Decision:** Waive the 300-line rule for `demo_game/ui/branch_panel.py`; re-baseline via
`make check-rules-update`. Splitting the render into a sibling would scatter tightly-coupled draw
state/constants for no cohesion gain. Functions stay ≤40 lines / ≤3 nesting.
**Consequence:** the branch choice modal lives in one widget file, consistent with the other demo panels.

## DEC-111: `IDEMPOTENCY_ENFORCE_HEADER=false` — advisory warn vs hard-raise in staging/prod?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L1-06/L1-10)
**Context:** With `IDEMPOTENCY_ENFORCE_HEADER=false` (the shipped default), all mutating endpoints are
replay-able. `config.py:258-263` emits a WARNING in staging/prod but does not raise — chosen "warn, not
raise, for back-compat." A studio that copies the dev `.env` runs replay-able mutations in prod.
**Question:** Keep advisory (warn) or hard-raise in staging/prod like the API-key check? Hard-raise is a
breaking operational change for any existing staging deploy that copies dev `.env`.
**Owner decision needed before** wiring any enforcement.

## DEC-112: Move `system_v1_router` under `admin_prefix`?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L1-13)
**Context:** `system_v1_router` is mounted at `/v1/system/*`; the other admin surfaces sit under
`/v1/admin/*`. Relocating it improves consistency but changes the public URL (`/v1/system/events` →
`/v1/admin/system/events`), breaking existing clients.
**Question:** Relocate (interface change) or leave as-is? Needs sign-off because it is a public API change.

## DEC-113: Adopt `mypy --strict`?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L3-14)
**Context:** The current `make type` gate runs non-strict and reports 0 errors. `mypy --strict` surfaces
274 errors across 87 files (bare `dict` returns, missing annotations, an `attr-defined` in `batch.py:17`).
**Question:** (a) targeted intermediate (`disallow_untyped_defs` + `warn_return_any`), (b) full `--strict`
with per-file `# type: ignore` debt, or (c) keep non-strict + add an advisory `make type-strict`? Choice
sets the scope of any typing fix work (affects SEV-06's `run_tick` change).

## DEC-114: Type the API response envelope across all 130 `OkEnvelope[dict[str,Any]]` routes?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L3-09)
**Context:** `response_model=` is now 147/147, but 130 routes wrap `OkEnvelope[dict[str,Any]]` — the `data`
payload is opaque to every OpenAPI/SDK client. SEV-03 fixes the scheme route specifically; the other ~129
remain. L effort.
**Question:** Do all routes, a subset (public/SDK-facing only), or log-and-defer until the SDK contract
freeze? Relevant before any Unity/Unreal SDK is generated from the OpenAPI schema.

## DEC-115: `dependencies_advanced.py` as a second composition root — bless or fold?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L2-06)
**Context:** CLAUDE.md: "`api/dependencies.py` is the sole composition root." `dependencies_advanced.py`
defines `@lru_cache` singletons for 11 advanced engines and is imported by `get_tick_scheduler()` in
`dependencies_engines.py`. DEC-042/076 bless `dependencies_engines.py` but not this further split.
**Question:** Formally bless `dependencies_advanced.py` as a named second root (with a boundary rule) or
fold it back? Relates to ISSUE-105 (line-cap breach).

## DEC-116: Is `covert_event_factory`'s summary template "prompt content"?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L2-10)
**Context:** `covert_event_factory.py:33` `_COVERT_SUMMARY_TEMPLATE` builds the Event `summary` data field.
If `event.summary` is later included in LLM context assembly (as other event summaries are), this template
effectively shapes LLM input and should be YAML in `prompts/` per the no-prompt-strings-outside-prompts rule.
**Question:** Confirm whether `event.summary` reaches LLM context. If yes → move to `prompts/scheming/`. If
no → document the determination in-file. Needs a data-flow trace decision.

## DEC-117: Enforce the 40-line function / 3-nesting rule, or formally waive the violators?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L5-01/L5-02)
**Context:** The strict 40-line function rule is ungated and widely violated: `advance()`
(`tick_scheduler.py:303`) is 373 lines at nesting depth 7; 14 more functions exceed 40 lines (`dispatch()`
201, `seed()` 202, `assemble_tier_a_context()` 186). Only file-size waivers exist (DEC-042 etc.), none for
function length.
**Question:** Add an enforcing gate + refactor/​waive the ~15 functions, or formally re-classify the
40-line limit as a guideline for orchestration loops with per-function DEC waivers? Either way the rule
should stop being silently violated.

## DEC-118: `investigation_service.py` — raw `CREATE` vs `MERGE` (dedup semantics)?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L4-09)
**Context:** The six `investigation_service.py` writers use raw `CREATE`; duplicate calls silently create
duplicate nodes. SEV-05 adds tests for the CURRENT behavior; whether to switch to `MERGE` (idempotent) is a
graph-write-semantics change that affects dedup and must be decided deliberately.
**Question:** Keep `CREATE` (and rely on callers for uniqueness) or switch to `MERGE`? A schema/behavior call.

## DEC-119: Session-ownership — migrate 14+ graph sub-writers to `AsyncTransaction`, or bless the distributed-tx pattern?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L2-01/L2-03)
**Context:** CLAUDE.md: "graph sub-writers receive `AsyncSession` as a parameter; `graph_writer.py` is the
only file that opens and commits transactions." This is systemically violated — 14+ `graph/` files open
their own transactions (`belief_service`, `goal_service`, `memory_service`, `currency_writer`,
`scheme_writer`, …). SEV-01 fixes only the new scheme files; fixing only those creates an inconsistent
standard.
**Question:** Commit to migrating all `graph/` sub-writers to accept `AsyncTransaction` (large refactor), or
amend the rule to bless the distributed begin_transaction pattern with a DECISIONS entry? Decide the
standard before more graph writers are added.

## DEC-120: `DistortionType` — `Literal` vs `str`/extensible enum?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L7-01-R)
**Context:** Gossip distortion strategies are now an open `STRATEGY_REGISTRY`, but `DistortionType` is still
a closed `Literal` and `REGISTRY_KEYS` is frozen at import — a 5th strategy is unreachable at runtime and
rejected by the Literal/`GossipDistortion` model. Loosening to `str` loses IDE/Pydantic enum checking and
affects the `mutation_type` string serialized on BELIEVES_RUMOR edges.
**Question:** `str` + runtime validator against the registry, or an extensible enum class? A serialization/
type-safety trade-off.

## DEC-121: Split the fat `LLMClientProtocol` (ISP) before the SDK contract freeze?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L7-08)
**Context:** `protocols.py` bundles `generate` + `generate_structured` + `stream` + `health_check` +
`model_name`. A streaming-only or structured-only backend must stub the rest, risking LSP drift. Splitting
into `LLMGenerateProtocol` / `LLMStructuredProtocol` / `LLMStreamProtocol` is the ISP-correct shape.
**Question:** Split now (before any SDK client is built against the protocol shape — a breaking change
afterward) or defer? Decide before the OpenAPI/SDK contract freeze.
