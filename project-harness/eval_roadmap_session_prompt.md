# Session prompt — adversarial review + eval roadmap construction

> Paste the block below into a **fresh session** at the repo root.

---

You are doing **planning and adversarial review only**. You will write **zero implementation
code** this session. Your deliverables are (1) a review report and (2) edits to
`project-harness/ROADMAP.md` plus two small housekeeping files. If you find yourself editing a
`.py` file, you have gone off-mission.

## Mission

Turn `project-harness/npc_system_eval_plan_idea` — an ambitious but **externally written,
codebase-blind** plan for building an eval pipeline — into a grounded, phase-by-phase program in
`project-harness/ROADMAP.md` that I can execute one phase per session with `/expand-next`.

The plan is a proposal, not a spec. Treat it as a hostile witness: it makes claims about this
repo that are wrong, and its time estimates were written without reading a single file.

## Step 1 — Read, in this order

1. `project-harness/npc_system_eval_plan_idea` — the plan under review, in full.
2. `project-harness/CLAUDE.md` — hard rules. Every one applies to eval code too.
3. `project-harness/ROADMAP.md` — all active programs, especially `## Active — Eval suite
   redesign (EVAL-B2..FINAL)` and the unticked `EVAL-FINAL.1`.
4. `project-harness/DECISIONS.md` — at minimum **DEC-143** (judge/generation model separation)
   and **DEC-144** (two-phase generate→judge). Grep for others touching evals.
5. `project-harness/ISSUES.md` — open items that collide with eval work.
6. `evals/` — every module. Pay closest attention to `eval_records.py`, `generate_runner.py`,
   `judge_runner.py`, `matchers.py`, `summary.py`, `runner.py`, `judge_config.py`,
   `retrieval_runner.py`, `retrieval_matchers.py`, `preconditions.py`.
7. `evals/cases/` — sample 5-6 YAML cases across the `case_pos_` / `case_neg_` / `case_adv_` /
   `case_voice_` families, plus `anti_hallucination_demo.json` and `retrieval_demo.json`.
8. `Makefile` — every `eval*` target and what `make check` actually gates.
9. `~/.claude/commands/expand-next.md` — the executor. Your roadmap output must be consumable
   by it without interpretation.

## Step 2 — Ground truth already established (verify, don't re-derive)

A prior session established the following. **Spot-check each one and correct me where I am
wrong** — do not take them on faith, but do not spend the session rediscovering them either.

- **The plan's Phase 1 is roughly 40% already shipped.** `evals/eval_records.py`
  (`GenerationRecord` / `JudgedRecord` / `TranscriptFile`, all Pydantic v2, `frozen=True`),
  `evals/generate_runner.py`, and `evals/judge_runner.py` already implement generate→judge
  separation under DEC-144, with `make eval-generate` / `make eval-judge`.
- **What Phase 1 is actually missing:** `--k N` repeats; a `gen_id` directory artifact; the
  `config` block (prompt version, retrieval params, model/temperature/seed); `git_sha`;
  `golden_set_version`; and — the important one — **persisting the retrieved context** that
  produced each reply.
- **`TranscriptFile` is frozen and has no config/k fields.** Adding them is a schema v2
  migration with a compatibility decision, not an additive field.
- **No calibration artifact exists anywhere in the repo.** Zero hits for
  `calibrat|human_verdict|kappa` outside the plan document itself.
- **56 golden cases exist**, YAML, `case_id` + `seed` + `input` + `expected[{kind}]`. There is
  **no** `added_in`, no `retired_in`, and no required-fact annotation on any of them.
- **The judge is a separate model** (`mixtral:8x7b`, DEC-143, with a hard-fail collision guard
  in `judge_config.py`). The plan never accounts for this.
- **Competing active programs:** REORG-PR6..PR9, the REM-* issue-remediation program, and the
  P0/P1/P2 shippable-demo program. `EVAL-FINAL.1` is still unticked.

## Step 3 — Owner constraints (already decided; treat as fixed inputs)

