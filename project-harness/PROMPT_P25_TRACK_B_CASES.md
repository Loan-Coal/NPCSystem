# Session prompt — TRACK B: the contract, then author the cases (EVAL-P25.1, P25.2, P26.2)

**Runs in parallel with Track A** (`PROMPT_P25_TRACK_A_TOOLING.md`). Read
`project-harness/PROMPT_P25_GOLDEN_SET.md` for why the split is safe. **Paste everything below
"PROMPT — copy from here" into a fresh session, in its own git worktree.**

**Needs the live stack** (`docker compose up -d`, Neo4j, and the seeded worlds). Track A does not.

---

## PROMPT — copy from here

You are working on NPC Engine (`c:\Users\lohan\Documents\hackathons\NPCSystem`). Read
`project-harness/CLAUDE.md` first — binding, and it applies to `evals/` and `scripts/` exactly as
to `src/`: strict TDD, 300-line non-test file cap, 40-line function cap, module + public function
+ public class docstrings, Pydantic v2 across module boundaries, no magic numbers or strings.

### You are TRACK B of two parallel sessions

Track A is concurrently building `scripts/check_base_rate.py`, `evals/variance_scorer.py`,
`evals/case_adversary.py` and `prompts/eval/case_adversary.yaml`. **You must not touch any of
those**, and you must not touch `docs/CASE_SET_POLICY.md` (Track A owns it — you may read it).

**Hard conflict rules — violating these breaks the other session:**

- **Do NOT edit `Makefile`, `project-harness/ROADMAP.md`, `project-harness/ISSUES.md`, or
  `project-harness/DECISIONS.md`.** `.PHONY` is a single continued line and both tracks would
  collide. Write **`project-harness/HANDOFF_TRACK_B.md`** instead: Makefile recipes to add,
  checkboxes to tick, and the *full text* of every ISSUES and DECISIONS entry. A serial
  integration step applies them.
- Your id ranges: **DECISIONS from DEC-220**, **ISSUES from ISSUE-230**. Track A owns
  DEC-216+/ISSUE-224+; DEC-215 and ISSUE-223 are already taken.
- You own `docs/CAPABILITY_CASES.md`, `docs/ENGINE_EVAL_COVERAGE.md`,
  `docs/REASONING_DIMENSIONS.md`, `scripts/check_engine_coverage.py`, and new files under
  `evals/cases/`.

### Goal, in order — this order is not negotiable

**You write the contract first, then author against it.** P25.1 and P25.2 are the artifacts that
make authoring possible; authoring before they exist is authoring against a taxonomy nobody wrote.

### Why this exists — the paragraph that motivates it

Two of four scorers are suppressed by this repo's own trust policy: `refusal_judge` kappa 0.247,
`affirms_judge` kappa 0.530, both REFUSED against `docs/SCORER_TRUST_POLICY.md`'s 0.60 threshold.
The judged battery's pass base rate is **0.951**, and kappa is chance-corrected — so Pe sits near
0.9 and kappa is crushed even at 96.3% raw agreement. **A case every NPC passes is not a
measurement.** Your cases exist to pull that base rate into 0.55–0.85, where the statistic can
breathe. **Difficulty is the product here, not a side effect.**

### Ground truth, measured 2026-08-27 — spot-check, do NOT re-derive

**If a spot-check disagrees, stop and say so.**

- `ls src/npc_engine/engines/` is **40+ packages**. The current case set is **63 YAML files**,
  essentially all single-turn dialogue, with **16 capability cases against a target of ~35**
  (ISSUE-147). Village and tavern eval worlds have **zero** capability coverage.
- Multi-turn today is **six scenario adapters that each return a single boolean**
  (`evals/scenario_adapters*.py`). There is no per-turn judging anywhere in the repo. That is
  EVAL-P27, a separate programme — **you declare the dimension, you do not author for it.**
- **`make draft-cases` does not work** (ISSUE-148: no auth header; `GROUNDED_EDGE_TYPES` names
  three relationship types that do not exist; and the generic graph reader is blind to inner life
  even for the correct names). **Do not use it, do not fix it.** Read grounding through the typed
  admin endpoints: `GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id}`.
