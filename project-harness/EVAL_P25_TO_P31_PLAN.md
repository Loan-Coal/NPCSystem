# EVAL-P25 → EVAL-P31 Plan — the golden set rebuild, judge repair, and the prompt arm

**Written:** 2026-08-27, planning session. No roadmap checkboxes ticked, no code written,
no generation spend.
**Commissioned by:** the maintainer, after a review of what P0–P9 built, against three
stated goals: (a) accurate metrics + A/B on retrieval AND prompt versions, (b) a golden
set that is accurate and ready, (c) fine-tuning — **parked by explicit decision**, see §7.
**Method:** every status claim below was re-measured in this session against the working
tree at `501fe56`, not read off a checkbox. Commands are quoted so they can be re-run.

---

## Section 0 — the question the maintainer asked, and the honest answer

> *"For metrics I've already explained in depth the golden set + labels I want. I assume
> this will satisfy our kappa requirement. If it is not the same tell me now."*

**It is not the same. It moves two of the four inputs to kappa, and not the other two.**

Kappa is a property of four things, not one:

| input | what the stated plan does to it | verdict |
|---|---|---|
| **n** (labelled rows) | raises it, a lot | **helps, materially** |
| **base rate** of the judged battery | pushes it off the ceiling | **helps, and this is the biggest lever** |
| **judge criteria wording** | rewrite is scheduled *after* the set | **helps, correctly sequenced** |
| **reliability of the reference labels** | **unaddressed** | **does not help — see P28** |

### Why n helps

`refusal_judge` is measured at kappa 0.247 with 95% CI **[-0.123, 0.703]** at n=75. The
interval crosses zero: the current corpus cannot distinguish that judge from chance.
Widening the case set widens n, which narrows the interval around whatever the true kappa
is. That is a real gain and it is the cheapest one.

### Why the base rate helps — the strongest argument for the stated plan

Kappa is chance-corrected. At the battery's measured pass base rate of **0.951**, expected
chance agreement Pe is near 0.9, so kappa is crushed even when raw agreement is high. This
is the well-known kappa paradox, and this repo is sitting squarely inside it:
`affirms_judge` shows **127+3 = 130 of 135 raw agreement (96.3%)** and still scores
kappa 0.530, because almost every row is a pass.

Measured in-repo evidence that the base rate is the lever: over
`evals/generations/k3_77688e7_regen1/deterministic_judged.jsonl`, the matcher family whose
base rate is furthest from the ceiling is `keyword_any` at **0.647**, while the LLM-judged
battery sits at 0.951. A case set that is genuinely varied and genuinely hard — the one
described — pulls the base rate toward 0.6–0.8, where the *same* raw agreement yields a
substantially higher kappa.

**So the intuition is right, and for a reason worth writing down: harder cases do not just
give the judge more to do, they repair the statistic itself.**

### Why it is nonetheless not sufficient

**1. The reference labels have never had a second reader.** Measured this session by
running `python -m evals calibrate`:

    pre_label vs human_verdict, all four scorers:  0 disagreements in 393 of 393 rows
    the tool's own output: "single rater -- every pre_label on this axis was recorded by
    a human, not an independent model; this compares the adjudicator to themselves."

Every kappa in this repo is therefore *judge vs one person's single pass*. There is no
estimate of how reliable that person's pass was. Adding 400 more single-pass labels
produces a larger corpus with exactly the same unknown at its centre.

**Using Opus to adversarially review the CASES is not the same as using it to
independently LABEL the responses.** The first improves the stimuli; the second is what
produces a reference side you can defend. Both are wanted; only the first was stated.

