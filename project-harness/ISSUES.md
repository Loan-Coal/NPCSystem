# Issues Log

Persistent issues log. Read at the start of every session. Updated whenever
work is deferred or completed.

Rules:
- Never reuse IDs.
- Never delete entries. Mark as `[FIXED]` instead.
- Severity: P1 (blocking) | P2 (annoying) | P3 (nice-to-fix).
- New issues get the next monotonic ID.

---

## [FIXED] ISSUE-093: NPCs conflate past memories with current events (systemic — knowledge has no temporal frame)
**Fixed:** 2026-06-11, Phase 26 (S26.1–S26.4). All three layers addressed: (A) `_flatten_event_row` keeps
`knowledge_state` and `_extract_personal_accounts` routes rumour distorted summaries to a HEARSAY channel
(attributed, never firsthand) while keeping the distorted content — Rule 5b; (B) memories carry a coarse
`age` (recent|long_past) and Rule 15 forbids presenting a memory as the current situation; (C, DEC-094)
`occurred_at_game_time` + `is_historical` added to Memory, and old_henryk's past-war memory split out of
the current-war rumour string. Verified live (4 henryk cases pass) with a 6/6 no-regression sweep across
both the rumour-relay and firsthand paths. Closes ISSUE-082.
**Found:** 2026-06-11, during S22.5 live-eval root-cause investigation (deeper cause behind ISSUE-082)
**Severity:** P2 (immersion + anti-hallucination — NPCs present long-past experiences as the current situation)
**Where:** `retrieval/subgraph_retriever.py::_flatten_event_row`; `engines/dialogue/prompt_builder.py::_extract_personal_accounts` + Rule 5; `graph/memory_queries.py` (no event-time field); `demo_game/seed.py` (all inner-life stamped at one `_GAME_TIME`).
**Description:** The context/prompt has no temporal axis for knowledge — everything an NPC knows is a flat,
present-tense, authoritative bag. Three compounding layers:
  1. **Data model:** `Memory`/`Event` nodes carry only `created_at_game_time` (record time), never an
     `occurred_at`/era for *when the event happened*. The seeder stamps every memory at the current
     world time, so a decades-old memory is indistinguishable from a fresh one (and `recency_score`
     ranks it as fresh).
  2. **MY_ACCOUNT pipeline (root cause):** `_flatten_event_row` **deliberately drops `knowledge_state`**
     when a `distorted_summary` exists (to stop over-hedging on gossip — undocumented inline fix, no DEC).
     `_extract_personal_accounts` then renders every `distorted_summary` as an authoritative, verbatim
     `MY_ACCOUNT_N` line (Rule 5). A 2-hop *rumour* becomes a firsthand account the model is ordered to
     recite. Rule 5 (authoritative) directly contradicts Rule 10 (hedge rumour); Rule 5 wins.
  3. **Prompt:** no instruction separates "a finished event I experienced long ago" from "the ongoing
     situation the player asks about", so a player conflating them ("you were at the front") is accepted.
**Concrete failure:** `case_neg_old_henryk_no_eyewitness_claim` — Henryk recounts the current war as
firsthand because his rumour `distorted_summary` is authored first-person and rendered as MY_ACCOUNT.
**Why deferred from S22.5:** S22.5 was YAML-only; this needs context + prompt + a schema change.
**To fix:** Phased plan — see ROADMAP **Phase 26**. (A) restore `knowledge_state` + split MY_ACCOUNT vs a
new HEARSAY channel that keeps the confident distorted content but strips firsthand framing; (B) thread
memory age into context + add a past-recollection prompt rule; (C, schema/DEC-094) add `occurred_at_game_time`
+ `is_historical` and split Henryk's past-war memory from the current rumour in the seed; (D) temporal-conflation
eval set. Closing this also closes ISSUE-082.

## Open

## [FIXED] ISSUE-080: demo world_state epoch drifts to age_of_peace; skip-if-exists seeder cannot restore it
**Found:** 2026-06-09, during eval-harness redesign
**Severity:** P1 (blocking — invalidates the entire war-premise eval battery silently)
**Where:** `demo_game/seed.py::_seed_node` (line ~233), `world_state/world` node
**Description:** The running demo `world_state/world` node was observed at `epoch=age_of_peace`,
`active_conditions=[]`, even though `seed.py:915` seeds it as `war`/`["northern_war"]`. `_seed_node`
is skip-if-exists, so `make demo-seed` will NOT overwrite a drifted world_state. The full eval
battery (and the new lore `affirms_judge`) assume `epoch=war`; against a peace world every
war-premise NPC answer ("the peace has held") is CORRECT, so the checks false-fail and the run is
meaningless. This produced 6 phantom "peace hallucinations" that vanished once epoch was reset to
war (45/49 vs 36/49). Root cause of the drift not yet established (clock transition, default node
creation, or an earlier peace seed).
**Why deferred:** Restoring epoch via PATCH unblocked this session; the systemic fix is separate.
**Fixed:** 2026-06-09, commit 068b0e1 — `_force_patch_world_state` always-patches epoch=war in `demo_game/seed.py`.
**To fix:** Either (a) make `make demo-seed` force-PATCH the `world_state` epoch/active_conditions
to the intended values (idempotent overwrite for world_state only), or (b) have the eval runner
assert/seed the required `epoch` precondition per case (e.g. a `seed.requires_epoch` field) before
running war-premise cases, failing fast if the world is not at war.

## ISSUE-081: dialogue_handler hardcodes archetype="default" for canned/degradation responses
**Found:** 2026-06-09, during Lira fallback diagnosis
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/dialogue/dialogue_handler.py::handle` (the
`execute_with_degradation(..., archetype="default", ...)` call); also
`src/npc_engine/engines/dialogue/llm_client.py::_load_fallback_dialogue` (always reads the
`"default"` key of `fallback_responses.json`).
**Description:** When dialogue degrades to the canned tier OR the structured-output validation
fallback fires, the served line is always from the `"default"` archetype ("I need a moment to
think."), never the NPC's real archetype (innkeeper/fence/merchant/guard/elder). The NPC's
archetype is available but never threaded into the degradation/fallback path. Cosmetic while
fallbacks are rare, but makes every fallback obviously generic and out-of-voice.
**Why deferred:** Out of scope for the eval-harness redesign; touches the dialogue handler
signature + llm_client fallback loader.
**To fix:** Thread the NPC archetype from the request/profile into `execute_with_degradation`
and into `DialogueLLMClient._load_fallback_dialogue` so the archetype-keyed fallback lines are used.

## [FIXED] ISSUE-082: old_henryk accepts false-eyewitness presupposition despite ECHO_GUARD reinforcement
**Fixed:** 2026-06-11, Phase 26 (S26.1–S26.4). Root cause was systemic (ISSUE-093): rumour distorted
summaries were rendered as authoritative firsthand MY_ACCOUNT lines, and a past-war memory was fused
into the current-war rumour string. After the HEARSAY/MY_ACCOUNT split (S26.1), memory temporal framing
(S26.2), and the event-time schema + Henryk seed split (S26.3), all three henryk cases pass live on
qwen2.5:14b: `case_neg_old_henryk_no_eyewitness_claim`, `case_adv_false_eyewitness_henryk`, and the new
`case_neg_old_henryk_past_war_not_current` (S26.4). S22.5's prompt clause contributed the first half.
**Found:** 2026-06-09, during eval re-run (epoch=war, prompt stage_b_v2.9)
**Severity:** P2 (annoying — 2 real anti-hallucination guard failures; the headline's only true hallucinations)
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Rules 5/9/10), the runtime
`ECHO_GUARD` in `prompt_builder.py`; cases `case_adv_false_eyewitness_henryk`,
`case_neg_old_henryk_no_eyewitness_claim`.
**Description:** Asked leading questions that presuppose he was present ("you were at the front,
weren't you?"), old_henryk affirms it: "I did see them pass through" / "I was indeed at the
northern front." His knowledge is 2-hop rumour only — this is presupposition capture (Rule 9
false-premise + Rule 10 certainty). The `ECHO_GUARD`/`PREMISE_GUARD` line added in stage_b_v2.9
("if the player claims you witnessed... do not confirm it") did NOT stop it on qwen2.5:14b. The
new `affirms_judge` correctly catches both (honest detection); reducing them is prompt engineering.
**Why deferred:** Per task decision, echo/presupposition is prompt-reinforcement-only and residual
14b flakiness is accepted; detection is the deliverable, reduction is follow-up.
**To fix:** Iterate the system prompt / runtime guard for presupposition specifically (e.g. an
explicit "the player may falsely claim you were somewhere or saw something — deny first, then
answer from context only" rule, or a worked example). Consider a Henryk-specific MY_ACCOUNT framing
that forces rumour attribution. Re-run the two cases to verify.
**Progress 2026-06-11 (S22.5):** Added the explicit deny-first clause — `system_v1.yaml` Rule 9 now
carries a `PRESENCE PRESUPPOSITION` block ("if the player presupposes you witnessed/were present —
deny or correct FIRST, then answer from context only with source attribution") plus a Rule 10
reinforcement; `PROMPT_VERSION` bumped to `stage_b_v2.10`. Unit test `test_presence_presupposition_guard.py`
asserts the clause loads. **Kept OPEN:** the reduction is unverified — the two cases require a live
`make eval-llm-demo` (Ollama) run not available in the implementing gate. Close once both cases pass
on qwen2.5:14b (or document accepted residual 14b flakiness per the original deferral rationale).
**Live verification 2026-06-11 (qwen2.5:14b, stage_b_v2.10, demo world, container confirmed serving
the new clause):** `case_adv_false_eyewitness_henryk` now **PASSES** (the harder presupposition-frame
variant — the deny-first clause works where there is no competing memory). `case_neg_old_henryk_no_eyewitness_claim`
still **FAILS** — response: *"Oh, the northern front! I was there during the last big push. Saw plenty
of action... soldiers march through the village square..."*
**Root cause (newly diagnosed): seed-vs-rule conflict, not prompt weakness.** old_henryk's seed
(`demo_game/seed.py`) makes him a *"retired courier who has seen three wars"*, bio *"Mixes current
rumour with personal memories from decades ago... Never hedges"*, with an **importance-92** memory
*"Running dispatches through the north pass during the last war — half my route was behind enemy
lines"* and a **first-person** `KNOWS_ABOUT` distorted_summary *"I ran dispatches through king's pass
in the last war..."*. He genuinely served at the northern front in a *past* war; the *current*
`northern_war_begins` is 2-hop rumour. The model transfers firsthand authority from the past event to
the current one — exactly his characterization. `case_adv` (asks re: the village *square*, no memory
anchor) is unaffected; `case_neg` (asks re: the *northern front*) collides with the importance-92 memory.
**Revised fix options:** (1) re-seed Henryk's war memory to explicitly tag it as a *prior* war and add
a temporal-disambiguation rule ("do not transfer firsthand authority from a long-past event to a current
one you only heard about"); or (2) Henryk-specific MY_ACCOUNT rumour-attribution framing. Both exceed
S22.5's YAML-only scope (touch `demo_game/seed.py` and/or the voice descriptor) → follow-up work.

## ISSUE-083: two voice tone_judge cases fail under epoch=war / stage_b_v2.9 (captain_sorn, mira_innkeeper)
**Found:** 2026-06-09, during eval re-run
**Severity:** P3 (nice-to-fix — voice quality, not anti-hallucination)
**Where:** `case_voice_captain_sorn_001`, `case_voice_mira_innkeeper_001`; possibly influenced by
the `ECHO_GUARD` line in `prompt_builder.py` (stage_b_v2.9).
**Description:** captain_sorn's reply hedges ("no major breakthroughs or setbacks announced yet"),
failing the authoritative-military voice judge (borderline, pre-existing). mira_innkeeper's reply
reads as a dry objective war report rather than warm gossip ("Villagers speak of soldiers
marching...") and now fails the warm-gossip voice judge — it was passing before. The new ECHO_GUARD
("answer only in your own general terms... speak only from the knowledge in your context") may be
nudging NPCs toward terse, factual reporting at the cost of voice colour; could also be LLM variance.
**Why deferred:** Voice polish is a separate axis from the anti-hallucination guarantee this task targets.
**To fix:** Confirm whether ECHO_GUARD is the cause (A/B a couple of runs with the line removed). If
so, soften the guard wording so it constrains echoing without flattening voice, or scope it to only
fire when the player message contains a planted figure/presupposition. Otherwise tune the two voice prompts.

## [FIXED] ISSUE-079: mira_innkeeper consistently hits Tier-3 canned fallback during evals
**Found:** 2026-06-08, during anti-hallucination eval run
**Fixed:** 2026-06-08, in dialogue anti-hallucination remediation task
**Severity:** P1 (blocking — all Mira eval cases fail)
**Where:** `src/npc_engine/retrieval/context_utils.py::serialize_json`,
`src/npc_engine/retrieval/context_builder.py` (second-hop loop, ~line 343)
**Description:** Every `mira_innkeeper` dialogue query returned a canned fallback
(`"I need a moment to think."` etc.). Root cause was NOT token budget (the original
hypothesis): the live traceback showed
`TypeError: Object of type DateTime is not JSON serializable` raised in BOTH the full
and graph_only tiers at `context_builder.py:343`, where second-hop event rows are
serialized via `serialize_json(evt, strip_nulls=True)`. A raw Neo4j `DateTime` survives
in the second-hop event dict, and `json.dumps` had no `default=` handler. Mira-specific
only because she is the gossip hub — the only NPC with non-empty `second_hop_events`;
every other NPC skips the loop, so the bug never fired for them.
**Fix:**
1. `serialize_json` now passes `default=_json_default` to `json.dumps`; `_json_default`
   converts any temporal type (Python + Neo4j, all expose `isoformat`) to an ISO string
   and degrades any other non-native object to `str()`. Robust for every call site.
2. Bounded the previously-unbounded second-hop loop with `MAX_SECOND_HOP_EVENTS`
   (config.py, default 5) — defensive, prevents tier-A accumulation for hub NPCs.

## [FIXED] ISSUE-077: quest_lifecycle_engine.py is 643 lines — pre-existing over 300-line limit
**Found:** 2026-06-06, during EXP-20 fan-in
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/quest/quest_lifecycle_engine.py` (643 lines)
**Description:** File exceeds the 300-line hard limit (CLAUDE.md). Pre-existing before EXP-20 (EXP-20 reduced it by 2 lines net). The file is grandfathered in `scripts/rules_baseline.txt`.
**Why deferred:** Splitting would require either a new `quest_reward_engine.py` (reward routing logic) + `quest_objective_engine.py` (objective verification) or a `quest_transition_engine.py` for the state machine. This is a non-trivial refactor requiring its own task. A DECISIONS.md entry would be needed to approve the split boundary.
**To fix:** Split into at least two files: `quest_lifecycle_engine.py` (state transitions only, ≤300 lines) + `quest_reward_router.py` (reward routing + item transfer logic). Write a DECISIONS.md entry proposing the split boundary first.
**Fixed:** 2026-06-09, in Batch D (DEC-078). 3-way split: quest_lifecycle_engine.py (285L, accept/update/evaluate), quest_offer_service.py (213L, offer_draft_quest/offer_quest), quest_reward_router.py (290L, apply_rewards). All 17 affected tests updated; 1783+ unit tests green.

