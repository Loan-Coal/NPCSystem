# NPCSystem — Engine Roadmap

**Status (2026-09-03): the 2026-08 remediation programme is retired.** R0–R5 are complete and
archived. The metrics-readiness review of 2026-09-03 replaced them with two live programmes:
**M** — make the metrics mean something — and **R6** — make the overnight loop trustworthy.

**What the review found.** The harness is sound: Wilson intervals, exact McNemar, bootstrap
kappa, a three-model judge panel, and a trust policy enforced in code. What is broken is
everything the instruments point at. A live write leak mints one draft Quest per tick forever
(23,292 nodes against ~681 nodes of real world content, ISSUE-273). The judge calibration set is
two thirds orphaned — 393 labels, 66.4% surviving, and **zero** surviving rows for the two
hallucination-facing scorers, whose kappas are therefore computed against cases that no longer
exist. 44 of 46 capability cases are unlabelled. A canned hedge scores 37/37 against the guard
battery. Latency, cost per turn and long-horizon consistency are not measured at all.

**The queue below holds the mechanical half of M**, which the loop can grind unattended.
Everything needing a human judgment or a live model run sits outside the fence, so the day is
spent on judgment and the night on grinding.

Every task carries a **RED anchor** — a check that fails today and passes after. A check bound to
an artifact's form rather than the behaviour it stands for cannot be verified, which was the root
cause the 2026-08 review found; a task without a red-first anchor must not be ticked.

**Phase order is a dependency order, not a priority order.** M1 before M2 — perf numbers taken on
a leaking graph measure the leak. M1 and M2 before M3 — do not re-author cases against a corpus
that is about to change. M3 before M4 — re-authoring changes both what is generated and what is
labelled, so doing it after the regeneration burns the entire relabel, which is the most
expensive human step in the programme.

### Carry-forward notes

*Cheap context for the next session. Add a line when a task creates something downstream work
needs; delete it once consumed. Keep <= 10 lines.*

- ISSUE-273 must land before any graph wipe, or the leak refills within a day.
- Integration tests need the override: `docker compose -f docker-compose.yml -f
  docker-compose.test.yml up -d`, then `NEO4J_URI=bolt://localhost:7687`. Base compose alone
  cannot reach bolt (DEC-232).
- Judge panel is `mixtral:8x7b` + `qwen2.5:14b` + `llama3.1:8b`. The judge must never equal a
  generation model — `evals/judge_config.py` raises `JudgeModelCollisionError` (DEC-143, DEC-183).
- The flag scan is a substring match over a task's whole body (ISSUE-134), so never write the
  literal gate token in prose. Use the ⏸️ glyph, which matches exactly.
- The loop must run from its own worktree once R6.3 lands (ISSUE-139).

### History

| What | Where |
|---|---|
| The 2026-08 remediation programme (R0–R5, 37 items, 8 phases) | `archive/ROADMAP_remediation-2026-08_2026-09-03.md` |
| Full pre-remediation roadmap (phases 0–26, EXP/F-G-H/SEV programs, eval P0–P31, 210 ticked items) | `archive/ROADMAP_pre-remediation_2026-08-28.md` |
| Phases 0–13 | `proposals/archive/ROADMAP_through_phase13_2026-06-03.md` |
| Phases 14–26 | `archive/ROADMAP_phase14-26_2026-06-11.md` |
| The 2026-08 review itself | `CODEBASE_REVIEW.md`, `review-2026-08/` |

<!-- LOOP:QUEUE start -->
<!-- Everything between these markers is the overnight loop's work queue.
     scripts/roadmap_cursor.py sees NOTHING outside these markers — deliberate.
     Scope agreed 2026-09-03: the mechanical half of the M programme (M1, M2). A task
     tagged with the deferred-token glyph or "(live" is skipped without spending a session.
     M3, M4 and R6 sit outside the fence: M3 and M4 need human judgment and live model
     runs, and R6 would have the loop rewrite its own driver mid-run. -->

### Phase M1

Graph integrity. Nothing measured before this means anything — the database is 97% leaked
Quest nodes, and one node kind is split across two labels.

