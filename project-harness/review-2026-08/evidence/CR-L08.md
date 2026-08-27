# CR-L08 — Code debt (oversized files, duplication, dead code, orphans)

Branch `eval-ab-context-arms`, HEAD `d46ae42`. Read-only review.

## Required measurements

### 1. Grandfathered rule-baseline violations

Live gate run:

```
$ python scripts/check_rules.py
check-rules: OK - no new violations (133 grandfathered).
$ python scripts/check_rules.py --evals
check-evals-rules: OK - no new violations (72 grandfathered).
```

`scripts/rules_baseline.txt` (src + demo_game, 133 rows):

| Rule | Count | Top 5 files |
|---|---|---|
| R001 file-size | 31 | `demo_game/client.py`, `demo_game/seeds/seed.py`, `demo_game/ui/layout/game_window.py`, `src/npc_engine/retrieval/context/context_builder.py`, `src/npc_engine/scheduler/tick_scheduler.py` |
| R006 fn-length | 102 | `graph/graph_writer.py` (3), `engines/quest/quest_lifecycle_engine.py` (3), `engines/llm/ollama_adapter.py` (3), `engines/interaction/trade_handler.py` (3), `engines/gossip/gossip_handler.py` (3) |

`scripts/evals_baseline.txt` (evals, 72 rows):

| Rule | Count | Top 5 files |
|---|---|---|
| R001 file-size | 7 | `evals/calibration.py`, `evals/compare.py`, `evals/summary.py`, `evals/matchers.py`, `evals/anti_hallucination_runner.py` |
| R002 print | 20 | (spread across `evals/__main__.py`, `adjudicate.py`, `arm_probe.py`, `arm_probe_report.py`, `arm_supply.py`, ≤1 each) |
| R003 swallow | 3 | `evals/__main__.py`, `evals/dashboard/app.py`, `evals/dashboard/detail.py` |
| R006 fn-length | 42 | `evals/case_drafts.py` (4), `evals/summary.py` (3), `evals/scenario_adapters_extra.py` (3), `evals/label_import.py` (3), `evals/runner.py` (2) |

**Combined total tracked by the two ratchet files: 205 (133 + 72).**

**The review brief's "313 total" and "57 in the rules baseline" are both wrong for the current tree.**
- 313: not found anywhere as a live or historical count. `git log` over `scripts/rules_baseline.txt`'s last 20 revisions shows the file has stayed in the 133–137 range; it never held 313 rows, and 313 + evals' 72 doesn't reach it either. Unverifiable — treat as stale/incorrect.
- 57: real, but historical and superseded. `project-harness/DECISIONS.md:1996` (DEC-140, 2026-06-22): *"ISSUE-053 originally tracked '57 grandfathered check-rules violations'... Those clusters are now fully cleared... What remains is only R001... and R006."* DEC-140 explicitly redefines "done" and reports the baseline at 137→136 immediately after — i.e. the brief is quoting the pre-redefinition count from over two months ago, not the current 133.

### 2. Oversized files (non-test .py > 300 lines)

Method: `find <body> -name "*.py" | wc -l` per file, excluding paths under any `tests/` dir, `test_*.py`, or `*_test.py`. **40 files** across src/demo_game/evals/scripts (tests/ exempted per CLAUDE.md, see §6).

| Body | Oversized files |
|---|---|
| demo_game | 18 |
| src | 13 |
| evals | 7 |
| scripts | 2 (not gated at all — see CR-L08-04) |

Top 15:

| Lines | File | Waived in DECISIONS.md? |
|---|---|---|
| 1901 | `demo_game/client.py` | Yes — DEC-034 (waived at 680, "grow to ~750 by end of Phase 4") |
| 1677 | `demo_game/seeds/seed.py` | Yes — DEC-033 (waived at 671, limit "~800") |
| 925 | `demo_game/ui/layout/game_window.py` | Stale — DEC-032/074 waived at 350; nothing since |
| 875 | `evals/calibration.py` | No DECISIONS entry found |
| 799 | `src/npc_engine/retrieval/context/context_builder.py` | Yes — DEC-016 (waived at ~464) |
| 654 | `demo_game/runners/run_scenes.py` | Via DEC-049 (split rationale, no line ceiling stated) |
| 630 | `src/npc_engine/scheduler/tick_scheduler.py` | Yes — DEC-042 (waived at ~480) |
| 627 | `demo_game/runners/run.py` | Via DEC-049 |
| 618 | `demo_game/ui/layout/right_panel.py` | Yes — DEC-047 (waived at ~405) |
| 577 | `src/npc_engine/retrieval/context/context_budget_enforcer.py` | Yes — DEC-073 (waived at 323, "do not grow further") |
| 559 | `evals/compare.py` | No DECISIONS entry found |
| 556 | `demo_game/game_controller.py` | Not individually named in DEC-140's catalog |
| 541 | `evals/summary.py` | No DECISIONS entry found |
| 517 | `demo_game/ui/layout/left_panel.py` | Yes — DEC-036 (waived at 322, "may reach ~340") |
| 509 | `evals/matchers.py` | Yes — DEC-145 (waived at 474) |

**Waiver drift** (stated waiver line count vs. actual today) is severe for several files — see CR-L08-01/02/03.

### 3. Dead code estimate

Method: `vulture` (installed into project venv for this scan only, no source touched) at `--min-confidence 60`, cross-checked by hand with `grep -rn` for every candidate before calling it dead — vulture alone is unreliable here because FastAPI route handlers, Pydantic `@field_validator`s, and `Protocol` methods are only ever called through framework/decorator machinery it can't see, so its raw "unused function" hits (193 across src) are **>90% false positives** (route handlers, config validators). Confirmed dead code required an explicit grep showing zero call/construct sites outside the definition, its own tests-that-mock-it, and docstrings.

Confirmed dead (2 items, both exception classes with a documented contract that no code path implements):
1. `src/npc_engine/utils/errors.py:53` `GraphUnavailableError` — cited in 4 docstrings as the fallback for "Neo4j unavailable" (`engines/military/military_battle_service.py:59`, `military_resource_service.py:47`, `engines/ports/dialogue_graph_port.py:73`, `graph/political/pledge_violation_service.py:86`) but `grep -rn "raise GraphUnavailableError" src/` returns **zero** hits. The only place it's raised is `tests/unit/engines/test_investigation_service.py`, which injects it via a mock session (`_make_failing_session(exc)`) rather than exercising a real conversion from a Neo4j driver error.
2. `src/npc_engine/utils/errors.py:301` `TokenBudgetExceededError` — the exact contract CLAUDE.md cites ("`context_builder.py` raises `TokenBudgetExceededError`"), but `context_budget_enforcer.py` raises `ContextBudgetError` (5 raise sites, lines 78/88/151/321) instead; `grep -rn "TokenBudgetExceededError" src/` finds only the class definition. It also doesn't inherit `StructuredNPCSystemError` like its siblings, breaking the "custom exception hierarchy" rule on its own terms. 12 lines dead, imported-but-unused by one test (`tests/unit/retrieval/test_context_budget_enforcer_v14.py:20`).

Likely-dead subsystem (not individually re-verified per function, flagged as a cluster): `graph/political/*` (7 unused-function hits: `political_agenda_writer.py`, `political_leverage_writer.py` x2, `political_queries.py` x5, `political_title_writer.py` x2) and `graph/military/military_writer.py` (5 unused-function hits: `create_army`, `create_resource_node`, `link_resource_node`, `move_army`, `link_army_to_commander`) — these read as complete graph-writer layers for game features with no api/routes or engines/ caller found in the same vulture pass. Not individually confirmed by grep in this pass (time-boxed); flagged as **Suspected**, worth a dedicated grep-per-symbol pass.

LOC estimate: only the 2 Confirmed items (~15 lines) are safe to state as a number. The Suspected political/military cluster, if genuinely orphaned, would be several hundred LOC across ~7 files — not counted in the total below because unconfirmed.

### 4. Duplication

Method: `ast.parse` over src/demo_game/evals (test dirs excluded), grouped `FunctionDef`/`AsyncFunctionDef` names appearing in >1 file, then hand-diffed the plausible ones (Protocol/impl pairs and the mandated `_work(tx)` transaction-coordinator closure pattern — DEC-119/SEV-21 — are expected repeats, not duplication, and were excluded).