## [FIXED] ISSUE-078: gossip_handler.py uses stdlib logging.getLogger directly — bypasses npc_engine logging setup
**Found:** 2026-06-06, during EXP-12 fan-in (worker observation)
**Fixed:** 2026-06-09, Batch A gate-fixes (replace `logging.getLogger` with `get_logger` from `npc_engine.utils.logging`)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/gossip/gossip_handler.py` — `import logging; LOGGER = logging.getLogger(__name__)`
**Description:** Uses stdlib `logging.getLogger` directly instead of `npc_engine.utils.logging.get_logger`. This means gossip handler log records go through a different logger hierarchy. In production, if `configure_logging()` is not applied to the root logger, gossip events may not be captured correctly. Inconsistent with the project logging pattern.
**Why deferred:** Low-severity; gossip logs still appear but via a different path. Out of scope for EXP-12 which only touched `relation_mutator.py`.
**To fix:** Replace `import logging; LOGGER = logging.getLogger(__name__)` with `from npc_engine.utils.logging import get_logger; _LOGGER = get_logger(__name__)` in `gossip_handler.py`. Verify existing gossip tests still pass.

## [FIXED] ISSUE-068: test_game_window.py layout tests fail — WorldStatePoller not imported in game_window.py
**Fixed:** 2026-06-11, S22.3 (reconcile) — `game_window.py` now imports `WorldStatePoller` (line 44)
and instantiates it (line 134), so the test patch resolves; all 6 `TestGameWindowLayout` tests pass
(618 demo tests green). The import was added by a later refactor; no code change needed this session.
**Found:** 2026-06-05, during EXP-80 batch fan-in (make test-demo gate)
**Severity:** P2 (annoying)
**Where:** `demo_game/tests/test_game_window.py:33` — monkeypatches `demo_game.ui.game_window.WorldStatePoller` which is not imported in `game_window.py`
**Description:** 6 layout tests in `TestGameWindowLayout` fail because `test_game_window.py` patches `WorldStatePoller` via `patch("demo_game.ui.game_window.WorldStatePoller")`, but `WorldStatePoller` is never imported into `game_window.py`. Pre-existing before this expansion batch (confirmed by reverting changes and re-running).
**Why deferred:** Pre-existing issue discovered at gate time; not introduced by this batch. Fixing requires either adding the import to game_window.py (if it uses WorldStatePoller) or removing the stale patch from the tests.
**To fix:** Check if `GameWindow` actually uses `WorldStatePoller`; if yes, add the import; if not (it was removed in a refactor), update the test to mock the correct poller class.

## ISSUE-054: redundant `token_budget_enforcer.py` superseded by `fill_to_budget`
**Found:** 2026-06-03, during SEV-07
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/retrieval/token_budget_enforcer.py` + `tests/unit/test_context_pipeline.py`
**Description:** `enforce_budget` is not wired anywhere and silently drops Tier-A, contradicting the canonical `fill_to_budget` enforcer (see DEC-057). It and its tests are dead weight.
**Why deferred:** Deleting a non-temporary file requires human approval per CLAUDE.md; out of scope for the SEV-07 bug fix.
**To fix:** With approval, delete `token_budget_enforcer.py` and its `test_context_pipeline.py` tests; confirm no imports remain.

## [FIXED] ISSUE-052: 256 mypy type errors across 86 files (type gate red)
**Fixed:** 2026-06-11, in Phase 20 (S20.1–S20.6). `make type` is now 0 errors across 430 files
(`no-any-return` cluster eliminated); `OkEnvelope[T]` + per-route `response_model` landed and the
S20.6 contract test asserts every route emits a typed, non-empty OpenAPI body.
**Found:** 2026-06-03, during the multi-agent codebase review (SEV-14/SEV-15)
**Severity:** P2 (annoying)
**Where:** `src/` (86 files); see `project-harness/review-evidence/04_type.log`. Root clusters: ~90 `no-any-return` from `dict[Any,Any]` route returns, 22 `FrozenApiModel`-as-base-class in `api/schemas.py`, `create_model(__config__=...)` in `type_registry/runtime_models.py`, `Record`/`BaseModel` arg/attr errors in `graph/*_writer.py`, 14 validator `no-any-return` in `config.py`.
**Description:** `make type` (mypy) fails with 256 errors. The count is pinned by the ratchet (`.mypy_baseline = 256`, `scripts/mypy_ratchet.py`) so it can only shrink; `make type` is reported in CI but cannot be a hard gate until this reaches 0.
**Why deferred:** Large incremental burn-down (full remediation brief in `project-harness/review-fixes/FIX-SEV-14.md`); out of scope for the harness-hardening task that surfaced it.
**To fix:** Execute FIX-SEV-14 (generic `OkEnvelope[T]` + per-route `response_model`, drop the `FrozenApiModel` alias, fix `create_model`, type the graph writers, annotate config validators). Drive `.mypy_baseline` to 0 via `make type-ratchet-update`, then flip `make type` to gating in CI (FIX-SEV-15).

## ISSUE-053: 57 grandfathered CLAUDE.md rule violations (file-size, swallows, prints, Cypher-leak, demo imports)
**Found:** 2026-06-03, during the multi-agent codebase review
**Severity:** P2 (annoying)
**Where:** `scripts/rules_baseline.txt` (enumerated); spans `src/` and `demo_game/`. Maps to SEV-23 (file-size), SEV-18/PY-06 (swallows), SEV-40 (prints), SEV-04 (Cypher outside `graph/`), SEV-02/DEMO-01 (demo imports `npc_engine`).
**Description:** The `make check-rules` gate (`scripts/check_rules.py`) records 57 existing rule violations as a baseline so only NEW ones fail CI. The baseline is the debt backlog.
**Why deferred:** Each cluster has its own remediation brief in `project-harness/review-fixes/`; the gate prevents growth while they are worked down.
**To fix:** Work the SEV briefs; after each, run `make check-rules-update` to shrink `scripts/rules_baseline.txt`. Done when the baseline is empty.

## [WONTFIX] ISSUE-051: Dashboard S12.4 engine cadence/cost controls are read-only (no live mutation)
**Found:** 2026-06-03, during S12.4
**Severity:** P3 (nice-to-fix)
**Where:** `dashboard/js/engines.js`, `src/npc_engine/api/routes/system.py` (`/v1/system/config`)
**Description:** The Engines tab displays runtime cadence/cost config + per-engine status but cannot change them. `Settings` is a frozen `lru_cache` singleton and the autopilot captures `interval_seconds`/`budget_guard` at construction in the lifespan, so there is no runtime-mutation path. See DEC-054.
**Why deferred:** Live mutation requires a `RuntimeConfigStore` injected into the autopilot + a guarded write endpoint — a public-interface/scheduler change needing approval, out of scope for the read-only first slice.
**To fix:** Add a `RuntimeConfigStore` read by the autopilot each loop for interval + LLM budget; expose `PATCH /v1/system/config` (graph_admin scope, bounded values); wire the dashboard inputs to it.
**Closed:** 2026-06-03, S13.2 dropped (DEC-055) — deprioritized below the CRITICAL/HIGH review-remediation backlog; dashboard controls remain read-only. Reopen if a customer needs live tuning.

## [FIXED] ISSUE-050: test_put_world_state_success asserts id=="world" but client uses "world_demo"
**Found:** 2026-06-03, during S7.2 test run
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/tests/test_client.py:479`
**Description:** `test_put_world_state_success` asserts `kwargs["json"]["properties"]["id"] == "world"` but `put_world_state` in `client.py` hardcodes `"world_demo"` (changed by ISSUE-044 fix). The test was not updated when the ID changed.
**Why deferred:** Test failure is pre-existing, not blocking S7.2. Single-line fix.
**To fix:** Change the assertion in `test_put_world_state_success` to `"world_demo"`.
**Fixed:** 2026-06-03, S7.3 — changed assertion to `"world_demo"` in `demo_game/tests/test_client.py:479`.

## [FIXED] ISSUE-049: Give Item action always gives first inventory item — no player choice
**Found:** 2026-06-02, during S4.2 review
**Severity:** P2 (annoying)
**Where:** `demo_game/quest_trade_controller.py` — `handle_give_item` / give-item flow
**Description:** When the player clicks `[Give Item]`, the first item in the player's inventory was given automatically without prompting the player to choose.
**Fixed:** 2026-06-02, S4.2 — added give mode to `InventoryPanelWidget` (clickable rows + Cancel button); added `start_item_pick` to `RightPanelRenderer` (switches to INVENTORY tab, wraps callbacks to restore ACTIONS tab on completion or cancel); removed `get_player_first_item` from `RightPanelRenderer`; updated `game_window.py` callback and event routing. DEC-047 added for right_panel.py line-count exception. 17 new tests.

## [FIXED] ISSUE-048: game_controller.py exceeds 300-line hard limit
**Found:** 2026-06-02, during S3.4
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/game_controller.py` (was 520 lines after S4.1)
**Fixed:** 2026-06-02, S4.2 — extracted `demo_game/action_workers.py` (96 lines) with all worker functions; extracted `demo_game/quest_trade_controller.py` (283 lines) with all quest/trade/give-item handlers. `game_controller.py` is now 297 lines.

---

## [FIXED] ISSUE-035: reputation_dialogue_tone_001 eval fails — merchant archetype doesn't express warmth toward allied player
**Found:** 2026-05-27, during eval repair sprint
**Severity:** P2 (annoying)
**Where:** `evals/cases/reputation_dialogue_tone.yaml`, `prompts/system_v1.yaml` (or equivalent NPC voice prompt)
**Description:** Reputation context is correctly injected (hero_player has standing=80 "allied" with tw_merchants; threshold=20). However `tw_merchant` still responded in a purely transactional tone ("No nonsense, just business") even to an allied player. The tone_judge expects warmth/privilege but a mercantile-archetype NPC produced professional efficiency instead.
**Fixed:** 2026-06-02, S0.5 — chose Option B (strengthen prompt). Rule 2 "allied" bullet in `system_v1.yaml` now mandates three explicit tone shifts even when VOICE_DESCRIPTOR is clipped/transactional: (a) warm/respectful address, (b) skip price caveats, (c) express genuine eagerness. Rule 8 updated to clarify VOICE_DESCRIPTOR governs style only, not mandatory behavioral rules. Removed `skip_until_implemented: true` from eval case. PROMPT_VERSION bumped to `stage_b_v2.6`.

---

## [FIXED] ISSUE-031: Military engine run_tick is a stub
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/military/military_engine.py`
**Description:** `MilitaryEngine.run_tick` returns `{"skipped": True}` with no logic. Battle resolution, resource yield, and depletion tracking are not implemented.
**Why deferred:** User confirmed military tick logic should be deferred; engine is wired for future expansion.
**To fix:** Implement battle resolution (opposing armies at same location → strength comparison, CONTROLS/OCCUPIES edge updates), resource yield (PRODUCES → faction.treasury per tick), and depletion tracking (ResourceNode.depletion decrement).
**Fixed:** 2026-06-03, S6.5 — added `military_battle_service.py` (battle resolution: strength compare, set_controls_location, remove_controls_location, damage, battle Event); added `military_resource_service.py` (resource yield + depletion decrement); added 4 write helpers to `military_writer.py`; replaced stub `military_engine.py` with real orchestration. 21 new tests.

---

## [FIXED] ISSUE-032: OathEngine.check_pledge_violations returns empty list
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/oath/oath_engine.py`
**Description:** Violation scan stub returns `[]` unconditionally. Pledgers whose recent actions conflict with their pledge are never flagged.
**Why deferred:** Violation detection requires cross-referencing PARTICIPATED_IN and WITNESSED edges against pledge semantics — non-trivial scope for initial implementation.
**To fix:** For each active pledge, query pledger's PARTICIPATED_IN and WITNESSED edges since `sworn_at_tick`; check action_type against pledge_type; call `break_pledge` on violation and generate high-severity EVENT.
**Fixed:** 2026-06-03, S2.3 — extracted `pledge_violation_service.py` with `check_pledge_violations()`, `_VIOLATION_ACTIONS`, `_VIOLATION_ROLES`, Cypher queries `CYPHER_GET_WITNESSED_VIOLATIONS`/`CYPHER_GET_PARTICIPATED_VIOLATIONS`, and `_emit_violation_event()`. `oath_engine.run_tick` now queries all active pledgers (not just expiring ones) and calls `check_pledge_violations` for each. Returns `violated_pledges` count. 10 new unit tests.