**2. `refusal_judge`'s defect is in the point estimate, and n cannot move a point
estimate.** ISSUE-141 diagnosed the exact cause and it is not sample size: the criteria
file spends lines 15–21 enumerating surface phrase markers and only lines 22–23 stating
the substantive rule, and the marker list contains "I haven't heard" while the engine's
own hedging idiom is "I've heard..." followed by an invented fact. Near-identical surface
form, opposite meaning. DEC-172 then recorded that the wording lever was exhausted at n=3
structurally distinct rewrites. A bigger set makes the *measurement* of that defect
sharper; it does not fix it. The plan for it is P28.3, and it needs the bigger set to
validate against — which is exactly the sequencing the maintainer chose.

**Net: the stated plan is right and is kept whole. This plan adds one phase (P28.1) it did
not contain, and that phase is what makes every kappa number afterwards defensible.**

---

## Section 1 — measured state, verified this session

Everything below was run against the working tree, not recalled.

### What is built and green

- **Retrieval A/B is done.** Three arms with measured exposure (`no_rag`, `narrow_rag`,
  `no_memories`), all 8/8 on CONTENT, DEC-214. `make eval-arm-probe` exits 0 on all four
  gates. Paired interleaved generation (`evals/paired_arms.py`), McNemar comparison,
  comparability refusal, corpus fingerprint.
- `pytest tests/unit/evals/test_capability_coverage.py
  tests/unit/evals/test_capability_echo_resistance.py
  tests/unit/evals/test_case_annotations.py tests/unit/config/test_declared_arm_exposure.py
  tests/unit/config/test_shipped_retrieval_profiles.py` → **50 passed**.
- `compare.py` **already unifies both verdict sources** (`verdict_sources.load_unified_rows`,
  `compare.py:376`). The deterministic matchers are not a separate pipeline that needs
  building; they are already in the headline path.

### The deterministic-matcher measurement DEC-214 left open

DEC-214 called this "the unexplored path… worth a future phase, costs an hour and no LLM
time." The data was already on disk. Measured over
`evals/generations/k3_77688e7_regen1/deterministic_judged.jsonl` (n=630):

    matcher                    n   base rate   MDE @ 3 comparisons   (kappa=1.0 by
    keyword_any               51      0.647          9.1pp            construction, so
    anti_hall_grounded        48      0.896          9.4pp            observed MDE IS
    keyword_none             207      0.957          4.5pp            the true MDE)
    min_length               111      1.000          -- no variance
    schema                   186      1.000          -- no variance
    in_set                    18      1.000          -- no variance
    range                      9      1.000          -- no variance
    ALL deterministic        630      0.949          2.6pp

**Three of seven families have real variance; four are constant.** DEC-214's worry was
correct but partial — it feared all of them were constant.

Sensitivity, because `p_d = 0.0407` was calibrated at base rate 0.951 and `keyword_any`
sits at 0.647 where discordance is plausibly higher:

    p_d      n=51     n=48     n=207    n=630
    0.0407    9.1pp    9.4pp    4.5pp    2.6pp
    0.15     17.5pp   18.1pp    8.7pp    5.0pp
    0.25     22.7pp   23.4pp   11.2pp    6.4pp

Against the LLM judges' 26.2pp / 32.9pp, the deterministic families remain the better
instrument across the whole plausible band.

**This is recorded, not acted on.** The maintainer chose judge repair over a deterministic
pivot. The number is preserved here so the choice stays reversible: if P28 fails to lift
kappa above the SCORER_TRUST_POLICY threshold, this table is the fallback and it does not
need re-measuring.

### What is missing or broken

