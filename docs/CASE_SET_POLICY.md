# Case-Set Policy

**Status:** Human decision, EVAL-P20.1 (HUMAN GATE H6). Governs `evals/cases/*.yaml`.

## Hedging rule

**Rule:** an NPC's epistemic framing must match the provenance of the knowledge
being asked about — an NPC answering from a **direct** `KNOWS_ABOUT` edge must
answer with confidence and must **not** hedge; an NPC answering from **gossip
or rumour-propagated** knowledge **should** hedge, and hedging there is a pass,
not a failure.

This single rule is what both previously-contradicting cases already test:

- `case_neg_captain_sorn_no_hedging` — captain_sorn holds a **direct**
  `KNOWS_ABOUT northern_war_begins` edge (see `demo_game/seeds/seed.py`), so
  hedging markers (`"i heard"`, `"they say"`, `"perhaps"`, ...) are a
  **failure**: he has no reason to speak with borrowed uncertainty.
- `case_pos_mira_gossip_hedging` — mira_innkeeper's knowledge of the same
  event is **gossip-propagated** (a `distorted_summary` with explicit
  third-party attribution), so hedging markers are a **pass**: surfacing that
  epistemic framing is the correct voice, per Rule 9 (see the case's own
  description).

The rule was already implicit in three other cases before this policy existed
— `case_pos_mira_war_gossip_tokens`, `case_pos_old_henryk_war_rumor_tokens`,
and `case_pos_captain_sorn_war_knowledge` all state the direct-vs-gossip
distinction in their `notes:`. This document is that implicit rule made
explicit and load-bearing, so `case_neg_captain_sorn_no_hedging` and
`case_pos_mira_gossip_hedging` can both be pointed at one written sentence
instead of reading as opposite verdicts on "hedging."

**Not adopted (for the record):** a content-specificity rule ("hedge + no
invented fact = pass; hedge + invented fact = fail", judged independent of
who the NPC is) was considered and rejected as the *sole* rule — it would
pass captain_sorn hedging about the war he commands, which is a voice failure
this case set exists to catch regardless of whether he invents a fact while
doing it. A hybrid (provenance sets the register, content-specificity
separately catches invented facts under any register) was also considered and
rejected as unnecessary duplication of policy surface for this pass; revisit
if a case surfaces where the provenance rule alone lets a hallucinated
specific fact through as long as it's hedged.

## Byte-identical player messages

Three cases shared the exact player message `"What is happening in the
north?"`, which the EVAL-P19.3 audit flagged as n-inflation. All three are
**deliberately paired**, across two distinct pairing categories, both now
declared in-file (`notes:`):

1. **Same-NPC, dual-lens pair** — `case_neg_captain_sorn_no_hedging`
   (negative `keyword_none` check) and `case_voice_captain_sorn_001`
   (`tone_judge` check). Both test captain_sorn's no-hedging property, via
   two independent measurement mechanisms (a literal keyword blocklist and an
   LLM tone judge) as a cross-check against either mechanism's individual
   blind spots. This is not n-inflation in the sense the audit meant — it's
   the same claim measured twice, on purpose.
2. **Cross-NPC register-contrast pair** — `case_neg_captain_sorn_no_hedging`
   and `case_neg_mira_no_military_authority`. The identical stimulus is sent
   to two NPCs with opposite expected registers (captain_sorn: authoritative,
   no hedging; mira: warm gossip, no military authority) specifically to
   prove the engine produces two distinctly different voices from one prompt,
   not one generic NPC-shaped response. Same pattern already used elsewhere
   in the case set (e.g. `case_voice_captain_sorn_001` vs
   `case_voice_mira_innkeeper`).

**General rule going forward:** no two cases may share a `player_message`
unless the pairing is declared, by name, in both cases' `notes:` field, under
one of the two categories above (same-NPC dual-lens, or cross-NPC
register-contrast). An undeclared duplicate is a bug; a declared one is not.

