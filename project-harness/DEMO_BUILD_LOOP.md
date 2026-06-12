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

- **Phase in progress:** F3 (engine correctness & cleanup). F2 complete except blocked F2.3.
- **Current batch:** F1.1–F1.5, F1.7, F2.1–F2.2, F2.4–F2.5, F3.4, F3.1, F3.2, **F3.6** landed; F1.6 + F2.3 DEFERRED/BLOCKED. Next candidate: **F3.3** (deception into eval loop), then F3.5 🔶 last.
- **Last green commit:** `f1f53e0` feat(demo): F3.6 — seed player KNOWS_ABOUT edges.
- **Next:** **F3.3 (EXP-228 s2)** — wire `classify_deception_belief` into the LIVE anti-hallucination eval loop (`_classify_case`). Eval-side change: a planted `is_deception` belief must NOT be scored as a hallucination failure, while ordinary unsupported claims still are. Find `classify_deception_belief` + the eval `_classify_case` (likely under `evals/` or `e2e/`/`src/.../eval`); check how cases are classified + thread the deception check. ⚠ may touch eval harness, not demo. **F3.5 🔶 LAST** — DEC-106 `dialogue_turn` node schema just-in-time (orchestrator-only): write the DECISIONS entry + `base_nodes/dialogue_turn.yaml` (fields per ROADMAP F3.5: player_id, npc_id, turn_index, role, content, occurred_at_game_time, tick), land it WITH the SessionStore→node migration in ONE batch (no unused-type gate fail); STOP+surface if the type-registry gate can't go green in 2 tries. **After F3.5 (or if blocked) → Phase F is done (modulo F1.6/F2.3) → advance to Phase G.**

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