---

## [FIXED] ISSUE-033: Treaty tribute condition checking does not verify payment
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/treaty_service.py:check_treaty_conditions_mechanical`
**Description:** Tribute conditions detect when payment is due (tick % interval == 0) but do not verify whether payment was actually made. All tribute conditions are flagged as due without checking faction treasury.
**Why deferred:** Payment verification requires faction treasury write operations not yet implemented in this layer.
**To fix:** Query faction treasury, verify amount >= condition.amount, deduct on payment, and only flag as violation if treasury insufficient.
**Fixed:** 2026-06-02, S2.4 — added `check_tribute_payment()` to `treaty_service.py`; reads faction treasury via `get_faction_treasury()`, auto-deducts via `deduct_faction_treasury()`, returns violation only if treasury < required. Updated `check_treaty_conditions_mechanical` to call it; added `_find_payer_faction` helper to identify payer from BOUND_BY parties. Wired condition checks into `TreatyEngine.run_tick` via new `get_all_active_treaty_ids()` query. 8 new unit tests added.

---

## [FIXED] ISSUE-034: SATISFIES_NEED src_type is multi-type (Item or Location)
**Found:** 2026-05-19, during Phase 7 L implementation
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/type_registry/base_edges/satisfies_need.yaml`
**Description:** SATISFIES_NEED should accept both Item and Location as source nodes, but the type registry YAML format only supports a single string for `src_type`. Current implementation uses `location` as src_type; Item→Need satisfaction is not schema-registered.
**Why deferred:** Registry extension to support multi-type src_type requires changes to `registry.py` edge model validation — out of scope for Phase 7 L.
**To fix:** Either (a) add an `item_satisfies_need.yaml` edge type for Item→Need, or (b) extend registry to accept `src_type: [location, item]` list syntax.
**Fixed:** 2026-06-01, S0.3 — extended `BaseEdgeTypeDocument.src_type` to `str | list[str]`; `RuntimeEdgeTypeDefinition.src_type` to `str | tuple[str, ...]`; added `resolve_src_label_expr()` helper for Neo4j label-union Cypher; updated validation to check membership; updated `satisfies_need.yaml` to `src_type: [location, item]`.


## [FIXED] ISSUE-022: LLMCache key in demo_game/run.py excludes prompt content
**Found:** 2026-05-24, during P2 iteration
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/run.py` — `LLMCache` key computation (`sha256("{npc_id}:{player_input}")`)
**Description:** The cache key is derived from `npc_id` and `player_input` only. Any change
to `system_v1.yaml`, `npc_voices.yaml`, or the context serialization code does not bust the
cache. After a prompt or code change, stale cached responses continue to be served silently
under `make demo-run ARGS=--cached`. This also means the cache can be poisoned if `make demo-run`
is run before Ollama is up — the engine returns canned "I need a moment to think" strings
which get written to cache as valid LLM responses.
**Why deferred:** Cache busting is a manual step in the S2.8 iteration loop. A
prompt-aware key (e.g. including a hash of the rendered prompt string, or
`PROMPT_VERSION`) would automate this but requires changing how the demo runner
threads prompt state into the cache layer.
**To fix:** Include `PROMPT_VERSION` from `prompt_builder.py` in the cache key:
`sha256("{npc_id}:{player_input}:{PROMPT_VERSION}")`. This automatically invalidates
all cached responses when the prompt version is bumped.
**Fixed:** 2026-06-01, S0.3 — imported `PROMPT_VERSION` from `prompt_builder` in `run.py`; updated `LLMCache._key()` to include it.

## [FIXED] ISSUE-021: test_gossip_propagates_after_clock_advance is trivially true
**Found:** 2026-05-22, during P2.5 planning
**Severity:** P3 (nice-to-fix)
**Where:** `e2e/scenarios/scenario_demo_game_judge.py::test_gossip_propagates_after_clock_advance`
**Description:** The `northern_war_begins` Event node is seeded by `demo_game/seed.py` and
is always present in the graph. `GET /v1/graph/nodes/Event` will return it regardless of
whether a clock advance triggers gossip propagation. The test functions as a basic engine
sanity check (state intact after advance_clock) but does not prove that gossip actually ran.
**Why deferred:** A stronger test (e.g., count KNOWS_ABOUT edges before/after advance, or
check per-NPC belief updates) may be flaky if the gossip engine requires multiple ticks to
propagate knowledge. The war-dialogue test (test 1) is the substantive LLM judge gate for P2.5.
**To fix:** Replace with a two-step test: (1) GET KNOWS_ABOUT edge count before advance,
(2) advance clock, (3) assert edge count increased. OR check that a specific non-captain_sorn
NPC has acquired a new belief mentioning war after the advance.
**Fixed:** 2026-06-01, S0.3 — replaced LLM-judge event-ID check with before/after `KNOWS_ABOUT` edge count assertion (advances 10 ticks, verifies count_after > count_before).

## [FIXED] ISSUE-025: system_v1.yaml Rules 2–7 had dead context key references
**Found:** 2026-05-24, during P2.1 audit
**Severity:** P2 (annoying — rules were silently no-ops; NPC emotion/reputation/goals ignored)
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` — Rules 2, 3, 4, 5, 6, 7
**Description:** Five rules referenced paths that do not exist in the serialized context:
`context.player_reputation` (should be `context.reputation`),
`context.npc.emotion.current_mood` (→ `context.emotion.current_mood`),
`context.npc.profile` (→ `context.character`),
`context.npc_known_events` (→ `event:N:npc_id` keyed items),
`context.recent_session_turns` (→ `context.session`),
`context.npc.goals` (→ `context.goals`).
The LLM never saw these fields under the referenced paths so all six behavioral
rules — reputation gating, emotion coloring, persona anchoring, event knowledge,
session continuity, goal surfacing — were effectively no-ops.
**Fixed:** 2026-05-24, P2.3 — all six references corrected in `system_v1.yaml`.

## [FIXED] ISSUE-024: PROMPT_TOKEN_BUDGET hardcoded at 8000 while Ollama context was 4096
**Found:** 2026-05-24, during P2 context debugging
**Severity:** P2 (annoying — engine was building 8000 tokens of context that Ollama silently truncated)
**Where:** `src/npc_engine/config.py` — `PROMPT_TOKEN_BUDGET` field; `src/npc_engine/.env.example`
**Description:** `PROMPT_TOKEN_BUDGET` was left at 8000 (a Mixtral 32K-era value) while the
Ollama instance was configured with a 4096 token context window. The context builder assembled
up to 8000 tokens of NPC context that Ollama then silently truncated on input. NPCs appeared to
have full context in logs but the LLM received a truncated version, causing inconsistent behavior.
**Fixed:** 2026-05-24, P2 — added `OLLAMA_CONTEXT_LENGTH: int = 4096` to `config.py` as the
single source of truth; added `_derive_prompt_token_budget` model_validator that sets
`PROMPT_TOKEN_BUDGET = OLLAMA_CONTEXT_LENGTH - 1200` when not explicitly overridden; updated
`.env.example` to document the derivation.

## [FIXED] ISSUE-023: Event ContextItems had priority below traits/groups/rumors
**Found:** 2026-05-24, during P2.6 iteration (Henryk giving generic response)
**Severity:** P2 (annoying — NPC-specific knowledge events truncated for socially-rich NPCs)
**Where:** `src/npc_engine/retrieval/subgraph_retriever.py` — `assemble_tier_a_context` event loop
**Description:** Event ContextItems were assigned `priority=80 - index`. Traits (83),
group memberships (82), and believed rumors (81) all ranked higher. For NPCs like
`old_henryk` who have multiple social associations, the token budget filled before
reaching the NPC's KNOWS_ABOUT events. The result was a completely generic response
with no reference to the war — as if the NPC had no relevant event knowledge.
**Fixed:** 2026-05-24, P2.6 — priority raised to `89 - index` (above all social context tiers).

## [FIXED] ISSUE-019: 20 pre-existing test failures — `consume()` missing on mock Neo4j result objects
**Found:** 2026-05-21, during P2.1 scaffold (confirmed pre-existing via git stash comparison)
**Severity:** P2 (test coverage gap — affected functions work in prod but are undertested)
**Where:** `tests/unit/test_belief_service.py`, `test_generic_graph_service.py`,
           `test_reputation_queries.py`, `test_world_reader.py`, and others
**Description:** Multiple test mock stubs (e.g. `_FakeResult`, `_SessionStub`, `_FakeSession`)
do not implement `consume()` on their result objects. The production code calls
`await result.consume()` after reading records to properly drain the Neo4j cursor.
The mocks were written before `consume()` calls were added, so they now raise
`AttributeError`. These tests fail consistently in the full `pytest tests/` suite.
`make test` count: 20 failed, 951 passed, 17 skipped (988 total). This contradicts
the NEXT_SESSION.md claim of "964/965" which was likely written counting only passing
test files rather than the full suite.
**Why deferred:** Not blocking Phase 2 — production paths work correctly (consume()
only affects the test stubs). Fixing requires updating mock objects in ~5 test files.
**To fix:** Add a `consume()` async no-op method to each affected mock result class,
e.g. `async def consume(self): pass`. Files to update: `test_belief_service.py`,
`test_generic_graph_service.py`, `test_reputation_queries.py`, `test_world_reader.py`,
and any others in the failing set.
**Fixed:** 2026-05-21 — added `async def consume(self) -> None: pass` to `_ResultStub`/`_FakeResult`
classes in `test_generic_graph_service.py`, `test_reputation_queries.py`, `test_world_reader.py`,
`test_reputation_writer.py`, `test_faction_queries.py`, `test_item_writer_v14.py`,
`test_currency_writer_v14.py`; refactored inline async generators in `test_belief_service.py`
into `_R` wrapper classes with `__aiter__` and `consume`.

## [FIXED] ISSUE-017: Unregistered graph type returns HTTP 500 (plain text) instead of 404/422
**Found:** 2026-05-21, during P2.0 smoke-test
**Severity:** P2 (annoying — misleading error for API consumers)
**Where:** `src/npc_engine/api/routes/graph.py` → `list_nodes` / `list_edges` handlers
**Description:** Requesting a node or edge type not registered in the type registry
(e.g. `GET /v1/graph/nodes/WorldEvent`) returns HTTP 500 with a plain-text
"Internal Server Error" body. The root cause is a `dataclasses.FrozenInstanceError`
in `get_db_session`: when `RegistryPayloadValidationError` (a frozen dataclass) is
raised inside the `async with graph_db.get_session()` block, Python 3.11's
`contextlib.__aexit__` tries to set `exc.__traceback__`, which fails on the frozen
dataclass and masks the original error with a second exception.
**Why deferred:** Not blocking Phase 2 — all required types exist under their
correct names (documented in `phase2_demo_game/decisions.md` DEC-P2-03). A proper
fix requires either making `RegistryPayloadValidationError` non-frozen or catching
it in the route handler before the session context manager unwinds.
**To fix:** Catch `RegistryPayloadValidationError` (and similar registry errors)
in `list_nodes` / `list_edges` route handlers before the DB session context exits,
or make the exception class inherit from a non-frozen base. Return 422 with a JSON
body matching the existing error envelope format.
**Fixed:** 2026-05-21 — wrapped `service.list_nodes()` and `service.list_edges()` calls in
`src/npc_engine/api/routes/graph.py` with `try/except RegistryPayloadValidationError` raising
`graph_error_to_http(error)`, matching the existing pattern in POST/PATCH handlers. Added
regression tests `test_list_nodes_unknown_type_returns_422` and
`test_list_edges_unknown_type_returns_422` in `tests/unit/test_graph_warning_pipeline.py`.

## [FIXED] ISSUE-018: subphases.md uses wrong graph type names (WorldEvent, TRUSTS, FEARS, HAS_BELIEF, HAS_GOAL)
**Found:** 2026-05-21, during P2.0 smoke-test
**Severity:** P2 (would cause P2.2/P2.4 code to target non-existent endpoints)
**Where:** `project/roadmap3/phase2_demo_game/subphases.md` — P2.2 and P2.4 steps
**Description:** The subphases plan refers to type names that are not registered in
the type registry. Actual registered equivalents:
`WorldEvent` → `Event`; `WorldState` (capital S) → `world_state` (lowercase);
`TRUSTS` → `STANDS_WITH`; `FEARS` → `OPPOSES`; `HAS_BELIEF` → `BELIEVES`;
`HAS_GOAL` → `PURSUES`.
**Why deferred:** Correction is captured in `phase2_demo_game/decisions.md`
DEC-P2-03. The subphases.md document is a planning artefact; correcting all
inline references now would risk churn. P2.2 and P2.4 implementations will use
the correct names directly.
**To fix:** When Phase 2 is done, do a single pass over `subphases.md` to replace
the planned names with the actual names so the document is accurate for reference.
**Fixed:** 2026-05-21 — replaced all wrong type names in `project/roadmap3/phase2_demo_game/subphases.md`
(11 occurrences: WorldEvent→Event, WorldState→world_state, TRUSTS→STANDS_WITH, FEARS→OPPOSES,
HAS_BELIEF→BELIEVES, HAS_GOAL→PURSUES) and 1 occurrence in `README.md` (WorldState→world_state).
`decisions.md` left intact — it intentionally documents the mapping for historical reference.