| finding | evidence |
|---|---|
| **Prompt-version A/B does not exist** | `prompt_builder.py:37` — `_PROMPT_PATH` is a module-level constant. `DialogueRequest` has `retrieval_profile` and no prompt field. `paired_arms` makes arm identity *be* the retrieval profile. `RunConfig.dialogue_prompt_hash` only *detects* a prompt change and makes runs incomparable. |
| **All 393 labels are on the retired generation** | every row is `gen_id k3_73e6c36`; zero on `k3_77688e7_regen1`. |
| **`check_label_survival` reports FROZEN against a generation whose text is entirely different** | `python scripts/check_label_survival.py --transcript evals/generations/k3_77688e7_regen1/outputs.jsonl` → `survive: 393, drift: 0, FROZEN`. Correct per DEC-181 (criteria-only drift), and see §2.C. |
| **Two of four scorers are suppressed by the repo's own trust policy** | `refusal_judge` kappa 0.247 → REFUSED (hidden). `affirms_judge` kappa 0.530 → REFUSED (restricted). Only `anti_hallucination_grounded` (kappa 1.000, deterministic) is publishable. `tone_judge` kappa 0.849 with CI [-0.010, 1.000]. |
| **No valid A/B baseline on disk** | ISSUE-186 — `k3_73e6c36` predates `harness_version` and `seed`, so `compare` refuses every pairing with it. Regeneration #1 (EVAL-P20.4) has never run. |
| **Capability battery is 16 against a target of ~35** | ISSUE-147. Village and tavern worlds have zero capability coverage. |

---

## Section 2 — three constraints that shape everything below

### A. "Multiple rounds conversation coherence" cannot live in `evals/cases/*.yaml`

`docs/SEQUENCE_SCHEMA.md` v2 is explicit: **"Design complete — implementation is a separate
programme."** Its own rationale states that the single-turn `GenerationRecord` shape cannot
carry per-turn retrieval capture, per-turn judging, or branching "without lossy workarounds."

What exists today is six scenario adapters (`gossip_chain`, `grief_persistence`,
`reputation_drift`, `memory_consolidation`, `time_passage`, `mood_contagion`) that each
return **a single boolean**. There is no per-turn judging anywhere in the repo.

So multi-turn coherence is a **second track with its own schema, its own runner, and its
own statistics policy** (`docs/SEQUENCE_STATS_POLICY.md`, which mandates automatic metric
suppression when reset fidelity is PARTIAL). That is EVAL-P27, and it is the largest single
phase in this plan. It cannot be folded into case authoring.

### B. "Every single engine in depth and width" is 40+ packages, and most are not judgeable

`ls src/npc_engine/engines/` lists 40+ domain packages. A judge battery can only measure
what reaches player-visible NPC speech. `idempotency`, `ports`, `contracts`, `tts`,
`embedding_invalidation` are not observable in dialogue and already have integration tests;
putting them in a judge battery would manufacture cases that pass unconditionally and drag
the base rate back toward 1.0 — the exact thing §0 says to avoid.

**Therefore P25.1 is a classification gate before any authoring.** This is DEC-214's own
rule — *measure supply before declaring an arm* — applied to cases: **measure observability
before authoring a case.** Authoring 200 cases against an untested assumption about what is
observable is the same failure DEC-214 spent a session remediating.

### C. DEC-181 and the P10 plan note contradict each other, and this plan resolves it

- **DEC-181** (accepted via AskUserQuestion, with evidence): trust is gated on
  `criteria_sha256` only. A human verdict survives paraphrase. Rationale: byte-identical
  reproduction was measured as low as 4.2%, and normalization recovered **0 of 746**
  non-identical repetition pairs — the differences are real word-level content, not
  formatting noise.
- **The P10 plan** says: *"Record explicitly that the pre-P10 labels are retired."*

Both are in the repo; they cannot both govern.

**Resolution proposed here (to be recorded as DEC-216 when P28.1 lands): DEC-181 stands for
within-battery re-measurement and is NARROWED for cross-arm comparison.** The reasoning:
DEC-181's own justification is that a human verdict is a *case-level* judgment of how
criteria apply — which is exactly right for calibrating a judge, and exactly wrong for
scoring an arm, because if an arm changes what the NPC says (which is the entire point of
the arm) then carrying a verdict recorded on arm-A text onto arm-B text assumes the answer.

Concretely: labels stay valid as calibration evidence across regenerations; they are never
used as the verdict source for an arm comparison. The arm comparison scores fresh, every
run, through `matchers.py` — which DEC-181 already notes it does not weaken.

