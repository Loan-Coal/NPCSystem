# FINDINGS — adversarial review of the T programme

**Target:** `project-harness/ROADMAP.md` at HEAD `c7c55f9a`, branch `remediation-2026-08`.
**Run:** 2026-09-08. **Lenses:** R1 ground truth · R2 cascade coherence · R3 harness
executability · R4 gate & metric conflict · R5 product regret · R6 backlog coherence.
**Inputs:** `R1.md`, `R2.md`, `R3.md`, `R4.md`, `R5.md`, `R6.md`, `gate-baseline.txt`.
**77 findings.** This file merges, ranks and turns them into a patch list.

---

## §0 Disposition — APPLIED 2026-09-09

**All 39 patches in §5 have been applied to `ROADMAP.md`**, plus banners on
`review-fixes/INDEX.md` and `review-2026-08/TRIAGE.md`. The 15 owner decisions in §6 were put to the
owner and answered; §5 and §6 below are the *pre-decision* record and are left unedited so the
reasoning stays auditable. Where an answer differed from the review's recommendation, the roadmap
follows **the owner**, not this file.

**Owner answers that diverged from the recommendation:**

| # | Decision | Recommended | Chosen |
|---|---|---|---|
| OD-5 | Rules copied into `CLAUDE.md` | only the gated four | **all nine** — T10.2 must label rules 2, 7, 8, 9 as ungated |
| OD-6 | 800-line "hard and unwaivable" vs the 925 baseline | amend the wording | **leave it**; T14.2 resolves the only instance |
| OD-7 | Political-engine recoverability estimate | correct it now | **leave it**, re-measure if a studio asks |
| OD-10 | The two live 2026-08 CRITICALs | fold one, file one | **fold both** — now T5.3 and T16.6 |
| OD-15 | DIP waiver cap / date-as-gate / rule 8 script | adopt them | **none** — recorded in the preamble as deliberately unenforced |