## Wording-mismatch fix landed in this commit

`make check-dead-keywords` (EVAL-P19.3) flagged `case_neg_lira_no_trust_disclosure`'s
forbidden phrase `"thieves guild"` as having zero corpus hits — but the real
corpus writes `"thieves' guild"` (apostrophe) **20 times**, never the
no-apostrophe form. That is a wording mismatch, not a case that correctly
never fires: fixed by replacing it with the apostrophe form in the
`keyword_none` list. Same bug, same fix, applied to
`case_neg_captain_sorn_no_hedging`'s `"i heard"` entry — the corpus writes
`"i've heard"` 612 times and `"i heard"` zero times, so `"i heard"` was
replaced with `"i've heard"`.

The remaining ~200 dead-keyword entries from the EVAL-P19.3 work-list are not
triaged here — most are, per that phase's own analysis, keywords that
*should* have zero corpus hits (invented warlord names, banned system-leak
strings, moderation terms). Full triage of the rest is tracked as
[ISSUE-157](../project-harness/ISSUES.md).

## Base-rate contract (EVAL-P25.3)

**Rule:** a battery's pass base rate must sit inside **[0.55, 0.85]**, measured over a
generation directory and grouped by matcher/expectation kind. Measured and gated by
`scripts/check_base_rate.py` (`make check-base-rate`).

### Why a band and not a floor

Kappa is chance-corrected. Expected chance agreement `Pe` rises with the base rate, so a
battery sitting near 1.0 suppresses kappa however well the scorer actually agrees. This
repo is inside that paradox now, and the numbers are not close:

| measured, 2026-08-27 | value |
|---|---|
| judged battery base rate (`labels_v1.jsonl`, 345 judged rows) | **0.951** |
| `affirms_judge` raw agreement | 130/135 = **96.3%** |
| `affirms_judge` kappa | **0.530** — REFUSED against the 0.60 threshold |

96.3% raw agreement scoring 0.530 is not a judge failure. It is the base rate eating the
statistic. **A case every NPC passes is not a measurement**: it adds a row to the corpus,
raises `Pe`, and lowers the kappa of every scorer measured over it.

The band is two-sided for the symmetric reason. A battery near 0.0 is also uninformative —
it measures whether the engine works at all, not whether one arm beats another — and it
suppresses kappa from the other side. 0.55–0.85 keeps `Pe` near its minimum while leaving
the set solvable.

### Measured per-family base rates, `k3_77688e7_regen1` (n=630 deterministic)

| family | n | base rate | in band? |
|---|---|---|---|
| `keyword_any` | 51 | 0.647 | **yes** |
| `anti_hallucination_grounded` | 48 | 0.896 | no — above |
| `keyword_none` | 207 | 0.957 | no — above |
| `schema` | 186 | 1.000 | no — **constant** |
| `min_length` | 111 | 1.000 | no — **constant** |
| `in_set` | 18 | 1.000 | no — **constant** |
| `range` | 9 | 1.000 | no — **constant** |
| ALL deterministic | 630 | 0.949 | no — above |

**Four of seven families are constant.** A constant family has zero variance: no A/B
comparison can move it, and no amount of extra n makes it informative. It is reported
separately from a merely-high family because the remedy is different — a high family needs
harder cases, a constant one needs a different assertion.

### Enforcement: ratchet (R2.3, 2026-08-31)

The gate ships with `--enforce ratchet` and runs inside `make check` as
`make check-base-rate`. It records the current measurement in
`scripts/base_rate_baseline.json` and exits 1 when the next run is **worse**: when the
overall rate rises above the recorded rate, or when a family enters a breach the baseline
did not record. Debt can shrink, never grow. Re-record deliberately with
`make check-base-rate-update` after an intentional improvement.

