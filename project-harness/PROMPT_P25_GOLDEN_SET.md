# Golden-set rebuild — parallel session plan (EVAL-P25 + EVAL-P26)

**Written:** 2026-08-27. **This file is the coordinator, not a prompt.** The two prompts to
paste live in:

- **`project-harness/PROMPT_P25_TRACK_A_TOOLING.md`** — builds the instrument.
- **`project-harness/PROMPT_P25_TRACK_B_CASES.md`** — writes the contract, then authors the cases.

Start both at the same time. They are designed to not collide.

---

## Why the obvious split does not parallelise, and what does

The naive split is "instrument in one session, cases in the other." It deadlocks: authoring
binds to **two artifacts the instrument session produces** — `docs/ENGINE_EVAL_COVERAGE.md`
(which engines a judge can even observe) and `docs/REASONING_DIMENSIONS.md` (what the dimensions
are and what each asserts). An authoring session that starts before those exist is authoring
against a taxonomy nobody has written.

The fix is to notice that those two artifacts are **documents, not code**, and that the code in
EVAL-P25 does not depend on them:

| sub-phase | needs the taxonomy? | track |
|---|---|---|
| P25.1 engine observability audit | it *is* the contract | **B** |
| P25.2 reasoning-dimension taxonomy | it *is* the contract | **B** |
| P25.3 base-rate gate | no — groups by matcher kind, which already exists | **A** |
| P25.4 contextual-variance scorer | no — scores response dissimilarity | **A** |
| P26.1 case adversary | core checks come from the *existing* `CAPABILITY_CASES.md` | **A** |
| P26.2 author the cases | yes, and it is the same session that writes it | **B** |
| P26.3 coverage + adversary gate | needs **both** tracks | **integration, serial** |

So: **Track B writes its own contract and then authors against it. Track A builds every piece of
tooling that does not need that contract.** Both start at t=0. Neither waits.

## The one real risk, stated plainly

Track B will author cases while Track A is still building the adversary that checks them. If the
adversary lands and rejects a large fraction, that is rework.

**Mitigation, and it is why this is acceptable:** the anti-gaming rules the adversary automates
are *already written down and already enforced* —
`tests/unit/evals/test_capability_echo_resistance.py` and `make hedge-probe`
(`scripts/hedge_responder_probe.py`) exist today and encode the same rules. Track B authors
against those directly, case by case, as it goes. The adversary is a faster, broader re-run of
checks Track B is already applying by hand — not a new standard arriving late.

## Conflict control — read this before starting either track

This repo's recurring failure is ISSUE-139: concurrent sessions sweeping each other's work into
their commits. Three rules make these two tracks safe.

**1. Run each track in its own git worktree.** The repo already has the pattern
(`/expand-parallel`, `/fix-parallel`): isolated worktrees, then serial integration.

**2. Neither track edits any of these four files. They are the integration step's job:**

| file | why it collides |
|---|---|
| `Makefile` | `.PHONY` is a **single continued line**; both tracks add targets to it. Guaranteed conflict, in git too. |
| `project-harness/ROADMAP.md` | both tick checkboxes in the same Program 4 block |
| `project-harness/ISSUES.md` | both append |
| `project-harness/DECISIONS.md` | both append |

Instead each track writes **`project-harness/HANDOFF_TRACK_<A|B>.md`** containing: the Makefile
targets to add (verbatim recipe lines), the checkboxes to tick, and the full text of any ISSUES
or DECISIONS entries. Integration applies all of them in one pass. Nothing is lost, and the
CLAUDE.md ledger discipline is satisfied — just deferred by one step, deliberately.

**3. Pre-allocated id ranges, so two tracks never claim the same number:**

| | DECISIONS | ISSUES |
|---|---|---|
| Track A | **DEC-216** onward | **ISSUE-224** onward |
| Track B | **DEC-220** onward | **ISSUE-230** onward |

(`DEC-215` is already taken by the concurrent EVAL-P10 session. `ISSUE-223` is taken.)

**File ownership is exclusive.** Track A owns `docs/CASE_SET_POLICY.md`; Track B owns
`docs/CAPABILITY_CASES.md`. Neither touches the other's.

## Two things both tracks must know

**Adding cases moves `harness_version`.** `resolve_harness_version` hashes recursive `.yaml`
case files, and `compare.py` refuses to pair two runs whose `harness_version` differs. That is
the comparability key working correctly, and it has a scheduling consequence: **the case set
must be frozen before the EVAL-P28 labelling run.** Authoring one more case after labelling
starts invalidates the pairing.

**There is no Anthropic client in this repo.** Opus is reached by a *manual batch/paste*
workflow — `evals/calibration/OPUS_LABEL_PROMPT.md` is piped verbatim, batches are JSON files
under `oracle_batches/`, results come back as JSONL and are imported. Any design that assumes a
Python module can call Opus directly requires a new dependency and is a stop-and-ask. P26.1 is
specified to follow the existing batch/paste pattern instead.

## Integration step (serial, after both tracks report)

1. Merge both worktrees.
2. Apply `HANDOFF_TRACK_A.md` and `HANDOFF_TRACK_B.md`: Makefile targets, ROADMAP checkboxes,
   ISSUES and DECISIONS entries.
3. **EVAL-P26.3** — wire the adversary and the coverage rule together: every authored case must
   pass the P26.1 adversary and the existing echo/hedge gates before it counts toward coverage.
   `edit tests/unit/evals/test_capability_coverage.py`.
4. Run the P26.1 adversary over the **entire** authored set and fix what it rejects.
5. Flip P25.3's base-rate gate from advisory to blocking, and record the measured base rate.
6. `make check` green. `make roadmap-verify` and `make check-human-gates` green.

Then 🔴 **HUMAN GATE H13** — the labelling budget and the DEC-181 resolution. EVAL-P28 follows.

## What is still not in these two sessions

- **EVAL-P27** (multi-turn / conversation coherence). Its own programme; `docs/SEQUENCE_SCHEMA.md`
  says so itself. The taxonomy declares the dimension so it is complete; the cases are authored there.
- **EVAL-P28** (blind dual-labelling and the kappa repair). Behind HUMAN GATE H13.

## A policy flag worth one line

`ROADMAP.md` marks **EVAL-P26.2 as ⏸️ human authoring** — "only a human can say what an NPC
should say," the same principle behind `docs/CASE_SET_POLICY.md` (EVAL-P20.1: what a case forbids
is a product decision). Track B has an agent author them instead, with the graph as the source of
grounding and the echo/hedge gates as the guard. **That is a deliberate relaxation of an existing
flag, not an oversight.** Track B's prompt requires the maintainer to review the authored set
before EVAL-P26.3 ticks. If you would rather keep the flag strict, run Track A alone and author
by hand.