Confirmed near/exact duplicates:
1. `demo_game/ui/boards/faction_board.py:193` `_draw_no_data(surface, font, text, clr, rect)` vs `demo_game/ui/panels/retrieval_panel.py:210` `_draw_no_data(...)` — **byte-identical 38-line body**, `diff` shows exactly one word differs ("centred" vs "centered" in the docstring).
2. `demo_game/ui/panels/player_model_panel.py:160` `_draw_no_data(self, surface, rect)` vs `demo_game/ui/panels/scheme_board_panel.py:144` `_draw_no_data(self, surface, rect)` — identical 7-line bodies (blit a centered message), differ only in docstring wording ("no data" vs "no schemes").

`_draw_no_data` exists in 5 sibling `demo_game/ui/{boards,panels}/*.py` files total (2 in the free-function form, 2 in the method form, 1 divergent — `memory_panel.py` has its own word-wrap variant). No shared base class or helper module for panel "empty state" rendering exists despite the repeated pattern.

### 5. Orphaned artifacts

| Artifact | Size | Last modified/committed | Tracked in git? |
|---|---|---|---|
| `p04_ah.log`, `p04_eval.log`, `p04_gen.log`, `p04_judge_mixtral.log`, `p04_judge_qwen14b.log`, `p04_retrieval.log` (6 files) | 4.8KB–46KB (75KB total) | Aug 5–6, 2026 | No — `git check-ignore -v` confirms all 6 match `.gitignore:51 *.log` |
| `live_openapi.json` | 178KB | Last **committed** 2026-07-31 (`f678dd4`), not touched since | **Yes**, tracked. `grep -rln live_openapi` finds it referenced only in 3 planning docs, zero code/CI consumers, zero Makefile target that regenerates it. `paths` count = 128 vs 136 live `@router.*` decorators today — already drifted from the source it claims to document. |
| `.claude/worktrees/` | 0 bytes | n/a | The brief's "9 stale worktrees" claim is **false for this checkout** — the directory exists but is empty (`find .claude/worktrees -maxdepth 2` returns only the dir itself), and `git worktree list` shows only the main worktree. |
| `project-harness/archive/` | 3.1MB, 224 `.md` files (brief said 215 — close, off by 9) | Spans 2026-05 (oldest: `review-2026-06-03/review-evidence/final/L2-architecture.md`) to **today** (`ISSUES_RESOLVED.md`, actively appended per the CLAUDE.md issue-close workflow) | Mixed — `review-2026-06-03/review-evidence/` is gitignored (`.gitignore:75`); the rest is tracked. Not uniformly "orphaned": `ISSUES_RESOLVED.md` is a live, canonical, actively-written file per CLAUDE.md's own process; the other ~223 files are frozen historical snapshots. |
| root `__pycache__/` | small (3 `.pyc` for `conftest.py` across 3 interpreter versions incl. a stray `cpython-314-pytest-8.4.2` from an old pytest) | Aug 18, 2026 | No — gitignored (`.gitignore:5`) |
| `transcripts/` (top level) | 5.5MB, 598 files | oldest May 11, newest current | No — gitignored (`.gitignore:44`), 0 tracked |
| `e2e/transcripts/` | 148KB, 1 file | Aug 6 | No — gitignored (`.gitignore:24`), 0 tracked |
| `dashboard/` | 56KB (index.html + css/js) | Jun 18, 2026 | Tracked (not checked further — out of scope for this pass beyond noting its age: untouched for ~10 weeks) |

### 6. Test-to-source ratio, oversized tests

| Body | Source LOC | Test LOC | Ratio (test/source) |
|---|---|---|---|
| `src/npc_engine` | 68,218 | 65,572 (`tests/` total 80,324 minus `tests/unit/evals` 14,752) | 0.96 |
| `evals` | 20,141 | 14,752 (`tests/unit/evals`, 89 files) | 0.73 |
| `demo_game` | 21,109 (non-test) | 15,852 (`demo_game/tests`, 87 files) | 0.75 |

