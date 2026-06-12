# DEMO_BUILD_LOOP.md — autonomous F→G→H build runbook

**Owner:** the orchestrator (main agent), re-entered each cycle via a scheduled wake-up.
**Goal:** drive **ROADMAP Phase F → Phase G → Phase H** to completion, one `/expand-parallel` batch per cycle,
**fully autonomously** until done or blocked. The user starts this once; it self-continues.
**Authority:** project owner authorized autonomous overnight build (2026-06-12), "everything sequenced"
(F wiring → G surfacing → H demo-game). Apply pre-approved schema; do not re-ask.
**Sibling/precedent:** `project-harness/expansion/OVERNIGHT_LOOP.md` (the EXP-201..230 loop that shipped 30
items in 12 clean cycles). Same machinery, new scope. Reuse its hard-won lessons (below).

This file is the **durable loop state**. On every wake: re-read it top-to-bottom, do exactly one cycle,
update the Progress Log + State pointer at the bottom, then schedule the next wake (or STOP).

---

## Invariants (never violate)

1. **Local only.** Commit to the `munich-demo` branch. **Never `git push`.** Never open a PR.
2. **One global gate per batch.** `make check` (+ `make test-demo` if demo code changed) must be green
   before a batch is integrated and before scheduling the next cycle.
3. **Phase order is law: F → G → H.** Never dispatch a G item before the F route/wiring it consumes is green.
   Never dispatch an H3 item before its H0 enabler is green. H1 (economy) and H2 (content) are pure type-A and
   may run as soon as Phase G is clear (they consume no F route) — but do **not** interleave them into Phase F
   cycles; finish F, then G, then H to keep the gate legible.
4. **Schema is orchestrator-only, just-in-time.** Parallel workers never change schema. Before dispatching a
   batch with a 🔶 item, apply that item's §Schema recipe, commit it, confirm `make check` green — THEN run
   `/expand-parallel`.
5. **Coordination files are orchestrator-owned:** `ROADMAP.md`, this file, `ISSUES.md`, `DECISIONS.md`,
   `demo-expansion/*`. Workers must not touch them.
6. **Stop, don't thrash.** If `make check` can't be made green in 2 focused repair attempts, STOP and surface —
   do not bisect blindly, do not commit red, do not loop on a failing gate.
7. **Merge-first worktree rule (learned, EXP loop cycle 1).** Worktrees fork from `worktree.baseRef=fresh` =
   origin, which is **stale** vs unpushed local `munich-demo`. So **every worker prompt MUST start with:**
   *"FIRST run `git merge munich-demo` in your worktree (resolve any conflict keeping current code) before
   building, so your commit applies cleanly on integration."* Integrate by cherry-picking each worker's feature
   commit; if it still conflicts, the worker didn't merge — re-dispatch it. Do not hand-resolve stale-base
   conflicts.

## The cycle (do exactly one per wake)

1. **Read state.** Read this file's §State pointer + §Progress Log, then §Ordered build plan to find the
   current phase and the next candidate batch.
2. **Pick the batch.** Take the next unchecked `[ ]` items from §Ordered build plan that are (a) in the current
   phase and (b) conflict-free per the batch hints (same-file items → one worker). If the current phase is fully
   `[x]`, advance to the next phase. If F, G, and H are all `[x]` (modulo deferred type-C) → **DONE** (see §Done).
3. **Apply due schema (if the batch has 🔶 items).** Apply the §Schema recipe, `make check`, commit
   `feat(schema): DEC-0NN <what>`. If the type-registry gate fails and you can't fix it in 2 tries → STOP + surface.
4. **Run the batch.** Invoke `/expand-parallel` (it auto-selects/falls back to the conflict-free batch; honor its
   grouping of `⚠conflict` items into one worker). Prepend the merge-first instruction (invariant 7) to every
   worker prompt. Give each worker its ROADMAP exit criterion + the cited `DEMO-Dx` mini-spec (Phase H) or the
   F/G exit line as its brief. Let it dispatch, integrate serially (cherry-pick), run the one global gate, and
   update coordination files.
5. **Verify + record.** Confirm the green gate. Check the `[x]` boxes in `ROADMAP.md` for landed items. Append a
   one-line §Progress Log entry (batch ids, pass/fail, test counts, fixes). Update §State pointer.