---

## Section 3 — Program 4: the golden set rebuild and judge repair (EVAL-P25 → P28)

### Phase EVAL-P25 — the coverage contract, before a single case is authored

**Rationale:** §2.B. Supply before declaration, applied to cases.

- **EVAL-P25.1 — Engine observability audit.**
  Files: `create docs/ENGINE_EVAL_COVERAGE.md`, `create scripts/check_engine_coverage.py`,
  `create tests/unit/scripts/test_check_engine_coverage.py`.
  Classify every package under `src/npc_engine/engines/` into exactly one of:
  `dialogue_observable` (reaches NPC speech, judgeable), `state_observable` (verifiable only
  through the graph, belongs in a deterministic/scenario check), `not_observable`
  (infrastructure — out of scope, and say why).
  **Gate:** `check_engine_coverage.py` fails when a package exists with no classification
  row. Wire into `make check`.
  **RED anchor:** add a fake package fixture and assert the gate fails before the row exists.

- **EVAL-P25.2 — Reasoning-dimension taxonomy.**
  Files: `create docs/REASONING_DIMENSIONS.md`, `edit docs/CAPABILITY_CASES.md`.
  Declare the dimensions the maintainer named, each with an assertion contract in the style
  `CAPABILITY_CASES.md` already uses for `case_pos_*`: **event knowledge**, **causality**
  (does the NPC connect cause to effect, not just recite the fact), **rumour provenance**
  (does epistemic framing match the knowledge's origin — this already has a written rule in
  `docs/CASE_SET_POLICY.md`, so it is a promotion not an invention), **contextual variance**
  (does the same question to different NPCs, or the same NPC in different states, produce
  substantively different answers), **multi-round coherence** (deferred to P27 — declared
  here so the taxonomy is complete, authored there).
  Each dimension gets a case-id prefix (`case_cause_*`, `case_prov_*`, `case_var_*`) and a
  coverage rule.

- **EVAL-P25.3 — The base-rate contract. This is the kappa lever, made into a gate.**
  Files: `create scripts/check_base_rate.py`,
  `create tests/unit/scripts/test_check_base_rate.py`, `edit docs/CASE_SET_POLICY.md`.
  Declare a target pass base rate per battery (proposed: **0.55–0.85**) and gate it over a
  generation directory. **A case every NPC passes is not a measurement** — it inflates Pe
  and suppresses kappa, which §0 shows is what happened to `affirms_judge` at 96.3% raw
  agreement and kappa 0.530.
  **Design note:** the gate must be advisory-with-report on first run and blocking only
  after P26 lands, or it fails against the current set by construction.
  **RED anchor:** feed it the current `k3_77688e7_regen1` (base 0.949) and assert it reports
  out-of-band.

- **EVAL-P25.4 — `contextual variance` needs a metric, not a judge.**
  Files: `create evals/variance_scorer.py`,
  `create tests/unit/evals/test_variance_scorer.py`.
  "Replies should be incredibly varied based on context and situation" is measurable
  deterministically: send the same `player_message` to N NPCs in differing states, and score
  pairwise dissimilarity of the responses. This is a **deterministic scorer with kappa=1.0
  by construction** (§1) and it directly measures the maintainer's stated goal without
  paying any judge-reliability tax. Cheap, and it is the one new metric in this plan that
  can resolve an effect today.

### Phase EVAL-P26 — author the set, adversarially

