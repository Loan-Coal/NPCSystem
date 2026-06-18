---
description: Fan out several independent review-remediation fixes across worktree subagents, then integrate serially.
argument-hint: "[SEV-NN SEV-NN ...]  (optional; defaults to all currently-parallelizable items)"
---

You are the ORCHESTRATOR for a batch of review-remediation fixes. You do not write fix
code yourself — you plan a conflict-free batch, dispatch worker subagents in isolated
worktrees, then integrate their results serially. Work LEAN and keep summaries terse.

The hard invariant: **workers run in parallel on disjoint file sets; YOU are the only one
who edits the four coordination files and the only one who runs the global gate.**

Coordination files (workers must NEVER touch these): `project-harness/review-fixes/INDEX.md`,
`project-harness/REVIEW_FINDINGS.md`, `project-harness/ISSUES.md`, `project-harness/DECISIONS.md`.

## 1. Select the candidate set
Read `project-harness/review-fixes/INDEX.md` (incl. the "Carry-forward notes" block — cheap context).
- If `$ARGUMENTS` lists SEVs, that is the candidate set.
- Otherwise the candidate set is every unchecked `[ ]` item whose `deps:` and Block A–F order
  are satisfied.
- DROP any item that is blocked or needs my approval (schema change / new dependency /
  DECISIONS entry — e.g. SEV-12, or any item with no brief AND an unmet dependency like SEV-30).
  List what you dropped and why; do not silently skip.
- If 0 or 1 item survives, say so and tell me to just run `/fix-next` instead. STOP.

## 2. Build the conflict graph (this is the whole point — do it carefully)
For each candidate, determine its **file set**: the exact files it will edit. Source from the
`FIX-<SEV>.md` brief's cited locations if a brief exists, else from the finding's paragraph in
`REVIEW_FINDINGS.md` §3 (read ONLY that finding's lines).
- Two items **conflict** if their file sets intersect (same source file, same `.env`, same
  config module, etc.). Coordination files don't count — you own those.
- **Group** every set of mutually-conflicting items into a single worker (that worker does them
  serially, in one worktree). Disjoint groups become separate workers.
- Print the grouping as a table: `worker | SEVs | file set | depends-on`. Confirm no two
  concurrently-dispatched workers share a file. If a grouping looks wrong, fix it before dispatch.

## 3. Write missing briefs (serial, before dispatch)
For any candidate lacking `project-harness/review-fixes/FIX-<SEV>.md`, write one now from the
§3 finding: Problem, Current shape (cited files+lines, verified against the code), Steps,
Verification (a concrete unit test + command), Blast radius. Each brief must be self-contained
so a cold worker needs nothing but the brief + its cited files. Commit the new briefs in one
`docs(review-fixes): briefs for <SEVs>` commit on the current branch before fanning out.

## 4. Dispatch workers (parallel, background, isolated)
For each worker group, launch one `Agent` with `subagent_type: general-purpose`,
`model: sonnet`, `isolation: "worktree"`, `run_in_background: true`. Cap at **4 concurrent**;
if more groups exist, dispatch the next as earlier ones report. Each worker prompt must say:

> You own SEV(s) <ids>. Read ONLY `FIX-<SEV>.md` and the files it cites. For each: write the
> regression test FIRST, confirm it fails for the right reason, implement the minimum fix,
> confirm it passes. Run ONLY the relevant unit tests (`pytest tests/unit/<...>`), NOT
> `make check`, NOT integration tests (shared Neo4j/Ollama are not yours to contend on).
> Obey CLAUDE.md: 300-line files, 40-line funcs, module docstrings, no prompt strings outside
> `prompts/`, no layer violations, typed/Pydantic boundaries. Do NOT edit INDEX.md,
> REVIEW_FINDINGS.md, ISSUES.md, or DECISIONS.md. Commit each fix on your worktree branch with
> a conventional message naming the SEV. Report back: branch name, commits, files touched,
> unit-test result, any 300-line/decision waiver needed, any adjacent issue you spotted (don't
> fix it), and whether the code had moved from the brief.

## 5. Fan in (serial — you do this)
As each worker reports, integrate ONE AT A TIME (never merge two unreviewed branches at once):
1. Review the branch diff for correctness, scope creep, and CLAUDE.md compliance. If a worker
   went off-spec, send it back via `SendMessage` rather than fixing it yourself.
2. Merge/cherry-pick its commits into the working branch. Resolve any incidental conflict.
3. YOU update the coordination files for that SEV: tick `[ ]`→`[x]` in INDEX, advance the SEV
   status line in REVIEW_FINDINGS, update any related ISSUE, add/clear Carry-forward notes
   (≤10 lines), append DECISIONS entries for any waiver the worker flagged, log any adjacent
   issue the worker found as the next ISSUE-NNN.

## 6. One global gate
After ALL workers are integrated, run `make check` **once** on the merged tree. If a rule/type
baseline shrank, run `make check-rules-update` / `make type-ratchet-update`. If `make check`
fails, identify the offending SEV and either fix narrowly or dispatch one targeted worker —
do not bisect blindly. Re-run until green.

## 7. Commit the integration & clean up
Commit the coordination-file updates in one `docs(review-fixes): batch <SEVs> integrated`
commit (the fix commits are already in history from fan-in). Remove worktrees (they auto-clean
if unchanged; otherwise prune them).

## 8. Stop
STOP. In ≤8 lines: the worker grouping that ran, per-SEV pass/fail, the single `make check`
result, anything sent back for rework, and the next parallelizable batch (or "run /fix-next
for the remaining serial/blocked items"). Do NOT start the next batch.