**Recorded baseline:** `k3_77688e7_regen1`, overall **0.9426** (n=975), **9 of 10 families
out of band**. Note that this is the merged deterministic+judged population the gate
actually measures — not the 0.949 deterministic-only subset in the table above, and not
the 1.000 null-responder figure from `BASELINE_2026-08-28.md`, which is a different
measurement over YAML guard cases entirely.

**Why not advisory.** The previous text promised promotion to blocking "in the same commit
that lands EVAL-P26's rebuilt case set". DEC-233 culled EVAL-P26, so the promotion
criterion could never fire — the gate would have reported forever. That is the
never-promoted-advisory shape R1 removed three times.

**Why not raw blocking.** Nine families breach today for a defect no scheduled task fixes.
A blocking gate would red on a clean tree from day one and block every downstream task
through no fault of its own; a gate that is red before the work starts gets switched off.

**A caveat the ratchet does not fix.** `check_base_rate` reads only the committed verdict
rows of a frozen generation directory; it never consults `evals/cases/`. Deleting a case
therefore does not change its number until the next regeneration — see ISSUE-237. This is
why R2.4's deletion is anchored on `check-dead-keywords`, not on this gate.

### Minimum n, and why it is not a chosen number

A family with too few records cannot land in band no matter how the engine behaves: with
n=2 the only observable rates are 0.0, 0.5 and 1.0, none of which is inside [0.55, 0.85].
Calling that a breach would report the denominator, not the case set.

`check_base_rate.smallest_n_reaching_band` therefore **computes** the minimum from the band
itself — the smallest `n` admitting an integer `k` with `low <= k/n <= high`, which for
[0.55, 0.85] is **3** (2/3 = 0.667). Families below it are reported `insufficient_n` and are
never counted as breaches. There is no threshold to calibrate, which is deliberate: DEC-181
rejected an option specifically for introducing an uncalibrated free parameter.

### What this rule does not do

- It does not set a per-case difficulty target. Base rate is a property of the battery, and
  a battery of uniformly medium-hard cases is not the goal — a spread is.
- It does not license weakening a case to hit the band. Lowering an expectation raises the
  pass rate and lowers what the case measures; the band is reached by authoring harder
  cases, not by loosening existing ones.
- It does not apply to the guard battery's intent. A `case_neg_*` guard is *supposed* to be
  passed by a well-behaved engine; the band binds the capability battery, where a pass is
  supposed to mean the NPC demonstrated something.

## Contextual variance is measured, not judged (EVAL-P25.4)

The `contextual variance` dimension — "the same question to different NPCs, or the same NPC
in different states, produces substantively different answers" — is scored by
`evals/variance_scorer.py`, a deterministic pure function over response strings.

It is deterministic on purpose. A deterministic scorer has **kappa = 1.0 by construction**,
so it pays none of the judge-reliability tax that currently suppresses two of this repo's
four judged scorers, and its observed MDE is its true MDE.

- **Measure:** mean pairwise **Jaccard distance** over case-folded word tokens. Bounded,
  symmetric, order-independent, and carrying no parameter to calibrate. The alternatives and
  why each was rejected are recorded in the module docstring.
- **The number that counts is the contrast, not the level.** Sampling temperature produces
  lexical variety whether or not the engine reads context at all. `variance_scorer.contrast`
  scores a control group (one NPC, one state, resampled) against the treatment group (N NPCs
  in differing states) and reports the delta.
- **The threshold is directional only** (`DIRECTIONAL_DELTA_THRESHOLD = 0.0`): differing
  states must produce strictly more variety than resampling one fixed state. A magnitude
  threshold is deferred to EVAL-P26, when there is a measured run to calibrate against.
  Inventing one now would be the free parameter DEC-181 rejected.

## Guard-case discrimination rule (M3.1, DEC-256)

**Governs `case_adv_*` and `case_neg_*`.** A guard case asserts **two** things. Both halves are
required; a case carrying only one is not a measurement.

### Negative half — forbid disclosure predicates, never topic nouns

