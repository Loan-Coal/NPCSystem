---
description: Build several independent NPC-engine expansions truly in parallel across isolated worktrees, then integrate serially. The expansion analog of /fix-parallel — fresh and clean, never touches the review harness.
argument-hint: "[EXP-NN EXP-NN ...]  (optional; defaults to the largest conflict-free, dependency-satisfied batch from EXPANSION_INDEX.md)"
---

You are the ORCHESTRATOR for a batch of **feature expansions** (not fixes, not review). You do
not write expansion code yourself — you select a conflict-free batch, dispatch fully-autonomous
worker subagents in isolated worktrees (each as independent as a separate Claude chat), then
integrate their results serially behind one global gate. Work LEAN; keep summaries terse.

**The hard invariant:** workers run **truly in parallel on disjoint file sets**; YOU are the only
one who edits the coordination files and the only one who runs the global gate. Expansions are
mostly **OCP new-file adds** (new engines, new `type_registry` YAML, new prompts) — that is exactly
why a wide parallel fan-out is safe here: independent expansions rarely share a file.

**Coordination files (workers must NEVER touch these):**
`project-harness/expansion/EXPANSION_INDEX.md`, `project-harness/expansion/EXPANSION_ROADMAP.md`,
`project-harness/ISSUES.md`, `project-harness/DECISIONS.md`.

**This command is for expansion only.** Never read or write `project-harness/review-fixes/`,
`REVIEW_FINDINGS.md`, or the archived review evidence — that harness is reserved for `/fix-next`
and `/fix-parallel` when a future review runs.

## 1. Select the candidate set
Read `project-harness/expansion/EXPANSION_INDEX.md` — **including the "Carry-forward notes" block at
the top** (that block is your cheap context; read it before anything else).
- If `$ARGUMENTS` lists EXP ids, that is the candidate set.
- Otherwise the candidate set is every unchecked `[ ]` item whose `deps:` are all satisfied (their
  prerequisites are `[x]` or already merged).
- **DROP and list (never silently skip)** any item that:
  - needs a **schema change or DECISIONS approval** not yet granted (check the brief's
    `Architecture fit:` / the `FEASIBILITY.md` flags — e.g. a new base node/edge, a layer change);
  - has an **unmet dependency** still open;
  - has **no first-slice brief** and you cannot write one cleanly from the mini-spec (see §3);
  - is an **L/XL** item not yet decomposed into a shippable first slice (parallel workers build
    *first slices*, not whole multi-session engines).
- Aim for a batch of **5–8** items (this skill is built for a wide fan-out). If fewer than 5 survive,
  take what's clean — but if only 0–1 survive, say so and tell the user to run `/fix-next`-style
  single-item iteration against the index instead. STOP.

## 2. Build the conflict graph (this is the whole point — do it carefully)
For each candidate, determine its **file set**: the exact files it will create or edit, from the
brief's `Files:` / cited locations.
- Two items **conflict** if their file sets intersect on any **existing** file (a shared engine,
  service, route module, `config.py`, an existing `type_registry` YAML, a shared prompt file).
  Brand-new files never conflict. Coordination files don't count — you own those.
- New `type_registry` base node/edge files are additive and disjoint, **but** if two items edit the
  **same** existing YAML or the same registry loader, they conflict.
- **Group** every set of mutually-conflicting items into a single worker (it does them serially in
  one worktree). Disjoint groups become separate parallel workers.
- Print the grouping as a table: `worker | EXPs | files (new vs edited) | deps`. Confirm no two
  concurrently-dispatched workers share an **existing** file. Fix the grouping before dispatch if
  any overlap remains. Prefer splitting an edited-shared-file item into its own later batch over
  forcing a conflict.