6. **Continue or stop.** If unchecked ready `[ ]` items remain → schedule the next wake (§Pacing) with this
   file's path as the continuation prompt. Else → §Done.

## Ordered build plan (the driver — phase order + batch/conflict hints)

> Batch hints: items that **edit the same file** must go to **one worker** (⚠same-file) or run in separate
> cycles. New-file-add items are parallel-safe. The orchestrator re-checks the live tree before each dispatch.

### Phase F — Activate & expose (do FIRST; see ROADMAP §Phase F for exit criteria)
- **F1 wiring** — ⚠ most edit the scheduler / `api/dependencies_engines.py` composition root → **serialize or
  one-worker-per-cycle**. Order: F1.1 (`dialogue_handler.py`, isolated) → F1.2 (scheduler + `dialogue_ws`) →
  F1.3 (composition root) → F1.4 (scheduler) → F1.5 (scheduler) → F1.6 (scheduler + revive investigation) →
  F1.7 (scheduler forgetting tick). Treat each scheduler-touching item as its own small batch.
- **F2 routes** — mostly new files, parallel-safe: F2.2 `player_model.py` (🔶 needs DEC-102 type already
  shipped — none new), F2.3 `schemes.py`, F2.4 pending/director read; F2.1 ⚠ extends `relationship.py`
  (solo); F2.5 optional.
- **F3 correctness** — F3.5 🔶 **SESSION_TURNS new node → needs a fresh DECISIONS entry (DEC-106) before it
  lands** (see §Schema recipes). F3.1/3.2/3.3/3.4/3.6 are independent.

### Phase G — Surface the cognition engines (after F; ROADMAP §Phase G)
- **G1** — ⚠ G1.1 + G1.4 both edit `left_panel.py` → **one worker**. G1.2 (`RetrievalPanel` poller) + G1.3
  (breadcrumb draw) separate.
- **G2** — new panels, parallel-safe (each consumes its F2 route): G2.1 player-model, G2.2 scheme board,
  G2.3 director beat, G2.4 proactive WS, G2.5 deception tell.
- **G3** — G3.1 new scenario file; G3.2 seed enrichment (⚠ edits `seed.py` — coordinate with any H2 seed work,
  but H2 is a later phase so no overlap in time).

### Phase H — Demo-game expansion (after G; ROADMAP §Phase H; specs in `demo-expansion/`)
- **H0 enablers** — ⚠ H0.1/H0.2/H0.5 all append to `client.py` → **one worker** (or sequential). H0.3 + H0.4
  are new route files + client methods → the route file is parallel-safe but the client method appends to
  `client.py` → fold into the same H0 worker. Net: **H0 = one worker for all five** (client.py is the shared
  file), landing the two new route files (`investigations.py`, `chapters.py`) alongside.
- **H1 economy** — ⚠ H1.1–H1.6 **all rewrite `game_end_checker.py`** → **one worker for the whole economy
  rewrite** (keep `evaluate_game_end` ≤40 lines: extract `check_win_multi`/`compute_grade`/failure-selection).
  Plus the end-card UI (`ui/`) and an objective-tracker poller. This is the single highest-value batch — D0's
  "it's a game now" verdict. Can start as soon as Phase G is `[x]`; needs no F route.
- **H2 content** — ⚠ H2.2–H2.5 edit `seed.py`/`seed_npc_data.py` → **one seed worker**. H2.1 branch primitive
  = new files (parallel-safe, but H2.8 depends on it → same or earlier cycle). H2.6 `GameController` guard +
  H2.7 `game_end_checker` per-world de-hardcode (⚠ touches game_end_checker again → after H1 lands).
- **H3 legacy panels** — each consumes an H0 enabler (gate: H0 green first). New panel files parallel-safe;
  poller/client appends ⚠ `client.py`. H3.5 tension HUD is type-A (no enabler) → can land with H1/H2.
- **Deferred type-C** (H-D1 military sim, H-D2 server-side decrement) — **NOT in the overnight set.** Skip; they
  need a human DECISIONS call (OQ-5/OQ-6).

## Schema recipes (pre-approved; apply just-in-time)

