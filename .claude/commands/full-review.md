---
description: Full codebase + demo review (night run). Fans out read-only reviewer agents across 9 lenses (engines AND demo_game), synthesizes findings, and regenerates the /fix-next + /fix-parallel backlog.
argument-hint: "[--inline] [--lenses L1,L6,L9]  (optional; default = all lenses, parallel)"
---

You are the ORCHESTRATOR of a full, regression-aware review of the WHOLE codebase —
both the engine (`src/npc_engine/`) and the demo (`demo_game/`). You do **not** fix
anything. Your single job is to produce a triaged findings report plus a remediation
backlog that `/fix-next` and `/fix-parallel` can consume directly. Work LEAN; keep all
summaries terse; never paraphrase files back to me.

This is designed to run **autonomously overnight** ("night run"): dispatch read-only
reviewer subagents in parallel, let them write per-lens evidence, then synthesize. The
review is **read-only** — neither you nor any worker edits source code, only the review
artifacts under `project-harness/`.

## Invariants (never violate)
1. **Read-only.** No source edits, no commits to `src/` or `demo_game/`. The only files
   written are the review artifacts in §6. Workers are explicitly read-only.
2. **Regression-aware.** Every prior fix must be re-verified, not assumed. Read the most
   recent archived review first (see §1) and confirm each prior SEV still holds.
3. **Cover both halves.** A finding set that ignores `demo_game/` is incomplete. L6 owns
   the demo; L9 actually runs it. Engine-only is a failed review.
4. **Output format is a contract.** `/fix-next` and `/fix-parallel` read
   `project-harness/review-fixes/INDEX.md`, the `FIX-<SEV>.md` briefs, and
   `project-harness/REVIEW_FINDINGS.md`. Produce exactly those, exactly there.
5. **One reality check.** Asserted-not-measured is the recurring failure of past reviews:
   a guard test that verifies a constant in isolation while the real path is unprotected.
   Prefer "I ran it / I traced the call site" over "the test exists."

## 1. Baseline + prior-art (do first, cheaply)
- `git status` must be clean. If dirty, STOP and tell me — a review of a dirty tree is noise.
- Record date (`2026-..`), branch, and HEAD commit for the report header.
- Read the newest archived review for regression context: the most recent
  `project-harness/archive/review-*/FINAL_REVIEW_FINDINGS.md` (currently `review-2026-06-03/`)
  — specifically its severity table and §2 systemic patterns. These become L8's checklist.
- If a CANONICAL review already exists (`project-harness/REVIEW_FINDINGS.md` or a non-empty
  `project-harness/review-fixes/`), archive it first: move both into
  `project-harness/archive/review-<its-date>/` so this run writes fresh. Note the move.

## 2. The lenses (9; each → one read-only worker)
Every lens worker writes ONE evidence file to `project-harness/review-fixes/evidence/<Lx>.md`
with this shape: a re-verification table of relevant prior SEVs (HOLDS / PARTIAL / REGRESSED),
then findings, each as `### [Lx-NN] <title>` + `Severity: CRITICAL|HIGH|MEDIUM|LOW · Confidence:
Confirmed|Likely|Suspected`, with **file:line evidence** and a one-line fix sketch. No fixes.

| Lens | Agent (`subagent_type`) | Scope |
|------|-------------------------|-------|
| **L1 Security** | `security-reviewer` | `auth/`, `api/`, `config/`, LLM/Neo4j boundaries: input caps (`MAX_PLAYER_MESSAGE_CHARS`, `delta_ticks` bounds), auth on every non-`/health` route, prompt-injection, secret handling, error-message leakage, WS connection cap actually enforced. |
| **L2 Architecture** | `architect` | Layer model (run `make check-layers`), DIP (engines import protocols not concretes), no LLM in `graph/`/`retrieval/`, no Neo4j outside `graph/`, no prompt strings outside `prompts/`, single composition root, session ownership. |
| **L3 Types & boundaries** | `python-reviewer` | Pydantic v2 on every module boundary (no raw `dict` crossing), `Literal`/`Enum` for fixed sets, `response_model=` on routes, no magic numbers/strings, `from __future__ import annotations`, mypy clean (`make` type gate). |
| **L4 Tests & efficacy** | `code-reviewer` | Coverage gaps, **asserted-not-measured** guard tests, mock validity (LSP: mocks match real adapter contract), Neo4j-touching code has real integration tests, LLM code has mock-adapter tests, eval battery isn't purely-negative. |
| **L5 Cleanliness** | `refactor-cleaner` | Dead code, duplication, 300-line file limit (+ existing DEC-waivers), 40-line funcs, ≤3 nesting, module/class/function docstrings present, orphaned bridge/temp files. |
| **L6 Demo / product** | `general-purpose` | **`demo_game/` correctness** (zero `src/` imports), `client.py` API calls match live routes, win/lose reachability in `game_end_checker.py`, poller/panel wiring, scenario integrity (`run.py`/`run_scenes.py`), branch/economy/content depth, `make test-demo` health. Plus product-level engine gaps. |
| **L7 OCP / expansion** | `architect` | Open-Closed seams for the roadmap: new LLM backends, distortion types, emotion models, location hierarchy — added by NEW file, never editing a closed module. Flag any variant that requires editing an existing engine. |
| **L8 Regression** | `general-purpose` | Mechanical: each prior-review SEV that was marked done — is the code still present AND the guard test still meaningful? Cross-check the archived `FINAL_REVIEW_FINDINGS.md` table. Catch "DONE overstated / partially landed." |
| **L9 Live verification** | `general-purpose` | Actually RUN it: `make check`, `make test`, `make test-demo`, `make demo-run ARGS=--dry-run`, and a container-boot sanity check (does a fresh checkout build a bootable app? the prior CRITICAL was a deleted runtime file). Report what's red on the current tree. Live-only breaks the static lenses can't see. |