- [x] **M1.1** Stop the quest leak — one draft Quest is minted per tick, forever
Files: `src/npc_engine/engines/quest_generation/world_state_quest_trigger.py`, plus a new
regression test under `tests/unit/engines/quest_generation/`
Spec: `run_tick` guards only on `self._last_triggered_tick == tick_id`, which dedupes the same
tick fired twice — not the same condition firing across successive ticks. The `world` WorldState
node sits permanently at `epoch="war"`, so `_EPOCH_ARCHETYPE_MAP` resolves on every tick and
`_pick_npc` falls through to `get_any_military_npc()` (`LIMIT 1`), which always returns
`captain_sorn`. Each tick therefore mints one `:Quest {source:"generated", status:"draft"}` node
and spends one LLM call. Measured on the running database 2026-09-03: 23,292 leaked quests and
23,292 `HAS_QUEST` edges, growing from 2026-08-27 at up to 7,104/day and still growing.
Reuse the guard that already works: `need_quest_trigger.py:117` calls
`has_draft_quest(character_id=...)`, which is keyed on outstanding state rather than on tick
identity. Mirror it, and add a cap on outstanding drafts per NPC. Do NOT invent a third
idempotency scheme — `event_quest_trigger`'s `NOT ((:Quest)-[:CAUSED_BY]->(e))` guard is also
correct, and the data proves it: exactly 2 such quests against exactly 2 `conflict` events.
RED anchor: a test that runs five ticks under a stable `war` epoch and asserts the quest count
after tick five equals the count after tick one. Today it is five times larger.
Blocks: M1.3, and every number M2 and M4 produce. ISSUE-273. ✅ AUTO (M1.1, 2026-09-03)

- [x] **M1.2** Make `resolve_node_label` read the registry's declared `node_type`
Files: `src/npc_engine/graph/generic/generic_graph_utils.py`,
`evals/fixtures/eval_world_baseline.json`, plus a new contract test
Spec: `BASE_NODE_LABELS` (`:20-28`) holds seven entries. `resolve_node_label` (`:101`) lowercases
the requested type, misses the table, and returns the registry KEY — which is the lowercase
filename stem. Meanwhile every `src/npc_engine/type_registry/base_nodes/*.yaml` already declares
the correct label in its own `node_type:` field, and nothing reads it. Measured on the running
database 2026-09-03: `Belief` (44 nodes) and `belief` (1) are the same concept under two labels,
and 28 `need` nodes are invisible to `need_queries.py:33`, which matches
`(:Character)-[:HAS_NEED]->(:Need)`. Fix: read the declared `node_type` first, fall back to
`BASE_NODE_LABELS`, then to the key. Scope note: the `need` nodes also carry a `character_id`
property where the reader expects a `HAS_NEED` edge, so the label fix alone does not restore
`npc.top_need` — that half stays ISSUE-210 and is not this task.
RED anchor: a contract test asserting every `base_nodes/*.yaml` `node_type` round-trips through
`resolve_node_label`. Today the 27 kinds absent from `BASE_NODE_LABELS` fail it.
Ordering: this mutates the checked-in eval baseline, so it must land before M4's regeneration and
never between a generation and its comparison. ISSUE-213.
✅ DONE (462908a8, 2026-09-04). **Implemented with a departure from the spec above:** the
prescribed precedence (declared `node_type` first) resolves `character` to whatever
`character.yaml` declares, which is lowercase for 20 of the 34 kinds and 404s every eval case at
`evals/runner.py:97`. `BASE_NODE_LABELS` stays FIRST, and the registry gained a separate `label:`
field so `node_type:` is the snake_case key and `label:` the Cypher label — one concept per
field. See DEC-258.

- [x] **M1.3** Wipe, reseed, and prove the eval world is quiescent
Files: a new quiescence test under `tests/integration/`, `evals/fixtures/eval_world_baseline.json`
Spec: only after M1.1 and M1.2 — a wipe before the leak is fixed refills within a day, and a wipe
before the label fix re-seeds the same split labels. Reseed from `demo_game/seeds/seed.py` plus
`seeds/worlds/seed_tavern_world.py` and `seeds/worlds/seed_village_world.py`, then snapshot
through the existing `make eval-world-snapshot`. Add the test ISSUE-221 asks for:
`get_rag_scope_ids_for_npc` returns the same scope across two reads with no intervening write.
ISSUE-221's open question — "whatever writes Quest nodes while the app idles" — is answered by
ISSUE-273, so it closes here as a duplicate once the test passes.
RED anchor: measure `captain_sorn`'s 1-hop scope twice, minutes apart, against the current
database. It grows (30 -> 49 -> 52 -> 54 when last measured). After the reseed it must not move.
Validation: a live label census shows no lowercase duplicates, and the total node count is under
1,000. ISSUE-221.
✅ DONE (2026-09-04). Corpus 27,620 → **250 nodes**, all PascalCase, no lowercase duplicates;
`Quest` 23,375 → 17, `TickLease` 3,566 → 0. `captain_sorn`'s scope held at **18 ids across 5
observed ticks with the app ticking**, against the 30 → 49 → 52 → 54 recorded above. The new
fixture is byte-for-byte the same shape as the old one — 250 nodes, 236 relationships, identical
per-kind counts — differing only in the four labels M1.2 corrected. ISSUE-221 closes as a
duplicate of ISSUE-273. Two findings came out of it: the corpus still grows ~2,500 nodes/hour
while the app ticks (ISSUE-279), now excluded from measurement runs by `make app-frozen` +
`make check-corpus-frozen` (DEC-259), and compose silently un-publishes bolt (ISSUE-280).

