# Decisions History

Entries moved from `DECISIONS.md` that are no longer cited outside this file.

## DEC-139: ISSUE-107 — memories_recalled added to DialogueResponse; port return type changed
**Date:** 2026-06-19
**Context:** Callers of `POST /dialogue` had no visibility into which Memory node IDs
the NPC's context actually retrieved. Without this, game clients cannot trigger UI
effects (glowing portrait, "memory surfaced" animation) tied to recalled memories.
**Decision:** Add `memories_recalled: tuple[str, ...]` to `DialogueResponse` (default `()`).
Change `DialogueContextPort.build_context` return type from `str` to `tuple[str, list[str]]`.
`Neo4jDialogueContextAdapter.build_context` parses the serialized context JSON and extracts
IDs from the `"memories"` and `"player_memories"` keys. The IDs are threaded from adapter →
handler via a closure (`memory_ids_captured: list[str]`) rather than changing
`execute_with_degradation`'s factory signature.
**Rationale:** Closure captures the IDs without changing the degradation helper's contract.
Parsing JSON for IDs in the adapter avoids bloating `build_serialized_context`'s return type.
`build_serialized_context` continues to return `str`; only the port-level return type changed.

## DEC-138: ISSUE-071 — SystemStateContext Tier-0 block grounding dialogue in live engine state
**Date:** 2026-06-19
**Context:** NPCs could offer trades when their inventory was empty, or re-offer quests
the player had already completed, because the context pipeline had no access to live
engine state (item counts, quest status). These are facts that the LLM must not contradict.
**Decision:** Add a new `SystemStateContext` Pydantic model (`engines/dialogue/system_state_context.py`)
with `npc_can_trade`, `npc_item_count`, and `player_quest_status`. `resolve_system_state` is
called in the route (`api/routes/dialogue.py`) and passed into `handler.handle()`.
`context_builder._build_tier0_items` receives it as an optional parameter and, when present,
appends a `ContextItem(key="system_state", tier="tier0", priority=97, pinned=True)`.
A matching rule in `prompts/dialogue/system_state_v1.yaml` is appended to the system prompt.
**Rationale:** Tier-0 is pinned and never evicted, guaranteeing these constraints survive
token budget trimming. Lazy imports inside `resolve_system_state` prevent circular imports
between the `engines` and `graph` layers. Route injection (not handler injection) keeps the
session lifetime at the request boundary, consistent with the session-ownership rule.

## DEC-133: ISSUE-112 — activate WITNESSED edges via EventTemplate.src_character_id (optional field)
**Date:** 2026-06-19
**Context:** `_record_witnesses` in `EventHandler` was dead code — it read `src_character_id` from
`raw_props` but `_build_event` never set it, so `actor_id` was always None. The fix had two options:
(A) add `src_character_id: str | None = None` to `EventTemplate` and propagate it through `_build_event`;
(B) drop the dead block entirely.
**Decision:** Option A. `src_character_id` is already an optional field in `event.yaml` (no schema
change needed). Adding it to `EventTemplate` as optional keeps the witnessing mechanic alive for
character-centric event templates that specify an actor, while autonomous templates (no actor) continue
to skip witnessing unchanged. The actor is excluded from the `witness_ids` list to avoid self-witness.
**Why not B:** Witnessing is a designed mechanic; dropping it would require a schema or port cleanup
and would lose the capability permanently. A is non-breaking and costs one optional field.

## DEC-123: R006 baseline — five dialogue-cluster functions accepted over 40 lines
**Date:** 2026-06-17
**Context:** SEV-24 dialogue cluster migration introduced or touched five functions that
exceed the 40-line R006 limit. All five cases are driven by mandatory multi-line docstrings
(Args/Returns/Raises sections required per CLAUDE.md) rather than logic complexity.
Splitting any of them would produce artificial helper functions with no independent utility.
**Functions accepted:**
- `DialogueHandler.__init__` (44 lines) — pure attribute assignment; no extractable logic.
- `DialogueHandler.handle` (41 lines) — single-concern orchestrator; was pre-existing.
- `apply_dialogue_relation_deltas` (42 lines) — 14-line Args section; body is 19 lines.
- `Neo4jDialogueRepository.apply_relation_deltas` (52 lines) — 22-line docstring; retry already extracted to `_apply_first_contact_retry`.
- `Neo4jDialogueContextAdapter.build_context` (47 lines) — 16-line docstring; body is a single session-scoped call.
**Decision:** Re-baseline with `make check-rules-update`. Do not split.

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

## DEC-075: quest_trade_controller.py accepted at 312 lines (300-line exception)
**Date:** 2026-06-06
**Context:** `demo_game/quest_trade_controller.py` grew to 312 lines when `fix(demo): substitute empty item_type in confirm-trade` (ISSUE-067) added input-sanitization helpers. The file handles quest + trade controller logic for the demo layer.
**Options considered:**
  1. Extract trade sanitization helpers to `quest_trade_sanitizer.py` — the 3 helper functions are only ~20 lines combined; creating a peer module for them adds indirection without real encapsulation.
  2. Accept the overrun with this entry.
**Decision:** Option 2. The overrun is small (12 lines) and the helpers are cohesive with the controller. No further growth without extracting either the trade or quest side into a dedicated controller.
**Limit:** Do not grow this file further. If new trade or quest demo logic is added, extract to `demo_game/trade_controller.py` and `demo_game/quest_controller.py`.

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

## DEC-050: put_world_state hardcoded "world" → "world_demo"
**Date:** 2026-06-03
**Context:** ISSUE-044 fix (S0.4) changed the canonical WorldState ID from "world" to "world_demo" in seed.py and Settings. However `EngineClient.put_world_state` still wrote to `id="world"`, so all EventFire scenes in the demo runner wrote to a node the engine never read.
**Decision:** Changed the hardcoded `"world"` to `"world_demo"` in `put_world_state`. All callers (run.py, game_window.py, scenario runners) now update the correct node.
**Why:** The world ID is a demo-world constant, not a general configuration value. Adding an injection point would be over-engineering; the demo is always `world_demo`.
**Future:** If multi-world support is added, `EngineClient` should accept a `world_id` parameter on all world-state mutating methods.

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

## DEC-012: No separate gateway service (Feature 0.3 scope reduction)
**Date:** 2026-05-05
**Context:** ROADMAP Feature 0.3 specified building a `gateway/` package in front of internal services. During route inventory, we found `main.py` already mounts all routes in a single FastAPI app with global `ApiKeyMiddleware` — the app already is what a gateway would be.
**Options considered:**
  1. Build `src/npc_engine/gateway/` as a second FastAPI app re-mounting existing routers. Cons: pure duplication, two apps for one process, double middleware overhead.
  2. Harden `main.py` as the canonical public entry point — rate limiting, request logging — without a separate gateway package.
**Decision:** Option 2.
**Why:** A separate gateway is justified when there are multiple processes to unify. We have one process. Adding architectural ceremony for a pattern that doesn't fit the topology is overengineering.

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

## DEC-025: Demo seed reverted to demo_game/seed.py (S3.2 — reversal of DEC-021)
**Date:** 2026-05-28
**Context:** DEC-021 moved the demo world seed from `demo_game/seed.py` → `seeds/worlds/seed_demo_world.py` for consolidation. S3.1 reversed this: the demo seed moved back to `demo_game/seed.py`.
**Decision:** `demo_game/seed.py` is the authoritative demo world seed. `seeds/worlds/seed_demo_world.py` is deleted. The DEC-021 "single folder" rationale is superseded for the demo seed specifically.
**Why:** The demo game must be self-contained and fully decoupled from the NPC engine source — as if a third-party studio built it on top of the shipped SDK. Its seed data belongs inside `demo_game/`, not alongside eval world seeds. Naming convention going forward: `seeds/worlds/seed_*.py` = eval harness worlds only; `demo_game/seed.py` = demo app seed.
**Consequence:** `seeds/worlds/` contains only `seed_tavern_world.py` and `seed_village_world.py`. Any reference to `seeds/worlds/seed_demo_world.py` in historical docs is stale but preserved for audit trail.

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

## DEC-044: quest_lifecycle_engine.py accepted over 300-line hard limit
**Date:** 2026-06-03
**Context:** S2.2 — adding `offer_draft_quest()` to `QuestLifecycleEngine` brings the file to ~560 lines. The class was already pre-existing at ~495 lines before this task.
**Decision:** Accepted. `QuestLifecycleEngine` is a single-class module (SRP satisfied). Its length comes from five distinct lifecycle methods (`offer_draft_quest`, `offer_quest`, `accept_quest`, `update_objective`, `evaluate_completion`, `apply_rewards`) each with full docstrings and narrow logic. Each method is under 40 lines. Splitting into two classes would require coordinating shared constants (`STATUS_*`) and dependencies across modules with no gain in cohesion.
**Why:** The 300-line limit targets wide classes with unrelated responsibilities. This class has one responsibility (quest lifecycle state machine) and is long due to the number of transitions in that machine, not due to sprawl.
**Consequence:** Acceptable until Phase 3 requires adding quest-type-specific transition logic — at that point extract per-type handlers via the Strategy pattern.

## DEC-060: main.py grandfathered at 361 lines pending SEV-23 split
**Date:** 2026-06-04
**Context:** SEV-33 added 77 lines to `src/npc_engine/main.py` (284 → 361), pushing it over the 300-line hard limit. This was not caught in that session. SEV-23 tracks splitting all over-300 files.
**Decision:** Waiver granted. `main.py` added to the rules baseline as a grandfathered violation. Will be resolved when SEV-23 executes.
**Why:** Splitting `main.py` mid-session during SEV-04 would expand scope and risk regressions in unrelated code. The violation was introduced by a committed prior fix, not by the current change.
**Consequence:** `make check-rules` passes with a baselined exception. SEV-23 must un-grandfather this when it splits the file.
**Resolved:** 2026-06-11 (Phase 21 S21.1) — superseded by DEC-089; `main.py` split to 217 lines, R001 baseline entry removed.

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

## DEC-097: Memory node — additive player-scope + salience fields (`subject_player_id`, `recall_count`, `never_forget`)
**Date:** 2026-06-11 · **Status:** ✅ ACCEPTED (grants OQ-1)
**Decision:** Add to `src/npc_engine/type_registry/base_nodes/memory.yaml` three optional, back-compat
fields: `subject_player_id: str|None` (null = world/un-scoped memory), `recall_count: int` (default 0),
`never_forget: bool` (default false). Define `MEMORY_FORGET_THRESHOLD` as a named `config.py` constant;
forgetting is gated behind `never_forget == false`. Unlocks EXP-11, EXP-17.
**Consequence:** existing memories remain valid (defaults apply). Player-scoped recall + salience-decay
become buildable as code-only changes against the extended node.

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

## DEC-117: Enforce the 40-line function / 3-nesting rule, or formally waive the violators?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L5-01/L5-02)
**Context:** The strict 40-line function rule is ungated and widely violated: `advance()`
(`tick_scheduler.py:303`) is 373 lines at nesting depth 7; 14 more functions exceed 40 lines (`dispatch()`
201, `seed()` 202, `assemble_tier_a_context()` 186). Only file-size waivers exist (DEC-042 etc.), none for
function length.
**Question:** Add an enforcing gate + refactor/​waive the ~15 functions, or formally re-classify the
40-line limit as a guideline for orchestration loops with per-function DEC waivers? Either way the rule
should stop being silently violated.

## DEC-120: `DistortionType` — `Literal` vs `str`/extensible enum?
**Date:** 2026-06-13 · **Status:** ❓ OPEN (raised by /full-review L7-01-R)
**Context:** Gossip distortion strategies are now an open `STRATEGY_REGISTRY`, but `DistortionType` is still
a closed `Literal` and `REGISTRY_KEYS` is frozen at import — a 5th strategy is unreachable at runtime and
rejected by the Literal/`GossipDistortion` model. Loosening to `str` loses IDE/Pydantic enum checking and
affects the `mutation_type` string serialized on BELIEVES_RUMOR edges.
**Question:** `str` + runtime validator against the registry, or an extensible enum class? A serialization/
type-safety trade-off.

## DEC-141: Standardize all engine LLM configs on qwen2.5:7b for local single-model runtime
**Date:** 2026-06-22 · **Status:** ✅ ACCEPTED · **Drives:** `src/npc_engine/engines/*/llm_config.yaml`
**Context:** The five engine `llm_config.yaml` files referenced three different Ollama models —
`qwen2.5:14b` (dialogue/memory/proactive), `mistral:7b-instruct` (chapter, NOT pulled on the dev machine),
and `mixtral:8x7b` (quest_generation, 26 GB). On a single local GPU this caused: (a) `mistral:7b-instruct`
missing → chapter engine LLM errors; (b) `mixtral:8x7b` cold-loads of 26 GB → `/v1/clock/advance` exceeding
the demo client's 15 s timeout; (c) model thrashing as ticks switched models. The target is a downloadable
game that runs fully locally (DEC-124 path A), where one resident model is far more reliable than three.
**Decision:** Point all five engines at `qwen2.5:7b` (already pulled, ~2× faster than 14b, ~4.7 GB resident,
no missing model, no 26 GB cold-load). Per-engine config is unchanged structurally, so any engine can be
re-pointed at a larger/specialized model later by editing its `llm_config.yaml` (OCP — no code change).
**Trade-off:** Slightly lower generation quality than 14b/mixtral for dialogue and quest-generation, accepted
in exchange for a single resident model, no missing-model failures, and tick latency under the demo timeout.
Revisit if a machine with more VRAM is targeted, or per-engine quality needs justify a second resident model.

## DEC-142: Run all engines on qwen2.5:14b (supersedes DEC-141) — quality over latency
**Date:** 2026-06-22 · **Status:** ✅ ACCEPTED (supersedes DEC-141) · **Drives:** `src/npc_engine/engines/*/llm_config.yaml`
**Context:** DEC-141 standardized every engine on `qwen2.5:7b` for speed/one-resident-model. Live eval runs
(`scenario_demo_game_judge`) showed 7b materially weakens NPC voice/persona — captain_sorn hedges, mira loses
warmth + source attribution, old_henryk stops distorting — turning the borderline ISSUE-083 voice cases into
clear fails. The owner prioritizes showcase quality for the upcoming Unreal demo over per-call latency.
**Decision:** Point all five engines at `qwen2.5:14b` (already pulled, ~9 GB, one resident model). This keeps
the single-model simplicity that motivated DEC-141 (no missing `mistral:7b-instruct`, no 26 GB `mixtral`
cold-load) while restoring voice quality. **Supersedes DEC-141.**
**Trade-off:** Dialogue ~11 s/call vs ~3 s on 7b; background ticks (`/v1/clock/advance`) are slower and may
exceed the demo client's 15 s `graph_timeout` under heavy ticks — acceptable for quality-first local runs.
ISSUE-083 (captain voice) may remain borderline even on 14b; it is documented and non-blocking.
Revisit if latency becomes the priority (drop back toward 7b) or a larger-VRAM machine allows per-engine tiers.

