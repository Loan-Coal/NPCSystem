# HANDOFF — EVAL-P25.3 / P25.4 / P26.1 (Track A tooling)

**Written:** 2026-08-27, Track A session (parallel with Track B, which owns
`docs/ENGINE_EVAL_COVERAGE.md`, `docs/REASONING_DIMENSIONS.md`, `docs/CAPABILITY_CASES.md`
and new `evals/cases/*.yaml`).

This session deliberately did **not** touch `Makefile`, `ROADMAP.md`, `ISSUES.md` or
`DECISIONS.md` — both tracks would collide in them (`.PHONY` is a single continued line).
Everything that belongs in those four files is written out below, verbatim, for a serial
integration step to apply.

---

## 1. Files this session created

| Path | What it is |
|---|---|
| `scripts/check_base_rate.py` | EVAL-P25.3 gate: reader, `check_generation`, report, CLI |
| `scripts/base_rate_contract.py` | EVAL-P25.3 contract: the band, band arithmetic, Pydantic models |
| `tests/unit/scripts/test_check_base_rate.py` | 12 tests, RED anchor included |
| `evals/variance_scorer.py` | EVAL-P25.4 deterministic contextual-variance metric |
| `tests/unit/evals/test_variance_scorer.py` | 11 tests |
| `evals/case_adversary.py` | EVAL-P26.1 deterministic checks + batch/paste half |
| `evals/case_adversary_contract.py` | EVAL-P26.1 models, check vocabulary, contract constants |
| `prompts/eval/case_adversary.yaml` | EVAL-P26.1 judgment-pass prompt (no prompt strings in Python) |
| `tests/unit/evals/test_case_adversary.py` | 16 tests, RED anchor included |
| `docs/CASE_SET_POLICY.md` | **edited** — appended the base-rate contract and the P25.4 note |
| `project-harness/HANDOFF_TRACK_A.md` | this file |

Both `check_base_rate.py` and `case_adversary.py` were split into a `*_contract` sibling to
stay inside CLAUDE.md's 300-line limit; the public surface is re-exported, so the primary
module named in the plan remains the single import point.

