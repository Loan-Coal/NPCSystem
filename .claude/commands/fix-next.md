---
description: Implement the next remediation fix from the 2026-08 program (one item, end to end).
argument-hint: "[R-id]  (e.g. R1.1; defaults to the next unblocked unchecked item)"
---

You are executing ONE item from the 2026-08 remediation program, end to end. Work LEAN:
this likely runs in a fresh session, so load only what you need and leave a crisp trail
for the next run. Do not paraphrase files back to me; keep all summaries terse.

## 1. Select
Read the **`## Remediation program (2026-08 review)`** section of `project-harness/ROADMAP.md`
— including the **Carry-forward notes** block at its top (that block is your cheap context;
read it before anything else). That section is the backlog and the state; there is no
separate index file.
- If `$ARGUMENTS` names an item (e.g. `R1.1`), take that item.
- Otherwise take the FIRST unchecked `[ ]` item **in phase order (R0 → R7)** whose phase
  prerequisites are satisfied. Phase order is a **dependency** order, not a priority order:
  never start an R2 item while an R1 item is unchecked, and never start R3 while R2 is open.
- Some items carry an explicit intra-phase dependency in their line or plan (e.g. R3.1 blocks
  R3.2; R2.4 must land before R2.5). Honour those.
- If the only remaining items are blocked, or need my approval (schema change / new
  dependency / a `DECISIONS.md` entry — e.g. R0.1, which is mine to do), STOP and tell me
  which and why.

## 2. Load (minimal context)
Read ONLY that item's section in `project-harness/review-2026-08/FIX_PLANS.md` and the exact
files it cites. Sections are headed `### [CR-Lxx-yy ...] <title>` and are grouped under the
`# R<n> — <phase>` heading matching the roadmap item — find yours by the phase heading, then
the `Roadmap phase:` field. Do **not** read `TRIAGE.md` or `CODEBASE_REVIEW.md`; the plan
section is self-contained. Use targeted reads (offset/limit) on large files.

Open each cited location to confirm its current shape still matches the plan before editing;
if the code has moved, adapt minimally and note it. The plans were written against `619dab2`.

## 3. Implement
Do exactly what the plan's **Chosen approach** specifies — no scope creep. The plan also lists
**Alternatives rejected**; do not silently pick one of them. If the chosen approach turns out
to be wrong, STOP and tell me rather than substituting.

**Write the Proof first.** Every plan has a `Proof:` field naming a check that is red today and
green after. Write it, run it, and confirm it fails **for the stated reason** — not an import
error, not a typo. A Proof that passes before your change means either the plan is wrong or you
wrote the wrong test; STOP and say which. Then implement the minimum fix and confirm it passes.

If you spot an adjacent problem, log it in `ISSUES.md` (next ISSUE-NNN — check **both**
`ISSUES.md` and `archive/ISSUES_RESOLVED.md` for the next free id) and keep going. Do not fix
it here.

## 4. Verify
Run the plan's Proof, then `make check`. Both must pass. If a rule- or type-error baseline
shrank as a result, run `make check-rules-update` / `make type-ratchet-update` to ratchet it
down.

If your item **changes a measured number** (guard rate, base rate, coverage, grandfathered
counts, `make test` duration), compare against
`project-harness/review-2026-08/BASELINE_2026-08-28.md` and state the delta explicitly in your
summary. A number that moved without explanation is a finding, not a side effect.

## 5. Record
- Tick `[ ]`→`[x]` for this item in the ROADMAP remediation section.
- Advance any related `ISSUE-NNN` in `ISSUES.md` with a one-line edit (do not reread the whole
  file). If the item closes an issue, mark it `[FIXED]`, add the `**Fixed:**` line, and move
  the entry to `archive/ISSUES_RESOLVED.md`.
- Append a `DECISIONS.md` entry for any waiver or non-obvious choice you had to make.
- Update the **Carry-forward notes** block at the top of the roadmap's remediation section: add
  a one-line note for anything a downstream item now needs (a new helper it should reuse, an
  assumption this fix introduced, a gotcha you hit), and DELETE notes that are now consumed.
  Keep it ≤10 lines.

## 6. Commit
Commit just this fix. Clean conventional-commit message naming the R-id and the CR finding id,
e.g. `fix(R1.1): make check-rules signatures line-count-bearing (CR-L06-05)`.

## 7. Stop
STOP. In ≤6 lines: what you fixed, the Proof result (pass/fail, and that it was red first), any
measured number that moved, and the next unchecked item. Do NOT start it.
