# Reasoning Dimensions — what a capability case is allowed to claim it measures

**Status:** EVAL-P25.2. Governs every `case_pos_*` file authored from 2026-08-27 onward.
**Reads with:** `docs/CAPABILITY_CASES.md` (the per-case contract — this document does not
replace it), `docs/CASE_SET_POLICY.md` (the hedging and duplicate-message rules),
`docs/ENGINE_EVAL_COVERAGE.md` (which engines a case may be grounded in at all).

## Why dimensions, and why difficulty is the product

The judged battery's pass base rate is **0.951**. Kappa is chance-corrected, so at that
base rate expected chance agreement sits near 0.9 and kappa is crushed even at high raw
agreement: `affirms_judge` scores **kappa 0.530 on 96.3% raw agreement**, and
`refusal_judge` scores 0.247 with a 95% CI that crosses zero. Both are REFUSED against
`docs/SCORER_TRUST_POLICY.md`'s 0.60 threshold.

**A case every NPC passes is not a measurement.** It contributes a row that inflates Pe
and suppresses the statistic. The target band for the battery is **0.55–0.85**
(EVAL-P25.3, `scripts/check_base_rate.py`). Dimensions exist to reach that band on
purpose: each one names a *distinct thing that can go wrong*, and each contract is written
so that the ways of being wrong outnumber the ways of shrugging convincingly.

Difficulty here is not harshness for its own sake. Every dimension below still fails a
case that a *correct* answer would fail — that is what the dual-failure and echo clauses
in `docs/CAPABILITY_CASES.md` enforce, and they apply to all five dimensions without
exception.

## Case-id prefixes are compound, and why

Each dimension takes a prefix **inside** the capability prefix:

| dimension | prefix | authored in |
|---|---|---|
| event knowledge | `case_pos_evk_*` | EVAL-P26.2 |
| causality | `case_pos_cause_*` | EVAL-P26.2 |
| rumour provenance | `case_pos_prov_*` | EVAL-P26.2 |
| contextual variance | `case_pos_var_*` | EVAL-P26.2 |
| multi-round coherence | `case_seq_*` | **EVAL-P27 — declared only, not authored here** |

The plan proposed bare `case_cause_*` / `case_prov_*` / `case_var_*`. They are compound
instead because **every capability gate in this repo keys off the literal string
`case_pos_`**: `scripts/hedge_responder_probe.py::_CASE_GLOB`,
`evals/case_stats.py::_CAPABILITY_PREFIX`, `evals/runner.py`, `evals/summary.py`, and both
`tests/unit/evals/test_capability_coverage.py` and `test_capability_echo_resistance.py`.
A bare `case_cause_*` file would be a case that **no gate checks** — not echo-tested, not
hedge-probed, not counted in the capability rate. Compound prefixes keep every existing
gate binding while still making each dimension greppable and countable. Recorded as
DEC-220.

---

## D1 — event knowledge (`case_pos_evk_*`)

**Claim:** the NPC surfaces a fact it demonstrably holds.

**Assertion contract**

- `relevant_node_ids` names the **one** grounded node the case expects to be surfaced.
- `notes:` opens with `Grounding: <EDGE_TYPE>(<npc_id>, <node_id>).`
- `expected:` is `schema` plus at least one `keyword_any` whose tokens are drawn **from
  that node's own text**, never from `input.player_message`.
- The player message is a fair question a player would ask, and supplies **none** of the
  scoring tokens.

**Fails on refusal** (a deflection carries no fact token) **and on fabrication** (a
different invented fact carries different tokens). **Fails on echo and on the canned
hedge** by construction, because the two vocabularies are disjoint.

**Coverage rule:** every grounding edge type that is seeded in a world
(`KNOWS_ABOUT`, `BELIEVES`, `REMEMBERS`, `PURSUES`) has at least one `case_pos_evk_*` in
that world. `KNOWS_SECRET` is excluded — see `docs/CAPABILITY_CASES.md`, a capability case
grounded in a secret rewards disclosure, which is the guard battery's business.

---

## D2 — causality (`case_pos_cause_*`)

**Claim:** the NPC connects cause to effect, rather than reciting the fact.

This is the dimension that most directly attacks the base rate. Reciting a held fact is
easy; naming its consequence requires the model to have actually read the fact and joined
it to something else in context.

**Assertion contract**

- `relevant_node_ids` names **at least two** grounded nodes: the *cause* node the NPC
  holds, and the *effect* node (a second belief, goal, memory, or event that follows from
  it).
- `input.player_message` asks a **consequence** question — "what does that mean for…",
  "what happens if…", "what are you doing about it" — whose answer is **not present in the
  cause node's text**.
- `expected:` scores `keyword_any` on tokens drawn from the **effect** node only. Tokens
  that appear in the cause node's text are not eligible: an NPC that recites the cause and
  stops must fail.
- `notes:` states both node ids and names which is cause and which is effect.

**Fails on refusal, on fabrication, and additionally on recitation** — which is the whole
point, and is why this dimension is expected to score lowest.

**Coverage rule:** at least one `case_pos_cause_*` per world.

---