## 3. Write missing first-slice briefs (serial, before dispatch)
Each parallel worker must be runnable cold from one brief. For any candidate lacking
`project-harness/expansion/briefs/EXP-NN-<slug>.md`, write one now, distilled from its §3 mini-spec
in `ENGINE_GAPS.md` / `NEW_ENGINES.md` / `DEMO_EXPANSIONS.md` plus the `FEASIBILITY.md` verdict.
Brief sections (self-contained — a cold worker needs nothing but the brief + its cited files):
- **Goal / business rationale** (one line + the BUSINESS_INTENT tie).
- **First slice** — the smallest shippable increment that proves the idea (this is the worker's scope).
- **Current state** — `file:line` of the seam to build on, verified against the code now.
- **Files** — new files to create + any existing files to edit (this is its conflict set).
- **Graph/API surface** — concrete `type_registry` YAML sketch / route shape, or "engine-internal".
- **Architecture fit** — which OCP seam; confirm new-file-add. Flag any schema/DECISIONS need (if so,
  it should have been dropped in §1).
- **Test plan** — the exact failing test to write first + the unit-test command to run.
- **Done when** — observable exit criterion.
Commit the new briefs in one `docs(expansion): briefs for <EXPs>` commit on the current branch
before fanning out.

## 4. Dispatch workers (parallel, background, isolated, autonomous)
For each worker group, launch one `Agent` with `subagent_type: general-purpose`, `model: sonnet`,
`isolation: "worktree"`, `run_in_background: true`. **Cap at 8 concurrent** (this is the wide-fan-out
skill); if more groups exist, dispatch the next as earlier ones report. Each worker prompt must say:

> You own expansion(s) <EXP ids> — build them as if you were an independent engineer in your own
> repo clone. Read ONLY `project-harness/expansion/briefs/EXP-<NN>-<slug>.md` and the files it cites.
> Build the brief's **first slice** end to end: write the failing test FIRST, confirm it fails for
> the right reason, implement the minimum to pass, refactor green. Run ONLY your own relevant unit
> tests (`pytest tests/unit/<...>` or `pytest demo_game/tests/<...>`), NOT `make check`, NOT
> integration tests (shared Neo4j/Ollama are not yours to contend on). Obey CLAUDE.md strictly:
> OCP **add-by-new-file** (never edit a closed engine to add a variant), the layer model, 300-line
> files / 40-line functions / ≤3 nesting, module + public-function docstrings, **no prompt strings
> outside `prompts/`**, Pydantic-v2 typed boundaries (no raw dict across modules), DI via the
> composition root, async-all-the-way (offload CPU-bound work with `asyncio.to_thread`). Do NOT add
> a new graph base node/edge or change a schema — if your slice needs one, STOP and report it. Do
> NOT edit EXPANSION_INDEX.md, EXPANSION_ROADMAP.md, ISSUES.md, or DECISIONS.md, and do NOT touch
> files outside your declared set. Commit each slice on your worktree branch with a conventional
> message naming the EXP id. Report back: branch name, commits, files created/edited, unit-test
> result, any 300-line/decision waiver needed, any adjacent issue you spotted (don't fix it), and
> whether the code had moved from the brief.

## 5. Fan in (serial — you do this)
As each worker reports, integrate ONE AT A TIME (never merge two unreviewed branches at once):
1. Review the branch diff for correctness, scope creep, and CLAUDE.md compliance (esp. OCP add-by-
   new-file, layers, prompts-in-YAML, typed boundaries). If a worker went off-spec or smuggled in a
   schema change, send it back via `SendMessage` rather than fixing it yourself.
2. Merge/cherry-pick its commits into the working branch. Resolve any incidental conflict (should be
   rare by construction — that's what §2 bought you).
3. YOU update the coordination files for that EXP: tick `[ ]`→`[x]` in EXPANSION_INDEX, advance its
   line in EXPANSION_ROADMAP, update any related ISSUE, append DECISIONS entries for any waiver the
   worker flagged, and update the Carry-forward notes block (≤10 lines: add a line for anything a
   downstream expansion now reuses — a new helper, a new protocol seam, a populated field — and
   DELETE consumed lines). Log any adjacent issue the worker found as the next ISSUE-NNN.

## 6. One global gate
After ALL workers are integrated, run `make check` **once** on the merged tree (engine work) and
`make test-demo` if any demo expansion landed. If a rule/type baseline shrank, run
`make check-rules-update` / `make type-ratchet-update`. If a gate fails, identify the offending EXP
and either fix narrowly or dispatch one targeted worker — do not bisect blindly. Re-run until green.

## 7. Commit the integration & clean up
Commit the coordination-file updates in one `docs(expansion): batch <EXPs> integrated` commit (the
slice commits are already in history from fan-in). Remove worktrees (they auto-clean if unchanged;
otherwise prune them).

## 7.5. Prepare for next invocation (mandatory — do this before stopping)
After the commit, make the index ready for the next `/expand-parallel` call:
1. **EXPANSION_INDEX.md carry-forward notes** — rewrite the block from scratch (≤10 lines total).
   Remove any line whose seam/helper has now been consumed. Add one line per new seam, protocol, or
   populated field unlocked by this batch that a downstream EXP will build on. Format:
   `- EXP-NN: <what was added> → usable by <EXP-NN|layer|pattern>`.
2. **EXPANSION_INDEX.md dependency closure** — for every remaining `[ ]` item, re-check that its
   `deps:` are still pointing at real IDs (not stale names). Mark any item whose dep was just
   satisfied in this batch so `§1` auto-selects it next time.
3. **EXPANSION_ROADMAP.md** — update the "Last batch" line and the "Next candidate batch" preview
   (the conflict-free set §1 would select right now). This is a one-line update per section.
4. **ISSUES.md** — flush any adjacent-issue notes the workers surfaced into proper `ISSUE-NNN`
   entries. Do not leave inline TODO comments in source as a substitute.
5. Commit these readiness updates in a second focused commit:
   `docs(expansion): index + roadmap ready for next batch` (separate from the integration commit
   so history is clean and reviewable). If no changes are needed, skip the commit.

After this step a cold `/expand-parallel` with no arguments must select the correct next batch
immediately, without the user needing to hand-edit the index.

## 8. Stop
STOP. In ≤8 lines: the worker grouping that ran, per-EXP pass/fail, the single `make check` (+ demo)
result, anything sent back for rework, the keystones/seams now unlocked for the next batch, and the
next conflict-free batch from the index. Do NOT start the next batch.