- The real edge types are `KNOWS_ABOUT`, `BELIEVES`, `REMEMBERS`, `PURSUES`, `KNOWS_SECRET` —
  **not** `HAS_MEMORY` / `HAS_GOAL` / `HAS_SECRET`, which do not exist.

### Read, in this order

1. `project-harness/CLAUDE.md`
2. `project-harness/EVAL_P25_TO_P31_PLAN.md` — **§0 first** (why the base rate is the lever), then
   §2.B (why most engines are not judgeable) and §3.
3. `docs/CAPABILITY_CASES.md` — the existing case contract, **in full**. You extend this shape;
   do not invent a competing one. Note its EVAL-P20.2 clause: a case must fail against an echo of
   its own `player_message` and against the reference hedge responder.
4. `docs/CASE_SET_POLICY.md` — **read-only** (Track A owns it). The hedging/provenance rule here
   is what your "rumour provenance" dimension promotes; it is not a new invention.
5. A spread of 6–8 existing cases across `case_pos_` / `case_neg_` / `case_adv_` / `case_voice_`.
6. `tests/unit/evals/test_capability_coverage.py`, `test_capability_echo_resistance.py` — the
   gates your cases must pass. **Run them as you author, not at the end.**
7. `scripts/hedge_responder_probe.py` (`make hedge-probe`) — run this against your set.

### The work

**EVAL-P25.1 — Engine observability audit. Do this first.**
`create docs/ENGINE_EVAL_COVERAGE.md`, `create scripts/check_engine_coverage.py`,
`create tests/unit/scripts/test_check_engine_coverage.py`.
Classify every package under `src/npc_engine/engines/` as exactly one of:
`dialogue_observable` (reaches player-visible NPC speech, so a judge can measure it),
`state_observable` (verifiable only through the graph — belongs in a deterministic or scenario
check), `not_observable` (infrastructure — and **record why**). The gate fails when a package
exists with no classification row.
**RED anchor:** a fixture package with no row must fail the gate before its row is added.
**Why this is first, and it is the whole rationale for the phase:** DEC-214 spent an entire
session remediating A/B arms that were declared before their supply was measured. This is that
rule applied to cases — *measure observability before authoring*. A case written against an
engine that never reaches NPC speech passes unconditionally, which drags the base rate back to
1.0, which is the exact defect this program exists to fix. Expect a large `not_observable` bucket
(`idempotency`, `ports`, `contracts`, `tts`, `embedding_invalidation` and similar); that is the
correct outcome, not a failure to find coverage.

**EVAL-P25.2 — Reasoning-dimension taxonomy. Second.**
`create docs/REASONING_DIMENSIONS.md`, `edit docs/CAPABILITY_CASES.md`. Declare, each with an
assertion contract in the style `CAPABILITY_CASES.md` already uses, a case-id prefix, and a
coverage rule:
- **event knowledge** — the NPC surfaces a fact it demonstrably holds.
- **causality** — the NPC connects cause to effect, rather than reciting the fact.
- **rumour provenance** — epistemic framing matches the knowledge's origin (direct `KNOWS_ABOUT`
  ⇒ confidence; gossip-propagated ⇒ hedging is a *pass*). Promote the existing `CASE_SET_POLICY.md`
  rule; do not restate it differently.
- **contextual variance** — the same question to different NPCs, or one NPC in different states,
  produces substantively different answers.
- **multi-round coherence** — **declared only**, so the taxonomy is complete. Authored in
  EVAL-P27. Say so in the doc.

**EVAL-P26.2 — Author the cases. Third, and the bulk of the session.**
Governed by the P25.1 table and the P25.2 taxonomy. Every case must satisfy
`docs/CAPABILITY_CASES.md` in full, including the dual-failure expectation (refusal fails AND
fabrication fails) and the ungameability clause.

