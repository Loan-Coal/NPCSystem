# Overnight combined run — handoff

Finished: 2026-08-26 01:10:50
Total duration: 05:36:38
Commit under test: **77688e7**
New A/B arm: **k3_77688e7_regen1**
Full log: `c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\combined_20260825_193411.log`

## Results

| Step | Outcome |
|---|---|
| Phase 1 panel (k3_73e6c36) | kappa **0.5256456241033006**, agreement 0.9555555555555556, 194/210 cases (status gate_failed) |
| Regeneration #1 | wrote `c:\Users\lohan\Documents\hackathons\NPCSystem\evals\generations\k3_77688e7_regen1` |
| Label survival (post-regen) | see `c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\label_survival_postregen_20260825_193411.log` — expect 393 survive / 0 drift / 0 orphaned |
| Arm 1 panel (k3_77688e7_regen1) | kappa **0.5807453416149063**, agreement 0.9478260869565217, 186/210 cases (status gate_failed) |
| EVAL-P22.1 labelling order | exit 0 — see `c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\label_order_20260825_193411.log` |
| EVAL-P22.2 oracle dry-run | see `c:\Users\lohan\Documents\hackathons\NPCSystem\project-harness\overnight_logs\oracle_p22_2_20260825_193411.log` |
| EVAL-P22B.1 trend baseline | `evals/trend/trend_v1.jsonl` now holds **1** row(s); this arm's fleiss_kappa = **** |
| EVAL-P22B.2 false-positive check | **SETUP ERROR** — a precondition failed or no comparable baseline existed. Nothing was measured. |

## What to check, in order

1. **Phase 1 reproduction.** Compare its kappa against the re-derived baseline
   (kappa 0.526, agreement 0.956, 329/345). Judge sampling is non-deterministic and
   qwen2.5:14b flipped on 9/115 records across repeats, so expect small drift, not an exact
   match. A kappa well inside [0.227, 0.730] is a pass; a large move is itself a finding.
2. **Label survival.** If anything drifted or was orphaned, a case was renamed or removed —
   that is the only mechanism that can orphan a label under DEC-181's criteria-only policy.
3. **Oracle kappas.** Confirm the five values match DEC-185's closed forms: refusal_judge=0.247,
   tone_judge=0.241, affirms_judge=0.106, keyword_any=0.146, anti_hallucination_grounded=0.232.
   This closes HUMAN GATE H9. The script does not judge this for you.
4. **Coverage gaps.** Read `c:\Users\lohan\Documents\hackathons\NPCSystem\evals\calibration\label_order_k3_77688e7_regen1.coverage_gaps.txt` — every scorer listed there has
   zero rows of one verdict and cannot have that class measured however much you label.

## What you now have that you did not before

`k3_77688e7_regen1` is your **first valid A/B arm**: seeded, `harness_version`-stamped, generated after
the ISSUE-165 tick unification, and panel-judged. `k3_73e6c36` cannot serve this role — its
`harness_version` and `seed` are both null, so `compare.py` refuses it against any modern
run (ISSUE-186). Its value is as a labelled calibration corpus, not a baseline.

To A/B an engine change from here: change engine/agent/context code (which does NOT alter
`harness_version` — that hashes cases, judge prompts and matchers.py), regenerate to a new
gen_id, panel-judge it, then:

```
python -m evals compare evals\generations\k3_77688e7_regen1 evals\generations\<new_arm>
```

Keep the instrument identical between arms. `compare.py` now refuses a panel-vs-single-judge
pairing (ISSUE-185, fixed 2026-08-18), but it cannot protect you from a roster change you make
deliberately.

## Not run, by design

- **EVAL-P22.3 (Opus pre-labelling)** — a paid, human-run session using
  `evals/calibration/OPUS_LABEL_PROMPT.md`, deliberately outside any automated pipeline.
- Nothing wrote to `evals/calibration/labels_v1.jsonl`. Every labelling step above is
  read-only or writes to the oracle-only path.

## Tick these by hand after reviewing

`EVAL-P20.4`, `EVAL-P22.1`, `EVAL-P22.2`, `EVAL-P22B.1` in ROADMAP.md, naming this gen_id.
Tick `EVAL-P22B.2` **only if the false-positive check above exited 0** — an exit 1 means the
gate's threshold is wrong, and an exit 3 means the instrument moved; neither is a passed no-op check.
`EVAL-P21.1`/`P21.2` remain blocked on ISSUE-183 (their named acceptance clauses were never
exercised by a live run) — that is a wording call, not a re-run.

## EVAL-P22B.3 — the dependency re-point (do this LAST, and only after a green step 10)

Editing `EVAL-P23`'s `Depends on:` line before step 10 has actually passed would assert a
prerequisite that is not yet true, which is exactly the flag EVAL-P22B.3 carries. When it is green:

1. In `EVAL-P23`'s **Depends on:** line, replace `EVAL-P22.4` with `EVAL-P22B.2`.
2. Record in `EVAL-P23`'s Notes that the trend baseline is regeneration #1, not #2 — the
   publication track can re-baseline onto regeneration #2 later without invalidating any engine
   comparison made in between, because `harness_version` comparability governs, not run recency.
3. Drop `EVAL-P23.1`/`.2`/`.3` from `HUMAN GATE H10`'s **Blocks:** list.

Effect: `EVAL-P23` no longer transitively depends on an Opus spend, and engine iteration is
unblocked independently of the publication-credibility track.
