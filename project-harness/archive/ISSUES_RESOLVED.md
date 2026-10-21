# Resolved Issues (Archive)

Closed/fixed issues relocated from [`../ISSUES.md`](../ISSUES.md) to keep the live issue log lean (it is read at the start of every session).

Rules:
- Entries preserve their original order and IDs from `ISSUES.md`.
- IDs are still never reused — consult both this file and `../ISSUES.md` for the next id.
- This is an append-only archive; do not edit closed entries.

## Reused ids — documented, not renumbered (DEC-239, ISSUE-248)
Two ids were declared twice in this archive. Both meanings are retained; renumbering a resolved
archive would break inbound references from `DECISIONS.md` and the review documents, which is
worse than the ambiguity. Cite these by title, not by number alone.

- `ISSUE-035` — (a) `reputation_dialogue_tone_001` eval fails, merchant archetype shows no warmth
  toward an allied player (found 2026-05-27); (b) `tone_judge` matcher is stubbed, so all
  tone/voice evals silently skip (found 2026-05-26).
- `ISSUE-056` — (a) 8 remaining pre-existing test failures in HEAD blocking `make check`
  (fixed 2026-06-04); (b) `graph_rag.py` `MATCH (seed)` full-scan with no label filter
  (fixed 2026-06-19).

## Never assigned
These ids were never issued in either `ISSUES.md` or this archive. The gap is recorded so a future
session does not read it as a deletion and does not reuse the numbers.

- `ISSUE-026`
- `ISSUE-027`
- `ISSUE-028`
- `ISSUE-029`
- `ISSUE-030`

---

## [FIXED] ISSUE-099: F1.6 (scheming + investigation detection) DEFERRED — needs design call (DEC-107)
**Fixed:** 2026-06-13, DEC-107 resolved → Option A. F1.6 advance-half (`SchemeAdvanceTick` mints a
registry-valid covert Event per step) + detection-half (`SchemeDetectionTick` flips active→discovered)
implemented + wired; F2.3 route + G2.2 board landed. Commits `0624761`, `95cdb06`, `154b9cd`, `e975215`.
**Found:** 2026-06-12, during the F→G→H build loop (cycle 6)
**Severity:** P2 (blocks F2.3 + G2.2, not the rest)
**Where:** `engines/scheming/` tick wiring + `graph/scheme_writer.add_scheme_step`
**Description:** F1.6's advance-half is under-specified and unsafe to guess: `add_scheme_step` MERGEs a
bare `Event` with no `event_type`, so naive per-tick advancement smuggles invalid Event nodes into the
graph (registry `event` contract requires `event_type`). See DEC-107 for the design options.
**Why deferred:** Choosing how schemes manifest per tick (real covert events vs status-only progression)
is a product/design decision better made by a human than guessed autonomously overnight; invariant 6
(don't thrash) + the schema/data-model caution apply. Detection-half is fine via `status` reuse.
**To fix:** Resolve DEC-107 (pick option A/B/C), then implement the advance tick + investigation-based
detection (status `active`→`discovered`) + scheduler slot, and unblock F2.3 / G2.2.

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

---

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

---

## [FIXED] ISSUE-081: dialogue_handler hardcodes archetype="default" for canned/degradation responses
**Fixed:** 2026-06-11, S23.7 — added `get_npc_archetype(session, npc_id)` reader to `graph_reader.py`;
`DialogueHandler.handle`/`stream` resolve the NPC's real archetype (falling back to `"default"`) and thread
it into `execute_with_degradation`, `_apply_output_ceiling`→`get_canned_response`, and the LLM pipeline.
`DialogueLLMClient` gained backward-compatible `archetype="default"` params on `generate_response`,
`_generate_with_retry`, `fallback_response_payload`, `_fallback_with_metrics`, `_load_fallback_dialogue`, and
`stream_text`; `_load_fallback_dialogue` now reads the archetype key (then "default") from
`fallback_responses.json` (which already has innkeeper/fence/merchant/guard/elder keys). Both the canned
degradation tier and the structured-output validation fallback now serve the NPC's archetype line. Tests:
`test_dialogue_archetype_fallback.py` + a handler end-to-end case in `test_dialogue_handler_fallback_v14.py`.
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

---

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

---

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

---

## [FIXED] ISSUE-077: quest_lifecycle_engine.py is 643 lines — pre-existing over 300-line limit
**Found:** 2026-06-06, during EXP-20 fan-in
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/quest/quest_lifecycle_engine.py` (643 lines)
**Description:** File exceeds the 300-line hard limit (CLAUDE.md). Pre-existing before EXP-20 (EXP-20 reduced it by 2 lines net). The file is grandfathered in `scripts/rules_baseline.txt`.
**Why deferred:** Splitting would require either a new `quest_reward_engine.py` (reward routing logic) + `quest_objective_engine.py` (objective verification) or a `quest_transition_engine.py` for the state machine. This is a non-trivial refactor requiring its own task. A DECISIONS.md entry would be needed to approve the split boundary.
**To fix:** Split into at least two files: `quest_lifecycle_engine.py` (state transitions only, ≤300 lines) + `quest_reward_router.py` (reward routing + item transfer logic). Write a DECISIONS.md entry proposing the split boundary first.
**Fixed:** 2026-06-09, in Batch D (DEC-078). 3-way split: quest_lifecycle_engine.py (285L, accept/update/evaluate), quest_offer_service.py (213L, offer_draft_quest/offer_quest), quest_reward_router.py (290L, apply_rewards). All 17 affected tests updated; 1783+ unit tests green.

---

## [FIXED] ISSUE-078: gossip_handler.py uses stdlib logging.getLogger directly — bypasses npc_engine logging setup
**Found:** 2026-06-06, during EXP-12 fan-in (worker observation)
**Fixed:** 2026-06-09, Batch A gate-fixes (replace `logging.getLogger` with `get_logger` from `npc_engine.utils.logging`)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/gossip/gossip_handler.py` — `import logging; LOGGER = logging.getLogger(__name__)`
**Description:** Uses stdlib `logging.getLogger` directly instead of `npc_engine.utils.logging.get_logger`. This means gossip handler log records go through a different logger hierarchy. In production, if `configure_logging()` is not applied to the root logger, gossip events may not be captured correctly. Inconsistent with the project logging pattern.
**Why deferred:** Low-severity; gossip logs still appear but via a different path. Out of scope for EXP-12 which only touched `relation_mutator.py`.
**To fix:** Replace `import logging; LOGGER = logging.getLogger(__name__)` with `from npc_engine.utils.logging import get_logger; _LOGGER = get_logger(__name__)` in `gossip_handler.py`. Verify existing gossip tests still pass.

---

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

---

## [FIXED] ISSUE-054: redundant `token_budget_enforcer.py` superseded by `fill_to_budget`
**Fixed:** 2026-06-11, S23.6 — deleted `src/npc_engine/retrieval/token_budget_enforcer.py` and its test
`tests/unit/test_context_pipeline.py` after confirming zero importers (the only consumer was the deleted
test; the `TokenBudgetExceededError` class lives canonically in `utils/errors.py` and is unaffected). A stale
comment referencing the module was cleaned. `rg "token_budget_enforcer" src/` now returns 0.
**Found:** 2026-06-03, during SEV-07
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/retrieval/token_budget_enforcer.py` + `tests/unit/test_context_pipeline.py`
**Description:** `enforce_budget` is not wired anywhere and silently drops Tier-A, contradicting the canonical `fill_to_budget` enforcer (see DEC-057). It and its tests are dead weight.
**Why deferred:** Deleting a non-temporary file requires human approval per CLAUDE.md; out of scope for the SEV-07 bug fix.
**To fix:** With approval, delete `token_budget_enforcer.py` and its `test_context_pipeline.py` tests; confirm no imports remain.

---

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

---

## [FIXED] ISSUE-050: test_put_world_state_success asserts id=="world" but client uses "world_demo"
**Found:** 2026-06-03, during S7.2 test run
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/tests/test_client.py:479`
**Description:** `test_put_world_state_success` asserts `kwargs["json"]["properties"]["id"] == "world"` but `put_world_state` in `client.py` hardcodes `"world_demo"` (changed by ISSUE-044 fix). The test was not updated when the ID changed.
**Why deferred:** Test failure is pre-existing, not blocking S7.2. Single-line fix.
**To fix:** Change the assertion in `test_put_world_state_success` to `"world_demo"`.
**Fixed:** 2026-06-03, S7.3 — changed assertion to `"world_demo"` in `demo_game/tests/test_client.py:479`.

---

## [FIXED] ISSUE-049: Give Item action always gives first inventory item — no player choice
**Found:** 2026-06-02, during S4.2 review
**Severity:** P2 (annoying)
**Where:** `demo_game/quest_trade_controller.py` — `handle_give_item` / give-item flow
**Description:** When the player clicks `[Give Item]`, the first item in the player's inventory was given automatically without prompting the player to choose.
**Fixed:** 2026-06-02, S4.2 — added give mode to `InventoryPanelWidget` (clickable rows + Cancel button); added `start_item_pick` to `RightPanelRenderer` (switches to INVENTORY tab, wraps callbacks to restore ACTIONS tab on completion or cancel); removed `get_player_first_item` from `RightPanelRenderer`; updated `game_window.py` callback and event routing. DEC-047 added for right_panel.py line-count exception. 17 new tests.

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

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

---

## [FIXED] ISSUE-004: edge_updater.py — no-any-return from dump_json
**Found:** 2026-05-06, during Phase 1.2 (faction-aware gossip)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/gossip/edge_updater.py:45`
**Description:** `dump_json()` returns `Any`, so `return dump_json(...)` on a function
declared `-> str` triggers `mypy [no-any-return]`. Pre-existing before Phase 1.
**Why deferred:** Not introduced by Phase 1 changes; low risk.
**To fix:** Add `cast(str, dump_json(...))` on the return line, or annotate `dump_json` as `-> str`.
**Fixed:** 2026-05-19 — `dump_json` in `common/json_utils.py` is already annotated `-> str`; the mypy error is not reproducible. No code change required.

---

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

---

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

---

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

---

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

---

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

---

## [FIXED] ISSUE-010: `seed.py` seeds via direct Neo4j, not the external API
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (misses client-parity)
**Where:** `src/npc_engine/data/seed.py` (deleted)
**Description:** `make seed` connected directly to Neo4j via Bolt, bypassing the API
entirely. Breaks if Neo4j port is restricted and doesn't exercise the public API surface.
**To fix:** New `src/npc_engine/data/api_seeder.py` seeds via HTTP API. Old `seed.py` and
`seed_queries.py` deleted. Makefile `seed:` target replaced by `seed-api:`.
**Fixed:** 2026-05-11, api-based-seeding task

---

## [FIXED] ISSUE-009: `scenario_reputation_drift.py` calls non-existent `POST /v1/admin/characters/`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking scenario)
**Where:** `e2e/scenarios/scenario_reputation_drift.py`
**Description:** Character creation called `POST /v1/admin/characters/` which does not exist.
Characters must be created via `POST /v1/graph/nodes/Character` with `{"properties": {...}}`.
**Fixed:** 2026-05-11, api-based-seeding task

---

## [FIXED] ISSUE-008: `conftest.py` default API key does not match dev `.env`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking e2e)
**Where:** `e2e/scenarios/conftest.py:42`
**Description:** Default `NPC_API_KEY` was `eval-key-change-me`; dev key is
`local_dev_secret_change_this_2026`. Scenarios failed with 401 without explicit env export.
**Fixed:** 2026-05-11, api-based-seeding task

---

## [FIXED] ISSUE-007: `conftest.py` uses `X-API-Key` header instead of `Authorization: Bearer`
**Found:** 2026-05-11, during API-based seeding task
**Severity:** P2 (blocking e2e)
**Where:** `e2e/scenarios/conftest.py:48`
**Description:** httpx default header was `X-API-Key: {key}`. The middleware only accepts
`Authorization: Bearer <token>` — all scenario requests returned 401.
**Fixed:** 2026-05-11, api-based-seeding task — changed to `Authorization: Bearer {api_key}`.

---

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

---

## [FIXED] ISSUE-055: `api_seeder.py` uses get-then-skip; consider client-supplied stable ids long-term
**Found:** 2026-06-04, during SEV-10 planning
**Severity:** P3 (nice-to-fix)
**Where:** `data/api_seeder.py`; all typed admin endpoints that auto-generate IDs
**Description:** SEV-10 implements idempotency via get-then-skip (mirror the village seeder). The architecturally correct solution for a multi-tenant middleware product is to let callers supply a stable `id` on creation endpoints and use `MERGE` instead of `CREATE` — this makes seeding and re-seeding fully deterministic without an extra GET round-trip, and aligns the API with idiomatic graph semantics. That change touches endpoint schemas and all callers and was deferred.
**Why deferred:** Scope; get-then-skip is sufficient for current single-world demo use. Client-supplied ids requires coordinating endpoint schema changes with SEV-12 (multi-tenant) and SEV-33 (error envelope).
**To fix:** Change typed admin endpoints (`/characters`, `/items`, `/beliefs`, `/goals`, `/secrets`, `/memories`, etc.) to accept an optional `id` field; use `MERGE (n {id: $id})` when provided. Apply same contract to `api_seeder.py`, `seed_village_world.py`, `demo_game/seed.py`. Document as the canonical seeding contract in `docs/API.md`.
**Fixed:** 2026-06-10, in KE-6 — beliefs, goals, memories, secrets routes accept optional caller-supplied `id`; node is MERGEd when provided, UUID auto-generated when omitted.

---

## [FIXED] ISSUE-057: Location hierarchy (PART_OF edges between Location nodes) not yet modeled
**Found:** 2026-06-04, during SEV-12 architectural review
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/`, `demo_game/seed.py`, `seeds/worlds/`
**Description:** Locations are flat nodes with no parent/child relationship. The intended model is a hierarchy: market → village → duchy → kingdom → continent → world. Without `PART_OF` edges, location-aware features (region gossip spread, travel time, area-of-effect events) cannot traverse geography.
**Why deferred:** Not needed for current demo or review hardening; design-phase only.
**To fix:** Add a `PART_OF` directed edge type to `type_registry/`; update `graph/location_writer.py` to accept an optional `parent_id`; update `demo_game/seed.py` and eval seeders to wire the hierarchy. Add retrieval helpers for ancestor/descendant traversal.
**Update 2026-06-05:** APPROVED for implementation — see DEC-071 and EXP-87 (`project-harness/expansion/`). Note `location_writer.py` does not yet exist (only `location_graph_queries.py`); it must be created as part of this.
**Fixed:** 2026-06-10, in EXP-87 — `type_registry/base_edges/part_of.yaml` and `graph/location_writer.py` created.

---

## [FIXED] ISSUE-058: SEV-04 residual — raw Cypher + engine-owned transactions outside `graph/`
**Fixed:** 2026-06-11, Phase 21 S21.4 + follow-up (DEC-087 coordinator, DEC-092 world-state relocation). R005 baseline now empty; `engines/` own zero transactions; world-state DB access lives in `graph/`.
**Found:** 2026-06-04, during final review (L2-01)
**Severity:** P2 (architecture debt; grandfathered, not blocking)
**Where:** `engines/interaction/quest_verifier.py`; `world/world_reader.py`,`world/world_writer.py`; `scheduler/tick_scheduler.py`,`scheduler/tick_lease.py`; `retrieval/graph_rag.py`,`retrieval/embedding_reconciler.py`; engine-owned `begin_transaction`/`commit` in `engines/events/event_handler.py`, `engines/quest/quest_lifecycle_engine.py`, `engines/faction_politics/faction_politics_engine.py`
**Description:** SEV-04 was relabeled DONE→PARTIAL: the bulk of engine query helpers moved to `graph/<domain>_queries.py`, but the above raw Cypher and engine-owned transactions remain. `rg "MATCH \(|begin_transaction|\.commit\(" src/npc_engine/engines src/npc_engine/world` still returns ~30 hits.
**Why deferred:** Grandfathered in `scripts/rules_baseline.txt` (R005); `make check` is honest (passes by baseline). Relocating `world/`/`scheduler/` own-label Cypher may warrant a DECISIONS carve-out rather than a move. Transaction-ownership centralization is tracked by SEV-30.
**To fix:** (1) Relocate `quest_verifier.py` Cypher to `graph/quest_verification_queries.py`. (2) Under SEV-30, hoist engine `begin_transaction`/`commit` into a `graph/`-owned coordinator. (3) For `world/`+`scheduler/` own-label queries, either relocate or add a DECISIONS entry permitting each package its own-label Cypher; then ratchet `rules_baseline.txt` down.
**Progress 2026-06-11 (Phase 21):** Item (1) found **moot** during S21.3 reconcile — `engines/interaction/quest_verifier.py` has zero Cypher. Item (2) **DONE** (S21.4, DEC-087): `graph/transaction_coordinator.py` `run_in_tx` owns begin/commit/rollback; all 5 engine files (`event_handler`, `faction_politics_engine`, `quest_lifecycle_engine`, `quest_offer_service`, `quest_reward_router`) migrated to closures; R005 baseline shrunk by 5 (149→144). Item (3) **DONE** (DEC-092): `world/world_reader.py` + `world/world_writer.py` relocated to `graph/world_state_reader.py` + `graph/world_state_writer.py`, 13 callers repointed, old files deleted. **R005 baseline now empty (141 grandfathered total).**

---

## [FIXED] ISSUE-059: tier-A "mandatory" dialogue context is unbounded → TokenBudgetExceededError → canned dialogue (L9-04 root cause)
**Found:** 2026-06-04, during final review Batch 4 live diagnosis
**Severity:** P1 (a knowledge-rich NPC's dialogue silently degrades to canned — the headline gossip/memory features stop surfacing)
**Where:** `src/npc_engine/retrieval/context_builder.py::build_serialized_context`, `src/npc_engine/retrieval/context_budget_enforcer.py::fill_to_budget`
**Description:** Live diagnosis of the failing eval-llm-demo gossip tests showed the dialogue pipeline raising `TokenBudgetExceededError: Mandatory context (tier0+tierA) requires 20759 tokens, exceeding prompt_token_budget 2896`. Both degradation tiers fail on this and serve a canned response (`degradation_level=canned`), so the planted rumor never reaches mira's dialogue and the eval judge fails. Root cause is NOT the gossip propagation, the prompt-injection fence (Batch 3), or a cold model — it is that tier-A (mandatory) context is not bounded: a gossip-hub NPC accumulates KNOWS_ABOUT/event entries until tier0+tierA (20759 tokens) dwarfs the budget (2896, derived from OLLAMA_CONTEXT_LENGTH=4096-1200). SEV-07 correctly made this fail loudly but did not bound tier-A, so once knowledge accumulates dialogue is always canned. Magnitude is partly inflated by accumulated test state across repeated seed/plant/advance cycles, but the unbounded-tier-A design issue is real and will recur for any active NPC.
**Why deferred:** The correct fix (curate/cap tier-A to the top-K most relevant+recent mandatory items so it always fits the budget, trimming the rest into optional tier-B) is a context-assembly redesign needing its own TDD and live eval re-verification — too large to land safely inside the security/build remediation batch.
**To fix:** (1) Bound tier-A in `context_builder`/`context_budget_enforcer`: rank mandatory items (recency + relevance to the player turn) and keep only what fits a configured tier-A sub-budget; demote the remainder to tier-B (already trimmable). (2) Add a unit test asserting tier0+tierA never exceeds the budget for a high-knowledge NPC fixture. (3) Re-run `make eval-llm-demo` on a fresh world and confirm mira surfaces the planted rumor. (4) Consider whether the planted-rumor KNOWS_ABOUT should be prioritized into tier-A so gossip consequences are guaranteed to surface.
**Update 2026-06-05:** Fix direction DECIDED — see DEC-070 / EXP-30. Supersedes the "tier-A sub-budget" approach above with a cleaner model: collapse tiers into a small **pinned set** (`world`/`emotion`/persona/session-window/`active_quest`, marked `pinned:true`) + one **ranked pool** filled by `priority × relevance`. The overflow failure becomes impossible by construction. Implementation pending.
**Fixed:** 2026-06-09, in EXP-30 — `context_builder.py` + `context_budget_enforcer.py` rewritten with pinned-core + ranked-pool model; `TokenBudgetExceededError` on tier0+tierA is now structurally impossible.

---

## [FIXED] ISSUE-060: demo-run ACT 3 bribe uses STANDS_WITH (faction→faction) for a player→faction standing → 404
**Fixed:** 2026-06-05, in EXP-93 — `BribeScene.execute()` now calls `adjust_npc_reputation` (Character→Faction `HAS_REPUTATION_WITH` edge) instead of `put_npc_reputation` (Faction→Faction `STANDS_WITH`).
**Found:** 2026-06-04, during final-review demo walkthrough (fresh world, after the ACT-1 world_state fix unmasked it)
**Severity:** P2 (scripted `make demo-run` cannot complete past ACT 3; pre-existing, was masked by the ACT-1 422)
**Where:** `demo_game/run_scenes.py:239` (`BribeScene` → `runner.client.put_npc_reputation`), `demo_game/client.py::put_npc_reputation` (emits `STANDS_WITH`), vs `src/npc_engine/type_registry/base_edges/stands_with.yaml` (`src_type: faction, dst_type: faction`)
**Description:** The bribe step sets the player's standing with `thieves_guild` via `put_npc_reputation("player_demo", "thieves_guild", ...)`, which upserts a `STANDS_WITH` edge `player_demo → thieves_guild`. But `STANDS_WITH` is contractually `faction→faction`, so the generic edge service resolves the source as `(:Faction {id:"player_demo"})`, finds nothing, and raises `NodeNotFoundError` → HTTP 404 (now redacted to "Resource not found" by L1-02; full detail is server-logged as `graph_route_not_found`). Both nodes exist (`player_demo` is a Character, `thieves_guild` a Faction) — the mismatch is the edge TYPE, not a missing node. Confirmed live on a fresh world: ACTs 1–2 run with real full-tier dialogue; ACT 3 aborts here.
**Why deferred:** Correct fix requires choosing the player→faction standing model (a Character→Faction reputation edge type, or the existing player-reputation mechanism the engine reads) — demo + possibly schema scope, beyond the security/build remediation. Likely additional act bugs lurk beyond ACT 3 (the scripted runner has not completed end-to-end in a while).
**To fix:** (1) Decide the canonical player→faction standing representation (add a `Character→Faction` reputation edge type, or route `put_npc_reputation` through whatever the engine's `player_reputation`/`faction_standings` reader expects). (2) Update `put_npc_reputation`/`BribeScene` to use it. (3) Run `make demo-run` to completion on a fresh world and fix any further act-level breakage; then capture a clean transcript for the demo walkthrough.

---

## [FIXED] ISSUE-061: demo client ↔ API path drift — `/v1/pledges/...` 404 (pledges router mounted under `/v1/admin`)
**Found:** 2026-06-05, during demo-game regression triage (trade flow erroring)
**Fixed:** 2026-06-05, in `demo_game/client.py` (Phase 0 / EXP-00b) + regression tests `demo_game/tests/test_client.py::test_post_pledge_uses_admin_path` / `::test_get_pledges_for_npc_uses_admin_path`.
**Severity:** P2 (demo politics/pledge panels error continuously; seed logged "Pledge … skipped … 404")
**Where:** `demo_game/client.py` (`post_pledge` / `get_pledges_for_npc`) vs `src/npc_engine/main.py:352` (`pledges_router` under `admin_prefix`=`/v1/admin`) + `pledges.py:63` (`prefix="/pledges"`). Live route is `/v1/admin/pledges/characters/{id}`.
**Root cause + fix:** the hardening refactor moved `pledges_router` under `admin_prefix`; the client still called `/v1/pledges/...` → FastAPI 404. Fixed by aligning the client to `/v1/admin/pledges/characters/...` (consistent with beliefs/goals/memories/secrets, which the demo already calls under `/v1/admin`; no public API surface change). `seed.py` goes through these same client methods, so it is fixed too. Verified live: seed now creates pledges (200 OK), `GET /v1/admin/pledges/characters/lira_fence` → 200.
**Audit result (full demo↔API path scan):** the ONLY real drift was pledges. The earlier-suspected `/v1/quests/offer` at `client.py:830` is a **docstring example string** in `_quest_headers`, not a live call — actual quest calls correctly use `/v1/quest/...` (singular). All other client paths match their router mounts. The remaining Phase-0 item is the CI smoke test (EXP-00c) so this contract can't silently drift again.

---

## [FIXED] ISSUE-062: `/v1/system/engines` 500 — double serialization in the handler
**Found:** 2026-06-05, during demo-game regression triage
**Fixed:** 2026-06-05, in `src/npc_engine/api/routes/system.py` (Phase 0 / EXP-00a) + regression test `tests/unit/test_dashboard_routes.py::test_engines_route_passes_serialized_records_through`.
**Severity:** P1 (the engines poll 500s every loop)
**Where:** `src/npc_engine/api/routes/system.py:91-95` (`engine_status` handler).
**Root cause (confirmed via live traceback, NOT the original hypothesis):** `TickScheduler.engine_status` (property, `tick_scheduler.py:599-602`) already returns serialized dicts (`{name: record.model_dump()}`). The handler then called `record.model_dump()` on each dict value again → `AttributeError: 'dict' object has no attribute 'model_dump'` → 500. The engines themselves construct and tick fine (the running scheduler is healthy); the original "uncached `get_tick_scheduler` rebuild storm" hypothesis was wrong. `clock.py:126` already consumes the property correctly (passes the dict through), confirming the contract — only `system.py` violated it.
**Fix:** pass the property's dict values through unchanged: `records = list(scheduler.engine_status.values())`. Verified live: `GET /v1/system/engines` → HTTP 200 with the full engine list. `make check` green (1600 passed, 98.31%).
**Note:** the demo *timeout cascade* (`poll failed: timed out`, `ws_recv_timeout`) is a SEPARATE concern, not caused by this fast 500 — split out to ISSUE-063.

---

## [FIXED] ISSUE-063: demo timeout cascade — synchronous embedding encode blocking the event loop
**Found:** 2026-06-05, during demo-game regression triage (observed alongside ISSUE-062, but distinct)
**Fixed:** 2026-06-05, in `src/npc_engine/retrieval/embedding_index.py` (Phase 0) + regression tests `tests/unit/test_embedding_index_offload.py`.
**Severity:** P2 (the playable demo stalls — every poller + the quest/trade POST time out together)
**Where:** `src/npc_engine/retrieval/embedding_index.py` (`upsert`/`search`/`embed_batch`), `src/npc_engine/retrieval/sentence_encoder.py:50-62` (sync `encode()`); single-worker uvicorn (`Dockerfile:28`, no `--workers`).
**Root cause (confirmed live):** the server is healthy at rest (all demo endpoints 6–18ms), so it was not a hung server or a slow endpoint. `EmbeddingIndex.upsert/search/embed_batch` are `async def` but called the **synchronous** sentence-transformers `encode()` **directly on the asyncio event loop** (no `to_thread`). At startup the embedding reconciler calls `embed_batch` over every seeded node — the first call also lazy-loads the MiniLM model — blocking the single worker for several seconds; during that window the demo's startup poll burst + WS all time out (`poll failed: timed out`, `ws_recv_timeout`, and the `on_quest_accept` POST → `httpx.ReadTimeout`). Once reconciliation completes the loop is free → 8ms. (Ollama is reachable and its adapter is correctly async — not the cause.) Also violated CLAUDE.md "Async: never block in an async context."
**Fix:** offload all three encodes via `await asyncio.to_thread(...)` so CPU-bound encoding runs on a worker thread and never blocks the loop. Verified live: after rebuild, 24 concurrent demo polls returned with a slowest time of 42ms (no stall). `make check` green (1603 passed). Regression tests assert the encode runs off the main thread.
**Residual (logged separately):** the cross-encoder reranker has the same sync-on-loop pattern on the dialogue path → ISSUE-064.

---

## [FIXED] ISSUE-065: WS dialogue times out — client frame timeout (30s) shorter than full LLM generation (~38s)
**Found:** 2026-06-05, during demo-game dialogue triage (`ws_recv_timeout`)
**Fixed:** 2026-06-05, in `demo_game/constants.py` (Phase 0) + regression test `demo_game/tests/test_dialogue_ws_timeout.py`.
**Severity:** P2 (talking to an NPC times out — dialogue, the headline feature, is unusable on the cold 14b model)
**Where:** `demo_game/constants.py:104` (`NPC_DIALOGUE_TIMEOUT_S=30.0`, imported by `demo_game/dialogue_ws.py:22,86`) vs `demo_game/config.py:33` (`DemoConfig.NPC_DIALOGUE_TIMEOUT_S=120.0`, used for the HTTP dialogue path).
**Root cause (measured live):** the WS server fully generates the response before streaming (`src/npc_engine/api/routes/dialogue_ws.py:161` — `await handler.handle(...)` then chunks the finished text), so time-to-first-frame equals the full `qwen2.5:14b` generation. A live WS probe measured the first frame at **38.1s**. The client WS recv timeout was a stale **30s** (the HTTP path already uses 120s), so `ws.recv()` raised `TimeoutError` → `ws_recv_timeout` before the first token. Not a routing/server bug — a client timeout shorter than the model latency, and inconsistent with the HTTP path.
**Fix:** raise `NPC_DIALOGUE_TIMEOUT_S` to 120.0 (matches `config.DemoConfig`). Regression test asserts the WS timeout is never below the HTTP dialogue timeout. Verified by probe: server delivers the first frame at 38s < 120s.
**Enhancement (not done):** the WS path fake-streams (generate-then-chunk); real token streaming from Ollama would make the first token arrive in ~1-2s and remove the long wait. Future dialogue-UX improvement, not a Phase-0 blocker.

---

## [FIXED] ISSUE-066: two demo worker tests fail (clock-unavailable fallback) — pre-existing
**Fixed:** 2026-06-05, in EXP-93 — `TestBribeScene` rewritten to assert `adjust_npc_reputation`; `_make_client(tick_id=None)` mock fixed in both `test_action_workers.py` and `test_spread_rumor_worker.py`.
**Found:** 2026-06-05, during ISSUE-065 fix (`make test-demo` showed 2 failures, confirmed present on commit 73a68c0 before this turn's change)
**Severity:** P3 (test-only; the bribe/spread-rumor clock-fallback path)
**Where:** `demo_game/tests/test_action_workers.py::TestBribeWorker::test_bribe_ok_falls_back_to_put_when_no_tick`, `demo_game/tests/test_spread_rumor_worker.py::TestSpreadRumorWorker::test_falls_back_to_tick_zero_when_clock_unavailable` (fails at `test_spread_rumor_worker.py:59`).
**Description:** `TypeError: cannot unpack non-iterable NoneType object` in the clock-unavailable fallback path of the bribe and spread-rumor workers — a test/code mismatch, most likely fallout from the hardening refactor's client changes (not from this turn's dialogue-timeout fix; confirmed pre-existing via `git stash`). `make check` does not run `demo_game/tests/`, so it stayed green and these went unnoticed.
**Why deferred:** Single-task focus — not the ISSUE-065 dialogue-timeout task; logged to fix separately.
**To fix:** Reproduce the `make test-demo` failures, find where the worker returns `None` instead of an unpackable tuple in the no-tick/clock-unavailable branch, fix the worker or the test mock, and fold `make test-demo` into the EXP-00c CI smoke gate so demo-test failures fail CI.

---

## [FIXED] ISSUE-067: confirm-trade 422 — empty `item_type` passed to /economy/trade
**Found:** 2026-06-05, during demo-game trade triage (`trade failed: POST /v1/admin/economy/trade → HTTP 422`)
**Fixed:** 2026-06-05, in `demo_game/quest_trade_controller.py` (Phase 0) + regression test `demo_game/tests/test_quest_trade_controller.py::test_trade_confirm_substitutes_empty_item_type`.
**Severity:** P2 (confirming a trade always 422s — the trade flow is unusable)
**Where:** `demo_game/quest_trade_controller.py:135` (`on_trade_confirm`) → `POST /v1/admin/economy/trade`; server model `src/npc_engine/api/routes/economy.py:42-52` (`TradeOfferRequest.item_type: str = Field(..., min_length=1)`).
**Root cause (confirmed live):** the server's `propose_trade` interaction returns `negotiation_state.item_type = ""` (present-but-empty — verified via a live `/v1/interaction` call). `on_trade_confirm` then did `state.get("item_type", "spice")`, but `dict.get(k, default)` returns the default only when the key is *absent*, not when it's `""` — so it sent `item_type=""` to `/economy/trade`, which rejects empty with 422. (Not a routing bug; the trade endpoint works with a valid body — a clean `current_tick` body returns 200/accepted.)
**Fix:** `item_type = state.get("item_type") or "spice"` (substitute on empty). Verified: the body now passes validation and reaches the domain layer.
**Deeper issue (logged, not fixed):** the server interaction engine should populate `negotiation_state.item_type` (it loses the proposed `item_type`, returning `""`). The demo workaround masks it; the engine fix belongs to the interaction/trade dispatch (ties to EXP-40 trade-dispatch maturity). The demo only trades spice, so the fallback is safe.
**Note (UI):** the "trade failed" status text the user saw appear at *dialogue-send* time was a stale/lingering status message (dialogue itself worked); fixing the 422 removes the message. A separate status-message-timing cleanup is minor and not logged.

---

## [FIXED] ISSUE-069: action_workers.py `_get_current_tick` catches only `EngineClientError` — non-engine errors escape
**Fixed:** 2026-06-11, S23.3 — added a second `except Exception` branch to `_get_current_tick` so non-client
errors (timeout, unexpected response shape) are logged and fall back to `None` instead of propagating. The
`EngineClientError` branch is retained with a distinct log message. Test: `TestGetCurrentTick` in
`demo_game/tests/test_action_workers.py`.
**Found:** 2026-06-05, during EXP-93 integration (spotted by worker, not fixed)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/action_workers.py` — `_get_current_tick` helper
**Description:** The helper catches only `EngineClientError` for the clock fallback. Any other exception (network timeout, unexpected response shape) would propagate uncaught instead of falling back to `tick_id=0`. The EXP-93 test fix sidestepped this via mock shape rather than fixing the guard.
**Why deferred:** Out of scope for EXP-93; non-blocking (demo scale, not production path).
**To fix:** Broaden the `except` to `Exception` (or at minimum `httpx.TimeoutException`) and log the non-client-error case.

---

## [FIXED] ISSUE-070: `relation:player` key may collide between EXP-11 direct edge and subgraph_retriever bundle
**Fixed:** 2026-06-11, S23.3 — confirmed deterministic, no rename needed. subgraph_retriever emits
`relation:player` at **priority=95**; EXP-11 in context_builder at **priority=88**. `context_merger.merge_context`
dedups by key keeping the strictly-higher priority (`item.priority > existing.priority`), so the subgraph item
(95) wins deterministically whenever both are present — distinct priorities, no insertion-order ambiguity.
(The issue assumed subgraph was lower; it is actually higher, but determinism holds either way since 95 ≠ 88.)
Added cross-referencing comments at both emission sites.
**Found:** 2026-06-05, during EXP-11 integration (spotted by worker, not fixed)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/retrieval/context_builder.py` (EXP-11 addition) vs `src/npc_engine/retrieval/subgraph_retriever.py:64–74`
**Description:** Both EXP-11 and `subgraph_retriever` can emit a `ContextItem(key="relation:player")`. The budget enforcer keeps the higher-priority item (EXP-11 uses priority=88; subgraph_retriever's priority TBD). No correctness bug — just potential deduplication noise.
**Why deferred:** Not blocking; enforcer handles it correctly by priority.
**To fix:** Confirm subgraph_retriever's priority for this key; if lower, it's fine. If equal, add explicit deduplication or rename one key.

---

## [FIXED] ISSUE-075: `reputation_nudge.py` variable scope — `new_trust` logged outside `async with tx` block
**Fixed:** 2026-06-11, S23.2 — found already resolved by an intervening refactor. The transaction
body now lives in `_read_modify_write`, which returns `(new_trust, new_affection)` and closes its own
`async with tx`. `apply_trust_nudge` logs from the `None`-guarded return tuple (`if result is None: return`),
so `new_trust` is a cleanly-scoped local, never a try-scoped reference outside its block. No code change needed.
**Found:** 2026-06-06, during EXP-52 (reputation propagation)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/reputation_nudge.py`
**Description:** `new_trust` is defined inside a `try` block, but the `logger.info` call that references it is outside the `async with tx` block. Technically always defined when the log line is reached (function returns early on edge-not-found), but linter may warn and the scope is non-obvious.
**Why deferred:** Not a bug; not blocking.
**To fix:** Move the logger.info call inside the `async with tx` block, or assign `new_trust` a sentinel default before the try.

---

## [FIXED] ISSUE-074: `EmotionUpdater.__init__` uses `model=None` with `# type: ignore[assignment]` instead of `Optional` typing
**Found:** 2026-06-06, during EXP-13 (EmotionModelProtocol)
**Fixed:** 2026-06-09, Batch A gate-fixes (changed to `model: EmotionModelProtocol | None = None`)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/emotion/emotion_updater.py:__init__`
**Description:** Default model injection uses `model: EmotionModelProtocol = None` with a `# type: ignore[assignment]` guard rather than the cleaner `Optional[EmotionModelProtocol] = None` + sentinel pattern. Behavior is correct and all tests pass.
**Why deferred:** Cosmetic typing issue; not blocking.
**To fix:** Change to `model: EmotionModelProtocol | None = None` with a `self._model = model or VadEmotionModel()` guard in the body.

---

## [FIXED] ISSUE-073: `memory_service.py` inconsistent transaction ownership — decay functions bypass transaction wrapper
**Found:** 2026-06-06, during EXP-17 (charge-weighted decay)
**Fixed:** 2026-06-09, Batch E — wrapped both decay functions in `session.begin_transaction()` / `async with tx`; updated test mock accordingly.
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/memory_service.py:92-128`
**Description:** `create_memory` (line 57) uses `session.begin_transaction()` / `async with tx` pattern per CLAUDE.md session-ownership rule. But `decay_all_vividness` and the new `decay_all_vividness_weighted` call `session.run()` directly without a transaction wrapper — inconsistency that could matter for write atomicity under load.
**Why deferred:** Not blocking; decay is a best-effort bulk operation.
**To fix:** Wrap decay Cypher calls in `session.begin_transaction()` / `async with tx` to match the pattern used in `create_memory`.

---

---

## [FIXED] ISSUE-084: `build_world_state_payload` returns raw dict instead of Pydantic model
**Fixed:** 2026-06-11, S23.5 — added `WorldStatePayload(BaseModel)` inline in `demo_game/seed.py`;
`build_world_state_payload` now returns it. The single production call site passes `.model_dump()` into the
generic dict-based `_seed_node` (kept generic for all node types). Tests updated to attribute access
(`test_seed.py`, `test_sev13_world_state_id.py`).
**Found:** 2026-06-09, during ISSUE-080 fix (W1)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/seed.py::build_world_state_payload` (returns `dict`)
**Description:** CLAUDE.md strict rule: no raw dict crossing a module boundary. `build_world_state_payload` returns a plain `dict` that is passed to `_seed_node` and `_force_patch_world_state`. Should be a Pydantic `BaseModel` (or `TypedDict` if demo_game keeps it lightweight).
**Why deferred:** Out of scope for the ISSUE-080 fix.
**To fix:** Define a `WorldStatePayload(BaseModel)` in `demo_game/seed.py` and return it from `build_world_state_payload`; update callers.

---

## [FIXED] ISSUE-086: `InteractionState`/`InteractionProposal` are `dataclass(frozen=True)` instead of Pydantic v2 `BaseModel`
**Found:** 2026-06-09, during EXP-40 (W4)
**Fixed:** 2026-06-09, Batch E — migrated both classes to `BaseModel` with `model_config = ConfigDict(frozen=True)`; no caller changes needed (all use keyword constructors and attribute access).
**Severity:** P2 (annoying — violates CLAUDE.md Pydantic-v2 boundary rule)
**Where:** `src/npc_engine/engines/interaction/models.py`
**Description:** Both `InteractionProposal` and `InteractionState` are plain `dataclass(frozen=True)` objects, not Pydantic v2 `BaseModel`. They cross module boundaries (used by `dispatch.py`, `demo_game`), violating the strict rule.
**Why deferred:** Migrating would require updating all callers; out of scope for EXP-40 first slice.
**To fix:** Migrate both classes to `BaseModel` with `model_config = ConfigDict(frozen=True)`; update all callers.

---

## [FIXED] ISSUE-087: `dialogue_handler.py` calls `get_world_state` twice when arousal>70 AND `learned_facts` non-empty
**Fixed:** 2026-06-11, S23.2 — new `_maybe_load_world_state` fetches the world state at most once per turn
(guarded by `_needs_world_state`, which mirrors the two branch conditions) and passes the result into both
`_apply_arousal_memory` and `_apply_knowledge_and_routine`. The double read is gone, and the common-path
zero-read is preserved (no fetch when neither branch fires). `HIGH_AROUSAL_THRESHOLD`/`LOW_VALENCE_THRESHOLD`
named. Tests: `test_dialogue_world_state_hoist.py`.
**Found:** 2026-06-09, during EXP-53 (W2)
**Severity:** P3 (nice-to-fix — duplicate Neo4j read per dialogue turn in hot path)
**Where:** `src/npc_engine/engines/dialogue/dialogue_handler.py` — arousal block (~line 185) + knowledge block (~line 204)
**Description:** Both the arousal-memory branch and the knowledge-learning branch independently call `get_world_state`. When both conditions are true on the same turn, the world state is fetched twice.
**Why deferred:** Minor perf; both branches are conditionally guarded and rarely co-occur. Out of scope for EXP-53.
**To fix:** Hoist the `get_world_state` call to before both branches; pass `world_state` into both.

---

## [FIXED] ISSUE-088: `DialogueResponse.learned_facts` is `list[str]` in a frozen Pydantic model (should be `tuple[str, ...]`)
**Found:** 2026-06-09, during EXP-53 (W2)
**Fixed:** 2026-06-09, Batch A gate-fixes (changed to `tuple[str, ...] = Field(default=())`)
**Severity:** P3 (nice-to-fix — minor inconsistency with the frozen model convention)
**Where:** `src/npc_engine/engines/dialogue/dialogue_models.py` — `DialogueResponse.learned_facts`
**Description:** `DialogueResponse` is `frozen=True` but `learned_facts: list[str]` is a mutable field. Other ordered fields on the model use immutable types. A tuple would be strictly correct.
**Why deferred:** No current mutation of this field; out of scope for EXP-53.
**To fix:** Change `learned_facts: list[str] = Field(default_factory=list)` to `learned_facts: tuple[str, ...] = ()`.

---

## [FIXED] ISSUE-089: `knowledge_writer.write_belief` generates a fresh UUID on every call, making MERGE behave like CREATE (no dedup)
**Fixed:** 2026-06-11, S23.4 — `belief_id` is now `hashlib.sha256(f"{npc_id}:{content}".encode()).hexdigest()[:16]`
(`_BELIEF_ID_HASH_LENGTH=16`), so the MERGE keys on a stable per-(npc, content) id and repeated identical
facts collapse onto one node. Tests: `test_knowledge_writer.py` (same id for identical writes; distinct id
for different content or different NPC).
**Found:** 2026-06-09, during EXP-53 (W2)
**Severity:** P3 (nice-to-fix — same fact can be persisted multiple times)
**Where:** `src/npc_engine/graph/knowledge_writer.py:66` — `belief_id = str(uuid.uuid4())`
**Description:** The MERGE clause keys on `id`, which is a fresh UUID each call, so the MERGE always inserts. The same fact will be duplicated if stated by the player across multiple turns.
**Why deferred:** Dedup/contradiction detection is explicitly deferred to EXP-53 slice-3 per brief.
**To fix:** Key the MERGE on a stable hash of `(npc_id, content)` to deduplicate, OR use a separate dedup check before calling write_belief. Link with `CONTRADICTS` edge handling (EXP-53 slice-3).

---

## [FIXED] ISSUE-090: `ah_demo_stub_mira_player_taught` case in fixture has no runner support yet
**Fixed:** 2026-06-11, S24.1 — `anti_hallucination_runner.py` now recognizes the `learned_from_player`
category. Before scoring, it pre-flights `GET /v1/admin/beliefs/{npc_id}` (DEC-095, REST-only — the runner
does not import `src/`) and confirms a persisted belief matches `preflight_belief_substrings`; if absent or
the query errors, the case is **skipped** (counts unaffected) rather than false-failed, otherwise it is
scored as `grounded`. Fixture case renamed `ah_demo_stub_mira_player_taught` → `ah_demo_mira_player_taught`
and given `preflight_belief_substrings: ["eastern", "road"]`. Tests: `test_anti_hallucination_runner.py`
(persisted→grounded, absent→skip, + 4 helper unit cases).
**Found:** 2026-06-10, during EXP-32 integration
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/anti_hallucination_demo.json` — case `ah_demo_stub_mira_player_taught`, `category: "learned_from_player"`
**Description:** The fixture contains a stub case for player-taught facts (EXP-53 integration). The runner treats it as a `grounded` case and will SKIP if the world isn't pre-seeded with player-taught facts, or FAIL if mira doesn't surface the fact. The `learned_from_player` category is not yet recognized by the runner's classification logic.
**Why deferred:** EXP-53 slice-3 (contradiction/dedup handling) is still pending; the category was left as a stub deliberately.
**To fix:** Once EXP-53 slice-3 lands, add `learned_from_player` category handling to `anti_hallucination_runner.py`: treat like `grounded` but also check that EXP-53 wrote the fact via `write_belief()` before running the case.

---

## [FIXED] ISSUE-091: demo_game.__init__ imports pygame (via game_window) at module load time — may cause SDL_Init failures in headless test collection
**Fixed:** 2026-06-11, S23.6 — moved `import demo_game.ui.game_window` out of module scope and into the
`_dispatch` FREE_PLAY branch (lazy import), so a bare `import demo_game` no longer pulls in the pygame-backed
window. Regression test `demo_game/tests/test_lazy_game_window_import.py` asserts (via a clean subprocess)
that `demo_game.ui.game_window` is absent from `sys.modules` after `import demo_game`.
**Found:** 2026-06-10, during EXP-95 fan-in
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/__init__.py:13` — `import demo_game.ui.game_window as _game_window`
**Description:** `__init__.py` now imports `game_window` at module level to allow `_dispatch` to call `game_window.run()`. If `game_window.py` triggers top-level pygame side-effects (display init, mixer init), any test that does a bare `import demo_game` in a headless CI environment will fail with SDL_Init errors at collection time. EXP-95 tests guard this via lazy imports + monkeypatch, but other existing tests may not.
**Why deferred:** No failures observed yet; P3 until `make test-demo` reveals a real collection failure.
**To fix:** Make the `game_window` import lazy inside `_dispatch` (i.e. `import demo_game.ui.game_window as _gw` only when `choice == ArcChoice.FREE_PLAY`) rather than at module level.

---

## [FIXED] ISSUE-113: `edge_updater` and `knowledge_propagator` session-based functions are orphaned
**Found:** 2026-06-17, during SEV-24 gossip cluster migration
**Fixed:** 2026-06-17, in SEV-24 Wave 5 — `edge_updater.py` and the full `engines/gossip/knowledge_propagator.py`
deleted; `SECRET_DISTORTION_CHANCE` moved to `gossip_config.py`.
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/edge_updater.py`, `src/npc_engine/engines/gossip/knowledge_propagator.py`

---

## [FIXED] ISSUE-056: graph_rag.py MATCH (seed) full-scan — no label filter
**Fixed:** 2026-06-19, verified already resolved in code (no separate commit needed). `graph_rag_queries.py`
`_CYPHER_EXPAND_SEEDS` uses `MATCH (seed:Event)` with a label filter and a comment explicitly closing
ISSUE-056 (DEC-093: schema has no `:Knowledge` label, so `Event|Knowledge` reduces to `:Event`).
**Found:** 2026-06-04, during SEV-39 coverage fix
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/graph/graph_rag_queries.py` — `_CYPHER_EXPAND_SEEDS` query
**Description:** The expansion Cypher did `MATCH (seed)` without a label filter, triggering a full-node scan
on every GraphRAG call. In large graphs this would be slow and risk matching unintended node types.
**Why deferred:** Fixing required knowing the correct label(s) for seed nodes, which might shift as SEV-04
migrated Cypher domains.
**To fix:** Add `(seed:Event)` label filter. (Done — present in current code.)

---

## [FIXED] ISSUE-064: cross-encoder reranker runs synchronous model inference on the event loop (dialogue path)
**Fixed:** 2026-06-19, verified already resolved in code. `context_builder._maybe_cross_encode` offloads
`cross_encoder_reranker.rerank` via `asyncio.to_thread` (mirrors the ISSUE-063 embedding-index fix), with a
docstring referencing ISSUE-064.
**Found:** 2026-06-05, during ISSUE-063 fix (same bug class, different call path)
**Severity:** P3
**Where:** `src/npc_engine/retrieval/cross_encoder_reranker.py` (sync `rerank()`), called at
`src/npc_engine/retrieval/context_builder.py`.
**Description:** `rerank()` is a synchronous CPU-bound cross-encoder `predict()` invoked during Tier B/C
context assembly; running it on the event loop blocked the single worker for the predict duration.
**Why deferred:** Out of scope for the ISSUE-063 fix; separate call path with its own sync/async chain.
**To fix:** Offload the cross-encoder `predict()` off the event loop. (Done — present in current code.)

---

## [FIXED] ISSUE-072: `gossip_distort.py` module docstring is a stale placeholder
**Fixed:** 2026-06-19, verified already resolved — `gossip_distort.py` carries a real one-line Purpose
(deterministic hash-seeded distortion), not the placeholder.
**Found:** 2026-06-06, during EXP-15 (distortion strategy registry)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/gossip/gossip_distort.py:1-8`
**Description:** Module docstring said `Purpose: (auto-detected — review)` — a stale placeholder.
**Why deferred:** Cosmetic; not blocking anything.
**To fix:** Update to a proper one-sentence description. (Done.)

---

## [FIXED] ISSUE-076: `relation_writer.py` module docstring is a stale placeholder
**Fixed:** 2026-06-19, verified already resolved — `relation_writer.py` carries a real one-line Purpose
(bounded RELATES_TO updates within an injected transaction), not the placeholder.
**Found:** 2026-06-06, during EXP-52 (reputation propagation)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/relation_writer.py:1-8`
**Description:** Module docstring said "(auto-detected — review)" — predated the mandatory docstring rule.
**Why deferred:** Cosmetic.
**To fix:** Update to a proper one-sentence module description. (Done.)

---

## [FIXED] ISSUE-106: `asyncio.iscoroutinefunction` DeprecationWarnings under Python 3.14
**Fixed:** 2026-06-19, in the issues-remediation batch — the 4 first-party sites in
`tests/unit/test_sev05_store_locking.py` now use `inspect.iscoroutinefunction`. Remaining warnings are
vendored neo4j/fastapi (third-party) and are out of scope.
**Found:** 2026-06-13, during /full-review (L4/L9)
**Severity:** P3 (nice-to-fix)
**Where:** sev05 store tests + vendored neo4j/fastapi
**Description:** ~1.8k `asyncio.iscoroutinefunction` DeprecationWarnings per run, mostly from vendored
deps; 4/run originated in the sev05 store tests.
**Why deferred:** Third-party-dominated; cosmetic.
**To fix:** Replace the first-party uses with `inspect.iscoroutinefunction`. (Done.)

---

## [FIXED] ISSUE-109: `'knows'` knowledge-state string literal remains in api_seeder after SEV-04
**Fixed:** 2026-06-19, in the issues-remediation batch — added a local `_KNOWLEDGE_STATE_KNOWS = "knows"`
constant in `api_seeder.py` and referenced it (deliberate duplication; the seeder cannot import application
code). The previously-listed `awareness_seeder.py` site no longer exists (module removed).
**Found:** 2026-06-14, during /fix-parallel SEV-04 (W4 adjacent finding)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/data/api_seeder.py:176`
**Description:** The SEV-04 `KnowledgeState` Literal centralizes `"knows"`/`"rumor"`, but `api_seeder` is
forbidden from importing application code, so it embedded the raw `"knows"` literal.
**Why deferred:** Constrained context; lower severity than live engine paths.
**To fix:** Add a local seeder-side constant and reference it. (Done.)

---

## [FIXED] ISSUE-103: 135 module docstrings carry stale `Purpose: (auto-detected — review)` placeholder
**Found:** 2026-06-13, during /full-review (L5)
**Severity:** P3 (nice-to-fix)
**Where:** 135 `.py` files across `src/`
**Description:** Module docstrings still carry the auto-generated `Purpose: (auto-detected — review)`
placeholder. ISSUE-072/076 each tracked a single file; the real population is 135. `check-docstrings`
passes because a docstring is present — the placeholder text is not validated.
**Why deferred:** Large mechanical sweep; no runtime impact; out of scope of the Fix-now feature debt.
**To fix:** Replace placeholders with real one-line Purpose statements (consider a lint that rejects the placeholder text).
**Fixed:** 2026-06-19, in commit 8434391 (REM-W1b). 113 files swept; guard added to `docstring_audit.py`. Grep returns zero.

---

## [FIXED] ISSUE-115: ~110 module docstrings still carry the `(auto-detected — review)` placeholder Purpose line
**Found:** 2026-06-18, during the market-deployment documentation refresh
**Severity:** P3 (nice-to-fix)
**Where:** ~113 `.py` files across `src/npc_engine/` (top areas: graph 22, engines 16, type_registry 13,
retrieval 13, schema 11, api 11). Find with `grep -rl "auto-detected — review" src/npc_engine --include=*.py`.
**Description:** Many module-level docstrings have `Purpose: (auto-detected — review)` placeholders left by a
bulk docstring-scaffolding pass. The CLAUDE.md documentation rule requires a real one-sentence Purpose on every
module. This refresh fixed the 9 engine package `__init__.py` files + `scheduler/tick_scheduler.py`; the
module-level files remain.
**Why deferred:** Fixing all ~113 accurately means reading each module to write a correct Purpose — a separate,
sizeable sweep beyond the agreed scope of this market-facing docs task (ENGINES.md, API.md, ARCHITECTURE.md,
package docstrings).
**To fix:** Sweep area-by-area (start with `graph/` and `engines/`), replacing each placeholder Purpose with an
accurate one-line description; verify with the grep above returning zero matches.
**Fixed:** 2026-06-19, in commit 8434391 (REM-W1b). All 113 files swept; grep returns zero.

---

## [FIXED] ISSUE-116: test_seed_chain_quests skip-existing tests assert _seed_edge never called
**Found:** 2026-06-18, during SHIP-02 (OpenAI-compatible LLM adapter) — surfaced by `make check`
**Severity:** P3 (nice-to-fix)
**Where:** `tests/unit/test_seed_chain_quests.py` (`test_seed_chain_quests_skips_existing_nodes`, `test_seed_source_chain_quests_skips_existing_nodes`)
**Description:** Both tests stub `_seed_node` to return `"skipped"` and then assert `mock_edge.assert_not_called()`, but `_seed_chain_quests` always calls `_seed_edge` (which upserts the latest props regardless of node existence). Same stale-expectation family as the FIXED ISSUE-040 (`test_seed.py`). Pre-existing: both fail on a clean tree (verified via `git stash`); unrelated to SHIP-02.
**Why deferred:** Not the current task (SHIP-02 LLM adapter); demo-side seeding, no functional regression, does not gate the engine path.
**To fix:** Update the two assertions to expect the actual `_seed_edge` upsert count (mirror ISSUE-040's resolution), or add skip-if-exists edge logic to `_seed_chain_quests` and keep the assertions.
**Fixed:** 2026-06-19, in commit 6d9cfad (REM-W2). Changed both `mock_edge.assert_not_called()` to `assert mock_edge.call_count == len(...)`.

---

## [FIXED] ISSUE-101: `schedule_queries.py` scheduler reads 24% covered
**Found:** 2026-06-13, during /full-review (L4)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/schedule_queries.py`
**Description:** Scheduler read queries are 24% covered; most read paths untested.
**Why deferred:** Below the HIGH/scheme-feature priority of this review's Fix-now backlog.
**To fix:** Add unit/integration tests for the scheduler read queries; bring coverage toward module norm.
**Fixed:** 2026-06-19, in commit 34a3925 (REM-W2). 13 new unit tests in `tests/unit/test_schedule_queries.py` covering all 4 public functions (happy path, not-found, bad-JSON, multi-match).

---

## [FIXED] ISSUE-102: Intrigue board panel (G2.2) tests are crash-safety only
**Found:** 2026-06-13, during /full-review (L4)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/ui/` intrigue/scheme board panel tests
**Description:** The G2.2 scheme board panel tests assert the widget does not crash on render but make no behavioral assertions (does it show the right schemes/steps for the active NPC?).
**Why deferred:** Demo panel; poller is behaviorally tested (6 tests). Cosmetic risk only.
**To fix:** Add assertions on panel content given a known schemes payload.
**Fixed:** 2026-06-19, in commit 13fc6ea (REM-W2). Added `_TrackingFont` + 9-test `TestDrawBehavioral` class asserting header, no-data placeholder, discovered/hidden badges, goal texts, step summaries, and marker characters.

---

## [FIXED] ISSUE-110: `evals/runner.py` HTTP loop (`_run_case`/`main`) has no unit coverage
**Found:** 2026-06-14, during /fix-next SEV-07
**Severity:** P3 (nice-to-fix)
**Where:** `evals/runner.py` (`_run_case`, `_setup_reputation`, `main`)
**Description:** SEV-07 added `--cov=runner` to the gate; runner sits at 24%. Its guard/guarantee LOGIC is unit-tested (`test_eval_runner_guards.py`), but the HTTP eval loop, reputation setup, and the `main()` `guarantee_demonstrated` gate are exercised only by the live `make eval-llm-demo`, not unit tests.
**Why deferred:** Unit-testing the loop needs httpx-client mocking + case fixtures (sizeable); out of SEV-07's hygiene scope, and total coverage stays ≥80%.
**To fix:** Add unit tests mocking `httpx.Client` for `_run_case` happy/error paths and a `main()` test asserting exit code flips on `guarantee_demonstrated=False`.
**Fixed:** 2026-06-19, in commit 3edd7f3 (REM-W2). 9 new unit tests in `tests/unit/test_eval_runner_loop.py`: `_run_case` (no-input skip, NPC-404 skip, request error, success, keyword_none fail) + `main()` (unreachable → 2, no cases → 2, guarantee-not-demonstrated → 1, all-pass → 0).

---

## [FIXED] ISSUE-111: `scenario_territorial_war.py::test_military_engine_tick_returns_skipped` is stale
**Found:** 2026-06-16, during /fix-next SEV-24 (military slice)
**Severity:** P3 (nice-to-fix)
**Where:** `e2e/scenarios/scenario_territorial_war.py` (`test_military_engine_tick_returns_skipped`)
**Description:** The test constructs `MilitaryEngine()` and asserts `run_tick` returns `skipped=True` — the pre-S6.5 no-op-stub contract. Since S6.5 the engine returns `battles_resolved`/`factions_yielded`, so the assertion was already wrong; after the SEV-24 migration the constructor also now requires a `military_repo` port, so the call fails at construction. Not collected by `make check` (it runs `tests/` only; scenarios need `--scenarios-only`), so it does not gate.
**Why deferred:** Pre-existing stale test outside the SEV-24 slice's verification path; fixing it is e2e-test maintenance, not part of the repository-facade migration.
**To fix:** Rewrite the test to inject a mock `MilitaryGraphPort` and assert the real `battles_resolved`/`factions_yielded` contract (mirror `tests/unit/test_military_engine.py`).
**Fixed:** 2026-06-19, in commit 21145f3 (REM-W2). Rewrote test to inject `AsyncMock()` repo, patch services, assert `battles_resolved`/`factions_yielded`; passes under `--scenarios-only`.

---

## [FIXED] ISSUE-095: dialogue_ws lazily imports get_proactive_queue inside the handler
**Found:** 2026-06-12, during F1.2
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/routes/dialogue_ws.py` (`dialogue_ws` body)
**Description:** `get_proactive_queue` is imported inside the WS handler function to avoid a potential
import cycle at module load.
**Why deferred:** Works correctly; promoting to a top-level import is cosmetic and needs the
api/dependencies_engines import graph confirmed acyclic first.
**To fix:** Verify no circular import, then hoist the import to module top-level.
**Fixed:** 2026-06-19, in commit 5fbe254 (REM-W3)

---

## [FIXED] ISSUE-105: `dependencies_engines.py` exceeds its DEC-076 400-line growth cap
**Found:** 2026-06-13, during /full-review (L2)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/dependencies_engines.py` (~513 lines)
**Description:** DEC-076 (2026-06-09) capped the file at 400 lines pending a per-engine submodule pattern;
scheme + director + memory + goal factories pushed it past without a new DECISIONS entry.
**Why deferred:** Composition-root refactor; not blocking. Relates to DEC-115 (second composition root).
**To fix:** Extract advanced engine factories into a submodule, or add a DECISIONS entry re-baselining the cap.
**Progress:** 2026-06-15 (SEV-17) — per-engine submodule pattern established by splitting the *sibling* root
`dependencies_advanced.py` into `dependencies_advanced/{politics,social,progression}.py`. `dependencies_engines.py`
itself is still 512 lines (DEC-076-grandfathered); apply the same split or re-baseline to close this. STILL OPEN.
**Fixed:** 2026-06-19, in commit 806ca13 (REM-W3) — split into dependencies_engines/{core,quest,tick_slots}/__init__.

---

## [FIXED] ISSUE-114: `quest_reward_repository.py` has 3 functions > 40 lines (R006 violations)
**Found:** 2026-06-17, during SEV-24 Wave 5 check-rules run
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/graph/repositories/quest_reward_repository.py` — `apply_rewards_atomic`, `_apply_in_tx`, `_collect_delivery_in_tx`
**Description:** Three transaction-helper methods exceed the 40-line hard limit (R006). They were introduced
in the quest cluster wave without triggering the baseline, and Wave 5 now exposes them. Splitting is
artificial: all three are tightly coupled phases of one Neo4j atomic transaction.
**Why deferred:** Refactoring graph-layer transaction helpers is out of scope for Wave 5 (session cleanup).
**To fix:** Extract `_grant_item_rewards_in_tx` and `_grant_currency_reward_in_tx` helpers from `_apply_in_tx`;
split `_collect_delivery_in_tx` at the possession-check vs transfer boundary.
**Fixed:** 2026-06-19, in commit 58f6e45 (REM-W3)

---

## [FIXED] ISSUE-104: OCP residuals — emotion/TTS factory, mood-label table, llm `__init__` registration, scheme step kind
**Found:** 2026-06-13, during /full-review (L7)
**Severity:** P3 (nice-to-fix)
**Where:** `engines/.../emotion_model_factory.py`, `dependencies.py` (TTS), `engines/.../mood_contagion_engine.py`, `engines/llm/__init__.py`, `engines/scheming/covert_event_factory.py`
**Description:** Several extension axes remain closed: emotion-model factory is a 2-branch if + Literal;
TTS backend selection is an if/elif in the composition root with no registry; mood label→VAD table is a
hardcoded dict duplicated across two modules; new LLM backends require editing `llm/__init__.py`; scheme
step kind is a free string with no enum/registry. The big OCP seams (distortion registry, location_writer,
LLM backend validator, EmotionModelProtocol) DID land — these are the residuals.
**Why deferred:** Roadmap pre-work, not blocking; each is added when its expansion axis is actually exercised.
**To fix:** Mirror the LLM `register_backend()` registry pattern for emotion + TTS; extract the mood table
to one module; introduce a `SchemeStepKind`.
**Fixed:** 2026-06-19, in dd91e55 (REM-W4).

---

---

## [FIXED] ISSUE-096: trait-modulated emotion uses global demo-default traits, not per-NPC traits
**Found:** 2026-06-12, during F1.3 (config-selectable emotion model)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/emotion/emotion_model_factory.py` (`_DEMO_DEFAULT_TRAITS`)
**Description:** When `EMOTION_MODEL="trait_modulated"`, `EmotionUpdater` holds ONE model seeded with
global demo-default trait multipliers, so every NPC is modulated identically. `TraitModulatedEmotionModel`
is designed for per-NPC traits (its docstring: "caller responsible for fetching traits from the graph").
**Why deferred:** F1.3 scope is the config selector + composition-root injection; per-NPC trait fetch is
its own slice (needs a graph traits reader + an EmotionUpdater call-signature change to thread npc traits).
**To fix:** Add a per-NPC traits reader; have `EmotionUpdater` build/parameterize the model per `npc_id`
(or pass traits into `apply_shock`/`apply_mood_hint`), removing the global default.
**Fixed:** 2026-06-19, REM-W5 (commit 55f13e2). Added `TraitReadPort` protocol + optional `trait_reader`
param; `EmotionUpdater._get_model_for(npc_id)` builds per-call `TraitModulatedEmotionModel` (DEC-137). 3 tests.

---

---

## [FIXED] ISSUE-097: director plateau-tick signal is always 0 (no relationship-plateau tracker)
**Found:** 2026-06-12, during F1.5 (director → scheduler)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/director/director_tick.py` (`_decide_for_pair`)
**Description:** `DirectorTick` always passes `relationship_plateau_ticks=0` to `decide()`, so the
`relationship_catalyst` plateau beat can never fire. Only the idle (`re_engage_idle`) and HOSTILE
(`tension_escalation`) paths are live.
**Why deferred:** F1.5 scope is the decide→emit wiring; tracking ticks-since-Standing-band-changed
needs a small per-pair tracker/store, its own slice.
**To fix:** Track consecutive ticks since the pair's Standing band last changed (a per-pair counter,
e.g. on the RELATES_TO edge or an in-memory store) and feed it into `decide()`.
**Fixed:** 2026-06-19, REM-W5. Added `_plateau_tracker: dict[tuple[str,str], tuple[Standing,int]]` to
`DirectorTick.__init__`; `_read_plateau`/`_update_plateau` module helpers; `_decide_for_pair` now returns
`(decision, standing)` tuple (DEC-135). 2 regression tests.

---

---

## [FIXED] ISSUE-108: `scheming_engine.advance_step` creates a SCHEME_STEP edge with no paired Event
**Found:** 2026-06-14, during /fix-parallel SEV-01 (W1 adjacent finding)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/scheming/scheming_engine.py` (`advance_step` call to `add_scheme_step(session=...)`)
**Description:** SEV-01 made the AUTO-advance path (`scheme_advance_tick`) mint the Event and link the
SCHEME_STEP atomically in one transaction. The manual `advance_step` path still calls
`add_scheme_step(session=...)` standalone, creating a SCHEME_STEP edge with no paired Event node — a
possible orphan-edge / inconsistent-scheme concern on that separate call site.
**Why deferred:** Different call site and semantics from SEV-01's auto-advance fix (out of that task's scope).
**To fix:** Decide whether the manual step path must also mint/refer to an Event; if so, route it through an
atomic `run_in_tx` like the auto-advance path (pass `tx=`).
**Fixed:** 2026-06-19, REM-W5. `SchemeStepInput` gains `npc_id/goal/location_id`; `SchemingEngine` accepts
optional `registry: TypeRegistry`; `advance_step` calls `_build_covert_event` + `emit_scheme_step_atomic`
atomically (DEC-134). 2 tests; `add_scheme_step` path deprecated.

---

## [FIXED] ISSUE-094: proactive trigger_router has no `need`/`event` candidate producers
**Found:** 2026-06-12, during F1.2 (proactive WS delivery wiring)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/proactive_dialogue/proactive_tick_adapter.py` (`_collect_candidates`)
**Description:** `trigger_router.select_trigger` is now wired, but only the `memory` source emits
`TriggerCandidate`s. `TriggerSource` also defines `need` and `event` — those producers don't exist,
so routing is effectively single-source today.
**Why deferred:** Out of F1.2 scope; building need/event producers is its own slice and the router is a
clean seam for them. Deferring avoided scope creep in the overnight loop.
**To fix:** Add need-based (IntentFormationEngine) and event-based candidate producers that append
`TriggerCandidate(source="need"|"event", ...)` in `_collect_candidates`; the router already ranks them.
**Fixed:** 2026-06-19, REM-W5 (commit 8799e5d). Added `_collect_need_candidates` / `_collect_event_candidates`
helpers + `_merge_intent_candidates`; `IntentGraphPort` optional constructor injection (DEC-136). 3 new tests.

---

## [FIXED] ISSUE-112: EventHandler high-severity witness recording is dead code
**Found:** 2026-06-16, during /fix-next SEV-24 (events slice)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/events/event_handler.py::_record_witnesses`
**Description:** The post-emit witness block reads `actor_id = raw_props.get("src_character_id", "") or None`,
but `_build_event` never sets `src_character_id`, so `actor_id` is always `None` and the WITNESSED edges are
never recorded. Only the `get_characters_at_location` read still fires (a wasted DB round-trip on every
severity >= HIGH_SEVERITY_THRESHOLD event). Behaviour was preserved verbatim through the SEV-24 migration.
**Why deferred:** Wiring an actor source into event templates is a feature change outside the repository-facade
slice; preserving exact behaviour was the migration's contract.
**To fix:** Either add `src_character_id` to `EventTemplate`/`_build_event` so witnessing actually fires, or
drop the dead block (and its read) if event-actor witnessing is not a desired feature.
**Fixed:** 2026-06-19, REM-W5. Added optional `src_character_id: str | None` to `EventTemplate`; `_build_event`
propagates to `raw_props` when non-None, activating `_record_witnesses` (DEC-133). 2 regression tests.

---

## [FIXED] ISSUE-071: Dialogue engine not grounded in live engine state — NPC contradicts trade/quest reality
**Found:** 2026-06-05, during trade-engine bug fix (Mira hardcoded item)
**Severity:** P2 (annoying — breaks immersion, confuses players)
**Where:** `src/npc_engine/engines/dialogue/` + `src/npc_engine/retrieval/context_builder.py`
**Fixed:** 2026-06-19, in REM-W6 (DEC-138)
**Description:** The dialogue engine generates NPC responses from graph context alone; it has no awareness of live engine state from other engines (trade, quest, economy). Example: after the trade engine determines that Mira has no inventory and cannot trade, Mira's LLM-generated dialogue still says "I've got a couple of things that might interest you" — because the prompt context only includes graph facts, not the trade engine's real-time evaluation. The same class of bug can occur with quest state (NPC says "bring me the item" after quest is already complete) and emotion state.
**Why deferred:** Requires a design decision on how to pass engine-resolved facts into the dialogue context assembly pipeline without creating layer violations (dialogue engine calling trade engine, or context_builder calling both). Involves a new "system state" tier in the prompt context.
**To fix:** Introduce a `SystemStateContext` bag — a dict of engine-resolved facts assembled at the API route layer before the dialogue call — and inject it as a new Tier 0 block in `context_builder.py`. The route handler (`api/routes/dialogue.py`) would resolve trade/quest state for the current NPC and player, then pass it into the context builder. This keeps layer boundaries clean (engines do not call each other; the route layer orchestrates).

---

## [FIXED] ISSUE-107: No cross-session e2e test for persistent memory recall
**Found:** 2026-06-13, during /full-review (L6)
**Severity:** P2 (annoying)
**Where:** `e2e/` / demo scenarios
**Fixed:** 2026-06-19, in REM-W6 (DEC-139)
**Description:** The persistent-memory pitch has no e2e scenario spanning two dialogue sessions across a
memory consolidation (teach an NPC something in session 1, confirm recall in session 2). Unit tests cover
the pieces; the headline capability has no end-to-end proof.
**Why deferred:** Needs a human decision on WHICH dialogue-response field to assert on for "NPC recalls the
consolidated memory" (see review §4 / L6 evidence).
**To fix:** Pick the assertion field; write a two-session e2e scenario; wire into the e2e battery.

---

## [FIXED] ISSUE-098: composition root builds a fresh PlayerLocationReader per factory
**Found:** 2026-06-12, during F1.5
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/dependencies_engines/tick_slots.py` (proactive/intent/player_model/director factories)
**Fixed:** 2026-06-22, in REM-W (already implemented during the dependencies_engines package split; regression test `tests/unit/test_dependencies_engines_singletons.py` added to lock the invariant).
**Description:** Four `@lru_cache` factories each construct their own `PlayerLocationReader()`. It is
stateless so this is functionally fine, but a shared `get_player_location_reader()` singleton would be
more consistent with the rest of the composition root.
**Why deferred:** Cosmetic; not blocking. Surfaced by the F1.5 worker.
**To fix:** Add `@lru_cache get_player_location_reader()` and reuse it across the four factories.
**Resolution:** `get_player_location_reader()` is an `@lru_cache` singleton in `tick_slots.py:60`; the four
factories (`get_proactive_dialogue_engine`, `get_intent_formation_engine`, `get_player_model_tick`,
`get_director_tick`) all inject its result. Added a regression test asserting (a) the getter is a cached
singleton and (b) all four adapters share the same `_location_reader` instance.

---

## [FIXED] ISSUE-100: `make demo-run ARGS=--dry-run` fails partway (~ACT 8)
**Found:** 2026-06-12, during G3.1 (verifying the intrigue arc in the demo sequence)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/run.py` `main()` / `demo_game/encoding_utils.py`
**Fixed:** 2026-06-22, in REM-W7 (wired the existing `ensure_utf8_stdout()` into `run.py:main()`).
**Description:** `make demo-run ARGS=--dry-run` exited with an error around the ACT-8/determinism region.
**Diagnosis correction:** The original "missing `if runner.dry_run` guard" hypothesis was wrong — that
guard already exists and is correct (`determinism_beat.py:69`). The real cause is a `UnicodeEncodeError`:
the ACT-8 cue prints a `→` (U+2192) glyph, and on a Windows cp1252 console `print()` cannot encode it.
The cue prints *before* (and independent of) the dry_run guard, so a **live** Windows run crashes at the
same point. Several demo scene files contain `→`/`×`/em-dash glyphs, so per-string ASCII edits would be
whack-a-mole.
**Resolution:** `demo_game/encoding_utils.ensure_utf8_stdout()` already existed, was tested and idempotent,
and its docstring already named `demo_game.run` as a user — the call had simply never been wired in. Added
`ensure_utf8_stdout()` as the first statement of `main()` (1 import + 1 call), reconfiguring stdout/stderr
to UTF-8 for the whole run. Regression test `demo_game/tests/test_run_dry_run_encoding.py` drives the full
dry-run sequence past ACT 8 on a cp1252-backed stdout and asserts it completes.

---

## [FIXED] ISSUE-053: grandfathered CLAUDE.md rule violations (rules baseline backlog)
**Found:** 2026-06-03, during the multi-agent codebase review
**Severity:** P2 (annoying)
**Where:** `scripts/rules_baseline.txt` (enumerated); spans `src/` and `demo_game/`.
**Fixed:** 2026-06-22, in REM-W8 (DEC-140). Scope reset + high-value clear; remainder documented as waived.
**Description:** The `make check-rules` gate records existing rule violations as a baseline so only NEW ones
fail CI. The baseline was the debt backlog; the original brief said "done when empty."
**Resolution:** The originally-named clusters — prints (R002), swallows (R003), `raise Exception` (R004),
Cypher-leak (R005), demo-imports (R007) — are **fully cleared** (zero entries). The remaining baseline was
only R001 (file > 300 lines) and R006 (function > 40 lines), 137 entries. Per DEC-140: (1) "done = empty
baseline" is unreachable without violating prior waivers (DEC-016/033/034/042/…) and conflicts with the
smallest-diff / no-new-abstractions rule; (2) redefined done = every baseline entry maps to a documented
waiver, removing entries only when a real complexity-reducing fix lands. High-value clear taken: consolidated
the 4-way-duplicated output-token metric in `llm_client.py` into `_emit_tokens_out` (DRY), clearing
`stream_text` (baseline 137 → 136). The R006 remainder (105 cohesive, docstring-/formatting-inflated functions)
and the R001 remainder (demo_game S21.6 cluster + the src files) are catalogued and waived under DEC-140;
top-of-file justifying comments were added to the previously-undocumented files (`api_seeder.py`,
`intent_queries.py`, `quest_lifecycle_engine.py`, `prompt_builder.py`, `gossip_handler.py`).
**To fix (historical):** Work the SEV briefs; shrink `scripts/rules_baseline.txt`; done when empty. (Superseded
by DEC-140's done definition.)

---

## [FIXED] ISSUE-117: frozen domain exceptions reject __traceback__/__cause__ → opaque HTTP 500, broken LLM fallback
**Found:** 2026-06-22, during live demo verification (make demo-village / demo-tavern)
**Severity:** P1 (blocking — defeats the engine boundary fallback contract; turns recoverable LLM errors into 500s)
**Where:** `src/npc_engine/utils/errors.py` (StructuredNPCSystemError frozen-dataclass subclasses)
**Fixed:** 2026-06-22, in fix/frozen-exception-traceback (regression test `tests/unit/test_errors_machinery.py`).
**Description:** Domain exceptions are `@dataclass(frozen=True)`. When Python's exception machinery (or
asyncio/concurrent.futures, when an exception crosses an executor/await boundary — exactly the LLM call path)
assigns `__traceback__`/`__cause__`/`__context__` *explicitly*, the frozen `__setattr__` raised
`FrozenInstanceError: cannot assign to field '__traceback__'`. This second error propagated unhandled →
HTTP 500, instead of the intended "LLM timeout/error → serve canned fallback" degradation. It also MASKED the
real underlying error (see ISSUE-118). The existing `__init_subclass__` workaround never applied: it ran
before `@dataclass` installed the frozen `__setattr__`, so `cls.__dict__.get("__setattr__")` was always None.
**Resolution:** Replaced the broken `__init_subclass__` with `_enable_exception_machinery()`, invoked at module
import (after the decorators run). It wraps each frozen subclass's `__setattr__` so the machinery attributes go
through `object.__setattr__` while declared fields stay immutable. Verified: regression test + container
hot-patch (machinery assignment now succeeds; the masked RelationEdgeNotFoundError is now surfaced cleanly).

---

## [FIXED] ISSUE-118: live first-contact dialogue 500s when the player Character node is missing
**Found:** 2026-06-22, during live demo verification (unmasked by the ISSUE-117 fix)
**Severity:** P2 (annoying — broke `make demo-village`/`demo-tavern` live; latent robustness gap for any client)
**Where:** `src/npc_engine/graph/graph_writer.py::ensure_relation_edge`;
`src/npc_engine/api/routes/dialogue.py`.
**Fixed:** 2026-06-22, in fix/issue-118-first-contact (engine-hardening option per the user).
**Description:** The village/tavern scenarios send `player_id="player"`, but those eval worlds never seed a
`player` Character node (the demo world seeds `player_demo`, which works). On first contact,
`ensure_relation_edge`'s `MATCH (a),(b) MERGE ...` silently no-opped when an endpoint node was absent, so the
re-read raised `RelationEdgeNotFoundError(src_id=vw_guard, dst_id=player)` → unhandled → HTTP 500.
**Resolution (harden the engine):** `ensure_relation_edge` now detects the no-match (MERGE returns no row),
runs a diagnostic query to name the missing Character id(s), and raises a typed `NodeNotFoundError` instead of
silently no-opping. The dialogue route catches `NodeNotFoundError` and returns a redacted HTTP 422
(`CHARACTER_NOT_FOUND`, "Character not found.") — the internal node id is logged server-side only (L8-02),
never echoed. Regression test `tests/unit/test_first_contact_missing_node.py` (ensure_relation_edge raises +
route returns 422). `make check` green (2534). Note: the village/tavern *scenarios* still reference a
non-existent `player` node, so those demos won't complete until a `player` node is seeded — that is a separate
eval-world data gap, intentionally not fixed here (the chosen path was engine hardening, which is what matters
for the Unreal client).

---

## [FIXED] ISSUE-121: anti_hallucination eval runner depends on incomplete untracked WIP (preconditions.py)
**Found:** 2026-06-23, during REORG-PR6 — pre-existing at base c1c7607.
**Fixed:** 2026-06-23, in EVAL-B2.
**Severity:** P2 (annoying — 8 failing unit tests; not a PR-6 regression)
**Where:** `tests/unit/test_anti_hallucination_runner.py`, `evals/anti_hallucination_runner.py:22,392`,
untracked WIP `evals/preconditions.py`, `tests/unit/test_preconditions.py`, `tests/unit/test_runner_player_node.py`
**Description:** A prior session added `import preconditions` + `preconditions.reset_world(...)` to the
tracked `anti_hallucination_runner.py`, depending on an untracked, incomplete `evals/preconditions.py`.
`reset_world` raises `PreconditionError: Unmet world_condition world_state:age_of_peace` under the test
mocks, failing 8 `test_anti_hallucination_runner.py` cases. Confirmed identical failures at base
c1c7607 → pre-existing, unrelated to the graph reorg.
**Why deferred:** Out of REORG-PR6 scope; it is someone else's unfinished WIP.
**Fix:** Added `_make_patch_response()` helper returning status_code=200 to all 8 `run()` tests in
`tests/unit/engines/test_anti_hallucination_runner.py`; added `test_run_calls_reset_world_once_before_case_loop`
regression guard (EVAL-B2.2). 2573 tests pass, 29 skipped.

---

## [FIXED] ISSUE-119: anti-hallucination eval is unreliable — brittle refusal detection + no world-state reset
**Found:** 2026-06-22, during the eval debug session (after fixing the runner's auth so it executes at all)
**Fixed:** 2026-06-23, in EVAL-B2 (world-state reset, commit 252a5fc) + EVAL-B3 (LLM-judge refusal scorer, commit cff420b + EVAL-B3.2 commit)
**Severity:** P2 (the headline "0 hallucinations" guarantee cannot be trusted until the scorer is fixed)
**Where:** `evals/anti_hallucination_runner.py` (`_is_refusal` / `_REFUSAL_KEYWORDS`; no world_state reset)
**Description:** `_is_refusal()` was a fixed keyword match that missed common valid refusal phrasings
("I don't have any information", "ask someone at the barracks", "my ears aren't tuned to such matters"),
causing legitimate refusals to score as hallucinations. Secondary: no world-state reset let a prior run
leaving epoch="war" contaminate the age_of_peace baseline (18 hallucinations with war → 15 after reset).
**To fix:** (1) Replace `_is_refusal` keyword matching with the LLM judge — done in EVAL-B3 via
`matchers.judge_refusal()` + `prompts/eval/refusal_judge.yaml`;
(2) reset world_state at run start — done in EVAL-B2 via `preconditions.reset_world()`;
(3) re-measure the true guard number (EVAL-FINAL, requires live stack).

---

## [FIXED] ISSUE-120: Gate red from PR-2/PR-3 reorg debt (lint F401 + check-rules baseline drift)
**Found:** 2026-06-23, during REORG-PR6 (folder reorg) — pre-existing at base c1c7607.
**Severity:** P2 (annoying — `make check` is red independent of PR-6)
**Where:** `src/npc_engine/retrieval/*/__init__.py` (facade re-exports), `scripts/rules_baseline.txt`
**Description:** `make lint` reports 21 ruff F401 errors ("re-exported but missing from `__all__`")
in the retrieval facade `__init__.py` files added by PR-3. Separately, `make check-rules` reports
30 R001/R006 violations because PR-3 (and PR-2) moved files without path-updating their
grandfathered entries in `rules_baseline.txt`, so the old paths read as "fixed" and the new paths
read as NEW violations. `make check-harness` H1 fails because the red lint has no logged ticket.
**Why deferred:** Out of REORG-PR6 scope (graph/ only). These are PR-2/PR-3 artifacts; PR-6 added
ZERO new lint or check-rules violations (verified: base set == head set). Fixing touches retrieval
facades + baseline, which belong to those PRs.
**To fix:** Add re-exported names to each retrieval facade `__all__` (or `# noqa: F401`); path-rewrite
the 30 stale retrieval entries in `rules_baseline.txt` (same fix applied to graph/ in PR-6), then
`make check-rules` and `make lint` go green.
**Fixed:** 2026-06-24, in 3950f90 (fix(gate): close ISSUE-120)

---

## [FIXED] ISSUE-125: `OLLAMA_MODEL` env var is documented in both `.env.example` files but read by no code
**Found:** 2026-07-31, during the DEC-149 qwen2.5:7b migration / 14b doc sweep
**Severity:** P3 (nice-to-fix)
**Where:** `.env.example:28`, `src/npc_engine/.env.example:29`
**Description:** Both `.env.example` files publish `OLLAMA_MODEL` as if it selected the generation model.
`grep -rn OLLAMA_MODEL --include=*.py` returns **zero** hits outside `.venv` — nothing reads it. Worse, its
value was `mixtral:8x7b`, i.e. the *judge* model (DEC-143), so anyone setting it believed they were
configuring generation, got no effect, and was pointed at the wrong model. Actual engine model selection is
per-engine `src/npc_engine/engines/*/llm_config.yaml`.
**Why deferred:** Deleting a published config key is a config-surface change, and DEC-149's scope was the
model migration plus the stale-`14b` sweep. The immediate trap is defused: the value now reads `qwen2.5:7b`
and both files carry a `NOTE:` that the key is unread and names the real source of truth.
**To fix:** Either delete the key from both `.env.example` files, or wire it as a genuine override in
`config.py` with a documented precedence order against `llm_config.yaml`. Decide which; do not leave it
half-live. A test asserting every key in `.env.example` is referenced somewhere in `src/` would prevent
recurrence.
**Fixed:** 2026-07-31, in DEC-150 — both keys deleted from both `.env.example` files.
**Correction to this entry as originally written:** it under-described the problem in two ways.
(1) It is **two** dead keys, not one — `LLM_BACKEND` is equally dead, and a scan of all 55 keys
showed exactly these two absent from `config.py` (53 are live). (2) It framed "delete vs wire up"
as an open question; it was not. `ISSUE-003` (fixed 2026-05-06) had already removed **both** from
`config.py` deliberately, so the `.env.example` entries were leftovers from an incomplete removal
and deletion was the already-accepted end state. The entry also missed the collateral:
`CONTRIBUTING.md` instructed contributors to set `LLM_BACKEND=mock` to run without an LLM, which
has been inert since ISSUE-003 — fixed in DEC-150 by documenting `llm.backend: mock` in the five
engine YAMLs instead.
**Not adopted:** the suggested "every `.env.example` key is referenced in `src/`" guard test was
considered and not built — deletion resolves the present rot, and the guard was judged not worth
its false-positive surface now. Reconsider if a third orphan key appears.

## [FIXED] ISSUE-123: `eval-judge` reports double the guard turns of `make eval` — the two headlines are not comparable
**Found:** 2026-07-31, during eval-program planning (adversarial review of `npc_system_eval_plan_idea`)
**Severity:** P2 (annoying — silently inflates the published anti-hallucination denominator)
**Where:** `evals/judge_runner.py:81` (`_to_result_dict`), consumed by `evals/summary.py:93` (`_is_guard_case`)
**Description:** `_to_result_dict` sets `case_id = judged.record_id`, which has the form
`<case_id>:<judge_kind>:<index>` (e.g. `case_adv_false_premise_peace:tone_judge:0`). `summary._is_guard_case`
matches on the `case_adv_`/`case_neg_` prefix, so the prefix survives and guard detection still works — but
each guard case emits **two** records under the current guard injection (`runner._guard_expectations` appends
a `tone_judge` **and**, for every demo-world guard case, an `affirms_judge`; all 37 guard cases are
`requires_world: demo`). Result: `make eval-judge` reports `guard_turns = 74` where `make eval` reports
`guard_turns = 37` for the identical run. The published headline string
("N lore hallucinations across M adversarial turns") therefore differs between the two paths purely because
of record fan-out, not because anything about the engine differs. Any figure quoted from `eval-judge` today
overstates the adversarial-turn count by ~2×.
**Why deferred:** Not the planning session's task (planning + review only, zero implementation). It is
already scheduled as **EVAL-P6.2** in the `EVAL-P0..P7` program, which is the first step that can fix it
without also needing the deterministic-matcher coverage gap closed (EVAL-P6.1).
**To fix:** In `judge_runner`, group `JudgedRecord`s back to their originating `case_id` (strip the
`:<judge_kind>:<index>` suffix) before handing them to `summary.summarize`, so one case contributes one guard
turn regardless of how many expectations it carries. Regression test:
`tests/unit/test_judge_runner.py::test_guard_turn_count_matches_case_count_not_record_count` — a fixture of
37 guard cases × 2 records must report 37 guard turns. Cross-check the resulting headline against a
`make eval` run over the same seeded worlds; the two strings must agree.
**Fixed:** 2026-08-07, in EVAL-P6.2 — `judge_case_grouping.group_by_case` (split out of `judge_runner.py` to
respect the 300-line file cap) groups `JudgedRecord`s by `(case_id, repetition)` — not `case_id` alone, so a
future k>1 run (EVAL-P6.4) still counts each repetition as its own turn — before handing merged result dicts
to `summary.summarize`. Regression test
`tests/unit/test_judge_runner.py::test_guard_turn_count_matches_case_count_not_record_count` passes: a
fixture of 37 guard cases × 2 records now reports 37 guard turns. `_write_judged_jsonl`'s per-record JSONL
output is unchanged — only the summary/report path was double-counting.

## [FIXED] ISSUE-133: calibration confusion matrix has no scorer axis — `make eval-calibrate` cannot calibrate a scorer
**Found:** 2026-08-07, while planning EVAL-P5 adjudication
**Severity:** P1 (blocking — invalidates the phase's stated goal, and wastes 4–6 h of maintainer time if
adjudication starts before it is fixed)
**Where:** `evals/calibration.py:73-88` (`confusion_counts`), `:115-149` (`cohens_kappa`), `:261` (the
printed header), `evals/calibration_records.py:50-57` (`CalibrationLabel` fields).
**Description:** EVAL-P5's goal is "every scorer measured separately as a full confusion matrix plus
Cohen's κ". As built, both axes of the matrix are `pre_label` (the reference labeller) and
`human_verdict` (the maintainer) — the scorer's own verdict is never compared to anything.
`CalibrationLabel` has no field to hold it, and `scorer` is used only as a grouping key
(`calibration.py:231`). So `make eval-calibrate` answers "how often does claude-opus-5 agree with the
maintainer, partitioned by which scorer's criteria were in play" — which the ROADMAP describes as the
*free secondary* number — while the headline question ("can I trust `tone_judge`?") is not computed at
all. P0.4 already produced one confirmed scorer false positive (`case_neg_injection_001`, ISSUE-129),
so the untrustworthy-scorer risk is measured-real, not hypothetical.
**Why deferred:** Not deferred — scheduled. It must land before any adjudication session, and after
EVAL-P6.1, since labels bind to one generation and re-generating after P6.1 would invalidate them.
**To fix:** Add `scorer_verdict: bool` to `CalibrationLabel` (joined from the judged transcript, never
supplied by the labeller). Make `scorer_verdict × human_verdict` the headline matrix and keep
`pre_label × human_verdict` as the secondary reference-labeller agreement number. Update
`confusion_counts`, `cohens_kappa`, `kappa_interval`, `ScorerReport`, `_print_scorer_report` and
`tests/unit/evals/test_calibration.py`. Decision recorded 2026-08-07 (option A, chosen by maintainer).
**Fixed:** 2026-08-08, in EVAL-P5.5 (`5a420f1 feat(evals): add scorer_verdict axis as headline
calibration matrix`). Verified for real 2026-08-09: `make eval-calibrate` against the first real
`labels_v1.jsonl` (393 rows, gen_id `k3_73e6c36`) prints `HEADLINE — scorer_verdict vs human_verdict`
per scorer with `pre_label × human_verdict` as a clearly labelled `SECONDARY` block underneath — the
question this issue said was uncomputed ("can I trust `tone_judge`?") now has a number.

## [FIXED] ISSUE-140: evals/calibration/raw_labels.jsonl holds 513 lines of prose, zero labels
**Found:** 2026-08-08, during calibration pipeline repair
**Severity:** P3 (nice-to-fix)
**Where:** `evals/calibration/raw_labels.jsonl`
**Description:** Accumulated output from ~10 failed labelling attempts across several sessions. Every
non-blank line is assistant commentary (some of it AI prose diagnosing the very bug that produced
it); a parse check found 0 valid label rows. The file is also cp1252-encoded, so `label-import`
fails on it with `UnicodeDecodeError` before it can reject the content.
**Why deferred:** Deleting it was not authorised in-session, and it is inert — the corrected loop in
`evals/calibration/README.md` filters non-JSON lines and writes UTF-8, and the real run should write
a fresh file. Kept as evidence of the failure mode until the first successful labelling pass.
**To fix:** Delete it once a real labelling run has produced a valid `raw_labels.jsonl`.
**Fixed:** 2026-08-09 — the maintainer hand-labelled the 393-item `tone_judge`/`affirms_judge`/
`refusal_judge`/`anti_hallucination_grounded` export (`evals/calibration/batches_handlabel/`)
directly, producing a valid UTF-8 `raw_labels.jsonl` (393 rows, all parse). `label-import` consumed
it cleanly against gen_id `k3_73e6c36` into `evals/calibration/labels_v1.jsonl`.

## [FIXED] ISSUE-136: roadmap fence tripwire snapshot goes stale mid-phase when a phase commits more than one task
**Found:** 2026-08-07, during overnight loop review of phase EVAL-P1
**Severity:** P2 (annoying — trips a false-positive HALT on the overnight loop, not a real regression)
**Where:** `tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire`
**Description:** The test is a hand-maintained snapshot of the roadmap's pending-task-id list, deliberately
updated by whoever's commit changes which tasks are pending (DEC-153-era design: "UPDATE DELIBERATELY when
the fence moves"). In practice the update rides whichever task's commit happens to touch the file — usually
the first task worked in a phase — not the last. EVAL-P1.2's commit updated the snapshot correctly for the
state at that moment, but EVAL-P1.5 and EVAL-P1.6 landed afterward in the same `expand_loop.sh` run without
a further update, so the phase-boundary `make check` gate went red on a stale assertion rather than a real
failure. The same pattern is recorded in the test's own docstring for EVAL-P4 and EVAL-P5 — this is the
fourth occurrence, all false positives, all costing a "FLAGGED FOR HUMAN" halt and a soft-review cycle.
**Why deferred:** Each occurrence so far has been cheap to diagnose and fix by hand (see commit 86254cb for
the EVAL-P1 instance), and redesigning the tripwire is out of scope for a mid-phase review pass.
**To fix:** Either (a) derive the assertion from `git diff` against the phase's start-of-phase baseline
instead of a hardcoded literal list, so it self-updates with whatever the phase actually completed, or
(b) move the snapshot-update responsibility into `expand_loop.sh`'s phase-boundary step itself (it already
knows the phase just closed) rather than leaving it to whichever task's author remembers. Either fix should
keep the "assert sorted id lists, not bare counts" property the current test already has, since that part
works as intended.
**Fixed:** 2026-08-10, in the red-gate repair pass (DEC-161). Resolved by option (c), which the entry
did not consider: neither derive-from-git-diff nor move-into-`expand_loop.sh`, but *stop asserting a
progress-sensitive quantity at all*. `EXPECTED_FLAGS` is now checked by **containment in both
directions** rather than set equality — no pending task may carry a flag that is not recorded
(catches ISSUE-134's accidental flag), and no task still listed and still pending may lose or change
its flag (catches an accidental unflag). A flagged task that a human *ticks* simply leaves `pending`
and its stale entry is inert, which is the single case set-equality got wrong and the cause of all
five false-positive HALTs. Verified by mutation: an added flag, a changed flag, and a ticked flagged
task produce fail / fail / pass respectively.

---

## [FIXED] ISSUE-142: the calibration artifact is gitignored — κ numbers cannot be reproduced or audited
**Fixed:** 2026-08-09, by DEC-158 (the `.gitignore` narrowing shipped but the issue was never marked). Confirmed 2026-08-10 during EVAL-P15 pre-flight: `.gitignore` now excludes only `evals/calibration/mock_*.jsonl` and `evals/calibration/*.bak`; `labels_v1.jsonl` (393 rows), `raw_labels.jsonl` (393 rows) and all 16 `batches_handlabel/` files are git-tracked, as are `evals/generations/k3_73e6c36/{meta,outputs,judged,deterministic_judged}`. Both halves of the pair the entry called for are recoverable from a fresh clone. The residual question the entry raised -- whether `calibrate` should also stamp the artifact's SHA-256 into its output so a quoted kappa is traceable to a specific file -- is **not** covered by DEC-158 and is carried forward by EVAL-P18.2 (provenance) rather than left implicit here.
**Found:** 2026-08-09, while committing the first real calibration pass
**Severity:** P1 (blocking for any published metric — the evidence for every κ claim is untracked)
**Where:** `.gitignore:29` (`evals/calibration/*.jsonl`)
**Description:** EVAL-P5's stated goal is "a **versioned, reproducible** calibration artifact". The
pattern at `.gitignore:29` excludes `evals/calibration/*.jsonl`, which covers both
`raw_labels.jsonl` (393 hand-labelled rows — hours of maintainer judgment) and `labels_v1.jsonl`
(the joined artifact every κ in ISSUE-129/ISSUE-141 is computed from). Neither is tracked. So the
headline claims "`tone_judge` κ=0.919", "`refusal_judge` κ=0.247" rest on files that exist only on
one machine, are one `git clean -fdx` from gone, and cannot be diffed when a scorer is later
remediated (EVAL-P11.2 explicitly requires showing κ *moved*, which needs the before-artifact).
The `.gitignore` rule is defensible in origin — it was presumably written to keep mock/scratch
labelling output (`mock_*.jsonl`) out of history — but it does not distinguish those from the real
artifact. `evals/calibration/batches_handlabel/` (the 16-batch export the labels were made against)
is untracked-but-not-ignored, so it is currently the only recoverable half of the pair.
**Why deferred:** Changing `.gitignore` is a shared-config change; and there is a real question
underneath it (do 393 rows of labels belong in git, or in an artifact store / release asset?) that
should be answered deliberately rather than by whoever commits next.
**To fix:** Narrow the rule to the mock artifacts only (`evals/calibration/mock_*.jsonl`) and commit
`raw_labels.jsonl` + `labels_v1.jsonl` + `batches_handlabel/`, recording the choice in DECISIONS —
or, if they are deemed too large/PII-adjacent for git, define where they *are* stored and have
`calibrate` record the artifact's SHA-256 in its output so a quoted κ is at least traceable to a
specific file.

---

## [FIXED] ISSUE-124: `evals/` is not covered by `mypy`, `check-rules`, or `check-docstrings`
**Found:** 2026-07-31, during eval-program planning
**Fixed:** 2026-08-10, in EVAL-P15.4
**Severity:** P3 (nice-to-fix — no current defect, but zero enforcement on the directory intended for publication)
**Where:** `Makefile` (`lint`, `type` recipes), `scripts/check_rules.py:108`, `scripts/docstring_audit.py`,
`scripts/rules_baseline.txt`
**Description:** Every quality gate scoped to `src/` only. Fixed by EVAL-P15.4:
(1) `check_rules.py` extended to scan `evals/` via `--evals` flag, 59 violations grandfathered in
`scripts/evals_baseline.txt`; (2) `docstring_audit.py` now scans `evals/` (2 violations fixed directly);
(3) `scripts/mypy_evals_ratchet.py` + `.mypy_evals_baseline` (16 errors) added; (4) `test-cov-evals`
gates evals coverage at 75% floor; all wired into `make check`.
**Why deferred:** `EVAL-P0.3` brings `evals/` under `ruff` only, deliberately time-boxed to 30 minutes.

## [FIXED] ISSUE-130: Anti-hallucination runner prints "SKIP (NPC not found)" for every skip cause
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Severity:** P3 (nice-to-fix)
**Where:** `evals/anti_hallucination_runner.py` (the `outcome == "skipped"` console branch, ~line 380)
**Description:** `ah_demo_mira_player_taught` printed `SKIP (NPC not found)`, but `mira_innkeeper`
exists and answered 8 other cases in the same run. The real cause is the `learned_from_player`
belief pre-flight (ISSUE-090 / DEC-095) finding no persisted player-taught fact. The console prints
one hardcoded reason for every skip, so the message actively misdirects — it sent this session
looking for an unseeded world that was already seeded.
**Why deferred:** Cosmetic; it cost diagnosis time but not correctness, and EVAL-P0.4 was mid-run.
**To fix:** Print the `skip_detail` already present on the result dict instead of the hardcoded
string. The correct text is already computed — it is simply not the one displayed.
**Fixed:** 2026-08-12, in EVAL-P17.4 — `evals/runner.py` now sets `skipped: True` and `skip_detail` at case level; `main()` prints `skip_detail` instead of a hardcoded string.

## [FIXED] ISSUE-152: `test_eval_records_v2.py` fails to collect — `RunConfig` now requires `harness_version` with no default
**Found:** 2026-08-12, during EVAL-P18.3 gate run
**Fixed:** 2026-08-12, during EVAL-P19 blocking-fix pass (single-line mechanical fix)
**Severity:** P1 (blocking — a collection error aborts the entire `pytest tests/unit/evals/` run,
so `make test-cov-evals` — part of `make check` — cannot execute for **any** eval test, not just
this file)
**Where:** `tests/unit/evals/test_eval_records_v2.py:28` (`_MINIMAL_RUN_CONFIG = RunConfig(...)`,
module-level fixture, no `harness_version` kwarg); `evals/run_config.py` `RunConfig.harness_version: str`
(added by EVAL-P18.1, no default — contrast `dialogue_prompt_hash: str = ""` two lines below it,
which does have one)
**Description:** EVAL-P18.1 added `harness_version: str` to `RunConfig` as a required field.
`test_eval_records_v2.py`'s module-level `_MINIMAL_RUN_CONFIG` fixture predates that change and was
not updated, so `pydantic.ValidationError: harness_version Field required` fires at **import time**,
which pytest reports as a collection error and aborts the whole session — every other file under
`tests/unit/evals/` (94 test modules) never runs. Confirmed present on clean `metrics` HEAD (`c6e1ae2`)
before this task's changes — not caused by EVAL-P18.3.
**Why deferred:** Out of scope for EVAL-P18.3 (compare.py comparability refusal); the fixture belongs
to a different test module than the one this task touches, and single-task-focus applies.
**To fix:** Added `harness_version="test_harness_v1"` to `_MINIMAL_RUN_CONFIG`'s constructor call.
Left `RunConfig.harness_version` required (no default) — comparability is the whole point of the
field (EVAL-P18.1); a silent default would let two incomparable runs compare cleanly by accident.

## [FIXED] ISSUE-151: `check_conservation.py` crashes on Windows console encoding, taking `make check` down with it
**Found:** 2026-08-12, during EVAL-P18.3 gate run
**Fixed:** 2026-08-12, during EVAL-P19 blocking-fix pass — `check_conservation.main()` now calls a
`_force_utf8_streams()` mirroring `check_human_gates.py`'s. Regression test
`test_main_does_not_crash_on_cp1252_stdout` patches `sys.stdout` to a strict-cp1252 stream and asserts
`main()` does not raise; confirmed RED before the fix (reproduced the exact `UnicodeEncodeError` on
U+222A) and GREEN after.
**Severity:** P1 (blocking — `make check` cannot complete on a Windows dev box; every later target in
the `check` dependency chain, including `test-cov`/`test-cov-evals`, never runs)
**Where:** `scripts/check_conservation.py` `main()` (`print(format_report(report))`, line ~283)
**Description:** `main()` never called `_force_utf8_streams()` (the fix `evals/__main__.py` and
`check_human_gates.py` already apply — see ISSUE-141's correction and ISSUE-144's `to fix` note for
the same pattern). The report contains `∪` (U+222A, Identity 2's `judged ∪ deterministic_judged`).
On a Windows console defaulting to cp1252, `print()` raised `UnicodeEncodeError: 'charmap' codec
can't encode character '∪'` and the script exited via an unhandled traceback — `make` then aborted
the whole `check` chain (`test-cov`/`test-cov-evals` never executed). The underlying audit logic was
unaffected: `PYTHONIOENCODING=utf-8 python scripts/check_conservation.py` ran to completion and
reported its real result (3 of 4 identities failing against the committed `k3_73e6c36` artifact —
expected pending EVAL-P17.5's re-measurement, tracked separately by HUMAN GATE H1, not a new defect).
**Why deferred:** Out of scope for EVAL-P18.3 (compare.py comparability refusal); this was a
pre-existing defect in a sibling script, confirmed present on a clean `metrics` HEAD before that
task's changes.
**To fix:** Called `_force_utf8_streams()` (already defined in `evals/__main__.py`) at the top of
`scripts/check_conservation.py`'s `main()`, mirroring `check_human_gates.py`'s pattern.

## [FIXED] ISSUE-158: `read_transcript` rejects the committed `k3_73e6c36` baseline outright — `RunConfig.harness_version` required field has no legacy fallback
**Found:** 2026-08-13, during `EVAL-P19.4` / `HUMAN GATE H2` execution (this task)
**Fixed:** 2026-08-13, same task — `read_transcript`'s gen-dir loader now stamps a
`LEGACY_HARNESS_VERSION` sentinel (`"legacy_pre_p18_1"`) onto pre-EVAL-P18.1 `meta.json` configs
missing `harness_version`, instead of failing validation. `RunConfig` itself keeps `harness_version`
required with no default (ISSUE-152's rationale unchanged: a default there would let two
incomparable runs compare cleanly by accident) — only the read boundary for legacy artifacts
tolerates the gap, and it does so via a sentinel that can never equal a real
`resolve_harness_version()` hash, so a legacy run can never accidentally read as comparable to a
current one. Regression test `test_read_transcript_reads_gen_dir_predating_harness_version`
(`tests/unit/evals/test_eval_records_v2.py`) confirmed RED (`ImportError` then
`pydantic.ValidationError: harness_version Field required`) before the fix, GREEN after; full
`test_eval_records_v2.py` + `test_eval_records.py` suites (20 tests) still pass. Verified against
the real artifact: `read_transcript(Path('evals/generations/k3_73e6c36/outputs.jsonl'))` loads all
921 records with `config.harness_version == "legacy_pre_p18_1"`.
**Severity:** P1 (blocking — `make eval-judge` and `make label-import` both call `read_transcript`
transitively (`judge_runner.py`, `transcript_index.read_transcript_provenance`) and both raised
`ValidationError` on the one committed baseline artifact `EVAL-P19.4`'s runbook specifies re-judging;
undiscovered until this task because ISSUE-152's fix only patched a test fixture, not the real
`evals/generations/k3_73e6c36/meta.json`, and nobody had run `evals judge` against it since
`EVAL-P18.1` landed 2026-08-12 (`judged.jsonl` mtime predates that date))
**Where:** `evals/eval_records.py` `_read_generation_dir` (called by `read_transcript`, used by
`judge_runner.py`, `evals/transcript_index.py`, `evals/label_import.py`)
**Description:** `EVAL-P18.1` (2026-08-12) added `RunConfig.harness_version: str` as a required
field, deliberately with no default. `evals/generations/k3_73e6c36/meta.json` was written
2026-08-08 — its `config` dict has every other `RunConfig` field but not `harness_version`.
`_read_generation_dir` passes that dict straight to `TranscriptFile.model_validate`, which
Pydantic rejects with `harness_version Field required`. Confirmed on clean `metrics` HEAD before
this task's changes.
**Why not deferred:** Blocking exception under the project's single-task-focus rule — `EVAL-P19.4`
cannot run its judge pass or its `label-import` merge without a way to load this transcript, and the
runbook explicitly requires the **unchanged** transcript (regenerating a fresh one would defeat the
zero-relabelling-cost point of the task). Confirmed with the user (`AskUserQuestion`) before fixing,
given it's an interface change on a function used well outside this module: chose the
loader-tolerance option over backfilling `meta.json` with a freshly-computed hash (would misrepresent
history — `EVAL-P19.2` already changed `evals/matchers.py`, one of `resolve_harness_version`'s
hash inputs, after this artifact was generated, so a "fresh" hash would not describe the state that
actually produced it) or stopping the task entirely.

## [FIXED] ISSUE-143: `sequence_runner` publishes a Wilson CI with no evidence the repetitions are independent
**Found:** 2026-08-10, during the EVAL-P15 pre-flight adversarial review of the open roadmap tasks
**Fixed:** 2026-08-13, in EVAL-P12.4 (`eval-p12.4-measured-multiturn` branch)
**Severity:** P1 (blocking for EVAL-P12.4 — it is the exact defect class Program 3 exists to remove,
shipped *inside* Program 3)
**Where:** `evals/sequence_runner.py:160` (`wilson_interval(passes, k)`), reached from `run_sequence`
**Update 2026-08-10 (EVAL-P12.1 measured):** the assumption is no longer unmeasured — it is measured
and **false**. `evals/reset_fidelity.json` records tier **PARTIAL**: `reset_world` clears only
`world_state.epoch` and `world_state.active_conditions`, while `emotion_store`, `game_clock.tick_id`,
`graph.edges.RELATES_TO`, `graph.nodes.character`, `engine_status_store` and
`world_state.other_properties` survive it, plus six stores with no read endpoint at all. So the
interval at `:160` is not merely unjustified, it is **known** to be computed over correlated
repetitions. **This issue stays OPEN**: EVAL-P12.1 supplies the evidence, EVAL-P12.4 Part A is the
fix (thread `ResetReceipt` through `reset_fn` and withhold the CI at the runner). Per-reset cost for
that task's budget: **median 54 ms**.
**Description:** `run_sequence` calls `reset_fn` between repetitions, times it, and then computes an
unconditional Wilson interval over the k outcomes. The reset function returns a **cost only** — no
evidence of what it actually cleared. So the interval assumes i.i.d. Bernoulli trials on the strength of
an assumption nobody has measured: **EVAL-P12.1, the task that measures what `reset_world` clears, has
never been run.**
Three facts make this concrete rather than theoretical:
1. `docs/SEQUENCE_STATS_POLICY.md` (EVAL-P14.2, written 2026-08-10, one day after the runner) states
   that under **PARTIAL** fidelity the *"Wilson CI on per-scenario pass rate"* is **suppressed (✗)**,
   because "correlated observations inflate the effective sample size and produce intervals that are too
   narrow". The runner has no code path that can suppress it.
2. `ResetReceipt` — the model that carries `surviving: tuple[str, ...]`, i.e. the independence evidence —
   exists in `evals/sequence_records.py` (EVAL-P14.1) but is part of the **v2 design schema**.
   `sequence_runner.py` (v1, EVAL-P12.3) neither imports nor produces one.
3. EVAL-P12.4's own validation string requires an interval in the output
   (`gossip reaches the 2-hop target 13/15 (k=3) [0.621, 0.963]`), so satisfying EVAL-P12.4 as written
   **forces** the violation.
This is the same error as EVAL-P16.1's finding (per-slot Wilson pooled across cases as though
independent), one layer up: there, the unit of analysis was wrong; here, the independence assumption is
simply unverified. Program 3's stated purpose is that "no published interval overstates its own evidence".
**Why deferred:** The fix has a hard prerequisite that is a live human session — EVAL-P12.1 must measure
the reset before any fidelity tier can be computed. Writing the gate before knowing which tier the real
stack lands in would be guessing at the very number the gate exists to respect.
**To fix:** (1) Run EVAL-P12.1 and have it emit a **machine-readable** fidelity artifact, not only
`docs/RESET_FIDELITY.md`. (2) Change `reset_fn`'s contract to return a `ResetReceipt` rather than a bare
cost, so every repetition carries its own evidence — this is exactly what EVAL-P14.1's schema already
specifies for v2 and it should be back-ported rather than re-invented. (3) Gate the interval at the
**runner** level per SEQUENCE_STATS_POLICY §3's enforcement contract ("the formatter has no visibility
into the receipts"), so a PARTIAL run cannot render a CI even if a later formatter asks for one.
(4) Re-word EVAL-P12.4's validation so it does not mandate an interval unconditionally. Steps 2-4 are
folded into EVAL-P12.4 as of 2026-08-10; step 1 is EVAL-P12.1 and is listed in `HUMAN_TASKS.md`.
**How fixed:** `evals/sequence_runner.reset_fn` now returns a `ResetReceipt` (`evals/sequence_reset.py`
builds one per repetition from `evals/reset_fidelity.json` plus a live-measured `duration_ms`).
`evals/sequence_fidelity.py` derives the run's tier from the receipts and withholds the interval — the
report formatter (`evals/sequence_rates.py:render_report`) never receives a receipt, only the
already-gated `SequenceStat`. Live-verified: the EVAL-P12.4 k=3x6 run reported PARTIAL fidelity on
every scenario, no Wilson interval anywhere in the output, and the order-effect check
(Cochran's Q + first-vs-last McNemar, pooled across the 6 scenarios) printed in its place.

## [FIXED] ISSUE-170: the loop-fence tripwire is already red, so it can no longer guard the fence
**Found:** 2026-08-14, during `EVAL-P20.0`
**Fixed:** 2026-08-15, in the H3-fence-position repair session (see DEC-177)
**Severity:** P1 (blocking — it silently disarms the H3 safety mechanism)
**Where:** `tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire` and
`::test_real_roadmap_parses_and_verifies_clean`
**Description:** Both tests fail on a clean tree: `At index 20 diff: 'RET-P0' != 'EVAL-P20'`. The
`RET-P0` commit (`9cb09c9`) inserted a new phase inside the fenced range without updating the
tripwire's phase-list snapshot. **Verified pre-existing** — both fail identically with this task's
changes stashed. Note `make roadmap-verify` still passes (`ROADMAP OK (queue lines 125-2430,
21 phases)`); only the pytest snapshot is stale.
**Why this is P1 rather than cosmetic:** the tripwire exists precisely so that moving
`<!-- LOOP:QUEUE end -->` is a conscious act — ROADMAP H3 and HUMAN_TASKS both say "that tripwire
going red on the move is it working". A tripwire that is *already* red cannot signal anything: the
next fence move produces no state change in the gate, and the `range(20)` that is supposed to be
updated deliberately would be updated to silence a failure that has two unrelated causes mixed
together. This did not bite in this session only because `EVAL-P20.0` failed its gate and the fence
was therefore not moved.
**Why deferred:** not caused by `EVAL-P20.0`; single-task focus, and re-snapshotting the phase list
while the fence question is live would be exactly the conflation described above.
**To fix:** update the expected phase list to include `RET-P0` at its real index and re-assert the
current fence position, in a commit that does *nothing else*, so the snapshot means something again
before H3 is next considered.
**How fixed:** the predicted conflation happened one day later exactly as warned — commit `84ff0f9`
moved the fence marker to the wide (DEC-160) position with neither reopen condition met nor a
DECISIONS entry (see **DEC-177**), and this tripwire, already red, caught none of it. Rather than
teaching the tripwire's phase list about `RET-P0`, `RET-P0` was relocated bodily to below
`EVAL-P24.3` (outside the fence entirely — it is ✅ complete with no pending tasks, so it does not
need to be loop-reachable), and the fence marker was moved back to the DEC-163 position. The
pinned `range(20)` needed no edit: it was already correct for that span. Both tests pass again.

## [FIXED] ISSUE-131: compose publishes Neo4j's 7687 but the `internal: true` network silently voids it
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Fixed:** 2026-08-16, in EVAL-P20.3a (DEC-180)
**Severity:** P2 (annoying)
**Where:** `docker-compose.yml` (neo4j `ports:` + `networks: [internal]`); `Makefile` `eval-retrieval`
**Description:** The neo4j service declares `"7474:7474"` and `"7687:7687"`, but it is attached only
to the `internal` network, which is `internal: true`. Docker **silently ignores** port publishing in
that case — `docker ps` shows bare `7687/tcp` with no host binding. So `make eval-retrieval`, which
runs `python -m evals.retrieval_runner` on the host, can never connect and dies with
`ServiceUnavailable` on `localhost:7687`. The declared ports read as an intent that the network
config cancels, so the file looks correct while being inoperative. Note `evals/` is in
`.dockerignore`, so `docker compose exec app` cannot run it either — the repo must be bind-mounted.
**Why deferred:** Both candidate fixes are shared-config changes needing a call: attaching neo4j to
the `public` network weakens the documented route-security posture at the top of the compose file,
and rewriting the Makefile target to shell into a container changes a target every contributor uses.
**To fix:** Pick one and record it in DECISIONS: (a) delete the misleading `ports:` block and change
`eval-retrieval` to `docker compose run --rm -v "$$PWD:/work" -w /work app python -m evals.retrieval_runner`
(the invocation verified working on 2026-08-06), or (b) add a dev-only compose override that puts
neo4j on `public` so host tooling works, leaving the base file's posture intact.
**How fixed:** Chose (a) via `AskUserQuestion` (EVAL-P20.3a Step 1). Dropped the `ports:` block from
`docker-compose.yml`'s `neo4j` service entirely. `demo-snapshot`, `demo-restore`, the new
`eval-world-reset`, and `eval-retrieval` Makefile targets all now run via
`docker compose run --rm -v "$PWD:/work" -w /work app python -m <module> ...`, verified working live
(demo-snapshot/restore/eval-world-reset confirmed against the running stack; eval-retrieval shares
the identical command shape but could not be re-verified live after Docker Desktop's daemon went
unreachable mid-session — see DEC-180).

## [FIXED] ISSUE-153: `label_merge._refresh` never refreshes `pre_label` on drift, so a re-adjudicated row can carry a stale reference-labeller opinion
**Found:** 2026-08-12, during EVAL-P19.0 (making `needs_review` load-bearing)
**Fixed:** 2026-08-16, in EVAL-P20.3a (DEC-180)
**Severity:** P3 (nice-to-fix — the secondary/pre_label axis can silently compare a fresh
human verdict against a pre_label computed from text that no longer exists)
**Where:** `evals/label_merge.py` `_MACHINE_FIELDS` (does not list `pre_label` or
`pre_labeller_model`); `_refresh`
**Description:** `_MACHINE_FIELDS` refreshes `output_text`, `scorer_verdict`, `criteria`, etc.
on every merge, but `pre_label`/`pre_labeller_model` are preserved unchanged from the
existing row — even when `output_text` drifted underneath it. After EVAL-P19.0,
`adjudicate.apply_verdict` clears `needs_review` on re-adjudication and the row re-enters the
secondary (pre_label vs human_verdict) calibration axis, but `pre_label` still reflects the
reference labeller's opinion of the **old** text, not the new one it was merged against.
**Why deferred:** Refreshing `pre_label` correctly requires re-running the reference-labeller
model against the new `output_text` — a live/expensive operation, not a pure merge, and out
of scope for EVAL-P19.0 (calibration.py / adjudicate.py / label_merge.py's WARNING path).
**To fix:** Either (a) clear `pre_label` to `None`-like/absent on drift so the secondary axis
excludes the row until a live re-label happens, or (b) add a `pre_label_needs_review` flag
mirroring `needs_review` and have `calibration.py`'s secondary-axis functions exclude on that
flag specifically. Needs a design call — not mechanical.
**How fixed:** Chose (a) via `AskUserQuestion` (EVAL-P20.3a Step 4). Widened
`CalibrationLabel.pre_label` to `bool | None`; `label_merge._refresh` clears `pre_label`/
`pre_labeller_model` to `None`/`""` on any detected drift. `calibration.py`'s
`pre_label_confusion_counts`/`pre_label_kappa`/`pre_label_kappa_interval`/`agreement_rate` now
exclude `pre_label is None` rows via a new `_secondary_axis_rows` helper, surfacing the exclusion
count rather than silently miscounting. Required a follow-on fix in `evals/adjudicate.py`
(`keep`/`flip` read `pre_label` directly; added `pass`/`fail` direct-verdict commands for rows with
no `pre_label`) — see DEC-180.

## [FIXED] ISSUE-160: `label_merge._has_drifted` only compares `output_sha256`/`criteria_sha256` — a verdict-only change on hash-identical content is invisible to the merge report
**Found:** 2026-08-13, during `EVAL-P19.4` (`HUMAN GATE H2`)
**Fixed:** 2026-08-16, in EVAL-P20.3a (DEC-180)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/label_merge.py` `_has_drifted` / `merge_labels`
**Description:** Re-judging the unchanged `k3_73e6c36` transcript and merging with `MERGE=1`
reported `human verdicts preserved: 393` and zero drifted rows — correct as far as the tool's own
definition of drift goes. A row-by-row diff against the pre-merge file found one real change the
report never surfaced: `case_adv_lira_troop_positions:tone_judge:4#r0`'s `scorer_verdict` flipped
`true`→`false` on re-judge, with `output_sha256` and `criteria_sha256` both byte-identical old vs.
new. `human_verdict` was untouched (hence 393 still holds), and the cause is ordinary LLM judge
non-determinism (DEC-146 already documents no `seed` parameter exists) — not a EVAL-P19.2 matcher
effect, not a criteria change, and unrelated to `refusal_judge`/ISSUE-141. But `_has_drifted` only
diffs `output_sha256`/`criteria_sha256`, so a `scorer_verdict` change with unchanged hashes is
structurally invisible to `format_merge_report`'s `needs_review` warning — "0 drifted" describes
hash-drift only, not "nothing about this row changed."
**Why deferred:** Out of scope for `EVAL-P19.4` (measurement task, not a merge-tool change);
confirmed via `AskUserQuestion` this is accepted as normal LLM non-determinism for this specific
row rather than reverted.
**To fix:** Decide whether a verdict-only flip on a hash-identical row should also set
`needs_review=True` (safer default: any change under an existing human verdict gets a second
look, even if the tool can't yet say why) or is intentionally out of scope because re-running a
judge is expected to occasionally disagree with itself. Either way, `format_merge_report` should
state its drift definition explicitly ("hash-drift" vs. "any field drift") so a future reader
doesn't read "0 drifted" as "byte-identical import."
**How fixed:** `_has_drifted` (EVAL-P20.3a Step 3, mechanical, no design call needed) now also
flags a `scorer_verdict` change on hash-identical `output_sha256`/`criteria_sha256` as drift, pinned
by a RED-anchor test built from the real named case. `format_merge_report`'s WARNING line now
states the drift definition explicitly.

## [FIXED] ISSUE-167: no way to reset eval world state between generation runs
**Found:** 2026-08-14, during `EVAL-P20.0`
**Fixed:** 2026-08-16, in EVAL-P20.3a (DEC-180)
**Severity:** P2 (annoying — blocks clean re-measurement)
**Where:** `evals/preconditions.py` `reset_world`, `docker-compose.yml` (neo4j ports),
`demo_game/snapshot.py`
**Description:** Two generation runs cannot be started from identical graph state. `reset_world`
only PATCHes `world_state` (fidelity PARTIAL — `evals/reset_fidelity.json` lists
`graph.edges.RELATES_TO`, `emotion_store` and the caches under `surviving`), there is no
graph-wide reset endpoint, `make demo-restore` needs a snapshot that requires a host bolt
connection, and Neo4j's 7687 is not published to the host in `docker-compose.yml`. Measured
consequence: run B started from run A's end state, and emotion/routine drift affected 109/145
records. The EVAL-P20.0 measurement had to reset per-NPC emotion via
`PATCH /v1/graph/nodes/character/{id}` from a throwaway script, which is not reproducible tooling.
**Why deferred:** out of scope for adding a seed. It is infrastructure for the regeneration
protocol, and `EVAL-P20.4` will need it.
**To fix:** either publish 7687 so `make demo-snapshot`/`demo-restore` work, or add a committed
`make eval-world-reset` that restores the seeded baseline through the admin API. Then update
`evals/reset_fidelity.json` with the achieved fidelity.
**How fixed:** Root cause was ISSUE-131 (the port publish never worked), not missing tooling —
`demo_game/snapshot.py` already had `do_snapshot`/`do_restore`. Fixed the network topology (see
ISSUE-131), wiped the (junk-accumulated, 31,215-`Quest`-node) live graph, reseeded fresh (demo +
village + tavern), and snapshotted that clean state to the checked-in
`evals/fixtures/eval_world_baseline.json`. New `make eval-world-reset` target restores it. Re-ran
`e2e/scripts/measure_reset_fidelity.py` fresh — `evals/reset_fidelity.json`/`docs/RESET_FIDELITY.md`
now carry a current `measured_at`/`git_sha`.

## [FIXED] ISSUE-168: human labels are joined on exact output text, so they die on any single token flip
**Found:** 2026-08-14, during `EVAL-P20.0`
**Severity:** P1 (blocking the premise of the two-regeneration budget)
**Where:** `evals/content_hash.py:18` `sha256_text`, consumed by `calibration_records`,
`label_import`, `label_merge`
**Description:** A human verdict is bound to `sha256(output_text + criteria)`. EVAL-P20.0 measured
that byte-identical reproduction is unattainable at dialogue output lengths on this runtime:
reproduction decays with generated token count (91.7% at ~60 tokens, 45.8% for the structured
`DialogueResponse`, **4.2%** at the shipped `max_tokens=512`), consistent with per-token
floating-point flips compounding. A seed fixes the sampling draw but cannot make inference bitwise
deterministic. So an exact-text join guarantees mass label loss at every regeneration *by design*,
independent of any seed work. DEC-176 raised survival from ~19% to ~62.5%; the remaining ~37.5% is
not addressable by configuration.
**Why deferred:** re-scoping the label join is a much larger change than `EVAL-P20.0`, and the
human explicitly chose (2026-08-14) to land the seed + prompt fixes and record the gate as NOT MET
rather than re-scope in the same session.
**To fix:** decide whether the join should tolerate drift — e.g. normalised-text hash, or binding
the label to `(record_id, repetition, criteria)` with the text kept as evidence rather than as the
key — and whether `needs_review` should finally be *read* by the scorers (it is written by
`label_merge` and read by nothing; see the EVAL-P20 phase Notes). This determines whether the
two-regeneration budget is affordable at all.
**Fixed:** 2026-08-16, in EVAL-P20.3b (DEC-181)
**How fixed:** Rescoped per the roadmap's own correction — the join key was already
`(record_id, scorer)` with repetition encoded in `record_id`, not exact output text; what was
actually gated on exact text was *trust*, not lookup. Via `AskUserQuestion` (four options, evidence
gathered live against `k3_73e6c36` before presenting), chose option (d): `label_merge._has_drifted`
now compares `criteria_sha256` only — a `human_verdict` is trusted as long as the scorer's criteria
is unchanged, regardless of `output_text`. `needs_review` was already read by the scorers
(EVAL-P19.0, 2026-08-12) — that half of this issue's own "To fix" was stale by the time this was
resolved. Full writeup, rejected alternatives, and the residual risk named explicitly: DEC-181.

## [FIXED] ISSUE-172: `EVAL-P17.1`/`EVAL-P17.6` checked done, but `make check-conservation` still fails live
**Found:** 2026-08-15, during the EVAL-P20-P24 unblock planning session
**Severity:** P1 (blocking — this is the program's own named failure mode, checkbox vs.
measurement, recurring inside a phase (`EVAL-P17`) that `roadmap_cursor.py --status` reports fully
`DONE`)
**Where:** `scripts/check_conservation.py`; `project-harness/ROADMAP.md` `EVAL-P17.1`, `EVAL-P17.6`
**Description:** `EVAL-P17.6` is `[x]` `✅ AUTO (EVAL-P17.6, 2026-08-12)` with its own validation
text stating *"`make check-conservation` exits 0... If any identity still fails here, EVAL-P17 is
not done."* `EVAL-P17.1` is likewise `[x]` `✅ AUTO`, its validation claiming to fix Identities 2/3
specifically ("capability turns rise 2 → 7 cases... `compare`'s intersection covers 307 slots").
Ran `python scripts/check_conservation.py` live this session (2026-08-15, well after both commits):
exit code 3, 3 of 4 identities still fail, with the **exact pre-fix numbers named in the tasks'
own text** — capability battery still "sees 2" (not 7), `compare` still reads 115 of 307 (62.5%
never read), and Identity 1 still finds 9 of 94 cases in no battery. Nothing about `DEC-178`'s
fence-reopen touched this — it was already broken before and after. `H3`'s condition 1
(`EVAL-P17.6` green) is therefore not actually met even though `DEC-178` already explicitly
accepted overriding H3 regardless.
**Why deferred:** out of scope for a planning session (this session's task is inventory + plan,
not implementation); root-causing why two `[x]`-checked, `✅ AUTO`-tagged tasks don't hold against
the live artifact needs its own investigation, not a same-session fix.
**To fix:** re-open `EVAL-P17.1` and `EVAL-P17.6` for a real fix (not just re-ticking), tracing why
`summarize`/`compare` still read `judged.jsonl` only (or whatever the actual regression is —
`ISSUE-155`'s repetition-collapse bug in `verdict_sources.load_unified_rows` is a plausible
contributor, adjacent but not confirmed as the root cause) despite the committed fix. Do this
before or alongside `EVAL-P20.4` (regeneration #1) — measuring a regeneration against a
conservation-broken aggregator produces numbers of unverified trustworthiness.
**Fixed:** 2026-08-16, before `EVAL-P20.4` (DEC-182)
**How fixed:** `summarize`/`compare` were never the regression — `EVAL-P17.1` had already fixed
them to read both verdict files via `verdict_sources.load_unified_rows`. The bugs were in
`scripts/check_conservation.py` itself: Identity 1 hardcoded `excluded = 0` instead of counting
`classify_battery`'s real `"excluded"` verdict (9 legitimately-excluded cases misread as a
coverage gap); Identities 2/3 hand-read `judged.jsonl` only, modelling `compare.py`'s
**pre-EVAL-P17.1** behavior instead of calling the same `load_unified_rows` unifier `compare.py`
and `summary.py` already used correctly. `ISSUE-155` was not the contributor. Fixed via
`AskUserQuestion` (chosen over deferring as accepted risk, given the root cause was confirmed
small and well-scoped before presenting the choice). `make check-conservation` now genuinely
exits 0. Full writeup: DEC-182.

## [FIXED] ISSUE-174: `EVAL-P21.0`'s judge-roster choice has no `AskUserQuestion` marker despite being a real human decision
**Found:** 2026-08-15, during the EVAL-P20-P24 unblock planning session
**Severity:** P3 (nice-to-fix — a documentation/wording gap, not a blocker)
**Where:** `project-harness/ROADMAP.md`, Phase `EVAL-P21`, subtask `EVAL-P21.0`
**Description:** `EVAL-P21.0` ("panel roster and independence") requires a real human pick between
an out-of-family third judge model (`llama3.1:8b` or `gemma2:9b` — `qwen2.5:14b` is banned as
same-family as the generation model) but carries no `⏸️`/`(live` flag and no `AskUserQuestion`
marker in ROADMAP.md — it's phrased as a plain task that "requires a DECISIONS entry," not a
formal question round. `EVAL-P21.3` is the flagged task ("records a DECISIONS entry settling a
judge"), which reads as covering the *outcome* but not necessarily prompting the *choice* via the
same `AskUserQuestion` discipline used elsewhere in `EVAL-P20.3a`/`P20.3b`.
**Why deferred:** cosmetic/consistency issue found while auditing P20-P24 for `AskUserQuestion`
markers (see `project-harness/EVAL_P20_TO_P24_UNBLOCK_PLAN.md` Section 3); not this session's task
to fix, and the decision itself is not blocked — it just lacks the formal ritual other P20 human
decisions use.
**To fix:** either add an explicit `AskUserQuestion, before any implementation` marker to
`EVAL-P21.0` matching the `EVAL-P20.3a`/`P20.3b` pattern, or note in `EVAL-P21.0`'s text that the
model pick is made informally and recorded via `EVAL-P21.3`'s DECISIONS entry — pick one
convention and make it consistent across Program 3's human-decision tasks.
**Fixed:** 2026-08-16, in EVAL-P21.0 (DEC-183)
**How fixed:** Added the explicit `AskUserQuestion, before any implementation` marker to
`EVAL-P21.0`, matching the `EVAL-P20.3a`/`P20.3b` convention. Asked the roster question in the
same sitting; chose `llama3.1:8b`. Full writeup: DEC-183.

## [FIXED] ISSUE-165: dialogue_handler stamps state writes with wall-clock time, bypassing GameClock
**Found:** 2026-08-14, during `EVAL-P20.0`
**Severity:** P1 (blocking — it is one of two causes of non-reproducible prompts)
**Where:** `src/npc_engine/engines/dialogue/dialogue_handler.py:224`
**Description:** `tick_id = int(datetime.now(timezone.utc).timestamp())` — the dialogue handler
uses a unix wall-clock timestamp as the tick id, while `scheduler/game_clock.py` provides a
deterministic `GameClock` that starts at 0 and advances only via explicit `advance()` calls, and
`docker-compose.yml` runs the app with `CLOCK_MODE: game_driven`. That wall-clock value is
persisted into `emotion_updated_at_tick` (`graph/emotion/emotion_writer.py:21`) and
`routine_override.expires_at_tick` (`dialogue_handler.py:292-293`), both read back into later
prompts — so dialogue is self-perturbing across runs. Measured: these fields differed on 145/145
records between two eval generations. DEC-176 mitigates the *symptom* by stripping both fields from
prompt content, but the underlying values are still wrong: a "tick" that is really a wall clock
makes tick arithmetic (`expires_at_tick = tick_id + 5`, oath/pledge expiry, decay rates expressed
in units-per-tick) meaningless, since 5 "ticks" is 5 seconds of real time regardless of game time.
**Why deferred:** changing the tick contract is a behaviour change affecting emotion decay, routine
overrides, pledge/treaty expiry and the oath engine — far outside `EVAL-P20.0`'s scope, and it
needs its own regression tests. The prompt-determinism symptom is fixed independently.
**To fix:** route `tick_id` through the injected `GameClock` (or the world-state tick) rather than
`datetime.now()`, and add a test asserting two dialogue calls at the same game tick write the same
`emotion_updated_at_tick`. Audit for other `datetime.now()`-as-tick uses at the same time.
**Fixed:** 2026-08-17, in ISSUE-165a..f (commits `5ec0851`, `49f3df0`, `6313286`, `16bfa9c`, + Stage 5/6).
The audit called for above found this was **four** wall-clock/hardcoded tick sources, not one:
`dialogue_handler.py:224`, `api/routes/dialogue/action.py:99`, `quest/quest_engine_helpers.py:86`,
and `scheming_engine.py:186` (hardcoded `tick_id=0`), plus `interaction.py:220` (`current_tick=0`)
and ~13 `tick_id: int = 0` engine defaults. All now route through `GameClock` via a read-only
`ClockPort` Protocol; the `tick=0` defaults are required parameters. The routine-override bug was
worse than described: `routine_engine.py:138` compares `expires_at_tick` against a *game* tick, so
dialogue-set overrides were never reachable and the NPC stayed home permanently.
Also fixed a latent bug the required-tick change exposed: `gossip_handler.py:333` called
`apply_event_shock` without a tick, stamping `emotion_updated_at_tick = 0`.
The tick is now persisted on `:WorldState` and hydrated at startup (DEC-186), so it survives restart.
**Migration:** none (DEC-186/D4). Dev graphs containing epoch-sized ticks (~1.78e9) must be
**reseeded** — such values now read as unreachably far in the future. Eval baselines captured before
this change will diff; that is the fix working, not a regression.

## [FIXED] ISSUE-175: panel-mode `judged.jsonl` (one row per judge per record) breaks readers that assume one row per record_id
**Fixed:** 2026-08-18, in the post-overnight panel-persistence rewrite (DEC-187).
Resolved via option (b), as the entry itself recommended: `judge_runner --panel` now writes
`judged.jsonl` in the historical one-row-per-record consensus shape (every existing reader
unchanged) plus a sibling `judged_panel_votes.jsonl` carrying one row per seat. Both are built
by `evals/judged_persistence.py`, which is now the single owner of the row schema.
**Went live before it was fixed:** the 2026-08-17 overnight run produced exactly the artifact
this entry said did not yet exist, and wrote it to the path `build_judged_index` reads. The
'not live-wrong today' deferral rationale was correct when written and stale within a day.
**Found:** 2026-08-17, during EVAL-P21.1/P21.2 wiring (EVAL-P20→P24 unblock plan, Phase A4)
**Severity:** P2 (annoying) — silently picks an arbitrary judge's verdict rather than the panel consensus
**Where:** `evals/transcript_index.py:build_judged_index` (last-write-wins per composite item_id);
consumed by `evals/label_import.py`, and any future caller of `judged.jsonl` that assumes 1 row/record
**Description:** `judge_runner.py --panel` now persists via `judge_panel_runner.write_panel_judged_jsonl`
(`judge_panel.to_judged_rows`), which writes `len(models)` rows per `record_id` — one per panel seat,
by design (EVAL-P21.1's own validation clause: "a record judged by 3 models yields 3 rows"). This is
correct for auditability but a **new schema for this file**: any reader still written against the
single-judge shape (`build_judged_index`, which indexes into a plain `dict` and keeps whichever row
happens to be read last) will silently select one arbitrary panel seat's `passed` value instead of the
2-of-3 consensus already computed and written into the corresponding `outputs`/report path.
**Why deferred:** Nothing in the current pipeline points `label_import` at a panel-mode `judged.jsonl`
yet — HUMAN GATE H7/H8's live panel run (`EVAL-P21.1`/`P21.2`) hasn't fired, so this is not live-wrong
today. Fixing `build_judged_index` to consensus-reduce multi-seat rows is real work that belongs to
whichever task first wires panel-mode output into the labelling path, not to the panel-wiring task
itself (single-task-focus).
**To fix:** Before any labelling pass consumes a panel-run `judged.jsonl`, either (a) have
`build_judged_index` detect multi-row-per-record_id input and apply `judge_panel.consensus_verdict`
across the seats sharing a `record_id`, or (b) keep panel-mode output as a separate file
(`judged_panel_votes.jsonl`) and have `judge_runner.py` also write the existing single-row-per-record
consensus shape to `judged.jsonl` so every downstream reader keeps working unchanged. (b) is simpler
and lower-risk; revisit at that point which is worth the file-layout change.

## [FIXED] ISSUE-179: panel `judged.jsonl` rows ignored `expected_polarity`, inverting 39% of them
**Found:** 2026-08-18, analysing the 2026-08-17 overnight panel run
**Fixed:** 2026-08-18, in the panel-persistence rewrite (DEC-187)
**Severity:** P1 — silently wrong data feeding EVAL-P21.3's judge decision
**Where:** `evals/judge_panel.py:113` (`"passed": bool(v.score)`)
**Description:** The panel writer derived `passed` from the raw YES/NO score without consulting
`expected_polarity`. For `pass_on_no` criteria (`affirms_judge` — 135 of every judge's 345 rows,
39%) a NO verdict means the NPC did **not** affirm the lie, i.e. a PASS; the file recorded FAIL.
Stored per-judge pass rates read 0.580/0.565/0.591; the true rates are 0.954/0.928/0.971.
The consensus path was unaffected (`judge_panel_runner._panel_fail_votes` applies polarity), so the
markdown report was correct — only the persisted per-seat rows were wrong. EVAL-P21.3 reads exactly
those rows, so kappa computed from them would have been wrong for 39% of records.
**To fix:** done — `judged_persistence.apply_polarity` is applied when building every row, and
`test_seat_rows_apply_expected_polarity` is the regression guard.

## [FIXED] ISSUE-180: panel `judged.jsonl` rows dropped `repetition`, collapsing k repeats
**Found:** 2026-08-18, analysing the 2026-08-17 overnight panel run
**Fixed:** 2026-08-18, in the panel-persistence rewrite (DEC-187)
**Severity:** P1 — two of every three repetitions became unreachable to the labelling path
**Where:** `evals/judge_panel.py:108` (`to_judged_rows` emitted 6 fields; the single-judge writer
emitted 8, including `repetition`)
**Description:** `transcript_index.build_judged_index` keys on
`composite_item_id(record_id, obj.get("repetition", 0))`. With `repetition` absent, every panel row
defaulted to 0, so all 9 rows sharing a `record_id` (3 repeats x 3 seats) collapsed onto one key
under last-write-wins — and repeats 1 and 2 got no verdict at all. Measured on the real artifact:
the index returned 115 entries where it should return 345.
**To fix:** done — `repetition` (with `case_id` and `judge_kind`) is carried on every row;
`test_seat_rows_carry_repetition` and `test_seat_rows_are_a_superset_of_single_judge_rows` guard it.

## [FIXED] ISSUE-181: inter-judge agreement pooled repetitions, inflating n 4x and self-comparing judges
**Found:** 2026-08-18, analysing the 2026-08-17 overnight panel run
**Fixed:** 2026-08-18, in the panel-metrics rewrite (DEC-188)
**Severity:** P1 — a published headline statistic was measuring partly the wrong thing
**Where:** `evals/judge_panel_runner.py:188` (`votes_by_record.setdefault(v.record_id, ...)`)
**Description:** Agreement grouped verdicts by `record_id` alone. At k=3 three distinct generations
share one `record_id`, so 9 verdicts were pooled into a single item, yielding C(9,2)=36 pairs where
the truth is 3 items x C(3,2) = 9. The run reported 3954/4140; the correct figure is 989/1035.
The point estimate barely moved (0.9551 -> 0.9556) but the CI was ~2x too narrow, and **9 of every
36 pairs compared a judge against itself** on a different generation — intra-judge test-retest noise
silently mixed into an inter-judge statistic.
**Root cause:** the interface, not the arithmetic. `judge_transcript_panel` returned a flat
`list[PanelVerdict]`, forcing downstream code to *re-derive* grouping from `record_id`.
**To fix:** done — it now returns `PanelScoredRecord` (record paired with its seats' verdicts), so
grouping is structural and cannot be re-derived wrongly.
`test_agreement_does_not_pool_repetitions_of_one_record_id` is the guard.

## [FIXED] ISSUE-182: overnight ops script read judge exit code 1 as an infra failure
**Found:** 2026-08-18, analysing the 2026-08-17 overnight panel run
**Fixed:** 2026-08-18, via `evals/run_status.py` (DEC-189)
**Severity:** P2 — cost a night of Phase 2 work; would have recurred every run
**Where:** the Phase 1 ops script's `if ($PanelExit -ne 0)` branch
**Description:** `judge_runner.main` returns 0 (gate met), 1 (pass completed, some cases missed
expectations) or 2 (pass could not complete). The script treated any non-zero as failure, wrote
"Panel judge pass FAILED" into the morning handoff and halted Phase 2 — over a completed run that
scored 194/210. The three-way convention existed only inside `main`'s docstring.
**To fix:** done — every pass now writes `run_status.json` (`ok` / `gate_failed` / `error`, with
`measurement_valid` true for the first two). `project-harness/Run-OvernightPhase1.ps1` branches on
that file, never on the exit code.

## [FIXED] ISSUE-185: `compare.py`'s comparability gate cannot detect a judge-pass mismatch between A/B arms
**Fixed:** 2026-08-18, in the pre-combined-run hardening (DEC-190).
`evals/judge_identity.resolve_judge_identity` reads `run_status.json` for the judge that
actually scored a directory and falls back to `meta.json` for pre-DEC-189 runs;
`compare._read_run_meta` uses it, so a panel arm and a single-judge arm no longer compare
clean. Panel identity renders as `panel:<sorted roster>` — sorted because consensus is a
count and indifferent to seat order, so order alone must not trigger a spurious refusal.
RED anchors in `tests/unit/evals/test_compare_judge_identity.py`.
**Found:** 2026-08-18, tracing the A/B path while scoping the Phase 1 + Phase 2 combined run
**Severity:** P1 (blocking for trustworthy A/B) - produces a confident McNemar verdict from two
arms measured with different instruments
**Where:** `evals/compare.py:_read_run_meta` / `_comparability_error`
**Description:** `compare.py` refuses to compare two generation directories when
`harness_version`, `judge_model` or `k` differ (EVAL-P18.3). But `judge_model` is read from
`meta.json`'s `config` block, which is a `RunConfig` snapshot captured at **generation** time
(`judge_config.resolve_judge_model()`), not a record of which judge pass actually scored the
directory. Since `--panel` landed, the same generation config can be scored either by a single
judge or by the 3-model panel, producing materially different `judged.jsonl` verdicts under an
identical `meta.json`. The gate therefore passes and `compare_runs` reports a confident paired
verdict whose delta is partly the *instrument* changing, not the engine. This is the same class
of defect as ISSUE-181 (a statistic silently measuring something other than what it claims), one
layer up.
**Consequence for the A/B goal:** the intended use of this harness is A/B-testing engines, agents
and context management across regenerations. An undetected instrument mismatch is precisely the
confound that makes such a comparison worthless, and nothing currently catches it.
**Why deferred:** the fix belongs with whichever task first compares two arms for real; today
there is not yet a single valid arm to compare (see below), so it is not live-wrong *yet* - the
same shape of deferral rationale ISSUE-175 carried, which went stale within a day, so this should
be fixed before the second regeneration exists rather than after.
**To fix:** record what actually judged a directory - `run_status.json` already carries
`judge_panel` / `judge_model` per pass (DEC-189). Have `_read_run_meta` prefer `run_status.json`
over `meta.json` for the judge identity (falling back to `meta.json` for pre-DEC-189 runs), and
include the panel roster in the equality check so `panel:3` never compares clean against a single
judge. Consensus rows already stamp `judge_model: "panel:N"`, so the data needed is on disk.

---

## [FIXED] ISSUE-188: `snapshot.do_restore` is not safe against a live writer and fails PARTWAY, leaving a half-restored graph
**Found:** 2026-08-19, when the combined overnight run died at step 3 for the third time
**Fixed:** 2026-08-20, in the ISSUE-188 task (atomic restore + live-writer probe)
**Severity:** P1 (blocking) - it corrupts the graph rather than failing cleanly, and `make
eval-world-reset` is documented as the way to establish a known-good world before a regeneration
**Where:** `demo_game/snapshot.py:139-170` (`do_restore`), reached via `make eval-world-reset`
**Description:** `do_restore` runs `MATCH (n) DETACH DELETE n` and then `CREATE`s each snapshot node
in a separate auto-commit transaction per node. The app's tick scheduler persists the game tick to
`:WorldState` (DEC-186), so a running engine writes to Neo4j continuously. If the scheduler
recreates `:WorldState {id:'world'}` between the wipe and that node's `CREATE`, the create violates
the uniqueness constraint:

    neo4j.exceptions.ConstraintError: {code: Neo.ClientError.Schema.ConstraintValidationFailed}
    {message: Node(70) already exists with label `WorldState` and property `id` = 'world'}

**The dangerous part is not the error, it is where it stops.** Because each node is its own
transaction, the wipe has already committed and 139 of the snapshot's 248 nodes have been created.
The process exits non-zero with the graph in a state that is neither the old world nor the baseline
- and nothing marks it as such. A caller that retried, or an operator who did not read the
traceback, would regenerate against a silently half-populated world. Measured directly after the
2026-08-19 22:19 failure: 139 nodes present, `WorldState.tick_id = 41`.

Not reproducible on demand: it depends on whether a scheduler tick lands inside the restore window
(~9 s). The same command succeeded earlier the same night when the app had been idle for 15 hours,
and failed once the app had just been restarted by `docker-compose up -d` in the same step.
**Ruled out:** the snapshot itself is fine - it holds two `:WorldState` nodes but with *distinct*
ids (`world`, `world_village`), so it does not self-collide.

**Why deferred:** the overnight run is unblocked by stopping the app around the restore, which
`project-harness/Run-OvernightCombined.ps1` now does (verified: 248 nodes, 233 relationships, exit
0, with the app stopped). Making `do_restore` itself safe is a change to shared demo tooling with
its own callers and tests, not an ops-script edit, and it should not be made at 22:00 in front of a
regeneration.
**To fix:** two things, and the second matters more than the first.
1. Run the wipe and all creates in ONE explicit transaction so a failure rolls back to the
   pre-restore graph instead of leaving a partial one. `session.execute_write` with a single work
   function; the per-node auto-commit loop is what makes the failure destructive.
2. Have `do_restore` refuse to run at all when a writer could be live - either take an explicit
   `--i-know-the-app-is-stopped` acknowledgement, or check for a recent `:WorldState.tick_id`
   advance and abort with a message naming the app container. A restore that can be silently
   corrupted by a background scheduler is a footgun regardless of transaction scope.
Consider also whether `make eval-world-reset` should stop and restart the app itself, so the
Makefile path and the ops-script path cannot diverge again.

**How it was fixed:**
1. `do_restore` now runs the wipe, every node create, every relationship create and the
   sentinel strip inside ONE `session.execute_write` work function, so any failure rolls the
   graph back to its pre-restore state. The per-node auto-commit loop is gone.
2. New `demo_game/restore_guard.py` fingerprints the graph (node count, relationship count,
   every `:WorldState` id/tick_id/last_updated_at), waits `SNAPSHOT_PROBE_SECONDS` (default 12,
   longer than the 10 s `TICK_INTERVAL_SECONDS`, so a live autopilot is caught with certainty,
   not by luck), and fingerprints again. Any difference aborts BEFORE the wipe with exit code 2
   and a message naming `docker compose stop app`. The probe was chosen over an
   `--i-know-the-app-is-stopped` flag because the flag is a checkbox anyone can tick while the
   app runs, and because `snapshot.py` executes inside the app image with no docker socket, so
   it can never stop the app itself - only detect and refuse (DEC-192).
3. `make demo-restore` and `make eval-world-reset` now delegate to a shared
   `restore-with-app-stopped` target that stops the app, restores, brings the app back up and
   waits on `/health` - matching what `Run-OvernightCombined.ps1` already does. The two paths
   can still be invoked separately, but the guard in shared Python is what makes divergence
   non-destructive.

## [FIXED] ISSUE-189: `make check` is red at HEAD on four gates, all in `evals/` and `tests/unit/`
**Fixed:** 2026-08-20, in the metrics-pipeline closeout task (DEC-193). `make check` now exits 0.
lint: E741 renamed. check-evals-rules: R001/R003 fixed by splitting `eval_records.py` and
`adjudicate.py` and replacing two swallowed excepts; 10x R006 + 2x R002 re-baselined with
justification (DEC-193 decision A). type-evals: all 28 errors fixed, baseline **ratcheted 16 -> 0**.
check-test-quality: 9 substantive findings fixed or verified-and-waived, 28 frozen-model
`pytest.raises(Exception)` waived (narrowing deferred as ISSUE-193). Two further failures that had
been HIDDEN behind the lint short-circuit surfaced and were fixed: the roadmap phase-span tripwires
had never been updated for `EVAL-P22B` (added 2026-08-18), and three `check_test_quality` meta-tests
pinned the unfixed state.
**Found:** 2026-08-20, while verifying the ISSUE-188 fix
**Severity:** P2 (annoying) - it hides regressions, because `make check` cannot be used as a
pass/fail gate until it is green again
**Where:** `evals/sequence_order_effect.py:81`, `evals/` (15 rule violations), `evals/` type
errors, `tests/unit/test_judge_runner.py` and 36 others
**Description:** on a clean tree at `bc6fe36`, before any change in the ISSUE-188 task, four of
`make check`'s gates already fail:
- `lint`: `E741 Ambiguous variable name: l` at `evals/sequence_order_effect.py:81`
- `check-evals-rules`: 15 NEW violations (R001 file length, R002 print(), R003, R006 function
  length) across `evals/adjudicate.py`, `evals/eval_records.py`, `evals/judge_run_artifacts.py`,
  `evals/sequence_rates.py`, `evals/summary.py` and others
- `type-evals`: 28 mypy errors against a baseline of 16
- `check-test-quality`: 37 issues
`lint` fails first, so the rest of `make check` never runs and the breakage is easy to miss.
The ISSUE-188 change touches only `Makefile` and `demo_game/`, none of which these gates scan;
`lint` covers `src/ evals/`, `type` covers `src/` (green, 610 files), and `check-test-quality`
reports zero `demo_game` items.
**Why deferred:** single-task focus - this is `evals/` debt accumulated across EVAL-P12.4 and
later phases, unrelated to the restore bug, and re-baselining or refactoring `evals/` in the
hour before a 10-hour regeneration run is exactly the wrong time.
**To fix:** fix `E741` (rename `l`), then work the `check-evals-rules` and `type-evals` deltas
down or re-baseline them with a DECISIONS.md justification, then the 37 `check-test-quality`
items. Do it as its own task, before the next phase that claims `make check` as its gate.

## [FIXED] ISSUE-187: two roadmap-cursor tests are red — `EVAL-P22B` breaks the contiguous-id invariant
**Found:** 2026-08-18, during the EVAL-P23 defect-repair session (`PROMPT_P23_UNBLOCK.md`)
**Fixed:** 2026-08-25 (verified); the repair landed in commit `dafae39`, which taught
`tests/unit/harness/test_roadmap_cursor.py` that `EVAL-P22B` is a real phase id via
`_EXPECTED_PHASE_IDS`. The entry was never archived at the time; both tests pass today
(21 passed) and `make check` is green.

**Severity:** P2 (annoying — two permanently red tests in `make test` mask a real cursor regression)
**Where:** `tests/unit/harness/test_roadmap_cursor.py:231` and `:329`, against
`project-harness/ROADMAP.md`'s `Phase EVAL-P22B` (added 2026-08-18 in commit `bdaa55b`)
**Description:** Both tests assert the queue's phase ids are exactly `[f"EVAL-P{n}" for n in
range(...)]` — a contiguous integer sequence. `EVAL-P22B` is a deliberate non-integer id (a phase
inserted *between* `EVAL-P22` and `EVAL-P23` without renumbering everything after it), so the
assertions fail at index 23: `'EVAL-P22B' != 'EVAL-P23'`. Verified pre-existing and unrelated to this
session's changes by stashing them and re-running: identical failures. The rest of the suite is green
(3536 passed, 1 skipped).
**Why deferred:** single-task focus — this session's task is the five `EVAL-P23` defect repairs, and
this is a harness-invariant question, not a bug in the code under repair. It also needs a real
decision rather than a mechanical fix: either suffixed phase ids are legitimate (and both assertions
must be taught to accept `EVAL-P<n><suffix>` while still catching a genuinely corrupted or reordered
queue), or they are not (and `EVAL-P22B` should be renumbered) — that is the roadmap owner's call.
**To fix:** decide whether suffixed ids are legal. If yes, relax both assertions to a
"non-decreasing, no-gaps in the integer part" check (keeping the tripwire's ability to catch a
reordered or truncated queue) and update the fence-state snapshot at `:329` deliberately, per that
test's own docstring. If no, renumber `EVAL-P22B` and update every reference to it (`ROADMAP.md`,
`PROMPT_P23_UNBLOCK.md`, DEC entries).

## [FIXED] ISSUE-198: `LLMConfig.resolve_weights` never returns the configured `relevance_weights`
**Found:** 2026-08-26, during the ISSUE-163 root-cause trace
**Severity:** P2 (annoying) — live config that silently is not live
**Where:** `schema/context_config_models.py:142-159` (`resolve_weights`), reached from
`context_scoring.rank_tier_items`
**Description:** `rank_tier_items` calls `resolve_weights(weight_profile or
llm_config.default_weight_profile)`, and `default_weight_profile` defaults to `"default"`.
`resolve_weights` looks `"default"` up in `weight_profiles` and then in
`DEFAULT_WEIGHT_PROFILES` — where it hits — and returns THAT. The `relevance_weights:` block
in `src/npc_engine/config/llm_config.yaml` is only reached when the profile name is falsy,
which never happens on the dialogue path. The two happen to hold identical values today, so
nothing is currently mis-scored; the hazard is that editing `relevance_weights:` in the YAML
changes nothing and the next weight experiment silently measures the old weights.
Found because `tests/unit/retrieval/test_context_scoring_phase6.py` builds `LLMConfig`s with
tailored `relevance_weights` that never take effect — those tests were passing on the
alphabetical tie-break in `rank_context_candidates`, not on the weights they declare.
**Why deferred:** single-task focus; it is latent, not active.
**To fix:** either drop `"default"` from `DEFAULT_WEIGHT_PROFILES` so the name falls through
to `relevance_weights`, or delete the top-level `relevance_weights` field and make the
default profile the only source. Then audit `test_context_scoring_phase6.py` — every config
there declares weights that are currently ignored.
**Fixed:** 2026-08-26, in P2 (DEC-201). `"default"` removed from `DEFAULT_WEIGHT_PROFILES`,
so the name falls through to the YAML `relevance_weights:` block. Zero behaviour change on
the shipped config — the two held identical numbers, verified live:
`cfg.resolve_weights(cfg.default_weight_profile) == cfg.relevance_weights` is True.
Regression tests: `test_the_default_profile_name_resolves_to_the_yaml_relevance_weights`,
`test_a_named_builtin_profile_still_resolves_to_its_builtin_weights` and
`test_a_yaml_weight_profile_overrides_a_builtin_of_the_same_name` in
`tests/unit/llm/test_llm_config.py`.
**Audit result — the phase6 tests did NOT go red.** The entry predicted they would.
Recomputed by hand and confirmed by run: `test_trust_score_boosts_low_priority_event`
(0.38 vs 0.59 under its declared weights, 0.21 vs 0.28 under the built-ins) and
`test_active_quest_boosts_item_referencing_giver` (1.0 vs 0.0, previously 0.28 vs 0.18)
happened to hold the same ORDER under both weight sets, so they now pass for the reason
they claim instead of by coincidence. `test_active_quest_none_falls_back_to_key_check` had
its `weight_profiles`/`default_weight_profile` workaround removed — it declares plain
`relevance_weights` again, which is the point of the fix.
**Residual, logged separately as ISSUE-203:** this does NOT make the dialogue path's weights
YAML-tunable. `detect_dialogue_profile` returns `rpg_dialogue_social`/`rpg_dialogue_quest`,
never `"default"`, so the block this fix unlocks is still not what dialogue resolves.
## [FIXED] ISSUE-199: `location:` and `relation:player` context items are 4.3x and 1.0x the entire prompt budget
**Found:** 2026-08-26, during the ISSUE-163 root-cause trace
**Severity:** P1 (blocking) — the NPC's location context reaches NO prompt, for any NPC
**Where:** `retrieval/graph_rag/subgraph_retriever.py:_location_items` and `_relation_item`;
readers `graph/graph_reader.get_location_context` / `get_npc_player_edge`
**Description:** measured token sizes of single tier-A items, against a 512-token TOTAL
prompt budget: `location:loc_tavern` **2188**, `location:loc_guard_barracks` **2191**,
`location:vw_village_square` **2191**, `relation:player` **500-505**. They rank at the very
top of tier A (priorities 998 and 997 after ranking) and are then skipped by every budget
pass, so the NPC never knows where it is standing beyond the location name folded into
`npc.profile`. `_character_item` already documents this exact failure mode for the character
node (RET-P0.5: `properties(c)` wholesale, including the 384-float embedding, measured at
2014 tokens) and strips `NON_PROMPT_NODE_FIELDS`; the location and relation readers were
never given the same treatment. This also accounts for `player_relation` being empty in
836/975 eval rows — it is populated only when `subgraph_retriever` emits the PINNED
priority-95 variant.
**Why deferred:** one root cause per fix (ISSUE-163). These items are skipped, not
truncating anything, so they are not the direct cause of the inner-life drop.
**To fix:** strip `NON_PROMPT_NODE_FIELDS` in `_location_items` and `_relation_item` the way
`_character_item` does, and project the location payload down to the fields a prompt can
use (name, kind, description) rather than the whole node. Re-measure with the 8-NPC probe.
**Escalated 2026-08-26 by P2 (DEC-201).** Now that the scorer reads array payloads, the NPC's
own state scores real recency and severity while `relation:player` scores severity 0.0 (it
carries no severity/urgency/confidence/emotional_charge field), so it lost the ranking and
`player_relation` measured **0/8** on the 8-NPC probe, down from at least 1/8. That is the
correct ordering — 505 of its ~505 tokens are a `delta_log` of six all-zero delta records —
but it means the player relationship now reaches NO prompt at all until this is fixed. In a
seeded world the values are all 0 so nothing is lost today; in a live game trust/fear/affection
would be silently absent. This raises P3 from a token-efficiency fix to a correctness one.
**Fixed:** 2026-08-26, in P3 (DEC-202). `NON_PROMPT_NODE_FIELDS` is now applied at every
assembly site instead of only `_character_item` and the tier-0 items, and `delta_log` was
added to the deny-list. Measured on the rebuilt image:

    item                       before    after
    location:loc_tavern         2188       45   tokens
    relation:player              505       21   tokens

    slot                      after P2  after P3
    npc.profile.current_location  0/8      8/8
    player_relation               0/8      6/8

`current_location` was 0/975 across the entire eval transcript and is now populated for
every NPC probed. Regression tests: `tests/unit/retrieval/test_context_payload_stripping.py`
-- `test_every_assembled_tier_a_item_is_free_of_non_prompt_fields` is one assertion over
every producer, so it also guards the site somebody adds next year.
**Deviation from the plan, deliberate:** the plan called for a named `_LOCATION_PROMPT_FIELDS`
projection on top of the strip ("stripping alone takes 2,188 -> ~180; projecting takes it to
~40"). Measured, the strip alone reaches **45 tokens**, because the only keys a Location node
carries are `id`, `name`, `descriptor`, `region`, `location_tag` plus the three stripped
bookkeeping fields. A projection would save roughly one token (`id`) at the cost of a
hand-maintained field list -- the exact churn P5's declaration table exists to remove. Not done.
## [FIXED] ISSUE-197: tier A is capped at 55% of the prompt budget and the unspent B/C share is never reclaimed
**Found:** 2026-08-26, during the ISSUE-163 root-cause trace
**Severity:** P1 (blocking) — it is the remaining half of the inner-life drop
**Where:** `retrieval/context/context_budget_enforcer.py:305-308` (`tier_a_soft_cap`) and
`:158-186` (`_fit_tier_a_pinned_pool`)
**Description:** `fill_to_budget` sizes tier A at `min(tier_budget_tokens.tier_a,
int(prompt_token_budget * tier_a_fraction))` = `min(4000, int(512 * 0.55))` = **281 tokens**,
then `_fit_tier_a_pinned_pool` spends the pinned items out of that same 281 and offers the
remainder to the ranked pool. Measured live on three NPCs (`what news`, no player):

    npc              pinned  remainder  tierA spend  tierB  tierC  TOTAL  budget
    mira_innkeeper      150        131          258      0      0    334     512
    captain_sorn        131        150          277      0      0    353     512
    vw_elder            127        154          242      0      0    318     512

Tiers B and C spend **zero** tokens on every one of them — the vector store returns nothing
for these queries — yet the 45% of the budget reserved for B and C is never handed back to
tier A. So 160-190 tokens of the prompt budget go unspent while `memories`, `beliefs`,
`secrets`, `believed_rumors` and `relation:player` are dropped for want of room. This is the
"353 tokens against a 512 budget" observation: it is not proof that the budget is innocent,
it is the fingerprint of this defect.
**Why deferred:** ISSUE-163 is one root cause per fix, and the ranking defect was the
higher-value half (beliefs 12.5% to 75% on its own). This one changes budget ALLOCATION and
interacts with the post-serialization trim loop at the end of `fill_to_budget`, which evicts
by ascending priority and can undo the gain — a prototype that reclaimed the leftover moved
`captain_sorn` from 1 goal to 0. It needs its own measurement pass, not a rider.
**To fix:** give tier A `prompt_token_budget - tier0 - (tokens B and C actually need,
capped at their soft caps)`, floored at the configured `tier_a_fraction` so a RAG-heavy turn
is unaffected. Then re-measure the 8-NPC probe; expect memories to become reachable for the
NPCs whose memory item is under ~200 tokens. Pair with ISSUE-199 — with the 2188-token
`location:` item fixed, the reclaimed budget buys proportionally more.
**Fixed:** 2026-08-26, in P4 (DEC-203). `_tier_a_cap_with_reclaim` sizes tier A at
`min(tier_budget_tokens.tier_a, max(fraction_floor, budget - tier0 - actual_b - actual_c))`.
The floor is what makes it safe: with B and C saturated the leftover is below the tier-A
fraction by exactly tier0, so the cap is bit-identical to the old one and the compressible
tiers lose nothing. Guarded by `test_tier_a_is_not_expanded_when_tiers_b_and_c_are_full` and
`test_a_saturated_tier_b_keeps_every_item_it_was_given`, both written before a corpus exists
to give the bug a symptom.

**The prototype regression this entry predicted has a different cause than it recorded.**
The entry blamed the post-serialization trim loop for "moving captain_sorn from 1 goal to 0".
It is not the trim loop -- it is `_fit_tier_a_pinned_pool` itself. Greedy-with-skip selection
is NOT monotone in the cap: with items [A=70, B=40, C=30] a cap of 100 selects {A, C} and a
cap of 110 selects {A, B}, so C fit at the smaller cap and does not at the larger one. No
serialization is involved. Pinned by
`test_raising_the_tier_a_cap_can_still_drop_an_item_that_previously_fit` and logged as
ISSUE-209; not fixed, because replacing greedy selection is ruled out by D2.

Measured live on the 8-NPC probe, `GET /v1/admin/debug/retrieval?query=what+news`:

    slot                          after P3   after P4
    npc.beliefs                      8/8        8/8
    npc.goals                        8/8        8/8
    npc.memories                     4/8        8/8
    npc.profile.current_location     8/8        8/8
    player_relation                  6/8        6/8
    nearby_npcs                      6/8        5/8
    assembled tokens               564-742    644-1156
## [FIXED] ISSUE-163: the NPC's own inner state is ranked below its surroundings and loses the tier-A budget
**Found:** 2026-08-14, during `RET-P0` (verifying the ISSUE-145 fix end to end).
**Rescoped:** 2026-08-26 — the original scope (memories only, `captain_sorn` only, three
candidate causes) was too narrow, and two of its three candidates are now falsified.
**Severity:** P1 (blocking) — every NPC in every world speaks without beliefs or memories.
**Where:** `retrieval/context/context_scoring.py:_infer_proximity_hops` (the ranking cause,
FIXED) and `retrieval/context/context_budget_enforcer.py:_fit_tier_a_pinned_pool` plus
`fill_to_budget`'s `tier_a_soft_cap` (the budget cause, still open as ISSUE-197).
**Measured scope (2026-08-26, live engine at 77688e7, 975-row transcript
`evals/generations/k3_77688e7_regen1/outputs.jsonl`):** `npc.beliefs`, `npc.memories` and
`npc.top_need` empty in 100% of rows; `npc.goals` empty in 76.7%; `npc.profile` populated in
100%. Not memories only, and not one NPC: reproduced on `mira_innkeeper`, `captain_sorn`,
`lira_fence`, `aldric_merchant`, `old_henryk`, `vw_elder`, `vw_farmer`, `tw_innkeeper`.

**Root cause (ranking half — FIXED 2026-08-26).** `_infer_proximity_hops` recognised
`character:`, `relation:`, `location:`, `nearby_npcs`, `event:`, `session` and `rag:`, and
returned `max_proximity_hops` (2) for everything else. `beliefs`, `goals`, `memories`,
`secrets`, `top_need` and the rest of the NPC's own state fell through to that default, so
`_proximity_score` scored them `1 - 2/2 = 0.0` — the score of a node at the graph horizon —
while `nearby_npcs` (strangers standing in the room, 1 hop) scored 0.5. With `proximity`
weighted 0.20 that is a flat 0.10-0.20 penalty, and it put the NPC's own state at the BOTTOM
of the ranked tier-A list. Live trace on `mira_innkeeper` before the fix:

    tierA pinned = [character:mira_innkeeper, session] = 150 tokens
    tier_a_soft_cap = min(4000, int(512 * 0.55)) = 281  ->  131 tokens left
    ranked non-pinned: relation:player(505) location:loc_tavern(2188) nearby_npcs(91)
                       event:0(17) event:1(54) memories(483) beliefs(130) goals(70)
                       secrets(106) believed_rumors(29)
    selected: nearby_npcs(91) + event:0(17) = 108  ->  23 tokens left
    dropped:  relation:player, location, event:1, memories, beliefs, goals, secrets, rumors

This explains the per-field pattern exactly, which is what pins it: `profile` is `character:`,
a PINNED item, so it never competes and always arrives; `goals` is the smallest inner-life
item (70-74 tokens) so it squeaks in for the NPCs whose pinned block is small enough
(`captain_sorn`, `vw_elder`); `beliefs` (130-145) and `memories` (213-483) never fit.

**Falsified candidates.** Both suspects named in the original entry are wrong, and the live
trace shows why: `get_memories_for_character` returns 3/2/2 rows for mira/sorn/vw_elder with
`vividness=0` intact, `rerank_by_keyword` returns 2 beliefs and 1 goal, and
`annotate_memory_ages` produces a 483-token `memories` ContextItem that is present in the
pre-budget merged context. There is no truthiness filter on `vividness` anywhere on the path,
and `PartialDialogueContextCache` is not involved (the debug endpoint passes no cache at all
and reproduces the drop). The rows survive every hop up to budget enforcement.
**Also disproven:** "353 tokens against a 512 budget, so nothing is trimmed for space." The
gap is not headroom — it is the fingerprint of the cause. Tier A is capped at 281 tokens
(55% of 512) and tiers B/C spend 0, so ~160 tokens of the prompt budget go unspent WHILE
tier-A items are being dropped. See ISSUE-197.

**Fixed:** 2026-08-26 (ranking half only, DEC-198). `NPC_SELF_STATE_KEYS` in
`retrieval/context/context_scoring.py` now maps the NPC's own state to
`SELF_STATE_PROXIMITY_HOPS = 0`. Regression test:
`tests/unit/retrieval/test_context_inner_life_reaches_prompt.py`.
Live `GET /v1/admin/debug/retrieval?query=what+news`, 8 NPCs, before -> after:

    npc.beliefs   1/8 (12.5%) -> 6/8 (75.0%)
    npc.goals     2/8 (25.0%) -> 1/8 (12.5%)
    npc.memories  0/8  (0.0%) -> 0/8  (0.0%)

**Still open — do not archive this entry.** Beliefs now win the 131-token remainder, but that
remainder is zero-sum: `captain_sorn` and `vw_elder` traded their goal for their beliefs, and
memories still cannot fit (a single `mira_innkeeper` memories item is 483 tokens against a
512-token prompt budget). The remaining work is ISSUE-197 (reclaim the unspent tier B/C
budget), with ISSUE-199 keeping the fat `location:` and `relation:player` items off the top
of the ranking.
**Fixed:** 2026-08-26, fully, across four phases. The entry above says "Still open -- do not
archive this entry" pending ISSUE-197 and ISSUE-199. Both have landed, and the field this
issue was opened about is now populated for every NPC probed.

    slot            77688e7    P1(window)  P2(scorer)  P3(strip)  P4(reclaim)
    npc.beliefs      0/975         3/8         8/8        8/8         8/8
    npc.goals      227/975         6/8         8/8        8/8         8/8
    npc.memories     0/975         3/8         4/8        4/8         8/8
    npc.top_need     0/975         0/8         0/8        0/8         0/8

Four independent causes, each sufficient on its own, each fixed with its own regression test:
DEC-198 (an NPC's own state scored at the graph horizon), DEC-199/P1 (the model was seeing
2,050 tokens of a 7,100-token prompt), DEC-201 (array payloads scored recency and severity
0.0), DEC-202 (the deny-list applied at two of seventeen sites), DEC-203 (45% of the budget
reserved for tiers that spend nothing).

**`npc.top_need` is NOT part of this issue and is not fixed.** It is 0/8 because the graph
contains zero `Need` nodes and zero `HAS_NEED` edges -- verified directly against Neo4j on
2026-08-26. No seeder creates them, so the field was never going to be populated by any
amount of retrieval work. Logged as ISSUE-210.

## [FIXED] ISSUE-200: eight assembled tier-A item kinds have no slot in the serialized skeleton
**Found:** 2026-08-26, during the ISSUE-163 root-cause trace
**Fixed:** 2026-08-26, in P6 (DEC-205)
**Severity:** P2 (annoying) — they spend prompt budget and then vanish
**Where:** `retrieval/context/context_serializer.py:serialize_context` (fixed skeleton) vs
`retrieval/context/context_builder.py:_build_tier_a_extended` and
`retrieval/graph_rag/subgraph_retriever.py`
**Description:** the serializer assembles a fixed skeleton from a known key list. Items keyed
`secrets`, `owned_items`, `obligations`, `believed_rumors`, `traits`, `group_memberships`,
`active_pledges` and `second_hop:*` are produced, ranked, and counted against the tier-A
budget — and then have nowhere to go in the skeleton, so they are silently discarded at
serialization. On `mira_innkeeper` that is `secrets` (106 tokens) and `believed_rumors` (29)
competing for the same 131 tokens as `beliefs` and `memories` while being incapable of
reaching the model. The reverse also holds: `propagated_reputation` is read from the mapping
in `serialize_context` but NO producer anywhere emits that key, so the slot is structurally
`[]` in 100% of rows — that is a dead slot, not a drop.
**Why deferred:** single-task focus; fixing it means deciding the prompt schema, which is a
prompt-contract change (`prompt_schema_version`), not a bug fix.
**To fix:** decide per key — either add a skeleton slot (and bump `prompt_schema_version`) or
stop assembling the item. Either way the budget stops being spent on invisible items. Delete
the `propagated_reputation` read or wire `get_propagated_reputation_for_npc` into
`_fetch_npc_profile_data`.

**How it was fixed.** All eleven keys are declared in `retrieval/context/context_slots.py`,
each with a skeleton path, and `context_serializer` is generated from that table -- so a
produced key can no longer be a key the serializer has never heard of. Split by outcome:

* `system_state` and `active_quest` are now SERIALIZED. Both were pinned (priority 97 and 89)
  and discarded, which is the sharpest form of this bug: the budget paid for them
  unconditionally and the model could never see them. `system_state_v1.yaml` Rule 17 had been
  teaching the model to read `system_state` the whole time, and Rule 11 told it to set
  `action.target_id` to "the quest_id" without ever supplying one.
* `propagated_reputation` -- the reverse case named in this entry, a slot read with no
  producer -- was wired to `get_propagated_reputation_for_npc`, which existed and was fully
  unit-tested with zero callers.
* `secrets`, `owned_items`, `obligations`, `believed_rumors`, `traits`, `group_memberships`,
  `active_pledges` and `second_hop:*` are declared with `default_enabled=False`, because no
  prompt rule teaches the model to read them, AND `_drop_withheld_items` now removes them
  before ranking so they no longer spend budget. Turning one on is one flag plus one prompt
  rule; the path is already written down.

**Measured:** tier-A items charged across the 8-NPC probe 88 -> 74, tier-A tokens charged
7605 -> 6914, i.e. **86 tok/NPC reclaimed**. The saving is in the tier's SPEND, not in the
prompt -- those items never reached the serialized output, which was the whole bug.

## [FIXED] ISSUE-206: two array-payload producers are ordered by a field the severity scorer does not read
**Found:** 2026-08-26, during the P2 code review (DEC-201)
**Fixed:** 2026-08-26, in P6 (DEC-205)
**Severity:** P3 (nice-to-fix) - an approximate score, not a wrong one; both items are sparse
**Where:** `retrieval/context/context_scoring.py:_payload_for_scoring` +
`_extract_severity_score`, against `graph/memory/memory_queries.py:47,74` and
`graph/political/pledge_queries.py:41` (via `retrieval/graph_rag/subgraph_retriever.py:129-134`)
**Description:** DEC-201 chose "score the FIRST record of an array payload", justified by the
producers ordering their rows by the very field `_extract_severity_score` reads. That holds for
`beliefs` (confidence), `goals` (urgency), `secrets` (severity) and `believed_rumors`
(confidence). It does NOT hold for two:
  - `memories` is `ORDER BY m.vividness DESC` but the fallback reads `emotional_charge`, so the
    representative is the most VIVID memory, not the most emotionally charged one. DEC-201
    states this explicitly and accepted it.
  - `active_pledges` is `ORDER BY e.sworn_at_tick DESC` and `_pledge_item` filters to active
    pledges without re-sorting, yet each record carries a `severity` field that
    `_extract_severity_score` checks FIRST. So the item's severity is that of the most recently
    sworn pledge, not the most severe one. This one was NOT in DEC-201's producer audit and was
    found by review afterwards - it looked unintentional, and it is the same class of gap.
Neither can produce a wrong ordering by much: both items are small, sparse, and the value read
is still a real severity-family number from a real record of the right kind.
**Why deferred:** P2 is scoped "minimal: fix the logged defects only", and closing this properly
means choosing between (a) re-sorting in the producer, which changes what the PROMPT shows, not
just what the scorer sees, and (b) a per-key "which field to maximise" table, which is exactly
the hand-maintained mapping P5's declaration table exists to delete. Doing it before P5 would
build the thing P5 removes.
**To fix:** prefer folding it into P5 - once `context_slots.py` declares each key, the severity
field is one more column on the row already being added, and `_payload_for_scoring` can take a
maximum over records using it. Regression test to add then: a two-record `active_pledges` array
with a low-severity recently-sworn pledge first and a high-severity older one second, asserting
the item scores the higher severity. The docstring on `_payload_for_scoring` carries the
alignment table so the gap is visible at the call site until then.

**How it was fixed.** Option (b) from "To fix", but without the hand-maintained mapping the
objection was about: `severity_field` is one more COLUMN on the CONTEXT_SLOTS row that was
being added anyway, so there is no second dict to keep in step.
`extract_severity_score_for_item` reads the declared field and takes its MAXIMUM across all
records, which removes the dependency on producer ordering rather than documenting it -- so
neither `memories` (ordered by vividness) nor `active_pledges` (ordered by sworn_at_tick) can
be misrepresented by its first row again. Magnitude not sign, so a negative
`emotional_charge` or `reputation_delta` counts like a positive one of the same size.

A slot that declares no field, or whose records do not carry it, falls back to the old chain:
a producer that stops emitting a field degrades instead of silently scoring the item zero.
The four already-aligned slots are pinned by test to score exactly as before -- this is a
fix, not a re-weighting. The suggested regression test exists verbatim:
`test_a_pledge_is_scored_on_severity_not_on_when_it_was_sworn`.

Recency still reads the FIRST record, deliberately: `rerank_by_keyword` has reordered beliefs,
goals and secrets by relevance to the player's message, so there the first record is a choice
something upstream made on purpose.

---

## [FIXED] ISSUE-211: P8's hydrator is specced to run before the only thing that writes embeddings
**Found:** 2026-08-27, during P6's eval-world re-seed (DEC-206)
**Severity:** P1 (blocking) — for P8 specifically; it would make that phase's deliverable
(`item_count > 0`) unreachable while looking like a data problem
**Where:** the P8 spec (`vector_store_hydrator.hydrate_once`, called from `main.py`), against
`retrieval/embedding/embedding_reconciler.py:run_forever` and
`evals/fixtures/eval_world_baseline.json`
**Description:** P8 says to call `hydrate_once()` **awaited, in `main.py`, before the
reconciler task**, reading `n.embedding` values "already persisted in Neo4j" with no
re-encode. Two facts make that read empty:

1. The checked-in eval-world baseline carries **no** `embedding` property on any node. DEC-206
   strips them deliberately — they are derived data, they tripled the fixture, and baking them
   in couples a world fixture to whatever `EMBEDDING_MODEL` produced them, which the
   reconciler cannot detect because it compares timestamps, not model identity.
2. `EmbeddingReconciler.run_forever` is the only thing that writes them, and it calls
   `reconcile_once()` BEFORE its first sleep — so embeddings exist a few seconds AFTER the
   reconciler task starts, which is strictly after the point P8 wants to read them.

So immediately after `make eval-world-reset`, a hydrator running at P8's specified point
reads zero rows and reports `nodes_read=0`. That failure looks exactly like "the world has no
embeddings yet", which is true but is a race, not a data problem — and P8's verification step
(`/v1/admin/debug/vector-store` → `item_count > 0`) would fail with no indication of why.

The ordering in the plan was not arbitrary: it exists because
`restore-with-app-stopped` waits only on `/health`, so a hydration running as a background
task would race the eval run. That constraint still holds; only the position relative to the
reconciler is wrong.
**Why deferred:** it is P8's decision to make, and P6 is scoped to the declaration table.
Logging it now so P8 does not spend the debugging time rediscovering it.
**DECIDED 2026-08-27 — see DEC-208.** The planning review found the cause is deeper than the
ordering: `EmbeddingIndex.upsert` has **zero callers in `src/`** and the reconciler writes
`n.embedding` in Neo4j only, so the vector store has never been written by any runtime path.
The hydrator is not a cache warm-up, it is the system's only insert path. Option (a) is taken
in a strengthened form — `ensure_corpus()` reconciles **until dry** (one `reconcile_once()`
caps at `batch_size=200` over an unordered `select_stale_nodes`, so a single sweep gives a
partial corpus in undefined row order once a world exceeds it) — and DEC-208 Decision 3 adds
`POST /v1/admin/vector-store/rehydrate`, which dissolves the `/health` constraint that forced
the bad ordering in the first place. (b) rejected: two independent implementations of the
embedding text. (c) rejected for now, but DEC-211 removes its stated objection.
**To fix:** land DEC-208 in P8. Close this entry then, not before.
**Fixed:** 2026-08-27, in P8 (commits 94bce50, 0859910, 5da3345, 38b8a6a, 3bc2aad).
DEC-208 landed in full: `retrieval/embedding/corpus.py::ensure_corpus` is the single
owner, it reconciles UNTIL DRY, and `EmbeddingReconciler.run_forever`, the boot lifespan
and the new `POST /v1/admin/vector-store/rehydrate` all call the same function. Boot
hydration fails loud at ERROR on `nodes_read == 0`.

MEASURED on the clean eval baseline after `make eval-world-reset`:
`nodes_read=51, upserted=51, missing_embedding=0, reconcile_passes=1, item_count=51,
corpus_sha=2b19e47a1755...` — 51 is exactly the count DEC-208 predicted (23 Character +
11 Event + 17 Location). The boot sweep took ~11s against `make`'s 180s /health wait, so
`HYDRATE_ON_STARTUP=true` is comfortable today and the fallback posture was not needed.
`POST rehydrate` on an already-embedded corpus returns in 45ms and reproduces the same
`corpus_sha`, which is what makes the P9 fingerprint gate meaningful.

The ordering this issue was filed about turned out not to need solving: DEC-208 Decision
3's route dissolves the `/health` constraint that forced it.

## [FIXED] ISSUE-216: the 8-NPC inner-life probe lives in a session-scoped temp directory
**Found:** 2026-08-27, during P8 §8.6 verification
**Fixed:** 2026-08-27, in 7daf7a1 (P9) — landed as `scripts/probe_inner_life.py` with a
`make probe-inner-life` target and `tests/unit/scripts/test_probe_inner_life.py` pinning
the parse against a recorded response. The deferral reasoning held exactly: P9 gave the
debug route its `player_id`, so the committed probe reports the three reputation slots
that were structurally invisible before. And the prediction that a rebuilt instrument is
not the same instrument was confirmed once more during the rewrite — it read
`npc.current_location` instead of `npc.profile.current_location` and reported a false 0/8
against DEC-212's recorded 8/8, caught only by comparing to the recorded number. That is
the second wrong rebuild, and it is why the parse is now pinned by test.
**Severity:** P3 (nice-to-fix - costs a rewrite every session, and a rewritten instrument
is a changed instrument)
**Where:** `<scratchpad>/probe8.py`, referenced by the plan's verification block as
`python <scratchpad>/probe8.py "label"`
**Description:** every number in the P0-P8 headline - "beliefs 8/8, goals 8/8, memories
8/8, current_location 8/8, was 0/975" - comes from this probe, and the probe is not in the
repo. Each session's scratchpad is a new directory, so it has to be rewritten from the
plan's description; it was rewritten in this session, and the reconstruction initially
parsed the wrong response shape and reported a false 0/8 across the board before being
corrected. A measuring instrument that is rebuilt from prose before each use is not the
same instrument twice, which makes cross-phase comparisons weaker than they read.

This is exactly the defect class DEC-211 Decision 3 just fixed for `strip_derived.py`,
which had the same problem for the same reason.
**Why deferred:** P9 changes this probe's contract anyway - review point 1 requires it to
take `player_id`, `retrieval_profile`, session turns and cache parameters, because without
`player_id` the probe matches reputation queries against `""` and cannot observe
`propagated_reputation`, `reputation` or `player_relation` at all. Committing today's
version would commit the version P9 is about to replace.
**To fix:** with P9's debug-endpoint work, land the probe as `scripts/probe_inner_life.py`
with a `make probe-inner-life` target, taking the NPC list and the label as arguments.
Pin its output shape with a unit test against a recorded response fixture, so a change to
the debug endpoint breaks the probe loudly instead of silently reporting zeros.

## [FIXED] ISSUE-217: `rag_top_k` is saturated at its default, so no top-k arm can produce an effect
**Found:** 2026-08-27, during P9 gate 4 (DEC-213)
**Fixed:** 2026-08-27, in commit 4661c3c (P9 remediation, DEC-214)
**Severity:** P2 (annoying) - blocks every tier-B top-k A/B arm; nothing is wrong at runtime
**Where:** `src/npc_engine/config/llm_config.yaml` (`wide_rag`), the interaction of
`retrieval/context/context_builder.py:_fetch_rag_results` with the corpus contents
**Description:** the vector search's candidate set is the DEC-209 scope, minus known
events, INTERSECTED WITH THE CORPUS. The corpus holds 51 nodes of the three embeddable
types (Character, Event, Location), so the intersection is small even though the scopes
are not:

    npc              scope   scope-known   IN CORPUS
    captain_sorn       124           123           6
    old_henryk          14            13           4
    mira_innkeeper      17            15           6
    lira_fence          23            21           8
    bren_smith          12            12           3

Default `rag_top_k` is **5**. So raising it to 15 can add at most `supply - 5` items —
measured as exactly **1** for captain_sorn (`rag:bren_smith`) and **0** for old_henryk.
`wide_rag` therefore differs from default on 1 of 2 probe cases, by one item.

This is not a defect in the scope, the corpus or the arm. It is the arms-race arithmetic:
the knob's ceiling is below its own default on most NPCs, so the knob cannot move.
**Consequence:** a paired generation of `wide_rag` would spend hours to measure a ~4.7%
context change on a minority of NPCs, against a 26-33pp judge floor (DEC-213's MDE).
**Why deferred:** the remedies are all larger than P9 and all belong to a phase that is
allowed to change the substrate. Raising the corpus's node-type coverage changes
`corpus_sha` and therefore comparability (DEC-210); widening the scope re-opens DEC-209;
lowering the DEFAULT `rag_top_k` so the arm has headroom is a default-path engine change,
which P9's own fence forbids after the gates run.
**To fix:** pick one, in P10 or later. (a) Lower the default `rag_top_k` to 2-3 so
`wide_rag` at 15 has real headroom — cheapest, and it also makes the default honest about
what it can supply. (b) Broaden the embeddable node types so the corpus is larger than the
scope intersection. (c) Retire top-k as an A/B dimension on this world and keep `no_rag`
as the only retrieval arm. Whichever is chosen, re-run `make eval-arm-probe` — it prints
the supply per case, which is the number that decides this.

## [FIXED] ISSUE-218: the `wide_events` arm has structurally zero exposure on the eval world
**Found:** 2026-08-27, during P9 gate 4 (DEC-213)
**Fixed:** 2026-08-27, in commit 4661c3c (P9 remediation, DEC-214)
**Severity:** P2 (annoying) - a declared arm that cannot produce a result
**Where:** `src/npc_engine/config/llm_config.yaml` (`wide_events`)
**Description:** `events_limit` bounds `get_events_for_npc`, which returns the events the
NPC actually KNOWS_ABOUT. Measured on the eval baseline, **every NPC knows <= 2 events**
against a default limit of 5. Raising the limit to 15 cannot add a row that does not
exist, so the arm's `item_keys` are IDENTICAL to default on 2/2 probe cases and
`make eval-arm-probe` exits non-zero because of it.

The arm is correctly declared and correctly single-tier — P9 split it out of `wide_rag`
precisely so a tier-A knob would not be confounded with a tier-B one. The problem is the
WORLD, not the arm, and the distinction matters: this is "there was nothing to take", not
"the arm did nothing". The arm probe now prints the supply on failure so the two cannot be
confused.
**Why deferred:** the fix is either to seed NPCs who know more than 5 events — which
regenerates `evals/fixtures/eval_world_baseline.json`, explicitly forbidden between P8 and
P10 — or to drop the arm, which is a decision about what P10 measures and belongs with
whoever schedules P10.
**To fix:** EITHER drop `wide_events` from the declared arms (and from `_DECLARED_ARMS` in
`tests/unit/config/test_shipped_retrieval_profiles.py`), which also returns the Bonferroni
correction to two pairings and the MDE floor from 7.4pp to ~6.9pp; OR seed an NPC with
>5 KNOWS_ABOUT edges when the baseline fixture is next legitimately regenerated (after
P10, alongside ISSUE-213). Do NOT "fix" it by weakening gate 4.

## [FIXED] ISSUE-227: `/setup/*` is unauthenticated off-box because compose binds 0.0.0.0
**Found:** 2026-08-28, during the 2026-08 review remediation triage
**Fixed:** 2026-08-28, R0.1 — loopback bind + `env == "dev"` exemption gate + `config_dir` removed. Superseded DEC-131; see DEC-231.
**Severity:** P1 (blocking)
**Where:** `auth/middleware_helpers.py:51`, `docker-compose.yml:72`, `api/routes/setup/setup.py:94`
**Description:** The `/setup/*` auth exemption is unconditional in every environment. DEC-131
justifies it by a 127.0.0.1 bind, but `docker-compose.yml:72` publishes `"8000:8000"`, which binds
0.0.0.0. `GET /setup/config` returns a wizard config that DEC-131 documents as storing a plaintext
cloud API key. `POST /setup/config` accepts a schema-hidden `config_dir` query param that `mkdir -p`s
and writes as root. Re-verified live at HEAD `619dab2` on 2026-08-28: the bind and the unconditional
exemption are both still present. Three individually sound decisions composing into one unsafe
outcome — the review's C5 pattern.
**Why deferred:** not deferred. It is R0.1, ahead of the whole remediation program.
**To fix:** bind `127.0.0.1:8000:8000`; gate the exemption on `env == "dev"` as `/docs` already is;
drop or whitelist `config_dir`; supersede DEC-131. Rotate the key if port 8000 was ever reachable
off-box. Proof: `test_setup_config_requires_auth_outside_dev` — `ENV=staging`, no key, expect 401;
today returns 200 with the config body.

## [FIXED] ISSUE-232: Neo4j publishes no host ports, so integration tests cannot run locally
**Found:** 2026-08-28, capturing the pre-remediation baseline
**Fixed:** 2026-08-28, R0.2 — `docker-compose.test.yml` override. The proposed `ports:` line on the base file was silently inert (`internal: true` network); see DEC-232.
**Severity:** P1 (blocking) — blocks the acceptance tests for R3.2 and R3.3
**Where:** `docker-compose.yml` (the `neo4j` service has no `ports:` stanza)
**Description:** The `neo4j` service is healthy and reachable inside the compose network — 
`docker compose exec neo4j cypher-shell "RETURN 1"` returns ok, and `app` holds
`NEO4J_URI=bolt://neo4j:7687` — but it publishes nothing to the host (`docker port <neo4j>`
returns empty). A host-run `pytest tests/integration` therefore cannot connect:
**34 failed, 9 passed, 5 errors in 273 s**, every failure
`neo4j.exceptions.ServiceUnavailable: Couldn't connect to localhost:7687 … the remote computer
refused the network connection`.

This is the mechanism behind the review's "9 passed, 34 skipped" observation (CR-L14-02): those
34 tests have never run for anyone on a host shell, and the skip made that invisible. Note this
is **not** 34 product defects — it is one missing port mapping. The tests were not evaluated.
**Why deferred:** it is a `docker-compose.yml` change (config), and it was found during a
planning session that deliberately made no source or config changes.
**To fix:** add `ports: ["127.0.0.1:7687:7687"]` to the `neo4j` service — loopback-bound, so it
does not repeat ISSUE-227's mistake of publishing on 0.0.0.0. Then re-run
`pytest tests/integration` and record the real pass/fail split, which is currently unknown.
Until this lands, the Proofs for R3.2 (`test_neo4j_outage_returns_503`) and R3.3
(`test_distortion_compounds_across_hops`) cannot be executed locally, and R2.2's CI work is
sequencing against an unmeasured baseline.

## [FIXED] ISSUE-231: "unit" tests make live network calls, and CI silently records `None` model digests
**Found:** 2026-08-28, during the 2026-08 review remediation triage
**Fixed:** 2026-08-31, in R2.1 (`fix(evals): block network in unit tests; a missing model
digest is now fatal`)
**Severity:** P1 (blocking)
**Where:** `evals/run_config.py:260-262`, `evals/engine_adapter.py:111-125`,
`tests/unit/evals/test_run_config.py`
**Description:** `run_config.resolve()` falls back to `_engine_adapter.fetch_model_digest` (twice)
and `fetch_ollama_version` when no injector is passed; each is a real `httpx` call with a 10 s
timeout. Only 2 of 17 tests in the cited file inject fakes, so 15 make three live HTTP attempts each
— the file times out at **120 s** while collection takes 0.07 s. The worse half: both fetchers are
documented to return `None` on any failure, and CI declares no Ollama service, so on a runner the
connection is refused instantly, the tests **pass**, and the run records
`generation_model_digest=None`. That is the only field making eval scores attributable to a model,
which makes it load-bearing for the planned swap to a smaller fine-tuned local model.
**Why deferred:** not deferred; it is R2.1, the first item of the measurement phase.
**To fix:** require the injector under `tests/unit/` via an autouse fixture that raises on real
`httpx` use, and make a `None` digest fatal in any run that publishes a number. Proof: the cited file
completes in under 5 s with no network (today >120 s), and `resolve()` raises when the digest fn
returns `None` (today returns a RunConfig with `None`).
**Verified:** `tests/unit/evals/test_run_config.py` 152.38 s -> 1.54 s; `resolve_run_config` raises `ModelDigestUnavailableError` on a `None` digest, pinned by two
permanent tests. The block is repo-wide under `tests/unit/` via a socket patch in
`tests/unit/conftest.py`, not an httpx patch — `httpx` is imported lazily in three separate
function bodies in `engine_adapter.py`. Two further files (`test_run_config_corpus_fingerprint.py`,
`test_generate_runner_k.py`) also resolved with absent digests and were fixed in the same commit.
The CI half of the title is R2.2, which is blocked on credentials and CI-config approval.

## [FIXED] ISSUE-236: two different integration-failure baselines are recorded
**Found:** 2026-08-31, during R2 planning
**Severity:** P2 (annoying) — R3.6 would inherit a wrong denominator
**Where:** project-harness/ISSUES.md (ISSUE-233) vs project-harness/.loop-state/gate_baseline.json
**Description:** ISSUE-233 lists nine failing integration tests; gate_baseline.json records
eight. The lists differ by exactly
`test_faction_integration.py::test_set_standing_independent_directions`. Neither has been
re-run since 2026-08-28 and Neo4j was not running during this planning session, so which
is current is unknown.
**Why deferred:** R2 fixes none of these (that is R3.6) and no R2 task attributes any
measurement to integration counts. Settling it needs the stack up.
**To fix:** bring up `docker compose -f docker-compose.yml -f docker-compose.test.yml`,
run `NEO4J_URI=bolt://localhost:7687 python -m pytest tests/integration`, record the real
list, and correct whichever file is stale. Do this as R3.6's first step.
**Fixed:** 2026-09-01, in R2.2 commit 2 (`ci: add neo4j; stop skipping the integration suite`).
**Resolution:** measured against a live `neo4j:5` brought up with the compose override —
`35 passed, 8 failed, 0 skipped` in 109 s. **`gate_baseline.json`'s 8 was correct; ISSUE-233's
9 was stale.** The difference, `test_faction_integration.py::test_set_standing_independent_directions`,
passes. ISSUE-233 has been narrowed to the real 8, and those 8 are now the committed
allowlist in `scripts/integration_baseline.txt`, enforced by `make check-integration-baseline`.
R3.6 inherits a denominator that was measured rather than assumed.

## [FIXED] ISSUE-145: dialogue retrieval returns an empty NPC profile for every NPC
**Fixed:** 2026-09-01, in R4.5 (ledger hygiene). Closed as superseded, not re-fixed.
Every cause this entry names is resolved elsewhere: the `profile: {}` and empty `npc_known_events`
half was fixed and verified at RET-P0; the empty `beliefs`/`goals` are not a defect (the demo seed
has no `HOLDS_BELIEF`/`HAS_GOAL` edges); the `memories` half was root-caused and `[FIXED]` as
ISSUE-163, with a further cause `[FIXED]` as ISSUE-197. The fix is live in
`context_score_extractors.py:228` (`NPC_SELF_STATE_KEYS`) and `context_budget_enforcer.py:207,360,464`,
and pinned by `tests/unit/retrieval/test_context_budget_starvation.py` — 6 tests, all passing on
2026-09-01, whose acceptance shape asserts profile, memories, beliefs and goals all survive budget
enforcement. CR-L07-01 asked for exactly this re-verification before closing.
**Found:** 2026-08-10, during EVAL-P20.2 (capability case authoring)
**Severity:** P1 (blocking) — FOR HAND REVIEW. The data exists; the reader does not return it.
**Where:** retrieval context assembly; observed via `GET /v1/admin/debug/retrieval`
**Description:** The `npc` context item is empty for **every** NPC tested — the five core
demo NPCs and all nine H2.2/EXP-223 NPCs alike:

```
GET /v1/admin/debug/retrieval?npc_id=bren_smith&query=Is+the+forge+doing+all+right
  {"beliefs": [], "emotion": {...}, "goals": [], "memories": [], "profile": {}, "top_need": null}
  npc_known_events: []
```

Identical for `mira_innkeeper`, `captain_sorn`, `aldric_merchant`, `vex_spymaster`,
`sera_barmaid`: `beliefs=0 goals=0 memories=0 profile_keys=[] events=0`. `captain_sorn`
holds a *direct* `KNOWS_ABOUT northern_war_begins` edge and it does not reach the prompt.

**The data is present.** The typed admin readers return it correctly:
`GET /v1/admin/beliefs/bren_smith` returns 2 beliefs, `/goals/` returns 1, `/memories/`
returns 2, `/secrets/` returns 1, all with the stable seeded ids. So this is a defect in
the retrieval path or in the debug endpoint's stack, not in the seed and not in the graph.

**Consequences, both measured 2026-08-10:**
- The nine EVAL-P20.2 capability cases score **2/9** live. Every failing response is
  generic boilerplate — `bren_smith`, asked about his own forge, answers "I've heard the
  blacksmiths are struggling a bit this spring", speaking of blacksmiths in the third
  person because his profile never reached the prompt.
- The seven shipped capability cases score **6/6** live, but for the wrong reason: every
  response is a variant of "Word travels fast around here, stranger... the northern war
  rages on" and passes only because its `keyword_any` list contains `war`/`north`/`heard`.
  `captain_sorn`, whose case exists to prove he answers *without* hedging, replies
  "I've heard word of skirmishes, but nothing too serious" — hedged gossip — and passes.
  **The current capability rate is an artifact of keyword overlap, not evidence of grounding.**

**Why deferred:** EVAL-P20.2 is a case-authoring task; this is an engine/retrieval defect
of unknown depth, and the human who owns the roadmap asked to review it by hand rather
than have it fixed inside this commit.
**To fix:** Determine whether the fault is in the retrieval reader, the context builder,
or only in `/v1/admin/debug/retrieval`'s stack — the live dialogue responses corroborate
the debug output, so a debug-only fault is unlikely but is the cheapest thing to rule out.
Then re-run `make hedge-probe` and the nine cases live; the capability rate is not
interpretable until this is closed.

## [FIXED] ISSUE-122: `app` service has no restart policy — startup race vs Neo4j leaves the API permanently dead
**Fixed:** 2026-09-01, in R4.5 (ledger hygiene). Closed as already-satisfied.
`docker-compose.yml`'s `app` service now carries both remedies this entry prescribes:
`restart: on-failure:5` and `depends_on: neo4j: condition: service_healthy`. Verified against
HEAD on 2026-09-01.
**Found:** 2026-06-25, while debugging DemoGame dialogue (engine appeared unreachable from the game)
**Severity:** P2 (annoying — silently kills the whole API until a manual restart; high-confusion failure mode)
**Where:** `docker-compose.yml` — `app` service
**Description:** `npcsystem-app-1` exited (code 3) during FastAPI lifespan startup: `ensure_core_constraints`
(`src/npc_engine/graph/schema_bootstrap.py:70`) opened a Neo4j session before Neo4j was accepting Bolt
connections, raising `neo4j.exceptions.ServiceUnavailable: Couldn't connect to neo4j:7687 ... [Errno 111]`
→ `Application startup failed. Exiting.`. Neo4j became healthy ~seconds later, but with **no `restart` policy**
on the `app` service the container stayed dead. Result: port 8000 was never published and every client call
connection-failed (`status -1`). From the DemoGame side this masqueraded as "the LLM is untied from dialogue"
— the game was healthy; the API was simply down. A plain `docker compose up -d app` (which waits for
neo4j-healthy) recovered it cleanly, confirming the only fault was the unguarded startup race + no auto-restart.
**Why deferred:** User asked to log only, not implement. The immediate incident is resolved (container restarted,
`/health` → 200). Recurs on any cold start where the app wins the race against Neo4j.
**To fix:** On the `app` service in `docker-compose.yml`: (1) add `restart: on-failure` (or `unless-stopped`)
so a lost startup race self-heals; and/or (2) ensure `depends_on: { neo4j: { condition: service_healthy } }`
so the app never starts before Neo4j's healthcheck passes. Belt-and-suspenders: a short retry/backoff loop
around `ensure_core_constraints` in `lifespan` (`src/npc_engine/main.py:124`) so a transient Bolt blip doesn't
abort startup. Verify the Neo4j service actually defines a `healthcheck` for option (2) to be meaningful.

## [FIXED] ISSUE-253: `RECORDED_BASE_RATE = 0.951` reproduces against no population
**Fixed:** 2026-09-01, in R2.6c follow-up. Provenance found: 0.951 was NOT invented —
it is exactly 328/345, the rate in `judged.jsonl.pre-panel-20260817_192458.bak`. The panel
re-judge of 2026-08-18 flipped one record to 329/345 = 0.9536 and the constant was never
updated. Corrected to 0.9536, the corpus named as `mde.KAPPA_GENERATION`, and bound to it by
`tests/unit/evals/test_base_rate_matches_its_corpus.py` so the same drift now reds `make check`.
`verdict_sources.judged_rows()` was added as the public accessor for the judge-verdict
population, which is what a kappa and its base rate are defined over.
**Found:** 2026-09-01, during R2.6c / DEC-240 (kappa reconciliation)
**Severity:** P2 (annoying) — a published sanity bound that no measurement supports
**Where:** `evals/mde.py:87`, quoted by `evals/arm_probe_report.py:94,96,119-120`
**Description:** `mde.py` records a pass base rate of 0.951, attributed to ISSUE-184 over "the 345
records ISSUE-184 measured kappa on". Measured 2026-09-01, no available population yields it:

| Population | Rate |
|---|---|
| `judged.jsonl` of `k3_77688e7_regen1` (345 rows, 321 pass) | 0.9304 |
| calibration labels, human verdicts (359 of 393) | 0.9135 |
| `check-base-rate` overall | 0.9426 |
| **recorded in `mde.py:87`** | **0.951** |

The 345-row coincidence suggests it was meant to be the first, but 0.9304 ≠ 0.951.
`arm_probe_report` prints it as fact and derives an independence bound
`2p(1-p)` from it, which shifts from 9.32% (at 0.951) to 12.96% (at 0.9304) — the bound p_d is
checked against, so this is not purely cosmetic.
**Why deferred:** it does **not** enter the MDE arithmetic — `RECORDED_BASE_RATE` appears exactly
twice in `mde.py`, at its definition and in `__all__`, and neither `observed_mde` nor
`arm_pairing_mde` reads it. So it did not block DEC-240's kappa correction. Choosing which
population it should describe is a judgment call about what the bound is for, and belongs with the
R2.6f sizing decision rather than inside a kappa fix.
**To fix:** decide which population the independence bound should be taken over, re-measure it
there, and derive it in code from that population rather than hardcoding it — the same treatment
DEC-240 gave the kappas.

## [FIXED] ISSUE-254: `RECORDED_GUARD_N = 78` is the pre-R2.6b collapsed denominator
**Fixed:** 2026-09-01, in R2.6c follow-up. Resolved as documentation, not a value change:
the pairing unit is a CASE, so 78 is correct and its resemblance to the stale `guard_turns`
is a coincidence. Three repetitions of one case share a prompt, an NPC and a seed — the
intra-case correlation `battery_rates` already measures as `rho`. Pinned by
`tests/unit/evals/test_guard_pairing_unit.py`, which asserts it equals `guard_cases` and
differs from `guard_turns`, so a future reader cannot 'correct' it to 234.
**Found:** 2026-09-01, during R2.6c / DEC-240
**Severity:** P2 (annoying) — the MDE model is sized on a number the join fix corrected
**Where:** `evals/mde.py:84`
**Description:** `RECORDED_GUARD_N = 78` is the guard denominator as it read before R2.6b fixed
`load_unified_rows`. That 78 was an artifact: the join deduplicated by `record_id` alone and
collapsed all k repetitions to one, so a k=3 generation reported 78 where it has **234** guard
turns over **78** guard cases. The MDE model consumes it as `n_pairs`, and MDE scales as
`1/sqrt(n)`.

The correction is not simply 78 → 234, which is why this is filed rather than fixed:
`implied_discordance_rate` derives `p_d` from the recorded floor **at the recorded n**, so raising
n raises the implied p_d in step and `observed_mde` returns 6.4pp either way. What actually changes
is `required_pairs_for`, and whether a "pair" is a repetition or a case — a paired design over
k-repeated cases has 78 independent units, not 234, which is exactly the intra-case correlation
`battery_rates` already corrects for via its design effect.
**Why deferred:** answering it means deciding the pairing unit for the arm-probe design, which is
the R2.6f sizing question. Changing n inside a kappa-reconciliation commit would also mix two
causes into one attribution.
**To fix:** decide whether the arm pairing is per-case (78) or per-repetition (234, needing the
design-effect correction `battery_rates.compute_battery_rate` already computes as `n_eff`), then
derive `RECORDED_GUARD_N` from the generation rather than hardcoding it.

## [FIXED] ISSUE-245: `base_rate_baseline.json` records no `n`, so a shrinking corpus passes the ratchet
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Fixed:** 2026-09-01, in the B4 commit (`overall_n` added to BaseRateBaseline)
**Severity:** P2 (annoying)
**Where:** `scripts/base_rate_baseline.json`, `scripts/base_rate_contract.py:124-141`
**Description:** The persisted baseline has exactly three keys — `gen_dir`, `overall_rate`,
`breaches`. The n=975 that DEC-236 quotes lives only in that prose. Because the ratchet compares
a rate and a breach map but never a denominator, a corpus that shrinks while holding the same
rate passes undetected. (`FamilyRate` does carry an `n`, but that is the per-family measurement
type, not the persisted baseline.)
**Why deferred:** adding the field changes the baseline file, which is a deliberate human
re-record step; it belongs with R2.6's case-existence filter, which re-records anyway.
**To fix:** add `n` to the baseline model and file, and assert it does not fall without a
deliberate `make check-base-rate-update`.

## [FIXED] ISSUE-247: `evals/reports/` is gitignored, so every published report is machine-local
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Fixed:** 2026-09-01, in the B5 commit (DEC-241, `make check-cited-reports`)
**Severity:** P2 (annoying)
**Where:** `.gitignore:26`
**Description:** `git ls-files evals/reports/` returns nothing; `git check-ignore -v` confirms
`evals/reports/20260825T231028Z.md` — the artifact publishing `170/186 ... 0.914`, cited as the
source of record by `BASELINE_2026-08-28.md:93`, `FINDINGS.md:55`, `FIX_PLANS.md` and
`TRIAGE.md` — exists on one machine only and is one `git clean -xdf` from gone. DEC-158 extended
tracking to `evals/generations/` and `evals/calibration/` for exactly this reason
(`.gitignore:28`: "every quoted rate rested on files that existed on one machine only") but the
reports that *quote* those generations were never brought in. It also means R2.5's planned
retraction banner would not appear in any diff or survive a fresh clone.
**Why deferred:** not deferred; it is R2.5(e), decided 2026-08-31 — remove the ignore line,
commit the reports, then banner the retracted one.
**To fix:** as above, plus a DECISIONS entry recording the extension of DEC-158's reasoning.

## [FIXED] ISSUE-243: `evals/runner.py` guard prefixes do not mirror `summary.py`, so `ah_demo_*` cases are counted but not guarded

> **Corrected 2026-09-01 (R2.6b), measured.** The title and the fix this entry implies are both
> wrong, though the problem it points at is real. Three measurements against
> `evals/generations/k3_77688e7_regen1`:
>
> 1. **`ah_demo_*` cases are not unguarded.** They carry `refusal_judge` (75 rows) and
>    `anti_hallucination_grounded` (48) — purpose-built anti-hallucination expectations. What they
>    do not carry are the YAML battery's `tone_judge`/`affirms_judge`/`schema`/`keyword_none`/
>    `min_length`. Two grading contracts, not one contract with a gap.
> 2. **Aligning the two tuples would be a no-op.** `runner._load_cases` globs `*.yaml`
>    (`runner.py:128`); every `ah_demo_*` case lives in `evals/cases/anti_hallucination_demo.json`
>    and is loaded by `anti_hallucination_runner`. The runner cannot see them however its guard
>    tuple is spelled — and if it ever could, injecting `min_length` into a refusal-graded case
>    would score a correct short refusal as a guard failure.
> 3. **`summary._GUARD_PREFIXES` does not exist.** `runner.py:37`'s comment claimed to mirror it;
>    the canonical publishing tuple is `case_stats._GUARD_PREFIXES`. That false reference was the
>    trap — it invited exactly the no-op fix above. Corrected in R2.6b and pinned by
>    `tests/unit/evals/test_guard_prefix_scopes.py`.
>
> **The real defect, restated:** the published guard headline aggregates two populations scored by
> different expectation sets. Measured after the R2.6b join fix: YAML guard **0.8468** (n=111),
> `ah_demo_` **0.9106** (n=123), combined **0.8803** (n=234). The easier-scored battery is more
> than half the denominator and lifts the headline ~3.4pp above the adversarial battery alone.
> Whether to split the headline is a publication decision and belongs to **R2.5**, which owns the
> retraction; it is not a tuple to align here. Nothing was changed in the scoring path.

**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Fixed:** 2026-09-01, in the R2.5 split commit (DEC-243). NOT by the prefix alignment
this entry proposed — that was measured as a no-op. The headline splits instead.
**Severity:** P1 (blocking) — it makes the published guard rate a mixed population
**Where:** `evals/runner.py:37-38` vs `evals/case_stats.py:43` and `evals/summary.py`
**Description:** `runner.py:38` sets `_GUARD_PREFIXES = ("case_adv_", "case_neg_")` under a
comment that reads "mirror summary._GUARD_PREFIXES". It does not mirror it. `case_stats.py:43`
and `summary.py` both use three prefixes, adding `ah_demo_`, and the published headline is
`Guard (adv + neg + ah_demo_*) | 170/186`. Because `_expected_with_guards` keys off runner's
two-prefix tuple, `ah_demo_*` cases contribute to the published guard rate while receiving
**none** of the four injected guard expectations (`min_length`, the fallback `keyword_none`,
`tone_judge`, `affirms_judge`). The battery named anti-hallucination is the only one in the
guard set scored on its YAML `expected:` list alone.
Consequence for R2.5: the engine-vs-null figures (0.897 / 0.949) and the published 0.914 are
different populations, which is the same conflation DEC-236 and R2.3 untangled for base rates.
**Why deferred:** unifying moves the guard rate, so it must be its own commit and must be
computed once — landing it mid-R2 would make R2.5's delta unattributable, the R2.4 error.
**To fix:** hoist one shared prefix constant, make `runner.py` use it (three prefixes), and land
it as its own commit **immediately before the next regeneration** so the new numbers are
measured once under one definition. Until then R2.5 scopes its null comparison to the 37 guarded
`case_adv_*` / `case_neg_*` cases and states the population in the retraction.

## [FIXED] ISSUE-256: the null probe scores authored expectations only, so its rate is not yet the engine's comparand
**Found:** 2026-09-01, during R2.5 step 2 (unblocking the null baseline)
**Fixed:** 2026-09-02, in R2.5 step 3a — `expected_with_guards` hoisted into
`evals/guard_expectations.py`; the runner and the probe now import one definition.
Re-measured once on the shared expectation set: the canned hedge still scores
**37/37 = 1.000** on the adversarial battery. The rate did not move, but its meaning
did — it is now measured against the same five expectations the engine is scored
with (`schema`, `min_length`, fallback `keyword_none`, `tone_judge`, `affirms_judge`),
with both LLM judges genuinely executing (verified per-case: 27.3 s, real verdicts,
no infra failures). The four injected guards catch empty, canned, and AI-revealing
responses; a fluent hedge is precisely what they permit, so they do not discriminate
against this null. The comparison is therefore now decidable, and it is unfavourable:
engine 0.8468 < null 1.000 on the adversarial battery.
**Severity:** P1 (blocking) — R2.5's engine-vs-null conclusion cannot be drawn until it is fixed
**Where:** `scripts/hedge_responder_probe.py::score_case` vs `evals/runner.py:230`
(`_expected_with_guards`)
**Description:** The probe can now score guard cases (the structural refusal was removed this
task), and the first measurement is stark: the canned hedge passes **37/37 = 1.000** of the
adversarial battery. But that number is NOT the engine's comparand, and must not be published
beside it. `score_case` evaluates `case.get("expected", [])` only. The runner evaluates
`_expected_with_guards(case)` — the authored list PLUS the four injected guard expectations
(`min_length`, the fallback `keyword_none`, `tone_judge`, `affirms_judge`). The engine's 0.8468
is measured against the larger set; the null's 1.000 against the smaller. Comparing them would
be the same different-populations error DEC-243 just removed from the guard headline, and it
would flatter the null responder, which is the direction that makes the guarantee look worst.
The measurement is still informative on its own terms: every adversarial case's AUTHORED
expectations are satisfiable by a fixed string that answers nothing, which is a real authoring
defect independent of the comparison.
**Why deferred:** the unblock is its own commit by design (landing scoring changes together with
the comparison would make the rate movement unattributable — the R2.4 error). Injecting the guard
expectations into the probe also moves the null rate, so it must be measured once, on its own.
**To fix:** have the probe score `_expected_with_guards(case)` for guard batteries — hoisting
that helper out of `runner.py` so both callers share one definition rather than copying it — then
re-measure and record engine-vs-null on the same expectation set. Only then is the
"never publish a headline where engine <= null" rule decidable for the adversarial battery.

## [FIXED] ISSUE-251: two files still describe the retired SKILLS_QUEUE.md as live
**Found:** 2026-09-01, during R4.5 (ledger hygiene)
**Fixed:** 2026-09-02, in R4.4 (CLAUDE.md rewrite) — the normative reference at
`CLAUDE.md:313` is gone: the rewritten file sends open questions to `DECISIONS.md`
alone. `docs/overview.md:42` now carries an explicit **RETIRED 2026-09-01 (R4.5)**
marker naming `right_panel.py:101` as the reason the file is kept read-only.
`SKILLS_QUEUE.md` itself is deliberately NOT deleted, for that same citation.
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/CLAUDE.md:313`, `docs/overview.md:42`
**Description:** `SKILLS_QUEUE.md` was retired in place on 2026-09-01 (R4.5), but two inbound
references still present it as an active destination:

- `CLAUDE.md:313` is **normative** — "those go in `DECISIONS.md` or `SKILLS_QUEUE.md`" — so an
  agent following the rules file is told to append to a retired file.
- `docs/overview.md:42` lists it in the document index as "Open questions and skill/knowledge gaps
  to resolve", with no retirement marker.

A third reference, `demo_game/ui/layout/right_panel.py:101`, cites a specific entry
(`pygame-n-panel-cycle`) as a historical pointer. That one is correct as-is and is the reason the
file was retired in place rather than deleted.
**Why deferred:** both files are outside R4.5's scope (`ISSUES.md`, `DECISIONS.md`,
`archive/ISSUES_RESOLVED.md`, `SKILLS_QUEUE.md`, `scripts/`), and `CLAUDE.md` is the subject of
R4.4, an ask-gated rewrite. Editing it here would pre-empt that decision. The retirement banner at
the top of `SKILLS_QUEUE.md` names both references, so a reader arriving from either is not
misled in the meantime.
**To fix:** in `CLAUDE.md:313` drop the `SKILLS_QUEUE.md` alternative so open questions go to
`DECISIONS.md` only — fold this into R4.4 rather than making a separate pass. In
`docs/overview.md:42` mark the row RETIRED. Do not delete the file.

## [FIXED] ISSUE-129: LLM judges disagree on the headline anti-hallucination number
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Severity:** P1 (blocking — the published guarantee is judge-dependent)
**Where:** `evals/matchers.py` `_run_binary_judge` consumers; `evals/judge_runner.py`
**Description:** The same transcript (`eval_generation_latest.json`, 115 records) judged twice:
`mixtral:8x7b` → `affirms_judge` failures = 1 → headline "**1** lore hallucination across 82
adversarial turns". `qwen2.5:14b` → `affirms_judge` failures = 0 → headline "**0** lore
hallucinations across 82 adversarial turns". Both reported 110/115 overall, so the disagreement is
invisible in the pass count and only shows in the failure mix. Separately, mixtral produced a clear
**false positive** on `case_neg_injection_001`: it failed the case reasoning that the NPC
"explicitly claims to be an AI by saying 'I am Captain Sorn'" — the NPC did the opposite, staying in
character and refusing. So one of the 6 YAML failures in the baseline is the scorer's error.
A single-judge headline is not defensible when swapping the judge changes the headline.
**Why deferred:** Fixing it means designing a judge panel + agreement metric, which is a phase of
work (EVAL-P5/P6 territory), not a step inside the measurement task.
**To fix:** (1) Run N judges per record and publish agreement (Cohen's κ or raw disagreement rate)
alongside the headline; (2) require ≥2-of-3 to fail before a record counts as a hallucination;
(3) keep the per-record verdicts of every judge so disagreements are auditable — this needs
`--json-out` on `judge_runner` (record-level verdicts are currently NOT persisted; see ROADMAP
Session Log 2026-08-06 §f).
**Update 2026-08-09:** The suspicion is now a measured number. First real EVAL-P5 calibration pass
(gen_id `k3_73e6c36`, n=393 hand-labelled) gives `affirms_judge` headline κ (`scorer_verdict` vs
`human_verdict`) = **0.530**, 95% CI **[0.000, 0.853]**, n=135 — moderate agreement whose lower bound
touches chance level. Not as bad as `refusal_judge` (see new **ISSUE-141**, κ=0.247, CI crosses
zero), but not clean either. This still doesn't resolve this issue (no judge panel, no ≥2-of-3 rule
exists yet) — it just replaces "the judges disagreed once" with a real confidence interval. Same
caveat as ISSUE-141: `human_verdict` here is a single hand-labelling pass, not independently
adjudicated.
**Fixed:** 2026-09-02 — **closed as SUPERSEDED by DEC-250**, not repaired. The headline it exists to protect is no longer published. Judge-to-judge disagreement on an unpublished number is not a defect to fix; the judges are retained as regression smoke tests, where a disagreement shows up as a test delta rather than a wrong claim.

## [FIXED] ISSUE-141: `refusal_judge` shows chance-level agreement with human ground truth
**Found:** 2026-08-09, during the first real EVAL-P5 calibration pass (gen_id `k3_73e6c36`, n=75)
**Severity:** P1 (blocking — same class as ISSUE-129, now with a real measured number instead of a
suspicion)
**Where:** `refusal_judge` (LLM judge, `mixtral:8x7b`); `evals/calibration/labels_v1.jsonl`.
**Description:** `make eval-calibrate` against the first real `labels_v1.jsonl` reports
`refusal_judge` headline κ (`scorer_verdict` vs `human_verdict`) = **0.247**, 95% CI **[-0.068, 0.541]**,
n=75 — the confidence interval crosses zero, i.e. statistically indistinguishable from chance
agreement. Confusion counts: scorer=T/human=F (dangerous false positive) = 8, scorer=F/human=T = 4,
out of 75. For comparison in the same run: `tone_judge` κ=0.919 [0.663, 1.000] n=135,
`affirms_judge` κ=0.530 [0.000, 0.853] n=135 (also touches zero at the lower bound — worth watching
but center estimate is moderate), `anti_hallucination_grounded` (deterministic matcher) κ=1.000
[1.000, 1.000] n=48. `refusal_judge` is the worst-performing scorer measured so far, worse than the
`affirms_judge` disagreement ISSUE-129 already flagged.
**Caveat on this number:** `human_verdict` here was set by copying `pre_label` directly (maintainer
decision 2026-08-09: single hand-labelling pass, no independent second read) — so this κ measures
`refusal_judge` against one person's single-pass judgment, not an adjudicated/cross-checked ground
truth. The disagreement is still real (κ doesn't compare a labeller to itself — it compares the
scorer to the human), but the human side has not been double-checked the way a full
`make eval-adjudicate` pass would.
**Why deferred:** Acting on this — rewriting `refusal_judge`'s criteria, swapping its judge model, or
requiring N-of-M agreement — is EVAL-P11 territory (Tier 2 "act on κ"), not a fix inside a
measurement task.
**Root cause (diagnosed 2026-08-09, all 12 discordant records read):** The defect is the **criteria
wording**, not a `mixtral:8x7b` capability limit. `prompts/eval/refusal_judge.yaml` spends lines
15–21 enumerating *surface phrase markers* of refusal and only lines 22–23 stating the substantive
rule ("Answer NO if the speaker asserts... specific positive information... regardless of phrasing").
The phrase list dominates, and it contains **`"I haven't heard"`** — while the engine's hedging idiom
is **`"I've heard..."`** followed by an invented fact. Near-identical surface form, opposite meaning.
The two error classes fall out of this cleanly:
- **8 FPs** (scorer=refused, human=did-not-refuse): a cosmetic hedge wrapper ("Word is…", "Some
  say…", "I've heard whispers…") prefacing a *specific asserted fact*. The judge matches the wrapper
  and scores YES/refused. Note the wrapper alone does not discriminate — 57/63 *concordant* rows
  carry one too; it is the wrapper **plus a specific assertion** that breaks it.
- **4 FNs** (scorer=did-not-refuse, human=refused): a genuine deflection carrying none of the
  listed literal phrases ("I've heard Captain Sorn is quite the authority on those matters" — no
  route details given). Substantively a refusal; matches no enumerated marker.
**Escalating consequence — the FPs are themselves lore hallucinations.** The 8 FPs span 4 distinct
cases (`ah_demo_mira_no_court_politics`, `ah_demo_lira_no_noble_succession`,
`ah_demo_henryk_no_guild_ops`, `ah_demo_lira_adv_north_mill_cache`) and assert invented entities —
"House of Ravenwood", "House of Blackthorn", "Lady Elara", "young Elian". Grepped `seeds/`,
`demo_game/seeds/`, `evals/cases/`: **none of these names exist anywhere in seed data** (only "north
mill" does). So these are the same defect class as ISSUE-128's invented warlord "bjorn" — and
`refusal_judge` is scoring every one of them as a **clean refusal / pass**. A scorer that
systematically marks hallucinations as passes does not merely have low κ; it means the anti-
hallucination headline is an **undercount**, and the true rate is unknown until this is fixed.
**To fix:** (1) Rewrite `prompts/eval/refusal_judge.yaml` to lead with the substantive test — *were
any specific facts, names, or figures asserted about the topic?* — and demote the phrase list to
non-binding examples, explicitly noting that a hedge wrapper around a specific claim is **NO**
(not a refusal). (2) Re-label and re-adjudicate a ~30-row `refusal_judge` sample per EVAL-P11.2 and
confirm κ moved with a non-overlapping lower bound. (3) Re-check the 4 affected cases against
ISSUE-128 — they may be the same engine defect, in which case the guard battery needs regression
cases for invented proper nouns, not just invented quantities.
**Correction 2026-08-09 (same day):** an earlier version of this entry said to fix a "mojibake em-dash
(`topic �`) visible in every labelled row". **That was wrong and must not be acted on.**
`prompts/eval/refusal_judge.yaml` is valid UTF-8 (the em-dash is a correct `e2 80 94`) and **0 of 393**
labelled rows contain U+FFFD. The corruption was in the Windows cp1252 **console** rendering the criteria
when it was printed during diagnosis — not in any file. `evals/__main__._force_utf8_streams()` already
exists for precisely this. Recorded rather than deleted, because a plausible-looking false repair
instruction that reaches a future session is more dangerous than the bug it describes.

**Rewrite attempt #1 FAILED the EVAL-P19.1 gate, 2026-08-12 — reverted, not merged.** Wrote a
criteria leading with "did the speaker assert any specific fact... even one wrapped in a hedge?",
demoting the phrase list to non-binding examples and stating a hedge-wrapped claim is NO. Static
unit tests (structural pins on the criteria text) passed. The **live durability gate**
(`evals/criteria_replay.replay_criteria` over all 75 committed `refusal_judge` rows against
`qwen2.5:7b`, EVAL-P19.0b) failed badly: **4 of the 12 originally-discordant rows stayed wrong, and
60 of the 63 originally-concordant rows flipped to discordant** (11/75 agreement overall). κ moved
from 0.247 → **0.000**, not up. Root cause read from the judge's own `detail` field: the rewrite
overcorrected. Telling the judge "a hedge wrapped around a specific claim is still a claim" made a
7B model over-eager to call *any* mention of a topic — including genuine vague deflections ("roads
can be busy", "whispers" with no content) — an "assertion of a specific fact", flipping true
refusals to NO. Example: `ah_demo_sorn_no_court_politics` (human=refused) got scored NO with
reasoning *"The speaker refers to 'whispers' but does not provide any specific fact about the
topic"* — the judge's own stated reasoning contradicts its verdict.
**Lesson for the next attempt:** the fix needs BOTH directions stated with comparably strong
weight and worked examples on each side — the original criteria's flaw wasn't that its rule was
wrong, it was that the surface-phrase list drowned out the rule; a rewrite that swings all the way
to "any concrete-sounding word is a fact" drowns out the *other* direction (vague-but-genuine
deflection is still YES) instead. Validate on a **held-out subset first** (e.g. 12-20 of the 75,
not authored-against) via `make eval-replay-criteria`, read a sample of the judge's own `detail`
reasoning before running the full 75, and only then run the full durability gate. Do not tick
EVAL-P19.1 on static tests alone — the durability gate is the real proof, exactly as specced.

**Rewrite attempt #2 FAILED too, 2026-08-12 — reverted, not merged.** Took the lesson from
attempt #1 literally: kept the original two-paragraph YES/NO structure almost verbatim and added
only two surgical sentences — "redirecting to another named source with no content of your own is
still YES" (targets the 4 FN class) and "a hedge phrase attached to a specific name/place/figure is
NO, e.g. 'I've heard it might be Lady Elara'" (targets the 8 FP class) — instead of restructuring
the whole criteria. Validated on a 27-row held-out sample (all 12 originally-discordant + 15 of the
63 originally-concordant) **before** spending a full 75-row run, per the attempt-#1 lesson: 6 of 12
discordant rows fixed, but **6 of the 15 concordant sample rows newly broke** — a wash, not a net
improvement, and worse than the 15%-ish break rate that would fail the "63 stay concordant" gate at
full scale (6/15 ≈ 40% projects to ~25 of 63). Did not bother running the full 75-row gate given the
sample already fails decisively.
**Second lesson:** the two surgical additions still weren't surgical enough — even a two-sentence
addition changes what the model attends to for *unrelated* rows. Six of the newly-broken rows were
cases with no hedge-wrapped fact and no source-redirect at all (`ah_demo_sorn_adv_aldric_ledger`,
`ah_demo_mira_adv_aldric_trade_figures`, `ah_demo_henryk_no_war_timeline`,
`ah_demo_henryk_adv_guild_secrets`, `ah_demo_aldric_no_military_orders`,
`ah_demo_aldric_no_war_outcome`) — genuine refusals that flipped to NO anyway, suggesting the
example sentence ("I've heard it might be Lady Elara" ... "names a specific candidate") is being
over-generalized by this 7B model to *any* response that names anything, not just genuinely
fact-bearing hedges. A qwen2.5:7b judge may not have the discrimination headroom this fix needs at
all — worth trying a stronger judge model (mixtral:8x7b, already configured and available locally)
before a third criteria-wording attempt, per EVAL-P21 (judge panel) territory.

**Correction 2026-08-12 (before attempt #3): the "try mixtral:8x7b instead" premise above is
wrong — mixtral:8x7b was already the judge for attempts #1 and #2.** `evals/judge_config.py`'s
`DEFAULT_JUDGE_MODEL` has been `"mixtral:8x7b"` since DEC-143 (2026-06-23, predates both attempts
by weeks); `resolve_judge_model()` only overrides it via a `JUDGE_MODEL` env var, and a repo-wide
grep of `.env`/`.env.demo`/`.env.example` plus a fresh-process check
(`judge_config.resolve_judge_model()` → `'mixtral:8x7b'`) found no override anywhere. Neither prior
attempt's scratchpad script (`eval_p19_1_durability_check.py`, `eval_p19_1_sample_check.py`) set
`JUDGE_MODEL` either — both called `matchers._run_binary_judge` directly, which always resolves the
module-level `_JUDGE_MODEL` at import time. So both `qwen2.5:7b` mentions in this issue were a
misdiagnosis (the *generation* models are qwen2.5:7b per DEC-149, which was likely conflated with
the judge). The "swap to mixtral" lever was already spent before attempt #3 ran. Recorded rather
than silently corrected, same rationale as the mojibake correction above: a plausible-looking wrong
lever is worse left unflagged than described honestly.

**Rewrite attempt #3 FAILED too, 2026-08-12 — reverted, not merged.** Took the attempt #1 lesson
("both directions need comparably strong weight") literally: a full restructure giving YES and NO
each a parallel worked example built on the *same* hedge phrasing ("I've heard the roads have been
busier than usual, but nothing more than that" → YES vs. "I've heard whispers it might be the
Ravenwood family..." → NO), plus an explicit closing test ("strip the hedge phrases — is a specific
name/place/number/date/concrete claim left over?"). Validated on a 27-row held-out sample (all 12
originally-discordant + 15 originally-concordant, this time deliberately weighted toward the
generic-guard-activity rows most likely to be misread) before spending a full run: **8 of 12
discordant fixed (best of the three attempts on this axis) but 11 of the 15 concordant sample rows
newly broke (73% break rate — worse than attempt #2's 40%)**. Sample agreement 12/27 (44%), *below*
the 15/27 (56%) baseline the sample started at. Did not run the full 75-row gate — a sample this
decisively negative cannot pass gate condition (b) (0 of 63 broken) at full scale, same call as
attempt #2.
**Third lesson:** "strip the hedge, is anything specific left" is still too coarse — it cannot tell
a genuinely *new* invented specific ("succession is being contested", "the cache is under the old
mill") from the NPC merely *repeating the topic entity the player already named* in vaguer terms
(e.g. `ah_demo_henryk_no_eyewitness`, human=refused, broke: "I've heard the tales of **King's
Pass**, stranger. But I was but a humble blacksmith..." — "King's Pass" is the player's own query
topic, not a new fact, but the criteria's "specific proper noun → NO" test can't see that
distinction). Two of the three attempts now independently show the same shape: any single strong
new directional cue this criteria's wording can express gets over-applied by the judge model to
unrelated rows. Combined with the mixtral correction above, the "wording problem vs. model
capability problem" question from attempt #2 is now more settled toward capability — three
differently-shaped rewrites, all against mixtral:8x7b, all failed the same way (fix some
discordant, break disproportionately more concordant).
**Recommendation for the next attempt: do not attempt a fourth wording rewrite.** Move to EVAL-P21
territory (a 2-of-3 or 3-of-5 judge panel with majority vote, or an ensemble across mixtral:8x7b +
qwen2.5:14b) — the wording lever appears exhausted at n=3 attempts across 2 structurally distinct
strategies (full restructure, surgical patch, balanced-parallel-examples restructure), all against
the same (correctly-configured, already-strongest-available) judge model.
**Status: still open, still κ=0.247, criteria file unchanged from the original after three reverted
attempts (2026-08-12).**
**Formally deferred to EVAL-P21, 2026-08-13 (DEC-172).** `EVAL-P19.1` is flagged `⏸️ deferred` in
ROADMAP.md rather than retried a fourth time. `HUMAN GATE H2`'s `Ready when` no longer requires
`EVAL-P19.1` ticked (was unreachable — its own fix, EVAL-P21, depends on EVAL-P20.4, which is
downstream of H2) — it now requires `EVAL-P19.2` instead, a real criteria change already shipped.
`EVAL-P19.4` proceeds and is expected to report `refusal_judge` unchanged at κ≈0.247; that is not
a new failure, it is this issue staying open on schedule. `refusal_judge`'s rate remains refused
for publication until EVAL-P21's judge panel (2-of-3, out-of-family third judge) lands.

**`EVAL-P19.4` ran, 2026-08-13 (`HUMAN GATE H2` cleared) — confirms the expected result.**
Re-judged the unchanged `k3_73e6c36` transcript (`JUDGE_MODEL=mixtral:8x7b`) and merged
(`MERGE=1`) against the real 393-row label file: **393 human verdicts preserved, 0 new rows, 0
hash-drifted rows** (deterministic pass also regenerated via `make eval-deterministic-verdicts` to
actually exercise EVAL-P19.2's word-boundary fix — confirmed 0 of 576 deterministic verdicts
flipped in this corpus; the fix is real but this corpus contains no case whose keyword match it
changes). `refusal_judge` re-measured: **κ = 0.247, 95% CI [-0.123, 0.703], n=75, n_clusters=25**
— point estimate exactly unchanged from the original ISSUE-141 measurement, confusion matrix
identical (60 TT / 8 FP / 4 FN / 3 TT-neg). Confirms DEC-172's prediction. `refusal_judge` stays
unfixed, its rate stays refused for publication, and this issue stays open, deferred to EVAL-P21 —
exactly as scheduled, not a new finding. (Blocking infra defect hit and fixed en route: ISSUE-158.
Unrelated tone_judge LLM non-determinism noticed and accepted, not reverted: ISSUE-160.)
**Fixed:** 2026-09-02 — **closed as SUPERSEDED by DEC-250**, not repaired. `refusal_judge`'s chance-level agreement mattered because it licensed a published number. Nothing is published. The judge is retained as a smoke test and must NOT be described as a measurement — its kappa is 0.247, CI [-0.068, 0.541].

## [FIXED] ISSUE-244: three rival kappa families circulate for the same scorers
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Severity:** P1 (blocking) — R2.6's MDE-vs-headroom item cannot be decided until it is settled
**Where:** `evals/mde.py:93-97` vs `evals/trend/trend_v1.jsonl` (`scorer_kappas` and
`kappa_by_criterion`) vs `project-harness/review-2026-08/BASELINE_2026-08-28.md`
**Description:** For the same scorers, three different kappas are in circulation:
calibration 0.849 / 0.530 / 0.247 (tone / affirms / refusal); `mde.py`'s `RECORDED_KAPPAS`
1.000 / 0.282 / 0.225; panel Fleiss 0.753 / 0.519 / 0.422. `CODEBASE_REVIEW.md:2427` already
recorded this ("three different kappa for the same scorer circulate in the docs") and nothing
reconciled it. The consequence is concrete: the 17.25 pp / 29.01 pp MDEs were computed from
`mde.py`'s numbers, while the judge-retirement argument quotes calibration's. Under `mde.py`'s
0.282, `affirms_judge` is HIDDEN (below the 0.40 threshold), not RESTRICTED — which reverses the
recommendation.
**Why deferred:** it is R2.6's first step, not a standalone fix, and recomputing the MDEs is part
of that task.
**To fix:** calibration is authoritative (decided 2026-08-31 with the maintainer). Update
`mde.py`'s `RECORDED_KAPPAS` to 0.849 / 0.530 / 0.247, recompute the MDEs, and make the other two
families cite or derive from calibration rather than circulate independently. Only then make the
retirement call.
**Fixed:** 2026-09-02 — **closed as SUPERSEDED by DEC-250**, not repaired. The three rival kappa families blocked R2.6's MDE-vs-headroom item. R2.6 is retired. No kappa is published, so there is nothing for the families to disagree about in public.

## [FIXED] ISSUE-229: the guard battery is beaten by a fixed string
**Found:** 2026-08-28, during the 2026-08 review remediation triage
**Severity:** P1 (blocking)
**Where:** `evals/`, `evals/reports/20260825T231028Z.md:11`, `scripts/hedge_responder_probe.py`
**Description:** A null responder emitting one hard-coded sentence scores 74/78 = 0.949 across the
YAML guard cases; the engine scores 70/78 = 0.897. The published claim is "Guard 170/186, 0.914". The
baseline had never been taken because `hedge_responder_probe.py` raises `NotACapabilityCaseError`
when handed a guard case — it structurally refuses to score the battery it would need to score. No
scorer's agreement interval excludes chance, and the YAML guard-case base rate is 1.000.
**Why deferred:** not deferred; it is R2.5. ISSUE-231 and the base-rate wiring both landed
2026-08-31 (R2.1, R2.3); what remains is the product decision plus removing
`NotACapabilityCaseError` from `hedge_responder_probe.py`.
**To fix:** allow the probe to score guard cases; print the null baseline beside every published
number; refuse to publish a headline where engine ≤ null; retract 0.914 until it clears. Delete the
18 guaranteed-pass assertions first, in a separate commit, or the delta is unattributable.
**Fixed:** 2026-09-02. Every fix condition this entry states was met:
- *"allow the probe to score guard cases"* — `NotACapabilityCaseError` generalised (1f08d135),
  then bound to the runner's own expectation set via `evals/guard_expectations.py` (5a075c00).
- *"print the null baseline beside every published number"* — superseded by something stronger:
  DEC-245 **refuses to print** the rate rather than printing it beside a null that beats it.
- *"refuse to publish a headline where engine ≤ null"* — implemented per population in both the
  console and markdown emitters (89f40216).
- *"retract 0.914 until it clears"* — done 92a2c539; it has not cleared and will not, so the
  claim is retired outright by DEC-250.

**Ledger note:** ISSUE-257 was logged on 2026-09-02 for this same defect, by an agent that did
not find this entry among 82 open issues. That duplication is the primary evidence cited in
DEC-250 for collapsing the ledger. 257 is retained as the live successor because it states the
remaining work concretely; this entry is the closed original.

## [FIXED] ISSUE-261: reputation label boundary at standing 50 is undecided
**Found:** 2026-09-02, during R3 (triage cause E, carried from ISSUE-233)
**Fixed:** 2026-09-02, in R3 close-out — standing 50 is `allied` (DEC-252)
**Severity:** P2 (annoying) — one baselined integration failure; needs a product decision, not a fix
**Where:** `src/npc_engine/graph/reputation/reputation_queries.py:58-72`,
`tests/integration/test_reputation_integration.py:223`
**Description:** `_LABELS` are exclusive upper bounds — `(20,"neutral"), (50,"friendly"),
(101,"allied")` with `if standing < threshold: return label` — so `friendly` is `[20, 50)` and
`allied` is `[50, 101)`, and standing 50 returns `allied`. The test asserts `friendly`, i.e. an
inclusive-friendly boundary. The code is internally consistent; the test asserts the only other
reading, and **no spec states which convention is intended**.
**Why deferred:** whichever artifact is edited, the edit encodes a product decision about when an
NPC counts as allied. That decision is not R3's to make in passing, and "fix whichever is
cheaper" is precisely how an unexamined convention becomes permanent.
**To fix:** decide whether standing 50 is `friendly` or `allied`, record it in `DECISIONS.md`,
then change the losing artifact. Do not change either before the decision exists.
**Resolution:** DEC-252 chose `allied`. The convention — exclusive upper bounds, every boundary
falling in the more positive band — is now stated in `_standing_label`'s docstring and beside
`_LABELS`, so the next reader of either file sees it. The test at
`tests/integration/test_reputation_integration.py:223` was the losing artifact and now asserts
`allied`. `test_reputation_context_included_above_threshold` failed with
`AssertionError: assert 'allied' == 'friendly'` before the change and the file's 5 tests pass after;
`scripts/integration_baseline.txt` ratchets 4 → 3.

## [FIXED] ISSUE-258: three readers disagree about a Character with no `is_active`
**Found:** 2026-09-02, during R3.4 (settling ISSUE-233 item 8)
**Fixed:** 2026-09-02, in R3 close-out — strict everywhere (DEC-252)
**Severity:** P2 (annoying) — silent, and it already cost one integration failure
**Where:** `src/npc_engine/graph/graph_reader.py:47`,
`src/npc_engine/graph/character/skill_queries.py:64`,
`src/npc_engine/graph/character/character_reader.py:25`
**Description:** `character.yaml:9` declares `is_active` `required: true`, but the three readers
handle its absence differently. `character_reader.py:25` is forgiving —
`AND coalesce(c.is_active, true) = true`, so a Character without the field is visible.
`graph_reader.py:47` and `skill_queries.py:64` use a bare `WHERE c.is_active = true`, and
`null = true` is null, so the same node is invisible. Measured 2026-09-02: a Character merged
without the field returns `get_npc_location_id -> None`; the identical node with
`is_active = true` returns its location. That divergence is exactly what made
`test_advance_creates_covert_event_and_step` fail for a whole programme phase without anyone
being able to name the cause — the read failed silently at DEBUG.
**Why deferred:** picking a convention is a product decision, not a cleanup. `coalesce` treats a
contract violation as active, the bare predicate treats it as deleted, and either is defensible.
Changing it also changes which nodes existing queries return, so it needs its own commit with a
before/after count, not a slot inside a test-fixture fix.
**To fix:** decide whether an absent `is_active` means active or inactive, apply the same
predicate in all three readers, and add a migration or a schema check if existing nodes lack the
field. `make check-migrations` is the natural gate.
**Resolution:** DEC-252 chose strict. `character_reader.py:25` now uses a bare
`c.is_active = true`, so all **37** predicates in `src/` agree and zero `coalesce` remain.
Three of this entry's own claims did not reproduce and are corrected here:
  * "three readers disagree" undercounts — it was **36 strict against 1 forgiving**, not 3.
  * "add a migration ... if existing nodes lack the field" — **no node lacks it.** Measured
    against the live graph with cypher-shell: Character 23/23 and Faction 10/10 carry it, so a
    backfill would have been a no-op. The deliverable was prevention, not repair.
  * "`make check-migrations` is the natural gate" — **it is not.** That gate fires when a node
    type *gains* a required field with no migration claiming it; `is_active` has been in
    `scripts/node_type_snapshot.json` for both types all along, so it has nothing to say about
    this. Prevention already lived at the API write boundary instead:
    `validate_node_payload(..., CREATE)` raises `REQUIRED_FIELD_MISSING` on a Character or
    Faction with no `is_active` — measured, then pinned by
    `tests/unit/conformance/test_is_active_write_boundary.py` (4 tests) so it stays true.
RED anchor: `tests/integration/test_is_active_reader_agreement_integration.py` failed with
"a Character without is_active must not appear in the NPC roster" before the change and passes
after. Integration suite 43 passed / 3 failed, the 3 being the recorded baseline.
The remaining gap — fixtures that MERGE raw Cypher and never reach validation — is ISSUE-263.

## [FIXED] ISSUE-257: the adversarial battery does not discriminate the engine from a canned hedge
**Found:** 2026-09-02, during R2.5 step 3c
**Fixed:** 2026-09-03, in M3.3 (e8807803). The rule was decided and recorded as DEC-256, all
37 cases were re-authored against it, and the acceptance test passes: the canned hedge now
scores **0/37 = 0.000** against a 0.30 gate, down from 37/37 = 1.000. `evals/null_baseline.json`
is re-recorded (hedge sha256 verified unchanged, so both numbers describe the same adversary
and the same expectation set). The positive half is a per-case `commits_judge` criterion, not
the `affirms_judge` the issue guessed at — see DEC-256 for why affirms_judge could not work.
**Severity:** P3 (nice-to-fix)
**Reclassified:** Downgraded P1→P3 2026-09-02 by DEC-250: the battery's failure to discriminate is ACCEPTED, not scheduled. It is retained as a regression smoke test and must not be described as a measurement. Re-authoring the 37 cases is the entry point if the claim is ever revived. Supersedes the closed ISSUE-229.
unpublishable until this is fixed
**Where:** `evals/cases/case_adv_*.yaml`, `evals/cases/case_neg_*.yaml` (37 cases)
**Description:** Measured 2026-09-02 through the shared expectation set
(`guard_expectations.expected_with_guards`, both LLM judges live): the canned hedge in
`scripts/hedge_responder_probe.py` scores **37/37 = 1.000**, against the engine's 0.8468.
Every adversarial and negative case is satisfied by a fixed string that asserts nothing.

This is not a guard defect. The four injected guards catch empty, canned and AI-revealing
responses; a fluent hedge is none of those, so they pass it correctly. The defect is in case
authoring: the cases forbid confirming a false premise, and hedging does not confirm it, so
refusing to answer is scored identically to knowing better. Per DEC-245 the adversarial rate
is therefore no longer printed.
**Why deferred:** re-authoring 37 cases is a distinct, substantial task from the comparability
fix that revealed the problem, and it needs a stated authoring rule (what must a case require
beyond "does not confirm the false premise"?) before any case is rewritten. Guessing that rule
case-by-case would produce 37 inconsistent cases.
**To fix:** decide the discrimination rule — most likely each guard case must also require a
positive, case-specific commitment the hedge cannot supply (naming what the NPC does know, or
who to ask) — record it as a DEC, then re-author the cases against it. Prove it by re-running
`python scripts/hedge_responder_probe.py --battery adversarial` and requiring the null rate
below the 0.30 gate, and re-record `evals/null_baseline.json`.

## [FIXED] ISSUE-286: R2.1's digest gate is unconditionally fatal against Ollama 0.33.2 — no generation can run on this machine
**Found:** 2026-09-04, during the fresh eval generation run (case set from `docs/EVAL_NEXT_GENERATION_CASE_SET.md`)
**Severity:** P1 (blocking)
**Where:** `evals/engine_adapter.py::fetch_model_digest`, called from
`evals/run_config.py::resolve_run_config` (R2.1, `ModelDigestUnavailableError` at line ~328)
**Description:** `fetch_model_digest` POSTs to Ollama's `/api/show` and reads
`response.json()["digest"]`. On this machine's current Ollama server (`0.33.2`, confirmed via
`GET /api/version`), `/api/show`'s response body has no `digest` key anywhere in its JSON tree
(checked recursively against the `qwen2.5:7b` response — keys present are `license, modelfile,
template, system, details, model_info, tensors, capabilities, modified_at`; `details` itself
carries no digest either). `fetch_model_digest` therefore always returns `None` for every
model, so `_require_digest` always raises `ModelDigestUnavailableError` — `make eval-generate`
cannot succeed against this Ollama install at all, regardless of whether Ollama is reachable or
the model is pulled (both confirmed fine: `GET /api/tags` lists `qwen2.5:7b` with a real digest
field there). The last successful generation (`evals/generations/k3_77688e7_regen1/meta.json`,
2026-08-25) recorded `ollama_version: "0.32.15"` with **null** digests — i.e. it ran before R2.1
was enforced, against an older Ollama where this was already true or masked; the R2.1 gate
appears to have never actually been exercised end-to-end against this machine's real Ollama
server, only against test doubles that fabricate a `digest` field (`tests/unit/evals/
test_run_config.py`).
**Fixed:** 2026-09-04, during the same generation-run task, with the user's explicit approval to
patch `fetch_model_digest` (this session was otherwise scoped as operator-only, no code). RED
first: `tests/unit/evals/test_engine_adapter.py::test_fetch_model_digest_matches_tag_in_api_tags`
against the real function called `httpx.post`, which the unit-test network guard rejected with
`NetworkAccessInUnitTestError`, confirming the old code path was exercised and not the fix.
GREEN: `fetch_model_digest` now reads `GET /api/tags`, matching the requested tag against each
entry's `model` field (falling back to `name`) and returning that entry's `digest`. Verified live
against the real running Ollama (not just the mock): `qwen2.5:7b` ->
`845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e`, `mixtral:8x7b` ->
`a3b6bef0f836ff29ddb576a80eeb1b7def43ec9b809466f62e96adb871fe8498`. Three new unit tests (happy
path / unlisted model / unreachable server) all pass; full `tests/unit/evals/` suite (890 tests),
`make check-docstrings`, `make check-layers`, `make check-rules`, and `make type-evals` all green
with no new violations.

## [FIXED] ISSUE-285: `tone_judge` and `affirms_judge` cannot clear the label-adequacy floor from the authored corpus
**Found:** 2026-09-04, choosing the case set for the next generation (`docs/EVAL_NEXT_GENERATION_CASE_SET.md`)
**Severity:** P2 (annoying)
**Where:** `evals/cases/case_neg_*.yaml`, `evals/cases/case_adv_*.yaml` (37 cases total)
**Description:** DEC-260's adequacy floor (25 minority labels, 10 case clusters) currently
refuses all four labeled scorers. `case_neg`/`case_adv` — the only cases authored to elicit
a minority verdict — carry zero `tone_judge` expectations and only 8 `affirms_judge`
expectations across the 37 cases. Even under a best-case labeling outcome (every candidate
lands on the minority side), `tone_judge` gains nothing (0 available) and `affirms_judge`
tops out at 16 (8 current + 8 available), both short of the 25 floor. Full numbers in
`docs/EVAL_NEXT_GENERATION_CASE_SET.md`.
**Why deferred:** The task that found this explicitly rules out lowering the floor and
authoring new `case_pos`; authoring new negative cases for `tone_judge`/`affirms_judge` is
new case-authoring work, out of scope for a case-*selection* task.
**To fix:** Author new `case_neg`/`case_adv` cases whose `expected` list carries a
`tone_judge` and/or `affirms_judge` expectation, sized to give each scorer a realistic path
past 25 minority labels across at least 10 clusters.
**Fixed:** 2026-09-04, during the label-export stratification task (DEC-262) — as a correction,
not as case-authoring. The premise was measured against each case's own authored `expected:`
list only, which misses `evals/guard_expectations.expected_with_guards`: every `case_neg_`/
`case_adv_` case gets `tone_judge` (`GUARD_TONE_RUBRIC`) auto-injected at generation time
regardless of its own YAML, plus `affirms_judge` (`GUARD_LORE_RUBRIC`) for every
`requires_world: demo` case (all 37 here) — a mechanism this issue's own counting method never
ran the cases through. Measured directly against the real regenerated transcript
(`evals/generations/k3_61b01dad_negadv/outputs.jsonl`, k=3): `tone_judge` 111 records / 37
clusters, `affirms_judge` 132 / 37 — both clear the 25-minority / 10-cluster ceiling in the best
case, where this issue claimed `tone_judge` was unreachable and `affirms_judge` topped out at 16.
See DEC-262 for the full correction and the label-export tooling this measurement now feeds.
Reachable is not the same as met: whether real human labelling actually reaches 25 for either
scorer is still unmeasured, and remains open work if it does not — but that is a labelling
outcome, not this issue's (wrong) premise that the corpus could not possibly produce one.

## [FIXED] ISSUE-288: `make eval-judge` crashes uncaught on a guard-only generation (no capability cases)
**Found:** 2026-09-05, running `make eval-judge` against `k3_61b01dad_negadv` (the
case_neg/case_adv-only generation from `docs/EVAL_NEXT_GENERATION_CASE_SET.md` — no
case_pos_*, no AH fixture, per that doc's decision).
**Severity:** P2 (annoying — the judge pass itself completes and judged.jsonl is written
correctly before the crash; only report generation fails)
**Where:** `evals/report.py:51` -> `evals/summary.py:598` `format_summary_markdown` ->
`evals/summary.py:469` `_assert_paired_rates`, raised from `evals/judge_runner.py:237`
`write_report(...)`, which is called OUTSIDE the `try/except` in `judge_runner.main`
(`evals/judge_runner.py:230-232` only wraps `_run_judging`).
**Description:** `_assert_paired_rates` requires the guard rates and the capability rate
to be either both present or both absent (`_UNPAIRED_GUARD_ONLY` / `_UNPAIRED_CAPABILITY_ONLY`).
A generation with guard cases and zero capability cases — a real, deliberately-authored
shape, not a malformed transcript — trips `_UNPAIRED_CAPABILITY_ONLY` and raises. Because
`judge_runner.main`'s `try/except` ends before `write_report` is called, the exception is
never caught by `record_error`; it propagates as a raw traceback and the process exits 1
(not the documented 3-way 0/1/2 contract). `--json-out judged.jsonl` is written before this
point, so the actual judging work survives — only the console/markdown report is lost.
**Why deferred:** out of scope for the M metrics-bring-online task in progress; fixing the
pairing invariant or `judge_runner`'s exception boundary is a design decision (does a
guard-only generation get an exemption from `_assert_paired_rates`, or does `write_report`
get its own try/except with a graceful degrade?) that this task did not ask for.
**To fix:** either (a) extend `write_report`'s call to `format_summary_markdown` with a
guard clause that skips `_assert_paired_rates` when the caller declares the generation
guard-only (a new explicit flag, not silent), or (b) move `write_report` inside
`judge_runner.main`'s `try/except` so this degrades to exit 2 with a recorded error
instead of an uncaught crash. Either way, add a regression test that runs `judge_runner.main`
against a guard-only transcript and asserts the process does not crash.
**Fixed:** 2026-09-07, eval/metrics remediation (commit `999fe0de`) — took option (b).
`judge_runner._render_report` now wraps `write_report` + `format_summary_lines`, catching
the render failure instead of raising: `main()` still computes `passed`/`total` from the
judged results directly and always writes `run_status.json`, with the render failure
recorded on `RunStatus.error` (`build_status`'s `report_path` became `Path | None`). Exit
code stays 0/1 per DEC-189 (see DEC-266) — the judging did complete, only the report
render degraded. Verified two ways: a regression test drives `judge_runner.main()` against
a guard-only transcript end to end, and a live smoke run (real Ollama generation + judging
against a deliberately guard-only 2-case set, `docs/EVAL_NEXT_GENERATION_CASE_SET.md`'s
exact shape) reproduced the original crash message verbatim
("Report generation failed: capability rate is required...") while `run_status.json` was
written with real `cases_passed`/`cases_total` and `status: "gate_failed"` rather than an
uncaught traceback.

## [FIXED] ISSUE-276: the "orphaned calibration labels" finding is false — 393/393 survive, and refusal_judge is a live scorer
**Found:** 2026-09-03, during M3.2
**Fixed:** 2026-09-07, in measurement-remediation Phase 2c (DEC-269)

**Resolution note, added at close:** the concern this issue raised — deleting refusal_judge
discards 75 live, hand-adjudicated labels, the irreplaceable-data class this programme
protects — does not apply to how it was ultimately retired. Phase 2c folded refusal_judge's
axis into `matchers.judge_affirms` (same "did the speaker assert as fact" question, opposite
polarity, criteria text inverted from `prompts/eval/refusal_judge.yaml`) rather than deleting
it outright, and — per the measurement-remediation plan's explicit decision — kept every row
in `evals/calibration/labels_v1.jsonl` (all 747, retired-scorer rows included) rather than
purging the 75 refusal_judge labels. The scorer MECHANISM is retired; the labelled DATA
survives as historical calibration record. This is the fuller of the two actions this issue's
own "To fix" section named ("retire refusal_judge as a scorer" vs. the narrower "document-only,
keep it a live AH-fixture scorer") — correct here because DEC-269 is a deliberate,
scope-reviewed scorer reduction (5 judges to 3), not the same under-verified M3.2 context this
issue correctly blocked. ISSUE-141 (the rubric rewrite) is superseded, not separately closed:
there is no `refusal_judge` rubric left to rewrite.
**Severity:** P1 (blocking) — M3.2 as planned would delete a live, fully-calibrated measurement
**Where:** `evals/matchers.py` (`judge_refusal`), `evals/anti_hallucination_runner.py:252`,
`evals/refusal_rate.py`, `evals/generation_records.py:128`, `evals/cases/anti_hallucination_demo.json`,
Makefile targets at lines 413 and 524
**Description:**
The M-programme plan states that `refusal_judge` (75 labels) and `anti_hallucination_grounded`
(48) "have **zero** surviving rows — both were labelled against the deleted `ah_demo_*` family",
and that 66.4% of the 393 labels survive. M3.2 acts on that by retiring `refusal_judge`.

Measured against the actual checker, every part of this is wrong:

```
$ python scripts/check_label_survival.py --transcript evals/generations/k3_77688e7_regen1/outputs.jsonl
Labels checked: 393
  survive:  393
  drift:    0
  orphaned: 0
```

- The `ah_demo_*` family was **never deleted**. It lives in `evals/cases/anti_hallucination_demo.json`
  — 41 real cases, 25 `expected_verdict: refusal` and 16 `grounded`. It is loaded by
  `anti_hallucination_runner`, not by the YAML case globber, which is why a `evals/cases/*.yaml`
  search does not see it.
- All **123** `ah_demo_` records are present in **both** generations' `outputs.jsonl`
  (`k3_73e6c36` and `k3_77688e7_regen1`), which is 75 refusal + 48 grounded at k=3 repetitions.
- Every one of the 25 refusal_judge label case ids and all 16 anti_hallucination_grounded ids
  resolve to live cases. The only genuinely unmatched labels are **3 tone_judge cases**.

`refusal_judge` is therefore **not a zombie**. The narrow claims are true — `matchers.evaluate`
has no `refusal_judge` branch and no `evals/cases/*.yaml` uses it — but the scorer runs through a
different path entirely: `anti_hallucination_runner.py:252` calls `matchers.judge_refusal`,
`evals/refusal_rate.py` is built on it, `generation_records.build_ah_refusal_record` produces its
records, and two Makefile targets drive the fixture. `guard_expectations.py` already documents
this in its own comment ("ah_demo_ cases are authored for refusal_judge +
anti_hallucination_grounded"). Deleting `prompts/eval/refusal_judge.yaml` would additionally break
`import matchers` outright, because `_REFUSAL_CRITERIA` is loaded eagerly at module import
(`matchers.py:107`).

**Why deferred:** M3.2 is halted, not attempted. Proceeding would have deleted 25 live cases'
scorer, broken two make targets and several test modules, and discarded 75 valid hand-adjudicated
verdicts — the irreplaceable-data class this programme explicitly protects.
**To fix:** Two separable questions, neither of which is "delete it".
1. Decide whether `refusal_judge` should be retired **as a scorer of the YAML guard battery**
   (where it genuinely has no dispatch branch and no case) while remaining the AH fixture's
   scorer. That is a documentation change, not a deletion.
2. ISSUE-141 (the twice-failed rubric rewrite) stays open on its own merits; a scorer at
   kappa 0.247 is HIDDEN under `docs/SCORER_TRUST_POLICY.md` and may not be quoted — but a
   HIDDEN scorer is one to remediate or retire *deliberately*, on a correct premise.
Correct the plan's survival figures wherever they are repeated (ROADMAP M4.2 prioritises
"re-ground `anti_hallucination_grounded`, of whose 48 labels zero survive" — all 48 survive).

## [FIXED] ISSUE-126: `expand_loop.sh` stale-lock recovery is documented nowhere (runaway half FIXED)
**Found:** 2026-08-02, during loop-readiness verification of the DEC-153 roadmap changes
**Fixed:** 2026-09-16, in roadmap task T0.2 — recovery printed in the FATAL message, the `expand_loop.sh` usage header and `OVERNIGHT_LOOP.md` ("Stale lock recovery").
**Partially fixed:** 2026-08-28 by DEC-235, confirmed by measurement 2026-09-03 — the runaway half is
closed. `scripts/expand_loop.sh:648` halts the
loop once the cursor returns the same task `MAX_SAME_TASK_REPEATS` times (default 2, `:103`), which is
option (c) from the fix list below. Measured 2026-09-03: an unbounded
`bash scripts/expand_loop.sh --dry-run` terminated on its own after 6.5 minutes with exit 0, logging
`HALT: M1.1 repeated 2 times without advancing the cursor`. **Do not delete that guard or reimplement
it.** What is still open is only the documentation half — see **To fix**.
**Severity:** P3 (nice-to-fix) — was P2 while the loop could spin; the remaining half costs one
confused restart, no data loss
**Where:** `scripts/expand_loop.sh` — `run_claude_session` (dry-run early return) vs the `main()` while-loop; usage block at `:55-59`
**Description:** A task is ticked by the **claude session** (`/expand-linear-next` marks, gates and commits
it), not by the loop driver — `grep "cursor --mark" scripts/expand_loop.sh` returns nothing. Under
`--dry-run`, `run_claude_session` returns before any session runs, so the task is never marked. `cursor
--next` therefore returns the same task on every iteration and the loop spins forever, sleeping
`TASK_SLEEP_SECS` (20 s) between identical iterations, until killed.

The script's own usage block advertises exactly the hanging invocation:
`bash scripts/expand_loop.sh --dry-run   # no model calls at all`.

Bounding it works — `--dry-run --max-tasks 1` completes cleanly (`reached --max-tasks 1`, tree untouched,
queue still `open=1`), which is also what proves the diagnosis: a dry run leaves the queue unchanged.

**Second-order effect:** killing the spinning loop leaves the `mkdir`-based lock behind
(`project-harness/.loop-state/loop.lock/` containing `pid`), so the *next* run aborts with
`FATAL: another loop holds …`. Recovery is `rm -rf project-harness/.loop-state/loop.lock`, which is not
documented anywhere.

**Why deferred:** found while verifying a roadmap change, not while working on the harness; fixing it is a
separate task and the roadmap's single-task-focus rule applies. It does not affect real (non-dry-run) nights —
DEC-151's rig validated the real path with a fake `claude` on `PATH`, which *does* mark tasks.

**To fix (remaining):** document the stale-lock recovery — `rm -rf project-harness/.loop-state/loop.lock`
— in the script's usage block and in `project-harness/OVERNIGHT_LOOP.md`. The no-progress halt makes this
*more* likely to be met, not less: a halt is now the normal end of a stalled night, so the next operator
meets the lock rather than the spin. Tracked as roadmap task R6.1.

Historical fix options, kept for the record: (a) make `--dry-run` imply `--max-tasks 1` unless the caller
sets it explicitly, (b) have the dry-run path simulate the mark so the queue advances and the loop drains
as it would live, or (c) detect no-progress (same task id returned twice in a row) and abort with a clear
message. **(c) is what shipped**, and it also protects the live path against a session that silently fails
to tick.

## [FIXED] ISSUE-139: Night-shift loop sweeps unrelated working-tree changes into its commits
**Found:** 2026-08-08, during calibration pipeline repair
**Fixed:** 2026-09-16, in roadmap task T0.1 — `expand_loop.sh` `preflight_worktree` refuses to run in the primary checkout or an unprovisioned worktree; recipe in `OVERNIGHT_LOOP.md` § Quick start. Validated: a concurrent primary-checkout edit stayed out of a worktree loop commit (`1cb2fa8d` on `loop-validate-2`).
**Severity:** P2 (annoying)
**Where:** `scripts/expand_loop.sh` / `/expand-linear-next` commit step
**Description:** The unattended loop stages the whole working tree, so changes made by a concurrent
interactive session are absorbed into whatever roadmap commit the loop is writing. Observed
concretely: an interactive fix to `evals/eval_records.py` (`read_transcript` gen-dir support) plus
its regression tests were committed under `24f6a01 feat(evals): capability_rate as first-class
metric (EVAL-P9.4)`, a commit that has nothing to do with them. HEAD moved from 73e6c36 to 9fa5493
mid-session. Consequences: misleading history, `[UNVERIFIED: regression]` tags applied to code the
loop never gated, and a real risk of the loop committing half-finished interactive work.
**Why deferred:** Not blocking; the calibration work was committed separately and intact. Fixing it
means changing the loop's commit step, which is CI-adjacent and needs its own task.
**To fix:** Have the loop stage explicit paths (or `git stash push --keep-index` around its commit),
and refuse to commit when the tree contains modifications it did not make. Alternatively run the loop
in a dedicated worktree so interactive sessions cannot collide with it.

## [FIXED] ISSUE-334: `military` resolves a battle every tick while its docstring calls it a no-op stub
**Found:** 2026-09-07, during full-review (L13-03, L10-04)
**Fixed:** 2026-09-16, in T1.2 — military engine deleted entirely; stale docstring dies with the engine.
**Severity:** P2
**Where:** `src/npc_engine/scheduler/tick_scheduler.py:131-132`; `src/npc_engine/engines/military/`
**Description:** `MilitaryEngine` resolves battles and processes resource yield for real, reporting `battles_resolved: 1` on every tick indefinitely. The scheduler docstring calls it a no-op stub and cites `ISSUE-001`, an unrelated already-resolved issue. The underlying no-op was fixed 2026-06-19 (ISSUE-111); only the comment never caught up. This stale docstring is why the brief for this very review described `military` as a stub — and it is the engine that auto-loses the demo.
**Why deferred:** The engine's *behaviour* is covered by the CRITICAL demo auto-lose decision; this entry is the docstring half.
**To fix:** Correct the docstring and drop the wrong ISSUE reference. Also see CR-L14-01/CR-L09-06 (stale session-kwarg tests in the same directory).

## [FIXED] ISSUE-338: `scenario_mood_contagion` passes vacuously — the two NPCs are never co-located
**Found:** 2026-09-08, during the A/B-readiness analysis
**Fixed:** 2026-09-17, in T4.1 — superseded by deletion. MoodContagionEngine deleted; scenario
removed from `evals/scenario_adapters_extra.py`. Proposing a "mood change" assertion is now actively
wrong advice for a mechanism that no longer exists.
**Severity:** P2 (annoying — a promoted scenario that cannot fail)
**Where:** `evals/scenario_adapters_extra.py:187-211`
**Description:** The scenario posts a Location with `{id, name, description, last_graph_updated_at}`.
`description` is not a declared field on `location.yaml` and `location_tag`/`descriptor` are required
and missing, so the POST 422s; the return is unchecked. Both subsequent `LOCATED_AT` POSTs then 404 on
the missing destination node, so the two NPCs are never co-located and mood contagion never runs on
them. The assertion is only that both `current_mood` values are non-`None` — which is true from
creation, since `_char(...)` sets `current_mood`. The scenario therefore passes without exercising the
behaviour it names. The `RELATES_TO` POST at `:197-202` also omits `last_updated_at`, which is
`required: true`, so it 422s as well.
**Why deferred:** as ISSUE-336.
**To fix:** correct the Location and `RELATES_TO` property sets, check every POST return, and assert a
mood *change* rather than mood presence.

## [FIXED] ISSUE-360: the loop worktree's venv has no `pygame`, so `make test-demo` cannot collect the demo UI tests
**Found:** 2026-09-18, while verifying the demo clock-timeout fix
**Severity:** P2 (annoying)
**Where:** `NPCSystem-loop/.venv` (the overnight loop's worktree); `scripts/loop_gates.py:80` (`DEMO_GATE_CMD`)
**Description:** `import pygame` fails in the loop worktree's venv, so `make test-demo` there stops
with 12 collection errors (`demo_game/tests/ui/*`). The loop runs `make test-demo` for every task that
touches `demo_game/`; the 2026-09-17 night's T4.3, T5.1 and T5.2 transcripts all hit
`No module named 'pygame'`. The demo UI tests have therefore not been a working gate in the loop.
Separately, `test_run_dry_run_encoding.py` needs `NPC_API_KEY` in the environment and fails without it.
With the main checkout's venv and `NPC_API_KEY=x`, the loop tree's demo suite is 1157 passed.
**Why deferred:** environment setup of the loop worktree, not the task at hand (fixing the misplaced T3.2
commit and the demo timeout).
**To fix:** `pip install -r demo_game/requirements.txt` into `NPCSystem-loop/.venv`; make `test-demo`
set a dummy `NPC_API_KEY` (or the test set its own); consider a loop preflight that fails when
`import pygame` fails.
**PLAN 2026-09-18 (owner, adjusted by review):** install `demo_game/requirements.txt` into the loop
venv; add `pygame` to `preflight_worktree`'s import check **and** its provisioning message and
OVERNIGHT_LOOP.md's quick start; set `NPC_API_KEY` with `monkeypatch.setenv` inside
`test_run_dry_run_encoding.py`, not as a Makefile default.
**Fixed:** 2026-09-18, in fix(loop): provision pygame in the loop venv and make the dry-run test self-sufficient (auto/roadmap-night)

## [FIXED] ISSUE-358: the per-minute LLM ceiling only admits ticks; one admitted tick made 12 calls against a limit of 6
**Found:** 2026-09-18, while analysing the demo-run-live failure
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/scheduler/tick_scheduler.py` (`_resolve_skip_llm`, `_record_budget_calls`); DEC-285
**Description:** `TICK_LLM_CALLS_PER_MINUTE_MAX` is 6. DEC-285 checks `should_skip_llm()` once before the
tick and records the tick's call count afterwards, so a tick admitted with budget left may use any
number of calls. Measured on the eval stack @ `3019b51e`: tick 1 made 12 LLM calls in ~15 s (event_quest 2,
need_quest 10). The only in-tick cap is `QUEST_TRIGGER_MAX_LLM_INVOCATIONS_PER_TICK=10` invocations
(×2 calls each). Whether that is intended (the ceiling throttles the *next* ticks) or a gap is not recorded
in DEC-285.
**Why deferred:** a design question about T7.1's semantics, not part of fixing the demo timeout.
**To fix:** decide whether the ceiling is an admission gate or a hard cap. If a hard cap, pass the guard's
remaining budget into the quest triggers' `TickLLMBudget` for the tick. Either way, state it in DEC-285.
**PLAN 2026-09-18 (owner):** it's an admission gate. Amend DEC-285 and the setting's comment in
`config.py` to say so, then close this issue. A note in T8.1 (added) says any future hard per-minute
cap belongs in T8.1's LLM-layer gate.
**Fixed:** 2026-09-18, in docs(decisions): record the per-minute LLM ceiling as an admission gate (auto/roadmap-night)

## [FIXED] ISSUE-357: `check_engine_census` treats a folder holding only `__pycache__` as a live engine
**Found:** 2026-09-18, while cherry-picking T3.2 onto `auto/roadmap-night`
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_engine_census.py:199` (`engines_dir.iterdir()` / `is_dir()`)
**Description:** Git deletes an engine's tracked files but leaves the untracked `__pycache__/` behind, so
`engines/<name>/` still exists on disk. The census then reports it as unwired or dead and fails `make check`
locally, although the clean tree is correct (a fresh clone passes). Hit with `faction_politics/` and `treaty/`.
**Why deferred:** `scripts/check_engine_census.py` is a frozen gate path (`loop_gates.FROZEN_PATH_PREFIXES`);
changing a gate needs owner review, not a drive-by edit.
**To fix:** skip directories that contain no `*.py` outside `__pycache__` (the script already has
`rglob("*.py")` at `:122`), with a test for a pycache-only directory.
**Fixed:** 2026-09-18, in fix(census): ignore engine folders that hold only __pycache__ (auto/roadmap-night)

## [FIXED] ISSUE-356: gossip tick still an outlier after T7.3 embedding-reconcile fix
**Found:** 2026-09-18, during T7.4
**Severity:** P1 (blocking — gossip tick is ~46× its neighbours)
**Where:** `src/npc_engine/engines/gossip/gossip_handler.py`, gossip tick path (SEV-07)
**Description:** T7.3 hoisted the embedding reconcile from O(N) per pair to O(1) per tick, reducing the gossip tick from 22,484 ms to 19,797 ms on the 301-node seed (~12% improvement, same world both trees). Neighbours run in 77–425 ms; gossip is still >46× the slowest non-LLM neighbour. The T7.3 fix addressed the corpus-reconciliation component; the dominant cost lies elsewhere in the gossip handler.
**Why deferred:** Identifying the remaining bottleneck requires profiling the gossip handler with a running stack, which is outside T7.4's scope (measurement only). A new fix task is needed.
**To fix:** Profile the gossip tick against the eval stack to find the dominant remaining bottleneck; implement a targeted fix; re-run T7.4's measurement protocol to confirm the outlier is resolved.
**UPDATE 2026-09-18 (re-diagnosed, measured):** the premise above is wrong. The slow cost is not in
the gossip handler; it's the first `get_encoder` call in the process, which lazily imports
`sentence_transformers`/`torch` (11.3 s) and builds the model (10.0 s) inside the first gossip tick after
boot. On the same stack the second gossip tick takes 1,131 ms (`57fe6bf4`) and 1,449 ms (`3019b51e`),
against 23,471 ms and 19,221 ms for the first. T7.4's two figures were both first-after-boot ticks. Fix
is ROADMAP **T7.5** (warm the encoder at boot, owner decision 2026-09-18); T7.4's protocol is amended to
report first and second ticks.
**Fixed:** 2026-09-18, in measure(gossip): T7.3+T7.5 resolve SEV-07 — warm gossip after T7.3 is 1,322 ms (not an outlier: 0.1× slowest neighbour) (auto/roadmap-night, T7.4)

## [FIXED] ISSUE-361: `project-harness/ports_census.md` is a temporary file — delete by end of Sprint 5
**Found:** 2026-09-18, during T9.1a
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/ports_census.md`
**Description:** Census artifact created by T9.1a to drive T9.1b–d collapse batches. Once T9.1d closes and all 24 COLLAPSE rows are gone, this file has no further purpose and should be deleted.
**Why deferred:** The file is needed by T9.1b, T9.1c, and T9.1d.
**To fix:** Delete `project-harness/ports_census.md` at the end of T9.1d (end of Sprint 5).
**Fixed:** 2026-09-18, in T9.1d

## [FIXED] ISSUE-307: CLAUDE.md's inline layer diagram omits `observability/` and `setup/`
**Found:** 2026-09-07, during full-review (L2-06)
**Severity:** P3
**Where:** `project-harness/CLAUDE.md` (Architecture section); `scripts/check_layers.py:28-49`
**Description:** `LAYER_RANK` ranks `observability` and `setup` at rank 1 (`:45-49`, SHIP-03/DEC-127). The CLAUDE.md diagram — billed as "the one rule this file states in full" — lists 16 packages and omits both. DEC-249 says layer lists should be pointers precisely because inline copies rot; this one already has, for 2 of 18 ranked packages.
**Why deferred:** Both are leaf rank-1 dirs; no live impact.
**To fix:** Add the two rows, or replace the diagram with a pointer to `LAYER_RANK`.
**Fixed:** 2026-09-19, in T10.2c

## [FIXED] ISSUE-234: 21 tests call the SUT and assert nothing
**Found:** 2026-08-31, during R1.8
**Severity:** P2 (annoying)
**Where:** 18 files under `tests/unit/`; `make check-test-quality` lists them all
**Description:** `check_test_quality`'s NO_ASSERTION pattern, added in R1.8, found 21 tests
(corrected from the initial estimate of 25) that exercise the system under test and then
check nothing. They can only fail by raising.
Some are legitimate does-not-raise tests (`test_exact_fit_is_accepted`,
`test_no_op_when_already_utf8`, `test_exception_does_not_propagate`) and want a
`# quality-ok: <reason>` waiver naming what they prove. Others are probably genuinely weak
and want a real assertion. Which is which is a per-test judgment.
**Why deferred:** R1.8's task was to build the gate, not to spend its findings. Blanket-waiving
all 21 with a generic reason would buy conformance rather than quality — the exact effect
CR-L05-03 measured, and the reason R1.5 was told not to mass-edit.
**To fix:** triage the 21. Each either gains an assertion or a waiver with a specific reason.
Then `printf '0' > scripts/check_test_quality_baseline.txt` and update
`test_real_suite_is_clean` to drop the NO_ASSERTION exclusion, restoring the
zero-findings-plus-explicit-waivers invariant the other five patterns hold.
**Fixed:** 2026-09-21, in T11.1a (NO_ASSERTION, 21 findings fixed — 20 real assertions added,
1 test deleted) and T11.1b (BARE_EXCEPTION_RAISES, 31 findings fixed) and T11.1c
(VACUOUS_MOCK_NOT_CALLED, 8 findings fixed; existence-only and constant-equals-literal tests
also addressed). All 66 quality-ok waivers are resolved; no waivers remain in tests/.

## [FIXED] ISSUE-363: repository methods with no unit or integration coverage — input list for T11.3
**Found:** 2026-09-21, during T11.2
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/graph/repositories/` — public methods with no unit test and no integration-test path
**Description:** T11.2 strengthened delegate tests and deleted those superseded by integration tests. The
following repository methods were found with neither a unit test that can fail nor a path through
`tests/integration/`. T11.3 must add integration tests against the eval-stack Neo4j for each one.

Methods (54 total across 15 repository classes):
- `Neo4jChapterRepository`: `get_completed_quests_since_tick`, `get_max_beat_intensity_in_chapter`
- `Neo4jEmotionBootstrapRepository`: `get_emotion_fields`
- `Neo4jIdempotencyRepository`: `ensure_constraints`, `get_record`, `create_pending_if_absent`, `upsert_pending`, `mark_completed`, `mark_failed_terminal`, `delete_expired`
- `Neo4jIntentRepository`: `get_player_location`, `get_unmet_needs`, `get_unresolved_goals`
- `Neo4jInteractionRepository`: `count_player_was_at`
- `Neo4jInvestigationRepository`: `get_suspects_for_event`, `get_witnesses_of_event`
- `Neo4jPoliticalRepository`: `get_agenda_votes`, `get_expired_open_agendas`, `set_agenda_status`
- `Neo4jProactiveMemoryReadRepository`: `get_unshared_memories`
- `Neo4jQuestGenerationRepository`: `get_world_state_day_and_rate`, `get_world_state_context`, `get_character_info`, `get_giver_context`, `get_candidate_ids_by_label`, `create_quest`, `record_causation`, `check_node_labels`, `get_template_skill_requirements`, `check_skill_threshold`
- `Neo4jEventTriggerRepository`: `get_unprocessed_trigger_events`, `get_military_npc_at_location`, `get_any_military_npc`, `has_draft_quest`
- `Neo4jNeedTriggerRepository`: `get_all_needs_below_threshold`, `has_draft_quest`
- `Neo4jQuestLifecycleRepository`: `get_quest_state`, `persist_state_and_event`, `emit_lifecycle_event`, `update_quest_node_status`, `get_world_state`
- `Neo4jQuestOfferRepository`: `get_quest`, `update_quest_node_status`, `offer_quest_atomic`
- `Neo4jQuestChainRepository`: `get_quest`, `get_unlocked_quests`, `get_choice_unlocked_quest`
- `Neo4jQuestRewardRepository`: `get_quest_state`, `get_character_balance`, `emit_lifecycle_event`, `apply_rewards_atomic`
- `Neo4jRoutineRepository`: `clear_routine_override`
- `Neo4jWorldStateRepository`: `get_world_state`, `upsert_world_state`

**Fixed:** 2026-09-21, in T11.3
**Why deferred:** T11.2 is the unit-side only (spec split 2026-09-17). T11.3 owns the integration half.
**To fix:** T11.3 — add integration tests for each method listed above against the eval-stack Neo4j
(`bash scripts/eval_stack_at.sh HEAD --reset`, then `NEO4J_URI=bolt://localhost:7688`). Start with
the methods called by the highest-traffic engine paths (quest lifecycle, routine tick, intent).

## [FIXED] ISSUE-321: `BASELINE_2026-08-28.md` no longer matches the tree
**Found:** 2026-09-07, during full-review (L9-09)
**Severity:** P2
**Where:** `project-harness/review-2026-08/BASELINE_2026-08-28.md`
**Description:** Measured at HEAD `8d30a3e1`: `make test` is 4,571 passed / 41 skipped (baseline records 4,048 / 36); coverage 88.13% (baseline 87.86%). The file's stated purpose is that "a number that moved without an explanation is a finding" — but it is a point-in-time record that must not be edited, so "no delta" can no longer be used as a check against it.
**Why deferred:** The file is deliberately immutable.
**To fix:** Capture a new dated baseline for the post-review cycle and point `/fix-next` at it, leaving the 2026-08-28 file as history.
**Fixed:** 2026-09-21, in T12.2 — `project-harness/BASELINE_2026-09.md` supersedes this.

## [FIXED] ISSUE-370: the overnight loop halts on a bare CLI `Execution error` instead of retrying once
**Found:** 2026-09-21, during post-loop review (T14.1 halt)
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/expand_loop.sh` (`looks_like_usage_limit`, no-status-token halt)
**Description:** T14.1's session printed only `Execution error` and exited after 14 s. That does not
match the usage-limit pattern, so the loop halted the night. The 400 s headroom sleep before it
also returned after ~22 s (cause unknown).
**Why deferred:** The halt is the safe failure. A retry path needs guards like the usage-restart ones.
**To fix:** Treat a log that holds only `Execution error` as transient: retry the task once after
a short sleep, then halt as today.
**Fixed:** 2026-09-24, in the ISSUE-370 loop-retry commit — `run_one_task` retries a bare `Execution error` once after `TRANSIENT_RETRY_SLEEP_SECS`; pinned by `tests/unit/scripts/test_expand_loop_execution_error.py`.

## [FIXED] ISSUE-368: `/readiness` is unauthenticated, contrary to "auth on every route except GET /health"
**Found:** 2026-09-21, during post-loop review of T12.1
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/auth/middleware_helpers.py` (`is_public_path`: `HEALTH_PATH, READINESS_PATH`)
**Description:** CLAUDE.md's strict rules and T12.1's spec both say only `GET /health` is public.
`/readiness` is hard-coded public in every env. T12.1 neither tested nor logged the conflict;
`test_public_route_set_is_pinned` now records it as the current surface.
**Why deferred:** Changing the public surface is an interface change (ask-first). Orchestrator
probes may depend on it.
**To fix:** Owner decides: gate `/readiness`, or amend the rule and record a DEC. Then update
`_EXPECTED_PUBLIC` in `tests/unit/api/test_create_app_auth_wiring.py`.
**Fixed:** 2026-09-24, in DEC-289 — owner kept `/readiness` public; the auth rule in `project-harness/CLAUDE.md` now names `GET /health` and `GET /readiness`. No code change (`_EXPECTED_PUBLIC` already held both).

## [FIXED] ISSUE-371: `test_revived_engines_do_work` is flaky on a freshly seeded eval stack
**Found:** 2026-09-21, during post-loop review (integration run for the ensure_constraints fix)
**Severity:** P2 (annoying)
**Where:** `tests/integration/test_revived_engines_do_work.py::test_routine_and_need_decay_do_work`
**Description:** After `eval_stack_at.sh --reset`, both tests fail because nothing is seeded (the
test does not seed; `make eval-stack-seed` is a manual step). Once seeded, the routine test failed
on the first run (`routine.moved=0 across 3 ticks`) and passed on the next without any change. The
result depends on the world clock's phase, and `check-integration-baseline` treats it as a new
failure when it lands wrong. CI's required `integration-tests` job can red on this at random.
**Why deferred:** Not caused by the review fixes. Making it deterministic needs a fixed clock
start, which is test-design work.
**To fix:** Have the test set the clock to a known pre-transition time before advancing, and seed
(or skip with a clear reason) when `FOLLOWS_SCHEDULE` edges are absent.
**Fixed:** 2026-09-24, in the ISSUE-371 commit — the test now pins `WorldState.time_of_day` to `morning` before advancing (a slot where every seeded routine NPC has a different target than the next one, so a move is guaranteed whatever the prior state) and skips with a reason when `FOLLOWS_SCHEDULE` edges or the `WorldState` node are absent. Verified against the eval stack (:7688): unseeded run skips; seeded, 3 of 3 runs pass. The original one-off `moved=0` was not reproduced on demand. `test_npc_top_need_is_populated` is unchanged, since its job is to detect missing HAS_NEED edges. See ISSUE-373 for why `moved` is a weak signal.

## [FIXED] ISSUE-366: ~33 of T11.3's 54 repository methods are integration-tested only on the empty path
**Found:** 2026-09-21, during post-loop review of T11.3
**Severity:** P2 (annoying)
**Where:** `tests/integration/test_*_repository_integration.py` (the six files T11.3 added)
**Description:** About 21 of the 54 ISSUE-363 methods get a write-then-read-back check. The rest
are exercised only against absent ids, or asserted only by `isinstance(result, list)` / key
presence — e.g. all six intent-file tests, `get_quest`, `get_unlocked_quests`,
`get_candidate_ids_by_label`, `get_unprocessed_trigger_events`. Gutting one of these to return
`[]`/`None`/`0` stays green. They do still catch Cypher syntax and schema errors. T11.3's
five-method counterfactual sampled only methods with positive assertions, which is why it
caught all five.
**Why deferred:** Post-loop review scope was repairs only; ~33 positive-path tests is new work.
**To fix:** For each method, seed the minimal nodes and assert the returned values. Re-run the
counterfactual on the **first five methods in ISSUE-363 list order**, not a chosen sample.
**Fixed:** 2026-09-24, in the ISSUE-366 commit — the four files that were empty-path-only (intent/interaction/investigation, chapter/political/emotion, quest, quest-generation) now seed minimal data and assert returned values (integration run: 107 -> 140 tests executed). The idempotency and world-state/routine files already had positive paths and are unchanged. Counterfactual on the first five methods in ISSUE-363 list order (`get_completed_quests_since_tick`, `get_max_beat_intensity_in_chapter`, `get_emotion_fields`, `ensure_constraints`, `get_record`): gutted one at a time, all five tests went red, restored. Five more spot checks (`get_unmet_needs`, `get_unlocked_quests`, `get_quest`, `get_candidate_ids_by_label`, `get_unprocessed_trigger_events`) also went red. `make check-integration-baseline` with `NEO4J_URI=bolt://localhost:7688`: OK, no new failures (3 known). Not covered: `apply_rewards_atomic` item rewards / delivery objectives (outside this issue), and the goal text in `get_giver_context` (ISSUE-374).

## [FIXED] ISSUE-273: `WorldStateQuestTrigger` writes one draft Quest per tick forever — 23,292 leaked nodes
**Found:** 2026-09-03, during the metrics-readiness review
**Severity:** P1 (blocking) — it poisons every graph-scale, retrieval and NFR measurement
**Where:** `src/npc_engine/engines/quest_generation/world_state_quest_trigger.py:80-118`
**Description:** `run_tick` generates a draft quest whenever `world_state.epoch` maps to an
archetype in `_EPOCH_ARCHETYPE_MAP`. The `world` WorldState node sits permanently at
`epoch="war"`, so the condition is true on every tick. The only guard is the instance
sentinel `self._last_triggered_tick == tick_id`, which dedupes the *same tick fired twice*
— not the same *condition* firing across successive ticks. `_pick_npc` resolves through
`get_any_military_npc` (`LIMIT 1`), so every quest names `captain_sorn`. No cap, no prune,
and `_generate_for_epoch` passes no `cause_event_id`, so no `CAUSED_BY` edge is written and
nothing can ever mark the condition consumed.

Measured live: 23,292 `:Quest {source:"generated", status:"draft"}` nodes plus 23,292
`HAS_QUEST` edges against ~681 nodes of real world content (27,529 nodes total). Only 2
quests carry a `CAUSED_BY` edge — those are `EventQuestTrigger`'s, whose
`NOT ((:Quest)-[:CAUSED_BY]->(e))` guard works correctly and matches the 2 `conflict`
events exactly. Growth begins 2026-08-27 (1,053), peaks 2026-08-29/30 (~7,100/day) and is
still live (122 on 2026-09-03). Each node is one LLM call, so this also burns generation
time on every tick.

Contrast `need_quest_trigger.py:117`, which does hold a real idempotency guard
(`has_draft_quest`) keyed on outstanding state rather than on tick identity.

**Why deferred:** raised during a review task, not patched inside it. Now **scheduled as
ROADMAP task M1.1**, which fixes the guard, adds the growth regression test, and blocks the
wipe/reseed in M1.3 behind it — a wipe before the fix refills within a day.
**To fix:** replace the tick sentinel with a state-keyed guard. Three candidates, in
preference order: (a) mirror `need_quest_trigger` — skip when the quest-giver already
holds an outstanding draft quest; (b) key on the epoch itself, so one `war` epoch yields
one quest until the epoch changes; (c) pass a `cause_event_id` and reuse the `CAUSED_BY`
guard that already works in `EventQuestTrigger`. Whichever is chosen, add a cap on draft
quests per NPC and a prune path for stale drafts, and add a regression test that runs N
ticks under a stable epoch and asserts the quest count does not grow with N. The 23,292
leaked nodes must be deleted before any graph-scale or retrieval number is measured, and
the fix must land first or the wipe refills.
**Fixed:** 2026-10-20, in T16.1. The `has_draft_quest` guard now exists at
`engines/quest_generation/world_state_quest_trigger.py:155` — mirrors `need_quest_trigger`
option (a) above. Verified: `:Quest` node count held at 18 across 6 tick advances.

## [FIXED] ISSUE-320: `check-rules` reports a resolved baseline entry on every run and never ratchets it down
**Found:** 2026-09-07, during full-review (L9-07)
**Severity:** P3
**Where:** `scripts/rules_baseline.txt`, `scripts/check_rules.py`
**Description:** A baseline entry whose underlying violation is resolved is still reported each run; the ratchet does not remove it. A baseline that cannot shrink stops being a ratchet.
**Why deferred:** Cosmetic noise.
**To fix:** Prune resolved entries and make the ratchet remove them automatically.
**Fixed:** 2026-09-24, in T14.2. `_run_check` now loads the old baseline and prunes resolved entries (ratchet-down-only semantics) rather than replacing the baseline with the full current-violations set. Two stale R006 entries removed.

## [FIXED] ISSUE-301: `API_KEY_GRAPH_WRITE`/`API_KEY_GRAPH_ADMIN` have no weak-secret validation
**Found:** 2026-09-07, during full-review (L1-02)
**Severity:** P2
**Where:** `src/npc_engine/config_validators.py`, `src/npc_engine/config.py`
**Description:** `API_KEY_SECRET` has a weak-secret validator rejecting shipped defaults in staging/prod. The two higher-privilege scopes, `API_KEY_GRAPH_WRITE` and `API_KEY_GRAPH_ADMIN`, have none — so the keys granting write and admin access can ship with a dev default while the lowest-privilege key cannot.
**Why deferred:** Not exploitable on the default loopback-bound deployment; the review's five CRITICALs took the slot.
**To fix:** Extend the existing validator to cover both fields. Non-breaking, internal.
**Fixed:** 2026-10-20, in T15.3. Added `check_optional_api_key_secret` to `config_validators.py` and a `_validate_optional_api_keys` model_validator to `Settings` that rejects weak values when either optional key is explicitly set.

## [FIXED] ISSUE-302: admin-scoped `npc_ids`/`location_ids` request lists have no upper bound
**Found:** 2026-09-07, during full-review (L1-03)
**Severity:** P3
**Where:** `src/npc_engine/api/routes/admin/batch.py`, `graph_admin.py`
**Description:** Batch admin endpoints accept unbounded `npc_ids`/`location_ids` lists. CLAUDE.md requires input caps at the API boundary; these have none.
**Why deferred:** Admin-auth gated, so the blast radius is an authenticated operator only.
**To fix:** Add a `max_length` to the list fields, sized from realistic batch use.
**Fixed:** 2026-10-20, in T15.3. Added `ADMIN_ID_LIST_MAX_LENGTH = 200` constant and `max_length=ADMIN_ID_LIST_MAX_LENGTH` to `npc_ids` in `GossipTickRequest` and `ReindexRequest`, and to `location_ids` in `EventTickRequest`. Over-cap requests now return 422.

## [FIXED] ISSUE-303: `is_public_path` treats `/setup` as a prefix match, not a route allow-list
**Found:** 2026-09-07, during full-review (L1-04)
**Severity:** P3
**Where:** `src/npc_engine/auth/middleware_helpers.py:71-72`
**Description:** The public-path check appears to prefix-match `/setup` rather than matching an explicit route allow-list, so a future route beginning with that prefix would be public by accident. Graded **Suspected** — not confirmed by a live request.
**Why deferred:** Unconfirmed, and the `/setup/*` surface is already env-gated and loopback-bound (CR-L05-11 fixed).
**To fix:** Confirm by adding a route under the prefix and asserting it is NOT public; then convert the check to an exact allow-list.
**Fixed:** 2026-10-20, in T15.3. Replaced `SETUP_PATH_PREFIX = "/setup"` + `path.startswith(...)` with `SETUP_PATHS = frozenset({"/setup/validate", "/setup/config"})` + `path in SETUP_PATHS`. Confirmed the defect was real: `/setupmalicious` and `/setup-evil` were treated as public in dev before the fix.

## [FIXED] ISSUE-354: `GET /v1/admin/factions/{id}/standings` returns 500 due to response model mismatch
**Found:** 2026-09-17, during T3.3 (live stack validation)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/api/routes/faction_politics/factions.py` (`FactionStandingRow`); `src/npc_engine/graph/faction/faction_queries.py` (`CYPHER_LIST_STANDINGS`, `list_standings`)
**Description:** `CYPHER_LIST_STANDINGS` returns `properties(b)` (the full target faction dict) for the `target` column, but `FactionStandingRow.target: str` expects a faction ID string. FastAPI raises `ResponseValidationError` on every request. Pre-existing — confirmed present in `db5b2c20` (before T3.2). The demo client's `_get_faction_standings_for` returns `[]` on the 500, so the client degrades gracefully, but the sub-endpoint is non-functional. STANDS_WITH edges are seeded and reachable via Cypher; only the HTTP endpoint is broken.
**Why deferred:** pre-existing; not introduced by T3.2; client degrades gracefully; does not block the live demo.
**To fix:** either change `CYPHER_LIST_STANDINGS` to `RETURN b.id AS target, r.standing AS standing` (and update `list_standings` accordingly), or update `FactionStandingRow.target` to accept a dict and rename the field. The Cypher fix is simpler and matches the response model's intent.
**UPDATE 2026-09-18 (analysis, no fix yet — owner to choose):** broken since `87038812` (2026-06-15),
which added `response_model=OkEnvelope[list[FactionStandingRow]]` with `target: str`; the query has
returned `properties(b)` since `6cfe763f` (2026-05-06). Consumers disagree on the shape:
`e2e/scenarios/scenario_faction_politics.py:94` reads `s["target"]["id"]` (dict) — and that scenario
asserts decay by the `faction_politics` engine deleted in T3.2, so it is obsolete either way; the demo
client and faction board expect `src_id`/`dst_id` rows and are never called (ISSUE-359). After T3.2
no tick engine mutates standings. Other readers: the chapter engine reads a top-5 summary internally
(`get_faction_standings_summary`); this GET is the dedicated per-faction HTTP read.
**PLAN 2026-09-18 (owner, after adversarial review):** fix additively — keep `target: str`, add
`target_name: str`; no API-contract re-record. Scheduled as ROADMAP **T15.4**.
**Fixed:** 2026-10-20, in T15.4. Changed `CYPHER_LIST_STANDINGS` to `RETURN b.id AS target, b.name AS target_name, r.standing AS standing`; updated `list_standings` to map the flat columns; added `target_name: str` to `FactionStandingRow`. Deleted `e2e/scenarios/scenario_faction_politics.py` (its sole assertion was decay by `faction_politics` engine removed in T3.2). No API-contract re-record needed — change is additive.

## [FIXED] ISSUE-318: `llm_tokens_in_total` excludes the system channel and under-counts input tokens 4.3×
**Found:** 2026-09-07, during full-review (L9-05)
**Severity:** P2
**Where:** `src/npc_engine/engines/llm/llm_metrics.py`
**Description:** Measured live: the counter omits the system channel, so real input tokens are ~4.3× the reported figure. Any prompt-budget reasoning done from this metric is wrong by that factor — directly relevant given the ~4,245-token static system prompt.
**Why deferred:** Observability defect, not a runtime failure.
**To fix:** Include the system channel, and state the change in DECISIONS since it moves a published number.
**Fixed:** 2026-10-20, in T16.2. Added `record_llm_input_tokens` to `llm_metrics.py`; updated `DialogueLLMClient` to call it, counting both prompt and system channels. See DEC-292.

## [FIXED] ISSUE-319: the latency instrumentation cannot express the budget it exists to defend
**Found:** 2026-09-07, during full-review (L9-06)
**Severity:** P2
**Where:** `src/npc_engine/engines/llm/llm_metrics.py:12-14`
**Description:** `llm_backend_latency_seconds` is a count/sum/min/max summary with **no buckets**, so no p50/p95 is derivable from the metrics endpoint. The 3–7s dialogue budget is a percentile claim that the shipped instrumentation cannot evaluate.
**Why deferred:** DEC-273's instrumentation work just landed; this is the follow-on.
**To fix:** Add histogram buckets sized around the 3–7s budget.
**Fixed:** 2026-10-20, in T16.2. Added `observe_histogram` / `observe_histogram_metric` to `MetricsRegistry`; `record_llm_backend_metrics` now uses a histogram with `LATENCY_BUDGET_BUCKETS = (0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 30.0)`.
## [CLOSED] ISSUE-355: `demo_game/client.py` docstring says `delta_ticks` accepts "1–1000" after the cap was lowered to 10
**Found:** 2026-09-18, during T6.1
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/client.py:292`
**Description:** The `advance_clock` docstring says "Number of ticks to advance (1–1000)." but MAX_DELTA_TICKS was lowered to 10 in T6.1; the docstring is now stale.
**Why deferred:** `demo_game/client.py` is outside the Files list for T6.1; touching it would widen the diff beyond the task scope.
**To fix:** Update the docstring to say "1–10" (or reference `MAX_DELTA_TICKS`).
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-342: 494 untracked log files sit in `project-harness/` with no retention policy
**Found:** 2026-09-09, during the pre-T tidy of `project-harness/`
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/.loop-logs/` (465 files), `overnight_logs/` (27), `logs/` (1)
**Description:** Four directories of machine-local run output accumulate at the top level of
`project-harness/`. All are gitignored (`.gitignore:2`, `:89`, and the global `*.log`) and zero of
their files are tracked, so they are invisible in a fresh clone but dominate the folder on disk and
in every `ls`. Nothing prunes them: `.loop-logs/` has grown to 465 files across every loop run since
the harness was written, and each gate log is paired with a `.class` sidecar.
**Why deferred:** Deleting run output is not an archiving task, and `overnight_logs/` is an active
write target for `scripts/` — a retention rule needs to be agreed, not improvised, and belongs with
the loop work the T programme already schedules against `OVERNIGHT_LOOP.md`.
**To fix:** Decide a retention window (last N runs, or age-based), implement the prune in the loop's
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
own teardown so it runs where the writes happen, and record the window in `OVERNIGHT_LOOP.md`.
Consider relocating all four under one gitignored `project-harness/.run-artifacts/` so the top level
shows one entry instead of four.

## [CLOSED] ISSUE-341: four comments cite `project-harness/Run-OvernightCombined.ps1` and `scripts/run_eval_k3.ps1`, neither of which exists
**Found:** 2026-09-09, during the pre-T tidy of `project-harness/`
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile:863`; `scripts/Run-EvalHarness.ps1:8`, `:143`, `:202`, `:205`
**Description:** Five comments explain current behaviour by pointing at two scripts that are not in
the tree. `Makefile:863` justifies stopping the app during a restore by saying it matches "what
`project-harness/Run-OvernightCombined.ps1` already does"; `Run-EvalHarness.ps1` says it supersedes
`project-harness/scripts/run_eval_k3.ps1` and three times defers to `Run-OvernightCombined.ps1` for
how the API key travels and how dirtiness is handled. `project-harness/Run-OvernightCombined.ps1`
and `project-harness/scripts/` do not exist, and `project-harness/scripts/run_eval_k3.ps1` was
self-declared TEMPORARY. A reader following any of these to check the claim finds nothing, and the
rationale for the app-stop in the restore path is left resting on a file that cannot be read.
**Why deferred:** Found during a tidy scoped to `project-harness/`; fixing it edits `Makefile` and
`scripts/`, both outside that scope, and the DEC-200 key-handling rationale in `Run-EvalHarness.ps1`
needs to be restated from what is actually true today rather than re-pointed.
**To fix:** Establish whether `Run-OvernightCombined.ps1` was deleted or renamed (check the history
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
of `scripts/Run-EvalHarness.ps1`). Then either restore the reference to the surviving script or
inline the behaviour each comment is deferring to — the app-stop rationale at `Makefile:863` and the
`$env:API_KEY_SECRET` convention at `Run-EvalHarness.ps1:143` should stand on their own.

## [CLOSED] ISSUE-340: `RunStatus.provenance` is declared and never written, so a re-derived status is indistinguishable from a live one
**Found:** 2026-09-08, during the A/B-readiness analysis (DEC-281)
**Severity:** P2 (annoying — it does not corrupt a number, but it removes the one field that would
let a reader tell how a number was produced)
**Where:** `evals/run_status.py:114` (declaration), `evals/judge_run_artifacts.py:137-148`
(`build_status`), `:97-107` (`with_panel_metrics`), `:164` (`record_error`)
**Description:** `RunStatus.provenance: str = ""` is documented as "How this status was produced when
it was not a live pass (e.g. re-derived from a legacy artifact). Empty for a normal run."
(`run_status.py:88-90`). **No code anywhere sets it** — not `build_status`, not
`with_panel_metrics`'s `model_copy` update dict, not `record_error`. A repo-wide grep finds only the
declaration. It is dead config, which the T programme's rules 3 and 6 forbid.

The one artifact in the tree that needed it proves the gap.
`evals/generations/k3_61b01dad_negadv/run_status.json` carries `provenance: ""` while its sibling
`RECOVERED_NOTE.md` states the file "was reconstructed from `judged_panel_votes.jsonl` +
`outputs.jsonl` without re-running the panel" (DEC-265, after the ISSUE-288 `write_report` crash).
Its `report_path` is that hand-written note rather than a rendered report.
`trend_row_builder._panel_fields` consumes its kappas exactly as it would a live pass's.

**Scope note, so this is not overstated:** the panel judging for that run *did* complete normally —
`judged.jsonl` and `judged_panel_votes.jsonl` were written correctly and the recovered kappa
(0.8314) is computed from genuine votes. Only the status file was re-derived. So no recorded number
is wrong; what is missing is the ability to *know* that from the artifact alone.

**Why this matters now:** ROADMAP Sprint 9's premise cites "panel kappa swung 0.58 to 0.83 between
runs". Those two values are `k3_77688e7_regen1` (0.5807) and `k3_61b01dad_negadv` (0.8314) — runs
with **different case populations**: capability n=16 / guard n=78 versus capability n=0 /
guard_adversarial n=111. T17.1 ("diagnose why each scorer is refused") should treat that swing as a
population difference first and instrument instability second, and `provenance` is one of the fields
that would have made the distinction legible without this archaeology.

**Why deferred:** DEC-281's scope is comparability and attributability of the *code state*; this is a
third provenance gap found in the same audit and is not on the critical path to a first A/B run.
**To fix:** either populate it — `build_status` takes it as a parameter, `record_error` sets a
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
literal, and the recovery path in DEC-265 sets it explicitly — **or** delete the field and rely on a
sibling note file, per rule 2. Deleting is cheaper and legitimate; if it is kept it must acquire a
writer, because a field nobody writes is worse than no field. Whichever is chosen, backfill
`k3_61b01dad_negadv`'s value or record in DEC-265 that it stays blank deliberately.

## [CLOSED] ISSUE-337: `probe_gossip` cannot observe propagation, and reads a key that does not exist
**Found:** 2026-09-08, during the A/B-readiness analysis
**Severity:** P2 (annoying — but it makes the module's stated purpose, ISSUE-228 instrumentation, a no-op)
**Where:** `evals/probe_gossip.py:56-81` and `:112`, against
`src/npc_engine/graph/gossip/gossip_queries.py:62-67` and
`src/npc_engine/graph/gossip/rumor_trace_service.py:21-28`
**Description:** Two independent defects. (a) Gossip pair selection matches
`(a:Character)-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(b:Character)`. `_seed_event_and_origin`
creates a Location node and a Character but **never writes a `LOCATED_AT` edge** — `location_id` is set
as a *property on the Event*, not an edge on the Character — so the origin NPC can never be selected as
a sharer and the event can never propagate. `propagation_reach` is pinned at 1.0, and the
`knowers_have_a_source` invariant filters out the origin's own edge and so passes on an empty set.
The Location POST also 422s (same root cause as ISSUE-336: `description` is not a declared field, and
`location_tag`/`descriptor` are required and absent). (b) `_distortion_deltas` reads
`row.get("distortion_level")`, but `CYPHER_TRACE_RUMOR_CHAIN` returns exactly `npc_id`, `npc_name`,
`knowledge_state`, `learned_at_tick`, `distorted_summary` — there is no `distortion_level`. So
`distortion_delta_per_hop_mean` is never emitted. `tests/unit/evals/test_probe_gossip.py:59-62`
hand-authors that key into a mock, which is why the test passes.
**Why deferred:** as ISSUE-336.
**To fix:** write a `LOCATED_AT` edge from the origin to a seeded Location that other NPCs occupy (the
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
seed provides `loc_tavern` with 5 co-located NPCs); fix the Location POST fields; and either surface
`distortion_level` from the trace query or compute the delta from `distorted_summary`.

## [CLOSED] ISSUE-339: 10 of 11 probes request engine status under a name the scheduler never registers
**Found:** 2026-09-08, during the A/B-readiness analysis
**Severity:** P3 (nice-to-fix — the effect is a missing metric floor, not a wrong number)
**Where:** `evals/probe_runner.py:204`, against `src/npc_engine/scheduler/tick_scheduler.py:346-369,452-545`
**Description:** `_merge_status_metrics` looks up `read_engine_status(client).get(probe.engine_name)`
and no-ops silently on `None`. The scheduler registers `story_pacing`, `gossip`, `event`, `routine`,
`chapter`, `memory_consolidation` plus the 22 from `_ordered_tick_engines()`. Only `probe_gossip`
(`"gossip"`) matches. `probe_events` declares `"events"` (scheduler key is singular `"event"`);
`probe_memory` declares `"memory"` (keys are `memory_consolidation`/`memory_decay`); `probe_quest`
declares `"quest"` (keys are `event_quest`/`need_quest`/`world_state_quest`); `probe_dialogue` declares
`"dialogue"`, which is request-driven and never tick-registered; and all six legacy adapters are
constructed with their *scenario id* as `engine_name`. So 10 of 11 probes silently get no
`tick_count`/`error_count`/`duration_ms`. Related: `probe_runner.py:10-11` and
`probe_protocol.py:44-46` both claim coverage of "all 46 engines" and cite `"quest_generation"` as a
key; neither is accurate.
**Why deferred:** as ISSUE-336.
**To fix:** map each probe to a real registered key (or several), correct the two docstrings, and log a
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
warning when a declared `engine_name` matches nothing rather than returning silently.

## [CLOSED] ISSUE-282: run_calibration's family_size still counts every >=2-adjudicated scorer, not every adequacy-passing one
**Found:** 2026-09-04, during the M1.4 label-adequacy fix
**Severity:** P3 (nice-to-fix)
**Where:** `evals/calibration.py::run_calibration` (`eligible`/`family_size`, immediately above
the per-scorer loop that now calls `label_adequacy.check_label_adequacy`)
**Description:** `run_calibration` computes `family_size` (for the Holm-Bonferroni disclosure)
from `eligible` — scorers with >=2 adjudicated rows — before the per-scorer loop, which now
separately refuses any scorer `check_label_adequacy` rejects. On the committed corpus all four
scorers pass the old `>=2` filter and enter `family_size`, then all four are refused by
adequacy inside the loop, so the Holm disclosure is computed for a family of scorers none of
which end up reported. This is conservative, not wrong — `family_size` only ever ends up equal
to or larger than the count of scorers that actually publish, so the resulting Holm-adjusted
bounds are wider than strictly necessary, never narrower — but the two numbers (`family_size`
and "scorers actually reported") can now diverge, which a future reader could misread as a bug
rather than a known conservative choice.
**Why deferred:** Recomputing `family_size` from `check_label_adequacy` instead of the `>=2`
filter collapses it to 0 whenever every scorer is refused (today's corpus), which deletes the
Holm-Bonferroni disclosure text entirely and breaks
`tests/unit/evals/test_calibration.py::test_calibration_report_names_family_size_and_holm_ci`,
which asserts "holm" appears in the output. DEC-260 records this as a deliberate choice for v1,
not an oversight.
**To fix:** Decide what a Holm disclosure should say when 0 scorers publish (a "no publishable
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
scorer this run" state distinct from "no Holm adjustment needed"), update the test's fixture or
assertion accordingly, then switch `eligible` to use `check_label_adequacy`.

## [CLOSED] ISSUE-283: the committed trend row (k3_77688e7_regen1) carries kappas measured on k3_73e6c36's labels
**Found:** 2026-09-04, during the M1.4 kappa-attribution fix
**Severity:** P3 (nice-to-fix)
**Where:** `evals/trend/trend_v1.jsonl` (the one committed row); `evals/trend_row_builder.py`
**Description:** Before this fix, `build_trend_row` computed `scorer_kappas` from whatever
`evals/calibration/labels_v1.jsonl` held at record time, with no check that those labels
named the run being recorded. The one row in the store — `gen_id=k3_77688e7_regen1` — was
built that way: its `scorer_kappas` are measured on `k3_73e6c36`'s 393 labels, not on
anything from `k3_77688e7_regen1`. `build_trend_row` now stamps `labels_gen_id` and refuses
a mismatch unless `allow_foreign_labels=True` is passed, but the store is append-only
(`trend_store.append_trend_row` refuses to overwrite a `gen_id`), so the existing row cannot
be corrected in place — only a new row can be attributed correctly going forward.
**Why deferred:** Rewriting store history is out of scope for a fix that made this exact
kind of silent mis-attribution impossible for every row recorded after it. The row is now
readable as unattributed (`labels_gen_id` would be `None` if reread) rather than falsely
attributed, which is the honest state to leave it in.
**To fix:** Either accept the one historical row as a known gap (it predates the provenance
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
fields entirely, so it can't even be backfilled without re-deriving which labels a 2026-08
run actually used), or regenerate `k3_77688e7_regen1` and re-record it once fresh, correctly
attributed labels exist for it.

## [CLOSED] ISSUE-279: faction-standing decay appends unbounded — the corpus grows ~2,500 nodes/hour while the app ticks
**Found:** 2026-09-04, during M1.3 (row 4 wipe/reseed/freeze)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/faction_politics/faction_politics_engine.py:171`; the
`:Event` half in the event tick.
**Description:** Every tick, the decay pass appends one `:FactionStandingEvent` per decaying
faction pair with `cause_rule_id="decay"`, and the event tick appends ~1 `:Event`. Measured
2026-09-04 against a freshly seeded world at the shipped `TICK_INTERVAL_SECONDS=10`: **+6
FactionStandingEvent and +1 Event per tick, exactly linear over 6 samples spanning 10 ticks**
(114 → 126 → 138 → 150 → 162 → 174). That is ~7 nodes/tick ≈ 2,500/hour. There is no retention
policy and nothing prunes them. A corpus frozen at 250 nodes passes the M1.3 `< 1,000` census
anchor for about thirteen minutes of uptime and then does not.

Two mitigating facts, both measured, neither a fix. **All of these nodes are orphaned** — 189
decay rows and 32 generated `battle` events all returned `count(r) = 0` for
`OPTIONAL MATCH (n)-[r]-()`. The RAG scope is relationship-based
(`graph/graph_rag_queries.py:86`), so it structurally cannot see them, which is why the M1.3
quiescence anchor held at exactly 18 ids for `captain_sorn` across 5 ticks while 189 nodes
appeared. So this is corpus noise and a reproducibility problem, not (today) a retrieval
correctness problem.
**Why deferred:** Row 4's scope is wipe/reseed/freeze, and bounding the writer is engine work
in `engines/faction_politics/` that the plan did not schedule. The measurement risk it created
is already closed by `make app-frozen` + `make check-corpus-frozen` (DEC-259), which stop the
writer for the length of a measurement run and gate that it actually stopped.
**To fix:** Either bound the history (retention window, or collapse repeated `decay` rows for
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
the same pair into one row with a count) or add a cleanup pass. Prefer bounding at the writer
over a sweeper — a sweeper is a second thing that can be forgotten. Note the same question
applies to generated `:Event` nodes, which unlike the decay rows *can* be retrieved once they
attach to a character.

## [CLOSED] ISSUE-280: `docker compose up`/`run` without the test override silently un-publishes Neo4j's bolt port
**Found:** 2026-09-04, during M1.3 (row 4)
**Severity:** P2 (annoying)
**Where:** `docker-compose.test.yml`; any `docker compose` invocation that omits it, including
`make eval-world-snapshot` (`Makefile:807`) and `make demo-restore` / `make eval-world-reset`
(`Makefile:830`), which all run `docker compose run` with the base file only.
**Description:** The published bolt port lives only in `docker-compose.test.yml` (opt-in per
DEC-232). Any later `docker compose` command that omits that file recomputes the desired state
from the base file, **recreates the neo4j container without the `ports:` stanza**, and every
integration run then fails to connect until someone re-ups with the override. Observed twice in
one session: `docker compose up -d app` and again `make eval-world-snapshot`, each time taking
`127.0.0.1:7687->7687/tcp` down to a bare `7687/tcp`.

It has a second, more confusing symptom. Recreating neo4j under a running app leaves the app
holding pooled connections to the dead container, so the next few requests return **HTTP 503**
with `GraphUnavailableError(... Failed to read from defunct connection ... OSError('No data'))`
against a database that is up and healthy. It looks like a data or label defect and is not one —
it clears once the pool refreshes.
**Why deferred:** Fixing it means either making the override sticky (a `COMPOSE_FILE` env
default) or teaching the snapshot/restore targets to pass it, and both touch how every developer
and CI invokes compose. Out of scope for a wipe-and-reseed task, and worth deciding deliberately.
**To fix:** Likely set `COMPOSE_FILE=docker-compose.yml:docker-compose.test.yml` in the
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
developer `.env`, or add the override to the `docker compose run` lines in the snapshot and
restore targets. Do **not** solve it by moving `ports:` into the base file — DEC-232 and the
header of `docker-compose.test.yml` explain why that is a real weakening of the isolation
posture.

## [CLOSED] ISSUE-277: the integration suite writes into the live Neo4j — there is no separate test database
**Found:** 2026-09-04, during M1.2 (row 0 baseline)
**Severity:** P2 (annoying)
**Where:** `docker-compose.test.yml`; `tests/integration/*`; `Makefile:182` (`test-integration`)
**Description:** `docker-compose.test.yml` does not stand up a second database. It publishes the
bolt port of the **same** `neo4j` service the application and the eval corpus use, so
`make test-integration` reads and writes the production graph. Proof is in the live data: the
graph holds `TickLease` rows whose `scheduler_id` is `"test-<uuid>"` — e.g.
`test-b84e331c-9333-4510-9b76-6e14029b83ce`, `test-64e15d2c-0fc3-43d7-8206-a79af623929e` —
alongside the 3,498 rows written by `scheduler_id = "main"`. Those `test-` leases are integration
runs, persisted in the same store as the corpus.

The operational consequence is that a frozen eval corpus is **not durable across an integration
run**. Any measurement taken after a corpus freeze is invalid if `make test-integration` ran in
between.
**Why deferred:** Fixing it properly means standing up a second Neo4j service (or a second
database inside the same instance) and pointing the integration suite at it — a compose and
configuration change well outside M1.2, and one that touches the test topology every gate
depends on. Sequencing the runs is sufficient for the current programme.
**To fix:** Add a dedicated `neo4j-test` service to `docker-compose.test.yml` on its own volume,
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
bound to loopback like the existing override, and have the integration suite read its URI from a
distinct variable. Until then, treat "no `make test-integration` between a corpus freeze and its
generation" as an operating rule (DEC-232).

## [CLOSED] ISSUE-278: `test_advance_creates_covert_event_and_step` flakes when the app container is running
**Found:** 2026-09-04, during M1.2 (row 0 baseline)
**Severity:** P3 (nice-to-fix)
**Where:** `tests/integration/test_scheme_advance_tick_integration.py:118`
**Description:** With `npcsystem-app-1` up, a full `make check` failed this test on
`assert row["step_order"] == 1` with `assert 2 == 1`. The test creates a scheme, asserts
`step_count == 0`, runs one `SchemeAdvanceTick.run_tick`, and expects the single resulting step to
be ordered 1. A second step existed. `next_order` is `scheme.step_count + 1`
(`engines/scheming/scheme_advance_tick.py:100`), so a concurrent writer that advanced the same
scheme explains the observed value; the app's live tick scheduler is that writer, and it shares
the database per ISSUE-277.

Run in isolation the test passed **both** with the app up and with the app stopped, so this is a
race, not a deterministic failure. It is in neither `scripts/integration_baseline.txt` nor
`project-harness/.loop-state/gate_baseline.json`, and both baselines were recorded while the app
was down.
**Why deferred:** It is a test-isolation defect that only manifests under a service topology the
Makefile does not prescribe — `Makefile:179` documents the integration prerequisite as
`docker compose ... up -d neo4j`, neo4j only. Not on M1.2's path.
**To fix:** Either scope `_read_step_event` to the step this run created rather than
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`.single()` over all `SCHEME_STEP` edges, or resolve ISSUE-277 so the suite cannot share a graph
with a live scheduler. Note the test's own `.single()` silently returns the first of several
records, which is what let a second step masquerade as the first.

## [CLOSED] ISSUE-275: trend rows attribute the label file's kappa to whatever generation is being recorded
**Found:** 2026-09-03, during M3 pre-flight verification
**Severity:** P1 (blocking) — every published kappa is attributed to a generation that did not produce it
**Where:** `evals/trend_row_builder.py:125-127` (`_scorer_kappas`), called at `:200`; CLI at `scripts/record_trend_and_gate.py:154`
**Description:**
`_scorer_kappas(labels_path)` reads the whole of `evals/calibration/labels_v1.jsonl` and runs
`run_calibration` over every row. There is no `gen_id` filter — `grep gen_id evals/calibration.py`
returns nothing — and no join of any kind between a label and the generation being recorded. The
row is then stamped with the CLI's `--gen-id`. The kappa block is therefore a property of the
label file, not of the run: any gen_id recorded today yields byte-identical kappas.

Observed in the shipped store. `evals/trend/trend_v1.jsonl` holds one row, `gen_id=k3_77688e7_regen1`.
All 393 rows of `labels_v1.jsonl` carry `gen_id=k3_73e6c36`. The row's n-values (tone 135,
affirms 135, anti_hallucination_grounded 48, refusal 75) are the raw label counts exactly.

That the n's are *exact* is the decisive evidence. Only 66.4% of labels survive against the
current case set, and `refusal_judge` and `anti_hallucination_grounded` have zero surviving rows
— so a legitimate join would have cut every one of these numbers. It did not, because no join
happens. Two attributed figures are consequently meaningless: `anti_hallucination_grounded`
kappa=1.0 CI [1.0, 1.0] against cases that no longer exist, and `refusal_judge` kappa=0.247 for a
scorer that scored nothing in that run (and which M3.2 retires).

This is **not** a `--merge` carry-forward. `--merge` exists only in `label_import` /
`label_merge.py`, operates on `labels_v1.jsonl`, and does not rewrite `gen_id`. There is no
carry-forward mechanism in the trend path and no provenance field on `TrendRow` to record one.
`evals/trend_store.py:123` documents the false claim in the type itself: *"Every calibrated
scorer's kappa for this run."*

**Why deferred:** M3 is case authoring; this is trend/calibration plumbing, and the fix changes
what every historical row means. It belongs with M4.3's re-baseline, where the trend is rewritten
anyway. Logged rather than fixed so the current row is not quoted in the meantime.
**To fix:** Either filter labels to the row's `gen_id` before calibrating, or — better, since
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
labels legitimately outlive one generation — add an explicit `labels_gen_id` (and label-count)
provenance field to `TrendRow`, populate it from the label file, and refuse to record a row whose
labels match no case in the generation. Correct the `scorer_kappas` docstring at
`trend_store.py:123` either way. Re-record the single existing row under M4.3.

## [CLOSED] ISSUE-274: `test_quest_lifecycle_offer_to_completion_and_rewards` has been red and invisible — `make check` skips it without services
**Found:** 2026-09-03, during the first watched bring-up of the M programme loop
**Severity:** P2 (annoying) — it sits in the loop's failing-test baseline, so every night of the M
programme will commit against a red gate and flag a human for it, every task, until it is fixed
**Where:** `tests/integration/test_quest_lifecycle_integration_v14.py::test_quest_lifecycle_offer_to_completion_and_rewards`
**Description:** The test fails in 0.35 s with
`ValueError: QuestLifecycleEngine requires a TypeRegistry injected via __init__` — it never reaches
the database. This is a test-side construction defect: the engine grew a required `TypeRegistry`
constructor dependency and this call site was not updated.

It is invisible to the normal gate. `make check` without services **collects and skips** the
integration suite (36 skipped, exit 0, measured 2026-09-03), so the suite reads green while this
test is red. It only surfaced because the loop was launched with `--with-services`, which is the
same "degraded, not red" hazard that makes `--with-services` mandatory for M1.3.

Distinguish it from the other two entries in the same baseline —
`test_faction_gossip_integration.py::test_hostile_pairs_rank_lower_than_neutral_pairs` and
`::test_same_faction_pairs_rank_higher_than_strangers`. Those fail for a different reason: they
assert a freshly-seeded pair appears in `select_pairs(max_pairs=20)`, and the live graph holds
27,534 nodes of which 23,292 are leaked draft quests (ISSUE-273) against 23 characters, so the
seeded pair cannot make the top-20 cut. **Those two are expected to go green when M1.3 wipes and
reseeds.** This one will not — it is unrelated to graph state.
**Why deferred:** found during a bring-up whose single task was M1.1, and the roadmap's
single-task-focus rule applies. It is also not a blocker: the loop attributes it to the baseline
and commits, rather than halting.
**To fix:** inject a `TypeRegistry` at the test's `QuestLifecycleEngine` construction, matching how
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
the engine's other call sites build it. Check whether sibling tests in the same file share the
defect. Then confirm the loop's baseline drops from 3 entries to 2.

---

## [CLOSED] ISSUE-235: 42 of 59 engine logger.info calls omit duration_ms
**Found:** 2026-08-31, during R1.8
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/**`; `make check-engine-logs` lists them
**Description:** CLAUDE.md requires `npc_id`, `player_id`, `tick` and `duration_ms` on every
engine log entry. 42 of the 59 `logger.info` calls in `engines/` carry no `duration_ms`, so
per-engine latency cannot be read out of the logs. `scripts/engine_logs_baseline.txt` records
42; the gate reds on 43, so this cannot grow.
**Why deferred:** R1.8 built the gate. Adding a duration to 42 call sites means timing the work
each one reports, which is a behaviour change per site, not a mechanical edit.
**To fix:** work the list down, re-recording with `python scripts/check_engine_logs.py --update`
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
as it shrinks. The gate only enforces `duration_ms` today — the other three fields CLAUDE.md
names are not yet checked, and widening it is a follow-on decision, not part of this issue.

## [CLOSED] ISSUE-223: the dialogue prompt is a process-wide singleton, so it cannot be A/B tested
**Found:** 2026-08-27, during the P0-P9 review that produced `EVAL_P25_TO_P31_PLAN.md`
**Severity:** P2 (annoying) - blocking for Program 5, not for anything shipping today
**Where:** `src/npc_engine/engines/dialogue/prompt_builder.py:32-40`
**Description:** `_PROMPT_PATH = _PROMPTS_DIR / "system_v1.yaml"` and the `llm_config.yaml`
load both run at MODULE level, so the dialogue system prompt is resolved once per process.
Three consequences: (1) no prompt variant can be selected per turn, so prompt-version A/B is
structurally impossible - `DialogueRequest` carries `retrieval_profile` and has no prompt
counterpart, and `paired_arms` makes arm identity *be* the retrieval profile; (2) it is a
module-level load of a stateful resource inside an engine, which CLAUDE.md's
constructor-injection rule forbids; (3) the only way to compare two prompts today is to edit
the YAML and rebuild, which changes `RunConfig.dialogue_prompt_hash` and therefore makes
`compare.py` refuse the pairing outright - so the comparison is not merely unpaired, it is
rejected by the harness.
**Why deferred:** it is the subject of EVAL-P29.2, and it is a `src/` change that collides
with the P9 fence ("no `src/` change lands after P9 goes green"). Sequencing against the P10
regeneration is an open scheduling decision recorded in the plan, not made.
**To fix:** EVAL-P29.1-29.3. Declare `prompt_variants:` in `llm_config.yaml` mirroring
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`retrieval_profiles:` with strict resolution; extract
`engines/dialogue/prompt_variant_resolver.py` (required, not optional - `prompt_builder.py`
already carries a 300-line waiver); make the variant an injected per-call argument. Pin with
a byte-identity digest test in the shape of DEC-194's
`test_no_profile_and_explicit_default_profile_are_byte_identical`, written RED first.

## [CLOSED] ISSUE-202: `retrieval_runner.main`'s docstring says it takes no options, and it takes two
**Found:** 2026-08-26, during the six A/B plumbing fixes (item 2, Makefile forwarding)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/retrieval_runner.py:269-276` (`main`'s docstring)
**Description:** The docstring states "This runner takes no options today; any argument is
rejected rather than ignored", documents `argv` as "Must be empty", and lists exit code "2 on
unexpected arguments". All three are false: the parser directly below it declares `--gen-dir`
and `--retrieval-profile`, and both are now passed by `make eval-retrieval` and by
`Run-OvernightCombined.ps1` step 4b. Nothing returns 2. The prose is a leftover from before
the flags were added.
**Why deferred:** the task that found it was explicitly scoped "DO NOT change
`evals/retrieval_runner.py` — its CLI already accepts both flags", and a docstring edit there
would have put an unrelated file in one of the six commits.
**To fix:** rewrite the summary to name both options, drop the "Must be empty" Args line and
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
the phantom exit code 2, and describe the actual contract (0 success, 1 connectivity/setup
failure). One-paragraph edit, no behaviour change.

## [CLOSED] ISSUE-195: `retrieved_context` consumers not yet migrated to `context_receipt`
**Found:** 2026-08-21, during the B/C3/C2 landing (DEC-195)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/dashboard/` case pane (renders `retrieved_context` item keys);
`evals/sequence_records.py:63` (`Turn.retrieved_context`)
**Description:** `GenerationRecord.context_receipt` now carries what ACTUALLY reached the
model. `retrieved_context` still carries the older approximation — a second call to
`GET /v1/admin/debug/retrieval` with `session_turns=[]`, describing a different assembly than
the one that produced `npc_response`. Both fields are populated on every new record, and the
two consumers above still read the deprecated one, so the dashboard's context pane is still
reporting over what the retriever RANKED rather than over what SURVIVED the prompt budget.
Those are different numbers, and the gap is the thing the receipt was built to expose.
**Why deferred:** Deleting or repointing them in the same change would have silently altered
what `recall@k` measures at the same moment as the field landed, with no released corpus
carrying `context_receipt` to compare against. The deprecation is marked in
`evals/retrieved_item.py` and in `GenerationRecord`'s docstring, and both fields are written,
so the migration can be measured rather than assumed. Committed corpora
(`evals/generations/k3_73e6c36/`) have no `context_receipt` at all and would read as empty.
**Update (measurement-remediation trim):** `evals/retrieval_join.py` — the third named
consumer above — is deleted; it had zero production callers (imported only by its own test)
and was never wired into `evals/report.py` despite its docstring's "planned" claim. The
recall@k comparison this issue originally asked `retrieval_join` to perform is folded into
the Phase-3/4 per-engine probe framework instead (see the measurement-remediation plan),
which reads `context_receipt` directly rather than resurrecting the deprecated join.
**To fix:** Move the dashboard case pane and `evals/sequence_records.py:63` over to
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`context_receipt.item_keys`, then drop `retrieved_context`, `evals/retrieved_item.py` and
`evals/context_capture.py` along with the second debug-endpoint call per turn — which also
removes roughly half of the generation pass's HTTP requests.

## [CLOSED] ISSUE-196: generation artifacts are written with platform line endings
**Found:** 2026-08-21, during the B/C3/C2 landing (DEC-195)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/eval_records.py:82-87` (`write_generation_dir`) and `:106`
(`write_transcript`); the same pattern in `evals/judged_persistence.py:167`
**Description:** `Path.write_text` is text mode, so on Windows the `"\n".join(...)` separators
in `outputs.jsonl` and the indentation newlines in `meta.json` are written as CRLF, while the
same code on Linux writes LF. Two runs of the same harness on different platforms therefore
produce byte-different artifacts from identical records. Nothing currently hashes these files
(`harness_version` covers cases, judge prompts and `matchers.py`; `golden_set_version` covers
cases), so no gate is wrong today — but any future content hash over a gen dir, or any diff of
two arms' artifacts, would report a platform difference as a data difference.
**Why deferred:** Not in scope for B/C3/C2, touches persistence shared by the judge pass, and
`evals/generations/` is a frozen path (`scripts/loop_gates.py FROZEN_PATH_PREFIXES`) so a fix
cannot be validated against the committed corpus in the same change.
**To fix:** Pass `newline=""` on every artifact write (the pattern `roadmap_cursor.py` already
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
uses on both ends, per DEC-151's CRLF hazard note), or write bytes. Add a test asserting `outputs.jsonl` contains
no `\r`.

## [CLOSED] ISSUE-173: no mechanical enforcement of phase-level `Depends on:` lines
**Found:** 2026-08-15, during the EVAL-P20-P24 unblock planning session
**Severity:** P2 (annoying — a real gap in loop safety, same family as ISSUE-171 but scoped to
task dependencies rather than the fence marker)
**Where:** `scripts/roadmap_cursor.py` / `_roadmap_cursor_core.compute_next`
**Description:** `compute_next` iterates phases in file order and returns the first task that is
`not done and not skippable` (`⏸️`/`(live` flagged). It never reads a phase's `Depends on:` line —
this was already established by DEC-164 for the *task-flag* mechanism, but its converse was not
separately logged: **a phase-level `Depends on:` is documentation only, not enforced.**
`EVAL-P21`'s own header states `**Depends on:** EVAL-P16.2, EVAL-P18.2, EVAL-P20.4.` but
`EVAL-P21.0` itself carries no `⏸️`/`(live` flag. If `EVAL-P20.3`, `EVAL-P20.3a`, `EVAL-P20.3b` all
land (clearing everything ahead of `EVAL-P21.0` in file order) before `EVAL-P20.4` (regeneration
#1) actually runs — which is entirely possible, since nothing currently stops it — an unattended
loop run would pick up `EVAL-P21.0` and attempt panel-roster work before the artifact its own
phase declares a dependency on exists. Low real-world severity right now (P21.0 is a config/roster
decision that doesn't need the artifact to draft), but the same pattern could bite a future task
whose work *does* require an undelivered dependency.
**Why deferred:** out of scope for a planning session; this is a harness-mechanism gap, not a
single-module bug fix — same class of fix as ISSUE-171 (a `HARNESS-P`-adjacent task), and possibly
worth solving together with it since both are "the roadmap's stated intent isn't mechanically
checked" gaps.
**To fix:** either have `compute_next` refuse a task whose phase's `Depends on:` phases/tasks are
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
not all done (would need a phase-to-task resolution helper), or extend `check_human_gates.py` to
also validate phase-level `Depends on:` lines against real task-done state, not just the 12
explicit `HUMAN GATE` blocks.

## [CLOSED] ISSUE-171: nothing enforced that a `LOOP:QUEUE end` move needs a DECISIONS.md entry
**Found:** 2026-08-15, during the H3-fence-position repair session
**Severity:** P1 (blocking — the exact mechanism HUMAN GATE H3 exists to stop failed silently once)
**Where:** `scripts/expand_loop.sh`, `scripts/roadmap_cursor.py --verify`, `Makefile:check-human-gates`
**Description:** Commit `84ff0f9` ("new task", 2026-08-15 08:43:09 — one second before the
`expand_loop.sh` run named in the day's session log started at 08:43:13) moved
`<!-- LOOP:QUEUE end -->` from the DEC-163 position (above `EVAL-P20`) down to below `EVAL-P24.3`,
reopening `EVAL-P20..P24`, with none of H3's three reopen conditions met (two of three, re-verified
live: `EVAL-P17.6`/`make check-conservation` still exits 3, and `EVAL-P20.0`'s gate measured 62.5%
per DEC-176, landed the day before). No DECISIONS.md entry recorded or justified the move, despite
the marker's own inline text saying to. Nothing mechanical caught this: `roadmap_cursor.py --verify`
only checks grammar (a moved marker is still valid grammar), `check_human_gates.py --verify` only
checks gate *grammar* not fence *position* vs the gates' own stated conditions, and the pytest
tripwire (`test_real_roadmap_fence_state_tripwire`) was itself already red for an unrelated reason
(ISSUE-170, now fixed) and so could not have caught this move even if someone had run it before
committing — see DEC-177 for the full repair. **Reverted** in DEC-177; this issue is about the
missing enforcement, not the one-time move.
**Why deferred:** fixing this means either (a) a new `make` check that diffs the fence marker's line
position against the last position recorded in DECISIONS.md (needs a machine-readable pointer, e.g.
a line in DECISIONS.md itself or a small state file), or (b) having `expand_loop.sh` refuse to
commit any diff touching the `LOOP:QUEUE end` line without a paired DECISIONS.md diff in the same
commit. Either is a new harness mechanism, not a bug fix in the current one, and is out of scope for
a session whose task is restoring the fence position, not redesigning how it's guarded.
**To fix:** design and land one of the two mechanisms above (or a better one), with its own tests,
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
as a dedicated task — likely a `RET-P0`-adjacent or fresh `HARNESS-P` phase.

## [CLOSED] ISSUE-194: the Retrieval Quality Program (RET-P1..P6) is referenced everywhere but exists nowhere
**Found:** 2026-08-21. **CORRECTED the same day — see the correction note below.**
**Severity:** P2 (annoying) — the highest-leverage retrieval fix has no owner and no roadmap entry
**Where:** `project-harness/ROADMAP.md:3289-3342` (`### Phase RET-P0` is the only RET phase)

**⚠️ CORRECTION.** This issue was originally filed as "the dialogue system prompt exceeds
OLLAMA_CONTEXT_LENGTH and PROMPT_TOKEN_BUDGET is silently the clamp floor". **That was a duplicate
of already-recorded work and it is retracted.** The prior art, which the original filing failed to
check for:
- `RET-P0.3` shipped `src/npc_engine/config_prompt_window.py` + `PromptWindowError`, which detect
  exactly this and are fully tested.
- `MEASURED_SYSTEM_PROMPT_TOKENS = 5426` is already recorded as a named constant with its derivation.
- **DEC-175** explicitly decided *not* to wire the check into `Settings`, and gave the reason: today's
  defaults are provably incoherent, so a hard-fail validator would refuse to boot, and "a warning
  nobody reads is not worth a startup-path change on its own". Both hard-fail AND warning-only were
  considered and rejected.
- `tests/unit/config/test_config_prompt_window.py::test_shipped_defaults_do_not_fit_the_default_window`
  already pins the incoherence so the fix has a measurable target.

So the engine defect is known, measured, instrumented and deliberately parked. Nothing about it needed
a new issue.

**What is genuinely new, and is what this issue now tracks:** `RET-P0`'s own header calls it the
"Opening phase of the Retrieval Quality Program (RET-P0...P6)", and both `RET-P0.3` and DEC-175 name
**RET-P6** as the phase that will wire the validator and raise the context window. Grepping
`ROADMAP.md` for `### Phase RET-`, the only entry that exists is `RET-P0`. **RET-P1 through RET-P6
have never been written down.** The consequence: the single largest known retrieval defect — a system
prompt that does not fit its own context window, which plausibly bounds the ~0.3 retrieval precision —
is assigned to a phase with no tasks, no gate, no effort estimate and no owner. It cannot be scheduled,
and `roadmap_cursor.py` cannot see it.

**Why deferred:** writing the RET-P1..P6 phase entries is roadmap authoring — a product-shaping call
about what the retrieval program contains and in what order, which is the maintainer's to make, not a
drive-by edit during metrics work.
**To fix:** author `### Phase RET-P6` (at minimum) in `ROADMAP.md` with the window raise and the
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
validator wiring as explicit tasks, carrying DEC-175's constraint that the window must be raised
*before* the validator is wired. Decide whether RET-P1..P5 are still wanted or whether the program
should be renumbered. Then the ISSUE-163/ISSUE-145 retrieval defects have somewhere to sit.

## [CLOSED] ISSUE-190: `src/npc_engine/config/` (data-only) shadows `config.py` as a namespace package
**Found:** 2026-08-20, during the metrics-pipeline closeout (DEC-193)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/config/` (holds only `llm_config.yaml`) vs `src/npc_engine/config.py`; surfaces at `evals/engine_adapter.py:37,61`
**Description:** the data-only directory wins import RESOLUTION over the module when mypy is
invoked as `mypy evals/`, so `from npc_engine.config import get_settings` reports
`attr-defined` even though `get_settings` exists at runtime (verified: it is in
`dir(npc_engine.config)`). `mypy.ini` excludes the directory from CHECKING, which does not
stop it shadowing. Two narrow `# type: ignore[attr-defined]` suppressions with an explanatory
comment are in place; `make type` over `src/` is unaffected and green.
**Why deferred:** the real fix is renaming the data directory, which touches runtime import
paths across the engine and needs an ask-gate. Not something to do in the hour before a
10-hour regeneration.
**To fix:** rename `src/npc_engine/config/` (e.g. to `config_data/`), update the loader that
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
reads `llm_config.yaml`, drop the two suppressions, and confirm `warn_unused_ignores` stays quiet.

## [CLOSED] ISSUE-191: `check_rules.py` is a regex scanner, so it flags patterns inside comments and docstrings
**Found:** 2026-08-20, during the metrics-pipeline closeout (DEC-193)
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_rules.py:48-50` (`_SWALLOW_RE`, `_PRINT_RE`)
**Description:** the R002/R003 detectors match raw file text, not an AST. Writing the words
`print(` or `` `except: pass` `` inside a comment or docstring — including a comment explaining
why the pattern was removed — re-introduces the violation. Hit twice while fixing R003 this
session: a docstring quoting the anti-pattern, and a comment saying no stdout write happens here.
Both had to be reworded rather than the code changed.
**Why deferred:** cosmetic; the workaround (reword) is trivial and the detector is otherwise
doing its job. `_oversized_functions` already uses `ast`, so the machinery exists.
**To fix:** move R002/R003 onto the `ast` walk that `_oversized_functions` already performs, so
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
only real `Call`/`ExceptHandler` nodes count.

## [CLOSED] ISSUE-193: 28 frozen-model tests assert `pytest.raises(Exception)` rather than the specific type
**Found:** 2026-08-20, during the metrics-pipeline closeout (DEC-193)
**Severity:** P3 (nice-to-fix)
**Where:** 28 sites across `tests/unit/` (evals, graph, llm, api, config, engines, retrieval)
**Description:** immutability tests assert that any exception is raised on mutation. The specific
type is knowable per site — pydantic v2 frozen models raise `ValidationError`, frozen dataclasses
raise `FrozenInstanceError` — so a test would still pass if the object raised for an unrelated
reason (a typo'd attribute name, say). All 28 now carry a `# quality-ok:` waiver naming this.
**Why deferred:** maintainer decision (DEC-193 decision A): re-baseline/waive the purely
structural findings rather than make a large mechanical diff across the test suite immediately
before regeneration #1.
**To fix:** narrow each to `ValidationError` or `FrozenInstanceError` per the model family and
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
delete the waiver comment in the same edit.

## [CLOSED] ISSUE-169: `make check-evals-rules` AND `make type-evals` are both red on main
**Found:** 2026-08-14, during `EVAL-P20.0` (running `make check` before committing)
**Severity:** P2 (annoying — two red gates that are not this task's fault mask real regressions)
**Where:** `scripts/evals_baseline.txt` and `scripts/mypy_evals_ratchet.py` vs
`evals/eval_records.py`, `evals/sequence_rates.py`, `evals/scenario_adapters_extra.py`,
`evals/sequence_order_effect.py`, `evals/scenario_adapters.py`
**Description:** Two independent gates are red before this task touches anything. **Both verified
pre-existing** by stashing this task's changes and re-running: identical output either way. They
share a cause — the `EVAL-P12.4` commit (`efbe7ce`) added new evals modules without updating either
baseline.
1. `check-evals-rules`: **6 NEW violations** — R001 `eval_records.py` >300 lines; R002 `print()` in
   `sequence_rates.py`; R006 >40 lines on `make_memory_consolidation`, `make_mood_contagion`,
   `make_time_passage`, `order_effect_check`.
2. `type-evals`: **23 type errors > baseline 16** (+7), concentrated in `scenario_adapters_extra.py`
   (`union-attr` / `operator` on a `dict | None`), plus pre-existing `no-any-return` and two
   `npc_engine.config has no attribute "get_settings"` in `engine_adapter.py`.
Distinct from ISSUE-162, which is the `make lint` E741 in `sequence_order_effect.py` — that is a
third gate. As of this session `make check` therefore has **three** independent pre-existing reds.
**Why deferred:** none of it is caused by or related to `EVAL-P20.0`; single-task focus. Fixing it
means splitting `eval_records.py`, extracting four helpers, and tightening `dict | None` handling —
judgement calls belonging to whoever owns EVAL-P12.4's code.
**To fix:** decide per violation whether to split/extract or waive; fix the `union-attr` errors
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
properly (they are real latent `None` dereferences, not noise). Do **not** blanket-run
`make check-evals-rules-update` or re-baseline the mypy ratchet: both baseline headers forbid
re-baselining without justification, and doing so would silently absorb whatever else has drifted.

## [CLOSED] ISSUE-164: CLAUDE.md stack table claims "no OpenAI adapter ships today" but one exists
**Found:** 2026-08-14, during `EVAL-P20.0`
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/CLAUDE.md` stack table (LLM row) vs
`src/npc_engine/engines/llm/openai_adapter.py`
**Description:** The stack table says the LLM is "pluggable via `LLMClientProtocol` + factory
registry (add a local or API backend by registering an adapter — **no OpenAI adapter ships
today**)". `OpenAICompatibleAdapter` does ship (SHIP-02 / DEC-126), is registered in the factory,
subclasses `LLMClientProtocol`, and has its own test module. The roadmap's `EVAL-P20.0` file list
inherited this error: it named only `protocols.py` and `ollama_adapter.py`, omitting both
`openai_adapter.py` and `mock_adapter.py`, each of which also defines `generate()`.
**Why deferred:** documentation drift found while doing `EVAL-P20.0`; single-task focus. Correcting
CLAUDE.md is not part of adding a seed.
**To fix:** amend the stack table's LLM row to name `OpenAICompatibleAdapter` as shipped, and audit
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
the table for other claims that have since gone stale (the `prompts/eval/` path row was corrected
the same way on 2026-08-10).

## [CLOSED] ISSUE-166: 173 of 228 Cypher queries with RETURN have no ORDER BY
**Found:** 2026-08-14, during `EVAL-P20.0` determinism investigation
**Severity:** P2 (annoying — latent prompt non-determinism)
**Where:** `src/npc_engine/graph/**` (static scan: 228 Cypher blocks containing `RETURN`, 173
without `ORDER BY`)
**Description:** Neo4j does not guarantee row order without `ORDER BY`. Any such query whose rows
are serialized into prompt content can reorder between runs, changing prompt bytes and therefore
the generated text. This was **not** the dominant term in the EVAL-P20.0 measurement — after the
DEC-176 prompt fix, `retrieved_context` drift was 0/145 — but it is unbounded risk that grows with
graph size, and it silently defeats reproducibility when it does bite.
**Why deferred:** not the measured cause of the EVAL-P20.0 gate failure; single-task focus. Fixing
173 queries blind would be churn.
**To fix:** identify the subset whose results reach prompt content (memories, beliefs, goals,
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
rumors, secrets, items, traits, reputation) and add a deterministic `ORDER BY` — id or an explicit
score then id as a tiebreak — to those first. Add a check-rules rule for new prompt-feeding queries.

## [CLOSED] ISSUE-162: `make lint` is red on `main` — E741 ambiguous variable name in `sequence_order_effect.py`
**Found:** 2026-08-14, during `RET-P0` (retrieval quality program)
**Severity:** P2 (annoying)
**Where:** `evals/sequence_order_effect.py:81:46`
**Description:** `make lint` fails with `E741 Ambiguous variable name: 'l'`, which fails the whole
`make check` gate (`lint` is its first target). Pre-existing and unrelated to RET-P0: the file is
untouched by that task (`git diff HEAD -- evals/sequence_order_effect.py` is empty) and was last
modified in `efbe7ce` (EVAL-P12.4). Confirmed the only lint error in the repo.
**Why deferred:** Single-task focus — RET-P0 is scoped to context budget starvation, and this is
stats code owned by the EVAL-P12 line. The variable `l` is deliberate notation for `Lᵢ` from the
Cochran's Q block design documented in DEC-174, so the rename should be made by someone confirming
it stays faithful to `docs/SEQUENCE_STATS_POLICY.md` §4.2 rather than blind-renamed to satisfy ruff.
**To fix:** Rename `l` to a non-ambiguous name that preserves the `Lᵢ` meaning (e.g. `l_i` or
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`rep_passes`) and re-run `make lint`. One-line change; the only reason it is not done here is diff
hygiene.

## [CLOSED] ISSUE-161: `import npc_engine.retrieval.context` fails standalone with a circular `ImportError`
**Found:** 2026-08-14, during `RET-P0` (retrieval quality program)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/retrieval/context/__init__.py` → `context_builder.py:68` → `retrieval/dialogue_context/__init__.py:13` → `dialogue_context_adapter.py:20`
**Description:** Importing the context package on its own raises
`ImportError: cannot import name 'build_serialized_context' from partially initialized module
'npc_engine.retrieval.context.context_builder' (most likely due to a circular import)`.
Verified directly: `python -c "import npc_engine.retrieval.context"` fails, while
`import npc_engine.retrieval.dialogue_context` followed by `import npc_engine.retrieval.context`
succeeds. The cycle is `context` → `dialogue_context` → `context`. It is invisible today only
because every production entry point happens to import `dialogue_context` first, so import order
is load-bearing but undocumented and unenforced.
**Why deferred:** RET-P0 is scoped to budget starvation (ISSUE-145); single-task focus. The cycle
predates this task and breaks nothing currently shipping.
**To fix:** Break the cycle by having `dialogue_context_adapter` import `build_serialized_context`
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
lazily inside the calling method, or move the shared entry point into a module both packages can
depend on downward. Add a regression test that imports `npc_engine.retrieval.context` in a fresh
interpreter. **Blocking for RET-P1.3**, whose in-process eval fallback imports the context package
directly and will hit this.

## [CLOSED] ISSUE-159: `/v1/npc/{id}/state` and `/v1/npc/{id}/emotion` return their model directly, unlike the rest of the API's `OkEnvelope` convention
**Found:** 2026-08-13, during EVAL-P12.4 (HUMAN GATE H5), while writing `evals/scenario_adapters.py`
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/routes/dialogue/npc_state.py` (`npc_state`, `npc_emotion`) and
`src/npc_engine/api/routes/dialogue/dialogue.py` (`dialogue`) — all three declare
`response_model=<Model>` and return the model instance directly, rather than
`response_model=OkEnvelope[<Model>]` + `ok_response(...)` the way every admin/graph/reputation route
in this codebase does.
**Description:** A client written against the API's dominant convention (`{"success": true, "data":
{...}, "meta": null}`) will silently read `None`/`{}`/`0.0` from these three endpoints instead of an
error — the response is still 200 with a well-formed body, just shaped differently. Cost real debugging
time in this task: the first draft of `evals/scenario_adapters.py`'s `gossip_chain` and
`grief_persistence` adapters read `resp.json().get("data", {}).get(...)`, which is correct for every
other endpoint in this file but silently returned `[]`/`0.0` for these three, making two working
scenarios look like they were failing their pass/fail predicate.
**Why deferred:** out of scope for EVAL-P12.4 — fixing it changes a public response shape three routes
have shipped with, which needs a version/compat decision (does `demo_game/client.py` or any other
consumer already depend on the unwrapped shape?) that this task's live-measurement mandate does not
cover.
**To fix:** either (a) wrap all three in `OkEnvelope`/`ok_response` for consistency, coordinating the
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
breaking change with every known consumer, or (b) if the unwrapped shape is intentional (these are the
only three read-only "current state" endpoints with no `error`/`meta` need), document the split
explicitly in the API conventions doc so the next integrator doesn't rediscover it as a bug.

## [CLOSED] ISSUE-155: `verdict_sources.load_unified_rows` dedups by `record_id` alone, silently
collapsing k=3 repetitions to k=1 (found while re-measuring EVAL-P17.5)
**Found:** 2026-08-12, during EVAL-P17.5 step 3 (re-running `summarize_from_dir` over the
unchanged `evals/generations/k3_73e6c36` artifact)
**Severity:** P2 (annoying)
**Reclassified:** Downgraded P1→P2 2026-09-02 by DEC-250 — but NOT closed, deliberately. Collapsing k=3 repetitions to k=1 corrupts any number `summarize_from_dir` produces, including regression comparisons the retained tests depend on. It survives the retirement of the claim; only its urgency drops.
including the one EVAL-P17.5 is re-measuring, and by extension `compare`, which also consumes
`load_unified_rows`)
**Where:** `evals/verdict_sources.py:166-171`, function `load_unified_rows`
**Description:** `record_id` (e.g. `case_adv_aldric_black_market:schema:0`) encodes
`case_id:matcher_kind:expectation_index` — it does **not** encode `repetition`. Confirmed by
direct inspection of `outputs.jsonl`: the same `record_id` recurs once per repetition (0, 1, 2)
with `repetition` carried as a *separate* field. `load_unified_rows` builds
`seen: dict[str, VerdictRow] = {}` keyed on `row.record_id` alone
(`seen[row.record_id] = row`), so the three repetitions of every slot collide on the same key
and only the last one written survives — silently discarding 2 of every 3 repetitions before
`to_summarize_results` ever groups by `(case_id, repetition)`.
Measured effect on the unchanged `k3_73e6c36` artifact (`k=3` per `meta.json`):
`summarize_from_dir` reports `guard_turns=78` (== `guard_cases=78`, i.e. exactly 1 turn per
case) instead of the expected 78 × 3 = 234, and the battery-rate design-effect string prints
`k=1.0` where it should print `k=3.0`. Direct check: `case_adv_aldric_black_market` has 4
distinct `record_id`s in `deterministic_judged.jsonl`, each appearing 3 times (once per
`repetition` 0/1/2, all `passed=True` in this sample) — `load_unified_rows` returns only 1 row
per `record_id` for that case, not 3.
This also means `compare` (EVAL-P18.3, same `load_unified_rows` dependency) has been comparing
whichever single repetition happened to be written last per slot, not an aggregate over k
repetitions, since EVAL-P17.1 landed.
**Why deferred:** Out of scope for EVAL-P17.5 (re-measure and retract is read-only arithmetic
over the existing artifact, not a pipeline fix) and out of scope per `project-harness/CLAUDE.md`
single-task-focus — fixing this is a new, separate change to `evals/verdict_sources.py`.
Surfaced to the human via `EVAL-P17.5` step 4 before any Session Log edit, per that phase's "traced,
not hand-waved" gate.
**To fix:** Key `seen` in `load_unified_rows` by `(row.record_id, row.repetition)` instead of
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`row.record_id` alone; update `to_summarize_results` grouping if needed (it already groups by
`(case_id, repetition)`, so no change expected there); add a regression test asserting
`len(load_unified_rows(gen_dir)) == 3 * <slots-in-a-single-repetition>` for a fixture with
`k=3`. Re-run `EVAL-P17.5`'s re-measurement afterward — the corrected headline will not match
either the number in this issue or the ISSUE-154 prediction.

## [CLOSED] ISSUE-154: EVAL-P17.5 re-measurement — prediction recorded before running (pre-registered)
**Found:** 2026-08-12, during EVAL-P17.5 (re-measure and retract)
**Severity:** P2 (tracking entry — not a bug; a pre-registered prediction, written before the
re-measurement runs, per EVAL-P17.5's "write expected numbers before you run anything" discipline)
**Where:** `evals/generations/k3_73e6c36` (unchanged artifact), read via
`summary.summarize_from_dir` / `summary.format_summary_lines` (no regeneration)
**Description:** Predicted corrected headline: **~18 lore hallucinations across ~234
case-repetitions** (78 guard cases × k=3), superseding the 2026-08-10 audit's floor of "≥10
across ≥186 turns," which itself superseded the currently-published (and now retracted) "3 lore
hallucinations across 111 adversarial turns."

Reasoning: the retracted "3 across 111" and the audit's "≥10 across ≥186" were both undercounts
because both were computed from `judged.jsonl` alone (LLM-judge verdicts only).
- **EVAL-P17.1** (aggregate over both verdict sources) now merges `judged.jsonl` with
  `deterministic_judged.jsonl` via `verdict_sources.load_unified_rows`, which surfaces 8
  previously-invisible failing `anti_hallucination_grounded` deterministic rows that never
  appeared in the old judged-only count.
- **EVAL-P17.2** (unclassifiable cases raise, delegated to `classify_battery`) raises the guard
  battery from the old, incompletely-classified set to **78 cases** (adding the 41 `ah_demo_*`
  cases that previously fell outside any recognized battery prefix), so the denominator becomes
  78 × k=3 = **234 case-repetitions**, not 111 or 186.
- EVAL-P17.3 (infra vs. content separation) and EVAL-P17.4 (skips leave the numerator) affect
  which failures count as content hallucinations vs. inconclusive/skipped, feeding into the same
  headline via `summary.EvalSummary.headline`.
**Why deferred:** N/A — this is not deferred work. It is the pre-registered prediction for
EVAL-P17.5 step 4 (compare actual vs. this prediction). Human-confirmed via AskUserQuestion on
2026-08-12 before being written here, per ROADMAP.md's HUMAN GATE H1.
**To fix:** N/A. Close out (do not mark `[FIXED]`) once EVAL-P17.5 step 4 records the actual
re-measured number next to this prediction and either matches it or traces the delta to a named
`case_id`/line of code.
**Result (2026-08-12):** Confirmed. The shipped pipeline reported "1 lore hallucination across
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
78 adversarial turns" (not 18/234) due to two now-logged bugs — ISSUE-155 (repetition collision
in `load_unified_rows`) and ISSUE-156 (`refusal_judge`/`anti_hallucination_grounded` excluded
from `hallucination_failures`). With both hand-patched in a scratch script (not committed), the
recomputed headline is exactly **18 lore hallucinations across 234 adversarial turns** — an
exact match to this prediction. Recorded as the corrected headline in ROADMAP.md's Session Log
per human decision 2026-08-12; `EVAL-P17.5` ticked. ISSUE-155/ISSUE-156 remain open — they are
the pipeline fix still required before live tooling (`summarize_from_dir`, `compare`)
reproduces this number.

## [CLOSED] ISSUE-147: capability battery is 16 cases against a target of ~35
**Found:** 2026-08-10, during EVAL-P20.2
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/case_pos_*.yaml`
**Description:** EVAL-P20.2 targets ~35 capability cases and was ticked under its own
ratchet clause at 9 authored (7 to 16). The remaining ~19 are unwritten. Coverage of
*demo-world NPCs* is complete — `UNCOVERED_BASELINE` is empty and every grounded demo NPC
has one case — so the remainder is depth (a second and third fact per NPC) plus the
village and tavern eval worlds, which have no capability coverage at all.
**Why deferred:** the ratchet clause exists precisely so this does not have to land in one
sitting; 9 cases clear the gate's authored-set requirement.
**To fix:** author against `docs/CAPABILITY_CASES.md`, one case per remaining grounded
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
fact. Each must resist the echo and the hedge —
`tests/unit/evals/test_capability_echo_resistance.py` enforces both for any new case.

## [CLOSED] ISSUE-127: No gate catches Makefile `-m <module>` targets that rot after a package move
**Found:** 2026-08-05, during EVAL-P0.4 setup
**Severity:** P2 (annoying)
**Where:** `Makefile` (every `$(PYTHON) -m ...` target); regression source was PR-5 (827212d)
**Description:** PR-5 split `demo_game/` into sub-packages, moving `demo_game/seed.py` →
`demo_game/seeds/seed.py`, but `make demo-seed` kept invoking `-m demo_game.seed`. The target
failed with `No module named demo_game.seed` for everyone who ran it, and `make check` stayed
green because no gate imports the module paths named in the Makefile. Any future package move
can silently break another target the same way.
**Why deferred:** The broken target itself is fixed (this session). The missing *gate* is
separate work and would have expanded EVAL-P0.4 setup into harness work.
**To fix:** Add a unit test that parses the Makefile for `-m <dotted.module>` occurrences and
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
asserts `importlib.util.find_spec` resolves each one. Cheap, no I/O, runs in `make check`.

## [CLOSED] ISSUE-128: `captain_sorn` invents a warlord name ("bjorn") under adversarial pressure
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Severity:** P2 (annoying)
**Where:** engine dialogue path; reproduced by `evals/cases/case_neg_captain_sorn_no_troop_specifics.yaml`
**Description:** Asked "How many Northmen are massing at the pass, Captain — exact numbers — and
what is their warlord's name?", the NPC replied "...As for their warlord, they ca[ll him bjorn]..."
tripping `keyword_none` on `['bjorn']`. No `bjorn` entity exists in the graph. This is the **single
case-level lore hallucination** in the 2026-08-06 baseline (1 across 37 guard turns) — a real
invention, not a scorer artifact. The NPC correctly hedged the troop-count half of the same
question, so the guard held for numbers but not for a proper noun.
**Why deferred:** EVAL-P0.4 is a *measurement* task — its output is the baseline, and fixing the
engine mid-measurement would invalidate the numbers it exists to produce.
**To fix:** Investigate whether the retrieved context leaks a name-shaped token or whether the
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
prompt's refusal rubric covers quantities but not named entities. Add the fix's regression case to
the guard battery. Re-measure against the frozen `evaluated_cases` denominator (ROADMAP Session Log
2026-08-06 §g) so the before/after is comparable.

## [CLOSED] ISSUE-150: `evals/runner.py` and `evals/report.py` have functions exceeding 40 lines
**Found:** 2026-08-12, during EVAL-P17.4
**Severity:** P3 (nice-to-fix)
**Where:** `evals/runner.py` (`_run_case` ~164 lines, `main` ~93 lines); `evals/report.py` (`write_report` ~71 lines)
**Description:** Pre-existing violations of the 40-line function limit. EVAL-P17.4 slightly extended each by adding skip-handling logic, but did not introduce the violation.
**Why deferred:** Splitting these functions was out of scope for EVAL-P17.4 (single-task focus). The functions are cohesive orchestrators; splitting would require a DECISIONS.md entry.
**To fix:** Extract sub-helpers (e.g. `_format_case_header`, `_count_results`, `_write_case_section` for report.py; `_print_skip_console`, `_count_non_skipped` for runner.py) to bring each function under 40 lines.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

---

## [CLOSED] ISSUE-083: two voice tone_judge cases fail under epoch=war / stage_b_v2.9 (captain_sorn, mira_innkeeper)
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
**Update (2026-06-11, S25.1 / DEC-096):** ECHO_GUARD confirmed as *a* cause and softened in
`prompt_builder.py` (`_ECHO_GUARD_TEXT`, `stage_b_v2.13`): dropped the always-on "answer only in your own
general terms" flattener, scoped each directive to an explicit player plant. Live A/B: voice **0/2 → ~1/2**
(mira recovers gossip framing; captain still borderline-fails on "Reports…/our scouts keep us informed"),
anti-hallucination **5/5** guards still pass (no moat regression). **Kept OPEN — narrowed residual:** the
captain_sorn failure is now voice-judge strictness + a secondary-source ("reports/scouts") habit, not the
ECHO_GUARD. Remaining fix is voice-prompt/seed tuning (out of S25.1's prompt-wording scope) — e.g. a
VOICE_DESCRIPTOR nudge away from third-person reporting toward first-person command, or relaxing the
captain tone judge to accept "reports of skirmishes" as a commander relaying field intel.
**Update (2026-06-22, engine-quality remediation):** Reviewed for a deterministic fix; **none exists** —
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
the residual is voice-judge strictness + LLM variance, and both candidate levers need an Ollama A/B to
verify (not deterministic). Note the demo seed's own descriptor reinforces the disliked habit:
`captain_sorn`'s `voice_descriptor` in `demo_game/seed.py:688` ends "Every sentence lands like a report to
a superior officer" — the "report" framing nudges toward third-person "reports/scouts" relay. Two minimal
levers remain, each LLM-variance-prone: (a) relax the tone judge in `evals/cases/case_voice_captain_sorn.yaml`
to accept a commander relaying field intel ("reports of skirmishes", "my scouts confirm") as authoritative;
(b) reword the seed `voice_descriptor` toward first-person command. **Kept OPEN (no churn)** per the
"recommend OPEN rather than churn prompts when no confident deterministic fix exists" guidance. Anti-
hallucination guards remain unaffected (separate axis).

---

## [CLOSED] ISSUE-304: two god-ports pair a 9- and 11-method interface with a single caller
**Found:** 2026-09-07, during full-review (L2-03)
**Severity:** P3
**Where:** `src/npc_engine/engines/ports/chapter_port.py:21-70`, `quest_generation_port.py:17-76`
**Description:** `ChapterGraphPort` (9 methods, 1 implementor, 1 caller) and `QuestGenerationGraphPort` (11 methods, 1 implementor, 2 callers) provide none of ISP's benefit and all of its cost.
**Why deferred:** Subsumed by the wider port-sizing decision (34 of 44 ports fail the repo's own DIP threshold), which is awaiting a human call.
**To fix:** Fold into whichever direction that decision takes.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-305: two ports import graph-owned types, one an explicitly private Protocol
**Found:** 2026-09-07, during full-review (L2-04)
**Severity:** P2
**Where:** `src/npc_engine/engines/ports/event_port.py:19-20,33`; also `relation_read_port.py:21`, `scheming_port.py:22`
**Description:** `event_port.py` imports `_EventNode` from `graph/event/event_writer.py:20` — a leading-underscore Protocol the writer marks private — and uses it as a parameter type. The port's own docstring (`:6-7`) says engines use it "instead of importing graph writers." The dependency inversion the port exists to create is undone through the type import. Layer-rank direction is legal, so `check-layers` correctly does not flag it; the defect is ownership.
**Why deferred:** No live failure; it is a latent coupling.
**To fix:** Have the port own its DTO (in `event_port.py` or a shared `engines/ports/_dtos.py`) and have the graph writer conform to it.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-306: three sibling quest Protocols redeclare identical methods
**Found:** 2026-09-07, during full-review (L2-05)
**Severity:** P3
**Where:** `src/npc_engine/engines/ports/quest_port.py:21-124`
**Description:** `QuestLifecycleGraphPort`, `QuestOfferGraphPort` and `QuestRewardGraphPort` each redeclare a method a sibling in the same file declares (`get_quest_state`, `update_quest_node_status`), all satisfied by one implementor. Structural typing lets the copies drift with no type-checker cross-check.
**Why deferred:** Cosmetic today.
**To fix:** Extract a shared base Protocol, or record "ISP over DRY" as deliberate in DECISIONS.md.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-308: the WS connection cap is tested at the helper, not at the endpoint
**Found:** 2026-09-07, during full-review (L4-04)
**Severity:** P2
**Where:** `src/npc_engine/api/routes/dialogue/dialogue_ws.py:221-225`; tests for `check_ws_connection_limit()`
**Description:** The guard test exercises the limit helper in isolation. The endpoint's own accounting is untested — which is exactly where the CRITICAL slot leak (SEV-01) lives. Asserted-not-measured.
**Why deferred:** SEV-01's brief includes the sequential-close endpoint test; this entry records the wider pattern for the WS surface.
**To fix:** Add endpoint-level tests via `TestClient(app).websocket_connect`, covering both acquire and release.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-309: repository-passthrough and Cypher-substring test patterns remain asserted-not-measured
**Found:** 2026-09-07, during full-review (L4-05)
**Severity:** P2
**Where:** `tests/unit/graph/` (e.g. `test_story_pacing_repository.py:31-41`)
**Description:** 127 delegate tests prove a mock echoed itself; an executed counterfactual gutting 105 repository passthroughs produced only 66 failures. Restated from CR-L14-02, confirmed unchanged at HEAD `8d30a3e1`. The wrapped Cypher is exercised only by `tests/integration`, which skips 34 of 43 in the default environment.
**Why deferred:** The remedy depends on whether the CI `integration-tests` job is merge-gating — an open question in DECISIONS.
**To fix:** Resolve the CI-gating question, then either rely on CI or add real-Cypher coverage locally.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-310: existence-only tests assert wiring, not behaviour
**Found:** 2026-09-07, during full-review (L4-06)
**Severity:** P3
**Where:** across `tests/unit/`
**Description:** Several tests assert `hasattr(...)` or `iscoroutinefunction(...)` — they prove a symbol exists and is async, not that it does anything. They survive any implementation change that keeps the signature.
**Why deferred:** Low individual value; better fixed opportunistically alongside the modules they cover.
**To fix:** Replace each with a behavioural assertion, or delete it as noise.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-312: the entire branch system is one two-option stub, undocumented as final scope
**Found:** 2026-09-07, during full-review (L6-03)
**Severity:** P2
**Where:** `demo_game/branches/`
**Description:** The branching system is a single two-option branch (`garrick_deserter`). Its docstring says "First-slice"; no second slice exists anywhere and no DECISIONS entry records that one-branch is the intended final scope.
**Why deferred:** Product-scope call, not a defect.
**To fix:** Either add branches or record the intended scope in DECISIONS.md so the "First-slice" docstring stops implying unfinished work.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-313: `matchers.py`'s `_DISPATCH` table is a closed seam for new eval-scorer kinds
**Found:** 2026-09-07, during full-review (L7-01)
**Severity:** P3
**Where:** `evals/matchers.py`
**Description:** Adding a scorer kind requires editing the `_DISPATCH` table — a closed module — whereas eval cases and generation are both file-glob open. Deliberate per DEC-145's size waiver, but it is the one closed eval-authoring surface.
**Why deferred:** Deliberate; low churn.
**To fix:** Registry-style registration if scorer kinds start changing often; otherwise leave and note the choice.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-314: `engines/llm/factory.py` docstrings describe a self-registration pattern the code does not use
**Found:** 2026-09-07, during full-review (L7-02)
**Severity:** P3
**Where:** `src/npc_engine/engines/llm/factory.py`
**Description:** The docstrings describe adapter self-registration; the code uses an explicit factory mapping. Documentation asserting capability the code lacks (systemic pattern §3.6).
**Why deferred:** Docs-only.
**To fix:** Correct the docstrings to describe the explicit registry.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-315: adding a tick-driven engine requires editing 4 existing files
**Found:** 2026-09-07, during full-review (L7-03)
**Severity:** P2
**Where:** `scheduler/tick_scheduler.py`, `scheduler/engine_slots.py`, a getter module, `api/dependencies_engines/__init__.py`
**Description:** The OCP verdict for the repo's main expansion axis is **closed**: a new engine is not a new file, it is 4 edits to closed modules. A good introspection-based wiring guard (`_assert_every_engine_slot_wired`) now exists and catches a missed edit, but the edits are still required.
**Why deferred:** A generic-registry refactor is a large change; L7 recommends deferring until a fifth distinct call signature appears.
**To fix:** Either a registry-driven engine table, or accept and document the 4-file cost.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-316: location-connection `kind` is still an unconstrained `str`
**Found:** 2026-09-07, during full-review (L7-04)
**Severity:** P3
**Where:** location graph models
**Description:** A fixed value set typed as `str`, against CLAUDE.md's `Literal`/`Enum` rule. Carried over from the 2026-06-03 L7-04 finding; still live.
**Why deferred:** Blocks nothing today; relevant when the PART_OF location hierarchy lands.
**To fix:** Convert to `Literal`/`Enum` with the hierarchy work.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-317: `distortion_strategy.registry_keys()`'s docstring overclaims openness
**Found:** 2026-09-07, during full-review (L7-06)
**Severity:** P3
**Where:** `src/npc_engine/engines/gossip/distortion_strategy.py`
**Description:** The docstring implies new distortion strategies register themselves; adding one still edits this module. The axis improved from closed to partly-open, but the docstring describes more openness than the code delivers.
**Why deferred:** Docs-only.
**To fix:** Correct the docstring.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-323: memory consolidation asks for structured JSON through the unstructured `generate` protocol
**Found:** 2026-09-07, during full-review (L11-04)
**Severity:** P2
**Where:** `src/npc_engine/engines/memory_consolidation/`
**Description:** The engine requests JSON via plain `generate` rather than `generate_structured`, so it gets no schema enforcement and must parse free text. This is precisely the cognitive-demand class a smaller model handles worst without structural constraints.
**Why deferred:** Requires a schema definition and a fallback path for parse failure.
**To fix:** Move to `generate_structured` with a Pydantic schema; keep the existing failure path.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-324: proactive dialogue line generation has zero fallback and no timeout enforcement
**Found:** 2026-09-07, during full-review (L11-05)
**Severity:** P2
**Where:** `src/npc_engine/engines/proactive_dialogue/`
**Description:** Unlike dialogue, the proactive path has no local fallback when the model fails, and its declared timeout is not enforced (see also the `timeouts_ms` dead-config finding). A model failure surfaces as no line at all.
**Why deferred:** Needs a product decision on what a failed proactive line should do (silence is arguably correct).
**To fix:** Decide the failure contract, then implement it explicitly rather than by omission.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-325: two dialogue rules are both numbered 17, and rule 15 is out of sequence
**Found:** 2026-09-07, during full-review (L12-01)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml`, `system_state_v1.yaml`
**Description:** `system_state_v1.yaml`'s appended rule collides with `system_v1.yaml`'s own Rule 17 in the assembled prompt, and Rule 15 is out of sequence. Cosmetic today (no broken cross-reference), but it is evidence the assembled artifact was never proofread as one document.
**Why deferred:** Any prompt edit changes `dialogue_prompt_hash` and breaks eval comparability.
**To fix:** Renumber when the next deliberate prompt change is taken, so the comparability cost is paid once.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-326: Rule 9 (ECHO PROHIBITION) and Rule 5 (verbatim inclusion) can collide
**Found:** 2026-09-07, during full-review (L12-03)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml`
**Description:** When the player's claim matches the NPC's own true account, Rule 9 forbids echoing it while Rule 5 requires including `MY_ACCOUNT_N` verbatim. Graded **Suspected** — not demonstrated in a live turn.
**Why deferred:** Unconfirmed, and prompt edits cost eval comparability.
**To fix:** Construct the colliding case and observe the model's behaviour before editing anything.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-327: the Rule 16 vs Rule 2 tie-break is delegated to model "judgement" with no algorithm
**Found:** 2026-09-07, during full-review (L12-04)
**Severity:** P2
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml`
**Description:** When STANDING (Rule 16) and PLAYER REPUTATION (Rule 2) disagree, the prompt tells the model to use its judgement rather than giving a rule. That is the single instruction most likely to degrade on a smaller model, since it asks for arbitration rather than a lookup.
**Why deferred:** Prompt edit; costs `dialogue_prompt_hash` comparability.
**To fix:** Specify a deterministic precedence, or merge the two systems (see ISSUE-328).
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-329: three rules restate the same anti-hallucination policy for three context objects
**Found:** 2026-09-07, during full-review (L12-06)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Rules 5, 14, 17)
**Description:** One policy stated three times, costing static prompt tokens on every turn without adding constraint.
**Why deferred:** Prompt-hash comparability cost.
**To fix:** Collapse into one rule that names the three objects.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-330: Output-rules prose restates constraints the JSON schema already enforces
**Found:** 2026-09-07, during full-review (L12-07)
**Severity:** P2
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Output rules block)
**Description:** The block restates enum and range constraints the generation schema enforces structurally. Free to cut in the sense that it does not affect decoded tokens — but it is static prompt tokens on every turn, and it is exactly the "should be structural, not textual" class.
**Why deferred:** Prompt-hash comparability cost.
**To fix:** Delete the restated constraints, keep the rules the schema cannot express.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-331: Rule 8's guard/soldier register carve-out plausibly contributes to ISSUE-128
**Found:** 2026-09-07, during full-review (L12-10)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Rule 8)
**Description:** ISSUE-128 records `captain_sorn` inventing a warlord name ("bjorn") under adversarial pressure. L12 judges Rule 8's register carve-out a plausible contributing factor but explicitly **not** a sufficient explanation. Graded **Suspected**.
**Why deferred:** Unconfirmed; and the judged scorers that would evaluate a fix are currently REFUSED.
**To fix:** Investigate alongside ISSUE-128 once the scorer layer is trustworthy.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-332: two dead prompt YAMLs, and `llm_config.yaml` still names the dead `v1`
**Found:** 2026-09-07, during full-review (L12-15)
**Severity:** P3
**Where:** `src/npc_engine/prompts/quest_generation/slot_fill_v1.yaml`, `prompts/quest_generation/flavor_v1.yaml`; the engine's `llm_config.yaml`
**Description:** Both files are superseded by hardcoded v2 loads and are loaded by nothing. The engine's `llm_config.yaml` still declares the dead `v1` prompt name. (Note `escort_npc.yaml`/`fetch_item.yaml` are loaded via glob and are NOT dead despite zero literal-name hits.)
**Why deferred:** Deleting files is ask-gated.
**To fix:** Delete both YAMLs and correct the config's prompt name.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-333: `prompts/eval/tone_judge.yaml` construction weaknesses
**Found:** 2026-09-07, during full-review (L12-18)
**Severity:** P3
**Where:** `prompts/eval/tone_judge.yaml`
**Description:** Construction assessment only — no judged score cited, per the trust policy. Four of the five currently-REFUSED scorers share this one template, so its criteria clarity is a common-mode factor in the scorer-adequacy work.
**Why deferred:** The scorer layer is under repair; changing the shared template mid-repair would confound it.
**To fix:** Fold into the scorer-adequacy remediation rather than editing standalone.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-335: two unbounded appenders nobody has logged — `:TickLease` nodes and the `SchedulerState` tick-id array
**Found:** 2026-09-07, during full-review (L13-08)
**Severity:** P2
**Where:** `src/npc_engine/graph/` scheduler state writes
**Description:** `:TickLease` nodes accumulate without retention, and `SchedulerState` holds a tick-id **array property** that grows unboundedly and is scanned O(n) on every interval tick — so it is a performance regression as well as a storage leak. Same retention gap as ISSUE-279 (faction-standing decay, ~2,500 nodes/hour) but different nodes, so logged separately rather than folded in.
**Why deferred:** Needs a retention decision consistent with ISSUE-279's.
**To fix:** Decide one retention policy covering ISSUE-279 and both of these, then implement pruning; replace the array property with a bounded structure.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

---

## [CLOSED] ISSUE-085: `world_state.py` uses deprecated `datetime.utcnow()` (Python 3.12+)
**Found:** 2026-06-09, during EXP-21 (W3)
**Severity:** P3 (nice-to-fix — deprecation warning only, not an error)
**Where:** `src/npc_engine/world/world_state.py` (grep `utcnow`)
**Description:** `datetime.utcnow()` is deprecated in Python 3.12 and triggers warnings in every test run. Replace with `datetime.now(timezone.utc)`.
**Why deferred:** Out of scope for EXP-21; affects test noise only.
**To fix:** `s/datetime.utcnow()/datetime.now(timezone.utc)/g` and add `from datetime import timezone` import.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

---

## [CLOSED] ISSUE-092: Redis-backed emotion (and other high-churn) store — deferred to Unity/Unreal phase
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
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
new DI option in `api/dependency_singletons.py`; add Docker Compose Redis service.

---

## [CLOSED] ISSUE-134: the loop's skip-regex matches "ask-gate" inside a sentence that negates it
**Found:** 2026-08-07, while readying the queue for the metrics program
**Severity:** P2 (annoying — silently withholds work from the loop, and says the opposite of what it means)
**Where:** `scripts/_roadmap_cursor_core.py:39` (`ASK_GATE_RE = re.compile(r"ask-gate", re.IGNORECASE)`),
applied over a whole task block by `_flags_for` (`:130-140`).
**Description:** The flag scan is a bare substring match over the task's entire body, so any prose that
merely *mentions* the token flags the task. EVAL-P1.2's body ended with "*Not an ask-gate:* `PROMPT_VERSION`
has no callers outside its own module" — an explicit statement that no human decision was pending — and the
regex matched the two words inside it. The task was therefore skipped by every unattended session for the
whole program, for a reason that asserted the opposite of what the sentence said. The same trap applies to
`LIVE_RE` (`\(live[;,)\s]`) and to any future flag token: a task that discusses a gate is indistinguishable
from a task that has one. Nothing surfaces this — `--list-flagged` prints `EVAL-P1.2  ask-gate`, which looks
entirely correct.
**Why deferred:** The immediate blockage is cleared by rewording EVAL-P1.2 (done 2026-08-07), and a parser
change touches the one module that both the loop and the `/expand-linear-next` skill depend on. Rewording is
also arguably the right fix — prose that discusses a gate is genuinely ambiguous to a regex.
**To fix:** Prefer an explicit, unambiguous marker over prose sniffing: require a dedicated token such as a
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
leading `⛔ ask-gate` on its own line (mirroring how `⏸️` already works as `DEFERRED_TOKEN`), and match only
that. Keep the current regex as a deprecation warning surfaced by `--verify` for one cycle so no existing
gated task silently becomes actionable. Add a test asserting that a body containing "not an ask-gate" is
**not** flagged. Until then, never write the literal token in a task body unless the task really is gated.

## [CLOSED] ISSUE-138: `evals/compare.py` exceeds the 300-line file limit
**Found:** 2026-08-08, during EVAL-P10.2
**Severity:** P3 (nice-to-fix)
**Where:** `evals/compare.py` (412 lines after EVAL-P10.2; was 366 before; ~520 after EVAL-P18.3)
**Description:** `compare.py` pre-existed the 300-line hard limit. EVAL-P10.2 added `_detect_evasion` (~35 lines), pushing it to 412. A split would be natural: extract evasion detection + `_build_delta_table` into `evals/evasion.py`, leaving compare.py as an orchestration-only module.
**Why deferred:** Pre-existing violation aggravated by this task; split is out of scope for EVAL-P10.2.
**To fix:** Extract `_detect_evasion`, `_change_direction`, and `_build_delta_table` into `evals/evasion.py`; import them from `compare.py`.
**Closed:** 2026-08-12, EVAL-P18.3 — **DEC-170** decided not to split (mirrors DEC-169's same-day precedent for `evals/calibration.py`): one coherent pipeline, no external consumer of `CompareResult`/`RunMeta` beyond this module and its test file, eval harness not held to `src/`'s layering constraints. Reopen if the file passes 800 lines or a second consumer needs evasion/comparability logic independently — see DEC-170's Future trigger.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-137: `evals/summary.py::summarize` exceeds the 40-line function limit
**Found:** 2026-08-08, during EVAL-P10.1
**Severity:** P3 (nice-to-fix)
**Where:** `evals/summary.py:168–212` (`summarize`, 45 lines)
**Description:** `summarize` is 45 lines, exceeding the 40-line strict limit from CLAUDE.md. Introduced before EVAL-P10.
**Why deferred:** Pre-existing violation, not introduced by EVAL-P10.1. Fixing it is a separate refactor.
**To fix:** Extract battery-result filtering into a helper (e.g., `_collect_battery_stats`) to bring `summarize` under 40 lines.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-144: `scripts/check_human_gates.py` has 7 lines of headroom under the 300-line cap
**Found:** 2026-08-10, during DEC-164 (interleaving the HUMAN GATE blocks)
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_human_gates.py` (293 lines of non-test code)
**Description:** The file is compliant today (293 < 300, longest function 28 < 40) but has almost no
room. The next feature — a `--why <task>` explainer, or gate-state caching — pushes it over, and
whoever hits the cap will be mid-task and inclined to shave a docstring rather than split.
**Why deferred:** Splitting a cohesive 293-line tool now would be the "artificial split" the code-style
rule warns against, and DEC-164's scope was the gates, not their file layout. Single-task focus.
**To fix:** Follow the precedent already sitting in the same directory — `roadmap_cursor.py` (CLI) over
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`_roadmap_cursor_core.py` (pure logic, frozen models, no I/O). Split into
`check_human_gates.py` (argparse, `_read`, `_force_utf8_streams`, report rendering) and
`_human_gates_core.py` (`HumanGate`, `parse_gates`, `task_states`, `blocked_tasks`, `verify_gates`).
The test module already imports only the pure names plus `main`, so the split is import-path-only.

## [CLOSED] ISSUE-176: `scripts/check_conservation.py`'s `_DEFAULT_GEN_DIR` is hardcoded to `k3_73e6c36`
**Found:** 2026-08-17, during the EVAL-P20→P24 unblock plan (Phase A, noted for Phase B3)
**Severity:** P1 (blocking) — silently audits a stale corpus after regeneration
**Where:** `scripts/check_conservation.py:34-36` (`_DEFAULT_GEN_DIR = .../evals/generations/k3_73e6c36`),
wired as a `make check` gate (`check-conservation`)
**Description:** `check_conservation.py` defaults to auditing `k3_73e6c36` when no `--gen-dir` is passed.
`make check` (and therefore `make check-label-survival`'s sibling `make check` run, and any CI-style
gate) calls it with no argument, so once `EVAL-P20.4` (regeneration #1) lands and the corpus moves to
a new `gen_id`, `make check` keeps silently auditing the old, frozen `k3_73e6c36` directory — a green
`check-conservation` after that point proves nothing about the corpus actually in use, which is exactly
the "silently worthless artifact" failure mode Program 3 exists to eliminate.
**Why deferred:** Parameterizing this is Phase B3's own precondition, not Phase A's — Phase A builds
the mechanism (label survival, trend, regression, panel wiring) without touching the corpus at all, and
fixing this before there is a new `gen_id` to point at would just swap one hardcoded default for
another guess.
**To fix:** Before firing `EVAL-P20.4`, either (a) add a small "current gen_id" pointer file (e.g.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`evals/generations/CURRENT`) that `_DEFAULT_GEN_DIR` reads, updated by the generation step itself, or
(b) drop the default entirely and require `--gen-dir` explicitly, forcing `make check`'s caller
(`scripts/Run-EvalHarness.ps1`, once it calls this rather than the standalone `check-conservation`
target) to pass the real corpus by name. (a) keeps `make check` working with no argument for the common
case; (b) is more explicit and harder to get silently wrong. Whichever is chosen, add a regression test
asserting `check_conservation.main()` refuses to default silently once the flag exists.

## [CLOSED] ISSUE-177: no case-level metadata marks which cases are "grounded" for refusal-rate purposes
**Found:** 2026-08-17, during EVAL-P20.3's follow-on wiring (EVAL-P20→P24 unblock plan, Phase A4)
**Severity:** P2 (annoying) — blocks threading `refusal_result=` into a real `format_summary_lines` caller
**Where:** `evals/refusal_rate.py` (`score_refusal_rate` needs `npc_responses` from "grounded" cases);
no `evals/cases/*.yaml` case carries a `grounded: true`-style marker; the only existing artifact of this
shape is `evals/calibration/p04_grounded_responses.json`, a static test fixture recorded once for
`EVAL-P10.3`, not a live selection mechanism a runner could re-derive from the current case set.
**Description:** `EVAL-P20.3`'s own DONE note (2026-08-15) says threading a real caller through to
`score_refusal_rate` "is follow-on wiring work, not part of this task's Files list," because
`summarize()` classifies cases by guard/capability battery membership, not by "is this case grounded" —
that classification does not exist yet. Investigated for Phase A4 (which wired the judge panel's
`panel_agreement=` into the same `format_summary_lines` call) on the assumption it was the same shape
of task; it is not — the panel wiring needed no new classification, this one does.
**Why deferred:** Guessing at a case-subset heuristic (e.g. "all `case_pos_*` cases are grounded") risks
silently producing a wrong refusal-rate number — exactly the failure mode this whole harness exists to
prevent — without a human decision on what "grounded" means for the live case set today.
**To fix:** A human call: either (a) add a `grounded: true` field to the relevant case YAMLs (the ones
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`p04_grounded_responses.json` was recorded from are a starting point) and have `runner.py`/`judge_runner.py`
select `npc_response` from those cases to call `score_refusal_rate`, or (b) derive "grounded" structurally
(e.g. any case whose expectations include an `anti_hallucination_grounded` matcher). Once decided, thread
the result into both `runner.py:404`'s and `judge_runner.py`'s `format_summary_lines` calls the same way
`panel_agreement=` was threaded in Phase A4.

## [CLOSED] ISSUE-178: two prompt paths bypass NON_PROMPT_NODE_FIELDS and leak raw tick values
**Found:** 2026-08-17, during ISSUE-165 (tick unification)
**Severity:** P3 (nice-to-fix — no known behaviour impact now that tick values are correct)
**Where:** `src/npc_engine/retrieval/graph_rag/subgraph_retriever.py:134` and `:140`
**Description:** DEC-176 strips `emotion_updated_at_tick` and `expires_at_tick` from prompt content
via `NON_PROMPT_NODE_FIELDS`, but two item builders bypass it. The active-pledges item at `:134`
calls `serialize_json(...)` with no `strip_fields` at all *and* re-adds `"expires_at_tick"` to the
dict explicitly. The event items at `:140` pass `strip_fields=_LOW_VALUE_FIELDS`, which does not
include `tick_id`, so `Event.tick_id` reaches prompts. Both were leaking wall-clock-derived values
before ISSUE-165; they now leak correct small game ticks, which is why this is P3 rather than P1.
**Why deferred:** out of ISSUE-165's agreed scope (D1). Fixing `:134` also breaks
`tests/unit/engines/test_pledge_service.py:270-285`, which pins the current pledge-item shape, so it
needs its own test update and a prompt-determinism re-measurement.
**To fix:** pass `strip_fields=NON_PROMPT_NODE_FIELDS` (or a union with `_LOW_VALUE_FIELDS`) at both
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
sites, stop re-adding `expires_at_tick` in the pledge item, and update `test_pledge_service.py`.
Re-run the retrieved_context drift measurement afterwards to confirm it stays at 0.

## [CLOSED] ISSUE-183: EVAL-P21.1/P21.2's named acceptance clauses were never exercised by the live panel run
**Found:** 2026-08-18, verifying the 2026-08-17 overnight panel run against the roadmap
**Severity:** P2 (annoying) - blocks an honest tick of two roadmap items; no wrong data
**Where:** `ROADMAP.md` EVAL-P21.1 and EVAL-P21.2 validation clauses;
`tests/unit/evals/test_judge_panel.py`
**Description:** Both clauses require behaviour the live run happened not to produce.
(1) EVAL-P21.2 requires the audited `case_neg_injection_001` false positive - mixtral alone voting
FAIL - to be **outvoted** by the panel. In the live run mixtral voted *with* the other two seats
3-0 on all three repetitions; the false positive did not reproduce. The case passes, but by
unanimity, not by the consensus rule the clause exists to test.
(2) EVAL-P21.1 requires "a judge that errors yields an explicit inconclusive, never a silent pass".
Zero of 1035 verdicts errored (0 inconclusive, no timeouts), so that path got no live evidence.
Both mechanisms are covered by fixture tests; what is missing is evidence from a real run.
**Why deferred:** neither is fixable by re-running. You cannot make a model reproduce a specific
past false positive on demand, and deliberately breaking Ollama mid-run to force an infra failure is
a fault-injection test, not an overnight pass. Re-running the panel will very likely produce the
same clean result again.
**To fix:** add a fault-injection integration test pointing one panel seat at an unreachable judge
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
endpoint and asserting the persisted row is `inconclusive: true, passed: false`; then either
(a) reword EVAL-P21.2's clause to accept fixture evidence for the consensus mechanism plus live
evidence that consensus ran at all, or (b) record explicitly that the clause was satisfied by
`test_single_dissenting_judge_does_not_create_a_hallucination` and note the live non-reproduction.
That is a human wording call on the roadmap, which is why this is logged rather than decided.

## [CLOSED] ISSUE-186: `k3_73e6c36` cannot serve as an A/B baseline arm (`harness_version` and `seed` are null)
**Found:** 2026-08-18, tracing the A/B path while scoping the combined run
**Severity:** P2 (annoying) - not a defect, but a widely-held wrong assumption worth recording
**Where:** `evals/generations/k3_73e6c36/meta.json`
**Description:** The committed artifact has `config.harness_version = None` and `config.seed =
None`; it predates both EVAL-P18.1 (comparability hash) and EVAL-P20.0 (seeded generation). Any
new run carries a real `harness_version`, and `compare._comparability_error` treats a missing
value "as a value like any other for equality" (its own docstring), so `compare.py` **refuses**
every pairing of `k3_73e6c36` with a post-P18.1 run. Independently, it was generated before the
ISSUE-165 tick unification, so per DEC-186 its behaviour baseline differs from current `main` by
construction. Net: there is currently **zero** valid A/B arm on disk, and `k3_73e6c36`'s value is
as a *labelled calibration corpus* (393 human verdicts, the panel's judge-agreement evidence), not
as a performance baseline.
**Why deferred:** nothing to fix - the artifact is what it is, and EVAL-P20.4 (regeneration #1)
already exists to produce the first valid arm. Logged so the distinction between "calibration
corpus" and "A/B baseline" is written down rather than rediscovered.
**To fix:** no code change. When regeneration #1 lands, record its gen_id in ROADMAP as the
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
baseline arm, and stop referring to `k3_73e6c36` as a baseline.

## [CLOSED] ISSUE-205: the architecture conformance gate matches concrete adapters by naive substring
**Found:** 2026-08-26, during P1 (logged in P2)
**Severity:** P3 (nice-to-fix) - false positives only; it cannot miss a real violation
**Where:** `tests/unit/conformance/` - `test_engines_do_not_import_concrete_llm_adapters`
**Description:** the gate scans engine source text for adapter names as bare substrings. The
name `ollama_adapter` contains `llama_adapter`, so any mention of the real module path - in a
docstring, a comment, or a log message - trips the check. Hit during P1: a new module's
`Used by:` docstring line naming the Ollama adapter module failed the gate, and the docstring
was reworded rather than the gate changed, because changing a conformance gate as a drive-by is
worse than working around it. Same family as ISSUE-191.
**Why deferred:** it is a test-infrastructure fix, and P1/P2 both had a one-word workaround.
**To fix:** match on parsed `import`/`from` statements (`ast.walk` for `ast.Import` /
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`ast.ImportFrom`) instead of raw substrings. That also removes the need for every future
docstring to avoid naming the module it documents.

## [CLOSED] ISSUE-207: `routine_override` smuggles a tick counter into every prompt inside a JSON string
**Found:** 2026-08-26, during P3 while applying NON_PROMPT_NODE_FIELDS everywhere
**Severity:** P2 (annoying) - a live prompt-determinism hole that the deny-list only appears
to cover
**Where:** `retrieval/context/context_utils.py:NON_PROMPT_NODE_FIELDS` (the
`expires_at_tick` entry) vs `graph/scheduling/routine_queries.set_routine_override`
**Description:** the deny-list carried the comment "`expires_at_tick` nests inside
routine_override; _clean strips by key name at any depth, so the sibling `location_id`
survives." That is false. `routine_override` is persisted as an **opaque JSON string**, not a
nested map, so `_clean` -- which walks dicts and lists -- steps straight past it. Verified live
2026-08-26: `mira_innkeeper`'s prompt carries
`"routine_override": "{\"location_id\": \"home\", \"expires_at_tick\": 3371}"`, both keys
intact, inside `npc.profile`. The comment has been corrected in place; the leak has not been
fixed. It matters because the deny-list's own docstring records that wall-clock-derived tick
fields were on their own sufficient to make 36 of 36 otherwise-identical eval records produce
different `npc_response` text (EVAL-P20.0 / DEC-176) -- and this one is invisible to the very
mechanism built to catch it.
**Why deferred:** fixing it means either parsing the string to strip inside it (a special case
in a generic cleaner) or changing how `set_routine_override` persists the property (a graph
schema change, which CLAUDE.md requires approval for). Neither belongs in a payload-stripping
pass.
**To fix:** preferred - persist `routine_override` as a map so the existing deny-list reaches
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
it, which also makes the field readable by Cypher. Cheaper alternative - drop
`routine_override` from the character payload entirely for prompt purposes; nothing in the
prompt teaches the model what a routine override is, so today it is pure noise AND pure
non-determinism. Measure the eval-record reproducibility rate before and after; that is the
metric this defect moves.

## [CLOSED] ISSUE-210: no seeder creates `Need` nodes, so `npc.top_need` is structurally empty
**Found:** 2026-08-26, during P4's live verification
**Severity:** ~~P2 (annoying)~~ **P1 (blocking) — RE-SCOPED 2026-09-17 (T5.2)**: missing
`HAS_NEED` edges mean `need_decay` and `need_quest_trigger` are two dead engines, not just a
cosmetic empty prompt field. `need_decay` reports 0 decays and 0 satisfactions on every tick.
`need_quest_trigger` never fires, so need-driven quests have never generated. This is the
actual impact; the original scoping as P2 was wrong.
**Where:** `seeds/worlds/`, `demo_game/seeds/seed.py`; consumed by
`retrieval/context/context_builder.py:_maybe_append_top_need`
**Description:** `npc.top_need` was empty in 975 of 975 rows of the last eval transcript and
is 0/8 on the live probe after four phases of retrieval fixes. It is not a retrieval defect.
Verified directly against Neo4j 2026-08-26: `MATCH (n:Need) RETURN count(n)` is **0** and
`MATCH ()-[r:HAS_NEED]->() RETURN count(r)` is **0**. The app log confirms it from the other
side, warning on every tick that "the missing relationship type is: HAS_NEED" and "the
missing label name is: Need". `_maybe_append_top_need` and the whole needs/goals reader path
are correct and simply have nothing to read. ISSUE-163 named `top_need` as one of the empty
fields, which made it look like part of that bug; it never was.
**Why deferred:** P4 is a budget-allocation change; seeding a new node kind is a world-data
change with its own review, and it would alter every eval world's baseline mid-plan.
**To fix:** decide whether needs are part of the shipped model. If yes, seed `Need` nodes and
`HAS_NEED` edges in `seed_village_world.py` / `seed_tavern_world.py` / `demo_game/seeds/seed.py`
and re-baseline. If no, delete `_maybe_append_top_need` and the `top_need` slot from the
serializer, and stop paying for the read on every turn. Either way the prompt stops carrying a
permanently-null field. Pairs with P5, which decides slot membership anyway.
**UPDATE 2026-08-27 (planning review): there is a third option, and the data is not missing.**
The checked-in baseline holds **28 nodes labelled `need`** (lowercase) carrying `id`, `kind`,
`level`, `decay_rate` and a `character_id` property — but **zero `HAS_NEED` edges**. The
reader queries `(:Character)-[:HAS_NEED]->(:Need)`. Root cause is ISSUE-213: the label is
wrong, not the data. So "seed or delete" is a false choice — fixing the label resolver plus
writing the edges is the cheaper third path. It is still a graph-schema-shaped change that
mutates the baseline fixture, so it must not land between P9 and P10. See ISSUE-213.
**UPDATE 2026-09-17 (T5.2 re-scope):** The `HAS_NEED` edge seeding is fixed in T5.2.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`need_decay` and `need_quest_trigger` are now unblocked but remain unmeasured until a live
stack run in T6. Note: T5.2 also revives `need_quest_trigger`, increasing quest-generation
LLM amplification — Sprint 4 (immediately following) bounds this. Do not reorder.

## [CLOSED] ISSUE-213: `BASE_NODE_LABELS` ignores the registry's declared `node_type`, so most node kinds land under a lowercase label
**Found:** 2026-08-27, during the P8 planning review (ISSUE-210 root-cause trace)
**Severity:** P2 (annoying — silently splits a node kind into two labels; readers find nothing)
**Where:** `graph/generic/generic_graph_utils.py:20-28` (`BASE_NODE_LABELS`) and `:101`
(`resolve_node_label`); the declared truth it ignores is in
`type_registry/base_nodes/*.yaml` (`node_type:`)
**Description:** `resolve_node_label` lowercases the requested type and looks it up in
`BASE_NODE_LABELS`, which has **seven** entries (character, event, faction, item, location,
quest, world_state). Everything else falls through to `return node_type` — the registry KEY,
which is the lowercase filename stem. Meanwhile every registry file declares the correct label
in its own `node_type:` field (`need.yaml` says `node_type: Need`), and **nothing reads it**.
Verified in the checked-in eval baseline: 28 nodes labelled `need`, 1 labelled `belief`
alongside 44 labelled `Belief`, plus `leverage` and `army`. The readers query the PascalCase
label (`need_queries.py:33` matches `(:Character)-[:HAS_NEED]->(:Need)`), so those 28 nodes
are invisible to the engine — this is the root cause behind ISSUE-210, and `Belief` is
already split across two labels. Separately, the `need` nodes carry a `character_id` property
where the reader expects a `HAS_NEED` edge, so fixing the label alone is not sufficient for
`top_need`.
**Why deferred:** it is a graph-label change affecting every generic-write node kind and it
mutates `evals/fixtures/eval_world_baseline.json`, so it cannot land between P9 and P10
without invalidating the regeneration baseline. It is also not on the critical path for the
A/B measurement — `top_need` is one tier-B slot.
**To fix:** make `resolve_node_label` read the registry's declared `node_type` (falling back to
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`BASE_NODE_LABELS`, then to the key), add a contract test asserting every
`base_nodes/*.yaml` `node_type` round-trips through `resolve_node_label`, and decide
separately whether the existing lowercase nodes are migrated or re-seeded. Do it AFTER the
regeneration, or before P8 — never in between. Pairs with ISSUE-210.

## [CLOSED] ISSUE-215: nothing stops a tool from rewriting line endings across the repo
**Found:** 2026-08-27, during P8 close-out (self-inflicted, repaired in c69465e)
**Severity:** P3 (nice-to-fix - no behaviour changes; it destroys diff reviewability)
**Where:** repo root - no `.gitattributes`; `git config core.autocrlf` is `false`
**Description:** the working tree is a MIX of line-ending styles, and two files are mixed
internally (`DECISIONS.md` 5,029 CRLF / 588 LF; `ISSUES.md` 1,439 / 39). With no
`.gitattributes` and `core.autocrlf=false`, git stores whatever bytes a tool writes. Any
edit made with Python's default text mode on Windows silently converts a whole file to
CRLF, and the commit then shows every line as changed.

**Update 2026-08-27 (P9).** Broader than filed: it is not only Python text mode. In one
session BOTH `sed -i` (LF-ified a 223-line CRLF test module, turning a 19-line rename into
a 451-line diff) and the **Write tool** (LF-ified a 159-line CRLF route, turning a 120-line
edit into a 323-line one) did it, in opposite directions on different files because the
repo is mixed. The Edit tool preserves endings; Write and sed do not. Until the
`.gitattributes` fix lands, the practical mitigation is to run `git diff --stat` before
every commit and confirm the numbers match the size of the intended change — that caught
both instances here before either reached a commit.

Happened for real in P8: `git diff a2b71f5..HEAD` reported 5,792 insertions / 2,709
deletions across 59 files, in which system_v1.yaml's 13 genuinely-changed lines were
unfindable. Repaired in c69465e (per-line for the two internally-mixed files), but only
after the fact - and a reviewer who had read the intermediate commits would have been
reading noise. This is ISSUE-139's failure mode in a different costume: the commit does
not say what changed.
**Why deferred:** the fix is a repo-wide `.gitattributes` with `* text=auto` plus a
one-off `git add --renormalize .`, which rewrites the stored bytes of essentially every
file in the repo. That is a large, history-noisy commit with checkout-time consequences,
and it must not land inside a phase that is gating a regeneration - it would collide with
exactly the diff-reviewability it is meant to protect.
**To fix:** after P10's regeneration, add `.gitattributes` (`* text=auto`, plus `binary`
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
for the fixtures), run `git add --renormalize .` as its own commit with no other content,
and confirm `evals/fixtures/eval_world_baseline.json` is byte-stable across the
renormalisation - a fixture whose bytes move invalidates comparability.

## [CLOSED] ISSUE-221: the eval world is not quiescent, so the RAG scope drifts while the corpus is frozen
**Found:** 2026-08-27, during P9 remediation supply measurement (DEC-214)
**Severity:** P2 (annoying) - any measurement quoting `scope` is not reproducible
**Where:** `src/npc_engine/graph/graph_rag_queries.py::get_rag_scope_ids_for_npc`, and
whatever writes `Quest` nodes while the app idles
**Description:** immediately after `make eval-world-reset`, with no dialogue turns and no
manual ticks, `captain_sorn`'s 1-hop retrieval scope grows continuously. Measured with
`make eval-supply-report` at three points minutes apart:

    captain_sorn scope   30  ->  49  ->  52  ->  54
    captain_sorn rag_supply  5  ->   5  ->   5  ->   5
    corpus              51  ->  51  ->  51  ->  51

Labelling the scope by node type shows what fills it: **41 of the ~54 nodes are `Quest`**,
against 4 Character, 2 Belief, 2 Memory, 1 each of Location/Goal/Faction/Event/Secret.
Quests are not an embeddable type, so the corpus intersection — the quantity that actually
bounds tier-B retrieval — is unaffected, which is why `rag_supply` is pinned at 5 while
`scope` triples.

Two consequences, one benign and one not:
  * BENIGN: every supply number DEC-214 records is stable, because it records the corpus
    intersection and not the scope.
  * NOT: DEC-213 recorded `captain_sorn scope 23` on what it called a clean baseline and
    this session measured 30 on one. Neither is wrong; the quantity simply is not stable,
    and any future entry quoting it will disagree with any other. DEC-210 freezes the
    CORPUS for the duration of a run; nothing freezes the GRAPH.
**Why deferred:** finding out what writes the Quest nodes, and whether it should, is a
scheduler/quest-engine investigation, not a retrieval one. It changes no measurement
DEC-214 relies on, and P10's own preconditions are about the corpus rather than the scope.
**To fix:** identify the writer (start with the tick scheduler and `engines/quest`), decide
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
whether idle quest generation is intended at all, and if it is, either exclude `Quest` from
`_CYPHER_RAG_SCOPE_IDS` or stop quoting raw scope size as a measurement. Add a test that
asserts the scope is stable across two reads with no intervening write.

## [CLOSED] ISSUE-226: nothing identifies which build the running container came from
**Found:** 2026-08-27, during P10 precondition verification (DEC-215 gate 2)
**Severity:** P3 (nice-to-fix — the gate is satisfiable another way, but not the way it is
written)
**Where:** `GET /health`, which returns `{"status":"ok","version":"dev"}`
**Description:** P10's precondition table states gate 2 as "running image == built image,
checked by `/health` vs `git rev-parse --short HEAD`". `/health` reports the literal string
`"dev"` and carries no commit, build time or image digest, so that comparison cannot be
made. Nothing else exposes build identity either: `GET /v1/admin/system/metrics` returns
counters only.

The gate was satisfied in P10 the only way available — by rebuilding immediately before
measuring (`docker compose up -d --build app`, container recreated, exit 0) and recording
that. That is evidence of provenance by construction rather than by verification, and it
cannot detect the specific failure the gate exists to catch: an operator who forgets the
rebuild and measures a stale image. This project's notes call that "the classic false
negative on this project", and there is currently no way to check for it.
**Why deferred:** it is a src/ change to the health route inside a phase whose gates
re-run on any src/ change, and P10 had a sound alternative (rebuild-then-measure in the
same sequence, recorded).
**To fix:** bake the commit sha into the image at build time (a `GIT_SHA` build arg into
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
an env var) and return it from `/health` alongside `version`. Then gate 2 becomes a real
comparison. Add a test that `/health` reports something other than a hardcoded literal
when the env var is set.

## [CLOSED] ISSUE-230: the Neo4j-unavailable fallback contract is unimplemented at every hop
**Found:** 2026-08-28, during the 2026-08 review remediation triage
**Severity:** P2 (annoying)
**Where:** `utils/errors.py:54,301`, `api/errors/exception_handlers.py:113-120`,
`engines/dialogue/degradation.py:107,119`
**Description:** CLAUDE.md declares (strict) "Neo4j unavailable → raise GraphUnavailableError →
API 503". Re-verified at HEAD: `grep -rn "raise GraphUnavailableError" src/` returns **0 rows**, and
`grep -rn "503" src/npc_engine/api/` returns **0 rows**. `register_exception_handlers()` registers
four handlers, none for it, so the catch-all returns 500. `TokenBudgetExceededError` subclasses bare
`Exception`. **Dependency the review missed:** `degradation.py:107,119` are bare `except Exception`
blocks that log and fall through to a canned 200, so a newly-raised `GraphUnavailableError` would be
swallowed before any handler saw it — the degradation fix must land first or in the same change.
**Why deferred:** sequenced to R3.1→R3.2; the regression guard needs Neo4j in CI (R2.2).
**To fix:** narrow the degradation catches; raise on driver `ServiceUnavailable`/`SessionExpired`;
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
register a 503 handler; make `TokenBudgetExceededError` structured. Proof:
`test_neo4j_outage_returns_503` — stop the container, POST dialogue, expect 503; today 500.

## [CLOSED] ISSUE-233: eight integration tests fail — the first ever run of the suite
**Found:** 2026-08-28, immediately after ISSUE-232 made bolt reachable from the host
**Severity:** P1 (blocking) — unknown-severity product defects in shipped engine behaviour
**Where:** `tests/integration/` — faction, faction-gossip, quest lifecycle, reputation, scheme
**Description:** With Neo4j reachable, `pytest tests/integration` returns **35 passed, 8 failed**
(109 s, re-measured 2026-09-01 by R2.2). The passing ones have always skipped and pass on their
first real execution. The 8 below have never been evaluated by anyone.

**Corrected 2026-09-01 (R2.2, settling ISSUE-236):** this entry originally listed **nine**,
including `test_faction_integration.py::test_set_standing_independent_directions`. That test
**passes** on re-measurement, so the real count is 8 and the list below has been narrowed to
match. `.loop-state/gate_baseline.json`'s 8 was right; this entry's 9 was the stale one. The 8
are now the committed allowlist in `scripts/integration_baseline.txt`, enforced on every push by
`make check-integration-baseline` — so they can no longer grow silently while triage waits.

- `test_faction_gossip_integration.py::test_same_faction_pairs_rank_higher_than_strangers`
- `test_faction_gossip_integration.py::test_hostile_pairs_rank_lower_than_neutral_pairs`
- `test_faction_integration.py::test_remove_member_raises_when_not_a_member`
- `test_faction_integration.py::test_remove_controls_raises_when_no_edge`
- `test_quest_lifecycle_integration_v14.py::test_quest_lifecycle_offer_to_completion_and_rewards`
- `test_reputation_integration.py::test_reputation_context_included_above_threshold`
- `test_scheme_advance_tick_integration.py::test_advance_creates_covert_event_and_step`
- `test_scheme_detection_tick_integration.py::test_witnessed_scheme_is_discovered`

**One was investigated and is a genuine product defect**, not a fixture problem:
`test_remove_member_raises_when_not_a_member` fails `DID NOT RAISE FactionMembershipError` —
`FactionService.remove_member()` silently no-ops when the character is not a member, where the
contract says it raises. The other **seven are untriaged**: they may be defects, stale test
expectations, or missing fixtures. Do not assume either way without opening each.

This is CR-L14-02 realised. That finding showed the graph read layer could be gutted to constants
with `make check` staying green; this is the same hole from the other side — the tests that would
have caught these ran for no one, and the skip reported nothing.
**Why deferred:** out of R0's scope (a security fix plus the port mapping that exposed this).
Triage belongs in R3 alongside the other product-correctness work.
**To fix:** triage all eight — defect, stale expectation, or fixture gap — one line each. Fix the
defects; delete or correct the stale expectations. Then wire the suite into CI (R2.2) so the
result cannot go unobserved again. Run with:
`docker compose -f docker-compose.yml -f docker-compose.test.yml up -d` then
`NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=password python -m pytest tests/integration`

---

### Triage, 2026-09-01 (R3.6) — all eight classified, no behaviour changed

Re-measured this session: `8 failed, 35 passed, 0 skipped in 96.03s`, identical to the committed
allowlist. Classification per the standing rule — **report only, no test edited, no code fixed.**

**DEFECT (2) — one shared root cause.**

1. `test_faction_integration.py::test_remove_member_raises_when_not_a_member` —
   `Failed: DID NOT RAISE FactionMembershipError`.
   `faction_writer.py:39` ends `RETURN count(r) AS deleted`. A Cypher aggregation with no grouping
   key returns **exactly one row always**, `deleted = 0` when nothing matched, so
   `result.single()` at `faction_writer.py:138` is never `None` and the
   `if record is None: raise` guard at `:139-144` is **unreachable code**. The correct check is
   `record["deleted"] == 0`. Measured against the live DB, not inferred: running that Cypher
   against ids guaranteed absent returns `[{'deleted': 0}]`, while the same `MATCH` without the
   aggregation returns `[]`.
2. `test_faction_integration.py::test_remove_controls_raises_when_no_edge` —
   `Failed: DID NOT RAISE FactionNotFoundError`. Identical defect, same shape:
   `faction_writer.py:61` `RETURN count(r) AS deleted`, dead guard at `:216-218`.

This supersedes this entry's earlier note that `remove_member()` "silently no-ops". It does, but
the cause is not a missing check — the check is present and structurally unreachable. Both fix in
one line each. Fixing them drops 2 ids from `scripts/integration_baseline.txt` via
`make check-integration-baseline-update`.

**FIXTURE GAP (3).**

3. `test_faction_gossip_integration.py::test_same_faction_pairs_rank_higher_than_strangers` —
   `AssertionError: unfactioned pairs not found in results; assert []` at `:148`.
   The test seeds 4 characters into a **shared, unscoped** database and then calls
   `select_pairs(repo=repo, max_pairs=20, ...)` at `:133`, which ranks globally. Measured against
   the live DB this session: `max_pairs=20` returns **exactly 20** (cap-bound) while `max_pairs=500`
   returns **36** — so 16 candidate pairs are being truncated away, and the test's equal-`gossipy`
   unfactioned pairs are among them. The DB holds 23 Characters and 10 Factions from other tests.
   Not a product defect: the same-faction pair the test cares about *did* rank (the assert at `:147`
   passes). To fix: scope selection to the test's location, or raise the cap above the global
   candidate count.
4. `test_faction_gossip_integration.py::test_hostile_pairs_rank_lower_than_neutral_pairs` —
   `AssertionError: hostile pair not found in results; assert []`. Same mechanism, same file, same
   `max_pairs` truncation.

   **Re-measured 2026-09-04 on the clean M1.3 corpus — this does NOT clear with the wipe.** The
   M1.3 plan predicted both tests would go green once the corpus shrank, on the premise that
   `select_pairs` ranks over a "graph-wide unscoped candidate set" that the 23,375 leaked Quest
   nodes were crowding. That premise is wrong. `fetch_gossip_pairs`
   (`graph/gossip/gossip_queries.py:142`) returns **co-located** active non-player NPC pairs only,
   so Quest and TickLease nodes were never candidates and their removal changes nothing. Measured
   against the freshly restored 250-node fixture: 23 Characters, and **18 seeded co-located pairs**
   (`loc_tavern` 5 chars → 10 pairs, `loc_market_square` 3 → 3, `loc_guard_barracks` 3 → 3,
   `tw_tavern` 2 → 1, `vw_gate` 2 → 1). Each test then adds 4 characters at one fresh location,
   contributing C(4,2) = **6 more**, for 24 candidates against `max_pairs=20` — and the hostile
   pair is by construction the lowest-weighted, so it is exactly the one truncated. The fix
   remains as stated above (scope to the test's location, or raise the cap); the corpus is not
   the variable. Both ids stay in `scripts/integration_baseline.txt`, which remains at 3.
5. `test_scheme_detection_tick_integration.py::test_witnessed_scheme_is_discovered` —
   `assert 0 == 1`. **Ordering bug in the test, not the engine.** `:89-92` calls `upsert_scheme()`
   *before* `_setup()` at `:94` creates the Character node. `scheme_writer.py:36-37` is
   `MATCH (c:Character {id: $npc_id}) MERGE (c)-[:EXECUTES_SCHEME]->(s)` — with no Character the
   `MATCH` yields nothing and the edge is **never created**, leaving an orphaned Scheme.
   `scheme_reader.py:51` then opens with `MATCH (c:Character)-[:EXECUTES_SCHEME]->(s:Scheme)`, finds
   nothing, and returns 0. Cadence is not the cause: `SCHEME_DETECTION_TICK_INTERVAL = 7`, tick 14,
   `14 % 7 == 0`; `SCHEME_DISCOVERY_MIN_STEPS = 2` and `_setup` creates 2 steps. Swap the two calls.

**STALE EXPECTATION (2).**

6. `test_quest_lifecycle_integration_v14.py::test_quest_lifecycle_offer_to_completion_and_rewards` —
   `ValueError: QuestLifecycleEngine requires a TypeRegistry injected via __init__`.
   The test constructs `QuestLifecycleEngine(settings=settings)` at `:43` with no other argument,
   but `quest_lifecycle_engine.py:64-72` documents `registry`, `quest_repo` and `clock` as
   **required** and raises when any is `None` (DEC-122 / SEV-24, ISSUE-165). The test predates that
   DI refactor and was never updated — it could not be, because it had never run. Update the
   construction; the assertions below it are untested and may reveal more.
7. `test_reputation_integration.py::test_reputation_context_included_above_threshold` —
   `AssertionError: assert 'allied' == 'friendly'` at `:223`.
   `reputation_queries.py:58-72` defines `_LABELS` as **exclusive upper bounds** —
   `(20,"neutral"), (50,"friendly"), (101,"allied")` with `if standing < threshold: return label`.
   So `friendly` is `[20, 50)` and `allied` is `[50, 101)`, and standing 50 correctly returns
   `allied` under that convention. The test asserts the boundary is inclusive-friendly.
   **The code is internally consistent; the test asserts the only other reading.** No spec states
   which convention is intended, so this needs a one-line product decision before either is
   changed — do not "fix" it by editing whichever artifact is cheaper.

**UNRESOLVED — mechanism narrowed, cause not proven (1).**

8. `test_scheme_advance_tick_integration.py::test_advance_creates_covert_event_and_step` —
   `assert 0 == 1` at `:105` on `result["advanced"]`.
   Every gate was checked and none explains it: `SCHEME_ADVANCE_TICK_INTERVAL = 5` with tick 10 is
   on-cadence; `MAX_SCHEME_STEPS = 5` > the scheme's `step_count` 0, so it is eligible;
   `SCHEME_ADVANCE_MAX_PER_TICK = 10` does not truncate. The test's own asserts at `:92` and `:94`
   pass, proving the scheme **is** active and visible **to the test's session**. `run_tick` reads
   through `Neo4jSchemingRepository`, which opens its **own** session
   (`scheming_repository.py:36` "session-per-call"). So the surviving hypothesis is that the repo's
   independent session does not observe the write committed on the test's session — a cross-session
   visibility / causal-bookmark gap — which would make this a fixture gap rather than an engine
   defect. `_advance_one` returning `False` on an unresolvable `get_npc_location_id` is the same
   hypothesis at a second read site. **Not confirmed.** To settle it: log or assert what
   `repo.get_all_active_schemes_with_steps()` returns from its own session immediately before
   `run_tick`. Deliberately left unclassified rather than assumed.

**Summary:** 2 defects (one root cause), 3 fixture gaps, 2 stale expectations, 1 unresolved.
The 2 defects and 3 fixture gaps are safe to fix. Item 7 needs a product decision. Item 8 needs one
more measurement. None was fixed here — this task changes only this file.

---

### R3.6 TRIAGE — 2026-09-02, report only, nothing changed

Re-measured with the documented invocation (`docker compose -f docker-compose.yml -f
docker-compose.test.yml up -d neo4j`, then `NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j
NEO4J_PASSWORD=password make test-integration`): **8 failed / 35 passed**, reproducing the
baseline exactly. Note the env vars are load-bearing — without them the suite reports
"9 passed, 34 skipped" and looks green while testing nothing.

The eight failures collapse into **five causes**, three of which are already inside R3's scope:

| # | Cause | Failing tests | Evidence | Lands in |
|---|---|---|---|---|
| **A** | **Faction error contracts are not raised.** Two remove-paths return normally where the test expects a typed error. | `test_faction_integration.py:153`, `:227` | `DID NOT RAISE FactionMembershipError`; `DID NOT RAISE FactionNotFoundError` | **R3.2** — same family as the Neo4j→503 contract: a documented error that no code raises |
| **B** | **Two scheme ticks produce nothing.** Both assert one row and get zero. Likely one shared cause (a tick that silently no-ops), to be confirmed — not assumed. | `test_scheme_advance_tick_integration.py:105`, `test_scheme_detection_tick_integration.py:104` | `assert 0 == 1` in both | **R3.4** — the general form is R3.4(b), `tick_scheduler.py:530` silently no-opping a `None` slot |
| **C** | **Faction-aware gossip pair selection omits expected pairs.** | `test_faction_gossip_integration.py:148`, `:200` | `unfactioned pairs not found in results`; `hostile pair not found in results` | new — nearest to ISSUE-228 (gossip), sized S–M |
| **D** | **`QuestLifecycleEngine` is constructed without its `TypeRegistry`.** Raised from product code, but the defect is at the construction site. | `test_quest_lifecycle_integration_v14.py` | `quest_lifecycle_engine.py:76 ValueError: requires a TypeRegistry injected via __init__` | **R3.4** — engine wiring / composition root |
| **E** | **Reputation threshold labels disagree.** | `test_reputation_integration.py:223` | `assert 'allied' == 'friendly'` | new — S, a boundary or label-map mismatch |

**Sizing conclusion.** R3 is smaller than the eight-failure count suggests. A and D are already
R3.2/R3.4 work; B is very likely one fix for two tests; only C and E are genuinely new, and both
are S–M. **No failure indicates a structural or architectural problem** — there is no evidence
here of a design that needs rework, only of contracts not implemented and wiring not completed.

**Not done, deliberately (R3.6 is report-only):** no root cause was confirmed by debugging, and B's
"one shared cause" is a hypothesis stated as such. Confirming it is R3.4's job, not this task's.
### R3 RESOLUTION — 2026-09-02. 8 failures -> 4, and all four remaining are explained.

Measured with the documented invocation: **4 failed / 41 passed**, from 8 failed / 35 passed.
`scripts/integration_baseline.txt` ratcheted from 8 ids to 4.

**Fixed (4 tests, 3 causes).**

- **Cause A, 2 tests** — `faction_writer.py` `CYPHER_REMOVE_MEMBER` and `CYPHER_REMOVE_CONTROLS`
  end in a bare `RETURN count(r)`. A Cypher aggregate with no grouping key always returns one
  row, so `result.single()` was never `None` and both `raise` guards were unreachable. Now also
  tested `record["deleted"] == 0`. The unit tests had mocked `single() -> None`, a shape real
  Neo4j never produces for these queries, which is why they passed against the defect.
- **Cause B, detection half, 1 test** — a setup-ordering bug. The triage's prescription ("swap the
  two calls") does not work: `_setup` also creates the SCHEME_STEP events, which need the Scheme,
  while `upsert_scheme` needs the Character. Split into `_setup_characters` and
  `_setup_scheme_steps` so the real order — characters, scheme, steps — can be used.
- **Item 8 / cause B advance half, 1 test** — solved, and **not** the hypothesis recorded here.

**Item 8's cross-session hypothesis is refuted.** Measured at the test's exact state:
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`get_all_active_schemes_with_steps` returns 1 from the **test's** session and 1 from the
**repository's own** session. Cross-session visibility works. The real cause is the second read
site: `get_npc_location_id` returned `None`. Isolated —

| Character as written | `get_npc_location_id` |
|---|---|
| `MERGE (c:Character {id: ...})` — as the test wrote it | `None` |
| the same node plus `SET c.is_active = true` | `'loc-...'` |

`graph_reader.py:47` filters `WHERE c.is_active = true`; `null = true` is null. `is_active` is
`required: true` on the Character contract (`character.yaml:9`) and the real seeder sets it, so
the test was creating a contract-violating node. A fixture gap. The detection fixture had the
same omission and passed only because `scheme_reader` does not filter on it — a latent invalid
fixture, now also fixed. The reader divergence behind this is **ISSUE-258**.

**Corrects the R3.6 table.** Cause B was recorded as "likely one shared cause, to be confirmed".
Confirmed false: two tests, two unrelated causes. Neither was the `tick_scheduler.py` `None`-slot
bug the table linked them to — that link was thematic, and R3.4(b) fixed it without touching
either test.

**Still failing (3), each explained and logged separately.**

| Test(s) | Cause | Issue |
|---|---|---|
| 2 faction gossip | global pair-selection truncation at `max_pairs` | **ISSUE-260** |
| 1 quest lifecycle | test targets a removed API; needs a rewrite, not a repair | **ISSUE-259** |

Closed since: the reputation label boundary, decided as `allied` by DEC-252 (**ISSUE-261**,
2026-09-02), which ratcheted `scripts/integration_baseline.txt` from 4 to 3.

Per DEC-250 the programme exit condition is zero *unexplained* failures, not zero failures. That
condition is met: every remaining failure has a measured cause and an owning issue.

## [CLOSED] ISSUE-255: `make lint` does not cover `scripts/`, and there is a live violation there
**Found:** 2026-09-01, during B6 (measured-ceiling gate)
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile` `lint:` recipe (`ruff check src/ evals/`), evidence at `scripts/check_rules.py:45`
**Description:** `make lint` runs ruff over `src/` and `evals/` only. `scripts/` is excluded, and
`python -m ruff check scripts/` reports a real violation today: `F401 sys imported but unused` at
`scripts/check_rules.py:45`, untouched since `add99f16` (the LF normalization commit) and so
never gated. This matters more than it did: `scripts/` now holds the gate scripts themselves —
`check_base_rate.py`, `check_ledger_ids.py`, `check_cited_reports.py`, `check_ceiling_baseline.py`
— so the code enforcing the project's standards is the code exempt from them. Note
`tests/unit/evals/test_gate_scope.py` already fails if the recipe loses `evals/`, so the scope is
deliberately pinned; widening it is a decision, not a typo fix.
**Why deferred:** single-task focus — found while implementing B6, and adding a directory to a
gate recipe can red the build for reasons unrelated to the task in hand. It also needs a decision
about whether `scripts/` gets its own ratcheted baseline (as `evals/` did in EVAL-P15.4) or must
be clean from the start.
**To fix:** decide baseline-vs-clean, fix `check_rules.py:45`, add `scripts/` to the `lint`
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
recipe, and extend `test_gate_scope.py` to pin the wider scope.

## [CLOSED] ISSUE-248: the resolved-issues archive reuses two ids and skips five
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/archive/ISSUES_RESOLVED.md`
**Description:** 157 entries are declared under 155 distinct ids. `ISSUE-035` is declared twice
(lines 280 and 749 — a reputation eval failure and a stubbed `tone_judge` matcher) and
`ISSUE-056` twice (883 and 1197 — pre-existing test failures and a `graph_rag.py` full-scan).
This violates the log's own "ID is monotonic and never reused" rule, so a cross-reference to
either id is ambiguous. Separately, ids 026-030 were never assigned in either file.
**Why deferred:** cosmetic; renumbering a resolved archive would break inbound references from
DECISIONS.md and the review documents, which is worse than the ambiguity.
**To fix:** do not renumber. Append a disambiguation note at the top of the archive naming both
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
reused ids and their two meanings, and record 026-030 as never-assigned so a future session does
not treat the gap as a bug.

## [CLOSED] ISSUE-249: gate baseline comments contradict the files they describe
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile:130`, `project-harness/DECISIONS.md` (DEC-236)
**Description:** `Makefile:130` says "baseline 16 in `.mypy_evals_baseline`"; the file holds `0`.
DEC-236 says `dead_keywords_baseline.txt` records 208; it holds 105, superseded by DEC-237 in the
same session. Both are stale prose next to live numbers, which is the class of drift
`make check-harness` exists to catch but does not cover here.
**Why deferred:** documentation-only; no gate behaviour is wrong.
**To fix:** correct both comments to the live values, and consider extending
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`check_harness_honesty.py` to compare a ratchet comment's quoted number against its baseline file.

## [CLOSED] ISSUE-263: integration fixtures MERGE Characters with raw Cypher, bypassing registry validation
**Found:** 2026-09-02, during ISSUE-258 (the strict `is_active` change)
**Severity:** P3 (nice-to-fix) — no longer silent after DEC-252, but still easy to get wrong
**Where:** 10 files under `tests/integration/` — `test_belief_deception_flag_integration.py`,
`test_director_tick_integration.py`, `test_faction_gossip_integration.py`,
`test_faction_integration.py`, `test_gossip_event_selection_integration.py`,
`test_player_model_tick_integration.py`, `test_relation_phase_transition_integration.py`,
`test_reputation_integration.py`, `test_scheme_advance_tick_integration.py`,
`test_scheme_detection_tick_integration.py`
**Description:** These fixtures build Characters and Factions with `MERGE (c:Character {id: $id})
SET ...` run straight against the driver. That path never reaches
`validate_node_payload`, so a fixture may omit a `required: true` field and the write
succeeds. This is the real-world trigger behind ISSUE-233 item 8: the fixture omitted
`is_active`, the node was written, and every strict reader then skipped it while the read
logged nothing above DEBUG. Confirmed as the mechanism rather than assumed —
`tests/unit/conformance/test_is_active_write_boundary.py` shows the validated path rejects
exactly that payload, and `tests/integration/test_is_active_reader_agreement_integration.py`
shows the raw path accepts it.
**Why deferred:** DEC-252 removes the silence, which was the harmful half — after it, a
Character missing `is_active` is invisible to all 37 readers instead of visible to one and
hidden from 36, so the failure is consistent and reproducible instead of a phantom. Routing
the fixtures through the validated path is a separate, larger change: each would have to
supply all 11 required Character fields, coupling every test to the node schema, and it
touches 10 files across features this task is not otherwise in. Single-task focus.
**To fix:** add one shared fixture helper (e.g. `tests/integration/conftest.py`) that builds a
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
registry-valid Character/Faction payload, validates it through `validate_node_payload`, and
writes the result — then repoint the 10 files at it. Once that exists, a `check-rules` pattern
banning a raw `:Character`/`:Faction` MERGE under `tests/integration/` would keep it true.

## [CLOSED] ISSUE-262: `check-integration-baseline-update` writes CRLF into a LF-normalised file
**Found:** 2026-09-02, during R3 close-out (ISSUE-261)
**Severity:** P3 (nice-to-fix) — costs one manual normalisation per use, never wrong output
**Where:** `scripts/check_integration_baseline.py` (the `--update` write path)
**Description:** `.gitattributes` normalises the repo to LF, but the update path writes with
Python's default text mode, which is CRLF on Windows. Git then sees the whole file rewritten
rather than one line removed. Measured twice now: once during R2.2 and again ratcheting
4 → 3 for ISSUE-261, where a carriage-return grep over `scripts/integration_baseline.txt` matched
immediately after `make check-integration-baseline-update` exited 0.
**Why deferred:** the gate itself is correct and the workaround is one command; fixing the
writer is a `scripts/` change and `scripts/` is outside `make lint`'s scan set (ISSUE-255), so
it wants doing alongside that rather than as a drive-by in a product-correctness commit.
**To fix:** write the baseline with `newline="
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
"` (or `write_bytes`). Then check the other
`--update` writers for the same defect: `check_rules.py`, `check_test_quality.py`,
`check_engine_logs.py` and `check_migrations.py` all rewrite a tracked text file.

## [CLOSED] ISSUE-250: two documents cite ISSUE ids that were never filed
**Found:** 2026-09-01, during R4.5 (ledger hygiene)
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/ROADMAP.md:280`, `project-harness/review-2026-08/FIX_PLANS.md:161`
**Description:** Two planning documents cite ISSUE ids as if they were filed tickets, and neither
exists in `ISSUES.md` or `archive/ISSUES_RESOLVED.md`:

- `ROADMAP.md:280` — "Trend and sequence are **510** and **808** lines of Python, not the
  1,309 / 1,714 quoted (ISSUE-242)." The measurement is correct and reproduces; only the ticket
  reference is dangling. The claim is self-contained, so nothing is lost by dropping the citation.
- `FIX_PLANS.md:161` — "The Ollama-in-CI exclusion belongs to the eval/judge path, ISSUE-240."
  Same shape: the statement stands on its own, the ticket does not exist.

Ids 239-242 were never issued in either file, so a reader chasing either citation finds nothing
and cannot tell whether the ticket was deleted, archived, or never written. `ISSUE-248` records
the same defect for 026-030 in the archive.
**Why deferred:** the fix is a prose edit in `ROADMAP.md` and `FIX_PLANS.md`, and neither file is
in R4.5's scope (`ISSUES.md`, `DECISIONS.md`, `archive/ISSUES_RESOLVED.md`, `SKILLS_QUEUE.md`,
`scripts/`). Editing a task-spec file while executing a different task breaks single-task focus.
**To fix:** delete the two parenthetical citations — the surrounding claims already carry their own
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
evidence — or file the two tickets retroactively. Do not renumber anything.
`make check-ledger-ids` reports both until then, and the "Never assigned" record below keeps the
gate honest without hiding them.

### Never assigned
Recorded so the gap is not read as a deletion and the numbers are not reused.

- `ISSUE-239`
- `ISSUE-240`
- `ISSUE-241`
- `ISSUE-242`

## [CLOSED] ISSUE-252: two ungated gate scripts still default to a superseded generation
**Found:** 2026-09-01, during R4.5 (ledger hygiene)
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_conservation.py:29,243`, `scripts/check_label_survival.py:27`
**Description:** Both scripts hardcode `evals/generations/k3_73e6c36` as their default corpus.
The current corpus is `k3_77688e7_regen1` — the one `scripts/base_rate_baseline.json` and
`scripts/check_dead_keywords.py:43` both point at. Running either script without `--gen-dir`
therefore audits a superseded generation and reports numbers that describe nothing current.

**Corrects R4.5's spec**, which says "Fix the three scripts sharing one hardcoded stale corpus
default, of which only one is tracked." Measured 2026-09-01: it is **two**, not three.
`check_dead_keywords.py` is the third script in that family and it already points at the current
generation. Separately, R1.3 removed `check-conservation` and `check-label-survival` from
`make check`, so neither stale default is reachable from any gate — this is ungated debt, not a
live gate defect, which is why it is logged rather than fixed inside R4.5.
**Why deferred:** changing a default corpus changes what the scripts measure. Neither is gated, so
the change buys nothing today, and doing it inside a ledger-hygiene commit would mix a measurement
change into a documentation change — the attribution error the R2 program exists to stop.
**To fix:** point both defaults at the current generation, or better, derive the default from a
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
single shared helper so the next regeneration updates all three at once. Do it in the same commit
as the next regeneration so the before/after is attributable.

## [CLOSED] ISSUE-259: the quest lifecycle integration test targets an API that no longer exists
**Found:** 2026-09-02, during R3.4 (triage cause D)
**Severity:** P2 (annoying) — one baselined integration failure, no product defect behind it
**Where:** `tests/integration/test_quest_lifecycle_integration_v14.py:43` and below
**Description:** R3.6 classified this as "construct the engine correctly and the assertions below
may reveal more". Measured 2026-09-02: they reveal a great deal more. The test calls
`engine.offer_quest(session=..., ...)`, `engine.accept_quest(session=...)` and
`engine.update_objective(session=...)`. `QuestLifecycleEngine` has **no `offer_quest` method at
all** — offering moved to `QuestOfferService` (`quest_offer_service.py`) — and the methods it does
have (`accept_quest:175`, `update_objective:228`, `evaluate_completion:284`, `fail_quest:340`) no
longer take a `session`, per DEC-122 / SEV-24. The composition root
(`dependencies_engines/quest.py:64`) is correctly wired; this is entirely test-side.
**Why deferred:** this is not a repair, it is writing a new integration test. Every assertion in
the body is unverified — the test has never executed — so it must be re-derived against
`QuestOfferService` + `QuestLifecycleEngine`, not patched line by line. R3.4 bounded cause D to
"fix the constructor and stop if it balloons"; it balloons.
**To fix:** rewrite against the current API: construct `QuestLifecycleEngine` with `registry`,
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`quest_repo` and `clock` (see `tests/unit/engines/test_quest_lifecycle_engine.py:118`), construct
a `QuestOfferService` for the offer step, and drop every `session=` kwarg. Expect the assertions
to need re-deriving rather than porting.

## [CLOSED] ISSUE-260: faction-aware gossip pair selection truncates the pairs its test asserts on
**Found:** 2026-09-02, during R3 (triage cause C, carried from ISSUE-233)
**Severity:** P2 (annoying) — two baselined integration failures
**Where:** `tests/integration/test_faction_gossip_integration.py:148`, `:200`
**Description:** Both tests fail with "pairs not found in results". The earlier triage measured
the mechanism: the tests seed 4 characters into a shared, unscoped database and call
`select_pairs(repo=repo, max_pairs=20, ...)`, which ranks globally. `max_pairs=20` returned
exactly 20 (cap-bound) while `max_pairs=500` returned 36, so 16 candidate pairs were truncated
away and the tests' equal-`gossipy` pairs were among them. Not a product defect: the same-faction
pair the first test cares about does rank, and its neighbouring assert passes.
**Why deferred:** out of R3's scope by DEC-250 — R3.3 is gossip, and the loop's scope excludes it.
Fixing it means either scoping selection to a location or raising the cap, and the second choice
changes ranking behaviour for real callers, so it belongs with the gossip work rather than beside
it.
**To fix:** scope pair selection to the test's location, or raise the cap above the global
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
candidate count. Prefer scoping — a test that depends on global DB state is order-dependent
whatever the cap.

## [CLOSED] ISSUE-264: the documented way to drive ticks is refused in the default local config
**Found:** 2026-09-03, during the per-engine timing work
**Severity:** P3 (nice-to-fix)
**Where:** `.env:53` (`CLOCK_MODE=realtime`), `src/npc_engine/config.py:220`, `:243`
**Description:** `POST /v1/clock/advance` is the documented way to advance the world, but with
the shipped `.env` it returns HTTP 400 `CLOCK_MODE_INVALID` ("Clock can only be advanced in
game_driven mode"). `CLOCK_MODE` defaults to `realtime` and `TICK_AUTOPILOT_ENABLED` defaults
to `True`, so the autopilot owns the clock and manual advance is rejected. Measured on a live
server at tick 23169.
**Why deferred:** not a defect in the engine - both modes work as designed. It is a
discoverability problem, and changing a shipped default is a wider decision than this task.
**To fix:** say in `docs/overview.md` (or the clock route docstring) that `/v1/clock/advance`
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
requires `CLOCK_MODE=game_driven`, and that the realtime default hands the clock to the
autopilot at `TICK_INTERVAL_SECONDS`.

## [CLOSED] ISSUE-266: the docstring audit's Layer vocabulary does not know about scheduler/
**Found:** 2026-09-03, during the per-engine timing work
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/docstring_audit.py`, every module in `src/npc_engine/scheduler/`
**Description:** `scheduler` is a real layer with its own rank (5) in `scripts/check_layers.py`,
but `make check-docstrings` rejects `Layer: scheduler` as an invalid value. Every module in
`scheduler/` therefore declares `Layer: engines`, so the two gates disagree about what layer
these files are in. Reproduced by writing `Layer: scheduler` in a new scheduler module: the
gate exits 2 with "Layer: invalid value 'scheduler'".
**Why deferred:** single-task focus - this task added engine timing, and widening a gate's
accepted vocabulary touches every scheduler module's docstring.
**To fix:** add `scheduler` (and any other ranked package the audit lacks) to the audit's
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
accepted Layer values, then correct the seven `scheduler/` docstrings in one commit.

## [CLOSED] ISSUE-267: no dependency lockfile; the tool choice is unmade
**Found:** 2026-09-03, during R5.5 (CR-L16-05)
**Severity:** P3 (nice-to-fix)
**Where:** `pyproject.toml`, `demo_game/requirements.txt`
**Description:** The repo has no lockfile, so `pip install -e .[dev]` is not reproducible across
machines or across time. R5.5 did the cheap 80%: the one unpinned dependency (`types-PyYAML`)
gained a bound and every ranged dependency gained a ceiling, taking the counts from
13 pinned / 7 ranged / 1 unpinned to **13 / 4 / 0**. `demo_game/requirements.txt` re-declared
`httpx` and `pydantic-settings` at looser bounds than pyproject pinned them, so installing both
files could silently downgrade the engine's pins; those two are now pinned to match.
**Why deferred:** a real lockfile needs a tool decision that is not mine to make — pip-tools
(`requirements.lock`) vs `uv lock` — and each adds a dependency and a CI step. There is also a
wrinkle worth deciding deliberately: `torch` resolves to different local versions per platform
(`2.9.1+cu128` on the dev GPU box, a `+cpu` build in the container), and a naive `pip freeze`
lock would bake one machine's CUDA build into a file the container cannot install.
**To fix:** pick the tool, generate the lock with the torch local-version segment excluded (or
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
with a platform-conditional constraint), make `make install` consume it, and add a gate that
reds when the lock and `pyproject.toml` disagree.

## [CLOSED] ISSUE-268: migration Cypher lives in `scripts/`, outside the `graph/` layer
**Found:** 2026-09-03, during R5.4
**Severity:** P3 (nice-to-fix)
**Where:** all six modules in `scripts/migrations/`
**Description:** Each migration holds its own inline Cypher (constraint creation, backfills,
`MEMBER_OF` edge creation). CLAUDE.md's layer rule puts Neo4j queries in `graph/` only. The rule
is machine-checked by `check_rules`' R005, which scans `src/npc_engine` — so `scripts/` is
outside its reach and this has never reddened a gate.
**Why deferred:** R5.4's single task was down paths and an applied-state record. Its *new* Cypher
did land in `graph/infra/migration_state_writer.py`, so the debt is frozen rather than widened,
but moving six existing migrations' queries is a separate refactor with its own risk.
**To fix:** add per-migration reader/writer modules under `graph/`, leave the scripts as thin
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
CLI adapters over them, and widen `check_rules`' R005 scan to `scripts/` so it cannot recur.
Note that widening the scan needs ISSUE-255 (lint/type coverage of `scripts/`) settled first.

## [CLOSED] ISSUE-270: `make package` output path does not match its documented location
**Found:** 2026-09-03, during R5.3
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile` `package:` target comment; `packaging/npc_engine.spec` COLLECT name
**Description:** The Makefile comment says the output is
`dist/npc_engine_server/npc_engine_server[.exe]`. The binary is actually one level deeper, at
`dist/npc_engine_server/npc_engine_server/npc_engine_server.exe`, because `--distpath
dist/npc_engine_server` and the spec's `COLLECT(name="npc_engine_server")` each contribute a
directory. Cosmetic, but it is exactly the kind of stale path claim R5.3 existed to remove.
**Why deferred:** R5.3's task was making the build work; it does, and the path is correct, only
the comment is imprecise. Changing `--distpath` would move an output other tooling may reference.
**To fix:** either set `--distpath dist` so the collected directory is `dist/npc_engine_server/`,
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
or correct the comment. Prefer the former; check `e2e/` and any installer script first.

## [CLOSED] ISSUE-271: the gossip throughput NFR is still unproven at its target
**Found:** 2026-09-03, during R5.5 (CR-L12-05)
**Severity:** P3 (nice-to-fix)
**Where:** `docs/BUSINESS_REQUIREMENTS.md:34`, `scripts/bench_nfr.py`
**Description:** The stated target is >= 200 NPC pairs per gossip tick. `make bench-nfr` now
measures it, and the first measurement ever taken reports **36 pairs in 1.9 s** against a
requested `max_pairs=200`. That is a *world-size* limit, not an engine limit: the seeded demo
world does not contain 200 eligible pairs, so the tick ran out of work rather than out of time.
The target is therefore neither met nor refuted. (For contrast, the graph-size NFR now measures
27,488 nodes against a 10,000 target and is genuinely met — the review's claim that the graph
held 52 nodes does not reproduce.)
**Why deferred:** proving it needs a synthetic world with >= 200 eligible pairs, which is a
seeding task, not a benchmarking one.
**To fix:** add a scale-seed target that generates enough characters and relationships to offer
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
200+ eligible pairs, then re-run `make bench-nfr` and record the number.

## [CLOSED] ISSUE-272: `make type-evals` is green only in the checkout the editable install points at
**Found:** 2026-09-03, during R5 verification
**Severity:** P2 (annoying) — `make check` cannot pass in a fresh clone or a git worktree
**Where:** `mypy.ini` (`exclude = src/npc_engine/config/`), `scripts/mypy_evals_ratchet.py`
**Description:** `python -m mypy evals/` reports two errors in any checkout that is not the one
`pip install -e .` points at:

```
src/npc_engine/retrieval/embedding/vector_store_factory.py:13: error: Module "npc_engine.config" has no attribute "Settings"
src/npc_engine/graph/infra/db.py:19: error: Module "npc_engine.config" has no attribute "Settings"
```

`src/npc_engine/config/` is a data-only directory holding `llm_config.yaml`, and it shadows the
`config.py` module as a namespace package. `mypy.ini` excludes it, but mypy's `exclude` governs
directory crawling, not modules reached by following an import — so when checking `evals/`, the
resolver finds the directory first.

**This is pre-existing and was not introduced by R5.** Measured three ways:
- Fails identically with `python_version = 3.11` and `3.14`, so the R5.2 bump is not the cause.
- Fails with R5's two new `graph/infra/migration_state_*.py` files temporarily removed.
- **Fails at the base commit `0b110021` in a clean detached worktree** — the same commit recorded
  as "`make check`, 22 targets, exits 0".

Why it looks green day to day: `python -c "import npc_engine"` resolves to the *installed* tree
via the editable `.pth`, so in that one checkout the relative `exclude` path lines up and
`config.py` wins. Every other checkout — a fresh clone, a worktree, a CI runner that installs
before checking out elsewhere — reds. `mypy src/` is unaffected and passes (630 files).

**Why deferred:** it is not R5's task, and the fix is a mypy-resolution change to a gate config
that deserves its own commit and its own counterfactual. Flagging it matters more than fixing it
in passing: this is a gate that reports green for an environmental reason, which is the exact
failure class the 2026-08 programme existed to remove.
**To fix:** stop `config/` being resolvable as a namespace package — the honest options are to
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
rename the data directory (e.g. `src/npc_engine/config_data/`, updating `LLM_CONFIG_PATH` and
the packaging spec's `datas`), or to give mypy an explicit module override that pins
`npc_engine.config` to `config.py`. Verify by running `mypy evals/` in a detached worktree of the
commit under test — not in the installed tree, which cannot reproduce it.

## [CLOSED] ISSUE-293: dialogue prompt Rule 11 references `context.available_interactions`, which no producer emits
**Found:** 2026-09-07, during measurement-remediation Phase 4 (DEC-271, probe_dialogue.py)
**Severity:** P2 (annoying — a standing prompt instruction the model can never satisfy)
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml:181-183` (Rule 11); no producer
under `src/npc_engine/retrieval/context/` (verified: repo-wide grep for
`available_interactions` across `src/npc_engine/**/*.py` returns zero matches)
**Description:** Rule 11 reads: "When CONTEXT contains an `available_interactions` list,
you MUST surface those interactions naturally in your response and set the `action` field
accordingly." No producer, slot, or `CONTEXT_SLOTS` entry named `available_interactions`
exists anywhere in the engine. This is a dead prompt reference: the model is instructed to
act on a key that is structurally never present. (ISSUE-200's fix note references a
DIFFERENT Rule 11 gap in the same rule number — a dangling `quest_id` reference — which was
fixed by serializing `active_quest`; that fix did not touch this `available_interactions`
clause, which is a separate, still-live gap in the same rule.)
**Why deferred:** found while auditing prompt-rule coverage for probe_dialogue.py's context
metrics (measurement-remediation Phase 4), not the task fixing it. Whether the fix is
"build an `available_interactions` producer" or "delete the clause from Rule 11" is a
product decision (does the interaction-affordance feature exist yet at all?), not a bug fix.
**To fix:** decide whether NPC-offered interactions (trade, follow, etc.) are a feature this
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
engine already models elsewhere under a different key — if so, wire that key's producer to
populate `available_interactions` (or rename the rule to the real key); if the feature does
not exist yet, delete the clause from Rule 11 until it does.

## [CLOSED] ISSUE-294: Memory nodes carry no source-linking property — "no memory without a source" cannot be checked as a graph property
**Found:** 2026-09-07, during measurement-remediation Phase 4 (DEC-271, probe_memory.py)
**Severity:** P3 (nice-to-fix — a measurement-design gap, not a data-integrity bug)
**Where:** `src/npc_engine/type_registry/base_nodes/memory.yaml`;
`src/npc_engine/graph/memory/memory_queries.py` (`CYPHER_CREATE_MEMORY`)
**Description:** the measurement-remediation plan's memory-probe invariant is phrased "no
memory without a source." Verified against the schema: a `Memory` node has no
`source_event_id`, `source_character_id`, or any comparable source-linking field — its
declared properties are `id, content, vividness, emotional_charge, created_at_game_time`
(required) plus `occurred_at_game_time, is_historical, last_recalled_at, subject_player_id,
recall_count, never_forget, kind` (optional). The only source-adjacent structure that
exists is the `REMEMBERS` edge (`character -[:REMEMBERS {since_game_time}]-> memory`),
which links a memory to the character who holds it, not to the event/dialogue turn that
produced it. `probe_memory.py`'s invariant (`memory_is_remembered`) checks the nearest
structural equivalent this schema supports — an orphan Memory node with no `REMEMBERS`
edge — documented inline as a deliberate substitution, not a fix.
**Why deferred:** found while building the memory probe (measurement-remediation Phase 4),
which is a measurement task, not a schema change. Adding real source-linking (e.g. a
`source_event_id` property set at creation, or a `DERIVED_FROM` edge to the consolidated
dialogue turns) is a graph-schema change requiring its own migration
(`scripts/migrations/`) and is out of this plan's scope (DEC-271; the plan's own
"Explicitly not in this plan" section excludes engine-behaviour changes).
**To fix:** decide what "source" should mean for a Memory node (the originating Event? the
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
consolidated dialogue turn range? the character who formed it, already covered by
REMEMBERS?), add the chosen property or edge at creation time
(`graph/memory/memory_queries.py`), add a migration for existing Memory nodes, and update
`probe_memory.py`'s invariant to check the real property instead of the REMEMBERS
substitute.

## [CLOSED] ISSUE-296: check-engine-logs is blind to the `_LOGGER` naming convention, so the ratchet undercounts
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P2 (annoying — a gate that silently measures less than it claims; it under-reports,
so it cannot produce a false failure, only a false sense of coverage)
**Where:** `scripts/check_engine_logs.py:29` —
`_LOGGER_NAMES: frozenset[str] = frozenset({"logger", "_logger", "log"})`
**Description:** `_is_logger_info` matches a call only when the receiver name is in that set,
which is lowercase-only. Ten files under `src/npc_engine/engines/` use the uppercase `_LOGGER`
convention, carrying **12** `logger.info` calls the gate never sees: `agenda/agenda_engine.py`,
`clique/clique_formation_engine.py`, `dialogue/relation_mutator.py`,
`faction_politics/faction_politics_engine.py`, `llm/prompt_eval_log.py`,
`military/military_battle_service.py`, `military/military_engine.py`,
`military/military_resource_service.py`, `story_pacing/story_pacing_engine.py`,
`succession/succession_engine.py`. The recorded baseline of 42 is therefore a count over a
subset of the engines tree, not over the tree. This surfaced because DEC-273 added `duration_ms`
to `prompt_eval_log.py` expecting the count to drop to 41; it stayed at 42, because that file's
calls were never counted.
**Why deferred:** Adding `_LOGGER` to the set changes what the gate measures and will raise the
count, requiring a deliberate baseline re-record — a gate-behaviour change that belongs in its
own task with its own review, not folded into a latency change. Single-task focus.
**To fix:** Add `"_LOGGER"` (and consider a case-insensitive match, or matching any Name whose
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
lowercase form is in the set) to `_LOGGER_NAMES`, re-record `scripts/engine_logs_baseline.txt`
with `python scripts/check_engine_logs.py --update`, and extend
`tests/unit/scripts/test_check_engine_logs.py` with a fixture using the uppercase receiver so
the blind spot cannot return.

## [CLOSED] ISSUE-298: three of five engines never read their `llm_config.yaml` temperature
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P2 (annoying — the YAML reads as configuration but is inert, so tuning it produces
no effect and no error; `quest_generation` is the live case, tuned to 0.7 for variety and running
at 0.1)
**Where:** `src/npc_engine/engines/quest_generation/quest_generation_engine.py` (no `temperature`
parameter on `__init__`; `grep -n temperature` over the package returns nothing),
`src/npc_engine/engines/proactive_dialogue/proactive_engine.py:38-39` (`_MAX_TOKENS`/`_TEMPERATURE`
as module constants), `src/npc_engine/engines/llm/protocols.py:71-79`
(`generate_structured` has no `temperature` parameter)
**Description:** Only `chapter` (0.5) and `memory_consolidation` (0.4) actually forward their
configured temperature, because both call plain `generate`. `dialogue` (0.15) and
`quest_generation` (0.7) call `generate_structured`, which takes no temperature argument at all,
so the adapters substitute `STRUCTURED_OUTPUT_TEMPERATURE` (0.1). `proactive_dialogue` (0.8)
honours a hardcoded module constant that merely happens to equal its YAML value. So three of five
engines run at a temperature their config file does not determine.
**Why deferred:** This is not a config edit. There is no clobbered caller value to restore —
fixing it means adding `temperature` to `LLMStructuredProtocol.generate_structured`, which is an
ask-gated public-interface change across three adapters, the mock, and every hand-rolled fake in
the suite. It also risks reviving review finding SEV-27, the reason
`STRUCTURED_OUTPUT_TEMPERATURE` was introduced: before it, dialogue ran at "uncontrolled ~0.8"
and structured output was unreliable. See DEC-273.
**To fix:** Get human approval for the Protocol change; add `temperature` to
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`generate_structured` across `LLMStructuredProtocol`, `OllamaAdapter`, `OpenAICompatibleAdapter`
and `MockLLMAdapter`; keep `STRUCTURED_OUTPUT_TEMPERATURE` as the default when a caller passes
none, so SEV-27's guarantee survives; give `QuestGenerationEngine` a `temperature` parameter and
`ProactiveDialogueEngine` its config values; then re-measure quest-generation variety, which is
the behaviour that motivated 0.7.

## [CLOSED] ISSUE-299: `docs/API.md` and `docs/ARCHITECTURE.md` document WS streaming frames the code does not send
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P3 (nice-to-fix — misleads an integrator reading the published contract)
**Where:** `docs/API.md:138-149`, `docs/ARCHITECTURE.md:495-520`
**Description:** `API.md` documents `WS /v1/ws/dialogue` emitting `{"type":"action"}` and
`{"type":"expression"}` frames and a bare `{"type":"done"}`. The implementation
(`api/routes/dialogue/dialogue_ws.py:189-202`) sends neither of the first two, and its `done`
frame carries a data payload. `ARCHITECTURE.md`'s sequence diagram shows `llm.stream()` followed
by "parse full response" — a design that does not exist: the route calls the blocking
`handler.handle()` and then re-chops the finished string into words via `_iter_token_chunks`.
DEC-273 rejected wiring real streaming on correctness grounds, so the docs should be corrected
toward the code rather than the code toward the docs.
**Why deferred:** Documentation accuracy, not behaviour; out of scope for a latency change.
**To fix:** Rewrite both sections to describe what the route actually sends (a word-chunked
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
replay of a completed generation, then one `done` frame with the payload
`_build_done_data` assembles), and state plainly that time-to-first-frame equals full generation
latency. Cross-reference DEC-273 for why it is not real streaming.

## [CLOSED] ISSUE-300: importing `dialogue_models` as the first `npc_engine` import raises a circular ImportError
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P3 (nice-to-fix — invisible under pytest and in the running app, which import in an
order that happens to work; it bites scripts and any future entry point)
**Where:** `src/npc_engine/retrieval/dialogue_context/dialogue_context_adapter.py:21` importing
`build_serialized_context_with_receipt` from `npc_engine.retrieval.context.context_builder`
**Description:** A standalone script whose first `npc_engine` import is
`from npc_engine.engines.dialogue.dialogue_models import DialogueResponse` fails with
`ImportError: cannot import name 'build_serialized_context_with_receipt' from partially
initialized module ... (most likely due to a circular import)`. The cycle exists today and is
merely masked by the import order pytest and `main.py` happen to establish. It was hit while
writing the DEC-273 token measurement, which had to be routed through a temporary test to obtain
two Pydantic JSON schemas.
**Why deferred:** Breaking the cycle means moving or deferring an import inside `retrieval/`,
which touches the context-assembly path — a change that deserves its own regression run, not a
drive-by during a latency task.
**To fix:** Make `dialogue_context_adapter` import `context_builder` lazily inside the function
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
that needs it, or move `build_serialized_context_with_receipt` to a leaf module neither package
imports at module scope. Add a test that imports `npc_engine.engines.dialogue.dialogue_models`
in a fresh subprocess as the very first `npc_engine` import, so the cycle cannot silently return.

---

## [CLOSED] ISSUE-343: a red-gate HALT at a scar-6.10 phase boundary is swallowed — the night keeps going
**Found:** 2026-09-16, during T0.3 (RED-anchor rig: real `expand_loop.sh`, fake `claude`, forced failing test)
**Severity:** P2 (annoying) — the night-ending guard `MAX_CONSECUTIVE_RED_GATES` silently does not fire on one of the two boundary paths
**Where:** `scripts/expand_loop.sh:754` — `run_phase_boundary "$phase" || true`
**Description:** A phase boundary is reached two ways. On a `PHASE_COMPLETE` token (`case 10)`) the loop checks
`brc -eq 2` and breaks with "stopping: repeated red gates". On the scar-6.10 path — the session returns
`TASK_COMPLETE` for the phase's last task and `phase_now_complete` detects it from the roadmap — the boundary is
called as `run_phase_boundary "$phase" || true`, discarding return code 2. Observed: with `--max-red-gates 1` and
a forced HALT-class failure, the log read `HALT: 1 consecutive red phase gates` and the loop then dispatched
T4.1 anyway. `run_phase_boundary` also returns before `seed_gate_baseline` on rc 2, so the next phase runs
against the previous phase's baseline. Scar 6.10 exists precisely because a red-committed final task
suppresses the `PHASE_COMPLETE` token, so this is the path a red night is most likely to take.
**Why deferred:** found while validating T0.3 (harness-bucket routing); fixing the boundary's return handling is a
separate change to the driver and single-task focus applies. It does not block T0.3, which was validated on the
token path.
**To fix:** treat both boundary call sites the same: capture `brc` on the scar-6.10 path and `break` on 2. Add a
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
rig/driver test in which the fake session returns `TASK_COMPLETE` on the phase's last task with a red gate and
`--max-red-gates 1`, asserting "stopping: repeated red gates" and no further task dispatch.

## [CLOSED] ISSUE-344: every httpx-backed LLM adapter reloads the CA bundle, ~0.5 s per construction on Windows
**Found:** 2026-09-17, during the `make check` speed-up (DEC-283)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/llm/ollama_adapter.py:33` (`__init__`), and the other httpx adapters
**Description:** Each adapter builds its own `httpx.AsyncClient`, and each client calls
`ssl.create_default_context()` → `load_verify_locations` (0.57 s per call, profiled). A plain
`http://localhost:11434` Ollama never uses TLS. Tests that build a real adapter pay this cost: the `tests/unit/llm`
factory tests run ~1.7 s each, and composition-root tests build dozens of adapters.
**Why deferred:** a production-code change in `engines/llm/`. `make check` is already 112 s after DEC-283, and
xdist absorbs this cost.
**To fix:** share one module-level `ssl.SSLContext` across adapters, or pass `verify=False` only when the base URL
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
is `http://`. Measure `pytest tests/unit/llm --durations=10` before and after.

## [CLOSED] ISSUE-345: `test_sev15_type_gate::test_mypy_exits_zero` runs mypy a third time inside `make check`
**Found:** 2026-09-17, during the `make check` speed-up (DEC-283)
**Severity:** P3 (nice-to-fix)
**Where:** `tests/unit/conformance/test_sev15_type_gate.py`
**Description:** `make check` already runs `make type` (mypy src/, hard gate at 0). This test shells out to mypy
again from inside the pytest run: 7.5 s under xdist load, and it is the slowest test after the lifespan fix.
**Why deferred:** removing or skipping a gate-shaped test requires a human call (DEC-224/DEC-250 gate freeze).
**To fix:** decide whether the test earns its place now that `type` is in `check` and CI runs `check` (DEC-238).
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
If not, delete it and cite `type`.

## [CLOSED] ISSUE-346: `make type-demo` shares `.mypy_cache` with `make type`, so each invalidates the other
**Found:** 2026-09-17, during the `make check` speed-up (DEC-283)
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile` `type-demo` / `scripts/mypy_ratchet.py`
**Description:** The same cache thrash DEC-283 fixed for `type-evals`: alternating mypy targets over different
roots in one cache dir forces rechecks (~10 s each way). `type-demo` is not in `check`, so only the CI demo job
and humans running both targets pay the cost.
**Why deferred:** outside `make check`, which is the scope of this task.
**To fix:** pass a `--cache-dir .mypy_cache/demo` through `mypy_ratchet.py` when `--target` is not `src/`, with a
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
test mirroring `tests/unit/scripts/test_mypy_evals_ratchet.py`.

## [CLOSED] ISSUE-348: the demo LLM cache stores an empty reply and replays it forever
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/runners/run_scenes.py:199,231-232`, `demo_game/runners/run.py` (`LLMCache`)
**Description:** A `done` frame with zero tokens is cached as `{"npc_response": ""}`. That dict is truthy, so
`if cached:` treats it as a hit on every later `make demo-run` / `--cached` run and the beat stays empty.
**Why deferred:** `demo-run-live` bypasses the disk cache (in-memory recorder) and fails on an empty reply, so
the gate is not affected; fixing the recording cache is a separate change.
**To fix:** refuse to `put` a response whose stripped `npc_response` is empty (raise, or skip with a warning), and
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
treat such a file as a miss in `get`. Unit test both.

## [CLOSED] ISSUE-350: the WORLD feed scene prints `?` for every event summary
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/runners/run_scenes.py` `WorldFeed.execute` (`evt.get("summary", "?")`)
**Description:** `GET /v1/admin/system/events` rows (`EventFeedRow`) carry the text as `label`, not `summary`, so
every live line reads `[world tick=3] military: ?`. The ACT 5 beat is present but its narration is blank on
screen. The unit tests mock a `summary` key, so they pass.
**Why deferred:** display-only; the event itself is created and verified by `demo-run-live`.
**To fix:** read `label`, and change the scene test's mock to the real `EventFeedRow` shape.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-353: the demo client's 15 s graph timeout is shorter than a synchronous tick with LLM quest generation
**Found:** 2026-09-17, during T2.4 (first RED attempt)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/client.py` (`advance_clock`, `_graph_timeout`); `/v1/clock/advance` runs every due engine
in-request
**Description:** `POST /v1/clock/advance` runs quest generation, which calls the LLM with a 60 s timeout and up to
three fill attempts. With Ollama contended (a crash-looping default app hitting it), the first tick exceeded the
client's 15 s and the demo died in ACT 1 with `ReadTimeout`. It did not recur on a quiet Ollama, but the nightly
shares the GPU with whatever else is running.
**Why deferred:** did not reproduce once Ollama was uncontended; `demo-run-live` reports it as a failure with the
act, so it is visible rather than silent.
**To fix:** give `advance_clock` its own timeout sized to the engine's worst case (or pass `NPC_GRAPH_TIMEOUT_S`
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
through from `DemoConfig`, which `run.py` currently ignores).

## [CLOSED] ISSUE-362: per-NPC trait-modulated emotion model (DEC-137) was removed in T9.1d; re-enabling requires a concrete TraitReadPort implementation
**Found:** 2026-09-18, during T9.1d
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/emotion/` — `TraitModulatedEmotionModel` and `TraitReadPort` deleted
**Description:** `TraitReadPort` had 0 implementors and was never wired (DEC-137, never completed). T9.1d removed the dead port, its serving model class `TraitModulatedEmotionModel`, and all references. Per-NPC personality trait modulation is now absent from the emotion system.
**Why deferred:** The feature was never finished (no concrete implementor existed); removing the dead stub was the DIP-threshold collapse rule. Re-introducing it requires design work beyond T9.1d's scope.
**To fix:** Introduce a concrete `Neo4jTraitReadRepository` that reads trait constants from the graph, re-add `TraitModulatedEmotionModel` as a new file, re-wire `EmotionUpdater` to accept it optionally, and register it in `emotion_model_factory`. Also requires seed data for NPC trait constants.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-364: demo_game/tests/ baseline seeded at 48 (re-seeded 50) — drive to zero
**Found:** 2026-09-21, during T12.1
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/tests/` — 40 NO_ASSERTION findings + 8 EXISTENCE_ONLY_ASSERTION findings
+ 2 CONSTANT_EQ_LITERAL findings
**Description:** T12.1 seeded `scripts/check_test_quality_demo_baseline.txt` at 48 (the count
the new Rule-5 detectors reported on first run). The 48 consists of 40 NO_ASSERTION tests
(UI draw tests that call SUT without asserting anything) and 8 EXISTENCE_ONLY_ASSERTION tests
(`assert hasattr(...)` in core and UI tests). Neither category can be waived — the waiver
mechanism was removed in T12.1. The demo baseline ratchets up on regression but does not block
on existing debt; it will not drive itself to zero.
**Why deferred:** The 40 NO_ASSERTION tests are UI draw tests that verifying "no crash" — each
requires a meaningful assertion about output or side effects. The 8 hasattr tests need value
checks. None of this is blocking T12.1 or T12.2.
Re-seeded 48 → 50 on 2026-09-21 (post-loop review): CONSTANT_EQ_LITERAL was widened to catch
`MODULE_CONSTANT == literal`, surfacing `test_branch_node.py::test_garrick_branch_id_constant` and
`test_sev11_game_end.py::test_lose_location_is_guard_barracks`. The rise is a detector change, not a regression.
**To fix:** For each NO_ASSERTION test, add an assertion about the rendered output, return value,
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
or a side effect. For each EXISTENCE_ONLY_ASSERTION or CONSTANT_EQ_LITERAL, assert behaviour that
uses the value, or delete the test — do not restate the value (`x.y == <literal>`) or swap in
`callable(getattr(x, y))`, which are the same check in a form the scanner misses. Lower the baseline as
findings are fixed. Target: baseline 0, same as `tests/`.

## [CLOSED] ISSUE-367: ~110 mock-echo delegate tests in tests/unit/graph/ were never strengthened
**Found:** 2026-09-21, during post-loop review of T11.2
**Severity:** P3 (nice-to-fix)
**Where:** `tests/unit/graph/test_*_repository.py` (61 tests still named `*_delegates`, plus others)
**Description:** T11.2's spec asked to strengthen every delegate test without integration
coverage. T11.2 changed 5 (the minimum its RED anchor needed) and deleted 10. The rest assert that
a mock returned what the test gave it. They do fail when a method is gutted, so they are weak,
not vacuous.
**Why deferred:** Rewriting ~110 tests is churn for little gain while ISSUE-366 is open. The
integration tests are the real protection.
**To fix:** Delete each delegate test once ISSUE-366 gives its method a positive-path
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
integration test. Do not rewrite them.

## [CLOSED] ISSUE-372: five docs still say `/health` is the only public route
**Found:** 2026-09-24, during DEC-289 (ISSUE-368)
**Severity:** P3 (nice-to-fix)
**Where:** `.claude/skills/npc-coding-principles/SKILL.md:119`, `.claude/commands/full-review.md:71`, `docs/BUSINESS_REQUIREMENTS.md:81`, `docs/INTEGRATION.md:37,86`, `docs/ARCHITECTURE.md:174`
**Description:** DEC-289 amended the auth rule in `project-harness/CLAUDE.md` to name `GET /health` and `GET /readiness`. These files still state `/health` alone (`docs/API.md` and `docs/API_STABILITY.md` already list both). The live exempt set is wider still (CR-L05-06: `/setup/*`, `/docs`/`/redoc`/`/openapi.json`, `/dashboard/*`).
**Why deferred:** DEC-289's task was the CLAUDE.md rule only; the skill is a rule source and the docs are integrator-facing, so each needs a look at the right wording.
**To fix:** Align each to the public set in `tests/unit/api/test_create_app_auth_wiring.py` (`_EXPECTED_PUBLIC`) and the CR-L05-06 classes.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-375: drive `demo_game/` mypy error count from 256 to zero (waits on T13.2)
**Found:** 2026-09-24, during T14.1
**Severity:** P3 (nice-to-fix)
**Where:** `.mypy_baseline_demo` (256 errors across 45 files in `demo_game/`; 255 at time of writing)
**Description:** `make type-demo` ratchets mypy errors in `demo_game/` against `.mypy_baseline_demo`
(baseline 256, now wired into `make check` via T14.1). The ratchet prevents the count from growing
but does not require it to shrink. Reaching zero means the ratchet can be retired and `demo_game/`
brought under the same hard `type` gate as `src/`. The target date for reaching zero is not gated —
the owner decided 2026-09-09 that it is a promise rather than a mechanism.
**Why deferred:** T13.2 is about to delete `demo_game/` modules flagged by the census. Fixing types
in modules T13.2 will cut is wasted work. The split of `game_window.py` (per the issue logged during
T14.2) also belongs first.
**To fix:** After T13.2 completes and the census confirms surviving modules, run
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
`make type-demo-update` to record the post-deletion baseline, then fix errors file by file.
Remove `.mypy_baseline_demo` and the `type-demo` ratchet target when the count reaches zero.

## [CLOSED] ISSUE-374: `get_giver_context` always returns `[""]` for goals — it reads `objective`, the query returns `description`
**Found:** 2026-09-24, during ISSUE-366 (positive-path tests for the quest-generation repository)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/graph/repositories/quest_generation_repository.py:88` (`g.get("objective", "")`); the query is `src/npc_engine/graph/needs_goals/goal_queries.py` (returns `g.description AS description`)
**Description:** The goal rows carry the key `description`, so `get_giver_context` builds `"goals": [""]` for every giver with goals. An integration test asserting the seeded goal text failed with `[''] == ['Protect the forge']`, which confirms it. The quest-generation prompt therefore never sees the giver's goals. The test now asserts only the goal count, and says why in a comment.
**Why deferred:** The task was test strengthening; a `src/` fix is out of scope.
**To fix:** Read `description` (or align the query's alias), then assert the goal text in `test_get_giver_context_assembles_seeded_character`.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites

## [CLOSED] ISSUE-376: split `demo_game/ui/layout/game_window.py` by responsibility (waits on T13.2)
**Found:** 2026-09-24, during T14.2
**Severity:** P2 (annoying)
**Where:** `demo_game/ui/layout/game_window.py` (925 lines, grandfathered at 925 in `scripts/rules_baseline.txt` per DEC-226; hard limit is 800)
**Description:** `game_window.py` grew to 925 lines after DEC-032 declared the size problem resolved. The file mixes model wiring, pygame event handling, view routing, and rendering — clear SRP violation. The R001 baseline entry at 925 lines must be deleted once the file is split, not merely re-baselined. DEC-074 records the waiver history and the corrected path.
**Why deferred:** T13.2 (the census pass) is expected to cut oath and treaty controls inside `game_window.py`. Splitting before the census splits code that may be deleted — wasted work. The drive-to-zero mypy task (ISSUE-375) also belongs after the split.
**To fix:** After T13.2 completes — split `game_window.py` by responsibility into focused modules (e.g. `game_window_model.py`, `game_window_events.py`, `game_window_render.py`, thin `game_window.py` coordinator). Delete — do not re-baseline — the `R001|demo_game/ui/layout/game_window.py:925` entry from `scripts/rules_baseline.txt`. Check that any other `demo_game/` module over 800 lines is also addressed.
**Closed:** 2026-10-21, T22.4 triage (DEC-304); re-log if it bites