- **The rule that carries the most weight:** draw `keyword_any` tokens **from the grounded fact's
  text, never from the player prompt.** The audit that produced this rule found one canned hedge
  passing 6 of 7 capability cases precisely because the case scored on vocabulary it had itself
  supplied.
- **Verify grounding in the graph before writing the expectation.** A case whose "grounded fact"
  is not actually on an edge is a fabricated case. Use the typed admin endpoints.
- **Cover the village and tavern worlds**, not just demo — they have zero capability coverage
  today (`make seed-village-world`, `make seed-tavern-world`; prefixes `vw_` / `tw_`).
- **Ratchet clause applies** (the EVAL-P20.2 precedent): this need not land in one sitting. Author
  to a number you can defend, report the count, and leave the rest logged. Closes ISSUE-147 when
  the target is met.
- **Run `make hedge-probe` and the echo-resistance test as you go**, not once at the end. Track A
  is building an adversary that automates broader versions of these same checks; authoring
  against the existing gates now is what keeps its findings small.

### Stop and ask before

- **Any change under `src/`.** This session should touch **zero** `src/` files. If a case cannot
  be grounded without one, log it and move on.
- **Changing an existing case.** You are adding, not editing. An edit to an existing case changes
  `harness_version` in a way that also invalidates its meaning for prior runs — different
  decision, ask first.
- **Adding any dependency.**

### Do NOT

- **Do not touch Track A's files:** `scripts/check_base_rate.py`, `evals/variance_scorer.py`,
  `evals/case_adversary.py`, `prompts/eval/case_adversary.yaml`, `docs/CASE_SET_POLICY.md`.
- **Do not touch `evals/calibration/` or `evals/generations/`** — `FROZEN_PATH_PREFIXES`, holding
  393 irreplaceable human labels and real transcripts. Read-only.
- **Do not edit Makefile / ROADMAP / ISSUES / DECISIONS.** Use `HANDOFF_TRACK_B.md`.
- **Do not author multi-turn cases.** EVAL-P27, separate programme.
- **Do not rewrite line endings.** CRLF repo, no `.gitattributes` (ISSUE-215).
- **Do not commit files you did not create.** `git status` before every commit; the tree may carry
  a concurrent EVAL-P10 session's uncommitted `src/` work (ISSUE-139).

### One consequence of your own work, so it does not surprise anyone later

`resolve_harness_version` hashes recursive `.yaml` case files, and `compare.py` **refuses** to
pair two runs whose `harness_version` differs. Every case you add moves it. That is the
comparability key working correctly, and it means **the case set must be frozen before the
EVAL-P28 labelling run** — one more case authored after labelling begins invalidates the pairing.
Put this sentence in `HANDOFF_TRACK_B.md`.

### Definition of done

- [ ] `make lint check-evals-rules type-evals test-cov-evals` clean, plus
      `pytest tests/unit/evals/test_capability_coverage.py test_capability_echo_resistance.py`
      green with your cases in the set. (You have not wired new targets into `make check` — that
      is integration's job.)
- [ ] `make hedge-probe` run over the authored set, result reported as a number.
- [ ] Every authored case's grounding **verified against the live graph**, not assumed.
- [ ] `docs/ENGINE_EVAL_COVERAGE.md` and `docs/REASONING_DIMENSIONS.md` written, and
      `check_engine_coverage.py` has a RED anchor **confirmed failing for the right reason**.
- [ ] `project-harness/HANDOFF_TRACK_B.md` written (from DEC-220 / ISSUE-230), including the
      `harness_version` freeze note above.
- [ ] Your final message answers in one line each: **the observability split** (how many
      `dialogue_observable` of how many packages), **how many cases you authored, per dimension
      and per world**, and **the hedge-probe score**.

### For the maintainer, after this session

`ROADMAP.md` marks EVAL-P26.2 ⏸️ human authoring — "only a human can say what an NPC should say."
This session relaxes that deliberately, with the graph as the grounding source and the echo/hedge
gates as the guard. **Review the authored set before EVAL-P26.3 is ticked.**