Gates run directly (not wired into `make check` — that is integration's job):
`make lint` · `make check-rules` · `make check-evals-rules` · `make type-evals` ·
`make check-docstrings` — all clean. 39/39 new tests pass.

---

## 2. Makefile — targets to add

`.PHONY` line: add `check-base-rate variance-score review-cases`.

```make
# check-base-rate: EVAL-P25.3. Measure a generation's pass base rate against the
# [0.55, 0.85] target band in docs/CASE_SET_POLICY.md, grouped by matcher/judge kind.
# ADVISORY until EVAL-P26 lands the rebuilt case set: it reports the full breach list and
# exits 0. Switch ENFORCE to `blocking` in the same commit that lands EVAL-P26.2.
# Do NOT add to `make check` while ENFORCE=advisory — an always-green target in the gate
# list is noise; wire it in at the same moment it becomes blocking.
GEN ?= evals/generations/k3_77688e7_regen1
ENFORCE ?= advisory
check-base-rate:
	$(PYTHON) scripts/check_base_rate.py $(GEN) --enforce $(ENFORCE)

# review-cases: EVAL-P26.1. Deterministic adversarial review of candidate eval cases —
# tokens lifted from the case's own player_message, gameability against the echo and the
# reference hedge, and whether the declared grounding edge type is real. No LLM, no
# network. The judgment half (leading prompt / self-answering / insider vocabulary) is a
# batch/paste pass: see prompts/eval/case_adversary.yaml and section 6 below.
CASES ?= evals/cases
review-cases:
	$(PYTHON) -c "import sys, yaml, pathlib; sys.path[:0]=['evals','scripts']; \
	from case_adversary import review_case; \
	[sys.stdout.write(f'{r.case_id}: {[f.check.value for f in r.findings] or chr(10)}\n') \
	 for r in (review_case(yaml.safe_load(p.read_text(encoding='utf-8'))) \
	 for p in sorted(pathlib.Path('$(CASES)').glob('case_pos_*.yaml')))]"
```

> **Note for integration:** the `review-cases` recipe above is a stop-gap one-liner. If a
> CLI entry point is wanted, add `main()` to `evals/case_adversary.py` — it was left out
> deliberately this session because `evals/` is scanned by R002 (`no print()`), so any CLI
> there must write through `sys.stdout.write`, and adding one would have pushed the module
> back over the 300-line limit. A cleaner home is a `scripts/review_cases.py` wrapper.

`make variance-score` is intentionally **not** proposed. `evals/variance_scorer.py` is a
pure scoring library with no artifact to read: it becomes a make target in EVAL-P26.2, when
`case_var_*` cases exist to feed it.

---

## 3. ROADMAP checkboxes to tick

Under **Program 4**, phase **EVAL-P25**:

- [x] **EVAL-P25.3** — The base-rate contract, as a gate.
      `scripts/check_base_rate.py` + `scripts/base_rate_contract.py`,
      `tests/unit/scripts/test_check_base_rate.py`, `docs/CASE_SET_POLICY.md`.
      Band 0.55–0.85, advisory-with-report; switches to blocking with EVAL-P26.2.
- [x] **EVAL-P25.4** — Contextual-variance scorer. `evals/variance_scorer.py`,
      `tests/unit/evals/test_variance_scorer.py`. Deterministic, kappa 1.0 by construction.

Phase **EVAL-P26**:

- [x] **EVAL-P26.1** — The case adversary. `evals/case_adversary.py` +
      `evals/case_adversary_contract.py`, `prompts/eval/case_adversary.yaml`,
      `tests/unit/evals/test_case_adversary.py`. Deterministic checks land as code; the
      judgment checks land as a batch/paste prompt, mirroring the existing Opus workflow.
      **Makefile target not yet wired** — see section 2.

**Do not tick** EVAL-P25.1, EVAL-P25.2 (Track B), or EVAL-P26.2 / P26.3 (not started).

---

## 4. DECISIONS.md entries to add (full text)

### DEC-216: the base-rate gate ships advisory, and the switch to blocking is a dated parameter

**Date:** 2026-08-27
**Phase:** EVAL-P25.3
**Status:** Accepted

**Context.** The kappa paradox is the largest single lever on this repo's scorer
reliability. Measured 2026-08-27: the judged battery's pass base rate is **0.951** over the
345 judged rows in `evals/calibration/labels_v1.jsonl`; `affirms_judge` shows **130/135 raw
agreement (96.3%)** and still scores **kappa 0.530**, REFUSED against
`docs/SCORER_TRUST_POLICY.md`'s 0.60 threshold. Expected chance agreement `Pe` near 0.9 is
eating the statistic. A target band on the base rate turns that into something checkable.

**The problem with gating it now.** The deterministic battery measures **0.949** over
`evals/generations/k3_77688e7_regen1` (n=630), and four of its seven matcher families are
*constant* — `schema`, `min_length`, `in_set`, `range` all sit at exactly 1.000. A blocking
gate against the 0.55–0.85 band fails on the shipped set on day one, for a defect that
EVAL-P26 has not yet run to fix. In this repo's own history, a gate that is red before the
work starts is a gate that gets switched off.

**Decision.** `scripts/check_base_rate.py` takes an explicit `--enforce {advisory,blocking}`
parameter, defaulting to `advisory` via a named constant (`DEFAULT_ENFORCEMENT`), documented
in the module docstring and in `docs/CASE_SET_POLICY.md`. Advisory computes the identical
report and the identical breach list and exits 0. It is switched to `blocking` in the same
commit that lands EVAL-P26.2's rebuilt case set.

**Alternatives rejected.**
1. *Ship blocking now.* Fails by construction; see above.
2. *Ship the check commented out, uncomment later.* The finding disappears until someone
   remembers. A commented-out gate measures nothing and reminds no one.
3. *Widen the band so the current set passes.* That is weakening the contract to fit the
   result, which `SCORER_TRUST_POLICY.md` already refuses to do for kappa and which this
   policy should not do either.

**Consequences.** For one phase, `make check-base-rate` always exits 0. That is the cost,
and it is why the target is deliberately **not** wired into `make check` until the switch —
an always-green entry in the gate list trains people to skim it. The switch is a one-word
change to a documented default and a Makefile variable, and both places name EVAL-P26.

**Also decided here (mechanical, but worth recording).** The minimum record count below
which a family gets no band verdict is **computed** from the band, not chosen: it is the
smallest `n` for which some `k/n` falls inside it (3, for [0.55, 0.85]). DEC-181 rejected an
option for introducing an uncalibrated free parameter; there is no parameter here to
calibrate. `smallest_n_reaching_band` uses exact rational arithmetic so a rate exactly on a
band edge is not lost to floating-point rounding.

---

### DEC-217: contextual variance is scored lexically, and only the contrast is load-bearing

**Date:** 2026-08-27
**Phase:** EVAL-P25.4
**Status:** Accepted

**Context.** The maintainer's stated goal is that "replies should be incredibly varied based
on context and situation". Two of this repo's four judged scorers are suppressed and cannot
be quoted, and `tone_judge` is effectively unanimous and has no variance to move. A new
*judged* metric for this dimension would inherit the same tax and could not resolve an
effect today.

**Decision.** `evals/variance_scorer.py` scores it deterministically: mean **pairwise
Jaccard distance** over case-folded word tokens of the replies. Deterministic ⇒ kappa 1.0 by
construction ⇒ its observed MDE is its true MDE, no labels and no judge repair required.

**Why Jaccard, and what was rejected.**
1. *Embedding cosine* via the repo's existing
   `src/npc_engine/retrieval/embedding/sentence_encoder.py` would be semantically richer and
   is already in-tree. Rejected: `get_encoder` imports `sentence_transformers` and loads an
   ~80 MB model from disk or network on first call. The scorer's contract is a pure function
   over strings, and a scorer that can fail because a model download failed produces
   ambiguous zeroes. `evals/` also does not import `src/`. **No new dependency was added.**
2. *TF-IDF cosine.* The IDF vector is either a corpus dependency — the score then changes
   when the corpus does, so two runs stop being comparable — or estimated from the handful of
   replies being scored, which is unstable at n=5. Either way it is a free parameter.
3. *Normalized edit distance.* Dominated by length and word order, which are surface
   properties; two replies conveying different facts at the same length read as similar.

Jaccard is bounded [0, 1], symmetric, order-independent, and has **no parameter to
calibrate**.

**No stopword list, deliberately.** A stopword list is exactly such a parameter — change the
list, change every score. It is unnecessary because the load-bearing quantity is the
contrast, not the absolute level: function-word overlap is a floor present in the control
group and the treatment group alike and largely cancels in the delta.

**The contrast is the claim, not the level.** Sampling at non-zero temperature produces
lexical variety whether or not the engine reads context at all. `contrast()` scores a
control group (one NPC, one state, resampled) against a treatment group (N NPCs in differing
states) and reports the delta. Reporting the treatment score alone would credit sampling
noise as contextual sensitivity.

**The threshold is directional only.** `DIRECTIONAL_DELTA_THRESHOLD = 0.0`: differing states
must produce *strictly more* variety than resampling one fixed state. No measured run yet
exists from which to derive a magnitude, and inventing one now is precisely the uncalibrated
free parameter DEC-181 rejected. The magnitude threshold is deferred to EVAL-P26.

**Known limitation, recorded rather than hidden.** This is a lexical measure. Paraphrase
reads as varied when it is not; different facts sharing vocabulary read as similar when they
are not. It is used for the failure mode it detects reliably: a state-blind engine emitting
near-identical text for every context scores near 0.

---

### DEC-218: the case adversary is split — deterministic in code, judgment via batch/paste

**Date:** 2026-08-27
**Phase:** EVAL-P26.1
**Status:** Accepted

**Context.** The plan calls for "the Opus adversarial case reviewer". **There is no
Anthropic client in this repo.** Opus is reached by a manual batch/paste workflow:
`evals/calibration/OPUS_LABEL_PROMPT.md` is piped verbatim, JSON batches live under
`evals/calibration/oracle_batches/`, and JSONL results are imported back. A module that
called Opus directly would need a new dependency, which is a stop-and-ask.

**Decision.** Split the adversary along the line of what is mechanically decidable.

*Deterministic — pure Python, no LLM, and the majority of the value:*
- expectation tokens that also appear in the case's own `player_message` (the exact defect
  the EVAL-P20.2 audit found: one canned hedge passed 6 of 7 capability cases because the
  `keyword_any` lists were drawn from the vocabulary the case itself supplied);