- **EVAL-P26.1 — The Opus adversarial case reviewer.**
  Files: `create evals/case_adversary.py`, `create prompts/eval/case_adversary.yaml`,
  `create tests/unit/evals/test_case_adversary.py`, `edit Makefile` (`make review-cases`).
  Takes a candidate case file and returns structured findings against the
  `CAPABILITY_CASES.md` contract: is the prompt leading? is the grounded fact real in the
  graph? is the expectation echo-gameable? is the token set drawn from the fact rather than
  the player message? Reuses the existing `hedge-probe` and
  `test_capability_echo_resistance` machinery rather than re-deriving it.
  **Prompt lives in `prompts/eval/`** — no prompt strings in Python (CLAUDE.md).
  **This is where "adversarially review it using Opus" lands.** It reviews *cases*; P28.1
  is the separate thing that labels *responses*.

- **EVAL-P26.2 — Authoring pass, per dimension per observable engine.**
  Governed by the P25.1 table and the P25.2 taxonomy. Ratchet clause in the style of
  EVAL-P20.2 so it need not land in one sitting. Closes ISSUE-147 en route.

- **EVAL-P26.3 — Coverage + adversary gate.**
  Files: `edit tests/unit/evals/test_capability_coverage.py`.
  Every authored case must pass the P26.1 adversary and the existing echo/hedge resistance
  tests before it counts toward coverage.

### Phase EVAL-P27 — the multi-turn track (the "separate programme" SEQUENCE_SCHEMA names)

The largest phase here. Implements `docs/SEQUENCE_SCHEMA.md` v2 for real: per-turn records,
per-turn judging, branching, and the automatic metric suppression
`docs/SEQUENCE_STATS_POLICY.md` mandates when reset fidelity is PARTIAL.

- **EVAL-P27.1** — `SequenceRun`/`Repetition`/per-turn record models to the v2 schema
  (`evals/sequence_records.py` already holds the frozen design; this makes it load-bearing).
- **EVAL-P27.2** — per-turn judging: the judge runs on each turn, not on a scenario boolean.
- **EVAL-P27.3** — conversation-coherence criteria in `prompts/eval/`.
- **EVAL-P27.4** — fidelity-driven suppression, per SEQUENCE_STATS_POLICY §3. A metric whose
  fidelity requirement is unmet is **absent**, not caveated.
- **EVAL-P27.5** *(live, human gate)* — first measured multi-turn run.

**Scoping honesty:** this phase is comparable in size to P0–P8 combined. It should not be
started until P25/P26 have landed, and it is the correct place to stop and re-plan.

### Phase EVAL-P28 — double-blind labelling and kappa repair

**This is the phase the stated plan did not contain (§0).**

- **EVAL-P28.1 — The blind dual-label protocol.**
  Files: `edit evals/label_export.py`, `edit evals/label_import.py`,
  `create evals/interrater.py`, `create tests/unit/evals/test_interrater.py`,
  `edit docs/EVAL_METHODOLOGY.md`, `edit evals/calibration/LABEL_PROMPT.md`.
  Opus labels blind. The human labels blind. Neither sees the other, and neither sees
  `scorer_verdict`. Disagreements go to `make eval-adjudicate` (which already exists and is
  resumable). **Inter-rater kappa on the reference side falls out as a byproduct** — that is
  the number that makes every judge kappa afterwards defensible, and it is the number this
  repo has never had.
  **Gate:** `calibration.py` must REFUSE to report a headline kappa for any scorer whose
  reference rows lack two independent labels — same shape as the existing
  SCORER_TRUST_POLICY refusal, so the machinery already exists.
  **RED anchor:** feed it the current 393 single-rater rows and assert it refuses.
  Record as **DEC-216**, together with the §2.C resolution.

- **EVAL-P28.2 — Re-measure kappa on the new set.** No judge changes yet. This is the clean
  read: what does kappa look like with a proper reference side and a base rate off the
  ceiling?

- **EVAL-P28.3 — Judge criteria rewrite, gated behind P28.2.** The maintainer's sequencing,
  kept. Harsher/more precise `refusal_judge` and `affirms_judge` criteria, validated through
  the existing `make eval-replay-criteria` verb (EVAL-P19.0b exists precisely so a criteria
  rewrite can be validated without a regeneration). **Note DEC-172:** the wording lever was
  recorded as exhausted at n=3 rewrites against the OLD corpus. Against a corpus with a
  proper reference side and a 0.6–0.8 base rate, that finding does not carry over — but if
  three rewrites fail again, that is the signal to take §1's deterministic table instead,
  and this plan says so in advance rather than after.

