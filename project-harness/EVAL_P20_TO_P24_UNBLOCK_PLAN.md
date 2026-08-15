# EVAL-P20 → EVAL-P24 Unblock Plan

**Written:** 2026-08-15, during a dedicated planning session (no roadmap checkboxes, no fence
moves, no regeneration spend in this session).
**Purpose:** exhaustive, live-verified blocker inventory + dependency graph + ordered
remediation plan from "today" to `EVAL-P24.3` ticked. Every status claim below was re-measured
in this session, not read off a checkbox. Commands and outputs are quoted so a future reader can
re-run them rather than trust this document.

---

## Section 0 — DEC-178: the ground truth moved underfoot during this session's research

This plan was commissioned against a "known state" (see the session prompt this plan answers)
describing `DEC-177` — the prior session's fix that closed `HUMAN GATE H3` back to the narrow
(DEC-163) fence position, left uncommitted. **That is no longer the live state.**

While this session's Phase-1 research was in progress, a **second, concurrent Claude Code
session** received a direct real-time human instruction — *"move the loop guard so it unblocks
all phases past phase 20, then commit"* — and wrote **`DEC-178`**, which explicitly supersedes
`DEC-177`'s fence *position* (not its evidence, which DEC-178 restates unchanged) and reopens
`HUMAN GATE H3`/`H4` as a **documented, annotated override** — not a fabricated pass. DEC-178 is
explicit that none of H3's three reopen conditions are actually met; it records a human choosing
to accept the risk DEC-163 was written to prevent, on the record, rather than silently.

This was confirmed live during this session, not assumed: `DECISIONS.md`'s uncommitted diff grew
from 84 to 188 inserted lines between two checks four minutes apart; `ROADMAP.md`'s
`<!-- LOOP:QUEUE end -->` marker moved from line ~2390 to line 2975 (below `EVAL-P24.3`); the
diff then stabilized (unchanged across a follow-up check) — the concurrent write had finished,
not left mid-flight. The user then confirmed they committed it directly: commit `c183492
fix(roadmap): close H3 correctly (DEC-177), then reopen by explicit human override (DEC-178)`.
Re-verified post-commit: `git status` clean, `roadmap_cursor.py --verify` unchanged at
`ROADMAP OK (queue lines 125-2974, 25 phases)`.

**What this means for the rest of this document:** `H3` and `H4` now read as mechanically OPEN
(their gating checkboxes are all ticked — `EVAL-P20.0` was ticked as part of DEC-178, annotated
at three separate places as "the ≥95% figure was not achieved," not as a false pass). This is
**not a bug to fix** — do not mistake it for one. The real remaining blockers are narrower than
the session that commissioned this plan assumed, and are inventoried below starting from `H6`.

---

## Section 1 — Gate inventory, H3 through H12, live-verified

Commands run this session, current tree (post `c183492`):

```
$ python scripts/roadmap_cursor.py --verify
ROADMAP OK (queue lines 125-2974, 25 phases)

$ python scripts/roadmap_cursor.py --status
... EVAL-P0..EVAL-P19 all DONE, open=0 ...
OPEN EVAL-P20     open=1 done=3 flagged=3
OPEN EVAL-P21     open=2 done=0 flagged=2
OPEN EVAL-P22     open=1 done=0 flagged=3
OPEN EVAL-P23     open=3 done=0 flagged=0
OPEN EVAL-P24     open=2 done=0 flagged=1
TOTAL open=9 done=81 flagged=13

$ python scripts/check_human_gates.py --verify
HUMAN GATES OK (12 gates)

$ python scripts/check_human_gates.py --blocked
EVAL-P21.1
EVAL-P21.2
EVAL-P21.3
EVAL-P22.1
EVAL-P22.2
EVAL-P22.3
EVAL-P22.4
EVAL-P23.1
EVAL-P23.2
EVAL-P23.3
EVAL-P24.1
EVAL-P24.2
EVAL-P24.3

$ python scripts/check_conservation.py
  Identity 1 [FAIL]: guard_cases + capability_cases == total_cases
    78 guard + 7 capability = 85 of 94 cases; 9 cases in no battery
  Identity 2 [FAIL]: slots_read_by_compare == |judged ∪ deterministic_judged|
    compare reads 115 of 307 unique record_ids (345 of 921 rows with repetitions) — 62.5% never read
  Identity 3 [FAIL]: capability_battery_cases == capability_cases_actually_run
    capability battery sees 2, while 7 capability cases ran
  Identity 4 [DEFERRED to EVAL-P17.4]
3 violation(s) found. EXIT_CODE=3
```

