# Session prompt — TRACK A: build the golden-set instrument (EVAL-P25.3, P25.4, P26.1)

**Runs in parallel with Track B** (`PROMPT_P25_TRACK_B_CASES.md`). Read
`project-harness/PROMPT_P25_GOLDEN_SET.md` for why the split is safe. **Paste everything below
"PROMPT — copy from here" into a fresh session, in its own git worktree.**

---

## PROMPT — copy from here

You are working on NPC Engine (`c:\Users\lohan\Documents\hackathons\NPCSystem`). Read
`project-harness/CLAUDE.md` first — binding, and it applies to `evals/` and `scripts/` exactly as
to `src/`: strict TDD (failing test first, confirmed failing for the *right reason*), 300-line
non-test file cap, 40-line function cap, module + public function + public class docstrings,
Pydantic v2 for anything crossing a module boundary, no magic numbers or strings, no prompt
strings outside `prompts/`.

### You are TRACK A of two parallel sessions

Track B is concurrently writing `docs/ENGINE_EVAL_COVERAGE.md`, `docs/REASONING_DIMENSIONS.md`,
`docs/CAPABILITY_CASES.md` and new `evals/cases/*.yaml`. **You must not touch any of those.**

**Hard conflict rules — violating these breaks the other session:**

- **Do NOT edit `Makefile`, `project-harness/ROADMAP.md`, `project-harness/ISSUES.md`, or
  `project-harness/DECISIONS.md`.** Both tracks would collide (`.PHONY` is a single continued
  line). Instead write **`project-harness/HANDOFF_TRACK_A.md`** containing: the exact Makefile
  target recipes to add, the ROADMAP checkboxes to tick, and the *full text* of every ISSUES and
  DECISIONS entry you would have written. A serial integration step applies them.
- Your id ranges: **DECISIONS from DEC-216**, **ISSUES from ISSUE-224**. Do not use others —
  DEC-215 and ISSUE-223 are taken, and Track B owns DEC-220+/ISSUE-230+.
- You own `docs/CASE_SET_POLICY.md`. Track B owns `docs/CAPABILITY_CASES.md`. Do not cross.

### Goal

Build three pieces of tooling. Full spec in `project-harness/EVAL_P25_TO_P31_PLAN.md` §3;
checkboxes in `ROADMAP.md` under **Program 4**.

### Why this exists — the paragraph that motivates it

Two of four scorers are suppressed by this repo's own trust policy and cannot be quoted:
`refusal_judge` kappa 0.247, `affirms_judge` kappa 0.530, both REFUSED against
`docs/SCORER_TRUST_POLICY.md`'s 0.60 threshold. `tone_judge` is effectively unanimous and has no
variance to move. DEC-214 concluded EVAL-P10 can produce a *descriptive* result and not a
*significant* one. The maintainer chose to repair the judges and pay the golden-set cost upfront.

### Ground truth, measured 2026-08-27 — spot-check, do NOT re-derive

**If a spot-check disagrees, stop and say so. Do not quietly proceed on a new number.**

- Judged battery pass base rate **0.951**. Kappa is chance-corrected, so Pe is near 0.9 and kappa
  is crushed even at high raw agreement: `affirms_judge` shows 130/135 raw (96.3%) and scores
  0.530. **A case every NPC passes is not a measurement — it inflates Pe and suppresses kappa.**
  This is the single fact EVAL-P25.3 exists to enforce.
- Per-family base rates over `evals/generations/k3_77688e7_regen1/deterministic_judged.jsonl`
  (n=630): `keyword_any` 0.647 (n=51) · `anti_hall_grounded` 0.896 (n=48) · `keyword_none` 0.957
  (n=207) · `schema` 1.000 (n=186) · `min_length` 1.000 (n=111) · `in_set` 1.000 (n=18) · `range`
  1.000 (n=9). **Four of seven families are constant — zero variance, nothing to move.**
- Labels: 393 rows, all `gen_id k3_73e6c36`, and `pre_label` vs `human_verdict` is **0
  disagreements in 393 of 393** — single-rater. Not your problem this session (it is EVAL-P28.1),
  but it is why the base rate matters so much.

### Read, in this order

1. `project-harness/CLAUDE.md`
2. `project-harness/EVAL_P25_TO_P31_PLAN.md` — **§0 first**, then §1 and §3.
3. `docs/SCORER_TRUST_POLICY.md` — the 0.60 threshold and its **refusal mechanism**. P25.3's gate
   should read as a sibling of this, not a new idiom.
4. `evals/matchers.py`, `evals/deterministic_records.py` — the matcher families and scoring.
5. `evals/calibration/OPUS_LABEL_PROMPT.md` + `evals/calibration/README.md` — **the batch/paste
   workflow P26.1 must mirror.** Read before designing anything.
6. `scripts/hedge_responder_probe.py` (`make hedge-probe`),
   `tests/unit/evals/test_capability_echo_resistance.py` — reuse, do not re-derive.
7. `docs/CAPABILITY_CASES.md` — **read-only for you.** It is the contract P26.1 checks against.

### The work