- the case being satisfied by the reference always-hedge responder (reuses
  `scripts/hedge_responder_probe.CANNED_HEDGE` and `score_case`, DEC-167);
- the case being satisfied by an echo of its own `player_message` (same machinery
  `tests/unit/evals/test_capability_echo_resistance.py` ratchets against);
- the grounding edge type declared in `notes` being one the registry actually has.

*Judgment — the existing batch/paste workflow:* is the prompt leading, does it supply its own
answer, is the phrasing insider vocabulary lifted from the graph node. These live in
`prompts/eval/case_adversary.yaml`, are emitted by `build_review_batch`/`render_batch` in the
same on-disk shape as `oracle_batches/*.json`, and are imported back through
`parse_findings` into a Pydantic v2 model.

**Validation that the reuse is real.** Run over the 16 shipped `case_pos_*` files, the
deterministic half flags exactly the seven cases in `test_capability_echo_resistance`'s
`GAMEABLE_BASELINE` — the same seven, no more and no fewer — and exactly the two
judge-decided cases that module names. It also flags six cases whose `notes` name no
grounding edge type at all (ISSUE-224 below).

**Scope boundary, stated in the module docstring and enforced by a test.** This module
reviews **CASES**. EVAL-P28.1 labels **RESPONSES**. They are different jobs, and conflating
them is how the reference side of this repo stayed single-rater: reviewing the stimuli
improves what the engine is asked; independently labelling the outputs is what produces a
reference side that can be defended.