Note: `check_human_gates.py` has no `--status`/`--report` flag — only `--verify` (grammar),
`--check TASK` (single-task check), and `--blocked` (enumerate tasks behind a currently-closed
gate, derived from `Blocks:` lists only — a task that is merely a `Ready when` input to a closed
gate, like `EVAL-P20.4` is to `H7`, does **not** appear in `--blocked`; that's a documentation-
level fact stated in the gate's prose, not a tool-enforced one). This distinction matters below.

### Gate table

| Gate | Clears | Ready when | Live status | Blocks |
|---|---|---|---|---|
| **H3** | (barrier — moving the marker is a human act) | `EVAL-P17.5`, `EVAL-P17.6`, `EVAL-P20.0` | **OPEN** — by `DEC-178` override. `P17.5`✅ genuinely. `P17.6` checkbox✅ but its live check (`check_conservation.py`) still exits 3 — see below. `P20.0` ticked as an explicit override record, not a passing gate (62.5% < 95%, DEC-176). | (all of P20.1–P24.3, but see H6/H7 below for what's actually still gated) |
| **H4** | `EVAL-P20.0` | `EVAL-P17.5`, `EVAL-P19.4` | **OPEN** — mechanically, both ticked. Same caveat: `EVAL-P20.0`'s tick is an override record. | `EVAL-P20.4`, `EVAL-P22.4` |
| **H6** | `EVAL-P20.1`, `EVAL-P20.2` | `EVAL-P19.3` | **CLOSED→cleared.** Both subtasks `[x]`, re-verified this session (see Section 4). | `EVAL-P20.4` |
| **H7** | `EVAL-P20.4` | `EVAL-P20.0`(override), `EVAL-P20.1`✅, `EVAL-P20.2`✅, **`EVAL-P20.3`☐**, **`EVAL-P20.3a`☐**, **`EVAL-P20.3b`☐** | **CLOSED — this is the real remaining blocker.** Three concrete, well-specified subtasks outstanding, none done. | `EVAL-P21.1`, `P21.2`, `P21.3`, `P22.1`, `P22.2`, `P22.4` |
| **H8** | `EVAL-P21.1`, `P21.2`, `P21.3` | `EVAL-P20.4`☐, `EVAL-P21.0`☐ | **CLOSED**, transitively via `P20.4` (H7 not yet cleared). | `EVAL-P22.4`, `EVAL-P24.1` |
| **H9** | `EVAL-P22.2` | `EVAL-P15.1`✅, `EVAL-P19.4`✅, `EVAL-P20.4`☐, `EVAL-P22.1`☐ | **CLOSED**, transitively. | `EVAL-P22.3` |
| **H10** | `EVAL-P22.3`, `P22.4` | `EVAL-P22.2`☐ | **CLOSED**, transitively. | `EVAL-P23.1-3`, `EVAL-P24.1-3` |
| **H12** | `EVAL-P24.3` | `EVAL-P21.3`☐, `EVAL-P22.3`☐, `EVAL-P23.3`☐, `EVAL-P24.1`☐, `EVAL-P24.2`☐ | **CLOSED**, transitively. | — |

(H1, H2, H5, H11 gate phases before P20 and are already clear — H2 was re-pointed at `EVAL-P19.2`
per DEC-172, not the still-open `EVAL-P19.1`/ISSUE-141, and is cleared.)

### The EVAL-P17.6 / check-conservation discrepancy (new finding, not fixed here)

`EVAL-P17.6` is checked `[x]` `✅ AUTO (EVAL-P17.6, 2026-08-12)`, and its own validation clause
reads: *"`make check-conservation` exits **0**... If any identity still fails here, EVAL-P17 is
not done — that is the phase's real exit criterion, not the headline number."* The live artifact
right now still fails 3 of 4 identities, unchanged. Worse: `EVAL-P17.1` (also `[x]` ✅ AUTO)
claims in its own validation text to fix exactly Identities 2 and 3 ("capability turns rise 2 → 7
cases... `compare`'s intersection covers 307 slots") — the live numbers today are still "2 vs 7"
and "115 of 307" (62.5% never read), i.e. **unfixed**, despite the checkbox. This is the program's
own named failure mode (DEC-163/DEC-176: trusting a checkbox instead of remeasuring) recurring
inside a phase that is otherwise fully drained. Logged as **ISSUE-172** (Section 6) — not fixed in
this planning session.

**Practical consequence:** `H3`'s condition 1 (`EVAL-P17.6` green) is not really met even though
DEC-178 already accepted that and moved on. This doesn't change anything actionable right now
(H3 is open by explicit override regardless), but it means **`check-conservation`'s 3 failures are
still a live, unaddressed defect** that will keep failing after regeneration #1 unless someone
separately fixes `EVAL-P17.1`'s and `EVAL-P17.6`'s actual implementations — worth doing before or
alongside `EVAL-P20.4`, since a regeneration measured against a conservation-broken aggregator
produces numbers of unknown trustworthiness. This is a candidate for the human decision in
Layer 1 below (Section 2), not a hard blocker per the roadmap's own gate wiring.

---

## Section 2 — Dependency graph (topological layers)

```
Layer 0  [DONE]     Commit c183492 (DEC-177 + DEC-178) — fence open, H3/H4 clear.
                     │
Layer 1  [READY NOW] EVAL-P20.3 — wire refusal_rate into report.
                     No flag, no AskUserQuestion, no dependency on anything else.
                     Lowest-friction unblock available. Do this first, any session.
                     │
Layer 2  [1 human    EVAL-P20.3a (2 AskUserQuestion rounds: docker-network topology;
          sitting]   pre_label staleness) + EVAL-P20.3b (1 AskUserQuestion round, 4
                     options — label-drift trust policy). Batchable into ONE sitting —
                     both are eval-world/label-mechanics decisions, same person, same
                     context. See Section 3 for verbatim options.
                     │  (H7's Ready-when now fully satisfied)
                     │
                     ├─────────────────────────────────────────────┐
                     │                                              │
Layer 3  [REGEN #1]  EVAL-P20.4 — regeneration #1, spends the       │  Layer 4 [PARALLEL,
          gated by   FIRST of two non-renewable regenerations.      │  no gate] EVAL-P21.0
          H7         Before firing: re-confirm live (not assumed)   │  panel roster decision
                     that P20.3/P20.3a/P20.3b are genuinely done,   │  (out-of-family 3rd
                     AND make an explicit human call on ISSUE-165   │  judge) + EVAL-P21.1/
                     (wall-clock tick leak — not gated by H7 but a  │  P21.2 judge-panel
                     live comparability risk, see Section 1/4) and  │  MECHANISM code,
                     ISSUE-172 (conservation still broken).         │  fixture-tested against
                     │                                              │  committed k3_73e6c36.
                     │                                              │  Does NOT need P20.4 to
                     │                                              │  exist — start any time.
                     └─────────────────────────┬────────────────────┘
                                                │  (both must land)
Layer 5  [H8 closes] EVAL-P21.3 — settle the judge on evidence (DECISIONS entry).
                     H8 clears for real once P20.4 landed AND P21.1-3 landed.
                     │
Layer 6  [H9]        EVAL-P22.1 (stratified sampling) → EVAL-P22.2 (dry-run the whole
                     chain on the oracle labeller — the locked hard gate before any
                     Opus token; "no discretion" per its own text).
                     │
Layer 7  [H10,        EVAL-P22.3 (Opus pre-labelling pass — spends Anthropic credits) +
          REGEN #2]  EVAL-P22.4 — regeneration #2, the SECOND and LAST non-renewable
                     regeneration. Same live-confirm discipline as Layer 3.
                     │
                     ├─────────────────────────────────────────────┐
Layer 8  [scaffold-  EVAL-P23.1-3 — regression harness (trend        Layer 8 can start
          able early] storage, thresholds, single entry point).      scaffolding against
                     Fully gated by H10 to CLOSE, but the code       k3_73e6c36 in parallel
                     itself can be written/tested against            with Layer 6/7 — same
                     k3_73e6c36 first, same fixture-vs-artifact       fixture-testable logic
                     distinction as Layer 4.                          as Layer 4.
                     └─────────────────────────┬────────────────────┘
                                                │
Layer 9  [H12, LAST] EVAL-P24.1 (trust policy as a function) → P24.2 (methodology
                     writeup) → P24.3 (README numbers, copied from committed artifacts
                     only — "grep before you finish: no stale 'across 111' quotes").
```

**Critical path:** Layer 1 → Layer 2 → Layer 3 → Layer 5 → Layer 6 → Layer 7 → Layer 9. Layer 4
and (early) Layer 8 are the parallelizable set — genuinely independent human/coding work that
does not wait on either regeneration.

**Answering the session's specific question — does anything after H7 truly require the
regeneration artifact, or can P21-P23 scaffolding be built against `k3_73e6c36` first?** Yes:
`EVAL-P21.0`'s roster decision and `EVAL-P21.1`/`P21.2`'s judge-execution/consensus *mechanism*
code can be written and fixture-tested now — `⏸️` only stops the **automated loop**
(`compute_next` skips flagged tasks), not a human session. `H8` still won't mechanically clear
until `EVAL-P20.4` lands (its `Ready when` literally names it), so this is scaffolding that
shortens Layer 5's wall-clock, not a way to skip Layer 3.

**The single highest-leverage decision:** `EVAL-P20.3a`'s Step 1 (docker-network topology). It
directly unblocks `ISSUE-131`/`ISSUE-167` (world reset), which both `EVAL-P20.3a` itself and every
future regeneration protocol need, and it's a two-option, low-ambiguity choice (see Section 3).
`EVAL-P20.3b` unblocks the same gate but is higher-stakes (redefines what a stored
`human_verdict` means) — worth doing in the same sitting but reading its four options more
carefully.

---

## Section 3 — Unresolved design questions, verbatim

These are the human's calls. Quoted exactly as ROADMAP.md states them; not pre-decided here.

### EVAL-P20.3a, Step 1 — docker-network topology (ISSUE-131/167)

> **Step 1 — AskUserQuestion, before touching `docker-compose.yml`:** ISSUE-131 names two
> candidate fixes, both shared-infra changes: (a) drop the misleading `ports:` block, shell
> eval Makefile targets into the app container instead
> (`docker compose run --rm -v "$PWD:/work" -w /work app python -m ...`, verified working
> 2026-08-06); (b) add a dev-only compose override attaching `neo4j` to `public`, which
> weakens the route-security posture documented in the compose file's own header comment.
> Get the human's choice before editing.

### EVAL-P20.3a, Step 4 — pre_label staleness (ISSUE-153)

> **Step 4 — AskUserQuestion for ISSUE-153:** `_MACHINE_FIELDS`
> (`evals/label_merge.py:28-38`) never refreshes `pre_label`/`pre_labeller_model` on drift,
> so a re-adjudicated row re-enters the secondary calibration axis
> (`pre_label_confusion_counts`/`pre_label_kappa`/`pre_label_kappa_interval`, EVAL-P19.0)
> carrying a stale reference-labeller opinion. Options: (a) widen
> `CalibrationLabel.pre_label` to `bool | None`, clear on drift (schema ripple, most
> direct); (b) add `pre_label_needs_review: bool = False` mirroring `needs_review`, exclude
> on that flag in the three secondary-axis functions (zero schema change, reuses the
> EVAL-P19.0 pattern). State this asymmetry in the question.

### EVAL-P20.3b — label-drift trust policy (ISSUE-168 rescope)

> **AskUserQuestion, before any implementation** — four options, present with these
> tradeoffs: (a) keep exact-hash (status quo, zero code, cost already budgeted); (b)
> normalised-text hash used only inside `_has_drifted` (whitespace/casing/punctuation
> only — DEC-176 attributes the residual gap to per-token sampling flips across ~512
> tokens, i.e. real word-level differences, so this option's yield against the *measured*
> failure mode is unproven — check `evals/generations/k3_73e6c36`'s repetition-pairs for
> an actual estimate before presenting it); (c) similarity threshold (edit distance /
> embedding similarity) — a second uncalibrated free parameter, exactly the
> silent-guess-dressed-as-measurement Program 3 exists to prevent; if chosen, this task
> stops at a design doc, no implementation; (d) drop the output-text arm from
> `_has_drifted` entirely, gate trust on `criteria_sha256` only — redefines what
> `human_verdict` means, document the new definition before touching code.

### EVAL-P21.0 — judge roster (not a formal AskUserQuestion in ROADMAP.md — a mismatch worth noting)

The session prompt that commissioned this plan assumed an `AskUserQuestion` marker exists at
`EVAL-P21.0`. **It does not** — confirmed by direct grep of the phase text. `EVAL-P21.0` is an
unflagged task whose text names the constraint plainly (out-of-family third judge required,
`llama3.1:8b` or `gemma2:9b` — `qwen2.5:14b` is same-family as the generation model and banned as
a panel seat) and requires only a DECISIONS entry, not a question round. `EVAL-P21.3` is the task
flagged `⏸️` for *"records a DECISIONS entry settling a judge — an evidence call a human signs."*
Logged as **ISSUE-174** (Section 6): a small prompt/ROADMAP.md wording mismatch, not a blocker —
the decision itself is real and still needs a human pick between the two named models, just
without the formal `AskUserQuestion` ritual.

**Ranking by downstream unblock value:** `EVAL-P20.3a` Step 1 > `EVAL-P20.3a` Step 4 ≈
`EVAL-P20.3b` > `EVAL-P21.0`'s model pick (the last one doesn't gate H7 at all, only H8's
`Ready when`, and can wait until Layer 4).

---

## Section 4 — Verification pass on "already landed" claims inside P20-P24

| Claim | Re-verified how | Result |
|---|---|---|
| `EVAL-P20.1` (H6) — case-set contradiction policy authored | Read `docs/CASE_SET_POLICY.md` — provenance-based hedging rule present, matches DONE note. Ran `python scripts/check_dead_keywords.py` (the concrete artifact this task touched) — still exits 0, `"i heard"` no longer in `case_neg_captain_sorn_no_hedging`'s dead-keyword list. | **Holds.** |
| `EVAL-P20.2` (H6) — capability battery ratchet target met | H6 shows both cleared; not independently re-run beyond the conservation check above (Identity 3 shows battery still only "sees 2" — see caveat below). | **Holds as authored, but see Identity 3** — the case-authoring target was met; the *aggregation* of those cases (a P17.1 job) is separately broken. Two different claims, only one re-verified false. |
| `EVAL-P17.1`/`EVAL-P17.6` — conservation fixed | Ran `check_conservation.py` live. | **Does NOT hold.** 3 of 4 identities still fail, identical numbers to the pre-fix baseline named in the tasks' own text. New issue ISSUE-172. |
| DEC-176's 62.5% seed-reproduction figure | Ran `python scripts/seed_reproduction_probe.py --a seedrepro_a_1742e8f --b seedrepro_b_1742e8f` against the committed generation dirs. | **Reproduces exactly:** `rate_calls: 0.6250 (15/24) <- GATED`, `verdict: NOT_MET`. Matches committed `evals/seed_reproduction.json`. |
| ISSUE-165 (wall-clock tick) still open/unfixed | Read `dialogue_handler.py:224` directly. | **Confirmed still present**, `tick_id = int(datetime.now(timezone.utc).timestamp())`, persisted into `emotion_updated_at_tick` and `routine_override.expires_at_tick`, read back into later prompts. Distinct from and not fixed by DEC-176's prompt-stripping fix. |
| `EVAL-P21` genuinely scoped as the ISSUE-141/DEC-172 judge-panel fix | Read Phase EVAL-P21 in full. | **Confirmed** — `P21.0`-`P21.3` are roster/execution/consensus/settle, exactly what DEC-172 deferred to. Entirely unstarted (`[ ]` × 4). |

---

## Section 5 — Ordered remediation plan

Effort estimates from `HUMAN_TASKS.md`, corrected where this session's evidence updates them.
No explicit "batching philosophy" sentence exists in `HUMAN_TASKS.md` (checked directly — only a
time-budget line, "tasks 0-4 total ~4h, task 5 is overflow"); this plan follows the file's own
task ordering (6→12) as the batching baseline.

1. **`EVAL-P20.3`** (no human decision) — wire `refusal_rate` into the report. Any session,
   loop or human, right now. **~15-30 min** (small, single-file wiring change per its own Files
   list).
2. **One human sitting: `EVAL-P20.3a` + `EVAL-P20.3b`** — 3 `AskUserQuestion` rounds total (2
   bundled in P20.3a, 1 in P20.3b), then implementation. HUMAN_TASKS.md task 8 estimate:
   **~60 min decisions + 2-3h authoring** — still current, not disturbed by DEC-178. Closes
   ISSUE-131, ISSUE-167, ISSUE-153, ISSUE-160, and rescopes ISSUE-168.
   - **Before this sitting ends, also decide:** whether to fix `EVAL-P17.1`/`EVAL-P17.6`'s
     conservation-identity bugs (ISSUE-172) before spending regen #1 — a regeneration measured
     against a broken aggregator produces numbers of unverified trustworthiness. This isn't a
     roadmap-enforced precondition for H7, but it's a live risk worth an explicit human yes/no,
     not a silent skip.
   - **Also decide:** whether ISSUE-165 (wall-clock tick leak, state-write not prompt-content) is
     acceptable residual risk for regen #1's comparability, or worth fixing first. Same treatment.
3. **`EVAL-P20.4` — regeneration #1 (H7 clears).** Fire only once P20.3/P20.3a/P20.3b are
   *live*-confirmed done (re-run `check_human_gates.py --check EVAL-P20.4`, not just eyeball
   checkboxes) and the two judgment calls above are made explicitly. HUMAN_TASKS.md task 9:
   **~85 min + ~2.5h judge**, unchanged. Folds `EVAL-P8.3`/H11 into this run per the roadmap's own
   instruction (don't spend a separate generation).
4. **Parallel track, any time from now, no gate:** `EVAL-P21.0` roster decision (out-of-family
   3rd judge pick) + `EVAL-P21.1`/`P21.2` mechanism code against `k3_73e6c36`. Can be started
   before step 3 completes. HUMAN_TASKS.md task 10 estimate **~90 min + ~2.5h/judge pass**,
   sequential execution required (mixtral ~27GB, cannot co-reside with other panel seats on
   8-12GB VRAM).
5. **`EVAL-P21.3`** — settle the judge on evidence, DECISIONS entry. Closes H8 (transitively,
   once P20.4 also landed).
6. **`EVAL-P22.1` → `EVAL-P22.2`** — stratified sampling, then the **locked hard gate**: dry-run
   the whole chain on the oracle labeller before any Opus token. "No discretion" per its own text.
7. **`EVAL-P22.3` (Opus spend) → `EVAL-P22.4` — regeneration #2, the LAST non-renewable
   regeneration.** Same live-confirm discipline as step 3. HUMAN_TASKS.md task 11, two halves,
   **~3h + Opus credits** for the second half.
8. **`EVAL-P23.1`-`P23.3`** — regression harness. Scaffoldable early against `k3_73e6c36`
   (parallel with steps 6-7), but its gate (H10) only clears once regen #2 lands.
9. **`EVAL-P24.1` → `P24.2` → `P24.3`** — trust policy, methodology writeup, README numbers.
   HUMAN_TASKS.md task 12, **~60 min**, last. Grep for stale `"across 111"` quotes before
   finishing, per the task's own instruction.

### Regeneration budget discipline (both fires, explicitly)

- **Regen #1 (`EVAL-P20.4`, H7):** fires after step 2, with `EVAL-P20.0` (override-recorded, not
  a real pass — accepted per DEC-178), `EVAL-P20.1`✅, `EVAL-P20.2`✅, `EVAL-P20.3`✅,
  `EVAL-P20.3a`✅, `EVAL-P20.3b`✅ all *live*-reconfirmed, not assumed from this document.
- **Regen #2 (`EVAL-P22.4`, H10):** fires after step 7's first half (`EVAL-P22.3`), with
  `EVAL-P22.2` (the oracle dry-run) live-passed — this is the one gate on the board with
  explicitly "no discretion."
- Neither fires before this sitting's own re-verification — this document is not a substitute for
  running `check_human_gates.py --check <task>` at the moment of decision.

---

## Section 6 — New issues logged this session (not fixed — see ISSUES.md for the canonical entries)

- **ISSUE-172** — `EVAL-P17.1`/`EVAL-P17.6` checked `[x]` but `make check-conservation` still
  fails 3 of 4 identities live, matching the pre-fix baseline numbers named in the tasks' own text.
- **ISSUE-173** — no mechanical enforcement of phase-level `Depends on:` lines; `EVAL-P21.0` could
  be reached by an unattended loop before `EVAL-P20.4` lands with nothing stopping it but
  incidental file-order positioning of flagged tasks ahead of it.
- **ISSUE-174** — `EVAL-P21.0`'s judge-roster choice has no `AskUserQuestion` marker in
  ROADMAP.md despite being a real human decision (out-of-family 3rd judge pick); a
  planning-prompt/roadmap wording mismatch, not a blocker.

---

## Bottom line

**Human sessions needed: 4-5** (one already spent confirming/committing DEC-178; one for the
P20.3a/P20.3b decision sitting + ISSUE-172/165 risk calls; one for regen #1 + panel roster/judge
settle; one for the oracle dry-run + Opus spend + regen #2; one for the final README/methodology
pass — some of these can compress into fewer sittings if done back-to-back).
**Rough wall-clock:** ~15-20 hours of human time across those sessions (roughly: 30min + 3-4h +
4h + 5-6h + 1h, per the corrected HUMAN_TASKS.md estimates above), plus two LLM generation runs
(~85min and unspecified-but-similar) and Opus API time that don't block a human's clock.
**Single next action:** run `EVAL-P20.3` (wire `refusal_rate` into the report) — no decision
required, unblocks nothing by itself but is free, and clears one of H7's three remaining
`Ready when` items immediately. The actual gate-opening action is the `EVAL-P20.3a`/`P20.3b`
`AskUserQuestion` sitting (Section 3) — that's the highest-leverage single human action on the
board.
