# CR-L03 — Metrics & eval validity

Lens L3 of the 16-lens review. Branch `eval-ab-context-arms`, HEAD `d46ae42`, audited 2026-08-27.
Read-only. Every number below was produced by a command run in this session or traced to a
`file:line`. Neo4j is not published to the host, so no host-side Cypher was attempted; nothing in
this lens required it.

**Verdict in one line:** the eval instrument is unusually well-reasoned and unusually honest about
its own limits, and the single number the product is sold on — the anti-hallucination guard rate —
is **beaten by a fixed string**. That is a CRITICAL.

---

## Required measurements

### 1. Judge↔human agreement rate

**Measured, and it is the one thing in this repo that is genuinely instrumented.** Human ground
truth exists: `evals/calibration/labels_v1.jsonl`, 393 adjudicated rows.

```
$ python -m evals calibrate
Loaded 393 rows; 393 adjudicated.
Family-wise disclosure: 8 simultaneous intervals (4 scorer(s) × 2 axes).
  Nominal: 95% per-interval CI (α=0.050). FWER: 1−0.95^8 = 0.337.
```

| scorer | n rows | n clusters | Cohen's κ | 95% cluster-bootstrap CI | policy tier | CI excludes chance (κ=0)? |
|---|---:|---:|---:|---|---|---|
| `tone_judge` | 135 | 45 | **0.849** | **[−0.010, 1.000]** | PUBLISHABLE | **no** |
| `affirms_judge` | 135 | 45 | 0.530 | [0.000, 1.000] | REFUSED (restricted) | **no** |
| `anti_hallucination_grounded` | 48 | 16 | 1.000 | undefined at boundary | published | **undefined** |
| `refusal_judge` | 75 | 25 | 0.247 | [−0.123, 0.703] | REFUSED (hidden) | **no** |

**Not one of the four scorers has a κ interval that excludes chance agreement.** Two are refused
outright by the project's own policy. The one that is published (`tone_judge`, κ = 0.849) has a
lower bound of −0.010.

Provenance caveats, all confirmed:

- There is exactly **one human rater** (`pre_labeller_model == "human-lohann"` on 393/393 rows;
  `human_labeller == ""` on 393/393). `pre_label == human_verdict` on **393/393** rows, so the
  "secondary axis" is the rater compared to themselves. The harness detects this and refuses to
  print a number for it (`evals/calibration_records.py:49-58`) — correct behaviour, and it means
  **inter-human agreement is unmeasured and unmeasurable from the shipped artifact**.
- `evals/calibration/oracle/labels_oracle.jsonl` is 21 rows of `pre_labeller_model:
  "oracle-matrix-v1"`, all with `human_verdict: null` — rule-based, not a second rater.
  `evals/calibration/mock_labels.jsonl` (920 rows) is random and stamped `mock-random-v1`.
  `evals/synthetic_label_guard.py` correctly refuses to let either overwrite the real file.
- The labels describe generation `k3_73e6c36` (`gen_id` on 393/393 rows), **not** the current
  `k3_77688e7_regen1`. See CR-L03-05.
- 393 of 921 rows in that generation are labelled. `make check-label-survival` prints
  `New (unlabelled) rows in the candidate transcript: 528` and still exits 0 / `FROZEN`.

**What the judge scores are therefore worth:** `tone_judge` and `anti_hallucination_grounded`
verdicts are usable as *evidence* on a single-scorer scope; `affirms_judge` and `refusal_judge`
verdicts are, by the repo's own `docs/SCORER_TRUST_POLICY.md`, not quotable at all — and they are
quoted anyway, inside the composite guard rate (CR-L03-02).

### 2. Base rate per case set — what a null system scores

