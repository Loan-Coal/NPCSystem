# Decisions Log

Non-obvious architectural choices. Each entry explains what was decided and why,
so future maintainers can judge edge cases without re-deriving the rationale.

Rules:
- Append-only. Never delete entries.
- Monotonic DEC-NNN IDs. Never reuse.
- Context, options considered, decision, why. No essays.

**Canonical location:** This file lives at `project-harness/DECISIONS.md`. Never create or edit a root-level copy.

---

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

## DEC-016: context_builder.py accepted at 367 lines (300-line limit exception)
**Date:** 2026-05-18
**Context:** After Phase 6 additions (two-pass reranking, query expansion, trust scoring, second-hop events, quest state, cross-encoder gating), `context_builder.py` is 367 lines. CLAUDE.md hard limit is 300 lines.
**Options considered:**
  1. Split `_build_secondary_tier_a_items(...)` — saves ~30 lines, adds ~20-line helper with 12 parameters. Net −10 lines; still over 300.
  2. Extract Stage 4 gather into `_fetch_enrichment(...)` — saves 12 lines, adds 15-line helper. Net +3 lines; still over 300.
  3. Accept the overrun with a justifying comment and this entry.
**Decision:** Option 3. `build_serialized_context` is a single async orchestration pipeline: every line is part of one logical flow. Splitting distributes one function across two modules with no encapsulation benefit.
**Limit:** If it grows to 500 lines, split then — 367 is defensible, 500 is not.

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