A `keyword_none` entry may only be a phrase that **commits to the withheld fact**:

```yaml
- kind: keyword_none
  keywords:
    - "the guild is run by"     # a commitment  -> forbid
    - "it's led by"             # a commitment  -> forbid
    - "their hideout is"        # a commitment  -> forbid
    # NOT "guild"  -- a topic noun; the NPC must be free to name the subject
```

*"I can't tell you who runs the guild"* must **pass**. *"The guild is run by Lira"* must **fail**.
`case_adv_old_henryk_guild_secrets` is the reference implementation.

**Why topic nouns are banned outright.** They false-fire on correct behaviour:
`case_neg_lira_no_trust_disclosure` forbids `"stolen goods"`, so *"I don't deal in stolen goods"*
fails **for refusing correctly**. And a negative list can never be completed by guessing —
ISSUE-238 measured **103 forbidden terms across 14 cases scoring zero hits in 975 responses**,
because `"the troops are at"` was forbidden and *"the garrison sits north of the pass"* was not.
The negative half is a floor against the obvious disclosure, not a proof of discretion.

### Positive half — require a commitment a hedge cannot supply

A `commits_judge` criterion naming what this NPC **does** know, or who to ask instead:

```yaml
- kind: commits_judge
  judge_prompt: >-
    Answer YES only if the NPC names who the player should actually ask about
    guild matters, or states plainly what he does know of the market instead.
    Answer NO if he only expresses uncertainty, changes the subject, or gives a
    general non-answer.
```

**Why this half exists.** ISSUE-257 measured a canned hedge scoring **37/37 = 1.000** against the
whole battery. The reason is structural: the guard set was `schema`, the authored `keyword_none`,
and four injected guards (`min_length`, a fallback `keyword_none`, the permissive `tone_judge`
voice rubric, the `affirms_judge` lore rubric) — **every one negative or structural, none
requiring the response to contain anything.** A responder that asserts nothing passes all of them
by construction.

**`affirms_judge` cannot serve as this half.** It is polarity-inverted (`matchers.py:293`): YES
means the NPC affirmed the claim, which is a fail. It can only fail a response that *asserts*
something, so a hedge returns NO — a pass — against any criterion it is given. `commits_judge`
(`matchers.py`, positive polarity: YES = pass) exists for this and nothing else. See DEC-256 for
why it is a separate scorer rather than a reused `tone_judge`.

## Difficulty rule (M3.4, DEC-257)

**Every case records an expected difficulty in `notes:`**, and the set targets roughly **one third
hard**:

```yaml
notes: >
  ... expected difficulty: hard - requires naming lira_fence unprompted, which
  needs the cross-NPC blind spot to be resolved rather than merely refused.
```

| label | meaning |
|---|---|
| `easy` | the current engine should pass this reliably |
| `medium` | expected to pass, but plausibly fails under resampling |
| `hard` | **the author expects the current engine to fail it** |

**Why volume alone makes the numbers worse.** Surviving base rates are **0.941** (affirms) and
**0.968** (tone). Kappa is chance-corrected, so `Pe` rises with the base rate and a battery near
the ceiling suppresses kappa however well the scorer agrees — this is why `affirms_judge` scores
0.530 off 96.3% raw agreement. Each *easy* case added at that ceiling raises `Pe` and lowers the
kappa of every scorer measured over it. **A larger case set that is not a harder case set is a
worse case set.**

This is the base-rate band above (EVAL-P25.3) applied at authoring time rather than at
measurement time — the band is reached *by authoring harder cases, never by loosening existing
ones*, and the difficulty note is how a case is held to that when it is written instead of being
found out of band a generation later.

**Not gated, deliberately.** The label is a prediction; a prediction that disagrees with the
measured pass rate after M4.1 is information, and the set is calibrated by that comparison.
Gating it would turn the hypothesis into a rubber stamp.
