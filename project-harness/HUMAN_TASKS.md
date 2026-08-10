# HUMAN_TASKS — the work the overnight loop cannot do

**Written:** 2026-08-10, during the EVAL-P15 pre-flight review.
**Audience:** you, at the keyboard, with the stack up.
**Scope:** every open roadmap task that is flagged `(live` or `⏸️` and therefore skipped by
`compute_next`, ordered by when you can actually do it.

> **Why this file exists.** Every task in EVAL-P0..P14 that a machine could build *is* built.
> Every task that needed a human is still open. That is not a coincidence — it is the shape of the
> failure. `make check` is green, 3025 tests pass, and the harness has never produced a number it can
> defend. This file is the list that closes that gap.

**The one rule:** the ROADMAP task is the source of truth for *what*. This file is the source of
truth for *when* and *how*. If they disagree, the ROADMAP wins on content and you should fix this file.

---

## Status board

| # | Task | When it unblocks | Your time | Blocks |
|---|---|---|---|---|
| **0** | Release the loop | **now** | 10 min | everything |
| **1** | `EVAL-P12.1` — reset fidelity | **now** (independent of the loop) | ~45 min | P12.4, P14.3, ISSUE-143 |
| **2** | `EVAL-P17.5` — re-measure and retract | after loop ticks **P17.4** | ~30 min | P13.3, fence reopen |
| **3** | `EVAL-P15.1` — oracle labeller | after loop ticks **P15.2** | ~75 min | P19.4, P22.2, P22.3 |
| **4** | `EVAL-P19.4` — re-judge, merge, re-measure κ | after loop ticks **P19.1** + task 3 | ~90 min | publication of any guard rate |
| **5** | `EVAL-P20.2` — capability cases | any time after task 0 | 2–3 h (of ~4–5 h) | a non-gameable headline |
| — | **Week-2 boundary** — everything below needs the fence reopened | | | |
| 6 | `EVAL-P20.0` — deterministic seed | after tasks 2 + 4 | ~60 min | **every** regeneration |
| 7 | `EVAL-P12.4` — measured multi-turn | after task 1 | budget from P12.1 | P13.2, P14.3 |
| 8 | `EVAL-P20.1` — case-set contradictions | after loop ticks P19.3 | ~60 min | regen #1 |
| 9 | `EVAL-P20.4` — regeneration #1 | after tasks 5, 6, 8 | ~85 min + 2.5 h judge | P21, P22 |
| 10 | `EVAL-P21.1`, `P21.3` — panel + settle the judge | after task 9 | ~90 min | P22.4 |
| 11 | `EVAL-P22.2` → `P22.3` → `P22.4` | after task 10 | ~3 h + Opus credits | P23, P24 |
| 12 | `EVAL-P24.3`, `EVAL-P8.3` | last | ~60 min | README |

**This week's budget (4–6 h stated):** tasks 0–4 total **~4 h**. Task 5 is the overflow —
take it as far as it goes and use the ratchet (see task 5).

---

## Task 0 — Release the loop *(10 min, do this first)*

The pre-flight is done: the stdlib shadowing is gone (DEC-162), the fence is narrowed to
EVAL-P0..P19 (DEC-163), ISSUE-142 is archived, and three stale roadmap facts are corrected.
`make check` is green and `roadmap_cursor.py --next` reports `EVAL-P15 / EVAL-P15.2`.

```bash
git status --porcelain          # MUST be empty — ISSUE-139 is still open, the loop
                                # stages the whole tree and will sweep your edits into its commit
git checkout -b auto/roadmap-night
bash scripts/expand_loop.sh --max-tasks 1     # watch ONE task in the foreground first
```

Read what it did. Then widen:

```bash
bash scripts/expand_loop.sh --start-at 20:00 --stop-at 08:00
```

**Expect it to reach roughly EVAL-P17 on night 1 and EVAL-P19 by night 3** (~18 h of loop work
across P15.2–P19.3, 15 tasks).

**Abort if:** two consecutive red gates (`MAX_CONSECUTIVE_RED_GATES=2` halts it for you), or
`check-conservation` starts *passing* before EVAL-P17.1 lands — that would mean the detector is
broken, not that the pipeline is fixed. All four identities are supposed to fail at EVAL-P15.2.

---

## Task 1 — `EVAL-P12.1`: measure what `reset_world` actually clears *(~45 min, do now)*