If `$ARGUMENTS` contains `--lenses L1,L6,...`, run only those. Otherwise run all 9.

## 3. Dispatch (parallel, background, read-only)
Unless `$ARGUMENTS` contains `--inline`, launch one `Agent` per lens with
`run_in_background: true`, **capped at 4 concurrent** (dispatch the next as earlier ones
report). Use `model: sonnet` for L1–L8; L9 may use the default. Each worker prompt MUST say:

> READ-ONLY review. Do NOT edit any source file, do NOT commit. Obey `project-harness/CLAUDE.md`
> as the rubric (layer model, 300-line files, 40-line funcs, Pydantic boundaries, typed/Literal
> fixed sets, structured logging, auth+input-caps, fallback contracts). Re-verify the prior SEVs
> I list, then hunt new issues. Cite file:line for everything. Write your evidence to
> `project-harness/review-fixes/evidence/<Lx>.md` in the required shape. Prefer "I ran/traced it"
> over "the test exists" — call out asserted-not-measured. Return: counts by severity, your 3
> highest-severity finding ids, and anything that needs a human decision (schema/dependency).

For `--inline`: skip subagents and work each lens yourself in sequence, writing the same
evidence files. Slower, no spawn cost.

## 4. Synthesize → REVIEW_FINDINGS.md
When all lenses report, read the evidence files and write `project-harness/REVIEW_FINDINGS.md`:
- **Header**: date, branch, HEAD, "Mode: 9-lens parallel review (engines + demo)", prior-review pointer.
- **§1 Verdict**: one paragraph — is the tree release-clean? Lead with any CRITICAL.
- **§2 Severity counts** table (CRITICAL/HIGH/MEDIUM/LOW with the lens-prefixed ids).
- **§3 Systemic patterns**: root-cause clusters across lenses (the high-value section).
- **§4 Triage table**: every finding → `id | sev | title | lens | disposition` where disposition
  is **Fix now** / **Log** (defer to ISSUES.md) / **Decide** (needs my call: schema, dependency,
  interface change). Assign each Fix-now/Log finding a fresh monotonic **SEV-NN**.

## 5. Generate the fix backlog (the /fix-* contract)
- Create `project-harness/review-fixes/INDEX.md`: a **Carry-forward notes** block at the top
  (≤10 lines, starts empty), then an ordered `[ ]` checklist of every **Fix-now** SEV grouped
  into dependency blocks (A–F style), each line: `[ ] SEV-NN — <title>  (deps: …, file set: …)`.
  Mark **Decide** items clearly as blocked-pending-approval; **Log**-only items go to ISSUES.md, not here.
- For each **Fix-now** SEV write a self-contained `project-harness/review-fixes/FIX-SEV-NN.md`:
  **Problem**, **Current shape** (cited files+lines, verified against the code now), **Steps**,
  **Verification** (a concrete unit test + the exact command — e.g. `pytest tests/unit/<...>` then
  `make check`/`make test-demo`), **Blast radius**. A cold worker must need nothing but this brief
  and its cited files.
- For **Log** findings, append `ISSUE-NNN` entries to `project-harness/ISSUES.md` (monotonic id,
  the standard format). For **Decide** findings, append a `DECISIONS.md` question stub.

## 6. Artifacts written (and ONLY these)
- `project-harness/REVIEW_FINDINGS.md`
- `project-harness/review-fixes/INDEX.md`
- `project-harness/review-fixes/FIX-SEV-*.md`  (one per Fix-now item)
- `project-harness/review-fixes/evidence/L1..L9.md`
- appended entries in `project-harness/ISSUES.md` (Log) and `DECISIONS.md` (Decide)
Commit them in one `docs(review): full codebase+demo review <date> — findings + fix backlog`
commit on the current branch. No source changes in this commit.

## 7. Stop
STOP. In ≤10 lines: the verdict (release-clean? any CRITICAL), severity counts, the count of
Fix-now SEVs in the backlog, anything flagged **Decide** (needs my call), and the next step
("run `/fix-parallel` for the parallelizable batch, `/fix-next` for serial/blocked items").
Do NOT start fixing — that is `/fix-next`'s job.