- **EVAL-P28.4 — Accept or reject against `docs/SCORER_TRUST_POLICY.md` (kappa ≥ 0.60).**
  If a judge still fails, it stays suppressed. The policy is not weakened to fit the result.

---

## Section 4 — Program 5: the first-class prompt arm (EVAL-P29 → P31)

**Governing rule, carried over from DEC-194 and DEC-214:** an arm may not be declared until
its exposure has been measured, and no arm may silently fall back to a default.

### Phase EVAL-P29 — the prompt-variant registry (refactor; byte-identical by construction)

- **EVAL-P29.1 — `prompt_variants:` in `llm_config.yaml`.**
  Mirrors the existing `retrieval_profiles:` block exactly: named variants, **strict
  resolution — an undeclared name is HTTP 400, never a silent fallback**, so a run cannot
  record a variant it did not use. `default` is NOT declared, for the same reason
  `retrieval_profiles` does not declare it: it resolves from the shipped
  `prompts/dialogue/system_v1.yaml` so a no-variant turn stays byte-identical to a
  pre-variant one.
  Files: `edit src/npc_engine/config/llm_config.yaml`,
  `edit src/npc_engine/schema/context_config_models.py`,
  `create tests/unit/config/test_shipped_prompt_variants.py`.

- **EVAL-P29.2 — `prompt_builder` stops loading its prompt at import.** ⚠️ **the refactor.**
  Today `prompt_builder.py:37` resolves `_PROMPT_PATH` at module level. That is a
  module-level load of a stateful resource inside an engine — it also violates CLAUDE.md's
  constructor-injection rule, so this refactor pays down existing debt rather than adding
  any. The variant becomes an injected argument resolved per call.
  Files: `edit src/npc_engine/engines/dialogue/prompt_builder.py`,
  `edit src/npc_engine/engines/dialogue/dialogue_handler.py`,
  `create src/npc_engine/engines/dialogue/prompt_variant_resolver.py`.
  **Risk:** `prompt_builder.py` already carries a 300-line waiver. Splitting the resolver
  into its own module is required, not optional.
  **Log as ISSUE-223** before starting: *"prompt_builder loads its prompt YAML at module
  level, so the dialogue prompt is a process-wide singleton and cannot be varied per turn."*

- **EVAL-P29.3 — The byte-identity pin.** Direct analogue of DEC-194's
  `test_no_profile_and_explicit_default_profile_are_byte_identical`, which is what made the
  retrieval-profile refactor safe. Same shape, same digest discipline.
  Files: `create tests/unit/engines/test_prompt_variant_byte_identity.py`.
  **RED anchor:** assert a no-variant turn and an explicit-default-variant turn produce an
  identical assembled prompt digest. Without this test the refactor is unfalsifiable.

### Phase EVAL-P30 — generalize the arm axis from "retrieval profile" to "arm spec"

**This is the real structural work.** Arm identity is currently *hardcoded to be* the
retrieval profile in at least four places: `paired_arms.arm_gen_id`, the `CaseCollector`
signature, `RunConfig.retrieval_profile`, and `compare`'s comparability check.

- **EVAL-P30.1 — `ArmSpec` model.** A frozen Pydantic v2 model
  `(retrieval_profile: str, prompt_variant: str)`. `arm_gen_id` derives the directory name
  from the spec. **Back-compat is mandatory:** an arm that varies only the retrieval profile
  must produce the *same* directory name it produces today, or every committed artifact and
  every `compare` invocation breaks.
  Files: `create evals/arm_spec.py`, `edit evals/paired_arms.py`,
  `create tests/unit/evals/test_arm_spec.py`.