**Why first:** it is independent of the loop, it unblocks the entire multi-turn track (your stated
differentiator), and it is the prerequisite for fixing **ISSUE-143** — `sequence_runner.py:160`
currently publishes a Wilson confidence interval over k repetitions with *no evidence whatsoever*
that those repetitions are independent. That is the programme's own headline error, sitting inside
the programme.

### Steps

1. **Bring the stack up and seed all three worlds.**
   ```bash
   docker-compose up -d
   make demo-seed
   make seed-village-world
   make seed-tavern-world
   ```
   Confirm the API answers before going further — a silently-down service is how this project has
   produced worthless artifacts before.

2. **Write `e2e/scripts/measure_reset_fidelity.py`.** It must:
   - snapshot the full graph + every in-process store the API exposes,
   - run a *mutating* scenario (gossip propagation is the obvious one — it writes `KNOWS_ABOUT`
     edges, emotion state and memory),
   - call `preconditions.reset_world`,
   - snapshot again and **diff**,
   - time the reset.

3. **Emit two artifacts, not one.**
   - `docs/RESET_FIDELITY.md` — the human-readable table, one row per surviving item with a verdict
     (`acceptable` / `correlates repeats`).
   - `evals/reset_fidelity.json` — **the machine-readable one, and the whole point of the
     strengthening.** Shape:
     ```json
     {"fidelity": "PARTIAL", "surviving": ["emotion_store", "..."],
      "reset_cost_ms": 1234, "measured_at": "...", "git_sha": "..."}
     ```
     Field names must match `ResetReceipt` in `evals/sequence_records.py` so the v2 schema
     (EVAL-P14.1) consumes it with no translation layer.

4. **Assign the tier from `docs/SEQUENCE_STATS_POLICY.md` §2.** `FULL` only if **nothing**
   survives. Anything else is `PARTIAL`. **There is no third tier** and the policy says so
   explicitly — "mostly full" is how a correlated run acquires an interval it has not earned.

### The part that matters

