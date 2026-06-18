# Archived — 2026-06-03 codebase review cycle

Archived 2026-06-05 after the review/remediation cycle completed, to keep `project-harness/` clean
for the expansion phase. Nothing here is needed for day-to-day feature work.

## Contents
- `REVIEW_FINDINGS.md` — the multi-agent audit synthesis (BLOCK, 43 findings: 2 CRITICAL + 16 HIGH + …).
- `FINAL_REVIEW_FINDINGS.md` — the final hardening-review findings (L1–L9 lenses; the L7 expansion-readiness
  cluster fed `expansion/FEASIBILITY.md`).
- `review-fixes/` — the per-SEV remediation briefs (`FIX-SEV-01…43`) + `INDEX.md` (carry-forward + ordered
  checklist) that drove `/fix-next` and `/fix-parallel` for this cycle. Most items are `[x]` done.
- `review-evidence/` — raw logs/evidence captured during the review (gitignored; present locally only).

## For a future review
The `/fix-next` and `/fix-parallel` skills still point at the **canonical** path
`project-harness/review-fixes/` (NOT this archive). A future review run regenerates `REVIEW_FINDINGS.md`
and `review-fixes/INDEX.md` fresh at that canonical location — this folder is the historical record of the
2026-06-03 cycle, not an input to the next one.

Cross-references elsewhere in the harness (e.g. `expansion/BUSINESS_INTENT.md`, `DECISIONS.md` history,
`DEMO_WALKTHROUGH.md`) cite `project-harness/FINAL_REVIEW_FINDINGS.md` / `REVIEW_FINDINGS.md` by their
original top-level path — those are point-in-time citations; the content they reference now lives here.