**What it deliberately does not do.** It never asserts the grounded fact exists in the graph.
Checking the declared edge type is a pure string check; confirming the node needs
`GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id}` (the generic graph reader is blind
to seeded inner life, ISSUE-148). Every review therefore carries
`live_verification_required=True` so the remaining step stays visible rather than assumed.

**LLM-decided expectations are reported unmeasured, never clean.** Scoring a `tone_judge`
expectation would call Ollama over HTTP, which this pure module must not do. Those
expectations are dropped from the gameability scoring and reported as
`judge_decided_unmeasured` — the same honest treatment
`test_capability_echo_resistance.py` already applies. A check that could not run is a
reported hole, not a silent pass.

---

## 5. ISSUES.md entries to add (full text)

```markdown
## ISSUE-224: six shipped capability cases name no grounding edge type in `notes`
**Found:** 2026-08-27, during EVAL-P26.1 (building the case adversary)
**Severity:** P2 (annoying)
**Where:** `evals/cases/case_pos_{aldric_trade_disruption, captain_sorn_war_knowledge,
lira_fence_trade, mira_war_gossip_tokens, old_henryk_war_rumor_tokens, world_blight_guard}.yaml`
**Description:** `docs/CAPABILITY_CASES.md` requires the `notes` field to "identify the
grounding edge type and node ID so cases are traceable to the graph". Six of the sixteen
shipped `case_pos_*` files do not. `case_pos_captain_sorn_war_knowledge`, for example, has
`notes` reading "Requires demo world seed (make demo-seed). Direct edge -> a confident,
specific answer is correct..." — it says "direct edge" without naming which one. The new
`evals/case_adversary.py` flags all six as `undeclared_grounding_edge`.
**Why deferred:** all six are also in `test_capability_echo_resistance.GAMEABLE_BASELINE`
and are being rewritten wholesale by EVAL-P26.2. Fixing the `notes` now would be edited
away in the rewrite, and this session must not touch `evals/cases/` — Track B is authoring
there concurrently.
**To fix:** as part of EVAL-P26.2's authoring pass, give every rewritten case a `notes`
line of the form `Grounding: <EDGE_TYPE>(<npc_id>, <node_id>).` using one of the five real
types (`KNOWS_ABOUT`, `BELIEVES`, `REMEMBERS`, `PURSUES`, `KNOWS_SECRET`). EVAL-P26.3's gate
should then require `undeclared_grounding_edge` to be empty.

## ISSUE-225: `make check-base-rate` is not in `make check`, by design, until EVAL-P26.2
**Found:** 2026-08-27, during EVAL-P25.3
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile` (`check:` target), `scripts/check_base_rate.py` (`DEFAULT_ENFORCEMENT`)
**Description:** the base-rate gate ships advisory (DEC-216), so wiring it into `make check`
today would add an entry that can never fail. It is therefore left out of the aggregate
gate, which means nothing runs it automatically and its report is only seen when someone
asks for it.
**Why deferred:** this is the intended state for exactly one phase. It is logged so the
switch is not forgotten rather than because it is wrong now.
**To fix:** in the same commit that lands EVAL-P26.2, set
`base_rate_contract.DEFAULT_ENFORCEMENT = BLOCKING`, set `ENFORCE ?= blocking` in the
Makefile, add `check-base-rate` to the `check:` target, and update
`docs/CASE_SET_POLICY.md`'s "Enforcement" section from "advisory first" to the landed state.