**PARTIAL is the expected answer, and reporting it is a success, not a failure of this task.**
It costs EVAL-P12.4 its confidence intervals and promotes the order-effect check
(Cochran's Q across repetition indices; first-vs-last McNemar — SEQUENCE_STATS_POLICY §4) to the
primary statistic. A tier chosen because it keeps a metric alive is the single worst outcome
available here, and it would be invisible to every gate in the repo.

**Record the measured per-reset cost.** EVAL-P12.4's wall-clock budget is
`6 scenarios × k × (turns + reset_cost)` and it is computed from this number.

---

## Task 2 — `EVAL-P17.5`: re-measure and retract *(~30 min; after the loop ticks P17.4)*

**Wait for:** `EVAL-P17.1`–`P17.4` ticked in ROADMAP.md. Check with
`python scripts/roadmap_cursor.py --next`.

**No regeneration. This is arithmetic over data already on disk.**

### Steps, in this order — the order is the whole discipline

1. **Write the expected numbers into `ISSUES.md` BEFORE you run anything.** The roadmap's honest
   post-fix expectation is **~18 failures across ~234 case-repetitions** (78 guard cases × k=3),
   superseding the audit's `≥10 across ≥186` floor, which was itself computed from `judged.jsonl`
   alone. Write that down first, with your reasoning.

2. Re-run `summarize` + `report` over the **unchanged** `evals/generations/k3_73e6c36` artifact.

3. **Record met / not-met as a binary.** The roadmap is explicit that *"either met or explained"* is
   an escape hatch, not a gate. If the count differs from your written prediction, the phase does
   **not** tick until the difference is traced to a **named** `case_id` or a named line of code.

4. Record the corrected headline next to the retracted `3 lore hallucinations across 111 adversarial
   turns` in the ROADMAP Session Log, and explain the delta line by line: battery reclassification
   (+41 `ah_demo_*` cases), both-source aggregation (+192 slots), infra-vs-content separation, skips.

5. Treat **every prior quotation of `3 across 111` as retracted.** Grep for it before you finish:
   ```bash
   grep -rn "across 111" README.md docs/ project-harness/
   ```

---

## Task 3 — `EVAL-P15.1`: the oracle labeller *(~75 min; after the loop ticks P15.2)*

**Why a human does this:** it writes label-shaped artifacts, and `label-import`'s `--out`
**defaults to the real 393-row labels file**. A target that forgets the flag overwrites two rounds of
hand-labelling. `loop_gates.FROZEN_PATH_PREFIXES` covers `evals/calibration/`, which is why the loop
cannot do it and why you must be careful when you do.

### Steps

1. **Build the guard first, before the labeller.** In `label_import.py`, refuse any run whose
   `--model` matches `mock-*` / `oracle-*` while `--out` resolves to `calibration_records.LABELS_FILE`.
   Add the unit test asserting the oracle's output path can never equal it. Getting this order wrong
   is the only way this task can cost you something irreversible.

2. **Write `scripts/oracle_labeller.py`.** Unlike `scripts/mock_labeller.py` (random labels — proves
   data moves, proves nothing about arithmetic), the oracle labels by a **declared rule** with a
   **known-by-construction confusion matrix**, so the pipeline's κ is predictable in closed form.
   Mandatory paths: `--out-dir evals/calibration/oracle_batches`,
   `--out evals/calibration/oracle/labels_oracle.jsonl`.

3. **Compute per-cell caps and raise a named error when a request is unsatisfiable.** The requested
   matrix is bounded by the rows that exist. Measured `scorer_verdict=False` counts:
   `affirms_judge` 3, `refusal_judge` 7, `tone_judge` 6, `anti_hallucination_grounded` 8,
   `keyword_any` 3, and **0** for the other five matchers. The naive example (tp=40, fp=5, fn=3,
   tn=12) needs 15 negatives and **is unsatisfiable for every scorer**. Use a satisfiable one, e.g.
   `refusal_judge` tp=60, fp=8, fn=4, tn=3.

4. **Hardcode the expected κ as a decimal literal in the test, with the arithmetic in a comment.**
   The test file must import **nothing** from `evals/calibration*` — otherwise it validates the
   broken function against itself. (`_kappa_from_matrix(60,0,0,0)` returns **1.0** today; verified
   2026-08-10. EVAL-P16.3 fixes that, and this test must not depend on whether it has.)

**Validation:** `label-import --merge` → `calibrate` reports **exactly** the requested counts and a κ
equal to your hand-computed value to 3 dp.

---

## Task 4 — `EVAL-P19.4`: re-judge, merge, re-measure κ *(~90 min; the highest-value hour on the board)*

**Wait for:** loop has ticked `EVAL-P19.0`, `P19.0b`, `P19.1`. Task 3 done.

**Why this is the best hour you have:** `refusal_judge` κ = **0.247, 95% CI [−0.068, 0.541], n=75** —
the interval crosses zero, i.e. statistically indistinguishable from chance. It is the scorer that
produces your anti-hallucination headline, and its 8 false positives assert invented entities
("House of Ravenwood", "Lady Elara", "young Elian") that exist nowhere in seed data. It is scoring
hallucinations as clean refusals. **Until this is fixed no guard rate is publishable under any trust
policy.** And because the transcript text does not change, **all 393 human labels survive whole —
this costs zero relabelling.**

### Steps

1. **Back up first**, even though `--merge` is non-destructive by design and the labels are now
   git-tracked (ISSUE-142 archived):
   ```bash
   git status --porcelain evals/calibration/     # must be clean, so a bad merge is one checkout away
   ```

2. **Re-run the judge pass over the unchanged transcript** with the fixed criteria:
   ```bash
   export JUDGE_MODEL=mixtral:8x7b
   export JUDGE_TIMEOUT_SECONDS=300        # the 30 s default times out under load
   GEN=evals/generations/k3_73e6c36
   make eval-judge TRANSCRIPT=$GEN/outputs.jsonl GEN_ID=k3_73e6c36
   ```

3. **Merge — `MERGE=1` is not optional.** Without it, `label-import` targets the real labels file
   and refuses (correctly); with `--force-overwrite` it would destroy the human verdicts.
   ```bash
   make label-import RAW=evals/calibration/raw_labels.jsonl \
                     TRANSCRIPT=$GEN/outputs.jsonl \
                     JUDGED="$GEN/judged.jsonl $GEN/deterministic_judged.jsonl" \
                     MERGE=1
   make eval-calibrate
   ```

4. **Check the three validations.**
   - `human verdicts preserved: 393`. ⚠️ Note the roadmap's own warning: `format_merge_report` prints
     this field by **key match regardless of drift**, so it reads 393 by construction. It is
     necessary, not sufficient — that is exactly why EVAL-P19.0 makes `needs_review` load-bearing.
   - The rows whose criteria changed are flagged `needs_review` **and named**.
   - `refusal_judge` κ is re-reported with its cluster-corrected CI.

### The branch that matters

**If κ clears the EVAL-P11.1 threshold:** ISSUE-141 closes. Record the before/after with both
intervals and n.

**If it does not:** the scorer is recorded as **unfixed** and its rate is **refused publication** —
never quietly kept. And per EVAL-P19.1, if the replay gate fails (the 8 FPs not fixed, *or* any of
the 63 currently-concordant rows broken), **the rewrite is reverted**. A rewrite that fixes 12 rows
and breaks 15 must fail, and the ≥10-of-12 figure is a diagnostic, not the gate — those 12 rows were
read in order to write the fix, so scoring the fix on them is fitting and testing on the same points.

---

## Task 5 — `EVAL-P20.2`: capability cases *(2–3 h of ~4–5 h; the overflow task)*

**Why it cannot be automated:** only a human can say what an NPC *should* say. And the current
capability battery is **7 cases**, of which a single canned hedge string passes **6** — alongside
**37/37** guard cases. A headline built on that is gameable by a responder that knows nothing.

### Steps

1. Generate the mechanical 80%:
   ```bash
   make draft-cases                       # requires the seeded stack; writes evals/cases/_drafts/
   ```

2. Review and promote. Target the 9 grounded NPCs with no case: `bren_smith`, `dorn_dockmaster`,
   `garrick_deserter`, `harwick_guard`, `nel_pickpocket`, `nessa_priestess`, `sera_barmaid`,
   `tilda_herbalist`, `vex_spymaster`.

3. **Every new case must fail an echo of its own prompt.** The gameability defect exists because
   `keyword_any` lists are drawn from the same vocabulary as the player prompt —
   `case_pos_aldric_trade_disruption` asks about *war* and *trade*, forbids nothing, and so passes on
   an echo.

4. **Add a `relevant_node_ids` annotation to every new case**, so the EVAL-P4.2 retrieval cross-tab
   stops covering only guard cases (currently 15 annotated of 53).

5. **Shrink `UNCOVERED_BASELINE` in the same commit** that adds each case.
   `test_uncovered_baseline_has_no_stale_entries` fails if you forget — that is deliberate, so the
   work-list cannot rot into a permanent excuse.

### Ratchet — read this before you start

⚠️ **`test_capability_coverage.py` passes today and tells you nothing.** DEC-161 converted it to a
ratchet against a hardcoded 9-NPC `UNCOVERED_BASELINE` precisely so a gate the loop could not turn
green would stop halting the phase. "The test passes" would be satisfied by changing nothing.

**The real gate is validation (2): a scripted always-hedge responder must score < 0.30 capability
(currently 0.857).** That is the one a ratchet cannot fake.

**You may tick this task at ≥ 9 authored cases** (capability n: 7 → 16), provided the always-hedge
gate and the `relevant_node_ids` requirement hold for the authored set, with the remainder tracked as
an ISSUE naming the ~35 target. A 4–5 h block that must complete in one sitting or count for nothing
is the shape of task that never gets started. **Record the achieved count by number.**

---

## Week 2 — after the fence reopens

The `LOOP:QUEUE end` marker now sits above `### Phase EVAL-P20` (DEC-163). Move it back down to
below `EVAL-P24.3` only when **all three** reopen conditions hold — checked by you, not inferred
from a green suite:

1. **`EVAL-P17.6` green** — `make check-conservation` exits 0 with all four identities satisfied.
   This is EVAL-P17's real exit criterion, not the headline number.
2. **`EVAL-P17.5` ticked** — corrected headline recorded next to the retracted one (task 2).
3. **`EVAL-P20.0` landed and its ≥95% seed-reproduction gate MET by measurement.**

Moving the marker requires a DECISIONS entry, and
`test_real_roadmap_fence_state_tripwire` will go red on the move — update `range(20)` deliberately.
That tripwire firing is it working.

### Task 6 — `EVAL-P20.0`: deterministic generation *(~60 min — do this before ANY regeneration)*

**The highest-leverage hour in Program 3, and the easiest to skip by accident.** Without a seed,
**~81% of the 393 labels are invalidated by every regeneration** — 190 of 307 record_ids already
produce 3 distinct texts across 3 repetitions, and an independent regeneration at `temperature=0.15`
with no seed is exactly such a draw. That is ~660 re-adjudications across the two budgeted
regenerations: more hand-labelling than this project has ever done, and precisely what the programme
exists to avoid.

The ask-gate is **already cleared by explicit human approval (2026-08-09)** — it changes
`LLMGenerateProtocol` and reverses the `seed`-absent half of DEC-146, and both are approved.

**Do not proceed on hope.** Ollama's `seed` does not guarantee bit-identical output across differing
quantisation or driver versions. Two generations of ≥20 records at the same seed must reproduce
**≥95%** byte-identical `npc_response`, and **you record the achieved rate as a number**. Below 95%,
the seed did not solve the problem: amend EVAL-P20.4's notes with the measured re-adjudication cost
in rows *before* the regeneration runs, and make EVAL-P22's labelling budget absorb it.

### Tasks 7–12

Each is specified in full in the ROADMAP; the sequencing constraints that are easy to get wrong:

- **`EVAL-P12.4`** needs task 1's `evals/reset_fidelity.json`. Its validation is now
  **fidelity-conditional** — under PARTIAL it must print the order-effect check *in place of* the
  interval, and a run that prints neither has reported nothing.
- **`EVAL-P20.1`** (case-set contradictions) must land in **one commit** with task 5, before regen #1.
  `case_neg_captain_sorn_no_hedging` fails hedging while `case_pos_mira_gossip_hedging` passes it on
  a prompt 0.71 similar — the battery currently scores hedging as both the failure mode and the
  success mode.
- **`EVAL-P21.0`** must seat an **out-of-family** third judge (`llama3.1:8b` or `gemma2:9b`).
  `qwen2.5:7b` is banned — it is the generation model in all five engines. And `qwen2.5:14b` +
  `qwen2.5:7b` are **not independent raters**: under 2-of-3 a same-family pair casts one vote with a
  veto. Panel runs **sequentially** — mixtral is ~27 GB and cannot co-reside on 8–12 GB VRAM.
- **`EVAL-P22.3`** (the Opus spend) is hard-gated behind `EVAL-P22.2` passing on the oracle labeller.
  No Opus run against an unproven chain — that is a locked decision, not a guideline.
- **`EVAL-P8.3`** must **not** run before `EVAL-P16.4`, `P17.1` and `P18.3`. Verified 2026-08-10:
  `compare` reads 115 of 307 slots, groups by expectation slot rather than case, and returns
  `NO_DETECTABLE_CHANGE p=1.0000` with **exit 0** over an empty intersection. Cheaper still: fold it
  into task 9's regeneration rather than spending a separate 62-minute generation.

---

## Standing hazards

- **ISSUE-139 is open.** The loop stages the whole working tree. Start it only from a clean tree,
  ideally in a dedicated worktree, or your interactive edits land in its commits.
- **`label-import --out` defaults to the real labels file.** Always pass `MERGE=1` after the first
  import. Never `--force-overwrite` on a file holding human verdicts.
- **The secondary calibration axis is tautological — two sittings, one rater.** Confirmed by you on
  2026-08-10: the 393 rows were labelled across **two sittings**, but the second **copied `pre_label`
  into `human_verdict`** rather than re-deciding it. So every scorer reports `pre_label vs
  human_verdict` κ = 1.000 at 100% agreement, which is the signature of a variable compared with
  itself. Three consequences:
  - The **headline** axis (`scorer_verdict vs human_verdict`) is **unaffected**. κ never compares a
    labeller to itself there. `refusal_judge` 0.247 and `tone_judge` 0.919 stand as measured.
  - There is currently **no inter-rater number at all.** Never quote the 1.000 as agreement. The
    README must say *"single rater"* — otherwise the calibration section becomes the weakest claim
    in the document rather than the strongest. `EVAL-P22.3` restores a genuine second axis by using
    Opus as a pre-labeller **distinct from** the adjudicator.
  - The effort was real and is exactly why `EVAL-P20.0`'s seed and the `--merge` durability work are
    non-negotiable. Two sittings of your time is not something to spend again.
  (The Program 3 header said "hand-labelled twice", which read as an independent second opinion —
  corrected in ROADMAP.md on 2026-08-10.)