Test files > 300 lines: **41** under `tests/` + **11** under `demo_game/tests` = 52 total, all exempt from R001 by the CLAUDE.md test carve-out. Spot-checked the two largest (`tests/unit/engines/test_anti_hallucination_runner.py`, 663 lines / 19 test functions; `tests/unit/retrieval/test_context_builder.py`, 639 lines / 12 test functions, ≈53 lines/test) — size tracks the genuine complexity of the module under test (`context_builder.py` is itself the largest oversized src file at 799 lines) rather than looking like padding or copy-pasted setup. No evidence in this sample that the test exemption is being used to hide complexity; not exhaustively checked across all 52.

---

## Findings

### [CR-L08-01] `client.py` and `seed.py` blew through their own DECISIONS-stated growth ceilings by 2–3x, unactioned

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** DEC-034 (`project-harness/DECISIONS.md:885`) waives `demo_game/client.py` at 680 lines with an explicit limit: *"If client.py exceeds ~900 lines, extract a QuestClient and EconomyClient mixin."* Actual today: `demo_game/client.py` = **1901 lines** (`wc -l`), 2.1x the stated trigger, no follow-up DECISIONS entry. DEC-033 (`DECISIONS.md:914`) waives `demo_game/seeds/seed.py` at 671 lines with limit *"If seed.py grows past ~800 lines, extract helpers into `demo_game/_seed_helpers.py`."* Actual today: **1677 lines**, 2.1x the stated trigger. Compounding this, `seed.py`'s own module docstring (lines 11-12) says the sibling split into `seed_npc_data.py` was done "to keep this file under the 300-line limit" — a claim false by 5.6x for the file the docstring is written in.
- **Cost of inaction:** Both files keep absorbing every new demo feature (client.py is the single HTTP surface for every engine endpoint; seed.py is the single world-seeding entrypoint) with no split boundary in force — the next contributor has no signal that the previously-agreed limit was already passed, twice.
- **Fix sketch:** Action the DEC-034 mixin extraction (QuestClient/EconomyClient) and the DEC-033 `_seed_helpers.py` extraction now that both stated thresholds are exceeded; update the seed.py docstring to stop asserting a false 300-line claim.
- **Effort:** L
- **Removes:** 0 lines (extraction, not deletion) — but resolves ~3,578 lines of file-size debt across the two files
- **Blast radius:** `client.py` is imported by every demo runner/scenario/poller; a mixin split changes only internal organization if `EngineClient` still exposes the same methods, but touches the most-imported file in `demo_game/`.

### [CR-L08-02] `game_window.py` regrew past its "resolved" split to 925 lines with no waiver since 350

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** DEC-032 (`DECISIONS.md:873`) split `game_window.py` specifically to fix repeat overruns, targeting *"thin `GameWindow`: pygame event loop, thread ownership... (~150 lines)"* and concluding *"File sizes stay within 300-line limit without exceptions."* DEC-074 one week later already found it back at 350 lines. `grep -n "game_window" project-harness/DECISIONS.md` shows no entry after DEC-074 (2026-06-05) addressing further growth. Actual today: `demo_game/ui/layout/game_window.py` = **925 lines** — 2.6x the last documented waiver, 6.2x the post-split target the split was supposed to guarantee.
- **Cost of inaction:** The file is currently the largest undocumented overrun in the repo; whatever DEC-032 split apart (thread ownership vs rendering) has plausibly re-merged, since nothing tracks what grew.
- **Fix sketch:** Read the current file to identify what's been added since DEC-074 (likely more UI wiring); either extract it to a fourth renderer/coordinator file per the DEC-032 pattern, or write the DEC-140-style top-of-file waiver comment this file currently lacks.
- **Effort:** M
- **Removes:** 0 (needs a real split or a documented waiver, not deletion)
- **Blast radius:** Central demo UI file; any split touches the pygame event loop all panels depend on.