Only **two** schema touches in the whole F→G→H run (H is otherwise DEC-free):
- **F3.5 → SESSION_TURNS node (DEC-106, NEW).** Before F3.5: write a `DECISIONS.md` DEC-106 entry proposing a
  `base_nodes/session_turns.yaml` node type (fields: `player_id`, `npc_id`, `turn_index`, `role`, `content`,
  `tick`) to replace the property-key-collision session persistence (OQ-9). Create the YAML, validate via the
  type_registry tests, land it **with** the F3.5 engine change in the same batch (no unused-type gate fail).
  If the type-registry gate can't go green in 2 tries → STOP + surface.
- **F2.2 player_model / F2.3 schemes routes** — the node/edge types (DEC-102/104) already shipped in the EXP
  program; the routes are additive reads over existing types. **No new schema.**

All Phase H enablers (H0.1–H0.5) are route/client additions over existing routes or new read-only routes —
**no schema, no DECISIONS entry.** Economy constants (`WEALTH_WIN_THRESHOLD`, `DEADLINE_TICKS`, etc.) are named
in `config.py` / the demo's `constants.py`, not schema.

## Pacing (scheduling the next wake)

Each `/expand-parallel` cycle is long (parallel workers + integration + gate). After a cycle completes, schedule
the next wake **~60s out** — long enough to flush, short enough to keep momentum overnight. Pass this file's path
as the continuation. The runtime re-invokes automatically; do not poll.

## Done / Stop conditions

- **DONE** — every `[ ]` in ROADMAP Phase F, G, and H is `[x]` except the deferred type-C items (H-D1, H-D2).
  Write a final §Progress Log summary, run one last `make check`, do NOT schedule another wake, post a wrap-up.
- **STOP + surface** — `make check` unrecoverable in 2 tries; a worker repeatedly smuggles schema/scope; a
  type-registry gate (DEC-106) can't go green; or any invariant would break. Leave the tree green at the last
  good commit, write the blocker to §Progress Log, do NOT schedule a wake, surface for the human.
- **User interrupt** — if the user sends a message, honor it; the loop is theirs to redirect.

## Lessons carried from the EXP-201..230 loop (apply preemptively)

- A new graph/service call added to a **shared builder** must be mocked in **every** test file that drives it —
  grep the call site before gating (cost 2 fixes last time).
- Adding a function to a **near-300-line file** tips R001 (file size) + R006 (40-line) together — prefer a
  sibling-module split over a waiver for engine files (e.g. `prompt_builder_standing.py`).
- Don't thread mockable `config` values into pure helpers — `int >= MagicMock` blows up mocked-config tests;
  guard with `isinstance(...)` or use module-default constants.
- Workers sometimes write `from src.npc_engine...` (mypy duplicate-module + import-rule break) — grep `from src`
  on integration and fix the prefix.
- New-node YAML is a generic contract; it does **not** need a per-node Pydantic model to pass the unused-type
  gate (validated with player_model/scheme in the EXP loop) — relevant to DEC-106.

---

## State pointer

