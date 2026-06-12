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

- **Phase in progress:** F (F1 wiring underway)
- **Current batch:** F1.1 landed. Next candidate: F1.2 (trigger_router → tick scheduler + ProactiveQueue drain over WS).
- **Last green commit:** `6f513d3` feat(relationship): F1.1 — persist relationship phase transition.
- **Next:** F1.2 (scheduler + `dialogue_ws`) — its own small batch (scheduler-touching, serialize per invariant 7/3).

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
