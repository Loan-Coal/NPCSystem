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

### Enforcement: advisory first, blocking after EVAL-P26

The gate ships with `--enforce advisory`. It computes the full report and the full breach
list, and exits 0. It is switched to `--enforce blocking` in the same commit that lands
EVAL-P26's rebuilt case set.

This is a declared parameter, not a disabled check. The reason is arithmetic: today's
battery measures 0.949, so a blocking gate would fail against the shipped set by
construction, on day one, for a defect the phase that fixes it has not run yet. A gate that
is red before the work starts gets switched off; a gate that reports the number every run
and turns red on a declared date does not. The report is byte-identical in both modes —
only the exit code differs.

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