## D3 — rumour provenance (`case_pos_prov_*`)

**Claim:** the NPC's epistemic framing matches where its knowledge came from.

This **promotes the existing rule in `docs/CASE_SET_POLICY.md` § Hedging rule**. It is not
a new rule and is deliberately not restated in different words here: an NPC answering from
a direct `KNOWS_ABOUT` edge must answer with confidence and must not hedge; an NPC
answering from gossip- or rumour-propagated knowledge **should** hedge, and hedging there
is a pass. Read that section; this one only says how to encode it in a case.

**Assertion contract — direct provenance** (`knowledge_state: fact` or `witnessed`,
`distortion_level: 0`):

- `schema`, plus `keyword_any` on tokens from the fact's own text,
- plus `keyword_none` on hedging markers.

**Assertion contract — gossip provenance** (`knowledge_state: rumor`, or a
`distorted_summary` with third-party attribution):

- `schema`, plus `keyword_any` on tokens from the **distorted summary's** text,
- plus a second `keyword_any` on hedging markers.

Both expectations must pass. That is what makes a gossip provenance case ungameable: the
canned always-hedge responder satisfies the hedging list and fails the fact list, while a
confident fabrication does the reverse.

**Hedging marker lists are drawn from the corpus, not from intuition.** The committed
corpus writes `"i've heard"` 612 times and `"i heard"` zero times (EVAL-P19.3
dead-keyword finding, applied in `case_neg_captain_sorn_no_hedging`). A marker with zero
corpus hits is a check that never fires.

**Coverage rule:** each world with both a direct and a gossip-propagated knowledge edge
gets one case of each polarity, and the two name each other in `notes:`.

---

## D4 — contextual variance (`case_pos_var_*`)

**Claim:** the same question, asked of different NPCs or of one NPC in different states,
produces substantively different answers.

**Assertion contract**

- A variance case is never alone. It is a **declared set of two or more** case files that
  share a byte-identical `input.player_message`.
- Each member names every other member by case id in `notes:`, under
  `docs/CASE_SET_POLICY.md`'s **cross-NPC register-contrast** category. An undeclared
  duplicate message is a bug; a declared one is the measurement.
- Each member scores `keyword_any` **only** on tokens its own NPC's grounded material
  supplies — no token may be scoreable from any other member's grounding.
- Consequence, and the actual assertion: **pasting member A's correct response into member
  B's expectations must fail.** That is what "substantively different" means here, and it
  is checkable with no judge at all.

**Relationship to the variance scorer.** `evals/variance_scorer.py` (EVAL-P25.4, Track A)
computed pairwise dissimilarity across responses to one stimulus; it was deleted in the
measurement-remediation trim for having no production caller (see
`docs/CASE_SET_POLICY.md`'s retraction note). This dimension does not depend on it — it
supplies its own stimuli and asserts per-NPC groundedness directly via `keyword_any`.

**Coverage rule:** at least one declared variance set per world.

---

## D5 — multi-round coherence (`case_seq_*`) — DECLARED ONLY

**Claim:** across several turns, the NPC stays consistent with what it already said, with
what the player already told it, and with what it holds in the graph.

**This dimension is declared here so the taxonomy is complete. It is NOT authored in
EVAL-P26.2, and no `case_seq_*` file exists.** It is authored in **EVAL-P27**.

The reason is structural, not scheduling. `docs/SEQUENCE_SCHEMA.md` v2 states that the
single-turn `GenerationRecord` shape cannot carry per-turn retrieval capture, per-turn
judging, or branching "without lossy workarounds", and its implementation is "a separate
programme". What exists today is six scenario adapters
(`evals/scenario_adapters*.py` — `gossip_chain`, `grief_persistence`, `reputation_drift`,
`memory_consolidation`, `time_passage`, `mood_contagion`) that each return **a single
boolean**. There is no per-turn judging anywhere in the repo. A multi-round case authored
against `evals/cases/*.yaml` today would therefore be scored on its last turn only, which
is not the claim above.

When EVAL-P27 lands it also owns the statistics policy: `docs/SEQUENCE_STATS_POLICY.md` §3
requires a metric whose reset-fidelity requirement is unmet to be **absent**, not
caveated.

---

## What every dimension inherits

From `docs/CAPABILITY_CASES.md`, without exception and without restatement:

1. **Grounded fact** — verified in the live graph through the typed admin endpoints
   `GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id}`, before the expectation is
   written. The generic graph reader returns empty for seeded inner life (ISSUE-148), so
   "the graph says this NPC has nothing" is not a safe conclusion to draw from it.
2. **Fair eliciting message** — no leading, no insider phrasing, no supplying the answer.
3. **Dual-failure expectation** — refusal fails and fabrication fails.
4. **Ungameable by a knowledge-free response** (EVAL-P20.2) — fails against an echo of its
   own `player_message` and against the reference always-hedge responder. Measured by
   `make hedge-probe` and `tests/unit/evals/test_capability_echo_resistance.py`.
5. **Tokens from the fact, never from the prompt.** The audit that produced this rule
   found one canned hedge passing 6 of 7 capability cases precisely because the case
   scored on vocabulary it had itself supplied.