- **Calibration set does not exist and must be built.** The plan's "the labels already exist, so
  this is cheap" framing is false. Budget real labelling time and design the labelling loop
  (how many outputs, sampled how, stored where, how a second pass measures self-agreement).
- **Time budget: ~5-8h across the weekend, ~6-10h the following week.** ~14-18h total. This is a
  hard ceiling. Anything that does not fit goes into an explicitly labelled `Parked` subsection
  rather than being silently compressed into an optimistic estimate.
- **Learning goals, in priority order:** (1) eval methodology + statistics — implemented by hand,
  not imported, because the point is being able to defend every number; (2) RAG / graph-context
  retrieval measurement — decomposing retrieval failure from generation failure; (3) harness and
  pipeline engineering — artifact schemas, reproducibility, CLI design; (4) **dashboard and
  production UI/UX** — this is a genuine learning goal, so the report/dashboard phases are
  **in scope**, not the first thing cut.
- **`evals/` extraction discipline is enforced from the first phase.** `evals/` stays src-free
  behind one thin adapter so the harness + schemas + a synthetic fixture set can be published
  standalone while the engine stays private. Every phase must preserve this.
- **Consolidate, do not accrete.** The legacy targets (`make eval`, `eval-anti-hallucination`,
  `eval-llm`, `eval-llm-demo`, `eval-retrieval`, `eval-report`) must be **folded into** the new
  suite. The end state is one coherent pipeline, not old and new runners living side by side.
  Sequence the migration so the gate stays green at every commit and no target is orphaned.
- **Strip Unity and Unreal work out of `ROADMAP.md`** into a new
  `project-harness/UNREAL_DEFERRED.md` (move verbatim, preserve step IDs, leave a one-line
  pointer behind). Anything about the actual game-client integration is deferred.

## Step 4 — Adversarial review (the core of the session)

Produce a verdict table. Every row: **claim → CONFIRMED / REFUTED / UNVERIFIABLE → evidence
(file:line, command output, or "cannot be checked without a live run")**. Never mark something
confirmed on plausibility.

At minimum, attack these:

**Cost and feasibility claims**
- The "~20 minutes per full eval run" figure — where does it come from, and does the case count
  in `evals/cases/` support it? Design the smallest measurement that settles it.
- "k=15 full set ≈ 5 hours" — recompute against the real case count, and against the fact that
  **judging is a second LLM pass on a second model**. Does the plan's arithmetic survive?
- "Both deterministic metrics run in seconds with no LLM" — true, but they need **Neo4j up**.
  Is that compatible with `make check` and with the "every save" iteration loop the plan sells?

**Repo-state claims**
- "Prompts externalised and versioned" — is there an actual *version* identifier on a prompt
  today, or just files in `prompts/`? A/B comparison is impossible without one; if it is
  missing, that is a hidden prerequisite phase.
- "~951 passing tests on the deterministic layer" — check it. Report the real number.
- "The hard half (the scoring function) already exists" — against `matchers.py` and
  `summary.py`, is that true, or does the plan's metric set need mostly new scorers?

**Design claims that could be wrong for this codebase**
- **Retrieved-context capture.** Does the dialogue path expose the retrieved subgraph to a
  caller today? There is a debug-retrieval route and `retrieval_runner.py` — establish exactly
  what is reachable without violating the layer rules or the `evals/` src-free constraint. If it
  is not reachable, that is a prerequisite step and it belongs early, because the plan is right
  that regenerating later is expensive.
- **Determinism.** Does the LLM adapter accept `seed` / `temperature`? If not, the config block
  the plan specifies cannot be populated honestly.
- **Entity extraction for hallucinated-entity rate.** Can the entity vocabulary be enumerated
  from the graph, and by what path from `evals/`? Name the honest method and its failure modes
  (aliases, pronouns, partial names) rather than assuming NER.
- **Knowledge-boundary violations.** Which existing graph reader answers "has this fact
  propagated to this NPC?", and does calling it from `evals/` cross a layer or the adapter
  boundary?