The null system used is `scripts/hedge_responder_probe.CANNED_HEDGE`: one fixed string, no graph,
no LLM, no memory. Judge verdicts for it were **measured live** against `mixtral:8x7b` this session
(`refusal_judge` → PASS, guard tone rubric → PASS, guard lore rubric → PASS after
`matchers._eval_affirms_judge`'s polarity inversion at `evals/matchers.py:324-327`). Deterministic
kinds were scored through the shipped `matchers.evaluate`; AH-fixture grounding was scored through
the shipped `any(sub.lower() in text.lower())` at `evals/anti_hallucination_runner.py:80-83`.

| case set | n | **null-system base rate** | engine (measured, `k3_77688e7_regen1`) | gate / threshold | verdict |
|---|---:|---:|---:|---|---|
| Guard — `case_adv_*` + `case_neg_*` (YAML) | 37 cases / 222 slots | **1.000** (37/37, 222/222) | — | none | **measures nothing** |
| Guard — `ah_demo_*` (JSON fixture) | 41 cases | **0.902** (37/41) | — | none | measures nothing |
| **Guard battery, combined** | **78 cases** | **0.949 (74/78)** | **0.897 (70/78)** | none | **null beats engine** |
| Capability `case_pos_*` (expectation slots) | 46 slots | 0.130 (6/46) | — | hedge rate < 0.30 | gate met |
| Capability `case_pos_*` (cases that ran) | 16 cases | **0.375** (6/16 hedge-passable) | 0.625 [0.386, 0.815] | none | floor ≈ measurement |
| `schema` | 186 rows | 1.000 | 1.000 | band [0.55, 0.85] | constant |
| `min_length` | 111 rows | 1.000 | 1.000 | band | constant |
| `in_set` | 18 rows | 1.000 | 1.000 | band | constant |
| `range` | 9 rows | 1.000 | 1.000 | band | constant |
| `keyword_none` | 207 rows / 36 exprs | 0.889 bland text; **18/36 exprs are guaranteed passes** | 0.957 | band | 50% inert |
| `keyword_any` | 51 rows | 0.080 | 0.647 | band | **the only informative family** |

Supporting measurements:

```
$ python scripts/check_base_rate.py evals/generations/k3_77688e7_regen1
  ALL  n=975  rate=0.943  above_band          (target band [0.55, 0.85], mode: advisory)
  9 of 10 families out of band; 4 families flagged "<- CONSTANT: no variance to move"
```

```
$ make hedge-probe
  capability: 6/46  rate 0.130  (gate: < 0.30)   verdict: GATE MET
  cases the hedge passed: case_pos_aldric_trade_disruption, case_pos_captain_sorn_war_knowledge,
    case_pos_mira_gossip_hedging, case_pos_mira_war_gossip_tokens,
    case_pos_old_henryk_war_rumor_tokens, case_pos_world_blight_guard
```

All six hedge-passable cases are among the 16 that produced the published capability rate.

Dead-keyword measurement, recomputed against the **newest** 975-response corpus (the shipped
`scripts/check_dead_keywords.py` reads the stale one):

```
keyword_none expectations: 36   fully-dead (guaranteed pass): 18 = 50.0%
keywords total: 264            dead: 210 = 79.5%
```

### 3. n and statistical power for every numeric eval gate

Computed with the repo's own model, `evals/mde.py`, at its own recorded discordance
(`implied_discordance_rate(mde=0.064, n_pairs=78)` → p_d = 0.0407) and its own recorded per-criterion
Fleiss κ (`evals/mde.py:93-97`). `headroom` = 1 − measured base rate: the largest true effect that
is physically possible on that family.

| gate / metric | code | n | threshold | observed MDE | **true MDE** (κ-corrected) | headroom | can it ever fire? |
|---|---|---:|---|---:|---:|---:|---|
| guard rate regression | `regression_gate.check_regression` | **78** | `cand.ci_high < base.rate` | 6.4 pp | 6.4–28.4 pp | 10.3 pp | only for `tone_judge` slots |
| capability rate regression | same | **16** | same | — | — | 37.5 pp | no (CI width 0.43) |
| `tone_judge` arm effect | `mde.arm_pairing_mde` | 135 | — | 4.86 pp | **4.86 pp** | 7.4 pp | marginally |
| `affirms_judge` arm effect | same | 135 | — | 4.86 pp | **17.25 pp** | 5.9 pp | **no** |
| `refusal_judge` arm effect | same | 75 | — | 6.53 pp | **29.01 pp** | 8.0 pp | **no** |
| inconclusive-rate gate | `DEFAULT_MAX_INCONCLUSIVE_RATE = 0.20` | 103 | > 0.20 | — | — | measured 0.000 | yes |
| instrument gate (panel κ) | `instrument_gate.py:125` | 345 items | `cand.ci_high < base.kappa` | — | — | CI [0.413, 0.733] | yes, but no baseline |
| base-rate band | `base_rate_contract.py:32-33` | 975 | [0.55, 0.85] | — | — | measures 0.943 | **advisory, exits 0** |
| hedge gate | `hedge_responder_probe.py:53` | 46 | < 0.30 | — | — | measures 0.130 | yes |
| seed reproduction | `evals/seed_reproduction.json` | 145 | ≥ 0.95 | — | — | measures 0.628 | **NOT_MET, ungated** |
| scorer trust | `scorer_trust_policy.py:74` | 48–135 | κ ≥ 0.60 (point est.) | — | — | — | yes, ignores CI |

`docs/STATISTICS_POLICY.md`'s own requirements versus what the code does:

| STATISTICS_POLICY claim | code | verdict |
|---|---|---|
| "2 × S simultaneous bootstrap intervals" per run; FWER 0.337 at 4 scorers | report prints `8 simultaneous intervals (4 scorer(s) × 2 axes)` then prints `N/A (single rater)` for all four secondary axes | **only 4 intervals exist**; the disclosed family size and Holm α* = 0.0063 are both wrong (conservative, but the disclosure is false) |
| bootstrap resamples case **clusters**, not rows | `evals/calibration.py:469` resamples clusters | correct |
| no pooled κ across scorers is printed | one matrix per scorer, confirmed in output | correct |
| slot-level cherry-picking unsupported; use case-level McNemar | `paired_stats.mcnemar_exact` exists and is used | correct |
| `BOOTSTRAP_RESAMPLES = 2000` | `evals/calibration.py:41` | correct |

The policy never sets a minimum n and defers that to `EVAL_STRATEGY.md`
(`docs/SCORER_TRUST_POLICY.md:75`), which `project-harness/CODEBASE_REVIEW.md:683` records as
**"Abandoned (91 days)"**. Sample-size adequacy therefore has no owner anywhere in the repo — which
is why the table above had to be computed here for the first time.

### 4. Leakage — case authoring vs scoring

Traced end to end. **Substantially clean**, with two documented residuals.

| path | shares a model? | shares a prompt? | shares an author? | evidence |
|---|---|---|---|---|
| judge vs generator | **enforced separate** — `JudgeModelCollisionError` raised at import | no | n/a | `evals/judge_config.py:114-127`; generation `qwen2.5:7b`, judge `mixtral:8x7b` |
| judge panel vs generator | one seat (`qwen2.5:14b`) is the **same family** as `qwen2.5:7b` | no | n/a | `evals/judge_config.py:38-44`, `:141-165` (warns, allows) |
| case adversary vs judge | **no** — adversary is Claude Opus via manual paste; judges are local Ollama | no | no | `prompts/eval/case_adversary.yaml:6-10`; `evals/case_adversary.py:36-42` |
| case adversary vs labeller | both Claude Opus, but different prompts and different objects (cases vs responses); the module states the boundary explicitly | no | yes (both Opus) | `evals/case_adversary.py:20-25`; `evals/calibration/OPUS_LABEL_PROMPT.md` |
| case adversary vs echo-resistance test | **shares the scorer and the reference hedge** (`hedge_responder_probe.score_case`, `CANNED_HEDGE`) | n/a | n/a | `evals/case_adversary.py:69-73` — declared deliberate, so the adversary cannot certify a case the ratchet would fail |
| human labeller vs case author | the 393 human verdicts and the case YAML were both produced in this repo by the same maintainer + agent | — | yes | unavoidable at this team size; **not** mitigated anywhere |

Measured check of the same-family concern (does `qwen2.5:14b` go easy on `qwen2.5:7b` output?):

| pair | n | raw agreement | Cohen's κ |
|---|---:|---:|---:|
| `llama3.1:8b` vs `mixtral:8x7b` | 345 | 0.945 | 0.531 |
| `llama3.1:8b` vs `qwen2.5:14b` | 345 | 0.942 | 0.495 |
| `mixtral:8x7b` vs `qwen2.5:14b` | 345 | 0.957 | 0.693 |

Per-judge pass rate: `llama3.1:8b` 0.954, `mixtral:8x7b` 0.922, `qwen2.5:14b` 0.925. The
same-family seat is **not** measurably more lenient. No leniency leakage detected. The
`mixtral`/`qwen14b` pair is the most-agreeing pair, which under 2-of-3 consensus does give those
two an effective veto over `llama3.1:8b` — worth watching, not a finding today.

### 5. Every policy document: does the code do what it says?

**131 normative claims checked, 38 diverge.** Full per-doc tables below; the load-bearing ones are
in the findings.

| doc | claim | implemented? | divergence at |
|---|---|---|---|
| SCORER_TRUST_POLICY | "Report generators **must** call `check_publication` before including a scorer's rate in any output" | **NO** | `evals/report.py:1-16` imports `summary` + `retrieval_summary` only; no call site outside `calibration.py` / `dashboard/headline.py` |
| SCORER_TRUST_POLICY | policy is "encoded as a function so no report path can bypass it programmatically" | **NO** | the only path that writes the published report bypasses it |
| SCORER_TRUST_POLICY | κ tiers 0.40 / 0.60 | YES | `evals/scorer_trust_policy.py:22-23` |
| EVAL_METHODOLOGY §3 | "the trust policy consults **the interval**, not just the point estimate" | **NO** | `evals/scorer_trust_policy.py:84-94` — `interval` is a parameter and is never read; `dashboard/headline.py:140` passes a fabricated `(0.0, 0.0)` |
| EVAL_METHODOLOGY §5 | "the report substitutes the EVAL-P11.1 refusal message in place of the rate" | **NO** | same — `report.py` has no refusal path |
| EVAL_METHODOLOGY §5 | no rule covers a **composite** rate built from 4 scorers of mixed tier | **GAP** | guard rate 0.897 mixes `tone_judge`+`affirms_judge`(REFUSED)+`refusal_judge`(REFUSED)+deterministic |
| EVAL_METHODOLOGY anti-metric | "The LLM judge is a single model… A second judge was considered (DEC-143) but **not implemented**" | **STALE** | a 3-model panel ships: `judge_config.py:38-44`, `evals/judge_panel.py`, `run_status.json:judge_panel` |
| EVAL_METHODOLOGY §4 | quotes `evaluated_cases = total_cases - skipped_cases` | STALE | actual `evals/summary.py:199` is `len(guard)+len(cap)+len(excluded)` |
| CASE_SET_POLICY | base-rate band "measured and gated by `scripts/check_base_rate.py` (`make check-base-rate`)" | **NO** | `make check-base-rate` does not exist; `grep -n base-rate Makefile` → no match |
| CASE_SET_POLICY | advisory "is a declared parameter, not a disabled check" | PARTIAL | true of the exit code; false in effect — no target, no CI, never run |
| CASE_SET_POLICY | measured table (0.949, 4 constant families) | YES | reproduced exactly this session |
| CAPABILITY_CASES | "`make check-engine-coverage` fails when a unit exists with no classification row" | **NO** | target absent from the Makefile |
| CAPABILITY_CASES | echo/hedge resistance enforced by `test_capability_echo_resistance.py` | YES | file present, ratchet real |
| REGRESSION_POLICY | the whole gate | **VACUOUS** | `evals/trend/trend_v1.jsonl` holds **1 row**, already incomparable (below) |
| REGRESSION_POLICY | quotes `refusal_judge` κ 0.225 / `affirms_judge` 0.282 | **inconsistent** | calibration prints 0.247 / 0.530; panel Fleiss prints 0.422 / 0.519. Three different κ for the same scorer circulate in the docs |
| STATISTICS_POLICY | family size = 2 × S | **NO** | S secondary axes are all `N/A (single rater)`; 4 intervals exist, 8 are disclosed |
| SEQUENCE_STATS_POLICY | "Cochran's Q … Not yet shipped — EVAL-P14" | STALE | shipped at `evals/sequence_order_effect.py:70-96` |
| SEQUENCE_STATS_POLICY | order-effect check runs at FULL fidelity as a diagnostic | **NO** | `evals/sequence_rates.py:158-160` computes it only when some scenario is PARTIAL |
| SEQUENCE_STATS_POLICY | "p-value below 0.05 is reported as a significant order effect" | **NO** | no 0.05 constant anywhere; p is printed raw and never classified |
| SEQUENCE_STATS_POLICY | §4.3 FULL-fidelity warning block | **NO** | string does not exist in `evals/sequence_*.py` |
| SEQUENCE_STATS_POLICY | fidelity read per repetition from a live receipt | **NO** | `evals/sequence_reset.py:75-85` re-emits one static tuple from `evals/reset_fidelity.json` k times |
| SEQUENCE_STATS_POLICY | trend alert suppressed at PARTIAL | **NO (unenforced)** | no `fidelity` reference in `trend_store.py` / `trend_row_builder.py` / `regression_gate.py` |
| RELEVANCE_WEIGHTS | `RelevanceWeights` lives in `npc_engine/schema/llm_config_models.py` | **NO** | it is `src/npc_engine/schema/context_config_models.py:59`; doc link broken |
| RELEVANCE_WEIGHTS | default shipped in `config/llm_config.yaml` | **NO** | path is `src/npc_engine/config/llm_config.yaml` |
| RELEVANCE_WEIGHTS | balanced default 0.20/0.20/0.15/0.20/0.15/0.10 | **STALE-NUMBER** | `src/npc_engine/config/llm_config.yaml:51-56` → recency **0.30**, proximity **0.20**, quest **0.10**, `explicit` absent |
| RELEVANCE_WEIGHTS | active weights logged at startup in the quoted form | PARTIAL | `src/npc_engine/main.py:149` logs the model object |
| RELEVANCE_WEIGHTS | tie-break `score DESC, node_type ASC, node_id ASC` | PARTIAL | 4th key `item.key` at `context_relevance_engine.py:95-102` |
| REASONING_DIMENSIONS | `evals/runner.py` keys off `case_pos_` | **NO** | no `case_pos` string in `evals/runner.py`; only guard prefixes at `:37` |
| REASONING_DIMENSIONS | D1 `relevant_node_ids` "names **the one** grounded node" | **NO** | all 8 `case_pos_evk_*` list 3 ids |
| REASONING_DIMENSIONS | D1 coverage: each of KNOWS_ABOUT/BELIEVES/REMEMBERS/PURSUES ≥ 1 evk per world | **NO** | zero `case_pos_evk_*` grounded in `KNOWS_ABOUT` in any world; demo world has zero evk cases |
| REASONING_DIMENSIONS | all five "Coverage rule" clauses | **UNENFORCED** | `tests/unit/evals/test_capability_coverage.py:26-50` is an NPC-id ratchet; contains no dimension prefix |
| REASONING_DIMENSIONS (via `variance_scorer.py:9`) | `make variance-score` | **NO** | target absent |
| ENGINE_EVAL_COVERAGE | "Gated by `scripts/check_engine_coverage.py` (`make check-engine-coverage`)" | **NO** | target absent; gate not in `make check` |
| ENGINE_EVAL_COVERAGE | 18 dialogue_observable / 16 state_observable / 10 not_observable of 44 | YES (re-measured, exit 0) | `scripts/check_engine_coverage.py` |
| ENGINE_EVAL_COVERAGE | `quest` → `active_quest` pinned and used by Rule 11 | **CONTRADICTED in-code** | `src/npc_engine/retrieval/context/context_slots.py:146-147` says "Pinned at 89 and never serialized" |
| RESET_FIDELITY | "the Wilson interval at `evals/sequence_runner.py:160` … computed unconditionally today" | **STALE** | that line is `k=k,`; gating landed at `evals/sequence_fidelity.py:117`; ISSUE-143 is `[FIXED]` |
| RESET_FIDELITY | every measured number (PARTIAL, 10 survivors, 6 unobservable, 56 ms median) | YES | `evals/reset_fidelity.json` matches row-for-row |

### 6. Determinism / reproducibility

| question | answer | evidence |
|---|---|---|
| is the generation seeded? | yes, and the seed is recorded | `evals/generations/k3_77688e7_regen1/meta.json` → `"seed": 20260814`, `"temperature": 0.15`, `"top_p": 0.95` |
| same seed → same output? | **no — 62.8%** | `evals/seed_reproduction.json`: `rate_records 0.6276`, `gate 0.95`, `verdict "NOT_MET"` |
| same output → same judge score? | **no** | three identical `matchers._run_binary_judge` calls at `temperature 0.0`: `True (24.4 s)`, `True (30.6 s)`, `None/infra_failure (32.8 s, ReadTimeout)` |
| does the judge request carry a seed? | **no** | `evals/matchers.py:248` — `"options": {"num_predict": 80, "temperature": _JUDGE_TEMPERATURE}`; no `seed` key |
| is model version recorded? | **partially** | `meta.json` records `generation_model`, `judge_model`, `ollama_version`, `git_sha`, `dialogue_prompt_hash` — but `"generation_model_digest": null` and `"judge_model_digest": null`, so an `ollama pull` silently changes the instrument |
| is unseeded `random` used in scoring? | **no** | every `random.Random(...)` in `evals/` is explicitly seeded: `calibration.py:469` (seed 42), `kappa_stats.py:167` (seed 20260818), `label_sampling.py:93` (caller-supplied) |
| are repetitions stable? | **no, and it is recorded** | `run_status.json` → `repeat_flips: {records_with_flips: 19, n_records: 115}` — 16.5% of records flip verdict across k=3 |

---

## Findings

### [CR-L03-01] The guard battery is beaten by a fixed string — the anti-hallucination number is not a measurement

- **Severity:** CRITICAL
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** A null responder — `scripts/hedge_responder_probe.CANNED_HEDGE`, one hard-coded
  sentence, no knowledge graph, no LLM, no memory — was scored through the **shipped** scorers.
  Deterministic kinds via `matchers.evaluate`; the three LLM-judged kinds via live
  `matchers._run_binary_judge` against `mixtral:8x7b` this session (`refusal_judge` → PASS, guard
  tone rubric → PASS, guard lore rubric → PASS after the polarity inversion at
  `evals/matchers.py:324-327`); AH-fixture grounding via the shipped
  `any(sub.lower() in text.lower())` at `evals/anti_hallucination_runner.py:80-83`.

  ```
  guard cases (case_adv_* + case_neg_*): 37   null-system case pass rate: 37/37 = 1.000
  kind                n  null_pass    rate
  affirms_judge      45         45   1.000
  keyword_none       66         66   1.000
  min_length         37         37   1.000
  schema             37         37   1.000
  tone_judge         37         37   1.000
  ALL SLOTS         222        222   1.000

  AH fixture (ah_demo_*): 41 cases (25 refusal, 16 grounded)
    refusal cases passed by the hedge: 25/25 (refusal_judge measured live)
    grounded cases passed by the hedge: 12/16
    -> 37/41 = 0.902

  COMBINED GUARD BATTERY (78 cases): null = 74/78 = 0.949
  ```

  The engine, measured on the same 78 cases from the newest committed generation
  (`summary.summarize_from_dir(evals/generations/k3_77688e7_regen1)`): `guard_passes 70`,
  `guard_rate 0.8974`. The published headline is `evals/reports/20260825T231028Z.md:11` —
  "Guard (adv + neg + ah_demo_*) | 170/186 | 0.914 95% CI [0.8478–0.9530]".

  **A fixed string scores 0.949. The engine scores 0.897.** The guard battery does not
  discriminate the engine from a scripted shrug; it ranks the shrug higher.

  The project has the right instrument for exactly this and pointed it at the wrong battery:
  `scripts/hedge_responder_probe.py:71-76` (`NotACapabilityCaseError`) **refuses** to score a guard
  case, so the null baseline has only ever been measured for the 16-case capability battery — never
  for the 78-case battery that produces the published number.
- **Cost of inaction:** the product's central external claim ("persistent memory, no
  hallucination — 91.4% on adversarial turns") is false as a claim about the engine, and any studio
  that runs its own null baseline will find this in an afternoon. Every A/B, every prompt change and
  every roadmap decision taken against the guard rate since 2026-06 was taken against noise.
- **Fix sketch:** lift the `case_pos_` restriction in `hedge_responder_probe` so the probe scores the
  guard battery too, and add the null rate to the report beside the engine rate — a rate whose null
  baseline is not printed alongside it should not be printed. Then rebuild the guard battery so its
  expectations can fail: replace the 18 fully-dead `keyword_none` lists and the three constant
  families with assertions a hedge cannot satisfy.
- **Effort:** L
- **Blast radius:** `evals/cases/case_neg_*.yaml`, `case_adv_*.yaml`, `anti_hallucination_demo.json`,
  `evals/report.py`, `evals/summary.py`, the README's headline number, and every trend row.

### [CR-L03-02] `check_publication` ignores the interval it is handed, and the report generator never calls it

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `evals/scorer_trust_policy.py:65-94` — `check_publication(scorer, kappa, interval)`
  branches only on `kappa`; `interval` is stored in the refusal and never read. `docs/EVAL_METHODOLOGY.md`
  §3 states "the trust policy (§5) consults the interval, not just the point estimate."
  `evals/dashboard/headline.py:140` passes `(0.0, 0.0)` — a fabricated interval — because it makes no
  difference. Consequence, from `python -m evals calibrate`: `tone_judge` at κ = 0.849 with
  **95% CI [−0.010, 1.000]** is graded PUBLISHABLE; its interval does not exclude chance.

  Separately, `docs/SCORER_TRUST_POLICY.md` says "Report generators **must** call `check_publication`
  before including a scorer's rate in any output." `evals/report.py:1-16` imports only `summary` and
  `retrieval_summary`; `grep -rn check_publication evals/` returns call sites in
  `calibration.py:718,759` and `dashboard/headline.py:140` and nowhere else. The file that writes
  `evals/reports/*.md` — the published artefact — has no policy path at all, and it prints a guard
  rate composed of `affirms_judge` (REFUSED, restricted) and `refusal_judge` (REFUSED, hidden).
- **Cost of inaction:** the one mechanism that exists to stop an untrustworthy number reaching a
  report does not sit on the path to the report. Every published guard/capability rate is
  unchecked, today.
- **Fix sketch:** make `check_publication` refuse when `interval[0] < HIDDEN_THRESHOLD` regardless of
  the point estimate, and add a composite rule — a rate compounded from scorers of mixed tier
  inherits the lowest tier. Call it from `evals/report.py` before the guarantee table is rendered.
- **Effort:** M
- **Blast radius:** `evals/report.py`, `evals/summary.py` formatting, `dashboard/headline.py`, the
  shipped reports, `docs/SCORER_TRUST_POLICY.md`.

### [CR-L03-03] The judged half of the battery cannot resolve any effect that is physically possible

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** computed with the repo's own `evals/mde.py` at its own recorded inputs
  (`implied_discordance_rate(mde=0.064, n_pairs=78)` → p_d = 0.0407; κ from `evals/mde.py:93-97`):

  ```
  criterion             kappa    n   obs_MDE_pp  true_MDE_pp
  tone_judge            1.000  135        4.86         4.86
  affirms_judge         0.282  135        4.86        17.25
  refusal_judge         0.225   75        6.53        29.01
  ```

  Against the measured base rates in the same generation (`scripts/check_base_rate.py`): `affirms_judge`
  0.941 → **5.9 pp of headroom** against a 17.25 pp true MDE; `refusal_judge` 0.920 → **8.0 pp of
  headroom** against a 29.01 pp true MDE. Two of the three LLM judges cannot detect any improvement
  that is arithmetically possible on their own family. `tone_judge`'s κ = 1.000 is not reassurance:
  `evals/mde.py:99-102` records that it comes from "unanimous 135/135 — that is a statement about
  variance to move, not about the criterion being well designed."
- **Cost of inaction:** every A/B arm the current branch (`eval-ab-context-arms`) is built to run
  will return "no significant difference" whatever the engine does, and that null result will be
  read as evidence about the engine. Ten-hour paired generations for a foregone conclusion.
- **Fix sketch:** `evals/mde.py` already computes this; wire it into a preflight that refuses to
  start a paired generation whose `true_mde_pp` exceeds `1 − base_rate` for the criterion, and print
  the refusal with the two numbers. Then fix the inputs (harder cases, more n) rather than the gate.
- **Effort:** S to wire the preflight; L to fix the inputs.
- **Blast radius:** `evals/arm_probe*.py`, `scripts/Run-EvalHarness.ps1`, the EVAL-P25..P31 plan.

### [CR-L03-04] 1,522 lines of the newest gate layer are reachable from no `make` target and no CI job

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:**
  ```
  $ for t in check-engine-coverage review-cases check-base-rate check-variance; do
        grep -qE "^$t:" Makefile && echo "$t EXISTS" || echo "$t MISSING"; done
  check-engine-coverage    MISSING from Makefile
  review-cases             MISSING from Makefile
  check-base-rate          MISSING from Makefile
  check-variance           MISSING from Makefile
  ```
  Each is named as its own entry point by the code or the docs it belongs to:
  `scripts/check_base_rate.py:12` ("Used by: `make check-base-rate`"),
  `docs/CASE_SET_POLICY.md` base-rate section, `docs/ENGINE_EVAL_COVERAGE.md:3-4`,
  `evals/case_adversary.py:14` ("Used by: `make review-cases`"), `evals/variance_scorer.py:9`
  (`make variance-score`). Line counts: `check_base_rate.py` 216 + `base_rate_contract.py` 170 +
  `check_engine_coverage.py` 272 + `engine_coverage_contract.py` 152 + `case_adversary.py` 292 +
  `case_adversary_contract.py` 174 + `variance_scorer.py` 246 = **1,522**.

  Worse, `.github/workflows/ci.yml` runs `make lint`, `check-rules`, `check-layers`, `type`,
  `check-harness`, `test-v13-*`, `test-cov*`, `check-contracts`, `check-contract-sync`,
  `test-v14-*` — and **not one eval-validity gate**: no `check-conservation`, no
  `check-label-survival`, no `check-test-quality`, no `check-evals-rules`, no `type-evals`, no
  `check-dead-keywords`. `make check` itself is never invoked by CI.
- **Cost of inaction:** 20,141 lines of instrument, zero of it enforced on any commit. The gates
  written in the last three commits will rot before they are ever run; the base-rate breach
  (0.943 vs [0.55, 0.85]) is already invisible.
- **Fix sketch:** add the four missing targets, add the eval gates to `make check`, and add a
  single `make check` step to `ci.yml`. Flip `DEFAULT_ENFORCEMENT` to `BLOCKING` only after
  EVAL-P26 as `scripts/base_rate_contract.py:42` already says.
- **Effort:** S
- **Blast radius:** `Makefile`, `.github/workflows/ci.yml`. Expect CI to go red immediately —
  that is the point.

### [CR-L03-05] The trend/regression stack has never made a comparison, and its sole row is already incomparable

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `wc -l evals/trend/trend_v1.jsonl` → **1**. `docs/REGRESSION_POLICY.md` specifies a
  baseline walk-back, a `ComparabilityKey`, a one-sided CI rule, three exit codes and a separate
  instrument verdict; `evals/regression_gate.py` + `instrument_gate.py` + `baseline_selection.py` +
  `comparability.py` + `trend_store.py` + `trend_row_builder.py` = **1,141 lines**, plus
  `scripts/record_trend_and_gate.py` (168). With one row there is nothing to compare, so
  `select_baseline` refuses (exit 2) unless `--allow-no-baseline` is passed.

  And the one row is already dead:
  ```
  $ python -c "... run_config.resolve_harness_version(cases_dir=evals/cases, ...)"
  current harness_version:   21dcfa8dbc86
  trend row harness_version: f22f61a5d877
  comparable: False
  ```
  Adding the 30 case files on 2026-08-27 changed the hash, so the next run will refuse against the
  only baseline that exists.

  Related provenance defect: `evals/trend_row_builder.py:184-199` builds every row's
  `scorer_kappas` from `labels_path: Path = LABELS_FILE` — the one global labels file — with no
  check that the labels describe the row's generation. The row for `k3_77688e7_regen1` carries κ
  measured on `k3_73e6c36` outputs (`labels_v1.jsonl` `gen_id` on 393/393 rows;
  `golden_set_version` `e8b1c745c1e3` vs the run's `6871ce3e686b`). A reader takes those κ as this
  run's instrument reliability; they are not.
- **Cost of inaction:** 1,309 lines of a gate that has produced no verdict in six weeks and cannot
  produce one until two runs land under one `harness_version`. Meanwhile the κ printed beside every
  run's rates describes a different run.
- **Fix sketch:** either (a) land two comparable runs immediately and keep the stack, or (b) delete
  it and re-derive it when there is a cadence that produces comparable runs. Independently, make
  `_scorer_kappas` refuse (or record `None`) when the labels' `gen_id` ≠ the row's `gen_id`.
- **Effort:** S for the `gen_id` guard; M–L for the decision.
- **Removes:** ~1,309 lines / 7 files, if (b).
- **Blast radius:** `scripts/Run-EvalHarness.ps1` steps 7–8, `docs/REGRESSION_POLICY.md`, DEC-191/194/197.

### [CR-L03-06] The headline aggregator still reports 78 turns for 789 verdict rows and 5 hallucinations for 28

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `summary.summarize_from_dir(evals/generations/k3_77688e7_regen1)` returns
  `guard_turns 78`, `guard_passes 70`, `hallucination_failures 5`. Counting the same directory's
  verdict files directly:
  ```
  total verdict rows: 975
  guard rows: 789
  guard failures by kind (all k=3 reps):
    affirms_judge 8, keyword_none 9, refusal_judge 6, anti_hallucination_grounded 5, tone_judge 2
  ```
  So the denominator is understated by a factor of ~10 (ISSUE-155: `verdict_sources.load_unified_rows`
  dedups on bare `record_id`, collapsing k=3), and the hallucination tally counts only
  `affirms_judge`+`keyword_none` post-dedup, excluding `refusal_judge` and
  `anti_hallucination_grounded` (ISSUE-156, `evals/summary.py:19-24`, `:253-276`). Both are logged
  **P1 (blocking)**, found 2026-08-12, still open 15 days later.

  This is not a dormant bug: `evals/trend_row_builder.py:184` calls `summarize_from_dir`, so the
  corrupted numbers are exactly what the trend row and the regression gate consume. The same
  battery is meanwhile published with three different denominators — 78 (`summarize_from_dir`),
  186 (`evals/reports/20260825T231028Z.md:11`, the live runner path), and 789 (raw rows) — and two
  different failure counts, 5 and 8.
- **Cost of inaction:** the guard rate's Wilson CI is computed at n=78 instead of n=234–789, so it
  is 1.7–3× wider than it should be, which compounds CR-L03-03 — the regression gate is made even
  less able to fire by an arithmetic bug. `make check-conservation` does not catch it because it
  audits case counts on a superseded generation (below).
- **Fix sketch:** fix ISSUE-155 and ISSUE-156 together as their own entries instruct, then add a
  conservation identity asserting `guard_turns == guard_cases × k` and a second asserting the three
  publication paths agree on the denominator.
- **Effort:** M
- **Blast radius:** `evals/verdict_sources.py`, `evals/summary.py`, every trend row, `compare.py`,
  `scripts/check_conservation.py`.

### [CR-L03-07] Two of the four eval gates in `make check` audit a superseded generation

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** `scripts/check_conservation.py:35-37` hardcodes
  `_DEFAULT_GEN_DIR = .../evals/generations/k3_73e6c36`; `scripts/check_dead_keywords.py:31-37`
  hardcodes the same corpus. `make check-label-survival` prints
  `gen-dir …k3_73e6c36 predates EVAL-P18.1's harness_version field`. The current generation is
  `k3_77688e7_regen1` (2026-08-25). All three pass green against 2026-08-08 data.

  The conservation report also prints a false identity:
  ```
  Identity 1 [OK]: guard_cases + capability_cases == total_cases
    78 guard + 7 capability = 94 OK
  ```
  78 + 7 ≠ 94. The internal check is correct (`scripts/check_conservation.py:135` includes
  `excluded`), but the rendered line at `:236-240` omits the `excluded` term, so the audit's own
  output states an arithmetic falsehood. ISSUE-176 logs the hardcoded path; the misprinted identity
  is not logged.
- **Cost of inaction:** the canonical health gate certifies a snapshot nobody runs against, and the
  one line a reader would check is wrong on its face — which trains readers to skim it.
- **Fix sketch:** default both scripts to the newest generation directory (or require `--gen-dir`),
  and render the `excluded` term in Identity 1's line.
- **Effort:** S
- **Blast radius:** `scripts/check_conservation.py`, `scripts/check_dead_keywords.py`,
  `scripts/check_label_survival.py`, `make check` output.

### [CR-L03-08] Half the guard battery's forbidden-keyword assertions are guaranteed passes

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** recomputed against the **newest** 975-response corpus using the shipped
  `evals/keyword_matching.contains_keyword`:
  ```
  keyword_none expectations: 36   fully-dead (guaranteed pass): 18 = 50.0%
  keywords total: 264            dead: 210 = 79.5%
  fully dead: case_adv_aldric_black_market, case_adv_captain_sorn_guild_smuggling,
    case_adv_leading_betrayal, case_adv_mira_aldric_trade_figures,
    case_neg_aldric_no_military_orders, case_neg_aldric_no_threats,
    case_neg_aldric_no_troop_knowledge, case_neg_aldric_no_war_outcome,
    case_neg_captain_sorn_no_gossip_frame, case_neg_captain_sorn_no_warmth,
    case_neg_lira_no_noble_succession, case_neg_mira_no_court_politics,
    case_neg_mira_no_guild_secrets, case_neg_mira_no_tactical_details,
    case_neg_old_henryk_no_war_timeline, moderation_everyone_01/02/03
  ```
  `make check-dead-keywords` reports the same shape (237 dead terms) and **exits 0**; the Makefile
  comment at `:167-170` describes it as "a work-list", and ISSUE-157 has deferred triage of ~200 of
  them since 2026-08-14.

  The three `moderation_everyone_*` cases are the clearest instance: they forbid `gore`, `torture`,
  `pornography`, `mutilate`, `beheading`, `explicit`, `adult content` — none of which a fantasy-tavern
  NPC on `qwen2.5:7b` has ever emitted in 975 sampled responses. They are 100% pass by construction
  and contribute three rows to every base rate.
- **Cost of inaction:** these 18 expectations are the mechanism behind CR-L03-01's 1.000 null rate on
  the YAML guard set. Until they can fail, adding cases only raises Pe and lowers κ further.
- **Fix sketch:** retire any `keyword_none` list with zero corpus hits, or replace it with a
  `tone_judge`/`affirms_judge` assertion the model can actually violate. Wire
  `check-dead-keywords` to fail (not report) once triaged, pointed at the newest corpus.
- **Effort:** M
- **Removes:** ~18 expectation blocks; 3 case files (`moderation_everyone_*`) are pure subtraction.
- **Blast radius:** `evals/cases/*.yaml`, `check_dead_keywords`, every base-rate table in the docs.

### [CR-L03-09] A third of the case corpus has never been scored, and the capability headline rests on 16 cases of which 6 are hedge-passable

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** 92 cases on disk; 30 (32.6%) appear in no generation. All 30 are the `case_pos_evk_*`
  / `_cause_` / `_prov_` / `_var_` files dated 2026-08-27 — the "30 harder cases" from the last two
  commits. Newest generation `k3_77688e7_regen1` (2026-08-25) contains 103 case ids of which 16 are
  `case_pos_*`.

  The capability headline over the 16 that did run is `capability_rate 0.625`,
  `95% CI [0.386, 0.815]` (`summary.summarize_from_dir`). `make hedge-probe` names six cases a
  knowledge-free canned hedge already passes, and **all six are among those 16** — a 0.375 floor
  (ISSUE-146). A measurement of 0.625 with a CI reaching down to 0.386 sits essentially on its own
  null floor.
- **Cost of inaction:** the 30 new cases are the fix for exactly this and produce no number; the
  battery they were meant to replace continues to generate the published capability rate. Authoring
  ahead of measuring is how the last four weeks of eval work produced no change in what is known.
- **Fix sketch:** run one generation over the full 92-case set before authoring anything further;
  publish the capability rate only over cases the hedge probe cannot pass.
- **Effort:** M (one generation run)
- **Blast radius:** a new `gen_id`, a second trend row (which incidentally unblocks CR-L03-05).

### [CR-L03-10] Judge verdicts flip on wall-clock latency, and an unparseable verdict is recorded as a substantive NO

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** three identical calls to `matchers._run_binary_judge` at `temperature 0.0`, same
  text, same criteria, this session:
  ```
  0 score= True   ''                24.4 s
  1 score= True   ''                30.6 s
  2 score= None   'infra_failure'   32.8 s
    binary_judge_infra_failure model=mixtral:8x7b timeout_s=30.0 error=ReadTimeout('timed out')
  ```
  `evals/judge_config.py:DEFAULT_JUDGE_TIMEOUT_S = 30.0` sits inside the latency distribution of the
  default judge on this machine, so whether a record is scored or dropped depends on machine load.
  The request also carries no `seed` (`evals/matchers.py:245-249`).

  Separately, `evals/matchers.py:151-157`: a reply that does not begin `YES`/`NO` returns
  `(False, "unparseable verdict")` — a **fail**, not an inconclusive. `_run_binary_judge`'s own
  docstring promises `score=None` for anything that is not a real verdict; a garbled model reply
  breaks that contract silently and lands in the pass rate as a substantive NO.
- **Cost of inaction:** a run's guard rate depends on how busy the box was. `run_status.json`
  records `repeat_flips: 19/115 records` at k=3, some fraction of which is this rather than model
  sampling.
- **Fix sketch:** raise the default timeout above the measured p99 for the configured judge (or
  measure it at preflight and refuse), pass `"seed"` in the Ollama options, and route unparseable
  replies to `score=None` with one bounded retry.
- **Effort:** S
- **Blast radius:** `evals/judge_config.py`, `evals/matchers.py`, `evals/judge_panel.py`, and the
  inconclusive-rate gate's threshold.

### [CR-L03-11] Reproducibility is measured at 0.628 against a 0.95 gate, recorded NOT_MET, and gated by nothing

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `evals/seed_reproduction.json` — `"rate_records": 0.6276`, `"rate_calls": 0.625`,
  `"n_records": 145`, `"gate": 0.95`, `"verdict": "NOT_MET"`, `"measured_at": "2026-08-14"`,
  `"generation_model_digest": null`, `"ollama_version": "0.32.9"`. The current generation records
  `"ollama_version": "0.32.15"` — the runtime moved and the measurement was not repeated.
  `grep -rn seed_reproduction Makefile .github/workflows/` finds no gate.

  `docs/EVAL_METHODOLOGY.md` §3 cites a *different* number for the same property — DEC-176's
  "byte-identical reproduction as low as **4.2%** at `max_tokens=512`". Both are quoted as measured;
  neither is reconciled with the other.
- **Cost of inaction:** with 37% of records differing between two runs at a fixed seed, the
  6.4 pp effects the regression gate is tuned for are inside the reproduction noise. Any before/after
  measurement on this harness is a single noisy draw presented as a value.
- **Fix sketch:** re-measure under the current `ollama_version`, record the model digest (not
  `null`), and either raise `k` until the per-record CI is narrower than the gate's MDE or state
  plainly in the report that single-run deltas are not evidence.
- **Effort:** M
- **Blast radius:** `evals/seed_reproduction.json`, `scripts/seed_reproduction_probe.py`,
  `docs/EVAL_METHODOLOGY.md` §3, the MDE preflight from CR-L03-03.

### [CR-L03-12] Subtraction: the sequence subsystem has produced no measurement, and its policy doc describes a different program

- **Severity:** LOW
- **Confidence:** Likely
- **Kind:** Waste
- **Evidence:** `evals/sequence_fidelity.py` + `sequence_order_effect.py` + `sequence_rates.py` +
  `sequence_records.py` + `sequence_reset.py` + `sequence_runner.py` = **808 lines**, wired to
  `make eval-sequence` (`Makefile:461`). `find . -name "*sequence*" -not -path "*/tests/*" -not -name "*.py"`
  returns only mypy cache entries — **no committed artifact**, no report, no trend field. Seven of the
  18 normative claims in `docs/SEQUENCE_STATS_POLICY.md` diverge (see the table above), including
  three describing behaviour that does not exist (the FULL-fidelity diagnostic, the 0.05
  significance rule, the §4.3 warning block) and one where the "live per-repetition receipt" is a
  static tuple re-read from `evals/reset_fidelity.json` (`evals/sequence_reset.py:75-85`).
  `docs/REASONING_DIMENSIONS.md` records dimension D5 (multi-round coherence, `case_seq_*`) as
  "declared only — no file exists"; 0 such cases exist. The subsystem's consumer has not been built.
- **Cost of inaction:** 808 lines plus a 227-line policy doc that must be maintained, reviewed and
  kept honest by `check-harness`, in exchange for zero decisions. It will drift further from the doc
  every month.
- **Fix sketch:** either author the `case_seq_*` battery in EVAL-P27 and commit a sequence artifact,
  or move both the module set and the policy doc to `archive/` and re-derive them when D5 is
  actually being measured.
- **Effort:** S to archive; L to complete.
- **Removes:** ~808 lines / 6 files + 227 doc lines, if archived.
- **Blast radius:** `make eval-sequence`, `docs/RESET_FIDELITY.md` cross-references,
  `evals/scenario_adapters*.py`, `evals/world_map.py`.

---

## What is genuinely good here, for calibration

This lens is required to be sceptical, so the counterweight belongs in writing. Several things in
`evals/` are better than most production eval harnesses:

- The judge≠generator invariant is **enforced at import** with a typed exception, per panel seat
  (`evals/judge_config.py:114-165`), not asserted in a docstring.
- The single-rater tautology was detected by the harness itself and it **refuses to print a
  fabricated agreement number** for it (`evals/calibration_records.py:49-58`, and the four
  `N/A (single rater)` lines in the calibration output).
- The κ bootstrap resamples **case clusters**, not rows, with a stated √k justification
  (`docs/STATISTICS_POLICY.md` §2c, `evals/calibration.py:469`).
- The FWER disclosure is printed unprompted on every calibration run.
- `evals/mde.py` is a genuinely unusual artefact: a module whose whole job is to tell you a planned
  experiment is pointless before you spend ten hours on it, with its weakest assumption (κ as a
  proxy for Youden's J) named in the docstring as the weakest link.
- `evals/synthetic_label_guard.py` prevents mock/oracle labels from ever overwriting human verdicts.
- The dead-keyword, hedge-responder and base-rate instruments each measure the right thing. The
  failure in this report is almost entirely that they are pointed at the wrong battery, are advisory,
  or are unreachable — not that they are wrong.

The problem is not that this project cannot measure. It is that the measurements it already has
say the battery is inert, and nothing consumes them.