### [CR-L08-03] Two error classes document a fallback contract that no code path implements

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `src/npc_engine/utils/errors.py:53` `GraphUnavailableError` is named as the Neo4j-unavailable fallback in 4 docstrings (`engines/military/military_battle_service.py:59`, `military_resource_service.py:47`, `engines/ports/dialogue_graph_port.py:73`, `graph/political/pledge_violation_service.py:86`) and in this repo's own CLAUDE.md example ("Neo4j unavailable → raise `GraphUnavailableError`"), but `grep -rn "raise GraphUnavailableError" src/` returns nothing — it is never raised by production code, only injected via mock in `tests/unit/engines/test_investigation_service.py:164` to test that it *propagates*, not that anything *produces* it. `src/npc_engine/utils/errors.py:301` `TokenBudgetExceededError` is the exact class CLAUDE.md's prompt-hygiene rule names, but `context_budget_enforcer.py` raises `ContextBudgetError` at all 5 of its raise sites instead — `TokenBudgetExceededError` is never raised anywhere in `src/`.
- **Cost of inaction:** A real Neo4j outage today propagates whatever the neo4j driver raises (e.g. `ServiceUnavailable`) straight to the caller uncaught and untyped, not the documented, structured `GraphUnavailableError` → 503 contract the docstrings and CLAUDE.md promise operators.
- **Fix sketch:** Either wrap the driver's connectivity exceptions into `GraphUnavailableError` at the graph-session boundary (the actual fix CLAUDE.md's contract implies), or delete both classes and correct the 4 docstrings + CLAUDE.md's example if the contract was abandoned deliberately.
- **Effort:** M
- **Removes:** ~15 lines if abandoned; 0 if implemented (adds a wrapper instead)
- **Blast radius:** Every graph-session call site if the wrap is added at a shared boundary (e.g. `transaction_coordinator.py`); low blast radius if just deleting the two dead classes and 4 docstring lines.