### Phase M2

The four dimensions that do not exist. Extend the trend row; build no new subsystem.
`evals/trend_row_builder.py` and `evals/trend_store.py` already carry `guard`, `capability`,
`scorer_kappas`, `panel_kappa`, `retrieval_profile`, `prompt_token_budget` and
`mean_precision_at_k` — a new dimension is one more field on a row that is already written,
stored, trended and reported.

**Validation in this phase is unit-only, and deliberately so.** The loop brings up `neo4j` alone
(`scripts/loop_compat.sh:166`), and the `app` service in `docker-compose.yml:73` declares no bind
mount, so it serves the image baked at build time — never the code M1 and M2 write during a
night. "A generation run writes the new field" is therefore a check the loop cannot honestly
perform: it would pass against yesterday's image or fail for reasons that have nothing to do with
the task. Every M2 task is proven instead against fake turn records, in-process, with no model and
no database. The end-to-end confirmation is M4.1, which is human-driven and follows a deliberate
`docker compose build app`.

- [ ] **M2.1** Per-turn latency and token cost as trend fields
Files: new `evals/perf_records.py`, `evals/trend_row_builder.py`, `evals/trend_store.py`,
`evals/runner.py`
Spec: no per-turn timing or token accounting exists anywhere in the repo. `scripts/bench_nfr.py`
measures only gossip throughput and graph size, and honestly reports the other targets as not
measured. Add a Pydantic record capturing wall-clock duration and prompt/completion token counts
around the turn the runner already makes, aggregate to p50 and p95 latency and mean tokens in and
out, and surface them as new fields on the trend row. Keep the new module under 150 lines and add
no new report path — the existing summary and dashboard already read the trend row.
RED anchor: a unit test under `tests/unit/evals/` that constructs a handful of fake turn records
with known durations and token counts, builds a trend row from them, and asserts the row carries
p50 latency, p95 latency and mean tokens-in/out. It fails at import today — `evals/perf_records.py`
does not exist and `grep -c p95 evals/trend_row_builder.py` returns 0.
Validation: that same unit test, green, with the aggregates checked against hand-computed values
rather than against whatever the code produces. No process is started and no run is generated;
see the phase note above for why, and M4.1 for where the end-to-end proof happens.

- [ ] **M2.2** Record realised per-turn context size against its declared budget
Files: `evals/perf_records.py`, `evals/trend_row_builder.py`
Spec: `prompt_token_budget` is recorded per trend row, but nothing records what a turn actually
spent, so the budget cannot be shown to bind. Record realised per-turn context size alongside the
declared budget and surface mean and max. Related but NOT this task:
`session_turns_budget_tokens` is enforced only by a function nothing calls (ISSUE-225) — record
the number here, do not change the enforcement.
RED anchor: a unit test asserting a trend row built from fake turn records carries a realised
context-size field alongside the declared `prompt_token_budget`. Fails today — the field does not
exist.
Validation: the same test, green, fed two fixtures — one whose realised sizes sit under the
declared budget and one that straddles it — asserting the mean and the max are reported as given
and that the overshoot is visible in the row rather than clamped or absorbed. Whether a real run
overshoots is a question for M4.1; this task only has to make the answer readable.