## ISSUE-226: `evals/case_adversary.py` has no CLI entry point
**Found:** 2026-08-27, during EVAL-P26.1
**Severity:** P3 (nice-to-fix)
**Where:** `evals/case_adversary.py`, `Makefile` (proposed `review-cases` target)
**Description:** the module is library-only. The `make review-cases` recipe proposed in
`HANDOFF_TRACK_A.md` §2 is a `python -c` one-liner, which is fine for a first pass but is
not somewhere to add flags (batch emission, JSONL import, `--cases` filtering).
**Why deferred:** `evals/` is scanned by check_rules R002 (`no print()`), so a CLI there
must write through `sys.stdout.write`, and adding one would have pushed the module back over
CLAUDE.md's 300-line limit — which is already why `case_adversary_contract.py` exists.
**To fix:** add `scripts/review_cases.py`, a thin wrapper owning `argparse`, the report
rendering, `render_batch` output to a file, and `parse_findings` import. Point the Makefile
target at it and delete the one-liner.

## ISSUE-227: the variance scorer has no magnitude threshold, only a directional one
**Found:** 2026-08-27, during EVAL-P25.4
**Severity:** P3 (nice-to-fix)
**Where:** `evals/variance_scorer.py` (`DIRECTIONAL_DELTA_THRESHOLD`)
**Description:** the gate asserts only that differing states produce strictly more variety
than resampling one fixed state (delta > 0.0). A delta of 0.001 passes. That is a weak gate.
**Why deferred:** no measured run exists to calibrate a magnitude against, and inventing one
is the uncalibrated free parameter DEC-181 rejected. Recording the weakness is better than
picking a number and calling it a threshold.
**To fix:** after EVAL-P26.2 authors `case_var_*` cases and a run produces control and
treatment groups, measure the delta distribution and set the threshold from it — the same
way the hedge probe's 0.30 was set from a measurement rather than chosen. Record the
derivation in `docs/CASE_SET_POLICY.md`.
```

---

## 6. How to run the EVAL-P26.1 judgment pass (for whoever runs it)

Deterministic half — no credits, no network:

```bash
make review-cases                       # or CASES=evals/cases_draft make review-cases
```

Judgment half — mirrors `evals/calibration/README.md` step 3:

```powershell
# 1. emit the batch (until ISSUE-226 lands, do this inline)
python -c "import sys, yaml, pathlib; sys.path[:0]=['evals','scripts']; \
from case_adversary import build_review_batch, render_batch; \
cases=[yaml.safe_load(p.read_text(encoding='utf-8')) for p in sorted(pathlib.Path('evals/cases').glob('case_pos_*.yaml'))]; \
print(render_batch(build_review_batch(cases)))" > evals/case_review/batch_001.json