**Two decisions the review did not put in §5 and should have**, both raised and answered separately:
DEC-280(a)'s `demo-run-live` nightly gate (**adopted**, now **T2.4**), and the general
"read path outlived its writer" detector (**declined**; T3.2's completion note is the control).

**One owner instruction overrode a review patch outright.** Patch 2 proposed narrowing T3.1's delete
target to `agenda_engine.py`. The owner instead removed `agenda` from the delete set entirely on
2026-09-09. T3.1 is now "Delete `succession` and `oath`", and the consequence the review had not
traced was verified before applying: `PoliticalGraphPort` and `Neo4jPoliticalRepository` are shared
by `agenda_engine.py:18,36` and `succession_engine.py:18,35`, so **both survive**, and
`api/dependencies_advanced/politics.py` survives carrying `get_agenda_engine` alone. Deleting either,
as the original T3.1 instructed, would have broken the engine the owner chose to keep.

**Verification after applying:** `make roadmap-verify` → `ROADMAP OK (16 phases)`; the loop's own
parser returns `verify() == []` with **46 in-fence tasks, 40 loop-runnable, exactly 6 flagged**
(T6.3, T13.1, T13.2, T15.2, T16.1, T16.4) and **no accidental flags** — all four in-file mentions of
`ask-gate` sit outside the fence. `pytest tests/unit/harness/ tests/unit/scripts/` → 448 passed,
**the same 2 pre-existing failures and no new ones**. Those two are the CRITICAL this review found,
and they are now scheduled as **T0.0**; applying the patch list does not fix them, because fixing
them is a code change in a frozen path that must be done by hand.

**Task count moved 37 → 46.** Nine tasks added: T0.0, T2.4, T4.3, T5.3, T7.3, T15.3, T16.6, and
T9.1 split into T9.1a–d.

---

## §1 Verdict

**Executable as written: NO.**

`make check` is **red at HEAD** (exit 2), and no task in the programme fixes it. Two tests in
`tests/unit/harness/test_roadmap_cursor.py` fail because the commit that authored this roadmap
moved the LOOP:QUEUE fence and left the tripwire pinned to the retired M programme
(`_EXPECTED_PHASE_IDS = ["M1","M2"]` at `:201`; `EXPECTED_FLAGS = {}` at `:171`). Three lenses
found this independently. Its consequences are total: every one of the 39 tasks ends
`Done when: make check is green`, so none can be honestly ticked; `gate_attribution.py:65` can
never return GREEN, so every task commits and emits `TASK_COMPLETE_BASELINE_RED`; the phase gate
reds at every boundary and `MAX_CONSECUTIVE_RED_GATES=2` ends the night after two phases; and
`make check` aborts at target 14 of 23, so nine gates — including every gate that notices a
deletion (`check-api-contract`, `check-api-stability`, `check-migrations`, `check-engine-logs`)
— have never been observed on this tree. The fix lives in `tests/`, the first entry in
`FROZEN_PATH_PREFIXES`, so no repair session can ever make it. The programme cannot start.

Six further CRITICALs sit behind it: T3.1's `Files:` line deletes a whole directory containing a
**live, wired tick engine**; 18 in-fence tasks trip the skill's own halt table by design, and a
halt discards the **whole phase**, so Sprint 2 most likely never runs; `demo_game/seeds/seed.py`
is at **exactly** its R001 baseline of 1677, so both of Sprint 3's loop-runnable tasks are
structurally guaranteed to red a gate their repair session is forbidden to fix; the five gates
the programme installs are invisible to `classify_gate_failure.py` and turn every future
violation into an undiagnosable night-ending halt; T0.1's mandated worktree has no `.venv` and no
`.env`, so the first `make check` there dies on a missing toolchain; and the fence actually holds
**37 tasks and 6 flagged tasks**, not the 34/5 the roadmap states — with T16.4 invisible in all
three places the roadmap records deferred work, including T0B.2's own RED anchor.

**Smallest set of patches that makes it YES:** patches **1–8** in §5 — add `T0.0` (repair the
tripwire, by hand, before anything else); correct T3.1's delete target; adopt the `Pre-approved:`
token and teach the halt table to read it; resolve `seed.py`'s R001 headroom; register the five
new gates in `loop_gates.py`; provision the worktree in T0.1; correct the 37/6 counts and T0B.2's
anchor; and add the four missing `Files:` entries (the repository re-export barrel,
`dependencies_engines/core.py`) without which Sprint 2's first task reds on a file it may not
touch. Everything after patch 8 raises quality; those eight decide whether the loop runs at all.

---

## §2 Severity counts

| Lens | CRITICAL | HIGH | MEDIUM | LOW | Total |
|---|---:|---:|---:|---:|---:|
| R1 ground truth | 2 | 5 | 7 | 2 | 16 |
| R2 cascade coherence | 0 | 3 | 2 | 3 | 8 |
| R3 harness executability | 4 | 5 | 5 | 1 | 15 |
| R4 gate & metric conflict | 3 | 6 | 8 | 2 | 19 |
| R5 product regret | 0 | 4 | 4 | 2 | 10 |
| R6 backlog coherence | 0 | 4 | 4 | 1 | 9 |
| **Raw total** | **9** | **27** | **30** | **11** | **77** |
| **After dedupe (§3)** | **7** | **22** | **26** | **11** | **66** |

CRITICAL ids: `R1-01` `R1-02` `R3-01` `R3-02` `R3-03` `R3-04` `R4-01` `R4-02` `R4-03`.
Nine raw → seven merged.

---

## §3 Dedupe ledger

Fourteen merges. **A finding two lenses reached independently is stronger, not redundant** —
each merge below records that the lenses used *different methods* and converged.

| Merged id | Lens findings | Sev | Why the convergence matters |
|---|---|---|---|
| **S-01** red gate at HEAD | `R1-01` + `R3-01` + `R4-01` | CRITICAL | **Three lenses, three routes.** R1 found it by running `make check`; R3 by tracing `gate_attribution.py`/`run_phase_gate` from the harness side; R4 by reading the baseline and following `classify_gate_failure.py`. R4 alone found the *second* stale constant, `EXPECTED_FLAGS = {}` at `:171` — fixing only the phase ids makes `:331` fire instead. This is the single most-corroborated finding in the review. |
| **S-02** fence is 37 tasks / 6 flagged; T16.4 invisible | `R1-03` + `R3-02` | CRITICAL (R3) / HIGH (R1) | Both ran the loop's own parser. Take the higher grade: T0B.2's RED anchor asserts a five-element set and will be **falsified on first run**, so the task that exists to stop deferred work vanishing is itself blind to a deferred task. **Orchestrator note:** `R4-01`'s *proposed* T0.0 tells the implementer to record "the five flagged tasks" — that draft would re-break the tripwire. Verified independently: `grep -n "⏸️" ROADMAP.md` returns **six** lines (667, 1063, 1084, 1186, 1209, 1296). Patch 1 uses six. |
| **S-03** T14.2's anchor is false | `R1-04` + `R4-13` | HIGH | R1 read `check_rules.py`'s docstring and scan set; R4 read the baseline file and cross-checked R1's gate output. Same conclusion by different evidence: `demo_game/` **is** scanned, and `game_window.py` is silent only because it is grandfathered at exactly 925 — 125 lines past a limit `CLAUDE.md` calls "hard and unwaivable". |
| **S-04** T14.1 asks for a ratchet that exists | `R1-05` + `R4-14` | HIGH | R1 verified the error/file/checked counts match `.mypy_baseline_demo` exactly (256/45/184); R4 verified `type-demo` is absent from `Makefile:432`. The real task is one Makefile word, not a session of building a second ratchet. R4 adds that `check_harness_honesty.py` reads only `.mypy_baseline`, so a 256-error ratchet stays invisible to the honesty gate. |
| **S-05** T11.1's category (a) is already green | `R1-06` + `R4-08` | HIGH | Independent methods, different populations, same verdict. R1 ran an AST scan of `tests/` → ~105 no-assert functions and 67 `quality-ok:` markers. R4 re-ran **the real scanner with waivers disabled** → 60 findings (21 NO_ASSERTION, 31 BARE_EXCEPTION_RAISES, 8 VACUOUS_MOCK) and 66 markers. R4's number is the one to put in the roadmap (it is what the gate would report); R1's is the wider population. ISSUE-234 says 25; it is 21. |
| **S-06** T4.2's census does not classify `emotion/` | `R1-14` + `R2-05` | MEDIUM | R1 enumerated all 37 `engines/` entries and found six dir↔ordered-name mismatches besides; R2 found `emotion/` specifically and confirmed it **is** imported from `api/routes/dialogue/npc_state.py`, i.e. live and load-bearing. Together: the gate has an undefined outcome on live code, plus a name-mapping problem R2 did not see. |
| **S-07** execution contract item 4 is false | `R3-10` + `R4-11` | MEDIUM | Both ran the same check on `Makefile:432`. `roadmap-verify` is **not** a prerequisite of `check`. R4 extends it: `check-mutations`, `check-conservation` and `check-label-survival` are also ungated, and `mutation_probe.py` mutates `evals/` only — so the brief's question about `check-mutations` under a test prune resolves to "it is not a gate at all". |
| **S-08** coverage vs the prune | `R3-08` + `R4-10` | HIGH mechanism / MEDIUM trigger | **The two halves disagree and both are right.** R3 proved the *mechanism*: `loop_gates.HALT_CHECK_SPECS` runs pytest without `--cov-fail-under`, so a coverage-only red yields zero failing node ids and `gate_attribution` reports `BASELINE_RED` — the task commits and ticks under-floor. R4 **refuted the brief's premise with numbers**: headroom is 1,486 statements; losing *all* `graph/repositories` coverage lands at 83.3%; Sprint 2's deleted set is 863 statements at 95.8%, so deletion *lowers* the headline only 87.97→87.57. Net: the floors will not be crossed, so T12.2 as written performs the ceremony its own sentence warns against — but the blind spot is real and should be written down anyway. |
| **S-09** LOC ratchet: loophole + ordering | `R4-06` + `R4-07` + `R5-05` | HIGH | R4 measured the loophole (70.4% of the repo — 164,715 LOC — uncounted) and found the programme is its **first user**: ~2,500 LOC of new gate code lands in `scripts/` and `tests/`. R5 reached the same place from the rot angle: a ratchet bumped on a predictable cadence within the programme that installed it teaches "ask for an exception". R4-06 adds the ordering half: T10.2 installs the ratchet in Sprint 5, three sprints before the last additive src work (T15.1, T16.2), and neither task lists `loc_baseline.txt` in `Files:`. |
| **S-10** gate-surface files are not frozen | `R4-05` + `R5-04` | HIGH | R4: `loc_baseline.txt`, `dip_waivers.txt`, `check_test_quality.py` and its baseline are absent from `FROZEN_PATH_PREFIXES`, so a bounded repair session can launder them green — the exact laundering `scan_fix_diff.py:9-14` was written to prevent. R5: the waiver file's only enforced property is "cites a `DEC-NNN`", which is a citation, not an argument. Same organ, two failure modes: it can be filled legitimately forever, and it can be filled *automatically*. |
| **S-11** deferred work has no forcing function | `R5-07` + `R5-09` + `R3-02` | HIGH | R5 found first-party precedent in the roadmap's own Provenance note — R6.1-3 sat archived-and-unticked through a whole review cycle, which is why Sprint 0 exists at all. T0B.2 is explicitly "a report, not a gate". Sprints 9/10 have no owner and no date, and Sprints 6–8 spend real effort (T16.3-T16.5) on infrastructure whose entire payoff is conditional on Sprint 9 running. |
| **S-12** T0.1 does not do what the roadmap claims | `R2-01` + `R3-03` | CRITICAL (R3) | R2 refuted the *claim*: `_roadmap_cursor_core.py` structurally cannot see outside the fence, so Sprint-0 completeness is invisible to the cursor and the "mechanical block" is worktree-location only. R3 refuted the *mechanism*: `.venv` and `.env` are gitignored, `Makefile:1-7` falls back to ambient `python`, and the `/fix-parallel` precedent T0.1 cites never ran `make check` in a worktree. Together the task is both over-claimed and under-specified. |
| **S-13** SEV-07 and the wider traceability gap | `R1-07` + `R6-01` + `R6-07` | HIGH | Calibration item 3 **confirmed**: SEV-07 appears nowhere, fix brief already written. R1 adds that SEV-02/SEV-03 survive only under L-ids, so `INDEX.md` can never be reconciled. R6 found the larger version: two 2026-08 CRITICALs (`CR-L01-01` gossip distortion written-never-read; `CR-L15-01` eval live-network digest defaults) verified **still live in the tree today** and absent from the roadmap under any id, plus 14 Log-dispositioned findings — including three security ones — neither scheduled nor parked. |
| **S-14** wrong path `demo_game/game_window.py` | `R1-09` + `R4-13` | MEDIUM | Both resolved it to `demo_game/ui/layout/game_window.py`. R1 adds three more bad paths and one absent parent directory (`tests/unit/demo/`), and notes `DEC-074` records the file under a *third* path. |

Findings **not** merged, recorded so they are not mistaken for duplicates: `R6-02` (ISSUE-338 /
`scenario_adapters_extra.py`) sits outside `evals/cases/`, so R2's eval sweep could not have
caught it — a genuine inter-lens gap, not double-counting. `R4-19` and `R2-07` are explicit
**refutations** (T6.1 does not break `check-api-contract`; no hardcoded keeper list names a
Sprint-2 deletion, and no eval case functionally depends on a deleted engine) — recorded so the
owner does not re-litigate them.

---

## §4 Systemic clusters

Four root causes. The first blocks execution and everything else waits behind it.

### C1 — The gate is off, and the programme is written as if it were on *(blocking)*
`S-01`, `S-07`, `R4-12`, `R3-13`, `R4-03`, `S-08`.

Every task's `Done when:` is `make check` green; `make check` has been red since the commit that
wrote the roadmap; the failure is in a frozen path no repair session can reach; nine of 23 targets
have never run on this tree at all. Around that sit three smaller instances of the same shape: the
contract names a gate mechanism that is not wired (`roadmap-verify`), the loop's classifier cannot
see any gate the programme adds, and a coverage breach produces zero failing node ids so it is
reported as `BASELINE_RED` rather than as a coverage failure. **The common form is a gate that
reports success or silence where it should report a failure** — which is precisely the defect
class the programme's own preamble was written about ("a gate that green-lights a broken product
is worse than no gate"). The programme reproduces it in its own machinery.

### C2 — Roadmap-vs-harness impedance mismatch
`S-03` (via `R3-04`), `R3-05`, `R3-06`, `R3-07`, `R3-09`, `R3-12`, `R4-02`, `S-12`.

The roadmap was written as a *plan for a competent engineer*; it is executed by a cheap model
inside a rigid harness. Every place the two disagree, the harness wins silently. Tasks instruct
batching against a one-task-one-commit loop (T9.1: 70–100 file touches, five stated commits, five
gate runs ≈ 60 min of a 90-min budget). Tasks instruct `git stash` / a second `git worktree`
against a driver that refuses a dirty tree. Eighteen tasks trip a halt table that keys on tokens,
not on the prose sentence saying "the owner decided 2026-09-08 to delete" — and a halt discards
the **whole phase**, so a halt on T3.1 silently loses T3.2 as well; two such phases ends the
night. Four deletion tasks cannot be completed inside their declared `Files:` set because nobody
listed the re-export barrel `graph/repositories/__init__.py`. Sprint 3's two tasks both grow a
file sitting at exactly its R001 baseline. **The remedy is uniformly cheap** — a machine-readable
`Pre-approved:` token, four added `Files:` lines, one baseline entry, one task split — but none of
it happens by itself, and the failure mode of each is a silent skip, not an error.

### C3 — Transcription drift from the evidence files
`S-03`, `S-04`, `S-05`, `S-14`, `R1-08`, `R1-10`, `R1-11`, `R1-13`, `R1-15`, `R2-03`, `R1-02`.

The spec predicted this and it is confirmed at scale. R1 opened 85 citations: **68 exact, 10 off
by 1–3 lines, 4 out of range or past EOF, 3 wrong path** — and, more seriously, **five RED anchors
are already GREEN or misspecified**: T11.1(a), T14.1, T14.2, T1.1's "introduce a constant that
already exists", and T0B.2's expected flag set. An anchor that is green on arrival means the task
is a no-op the agent will tick having done nothing. The severe end of this cluster is not an
offset: T3.1's `Files:` line says delete `engines/agenda/`, a directory whose spec describes one
module but which also holds `intent_formation_engine.py` — **live, wired at `tick_slots.py:25,116`
and `tick_scheduler.py:360`**. Read literally at 3am, Sprint 2's most mechanical task removes a
working engine. R2 found the same shape one layer out: two of L13.md §A.2's twelve
read-after-write pairs name engines Sprint 2 deletes two phases earlier, and T6.2 says "each
pair", full stop.

### C4 — The programme is not an honest successor to the backlog it replaces
`S-13`, `S-11`, `R6-02`..`R6-09`, `R5-01`, `R5-02`.

The roadmap brands itself the successor to everything before it. It is not, and nothing says so.
One HIGH finding with a fix brief already written (SEV-07, 24.25s gossip tick) was dropped in
translation. Two CRITICALs from the 2026-08 review are **verified still live in the tree** and
absent under any id — one of them, gossip distortion written and never read back, silently defeats
the exact mechanic the product pitch rests on and sits directly downstream of Sprint 3's revival
work. Fourteen Log findings, three of them security (weak-secret validation, unbounded admin
lists, `/setup` prefix-match), are neither scheduled nor listed as parked, unlike ISSUE-322/323/335
which the owner parked in writing. `DECISIONS.md` still reads "OPEN / pending" for DEC-275/276/279
which the roadmap answered. Five documents now claim to be an authoritative backlog with no stated
precedence. And two claims the owner's own decisions rest on are overstated: political-engine
restoration is "1–2 sessions for all six" when the *cheapest* engine alone is ~3–4.5 hours into the
post-Sprint-5 codebase, and `docs/DEMO_SCRIPT.md` Act 5 plus `demo_game/runners/run.py` still
narrate a battle that T1.2 makes impossible, in the sprint whose stated goal is "the demo works".

---

## §5 The patch list

Ordered so that applying top to bottom never invalidates a later patch. New task ids (`T0.0`,
`T4.3`) do not renumber anything. **M** = mechanical, apply directly. **OD** = owner-decision.

| # | Task(s) | Edit | Why | M/OD |
|---:|---|---|---|:---:|
| **1** | new **T0.0** (Sprint 0, before T0.1) | Add a hand-run task: re-point `tests/unit/harness/test_roadmap_cursor.py` — set `_EXPECTED_PHASE_IDS` (`:201`) to the 16 T phases **and** populate `EXPECTED_FLAGS` (`:171`) with the **six** flagged tasks (T6.3, T13.1, T13.2, T15.2, T16.1, **T16.4**), updating the dated history comment per that docstring's own contract. `Done when:` `make check` runs past target 14 for the first time and the completion note records which of the nine never-reached targets pass, plus the true green duration. | `make check` is red at HEAD; the fix is in a frozen path no repair session can touch; without it all 39 tasks commit `BASELINE_RED` and the night halts after two phases. Use **six**, not five — `R4-01`'s draft says five and would re-break the tripwire. | **M** |
| **2** | **T3.1** | `Files:` — replace `delete src/npc_engine/engines/agenda/` with `delete src/npc_engine/engines/agenda/agenda_engine.py`. Add to `Spec:` that the directory also holds `intent_formation_engine.py` (live: `tick_slots.py:25,116`, `tick_scheduler.py:360`) and `conversation_intent_service.py`; **the directory survives**; audit the service for callers and log an issue if it has none. | A literal read deletes a working, wired tick engine. R1 confirmed the other eight `delete <dir>/` lines are safe as written. | **M** |
| **3** | **T1.2, T3.1, T3.2, T4.1** | Add `src/npc_engine/graph/repositories/__init__.py` to all four `Files:` lines; add `src/npc_engine/api/dependencies_engines/core.py` to T3.2's (it builds `FactionPoliticsEngine` at `:150`, imports its repo at `:157`). Add step (10) to T3.1's deletion checklist: "its re-export in `graph/repositories/__init__.py` and `engines/ports/__init__.py` — the barrels keep a deleted module importable until edited, and are the single most likely cause of a red gate on a deletion task." | Without this the first Sprint-2 task reds on an `ImportError` caused by a file it was told it may not touch; its only in-contract exits are a phase-discarding halt or a contract violation. | **M** |
| **4** | **T4.2, T10.1, T10.2, T12.1** | Add `scripts/loop_gates.py` to each `Files:`; add to each `Done when:` "the new target is appended to `AUTOFIX_CHECK_SPECS` (form-class), and its script **and** any baseline/waiver file it reads are appended to `FROZEN_PATH_PREFIXES`." While there, freeze the three already-unprotected entries: `check_test_quality.py`, `check_test_quality_baseline.txt`, `evals_baseline.txt`, `engine_logs_baseline.txt`. Add to the Sprint 5/6 headers: "these sprints edit `loop_gates.py` — do it with the loop stopped." | Unregistered gates classify as `UNATTRIBUTED` (exit 3): no repair, red counter, night ends with a message naming neither gate nor cause. Unfrozen baselines can be laundered green by an unattended repair session — `loc_baseline.txt` and `dip_waivers.txt` are exactly the shape `scan_fix_diff.py:9-14` exists to prevent. | **M** |
| **5** | **T0.1** | Add `Makefile` to `Files:`. Add to `Spec:`/`Validation:`/`Done when:`: the preflight must also verify, in the worktree, that `.venv` resolves to a working interpreter and `.env` exists, failing with the exact provisioning commands; `OVERNIGHT_LOOP.md` must carry the full recipe (`git worktree add` → create/link `.venv` → copy `.env` → one hand-run green `make check`) before the loop starts. State plainly that the `/fix-parallel` precedent does **not** cover this: those workers gate serially after fan-in and never run `make check` in a worktree. | `.venv`/`.env` are gitignored; `Makefile:1-7` falls back to ambient `python`; every one of the 23 targets dies. T0.1's preflight makes this the *only* way to start. | **M** |
| **6** | **ROADMAP.md:139-141** | Stop calling T0.1's preflight "the mechanical block" that enforces Sprint 0 first. State: only the worktree-location half is enforced in code — `_roadmap_cursor_core.py` cannot see outside the fence, so Sprint-0 completeness is invisible to the cursor. Either accept that as operator discipline (naming the specific defects T0.2/T0.3/T0B.1 fix, of which T0B.1's stale "144 s" is the night-losing one), or have the preflight grep the raw file for unticked `T0.2/T0.3/T0B.1/T0B.2`. | The roadmap advertises a mechanical gate for a real safety property that the named mechanism does not provide. | **M** |
| **7** | **ROADMAP.md:92-93, :270, :288-294** | Correct the counts: the fence holds **37** tasks and **6** flagged. Add a T16.4 row to the Deferred backlog table. Change T0B.2's RED anchor to "must list T6.3, T13.1, T13.2, T15.2, T16.1 **and T16.4** today — six." Add to T0B.2's `Done when:` that the carry-forward note, the backlog table, `make roadmap-audit`'s output **and** `EXPECTED_FLAGS` must agree, asserted against the real file. Replace "the roadmap carries the backlog section" (already true — `:278-299`) with that reconciliation. | Verified: `grep -n "⏸️"` returns six lines. T0B.2's anchor is falsified on first run; one third of its finish line is pre-satisfied; and the task built to make deferred work visible is blind to a deferred task. | **M** |
| **8** | 18 tasks + **T0B.1** | Add a machine-checkable `Pre-approved: <class> · owner 2026-09-08 · DEC-279` line (vocabulary limited to `file-deletion`, `public-interface`, `graph-schema`, `new-dependency`) to T1.2, T3.1, T3.2, T4.1, T5.1, T5.2, T6.1, T7.1, T8.2, T9.1, T9.2, T10.2, T11.1, T11.2, T13.2, T15.1, T16.3, T16.4, T16.5. Add a fourth correction to T0B.1 teaching the skill's halt table to recognise it (class must match the action), and to its `Done when:` "a dry run over T3.1 confirms the agent does not halt." | Sprints 2/3/5 delete files, change public interfaces and add edge types **by design**; the halt check runs before the agent reads prose. A halt discards the whole phase (`expand_loop.sh:551`) and two consecutive ones end the night — and phases T3 and T4 both open with a deletion task. **See OD-1: the alternative is running these 18 interactively.** | **OD** |
| **9** | **T5.1, T5.2** | Resolve the `seed.py` headroom. Minimum: add `scripts/rules_baseline.txt` to both `Files:` and `make check-rules-update` to both `Validation:`, stating the new count and reason in the commit. Preferred: insert **T4.3** before Sprint 3 splitting `demo_game/seeds/seed.py` by seeded domain, preserving every NPC id verbatim. | `wc -l` = **1677**; `rules_baseline.txt:5` = `R001|demo_game/seeds/seed.py:1677`. One added line hard-reds `check-rules`, and the repair session's only legal remedy is splitting a 1,677-line seed file — which risks renaming NPC ids the roadmap calls stable. **See OD-2.** | **OD** |
| **10** | **T5.2** | Add `src/npc_engine/type_registry/base_edges/has_need.yaml` to `Files:` and a prerequisite paragraph: `HAS_NEED` is used in production Cypher (`need_queries.py:33,61,95`, `need_writer.py:27,50`) but is **not** declared in the registry — only `SATISFIES_NEED` is. Declaring it is part of this task and is pre-approved; conform to the existing writer at `need_writer.py:50`. | T5.1 sets the explicit precedent "if the registry declares no type, halt". An agent applying that rule four lines later loses phase T5 and takes T5.1 with it; one that does not, writes an undeclared edge under a schema-enforcing layer. | **M** |
| **11** | **T4.2, T10.1, T15.2** | Replace the `git stash` / second-`git worktree` RED anchors with a read-only extraction: `git archive <pre-sprint-sha> \| tar -x -C <tmpdir>` and a `--root` flag each new gate script must accept. Record the pre-sprint SHA in the completion note; it must report the deleted engines against that tree and zero against the current one. | The loop refuses to start on a dirty tree and a stray stash poisons the next run; a nested worktree inherits the same missing toolchain. These three anchors are the *only* proof the new gates check anything, and T4.2 says so itself. `--root` also makes each gate testable from `tests/unit/scripts/` with no git operation. | **M** |
| **12** | **T4.2** | Add `emotion` to the non-tick-engine list; add the name-mapping caveat (`skill`→`skill_progression`, `mood`→`mood_contagion`, `need`→`need_decay`, `memory`→`memory_decay`, `scheming`→`scheme_advance`, `investigation`→`scheme_detection`) and the direct-call paths (`routine` `:464`, `chapter` `:467`, `memory_consolidation` `:535`, `story_pacing` ctor `:60`, interval gossip/event). Instruct the script to **fail loudly** on any directory matching none of the buckets. | `emotion/` declares no `run_tick` and is in neither exempt list, yet is imported by `api/routes/dialogue/npc_state.py` — live code with an undefined outcome in the gate whose `Done when:` is "green on this tree". | **M** |
| **13** | **T6.2** | Add: "Two of L13.md §A.2's twelve pairs (`mood_contagion` reading `routine`, `faction_politics` reading `gossip`/`event`) name engines Sprint 2 already deleted — skip them; ten pairs remain." | The evidence table is frozen from before Sprint 2's deletions were decided; "each read-after-write pair" is literally impossible by the time T6.2 runs. | **M** |
| **14** | **T11.1** | Rewrite category (a): `check-test-quality` reports 0 because all findings carry `# quality-ok:` waivers (**66** markers). Re-run the scanner with waivers ignored — **60 findings: 21 NO_ASSERTION, 31 BARE_EXCEPTION_RAISES, 8 VACUOUS_MOCK** (2026-09-08). ISSUE-234 says 25; it is 21 — correct it when closing. Add the coverage note from `R3-08` (a coverage-only red yields zero node ids → `BASELINE_RED`; record `make test-cov \| tail -3` before and after; if coverage falls below 80, **do not tick**). Add the loop note: every failure this task can cause lands on a frozen path, so leave the tree green and fix form-gate reds in *this* session — nothing downstream can. | The sprint whose goal is "every surviving test can fail" is gated by a check that already reports success against ~105 tests that cannot. The prescribed scan returns zero on arrival. | **M** |
| **15** | **T12.1** | Require the extension to keep `check_test_quality_baseline.txt` at `0` (missing work belongs in T11.1, not a raised baseline); require the gate to report the waiver count and each `# quality-ok:` to name a specific contract; point the scanner at **both** test roots via a `--tests-dir` list and record `demo_game/tests/`'s count separately. Add to T11.1's `Done when:` that `grep -rn 'assert hasattr\|iscoroutinefunction' tests/` returns only specifically-waived lines. | The new detectors surface 30+ findings against a baseline of 0 the moment they land — the gate T12.1 writes reds the gate T12.1 must pass. And `demo_game/tests/` (87 files, 15,852 LOC, **1,097 test functions = 25.6% of the repo's tests**) is invisible to rule 5's gate — exactly where Sprint 3 puts both its RED anchors. | **M** |
| **16** | **T12.2** | Make instruction (3) conditional: re-measure both floors and **lower one only if the measured value is within 2pp**; otherwise record the numbers and leave the floors alone. Correct the evals aggregate: **82.79%** re-measured 2026-09-08, not 79.76%, and re-run `make test-cov-evals` at the moment of writing `BASELINE_2026-09.md` rather than copying from the roadmap. Add "close ISSUE-321". Add to T11.2's `Done when:` "report the coverage delta; if it exceeds 3pp, stop — you deleted more than delegate tests." | Measured headroom is 1,486 statements; the prune cannot cross the floor. Lowering it anyway is the ceremony the task's own sentence warns against — and seeding a new immutable baseline from a stale aggregate is how the last baseline stopped meaning anything. | **M** |
| **17** | **T14.1** | Rewrite the premise: `demo_game/` is *ratcheted but not gated* — `make type-demo` drives `mypy_ratchet.py` against `.mypy_baseline_demo` (=256, matching `python -m mypy demo_game` exactly) but `type-demo` is absent from `Makefile:432`. Add it to `check:`, then drive the count down from the post-T13.2 tree with `make type-demo-update`. **Do not build a second ratchet.** Note that `check_harness_honesty.py` reads only `.mypy_baseline`, so a non-zero demo baseline is invisible to the honesty gate. | Building a thing that exists either ships a duplicate or burns the session discovering the premise was wrong — and neither outcome adds `type-demo` to `make check`. | **M** |
| **18** | **T14.2** | Correct the path to `demo_game/ui/layout/game_window.py` throughout (and in T13.1, and `DEC-074`'s third variant). Delete "today it does not, because the file is not scanned" and "getting it to report is half the task". New anchor: `grep -n game_window scripts/rules_baseline.txt` returns `R001|…:925` — scanned, and baselined past a limit `CLAUDE.md` calls unwaivable; remove the row, confirm `check-rules` reports it, then split the file. Note CR-L02-04 is about `src/` sub-packages and does not transfer. | Both clauses of the anchor are false; an agent can "get it to report" by changing nothing and tick with the file still at 925. **See OD-6 on the 800-line contradiction.** | **M** |
| **19** | **T1.1, T7.1, T8.2, T9.2, T1.2, T6.1, T16.1, T13.1** | Apply R1's citation corrections: delete T1.1's "introduce `PROACTIVE_DRAIN_POLL_SECONDS`" (it exists at `dialogue_ws.py:45`, used at `:233`); `tick_budget_guard.py:76-83`→`:54-61` (+ "only caller `tick_autopilot.py:102`"); bump T8.2's four `llm_config.yaml` citations by 2; T9.2 — `RoutineOverridePlan` is from `event_emission_service.py:19`, only `_EventNode` from `event_writer.py:20`, and `quest_port.py` holds **four** sibling protocols; T1.2 — replace `tests/unit/engines/military/` with the five flat test paths, re-home the new test to `tests/unit/seeds/`, and add the sixth wiring site `tick_scheduler.py:329`; T6.1 `:461`→`:464`; T16.1 `engines/quest/`→`engines/quest_generation/`; T7.2's `Files:` likewise. Add `tests/unit/engines/test_emotion_updater.py` to T9.1's `Files:`. | Ten citations off by 1–3, four out of range or past EOF, three wrong paths, one absent parent directory. Individually trivial; collectively they train the agent to distrust `Spec:` — and T1.1 is the *first* task the loop runs. | **M** |
| **20** | **T0.2, T0.3** | Replace T0.2's structurally-unmatchable anchor (`loop-state/loop.lock` is composed from variables) with `grep -rn "rm -rf.*loop.lock\|stale lock" …`; correct `:648`→`:649`. Add to T0.3's `Done when:` that it changes the **phase** gate's routing only — `gate_attribution.py` is untouched, so a red harness self-test still makes every task report `BASELINE_RED`; that is T0.0's job. Add `scripts/expand_loop.sh` to T0.3's `Files:` and require that a harness-classified red does not increment `CONSECUTIVE_RED_GATES`. Add the T11.1 caveat: bucket on the test's **path**, never on which task was running. | An anchor that stays red after the fix cannot distinguish done from not-done; and T0.3 cannot deliver its stated outcome from the two files it lists, because the decision that ends the night is in `expand_loop.sh:430-443`. | **M** |
| **21** | **T0B.1** | Add two stale facts to its correction list: the skill says "Never read the whole ROADMAP.md — it is 1183 lines" (it is 1,429), and the gate-duration correction must carry its budget consequence — at ~12 min a gate run is ~13% of the 90-minute timeout, so **run the full gate at most twice**; use targeted `pytest` for iteration. | R1 confirmed the three stale facts T0B.1 already names; these are the fourth and fifth. The bare number does not tell the agent to budget gate runs, which is the actual failure (three runs = 36 min before a line is written). | **M** |
| **22** | **T4.2, T10.1, T10.2, T12.1** | Move each gate's *own* test to `tests/unit/scripts/test_<script>.py` (product tests stay put — T12.1's `test_create_app_auth_wiring.py` is correctly a product test and must **not** move into the skip bucket). T10.2 currently lists no test file at all. | T0.3 defines the harness-self-test bucket as `tests/unit/scripts/` + `tests/unit/harness/`, but as written only 1 of 5 new gates lands there and two ship with no self-test — against `CLAUDE.md`'s own "every public function gets a happy-path and a failure test" and every existing gate's precedent. | **M** |
| **23** | rule 1, rule 9, **T10.2, T15.1, T16.2** | Widen rule 1 to non-test LOC across `src/npc_engine/`, `scripts/`, `evals/` and `demo_game/` **in total**, with the four counts reported separately so a migration is visible; seed `loc_baseline.txt` with one line per directory plus a total. Amend rule 9 to name what it measures. Add `scripts/loc_baseline.txt` to T15.1's and T16.2's `Files:` with a deliberate-bump instruction. Note the uncounted-directory limitation next to rule 1 in prose. | 70.4% of the repo (164,715 LOC) is outside the src-only ratchet, and the programme is its first user (~2,500 LOC of gate code into `scripts/` + `tests/`). Rule 9 is contradicted in the roadmap's own text (T16.3 "+15", T16.4 "+10"). **See OD-3 and OD-4.** | **OD** |
| **24** | **T10.2** | Copy into `CLAUDE.md` only the rules that carry a gate — 1, 3/6, 4, 5 — each naming its `make` target; leave 2, 7, 8, 9 in `ROADMAP.md` as programme policy with one pointer line. Amend rule 3 to match its gate (it covers `Settings` fields, prompt YAMLs and contract YAMLs — **not** public functions). Amend rule 5 to acknowledge the waiver and require a specific reason. Record in `DECISIONS.md` that T8.2 and T2.1 are deliberate exceptions to rules 2 and 8. | Four of nine rules have no gate, and `CLAUDE.md` closes with "prefer adding a gate over adding prose (DEC-249)" and opens with "a copy here is a copy that rots". Nine copied rules is nine more rots, four of them ungated. **See OD-5.** | **OD** |
| **25** | execution contract (items 4, new 6) | Correct item 4: `roadmap-verify` is **not** a prerequisite of `check` (`Makefile:432`); what guards the queue inside `make check` is `tests/unit/harness/test_roadmap_cursor.py`. Note `check-mutations`, `check-conservation` and `check-label-survival` are also ungated. Add item **6 — Baselines**: if `check-rules` reports "N baselined violation(s) resolved", run `make check-rules-update` in the **same** commit and state N; this is a task-session action, never a repair-session one; same for `make type-demo-update` and `loc_baseline.txt`. | Seven tasks (T1.2, T3.1, T3.2, T4.1, T9.1/T9.2, T13.2, T14.2) need `check-rules-update` and exactly one names it. The nag is live today (ISSUE-320) and prints on every run until Sprint 7 — ~30 sessions of gate output carrying an instruction the session believes it is forbidden to follow. | **M** |
| **26** | **T13.1, T13.2** | Add to T13.1: compute the census over `demo_game/` **excluding** `tests/`; judge `demo_game/tests/` by whether the module it tests survives, not by whether the test file executed during a live run. Change T13.2's RED anchor to assert by name that `demo_game/tests/seeds/test_seed_schedules.py` and `test_seed_needs.py` are still present, not merely that the aggregate count balances. Note the TREATY/OATH tabs as known deletion candidates. | No test file is ever executed by the demo *process*, so the stated method returns "dead" for **every** test in `demo_game/tests/` — including the two T5.1/T5.2 add four sprints earlier. The existing anchor is tautological for this failure mode. | **M** |
| **27** | **T1.2** | Add `src/npc_engine/graph/military/` (579 LOC, 3 modules) to the delete list, with the verifying grep. Add to T3.2's `Done when:` a live confirmation that `GET /v1/admin/factions/` returns a **non-empty** standings list, not merely a 200. Extend T10.2's `check_dead_surface.py` scope to `src/npc_engine/graph/` modules with no importer outside their own package. | `WITH_SERVICES=0` means `make check` executes zero real Cypher, so a service that survives deletion but returns nothing looks identical to one that works. And 579 LOC of dead Cypher survives a programme whose rule 3 is "no code without a live caller". *(Graded Likely by R3 — verify the grep before applying.)* | **M** |
| **28** | fence prose | Add a `---` rule immediately before each `# SPRINT n` heading inside the fence (7 places). Add to T0B.2: `--audit-deferred` must print the **matched line** that caused each flag, with a fixture whose sprint heading contains `ask-gate`. | `BLOCK_END_RE` matches `##`–`####` but **not** a level-1 `# `, so the last task of every phase absorbs the next sprint's prose into its flag scan. The roadmap discusses `ask-gate` at `:255`; one paragraph moving inside the fence silently defers a task, and `compute_next` walks past it without a word. Today's file is clean — this is a one-line-edit away from not being. | **M** |
| **29** | **T4.1, T15.1, T12.2, T1.2, T3.1** | Ledger reconciliation: add `evals/scenario_adapters_extra.py` to T4.1's `Files:` and instruct deleting/retargeting `scenario_mood_contagion` and marking ISSUE-338 superseded; add a cross-reference to T15.1 that it does **not** fix ISSUE-339 (probe engine-name mismatch), which must land before probes can observe `working_set_size`; add "close ISSUE-321" to T12.2; record in T1.2 that it resolves DEC-274 by a **fourth** option not listed in that DEC; add a housekeeping line updating DEC-275/276/279's `Decision:` field. | After T4.1, ISSUE-338's proposed fix ("assert a mood *change*") becomes actively wrong advice for an engine that no longer exists. Two documents both claim to record what was decided and disagree on *status*. | **M** |
| **30** | Parked section | Correct the recoverability claim: recoverable in **source**, but restoration into the post-Sprint-5/6 codebase (concrete injection, DIP/LOC/dead-surface gates, pinned tick order, a deleted `Settings` field and its factory module) is a redesign per engine — budget **one engine per session minimum**, more for `agenda` and `military`. Note separately that `military` needs a *cadence/trigger design*, not code recovery: restoring it as-is restores the tick-5 auto-lose. | Measured for `treaty`, the cheapest of the six (182 LOC): ~3–4.5 hours, against the ~15–30 min/engine "1–2 sessions for all six" implies. The owner's decision rested partly on this. **See OD-7.** | **OD** |
| **31** | **T1.2** or **T13.2** | Rewrite `docs/DEMO_SCRIPT.md` Act 5 and `demo_game/runners/run.py`'s ACT 5 block to replace the military beat with one the surviving engines can produce, or delete Act 5 and renumber. Neither file is in any task's `Files:`. | Act 5 narrates "battle resolved. Iron Legion wins" and the sign-off checklist *requires* a visible battle event — after T1.2 the tick fires and nothing writes one. The census would mark the beat "executed" (it runs; it produces nothing). This is the studio-facing script, in the sprint whose goal is "the demo works again". **See OD-8.** | **OD** |
| **32** | Sprint 4 / new task | Schedule **SEV-07** (gossip tick 24,252 ms vs 433–570 ms for neighbours, zero LLM calls) from the existing brief at `review-fixes/FIX-SEV-07.md`. Append `SEV-02` to T7.1's finding line and `SEV-03` to T7.2's so all 15 SEVs are greppable in `ROADMAP.md`. | Confirmed absent. One HIGH finding with a written fix was lost in translation, and `review-fixes/INDEX.md` — a checkbox list keyed by SEV id — can never be reconciled against the roadmap. **See OD-9.** | **OD** |
| **33** | new tasks or ISSUE-341/342 | Decide the disposition of the two 2026-08 CRITICALs verified still live: **CR-L01-01** — `gossip_batch_queries.py:34-46` reads `best_event.summary` and never `k.distorted_summary`, so distortion is written on every hop and discarded on read; **CR-L15-01** — `run_config.py:348-350`'s live-network digest fallbacks make CI record `None` model digests. Add a line to the History table recording the re-triage. | The programme brands itself successor to everything before it. CR-L01-01 silently defeats the gossip mechanic the pitch rests on and sits downstream of Sprint 3's revival work; CR-L15-01 undermines the eval comparability T16.4 is hardening. **See OD-10.** | **OD** |
| **34** | new "Also open, not scheduled" section | List the 14 Log-dispositioned findings that are in neither a task nor the Parked section, one line each — at minimum **ISSUE-301** (no weak-secret validation on `API_KEY_GRAPH_WRITE`/`_ADMIN`), **ISSUE-302** (unbounded admin `npc_ids`/`location_ids`), **ISSUE-303** (`/setup` prefix-match, not an allow-list). Add a banner to `review-fixes/INDEX.md`: "Superseded 2026-09-08 by ROADMAP.md's T programme." Add the re-triage line to `review-2026-08/TRIAGE.md`. | Three are the exact class `CLAUDE.md` names ("input caps at the API boundary; auth on every route") and the ones a studio security review asks about first. A reader of `ROADMAP.md` alone would not learn they exist. Five documents currently claim to be an authoritative backlog with no stated precedence. **See OD-11.** | **OD** |
| **35** | **T9.1** | Split into `T9.1a` (census → `ports_census.md`, no deletions) + `T9.1b/c/d` (row ranges), each one session and one commit, each with its own `make check` and LOC delta. Replace "work in batches of about five ports per commit". Apply the same split to T11.1 by test directory if its own census shows >~30 files. | 70–100 file touches and five stated commits against a one-task-one-commit loop with `CLAUDE_TIMEOUT=5400`; five gate runs alone is ~60 min of a 90-min budget. A timed-out session is stashed, and a half-collapsed ports layer still compiles — the least detectable partial completion in the programme. **See OD-12.** | **OD** |
| **36** | **T6.3** | Either move after T7.1+T7.2 land, or add: "advance ticks one at a time and watch for LLM timeouts; a zero or flaky `need_quest_trigger` count under visible timeout errors is a Sprint-4 ordering artifact, not evidence T5.2 failed — do not use it to reopen Sprint 3." | T6.3 is the only live tick advance between T5.2 reviving `need_quest_trigger` and Sprint 4 bounding it — up to 84 calls for a saturated tick, single resident model, no admission control, 10 s timeout. Its `Done when:` is a hard binary that load can falsify. **See OD-13.** | **OD** |
| **37** | rules 4, 8; T10.1; T14.1 | Cap `dip_waivers.txt` at a fixed size (e.g. T9.1's 9 named keepers) enforced by the gate, and require periodic re-justification against current implementor/caller counts. Turn T14.1's "record a target date in `ISSUES.md`" into a gate that fails once the date passes with the baseline non-zero. Give rule 8 a reporting script (grep new engine code for `llm_client\.|generate(_structured)?\(` without an adjacent deterministic path) — report, not fail. | Rule 4 exists because 34 of 44 protocols failed the threshold; a waiver file whose only enforced property is "cites a `DEC-NNN`" reproduces that failure one layer up. T14.1's own text predicts its decay and answers it with a date in a markdown file — the same enforcement power as the ceremony it warns against. | **OD** |
| **38** | Deferred backlog, Sprints 9/10 | Name an owner and a date for each of the six flagged tasks and for Sprints 9/10, in `ROADMAP.md` next to the backlog table. Add a line under the Sprint 9 header: "unscheduled; do not assume it will happen automatically." | T0B.2 is "a report, not a gate", and this repo has already lived the decay once — R6.1-3 sat archived-and-unticked through a full review cycle, which is why Sprint 0 exists. Sprints 6–8 spend real effort (T16.3-T16.5) on infrastructure whose entire payoff is conditional on Sprint 9 running. **See OD-14.** | **OD** |
| **39** | **T15.2, T3.1/T3.2/T4.1** | Change T15.2's `docs/ENGINES.md` clause to say what Sprint 2 leaves undone ("per-engine rows are handled in Sprint 2; this task re-derives the tick-order and dependency sections") rather than restating it as if Sprint 2 never ran. | The file is assigned to four tasks across five sprints with no acknowledgement of the overlap; a partial fix in Sprint 2 is invisible until someone re-reads the whole file at T15.2. | **M** |

**Mechanical: 24 · Owner-decision: 15.**

---

## §6 Owner decisions

Fifteen calls, shortest first. Numbers refer to §5 patch rows.

| # | Decision | Options and trade-offs | Recommendation |
|---|---|---|---|
| **OD-1** (p.8) | How do the 18 pre-approved tasks get past the halt table? | (a) `Pre-approved:` token + one halt-table row via T0B.1 — one line on 18 tasks, ~6 in the skill. (b) Run those 18 interactively — loses most of the loop's value. (c) Weaken the halt table — unsafe. | **(a).** This single call decides whether the loop is used at all. |
| **OD-2** (p.9) | `seed.py` at exactly its R001 baseline. | (a) Bump the baseline in T5.1/T5.2 — cheap, but grows a 1,677-line file and normalises bumping. (b) New **T4.3** splitting `seed.py` by domain first — one extra session, pre-pays T13.2/T14.2, keeps NPC ids stable under a *task* session rather than an unattended repair one. | **(b).** The repair path's only legal remedy is doing (b) unattended, which is exactly where NPC ids get renamed. |
| **OD-3** (p.23) | Rule 1's scope: src-only, or four directories? | (a) Keep src-only, and say in the roadmap that 70.4% of the repo is uncounted. (b) Widen to `src`+`scripts`+`evals`+`demo_game` with per-directory reporting. The programme itself adds ~2,500 LOC to uncounted dirs. | **(b) with per-directory reporting** — a migration should be visible, not free. |
| **OD-4** (p.23) | Where does the LOC ratchet install? | (a) T10.2 (Sprint 5) as written — three sprints before the last additive src work. (b) End of Sprint 8. (c) Keep Sprint 5 but seed the baseline with T15.1/T16.2's budgeted additions. | **(c)** — keeps the ratchet early without guaranteeing a red at T15.1. |
| **OD-5** (p.24) | Copy all nine rules into `CLAUDE.md`? | (a) All nine — four have no gate, contradicting DEC-249 and that file's own "no facts it does not own". (b) Only the gated four, plus one pointer line. | **(b).** |
| **OD-6** (p.18) | `CLAUDE.md` says 800 lines is "hard and unwaivable"; `rules_baseline.txt` grandfathers 925. Which wins? | (a) Amend `CLAUDE.md` to say hard-but-grandfathered, with the baseline as the record. (b) Keep "unwaivable" and treat every R001 row as a dated defect with an owner. | Either, but **decide** — the precedent that a hard limit can be baselined survives into every later rule. |
| **OD-7** (p.30) | Correct the political-engine recoverability estimate now? | (a) Correct it — measured ~3–4.5 h for the *cheapest* engine vs ~15–30 min implied. (b) Leave it and re-measure if a studio asks. | **(a), before any studio conversation cites it.** |
| **OD-8** (p.31) | `DEMO_SCRIPT.md` Act 5 narrates a battle T1.2 makes impossible. | (a) Fold the rewrite into T1.2. (b) Own task in Sprint 7. (c) Leave it for whoever next runs the demo. | **(a).** (c) means the studio-facing script is wrong from Sprint 1 onward and the census will not catch it. |
| **OD-9** (p.32) | SEV-07 (24.25 s gossip tick, brief already written). | (a) Add a Sprint-4 task. (b) Accept the gap explicitly in the Parked section. | **(a)** — the fix brief exists and the tick is 40–55× its neighbours. |
| **OD-10** (p.33) | The two live 2026-08 CRITICALs. | (a) Fold both into the T programme now. (b) File as ISSUE-341/342 and schedule later. (c) Neither — current state. | **(a) for CR-L01-01** (it defeats the gossip mechanic Sprint 3 is reviving), **(b) for CR-L15-01** (Sprint 9 prerequisite). (c) is not defensible. |
| **OD-11** (p.34) | The 14 unscheduled Log findings, three of them security. | (a) Schedule ISSUE-301/302/303. (b) List all 14 under "Also open, not scheduled". (c) Silence — current state. | **(b) at minimum**; (a) for the three security ones before a studio review. |
| **OD-12** (p.35) | Split T9.1? | (a) Split into T9.1a–d. (b) Move it out of the fence and run it interactively. (c) Leave it — it will time out and be stashed. | **(a).** |
| **OD-13** (p.36) | Reorder T6.3 after Sprint 4? | (a) Reorder — delays Sprint 3's confirmation, which the roadmap already tolerates for other flagged tasks. (b) Keep the order and add the load caveat. | **(b)** is cheaper and sufficient if the caveat is explicit; (a) is safer. This touches sequencing the owner already approved once. |
| **OD-14** (p.38) | Owner + date for the six flagged tasks and Sprints 9/10? | (a) Assign now. (b) Rely on T0B.2's report. | **(a).** A report nobody is assigned to read is no report, and this repo has proven that once. |
| **OD-15** (p.37) | DIP waiver cap, T14.1's date-as-gate, rule 8's reporting script. | (a) All three. (b) The waiver cap only. (c) None — accept the decay. | **(a) or (b).** These are the three mechanisms most likely to be pure ceremony by 2027. |

---

## §7 Consolidated 6-month predictions

Deduped across lenses. Each names a **week-2-observable trigger**. Four predictions from the lens
files were dropped for having no early trigger.

| # | Prediction | Trigger, observable by week 2 |
|---:|---|---|
| **1** | The programme is recorded as done without ever having been gated. | Night 1: the morning report contains `task <N> committed with a pre-existing red gate` (`expand_loop.sh:527`) for **every** task run. 10 of 10 rather than 0 of 10 after the first ten tasks means the flag has stopped carrying information. Also night 1: `HALT: 2 consecutive red phase gates` before T2.2 is ticked. |
| **2** | Sprint 2 never runs, and the roadmap does not say so. | The loop log contains `skipping phase T3` or `skipping phase T4` with reason `ask-gate`/`blocked-prerequisite`. The tell is that **T3.2 is never attempted at all** — a phase skip discards its siblings. First night that reaches phase T3. |
| **3** | A live engine is deleted and stays deleted. | `git show <T3.1 sha> --stat` the morning after Sprint 2's first night names `intent_formation_engine.py`. Nothing later notices: T15.2's expected-to-work list is authored months afterwards, against the already-broken tree. |
| **4** | Night 1's worktree launch fails before the first gate. | The first `make check` in the new worktree emits `ruff: command not found` or `No module named pytest`. Observable the moment T0.1 is validated. |
| **5** | Sprint 3 stalls on a red `check-rules` nobody can attribute. | `check-rules` reports `NEW R001|demo_game/seeds/seed.py:16xx` at T5.1 (task 12 of 37), or an `autofix: repair committed and flagged` entry touches `demo_game/seeds/`. |
| **6** | T16.4 is never done and no one learns it. | Run `make roadmap-audit` the day T0B.2 lands: five rows instead of six. `make roadmap-audit \| grep -c T16` returns 1, not 2. |
| **7** | The test prune deletes almost nothing and ISSUE-234 is closed anyway. | T11.1's completion note quotes `check-test-quality: 0 issues found` as evidence, or reports a `make test` pass-count drop under 30 / a LOC delta smaller than −2,000. Cross-check `grep -rc "quality-ok:" tests/` — **66 today**; if it has not fallen, nothing was triaged. |
| **8** | Rule 1 dies within three sprints of being born. | The enabling condition is checkable **now**, week 1: `grep -c loc_baseline scripts/loop_gates.py` → 0. Then: any commit whose message starts `fix(loop): auto-repair` that also touches `loc_baseline.txt`, `dip_waivers.txt` or `check_test_quality_baseline.txt`. |
| **9** | The repo grows through the programme while rule 1 reports success. | Re-run the four-directory count after Sprint 5 against the 2026-09-08 baseline (src 69,247 · tests 87,566 · demo_game 36,937 · evals 23,130 · scripts 9,477). If `scripts/` + `tests/` grew >1,500 LOC while `check-loc-ratchet` is green, the loophole is in use. Partially observable at T4.2 — one gate script plus its test. |
| **10** | At least one new gate ships vacuous. | T4.2's completion note records "zero on the current tree" and **no pre-sprint SHA or count** — the awkward half was skipped. T4.2's own Spec predicts this; the prediction is that nobody performs the check. T10.1 and T15.2 then follow. |
| **11** | A prose edit silently defers a task. | Diff `make roadmap-audit`'s output after every roadmap edit. The first time the flagged count changes without a task being flagged deliberately, `BLOCK_END_RE` has fired on absorbed sprint prose. |
| **12** | The demo type-gate becomes a second ratchet. | The day T14.1 lands: `grep -c type-demo Makefile` on the `check:` line is still 0, and a new baseline file sits alongside `.mypy_baseline_demo`. |
| **13** | `game_window.py` is still 925 lines. | Checkable **at Sprint 0**: `grep game_window scripts/rules_baseline.txt` returns the row today and T14.2's anchor does not mention it. If T14.2 is ticked without that row disappearing, the "unwaivable" limit is documented as enforced 125 lines past a live breach. |
| **14** | SEV-07 is rediscovered as new. | `grep -c SEV-07 project-harness/ROADMAP.md` is still 0 after the Sprint-4 tasks are written. The gossip tick will still be ~24 s when T15.2's census first runs, because nothing in the programme touches it. |
| **15** | `demo_game/tests/` becomes where weak tests go to live. | T5.2, week 2: `demo_game/tests/` grows during Sprint 3 while `check-test-quality` still reports 0. Baseline measured 2026-09-08: 87 files / 15,852 LOC / 1,097 test functions. |
| **16** | The eval infrastructure delivers no quality signal. | Two weeks after Sprint 8's last commit, Sprint 9 still has no tasks, owner or date — and "no judged number may be quoted as evidence of quality" is still true. Early tell at T15.1: `evals/probe_runner.py`'s engine-name mapping is unchanged, so `working_set_size` reads zero for the same 10 probes ISSUE-339 names. |
| **17** | The gossip mechanic is measured without working. | `grep -n "best_event.summary" src/npc_engine/graph/gossip/gossip_batch_queries.py` still shows the propagate-read query ignoring `k.distorted_summary`. Checkable **today**; if unchanged when Sprint 3's revival lands, distortion is still written on every hop and discarded on read. |
| **18** | The deferred backlog never drains. | Two weeks after Sprint 8's last commit, `make roadmap-audit` still lists T6.3, T13.1, T13.2, T15.2, T16.1, T16.4 as flagged-and-undone. Precedent: R6.1-3 sat archived-and-unticked for a full review cycle. |

**Dropped for having no early trigger:** "which deletions will be regretted" (R5-03 — a product
judgement, not an observable); "the demo becomes dishonest over five sprints" (R2-08 — subsumed by
#3 and OD-8); "`dip_waivers.txt` reaches 10+ entries" (R5-01's prediction 1 — the week-2 form is
already prediction #8); "a future roadmap rewrite drops Sprints 9/10 the way R6 was dropped"
(R5-07 — real, but unobservable until it happens).

---

## §8 Confidence ledger, and what was NOT checked

| Grade | Count | Notes |
|---|---:|---|
| **Confirmed** | 68 | Every CRITICAL. R1 verified ~215 citations; R4 graded all 19 of its findings Confirmed. |
| **Likely** | 9 | `R1-14`, `R2-02`, `R2-04`, `R2-06`, `R3-11`, `R3-14`, `R5-03`, `R5-04`, `R5-05`. |
| **Suspected** | 0 | — |

**No finding is graded Suspected, so no mechanical patch rests on one.** Two mechanical patches do
rest on *Likely* findings and are marked here rather than downgraded: **patch 27** (delete
`graph/military/`) rests on `R3-14` — re-run
`grep -rln "graph.military\|graph import military" src/ demo_game/ e2e/ evals/` before applying;
and **patch 26** (demo census methodology) rests on `R2-02` — the mechanism is confirmed, the
*likelihood* that the census sweeps up T5.1/T5.2's tests is the Likely half. Every other mechanical
patch rests on Confirmed evidence. All five *Likely* findings that inform **owner-decision** rows
(`R5-03`, `R5-04`, `R5-05`, `R2-04`, `R3-11`) are flagged as judgement calls in §6 rather than
presented as fact.

**Verification volume.** R1: ~215 citations — 265 path tokens machine-checked, ~130 individually
resolved, 85 `file:line` opened (68 exact, 10 off by 1–3, 4 out of range, 3 wrong path), 11 make
targets, 41 issue statuses, all 6 named constants, 17 RED anchors run and 11 more premises
verified, **5 anchors found already GREEN or misspecified**. The orchestrator independently
re-verified the four facts that drive CRITICAL patches: the six `⏸️` lines, `seed.py` = 1677 =
its baseline row, both stale tripwire constants, and the three modules in `engines/agenda/`.

**What this review did NOT cover:**

1. **The integration suite** — forbidden (ISSUE-277: no test database; it writes to the live Neo4j).
2. **Nine of the 23 `make check` targets** — `test-cov-evals`, `test-cov-v13`,
   `test-cov-full-report`, `check-migrations`, `check-api-stability`, `check-api-contract`,
   `check-engine-logs`, `check-base-rate`, `check-dead-keywords` have **never been observed on this
   tree**, because `make check` aborts at target 14. They include every gate that notices a
   deletion. Patch 1's `T0.0` is what finds out; until then the programme's central verification
   claim is unverified for 39% of the gate.
3. **Judged eval quality** — forbidden as evidence (all five scorers REFUSED by
   `check_label_adequacy.py`). No lens quoted a judged score.
4. **Anything requiring a running stack** — T6.3, T13.1, T13.2, T15.2, T16.1 and T16.4's live half
   were reviewed as text only. `make test-demo`'s 1,116 baseline was taken as given.
5. **Whether the deletions actually compile.** R2 simulated the cascade by reading the tree; nobody
   deleted anything. The post-Sprint-2/3 tree is inferred, not built.
6. **The exact below-threshold port count after Sprints 2–3** — R3 estimated ~23 from the review's
   34-of-44 figure rather than recounting.
7. **CR-L03-01** (`hedge_responder_probe.py`) — the file no longer exists; R6 could not verify
   whether it was fixed or refactored away, and did not, per the read-only constraint.
8. **Sprints 9 and 10 as work** — they are sketches by design; only their scheduling risk was judged.
9. **The `demo_game` UI/UX and art surfaces** beyond what T13.1/T13.2 and `DEMO_SCRIPT.md` state.

**On the review's own calibration items:** all three confirmed. (1) T9.1's five-commit instruction
against a one-commit loop — confirmed and sized at 70–100 file touches (patch 35). (2) The halt-gate
collision — confirmed and *worse than stated*: 18 tasks, and a halt discards the whole phase
(patch 8). (3) SEV-07 missing — confirmed, plus SEV-02/SEV-03 untraceable and two 2026-08 CRITICALs
absent entirely (patches 32, 33). The three were the floor, not the target: this review adds seven
CRITICALs they did not name.