## DEC-152: Reference-labeller model separation — labeller is `claude-opus-5`
**Date:** 2026-08-02 · **Status:** ✅ ACCEPTED · **Gates:** `EVAL-P5.2` · **Drives:** `evals/label_runner.py`, `evals/calibration_records.py`, `Makefile`
**Context:** EVAL-P5 calibrates each scorer against adjudicated labels. Because the maintainer adjudicates
*model-proposed* labels rather than labelling cold, the pre-labelling model is load-bearing: it defines the
starting point for every human verdict and therefore, indirectly, every κ the program publishes.

DEC-143 established that the eval judge must differ from the generation model (no self-evaluation). The same
invariant must extend to the labeller, or the calibration measures a model against itself one step removed.

**This decision exists because the roadmap claimed it already did.** `EVAL-P5` said *"propose **DEC-149** —
reference-labeller model separation … It gates EVAL-P5.2"*, and `EVAL-P5.2` then said *"✅ DEC-149 ACCEPTED
2026-07-31 — no longer a halt condition."* But `DEC-149` is *"All five engines standardise on qwen2.5:7b"* —
an unrelated decision written during EVAL-P0.1. A grep for `labeller|labeler` across DECISIONS.md returns
nothing substantive. **The ask-gate was marked cleared by a decision that was never made.**

That was not cosmetic. The overnight loop's ask-gate detector is a regex on the literal string `ask-gate`
(`scripts/_roadmap_cursor_core.py:39`), so P5.2 no longer carried a live gate — it carried a *clearance*. An
unattended session reaching it would have picked its own labeller, wired a paid API client, and spent money
against a policy nobody approved.

**Decision:**
1. **Invariant:** the reference labeller ∉ {discovered generation models} ∪ {judge model}, enforced at runtime
   by `LabellerModelCollisionError`, mirroring `judge_config.resolve_judge_model`'s `JudgeModelCollisionError`.
2. **Labeller = `claude-opus-5`** via raw `httpx` against `POST /v1/messages`
   (`anthropic-version: 2023-06-01`). The `anthropic` SDK stays out — it is a new dependency and trips the
   CLAUDE.md ask-gate; the REST surface needed here is one endpoint.
3. **Prefer the Batches API** (`POST /v1/messages/batches`) — 50 % cheaper, and this is a bulk offline job with
   no latency requirement. Results are keyed by `custom_id` and return in **any** order; key by it, never by
   position.
4. `ANTHROPIC_API_KEY` from env only. Never committed, never logged, never in an error message.

**Options considered:** `claude-sonnet-5` ($3/$15 per Mtok, ≈$0.65) and `claude-haiku-4-5` ($1/$5, ≈$0.33)
were both cheaper; a two-model panel (Opus 5 + Sonnet 5, disagreements prioritised for adjudication) was the
most informative. A third *local* Ollama model was also viable and free.
**Rationale for Opus 5:** cost is not the axis. 500 labels ≈ **$4** at $5/$25 per Mtok, halvable via Batches —
against 4–6 h of maintainer adjudication time, the dollar figure is noise. What the labeller buys is the
quality of the anchor: you adjudicate its proposals, so a weak pre-label biases you toward weak judgments,
which is the precise opposite of what a calibration artifact is for. Saving $3 on the artifact that defines
"correct" for every downstream κ is a false economy. The local-model option was rejected for the same reason.

**Trade-off:** introduces an external paid dependency into a program whose other components are all local.
Accepted because it is bounded (one offline batch, ~$4, no runtime path), and because the alternative —
calibrating against a model from the same family as the judge or generation fleet — defeats the phase.

**Related:** DEC-143 (judge ≠ generation), DEC-150 (DEC-143 enforced by AST scan), DEC-153 §1.

---

## DEC-154: `evals/` joins the lint gate; the loop fence reopens to EVAL-P0..P8
**Date:** 2026-08-06 · **Status:** ✅ ACCEPTED · **Drives:** `Makefile` (`lint`), `scripts/check_harness_honesty.py`, `project-harness/ROADMAP.md` (the `LOOP:QUEUE` fence), `tests/unit/evals/test_gate_scope.py`, `tests/unit/harness/test_roadmap_cursor.py`
**Context:** EVAL-P0.3 is ask-gated because it edits the shared `make check` health gate. Answered by the
human session on 2026-08-06. Recorded because three of the four decisions below are invisible in the diff.

**1 — `lint` scope becomes `ruff check src/ evals/`, and nothing wider.** `tests/`, `scripts/` and
`demo_game/` were offered and declined: their violation counts are unmeasured and the phase carried a 30-min
time-box. **Measured result: the 13 `evals/` modules held exactly ONE violation** — `E402` at
`retrieval_runner.py:39`, a `from pydantic import BaseModel` stranded below a comment banner. Fixed by moving
it into the third-party import group rather than `# noqa`-ing it, so the import-order rule is satisfied and
not merely suppressed. The escape hatch the roadmap wrote (fix the mechanical ones, baseline the rest, log an
ISSUE) never fired: `scripts/rules_baseline.txt` is untouched and no ISSUE was opened.
**Consequence for the Parked item:** *"`evals/` under `mypy` + `check-docstrings`"* was parked as *"unbounded
until EVAL-P0.3's ruff pass reveals the true violation count"*. The ruff count is now known and it is 1. That
does **not** transfer to mypy or docstrings — those remain unmeasured — so the item stays Parked, but its
stated blocker is retired and the next session can size it directly.

**2 — `check_harness_honesty._lint_clean()` had to move with it.** That script re-runs ruff itself and had
`src/` hardcoded. Left alone it would report "lint clean" while `make lint` was red on `evals/` — the script
whose single purpose is catching the harness lying about a gate would have become the lie. Scope is now the
named `_LINT_PATHS = ("src/", "evals/")` and `test_gate_scope.py` asserts it equals the Makefile recipe's
scope in both directions. This was not in the phase's file list; it is in scope because the phase's claim is
"`evals/` is gated", and it was not gated while an honesty checker could green-light it.

**3 — The fence reopened, releasing EVAL-P1..P8.** DEC-153 §3 narrowed `<!-- LOOP:QUEUE end -->` to sit above
Phase EVAL-P1 and wrote the reopen condition: both EVAL-P0.3 and EVAL-P0.4 ticked. Both are now ticked
(P0.4 measured the live baseline earlier on 2026-08-06), so the condition fired and the marker moved to just
above `### Parked (out of budget)`. Queue: **9 phases, 23 open tasks, 3 flagged** (`EVAL-P1.2`, `EVAL-P5.2`,
`EVAL-P6.3`, all ask-gate); `--next` returns `EVAL-P1.1`. The narrowing did its job — the baseline exists
before a single judge call was spent on P1..P8, which is exactly what DEC-153 §3 was protecting. The fence
was **not** deleted: the 19 open tasks below the marker stay structurally unreachable at 3am.
The EVAL-P0.4 Session Log now sits *inside* the fence. It is prose with no `- [ ]` bullets, so the cursor's
grammar cannot see it; the only effect is a longer `--slice EVAL-P0`, and EVAL-P0 is complete.

**4 — The fence tripwire was re-snapshotted, and it was already red before this task touched it.**
`test_real_roadmap_fence_state_tripwire` asserted `pending == 1`. `PhaseEntry.pending` **excludes flagged
tasks**, and the only two tasks left in EVAL-P0 were both flagged, so the true value was 0 — verified against
the committed `HEAD` copy of ROADMAP.md, not just the working tree. The test had therefore been failing
independently of EVAL-P0.3, and `make check` could not have gone green without addressing it. Rewritten to
assert **sorted id lists** (`EVAL-P0..P8`; flagged `== ["EVAL-P1.2", "EVAL-P5.2", "EVAL-P6.3"]`) alongside the
counts: a bare count tells whoever trips it that *something* moved, never *which* task appeared or vanished,
which is the one thing a deliberate-update tripwire has to report.

---

## DEC-156: Calibration pipeline — composite item ids, deterministic scorer verdicts, prompt-only LABEL_PROMPT