## [FIXED] ISSUE-016: test_gossip_rumor_integration mock collision — KeyError 'secret_id'
**Found:** 2026-05-18, during Phase 5 full-suite run
**Severity:** P2 (annoying — 1 failing test)
**Where:** `tests/unit/test_gossip_rumor_integration.py::test_knows_about_still_created_alongside_rumor`
**Description:** `trust_record.__getitem__` lambda only maps `"trust"` → 5; when the gossip
handler reuses the same mock for the secret query, `secret_record["secret_id"]` raises
`KeyError: 'secret_id'`. The test mock setup leaks into the secret-propagation branch.
**Why deferred:** Pre-existing before Phase 5; not introduced by this session's changes.
**To fix:** Give the secret query its own distinct mock result with `secret_id` and `severity` keys.
**Fixed:** 2026-05-19 — added `patch("...gossip_handler.random") as mock_random` with
`mock_random.random.return_value = 1.0` in `test_knows_about_still_created_alongside_rumor`
to suppress the secret-propagation branch, matching the pattern already used in
`test_gossip_handler_calls_propagate_always`.

## [FIXED] ISSUE-011: `.env` NEO4J_URI is container DNS — migration script breaks if `.env` is sourced
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P3 (nice-to-fix)
**Where:** `.env` line 1 (`NEO4J_URI=bolt://neo4j:7687`), `scripts/migrations/add_faction_support.py`
**Description:** `.env` sets `NEO4J_URI=bolt://neo4j:7687` (container hostname). If a user
sources `.env` into the shell before running the migration script from outside Docker,
the Neo4j connection fails — `neo4j` hostname is only resolvable inside the Docker network.
The migration script already defaults to `localhost:7687` via `os.getenv()`, but the trap
is invisible unless documented.
**Why deferred:** Documentation-only fix; no code change required.
**To fix:** Documented in `docs/API.md` under "Migration script" section. Optionally add a
prominent comment in `.env` warning against sourcing it for outside-Docker tooling.
**Fixed:** 2026-05-19 — added inline comment to `.env` on the `NEO4J_URI` line:
`# Docker container hostname — do NOT source this file from the host`.

## [FIXED] ISSUE-004: edge_updater.py — no-any-return from dump_json
**Found:** 2026-05-06, during Phase 1.2 (faction-aware gossip)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/gossip/edge_updater.py:45`
**Description:** `dump_json()` returns `Any`, so `return dump_json(...)` on a function
declared `-> str` triggers `mypy [no-any-return]`. Pre-existing before Phase 1.
**Why deferred:** Not introduced by Phase 1 changes; low risk.
**To fix:** Add `cast(str, dump_json(...))` on the return line, or annotate `dump_json` as `-> str`.
**Fixed:** 2026-05-19 — `dump_json` in `common/json_utils.py` is already annotated `-> str`; the mypy error is not reproducible. No code change required.

## [FIXED] ISSUE-005: adjust_reputation_for_event not wired to event engine
**Found:** 2026-05-06, during Phase 1.3 planning
**Severity:** P3 (nice-to-fix)
**Where:** Future `src/npc_engine/graph/reputation_writer.py` (Phase 1.3)
**Description:** `adjust_reputation_for_event` will be implemented in 1.3 but the
event engine wiring that calls it (e.g., killing a faction member → -20 reputation)
is out of scope for Phase 1. The function will exist but never be triggered automatically.
**Why deferred:** Requires engine changes belonging to a later phase.
**To fix:** Wire in a future event-processing phase that calls `adjust_reputation_for_event`
based on event type + target faction membership.
**Fixed:** 2026-05-19 — added optional `faction_id`/`reputation_delta` fields to `EventTemplate`
and `event.yaml`; wired `adjust_reputation_for_event` in `EventHandler.run_tick` for all characters
at the event location when the template carries these fields; added 5 unit tests in
`test_event_reputation_wiring.py`; annotated 3 event templates (`evt_05_keep_drill`,
`evt_10_guard_desertion`, `evt_06_tax_riot`) with faction/delta values.

## [FIXED] ISSUE-006: character.faction string field not migrated to MEMBER_OF edges
**Found:** 2026-05-06, during Phase 1.1 (faction nodes)
**Severity:** P3 (nice-to-fix)
**Where:** Existing Character nodes with a `faction` string property
**Description:** The migration script only adds the Faction node uniqueness constraint.
Pre-existing `character.faction` string fields are not converted to MEMBER_OF edges,
since that mapping is game-data-specific.
**Why deferred:** Needs operator-supplied mapping of faction name strings to Faction node IDs.
**To fix:** Provide a game-specific migration that reads character.faction, resolves it to
a Faction node ID, and creates the MEMBER_OF edge.
**Fixed:** 2026-05-19 — created `scripts/migrations/migrate_faction_strings.py`; finds
unmigrated Characters, validates all referenced Faction nodes exist (fails fast if any are
missing), creates MEMBER_OF edges; supports `--dry-run` flag.

## [FIXED] ISSUE-015: FactionPoliticsEngine CAUSED_BY retrofit deferred
**Found:** 2026-05-18, during Phase 4.2 (CAUSED_BY retrofit)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/faction_politics/faction_politics_engine.py`
**Description:** EventHandler and QuestGenerationEngine are wired with CAUSED_BY edges.
FactionPoliticsEngine is not — it calls `set_standing()` but the triggering event has no
dedicated graph node to link as `effect_node_id`. A `FactionStandingEvent` node type is
needed before this can be retrofitted cleanly.
**Why deferred:** Requires a new node schema and migration; out of Phase 4 scope.
**To fix:** Define `FactionStandingEvent` node type in the type registry, write it during
`set_standing()`, then add `record_causation(session, effect_node_id=..., cause_event_id=...)`.
**Fixed:** 2026-05-18, Phase 5.3 — `FactionStandingEvent` node and `faction_history_service`
created; `faction_politics_engine` now calls `record_standing_change` after each `set_standing`,
with `cause_event_id` and `cause_rule_id` written for full traceability. tick_id passed through.

## [FIXED] ISSUE-014: WAS_AT `arrived_at_tick` uses current tick as approximation
**Found:** 2026-05-18, during Phase 4.1 (WAS_AT edge)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/routine/routine_engine.py` — `record_departure` call site
**Description:** `arrived_at_tick` is set to `tick_id` (the departure tick) because LOCATED_AT
edges do not store an arrival tick. The true arrival time is unknown at departure time.
`tick_duration` is consequently always 0.
**Why deferred:** Tracking arrival tick requires writing it when `update_character_location`
runs; that is a separate schema addition.
**To fix:** Add `arrived_at_tick: int` to the LOCATED_AT edge schema; write it in
`update_character_location`; read it back in the routine engine before calling `record_departure`.
**Fixed:** 2026-05-18, Phase 5 — added `arrived_at_tick` to `CYPHER_GET_SCHEDULED_CHARACTERS`
and `CYPHER_UPDATE_LOCATED_AT`; `update_character_location` now accepts and writes the tick;
`routine_engine` reads `current_arrived_at_tick` from the row with fallback to `tick_id`.

## [FIXED] ISSUE-013: `how_long_ago` has no defined bucket for 7–27 day distances
**Found:** 2026-05-11, during Phase 3.1 (time_utils.py)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/world/time_utils.py` — `how_long_ago`
**Description:** The ROADMAP spec defines buckets for 0, 1, 2–6, 28, and >28 days but omits
7–27. Current implementation extends "a few days ago" to cover 2–27. See DECISIONS.md entry.
**Why deferred:** Spec ambiguity; not blocking any feature.
**To fix:** Agree on wording (e.g., "a week or two ago") and add a 7–27 bucket in time_utils.
**Fixed:** 2026-05-19 — split bucket: 2–6 → "a few days ago" (unchanged), 7–27 → "a few weeks ago"
(new); updated docstring and added `test_how_long_ago_few_weeks` unit test in
`test_world_time_service.py`.

---

## Closed

## [FIXED] ISSUE-012: `time_of_day`, `year`, `season`, `day` not persisted before Phase 3.1
**Found:** 2026-05-11, during Phase 3.1 (world_writer.py audit)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/world/world_writer.py`, `src/npc_engine/engines/events/event_handler.py`
**Description:** Both `CYPHER_MERGE_WORLD_STATE` constants omitted `time_of_day` from their SET
clauses; the new `year`, `season`, `day` fields were also absent. Time fields were never written
to the graph, so they reset to defaults on each server restart.
**Why deferred:** Pre-existing; discovered during 3.1 schema update.
**To fix:** Add all four time fields to both SET clauses and their `session.run()` call sites.
**Fixed:** 2026-05-11, Phase 3.1 — world_writer.py and event_handler.py updated.

## [FIXED] ISSUE-010: `seed.py` seeds via direct Neo4j, not the external API
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (misses client-parity)
**Where:** `src/npc_engine/data/seed.py` (deleted)
**Description:** `make seed` connected directly to Neo4j via Bolt, bypassing the API
entirely. Breaks if Neo4j port is restricted and doesn't exercise the public API surface.
**To fix:** New `src/npc_engine/data/api_seeder.py` seeds via HTTP API. Old `seed.py` and
`seed_queries.py` deleted. Makefile `seed:` target replaced by `seed-api:`.
**Fixed:** 2026-05-11, api-based-seeding task

## [FIXED] ISSUE-009: `scenario_reputation_drift.py` calls non-existent `POST /v1/admin/characters/`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking scenario)
**Where:** `e2e/scenarios/scenario_reputation_drift.py`
**Description:** Character creation called `POST /v1/admin/characters/` which does not exist.
Characters must be created via `POST /v1/graph/nodes/Character` with `{"properties": {...}}`.
**Fixed:** 2026-05-11, api-based-seeding task

## [FIXED] ISSUE-008: `conftest.py` default API key does not match dev `.env`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking e2e)
**Where:** `e2e/scenarios/conftest.py:42`
**Description:** Default `NPC_API_KEY` was `eval-key-change-me`; dev key is
`local_dev_secret_change_this_2026`. Scenarios failed with 401 without explicit env export.
**Fixed:** 2026-05-11, api-based-seeding task

## [FIXED] ISSUE-007: `conftest.py` uses `X-API-Key` header instead of `Authorization: Bearer`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking e2e)
**Where:** `e2e/scenarios/conftest.py:48`
**Description:** httpx default header was `X-API-Key: {key}`. The middleware only accepts
`Authorization: Bearer <token>` — all scenario requests returned 401.
**Fixed:** 2026-05-11, api-based-seeding task — changed to `Authorization: Bearer {api_key}`.

## [FIXED] ISSUE-001: top_p and stop_sequences stored but not forwarded to adapters
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/llm/factory.py`, all adapter `generate`/`stream` call sites
**Description:** `EngineModelConfig.llm` declares `top_p` and `stop_sequences` fields
(required by ROADMAP 0.4 schema), but none of the LLM adapters accept these parameters.
The values are stored in config but silently ignored when building generation calls.
**Why deferred:** Adapters need interface updates (protocol + all implementations). Not
blocking — default adapter behaviour is acceptable for current backends.
**To fix:** Add `top_p: float` and `stop_sequences: list[str]` to `LLMClientProtocol.generate`
and `stream` signatures; update all adapters; forward from `DialogueLLMClient`.
**Fixed:** 2026-05-06, stability_refactor — added optional `top_p`/`stop_sequences` to all
three protocol methods; updated OllamaAdapter (forwarded to `options`), MistralAdapter
(forwarded to payload), MockLLMAdapter (accepted, ignored); `DialogueLLMClient` stores and
forwards both params; `DialogueHandler` passes them from `engine_model_config.llm`.

---

## [FIXED] ISSUE-002: currency_engine contract name vs economy/ directory mismatch
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/contracts/currency_engine.yaml`,
`src/npc_engine/engines/economy/`
**Description:** `_engine_dir_from_contract_name("currency_engine")` → `"currency"`,
but the actual engine directory is `engines/economy/`. If `currency_engine` ever
gains `uses_llm: true`, `get_config("currency")` will look in the wrong directory.
Currently `uses_llm: false` so there is no runtime failure.
**Why deferred:** Not blocking today. Renaming the directory requires touching imports.
**To fix:** Either rename the contract to `economy_engine` or rename the directory to
`engines/currency/` and update all imports. Coordinate with any planned economy feature work.
**Fixed:** 2026-05-06, stability_refactor — renamed `engines/economy/` → `engines/currency/`;
updated `__init__.py` docstring. No import changes needed (directory was empty stub).

---

## [FIXED] ISSUE-003: OLLAMA_MODEL in Settings is superseded by per-engine model declaration
**Found:** 2026-05-05, during Phase 0.4 (per-engine LLM config)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/config.py` (`OLLAMA_MODEL` field),
`src/npc_engine/engines/llm/factory.py` (`create_llm_client`)
**Description:** `Settings.OLLAMA_MODEL` was the global model name used by the Ollama
adapter. The new `create_llm_client_for_engine` reads the model from `engine_config.llm.model`
instead, making `OLLAMA_MODEL` redundant for all engines that use the new factory path.
`OLLAMA_MODEL` is still read by the legacy `create_llm_client` function which remains for
backward compat.
**Why deferred:** Removing it requires auditing all remaining callers of `create_llm_client`
and may affect tests that construct Settings with this field.
**To fix:** After all call sites migrate to `create_llm_client_for_engine`, remove
`OLLAMA_MODEL` from `config.py` and delete the legacy `create_llm_client` function.
**Fixed:** 2026-05-06, stability_refactor — confirmed zero callers of `create_llm_client`;
removed `create_llm_client`, `BACKEND_BUILDERS`, and all private `_create_*` helpers from
`factory.py`; removed `OLLAMA_MODEL` and `LLM_BACKEND` from `config.py`; rewrote
`test_llm_factory.py` to target `create_llm_client_for_engine`.

---