- **Statistics honesty.** Wilson intervals on k=3 are extremely wide. State what k the budget
  can actually afford and what claim that k does and does not support.
- **Overlap with existing work.** `retrieval_runner.py` + `retrieval_matchers.py` +
  `retrieval_summary.py` already compute precision@k / recall@k / MRR. How much of the plan's
  Phase 4/7 retrieval work is duplication?

**Then: what the plan misses entirely.** Be specific and short — no more than six items, each
one something you can point at in the codebase.

## Step 5 — Ask before writing

Use `AskUserQuestion`. Batch your questions; at most two rounds. Ask only about things where
different answers produce materially different roadmaps — sequencing against the other active
programs, what to do with `EVAL-FINAL.1`, the transcript-schema migration strategy, how much
labelling I am willing to do by hand, whether the dashboard is FastAPI+templates or something
else. Do not ask about anything you can determine by reading a file.

## Step 6 — Write the roadmap

Insert a new program into `project-harness/ROADMAP.md` matching the **exact house format** used
by the existing `EVAL-B*` block. Phase IDs `EVAL-P0` upward. Each phase:

```markdown
### Phase EVAL-P1 — <outcome-shaped title>
**Goal:** One or two sentences. An outcome, not an activity.
**Effort:** <hours of my time> (+ <wall-clock background time> if any)
**Constraint:** The invariant this phase must not break.
**Notes:** Prior art in the repo, known gotchas, what makes this hard.
**Done when:** A checkable condition. Someone else must be able to verify it without asking me.

- [ ] **EVAL-P1.1** <imperative task>. Files: `create evals/x.py`, `edit evals/y.py`.
      RED anchor: `tests/unit/.../test_x.py::test_<name>` fails because <reason>.
      Validation: <the observable change — a command's output, a file that now exists, a number>.
```

Rules for the roadmap you produce:

- **One step ≈ one commit.** If a step cannot be committed green on its own, split it.
- **Every step names its files and its RED test anchor.** `/expand-next` writes the failing test
  first; a step that does not say what should fail is unusable.
- **Every step has a validation line** stating the observable change. "Improve the golden set" is
  not a step. "Add `added_in: v1` to all 56 cases; `python -m evals.<x> --validate` reports 56/56
  tagged" is.
- **Phases are ordered by dependency and each leaves the gate green.** State cross-phase
  dependencies explicitly in Notes.
- **Total effort must fit 14-18h.** Show the running total. Anything that does not fit goes under
  a `### Parked (out of budget)` heading with a one-line reason each.
- **Flag every step that hits a CLAUDE.md "ask before doing" gate** (new dependency, public
  interface change, schema change, CI change) so `/expand-next` halts rather than improvising.
  If a phase needs a decision, write the `DECISIONS.md` entry as 🔶 proposed and say which step
  it gates.
- **Do not inherit the plan's phase numbering or its estimates.** Renumber and re-time from what
  you found in the codebase.
- **Do not design the dashboard before the artifact schema is settled.** The UI phase reads a
  stable schema; if it lands early it will be rewritten.

## Step 7 — Housekeeping, in the same session

- Create `project-harness/UNREAL_DEFERRED.md` and move the Unity/Unreal-client material there
  verbatim, leaving a one-line pointer in `ROADMAP.md`.
- Add 🔶 `DECISIONS.md` proposals for: the transcript schema v2 migration, the `evals/` adapter
  boundary contract, and the legacy-eval-target consolidation.
- State your recommended ordering of this program against REORG-PR6..PR9, REM-*, and P0 — and
  what happens to `EVAL-FINAL.1`.

## Output for this session, in order

1. The verdict table from Step 4, plus the "what the plan misses" list.
2. Your questions (Step 5).
3. After I answer: the `ROADMAP.md` edit, `UNREAL_DEFERRED.md`, and the `DECISIONS.md`
   proposals — then a closing summary of the phase list with the running effort total.

Be blunt in the review. A plan I execute on a false premise costs me a weekend; a plan you
correctly tell me is wrong costs me ten minutes.