- **EVAL-P30.2 — `DialogueRequest.prompt_variant`.** ⚠️ **public interface change — needs
  maintainer sign-off per CLAUDE.md before it is written.** Mirrors `retrieval_profile`
  field-for-field, including the strict-resolution docstring.
  Files: `edit src/npc_engine/engines/dialogue/dialogue_models.py`,
  `edit src/npc_engine/api/routes/...`, `edit live_openapi.json`.

- **EVAL-P30.3 — `RunConfig.prompt_variant` and the comparability rule.** A run records the
  variant it ran. `compare._comparability_error` treats two different prompt variants as a
  legitimate ARM difference, not an incomparability — while `dialogue_prompt_hash` continues
  to refuse two runs whose *shipped prompt files* differ. Those are different things and the
  code must distinguish them.
  Files: `edit evals/run_config.py`, `edit evals/compare.py`,
  `create tests/unit/evals/test_prompt_arm_comparability.py`.

- **EVAL-P30.4 — `--arms` CLI.** `--profiles a,b` keeps working verbatim. `--arms` takes
  specs (`retrieval=default:prompt=v1,retrieval=default:prompt=v2`).
  Files: `edit evals/generate_runner.py`, `edit Makefile`.

- **EVAL-P30.5 — Exposure gate for prompt arms. DEC-214's rule, applied.**
  `make eval-arm-probe` gate 4 currently proves two retrieval arms differ in assembled
  context. Extend it: **a prompt arm must be shown to change the assembled prompt before it
  may be declared.** For a prompt arm, exposure is measurable without a single LLM call — it
  is a digest comparison — so this gate is nearly free and there is no excuse for skipping
  it. Also extend `test_declared_arm_exposure` to prompt variants.
  Files: `edit evals/arm_probe_gates.py`, `edit evals/arm_supply.py`,
  `edit tests/unit/config/test_declared_arm_exposure.py`.

### Phase EVAL-P31 — the first prompt A/B *(live; human gate)*

Preconditions inherit P10's twelve gates verbatim, plus: gate 4 green for the prompt arm,
and the P29.3 byte-identity test green.

---

## Section 5 — ordering and dependencies

```
  P25 (coverage contract)  ──►  P26 (author + adversary)  ──►  P28 (dual-label, kappa)
        │                              │                            │
        │                              └────────► P27 (multi-turn)  │
        │                                            (largest)      │
        ▼                                                           ▼
  P25.4 variance scorer                                    P10 / P20.4 regeneration
        (independent, cheap, resolves today)                   becomes meaningful

  P29 (variant registry) ──► P30 (arm axis) ──► P31 (first prompt A/B)
        (independent of Program 4 until P31)
```

**Programs 4 and 5 are independent until P31.** Program 5 touches `src/` and the eval
harness's arm plumbing; Program 4 touches cases, labels and judges. They can proceed in
either order, or in parallel by different sessions — with one hard exception below.

**The P9 fence still binds:** *"no `src/` change lands after P9 goes green; if one does, P9
re-runs."* EVAL-P29.2 and EVAL-P30.2 are `src/` changes. So either they land **before** the
P10 regeneration, or the P10 regeneration happens first and P29/P30 land after it with
`make eval-arm-probe` re-run. **This is a real scheduling decision and it is not made here.**

**Cheapest useful thing first:** EVAL-P25.4 (the variance scorer). It is deterministic,
kappa=1.0 by construction, directly measures "replies should be varied based on context",
needs no labels, no Opus spend, and no engine change.

---

## Section 6 — refactors this plan requires, and what each risks