- **Phase in progress:** ✅ **PHASES F + G COMPLETE** (modulo deferred F1.6 + F2.3 + G2.2, all gated on DEC-107). Now **Phase H** (turn the demo into a *game*: economy + content + legacy engines).
- **Current batch:** All F + all G (sans G2.2) + **H0 (all 5 enablers) landed**. Next candidate: **H1 economy** (the highest-value batch — multi-objective win/lose).
- **Last green commit:** `c486e12` fix(H0): investigations route helper (after `22f9879` H0 worker).
- **Next:** **H1 economy — the single highest-value batch ("it's a game now", D0's verdict). ONE worker, pure demo-side (`make test-demo`).** Rewrite `demo_game/game_end_checker.py` to a multi-objective win/lose economy per the `DEMO-D3` mini-specs in `demo-expansion/`: **H1.1** multi-objective win (faction-standing OR wealth OR quest-chain OR brokered treaty via H0.2); **H1.2** currency win/lose axis (`WEALTH_WIN_THRESHOLD`; bankruptcy `BANKRUPTCY_LOSE_THRESHOLD` armed after gold was once positive) over `GoldPoller`; **H1.3** faction tension/overreach (gains with one faction cost a rival via `adjust_npc_reputation`, `client.py:~1414`) as a branch/quest effect; **H1.4** tick-deadline pressure (relative `DEADLINE_TICKS` from a latched start tick via `get_clock_state().current_tick`); **H1.5/H1.6** end-card UI (`demo_game/ui/`) + objective-tracker poller. **Constraint:** keep `evaluate_game_end` ≤40 lines / ≤3 nesting — extract `check_win_multi`/`compute_grade`/failure-selection helpers (named constants in `demo_game/constants.py`, no magic numbers). Baseline verified 2026-06-12: `game_end_checker.py` still single-win (2/3 factions ≥ 50) + inert single-lose. Needs NO F route → start now. Inspect `game_end_checker.py` + `game_end_poller.py` + `gold_poller.py` first. After H1 → **H2 content** (seed worker) → **H3 legacy panels** (each gated on its H0 enabler, now all landed). **(H0 enablers FIRST — DONE. Ref below.)** Per §Ordered build plan + invariant 3: ~~H0 enablers FIRST~~ (the only non-pure-demo items — small engine-side route/client additions, DEC-free): **H0 = ONE worker for all five** (H0.1 `EngineClient.break_pledge`, H0.2 `create_treaty`/`get_faction_treaties`/`break_treaty`, H0.3 new read-only `api/routes/investigations.py` + `get_investigation`, H0.4 new `api/routes/chapters.py` + `get_current_chapter`, H0.5 `post_quest_choice`) — `client.py` is the shared file so all five go to one worker; lands 2 new route files. **H0 touches `src/` → run `make check` AND `make test-demo`.** Then **H1 economy** (the single highest-value batch — "it's a game now"): ONE worker rewrites `demo_game/game_end_checker.py` to multi-objective win (faction OR wealth OR quest-chain OR treaty) + currency win/lose + tension/overreach + tick-deadline, keeping `evaluate_game_end` ≤40 lines (extract `check_win_multi`/`compute_grade`/failure-selection) + end-card UI + objective-tracker poller; needs no F route. Then **H2 content** (one seed worker for `seed.py`/`seed_npc_data.py` + branch primitive), **H3 legacy panels** (each gated on its H0 enabler). **Deferred type-C (H-D1/H-D2) NOT in scope.** Start: dispatch the H0 worker (all 5, shared `client.py`). **Original G2 batch notes below (for reference):**
- (ref) **Phase G2 — new cognition-engine panels (pure demo-side; run `make test-demo`).** Each consumes its F2 route + needs a `demo_game/client.py` method (add if missing) + a new panel widget + `game_window`/`right_panel` wiring. Items: **G2.1** player-model "What they think of YOU" panel (F2.2 `GET /npc/{npc}/player-model/{player}` — add `client.get_player_model`); **G2.2 scheme board — BLOCKED on F1.6/F2.3 → SKIP** (note dep); **G2.3** director-beat "something stirs" cue (F2.4 `GET /v1/dialogue/director-beats` — add `client.get_director_beats`; DirectorBeatLog is in-memory so beats appear once the scheduler/autopilot ticks); **G2.4** proactive dialogue in the interactive window over WS (F1.2 delivery + `dialogue_ws` idle drain already land lines; surface the hail live — highlight/prefill from EXP-225); **G2.5** deception "tell" affordance (F2.5 `is_deception` on the beliefs read — subtle buyer-facing reveal). ⚠ G2.x panels each touch `game_window.py`/`right_panel.py` (shared) → if dispatching parallel workers, the shared-file wiring conflicts; prefer ONE worker for the G2 batch (or serialize). Then **G3** (G3.1 intrigue scenario new file; G3.2 seed enrichment ⚠ `seed.py`). Start: dispatch a G2 worker for G2.1 + G2.3 + G2.5 (+ G2.4) as one batch (shared `game_window`), SKIP G2.2.

## Progress Log

- **0 · 2026-06-12 setup** — wrote this runbook; planned ROADMAP Phase H (demo-game expansion) from
  `demo-expansion/` + RECONCILIATION; rebaselined content counts (8 NPC / 4 loc); confirmed only 2 schema
  touches in the whole run (DEC-106 SESSION_TURNS). Loop armed; no cycle run yet.
- **1 · 2026-06-12 F1.1** — PASS. Wired `apply_phase_transition` into `dialogue_handler` after the relation
  delta. New: `graph/relation_phase_reader.py` (edge scalars + stored phase), `engines/relationship/
  phase_transition_applier.py` (read→derive→conditional-write). Tests: +2 unit files (7 cases) + 1 Neo4j
  integration test (skips w/o DB). Gate: `make check` green (2069 passed, 23 skipped, 86.2% cov). Single
  isolated item → implemented inline by orchestrator (cheaper than a cold worktree worker for a 1-file wire).
  Fixes carried-lesson hazard: mocked the new call site in **3** handler-driving test files
  (fallback, knowledge_extraction, routine_disruption) — caught 6 reds on first gate, fixed, re-green.
  Commits: `f20f340` (arm runbook) → `6f513d3` (F1.1).
- **2 · 2026-06-12 F1.2** — PASS. Wired the full proactive delivery path (was entirely unwired): shared
  `get_proactive_queue()` singleton; `ProactiveDialogueTick` collects per-pair `TriggerCandidate`s, routes
  via `select_trigger` to one winner/tick (anti-spam), enqueues keyed by player_id; `dialogue_ws` idle-drains
  the queue → `push_proactive_line` after the first turn until disconnect (first-turn + conn-cap untouched).
  Dispatched **1 worktree worker** (runbook step-4 pattern; F1.2 is a real multi-file batch) → cherry-picked
  `91fa694` clean (merge-first held). Integration fix: typed `_MEMORY_SOURCE` as `TriggerSource` (mypy
  Literal) + ratcheted rules baseline 141→140. Gate: `make check` green (2076 passed, +7 tests, 86.2% cov).
  Adjacent issues logged: ISSUE-094 (no need/event producers — router seam), ISSUE-095 (lazy import).
  Commits: `375ae14` (worker) → `b40d674` (integration fix).
- **3 · 2026-06-12 F1.3** — PASS. Config-selectable emotion model: added `EMOTION_MODEL` setting
  (`vad`|`trait_modulated`) + `engines/emotion/emotion_model_factory.build_emotion_model`; wired
  `get_emotion_updater` to inject the selected `EmotionModelProtocol` (EmotionUpdater already accepted
  `model=`). `trait_modulated` seeds demo-default traits (fear=1.5) so shocks are visibly modulated.
  Implemented inline (small composition-root + config slice, no interface break). +4 unit tests. Gate:
  `make check` green (2080 passed, 86.2% cov). Deferred per-NPC trait fetch → ISSUE-096. Commit: `eed1700`.
- **4 · 2026-06-12 F1.4** — PASS. Wired `PlayerModelEngine` (pure derive) + `player_model_writer` (upsert)
  via a new `PlayerModelTick` adapter (co-located pairs → read RELATES_TO scalars → derive → upsert;
  skips no-edge pairs). Added `player_model_engine` slot to `TickScheduler` (constructor + advance() block
  + response key) and `get_player_model_tick()` singleton in the composition root. Implemented inline
  (mechanical, mirrors proactive-slot pattern). +2 unit tests + 1 Neo4j integration test (skips w/o DB).
  Gate: `make check` green (2082 passed, 24 skipped, 86.3% cov). Commit: `d1a0a97`.
- **5 · 2026-06-12 F1.5** — PASS. Director → scheduler. **Avoided a schema trap:** emitting a beat as
  `Event.event_type=<beat_kind>` would need an enum extension (BASE_EVENT_TYPES={crime,battle,trade,
  discovery}) — forbidden. Correct design: `DirectorTick.decide()` (signals: idle ticks via location
  reader, Standing via `derive_standing`) GATES `EventHandler.run_tick` to inject a valid-type event;
  beat_kind/reason are metadata only. New `engines/director/director_tick.py` + `director_engine`
  scheduler slot + `get_director_tick()` composition wiring. Dispatched 1 worktree worker (brief
  pre-resolved the schema-safe emission so it wouldn't thrash) → cherry-picked `4b1c06a`. Integration
  fix: restored `Does NOT:` line in director `__init__.py` (conformance gate caught it). Gate green
  (2086 passed, 25 skipped, 86.3% cov). Deferred: plateau tracker (ISSUE-097), shared location reader
  (ISSUE-098). Commits: `e236af4` (worker) → `b20c65a` (fix).
- **6 · 2026-06-12 F1.6 DEFER + F1.7** — F1.6 **DEFERRED** for a human design call: `add_scheme_step`
  MERGEs a bare `Event` (no `event_type`) so per-tick advance smuggles invalid nodes; recorded options in
  DEC-107, logged ISSUE-099 (blocks only F2.3 + G2.2). Then implemented **F1.7** (forgetting-decay):
  `MemoryDecayTick` self-gates on `MEMORY_DECAY_TICK_INTERVAL` and runs charge-weighted vividness decay;
  new scheduler slot + `get_memory_decay_tick()` wiring. Implemented inline (mechanical, F1.4 pattern).
  +3 unit + 1 Neo4j integration test (vividness drops over ticks). Gate green (2089 passed, 26 skipped,
  86.3% cov). F1 now complete except deferred F1.6 → advancing to Phase F2. Commit: `28036e2`.
- **7 · 2026-06-12 F2.1** — PASS. `routes/relationship.py` now returns `relationship_phase` +
  `phase_started_at_tick` (the edge props F1.1 writes). Extended `get_relation_phase_state`/`RelationPhaseRow`
  with `phase_started_at_tick`; added `RelationReader.get_relation_phase_row` (keeps route DI testable).
  Caught + fixed a latent route bug: `response_model=RelationshipResponse` vs an `ok_response` envelope
  (would 500 on real calls) → `OkEnvelope[dict]` per codebase convention. Inline; +3 route tests (TestClient
  + dep-override, no Neo4j). Gate green (2092 passed, 26 skipped, 86.4% cov). Commit: `1dc504c`.
- **8 · 2026-06-12 F2.2** — PASS. New `routes/player_model.py` — `GET /npc/{npc_id}/player-model/{player_id}`
  reads F1.4 `PlayerModel` nodes via `get_player_model`, returns perceived_trust/intent (404 when absent);
  registered under API_V1_PREFIX (auth applies). Inline; +2 route tests (TestClient + dep-override/
  monkeypatch, no Neo4j). Gate green (2094 passed, 26 skipped, 86.4% cov). Commit: `1e4f1b6`.
- **9 · 2026-06-12 F2.4** — PASS. **Pending-intents route already existed** (`GET /v1/dialogue/pending`
  reads graph-backed intents from the wired intent_formation engine) → confirmed, no work. Added the missing
  **director-beat read**: F1.5 beats weren't persisted, so new in-memory `DirectorBeatLog` (bounded ring
  buffer) + `DirectorTick` records each fired beat (optional injected log, backward-compat) + `get_director_
  beat_log()` singleton + non-destructive `GET /v1/dialogue/director-beats` (newest-first, limit). Inline;
  +7 tests. Gate green (2101 passed, 26 skipped, 86.5% cov). Commit: `6ecb47f`.
- **10 · 2026-06-12 F2.5** — PASS (optional). Beliefs read now surfaces the BELIEVES-edge `is_deception`
  flag: extended `CYPHER_GET_BELIEFS_FOR_CHARACTER` with `coalesce(r.is_deception, false)`; flows through
  `belief_service` + `GET /beliefs/{character_id}` untyped passthrough (content unchanged — buyer-facing
  tell). Inline; +1 Neo4j integration test (skips w/o DB). Gate green (2101 passed, 27 skipped, 86.5% cov).
  **Phase F2 complete except blocked F2.3** → advancing to Phase F3. Commit: `24938e5`.
- **11 · 2026-06-12 F3.4** — PASS. DI cleanup: `QuestLifecycleEngine` no longer hard-builds `MemoryEngine()`
  in `__init__`; added a `memory_engine` param (default-fallback for direct callers) + a shared
  `get_memory_engine()` lru_cache singleton in the composition root, injected into
  `get_quest_lifecycle_engine`. Inline; +2 DI tests. Gate green (2103 passed, 27 skipped, 86.5% cov).
  Commit: `f538467`.
- **12 · 2026-06-12 F3.1** — PASS. Gossip secret-share now gated by Standing band, not a flat 0.2 random:
  new `engines/gossip/secret_share_policy.secret_share_probability(standing)` (HOSTILE/WARY=0 → ALLIED 0.6).
  Derived the band from the per-pair `trust` ALREADY in `_run_side_effects` scope (`derive_standing(trust,
  0,0)`) → **no new graph read**; extracted `_maybe_propagate_secret`. Carried-lesson hazard: higher prob for
  high-trust pairs made 2 rumor tests reach the (previously-unfired) unmocked `select_gossip_secret` → added
  that mock (initial scope error: assumed `trust` in scope at the secret block; it was in a different method —
  fixed to `int(row["trust"])`). Inline; +3 policy tests. Gate green (2106 passed, 27 skipped, 86.5% cov).
  Commit: `b4f559e`.
- **13 · 2026-06-12 F3.2** — PASS (confirm + lock). The canonical mood line is ALREADY wired end-to-end:
  `EmotionStore`→`EmotionUpdater.get_state`→`dialogue_handler` `emotion_state`→`context_builder` tier0
  emotion item→`payload.npc.emotion.current_mood`. Existing test only covered the stale-property fallback;
  added a test locking that the canonical `emotion_state` mood WINS over `character.current_mood` (DEC-099
  guarantee). No src change needed. Gate green (2107 passed, 27 skipped, 86.5% cov). Commit: `c818233`.
- **14 · 2026-06-12 F3.6** — PASS. Seeded player `KNOWS_ABOUT` edges (`_PLAYER_KNOWS_ABOUT`: player_demo
  knows northern_war_begins + market_fire, firsthand/undistorted) applied AFTER `_seed_player_and_items`
  (edge source must exist first) so `GET /player/{id}/events` returns data on a fresh seed. Demo code →
  ran BOTH gates: `make test-demo` 724 passed + `make check` 2107 passed (86.5% cov). +1 demo seed test.
  Commit: `f1f53e0`.
- **15 · 2026-06-12 F3.3** — PASS. Wired `classify_deception_belief` into the live anti-hallucination eval:
  `_classify_case` now rescues a `refusal_fail` to `deception_intended` when the NPC voiced a planted
  `is_deception` belief (new `_response_reflects_planted_deception` queries the beliefs read — is_deception
  surfaced by F2.5 — and matches content against the response). `deception_intended` is not counted in
  `hallucination_count`; ordinary unsupported claims still `refusal_fail`. Eval-side (not in `make check`
  LLM path, but unit-tested). +2 unit tests. Gate green (2109 passed, 27 skipped, 86.5% cov). Commit: `74535eb`.
- **16 · 2026-06-12 F3.5 🔶 SCHEMA** — PASS (first gate try). Migrated session persistence to first-class
  `dialogue_turn` nodes (DEC-106): new `base_nodes/dialogue_turn.yaml` (property-anchored by npc_id+player_id,
  no edge — matches player_model pattern); rewrote `graph/session_persistence` (replace-on-save delete+create,
  round-trip-safe role/content split+join, read grouped/ordered by turn_index); added
  `:DialogueTurn(npc_id,player_id,tick)` index in `schema_bootstrap`. Fixes OQ-9 player-id collision (each
  turn a node, no dynamic property keys). Rewrote persistence tests as genuine in-memory round-trip + added
  distinct-player no-collision test; fixed the bootstrap call-count test for the new index. Type-registry gate
  GREEN first try (bare node YAML, per carried lesson). `make check` 2110 passed, 27 skipped, 86.5% cov.
  Commit: `d219c42`. **→ PHASE F COMPLETE (modulo deferred F1.6/F2.3) → advancing to Phase G.**
- **17 · 2026-06-12 G1** — PASS. Phase G demo surfacing, all 4 G1 items (one worker; all wire into
  `game_window`). G1.1 facial-glyph live-update (new `on_facial_expression` controller callback, fired from
  both WS-done + REST paths). G1.2 retrieval panel on-turn refresh (keyed to the player's submitted message —
  worker chose on-turn over a poller since retrieval needs the query; sound call). G1.3 PART_OF breadcrumb
  rendered in the draw loop. G1.4 relationship phase: new `client.get_relationship` + `LeftPanelRenderer.
  set_relationship_phase` + window wiring (NPC switch / location / post-turn). Dispatched 1 worktree worker
  → cherry-picked `4184ccd` clean. Pure demo-side (verified zero `src/` imports). +18 demo tests. Gates:
  `make test-demo` 742 passed + `make check` 2110 (unaffected). Commits: `f9cc210`. Adjacent note: DialogueTurn
  doesn't carry facial_expression (controller reads raw metadata) — minor future unify, not logged.
- **18 · 2026-06-12 G2 (G2.1/G2.3/G2.5)** — PASS. One worker for the 3 clear cognition panels (shared
  `game_window`/`right_panel`). G2.1 player-model "What they think of YOU" tab (new `client.get_player_model`
  + `npc_player_model_poller` + `PlayerModelPanelWidget` trust-bar/intent-badge, 17th RightPanel tab).
  G2.3 director-beat cue (new `client.get_director_beats` + `director_beat_poller` head-identity tracking +
  transient "something stirs" HUD line). G2.5 deception tell (`inspect_panel` BELIEFS rows tag is_deception
  with "⚑ planted", content untouched). Cherry-picked `214d0b5` clean; pure demo-side (zero src imports).
  +42 demo tests. Gates: `make test-demo` 784 + `make check` 2110. **G2.2 SKIPPED (F1.6 blocked); G2.4
  deferred to a focused cycle.** Commit: `be4a13a`.
- **19 · 2026-06-12 G2.4** — PASS (confirm + lock). The interactive window ALREADY hails an idle player
  live: F1 intent_formation engine → graph intent queue → `NpcInitiativePoller` (`get_pending_intents`)
  → `_poll_intent_queue` → hail bubble + NPC highlight + input prefill (EXP-225; 4 existing `test_game_window`
  tests). Added `test_npc_initiative_poller.py` locking the poller's client integration (poll buffers intents;
  errors swallowed). No src change. `make test-demo` 787 passed. Commit: `80040c3`. **Phase G2 complete except
  blocked G2.2 → advancing to G3.**
