# Issues Log

Persistent issues log. Read at the start of every session. Updated whenever
work is deferred or completed.

Rules:
- Never reuse IDs (check both this file and the archive for the next id).
- Never delete entries. When fixed, mark `[FIXED]` with a `**Fixed:**` line, then
  move the entry to [`archive/ISSUES_RESOLVED.md`](archive/ISSUES_RESOLVED.md).
- Severity: P1 (blocking) | P2 (annoying) | P3 (nice-to-fix).
- New issues get the next monotonic ID.

> **Resolved issues are archived.** Closed/fixed entries now live in [`archive/ISSUES_RESOLVED.md`](archive/ISSUES_RESOLVED.md). This file tracks open issues only.

---

## Open

## ISSUE-359: demo faction board is never fed, and would render every standing as 0 if it were
**Found:** 2026-09-18, while analysing ISSUE-354
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/client.py:1829` (`get_faction_standings`), `demo_game/ui/boards/faction_board.py:156`,
`demo_game/ui/layout/right_panel.py:362`
**Description:** No non-test code calls `get_faction_standings()` or `set_faction_standings()`, so the
FACTION panel is dead wiring. It also expects three incompatible shapes: the client docstring and
`test_faction_board.py` mocks use `src_id`/`dst_id`/`standing` rows; the API model says
`target: str`; the query returns `target` as a whole node dict. `FactionBoard` reads
`entry.get("standing")` from the *outer* per-faction dict (which has `faction_id`, `faction_name`,
`standings`), so every row would render as `0`.
**Why deferred:** not blocking the demo (the panel is never shown with data); its fix depends on the
ISSUE-354 decision.
**To fix:** after ISSUE-354 fixes the response shape, either wire the panel (fetch on tab open, render
the inner `standings` list) or delete the dead client method and widget.
**PLAN 2026-09-18 (owner):** handed to **T13.1**, which rules on unused demo panels (like TREATY/OATH).
No code before that ruling; if kept, feed it on tab open via `RightPanelRenderer`, no poller.

## ISSUE-291: tone_judge fate is decided (author failing cases) but not implemented
**Found:** 2026-09-07, eval/metrics remediation
**Severity:** P2 (annoying — the battery stays HIDDEN under scorer_trust_policy in the
meantime, so nothing is silently trusted; this is a backlog item, not a live risk)
**Where:** `evals/cases/` (case authoring), tone_judge's criteria in the judge prompts
**Description:** tone_judge has near-zero minority-class labels across three independent
raters — my original 128 PASS/7 FAIL, Opus's 354-row pre-label pass at 111 PASS/0 FAIL, and
the 3-model panel's 109/111 unanimous at kappa 0.003 — so no kappa is computable and
label_adequacy refuses it (minority count 7, floor 25). Decided (2026-09-07): the case set
never probes a tone failure, not that the judge is miscalibrated — author new cases
designed to fail tone (e.g. `case_tone_fail_*`) rather than re-authoring the judge's
criteria or retiring the capability battery.
**Why deferred:** eval-case authoring is its own task with its own review, out of scope for
this remediation session (which fixed ISSUE-288/289 and the labels/panel-kappa reporting
bugs only).
**To fix:** author N `case_tone_fail_*` cases that a working tone_judge should fail, run
**Theme:** T17
them through the panel, re-check label_adequacy's minority count, and calibrate.

**Update 2026-09-07 (measurement-remediation Phase 5, DEC-272) — quantified, and it is now
blocking a specific piece of work.** `make adjudication-yield` puts an exact number on this:
of tone_judge's 111 pending Opus pre-labels, **111 are PASS and 0 are FAIL**, so adjudicating
every one of them as `keep` leaves the minority class at **7**, unchanged. Reaching the floor
of 25 by adjudication alone would require the adjudicator to flip **≥18** of Opus's PASS calls
to FAIL — i.e. to assert Opus was wrong in one direction ~16% of the time, on a case set that
by this issue's own diagnosis contains no tone failures to find. Consequence for the labelling
push: **tone_judge's 111 pending rows should not be adjudicated yet.** That is several hours of
keep/flip that cannot lift the scorer above REFUSED. `affirms_judge` (keep-all 32 minority) and
`commits_judge` (keep-all 45) both clear the floor and are where the push should go. This issue
is the gate on tone_judge's half of Phase 5, not a backlog item that can wait behind it.

## ISSUE-290: instrument_gate.py compares only pooled panel_kappa, never per-criterion
**Found:** 2026-09-07, fixing the pooled-panel-kappa reporting gap (panel_metrics_format.py)
**Severity:** P3 (nice-to-fix — no live run has hit this yet; it is a gap in what the gate
can detect, not a wrong result it has produced)
**Where:** `evals/instrument_gate.py:101` `check_instrument`
**Description:** The trend gate's "did the measuring instrument degrade" check (exit code
3) compares only `TrendRow.panel_kappa` — the pooled Fleiss kappa across every judge_kind —
against the baseline run's pooled value. It has no per-criterion form. A single criterion's
agreement could collapse between two runs while the others compensate in the pool, and
`check_instrument` would report "INSTRUMENT STABLE" even though one judge's reliability
genuinely fell. This is the same pooling-hides-a-real-problem shape
panel_metrics_format.py's new caveat (this task) flags for the *reporting* side; this issue
is the *gating* side of the same gap.
**Why deferred:** not one of this remediation's four stated priorities (ISSUE-288,
labels_gen_id/labels_n, pooled-panel-kappa reporting, ISSUE-289); adding a per-criterion
form to `check_instrument` is a design decision (which criteria matter enough to gate on
individually? does a single criterion's regression alone justify exit code 3?) that needs
its own proposal.
**To fix:** extend `check_instrument` (or add a sibling check) to compare
**Theme:** T17
`TrendRow.kappa_by_criterion` entries by `judge_kind` between candidate and baseline, using
the same one-sided-CI-below-baseline-point-estimate rule `check_instrument` already uses for
the pooled figure — `CriterionKappa` carries no CI today (see its docstring), so that would
need to be added first.

## ISSUE-289: `mypy.ini`'s `mypy_path = src` silently Any-types every intra-`evals/` import
**Found:** 2026-09-05, wiring `battery_trust.trust_gate` into `evals/summary.py`. Investigated
further 2026-09-07 (eval/metrics remediation) — the originally-proposed fix does not work;
see the correction below.
**Severity:** P2 (annoying — `make type-evals` still catches real errors when they
happen to surface as a mismatched *return*, which is how this was found; it silently
misses everything else)
**Where:** `mypy.ini:3` (`mypy_path = src`); affects every module under `evals/`
**Description:** When mypy analyzes an `evals/*.py` file as a root (exactly what
`mypy evals/` — the real `scripts/mypy_evals_ratchet.py` invocation — does), a sibling
import like `from battery_trust import trust_gate` resolves to `Any` rather than the real
`(battery: str, current_str: str, scorer_kappas: Sequence[ScorerKappa]) -> str`
signature (confirmed via `reveal_type`, both on 2026-09-05 and re-confirmed 2026-09-07;
`ignore_missing_imports = True` swallows the "cannot find module" error that would
otherwise surface this). This is not new to `battery_trust.py` — `evals/summary.py`
already imported `headline_refusal.refusal_for_battery`, `battery_rates`, `panel_metrics`
etc. the identical way; none of those calls happened to be a bare `return <call>` from a
function with a concrete return annotation, which is the one shape `[no-any-return]`
catches, so the gap was invisible until now.
**Why deferred:** **2026-09-07 correction** — the original "To fix" premise below
("`evals/` has no `__init__.py`") is REFUTED: `evals/__init__.py` exists and has since
`e018da01` (EVAL-P0.2), well before this issue was filed. Adding `evals` to `mypy_path`
(the prescribed fix) was attempted and does not simply surface "a batch of newly-real
errors to rebaseline" as assumed — it makes mypy **abort entirely**. `evals/` mixes two
import conventions throughout: bare sibling imports (`from battery_trust import
trust_gate`, the overwhelming majority) and `evals.<module>`-style absolute imports (at
least `evals/dashboard/app.py`, `evals/retrieval_join.py`, `evals/retrieval_runner.py`,
plus 8+ test files including `tests/unit/evals/test_cli_dispatch.py`,
`test_dashboard_runs.py`, `test_dashboard_detail.py`, `test_dashboard_case.py`,
`test_retrieval_join.py`, `test_context_keys.py`, `test_src_free.py`). With `evals` in
`mypy_path`, mypy discovers the same file two ways and refuses to proceed — first
`"Duplicate module named __main__"` (evals/__main__.py, worked around by excluding it),
then immediately `"Source file found twice under different module names: 'dashboard.detail'
and 'evals.dashboard.detail'"` (evals/dashboard/detail.py) — and there is no way to know
how many more such collisions remain without fixing each one and re-running, since mypy
stops at the first. This is a pre-existing structural inconsistency in how the package is
imported, not a config one-liner; out of scope for this remediation session, which is why
this issue stays open rather than fixed.
**To fix:** either (a) standardize every `evals.<module>`-style absolute import in the
**Theme:** T17
~11 files above to the bare-sibling-import convention the rest of the package uses (a
real, moderate-size refactor with its own review — not a `mypy.ini` change), then add
`evals` to `mypy_path`; or (b) accept per-collision `exclude` entries one at a time as
mypy surfaces each one, tracking how large that list grows before deciding it has stopped
being "minimal." Either way: run `make type-evals`, baseline whatever newly-real error
count results with `make type-evals-update`, plus a `DECISIONS.md` entry — do not silently
raise the baseline without recording why.

## ISSUE-287: `make eval-generate`'s own recipe never populates a generation's corpus fingerprint
**Found:** 2026-09-04, during the fresh eval generation run (`k3_61b01dad_negadv`)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/_run_config_corpus.py::default_corpus_fetcher`; `Makefile` `eval-generate` recipe
**Description:** `default_corpus_fetcher` reads the API key from the `API_KEY_SECRET`
*environment variable*, not from the `--api-key` CLI flag `eval-generate` passes to `evals
generate`. The Makefile recipe computes `API_KEY` from `.env` and forwards it only as
`--api-key`, never exporting it into the recipe's own subshell — so the corpus-fingerprint
probe (`GET /v1/admin/debug/vector-store`) always sends `Authorization: Bearer ` (empty),
fails with `LocalProtocolError("Illegal header value b'Bearer '")`, and every generation
records `corpus_item_count/embedding_model/embedding_dim/sha` as null/empty. Confirmed this is
not new to today's run: `k3_73e6c36`, `k3_77688e7_regen1`, `seedrepro_a_1742e8f` and
`seedrepro_b_1742e8f` all carry the same nulls in `meta.json`. Harmless to today's run's core
deliverable (model digests are unaffected and both populated), but DEC-210 Decision 2 added
these fields specifically so "was RAG live during this run?" would be a recorded fact rather
than an inference — that fact has never actually been recorded by any `make eval-generate` run.
**Why deferred:** Out of scope for an operator run; not blocking (an empty corpus fingerprint
degrades a record, it does not corrupt one — `corpus_fields` is deliberately designed to leave
these fields at their None/"" defaults rather than lie).
**To fix:** Either export `API_KEY_SECRET=$(API_KEY)` in the `eval-generate` recipe's own
**Theme:** T17
shell, or have `default_corpus_fetcher` read the same value `evals generate`'s `--api-key`
resolves to instead of a separate env var.

## ISSUE-284: the generate verb's AH-fixture path still has no world guard
**Found:** 2026-09-04, during DEC-261 (the requires_world guard extraction for YAML cases)
**Severity:** P2 (annoying)
**Where:** `evals/generation_collection.py::collect_ah_case_records`
**Description:** DEC-261's new shared guard (`preconditions.npc_exists`, used by both
`runner._run_case` and `generation_collection.collect_yaml_case_records`) only covers YAML
cases. `collect_ah_case_records` still POSTs to `/v1/dialogue` unconditionally for every
`anti_hallucination_demo.json` case. When the NPC is missing, `post_dialogue`'s own
try/except catches the resulting HTTP error and returns `{}` (logged as a warning, not a
skip), and a record is still built from that empty response — an AH case degrades to a
wrong-shaped record instead of skipping cleanly, the same failure mode ISSUE-284 fixed for
YAML cases, one layer down.
**Why deferred:** Out of scope for the YAML-case fix this was found during (single-task
focus); no AH case in the corpus currently requires an unseeded world, so nothing is
corrupted by this today.
**To fix:** Add the same `preconditions.npc_exists` check to the top of
**Theme:** T17
`collect_ah_case_records`, returning `[]` and logging a skip exactly as the YAML path now
does.

## ISSUE-281: the Makefile pins no `SHELL`, so POSIX recipes silently fail when make is run from PowerShell
**Found:** 2026-09-04, during M1.3 row 5 handoff
**Severity:** P2 (annoying)
**Where:** `Makefile` (no `SHELL :=` assignment); affects every recipe using POSIX syntax —
`eval-world-snapshot` (:807), `eval-world-reset` (:820), `restore-with-app-stopped` (:830),
`boot-check` (:72), `app-frozen`.
**Description:** GNU make picks its shell from the environment when the Makefile does not set
one. Run from Git Bash it resolves to `C:/Program Files/Git/usr/bin/sh.exe` and everything
works; run from PowerShell it falls back to `cmd.exe`, which cannot parse the `VAR=value cmd`
prefix, `$PWD`, `$(seq 1 60)` or backslash-continued blocks. The failure surfaces as a bare
`The system cannot find the path specified.` followed by `make: *** [Makefile:856:
restore-with-app-stopped] Error 1`, which names neither the shell nor the real cause.

This is worse than a normal portability wart because the failure is **partial**:
`restore-with-app-stopped` runs `docker compose stop app` successfully (a simple line cmd.exe
can parse) and only then dies on the `MSYS_NO_PATHCONV=1 docker compose run` line. The operator
is left with the app stopped and the graph un-restored, while believing the restore ran.
**Why deferred:** Setting `SHELL` in the Makefile affects every target and both CI and local
runs on three platforms, which is a deliberate change, not a drive-by. It is also adjacent to
CI configuration, which requires approval before touching.
**To fix:** Set `SHELL := /bin/sh` (or a detected Git Bash `sh.exe` on Windows) at the top of
the Makefile, and add a guard target that fails with a readable message when the resolved shell
cannot run a POSIX test. Until then, run make from Git Bash on Windows.

## ISSUE-192: `evals/dashboard/headline.py` silently skips malformed calibration rows without counting them
**Found:** 2026-08-20, during the metrics-pipeline closeout (DEC-193)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/dashboard/headline.py::_adjudicated_row_or_none`
**Description:** a malformed line in `labels_v1.jsonl` is skipped so one bad row cannot blank the
whole kappa badge. The skip is now an explicit sentinel rather than a swallowed exception, but
the COUNT of skipped rows is not surfaced anywhere — so silent data loss in a metrics dashboard
is still possible, which is the failure mode this programme exists to catch.
**Why deferred:** out of scope for the gate-greening task; needs a UI decision about where the
count belongs on the card.
**To fix:** return the skip count alongside the kappas and render it on the badge
**Theme:** T17
(e.g. "3 rows unparseable"), so a degraded input is visible rather than inferred.

## ISSUE-157: ~200 of the 203 dead-keyword findings from `make check-dead-keywords` are untriaged
**Found:** 2026-08-13, during EVAL-P20.1 (HUMAN GATE H6)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/*.yaml` — see `make check-dead-keywords` output (EVAL-P19.3)
**Description:** EVAL-P19.3's dead-keyword detector flags 203 `keyword_none` entries across ~35
cases with zero occurrences anywhere in the committed `k3_73e6c36` corpus. EVAL-P20.1 triaged and
fixed the two named audit examples (`case_neg_lira_no_trust_disclosure: 'thieves guild'` →
apostrophe variant added; `case_neg_captain_sorn_no_hedging: 'i heard'` → apostrophe variant
added, found via the same cross-reference). The remaining ~200 are not individually triaged —
distinguishing "dead because of a wording mismatch" (fix the case) from "dead because the engine
correctly never says this" (leave it, e.g. invented warlord names, system-leak strings,
moderation terms) is a human call per case.
**Why deferred:** out of scope for EVAL-P20.1's ~60 min budget; the two named examples were the
task's actual deliverable, not a mandate to triage the full work-list in one sitting.
**To fix:** re-run `make check-dead-keywords` against the current corpus, manually classify each
**Theme:** T17
remaining entry, and add wording-mismatch fixes to the affected case files' `keyword_none` lists.

## ISSUE-156: `summary._bucket_expectation` never counts `refusal_judge` or
`anti_hallucination_grounded` failures toward `hallucination_failures` (found while
re-measuring EVAL-P17.5)
**Found:** 2026-08-12, during EVAL-P17.5 step 3/4 (same investigation as ISSUE-155)
**Severity:** P2 (annoying)
**Reclassified:** Downgraded P1→P2 2026-09-02 by DEC-250: `hallucination_failures` under-counting distorts a headline string that is no longer published. Kept above P3 because `summary.headline` is still emitted and still wrong.
headline silently excludes two of the three matcher kinds ROADMAP.md's own EVAL-P17.5 spec says
must be counted)
**Where:** `evals/summary.py:19-24` (`_KIND_*` constants) and `_bucket_expectation`
(`evals/summary.py:253-276`)
**Description:** `_bucket_expectation` only adds to `tally["hallucination"]` (guarded by
`is_guard`) for `kind == _KIND_KEYWORD_NONE` (`"keyword_none"`) or
`kind == _KIND_AFFIRMS_JUDGE` (`"affirms_judge"`). Every other kind — including
`"refusal_judge"` (a judge-scored kind, present in `judged.jsonl`) and
`"anti_hallucination_grounded"` (a deterministic kind, present in
`deterministic_judged.jsonl`) — falls through to `else: tally["other"] += 1` and never reaches
`hallucination_failures`, regardless of `is_guard`.
This contradicts ROADMAP.md's own EVAL-P17.5 text verbatim: "the honest post-fix expectation is
~18 failures ... adding the 8 failing `anti_hallucination_grounded` deterministic rows" to the
audit's "≥10 across ≥186" floor. Measured on the unchanged `k3_73e6c36` artifact, with
ISSUE-155's repetition-collision bug hand-patched for this check only (all 3 repetitions
included, not committed to source): failing guard-case rows by kind are `affirms_judge`=3,
`refusal_judge`=7, `anti_hallucination_grounded`=8 — 3+7+8=**18**, exactly the roadmap's
predicted count, and the audit's own "≥10" floor is exactly `affirms_judge`(3)+`refusal_judge`(7).
But `summary.py` as shipped only ever adds `affirms_judge` (and `keyword_none`, which has 0
failures in this artifact) to `hallucination_failures` — `refusal_judge` and
`anti_hallucination_grounded` are silently invisible to the headline. Combined with ISSUE-155,
the pipeline as shipped currently reports "1 lore hallucination across 78 adversarial turns"
instead of the true "18 lore hallucinations across 234 adversarial turns."
**Why deferred:** Out of scope for EVAL-P17.5 (read-only re-measurement, not a pipeline fix) and
out of scope per `project-harness/CLAUDE.md` single-task-focus. Surfaced to the human via
EVAL-P17.5 step 4 before any Session Log edit.
**To fix:** Add `_KIND_REFUSAL_JUDGE = "refusal_judge"` to the `_KIND_*` constants and route it
**Theme:** T17
(and `_KIND_ANTI_HALLUCINATION_GROUNDED = "anti_hallucination_grounded"`) into
`tally["hallucination"]` when `is_guard` is true, in `_bucket_expectation`. Add a regression
test asserting a failing `refusal_judge` and a failing `anti_hallucination_grounded` expectation
in a guard case both increment `EvalSummary.hallucination_failures`. Fix this **together with**
ISSUE-155 — fixing one without the other still produces a wrong headline (either right kinds at
k=1, or right k at wrong kinds).

## ISSUE-146: the legacy capability cases floor the hedge gate at 0.375
**Found:** 2026-08-10, during EVAL-P20.2
**Severity:** P2 (annoying)
**Where:** the seven pre-EVAL-P20.2 `evals/cases/case_pos_*.yaml` files
**Description:** EVAL-P20.2 validation (2) wants the whole capability battery to hold a
scripted always-hedge responder below 0.30. Measured with `make hedge-probe`:

| Set | Rate | Verdict |
|---|---|---|
| the 9 cases authored by EVAL-P20.2 | **0/9 = 0.000** | GATE MET |
| whole battery (16 cases) | **6/16 = 0.375** | GATE NOT MET |

The six legacy cases the hedge beats are the entire remainder — the authored set
contributes zero. A seventh, `case_pos_lira_fence_trade`, resists the hedge but is beaten
by an echo of its own prompt: its `tone_judge` asks whether the speaker engages with the
player's illicit request, and the player's own request trivially does. All seven are named
in `GAMEABLE_BASELINE` in `tests/unit/evals/test_capability_echo_resistance.py`.
**Why deferred:** repairing them changes what existing cases measure, which breaks
comparability with prior generations. That trade belongs to EVAL-P20.1, which already owns
the case-set contradictions, and to the EVAL-P20.4 regeneration that follows it.
**To fix:** strip prompt-echo and hedging tokens from the six keyword lists, replace
**Theme:** T17
`case_pos_lira_fence_trade`'s judge with one that cannot be satisfied by the prompt, then
delete each repaired id from `GAMEABLE_BASELINE` and confirm `make hedge-probe` exits 0.

## ISSUE-148: `make draft-cases` cannot reach the grounded edges it exists to read
**Found:** 2026-08-10, during EVAL-P20.2
**Severity:** P2 (annoying)
**Where:** `evals/case_drafts.py:27-33` (`GROUNDED_EDGE_TYPES`), `:342` (`httpx.Client()`), `Makefile` `draft-cases`
**Description:** Three independent faults, each sufficient on its own to make the tool
return nothing:
1. **No auth.** `case_drafts.py:342` builds `httpx.Client()` with no `Authorization`
   header and the CLI exposes no `--api-key`, so every request 401s at
   `_fetch_grounded_edges`'s `raise_for_status()`. The Makefile target has `$(API_KEY)`
   available and does not pass it.
2. **Two-thirds of the edge types do not exist.** `GROUNDED_EDGE_TYPES` names
   `HAS_MEMORY`, `HAS_GOAL` and `HAS_SECRET`. The registry
   (`GET /v1/admin/schema/registry`) has `REMEMBERS`, `PURSUES` and `KNOWS_SECRET`;
   the three wrong names return HTTP 422.
3. **The generic graph reader is blind to inner life even for the correct names.**
   `GET /v1/graph/edges/BELIEVES?src_id=bren_smith` returns `[]` and
   `GET /v1/graph/nodes/Belief` returns a single unrelated node, while
   `GET /v1/admin/beliefs/bren_smith` returns the two seeded beliefs. Same for goals,
   memories and secrets. This may share a root cause with ISSUE-145.

EVAL-P20.2 was authored against the typed admin endpoints instead; the tool produced no
usable draft.
**Why deferred:** `make draft-cases` is EVAL-P9.2's deliverable, and (3) is likely the
same defect as ISSUE-145 — fixing the tool before the reader would be repairing a symptom.
**To fix:** settle ISSUE-145 first, then add `--api-key` (defaulting to `$API_KEY_SECRET`)
and wire `--api-key $(API_KEY)` into the Makefile target, correct `GROUNDED_EDGE_TYPES` to
the registry names, and add a test that fails when a name in it is absent from
`GET /v1/admin/schema/registry`.

## [WONTFIX] ISSUE-051: Dashboard S12.4 engine cadence/cost controls are read-only (no live mutation)
**Found:** 2026-06-03, during S12.4
**Severity:** P3 (nice-to-fix)
**Where:** `dashboard/js/engines.js`, `src/npc_engine/api/routes/system.py` (`/v1/system/config`)
**Description:** The Engines tab displays runtime cadence/cost config + per-engine status but cannot change them. `Settings` is a frozen `lru_cache` singleton and the autopilot captures `interval_seconds`/`budget_guard` at construction in the lifespan, so there is no runtime-mutation path. See DEC-054.
**Why deferred:** Live mutation requires a `RuntimeConfigStore` injected into the autopilot + a guarded write endpoint — a public-interface/scheduler change needing approval, out of scope for the read-only first slice.
**To fix:** Add a `RuntimeConfigStore` read by the autopilot each loop for interval + LLM budget; expose `PATCH /v1/system/config` (graph_admin scope, bounded values); wire the dashboard inputs to it.
**Closed:** 2026-06-03, S13.2 dropped (DEC-055) — deprioritized below the CRITICAL/HIGH review-remediation backlog; dashboard controls remain read-only. Reopen if a customer needs live tuning.

---

## ISSUE-311: ISSUE-107's "wired into the e2e battery" claim is false
**Found:** 2026-09-07, during full-review (L6-02)
**Severity:** P2
**Where:** `e2e/scenarios/scenario_memory_recall_e2e.py`
**Description:** ISSUE-107 was resolved with the claim that the cross-session memory-recall scenario is "wired into the e2e battery". It is not: the file has no `test_*` function or marker and is collected by nothing. The persistent-memory guarantee — the product's headline capability — has no automatic cross-session test. Contradicts a resolved issue, so this is a **regression** of the resolution, not a new gap.
**Why deferred:** Needs a decision on where cross-session e2e runs (it needs live services).
**To fix:** Give the scenario a collectable test entry point and put it in a suite something actually runs.

## ISSUE-322: the `stream`/`stream_text` call site is dead in the production dialogue path
**Found:** 2026-09-07, during full-review (L11-01)
**Severity:** P2
**Where:** `src/npc_engine/engines/dialogue/`, `engines/llm/` streaming methods
**Description:** The streaming protocol methods are implemented but unreachable from the production dialogue path. Related to ISSUE-299 (docs describe WS streaming frames the code does not send).
**Why deferred:** Deleting a protocol method is a public-interface change.
**To fix:** Either wire streaming into the WS path (which is what the docs already claim) or delete the dead methods and correct the docs.

## ISSUE-328: two independent 5-band tone systems do the same job from different data
**Found:** 2026-09-07, during full-review (L12-05)
**Severity:** P2
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Rules 2 and 16)
**Description:** Rule 2 (PLAYER REPUTATION) and Rule 16 (STANDING) each define a 5-band tone system from a different data source, leaving the model to reconcile them per turn. L12 recommends a structural server-side merge over prompt-side arbitration — resolve the bands in code and hand the model one answer.
**Why deferred:** Behavioural change plus prompt-hash cost; needs sign-off.
**To fix:** Merge the bands server-side, pass one resolved tone into the prompt, delete the second rule.

## ISSUE-132: `evals/` mixes flat and package-absolute imports
**Found:** 2026-08-07, during EVAL-P6.3
**Severity:** P3 (nice-to-fix — currently papered over, not breaking)
**Where:** `evals/retrieval_runner.py:27-29` (package-absolute) vs `evals/generate_runner.py:22-30`,
`judge_runner.py:21-24`, `runner.py:24-28`, `deterministic_pass.py:31-34`, `calibration.py:20`,
`adjudicate.py:18`, `report.py:10-11` (flat).
**Description:** `retrieval_runner` imports `from evals import engine_adapter`; every other runner
imports `import matchers` / `from summary import ...`. Flat imports only resolve when `evals/` itself
is on `sys.path` — which `python evals/runner.py` provides implicitly and `python -m evals` does not.
pytest hides the split entirely because `pyproject.toml:60` sets
`pythonpath = ["src", "e2e/scenarios", "e2e", "evals"]`, so both styles work under test and the
inconsistency is invisible until something is invoked as a module.
**Why deferred:** EVAL-P6.3's binding constraint is a green gate at every commit; converting nine
modules' imports is a behaviour-neutral change with a wide blast radius that would also break the
documented `docker compose exec app python -m evals.retrieval_runner` workaround (ISSUE-131) if done
carelessly. `evals/__main__.py` prepends `evals/` to `sys.path`, which makes both styles resolve today.
See DEC-155 §3.
**To fix:** Convert every flat import in `evals/` to `from evals.x import y`, delete the `sys.path`
**Theme:** T17
shim in `evals/__main__.py:30-32`, and drop `"evals"` from `pyproject.toml`'s `pythonpath` so the gate
stops masking a regression. Verify `docker compose exec app python -m evals.retrieval_runner` still
runs, since ISSUE-131 makes it the only way to run retrieval against Neo4j.

## ISSUE-135: `generate_runner.collect_records` skips the `learned_from_player` preflight for AH cases
**Found:** 2026-08-07, while planning EVAL-P6.1
**Severity:** P2 (annoying — can mis-score a category of anti-hallucination cases in the two-phase pipeline)
**Where:** `evals/generate_runner.py:200-207` (the `ah_cases` loop in `collect_records`)
**Description:** `anti_hallucination_runner._classify_case` gates `learned_from_player` cases on
`_belief_fact_persisted` (a pre-flight GET against `/v1/admin/beliefs/{npc_id}`) and skips the case — rather
than scoring it — when the player-taught fact was never persisted in a prior session (ISSUE-090/DEC-095).
`generate_runner.collect_records`'s AH loop has no equivalent check: it calls `/v1/dialogue` for every
`ah_case` unconditionally and always builds a record. A `learned_from_player` case run through
`eval-generate` → `eval-judge`/`eval-score` before the taught fact exists will therefore be scored as a
false-fail (or false-pass) instead of skipped, which the single-phase `anti_hallucination_runner` path
already avoids.
**Why deferred:** Out of scope for EVAL-P6.1 (deterministic-matcher coverage) and EVAL-P6.2 (guard-turn
double-count) — orthogonal to both. Only matters once `learned_from_player` cases are actually run through
the two-phase pipeline; today's fixture (`anti_hallucination_demo.json`) does exercise that category via
`make eval-anti-hallucination`, not via `eval-generate`.
**To fix:** Port the `_belief_fact_persisted` pre-flight into `generate_runner.collect_records`'s AH loop
**Theme:** T17
(same GET, same `preflight_belief_substrings` fallback to `expected_fact_substrings`) and skip building any
record — deterministic or judged — for a `learned_from_player` case whose fact isn't persisted yet. Add a
regression test with a mocked "belief not found" response asserting zero records are produced for such a case.

## ISSUE-149: `judge_runner._apply_polarity` has zero direct test coverage — survives mutation
**Found:** 2026-08-11, during EVAL-P15.6 (mutation survival gate)
**Severity:** P2 (annoying)
**Where:** `evals/judge_runner.py:90-105` (`_apply_polarity`)
**Description:** `make check-mutations` (new in EVAL-P15.6) applies
`_apply_polarity → return score is True` and the full unit suite still passes — the mutation
survives. The mutated body is behaviorally identical to the original for `score is None` and for
`polarity == pass_on_yes`, but inverts every `pass_on_no` verdict (`score is False` → PASS becomes
`score is True` → PASS). `grep -rl _apply_polarity tests/ evals/` finds no test file that calls the
function directly — its only coverage is incidental, through whatever end-to-end fixtures happen to
route a `pass_on_no` record through `judge_one`/`judge_transcript`, and apparently none of those do.
**Why deferred:** EVAL-P15.6's task was building the mutation-probe mechanism itself, not fixing
every gap it finds on first run — same pattern as EVAL-P20.2 exposing ISSUE-145. Fixing this is a
separate, scoped task (single-task-focus).
**To fix:** Add a direct unit test for `_apply_polarity` in `tests/unit/evals/test_judge_runner.py`
**Theme:** T17
(or create it if it doesn't exist) covering all 5 cases: `score=None`, `pass_on_yes`+True,
`pass_on_yes`+False, `pass_on_no`+True, `pass_on_no`+False. Re-run `make check-mutations` and
confirm zero survivors.

## ISSUE-184: `refusal_judge` and `affirms_judge` have poor chance-corrected agreement (kappa 0.23 / 0.28)
**Found:** 2026-08-18, from the corrected panel metrics of the 2026-08-17 run
**Severity:** P2 (annoying) - bounds what any A/B comparison on these criteria can resolve
**Where:** `prompts/eval/refusal_judge.yaml`, the `affirms_judge` criterion set
**Description:** With polarity applied and repetitions no longer pooled, per-criterion Fleiss kappa
over 345 records is: `tone_judge` 1.000 (unanimous 135/135), `affirms_judge` 0.282 (unanimous
128/135), `refusal_judge` 0.225 (unanimous 59/75). Overall kappa is 0.526 with a wide clustered
bootstrap 95% CI of [0.227, 0.730]. The raw agreement headline of 0.956 conceals this entirely,
because the pass base rate is 0.951. This is independent empirical confirmation of ISSUE-141's
diagnosis (two `refusal_judge` prompt rewrites already attempted and reverted) and extends it:
`affirms_judge` is nearly as weak. Practical consequence for the A/B pipeline - an effect smaller
than the judge noise floor on these two criteria is not measurable with this panel, whatever the
sample size.
**Why deferred:** fixing it means prompt work on two judge criteria plus a re-run to measure the
effect, which is its own task; the measurement that establishes the problem is the current task.
Supersedes nothing - ISSUE-141 stays open and is now better evidenced.
**To fix:** treat per-criterion kappa as the target metric for the next `refusal_judge` /
**Theme:** T17
`affirms_judge` prompt iteration (ISSUE-141), and judge progress on the per-criterion breakdown
rather than the raw-agreement headline.

## ISSUE-203: the two weight profiles the dialogue path actually uses cannot be tuned from YAML
**Found:** 2026-08-26, during P2 while fixing ISSUE-198
**Severity:** P2 (annoying) - blocks weight A/B arms; not wrong today, just unreachable
**Where:** `retrieval/context/context_builder.py:622`, `retrieval/embedding/topic_classifier.py:24`,
`schema/context_config_models.py:DEFAULT_WEIGHT_PROFILES`
**Description:** ISSUE-198 made `relevance_weights:` live for the profile name `"default"`.
Dialogue never asks for that name. `build_serialized_context_with_receipt` resolves
`weight_profile or active_profile.weight_profile or detect_dialogue_profile(player_message)`,
and `detect_dialogue_profile` always returns a non-empty string - `"rpg_dialogue_quest"` or
`"rpg_dialogue_social"`. Both live only in the Python dict `DEFAULT_WEIGHT_PROFILES`, and
`llm_config.yaml` declares no `weight_profiles:` block, so **the weights every dialogue turn
is ranked by are a hardcoded Python literal.** `llm_config.default_weight_profile` is dead on
this path for the same reason. Changing dialogue ranking today means editing Python and
rebuilding the image, which is exactly the churn the A/B pipeline exists to avoid.
The lever already exists and is untested-in-anger: `resolve_weights` checks
`self.weight_profiles` BEFORE `DEFAULT_WEIGHT_PROFILES`, so a YAML entry of the same name wins.
Pinned by `test_a_yaml_weight_profile_overrides_a_builtin_of_the_same_name`.
**Why deferred:** P2 is scoped "minimal: fix the logged defects only", and declaring the two
profiles in YAML duplicates numbers that already exist in Python - that needs a decision on
which is canonical, not a drive-by edit.
**To fix:** declare `weight_profiles:` in `src/npc_engine/config/llm_config.yaml` with
`rpg_dialogue_social` and `rpg_dialogue_quest`, and decide whether `DEFAULT_WEIGHT_PROFILES`
becomes a fallback-only registry or is deleted for those two names. Pairs naturally with P7's
tier gating: `RetrievalProfile.weight_profile` is already a per-arm field, so once the names
resolve from YAML a weight arm costs one config block and no code.

## ISSUE-204: `e2e/scenarios/scenario_territorial_war.py` cannot be imported
**Found:** 2026-08-26, during P2's full-suite run
**Severity:** P3 (nice-to-fix) - invisible to `make test`, which runs `tests/` only
**Where:** `e2e/scenarios/scenario_territorial_war.py:18`
**Description:** `from npc_engine.graph.military_queries import get_armies_in_conflict` raises
`ModuleNotFoundError`. The module moved to `npc_engine.graph.military.military_queries` in the
graph-layer package split and this import was never updated. Collecting the repo root
(`pytest -q` with no path) therefore aborts with a collection error before running anything -
`Interrupted: 1 error during collection`. Confirmed pre-existing: reproduced with all P2 work
stashed. `make test` targets `tests/` so CI never sees it, which is why it has survived.
**Why deferred:** not P2's subsystem, and not P2's regression.
**To fix:** one-line import update to `npc_engine.graph.military.military_queries`, then run
the scenario to see whether the rest of it still matches `MilitaryEngine`'s contract (the file
was last touched by `21145f3 test(military): rewrite stale scenario test...`, so it may have
drifted further). Consider adding `e2e/` to a collect-only CI step so this class of rot fails
fast instead of silently.

## ISSUE-208: `active_pledges` loses its expiry tick to the global deny-list
**Found:** 2026-08-26, during P3
**Severity:** P3 (nice-to-fix) - no observable effect today
**Where:** `retrieval/graph_rag/subgraph_retriever.py:_pledge_item`
**Description:** `_pledge_item` hand-projects `expires_at_tick` as prompt content, and
`expires_at_tick` is in `NON_PROMPT_NODE_FIELDS`, so P3's uniform strip now removes it. This
was a deliberate choice over adding a per-producer exception (see DEC-202): a global deny-list
with one carve-out is the kind of thing nobody remembers, and the carve-out would have to be
re-justified at every future producer. Nothing observable changes because `active_pledges` has
no slot in the serialized skeleton at all (ISSUE-200) - the item is assembled, ranked, charged
to the tier-A budget, then discarded.
**Why deferred:** whether a bare tick number is useful to the model is a prompt-schema question
and cannot be answered until the key has a slot.
**To fix:** decide with ISSUE-200 in P5. If pledges get a slot, either render the expiry as a
relative phrase the model can use ("expires in 12 ticks") rather than an absolute counter it
cannot compare, or drop it. If they do not get a slot, stop assembling the item and the
question disappears.

**Update 2026-08-26 (P6, DEC-205).** Half-answered, and the remaining half is now a one-flag
decision instead of an open design question. `active_pledges` HAS a declared slot --
`npc.active_pledges`, severity_field `severity` -- but `default_enabled=False`, because no
prompt rule teaches the model to read it. `_drop_withheld_items` now also stops the item
being assembled and charged at all, so the "stop assembling the item" branch of the fix
above is what actually happens today and the budget question is closed. The expiry-rendering
question stays open and stays parked with the flag: whoever flips `default_enabled` to True
must decide then whether a bare `expires_at_tick` is usable by the model or needs rendering
as a relative phrase, and add the prompt rule in the same change.

## ISSUE-209: tier-A selection is not monotone in the tier-A cap
**Found:** 2026-08-26, during P4 while guarding the ISSUE-197 reclaim
**Severity:** P3 (nice-to-fix) - a small, bounded loss at the margin; no data is corrupted
**Where:** `retrieval/context/context_budget_enforcer.py:_fit_tier_a_pinned_pool`
**Description:** the non-pinned pool is filled greedily in priority order, SKIPPING any item
that does not fit rather than stopping (which is correct -- stopping is the ISSUE-145 bug).
The consequence is that raising the cap can DROP an item that previously fit, because a
larger cap admits a high-priority item that was being skipped and it consumes the room two
smaller items behind it were sharing:

    items [A=70, B=40, C=30]    cap 100 -> {A, C}    cap 110 -> {A, B}

ISSUE-197 recorded this symptom ("a prototype that reclaimed the leftover moved captain_sorn
from 1 goal to 0") and attributed it to the post-serialization trim loop. That attribution is
wrong: no serialization is involved, and the trim loop only ever removes items. Observed live
in P4 as well -- `old_henryk`, the NPC with the fullest context at 1,156 tokens, gained his
memories and lost `nearby_npcs`, which he does have (`tilda_herbalist`, `aldric_merchant` are
co-located; `vw_elder` and `vw_farmer` are genuinely alone, so their empty slot is correct).
Pinned by `test_raising_the_tier_a_cap_can_still_drop_an_item_that_previously_fit`.
**Why deferred:** the fix is to stop selecting greedily -- a bounded knapsack over ~12 items,
which is cheap to compute but is an allocator rewrite, and D2 ruled that out for this plan
("keep four tiers, keep fill_to_budget, no rewrite"). The loss is also small and bounded: it
can only affect items at the very tail of the budget.
**To fix:** replace the two skip-loops with a bounded knapsack (or a simple best-fit pass
after the greedy one, which recovers most of the gap for a fraction of the change). Measure
on the 8-NPC probe: the target is `nearby_npcs` back to 6/8 without losing any inner-life
field. Do it after P7, so the RAG tiers are exercising the allocator too.

**Update 2026-08-26 (P5, DEC-204).** Masked, not fixed. At `PROMPT_TOKEN_BUDGET` 25888 the
cap never binds, so the symptom disappears: a controlled A/B (same world, same image, window
the only difference) shows `old_henryk` regaining `nearby_npcs` 0 → 49 tokens, and the
tier-A soft-cap drop count going 1 → 0. That is the ONLY item this bug was costing across
eight NPCs. It will come back the moment P10 trims the window or P8's live tier B puts the
allocator under pressure again, so the "measure on the 8-NPC probe" instruction above must
be run at the POST-TRIM window, not at 32768 where it would pass vacuously.

## ISSUE-212: the admin reindex job reports `completed` while only deleting entries that were never inserted
**Found:** 2026-08-27, during the P8 planning review (DEC-208)
**Severity:** P2 (annoying — an admin endpoint that cannot do what its name says, and says it did)
**Where:** `retrieval/graph_rag/reindex_job_service.py:70-88` (`_run_reindex_job`), reached from
`api/routes/admin/graph_admin.py:131`
**Description:** `submit_reindex(npc_ids, embedding_index)` loops over the ids calling
`embedding_index.invalidate(item_id=npc_id)` — i.e. `vector_store.delete` — then sets
`status: "completed"`, `processed_ids: [...]`, `failed_count: 0`. Nothing re-indexes. There is
no upsert in the job, and (per DEC-208) there was no upsert anywhere in `src/` at all, so the
job has always been deleting entries that never existed and reporting success for work it did
not do. An operator invalidating a stale NPC embedding gets a green job and an unchanged store.
DEC-208 lands the insert path and `ensure_corpus`, which makes a real reindex *possible*; it
does not by itself fix this job's semantics or its status reporting.
**Why deferred:** DEC-208's scope is corpus ownership and the boot/populate path. Repointing
this job at `ensure_corpus` (or at a per-id upsert) changes an admin endpoint's behaviour and
belongs in its own change with its own test, not inside the phase that is gating a
regeneration.
**To fix:** after DEC-208 lands, repoint `_run_reindex_job` at invalidate-then-upsert per id
(or at a scoped `ensure_corpus`), and make `processed_ids` mean "re-embedded", not "delete
attempted". Add a test asserting the store holds an entry for each processed id afterwards —
the current test suite cannot distinguish this job from a no-op.

## ISSUE-214: byte truncation still emits invalid JSON whenever a PROJECTED payload is over budget
**Found:** 2026-08-27, during P8 §8.2 (DEC-209 Decision 3)
**Severity:** P2 (annoying — the prompt receives a raw broken string in place of an object)
**Where:** `retrieval/context/context_compression.py:_compress_text` (reached from
`_field_select_compress` when the projected text still exceeds `target_chars`)
**Description:** DEC-209 Decision 3 added `rag` to `_ESSENTIAL_FIELDS`, which fixes the
*observed* case: an uncompressed `rag:` payload fell straight through to byte truncation
and produced `{"occurred_at":"2026-01-01","severity":60,"summary":"...[compressed]#b1113aa4`
— unclosed string, unclosed brace — which `_safe_parse` then handed to the prompt as a raw
string. Projection now removes the bulk, so a realistic payload compresses to valid JSON.

The truncation path itself is unchanged and still character-based. Any item whose
payload is over budget *after* projection gets the same broken output, and this is NOT
rag-specific: `event`, `character`, `memory` and every other row in `_ESSENTIAL_FIELDS`
reach the same `_compress_text`. A single long `summary` or `content` field is enough.
Verified with a 920-character summary: `json.loads` raises
`Unterminated string starting at: line 1 column 14`.

Nothing has hit this in production because tier B has carried zero items on every run
ever recorded, and tier-A payloads at the current budget do not trigger compression.
P8 makes tier B reachable; P10's trim makes compression reachable.
**Why deferred:** DEC-209 Decision 3 names the fix and it is the `_ESSENTIAL_FIELDS` row.
The truncation path is shared by every node type, so changing it changes compression for
tier A too — which is a behaviour change inside the phase that is gating a regeneration.
It is also masked at P5's 25,888-token budget, where nothing is compressed at all.
**To fix:** truncate the longest FIELD VALUE and re-serialize, rather than truncating the
**Theme:** T17
JSON string, so the output is always parseable; keep the `...[compressed]#<sha>` marker
inside the truncated value. Add a property test over `_ESSENTIAL_FIELDS` asserting
`json.loads` succeeds for every node type at every target size. Do it with P10's trim,
where compression actually fires, not before.

## ISSUE-222: an empty producer item is still keyed, ranked and charged
**Found:** 2026-08-27, during P9 remediation while sizing the tier-A arm (DEC-214)
**Severity:** P3 (nice-to-fix - ~1 token; the cost is that it misleads an instrument)
**Where:** the tier-A producers feeding `context_builder`, e.g. `nearby_npcs`
**Description:** `bren_smith`'s `nearby_npcs` context item exists with text `"[]"`. It is
in `item_keys`, it is ranked, and it is charged to the budget, and it carries nothing. The
token cost is negligible. The real cost is that `item_keys` occupancy stops being a valid
signal of whether a slot delivers anything: `nearby_npcs` reads 8/8 by item_keys and 7/8 by
`scripts/probe_inner_life.py`, and the second number is the true one.

This nearly shipped a dead A/B arm. `no_nearby_npcs` was declared on the 8/8 figure and
would have been a guaranteed null for one NPC in eight, because P6 emits every declared
slot with its empty default — so withholding an already-empty item leaves the serialized
context byte-identical. Caught by comparing the two instruments; the tier-A arm now
withholds `memories` instead (DEC-214).
**Why deferred:** it is a change across several producer call sites, and DEC-214's own
scope was the arm set. Gate 4 is unaffected either way.
**To fix:** either have the producers skip an item whose serialized text is an empty
**Theme:** T17
container, or teach `_drop_withheld_items` to drop it centrally — the latter matches the
"one place, not twenty call sites" argument already in that function's docstring. Verify
with `make probe-inner-life`: `nearby_npcs` must read 7/8 by BOTH instruments.

## ISSUE-219: the player character node is inside the RAG scope and retrievable
**Found:** 2026-08-27, during P9 gate 4 while reading probe output
**Severity:** P3 (nice-to-fix - no wrong answer today; a category error in the context)
**Where:** `src/npc_engine/graph/graph_rag_queries.py:_CYPHER_RAG_SCOPE_IDS`
**Description:** `captain_sorn`'s default assembly retrieves `rag:player_demo` — the
PLAYER's own Character node — as tier-B/C context about the NPC's surroundings. It is in
scope legitimately (the player is a `Character` in the NPC's 1-hop subgraph, and the
corpus embeds every Character), and it is not currently harmful, because the payload is
the player's own profile fields.

It is still a category error. `retrieved_context` is declared to the model as "related
information, not events you witnessed" (system prompt Rule 17), and handing an NPC the
player's node under that heading invites the model to narrate the player's biography back
at them as background lore. It also spends tier-B budget on a node the player already
carries via `player_relation`.
**Why deferred:** it is a scope-query change, and DEC-209's scope is a signed-off decision
with its own tests; changing it after P9's gates run would re-arm the whole phase under
P9's own no-src-change-after-green fence. It affects one item out of five and costs no
correctness today.
**To fix:** exclude the requesting `player_id` (and any node whose label set marks it as a
**Theme:** T17
player) from `get_rag_scope_ids_for_npc`, the same way `known_event_ids` is subtracted by
the caller. Add `test_the_rag_scope_never_contains_the_player_being_talked_to`. Verify with
`make eval-arm-probe`: `rag:player_demo` must disappear from captain_sorn's default keys
and the tier-B count drop from 2 to 2 with a different member, not to 1.

## ISSUE-220: the retrieval probe still assembles one fewer tier-0 item than a dialogue turn
**Found:** 2026-08-27, during P9 final verification (DEC-213)
**Severity:** P3 (nice-to-fix - 1 item / 18 tokens; parity is otherwise exact)
**Where:** `src/npc_engine/api/routes/admin/debug_retrieval.py::get_debug_retrieval`
**Description:** P9 gave the probe the dialogue turn's `player_id`, `retrieval_profile`,
session turns and cache parameters, and parity is now exact on the three tiers that
matter. Measured back to back on the clean eval baseline, captain_sorn / "what news":

    dialogue turn   tier0 3/93   tierA 8/687   tierB 2/93   tierC 3/140   total 1013
    debug probe     tier0 2/75   tierA 8/687   tierB 2/93   tierC 3/140   total  995

tierA, tierB and tierC agree exactly, including the `rag:` members. The residual is
`system_state`: `build_serialized_context_with_receipt` takes a `system_state_context`
argument, the dialogue handler passes one, and this route passes None. The slot is still
EMITTED (P6 makes every declared slot unconditional), so the JSON schema the model sees is
unchanged; it is emitted empty.

Consequence is small but real: any P10 number quoted from the probe understates a real
turn's tier-0 spend by ~18 tokens, and `system_state` is the one slot the probe cannot
observe at all.
**Why deferred:** it is a `src/` change, and P9's own hard rule is that no `src/` change
lands after the gates run. Found DURING the final verification pass, after the gates.
Fixing it now would re-arm the whole phase for 18 tokens.
**To fix:** thread a `system_state_context` through the route the way the dialogue handler
**Theme:** T17
builds it, or expose the handler's builder so both call sites share one construction. Add
a parity test asserting the probe and a dialogue turn produce the same tier-0 item COUNT
for one fixture NPC. Verify by re-running the back-to-back comparison above: tier0 must
read 3/93 on both sides.

## ISSUE-224: `session_turn` on the retrieval probe rejects every value it is given
**Found:** 2026-08-27, during P10 while measuring the assembled-context ceiling (DEC-215)
**Severity:** P2 (annoying — a declared parameter of a measuring instrument is unusable,
and its absence silently understates every ceiling the instrument reports)
**Where:** `src/npc_engine/api/routes/admin/debug_retrieval.py:105`, the
`session_turn: _SessionTurns | None = None` parameter (`_SessionTurns` is
`Annotated[list[str], Query(...)]`, declared at :74)
**Description:** P9 added `session_turn` to `GET /v1/admin/debug/retrieval` so the probe
could assemble context the way a real dialogue turn does. It accepts nothing. Any value,
at any repetition count, is rejected:

    GET /v1/admin/debug/retrieval?npc_id=mira_innkeeper&query=what+news
        &player_id=player_demo&session_turn=hello1
    -> 422 {"field":"query.session_turn","reason":"Input should be a valid list"}

Reproduced at 1, 2 and 5 repetitions; only the zero-repetition case (parameter omitted
entirely) succeeds. The `| None = None` union around an `Annotated[list[str], Query(...)]`
is what defeats FastAPI's repeated-query-parameter parsing.

**Two consequences, and the second is the one that matters.**
  * DEC-213 records "Parity with a dialogue turn is verified EXACT on tierA/tierB/tierC".
    That parity was necessarily verified at ZERO session turns, because no other value is
    reachable. It is a true statement about a narrower claim than it reads as.
  * Session turns are tier-A items charged against the same prompt budget. Every ceiling
    figure in DEC-215 therefore EXCLUDES session history and understates a real client
    turn by however much a session costs. DEC-215 works around this by sizing the window
    to hold the measured ceiling PLUS the full 1200-token `session_turns_budget_tokens`
    allowance, which is a design bound rather than a measurement — see ISSUE-225 for why
    even that bound is not enforced.
**Why deferred:** it is an API-signature fix in `src/`, and P10's remaining work is a
window trim whose gates would all have to re-run after it. The window chosen is large
enough that the missing measurement cannot change the decision: at budget 5158 the
measured ceiling of 1151 plus the entire session allowance is still under half the budget.
**To fix:** drop the `| None` and give the parameter a list default —
**Theme:** T17
`session_turn: _SessionTurns = Query(default=[])` — or take the turns in a POST body.
Add a route test asserting a two-repetition request returns 200 AND that the receipt's
tier-A spend GROWS relative to the same request with none, so a parameter that parses but
is ignored still fails. Then re-measure the ceiling table in DEC-215 with a full session
and confirm the chosen window still holds it.

## ISSUE-225: `session_turns_budget_tokens` is enforced only by a function nothing calls
**Found:** 2026-08-27, during P10 while bounding the session contribution to the ceiling
**Severity:** P2 (annoying — an unbounded quantity inside a bounded budget; no data is
corrupted, but the cap that is supposed to stop it is decorative)
**Where:** `src/npc_engine/retrieval/context/context_budget_enforcer.py:87` (the check),
inside `enforce_context_budget`, which has no production callers
**Description:** `llm_config.yaml` declares `session_turns_budget_tokens: 1200` and
`enforce_context_budget` raises `ContextBudgetError` when the tier-A items keyed
`session` exceed it. Nothing in production calls `enforce_context_budget`. The live path
is `fill_to_budget_with_report`, reached from `context_builder.py:575`, and it performs no
session check at all — it validates tier 0 (`_validated_tier0_tokens`) and nothing else.

Verified repo-wide: every reference to `enforce_context_budget` outside its own module is
either the `retrieval/context/__init__.py` re-export or a test
(`test_context_budget_enforcer_v14.py`, `test_context_pinned_pool.py`). `src/`, `evals/`,
`demo_game/` and `e2e/` contain no call.

So session history is unbounded within tier A on the path that actually runs. With
`DIALOGUE_SESSION_TURNS=10` and `MAX_PLAYER_MESSAGE_CHARS=1000`, ten turns of
player message plus a 512-token reply is on the order of 7,600 tokens — well above the
1,200 the config claims and above the whole assembled-context ceiling.

It has not bitten because the eval harness never sends a `session_id`
(`evals/generation_collection.py` omits it), so every measured turn in P8, P9, DEC-214 and
DEC-215 has zero session history. A game client does send one.

**Why deferred:** the fix is a behaviour change inside the budget enforcer, and D2's "no
allocator rewrite" plus P10's own "gates re-run after any src/ change" make it the wrong
thing to land inside a phase that is gating a regeneration. It is also not what P10 is
for.
**To fix:** decide whether `enforce_context_budget` is dead code to delete or a check to
move. If the latter, lift the session sub-budget check into
`fill_to_budget_with_report` alongside `_validated_tier0_tokens` — but note it currently
RAISES, and `fill_to_budget` is documented as never failing a turn for budget reasons, so
the session excess probably wants to be TRIMMED (oldest turn first) rather than raised on.
Add a test that a session over the sub-budget is bounded on the live path, and a test that
fails if `enforce_context_budget` regains zero callers while still being exported.

## ISSUE-237: check_base_rate scores generation rows for cases that no longer exist
**Found:** 2026-08-31, during R2 planning
**Severity:** P2 (annoying) — silently overstates n and makes case deletions invisible
**Where:** scripts/check_base_rate.py `_iter_rows`
**Description:** `_iter_rows` reads only `deterministic_judged.jsonl` and `judged.jsonl`
from a generation directory and never consults `evals/cases/`. A case deleted from the
corpus keeps contributing verdict rows to every base rate forever. Measured: deleting the
19 fully-dead keyword_none blocks plus the 3 moderation cases would move the overall rate
0.943 -> 0.935 and keyword_none 0.957 -> 0.917 on `k3_77688e7_regen1` if the filter
existed; today it moves neither. This is why R2.4 had to be re-anchored onto
check-dead-keywords.
**Why deferred:** the fix couples the gate to working-tree case state and must derive
case_id by string-parsing `record_id` ("case:matcher:rep") for deterministic rows, which
carry no case_id field. Landing it inside R2.3 would add a second cause to that commit's
numbers, which is the attribution error R2 exists to stop.
**To fix:** add a case-existence filter to `_iter_rows`, report the dropped-row count
**Theme:** T17
explicitly so silent shrinkage is visible, and red when the drop rate exceeds a recorded
baseline. Revisit when a regeneration is next run.

## ISSUE-238: 14 guard cases state a knowledge-boundary property that nothing enforces
**Found:** 2026-08-31, during R2.4
**Severity:** P3 (nice-to-fix)
**Reclassified:** Downgraded P1→P3 2026-09-02 by DEC-250: 14 guard cases asserting nothing matter only to a published claim. They are dead weight in a retained smoke test, not a blocking defect.
**Where:** `evals/cases/case_adv_*.yaml`, `evals/cases/case_neg_*.yaml` (the 14 stripped by R2.4)
**Description:** Each of these 14 cases carries a precise property in its `description` — "NPC X,
pressed under a false premise, must not confabulate knowledge belonging to NPC Y's KNOWS_ABOUT
edges" (10 cases), "NPC X must hold its voice register" (3), or both (1). That property was
asserted by a `keyword_none` list of literal phrasings. Every one of those lists was 100% dead
against `k3_77688e7_regen1` — 103 terms, zero hits in 975 responses — so none could fail, and
R2.4 removed them. The lists were lexical, not semantic: `case_neg_aldric_no_troop_knowledge`
forbade `"the troops are at"` but not "the garrison sits north of the pass";
`case_neg_mira_no_guild_secrets` forbade `"the hideout is"` but not "Lira keeps things down by
the docks". Zero hits was therefore equally consistent with "the engine never leaks" and "the
engine leaks in words nobody guessed", and the block could not distinguish them. Two of the
files record earlier hand-repairs that made their lists *narrower* still
(`case_adv_captain_sorn_guild_smuggling` dropped `"the smugglers are"`,
`case_adv_mira_aldric_trade_figures` dropped `"exactly"`), so the lexical approach has already
been observed failing in both directions.
What still runs on these cases is the runtime-injected guard battery
(`evals/runner.py:_expected_with_guards`): `min_length`, a `keyword_none` over the canned
fallback lines, `tone_judge` (structural in-character rubric) and — for demo-world cases, which
all 14 are — `affirms_judge` with the war-is-over lore rubric. None of those asserts the
per-case knowledge boundary. That specific claim is currently unenforced.
**Why deferred:** the fix is 14 hand-written judge rubrics, which is a phase of work, and it
must be a separate commit from R2.4's deletion or the 208 -> 105 move has two causes — the
attribution error R2 exists to stop.
**Progress 2026-09-03 (M3.3, not a fix).** All 37 guard cases were re-authored against DEC-256.
Topic nouns are gone from every `keyword_none` list, the surviving entries are disclosure
predicates, and total dead keywords fell 203 -> 93 (baseline re-recorded downward). Each case also
gained a per-case `commits_judge` criterion, which took the canned hedge from 37/37 to 0/37 and
closed ISSUE-257. **That is the positive half only.** This issue's actual complaint — that the
per-case knowledge boundary ("NPC X must not confabulate NPC Y's knowledge") is enforced
lexically rather than semantically — still stands: the negative half is still a literal phrase
list, and a leak phrased in words nobody guessed still passes.
**To fix:** the issue's original prescription is still right, and DEC-256 sharpens why. Add a
**Theme:** T17
per-case `affirms_judge` criterion restating each case's `description` as a claim about the
withheld fact. `affirms_judge` is the correct instrument *here* precisely because it is
polarity-inverted: confabulation IS an assertion, so it fails exactly what a lexical list misses.
(It is the wrong instrument for the positive half, which is what DEC-256 rejected — the two halves
need opposite polarities, and this issue owns the negative one.) `affirms_judge` is a supported matcher kind (`evals/matchers.py:197`),
already used for the injected lore rubric, and carries real variance (0.941 on the recorded
generation) — so the assertion can actually fail. Do NOT use `refusal_judge`: it has no dispatch
branch in `matchers.py`, no case file uses it, and ISSUE-141 records kappa=0.247 with a CI
crossing zero. Note the replacement inherits ISSUE-129: `affirms_judge` kappa is 0.530
[0.000, 0.853], refused against the 0.60 threshold — a measurable instrument, not yet a trusted
one. Land it after the next regeneration so the before/after is comparable.

## ISSUE-246: the baseline generation records null model digests, so the trend re-decision can never unblock
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Severity:** P2 (annoying)
**Where:** `evals/generations/k3_77688e7_regen1/meta.json`, `evals/trend/trend_v1.jsonl`
**Description:** `meta.json` records `generation_model_digest: null` and
`judge_model_digest: null` — exactly the values R2.1 now makes fatal. Trend row 1 carries no
digest field at all; its model identity is the tag string
`panel:llama3.1:8b+mixtral:8x7b+qwen2.5:14b`. R2.7a's stated deferral condition is
"`wc -l trend_v1.jsonl` >= 2 **and** the two rows share a model digest". Since R2.1 guarantees
row 2 will have a digest and row 1 can never acquire one, that condition is unsatisfiable by
row 1 + row 2, so the trend re-decision would defer forever.
**Why deferred:** it is a restatement of R2.7a's exit condition, which is R2.7's job.
**To fix:** restate the condition as "two rows recorded **after** R2.1 share a model digest" —
**Theme:** T17
i.e. the comparable series restarts at row 2 — or regenerate the baseline. Also sequence R2.6d
(content-addressing) so it does not split the schema mid-series.

## ISSUE-265: a dialogue turn against an unconfigured Ollama model silently serves the fallback
**Found:** 2026-09-03, during the per-engine timing work
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/dialogue/`, metrics labels in `/v1/admin/system/metrics`
**Description:** With `llm_config.yaml` pinning `qwen2.5:7b` and Ollama holding only
`llama3.1:8b`, every dialogue turn returns the fallback ("I need a moment to think.") while
`llm_calls_total` is labelled `backend=qwen2_5_7b` and `llm_tokens_out_total` carries
`fallback=request_error`. The fallback contract works as documented, but the counter reads as
though the pinned model answered - only the `fallback=` label on a *different* counter says
otherwise, and `/v1/admin/system/engines` shows nothing at all.
**Why deferred:** out of scope for this task, which was engine-tick timing; changing metric
labelling is an observability decision of its own.
**To fix:** either label `llm_calls_total` with the fallback outcome too, or surface a
model-availability check at startup that fails loudly when the pinned model is absent.

## ISSUE-269: `check-api-stability` is now a strict subset of `check-api-contract`
**Found:** 2026-09-03, during R5.1
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_api_stability.py`, `scripts/api_stability_baseline.json`, `Makefile`
**Description:** R5.1 added `check-api-contract`, which detects every field drop the older gate
can plus route removal, type changes, required-set widening, status codes and auth. The old gate
covers 17 of the 105 BaseModel classes under `api/`. Keeping both means two baselines to
re-record for one deliberate change, which is the second-copy failure DEC-249 names.
**Why deferred:** deleting a gate is not something to do in passing, and the old one does hold
one thing the new one cannot — it reads source, so it sees a response model renamed before that
model is wired to any route. `make check` therefore carries both, at 23 targets.
**To fix:** decide whether the unrouted-model case is worth a gate. If not, delete the script,
its baseline and its test, and rename the target — `make check` returns to 22.

## ISSUE-292: 5 of 18 serialized context slots are read by no dialogue prompt rule
**Found:** 2026-09-07, during measurement-remediation Phase 4 (DEC-271, probe_dialogue.py)
**Severity:** P2 (annoying — budget and ranking are spent on data the model is never told to read)
**Where:** `src/npc_engine/retrieval/context/context_slots.py` (`CONTEXT_SLOTS`,
`default_enabled=True` rows) vs `src/npc_engine/prompts/dialogue/system_v1.yaml`
**Description:** `serialized_slots()` returns exactly 18 `default_enabled=True` slot keys.
Cross-referencing every one against `system_v1.yaml`'s numbered rules (verified by grep,
2026-09-07), 13 are read by a rule; 5 are not: `nearby_npcs`, `player_memories`,
`active_quest`, `beliefs`, `top_need`. Each is assembled, ranked, and charged to the tier-A
or tier-B budget on every turn, and then the prompt never once instructs the model to read
it — distinct from ISSUE-200 (fixed): that issue was slots with no serialization key at
all; this is the reverse — slots WITH a key that the prompt simply never names. Also
distinct from ISSUE-210 (`top_need` is structurally empty because no `Need` node seeder
exists) — that is a data-emptiness problem; this issue holds even for a slot that IS
populated (`nearby_npcs`, `beliefs`), because the gap is in the prompt, not the data.
**Why deferred:** found while building probe_dialogue.py's per-slot inclusion-rate metric
(measurement-remediation Phase 4), which is what surfaced it — not the task fixing it.
Deciding whether each of the 5 gets a prompt rule (spending more prompt budget on
instructions) or gets `default_enabled=False`'d (matching how ISSUE-200's leftover-8 were
resolved) is a prompt-schema decision needing its own change and its own
`prompt_schema_version` bump, per that issue's own precedent.
**To fix:** for each of the 5, either add a numbered rule to `system_v1.yaml` teaching the
model to read it, or flip `default_enabled=False` in `context_slots.py` and let
`_drop_withheld_items` stop assembling it (the ISSUE-200 pattern). `make eval-probe`'s
dialogue probe reports `slot_inclusion:<prefix>` for exactly the slots that DID reach a
turn's `item_keys` — comparing that list against this issue's 5 names is the check.

## ISSUE-295: the calibration population is derived from the labels file, so retired scorers are still calibrated
**Found:** 2026-09-07, during measurement-remediation Phase 5 (DEC-272)
**Severity:** P3 (nice-to-fix — noise in a report, not a wrong number; every affected scorer
is REFUSED anyway, so nothing untrustworthy is published as a result)
**Where:** `evals/calibration.py:817` (`scorers = list(dict.fromkeys(r.scorer for r in all_rows))`);
the same derivation in `scripts/check_label_adequacy.py:69`
**Description:** `run_calibration` derives which scorers to calibrate from the distinct
`scorer` values present in `labels_v1.jsonl`, not from any roster. Retiring a scorer in the
engine therefore does not remove it from calibration, because its historical labels stay in
the file (correctly — they are evidence about a real past run and DEC-130's never-delete rule
applies). So `python -m evals calibrate` today iterates **five** scorers: the three in scope
after DEC-269 (`tone_judge`, `affirms_judge`, `commits_judge`) plus `refusal_judge`, retired
into `affirms_judge` by DEC-269/ISSUE-276, and `anti_hallucination_grounded`, which is not in
`label_export_stratified.IN_SCOPE_SCORERS` and so can never be given fresh labels by the only
export verb that exists. Both print a `[REFUSED]` line on every run and always will. The
measurement-remediation plan's "3 scorers" framing is therefore true of the exporter
(`IN_SCOPE_SCORERS`) but not of the calibrator, which is the surface an operator actually
reads.
**Why deferred:** it is a change to what calibration reports, and the honest fix is a decision
about where the scorer roster lives, not a filter bolted onto one function. Phase 5's scope was
the labelling push's tooling; changing the calibrated population mid-push would also change the
family-size used for the Holm disclosure (`calibration.py:818-822`), which is a live number in
every published report.
**To fix:** decide whether the roster is declared (a constant, like
**Theme:** T17
`label_export_stratified.IN_SCOPE_SCORERS` or `battery_trust.BATTERY_JUDGED_SCORERS` — note
those two already disagree with each other on `anti_hallucination_grounded`) or derived with a
retirement list, then have `run_calibration` take the population as a parameter rather than
deriving it inline. Whichever is chosen, make the Holm `family_size` follow the same
population, and add a test that a retired scorer's historical labels stay readable while
dropping out of the report.

## ISSUE-297: two divergent `.env.example` files, neither gated, both drifted from the shipped defaults
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P3 (nice-to-fix — misleads a fresh checkout, but `config.py` defaults are what
actually ship, so no running system is wrong because of it)
**Where:** `./.env.example` (75 lines) and `./src/npc_engine/.env.example` (81 lines)
**Description:** Two example files carry the same key set but different values and comments, and
no test or gate compares either against `config.py` (`grep "env.example"` over all `*.py` returns
nothing). Both have drifted: the root file says `OLLAMA_CONTEXT_LENGTH=8192` and the nested one
says `4096`, where the shipped default is `12288`; the root file's comment still claims "At 8192
the budget derives to 1312", a figure `config.py:171-179` records as wrong from P8 onward. Both
also omit many shipped settings entirely (`OPENAI_API_URL`, `STRUCTURED_OUTPUT_TEMPERATURE`,
`RETRIEVAL_PROFILE`, the `TTS_*` block). DEC-273 added `OLLAMA_KEEP_ALIVE=30m` to both rather
than pick a winner.
**Why deferred:** Reconciling them means deciding which is authoritative and whether the nested
copy should exist at all — a packaging question, not a latency one.
**To fix:** Decide whether `src/npc_engine/.env.example` should exist (the app is configured from
the repo root via `docker-compose.yml`'s `env_file: .env`); delete it if not. Then add a
`check-env-example` gate asserting every non-secret `Settings` field appears in the surviving
file with a value matching its shipped default, and wire it into `make check`.

## ISSUE-349: demo docs have drifted — `DEMO_SCRIPT.md` says Act 5 is final; freeze.yml names a wrong route
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P3 (nice-to-fix)
**Where:** `docs/DEMO_SCRIPT.md` (Act Structure, API-calls table); `docker-compose.freeze.yml:22`
**Description:** `DEMO_SCRIPT.md` describes five acts ending in Act 5; `demo_game/runners/run.py` SCENES runs 12
acts plus `outro`, and `demo-run-live` treats `outro` as the final act. The ACT 7 gossip-boundary tick, the ACT 8
admin route and the seed change are not reflected either. Separately, the freeze.yml comment says request-driven
ticks go through `POST /v1/admin/clock/advance`; the route is `POST /v1/clock/advance`.
**Why deferred:** documentation only; T2.4 does not own the demo narrative, and changing a compose file needs the
owner's approval.
**To fix:** regenerate the act table and API-call list in `DEMO_SCRIPT.md` from `run.py` SCENES; fix the route in
the freeze.yml comment.

## ISSUE-352: the frozen eval world baseline still seeds `garrick_safe_passage` at severity 70
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/fixtures/eval_world_baseline.json` (`garrick_safe_passage`)
**Description:** T2.4 lowered the demo seed's `garrick_safe_passage` to severity 60 so story pacing does not stay
suppressed and block ACT 5 (`tests/unit/seeds/test_seed_does_not_suppress_story_pacing.py`). The eval baseline is
a snapshot taken from the old seed and still holds 70, so an eval world restored from it stays pacing-suppressed.
**Why deferred:** the baseline is a frozen corpus; editing it by hand breaks comparability with earlier eval runs.
**To fix:** at the next deliberate corpus refreeze, regenerate with `make eval-world-snapshot` from the current
**Theme:** T17
seed, and note the pacing change in that run's comparability record.

## ISSUE-365: no per-module coverage floor for `evals/` — aggregate can hide a zero
**Found:** 2026-09-21, during T12.2
**Severity:** P2 (annoying)
**Where:** `Makefile:test-cov-evals`, `scripts/` (no per-module coverage gate exists)
**Description:** `make test-cov-evals` enforces a single aggregate floor (75%) over all of
`evals/`. A module at 0% is invisible as long as well-tested modules keep the aggregate above
the floor. T12.2 found `evals/arm_probe.py` and `evals/arm_probe_report.py` both at 0% while
the aggregate was 82.79% — the floor was passing. T12.2 wrote tests bringing both to near-100%,
but the structural gap remains: the next new eval module ships at 0% and nothing catches it.
**Why deferred:** The harness has no per-module coverage mechanism and building one is out of
scope for T12.2 (spec: "if the harness has no per-module mechanism, log an issue rather than
building one here").
**To fix:** Add a per-module floor check to `make test-cov-evals` (or a sibling target). One
**Theme:** T17
approach: use `coverage report --include="evals/arm_probe*.py" --fail-under=NNN` for the
P9 measurement modules specifically, or write a script that fails if any single `evals/*.py`
module drops below a per-file threshold (e.g., 50%). Register the gate in `scripts/loop_gates.py`.

## ISSUE-369: `arm_probe._finish([])` reports PASS when no gate ran
**Found:** 2026-09-21, during post-loop review of T12.2
**Severity:** P3 (nice-to-fix)
**Where:** `evals/arm_probe.py` `_finish`; locked in by `tests/unit/evals/test_arm_probe_run.py::test_finish_with_empty_results_returns_0`
**Description:** Zero gate results exit 0 with "PASS". For the measurement-integrity tool, a run
that measured nothing should not read as a pass. That is the vacuous green rule 5 exists to stop.
**Why deferred:** It is unclear whether any caller legitimately reaches `_finish` with an empty
list. That is the owner's call, not a review fix.
**To fix:** If no caller does, make `_finish([])` exit 1 and flip the test.
**Theme:** T17

## ISSUE-377: `docs/ENGINES.md` capability catalog still lists engines deleted in T4.1
**Found:** 2026-10-20, during T15.2
**Severity:** P3 (nice-to-fix)
**Where:** `docs/ENGINES.md` — "Mood contagion" (l.122), "Clique formation" (l.131), "Deception" (l.138), "Currency" (l.153), "Skills & XP" (l.154) rows in the capability catalog
**Description:** T4.1 deleted five engine directories (`mood_contagion`, `clique`, `skill`, `deception`, `currency`) but did not update the per-engine rows in `docs/ENGINES.md`. The ROADMAP spec for T15.2 states that T4.1 already updated those rows — it did not, leaving five stale entries describing engines that no longer exist.
**Why deferred:** T15.2 owns the tick-order and dependency sections only; the description rows belong to the deleting task. Changing them here would mix responsibilities.
**To fix:** Remove or annotate the five stale rows from `docs/ENGINES.md`, confirming each against the current `src/npc_engine/engines/` directory.

## ISSUE-378: `demo_game/` mypy error count at 256; `.mypy_baseline_demo` ratchet not yet retired
**Found:** 2026-10-21, during T22.4
**Severity:** P3 (nice-to-fix)
**Where:** `.mypy_baseline_demo` (256 errors across `demo_game/`); `make type-demo` ratchet
**Description:** `make type-demo` ratchets demo_game mypy errors against `.mypy_baseline_demo` (baseline 256). The ratchet prevents growth but does not require shrinkage. Reaching zero would retire the baseline file and bring `demo_game/` under the same hard `type` gate as `src/`.
**Why deferred:** Blocked on T13.2 (census pass may delete modules whose type errors would vanish) and the `game_window.py` split. Fixing types in modules T13.2 will cut is wasted work.
**To fix:** After T13.2 completes, run `make type-demo-update` to record the post-deletion baseline, then fix errors file by file. Remove `.mypy_baseline_demo` and the `type-demo` target when the count reaches zero.

## ISSUE-379: REMEMBER pillar RED — relation `interaction_count` stays at 0; memory consolidation never fires
**Found:** 2026-10-22, during T24.4
**Severity:** P2 (annoying)
**Where:** `demo_game/runners/pillars.py` REMEMBER pillar; `src/npc_engine/graph/` relation writer; `src/npc_engine/engines/memory/`
**Description:** First committed `evals/pillar_verdicts.jsonl` (sha=04782e03) shows REMEMBER RED: `delta: 0/2 relation reads have interaction_count>0; memory: memory_id=None`. Two dialogue beats with Mira produce no `interaction_count` increment on any outgoing relation edge, and consolidation reports "Turn threshold not met (need more dialogue turns)" — the threshold is never crossed because the dialogue engine does not increment the relation counter per turn.
**Why deferred:** T24.4 records the red baseline only; fixes are sequenced in Sprint 15.
**To fix:** Find the relation-delta writer and confirm it increments `interaction_count` on each dialogue turn. Confirm the memory consolidation threshold matches the number of turns the demo runs. Add a targeted integration test asserting `interaction_count > 0` after one dialogue exchange.

## ISSUE-380: DETERMINISM pillar RED — `seeds_used` is empty in both gossip-tick runs
**Found:** 2026-10-22, during T24.4
**Severity:** P2 (annoying)
**Where:** `demo_game/runners/pillars.py` DETERMINISM pillar; `POST /v1/admin/batch/gossip_tick` response schema
**Description:** First committed `evals/pillar_verdicts.jsonl` (sha=04782e03) shows DETERMINISM RED: `seeds_used is empty: run1={} run2={}`. The batch gossip-tick endpoint returns no `seeds_used` field (or an empty dict) in both calls with `tick_override=42`, so the pillar cannot compare seeds and the determinism proof is vacuous — matching T24.3's fix of the `{} == {}` vacuous check.
**Why deferred:** T24.4 records the red baseline only; fixes are sequenced in Sprint 15.
**To fix:** Confirm `POST /v1/admin/batch/gossip_tick` populates `seeds_used` in its response. If the field is absent, add it to the response model and the batch handler. Add a targeted unit test asserting `seeds_used` is non-empty for a non-empty gossip graph.

## ISSUE-381: "Home" is one fixed location; design safe places and destination choice
**Found:** 2026-11-16, during T25.7
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/routine/routine_engine.py` (`HOME_LOCATION`, `_override_destination`); `engines/dialogue/dialogue_handler.py` (low-valence override); `engines/events/disruption_rules.yaml`; `type_registry/base_nodes/character.yaml` (`home_location_id`)
**Description:** T25.7 gave every Character one `home_location_id`, seeded to its start location, and made an override to `"home"` resolve through it. That fixes NPCs vanishing, but the model is thin:
- an NPC upset while already at home has nowhere to withdraw to, so it stays put;
- an innkeeper's "home" is her workplace (the tavern), so withdrawing changes nothing;
- the destination is fixed per NPC, whatever the cause (grief after a death, fear after a fire, sulking after an insult).
Owner ideas (2026-11-16):
- rename "home" to **safe places**, and allow several per NPC;
- a low-valence event at a safe place still makes the NPC leave, for another safe place;
- the event, or the planner/mover (`engines/planning/`), computes where the character goes, instead of a fixed sentinel.
**Why deferred:** the owner chose the seeded-start-location home for now; the richer model is a design task (graph schema, seed content, planner interplay).
**To fix:** write a design note covering:
- the safe-place data model (an edge such as `(:Character)-[:SAFE_PLACE {rank}]->(:Location)`, or a list property);
- who picks the destination (disruption rule, emotion, or the planner's goal former);
- how it interacts with need-driven moves and schedules.
Then replace the `HOME_LOCATION` sentinel with that choice. The WORLD pillar must keep passing (T25.9).

## ISSUE-382: Pillar eval has no real N-of-M for LLM-dependent pillars
**Found:** 2026-11-16, during T25.9
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/runners/pillars.py` (`main`, `judge_pillars`); DEC-321, DEC-331
**Description:** DEC-321 asked for 2-of-3 on FEEL, REMEMBER-delta and GOSSIP. The implementation re-read one static graph value three times after a single demo run, so its threshold never sampled LLM variance. T25.9 dropped the fake re-reads (`repeats: 1`). A single run's verdict on an LLM-dependent pillar can still flip on sampling.
**Why deferred:** one demo run takes about 10 minutes on the eval stack. N runs per phase gate is a budget decision.
**To fix:** add `--runs N` to `pillars.py`: reset and seed the stack between runs, judge each run, and report a pillar green when at least the threshold of runs pass. Decide N for the loop's phase gate against its time budget.

## ISSUE-383: Gossip distortion level and summary can disagree on an edge
**Found:** 2026-11-16, during the T25.2–T25.5 audit
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/gossip/gossip_distort.py` :213-247; `graph/gossip/gossip_batch_queries.py` (`CYPHER_BATCH_PROPAGATE_KNOWLEDGE`)
**Description:**
- When the distortion gate misses, or the event is canonical, the stored level drops to 0, although the summary passed on is the sharer's already-distorted text.
- The `SET` of the distortion fields runs on every re-tell, so a later sharer overwrites the level and summary, while `source_character_id` keeps the first sharer (`ON CREATE`).
**Update 2026-11-16:** T25.13 fixed the first bullet: a gate miss or a canonical event now carries the sharer's level forward. The second bullet is still open.
**Why deferred:** T25.12 made re-telling rarer (unknown events first). Whether a re-tell should overwrite the receiver's version is a design call.
**To fix:** either set source, level and summary together on every write, or only `ON CREATE`, and add an integration test for a re-tell.

## ISSUE-384: Relation-delta clamp lets non-finite and string values escape
**Found:** 2026-11-16, during the T25.2–T25.5 audit
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/dialogue/dialogue_models.py` (`RelationDeltas._clamp_deltas`)
**Description:**
- `float('inf')` makes `int(raw)` raise `OverflowError`, which escapes Pydantic.
- `"20"` is not clamped and fails validation.
- `True` is clamped as 1.
The constrained grammar (DEC-330) makes these unlikely from Ollama, but other backends parse through the same model.
**Why deferred:** no live occurrence; low risk under the constrained grammar.
**To fix:** clamp only finite `int` or `float` values (`math.isfinite`, excluding `bool`); coerce numeric strings first. Add parametrized tests.

## ISSUE-385: World-state PATCH route orchestrates domain logic and opens a session itself
**Found:** 2026-11-16, during the T25.2–T25.5 audit
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/routes/admin/graph.py` (`patch_world_state`, `_apply_world_event_shocks`)
**Description:** The route resolves events, finds witnesses through `graph.event.event_queries.get_characters_at_location` with a route-opened `AsyncSession`, and applies shocks. Layer ranks allow it, but this is engine orchestration in `api/`, and the session should not reach a route (CLAUDE.md: engines call services or retrieval).
**Why deferred:** T25.8 fixed the behaviour (only new events, no 500 after the write); moving the code is a refactor.
**To fix:** move the shock orchestration into an engine method, for example `EmotionUpdater.shock_witnesses(event_ids, tick)`, behind the existing repository. The route calls one method.

## ISSUE-386: A failing beat aborts the rest of the scripted demo
**Found:** 2026-11-16, during T25.6's live run
**Severity:** P2 (annoying)
**Where:** `demo_game/beats/determinism_beat.py` (raises `AssertionError`); `demo_game/runners/run.py` (`DemoRunner.run`)
**Description:** The determinism beat raised `AssertionError: seeds_used is empty`, which ended `DemoRunner.run()`, so no act after it ran. Every pillar that depends on a later act loses its evidence, and the verdict file does not say so. T25.12 fixes this instance; any future beat assertion does the same. Related: when `pillars._run_demo_with_recorder` times out (`DEMO_TIMEOUT_S`), its daemon thread keeps driving the stack while the after-reads run.
**Why deferred:** T25.12 removed the trigger; changing the runner's failure model is separate.
**To fix:** beats report a failure (log it and mark the act red) instead of raising. `DemoRunner.run` continues and returns a list of failed beats, and `pillars.py` puts it in the report. Add a test that a raising beat does not stop later scenes.

## ISSUE-387: `npc_engine.retrieval.context` cannot be imported on its own (circular import)
**Found:** 2026-11-16, during T25.11
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/retrieval/context/__init__.py` → `context_builder` → `context_cache_state` → `retrieval/dialogue_context/__init__.py` → `dialogue_context_adapter` → `context_builder`
**Description:** `python -c "import npc_engine.retrieval.context"`, and so `import npc_engine.engines.dialogue.dialogue_models`, raises `ImportError: cannot import name 'build_serialized_context_with_receipt' from partially initialized module`. The app works only because `npc_engine.main` happens to import modules in a working order. Any new entry point or test that imports these first fails.
**Why deferred:** found while diagnosing T25.11. Fixing it means moving an import or splitting a module.
**To fix:** break the cycle. Make `dialogue_context_adapter` import `context_builder` lazily inside the function, or move `build_serialized_context_with_receipt` below `context_cache_state`. Add a test that imports each `npc_engine` package in a fresh interpreter (`importlib` in a subprocess).

## ISSUE-388: An overnight loop loses its night to a short network outage, then false-flags a leak
**Found:** 2026-11-16, reviewing the 2026-10-22 night
**Severity:** P2 (annoying)
**Where:** `scripts/expand_loop.sh` (ISSUE-370 retry, `worktree_guard.py` check)
**Description:**
- On 2026-10-22, T25.6's session ended with a bare `Execution error` when the connection dropped. The loop retried once after 60 s, the network was still down, and the night ended.
- The operator's Ctrl+C then crashed `worktree_guard.py` at import (`KeyboardInterrupt`). Its non-zero exit was read as "task changed another worktree", a false flag in the report.
**Why deferred:** the driver is outside the drain fence (T21.4 frozen paths); changing it is owner work.
**To fix:**
- retry a bare `Execution error` with backoff (for example 1, 5 and 15 minutes) before halting;
- treat a guard that crashed (exit code above 1, or a traceback) as "guard failed", not as a leak, and say so in the report.

## ISSUE-389: `scripts/rules_baseline.txt` lists a deleted function
**Found:** 2026-11-16, during the T25.2–T25.5 audit
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/rules_baseline.txt` :27 (`relation_mutator.py::apply_dialogue_relation_deltas`)
**Description:** The waiver names a function that no longer exists, so the baseline has a dead entry. It cannot hide a new violation, but it misstates the waiver list.
**Why deferred:** cosmetic.
**To fix:** delete the line. Consider having `check_rules.py` fail on baseline entries that match nothing.
