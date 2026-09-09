# `project-harness/` — what is in here

The project's own working memory: ledgers, roadmaps, and the closed records of past reviews.
No product code lives here.

**Start with [`CLAUDE.md`](CLAUDE.md).** Its *Orientation* table is the canonical index of what to
read for a given question, and it is auto-loaded into every session. This file does not repeat it —
it maps the folder, and says what a new session should *skip*.

## A new session opens four files

| File | Why |
|---|---|
| `ROADMAP.md` | **Canonical for what to work on next.** The T programme, 16 phases. Everything else defers to it. |
| `ISSUES.md` | Open issues only. Fixed ones move to `archive/ISSUES_RESOLVED.md`. |
| `DECISIONS.md` | Architecture decisions and open questions. |
| `PATTERNS.md` | Reusable patterns, added on second use. |

`CLAUDE.md` names these as the **only** copies — never create root-level duplicates.

## Everything else at the top level

Live — read when the task touches them:

| File | What it is |
|---|---|
| `HARNESS_GATES.md` | What each `make` gate checks. Cited by `scripts/harness_status.py`. |
| `OVERNIGHT_LOOP.md` | The unattended roadmap loop: how it runs, what it may do. Several T tasks **edit** this file. |
| `human_verification.md` | Loop-written log of gates that stayed red. Appended at runtime by `scripts/loop.config.sh`; not hand-edited. |

Closed records — **do not work from these**, they are superseded by `ROADMAP.md`:

| File / folder | Closed | What it is |
|---|---|---|
| `REVIEW_FINDINGS.md` + `review-fixes/` | 2026-09-08 | The **2026-09-07** full review (68 findings) and its backlog. Has its own README. `ROADMAP.md` still reads `FIX-SEV-07.md` and `evidence/L13.md` as live task input. |
| `CODEBASE_REVIEW.md` + `review-2026-08/` | 2026-08-28 | The **2026-08** strategic review (118 canonical findings). Has its own README. `CODEBASE_REVIEW.md` is 580 KB of raw synthesis — `/fix-next` and `/fix-parallel` explicitly tell you not to read it. |
| `roadmap-review/` | live audit trail | The 2026-09-08 adversarial review **of `ROADMAP.md` itself** — 6 lenses, 77 findings. `FINDINGS.md` holds the finding→task mapping; `R1.md`–`R6.md` are the lenses. Leave as-is. |
| `EVAL_P25_TO_P31_PLAN.md` | superseded | The eval programme P25–P31. Kept in place: `docs/ENGINE_EVAL_COVERAGE.md:27,133` cites it by path. |
| `OVERNIGHT_LOOP_PLAN.md` | superseded by `OVERNIGHT_LOOP.md` | The Windows port brief. Kept in place: `DECISIONS.md:2159` cites it as the full port brief. |
| `SKILLS_QUEUE.md` | retired 2026-09-01 | Read-only. Not deleted because `demo_game/ui/layout/right_panel.py:101` cites an entry (`docs/overview.md:42`). Do not append — open questions go to `DECISIONS.md`. |
| `UNREAL_DEFERRED.md` | 2026-07-31 | Deferred Unreal/Unity client plans. Finding CR-L12-01 is about this file being a side file the loop cannot see. |

Folders:

| Folder | What it is |
|---|---|
| `archive/` | Retired documents, named `<ORIGINAL_NAME>_<what-it-was>_<YYYY-MM-DD>.md` and dated by the content's last meaningful date. Holds `ISSUES_RESOLVED.md`, four superseded `ROADMAP_*.md`, and three older review cycles. |
| `proposals/` | Historical `PROJECT_PLAN_v1.*.xml` and `proposals/archive/`, which still holds the phases 0–13 roadmap cited by `ROADMAP.md:131`. |

## Not in git — local artifacts only

`logs/`, `overnight_logs/`, `.loop-logs/` (465 files), `.loop-state/` and `PROMPT_*.md` are all
gitignored and **zero of their files are tracked**. They are machine-local run output and one-shot
prompts, not repository content, so they will not appear in a fresh clone and cannot be moved by
`git mv`. `overnight_logs/` and `.loop-state/gate_baseline.json` are written by the loop at runtime.

## Why so little has been archived

Almost every top-level file is pinned by a path citation from `ROADMAP.md`, `DECISIONS.md`,
`docs/`, `scripts/` or `.claude/commands/`. Moving one silently breaks a task spec or a tool.
Before moving anything out of here, rebuild the citation list and update every hit in the same
commit — the tables above record the pin for each file.
