# Adversarial roadmap review — full specification

**Target:** `project-harness/ROADMAP.md` (the T programme) at HEAD `cde995ac`, branch
`remediation-2026-08`.
**Written:** 2026-09-08. **Status:** not yet run.

This file is the complete brief. A session running this review needs only this file and the
repo — nothing else is assumed to be in context.

---

## 0. Shared preamble — EVERY lens gets this

You are red-teaming a plan, not admiring it. Your job is to find the reason this programme
fails. A review that concludes "looks solid" has failed. If you finish your scope early, go
deeper rather than stopping.

### The artifact
1,338 lines. 39 tasks total:
- **Sprint 0** (5 tasks: T0.1–T0.3, T0B.1–T0B.2) — **outside** the `LOOP:QUEUE` fence, done by hand
- **Sprints 1–8** (34 tasks, 16 phases) — **inside** the fence, run unattended
- **Sprints 9–10** — outside the fence, sketch only, human-driven

Of the 34 in-fence tasks, 29 are loop-runnable and 5 are flagged for an interactive session:
`T6.3`, `T13.1`, `T13.2`, `T15.2`, `T16.1`.

### How it was built — your highest-value target
The specs were written **from** `project-harness/REVIEW_FINDINGS.md` and
`project-harness/review-fixes/evidence/L*.md`, **not from the code directly**. Every `file:line`
in the roadmap is a transcription of a claim made by a review lens. Transcription errors are
likely, invisible, and will surface at 3am in an unattended session. Treat every cited fact as
unverified until you check it against the tree.

**Sprint 0 deserves extra suspicion:** it is five tasks written about the loop machinery by the
same author who analysed that machinery, with no independent check. It is the least verified part
of the file.

### How it will be executed
`scripts/expand_loop.sh` drives `.claude/commands/expand-linear-next.md`: **one task per Sonnet
session, one commit per task**, `make check` as the gate.

Key config (`scripts/loop.config.sh`): `CLAUDE_TIMEOUT=5400`, `MODEL=sonnet`,
`MAX_CONSECUTIVE_RED_GATES=2`, `MAX_RED_COMMITS=3`, `WITH_SERVICES=0`, `ALLOW_MAIN=0`.
`scripts/_roadmap_cursor_core.py`: `compute_next` **never returns a flagged task**.

### Measured facts — use these, do not re-derive them

| Measure | Value |
|---|---|
| `make check` | ~11m58s, exit 0 (the skill and `loop.config.sh` both still claim ~144s / 2,618 tests — stale; T0B.1 is meant to fix that) |
| `make test` | 4,571 passed / 41 skipped |
| `make test-demo` | 1,116 passed |
| coverage | 88.13% (floor 80) · evals 79.76% (floor 75) |
| mypy | 0 across 637 src files; `demo_game` ratchet `.mypy_baseline_demo` = 256 |
| LOC | tests 87,566 · src 69,247 · demo_game 36,937 · evals 23,130 · scripts 9,477 · e2e 7,605 · **total 233,962** |

