---
description: Fan out several independent 2026-08 remediation fixes across worktree subagents, then integrate serially.
argument-hint: "[R-id R-id ...]  (optional; defaults to all currently-parallelizable items in the active phase)"
---

You are the ORCHESTRATOR for a batch of remediation fixes from the 2026-08 program. You do not
write fix code yourself — you plan a conflict-free batch, dispatch worker subagents in isolated
worktrees, then integrate their results serially. Work LEAN and keep summaries terse.

The hard invariant: **workers run in parallel on disjoint file sets; YOU are the only one who
edits the coordination files and the only one who runs the global gate.**

Coordination files (workers must NEVER touch these): `project-harness/ROADMAP.md`,
`project-harness/ISSUES.md`, `project-harness/DECISIONS.md`,
`project-harness/review-2026-08/FIX_PLANS.md`.

## 1. Select the candidate set
Read the `## Remediation program (2026-08 review)` section of `project-harness/ROADMAP.md`
(incl. the **Carry-forward notes** block — cheap context).
- If `$ARGUMENTS` lists R-ids, that is the candidate set.
- Otherwise the candidate set is every unchecked `[ ]` item **within the earliest phase that
  still has unchecked items**. Phase order R0→R7 is a dependency order — never mix phases in
  one batch, and never open R2 while R1 has unchecked items.
- DROP any item that is blocked by an intra-phase dependency (R3.1 blocks R3.2; R2.4 must
  precede R2.5), or that needs my approval (schema change / new dependency / R0.1, which is
  mine). List what you dropped and why; do not silently skip.
- If 0 or 1 item survives, say so and tell me to just run `/fix-next` instead. STOP.

## 2. Build the conflict graph (this is the whole point — do it carefully)
For each candidate, determine its **file set** from the `Files touched:` field of its section in
`project-harness/review-2026-08/FIX_PLANS.md` (read ONLY that section). That field exists on
every plan; if one is missing or looks incomplete, open the cited code to complete it before
grouping.
- Two items **conflict** if their file sets intersect (same source file, same `Makefile`, same
  config module). Coordination files don't count — you own those. **`Makefile` and
  `.github/workflows/ci.yml` are high-collision**: several R1/R2 items touch both, so check
  them explicitly rather than assuming disjointness.
- **Group** every set of mutually-conflicting items into a single worker (that worker does them
  serially, in one worktree). Disjoint groups become separate workers.
- Print the grouping as a table: `worker | R-ids | file set | depends-on`. Confirm no two
  concurrently-dispatched workers share a file. If a grouping looks wrong, fix it before dispatch.

## 3. No brief-writing step
Unlike the old SEV flow, every item already has a self-contained plan section in `FIX_PLANS.md`
with Chosen approach, Alternatives rejected, Proof, Files touched, Effort and Risk. Do not write
new briefs and do not duplicate plan text into a new file. If a plan is genuinely insufficient
for a cold worker, fix that plan section in place and commit it as
`docs(fix-plans): clarify <R-id>` before fanning out.

## 4. Dispatch workers (parallel, background, isolated)
For each worker group, launch one `Agent` with `subagent_type: general-purpose`,
`model: sonnet`, `isolation: "worktree"`, `run_in_background: true`. Cap at **4 concurrent**;
if more groups exist, dispatch the next as earlier ones report. Each worker prompt must say:

> You own remediation item(s) <R-ids>. Read ONLY your section(s) of
> `project-harness/review-2026-08/FIX_PLANS.md` and the files they cite — do not read
> TRIAGE.md or CODEBASE_REVIEW.md. For each item: write the plan's **Proof** FIRST, run it,
> and confirm it fails for the stated reason. If the Proof passes before your change, STOP and
> report that — it means the plan or the test is wrong. Then implement the minimum fix per the
> plan's **Chosen approach** (do not substitute one of its Alternatives rejected) and confirm
> the Proof passes. Run ONLY the relevant unit tests (`pytest tests/unit/<...>`), NOT
> `make check`, NOT integration tests (shared Neo4j/Ollama are not yours to contend on).
> Obey CLAUDE.md: module docstrings, no prompt strings outside `prompts/`, no layer violations,
> typed/Pydantic boundaries. File-size limits are being changed by R1.1 — if your work is
> blocked by the 300-line rule, say so rather than splitting a file opportunistically. Do NOT
> edit ROADMAP.md, ISSUES.md, DECISIONS.md, or FIX_PLANS.md. Commit each fix on your worktree
> branch with a conventional message naming the R-id and CR finding id. Report back: branch
> name, commits, files touched, Proof result (incl. that it was red first), unit-test result,
> any waiver needed, any adjacent issue you spotted (don't fix it), any measured number that
> moved, and whether the code had moved from the plan.

## 5. Fan in (serial — you do this)
As each worker reports, integrate ONE AT A TIME (never merge two unreviewed branches at once):
1. Review the branch diff for correctness, scope creep, and CLAUDE.md compliance. **Confirm the
   worker actually saw its Proof red first** — a worker that skipped that step has not shown the
   fix does anything. Send it back via `SendMessage` rather than fixing it yourself.
2. Merge/cherry-pick its commits into the working branch. Resolve any incidental conflict.
3. YOU update the coordination files for that item: tick `[ ]`→`[x]` in the ROADMAP remediation
   section, update any related ISSUE (mark `[FIXED]` and move to `archive/ISSUES_RESOLVED.md`
   if closed), add/clear Carry-forward notes (≤10 lines), append DECISIONS entries for any
   waiver the worker flagged, and log any adjacent issue the worker found as the next
   ISSUE-NNN (check both `ISSUES.md` and the archive for the next free id).

## 6. One global gate
After ALL workers are integrated, run `make check` **once** on the merged tree. If a rule/type
baseline shrank, run `make check-rules-update` / `make type-ratchet-update`. If `make check`
fails, identify the offending item and either fix narrowly or dispatch one targeted worker —
do not bisect blindly. Re-run until green.

Then diff any measured number the batch touched against
`project-harness/review-2026-08/BASELINE_2026-08-28.md` and state the deltas. Several items
are *expected* to move numbers (R2.4 lowers the base rate, R2.2 changes coverage); an
unexplained move is a finding.

## 7. Commit the integration & clean up
Commit the coordination-file updates in one `docs(remediation): batch <R-ids> integrated`
commit (the fix commits are already in history from fan-in). Remove worktrees (they auto-clean
if unchanged; otherwise prune them).

## 8. Stop
STOP. In ≤8 lines: the worker grouping that ran, per-item pass/fail, the single `make check`
result, any measured number that moved, anything sent back for rework, and the next
parallelizable batch (or "run /fix-next for the remaining serial/blocked items"). Do NOT start
the next batch.