# 2. paste the prompt + batch to Opus, same shape as the label pass
$prompt = (python -c "import sys; sys.path[:0]=['evals','scripts']; from case_adversary import load_adversary_prompt; print(load_adversary_prompt())") `
        + "`n`n<BATCH>`n" + (Get-Content evals/case_review/batch_001.json -Raw) + "`n</BATCH>"
claude -p $prompt --model opus | Where-Object { $_ -match '^\s*\{' } |
  Add-Content evals/case_review/findings.jsonl -Encoding utf8

# 3. import — parse_findings rejects the whole file on any malformed line, by design
python -c "import sys, pathlib; sys.path[:0]=['evals','scripts']; \
from case_adversary import parse_findings; \
[print(f) for f in parse_findings(pathlib.Path('evals/case_review/findings.jsonl').read_text(encoding='utf-8'))]"
```

`evals/case_review/` is a new directory and is **not** under
`loop_gates.FROZEN_PATH_PREFIXES`. Do not write review artifacts into
`evals/calibration/` or `evals/generations/` — both are frozen and hold the 393
irreplaceable human labels and the real transcripts.

---

## 7. Measurements this session made, for the record

Spot-checked against the ground truth supplied at session start; all reproduce.

| claim | reproduced | how |
|---|---|---|
| judged battery base rate 0.951 | **0.9507** | `scorer_verdict` over the 345 judged rows of `evals/calibration/labels_v1.jsonl` |
| `keyword_any` 0.647 (n=51) | exact | `deterministic_judged.jsonl`, `k3_77688e7_regen1` |
| `anti_hall_grounded` 0.896 (n=48) | exact | same |
| `keyword_none` 0.957 (n=207) | exact | same |
| `schema` / `min_length` / `in_set` / `range` all 1.000 | exact | same |
| ALL deterministic 0.949 (n=630) | **0.9492** | same |
| labels: 0 `pre_label` vs `human_verdict` disagreements in 393 | exact | `labels_v1.jsonl`, all rows `gen_id k3_73e6c36` |

One number worth naming precisely, because it is easy to misquote: **0.951 is the base rate
over the labelled judged rows** (`labels_v1.jsonl`, n=345, gen `k3_73e6c36`). The same gen's
`judged.jsonl` computes 0.9536 over its own 345 rows, and `k3_77688e7_regen1/judged.jsonl`
computes 0.9304 — the three are different denominators of the same battery, not a
contradiction. `check_base_rate.py` reports whichever generation directory it is pointed at
and names it in the report header, so a quoted number is always traceable to a directory.

### First real-data reading from the variance scorer

Run over `evals/generations/k3_77688e7_regen1/outputs.jsonl`, using the cross-NPC
register-contrast pair `docs/CASE_SET_POLICY.md` already documents — the byte-identical
player message `"What is happening in the north?"` sent to `captain_sorn` and
`mira_innkeeper`:

    control   (captain_sorn, k=3 repetitions, same state):  0.770
    treatment (2 NPCs, differing states):                   0.905
    delta                                                  +0.134   directional gate: PASS

**The control floor is 0.770.** At the shipped generation temperature (0.15), resampling one
NPC in one fixed state already produces 0.77 mean lexical dissimilarity. This is the single
most useful thing this reading says, and it validates the design decision in DEC-217: an
absolute threshold on the treatment level would have been badly calibrated — 0.905 looks
impressive until the floor it is standing on is measured. Only the delta is interpretable.

n=2 NPCs is far too small to calibrate a magnitude threshold from, which is why ISSUE-227
stays open; but it is a real first data point, and it says the eventual threshold belongs on
the delta and is likely to be small.