### Locked decisions — do NOT relitigate
The owner decided on 2026-09-08 (see the roadmap's decisions table): delete the political/military
cluster; revive `routine`+`need` and delete `mood`+`clique`; delete `deception`+`skill` only;
collapse ports to concrete injection; aggressively prune tests; **keep and repair** the judged eval
layer; one batched prompt revision; trim `demo_game`.

You may **not** argue against these. You **must** flag any place where the roadmap mis-states their
consequences, mis-sequences them, or silently contradicts them.

### Method — non-negotiable
- Prefer "I ran it" over "it looks wrong". Every factual claim gets a command or a `file:line`.
- **Do NOT run the integration suite** — it writes to the live Neo4j; there is no test database
  (ISSUE-277).
- **Do NOT quote any judged eval score** as evidence of quality: all five scorers are REFUSED by
  `scripts/check_label_adequacy.py`.
- **Do NOT run `make check` yourself** — lens R1 runs it once and writes the output to
  `project-harness/roadmap-review/gate-baseline.txt`. Read that file.
- **Read-only.** Propose diffs; edit nothing except your own evidence file.
- The working tree has uncommitted ledger work from another session (DEC-281, ISSUE-336..340).
  Do not commit, revert, or tidy it. The next free issue id is **341**.

### Calibration — three known defects
Given as examples of the **shape** to hunt. Confirm or refute each, then find the ones **not**
listed. These three are the floor, not the target.

1. **T9.1** instructs "work in batches of about five ports per commit" — but the loop is
   one-task-one-commit. Several tasks may be written multi-session and scheduled as one.
2. **The skill halts on ask-gate conditions** (deleting files you did not create, public-interface
   changes with outside callers, graph schema changes). Sprints 2/3/5 do all three **by design**
   with owner pre-approval — but the executing agent has no way to know that and may halt on tasks
   it is supposed to do.
3. **SEV-07 is missing entirely.** The gossip tick costs 24,252ms against 433–570ms for
   neighbouring ticks — HIGH, zero LLM calls, fix brief already written at
   `review-fixes/FIX-SEV-07.md` — and appears nowhere in the roadmap. One HIGH finding was dropped
   in translation. **Find the others.**

### Output contract
Write ONE file: `project-harness/roadmap-review/<LENS>.md`

```
### [<LENS>-NN] <title>
Severity: CRITICAL | HIGH | MEDIUM | LOW · Confidence: Confirmed | Likely | Suspected
**Affects:** <roadmap task ids>
**Evidence:** command output, or file:line
**Why it breaks the programme:** one or two sentences
**Proposed fix:** a concrete diff or edit to the roadmap
```

Severity means impact **on the programme**:
- **CRITICAL** — a task cannot be executed as written, or execution corrupts the repo or the record
- **HIGH** — a task will be done wrong, or a needed outcome silently never happens
- **MEDIUM** — wasted sessions, rework, or a misleading record
- **LOW** — friction

Close with **6-month predictions**: each MUST name a trigger observable by week 2, in the form
"if `<observable X>` by task `<N>`, this is happening". A prediction you cannot check early is not
actionable.

**Return terse:** counts by severity · your 3 worst finding ids · verdict (executable as written,
YES/NO) · anything needing an owner decision.

---

## 1. Lens scopes

### R1 — Ground truth *(runs `make check` once; owns `gate-baseline.txt`)*

Verify every factual claim in all 39 tasks. Mechanical and exhaustive, not a sample.

1. Every path in every `Files:` line — does it exist? For deletion tasks, does the thing to be
   deleted actually exist? For "new test …" paths, is the parent directory real?
2. Every cited `file:line` in every `Spec:` — open it and confirm it says what the spec claims.
   There are roughly 150. A wrong line number is a defect; a line that says something different is
   a worse one.
3. Every **RED anchor**. Where the anchor is a grep, run it and report the count. Where it is "this
   test fails today", verify the premise is still true. **Report every anchor that is already
   GREEN** — that means the task is a no-op or misspecified, and it is the single most valuable
   thing you can find.
4. Every command in every `Validation:` line — does the make target exist? Does the pytest path
   resolve?
5. Named constants and settings: `MAX_DELTA_TICKS`, `MAX_WS_CONNECTIONS_PER_KEY`,
   `TICK_LLM_CALLS_PER_MINUTE_MAX`, `LLM_TIMEOUT_SECONDS`, `MAX_CONCURRENT_TICKS`, `timeouts_ms` —
   confirm each exists where the roadmap says, with the value it claims.
6. **Include Sprint 0:** verify ISSUE-139's whole-tree-staging claim, the lock path
   `project-harness/.loop-state/loop.lock`, `expand_loop.sh:648`'s no-progress guard, and the
   skill's stale "300-line" / "144s" claims.

Run `make check` **once**, save full output to `project-harness/roadmap-review/gate-baseline.txt`,
and report what is red today. R3 and R4 depend on that file.

### R2 — Cascade coherence

Simulate T0.1 → T16.2 in order and find where the plan eats itself.

1. Build a ledger: for each task, what it **deletes** and what it **creates**. Then find every later
   task referencing something an earlier task removed.
2. Audit every hardcoded list against the post-deletion tree:
   - T6.2's expected tick-order sequence (Sprint 2 deletes ~11 engines first)
   - T9.1's "known keepers" port list — does it name a port Sprint 2 deletes?
   - T15.2's expected-to-work engine list
   - T4.2's exempt-dirs list
3. Do any `evals/cases/*` reference a deleted engine? The owner is **keeping** the eval layer, so
   eval breakage is real breakage.
4. After deleting the `faction_politics`/`treaty`/`oath` **engines** while keeping their graph
   **services**: the demo reads data nothing writes any more. Does any demo beat, poller or scripted
   act depend on a standing or treaty **changing** rather than merely existing?
5. Sprint 7 trims `demo_game` — does it delete the tests T5.1/T5.2 add under `demo_game/tests/`?
6. T5.2 revives `need_quest_trigger`, increasing LLM load, **before** Sprint 4 bounds it. Is
   Sprint 3 → Sprint 4 the right order, or should it invert?
7. Sprint 0 is outside the fence: is there anything that **mechanically** stops Sprint 1 starting
   first? The roadmap claims T0.1's worktree preflight is that block. Verify or refute.

### R3 — Harness executability

Can the loop plus a Sonnet session actually run each task? Read
`.claude/commands/expand-linear-next.md`, `scripts/expand_loop.sh`, `scripts/loop.config.sh`,
`scripts/loop_gates.py`, `scripts/scan_fix_diff.py`, `scripts/_roadmap_cursor_core.py`.

1. **Size** every one of the 39 tasks against one session and one commit. Flag every task that
   instructs batching, multiple commits, or is simply too large. Estimate file-touch count.
2. **Halt-guard collisions:** list every task that would trip the skill's own halt table (ask-gate,
   live-task, needs-decision, blocked-prerequisite). Sprints 2/3/5 delete files and change public
   interfaces by design. Propose the minimal mechanism that tells the agent these are pre-approved.