### [CR-L08-04] `scripts/` is invisible to the 300-line and 40-line rule gates entirely

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Gap
- **Evidence:** `scripts/check_rules.py:112-113,148` — `_iter_py` is only ever called with `"src/npc_engine"`, `"demo_game"`, and (for `--evals`) `"evals"`. `scripts/` and `tests/` are never scanned for R001/R006. Live measurement: `scripts/check_conservation.py` = 327 lines, `scripts/_roadmap_cursor_core.py` = 311 lines — both over the 300-line limit CLAUDE.md states as universal, both absent from `rules_baseline.txt`, and neither can ever trip `check-rules` because the scanner doesn't look there.
- **Cost of inaction:** `scripts/` (the harness's own gate/automation code) can grow arbitrarily large with zero ratchet, including scripts that themselves enforce the very rule they're exempt from.
- **Fix sketch:** Add `"scripts"` to the `_iter_py` roots in `check_rules.py`'s R001/R006 passes and run `--update-baseline` once to grandfather the 2 current offenders.
- **Effort:** S
- **Removes:** 0 lines; adds 2 files to the baseline
- **Blast radius:** None — purely additive to the gate's scan scope.

### [CR-L08-05] Review brief's "313 grandfathered violations" figure does not match any live or historical count

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `python scripts/check_rules.py` → "133 grandfathered"; `--evals` → "72 grandfathered"; combined 205. `git log` over the last 20 revisions of `scripts/rules_baseline.txt` shows a range of 133-137 rows, never near 313, and no combination with `evals_baseline.txt` (max 75 rows ever, per `wc -l`) reaches it either.
- **Cost of inaction:** Downstream lenses or the synthesized review report may repeat "313" as ground truth, undermining the credibility of the whole codebase-debt narrative.
- **Fix sketch:** Correct the figure to 205 (133 rules + 72 evals) wherever "313" is cited in `project-harness/PROMPT_CODEBASE_REVIEW_2026-08.md` and any synthesized findings doc.
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** Documentation only.

### [CR-L08-06] `.claude/worktrees/` claim of "9 stale worktrees" is false for this checkout

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** `find .claude/worktrees -maxdepth 2` returns only the directory itself (empty); `git worktree list` shows exactly one worktree (the main checkout at `d46ae42`).
- **Cost of inaction:** Same as CR-L08-05 — a false orphan claim propagating into the synthesized report.
- **Fix sketch:** Drop the ".claude/worktrees" line item from the brief, or re-verify on whichever machine produced the "9" figure (possibly true on a different contributor's local checkout, but not reproducible here).
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** Documentation only.

### [CR-L08-07] Duplicated `_draw_no_data` empty-state helper across demo_game UI panels

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** `demo_game/ui/boards/faction_board.py:193` and `demo_game/ui/panels/retrieval_panel.py:210` — identical 38-line `_draw_no_data(surface, font, text, clr, rect)` free function (`diff` shows a 1-word docstring spelling difference only). Separately, `demo_game/ui/panels/player_model_panel.py:160` and `demo_game/ui/panels/scheme_board_panel.py:144` — identical 7-line method form.
- **Cost of inaction:** A future change to how "no data" states render (e.g. a new empty-state icon) needs to be hand-applied in 4+ places; two already drifted apart in styling (free-function word-wrap version vs. plain-centered method version).
- **Fix sketch:** Extract one `draw_no_data(surface, font, text, clr, rect)` free function into `demo_game/ui/panel_helpers.py` (or similar shared module) and have all 5 panels call it.
- **Effort:** S
- **Removes:** ~45 lines (net, after adding one shared function)
- **Blast radius:** 5 UI panel files; visual-only, low risk.

### [CR-L08-08] Waiver-mandated top-of-file comments missing on the 4 highest-drift oversized files

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** CLAUDE.md: *"If a split would be artificial, write a justifying comment at the top of the file."* DEC-140 promises this for 5 named files and confirmed present in all 5 (`api_seeder.py`, `intent_queries.py`, `quest_lifecycle_engine.py`, `prompt_builder.py`, `gossip_handler.py`). But `head -25` on the 4 files with the worst waiver-vs-actual drift shows no such comment: `src/npc_engine/config.py` (DEC-077, waived at 309, actual 504), `demo_game/ui/layout/game_window.py` (DEC-074, waived at 350, actual 925), `demo_game/client.py` (DEC-034, waived at 680, actual 1901), `src/npc_engine/retrieval/context/context_budget_enforcer.py` (DEC-073, waived at 323 with "do not grow further," actual 577).
- **Cost of inaction:** A contributor opening any of these 4 files has no in-file signal that the size is already a known, aging exception well past its last-agreed number — they'd need to grep DECISIONS.md and notice the line count no longer matches.
- **Fix sketch:** Add the one-line `DEC-0xx waiver, see DECISIONS.md` header CLAUDE.md requires to each of the 4 files; costs under 10 minutes total.
- **Effort:** S
- **Removes:** 0 lines
- **Blast radius:** None — comment-only addition.

### [CR-L08-09] `live_openapi.json` is a stale, unreferenced, git-tracked generated artifact

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** Tracked in git, last commit `f678dd4` (2026-07-31). `grep -rln live_openapi` across the repo finds it named only in 3 planning docs — zero code, zero CI, zero Makefile target reads or regenerates it. `python -c "json.load(...)"` shows 128 `paths` vs. 136 live `@router.*` route decorators counted today — it has already drifted from the API surface its filename claims to capture.
- **Cost of inaction:** Anyone who finds this file and trusts it (e.g. a partner studio doing API discovery) gets a wrong, ~4-week-stale contract with no generator to refresh it.
- **Fix sketch:** Delete the file, or add a `make openapi-dump` target plus a `.gitignore` entry so it's generated on demand instead of committed.
- **Effort:** S
- **Removes:** 182KB / 1 file
- **Blast radius:** None found — no consumer.

---

## Summary of counts

- Grandfathered rule violations (live, confirmed): **205** (133 `rules_baseline.txt` + 72 `evals_baseline.txt`) — not 313, not 57 (see CR-L08-05).
- Oversized non-test files (>300 lines, live count): **40** (18 demo_game, 13 src, 7 evals, 2 scripts — the last 2 invisible to the gate, CR-L08-04).
- Confirmed dead code: 2 classes, ~15 lines (CR-L08-03). A larger `graph/political/*` + `graph/military/military_writer.py` cluster is Suspected, not confirmed.
- Confirmed duplication: 2 near/exact-identical function pairs, ~45 lines removable (CR-L08-07).
- Orphaned artifacts: 6 gitignored log files (75KB, not tracked — low concern), 1 tracked stale JSON (182KB, CR-L08-09), `.claude/worktrees/` claim falsified (CR-L08-06), `project-harness/archive/` mostly-frozen-but-partly-live (224 md files, 3.1MB).