- [ ] **M2.3** Drive the long-horizon sequence machinery with three cases
Files: three new sequence cases under `evals/cases/`, and `evals/sequence_runner.py` if the
wiring proves incomplete
Spec: `sequence_fidelity.py`, `sequence_order_effect.py`, `sequence_reset.py`,
`sequence_rates.py` and `sequence_runner.py` all ship, and nothing drives them — there is no
multi-turn case in `evals/cases/`. Author exactly three, one each against `memory`, `gossip` and
`relationship`, which are the dialogue-observable engines with seeded, per-NPC, addressable
content (`docs/ENGINE_EVAL_COVERAGE.md`). Follow `docs/SEQUENCE_SCHEMA.md`. Three is the v1: do
not author a full set before the first three produce a number worth trusting.
RED anchor: a unit test that loads every sequence case in `evals/cases/`, asserts there are three
and that they name three distinct engines, and drives `evals/sequence_runner.py` across each with
a stub client replaying canned per-turn responses. It fails today at the count: `make eval-sequence`
has no cases to run.
Validation: that test green — the three cases parse against `docs/SEQUENCE_SCHEMA.md`, and each
produces a fidelity rate from the canned responses, with one fixture built to score below 1.0 so
the rate is shown to vary rather than merely to compute. Real models come in at M4.1.

<!-- LOOP:QUEUE end -->

## Outside the queue

These need a human, or must not run unattended.

### R6 — Overnight loop rework

**Excluded from the queue on principle:** these edit `expand_loop.sh` and `loop_gates.py`, which
are the driver executing the queue. A loop rewriting its own driver mid-run produces a night that
cannot be diagnosed. Run these with the loop stopped. Do R6 before M3 and M4 — the point of
fixing the loop is to have it grind M1 and M2 overnight while the days go to M3 and M4.

- [ ] R6.1 Document stale-lock recovery — the runaway half of ISSUE-126 is already fixed, and the
      roadmap said otherwise until 2026-09-03 · CR-L11-09
      **The no-progress guard exists (DEC-235). Do not delete it and do not write a second one.**
      `scripts/expand_loop.sh:648` compares each iteration's task id against `LAST_TASK_ID` and
      halts once `SAME_TASK_REPEATS` reaches `MAX_SAME_TASK_REPEATS` (default 2, set at `:103`),
      flagging the human before breaking the loop. Measured 2026-09-03: an unbounded
      `bash scripts/expand_loop.sh --dry-run` terminated on its own after 6.5 minutes with exit 0,
      logging `HALT: M1.1 repeated 2 times without advancing the cursor`. The RED anchor this task
      used to carry — "`--dry-run` terminates; today it must be killed" — is green and has been
      for some time.
      What remains is the half ISSUE-126 also asks for and nobody did: killing a loop leaves the
      `mkdir`-based lock directory `project-harness/.loop-state/loop.lock/` behind, so the next
      run aborts with `FATAL: another loop holds …`. Recovery is
      `rm -rf project-harness/.loop-state/loop.lock`, and it is documented nowhere — not in the
      script's usage block, not in `project-harness/OVERNIGHT_LOOP.md`. Write it into both.
      Note that the guard makes the stale lock *more* likely to be met, not less: a halt is now
      the normal end of a stalled night, so the next operator meets the lock rather than the spin.
      RED anchor: `grep -rn "loop-state/loop.lock" scripts/expand_loop.sh
      project-harness/OVERNIGHT_LOOP.md` surfaces no recovery instruction today.

- [ ] R6.2 Classify HALT causes so a self-test failure is not a product HALT — every HALT to date
      was the harness tripping over its own self-tests · CR-L11-03
      `scripts/loop_gates.py` already splits HALT-class (behaviour) from AUTOFIX-class (form) and
      re-runs a failing gate's constituents individually to decide. Extend that existing
      classification with a third bucket — harness-self-test failure — routed to skip-and-log
      rather than halting the night. One more branch in a structure that already exists; no new
      mechanism.
      RED anchor: force a failure in `tests/unit/scripts/` and confirm the loop HALTs today.

- [ ] R6.3 Run the loop in a dedicated git worktree · ISSUE-139
      The loop stages the whole working tree, so a concurrent interactive session's edits are
      absorbed into whatever roadmap commit the loop happens to be writing. Observed: an
      interactive fix to `evals/eval_records.py` and its tests landed inside
      `24f6a01 feat(evals): capability_rate as first-class metric`, and were tagged
      `[UNVERIFIED: regression]` by a loop that never gated them. A worktree is strictly better
      than teaching the commit step to stage explicit paths: it is a launch-time change rather
      than a change to the commit transaction, it makes collision structurally impossible rather
      than filtered, and the repo already works this way (`/fix-parallel`, `NPCSystem-r5`). Add a
      preflight that refuses to start in the primary checkout.
      RED anchor: dirty an unrelated file, run one task, and confirm it lands in the loop's commit
      today.

