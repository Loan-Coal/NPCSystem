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