## [FIXED] ISSUE-020: `emotion` field in DialogueTurn mapped from `mood_update`, not a first-class engine field
**Found:** 2026-05-22, during P2.3 implementation
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/dialogue.py:parse_dialogue_response`
**Description:** The P2.3 spec requested extracting an `emotion` field from
`POST /v1/dialogue` responses, but `DialogueResponse` has no `emotion` field.
`parse_dialogue_response` maps `DialogueTurn.emotion` from `mood_update: str | None`,
with a fallback to `facial_expression["type"]`. This is semantically close but not
identical to a dedicated emotion field.
**Why deferred:** The engine has no plans to add a dedicated `emotion` field. The
current mapping is good enough for demo badge display and does not affect correctness.
**To fix:** If the engine adds a dedicated top-level `emotion` field, update
`parse_dialogue_response` to read it directly and remove the fallback logic.
**Fixed:** 2026-06-01, S0.3 — added `emotion: str | None` to `DialogueResponse` with `model_validator` deriving it from `mood_update`; updated `parse_dialogue_response` to read `raw.get("emotion")` directly.

---

## [FIXED] ISSUE-035: `tone_judge` matcher is stubbed — all tone/voice evals silently skip
**Found:** 2026-05-26, during eval strategy review
**Fixed:** 2026-05-26 (R1.1)
**Severity:** P1 (blocking eval expansion)
**Where:** `evals/matchers.py`
**Description:** The `tone_judge` matcher returned `(True, "SKIP")` unconditionally. Every eval case checking voice or tone reported a false pass.
**Fix:** Replaced stub with synchronous Ollama HTTP call in `_eval_tone_judge`. Reads `judge_prompt` (falls back to `description`) from expectation YAML. Returns `(True/False, reasoning)`. Config via `JUDGE_OLLAMA_URL`, `JUDGE_MODEL`, `JUDGE_TIMEOUT_SECONDS` env vars.

---

## [FIXED] ISSUE-036: NPC voice is a YAML lookup, not a graph property — prompt is not NPC-agnostic
**Found:** 2026-05-26, during eval strategy review
**Fixed:** 2026-05-27 (R1.4)
**Severity:** P1 (architectural)
**Where:** `src/npc_engine/engines/dialogue/prompt_builder.py:31–44`, `src/npc_engine/prompts/dialogue/npc_voices.yaml`
**Description:** `_get_voice(npc_id)` looked up voice in a hardcoded YAML file. New NPCs without an entry got `_default` — a generic descriptor that produced undifferentiated responses. Every new NPC required a YAML edit. The dialogue prompt was not truly NPC-agnostic.
**Fix:** Added `voice_descriptor: { type: str, required: false }` to `character.yaml`. Pulled it in `get_character_with_relations()`. Included in serialized context. Updated `prompt_builder.py` to read from context instead of YAML. Updated all seed scripts to set `voice_descriptor` on Character nodes. Deprecated `npc_voices.yaml`.

---

## [FIXED] ISSUE-037: No negative test cases — behavioral constraints are untested
**Found:** 2026-05-26, during eval strategy review
**Fixed:** 2026-05-26 (R1.2)
**Severity:** P1 (coverage gap)
**Where:** `evals/cases/`
**Description:** All existing eval cases tested "should contain X". No cases tested "should NOT contain X" (e.g., NPC should not mention events they don't KNOWS_ABOUT, hostile NPCs should not offer help). Critical behavioral guards (knowledge guard Rule 5, reputation gate Rule 2) had no test coverage.
**Fix:** Added `keyword_none` matcher to `evals/matchers.py` and created 10 negative eval cases (`evals/cases/case_neg_*.yaml`) covering: knowledge hallucination, voice bleed, role bleed, gossip framing, and self-incrimination. All 17/17 eval cases pass.

---

## [FIXED] ISSUE-038: Existing eval cases reference unseeded NPCs
**Found:** 2026-05-26, during R1.1 implementation
**Fixed:** 2026-05-27 (R1.3)
**Severity:** P2 (annoying)
**Where:** `evals/cases/case_001_grieving_elder.yaml`, `evals/cases/case_002_suspicious_guard.yaml`, `evals/cases/reputation_dialogue_tone.yaml`
**Description:** NPCs `elder_1`, `guard_1`, `blacksmith_npc` were not seeded in the default dev setup. All expectations in these cases (including the now-live `tone_judge`) failed at the API-call level rather than exercising matcher logic.
**Fix:** Created `seeds/world/seed_village_world.py` (vw_ prefix) and `seeds/world/seed_tavern_world.py` (tw_ prefix). Updated cases: `elder_1`→`vw_elder` (location `vw_village_square`), `guard_1`→`vw_guard` (location `vw_gate`), `blacksmith_npc`→`tw_merchant`. All three cases now have `requires_world:` set. Run `make seed-village-world` + `make seed-tavern-world` before `make eval`.

---

## [FIXED] ISSUE-039: Voice eval cases require demo-seed with no enforcement
**Found:** 2026-05-26, during R1.1 implementation
**Fixed:** 2026-05-27 (R1.3)
**Severity:** P2 (annoying)
**Where:** `evals/cases/case_voice_captain_sorn.yaml`, `evals/cases/case_voice_mira_innkeeper.yaml` (and all demo-seed-dependent cases)
**Description:** `captain_sorn` and `mira_innkeeper` were only present after `make demo-seed`. Running `python evals/runner.py` on a fresh server silently failed these cases with no hint that seeding was needed.
**Fix:** Added `requires_world` field to eval case YAML (e.g. `requires_world: demo`). `runner.py` now prints a `[WARN]` line with the exact seed command to stderr whenever a case with `requires_world` fails at the API level. Added `requires_world: demo` to all 13 demo-seed-dependent cases. New tavern/village cases use `requires_world: tavern` and `requires_world: village` respectively.

---

## [FIXED] ISSUE-040: Demo seed tests assert upsert_edge.call_count == 0 but _seed_edge always upserts
**Found:** 2026-05-27, during R1.4 test run
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/tests/test_seed.py:252–255` (`test_seed_all_skips_existing_edges`) and `:302–305` (`test_seed_all_created_is_zero_when_all_exist`)
**Description:** `_seed_edge` is documented to "always write the latest properties" and always returns "created". These two tests assert that `upsert_edge` is never called and that `created == 0` when all nodes exist — incompatible with the current implementation. Pre-existing: both tests fail on the baseline commit before R1.4.
**Why deferred:** Pre-existing; tests don't gate the eval path. No functional regression.
**To fix:** Either (a) update the tests to assert actual edge upsert counts, or (b) add skip-if-exists logic to `_seed_edge` and keep the tests as written.
**Fixed:** 2026-06-01, S0.3 — verified `_seed_edge` already has skip-if-exists logic; both tests were already passing. Also fixed 3 related pre-existing failures (`test_seed_quests_*`) caused by the seeder switching from LLM generation to deterministic `post_quest_offer` path.

---

## [FIXED] ISSUE-041: Demo seed creates WorldState id="ws_main" but world_reader defaults to id="world"
**Found:** 2026-05-27, during R2.2 eval investigation
**Severity:** P2 (annoying)
**Where:** `seeds/worlds/seed_demo_world.py` (`_WORLD_STATE_ID = "ws_main"`), `src/npc_engine/world/world_reader.py:37` (`world_id: str = "world"`)
**Description:** The demo seed created a WorldState node with `id="ws_main"` but `get_world_state()` queried for `id="world"` by default. The demo world's epoch and active_conditions were therefore never read by the context builder — all dialogue requests received a default empty WorldState. Rule 1 epoch constraints never fired for demo world NPC queries.
**Fixed:** 2026-05-27, pre-Phase 3 cleanup — changed `_WORLD_STATE_ID = "world"` in `seeds/worlds/seed_demo_world.py`. Both the seed and reader now use `"world"` as the canonical WorldState id. Logged as DEC-022.

---

## [FIXED] ISSUE-042: faction_gossip_distortion eval case has no runnable endpoint
**Found:** 2026-05-27, during pre-Phase 3 eval coherence review
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/faction_gossip_distortion.yaml`, `evals/runner.py`
**Description:** `faction_gossip_distortion_001` targets a gossip distortion calculation endpoint that does not exist in the API. It has no `input` field so the eval runner auto-skips it with "SKIP: no 'input' field — case targets a non-dialogue endpoint". The case documents the expected gossip distortion logic and probabilities, but cannot be exercised by the current runner.
**Why deferred:** The gossip engine exists but has no dedicated eval endpoint. The case is valuable documentation.
**To fix:** Expose a `/v1/gossip/distort` endpoint (or similar) and extend the runner to POST to it when the case has a non-dialogue `endpoint` field. Alternatively, convert to a unit test against `GossipEngine.distort()`.
**Fixed:** 2026-06-01, S0.3 — deleted `faction_gossip_distortion.yaml`; added 3 unit tests to `tests/unit/test_gossip_distort.py` covering hostile-faction distortion, level range, and canonical-event bypass.

---

## [FIXED] ISSUE-044: Multi-world WorldState conflict — single id="world" is last-seed-wins
**Found:** 2026-05-27, during eval failure investigation
**Severity:** P2 (annoying)
**Where:** `seeds/worlds/seed_demo_world.py`, `seeds/worlds/seed_village_world.py`, `world_reader.py`
**Description:** All seed worlds write their WorldState to `id="world"`. Village seed sets `epoch="age_of_peace"` + `active_conditions=["crop_blight"]`; demo seed sets `epoch="war"` + `active_conditions=["northern_war"]`. Last seed run wins. Running `make seed-village-world` after `make demo-seed` causes demo world eval cases that depend on war epoch (`case_voice_captain_sorn_001`, `case_pos_mira_gossip_hedging`) to fail silently.
**Why deferred:** Mitigation: run `make demo-seed` last before `make eval`. Proper fix requires WorldState ID refactor.
**To fix:** Either (a) prefix WorldState IDs per world (`id="world_demo"`, `id="world_village"`) and extend `world_reader` to accept a configurable ID via eval case `seed` block, or (b) add a per-eval-run world-state setup POST before running cases.
**Fixed:** 2026-06-01, S0.4 — added `WORLD_ID: str = "world_demo"` to `Settings`; changed `demo_game/seed.py` `_WORLD_STATE_ID` to `"world_demo"`, `seed_village_world.py` to `"world_village"`; fixed `world_reader.py` fallback to return `WorldState(id=world_id)`; threaded `world_id` through all 8 `get_world_state` call sites (context_builder, dialogue_handler, event_handler ×2, clock route, quest_generation_engine, story_pacing_engine, tick_scheduler, chapter_engine). Configure per-world reads via `WORLD_ID` in `.env`.

---

## [FIXED] ISSUE-045: game_window.py line count exceeds DEC-024 ~450 soft limit
**Found:** 2026-05-28, during S3.4
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/ui/game_window.py` (~460 lines after S3.4)
**Description:** DEC-024 set a ~450-line soft limit for `game_window.py` (exempt from the 300-line hard limit). S3.4 adds ~24 lines, bringing the total to ~460.
**Why deferred:** Phase 4 `DialoguePanel` / `GraphPanel` refactor is the natural moment to extract rendering logic into separate panel classes. Splitting mid-session (between S3.4 and S3.5) would be artificial churn.
**To fix:** During Phase 4, extract `_draw_left_panel` helpers and/or the graph/sidebar draw branches into dedicated panel classes (`DialoguePanel`, `GraphPanel`, `SidebarPanel`). Each class gets its own file under `demo_game/ui/`.
**Fixed:** 2026-06-01, S0.3 — extracted thread/poller orchestration, queue dispatch, and quest/trade callbacks into new `demo_game/game_controller.py` (389 lines). `game_window.py` reduced from 624 → 260 lines.

---

## [FIXED] ISSUE-043: requires_world is a soft advisory warn, not a hard skip
**Found:** 2026-05-27, during pre-Phase 3 eval coherence review
**Severity:** P3 (nice-to-fix)
**Where:** `evals/runner.py:91–103`
**Description:** When a request fails and the case has `requires_world`, the runner prints a `[WARN]` hint but still marks the expectation FAIL. There is no explicit SKIP for "server is up but world not seeded" vs "server is down". A CI run with the wrong seed state produces unexplained failures rather than a clear skip with a seed-world instruction.
**Why deferred:** Current behavior is informative enough for manual runs. CI is not yet set up with per-world seed fixtures.
**To fix:** If the response is a 4xx with an NPC-not-found body, auto-skip all expectations and emit a clear SKIP reason rather than a FAIL. Or add a pre-flight `GET /v1/graph/nodes/Character/{npc_id}` check and skip if the NPC is absent.
**Fixed:** 2026-06-01, S0.3 — added pre-flight `GET /v1/graph/nodes/Character/{npc_id}` check in `evals/runner.py`; returns hard SKIP (passed=True, skipped=True) with seed command hint when NPC is absent (HTTP 404).

---

## [FIXED] ISSUE-046: GET /v1/economy/price endpoint not yet verified against running engine
**Found:** 2026-05-29, during S4.4 trade price implementation
**Severity:** P2 (annoying)
**Where:** `demo_game/client.py` — `get_item_price()`, `demo_game/ui/left_panel.py` — `set_trade_price()`
**Description:** `get_item_price()` calls `GET /v1/economy/price?item_type=spice&character_id=aldric_merchant`. The endpoint was assumed to exist from the plan; it has not been tested against a live engine. If the route is absent or has a different schema, the trade overlay will silently show nothing (non-fatal, error caught), but the demo feature won't function.
**Why deferred:** Required live engine + seeded Item node. Verification is a 5-minute manual check — deferred to pre-demo run.
**To fix:** Start engine + `make demo-seed`, then `curl "http://localhost:8000/v1/economy/price?item_type=spice&character_id=aldric_merchant"`. If 404: check route in `src/npc_engine/api/` and update the URL. If schema differs: update `get_item_price()` to match actual response shape.
**Fixed:** 2026-06-02, S2.4 — verified statically: `economy_router` is registered at `admin_prefix` (`/v1/admin`) with its own `/economy` prefix, so the route is `GET /v1/admin/economy/price`. `demo_game/client.py:get_item_price()` already calls exactly `/v1/admin/economy/price`. No code change needed.