### M3 — Re-author the guard battery

Must precede M4. Re-authoring changes what is generated **and** what is labelled, so doing it
after the regeneration burns the entire relabel.

- [x] M3.1 Write the discrimination rule as a DECISIONS entry, then into `docs/CASE_SET_POLICY.md`
      ISSUE-257 blocks on exactly this and says so: the rule must be stated before any case is
      rewritten, or 37 cases get 37 inconsistent rules. The rule, decided 2026-09-03: a guard
      case asserts **two** things. The negative half forbids **disclosure predicates**, never
      topic nouns — so "I can't tell you who runs the guild" passes while "the guild is run by
      Lira" fails. The positive half requires a **case-specific commitment a hedge cannot
      supply** — what the NPC does know, or who to ask. Both halves are needed: a topic-noun
      list false-fires on a correct refusal (`case_neg_lira_no_trust_disclosure` forbids
      "stolen goods", so "I don't deal in stolen goods" fails for refusing correctly), and a
      predicate list alone is beaten by a fluent hedge.

- [ ] M3.2 Retire `refusal_judge` — **HALTED 2026-09-03 on a false premise, see ISSUE-276**
      It is a zombie: `evals/matchers.py` dispatches `schema`, `min_length`,
      `keyword_any/all/none`, `in_set`, `range`, `substring`, `regex`, `tone_judge`,
      `affirms_judge` and `context_block_expected` — there is **no `refusal_judge` branch, and
      no case file uses it**. Its kappa of 0.247 measures a scorer that never scores anything,
      and all 75 of its calibration labels are orphaned. ISSUE-238 already records the verdict
      in writing: do not use it. Delete `prompts/eval/refusal_judge.yaml` and its harness
      references. Closes ISSUE-141 — do NOT attempt a third rubric rewrite; two have failed.

- [x] M3.3 Re-author the 37 guard cases against the rule
      Template for the negative half is `evals/cases/case_adv_old_henryk_guild_secrets.yaml`,
      which already does it correctly — it forbids "the guild is run by", "it's led by" and
      "their hideout is", and deliberately does not forbid "guild". For the positive half add an
      `affirms_judge` criterion restating each case's own `description` as a rubric; this is
      ISSUE-238's stated fix, `affirms_judge` is dispatched at `matchers.py:197`, and it carries
      real variance (0.941), so the assertion can actually fail. Inherited caveat: `affirms_judge`
      kappa is 0.530, which is RESTRICTED under `docs/SCORER_TRUST_POLICY.md` — a measurable
      instrument, not yet a trusted one.
      Acceptance: `python scripts/hedge_responder_probe.py --battery adversarial` drops the null
      rate from **1.0 to below 0.30**, then re-record `evals/null_baseline.json`.
      Closes ISSUE-238 and ISSUE-257.