**Date:** 2026-08-08
**Status:** ✅ ACCEPTED (ask-gate cleared by explicit human instruction: "these scorers exist for a
reason and are valuable data: keep them, build the pipeline to take them into account")
**Context:** The first real labelling attempt produced 921 export items of which 576 (62.5%) carried
`criteria: ""` and were unlabelable, and every labelling run returned prose instead of JSONL. Tracing
it surfaced four distinct defects, three of them silent.

**Decisions:**

1. **Deterministic scorers are calibrated, not filtered out.** The obvious fix — export only the 345
   LLM-judge records — was rejected. A mechanical matcher has no judgment and therefore fails in
   predictable ways (`keyword_none` flagging an innocent substring, `min_length` passing a long
   evasive non-answer); measuring that is the artifact's purpose. New `criteria_rendering.py` renders
   each matcher's `metadata["expectation"]` into a labelable sentence, and surfaces the response
   fields the matcher actually inspects (`in_set`/`range`/`schema` judge `facial_expression.type`,
   `relation_deltas.trust` — fields absent from `output_text`, so those items were previously
   unanswerable even in principle). An unmapped matcher kind raises rather than rendering blank.

2. **Labelled items are addressed by a composite `<record_id>#r<n>`** (`record_identity.py`).
   `GenerationRecord.record_id` omits `repetition`, so the k=3 run emitted 921 records under only
   **307 unique ids**, each repeated 3× with *different* response text. `label_import`'s
   `dict[record_id]` indexes kept the last repetition and silently joined every label to it — pairing
   a label made against one response with another response's verdict. Changing `record_id` itself was
   rejected: it would invalidate the existing transcript and force a ~60 min regeneration for no gain.

3. **`label-import --judged` accepts multiple files, and a missing verdict is fatal.**
   `judged.jsonl` holds LLM-judge records only; `deterministic_records.score_record` could always
   replay a matcher verdict but no verb ever persisted one, so nothing on disk covered the other 62%.
   New `deterministic-verdicts` verb writes them. Importing a record with no verdict now raises
   `MissingVerdictError` rather than defaulting to `False`, which would fabricate data points.

4. **`LABEL_PROMPT.md` is prompt-only.** The labelling loop pipes the whole file, so its "How to run"
   header was being read as the model's task — the direct cause of 513 lines of commentary and zero
   labels across ~10 sessions. Run instructions moved to `evals/calibration/README.md`.

5. **`python -m evals` forces UTF-8 on stdout/stderr.** `calibrate` crashed with
   `UnicodeEncodeError` on `≥` under the Windows cp1252 console — *after* a completed adjudication
   pass, i.e. it would have destroyed the summary at the end of a 4-6 hour session.

**Also added:** `scripts/mock_labeller.py` + `scripts/mock_adjudicate.py` and `make mock-calibrate`,
which drive the whole chain on seeded random labels for zero Claude spend. Defects 3 and 5 were both
found by that dry run, not by inspection. Mock artifacts are stamped `mock-random-v1` /
`adjudicated_at="MOCK"` and written to `mock_*.jsonl` so they can never be mistaken for a real pass.

**Consequences:** All 921 items now labelable and uniquely addressed (was 345 labelable / 307
addressable). `make check` green: 2945 passed, coverage 87.14%; the single remaining failure is the
pre-existing EVAL-P9.3 work-list test documented in ROADMAP.md:1115.

## DEC-157: Human adjudication display — join criteria/player_message/observed from the transcript, not the batch files

**Date:** 2026-08-09
**Status:** ✅ ACCEPTED (ask-gate for "changing a public interface with callers outside its module"
cleared by explicit human instruction for this task)
**Context:** `adjudicate.py`'s prompt showed only `scorer`, `record_id`, `pre_label`, and `output_text`
— `CalibrationLabel` had no field for the criteria being judged. For `in_set`/`range`/`schema` scorer
rows this made adjudication strictly impossible, not just hard: those matchers judge response fields
(`facial_expression.type`, `relation_deltas.trust`, …) that never appear in `output_text` at all. Every
such adjudication was a coin flip dressed up as a kappa measurement.

**Decisions:**

1. **`CalibrationLabel` gains three optional passthrough fields** — `criteria`, `player_message`,
   `observed: dict[str, Any]` — all defaulted (`""` / `""` / `{}`) so rows written before this change
   still parse. They are frozen like every other field on the model.

2. **The join source is the generation transcript, not `evals/calibration/batches/*.json`.** The batch
   files are a regenerable export artifact; coupling import to them would make label-import depend on
   something derived, not primary. `label_export.py:build_export_item()` already derives exactly these
   three values from a `GenerationRecord` (verbatim judge criteria, or `criteria_rendering` output plus
   the matcher's observed fields for deterministic records) — reused as-is rather than re-implemented.
   `label_import`'s `--transcript` argument was already required for `output_text`; it now also
   supplies criteria/player_message/observed via the same `ExportItem` the export step produces.

3. **The labeller contract is untouched.** `RawLabelRow` still has exactly four fields
   (`record_id`, `scorer`, `pre_label`, `notes`); `_CONTAMINATING_FIELDS` still rejects
   `output_text`/`scorer_verdict`. The three new fields are joined server-side from the transcript and
   never round-trip through the labeller — a labeller that could see them could echo them back
   uncritically, which is exactly the contamination `ContaminatedRowError` exists to prevent.

4. **File split, not a 300+-line exception.** Both `label_export.py` (336) and `label_import.py` (354)
   were already over the CLAUDE.md cap before this task and grew further with the join logic. `wc -l`
   by hand, since `scripts/check_rules.py` only scans `src/npc_engine` and `demo_game` — this directory
   is not gated automatically.
   - `export_item.py` (new, 170 lines): `ExportItem` + the `GenerationRecord → ExportItem` derivation
     (`build_export_item`, `build_export_items`, `_scorer_for_record`, `_expectation_for`,
     `GRAPH_SCORER_KINDS`). Extracted so `label_import`'s join step can reuse the derivation without a
     `label_export ↔ label_import` circular import. `label_export.py` re-exports the same names for
     backward compatibility with existing importers.
   - `transcript_index.py` (new, 78 lines): `build_transcript_index` (transcript → `item_id →
     ExportItem`, replacing the old `item_id → str` index) and `build_judged_index` (unchanged, moved
     as-is). `label_import.py`'s `_build_transcript_index`/`_build_judged_index` are gone; `main()` and
     `import_labels()` call the module functions directly.
   - `label_import_errors.py` (new, 66 lines): `UnknownRecordIdError`, `MissingVerdictError`,
     `ContaminatedRowError`, moved out verbatim. `label_import.py` re-exports them.
   - Result: `label_export.py` 336→222, `label_import.py` 354→274 — both now under the cap and smaller
     than found, per file.

**Consequences:** `evals/calibration_records.py`, `test_calibration_records.py`,
`test_label_import.py`, `test_adjudicate.py` extended; `test_transcript_index.py` added. `make check`
green except the pre-existing EVAL-P9.3 work-list failure (ROADMAP.md:1115). Verified by eye against
`evals/calibration/mock_labels.jsonl`: an `in_set` row's adjudication prompt now shows
`observed: {'facial_expression.type': 'neutral'}` alongside its criteria — previously invisible.

---

## DEC-165: The oracle labeller ships as four files, not one, and the guard lands before the labeller

**Date:** 2026-08-10
**Task:** EVAL-P15.1 (HUMAN_TASKS task 3)
**Status:** Accepted

EVAL-P15.1's file list is `create scripts/oracle_labeller.py`,
`create tests/unit/evals/test_oracle_labeller.py`, `edit Makefile`. The implementation is seven files.
Each departure is recorded here rather than left for a reader to discover as drift.

**1. `evals/synthetic_label_guard.py` + `tests/unit/evals/test_synthetic_label_guard.py` (new).**
The task body asks for the guard "in `label_import.py`". `label_import.py` was 260 of its 300 permitted
lines, so the check went to its own module and the two lines that call it went into `main()`. It is the
first thing `main()` does — before `read_raw_rows`, before any file is opened — so a refused run cannot
have begun writing. `test_label_import_main_refuses_a_synthetic_run_at_the_default_out` pins that ordering
by pointing the run at inputs that do not exist: if the guard ever moves after the reads, the test sees
`FileNotFoundError` instead of `SyntheticLabelTargetError` and fails.

**The guard was built and merged before a single line of the labeller.** `label-import --out` defaults to
`calibration_records.LABELS_FILE`, which holds 393 hand-made verdicts produced across two sittings. Writing
the labeller first and the guard second would have put a synthetic-label emitter and an unguarded default
in the same working tree at the same time, and no re-run reproduces those verdicts.

**2. `scripts/oracle_matrix.py` (new).** A single file held the models, the errors, the reader and the CLI
at 418 lines — over the 300-line cap. Split on the I/O boundary, which is also the SRP boundary: the
matrix model and the pure labelling rule (no file access, no RNG) on one side, the artifact reader and CLI
on the other. `oracle_labeller.py` re-exports the names so callers and tests keep one import site.

**3. `scripts/oracle_adjudicate.py` (new).** Not anticipated by the task, and load-bearing. The HEADLINE
calibration axis is `scorer_verdict` × `human_verdict`, but a labeller emits `pre_label`; something must
carry one to the other or the requested matrix never reaches the metric it was requested for. The existing
`scripts/mock_adjudicate.py` cannot do it: it draws `human_verdict` from `scorer_verdict` at a probability,
so `--agree-rate 1.0` yields `human_verdict == scorer_verdict` and collapses fp and fn to **zero** — the
exact opposite of a requested off-diagonal. The oracle adjudicator copies `pre_label` verbatim and nothing
else, which is what makes the matrix known before the run.

**4. `.gitignore` (edit).** Oracle artifacts follow `evals/calibration/mock_*.jsonl` out of the repo, for a
different reason: they are not random, but they are fully regenerable from the committed transcript plus
the declared rule. Committing them would put regenerable files inside a `FROZEN_PATH_PREFIXES` directory
that the loop's whole-tree staging (ISSUE-139) would then sweep into unrelated commits.

**The validation the task shipped with was unsatisfiable, and was corrected rather than satisfied.**
EVAL-P15.1's feasibility note proves `(tp=40, fp=5, fn=3, tn=12)` needs 15 negatives and that no scorer has
more than 8; its Validation line then mandated exactly that matrix. Following it literally would have meant
weakening the labeller until an impossible request succeeded — destroying the instrument in order to pass
the test of it. The naive matrix is struck as a validation and kept as the negative case
(`test_the_naive_example_is_rejected_and_the_caps_are_named`); `refusal_judge` (60, 8, 4, 3) replaces it.

**Why the expected κ is a literal and the test imports nothing from `evals/calibration*`.**
`_kappa_from_matrix(60, 0, 0, 0)` returns **1.0** today (Pe==1 short-circuit). EVAL-P16.3 is scheduled to
change that. A test that imported the function to compute its own expectation would pass in both worlds and
detect neither, so κ is a decimal literal with the arithmetic in a comment and a four-line local
re-implementation. 296/1196 = 0.2474916… → **0.247**.

**Validation (measured, not predicted):** `make mock-calibrate-oracle GEN_ID=k3_73e6c36` →
`refusal_judge n=75`, matrix **60 / 8 / 4 / 3**, headline κ **0.247** 95% CI [−0.071, 0.539] — the counts
requested and the κ computed by hand. `label-import --model oracle-matrix-v1` with the default `--out`
raises `SyntheticLabelTargetError`, verified on the live CLI; `git diff evals/calibration/labels_v1.jsonl`
is empty afterwards. The matrix saturates that scorer exactly (68 True + 7 False = 75) and has zero slack.

---

## DEC-168: capability cases are grounded in beliefs, goals and memories — never in secrets

**Date:** 2026-08-10
**Context:** Authoring the nine EVAL-P20.2 capability cases. Each of the nine NPCs holds a
`KNOWS_SECRET` edge, and the secret is usually their most lexically distinctive material —
`sec_sera_barmaid` (a dead drop she does not know she is), `sec_nel_pickpocket` (a ring
hidden from Lira). Grounding a case there would have been the easiest way to get tokens
that no player prompt supplies.

**Decision:** no capability case is grounded in a secret. Where the secret is the most
distinctive material, the case is grounded in the adjacent belief or memory instead —
`sera_barmaid` on what she overheard (`mem_sera_barmaid_0`), `nel_pickpocket` on Lira's
tests (`bel_nel_pickpocket_77ebc2b0`).

**Rationale:** a `case_pos_*` awards a point for surfacing the grounded fact. A case
grounded in a secret therefore rewards disclosure of the thing the NPC exists to keep, and
puts the capability battery in direct opposition to the guard battery on the same NPC. The
two batteries are meant to be complementary, not a trap where every answer loses one of
them.

**Consequences:** recorded in `docs/CAPABILITY_CASES.md` under the grounding table, so the
next authoring session does not rediscover the shortcut. Not mechanically enforced — a
future case could still cite a `sec_*` node in `relevant_node_ids` legitimately, as
context the retriever should have surfaced, without expecting disclosure.


## DEC-171: `prior_human_verdict` clears on re-adjudication rather than persisting (EVAL-P19.0)
**Date:** 2026-08-12
**Context:** EVAL-P19.0 made `needs_review` load-bearing: `adjudicate.collect_pending` now
re-surfaces a drifted row (content changed under an existing human verdict) and needed a way
to show the adjudicator what they decided last time. Two options: (a) a new
`prior_human_verdict` field set transiently by `collect_pending` and cleared by
`apply_verdict` once the row is re-judged, or (b) leave it set permanently as an audit trail
of the row's adjudication history.
**Decision:** (a) — `apply_verdict` resets both `needs_review` and `prior_human_verdict` to
their clean state (`False` / `None`) on `keep`/`flip`; `skip` leaves both untouched so the row
stays pending.
**Rationale:** `prior_human_verdict` exists to answer one question — "what did I say about
the text I'm looking at before it changed?" — for exactly as long as that question is live.
Once re-adjudicated, the row carries a fresh verdict against its current content; a
permanently-set `prior_human_verdict` would leave every historically-drifted row visually
flagged forever with no way to tell "still needs review" from "resolved, FYI it drifted
once," which is the ambiguity `needs_review` exists to remove.
**Consequences:** No adjudication-history audit trail beyond the labels file's own git
history. If a later phase wants one, add it as an explicit `drift_history` list rather than
overloading this field again.

## DEC-173: Hedging pass/fail follows knowledge provenance, not response content (EVAL-P20.1)
**Date:** 2026-08-13
**Context:** `case_neg_captain_sorn_no_hedging` failed hedging while `case_pos_mira_gossip_hedging`
passed it, on a player prompt measured 0.71 similar — the battery scored one mechanism as both
the failure mode and the success mode. Human decision requested via AskUserQuestion; two other
candidate rules were considered and rejected — see below.
**Decision:** the case set's hedging rule is knowledge-provenance-based: an NPC answering from a
**direct** `KNOWS_ABOUT` edge (captain_sorn) must not hedge; an NPC answering from
**gossip-propagated** knowledge (mira, old_henryk) should hedge, and hedging there is a pass.
Written up in `docs/CASE_SET_POLICY.md`, which both previously-contradicting cases now cite.
This was already the *implicit* rule in three other cases' `notes:`
(`case_pos_mira_war_gossip_tokens`, `case_pos_old_henryk_war_rumor_tokens`,
`case_pos_captain_sorn_war_knowledge`) — this decision makes it explicit and load-bearing rather
than leaving it to be re-derived per case.
**Rejected alternative 1 (content-specificity rule):** hedging is neutral for every NPC; a
response fails only when a hedge carries a specific invented fact (name/place/figure) stated as
certain. Rejected as the *sole* rule because it would pass captain_sorn hedging about the war he
commands as long as he invents nothing while doing it — a voice failure this case set exists to
catch independent of factual content.
**Rejected alternative 2 (hybrid):** provenance sets the expected register, content-specificity
independently catches invented facts under any register. Rejected for this pass as unneeded
duplication of policy surface — no case currently exists where provenance alone would let a
hallucinated specific fact through under cover of a hedge. Revisit if one does.
**Also decided (same gate):** the 3 cases sharing the byte-identical player message "What is
happening in the north?" stay identical, declared paired in-file under two named categories
(same-NPC dual-lens; cross-NPC register-contrast) — see `docs/CASE_SET_POLICY.md` for the
full rule going forward. Two `make check-dead-keywords` wording-mismatch findings
(`case_neg_captain_sorn_no_hedging`'s `"i heard"`, `case_neg_lira_no_trust_disclosure`'s
`"thieves guild"`) were fixed in the same commit; ~200 remaining dead-keyword entries are
untriaged (ISSUE-157).
**Consequences:** `EVAL-P20.2` had already shipped in a separate, earlier commit before this
decision — the roadmap's "both ids land in one commit" constraint (H6) could not be
retroactively satisfied. Recorded rather than silently ignored.

## DEC-179: EVAL-P20-P24 unblock plan written — the real remaining blocker is H7, not H3/H4
**Date:** 2026-08-15 · **Status:** ✅ ACCEPTED (planning session, no roadmap/fence/regeneration changes)
**Context:** Commissioned to inventory every blocker from `HUMAN GATE H4` through `H12` covering
`EVAL-P20`-`EVAL-P24`, with live-measured (not checkbox-trusted) status for each. Mid-session, a
concurrent Claude Code session landed `DEC-178` (reopening `H3`/`H4` by explicit human override),
changing the premises this session started against. Re-verified live post-commit (`c183492`)
rather than re-derived from the stale prompt.
**Findings:** `H3`/`H4` are mechanically open now (DEC-178). `H6` was already cleared. **`H7` is
the real remaining blocker** — gated on three concrete subtasks: `EVAL-P20.3` (no decision needed,
loop-executable now), `EVAL-P20.3a` (2 `AskUserQuestion` rounds — docker-network topology,
`pre_label` staleness), `EVAL-P20.3b` (1 `AskUserQuestion` round, 4 options — label-drift trust
policy). `H8`-`H12` are all transitively closed behind `H7`/regeneration #1 and #2. Three new
issues logged (not fixed): `ISSUE-172` (`EVAL-P17.1`/`EVAL-P17.6` checked done but
`check-conservation` still exits 3 live — the program's own named failure mode recurring),
`ISSUE-173` (no mechanical enforcement of phase-level `Depends on:` lines), `ISSUE-174` (a
ROADMAP.md wording gap — `EVAL-P21.0`'s judge pick has no formal `AskUserQuestion` marker).
**Decision:** full inventory, dependency graph (topological layers), verbatim unresolved
`AskUserQuestion` options, and an ordered remediation plan are recorded in
`project-harness/EVAL_P20_TO_P24_UNBLOCK_PLAN.md`. This entry is the pointer; that file is the
source of truth going forward for "what's left before `EVAL-P24.3`."
**Top-line conclusion:** ~4-5 human sessions, ~15-20 hours of human time, plus two LLM generation
runs and Opus API time that don't block a human's clock. **Single next action:** run
`EVAL-P20.3` (free, no decision needed), then hold one sitting for the `EVAL-P20.3a`/`P20.3b`
`AskUserQuestion` rounds — that sitting is the highest-leverage single human action on the board,
since it's the only thing standing between "today" and regeneration #1.
**Consequences:** `check-conservation`'s 3 live failures (`ISSUE-172`) should be decided on — fix
before regen #1, or explicitly accept as residual risk — in the same sitting as `EVAL-P20.3a`/
`P20.3b`, per the unblock plan's Section 5. Neither regeneration should fire without re-running
`check_human_gates.py --check <task>` at the moment of decision, not by trusting this entry or the
plan file's snapshot.

## DEC-180: EVAL-P20.3a — docker-network topology (option a) and pre_label staleness (option a)
**Date:** 2026-08-16 · **Status:** ✅ ACCEPTED (`AskUserQuestion`, human session)
**Context:** `EVAL-P20.3a`'s two design calls, batched in one sitting per the unblock plan.

**Step 1 (ISSUE-131/167 — docker-network topology).** Chose **(a) drop the misleading `ports:`
block, shell eval/demo Makefile targets into the app container instead**, over (b) attaching
`neo4j` to the `public` network (which would have weakened the route-security posture the compose
file's own header comment documents). `docker-compose.yml`'s `neo4j` service no longer publishes
`7474`/`7687` — live-verified those mappings never worked anyway (`docker ps` showed no host
binding despite the `ports:` block; Docker silently voids host publishing on an `internal: true`-
only network). `demo-snapshot`/`demo-restore`/new `eval-world-reset` Makefile targets now run via
`docker compose run --rm -v "$PWD:/work" -w /work app python -m demo_game.snapshot ...`, verified
working live against the running stack (`npcsystem-app-1`, `npcsystem-neo4j-1`). `eval-retrieval`
(also named in ISSUE-131's own "Where" — `evals.engine_adapter` connects to Neo4j directly via
bolt, same host-unreachable problem) got the identical treatment. ⚠️ Docker Desktop's daemon went
unreachable partway through this session (environment issue, not caused by this change) before
`eval-retrieval` specifically could be re-run live — the other three targets sharing the exact
same command shape were live-verified minutes earlier. If a future session finds `eval-retrieval`
broken, re-check this first, not the topology fix.

**Step 2 (ISSUE-167 — eval-world reset path).** The live Neo4j graph held 31,215 `Quest` nodes,
3,486 `TickLease` nodes, 886 `Memory` nodes, etc. — accumulated eval-run state, not a usable
baseline. With explicit human confirmation (the wipe was blocked by the sandbox classifier as
destructive; re-confirmed via `AskUserQuestion` before overriding), wiped the graph
(`MATCH (n) DETACH DELETE n`) and reseeded fresh via `make demo-seed seed-village-world
seed-tavern-world` (all three idempotent). Snapshotted that clean state (281 nodes, 241
relationships) to `evals/fixtures/eval_world_baseline.json`, checked in as the reset target.
`make eval-world-reset` restores it. Re-ran `e2e/scripts/measure_reset_fidelity.py` fresh:
`fidelity=PARTIAL cleared=2 surviving=10 unobservable=6`, unchanged verdict from the prior
measurement, freshly stamped (`git_sha=694fa74`, `measured_at=2026-08-16T09:04:41Z`) in
`evals/reset_fidelity.json`/`docs/RESET_FIDELITY.md`.

**Step 4 (ISSUE-153 — pre_label staleness).** Chose **(a) widen `CalibrationLabel.pre_label` to
`bool | None`, clear on drift** over (b) a `pre_label_needs_review` mirror flag — most direct,
self-documents the invariant via the type. Rejected (b) because two fields (`pre_label` +
a review flag) must stay conceptually paired, which is exactly ISSUE-153's bug shape one level
down. `label_merge._refresh` now clears `pre_label`/`pre_labeller_model` on any detected drift
(not gated on `human_verdict is not None` — a stale opinion is invalid regardless of adjudication
state), since `pre_label`'s source (a separate, not-necessarily-fresh reference-labelling file,
`label_import.py`) means `incoming`'s value isn't trustworthy either. `calibration.py`'s three
secondary-axis functions (`pre_label_confusion_counts`, `pre_label_kappa`,
`pre_label_kappa_interval`) and `agreement_rate` now exclude `pre_label is None` rows via a new
`_secondary_axis_rows` helper, with the exclusion count surfaced in both `ConfusionCounts` (new
`n_excluded_pre_label_cleared` field) and the printed report — the same "don't silently shrink a
denominator" discipline the pre-existing `n_excluded_drifted` field already followed.

**Follow-on fix required by Step 4, same commit:** `evals/adjudicate.py`'s `keep`/`flip` commands
read `row.pre_label` directly — with `pre_label` now legitimately `None` on exactly the drifted
rows `collect_pending` re-surfaces (the primary re-adjudication workflow ISSUE-153 exists to
serve), `keep` would have silently set `human_verdict=None` (un-adjudicating the row) and `flip`
would have fabricated `human_verdict=True` from nothing (`not None is True` in Python). Added
`pass`/`fail` as direct-verdict commands for a row with no `pre_label` to compare against;
`apply_verdict` now raises `ValueError` if `keep`/`flip` is attempted on a `pre_label=None` row;
`_read_command` is now context-aware (only offers `pass`/`fail`/`skip` for such a row) so a
mismatched command re-prompts rather than crashing the interactive session.

**Step 3 (ISSUE-160, mechanical, no `AskUserQuestion` needed per the roadmap text).**
`label_merge._has_drifted` now also flags a `scorer_verdict` change on hash-identical
`output_sha256`/`criteria_sha256` as drift (real case:
`case_adv_lira_troop_positions:tone_judge:4#r0`, ordinary LLM judge non-determinism, DEC-146).
`format_merge_report`'s WARNING line now states the drift definition explicitly ("output/criteria
hash changed, or scorer_verdict changed on identical content") instead of leaving "N drifted"
ambiguous between "byte-identical" and "nothing about this row changed".

**Verification:** RED anchors `test_verdict_only_drift_flags_needs_review`,
`test_drifted_pre_label_excluded_from_secondary_kappa` both pass. `pytest tests/unit/evals
tests/unit/harness tests/unit/scripts` — 681 passed, 0 failed. `make check-docstrings
check-layers` — both green. Closes ISSUE-131, ISSUE-160, ISSUE-153, ISSUE-167.

**Consequences:** `evals/fixtures/eval_world_baseline.json` is now the canonical eval-world reset
target — regenerate it (`make eval-world-reset`'s snapshot half) only via a deliberate, logged
re-seed, never by hand-editing. A labels file written before this change may contain rows whose
`pre_label` is a stale `bool` the merge never had a chance to clear (rows that haven't been
re-merged since); this is expected — the clearing is a merge-time behavior, not a retroactive
migration.

## DEC-182: ISSUE-172 fixed — `check_conservation.py`'s own bugs, not the aggregators it audits
**Date:** 2026-08-16 · **Status:** ✅ ACCEPTED (fixed before regen #1, per explicit human choice —
see the H7-gate-check judgment call in the same session; chosen over deferring as accepted risk)
**Context:** `make check-conservation` had failed 3 of 4 identities live since at least
2026-08-12, despite `EVAL-P17.1`/`EVAL-P17.6` being checked `[x]` `✅ AUTO` with validation text
claiming exactly these identities were fixed. Logged as `ISSUE-172` during the EVAL-P20-P24
unblock planning session (DEC-179) as the program's own named failure mode (checkbox vs.
measurement) recurring.

**Root-cause finding, made before presenting the fix-now-or-defer choice:** the bugs were in
`scripts/check_conservation.py` itself, not in the aggregators it was auditing
(`evals/compare.py`, `evals/summary.py`) — those were already correctly fixed by `EVAL-P17.1`.
- **Identity 1** hardcoded `excluded = 0` instead of counting `case_stats.classify_battery`'s real
  `"excluded"` verdict. 9 cases (`case_001_grieving_elder`, `case_002_suspicious_guard`,
  `case_003_trade_offer`, `case_voice_captain_sorn_001`, `case_voice_mira_innkeeper_001`,
  `moderation_everyone_01/02/03`, `reputation_dialogue_tone_001`) are legitimately excluded from
  both batteries by design, not uncategorized — the hardcoded zero routed them all into
  `neither_cases`, reading a working classification as a coverage gap.
- **Identities 2 and 3** hand-read `judged.jsonl` only, modelling `compare.py`'s **pre-EVAL-P17.1**
  behavior. `compare.py` and `summary.summarize_from_dir` have called
  `verdict_sources.load_unified_rows` (reading both `judged.jsonl` and
  `deterministic_judged.jsonl`) since `EVAL-P17.1` landed — the checker script was simply never
  updated to match, so it kept reporting the pre-fix gap as if it still existed.

Verified before implementing: manually ran `load_unified_rows` against `k3_73e6c36` and confirmed
it sees all 307 unique record_ids and all 7 capability cases — exactly Identity 2/3's target
numbers — establishing this was a small, well-understood fix (~30-45 min, confined to
`check_conservation.py`) rather than an open-ended investigation, before the human was asked to
choose fix-now vs. defer.

**Fix:** `_check_identity_1` now counts `classify_battery`'s `"excluded"` result explicitly.
`_check_identity_2`/`_check_identity_3` now call `verdict_sources.load_unified_rows` directly —
the same shared unifier `compare.py`/`summary.py` already use — instead of re-implementing a
narrower, stale version of the same logic. `python -m evals` and `check_conservation.py` now
audit via the identical code path, so they cannot drift apart the way they did here (residual
risk: both would need to diverge from `load_unified_rows` for the check to blind-spot again —
logged as acceptable, not tracked separately).

**Test changes, deliberate not silent:** `tests/unit/scripts/test_check_conservation.py`'s
`test_residual_cases_are_reported_not_dropped` (pinned the pre-fix violation counts as *expected*)
renamed to `test_all_identities_hold_against_the_committed_artifact`, now pinning all-OK counts
(94 = 78 guard + 7 capability + 9 excluded; 307 = 307; 7 = 7). `test_violation_exits_nonzero`
switched from the real `k3_73e6c36` artifact (which no longer has a violation to detect) to a new
synthetic `_make_broken_fixture` — a capability case present in `outputs.jsonl` with no verdict
row in either file — proving the detector still catches a genuine violation. Module docstring
updated to explain the supersession for a future reader.

**Verification:** `make check-conservation` — live, exits 0, "All identities satisfied."
`pytest tests/unit/scripts tests/unit/evals tests/unit/harness` — 685 passed. `make
check-docstrings check-layers` — both green.

**Consequences:** `HUMAN GATE H3`'s condition 1 (`EVAL-P17.6`'s live check green) is now genuinely
met — only condition 3 (`EVAL-P20.0`'s ≥95% reproduction gate, still 62.5% per DEC-176) remains
unmet of the three DEC-163 reopen conditions. All prose paragraphs in `ROADMAP.md` asserting
"`EVAL-P17.6`'s live check still fails" (the top-of-file queue-fence comment, the Program-3
"Fence policy" paragraph, `HUMAN GATE H3`'s own override note, `EVAL-P20`'s phase header, the
`LOOP:QUEUE end` marker's inline note) were updated in this same commit — this project's own
repeated failure mode is stale fence-state prose, and leaving five contradictory paragraphs after
fixing the underlying fact would recreate it. `ISSUE-172` closed, archived.

## DEC-192: a destructive graph restore is one transaction, and it detects the live writer
rather than asking the operator to promise there isn't one
**Date:** 2026-08-20
**Decided by:** the maintainer, this session, choosing between the two options ISSUE-188 left
open.

**Context.** `demo_game/snapshot.py --mode restore` backs `make demo-restore` and
`make eval-world-reset`, and `eval-world-reset` is what makes two generation runs comparable
(ISSUE-167). It wiped the graph and then created each snapshot node in its own auto-commit
transaction. The engine's tick autopilot is on by default (`config.py:177-178`,
`TICK_INTERVAL_SECONDS = 10`) and MERGEs `:WorldState` on every tick, so a tick landing inside
the restore window collided with the `:WorldState.id` uniqueness constraint. The wipe had
already committed: the 2026-08-19 22:19 run left 139 of 248 nodes and exited non-zero, with
nothing marking the graph as half-restored.

**Decision 1 - one transaction.** The wipe, every create and the sentinel strip run inside a
single `session.execute_write` work function. Any failure rolls back to the pre-restore graph.
`CREATE` after `DETACH DELETE` in the same transaction does not self-collide, because
uncommitted deletes are invisible to the constraint check. The driver may retry the work
function on transient errors, which is safe only because the wipe is its first statement - if
that ordering ever changes, the retry semantics change with it. The trade accepted: against a
live writer the restore now blocks on locks and raises, instead of writing a partial world.

**Decision 2 - probe, not an acknowledgement flag.** ISSUE-188 offered either an explicit
`--i-know-the-app-is-stopped` flag or a live-writer check. The probe was chosen for two reasons.
First, the flag is a checkbox an operator can tick while the app is running, and it would have
broken all three existing call sites. Second, `snapshot.py` executes *inside* the app image via
`docker compose run` (Neo4j has no host port - ISSUE-131) and has no docker socket, so it can
never stop the app itself; detect-and-refuse is the strongest thing it can do from where it
runs. `demo_game/restore_guard.py` fingerprints node count, relationship count and every
`:WorldState` id/tick_id/last_updated_at, waits `SNAPSHOT_PROBE_SECONDS` (default 12), and
fingerprints again; a difference aborts before the wipe with exit code 2. The default is
deliberately *longer* than `TICK_INTERVAL_SECONDS`: any 12-second window contains a tick
boundary, so a running autopilot is caught with certainty rather than probabilistically. Raising
`TICK_INTERVAL_SECONDS` without raising this constant silently weakens the guard.

**Decision 3 - the Makefile owns app lifecycle, the guard owns safety.** `demo-restore` and
`eval-world-reset` now delegate to a shared `restore-with-app-stopped` target that stops the
app, restores, brings it back up and waits on `/health`, mirroring
`project-harness/Run-OvernightCombined.ps1`. The ops script keeps its own inline copy because
the make recipes are POSIX/Git-Bash-only (ISSUE-187) and unusable from PowerShell. That
duplication is accepted: the convergence ISSUE-188 asked for is delivered by the guard living in
the shared Python both paths call, not by either wrapper. A future wrapper that forgets to stop
the app now gets a clean refusal instead of a corrupted graph.

**Rejected:** `SNAPSHOT_PROBE_SECONDS=0` exists as an escape hatch for tests and for a Neo4j
instance known to be isolated. It is not wired to any target and is not a supported operator
workflow; the 12 s cost of the probe is negligible against a restore that precedes a 10-hour
regeneration.

---

## DEC-199: `prompt_token_budget` in a trend row comes from the engine's receipts, never
## from meta.json
**Date:** 2026-08-26
**Decided by:** this session, wiring the six A/B plumbing fixes after the 2026-08-25
false-provenance run. **Drives:** `evals/trend_row_builder.py`.

**Context.** `trend_row_builder._variant_fields` read `prompt_token_budget` out of
`meta.json`'s `config` block. Nothing has ever written that key, so every trend row ever
recorded carried `null` — a field that looked measured and was not. The obvious fix is to
have `evals/run_config.py` stamp it into `meta.json` at generation time.

**Decision.** Derive it from the transcript's context receipts
(`GenerationRecord.context_receipt.prompt_token_budget`) and remove it from `_variant_fields`.

**Why not stamp meta.json.** `run_config` runs on the **client**. The budget is the
**engine's** — it is the number `context_builder` actually held the assembly to. A
client-side stamp asserts a value nothing verified, which is precisely the failure mode this
whole batch exists to close: the 2026-08-25 arm claimed a git SHA that the container it
talked to had never run, because the SHA was written by the caller rather than read from the
callee. Re-creating that pattern in a new field would be the same bug with a different name.
Importing `npc_engine.config.Settings` into `evals/` to read the budget locally is the same
mistake wearing a library: it reports what a fresh process *would* configure, not what the
running engine *did*.

**Disagreement is a finding, not a number to smooth.** When receipts disagree the row records
`None` and logs a warning naming the distinct values. Averaging them, or taking the first,
would publish a budget no turn was actually held to. Absent receipts (every arm generated
before the field existed) also record `None`, so a gap stays visible in the trend rather than
reading as continuity.

**Kept out of `_variant_fields` deliberately.** `comparability_key` calls `_variant_fields`
for `judge_identity` alone and must stay cheap — `--print-baseline` answers "which row would
this be gated against" before any summarise-and-calibrate work. Reading a transcript there
would make a cheap probe expensive for a field it never looks at.

## DEC-201: the relevance scorer reads the payload shape its producers actually emit, and the
## configured weights are the weights that run
**Date:** 2026-08-26
**Decided by:** this session, P2 of the context-pipeline plan ("make the scorer's config live").

**Context.** Two defects, both latent-looking on paper, both measured live.

**Defect 1 - every inner-life item scored recency 0.0 and severity 0.0.** `_build_candidate`
parsed `item.text` with `parse_json_object`, whose contract is "a dict, or `{}`". Every item
carrying an NPC's own state is serialized by `_build_tier_a_extended` as a JSON **array** of
records - `beliefs`, `goals`, `memories`, `secrets`, `obligations`, `owned_items`,
`reputation`, and likewise `traits`, `believed_rumors`, `nearby_npcs`. All of them parsed to
`{}`. A belief held with confidence 92 scored severity 0.0; so did a goal at urgency 100 and a
memory at emotional_charge -95. The four severity fallbacks in `_extract_severity_score`
(`severity` -> secrets, `urgency` -> goals, `confidence` -> beliefs, `emotional_charge` ->
memories) were each written FOR one of those items and could not be reached by any input the
engine produces. Recency was lost the same way. Those items were therefore ranked on proximity
and producer priority alone - and under the tier-A cap, ranking is what decides who reaches the
model (ISSUE-163).

**Defect 2 - `relevance_weights:` was a required YAML field nothing consulted (ISSUE-198).**
`default_weight_profile` defaults to the name `"default"`; `resolve_weights` found that name in
`DEFAULT_WEIGHT_PROFILES` and returned the Python literal. The two held identical numbers, which
is precisely why nobody noticed.

**Decision 1 - fix at the call site, not in `parse_json_object`.** Its "dict or `{}`" contract is
correct and has many callers; widening it to unwrap arrays would change behaviour in code that
has nothing to do with scoring. New private `_payload_for_scoring` in `context_scoring.py` owns
the scorer's own notion of "the record to score".

**Decision 2 - score the FIRST record of an array, not a merge or a maximum.** Arbitrary on its
face, and defensible from the producers: `belief_queries` ORDER BY `confidence DESC`,
`goal_queries` BY `urgency DESC`, `memory_queries` BY `vividness DESC`, `secret_queries` BY
`severity DESC` - for three of those four the ordering key IS the field the severity fallback
reads, so the first record is the strongest one. Where `rerank_by_keyword` has reordered
beliefs, goals and secrets, the first record is instead the one most relevant to the player's
message. Both are the producer's own idea of "best", and neither requires the scorer to know
which producer it is looking at. A maximum over records was rejected: it needs a per-key table
of which field to maximise, which is the hand-maintained mapping P5 exists to delete.

**Decision 3 - remove `"default"` from `DEFAULT_WEIGHT_PROFILES` rather than delete the YAML
field.** The alternative in ISSUE-198 was to drop `relevance_weights` and make the profile
registry the only source. Rejected: `relevance_weights` is a REQUIRED field of `LLMConfig`, so
deleting it is a breaking config-schema change for every `llm_config.yaml`, and it removes the
only place a config can state a default without naming a profile.

**Measured effect.** Rebuilt image, `GET /v1/admin/debug/retrieval?query=what+news`, the same
8 NPCs as ISSUE-163 and DEC-198. Only P2 changed between the two columns:

    field           after P1   after P2
    npc.beliefs        3/8        8/8
    npc.goals          6/8        8/8
    npc.memories       3/8        4/8
    npc.top_need       0/8        0/8
    current_location   0/8        0/8
    assembled tokens  635-829    536-729

**Consequence, stated plainly - inner life went up and total tokens went DOWN.** That is not a
paradox: the fat low-signal items lost the ranking to the small high-signal ones, so the budget
pass now skips them. On `mira_innkeeper` the 505-token `relation:player` item was displaced by
`nearby_npcs` (91) and `npc_known_events` (72), both of which had been empty. The cost is that
`player_relation` measured **0/8**, down from at least 1/8: the relation payload carries no
severity-family field at all, so it scores severity 0.0 while a belief scores 0.8. The ordering
is right and the item is wrong - 505 of its ~505 tokens are a `delta_log` of six all-zero delta
records. Recorded on ISSUE-199, which P3 fixes; until then the player relationship reaches no
prompt. In the seeded worlds every trust/fear/affection value is 0, so nothing of substance is
lost today.

**Not done, deliberately.** The plan's third P2 bullet asked for the literal producer priority
to be captured into `ContextRelevanceCandidate` so its meaning is fixed at capture. On
inspection it is already fixed at capture: `relation` is computed in `_build_candidate` from the
pre-rank item and frozen onto the candidate, and `rank_context_candidates` reads
`candidate.relation`, never `candidate.item.priority`. Adding a `source_priority` field nothing
reads would be churn, not anti-churn. The real invariant - that ranking an already-ranked list
would flatten the relation term to a constant 1.0, because post-rank priorities are
`max(1, 1000 - index)` and all clamp - is now a comment at the arithmetic in
`_extract_relation_score`, next to the code it constrains.

**Corrected after review, same day.** The producer audit above listed four array producers and
called out `memories` as the one whose ordering key (`vividness`) is not the field the severity
fallback reads (`emotional_charge`). It missed a fifth: `active_pledges` is
`ORDER BY e.sworn_at_tick DESC` yet its records carry `severity`, which
`_extract_severity_score` checks first -- so that item scores the severity of the most recently
sworn pledge. The `_payload_for_scoring` docstring now carries the full alignment table for all
six array producers rather than a prose claim about four of them, and the two unaligned cases
are ISSUE-206, to be folded into P5 where the per-key field mapping becomes one column of the
declaration table instead of a new hand-maintained dict.

## DEC-228: the eval program is culled to a minimal trustworthy instrument
**Date:** 2026-08-28
**Context:** 46 of 65 unchecked roadmap items were eval meta-work, and 8 of 8 active programs were
eval/harness. The 2026-08 triage established that the instrument those items were extending is
broken in two independent ways: a null responder emitting one fixed string scores 0.949 against the
engine's 0.897 on the guard battery whose published figure is 0.914 (ISSUE-229), and
`run_config.resolve()` records `generation_model_digest=None` wherever Ollama is absent, including CI
(ISSUE-231) — so no score is attributable to a model. Extending an instrument that cannot measure
produces more unmeasurement.
**Decision:** Cull to what a local-model A/B actually needs: base-rate gate, null baseline,
model-digest pinning, one working judge, and trend comparison once two comparable rows exist. That is
R2, seven items. Programs 4 and 5 (EVAL-P25..P31 — the golden-set rebuild, judge repair, and the
first-class prompt arm, 25 unstarted items) are **retired**; their specifications remain at
`619dab2`. Program 3's unchecked remainder is superseded by R2.
**Consequences:** The roadmap's eval surface drops from 46 unchecked items to 7. `check-base-rate`
(386 lines) is wired because it measures the ISSUE-229 breach directly; `check_engine_coverage`
(658 lines, reachable from no `make` target) is deleted. The trend/regression stack (1,309 lines, one
row) is **kept and integrated** rather than deleted — trend comparison is precisely what a model swap
needs, and it is unusable today only because ISSUE-231 nulls the identity that makes rows comparable.

## DEC-234: `roadmap_cursor.py --slice` was broken on Windows and had never worked
**Date:** 2026-08-28
**Context:** `/expand-linear-next` step 1 is `python scripts/roadmap_cursor.py --slice <PHASE>`,
and the skill instructs the session never to read the whole roadmap because the slice is what
keeps its context small. On Windows, stdout defaults to cp1252, which cannot encode `⏸️`
(`DEFERRED_TOKEN`) or `✅` (written into every `--mark` marker) — so `--slice` died with
`UnicodeEncodeError` on any phase containing either. Verified against **both** the new roadmap
and the archived pre-remediation one, so this predates today's rewrite: the loop's very first
command has never succeeded on this machine. It is a plausible contributing cause of night one
burning 11.45 h on a single issue.
**Decision:** `roadmap_cursor.py` reconfigures stdout/stderr to UTF-8 with `errors="replace"` at
import. Chosen over stripping non-ASCII from the roadmap because `⏸️` *is* the grammar — the
cursor's own skip token — so the file cannot avoid it.
**Consequences:** `--slice` works on both roadmaps. This is a harness bug fixed outside the
remediation phases because it blocks the program's execution mechanism; it is not counted as an
R-item.

## DEC-240: calibration kappa is authoritative for the MDE model
**Date:** 2026-09-01 · **Status:** ✅ ACCEPTED · **Closes:** ISSUE-244 (partially — see ISSUE-253/254)
**Drives:** `evals/mde.py`, `evals/arm_probe_report.py`,
`tests/unit/evals/test_kappas_match_calibration.py`
**Context:** Three kappa families circulated for the same three scorers, and `evals/mde.py` had
picked the wrong one:

| Family | tone | affirms | refusal | What it measures |
|---|---|---|---|---|
| Calibration vs human labels | **0.849** | **0.530** | **0.247** | judge vs ground truth |
| Inter-panel Fleiss | 1.000 | 0.282 | 0.225 | judge vs judge (what mde.py held) |
| Per-criterion panel Fleiss | 0.753 | 0.519 | 0.422 | per-criterion judge vs judge |

**Decision:** `RECORDED_KAPPAS` records the **calibration** family. The deciding argument is what
the number is used for: `arm_pairing_mde` computes `true_mde = observed_mde / kappa`, undoing judge
noise to recover the underlying effect. The noise that matters there is disagreement with ground
truth, which only calibration measures. Inter-panel agreement measures whether three judges share a
bias — and three judges can agree perfectly while all being wrong. `tone_judge` was unanimous
135/135, which is precisely how it came to read 1.000; a kappa of exactly 1.000 makes the division
a no-op and asserts the judge contributes no noise, which is never true.

**Recomputed, at the recorded n=78 pairs / 6.4pp floor / implied p_d 4.07%, comparisons=1:**

| criterion | κ before → after | TRUE MDE before → after | n for a 6.4pp true effect |
|---|---|---|---|
| tone_judge | 1.000 → 0.849 | 6.4pp → **7.5pp** | 78 → **108** |
| affirms_judge | 0.282 → 0.530 | 22.7pp → **12.1pp** | 981 → **278** |
| refusal_judge | 0.225 → 0.247 | 28.4pp → **25.9pp** | 1,541 → **1,278** |

`observed_mde` is unchanged at 6.4pp by construction: `implied_discordance_rate` inverts the
recorded floor at the recorded n, so re-applying it returns the floor. Only `true_mde` moves, and
only through kappa. Note these differ from the review's quoted 17.25pp / 29.01pp, which were
computed at a different `comparisons` (Bonferroni) setting; the values above use the default 1.

**Provenance, recorded so it is not mistaken later:** all 393 calibration labels carry
`gen_id: k3_73e6c36`, not the current `k3_77688e7_regen1`. That is correct — calibration describes
the judge, not the generation — but it means these kappas do not move when a generation lands, and
they go stale when the judge prompts change. Nothing currently gates that staleness.

**Not decided here:** whether `refusal_judge` should be retired. At κ 0.247 it still needs ~1,278
pairs to detect a 6.4pp true effect against the 78 available, so the retirement argument survives
the correction — but that is R2.6f and it is a human call. This entry only makes the input honest.
**Alternatives rejected:** (a) *Keep the panel family for continuity* — it is the family that
produced a 1.000, which is the defect. (b) *Average the three* — averages of measurements of
different things are not measurements.

## DEC-246: the session_kwarg tests are retired by rename, not deleted wholesale
**Date:** 2026-09-02 · **Status:** ✅ ACCEPTED · **Implements:** R4.3 (part)
**Drives:** 15 test functions across 15 files under `tests/unit/engines/` and `tests/unit/graph/`

**Context:** ROADMAP:310 specifies "delete the `session_kwarg` tests", on the premise that 61
references guard a parameter `military_engine.py:34` does not have. Two corrections, both
measured at HEAD with `__pycache__` excluded:

1. There are **16** references across **15** files, not 61. The quoted figure counted `.pyc`.
2. The problem is worse than the ROADMAP states. **Not one of the 15 tests passes `session=`.**
   Every one calls `run_tick(tick_id=...)` or equivalent. And no `run_tick` in `src/` accepts
   `**_` — so a test "fixed" to actually pass `session=` would `TypeError` on all of them.

They are phantom guards in the strict sense: the name and docstring assert a contract the body
never exercises and the code no longer honours. The scheduler confirms it from the other end —
every call it makes is `run_tick(tick_id=tick_id)`.

**Decision:** delete only those that are a strict subset of a sibling; rename the rest to what
they actually test. Deleting all 15 would discard real assertions that exist nowhere else, and
the ROADMAP's deletion premise was reasoning from a reference count, not from the bodies.

**Renamed (7)** — each asserts something no sibling does:

| file | new name | what it actually covers |
|---|---|---|
| `test_faction_politics_engine.py` | `test_run_tick_returns_zero_counts_when_there_are_no_events` | empty input; the sibling covers *non-matching* input |
| `test_intent_formation_engine.py` | `test_run_tick_returns_zero_counts_when_no_pairs_are_collocated` | the empty path; only the populated path existed |
| `test_military_engine.py` | `test_run_tick_reports_zero_counts_when_nothing_resolves` | the return shape; the sibling asserts awaits only |
| `test_need_decay_engine.py` | `test_a_single_need_decays_by_its_decay_rate` | exact arithmetic 50 → 40 for one need |
| `test_proactive_tick_adapter.py` | `test_run_tick_returns_no_lines_when_no_pairs_are_collocated` | the empty path plus the single-query assertion |
| `test_reputation_engine.py` | `test_run_tick_is_a_noop_when_the_engine_is_disabled` | disabled config through `run_tick` |
| `test_story_pacing_engine.py` | `test_run_tick_defaults_to_max_severity_when_no_quests_are_active` | no quests at all; the sibling covers no *high-severity* quest |

**Deleted (8)** — each verified line by line as a strict subset of a named sibling:
`test_goal_former_adapter.py` (⊂ `test_run_tick_calls_form_goal_for_each_npc`),
`test_gossip_n_plus_one.py` (⊂ `test_gossip_tick_result_counts_match_pairs`, which already
asserts `tick_id`), `test_mood_contagion_engine.py` (⊂ `test_run_tick_returns_affected_count`),
`test_routine_engine.py` (⊂ `test_character_moves_to_scheduled_location`, same fixture and a
stronger assertion), `test_skill_progression_engine.py` (⊂ `test_awards_xp_per_completed_skill_row`),
`test_succession_engine.py` (⊂ `test_vacant_title_triggers_succession`),
`test_event_handler_port.py` (⊂ `test_run_tick_forwards_faction_to_emit`, which asserts the same
`created == 1` and more), `test_player_model_tick.py` (⊂ `test_run_tick_derives_and_persists_per_pair`).

**Proof:** `grep -rn session_kwarg tests/ src/ --include=*.py | grep -v __pycache__ | wc -l`
returns 0 (16 before). The engines and graph unit suites go 1521 → 1513 passing: exactly the
eight deletions, no collateral loss.

**Rejected:** *delete all 15* — loses seven distinct assertions to satisfy a grep. *Rename all
15* — leaves eight tests that duplicate a sibling exactly, which is the vacuity R1.2 exists to
reduce. *Make them genuinely pass `session=`* — they would all fail, correctly: nothing accepts
it any more. That is the finding, not a repair.

---

## DEC-247: assertion-free tests are annotated, not deleted — the ROADMAP's premise is false
**Date:** 2026-09-02 · **Status:** ✅ ACCEPTED · **Implements:** R4.3 (part)
**Drives:** 25 test functions across 18 files, `scripts/check_test_quality_baseline.txt`

**Context:** ROADMAP:307 directs deleting "the 47 zero-call and 23 assertion-free tests — a test
that calls nothing or asserts nothing cannot fail". Measured at HEAD:
`python scripts/check_test_quality.py` reports **25 NO_ASSERTION findings and zero zero-call
tests**. The 47/23 split does not reproduce.

More importantly the premise is **false for this population**. All 25 are the shape *call the
SUT, assert nothing*, and `check_test_quality.py` classifies them `NO_ASSERTION` precisely
because a call is present (`body_has_call`). Such a test fails when the call raises — which is
the entire contract for every one of them. `test_save_swallows_graph_error`,
`test_exception_does_not_propagate` and `test_main_does_not_crash_on_cp1252_stdout` exist to
prove an exception does *not* escape; deleting them would delete the only coverage of the
swallow.

**Decision:** give each an explicit assertion where one genuinely strengthens the test, and a
`# quality-ok: <reason>` naming the protected contract everywhere the contract really is "this
call must not raise". Re-record the baseline 25 → 0 in the same commit so the ratchet cannot
drift back.

**Assertions added (4)** — these had one available that says more than "it returned":

| test | added |
|---|---|
| `test_clear_noop_for_absent` | `assert store.get("ghost") is None` |
| `test_noop_when_no_session` | `assert store.get("ghost") is None` |
| `test_run_tick_is_a_noop_when_the_engine_is_disabled` | `apply.assert_not_awaited()` — makes "without touching the graph" checkable rather than implied |
| `test_apply_mutation_produces_valid_python` | `assert "return ''" in mutated` — the mutation landed, not merely that the result parses |

**Waived (21)** — the contract is the absence of an exception, and the waiver says which one:
the three `check_prompt_window` coherence tests; the SEV-04 conformance test (which asserts by
`raise AssertionError` inside an AST walk, invisible to the scanner); both SEV-41 stream tests
(one of which asserts via a fake whose `reconfigure` raises if called); both input-moderation
pass-through tests; `test_handler_skips_when_engine_none`; `test_save_swallows_graph_error`;
both synthetic-label-guard tests; `test_emit_swallows_reputation_not_found`;
`test_ensure_relation_edge_ok_when_edge_returned`;
`test_ensure_quest_event_provenance_accepts_complete_payload`; both LLM-config validators;
`test_exception_does_not_propagate`; `test_main_does_not_crash_on_cp1252_stdout`; both
stack-launcher no-op tests.

That 21 of 25 are genuine "must not raise" contracts is the evidence for this decision, not an
excuse against it: a deletion pass would have removed 21 real regression guards.

**Nothing was ambiguous.** The brief required halting and logging an ISSUE rather than guessing
on any test whose intent was unclear; each of the 25 had a named contract recoverable from its
body, its sibling tests, or its fixtures, so no ISSUE was raised.

**Proof:** `python scripts/check_test_quality.py` → "0 issues found" (25 before);
`scripts/check_test_quality_baseline.txt` → 0 (25 before); `make check-test-quality` exits 0.

**Note on the RED anchor.** The obvious anchor — "the gate exits 1 today" — would have been
wrong: it exits **0**, because the baseline of 25 absorbed exactly the 25 findings. Anchoring on
the exit code would have been a green-today anchor. The anchor is the finding count plus the
baseline re-record.

---

## DEC-253: split context_builder on SRP, and time both scheduler paths with one helper

**Date:** 2026-09-03
**Status:** accepted
**Context:** `context_builder.py` was 799 lines against an unwaivable 800-line gate (DEC-226),
and `/v1/admin/system/engines` could say an engine ran but never how long it took.

**Decision (1) — the split is on category, not on line count.** `context_builder.py` held five
of CLAUDE.md's mutually exclusive SRP categories: model (`NeedSnapshot`), protocol
(`EmbeddingIndexProtocol`), reader (seven `_fetch_*`), builder (seven `_build_*`) and cache
state. Each moved to a module of its own — `context_need_models`, `context_graph_readers`,
`context_tier_builders`, `context_cache_state` — leaving an orchestrator-only module at 359
lines, under the 400-line advisory tier. The protocol was not moved but **deleted**:
`context_protocols.py` already defined it identically and `__init__.py` already re-exported it
from there, so the copy was dead weight.

The line count was the symptom and is deliberately not quoted in the new module docstring. The
previous note quoted "~448" against a real 799 — a number in prose rots, so `make check-rules`
owns the limit.

**Decision (2) — one `EngineTickTimer`, not a timer per call site.** `TickScheduler` runs
engines down two paths: `_run_engine_safe` for the simple per-tick engines and
`_run_distributed_interval` for the lease-held gossip and event engines (the latter is live by
default — `DISTRIBUTED_TICK_LEASE_ENABLED` is `True` at `config.py:239`). Those two had already
drifted apart in their error handling, which is the argument against duplicating a stopwatch
into both. `EngineTickTimer` owns the stopwatch, the store write and the metric emission; each
path keeps its own rule about *when* a run counts, so the distributed path still records only
when it actually held the lease (`row is not None`).

`tick_count` counts errors as well as successes: a tick that ran and raised still ran, and a
count that excluded failures would understate load exactly when an engine is misbehaving.

**Rationale:** the split had to be behaviour-preserving, and the honest risk was not the code
but the tests. Twenty-four graph readers are monkeypatched *by module path*, so moving the
readers moved the patch target. `monkeypatch.setattr` raises on a missing attribute, so every
stale target failed loudly rather than silently rebinding to a real graph reader — the failure
mode that would have made this refactor dangerous did not exist. `context_slots.PRODUCER_MODULES`
needed the two new producer modules for the same reason, and its contract test is explicitly
designed to fail when a producer module moves.

**Trade-off accepted:** this was NOT a zero-test-edit move. Twenty-four patch targets across
five test files and one import line were retargeted at the new modules. That is mechanically
equivalent to an import-path edit, but it is more than one, and it is recorded here rather than
described as a pure move.

**Explicitly not closed:** ISSUE-235. That gate counts `logger.info` sites inside `engines/`
that lack `duration_ms`; `scheduler/` is a different layer and none of those 42 sites is
touched. `scripts/engine_logs_baseline.txt` stays at 42.
## DEC-258: M1.2 splits `node_type` from `label` rather than PascalCasing `node_type`

**Date:** 2026-09-04, during M1.2 (ISSUE-213).

**Decision:** A base node contract declares **two** fields: `node_type:` is the registry key
(snake_case, API-facing, and the form `base_edges/*.yaml` reference in `src_type`/`dst_type`),
and a new `label:` carries the Cypher label the generic write path emits. `resolve_node_label`
resolves `BASE_NODE_LABELS` → declared `label` → key unchanged.

**Why not the prescribed fix.** ISSUE-213 and the M1.2 plan both prescribed correcting the
`node_type:` field itself to the PascalCase label. That cannot work, because
`base_contract_loader` derives the registry key by `node_type.strip().lower()`, so a PascalCase
value **collapses a multi-word key**. This is not hypothetical — it already shipped:
`ResourceNode` keys as `resourcenode`, `PendingIntent` as `pendingintent`,
`FactionStandingEvent` as `factionstandingevent`. `base_node_types.get("resource_node")` misses,
so a generic write with that node type raises `NODE_TYPE_UNKNOWN`, and
`base_edges/produces.yaml` declares `dst_type: resource_node` against a key that does not exist.

Applying the prescribed fix would have extended the same defect to `dialogue_turn`,
`narrative_beat`, `player_model`, `quest_template` and — worst — `world_state`, a **base kind**
that `generic_node_service._resolve_node_type` looks up as `world_state`. Every generic
WorldState write would have started failing. The prescribed fix was strictly worse than the bug
it was written to fix.

**Why two fields and not a smarter derivation.** The alternative was to keep one field and
derive the key with a Pascal→snake normaliser. That collapses two concepts with different
consumers and different constraints — the key is an identifier that appears in request payloads
and edge contracts, the label is a Cypher identifier — into one value, makes the key implicit,
and puts a casing algorithm with real edge cases (`NPCState` → `n_p_c_state`) on the hot path of
type resolution. Deriving the *label* from the key instead (`snake_to_pascal`) is correct for all
34 shipped kinds today, but gives the label no declared home at all and forces the first
divergent kind back into the hardcoded `BASE_NODE_LABELS` dict this work exists to stop growing.

**Why `BASE_NODE_LABELS` still wins.** Reading the declared label first is the inversion
ISSUE-213 originally prescribed, and it resolves `character` → whatever `character.yaml` says.
A lowercase value there 404s every eval case at `evals/runner.py:97`. The dict stays first as a
regression guard over the seven kinds the engine cannot function without;
`tests/unit/graph/test_node_label_contract.py` pins dict and YAML to agree, so the guard cannot
silently mask a divergence.

**Scope note.** The label is still written in two places overall — the registry YAML and ~90
hand-written Cypher files in `graph/` that use `:Belief` as a literal. This decision does not
unify those. It makes the YAML authoritative for the generic path and *pins* it to `graph/` by
test, each expected value cited to the query file that witnesses it.

**Governance.** DEC-250 froze `evals/`, `scripts/check_*`, `prompts/eval/` and
`docs/EVAL_*`/`docs/SCORER_*` "until R3 is green". This change touches none of those.

---

## DEC-263: `battery_trust.py` — a declared battery→judged-scorer map, worst-level-wins, additive gate

**Decision.** New module `evals/battery_trust.py` maps each of the three published batteries
(`adversarial`, `anti_hallucination`, `capability`) to the judge-calibrated scorers whose
verdicts feed it, and wires `scorer_trust_policy.check_publication` into `evals/summary.py`
(`_gated_rate_strs` -> `_one_battery_rate_str` -> `trust_gate`), then into `evals/report.py`'s
`write_report` via `battery_trust.load_current_scorer_kappas()`. This is the wiring
`docs/SCORER_TRUST_POLICY.md` already documented as required and that measured 2026-09-04 as
absent everywhere on the report-generation path.

**The map is declared, not derived (DEC-249).** `BATTERY_JUDGED_SCORERS` was read off the
`kind:` fields actually present in `evals/cases/case_adv_*.yaml`, `case_neg_*.yaml` and
`case_pos_*.yaml` (measured 2026-09-05: adversarial -> affirms_judge + commits_judge;
capability -> tone_judge only; anti_hallucination -> anti_hallucination_grounded, from the
scorer name in the calibration corpus, since no `ah_demo_*.yaml` case file exists any more).
Mechanical matchers (schema, keyword_none, keyword_any, in_set, range) are excluded on
purpose — they carry no Cohen's kappa, so `check_publication` has nothing to gate. `refusal_judge`
is excluded from `capability` on purpose too: no current `case_pos_*` case exercises it, and
touching it at all is out of scope (M3.2/ISSUE-276 stays halted).

**Worst level wins when a battery has 2+ contributing scorers.** `adversarial` currently names
two (`affirms_judge`, `commits_judge`); `battery_publication_status` takes the HIDDEN-beats-
RESTRICTED-beats-PUBLISHABLE maximum across whichever of them have a recorded `ScorerKappa`,
rather than averaging or requiring unanimity — a single untrustworthy contributor is enough to
make the combined rate untrustworthy, the same reasoning `check_publication` already applies
per-scorer (kappa AND CI floor must BOTH clear, CR-L03-02/DEC-244).

**A scorer with no recorded kappa does not gate its battery — absence of evidence, not evidence
of untrustworthiness**, mirroring `headline_refusal.refusal_for_battery`'s rule for an
unmeasured null baseline. Measured 2026-09-05: this is not a hypothetical — every one of the
five scorers in the post-negadv-merge `labels_v1.jsonl` is currently refused by
`label_adequacy.check_label_adequacy` (a floor below `check_publication`, on human-verdict
*count* rather than kappa), so `load_current_scorer_kappas()` returns `()` and every battery
renders trust-ungated today. That is a correct, honestly-reported state, not a silent pass —
see the M-programme report for what closes it (real `make eval-adjudicate` time).

**`evals/dashboard/headline.py` is deliberately NOT unified with this gate.** It already calls
`check_publication` itself, per-scorer, with its own two-tier (refused/shown) rendering — adding
a third RESTRICTED-caveat tier there, or replacing its logic with `battery_trust`, is a second
surface this task did not ask for and risks a dashboard regression with no test budget assigned
to it here. Logged as a natural follow-on, not fixed now (single-task focus).

**Additive, not widened (DEC-249's design bar).** `scorer_kappas` is a new keyword-only
parameter defaulting to `()` on `format_summary_lines`, `format_summary_markdown` and the
private `_gated_rate_strs`/`_one_battery_rate_str` — every existing caller that omits it
renders byte-identical output to before (pinned by
`test_no_scorer_kappas_argument_renders_ungated_as_before`).

**`load_current_scorer_kappas` duplicates `trend_row_builder._scorer_kappas`'s ~10-line glue
rather than importing it**, which is normally the wrong call per the PATTERNS.md "import a
sibling module's private helper" entry — but here it is required: `trend_row_builder.py`
already imports `summary` (`from summary import EvalSummary, summarize_from_dir`), so
`battery_trust` importing `trend_row_builder` would close a real cycle
(`summary` -> `battery_trust` -> `trend_row_builder` -> `summary`), not the "reads as a cycle
but isn't" case `comparability_key` calls out in that file's own docstring. The kappa *math*
still lives once, in `calibration.run_calibration`; only the "which four fields to pull into a
`ScorerKappa`" glue is duplicated.

## DEC-264: `latency_stats.py` dedupes by (case_id, repetition), not by GenerationRecord

**Decision.** `evals/latency_stats.py` computes p50/p95 turn latency by first collapsing every
`GenerationRecord` sharing one engine call down to a single `duration_ms` value, keyed on
`(record_id.split(":")[0], repetition)` — mirroring `label_adequacy._cluster_count`'s existing
case-cluster key. `generation_collection.stamp_records` stamps every expectation derived from
one `/v1/dialogue` call with the *same* `duration_ms`, so computing percentiles over raw records
would silently weight a case by how many expectations it happens to carry (a `schema` +
`keyword_none` + `commits_judge` case counts 3x a bare `schema`-only case) rather than by how
many turns actually ran. Nearest-rank percentile (`ceil(pct/100 * n)`-th smallest, 1-indexed) was
chosen over linear interpolation for the same reason `rate_stats`'s Wilson interval is exact
rather than approximate elsewhere in this codebase: a turn's latency is a real observed value,
and the reported percentile should name one of them, not an interpolated point between two.

**Wired as new optional `TrendRow` fields**, `latency_p50_ms`/`latency_p95_ms`, both `None`-
defaulted (the store is append-only; old rows have neither) and computed in
`trend_row_builder._latency_fields` from the same `read_transcript` call `_harness_version`
already makes — no new file read, no new I/O.

## DEC-266: several small calls made while fixing ISSUE-288, the labels-provenance counting
bug, and the pooled-panel-kappa reporting gap (eval/metrics remediation, 2026-09-07)
**Date:** 2026-09-07 · **Status:** ✅ ACCEPTED · **Drives:** `evals/judge_runner.py`,
`evals/judge_run_artifacts.py`, `evals/run_status.py`, `evals/trend_row_builder.py`,
`evals/panel_metrics_format.py`

**ISSUE-288 fix keeps the existing 0/1/2 exit-code contract.** A report-render failure
(guard-only generation, `_assert_paired_rates`) is caught in `judge_runner._render_report`
and recorded on `RunStatus.error`, but `main()`'s exit code still comes from
`passed == total` (0/1) per DEC-189, not a new code — the judging itself completed; only
the report render degraded, and that is a different fact than "the pass could not
complete" (exit 2). Ops scripts that branch on exit code are unaffected; scripts that want
to notice a degraded report must read `run_status.json`'s `error` field, which is now
non-empty in this case even though `status` stays `'ok'`/`'gate_failed'`.

**`labels_gen_id`/`labels_n` fix is a counting bug, not a data-placement problem — no file
split.** Investigated and rejected splitting `evals/calibration/labels_v1.jsonl`'s 354
un-adjudicated `k3_61b01dad_negadv` pre-labels into a separate file: every real
calibration computation (`label_adequacy.py`, `calibration.py`) already filters to
`human_verdict is not None`, so the merge never touched a real statistic. The one bug was
`trend_row_builder._labels_provenance` computing `gen_ids`/count over unfiltered rows;
fixed by filtering there instead. Smaller diff, same effect, and it also correctly
restores `_check_labels_attribution`'s foreign-labels refusal, which the same unfiltered
computation had been silently bypassing for any row recorded against the shared file.

**`k3_61b01dad_negadv`'s trend row is corrected via `allow_foreign_labels=True`, not left
at `(None, None)`.** Once `_labels_provenance` is fixed, building this row against the
shared `labels_v1.jsonl` correctly raises `LabelsGenerationMismatchError` (its own
adjudicated labels are still pending, so the only adjudicated labels in the file — 393,
`k3_73e6c36` — genuinely are a foreign generation's). Recorded with the explicit override
(`labels_gen_id="k3_73e6c36"`, `labels_n=393`) rather than pointing at an empty labels file
to get `(None, None)`: the override is the documented, honest way to say "these are
borrowed," and it is what a real `record_trend_and_gate` invocation would need today
regardless — this just does it once, in place, rather than leaving the bug's output
standing. `scorer_kappas` is unaffected either way (`()`, every scorer refused by
`label_adequacy`).

**Pooled-panel-kappa caveat reuses `scorer_trust_policy.HIDDEN_THRESHOLD` (0.40), not a new
constant**, and fires on a narrow, exact condition (pooled kappa clears the threshold while
every `by_criterion` entry sits below it) rather than a general "pooled vs. per-criterion
disagree" heuristic — narrower means fewer false positives on runs where pooling and
per-criterion genuinely agree, at the cost of not catching a partial mismatch (e.g. two of
three criteria below floor). Acceptable: the per-criterion breakdown is always printed
regardless, so a partial mismatch is still visible, just not specially flagged.

**ISSUE-289 (mypy_path) attempted and reverted, not fixed.** See ISSUE-289's own
2026-09-07 correction for the full finding: `evals/` mixes bare-sibling-import and
`evals.<module>`-absolute-import conventions across 11+ files, so adding `evals` to
`mypy_path` makes mypy abort on module-resolution collisions rather than surface a
countable batch of newly-real errors. `mypy.ini` is unchanged from before this session.

## DEC-268: measurement-remediation Phase 1 — a dedicated, isolated eval stack for
per-engine probes
**Date:** 2026-09-07 · **Status:** ✅ ACCEPTED · **Drives:** `docker-compose.eval.yml`,
`Makefile` (`eval-stack-*` targets)

**Context.** Per-engine probes (Phase 3/4) need deterministic control of the world clock
and freedom to mutate graph state without corrupting whatever world the default stack is
demoing from. Investigated before building: does the repo already have this?

**Finding: `CLOCK_MODE=game_driven` was already the effective default under any
`docker compose up` — ISSUE-264 is narrower than it reads.** `docker-compose.yml`'s `app`
service sets `CLOCK_MODE: game_driven` unconditionally in its `environment:` block, which
wins over `.env`'s `CLOCK_MODE=realtime` (Compose `environment:` beats `env_file:` for the
same key). ISSUE-264's "the shipped .env blocks `/clock/advance`" is true only for
`make run`'s bare `uvicorn` invocation, which has no compose file to apply the override.
Verified live: `POST /v1/clock/advance` against a freshly-built stack returned 200 with
`"mode":"game_driven"` on the first call, no `.env` edit needed. ISSUE-264 is not closed by
this finding (bare `make run` still has the gap) but this eval stack needed no fix for it.

**Design: layer `docker-compose.freeze.yml` in rather than duplicate its
`TICK_AUTOPILOT_ENABLED=false`**, and inline `docker-compose.test.yml`'s
`networks: [internal, public]` step for neo4j rather than chain that file — chaining both
would have tried to publish `test.yml`'s `127.0.0.1:7687` alongside this file's `:7688` on
one container, because Compose concatenates list-valued keys like `ports:` across files by
default rather than replacing them (confirmed by inspecting `docker compose config`'s
merged output before deciding, not assumed).

**The same concatenation bit the `app` service's port override during verification.**
`docker-compose.eval.yml`'s first draft added `ports: - "127.0.0.1:8001:8000"` for `app`;
`docker compose config` showed it published BOTH `8000` (from the base file) and `8001` to
one container, which fails to bind whenever the default dev stack already holds `8000` —
exactly the collision this file exists to avoid. Fixed with the Compose Specification's
`!override` merge tag (`ports: !override [...]`), which fully replaces the key instead of
appending to it. Verified via `docker compose config` before and after.

**Isolation achieved via a distinct project name (`-p npcsystem-eval`), not just ports.**
Compose derives container identity from `(project, service)`; without `-p`, two
invocations from the same directory reuse the SAME `neo4j`/`app` containers regardless of
what an override changes. `-p` gives genuinely separate containers, networks
(`npcsystem-eval_internal`/`_public`), and — combined with a distinctly-named volume key
(`neo4j_eval_data`, not the default `neo4j_data`) — a separate volume
(`npcsystem-eval_neo4j_eval_data`), so the eval stack can run alongside a plain
`docker compose up` or `make app-frozen` dev stack on one machine.

**`eval-stack-up` builds with `BUILD_SHA` stamped and `--build`, unlike `app-frozen`.**
`app-frozen`'s recipe (`Makefile:89-91`) omits both, so its own `boot_check.py
--expect-sha` assertion only passes by coincidence of a prior build matching HEAD.
Discovered live: the first `eval-stack-up` run built an image without `BUILD_SHA`, and
`boot_check.py` correctly failed it (`version='dev'` != HEAD's SHA). Fixed by mirroring
`boot-check`'s own pattern (`Makefile:82-84`) instead of `app-frozen`'s, rather than
weakening the assertion — `app-frozen`'s omission is a pre-existing inconsistency in this
same file, left alone as out of scope for this phase.

**Verified live, not just via `docker compose config`:** `make eval-stack-up` builds,
brings up an isolated stack, and passes `boot_check.py --expect-sha`; `POST
/v1/clock/advance` returns 200 with every one of the 25 tick-registered engines' per-tick
row in the response body (confirming the earlier validation finding that the advance
response, not `engine_status`, is the richer per-engine metric source — Phase 3's design
note); `GET /v1/clock/state`'s `engine_status` is fully populated with per-engine
`tick_count`/`error_count`/`last_duration_ms` for all 25; `make eval-stack-seed` seeded 236
demo-world nodes/edges against the isolated port with zero effect on any other stack; `make
eval-stack-reset` tore down containers, both networks, and the volume cleanly (confirmed
via `docker volume ls` / `docker ps -a` showing nothing left).

**Not done here:** no change to `evals/engine_adapter.py` — it already resolves
`NEO4J_URI` in one place via `get_settings()`, so "the eval stack's Neo4j URI resolved in
one place" was already satisfied architecturally; the Makefile's `EVAL_NEO4J_URI` default
(`bolt://localhost:7688`) exists for scripts that need direct graph access
(`retrieval_runner`, `arm_supply`) and is passed by the caller, matching the existing
`BASE_URL`/`API_KEY` override convention rather than inventing a new one.

## DEC-270: measurement-remediation Phase 3 — per-engine probe framework
(`EngineProbe`, `probe_runner`, `metrics` on `RepetitionRecord`)
**Date:** 2026-09-07 · **Status:** ACCEPTED · **Drives:** `evals/probe_protocol.py`
(new), `evals/probe_runner.py` (new), `evals/sequence_runner.py`,
`evals/sequence_fidelity.py`, `evals/sequence_rates.py`, `evals/__main__.py`, `Makefile`,
`scripts/evals_baseline.txt` (R002)

**Context.** Phase 2 (DEC-269) fixed *how* the three surviving judges are scored. Phase 3
is the next step in the governing measurement-remediation plan: a generalisation of
`evals/scenario_adapters*.py`'s six promoted scenarios, which return one `bool` per
k-repetition run, into a per-engine probe contract that returns a numeric metric dict. A
bool is one bit per run; the run's cost (a live tick, a reset, an HTTP round trip) is paid
regardless of how much the run reports, so paying it for one bit is the gap this phase
closes. This phase builds the framework only — no concrete probes. Phase 4 (unchanged,
not started) is where gossip/events/memory/quest/dialogue probes and context-budget
measurement land.

**1. `evals/probe_protocol.py` (new) — `EngineProbe` as a `typing.Protocol`.** Four
members: `engine_name: str`, `invariants: dict[str, InvariantFn]` (`InvariantFn =
Callable[[httpx.Client], bool]`), `setup(client)`, `drive(client, ticks)`,
`measure(client) -> dict[str, float]`. `setup()` is called once **per repetition**, not
once per probe instance — `reset_world()` wipes state between repetitions, so a probe must
re-seed every time, matching the existing convention in `scenario_adapters*.py` where
each `make_*()` factory's returned closure creates fresh entities per call. `invariants`
and `measure()` stay two separate concerns per the plan's own framing: metrics are
additive measurement, invariants are still boolean pass/fail correctness gating
`RepetitionRecord.passed`. No `@runtime_checkable` — nothing in this phase does an
`isinstance` check against the protocol; structural typing plus one conformance test
(`test_probe_protocol.py`) is enough (ISP/LSP: the mock matches the real contract's
shape).

**2. `evals/probe_runner.py` (new) — the k-repetition loop and the free engine-status
snapshot.** `run_probe(client, probe, k, ticks, reset_fn)` does reset -> setup -> drive ->
measure -> check invariants, k times, reusing `sequence_reset.make_reset_fn` for the reset
and `sequence_fidelity.sequence_stat`/`RepetitionRecord` for aggregation rather than
rebuilding either (the plan's explicit "reuse rather than rebuild" list). It does **not**
call `sequence_runner.run_sequence`/`_run_one` directly — `EngineProbe`'s
setup/drive/measure/invariants shape does not fit `ScenarioFn`'s bare `() -> bool`, and
forcing it through a closure that discards metrics to fit that signature would defeat the
entire point of this phase. Instead `probe_runner` builds `RepetitionRecord` instances
itself (`_run_one_probe_repetition`, mirroring `sequence_runner._run_one`'s
record-not-abort contract: a raising probe step is caught and recorded as a failed
repetition rather than aborting the k-set) and reuses the shared aggregation/receipt
types. `read_engine_status(client)` is a standalone `GET /v1/clock/state` snapshot,
independent of any registered probe — the plan's "free liveness and timing for all 46
engines, whether or not a probe exists" line. It is folded into a probe's own metrics
dict too (`_merge_status_metrics`, via `dict.setdefault` so the probe's own `measure()`
keys always win on a name collision) so every probe run gets `tick_count`/`error_count`/
`duration_ms` for its engine without writing a line of code for it. `EngineStatusSnapshot`
mirrors `npc_engine.scheduler.engine_status_store.EngineStatusRecord`'s field names by
hand rather than importing it — `engine_adapter.py` is the only sanctioned npc_engine
import point (DEC-147 §2), and this is an HTTP response contract, not a source-model
import; the same pattern `context_receipt_record.py` already uses for the engine's
`context_receipt` field.

**3. `RepetitionRecord.metrics: dict[str, float]` (additive, `sequence_runner.py`).**
Defaults to `{}` via `Field(default_factory=dict)` — every existing promoted-scenario
call path is unaffected, since no `ScenarioFn` today has a channel to populate it.
`run_sequence` threads `tuple(r.metrics for r in records)` into `sequence_stat(...)` (one
new line) so the field is never silently dropped even though nothing populates it yet.
`sequence_fidelity.sequence_stat` gained a `metrics: Sequence[dict[str, float]] = ()`
parameter and `SequenceStat.metrics_summary: dict[str, float]` — the mean of each key
across the repetitions that *reported* it (`_mean_metrics`; a key missing from some
repetitions is averaged only over the ones that have it, so a metric that only applies
under some post-drive state is not silently zero-padded into a misleading mean). Unlike
`interval`, `metrics_summary` is **never** fidelity-gated — a mean is descriptive
regardless of repetition independence; only the Wilson interval assumes i.i.d. Bernoulli
trials (SEQUENCE_STATS_POLICY.md §3, unchanged). `sequence_rates._format_stat_line`
appends a `" | metrics: k=v, ..."` suffix when `metrics_summary` is non-empty and nothing
when it is empty, so every existing scenario-report rendering and its tests are
byte-for-byte unchanged (verified: `test_sequence_runner.py`, `test_sequence_fidelity.py`,
`test_sequence_rates.py` all still pass, plus new tests added for every new branch).

**4. `probe` verb.** `evals/__main__.py` gained `VERBS["probe"] -> probe_runner.main`;
`Makefile` gained `eval-probe` (`make eval-probe [K=3] [TICKS=1]`), added to the
`.PHONY` list. With `PROBE_FACTORIES: dict[str, ProbeFactory] = {}` empty (Phase 3's
baseline — Phase 4 populates it, OCP: a new probe module arrives as a new file, no CLI
change needed), `main()` still does real, useful work today: it advances the clock once
and prints the free per-engine liveness/timing snapshot for all tick-registered engines.
It prints "No probes registered yet" rather than nothing, so a user is never left
wondering whether the command did anything.

**Found and fixed while implementing:** `_check_invariants`'s loop variable typed as
`Any` under mypy (returning `name` from `probe.invariants.items()` where `probe:
EngineProbe` is a `Protocol`) — fixed with an explicit `name: str` annotation rather than
loosening the return type. `_run_one_probe_repetition`, `run_probe` and `main` each
initially exceeded 40 AST-counted lines (R006) purely from full Args/Returns/Raises
docstrings on short bodies — resolved by extracting one helper from each
(`_execute_probe_cycle`, `_run_k_repetitions` + `_build_probe_result`,
`_build_arg_parser` + `_print_report`) rather than trimming documentation, matching
DEC-269's `matchers.evaluate()` precedent (extract, don't strip docstrings).

**Re-baselined `check-evals-rules`' R002 (print-in-evals) for the new
`evals/probe_runner.py`** via `make check-evals-rules-update`, adding one line to
`scripts/evals_baseline.txt` alongside the other CLI verbs' `main()` functions
(`sequence_rates.py`, `runner.py`, `generate_runner.py`, and the rest already
grandfathered there) — `probe_runner.main()`'s `print()` calls are the same kind of
verb-report CLI output every other `python -m evals <verb>` entry point already emits,
not a new class of violation.

**Not done here:** no concrete `EngineProbe` implementation for any engine — Phase 4's
job. No `ProbeFactory` is registered, so `make eval-probe` today only ever prints the
free engine-status snapshot; that is the intended Phase 3 baseline, not a bug.
`sequence_runner._run_one`'s own body is unchanged (metrics flows through it only because
`RepetitionRecord.metrics` has a default — no caller of `run_sequence` needed a new
`metrics_fn` parameter added, since none of the six promoted scenarios produce metrics
yet); adding one was considered and rejected as speculative for a phase with no caller
that would use it.

## DEC-282: Overnight-loop pre-flight review before the T programme — four repairs, two accepts
**Date:** 2026-09-09 · **Status:** ✅ ACCEPTED · **Drives:** `scripts/expand_loop.sh`

**Context.** Before greenlighting the T programme's overnight run, the driver and the roadmap were
reviewed for what decays over a multi-week programme rather than what fails tonight. Eleven candidate
defects were raised; five were withdrawn on adversarial re-check and are recorded here so they are not
re-raised. Net change: +24/-4 lines in one file, no new scripts, no new gates, no test churn.

**Withdrawn, with the reason.** (1) *The human-gate mechanism is dead* — true (`check_human_gates.py`
parses zero `#### HUMAN GATE` blocks from this roadmap, and its `TASK_ID_RE` still pins the retired
`EVAL-P` namespace) but harmless: zero gates blocks nothing, and **T0B.2 already reports deferred
tasks at both ends of every run**, which is the visibility that was actually missing. (2) *Flagged
tasks count toward `PhaseEntry.is_done`* — true and by design; same T0B.2 coverage. (3) *"Twelve
self-updating baselines"* — there are **eight** (`grep -oE '^[a-z-]+-update:' Makefile`), and they are
the repo's designed ratchet under a documented rule, not a defect. (4) *`demo-run-live` should block
`make check`* — that is an owner decision of 2026-09-08; relitigating it is out of order. (5) *Sprints
9-10 will not happen on their own* — the roadmap states this itself, in its own block quote.

**(a) The phase boundary launders a regression one task late — REPORT, do not change.**
`run_phase_gate` tolerates a red gate (rc=1 falls through at `expand_loop.sh:484`) and
`seed_gate_baseline` then re-seeds unconditionally, so phase N's unfixed failures become phase N+1's
"pre-existing debt" and `gate_attribution.py` returns `BASELINE_RED` for them forever.
**Suppressing the re-seed was considered and rejected as strictly worse:** a stale baseline makes
phase N's failures reproduce as `NEW` for phase N+1's *innocent* tasks, `gate_confirm.py` re-runs them,
they reproduce (they are real, just not that task's), and three `CONFIRMED` verdicts end the night on
false blame. The behaviour is therefore unchanged; the boundary now logs `baseline: N -> M` and raises
a `flag_for_human` when the baseline grows. Growth is a decision the operator makes with evidence
rather than one the loop makes silently.

**(b) `MAX_RED_COMMITS` becomes a per-run total.** The two `CONSECUTIVE_RED_COMMITS=0` resets on
`TASK_COMPLETE` and `PHASE_COMPLETE` meant the cap measured a streak, not a run: verified against a
simulated `REG OK REG OK REG OK REG` night, the old counter halts **never** and the new one halts at
three. Alternating good and bad tasks were unbounded, which is the shape a long programme actually
produces. The counter keeps its name and is now commented as a per-run total.

**(c) `loop-timeout` stashes join the pile-up guard.** `run_one_task` stashes a timed-out task's
partial work as `loop-timeout <task>` (`:593`) and nothing ever pops it; guard 4 (`:343`) counted only
`loop-auto-restart`, so the other kind accumulated uncounted. One `grep -c` became `grep -cE` over both.

**(d) `UNVERIFIED` ticks get one line in the end-of-run log.** `render_marked` sets `- [x]`
unconditionally and the `UNVERIFIED` suffix is cosmetic — `is_done`, `--phase-done` and `--status`
all count such a task as complete, and the only reader in the repo was a manual grep documented in
`OVERNIGHT_LOOP.md:62`. The run now prints the count and the command. The pattern is `UNVERIFIED (`,
matching the cursor's marker template, so the `[UNVERIFIED:` prose in T0.1's spec is not miscounted.

**(e) ACCEPTED, no change: four in-fence tasks edit `scripts/loop_gates.py`.** T4.2, T10.1, T10.2 and
T12.1 list it in `Files:`, which contradicts Sprint 0's header and T10.2's own "edit with the loop
stopped". The blast radius is bounded: each script is re-invoked fresh, so a bad spec surfaces as a
crashing gate, which reds, which halts at `MAX_CONSECUTIVE_RED_GATES=2` — recoverable and visible.
The alternative (pause-glyph all four) would move four gate-building tasks into a deferred backlog
that already has six items and one owner, which is the worse failure mode.

**(f) ACCEPTED, no change: T12.2 may edit `.github/workflows/ci.yml` unattended.** The skill's halt
table does not cover CI config — CI appears only in `project-harness/CLAUDE.md`'s ask-before list,
which the skill tells the agent to *read*, not to key on — so the realistic outcome is an edit, not a
halt. Accepted on the owner's call; the CI job's required-status question that T12.2 item (2) asks is
worth more than the risk of the edit.

**Verification.** `bash -n` clean; `make check-harness` green; no test in the repo references
`expand_loop.sh`, so the diff adds no failure surface; `tests/unit/harness/test_roadmap_cursor.py`
still fails exactly its two pre-existing T0.0 tests and no others. Each of (a)-(d) was exercised
against real data before sign-off.

## DEC-286: Loop task sessions run without the ECC session-summary hooks, behind a worktree leak guard

**Date:** 2026-09-18 · **Status:** ✅ ACCEPTED (owner, 2026-09-18) · **Drives:** `scripts/expand_loop.sh`, `scripts/worktree_guard.py`

**Context:** on 2026-09-17 the first task of the night (T3.2) committed `11275ee8` into the primary
checkout (`remediation-2026-08`) instead of the loop worktree. Its transcript shows the cause: the
everything-claude-code plugin's `session:start` hook injected the latest session summary from
`~/.claude/session-data/`, written by the owner's interactive session in the primary checkout
(`**Worktree:** ...\NPCSystem`, `**Branch:** remediation-2026-08`, absolute file paths). The unattended
session `cd`'d there for every command, including the commit. Later tasks read summaries written by loop
sessions and stayed put, so only the first task leaked. It also leaks the other way: interactive sessions
start with the loop's summary. The loop branch then carried T3.2's tick (from T3.3) without the deletion,
and nothing noticed until the morning review; `preflight_worktree` only checks where the loop *starts*.

**Decision:** (1) `preflight` exports `ECC_DISABLED_HOOKS=...,session:start,stop:session-end` (the
plugin's documented switch), so task sessions neither read nor write session summaries. (2)
`run_one_task` snapshots HEAD and a `git status` fingerprint of every *other* worktree before the
session (`worktree_guard.py snapshot`) and compares after it (`check`). Any change flags for a human
and HALTs the run.

**Trade-off accepted:** the guard cannot tell a leak from the owner's own interactive commit or edit in
another worktree during a task, so interactive work in the primary checkout while the loop runs will
halt it. The flag text says so; restarting the loop is the remedy. Chosen over detection-only and
issue-only (owner, 2026-09-18).

## DEC-287: Integration tests for uncovered repository methods run against the eval-stack Neo4j

**Date:** 2026-09-21 · **Status:** ✅ ACCEPTED (T11.3) · **Drives:** `tests/integration/test_*_repository_integration.py`

**Context:** T11.2 identified 54 repository methods with no unit test that can fail and no integration-test
path. T11.3's spec requires integration tests run against a real, disposable Neo4j — not the developer's
live database (ISSUE-277). Two options existed: (1) a separate test database, or (2) the eval stack's
Neo4j (bolt://localhost:7688, `npcsystem-eval` compose project), which already exists for live checks
and is wiped with `--reset`.

**Decision:** Integration tests for repository methods use the eval-stack Neo4j exclusively, identified
by `NEO4J_URI=bolt://localhost:7688`. Tests skip when any of `NEO4J_URI`/`NEO4J_USER`/`NEO4J_PASSWORD`
is **unset** — there is no port guard, so `make check` is free of Neo4j I/O only because it runs without
those exports. The `make check-integration-baseline` gate enforces a floor of executed tests (100 since
2026-09-21) to prevent silent all-skip passes. T12.2 records whether the CI `integration-tests` job gates merge.

**Corrected 2026-09-21 (post-loop review):** the original text claimed a skip when the URI "points to the
default port (7687)". No such guard exists, and none is added: CI's `integration-tests` job runs these
tests against its own compose Neo4j on 7687. Exporting `NEO4J_*` at the developer's live database and
running `make check` or `make test-integration` writes to it — the pre-existing, suite-wide ISSUE-277
hazard. Point the exports at the eval stack only.

**Trade-off accepted:** the eval stack must be built before integration tests run, adding ~3-5 minutes
to the setup. The alternative (mocking Neo4j) was rejected because mocks cannot detect Cypher regressions,
which is the entire point of these tests (T11.2/T11.3 motivation).

## DEC-290: `expand_loop.sh` runs `main` only when executed, so tests can source it

**Date:** 2026-09-24 · **Status:** ✅ ACCEPTED (owner, 2026-09-24) · **Drives:** `scripts/expand_loop.sh`, `tests/unit/scripts/test_expand_loop_execution_error.py`

**Context:** ISSUE-370 needed a unit test for a change in `run_one_task`, but `expand_loop.sh` called `main` unconditionally on its last line, so sourcing it started the loop. Nothing in `tests/` covered the script before this.

**Decision:** The final call is now `if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then main; fi`. A test sources the script, stubs `run_claude_session`, `flag_for_human` and `log`, and calls `run_one_task` directly.

**Rationale:** Behaviour is identical when the script is executed. Without the guard, the first test run started the real `main`; it stopped only because the new test file had left the tree dirty, so it was a near miss for an accidental live loop launch.

**What this does NOT change:** the loop's preflight, gates, lock handling or frozen-path list (`scripts/expand_loop.sh` stays frozen for unattended sessions).

## DEC-291: `test_revived_engines_do_work` pins the world clock with a direct Neo4j write

**Date:** 2026-09-24 · **Status:** ✅ ACCEPTED (owner, 2026-09-24) · **Drives:** `tests/integration/test_revived_engines_do_work.py`

**Context:** ISSUE-371: the routine test's outcome depended on where earlier runs left the persisted world clock. `POST /v1/clock/advance` only steps time forward, and no public route sets `time_of_day`.

**Decision:** Before advancing, the test writes `WorldState.time_of_day = 'morning'` on the eval stack through the Neo4j driver, and skips with a reason when there are no `FOLLOWS_SCHEDULE` edges or no `WorldState` node. `morning` was chosen because every seeded routine NPC has a different target in the following slot, so at least one move is guaranteed whatever their prior placement.

**Rationale:** The write is test-only and targets the eval stack (`bolt://localhost:7688`), never the default Neo4j (ISSUE-277). No production API is added for it.

**What this does NOT change:** `src/` and the public API. `routine.moved` remains a weak signal, because scheduled NPCs are reset to `loc_temple` after every advance (ISSUE-373), so the test asserts a counter and not a persisted location.

## DEC-292: `llm_tokens_in_total` now counts the system channel; `llm_backend_latency_seconds` is a histogram

**Date:** 2026-10-20 · **Status:** ✅ ACCEPTED (owner pre-approved, T16.2) · **Closes:** ISSUE-318, ISSUE-319 · **Drives:** `llm_metrics.py`, `llm_client.py`, `utils/metrics.py`

**Context:** DEC-273 introduced `llm_tokens_in_total` and `llm_backend_latency_seconds`. Two defects surfaced in the L9 review: (1) `llm_tokens_in_total` counted only the user/human prompt channel, omitting the ~4,245-token static system prompt — a 4.3× under-count that makes every prompt-budget calculation wrong. (2) `llm_backend_latency_seconds` was a count/sum/min/max summary with no histogram buckets, so no p50/p95 was derivable — the 3–7 s dialogue budget is a percentile claim the metric could not evaluate.

**Decisions:**

1. **Token counting change (ISSUE-318).** `llm_tokens_in_total` is redefined to count **both the prompt and the system channel**. A new `record_llm_input_tokens(prompt, system, labels)` function in `llm_metrics.py` owns this; `DialogueLLMClient` calls it for both `generate_response` and `stream_text`. Callers that read historical `llm_tokens_in_total` values will see a step-change upward; no migration of stored metric snapshots is attempted — in-process metrics reset on restart.

2. **Latency histogram (ISSUE-319).** `llm_backend_latency_seconds` moves from `observe_metric` (summary) to `observe_histogram_metric` (histogram) with `LATENCY_BUDGET_BUCKETS = (0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 30.0)`. Boundaries straddle the 3 s and 7 s budget points so a breach is visible at `le="5.0"` without arithmetic. `llm_backend_load_latency_seconds` stays a summary — its signal is `min` (the eviction detector), not a percentile.

**What this does NOT change:** the load-latency metric, the Prometheus export format (in-process only), or the public API. Downstream callers reading `"observations"."llm_backend_latency_seconds"` will find nothing; they must read `"histograms"."llm_backend_latency_seconds"` instead.

## DEC-293: `harness_version` split — instrument hash only; `case_set_version` tracks the subject
**Date:** 2026-10-20 · **Status:** ✅ ACCEPTED (owner pre-approved T16.3, DEC-281 (b)) · **Drives:** `evals/_run_config_hashing.py`, `evals/run_config.py`, `evals/comparability.py`, `evals/trend_store.py`, `evals/trend_row_builder.py`, `docs/REGRESSION_POLICY.md`

**Context.** `resolve_harness_version` hashed `evals/cases/**/*.yaml` + `prompts/eval/*.yaml` + `evals/matchers.py` into one value, and `ComparabilityKey = (harness_version, judge_identity)` compared for equality. Editing one case file therefore made every prior run incomparable. The two rows in `evals/trend/trend_v1.jsonl` carry `f22f61a5d877` and `014abac09947` — the trend store has never held a comparable pair and the regression gate has never had a baseline to select. This is the T16.3 delivery of DEC-281 (b).

**Decision.** `harness_version` is narrowed to the *instrument* only: `prompts/eval/*.yaml` + `matchers.py`. A new `resolve_case_set_version(cases_dir)` hashes `evals/cases/` and its result is stored in `RunConfig.case_set_version` and `TrendRow.case_set_version`. `ComparabilityKey` is unchanged in shape (`harness_version` + `judge_identity`), keying on the instrument because an instrument change is what genuinely invalidates a comparison. Case-set drift is already handled by `compare.py`'s case-intersection refusal.

**Migration cost.** Existing recorded hashes will not reproduce under the narrower scope: the two pre-existing rows (`f22f61a5d877`, `014abac09947`) were generated with cases folded into `harness_version` and are therefore incomparable with any run generated after this change. This is the same one-time cost DEC-281 (b) noted T20.1 accepts for `dialogue_prompt_hash`. Both existing rows were already mutually incomparable before this change (different harness_version), so the net loss is zero comparable pairs.

**What this does NOT change.** `ComparabilityKey`'s shape and fields. The `select_baseline` and `is_comparable` logic. The case-intersection check in `compare.py`. `TrendRow` serialisation — `case_set_version` defaults to `""` so old rows still parse.