---

## [FIXED] ISSUE-047: Multiple stale demo test expectations after API path + seeder changes
**Found:** 2026-06-01, during S0.3 (discovered while running `make test-demo`)
**Severity:** P2 (test suite not green)
**Where:** `demo_game/tests/test_client.py`, `demo_game/tests/test_seed.py`, `demo_game/tests/test_right_panel.py`
**Description:** Several tests expected outdated API paths and function signatures accumulated since the demo was extended. 5 client tests expected `/v1/quests/generate`, `/v1/quests/{id}`, `/v1/economy/price` but the client moved to `/v1/admin/` prefixed routes. `post_quest_offer` grew 3 new required args (objectives, item_rewards, currency_reward). 3 seed tests expected LLM-based quest generation but seeder switched to deterministic `post_quest_offer`. 2 right panel tests expected 4 enum values but `RightPanel` grew to 6.
**Fixed:** 2026-06-01, S0.3 — updated all stale test expectations to match current implementation; `test_seed_quests_*` and `test_seed_all_calls_quest_generation` rewritten to test `post_quest_offer` deterministic path; `test_right_panel_enum_has_four_values` → `_has_six_values`; `test_cycle_tab_wraps_back_to_graph` cycle count derived from `len(list(RightPanel))`.

---

## [FIXED] ISSUE-056: 8 remaining pre-existing test failures in HEAD blocking `make check`
**Fixed:** 2026-06-04, final-review Batch 2 (L4-01). Root causes per L4: 3 quest_event_provenance + 2 sev27 were cascades of the deleted `game_schema.yaml` (restored, L9-01); 2 sev06 awaited the now-async `append_turns` (SEV-05); 1 sev18 added the now-required `graph_db`/`settings` ctor args (SEV-08); sev27 also switched caplog→direct logger-patch (propagate=False order-flake). `make check` green: 1590 pass, 0 fail.
**Found:** 2026-06-04, during SEV-04 gossip migration
**Severity:** P2 (test suite not green; `make check` failing)
**Where:** test_quest_event_provenance_v14.py (3), test_sev06_semaphore.py (2), test_structured_output_sev27.py (2), test_error_swallowing_sev18.py (1)
**Description:** 20 failures originally; 12 fixed by SEV-08 (quest_lifecycle+routing TypeRegistry injection + monkeypatch update). Remaining 8: quest_event_provenance needs game_schema.yaml; sev06 calls append_turns synchronously; sev27 caplog fails due to propagate=False; sev18 witnessed-query patch path wrong.
**Why deferred:** Each requires understanding a specific module's current interface unrelated to SEV-08.
**To fix:** (1) Update `test_sev06_semaphore.py` to `await store.append_turns()`; (2) Fix caplog in `test_structured_output_sev27.py`; (3) Fix patch path in `test_error_swallowing_sev18.py`; (4) Fix schema path in `test_quest_event_provenance_v14.py`. Consider during SEV-39.
**Partial fix:** 2026-06-04, SEV-08 fixed 12/20 (test_quest_lifecycle_engine_v14.py + test_quest_reward_routing_v14.py).

## ISSUE-056: graph_rag.py MATCH (seed) full-scan — no label filter
**Found:** 2026-06-04, during SEV-39 coverage fix
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/retrieval/graph_rag.py` — `_CYPHER_EXPAND_SEEDS` query, `MATCH (seed) WHERE seed.id = seed_id`
**Description:** The expansion Cypher does `MATCH (seed)` without a label filter, triggering a full-node scan on every GraphRAG call. In large graphs this will be slow and risk matching unintended node types.
**Why deferred:** Fixing requires knowing the correct label(s) for seed nodes (Event, Knowledge, etc.) which may shift as SEV-04 migrates Cypher domains. Touching the query now risks coupling to SEV-04 in-flight work.
**To fix:** After SEV-04 completes, add `(seed:Event|Knowledge)` label filter (or the appropriate type-registry label constant) to `_CYPHER_EXPAND_SEEDS`. Verify with integration tests against test DB.

## [FIXED] ISSUE-055: `api_seeder.py` uses get-then-skip; consider client-supplied stable ids long-term
**Found:** 2026-06-04, during SEV-10 planning
**Severity:** P3 (nice-to-fix)
**Where:** `data/api_seeder.py`; all typed admin endpoints that auto-generate IDs
**Description:** SEV-10 implements idempotency via get-then-skip (mirror the village seeder). The architecturally correct solution for a multi-tenant middleware product is to let callers supply a stable `id` on creation endpoints and use `MERGE` instead of `CREATE` — this makes seeding and re-seeding fully deterministic without an extra GET round-trip, and aligns the API with idiomatic graph semantics. That change touches endpoint schemas and all callers and was deferred.
**Why deferred:** Scope; get-then-skip is sufficient for current single-world demo use. Client-supplied ids requires coordinating endpoint schema changes with SEV-12 (multi-tenant) and SEV-33 (error envelope).
**To fix:** Change typed admin endpoints (`/characters`, `/items`, `/beliefs`, `/goals`, `/secrets`, `/memories`, etc.) to accept an optional `id` field; use `MERGE (n {id: $id})` when provided. Apply same contract to `api_seeder.py`, `seed_village_world.py`, `demo_game/seed.py`. Document as the canonical seeding contract in `docs/API.md`.
**Fixed:** 2026-06-10, in KE-6 — beliefs, goals, memories, secrets routes accept optional caller-supplied `id`; node is MERGEd when provided, UUID auto-generated when omitted.

## [FIXED] ISSUE-057: Location hierarchy (PART_OF edges between Location nodes) not yet modeled
**Found:** 2026-06-04, during SEV-12 architectural review
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/`, `demo_game/seed.py`, `seeds/worlds/`
**Description:** Locations are flat nodes with no parent/child relationship. The intended model is a hierarchy: market → village → duchy → kingdom → continent → world. Without `PART_OF` edges, location-aware features (region gossip spread, travel time, area-of-effect events) cannot traverse geography.
**Why deferred:** Not needed for current demo or review hardening; design-phase only.
**To fix:** Add a `PART_OF` directed edge type to `type_registry/`; update `graph/location_writer.py` to accept an optional `parent_id`; update `demo_game/seed.py` and eval seeders to wire the hierarchy. Add retrieval helpers for ancestor/descendant traversal.
**Update 2026-06-05:** APPROVED for implementation — see DEC-071 and EXP-87 (`project-harness/expansion/`). Note `location_writer.py` does not yet exist (only `location_graph_queries.py`); it must be created as part of this.
**Fixed:** 2026-06-10, in EXP-87 — `type_registry/base_edges/part_of.yaml` and `graph/location_writer.py` created.

## [FIXED] ISSUE-058: SEV-04 residual — raw Cypher + engine-owned transactions outside `graph/`
**Fixed:** 2026-06-11, Phase 21 S21.4 + follow-up (DEC-087 coordinator, DEC-092 world-state relocation). R005 baseline now empty; `engines/` own zero transactions; world-state DB access lives in `graph/`.
**Found:** 2026-06-04, during final review (L2-01)
**Severity:** P2 (architecture debt; grandfathered, not blocking)
**Where:** `engines/interaction/quest_verifier.py`; `world/world_reader.py`,`world/world_writer.py`; `scheduler/tick_scheduler.py`,`scheduler/tick_lease.py`; `retrieval/graph_rag.py`,`retrieval/embedding_reconciler.py`; engine-owned `begin_transaction`/`commit` in `engines/events/event_handler.py`, `engines/quest/quest_lifecycle_engine.py`, `engines/faction_politics/faction_politics_engine.py`
**Description:** SEV-04 was relabeled DONE→PARTIAL: the bulk of engine query helpers moved to `graph/<domain>_queries.py`, but the above raw Cypher and engine-owned transactions remain. `rg "MATCH \(|begin_transaction|\.commit\(" src/npc_engine/engines src/npc_engine/world` still returns ~30 hits.
**Why deferred:** Grandfathered in `scripts/rules_baseline.txt` (R005); `make check` is honest (passes by baseline). Relocating `world/`/`scheduler/` own-label Cypher may warrant a DECISIONS carve-out rather than a move. Transaction-ownership centralization is tracked by SEV-30.
**To fix:** (1) Relocate `quest_verifier.py` Cypher to `graph/quest_verification_queries.py`. (2) Under SEV-30, hoist engine `begin_transaction`/`commit` into a `graph/`-owned coordinator. (3) For `world/`+`scheduler/` own-label queries, either relocate or add a DECISIONS entry permitting each package its own-label Cypher; then ratchet `rules_baseline.txt` down.
**Progress 2026-06-11 (Phase 21):** Item (1) found **moot** during S21.3 reconcile — `engines/interaction/quest_verifier.py` has zero Cypher. Item (2) **DONE** (S21.4, DEC-087): `graph/transaction_coordinator.py` `run_in_tx` owns begin/commit/rollback; all 5 engine files (`event_handler`, `faction_politics_engine`, `quest_lifecycle_engine`, `quest_offer_service`, `quest_reward_router`) migrated to closures; R005 baseline shrunk by 5 (149→144). Item (3) **DONE** (DEC-092): `world/world_reader.py` + `world/world_writer.py` relocated to `graph/world_state_reader.py` + `graph/world_state_writer.py`, 13 callers repointed, old files deleted. **R005 baseline now empty (141 grandfathered total).**