- [ ] M3.4 Expand the case set, weighted to the hard tail
      Authoring judgment, so it sits outside the fence. The constraint that makes volume worth
      paying for is DEC-257: surviving base rates are 0.941 and 0.968, and at that ceiling kappa
      collapses arithmetically, so **a larger case set that is not a harder one is a worse case
      set**. Target ~1/3 of new cases expected to fail, and record each case's expected
      difficulty in its `notes:`.
      Author against the SEED FILES as source of truth — `demo_game/seeds/seed.py` (plus
      `seed_npc_data.py`), `seeds/worlds/seed_tavern_world.py`, `seeds/worlds/seed_village_world.py`
      — never against the live database, which is ~97% leaked Quest nodes until M1.1 lands.
      Priorities, in order:
      1. **The 30 never-generated capability cases.** Verified 2026-09-03: all 46 `case_pos_*`
         exist as YAML, 16 appear in `k3_77688e7_regen1`, 30 have never been generated. All 30
         are **reachable** — `bren_smith` and `garrick_deserter` resolve through
         `demo_game/seeds/seed_npc_data.py`, which `seed.py` imports. The gap is generation
         configuration, not authoring: 24 of the 30 are `tavern`/`village` world cases and that
         run seeded only `demo` (15 demo + 1 village generated). Six demo-world cases were
         skipped for a separate reason still to be established. **M4.1 must seed all three
         worlds** or it will repeat the omission.
      2. **The 3 long-horizon sequence cases (M2.3) already exist — do not author duplicates.**
         Verified 2026-09-03. A sequence scenario is a Python `ScenarioFn = Callable[[], bool]`,
         not a YAML case; there is no scenario file format and no scenario directory. Six are
         promoted in `evals/scenario_adapters{,_extra}.py`, and three of them are exactly the
         three this priority asks for: `gossip_chain` (gossip), `grief_persistence` (memory) and
         `reputation_drift` (relationship). The other three are `memory_consolidation`,
         `time_passage` and `mood_contagion`.
         M2.3's premise that "nothing drives them" is also wrong: `make eval-sequence [K=3]`
         (Makefile:633) runs all six live through `python -m evals sequence`. What is actually
         missing is that the target needs running services, is not in `make check`, and has never
         been recorded into the trend. **The remaining work is to run it and record it, not to
         write cases.**
      3. **New cases across every `dialogue_observable` engine with seeded, addressable content.**
         `docs/ENGINE_EVAL_COVERAGE.md` names them: `events`, `gossip`, `memory`,
         `knowledge_learning`, `deception`, `planning`, `reputation` and `dialogue`. The other
         ten dialogue-observable engines carry no per-NPC seeded fact, so a case against them
         measures the prompt rather than the engine.

### M4 — Regenerate, relabel, recalibrate

Nothing is built here; the pipeline already exists end to end and is run:
`eval-generate` -> `eval-deterministic-verdicts` -> `eval-judge ARGS=--panel` -> `label-export`
-> `eval-adjudicate` -> `label-import` -> `eval-calibrate` -> `eval-compare`.

- [ ] M4.1 Fresh generation across all 90 cases on the clean, frozen corpus, with M2's perf
      fields captured. Record model digests — the current baseline records nulls, which is why
      the trend re-decision can never unblock (ISSUE-246).

- [ ] M4.2 Full relabel, adversarial-weighted. Surviving base rates are 0.941 and 0.968; at that
      ceiling kappa collapses arithmetically, so **adding easy cases makes the numbers worse**.
      Weight adjudication toward the hard tail. Priority order: the 44 unlabelled `case_pos_*`
      capability cases (capability is the product claim and sits at n=16 with a 43-point CI),
      then re-ground `anti_hallucination_grounded`, of whose 48 labels zero survive.

- [ ] M4.3 Recalibrate and re-baseline. Run `make eval-calibrate`, refresh
      `evals/trend/trend_v1.jsonl`, and put every rate through
      `evals/scorer_trust_policy.py::check_publication` before it appears anywhere. Nothing below
      kappa 0.60 is quoted as a headline.

### R1 remainder — the counterfactual audit

- [ ] R1.7 DEC-224 is written; what remains is the audit it implies. For each `make check`
      target, confirm its commit references a recorded counterfactual, or the gate leaves. That
      is a judgment call per gate and was never in the loop's scope — it is the one item carried
      forward from the 2026-08 remediation programme.
      Files: `project-harness/DECISIONS.md`

### R7 — Deferred large work

- [ ] R7.1 Pydantic models at `BaseEngine.run_tick()` / `generate_structured()` · CR-L02-05
      **Re-measured 2026-09-03, not started.** "145 functions" reproduces only as a
      package-wide dict census (147 today) in which **72 are unrelated `graph/` query
      helpers**. True scope for the task as titled: **49 production functions** (3 protocols,
      28 `run_tick` implementors, 11 callers, 1 + 3 + 3 for `generate_structured`), or 67 with
      test doubles. The signature half is already done — R3.5 replaced `*args/**kwargs` with
      three keyword-only protocols — so what remains is purely return types. Still XL, but for
      the 194 test call sites and 28 disjoint return shapes, not for 145 functions.

- [ ] R7.2 Debt with no urgency: the four file splits behind R1.1, `config.py` fan-in 74,
      single-caller DIP port cull, `intent_queries.py` coverage, double mypy run, ruff rule set ·
      CR-L14-03 +9

### Parked

- [ ] B2B / Unreal integration track — **deliberately paused** (DEC-229) until engine work lands
      and smaller fine-tuned local models free the VRAM budget. See `UNREAL_DEFERRED.md`.
