# OVERNIGHT_LOOP.md — autonomous expansion-build runbook

**Owner:** the orchestrator (main agent), re-entered each cycle via a scheduled wake-up.
**Goal:** drive the EXP-201..230 program in `EXPANSION_INDEX.md` to completion, one `/expand-parallel`
batch per cycle, **fully autonomously** until done or blocked. The user starts this once; it self-continues.
**Authority:** project owner authorized "auto-approve everything" (2026-06-11) — DEC-097..104 grant all
schema. Apply them; do not re-ask.

This file is the **durable loop state**. On every wake: re-read this file top-to-bottom, do exactly one
cycle, update the Progress Log + State pointer at the bottom, then schedule the next wake (or STOP).

---

## Invariants (never violate)

1. **Local only.** Commit to the `munich-demo` branch. **Never `git push`.** Never open a PR.
2. **One global gate per batch.** `make check` (+ `make test-demo` if demo code changed) must be green
   before a batch is considered integrated and before scheduling the next cycle.
3. **Schema is orchestrator-only, just-in-time.** Parallel workers never change schema. Before
   dispatching any batch containing a `🔶`-flagged item, the orchestrator applies that item's
   pre-approved schema (see §Schema recipes), commits it, and confirms `make check` green — THEN runs
   `/expand-parallel`.
4. **Coordination files are orchestrator-owned:** `EXPANSION_INDEX.md`, `EXPANSION_ROADMAP.md`,
   `ROADMAP.md`, `ISSUES.md`, `DECISIONS.md`, this file. Workers must not touch them.
5. **Stop, don't thrash.** If `make check` can't be made green within 2 focused repair attempts (narrow
   fix or one targeted repair worker), STOP and surface — do not bisect blindly, do not commit red,
   do not loop on a failing gate.

## The cycle (do exactly one per wake)

1. **Read state.** Read this file's §State pointer + §Progress Log, then `EXPANSION_INDEX.md` (esp.
   Carry-forward + Ordered checklist + Next candidate batch).
2. **Pick the batch.** Take the "Next candidate batch" the index suggests (the skill recomputes it each
   time via its §1). If it's empty/0–1 items and no schema-gated items remain → **DONE** (see §Done).
3. **Apply due schema (if the batch has 🔶 items).** For each 🔶 item in the batch, apply its
   §Schema recipe: Read the target YAML, match its format, add the field/type, name any new constant in
   `config.py`. Run `make check`. If green, commit `feat(schema): DEC-0NN <what> for EXP-2NN`. If the
   type-registry gate fails and you can't fix it in 2 tries → STOP + surface (esp. new-node items
   EXP-226/229).
4. **Run the batch.** Invoke `/expand-parallel` (no args → it auto-selects the conflict-free batch).
   Let it dispatch workers, integrate serially, run the one global gate, update coordination files, and
   self-prepare the index (its §7.5). Honor its grouping of `⚠conflict` items into one worker.
   **WORKTREE-BASE RULE (learned cycle 1):** worktrees fork from `worktree.baseRef=fresh` = origin
   (STALE — local setup commits are unpushed). So **every worker prompt MUST start with: "FIRST run
   `git merge munich-demo` in your worktree (resolve any conflict keeping current code) before
   building, so your commit applies cleanly on integration."** Integrate by cherry-picking each
   worker's feature commit; if it still conflicts, the worker didn't merge — re-dispatch it. Do not
   hand-resolve stale-base conflicts. (If the user sets `worktree.baseRef: head` in settings, this
   per-worker merge becomes unnecessary — the orchestrator cannot edit settings itself.)
5. **Verify + record.** Confirm the skill reported green gate. Append a one-line entry to §Progress Log
   (batch ids, pass/fail, test counts, anything sent back). Update §State pointer.
6. **Continue or stop.** If unchecked ready `[ ]` items remain → schedule the next wake (see §Pacing)
   with this file's path as the continuation prompt. Else → §Done.

## Schema recipes (pre-approved; apply just-in-time)

Read the target file first and match its existing field/entry format. All fields are optional/back-compat.

- **DEC-097 → EXP-211/212** — `src/npc_engine/type_registry/base_nodes/memory.yaml`: add
  `subject_player_id` (str, optional, nullable), `recall_count` (int, default 0),
  `never_forget` (bool, default false). Add `MEMORY_FORGET_THRESHOLD` constant to `config.py`.
- **DEC-100 → EXP-214** — same `memory.yaml`: add `kind` (one of `episodic|commitment|fact`, optional,
  null = episodic). (If EXP-211/212 already landed, this is an additive second edit.)
- **DEC-101 → EXP-218** — `base_edges/unlocks.yaml`: add `on_choice_id` (str, optional, nullable).
- **DEC-102 → EXP-226** — new `base_nodes/player_model.yaml` + `base_edges/has_player_model.yaml`. Land
  together with the EXP-226 engine's first reader in the same batch so no unused-type gate failure.