- **20 · 2026-06-12 G3.2** — PASS. Seed enrichment: `_seed_deception_belief` plants a `lira_fence` BELIEVES
  with `is_deception=true` (a heist-cover lie) — feeds the G2.5 "tell", keeps F3.3 from flagging the intended
  lie, and gives G3.1 a lie to reveal. Seeded after the player; idempotent. (Player KNOWS_ABOUT already from
  F3.6; player-model data comes from the F1.4 scheduler tick; scheme seeds await F1.6.) +1 demo test.
  `make test-demo` 788 passed. Commit: `726cfe9`. Did G3.2 before G3.1 (seed is the scenario's data dependency).
- **21 · 2026-06-12 G3.1** — PASS. Intrigue arc in the main demo: new `DeceptionRevealScene` (reads
  `get_beliefs`, surfaces the G3.2-seeded `is_deception` lie as a buyer "tell") + `PlayerModelDisplay`
  (reads `get_player_model` perceived trust/intent after a ClockTick); wired ACT 12 into `run.py` SCENES
  (NarratorCue + deception + tick + player-model); both respect `dry_run`. Scheme beat deferred (F1.6).
  Inline; +6 scene tests. `make test-demo` 794 passed. Found pre-existing `make demo-run --dry-run` harness
  failure (~ACT 8, reproduces with G3.1 stashed) → logged ISSUE-100 (not mine to fix here). Commit: `e9198b4`.
  **→ PHASES F + G COMPLETE (modulo deferred F1.6/F2.3/G2.2) → advancing to Phase H.**
- **22 · 2026-06-12 H0 (all 5 enablers)** — PASS. One worker for the legacy-engine enablers (shared
  `client.py`). New read routes: `api/routes/investigations.py` (GET investigator+event context, api→graph
  via `chapter_queries`... investigation_engine) + `api/routes/chapters.py` (GET /chapters/current →
  `graph.chapter_queries.get_current_chapter`; `ChapterEngine` is a pure writer, no read method — used the
  graph reader, valid api→graph). 7 client methods (break_pledge, create/get/break treaty, get_investigation,
  get_current_chapter, post_quest_choice). Both routes registered under API_V1_PREFIX (auth). Cherry-picked
  `22f9879`; integration fix: extracted `_has_investigation_data` (R006 ≤40 lines, `c486e12`). DEC-free.
  Gates: `make check` 2115 + `make test-demo` 821. Adjacent: ChapterEngine has no read-path API (ISSUE-able
  if chapter-history route needed later). Commits: `22f9879` → `c486e12`.