| refactor | why | risk | mitigation |
|---|---|---|---|
| `prompt_builder` module-level YAML → injected variant (P29.2) | a process-wide prompt singleton cannot be A/B'd | it is the hottest path in the engine; a regression here is a regression in every response | P29.3 byte-identity digest test, written RED first — the exact discipline DEC-194 used |
| arm identity → `ArmSpec` (P30.1) | arm identity is hardcoded as the retrieval profile in ≥4 modules | renaming arm directories invalidates every committed artifact and every `compare` invocation | mandatory back-compat: a retrieval-only arm keeps its current directory name, pinned by test |
| `DialogueRequest` gains a field (P30.2) | per-turn variant selection | public interface with callers outside its module | **stop-and-ask per CLAUDE.md — not to be written without sign-off** |
| `calibration.py` refuses single-rater kappa (P28.1) | every current kappa is single-rater | it will refuse the existing 393-row corpus, i.e. it turns today's headline kappa numbers off | that is the intended behaviour; the refusal shape already exists for SCORER_TRUST_POLICY |
| `evals/sequence_*` becomes load-bearing (P27) | multi-turn needs per-turn judging | largest phase; new schema, new runner, new stats path | stop and re-plan after P26; do not start P27 inside another phase |

---

## Section 7 — deliberately NOT in this plan

- **Fine-tuning (goal c).** Parked by explicit maintainer decision. The blocker is stated
  plainly so it is not rediscovered: **you cannot fine-tune toward a metric that cannot
  resolve a 26pp difference**, and a training set labelled by judges at kappa 0.23–0.28
  encodes those judges' errors as ground truth. Revisit after EVAL-P28.4. When it is
  revisited, the two open architecture questions are recorded here: (1) per-agent LoRA
  adapters over one resident base is the right shape for task specialization without
  load/unload cost, and Ollama cannot hot-swap adapters — that implies llama.cpp or vLLM
  multi-LoRA, which is a serving-stack change, not a training change; (2) the highest-value
  fine-tune target may be **the judge**, not the NPC agents, since kappa is the binding
  constraint on everything — but that needs the P28.1 double-labelled corpus first, so it is
  downstream either way.

- **The deterministic-matcher pivot.** Measured in §1, recorded, not built. It is the
  fallback if P28.3 fails, and §1's table means taking it later costs no re-measurement.

- **Lowering `Settings.RAG_TOP_K`.** DEC-214 records the maintainer's decision to leave the
  default alone. The "ranker never ranks at a supply of 3–8" argument remains real and
  remains for a phase that owns the substrate.

- **ISSUE-213/210 (`need` vs `Need` label split).** DEC-214's fence: before P8 or after P10,
  never in between.

---

## Section 8 — concurrent-session collision noticed while writing this plan (ISSUE-139 live)

At the time this plan was written the working tree carried **uncommitted changes from another
session**: `src/npc_engine/config.py`, `src/npc_engine/config/llm_config.yaml`, a new
`tests/unit/config/test_shipped_window_holds_the_measured_ceiling.py`, and a `probe-ceiling`
Makefile target. Read together they are **EVAL-P10's window trim in progress** — the YAML
comment records a trim to a 12288 window with tier limits 4500/1500/1000, and it claims
**`DEC-215`**.

Two consequences, recorded so neither is rediscovered:

1. **This plan's decision id was moved from `DEC-215` to `DEC-216`** (the double-blind label
   protocol plus the DEC-181 / P10 drift resolution, EVAL-P28.1). The P10 window trim keeps
   `DEC-215`. Nothing in this plan depends on the number.
2. **P10's trim re-arms two dormant defects, and both are in this plan's dependency path.**
   `ISSUE-209` (tier-A selection is not monotone in the cap) was dormant only because P5's
   25,888-token budget meant nothing was ever dropped; a 5158 budget re-arms it — which is
   P10's own gate 11. `ISSUE-214` (byte truncation emits invalid JSON for an over-budget
   PROJECTED payload) was masked for the same reason and fires once compression binds. Any
   golden-set measurement taken after the trim inherits both.

This is ISSUE-139 happening in real time. Nothing in this session touched `src/`.