- **DEC-103 → EXP-228** — `base_edges/believes.yaml`: add `is_deception` (bool, default false),
  `deception_goal_id` (str, optional, nullable). Coupling: ensure the anti-hallucination eval treats
  `is_deception=true` as intended (coordinate inside EXP-228's worker brief).
- **DEC-104 → EXP-229** — new `base_nodes/scheme.yaml` + `base_edges/executes_scheme.yaml` +
  `base_edges/scheme_step.yaml`. Add `MAX_ACTIVE_SCHEMES_PER_NPC = 2` to `config.py`. Land with the
  EXP-229 engine in the same batch.

## Pacing (scheduling the next wake)

Each `/expand-parallel` cycle is long (parallel workers + integration + gate). After a cycle completes,
schedule the next wake **~60s out** — long enough to flush, short enough to keep momentum overnight.
Pass this file's path as the continuation so the next wake re-enters the runbook. The runtime re-invokes
automatically; do not poll.

## Done / Stop conditions

- **DONE** — no unchecked ready `[ ]` items remain in `EXPANSION_INDEX.md` (all EXP-201..230 are `[x]`
  or only blocked items remain that are blocked on an external/human factor). Write a final summary to
  §Progress Log, run one last `make check`, do NOT schedule another wake, and post a wrap-up.
- **STOP + surface** — `make check` unrecoverable in 2 tries; a worker repeatedly smuggles schema/scope;
  a type-registry gate for a new node can't go green; or any invariant would have to be broken. Leave
  the tree green at the last good commit, write what blocked to §Progress Log, do NOT schedule a wake,
  and surface the blocker for the human.
- **User interrupt** — if the user sends a message, honor it; the loop is theirs to redirect.

---

## State pointer

- **Phase in progress:** A
- **Phase in progress:** E3 (FINAL; E1+E2 done; 28 of 30: EXP-201..228)
- **Next batch (E3, FINAL):** orchestrator creates `base_nodes/scheme.yaml` (id, npc_id, goal, status,
  created_at) + `base_edges/executes_scheme.yaml` (character→scheme) + `base_edges/scheme_step.yaml`
  (single-string dst_type) + `MAX_ACTIVE_SCHEMES_PER_NPC` in config.py; validate via `pytest -k
  'type_registry or contract or registry'`; commit; then dispatch EXP-229 (scheming engine, XL — first
  reader/writer) + EXP-230 (session persistence, no schema: SessionStore save_to_graph/load_to_graph +
  lifespan hooks). Gate once.
- **On all EXP-201..230 [x]: STOP the loop with a final wrap-up (do NOT schedule another wake).**
- **Last green commit:** d4d06fa (E2 EXP-228 integrated, gate green).

## Progress Log

- **0 · 2026-06-11 setup** — promoted Phases A–E to ROADMAP; granted DEC-097..104; reconciled index to
  EXP-201..230 (dropped 10 built items); wrote this runbook; pruned stale worktrees. Loop armed.
- **1 · 2026-06-11 cycle 1** — Batch EXP-201/203/204 dispatched (3 worktree workers). **EXP-201 ✅**
  integrated (a397661): slice-1 derive_phase + relation_phase_writer; orchestrator fixed a layer
  violation (graph importing engines → phase param now str). Gate green: 1976 passed, 22 skipped,
  85.75% cov; rules baseline ratcheted 141→140. **EXP-203/204 NOT landed** — their worktrees forked
  from stale origin base and cherry-pick conflicted; commits discarded, re-dispatch next cycle with the
  mandatory merge-first worker instruction (now in §The cycle step 4). Learning: worktree.baseRef=fresh
  is stale vs unpushed local munich-demo.
- **2 · 2026-06-11 cycle 2** — Batch EXP-203/204/206 (3 worktree workers, merge-first mandated).
  **All 3 ✅** (f511d42/e0ec882/62975ea) — merge-first WORKED, all cherry-picked clean (fix validated).
  Gate: fixed R006 (EXP-204 pushed `build_serialized_context` >40 lines → extracted `_maybe_append_top_need`)
  and a multi-file mock gap (new `get_needs_for_character` call needed mocking in 2 more context test
  files — exactly 3 such files exist, all now patched). Final fix 86fd746. Green: 1978 passed, 22 skipped,
  85.76% cov; demo 625 passed. Learning: a new graph call in a shared builder must be mocked in EVERY
  test file that drives it (grep the call site before gating).
- **3 · 2026-06-11 cycle 3** — Batch EXP-202/205/207 (merge-first). **All 3 ✅** (0ad8c02/6007e04/ff126b4),
  cherry-picked clean. Gate: EXP-202 tipped `prompt_builder.py` over 300 lines (R001) + `build_dialogue_prompt`
  over 40 (R006) → split `build_standing_line` into new `prompt_builder_standing.py` (engine module needs
  `Does NOT:`/`Dependencies injected:` docstring lines — conformance test caught it) + compressed a comment.
  Fix 32adae2. Green: make check 1985, demo 644. **PHASE A COMPLETE (7/7).** Learning: adding a function to a
  near-300-line file tips R001+R006 together — prefer a sibling-module split over a waiver for engine files.
- **4 · 2026-06-11 cycle 4** — Batch EXP-208 (solo, demo, merge-first). **✅** clean one-shot (1caaa04,
  integrated 859166f) — NO integration fix needed (first such cycle). Gate green: make check 1985, demo 661.
  **PHASE B COMPLETE.** Next is Phase C (first schema-touching phase): orchestrator applies DEC-097 memory
  fields before dispatch.
- **5 · 2026-06-12 cycle 5** — Phase C: applied DEC-097 schema (e6f54b2, gate green) THEN batch
  EXP-209/210/211+212 (merge-first). **All 4 ✅** (dc18e67/e958799/c571ae7). 4 integration fixes (most so
  far): R006 again (player-memory block → `_maybe_append_player_memory`); a worker wrote `from
  src.npc_engine...` (mypy duplicate-module + import-rule break) → fixed prefix; 2 `test_memory_service.py`
  mocks broke on the new `create_memory(subject_player_id=...)` kwarg → added `**_kwargs`. Fix 7a07737.
  Green: make check 2005 (85.83%), demo 661. **PHASES A+B+C COMPLETE (12 items).** Lessons in index
  carry-forward (grep `from src`; mock-signature tolerance; ≤3-file slices).
- **6 · 2026-06-12 cycle 6** — Phase D batch-1 EXP-213/216/217/219 (merge-first, cherry-picked clean).
  **All 4 ✅** (7be05fe/fc56e75/42682f4/6ca22af). 3 fixes: R006 (event_queries row-map → helper); EXP-213
  threaded config thresholds into a pure helper → 8 mocked-config gossip tests hit `int >= MagicMock` →
  guarded the bias block with inline `isinstance(...,int)` ×3 (lets mypy narrow). Fix f8a5fcc. Green: make
  check 2020 (85.97%). **15 items done (EXP-201..213, 216, 217, 219).** Lesson: don't thread mockable config
  into pure helpers — guard or use module defaults.
- **7 · 2026-06-12 cycle 7** — Phase D batch-2 EXP-215/220/224/225 (merge-first, cherry-picked clean).
  **All 4 ✅** (2ac16eb/69f7c80/5e1f230/c26c224). 2 fixes: EXP-224 emotion_panel >300 → DEC-105 waiver +
  re-baseline (demo UI widget, splitting artificial — like DEC-036); EXP-215 redundant `cast` → removed.
  Fix 4d8fd71. Green: make check 2022 (85.99%), demo 694. **19 items done.** EXP-225 also fixed a latent
  `NPC_DISPLAY_NAMES` import crash in game_window.
- **8 · 2026-06-12 cycle 8** — Phase D batch-3 demo EXP-221/222/223 (merge-first, cherry-picked clean).
  **All 3 ✅** (8e14e11/6c69444/36bec00) — clean one-shot, NO integration fix. Gate green (make check 2022,
  demo 723). **22 items done.** Only Phase D schema items (EXP-214, EXP-218) remain before Phase E.
- **9 · 2026-06-12 cycle 9** — Phase D schema: applied DEC-100 (memory.kind) + DEC-101 (unlocks.on_choice_id)
  (6430d34, gate green) THEN EXP-214/218 (merge-first, cherry-picked clean). **Both ✅** (0adc89f/d9b318a).
  1 fix: R006 `QuestChainResolver.choose` → extracted `_offer_choice_successor`. Fix 3d04521. Green: make
  check 2028 (85.99%). **PHASE D COMPLETE — 25 of 30 done.** Next: Phase E (flagship cognition, new node types).
  Follow-up: EXP-214 instantiates MemoryEngine() in quest_lifecycle __init__ (prefer DI injection).
- **10 · 2026-06-12 cycle 10** — Phase E1: created `player_model.yaml` + `has_player_model.yaml` (DEC-102),
  validated via type_registry tests (63 pass), committed 76424e4, THEN EXP-226/227 (merge-first, clean
  cherry-pick). **Both ✅** (4148fef/7b0f1d9). **First brand-new node type — no unused-type gate fail**
  (node YAML is a generic contract; no per-node Pydantic model needed). 2 fixes: R006 director `decide` →
  `_engagement_beat`; player_model `__init__.py` missing `Does NOT:`/`Dependencies injected:` (conformance
  test). Fix 0a31882. Green: make check 2045 (86.07%). **27 of 30 done.**
- **11 · 2026-06-12 cycle 11** — Phase E2: added believes.yaml is_deception+deception_goal_id (DEC-103,
  validated 94 tests, committed 86f53f8), THEN EXP-228 (merge-first, clean cherry-pick). **✅** (3b42061).
  1 fix: R006 on plant_belief + write_belief (verbose Args docstrings → trimmed). Fix d4d06fa. Green: make
  check 2048 (86.09%). **28 of 30 done.** (`from src` grep hit was a docstring, not an import.)