3. **Flag tokens:** scan all 39 task bodies for the deferred glyph, `ask-gate`, and `(live`. Confirm
   exactly 5 in-fence tasks are flagged (T6.3, T13.1, T13.2, T15.2, T16.1) and none is flagged by
   accident. Note ISSUE-134: the scan is a substring match over the whole body.
4. **Gate duration:** the roadmap adds ~5 new gates to `make check` (T4.2, T10.1, T10.2, T12.1).
   `make check` is already ~11m58s. Estimate the end-state duration and check it against
   `CLAUDE_TIMEOUT=5400` and against what the skill tells the agent to expect.
5. `scan_fix_diff.py` treats `tests/` as a **frozen path** for repair sessions. T11.1 deletes tests
   deliberately. What happens if T11.1 reds the gate and triggers the autofix path?
6. `WITH_SERVICES=0` means integration tests skip and `make check` executes **zero real Cypher**.
   Sprint 2 deletes 11 engines and their repositories under that gate. Is that safe?
7. **Sprint 0's own tasks:** are they executable by hand as written? T0.1 changes how the loop
   launches — does anything else in the repo assume the primary checkout?

### R4 — Gate & metric conflict

Find where the roadmap's own gates fight the roadmap's own work. Read `gate-baseline.txt` from R1
rather than running `make check`.

1. **Coverage vs the prune:** T11.1 aggressively deletes tests → coverage falls → the 80/75 floors
   red → but T12.2 lowers the floors **afterwards**. Since `make check` is the per-task gate, does
   T11.1 red the gate and get committed UNVERIFIED? If so, what is the correct order?
2. **LOC ratchet vs additive work:** rule 1 says non-test src LOC may only fall, and the gate lands
   in T10.2 (Sprint 5). Sprints 6–8 then **add** code (T12.1 gates, T15.1 `working_set` + metrics,
   T16.2 histogram buckets). Does the ratchet block them? Also: it counts non-test **src** only — is
   there a loophole where logic migrates to `tests/`, `scripts/`, `evals/` or `demo_game/` to dodge it?
3. `check-mutations` and `check-test-quality` are both in `make check`. How do they behave when
   T11.1 removes ~20–30k LOC of tests?
4. Each new gate ships its own tests under `tests/unit/scripts/`. Harness self-test failures
   currently HALT the night (T0.3 fixes this). Quantify how much the T programme enlarges that surface.
5. `rules_baseline.txt` / the R001 size ratchet / `.mypy_baseline_demo=256`: deleting files changes
   all three. Which tasks need a baseline update, and does any task need `make check-rules-update` —
   which `scan_fix_diff` explicitly forbids repair sessions from running?
6. Are the 9 rules in the preamble mutually consistent, and does any gate contradict `CLAUDE.md` as
   it stands?

### R5 — Product regret and 6-month rot

Judge as a product owner, and as someone maintaining this in 2027.

1. After Sprints 2 and 7, does the demo still tell the story the product exists to tell — NPCs that
   remember, feel, and gossip? Walk `docs/DEMO_SCRIPT.md` against what survives.
