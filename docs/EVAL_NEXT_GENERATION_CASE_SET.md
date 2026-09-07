# Case set for the next generation run

**Status:** decision record for an unrun generation — no generation was executed to
produce this document; every number below is measured from the committed corpus and
`evals/calibration/labels_v1.jsonl` as they stand on 2026-09-04.
**Depends on:** DEC-260 (the 25-minority / 10-cluster adequacy floor, `evals/label_adequacy.py`),
DEC-261 (the `requires_world` guard now shared by both eval verbs — the reason this run is
safe to make at all).

## Why this document exists

The label set backing every calibrated scorer is ~94% positive (see the per-scorer table
below). DEC-260's adequacy floor refuses to calibrate a scorer whose minority-verdict class
falls below 25 labels or 10 case clusters — as of today, **every scorer currently labeled
is refused**. `case_neg` and `case_adv` are the only cases in the corpus authored to elicit
the minority verdict; this document is the case-set decision for the run that will attempt
to close that gap, checked in *before* that run happens.

## Current state (measured, `scripts/check_label_adequacy.py` against `labels_v1.jsonl`)

| Scorer | Minority label count | Case clusters | Floor | Verdict |
|---|---|---|---|---|
| `tone_judge` | 7 | 45 | 25 / 10 | REFUSED (minority count) |
| `affirms_judge` | 8 | 37 | 25 / 10 | REFUSED (minority count) |
| `refusal_judge` | 11 | 25 | 25 / 10 | REFUSED (minority count) — **out of scope, ISSUE-276** |
| `anti_hallucination_grounded` (deterministic substring scorer, not an LLM judge) | 8 | 16 | 25 / 10 | REFUSED (minority count) |
| `commits_judge` | 0 — **zero labels of any kind** | 0 | 25 / 10 | REFUSED (no data at all) |

`commits_judge` has never produced a single generated record: it was added to
`evals/matchers.py` on 2026-09-03 (`e6e9256c`, DEC-256), after the corpus's last and only
generation against a `commits_judge`-carrying case set (`k3_77688e7_regen1`, generated
2026-08-25 — confirmed by `grep -c commits_judge evals/generations/k3_77688e7_regen1/outputs.jsonl`
== 0). Re-judging that existing generation cannot produce `commits_judge` verdicts; a new
generation is required for this scorer specifically, not just a new judge pass.

## What `case_neg` + `case_adv` can contribute per judge

Counted directly from the 37 case files (`evals/cases/case_neg_*.yaml`,
`evals/cases/case_adv_*.yaml`; 24 + 13) by their `expected[].kind`:

| Judge kind | `case_neg`+`case_adv` expectations | Ceiling this adds to minority_n (k=1, before dedup) | Reaches 25 from here? |
|---|---|---|---|
| `commits_judge` | 37 (every one of the 37 cases) | up to 37 | **Plausible** — 37 > 25, but not guaranteed: needs the true minority side of the judged split to be ≥25 of ≤37. Not knowable without generating and labeling. |
| `affirms_judge` | 8 | up to 8 more (8 current + 8 = 16 best case) | **No.** 16 < 25 even if every one of the 8 new candidates lands on the minority side. |
| `tone_judge` | 0 | 0 | **No.** Zero `case_neg`/`case_adv` cases carry a `tone_judge` expectation at all; nothing in this corpus can move this number. |
| `refusal_judge` | 0 | 0 | **No** — and out of scope regardless (ISSUE-276). `refusal_judge` is driven entirely by the 25 `anti_hallucination_demo.json` refusal-category cases, all 25 of which already have at least one label (current clusters == 25 == total available); growing this needs new AH fixture cases or more repetitions of the existing 25, not `case_neg`/`case_adv`. |

**`tone_judge` and `affirms_judge` cannot clear the adequacy floor from the currently
authored `case_neg`/`case_adv` corpus, full stop — this is a case-authoring gap, not
something a generation run can fix.** Per the task constraint, the floor is not being
lowered and no new `case_pos` is being authored to compensate; the fix is new negative
cases carrying `tone_judge`/`affirms_judge` expectations, which is out of scope here and is
not being done in this pass.

## Decision: the case set

**Run `case_neg` (24) + `case_adv` (13) = 37 cases.** No `case_pos` case is part of this
set — case_pos cases carry no judge expectation capable of producing a minority-class
label (they are, by construction, the ~94% majority side), so including them would not
move any scorer toward its floor; the task also rules out authoring new ones. The AH
fixture (`anti_hallucination_demo.json`, 41 cases) is left out of this set too: all 41 were
already generated in `k3_77688e7_regen1` and neither `refusal_judge` (out of scope) nor
`anti_hallucination_grounded` gains new clusters from re-running them (25/16 already equal
the cases available).

All 37 target cases were already generated once, under the pre-`commits_judge` case
definitions (`never-generated case_neg/case_adv` == `[]`, measured against
`k3_77688e7_regen1/outputs.jsonl`) — this run is not new case-authoring, only a
re-generation of existing cases that now carry an expectation the last run never asked
for.

**Repetitions:** cluster count does not scale with `k` — repeating a case adds candidate
labels within its one cluster, not a new cluster — so `k` does not affect whether the
10-cluster floor is met (37 clusters clears it at `k=1` already). It does affect how many
distinct judged texts exist to label toward the 25-minority floor for `commits_judge`; the
prior run's `k=3` is a reasonable default to keep rather than a new value to invent here
(the operator decides the actual `k` at run time — this document fixes the case set, not
the run parameters).

## Expected outcome, stated honestly

Running this set and fully labeling its output gives `commits_judge` its first-ever data
and a real (not guaranteed) shot at clearing both floors. It does **not** unblock
`tone_judge`, `affirms_judge`, or `refusal_judge` — those stay refused after this run
exactly as they are today, because the corpus has nothing left in it that could move them.
Closing those three needs new case authorship, logged as follow-up rather than done here.

## Addendum, 2026-09-04: the `tone_judge`/`affirms_judge` conclusion above was wrong

**Corrected by DEC-262** (label-export stratification task), after this run actually happened
(`evals/generations/k3_61b01dad_negadv`, k=3). The "what `case_neg`+`case_adv` can contribute
per judge" table above counts each case's own authored `expected:` list only. It misses
`evals/guard_expectations.expected_with_guards`: every `case_neg_`/`case_adv_` case gets
`tone_judge` (`GUARD_TONE_RUBRIC`) auto-injected at generation time regardless of what its own
YAML declares, plus `affirms_judge` (`GUARD_LORE_RUBRIC`) for every `requires_world: demo` case
(all 37 here) — a mechanism this document's counting method never accounted for.

Measured directly against the real transcript: `tone_judge` 111 records across 37 clusters,
`affirms_judge` 132 across 37 (not 0 and 16 as claimed above). Both clear the 25-minority /
10-cluster ceiling in the best case, same as `commits_judge`. ISSUE-285 (which restated this
document's wrong conclusion) is closed with this correction — see `archive/ISSUES_RESOLVED.md`
and `project-harness/DECISIONS.md` DEC-262 for the full numbers and the label-export tooling
that now uses this document's declared case set
(`evals/calibration/case_strata.yaml`).

This does not retroactively validate the rest of the document: the case-set decision itself
(run `case_neg`+`case_adv`, k=3, no `case_pos`) was sound and is what actually got generated.
Only the per-judge reachability table's `tone_judge`/`affirms_judge` rows were wrong, and only
because of the missed injection mechanism above — the `refusal_judge` row's conclusion (out of
scope, ISSUE-276, no case in this set touches it) is unaffected and still correct.
