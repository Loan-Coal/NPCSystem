# The 2026-08 strategic codebase review — closed

**What this is.** The complete record of the 16-lens strategic review run on **2026-08-28**
against HEAD `619dab2`: 145 raw findings in, 118 canonical out, 4 CRITICAL. The raw synthesis
that produced it is `../CODEBASE_REVIEW.md`; the one-shot prompt that commissioned it is
`../PROMPT_CODEBASE_REVIEW_2026-08.md` (gitignored, local-only). Both stay at the top level
because they are cited there by path — see `../README.md`.

**When it closed.** The review closed 2026-08-28 and its remediation programme (R0–R5) shipped
and was archived on 2026-09-03 (`../archive/ROADMAP_remediation-2026-08_2026-09-03.md`).
`TRIAGE.md` was **re-triaged on 2026-09-08** against the current tree — that header block is the
only edit this folder has taken since it closed. `FINDINGS.md`, `CODEBASE_REVIEW.md` and
`evidence/` are the immutable record of 2026-08-28 and were not edited.

**Read order.** `TRIAGE.md` first — it supersedes `FINDINGS.md` by reference and carries the
current verdicts. `FINDINGS.md` is the unfiltered original. `FIX_PLANS.md` holds the per-item
fix plans. `evidence/CR-L01.md`–`CR-L16.md` is one file per lens.

**What still cites this folder — do not move any of it:**

| Cited file | Cited by |
|---|---|
| `TRIAGE.md` | `../ROADMAP.md:136` (re-triage), `:1003` (CR-L01-01 → **T5.3**), `:2088` (CR-L15-01 → **T16.6**) |
| `BASELINE_2026-08-28.md` | `../ROADMAP.md:1632, :1766` (**T-programme re-baseline**), `../ISSUES.md:1431`, `.claude/commands/fix-next.md:56`, `fix-parallel.md:91` |
| `FIX_PLANS.md` | `../ISSUES.md:2791`, `.claude/commands/fix-next.md:26`, `fix-parallel.md:15, :31, :56` |
| the folder as a unit | `../ROADMAP.md:133`, `../REVIEW_FINDINGS.md` (re-verification input) |

The 2026-09-08 re-triage evidence lives in `../roadmap-review/R6.md`.

> This is **not** the 2026-09-07 review. That one is `../REVIEW_FINDINGS.md` + `../review-fixes/`.