**EVAL-P25.3 — The base-rate contract, as a gate.**
`create scripts/check_base_rate.py`, `create tests/unit/scripts/test_check_base_rate.py`,
`edit docs/CASE_SET_POLICY.md`. Target band **0.55–0.85** over a generation directory, grouped by
matcher/expectation kind (which already exists — you do not need Track B's taxonomy).
**The design constraint that matters:** it must be **advisory-with-report on first run and
blocking only once EVAL-P26 lands**, or it fails against the current set by construction —
today's battery is 0.949 and the new cases do not exist yet. Make that switch an explicit,
documented parameter, not a commented-out line.
**RED anchor:** feed it `evals/generations/k3_77688e7_regen1` (base 0.949) and assert it reports
out-of-band before the implementation exists.

**EVAL-P25.4 — Contextual-variance scorer. Build this one even if you run short on time.**
`create evals/variance_scorer.py`, `create tests/unit/evals/test_variance_scorer.py`.
The maintainer's goal is *"replies should be incredibly varied based on context and situation."*
That is measurable **deterministically**: one `player_message`, N NPCs in differing states, score
pairwise dissimilarity of the responses. Deterministic ⇒ **kappa = 1.0 by construction**, so it
pays no judge-reliability tax and its observed MDE is its true MDE. It is the only new metric in
this program that can resolve an effect today — no labels, no Opus, no engine change.
- **Do not add a dependency.** `sentence_encoder` already exists in this repo; check what it
  offers before reaching outside. If you conclude a new package is genuinely required, **stop and
  ask** — do not install it.
- **Justify the dissimilarity measure in the module docstring**, and make any threshold a named
  constant with the choice recorded. DEC-181 rejected an option specifically for introducing an
  uncalibrated free parameter; do not repeat that.
- Pure function over response strings. No I/O, no network. It scores text it is handed.

**EVAL-P26.1 — The case adversary. ⚠️ Read this whole item before designing.**
`create evals/case_adversary.py`, `create prompts/eval/case_adversary.yaml`,
`create tests/unit/evals/test_case_adversary.py`.

**There is no Anthropic client in this repo.** Opus is reached by a manual batch/paste workflow
(`OPUS_LABEL_PROMPT.md` piped verbatim, JSON batches under `evals/calibration/oracle_batches/`,
JSONL results imported back). A module that calls Opus directly needs a new dependency and is a
stop-and-ask. **Mirror the existing pattern instead.** Split the adversary in two:

1. **Deterministic checks — pure Python, no LLM, and this is the majority of the value:**
   - are the `keyword_any` tokens present in the case's own `player_message`? (that is the exact
     defect the audit found — one canned hedge passed 6 of 7 capability cases because the case
     scored on vocabulary it had itself supplied)
   - does the case fail against the reference hedge responder? (reuse `hedge_responder_probe.py`)
   - does it fail against an echo of its own `player_message`? (reuse
     `test_capability_echo_resistance.py`)
   - does the declared grounding edge type exist in the registry? **Note ISSUE-148:** the generic
     graph reader is blind to inner life; read grounding through the typed admin endpoints
     `GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id}`, exactly as `CAPABILITY_CASES.md`
     instructs. **`make draft-cases` is broken — do not use it and do not fix it this session.**
2. **Judgment checks — batch/paste:** is the prompt leading? does it supply its own answer? is
   the phrasing insider vocabulary lifted from the graph node? These go in
   `prompts/eval/case_adversary.yaml` and are emitted as a batch file for Opus, with a structured
   (Pydantic v2) findings schema for the imported result.

State the scope boundary in the module docstring: **this reviews CASES. EVAL-P28.1 labels
RESPONSES.** They are different jobs, and conflating them is how the reference side stays
single-rater.

### Stop and ask before

- **Adding any dependency.** Most likely temptation: a similarity or embedding library for P25.4,
  or an Anthropic SDK for P26.1. Neither is approved.
- **Any change under `src/`.** This session should touch **zero** `src/` files.
- Weakening any existing gate, or changing `SCORER_TRUST_POLICY.md`'s 0.60 threshold.

### Do NOT

- **Do not author eval cases.** Track B is doing that concurrently; you would collide in
  `evals/cases/`.
- **Do not touch `evals/calibration/` or `evals/generations/`** — both are in
  `loop_gates.FROZEN_PATH_PREFIXES` and hold 393 irreplaceable human labels and real transcripts.
  You may **read** them.
- **Do not edit Makefile / ROADMAP / ISSUES / DECISIONS.** Use `HANDOFF_TRACK_A.md`.
- **Do not start EVAL-P26.2, P26.3, P27 or P28.** P26.3 is the serial integration step and needs
  Track B's output.
- **Do not re-litigate the deterministic-vs-judge decision.** The maintainer chose judge repair;
  plan §1 keeps the deterministic table as the recorded fallback if EVAL-P28.3 fails.
- **Do not rewrite line endings.** This repo is CRLF with no `.gitattributes` (ISSUE-215). A small
  edit that shows thousands of changed lines is a bug — revert and redo it byte-level.
- **Do not commit files you did not create.** `git status` before every commit; the tree may carry
  a concurrent EVAL-P10 session's uncommitted `src/` work. ISSUE-139 is this repo's recurring
  failure mode.

### Definition of done

- [ ] `make check` exit 0 — except that you have **not** wired new targets into it (that is
      integration's job). Run `make lint check-evals-rules type-evals test-cov-evals` directly to
      confirm your own code is clean.
- [ ] Each of the three sub-phases has a RED anchor **confirmed failing for the right reason**
      before its implementation existed. Say in your summary how you confirmed each.
- [ ] `project-harness/HANDOFF_TRACK_A.md` written: Makefile recipes, checkboxes to tick, full
      ISSUES/DECISIONS text (from DEC-216 / ISSUE-224).
- [ ] Your final message answers in one line each: **what dissimilarity measure P25.4 uses and
      why**, and **which P26.1 checks came out deterministic vs batch/paste**.