## [FIXED] ISSUE-059: tier-A "mandatory" dialogue context is unbounded → TokenBudgetExceededError → canned dialogue (L9-04 root cause)
**Found:** 2026-06-04, during final review Batch 4 live diagnosis
**Severity:** P1 (a knowledge-rich NPC's dialogue silently degrades to canned — the headline gossip/memory features stop surfacing)
**Where:** `src/npc_engine/retrieval/context_builder.py::build_serialized_context`, `src/npc_engine/retrieval/context_budget_enforcer.py::fill_to_budget`
**Description:** Live diagnosis of the failing eval-llm-demo gossip tests showed the dialogue pipeline raising `TokenBudgetExceededError: Mandatory context (tier0+tierA) requires 20759 tokens, exceeding prompt_token_budget 2896`. Both degradation tiers fail on this and serve a canned response (`degradation_level=canned`), so the planted rumor never reaches mira's dialogue and the eval judge fails. Root cause is NOT the gossip propagation, the prompt-injection fence (Batch 3), or a cold model — it is that tier-A (mandatory) context is not bounded: a gossip-hub NPC accumulates KNOWS_ABOUT/event entries until tier0+tierA (20759 tokens) dwarfs the budget (2896, derived from OLLAMA_CONTEXT_LENGTH=4096-1200). SEV-07 correctly made this fail loudly but did not bound tier-A, so once knowledge accumulates dialogue is always canned. Magnitude is partly inflated by accumulated test state across repeated seed/plant/advance cycles, but the unbounded-tier-A design issue is real and will recur for any active NPC.
**Why deferred:** The correct fix (curate/cap tier-A to the top-K most relevant+recent mandatory items so it always fits the budget, trimming the rest into optional tier-B) is a context-assembly redesign needing its own TDD and live eval re-verification — too large to land safely inside the security/build remediation batch.
**To fix:** (1) Bound tier-A in `context_builder`/`context_budget_enforcer`: rank mandatory items (recency + relevance to the player turn) and keep only what fits a configured tier-A sub-budget; demote the remainder to tier-B (already trimmable). (2) Add a unit test asserting tier0+tierA never exceeds the budget for a high-knowledge NPC fixture. (3) Re-run `make eval-llm-demo` on a fresh world and confirm mira surfaces the planted rumor. (4) Consider whether the planted-rumor KNOWS_ABOUT should be prioritized into tier-A so gossip consequences are guaranteed to surface.
**Update 2026-06-05:** Fix direction DECIDED — see DEC-070 / EXP-30. Supersedes the "tier-A sub-budget" approach above with a cleaner model: collapse tiers into a small **pinned set** (`world`/`emotion`/persona/session-window/`active_quest`, marked `pinned:true`) + one **ranked pool** filled by `priority × relevance`. The overflow failure becomes impossible by construction. Implementation pending.
**Fixed:** 2026-06-09, in EXP-30 — `context_builder.py` + `context_budget_enforcer.py` rewritten with pinned-core + ranked-pool model; `TokenBudgetExceededError` on tier0+tierA is now structurally impossible.

## [FIXED] ISSUE-060: demo-run ACT 3 bribe uses STANDS_WITH (faction→faction) for a player→faction standing → 404
**Fixed:** 2026-06-05, in EXP-93 — `BribeScene.execute()` now calls `adjust_npc_reputation` (Character→Faction `HAS_REPUTATION_WITH` edge) instead of `put_npc_reputation` (Faction→Faction `STANDS_WITH`).
**Found:** 2026-06-04, during final-review demo walkthrough (fresh world, after the ACT-1 world_state fix unmasked it)
**Severity:** P2 (scripted `make demo-run` cannot complete past ACT 3; pre-existing, was masked by the ACT-1 422)
**Where:** `demo_game/run_scenes.py:239` (`BribeScene` → `runner.client.put_npc_reputation`), `demo_game/client.py::put_npc_reputation` (emits `STANDS_WITH`), vs `src/npc_engine/type_registry/base_edges/stands_with.yaml` (`src_type: faction, dst_type: faction`)
**Description:** The bribe step sets the player's standing with `thieves_guild` via `put_npc_reputation("player_demo", "thieves_guild", ...)`, which upserts a `STANDS_WITH` edge `player_demo → thieves_guild`. But `STANDS_WITH` is contractually `faction→faction`, so the generic edge service resolves the source as `(:Faction {id:"player_demo"})`, finds nothing, and raises `NodeNotFoundError` → HTTP 404 (now redacted to "Resource not found" by L1-02; full detail is server-logged as `graph_route_not_found`). Both nodes exist (`player_demo` is a Character, `thieves_guild` a Faction) — the mismatch is the edge TYPE, not a missing node. Confirmed live on a fresh world: ACTs 1–2 run with real full-tier dialogue; ACT 3 aborts here.
**Why deferred:** Correct fix requires choosing the player→faction standing model (a Character→Faction reputation edge type, or the existing player-reputation mechanism the engine reads) — demo + possibly schema scope, beyond the security/build remediation. Likely additional act bugs lurk beyond ACT 3 (the scripted runner has not completed end-to-end in a while).
**To fix:** (1) Decide the canonical player→faction standing representation (add a `Character→Faction` reputation edge type, or route `put_npc_reputation` through whatever the engine's `player_reputation`/`faction_standings` reader expects). (2) Update `put_npc_reputation`/`BribeScene` to use it. (3) Run `make demo-run` to completion on a fresh world and fix any further act-level breakage; then capture a clean transcript for the demo walkthrough.

## [FIXED] ISSUE-061: demo client ↔ API path drift — `/v1/pledges/...` 404 (pledges router mounted under `/v1/admin`)
**Found:** 2026-06-05, during demo-game regression triage (trade flow erroring)
**Fixed:** 2026-06-05, in `demo_game/client.py` (Phase 0 / EXP-00b) + regression tests `demo_game/tests/test_client.py::test_post_pledge_uses_admin_path` / `::test_get_pledges_for_npc_uses_admin_path`.
**Severity:** P2 (demo politics/pledge panels error continuously; seed logged "Pledge … skipped … 404")
**Where:** `demo_game/client.py` (`post_pledge` / `get_pledges_for_npc`) vs `src/npc_engine/main.py:352` (`pledges_router` under `admin_prefix`=`/v1/admin`) + `pledges.py:63` (`prefix="/pledges"`). Live route is `/v1/admin/pledges/characters/{id}`.
**Root cause + fix:** the hardening refactor moved `pledges_router` under `admin_prefix`; the client still called `/v1/pledges/...` → FastAPI 404. Fixed by aligning the client to `/v1/admin/pledges/characters/...` (consistent with beliefs/goals/memories/secrets, which the demo already calls under `/v1/admin`; no public API surface change). `seed.py` goes through these same client methods, so it is fixed too. Verified live: seed now creates pledges (200 OK), `GET /v1/admin/pledges/characters/lira_fence` → 200.
**Audit result (full demo↔API path scan):** the ONLY real drift was pledges. The earlier-suspected `/v1/quests/offer` at `client.py:830` is a **docstring example string** in `_quest_headers`, not a live call — actual quest calls correctly use `/v1/quest/...` (singular). All other client paths match their router mounts. The remaining Phase-0 item is the CI smoke test (EXP-00c) so this contract can't silently drift again.

## [FIXED] ISSUE-062: `/v1/system/engines` 500 — double serialization in the handler
**Found:** 2026-06-05, during demo-game regression triage
**Fixed:** 2026-06-05, in `src/npc_engine/api/routes/system.py` (Phase 0 / EXP-00a) + regression test `tests/unit/test_dashboard_routes.py::test_engines_route_passes_serialized_records_through`.
**Severity:** P1 (the engines poll 500s every loop)
**Where:** `src/npc_engine/api/routes/system.py:91-95` (`engine_status` handler).
**Root cause (confirmed via live traceback, NOT the original hypothesis):** `TickScheduler.engine_status` (property, `tick_scheduler.py:599-602`) already returns serialized dicts (`{name: record.model_dump()}`). The handler then called `record.model_dump()` on each dict value again → `AttributeError: 'dict' object has no attribute 'model_dump'` → 500. The engines themselves construct and tick fine (the running scheduler is healthy); the original "uncached `get_tick_scheduler` rebuild storm" hypothesis was wrong. `clock.py:126` already consumes the property correctly (passes the dict through), confirming the contract — only `system.py` violated it.
**Fix:** pass the property's dict values through unchanged: `records = list(scheduler.engine_status.values())`. Verified live: `GET /v1/system/engines` → HTTP 200 with the full engine list. `make check` green (1600 passed, 98.31%).
**Note:** the demo *timeout cascade* (`poll failed: timed out`, `ws_recv_timeout`) is a SEPARATE concern, not caused by this fast 500 — split out to ISSUE-063.

## [FIXED] ISSUE-063: demo timeout cascade — synchronous embedding encode blocking the event loop
**Found:** 2026-06-05, during demo-game regression triage (observed alongside ISSUE-062, but distinct)
**Fixed:** 2026-06-05, in `src/npc_engine/retrieval/embedding_index.py` (Phase 0) + regression tests `tests/unit/test_embedding_index_offload.py`.
**Severity:** P2 (the playable demo stalls — every poller + the quest/trade POST time out together)
**Where:** `src/npc_engine/retrieval/embedding_index.py` (`upsert`/`search`/`embed_batch`), `src/npc_engine/retrieval/sentence_encoder.py:50-62` (sync `encode()`); single-worker uvicorn (`Dockerfile:28`, no `--workers`).
**Root cause (confirmed live):** the server is healthy at rest (all demo endpoints 6–18ms), so it was not a hung server or a slow endpoint. `EmbeddingIndex.upsert/search/embed_batch` are `async def` but called the **synchronous** sentence-transformers `encode()` **directly on the asyncio event loop** (no `to_thread`). At startup the embedding reconciler calls `embed_batch` over every seeded node — the first call also lazy-loads the MiniLM model — blocking the single worker for several seconds; during that window the demo's startup poll burst + WS all time out (`poll failed: timed out`, `ws_recv_timeout`, and the `on_quest_accept` POST → `httpx.ReadTimeout`). Once reconciliation completes the loop is free → 8ms. (Ollama is reachable and its adapter is correctly async — not the cause.) Also violated CLAUDE.md "Async: never block in an async context."
**Fix:** offload all three encodes via `await asyncio.to_thread(...)` so CPU-bound encoding runs on a worker thread and never blocks the loop. Verified live: after rebuild, 24 concurrent demo polls returned with a slowest time of 42ms (no stall). `make check` green (1603 passed). Regression tests assert the encode runs off the main thread.
**Residual (logged separately):** the cross-encoder reranker has the same sync-on-loop pattern on the dialogue path → ISSUE-064.

## ISSUE-064: cross-encoder reranker runs synchronous model inference on the event loop (dialogue path)
**Found:** 2026-06-05, during ISSUE-063 fix (same bug class, different call path)
**Severity:** P3 (a shorter, dialogue-only block, not the startup cascade — but still blocks the single worker during retrieval rerank)
**Where:** `src/npc_engine/retrieval/cross_encoder_reranker.py:31-56` (sync `rerank()` → `model.predict()`), called at `src/npc_engine/retrieval/context_builder.py:268`.
**Description:** `rerank()` is a synchronous function doing CPU-bound cross-encoder `predict()`; invoked during Tier B/C context assembly on dialogue turns. If its call chain runs on the event loop, each rerank blocks the single worker for the predict duration (and the first call loads the cross-encoder model). Same fix pattern as ISSUE-063 — offload via `asyncio.to_thread` at the async call site (confirm `context_builder`'s enclosing function is async first; if sync, offload at its nearest async caller).
**Why deferred:** Out of scope for the ISSUE-063 fix (one item, no scope creep); separate call path with its own sync/async chain to confirm.
**To fix:** Offload the cross-encoder `predict()` off the event loop (mirror the `embedding_index` `to_thread` fix); add a regression test asserting it runs off the main thread.

## [FIXED] ISSUE-065: WS dialogue times out — client frame timeout (30s) shorter than full LLM generation (~38s)
**Found:** 2026-06-05, during demo-game dialogue triage (`ws_recv_timeout`)
**Fixed:** 2026-06-05, in `demo_game/constants.py` (Phase 0) + regression test `demo_game/tests/test_dialogue_ws_timeout.py`.
**Severity:** P2 (talking to an NPC times out — dialogue, the headline feature, is unusable on the cold 14b model)
**Where:** `demo_game/constants.py:104` (`NPC_DIALOGUE_TIMEOUT_S=30.0`, imported by `demo_game/dialogue_ws.py:22,86`) vs `demo_game/config.py:33` (`DemoConfig.NPC_DIALOGUE_TIMEOUT_S=120.0`, used for the HTTP dialogue path).
**Root cause (measured live):** the WS server fully generates the response before streaming (`src/npc_engine/api/routes/dialogue_ws.py:161` — `await handler.handle(...)` then chunks the finished text), so time-to-first-frame equals the full `qwen2.5:14b` generation. A live WS probe measured the first frame at **38.1s**. The client WS recv timeout was a stale **30s** (the HTTP path already uses 120s), so `ws.recv()` raised `TimeoutError` → `ws_recv_timeout` before the first token. Not a routing/server bug — a client timeout shorter than the model latency, and inconsistent with the HTTP path.
**Fix:** raise `NPC_DIALOGUE_TIMEOUT_S` to 120.0 (matches `config.DemoConfig`). Regression test asserts the WS timeout is never below the HTTP dialogue timeout. Verified by probe: server delivers the first frame at 38s < 120s.
**Enhancement (not done):** the WS path fake-streams (generate-then-chunk); real token streaming from Ollama would make the first token arrive in ~1-2s and remove the long wait. Future dialogue-UX improvement, not a Phase-0 blocker.

## [FIXED] ISSUE-066: two demo worker tests fail (clock-unavailable fallback) — pre-existing
**Fixed:** 2026-06-05, in EXP-93 — `TestBribeScene` rewritten to assert `adjust_npc_reputation`; `_make_client(tick_id=None)` mock fixed in both `test_action_workers.py` and `test_spread_rumor_worker.py`.
**Found:** 2026-06-05, during ISSUE-065 fix (`make test-demo` showed 2 failures, confirmed present on commit 73a68c0 before this turn's change)
**Severity:** P3 (test-only; the bribe/spread-rumor clock-fallback path)
**Where:** `demo_game/tests/test_action_workers.py::TestBribeWorker::test_bribe_ok_falls_back_to_put_when_no_tick`, `demo_game/tests/test_spread_rumor_worker.py::TestSpreadRumorWorker::test_falls_back_to_tick_zero_when_clock_unavailable` (fails at `test_spread_rumor_worker.py:59`).
**Description:** `TypeError: cannot unpack non-iterable NoneType object` in the clock-unavailable fallback path of the bribe and spread-rumor workers — a test/code mismatch, most likely fallout from the hardening refactor's client changes (not from this turn's dialogue-timeout fix; confirmed pre-existing via `git stash`). `make check` does not run `demo_game/tests/`, so it stayed green and these went unnoticed.
**Why deferred:** Single-task focus — not the ISSUE-065 dialogue-timeout task; logged to fix separately.
**To fix:** Reproduce the `make test-demo` failures, find where the worker returns `None` instead of an unpackable tuple in the no-tick/clock-unavailable branch, fix the worker or the test mock, and fold `make test-demo` into the EXP-00c CI smoke gate so demo-test failures fail CI.

## [FIXED] ISSUE-067: confirm-trade 422 — empty `item_type` passed to /economy/trade
**Found:** 2026-06-05, during demo-game trade triage (`trade failed: POST /v1/admin/economy/trade → HTTP 422`)
**Fixed:** 2026-06-05, in `demo_game/quest_trade_controller.py` (Phase 0) + regression test `demo_game/tests/test_quest_trade_controller.py::test_trade_confirm_substitutes_empty_item_type`.
**Severity:** P2 (confirming a trade always 422s — the trade flow is unusable)
**Where:** `demo_game/quest_trade_controller.py:135` (`on_trade_confirm`) → `POST /v1/admin/economy/trade`; server model `src/npc_engine/api/routes/economy.py:42-52` (`TradeOfferRequest.item_type: str = Field(..., min_length=1)`).
**Root cause (confirmed live):** the server's `propose_trade` interaction returns `negotiation_state.item_type = ""` (present-but-empty — verified via a live `/v1/interaction` call). `on_trade_confirm` then did `state.get("item_type", "spice")`, but `dict.get(k, default)` returns the default only when the key is *absent*, not when it's `""` — so it sent `item_type=""` to `/economy/trade`, which rejects empty with 422. (Not a routing bug; the trade endpoint works with a valid body — a clean `current_tick` body returns 200/accepted.)
**Fix:** `item_type = state.get("item_type") or "spice"` (substitute on empty). Verified: the body now passes validation and reaches the domain layer.
**Deeper issue (logged, not fixed):** the server interaction engine should populate `negotiation_state.item_type` (it loses the proposed `item_type`, returning `""`). The demo workaround masks it; the engine fix belongs to the interaction/trade dispatch (ties to EXP-40 trade-dispatch maturity). The demo only trades spice, so the fallback is safe.
**Note (UI):** the "trade failed" status text the user saw appear at *dialogue-send* time was a stale/lingering status message (dialogue itself worked); fixing the 422 removes the message. A separate status-message-timing cleanup is minor and not logged.

## ISSUE-069: action_workers.py `_get_current_tick` catches only `EngineClientError` — non-engine errors escape
**Found:** 2026-06-05, during EXP-93 integration (spotted by worker, not fixed)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/action_workers.py` — `_get_current_tick` helper
**Description:** The helper catches only `EngineClientError` for the clock fallback. Any other exception (network timeout, unexpected response shape) would propagate uncaught instead of falling back to `tick_id=0`. The EXP-93 test fix sidestepped this via mock shape rather than fixing the guard.
**Why deferred:** Out of scope for EXP-93; non-blocking (demo scale, not production path).
**To fix:** Broaden the `except` to `Exception` (or at minimum `httpx.TimeoutException`) and log the non-client-error case.

## ISSUE-070: `relation:player` key may collide between EXP-11 direct edge and subgraph_retriever bundle
**Found:** 2026-06-05, during EXP-11 integration (spotted by worker, not fixed)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/retrieval/context_builder.py` (EXP-11 addition) vs `src/npc_engine/retrieval/subgraph_retriever.py:64–74`
**Description:** Both EXP-11 and `subgraph_retriever` can emit a `ContextItem(key="relation:player")`. The budget enforcer keeps the higher-priority item (EXP-11 uses priority=88; subgraph_retriever's priority TBD). No correctness bug — just potential deduplication noise.
**Why deferred:** Not blocking; enforcer handles it correctly by priority.
**To fix:** Confirm subgraph_retriever's priority for this key; if lower, it's fine. If equal, add explicit deduplication or rename one key.

## ISSUE-072: `gossip_distort.py` module docstring is a stale placeholder
**Found:** 2026-06-06, during EXP-15 (distortion strategy registry)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/gossip/gossip_distort.py:1-8`
**Description:** Module docstring says `Purpose: (auto-detected — review)` — a stale placeholder from initial scaffolding, not an accurate description.
**Why deferred:** Cosmetic; not blocking anything.
**To fix:** Update to a proper one-sentence description of the module's purpose.

## ISSUE-075: `reputation_nudge.py` variable scope — `new_trust` logged outside `async with tx` block
**Found:** 2026-06-06, during EXP-52 (reputation propagation)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/reputation_nudge.py`
**Description:** `new_trust` is defined inside a `try` block, but the `logger.info` call that references it is outside the `async with tx` block. Technically always defined when the log line is reached (function returns early on edge-not-found), but linter may warn and the scope is non-obvious.
**Why deferred:** Not a bug; not blocking.
**To fix:** Move the logger.info call inside the `async with tx` block, or assign `new_trust` a sentinel default before the try.

## ISSUE-076: `relation_writer.py` module docstring is a stale placeholder
**Found:** 2026-06-06, during EXP-52 (reputation propagation)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/relation_writer.py:1-8`
**Description:** Module docstring says "(auto-detected — review)" — predates the mandatory docstring rule.
**Why deferred:** Cosmetic.
**To fix:** Update to a proper one-sentence module description.

## [FIXED] ISSUE-074: `EmotionUpdater.__init__` uses `model=None` with `# type: ignore[assignment]` instead of `Optional` typing
**Found:** 2026-06-06, during EXP-13 (EmotionModelProtocol)
**Fixed:** 2026-06-09, Batch A gate-fixes (changed to `model: EmotionModelProtocol | None = None`)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/emotion/emotion_updater.py:__init__`
**Description:** Default model injection uses `model: EmotionModelProtocol = None` with a `# type: ignore[assignment]` guard rather than the cleaner `Optional[EmotionModelProtocol] = None` + sentinel pattern. Behavior is correct and all tests pass.
**Why deferred:** Cosmetic typing issue; not blocking.
**To fix:** Change to `model: EmotionModelProtocol | None = None` with a `self._model = model or VadEmotionModel()` guard in the body.

## [FIXED] ISSUE-073: `memory_service.py` inconsistent transaction ownership — decay functions bypass transaction wrapper
**Found:** 2026-06-06, during EXP-17 (charge-weighted decay)
**Fixed:** 2026-06-09, Batch E — wrapped both decay functions in `session.begin_transaction()` / `async with tx`; updated test mock accordingly.
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/memory_service.py:92-128`
**Description:** `create_memory` (line 57) uses `session.begin_transaction()` / `async with tx` pattern per CLAUDE.md session-ownership rule. But `decay_all_vividness` and the new `decay_all_vividness_weighted` call `session.run()` directly without a transaction wrapper — inconsistency that could matter for write atomicity under load.
**Why deferred:** Not blocking; decay is a best-effort bulk operation.
**To fix:** Wrap decay Cypher calls in `session.begin_transaction()` / `async with tx` to match the pattern used in `create_memory`.

## ISSUE-071: Dialogue engine not grounded in live engine state — NPC contradicts trade/quest reality
**Found:** 2026-06-05, during trade-engine bug fix (Mira hardcoded item)
**Severity:** P2 (annoying — breaks immersion, confuses players)
**Where:** `src/npc_engine/engines/dialogue/` + `src/npc_engine/retrieval/context_builder.py`
**Description:** The dialogue engine generates NPC responses from graph context alone; it has no awareness of live engine state from other engines (trade, quest, economy). Example: after the trade engine determines that Mira has no inventory and cannot trade, Mira's LLM-generated dialogue still says "I've got a couple of things that might interest you" — because the prompt context only includes graph facts, not the trade engine's real-time evaluation. The same class of bug can occur with quest state (NPC says "bring me the item" after quest is already complete) and emotion state.
**Why deferred:** Requires a design decision on how to pass engine-resolved facts into the dialogue context assembly pipeline without creating layer violations (dialogue engine calling trade engine, or context_builder calling both). Involves a new "system state" tier in the prompt context.
**To fix:** Introduce a `SystemStateContext` bag — a dict of engine-resolved facts assembled at the API route layer before the dialogue call — and inject it as a new Tier 0 block in `context_builder.py`. The route handler (`api/routes/dialogue.py`) would resolve trade/quest state for the current NPC and player, then pass it into the context builder. This keeps layer boundaries clean (engines do not call each other; the route layer orchestrates).

<!--
Template for a new issue:

## ISSUE-NNN: <short title>
**Found:** YYYY-MM-DD, during <task>
**Severity:** P1 | P2 | P3
**Where:** <file:line or component>
**Description:** What is wrong.
**Why deferred:** Why this is not being fixed now.
**To fix:** What needs to happen to fix it.

When fixed, change the heading to:
## [FIXED] ISSUE-NNN: <short title>
And add:
**Fixed:** YYYY-MM-DD, in <commit/task>
-->

## ISSUE-084: `build_world_state_payload` returns raw dict instead of Pydantic model
**Found:** 2026-06-09, during ISSUE-080 fix (W1)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/seed.py::build_world_state_payload` (returns `dict`)
**Description:** CLAUDE.md strict rule: no raw dict crossing a module boundary. `build_world_state_payload` returns a plain `dict` that is passed to `_seed_node` and `_force_patch_world_state`. Should be a Pydantic `BaseModel` (or `TypedDict` if demo_game keeps it lightweight).
**Why deferred:** Out of scope for the ISSUE-080 fix.
**To fix:** Define a `WorldStatePayload(BaseModel)` in `demo_game/seed.py` and return it from `build_world_state_payload`; update callers.

## ISSUE-085: `world_state.py` uses deprecated `datetime.utcnow()` (Python 3.12+)
**Found:** 2026-06-09, during EXP-21 (W3)
**Severity:** P3 (nice-to-fix — deprecation warning only, not an error)
**Where:** `src/npc_engine/world/world_state.py` (grep `utcnow`)
**Description:** `datetime.utcnow()` is deprecated in Python 3.12 and triggers warnings in every test run. Replace with `datetime.now(timezone.utc)`.
**Why deferred:** Out of scope for EXP-21; affects test noise only.
**To fix:** `s/datetime.utcnow()/datetime.now(timezone.utc)/g` and add `from datetime import timezone` import.

## [FIXED] ISSUE-086: `InteractionState`/`InteractionProposal` are `dataclass(frozen=True)` instead of Pydantic v2 `BaseModel`
**Found:** 2026-06-09, during EXP-40 (W4)
**Fixed:** 2026-06-09, Batch E — migrated both classes to `BaseModel` with `model_config = ConfigDict(frozen=True)`; no caller changes needed (all use keyword constructors and attribute access).
**Severity:** P2 (annoying — violates CLAUDE.md Pydantic-v2 boundary rule)
**Where:** `src/npc_engine/engines/interaction/models.py`
**Description:** Both `InteractionProposal` and `InteractionState` are plain `dataclass(frozen=True)` objects, not Pydantic v2 `BaseModel`. They cross module boundaries (used by `dispatch.py`, `demo_game`), violating the strict rule.
**Why deferred:** Migrating would require updating all callers; out of scope for EXP-40 first slice.
**To fix:** Migrate both classes to `BaseModel` with `model_config = ConfigDict(frozen=True)`; update all callers.

## ISSUE-087: `dialogue_handler.py` calls `get_world_state` twice when arousal>70 AND `learned_facts` non-empty
**Found:** 2026-06-09, during EXP-53 (W2)
**Severity:** P3 (nice-to-fix — duplicate Neo4j read per dialogue turn in hot path)
**Where:** `src/npc_engine/engines/dialogue/dialogue_handler.py` — arousal block (~line 185) + knowledge block (~line 204)
**Description:** Both the arousal-memory branch and the knowledge-learning branch independently call `get_world_state`. When both conditions are true on the same turn, the world state is fetched twice.
**Why deferred:** Minor perf; both branches are conditionally guarded and rarely co-occur. Out of scope for EXP-53.
**To fix:** Hoist the `get_world_state` call to before both branches; pass `world_state` into both.

## [FIXED] ISSUE-088: `DialogueResponse.learned_facts` is `list[str]` in a frozen Pydantic model (should be `tuple[str, ...]`)
**Found:** 2026-06-09, during EXP-53 (W2)
**Fixed:** 2026-06-09, Batch A gate-fixes (changed to `tuple[str, ...] = Field(default=())`)
**Severity:** P3 (nice-to-fix — minor inconsistency with the frozen model convention)
**Where:** `src/npc_engine/engines/dialogue/dialogue_models.py` — `DialogueResponse.learned_facts`
**Description:** `DialogueResponse` is `frozen=True` but `learned_facts: list[str]` is a mutable field. Other ordered fields on the model use immutable types. A tuple would be strictly correct.
**Why deferred:** No current mutation of this field; out of scope for EXP-53.
**To fix:** Change `learned_facts: list[str] = Field(default_factory=list)` to `learned_facts: tuple[str, ...] = ()`.

## ISSUE-089: `knowledge_writer.write_belief` generates a fresh UUID on every call, making MERGE behave like CREATE (no dedup)
**Found:** 2026-06-09, during EXP-53 (W2)
**Severity:** P3 (nice-to-fix — same fact can be persisted multiple times)
**Where:** `src/npc_engine/graph/knowledge_writer.py:66` — `belief_id = str(uuid.uuid4())`
**Description:** The MERGE clause keys on `id`, which is a fresh UUID each call, so the MERGE always inserts. The same fact will be duplicated if stated by the player across multiple turns.
**Why deferred:** Dedup/contradiction detection is explicitly deferred to EXP-53 slice-3 per brief.
**To fix:** Key the MERGE on a stable hash of `(npc_id, content)` to deduplicate, OR use a separate dedup check before calling write_belief. Link with `CONTRADICTS` edge handling (EXP-53 slice-3).

## ISSUE-090: `ah_demo_stub_mira_player_taught` case in fixture has no runner support yet
**Found:** 2026-06-10, during EXP-32 integration
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/anti_hallucination_demo.json` — case `ah_demo_stub_mira_player_taught`, `category: "learned_from_player"`
**Description:** The fixture contains a stub case for player-taught facts (EXP-53 integration). The runner treats it as a `grounded` case and will SKIP if the world isn't pre-seeded with player-taught facts, or FAIL if mira doesn't surface the fact. The `learned_from_player` category is not yet recognized by the runner's classification logic.
**Why deferred:** EXP-53 slice-3 (contradiction/dedup handling) is still pending; the category was left as a stub deliberately.
**To fix:** Once EXP-53 slice-3 lands, add `learned_from_player` category handling to `anti_hallucination_runner.py`: treat like `grounded` but also check that EXP-53 wrote the fact via `write_belief()` before running the case.


## ISSUE-091: demo_game.__init__ imports pygame (via game_window) at module load time — may cause SDL_Init failures in headless test collection
**Found:** 2026-06-10, during EXP-95 fan-in
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/__init__.py:13` — `import demo_game.ui.game_window as _game_window`
**Description:** `__init__.py` now imports `game_window` at module level to allow `_dispatch` to call `game_window.run()`. If `game_window.py` triggers top-level pygame side-effects (display init, mixer init), any test that does a bare `import demo_game` in a headless CI environment will fail with SDL_Init errors at collection time. EXP-95 tests guard this via lazy imports + monkeypatch, but other existing tests may not.
**Why deferred:** No failures observed yet; P3 until `make test-demo` reveals a real collection failure.
**To fix:** Make the `game_window` import lazy inside `_dispatch` (i.e. `import demo_game.ui.game_window as _gw` only when `choice == ArcChoice.FREE_PLAY`) rather than at module level.

## ISSUE-092: Redis-backed emotion (and other high-churn) store — deferred to Unity/Unreal phase
**Found:** 2026-06-10, during EXP-14 DECISIONS (DEC-084)
**Severity:** P3 (nice-to-fix — Neo4j write-through is sufficient for now)
**Where:** `src/npc_engine/engines/emotion/emotion_store.py` + any future high-churn in-memory store
**Description:** README "What's next" advertises Redis-backed emotion store. Per DEC-084 we are
using Neo4j write-through for EXP-14 slice-1. Under heavy concurrent dialogue Redis would
outperform Neo4j for sub-millisecond hot state (valence/arousal); similarly, session_store and
any tick-rate counters would benefit from Redis TTL semantics.
**Why deferred:** New infrastructure dependency (redis-py / aioredis + Docker service + config).
Blocked until the Unity/Unreal SDK integration phase, which already introduces infrastructure
changes and is a natural inflection point.
**To fix:** Add Redis adapter behind EmotionStore and SessionStore interfaces; register as a
new DI option in `api/dependency_singletons.py`; add Docker Compose Redis service.