2. The roadmap claims the deleted political engines are recoverable from git in "1–2 sessions for
   all six". **Test that claim:** read one deleted engine and estimate honestly what restoring it
   into the post-Sprint-5 codebase (ports collapsed, gates added) costs. If the claim is optimistic,
   say so — the owner's decision rested partly on it.
3. Which deletions will be regretted? Be specific about which studio pitch each supports.
4. **Rot:** which of the 9 rules decays into ceremony? Consider `dip_waivers.txt` filling up, the LOC
   baseline being bumped routinely until it means nothing, the demo mypy ratchet never moving, the
   deferred backlog never draining.
5. **Perverse incentives:** what does each gate reward that you would not want? A reverse LOC ratchet
   rewards dense unreadable code and migrating logic to uncounted directories.
6. What does this programme **not** fix that will still hurt in 6 months?

### R6 — Backlog coherence

Does the T programme relate honestly to everything else already open?

1. **Coverage of the review that spawned it:** `review-fixes/INDEX.md` lists 15 Fix-now SEVs. Map
   each to a roadmap task. SEV-07 is already known missing — find every other gap. Then do the same
   for `REVIEW_FINDINGS.md`'s 68 findings: which have no task and no issue?
2. **The open ledger:** ~120 open issues in `ISSUES.md` (now through ISSUE-340). Which does the T
   programme close, which does it silently orphan, and which does it **contradict**? Concrete example
   to check: ISSUE-338 concerns `scenario_mood_contagion`, but Sprint 2 deletes the `mood` engine
   outright — is that issue about to be made moot, and does anyone know? Also check ISSUE-339 (probes
   requesting engine status under an unregistered name) against T15.1.
3. **The 2026-08 review:** `review-2026-08/TRIAGE.md` holds 118 canonical findings including 4
   surviving CRITICALs. Is the T programme a successor to it or a parallel backlog? Name any CRITICAL
   from that set the T programme does not address.
4. The 9 `DEC-274`..`DEC-280` decision stubs the 2026-09-07 review opened: which are now answered by
   the owner's locked decisions and should be closed, and which are still genuinely open?
5. Is there now more than one place a contributor must look to know what to work on? If so, say what
   should be canonical.

---

## 2. Synthesis pass (S) — run after all six report

Read all six evidence files. **Do not re-derive their findings and do not run the lenses again.**
You are merging, ranking and turning them into an actionable patch list.

Write `project-harness/roadmap-review/FINDINGS.md`:

**§1 Verdict.** One paragraph. Is the T programme **executable as written — YES or NO**? Lead with
any CRITICAL. If NO, name the smallest set of patches that makes it YES.

**§2 Severity counts.** Table, with lens-prefixed ids.

**§3 Dedupe ledger.** The lenses overlap by design — R2 and R3 on ordering, R4 and R6 on baselines,
R1 and R2 on hardcoded lists. For every finding reported by two or more lenses, merge into one id
and record the merge. A finding two lenses reached independently is **stronger**, not redundant —
say so.

**§4 Systemic clusters.** Root causes across lenses, not a list of symptoms. Expected candidates:
transcription drift from the evidence files, roadmap-vs-harness impedance mismatch, gates fighting
the work they gate. Lead with whichever cluster blocks execution.

**§5 The patch list.** The deliverable. An **ordered** list of concrete edits to `ROADMAP.md`:

| # | Task(s) affected | Edit | Why | Mechanical or owner-decision? |

Ordered so that applying them top to bottom never invalidates a later one. Mark each **mechanical**
(apply directly) or **owner-decision** (needs a human call — say exactly what is being decided and
give the options with trade-offs).

**§6 Owner decisions.** Pull every owner-decision patch into one place so the owner reads a short
list, not a long report.

**§7 Consolidated 6-month predictions.** Deduped across lenses, each with its week-2 trigger. Drop
any prediction whose trigger is not actually observable — that is the test of whether it was a real
prediction or a worry.

**§8 Confidence ledger + what was NOT checked.** Counts by Confirmed/Likely/Suspected. **Nothing
graded Suspected may appear as a mechanical patch** — it is owner-decision or it is verified first.
Then state plainly what this review did not cover, so the gaps are known rather than assumed away.

**Constraints:** do **not** edit `ROADMAP.md` — the patch list is the output, and the owner chooses
what to apply. Do not fix the code. Commit only the files under
`project-harness/roadmap-review/`.
