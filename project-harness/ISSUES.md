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

## ISSUE-342: 494 untracked log files sit in `project-harness/` with no retention policy
**Found:** 2026-09-09, during the pre-T tidy of `project-harness/`
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/.loop-logs/` (465 files), `overnight_logs/` (27), `logs/` (1)
**Description:** Four directories of machine-local run output accumulate at the top level of
`project-harness/`. All are gitignored (`.gitignore:2`, `:89`, and the global `*.log`) and zero of
their files are tracked, so they are invisible in a fresh clone but dominate the folder on disk and
in every `ls`. Nothing prunes them: `.loop-logs/` has grown to 465 files across every loop run since
the harness was written, and each gate log is paired with a `.class` sidecar.
**Why deferred:** Deleting run output is not an archiving task, and `overnight_logs/` is an active
write target for `scripts/` — a retention rule needs to be agreed, not improvised, and belongs with
the loop work the T programme already schedules against `OVERNIGHT_LOOP.md`.
**To fix:** Decide a retention window (last N runs, or age-based), implement the prune in the loop's
own teardown so it runs where the writes happen, and record the window in `OVERNIGHT_LOOP.md`.
Consider relocating all four under one gitignored `project-harness/.run-artifacts/` so the top level
shows one entry instead of four.

## ISSUE-341: four comments cite `project-harness/Run-OvernightCombined.ps1` and `scripts/run_eval_k3.ps1`, neither of which exists
**Found:** 2026-09-09, during the pre-T tidy of `project-harness/`
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile:863`; `scripts/Run-EvalHarness.ps1:8`, `:143`, `:202`, `:205`
**Description:** Five comments explain current behaviour by pointing at two scripts that are not in
the tree. `Makefile:863` justifies stopping the app during a restore by saying it matches "what
`project-harness/Run-OvernightCombined.ps1` already does"; `Run-EvalHarness.ps1` says it supersedes
`project-harness/scripts/run_eval_k3.ps1` and three times defers to `Run-OvernightCombined.ps1` for
how the API key travels and how dirtiness is handled. `project-harness/Run-OvernightCombined.ps1`
and `project-harness/scripts/` do not exist, and `project-harness/scripts/run_eval_k3.ps1` was
self-declared TEMPORARY. A reader following any of these to check the claim finds nothing, and the
rationale for the app-stop in the restore path is left resting on a file that cannot be read.
**Why deferred:** Found during a tidy scoped to `project-harness/`; fixing it edits `Makefile` and
`scripts/`, both outside that scope, and the DEC-200 key-handling rationale in `Run-EvalHarness.ps1`
needs to be restated from what is actually true today rather than re-pointed.
**To fix:** Establish whether `Run-OvernightCombined.ps1` was deleted or renamed (check the history
of `scripts/Run-EvalHarness.ps1`). Then either restore the reference to the surviving script or
inline the behaviour each comment is deferring to — the app-stop rationale at `Makefile:863` and the
`$env:API_KEY_SECRET` convention at `Run-EvalHarness.ps1:143` should stand on their own.

## ISSUE-340: `RunStatus.provenance` is declared and never written, so a re-derived status is indistinguishable from a live one
**Found:** 2026-09-08, during the A/B-readiness analysis (DEC-281)
**Severity:** P2 (annoying — it does not corrupt a number, but it removes the one field that would
let a reader tell how a number was produced)
**Where:** `evals/run_status.py:114` (declaration), `evals/judge_run_artifacts.py:137-148`
(`build_status`), `:97-107` (`with_panel_metrics`), `:164` (`record_error`)
**Description:** `RunStatus.provenance: str = ""` is documented as "How this status was produced when
it was not a live pass (e.g. re-derived from a legacy artifact). Empty for a normal run."
(`run_status.py:88-90`). **No code anywhere sets it** — not `build_status`, not
`with_panel_metrics`'s `model_copy` update dict, not `record_error`. A repo-wide grep finds only the
declaration. It is dead config, which the T programme's rules 3 and 6 forbid.

The one artifact in the tree that needed it proves the gap.
`evals/generations/k3_61b01dad_negadv/run_status.json` carries `provenance: ""` while its sibling
`RECOVERED_NOTE.md` states the file "was reconstructed from `judged_panel_votes.jsonl` +
`outputs.jsonl` without re-running the panel" (DEC-265, after the ISSUE-288 `write_report` crash).
Its `report_path` is that hand-written note rather than a rendered report.
`trend_row_builder._panel_fields` consumes its kappas exactly as it would a live pass's.

**Scope note, so this is not overstated:** the panel judging for that run *did* complete normally —
`judged.jsonl` and `judged_panel_votes.jsonl` were written correctly and the recovered kappa
(0.8314) is computed from genuine votes. Only the status file was re-derived. So no recorded number
is wrong; what is missing is the ability to *know* that from the artifact alone.

**Why this matters now:** ROADMAP Sprint 9's premise cites "panel kappa swung 0.58 to 0.83 between
runs". Those two values are `k3_77688e7_regen1` (0.5807) and `k3_61b01dad_negadv` (0.8314) — runs
with **different case populations**: capability n=16 / guard n=78 versus capability n=0 /
guard_adversarial n=111. T17.1 ("diagnose why each scorer is refused") should treat that swing as a
population difference first and instrument instability second, and `provenance` is one of the fields
that would have made the distinction legible without this archaeology.

**Why deferred:** DEC-281's scope is comparability and attributability of the *code state*; this is a
third provenance gap found in the same audit and is not on the critical path to a first A/B run.
**To fix:** either populate it — `build_status` takes it as a parameter, `record_error` sets a
literal, and the recovery path in DEC-265 sets it explicitly — **or** delete the field and rely on a
sibling note file, per rule 2. Deleting is cheaper and legitimate; if it is kept it must acquire a
writer, because a field nobody writes is worse than no field. Whichever is chosen, backfill
`k3_61b01dad_negadv`'s value or record in DEC-265 that it stays blank deliberately.

## ISSUE-336: `probe_events` creates zero Events — `location_id: None` 422s every POST
**Found:** 2026-09-08, during the A/B-readiness analysis
**Severity:** P2 (annoying — the probe path is not on any gate and is not currently run)
**Where:** `evals/probe_events.py:79-82`, against `src/npc_engine/type_registry/base_nodes/event.yaml`
**Description:** `drive()` posts an Event with `"location_id": None`. `location_id` is
`required: true`, and `type_registry/validation.py:184-190` raises `BASE_FIELD_NULL_FORBIDDEN` for an
explicit `None` on a required base field, which `route_helpers.py:157-159` maps to **HTTP 422**. The
return code is never checked, so every Event silently fails to exist. Downstream: each `KNOWS_ABOUT`
POST 404s on the missing node, `_has_knower` is False for all, `orphan_rate` reads 1.0, and the
`known_events_have_an_edge` invariant fails every repetition. Meanwhile `events_created_per_tick`
(hardcoded 1.0) and `severity_mean` (computed from the probe's own local `_SEVERITIES` list, never
read back from the server) stay green — so the probe reports success metrics for events that do not
exist. Unit tests pass because they assert against hand-authored `MagicMock` responses.
**Why deferred:** the A/B measurement unit is the case battery, not the probes (plan of 2026-09-08);
the probe path is excluded from that work rather than repaired inside it.
**To fix:** omit `location_id` or point it at a real Location; check `is_ok()` on every POST; derive
`severity_mean` from the server rather than from local state.

## ISSUE-337: `probe_gossip` cannot observe propagation, and reads a key that does not exist
**Found:** 2026-09-08, during the A/B-readiness analysis
**Severity:** P2 (annoying — but it makes the module's stated purpose, ISSUE-228 instrumentation, a no-op)
**Where:** `evals/probe_gossip.py:56-81` and `:112`, against
`src/npc_engine/graph/gossip/gossip_queries.py:62-67` and
`src/npc_engine/graph/gossip/rumor_trace_service.py:21-28`
**Description:** Two independent defects. (a) Gossip pair selection matches
`(a:Character)-[:LOCATED_AT]->(loc:Location)<-[:LOCATED_AT]-(b:Character)`. `_seed_event_and_origin`
creates a Location node and a Character but **never writes a `LOCATED_AT` edge** — `location_id` is set
as a *property on the Event*, not an edge on the Character — so the origin NPC can never be selected as
a sharer and the event can never propagate. `propagation_reach` is pinned at 1.0, and the
`knowers_have_a_source` invariant filters out the origin's own edge and so passes on an empty set.
The Location POST also 422s (same root cause as ISSUE-336: `description` is not a declared field, and
`location_tag`/`descriptor` are required and absent). (b) `_distortion_deltas` reads
`row.get("distortion_level")`, but `CYPHER_TRACE_RUMOR_CHAIN` returns exactly `npc_id`, `npc_name`,
`knowledge_state`, `learned_at_tick`, `distorted_summary` — there is no `distortion_level`. So
`distortion_delta_per_hop_mean` is never emitted. `tests/unit/evals/test_probe_gossip.py:59-62`
hand-authors that key into a mock, which is why the test passes.
**Why deferred:** as ISSUE-336.
**To fix:** write a `LOCATED_AT` edge from the origin to a seeded Location that other NPCs occupy (the
seed provides `loc_tavern` with 5 co-located NPCs); fix the Location POST fields; and either surface
`distortion_level` from the trace query or compute the delta from `distorted_summary`.

## ISSUE-338: `scenario_mood_contagion` passes vacuously — the two NPCs are never co-located
**Found:** 2026-09-08, during the A/B-readiness analysis
**Severity:** P2 (annoying — a promoted scenario that cannot fail)
**Where:** `evals/scenario_adapters_extra.py:187-211`
**Description:** The scenario posts a Location with `{id, name, description, last_graph_updated_at}`.
`description` is not a declared field on `location.yaml` and `location_tag`/`descriptor` are required
and missing, so the POST 422s; the return is unchecked. Both subsequent `LOCATED_AT` POSTs then 404 on
the missing destination node, so the two NPCs are never co-located and mood contagion never runs on
them. The assertion is only that both `current_mood` values are non-`None` — which is true from
creation, since `_char(...)` sets `current_mood`. The scenario therefore passes without exercising the
behaviour it names. The `RELATES_TO` POST at `:197-202` also omits `last_updated_at`, which is
`required: true`, so it 422s as well.
**Why deferred:** as ISSUE-336.
**To fix:** correct the Location and `RELATES_TO` property sets, check every POST return, and assert a
mood *change* rather than mood presence.

## ISSUE-339: 10 of 11 probes request engine status under a name the scheduler never registers
**Found:** 2026-09-08, during the A/B-readiness analysis
**Severity:** P3 (nice-to-fix — the effect is a missing metric floor, not a wrong number)
**Where:** `evals/probe_runner.py:204`, against `src/npc_engine/scheduler/tick_scheduler.py:346-369,452-545`
**Description:** `_merge_status_metrics` looks up `read_engine_status(client).get(probe.engine_name)`
and no-ops silently on `None`. The scheduler registers `story_pacing`, `gossip`, `event`, `routine`,
`chapter`, `memory_consolidation` plus the 22 from `_ordered_tick_engines()`. Only `probe_gossip`
(`"gossip"`) matches. `probe_events` declares `"events"` (scheduler key is singular `"event"`);
`probe_memory` declares `"memory"` (keys are `memory_consolidation`/`memory_decay`); `probe_quest`
declares `"quest"` (keys are `event_quest`/`need_quest`/`world_state_quest`); `probe_dialogue` declares
`"dialogue"`, which is request-driven and never tick-registered; and all six legacy adapters are
constructed with their *scenario id* as `engine_name`. So 10 of 11 probes silently get no
`tick_count`/`error_count`/`duration_ms`. Related: `probe_runner.py:10-11` and
`probe_protocol.py:44-46` both claim coverage of "all 46 engines" and cite `"quest_generation"` as a
key; neither is accurate.
**Why deferred:** as ISSUE-336.
**To fix:** map each probe to a real registered key (or several), correct the two docstrings, and log a
warning when a declared `engine_name` matches nothing rather than returning silently.

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
`collect_ah_case_records`, returning `[]` and logging a skip exactly as the YAML path now
does.

## ISSUE-282: run_calibration's family_size still counts every >=2-adjudicated scorer, not every adequacy-passing one
**Found:** 2026-09-04, during the M1.4 label-adequacy fix
**Severity:** P3 (nice-to-fix)
**Where:** `evals/calibration.py::run_calibration` (`eligible`/`family_size`, immediately above
the per-scorer loop that now calls `label_adequacy.check_label_adequacy`)
**Description:** `run_calibration` computes `family_size` (for the Holm-Bonferroni disclosure)
from `eligible` — scorers with >=2 adjudicated rows — before the per-scorer loop, which now
separately refuses any scorer `check_label_adequacy` rejects. On the committed corpus all four
scorers pass the old `>=2` filter and enter `family_size`, then all four are refused by
adequacy inside the loop, so the Holm disclosure is computed for a family of scorers none of
which end up reported. This is conservative, not wrong — `family_size` only ever ends up equal
to or larger than the count of scorers that actually publish, so the resulting Holm-adjusted
bounds are wider than strictly necessary, never narrower — but the two numbers (`family_size`
and "scorers actually reported") can now diverge, which a future reader could misread as a bug
rather than a known conservative choice.
**Why deferred:** Recomputing `family_size` from `check_label_adequacy` instead of the `>=2`
filter collapses it to 0 whenever every scorer is refused (today's corpus), which deletes the
Holm-Bonferroni disclosure text entirely and breaks
`tests/unit/evals/test_calibration.py::test_calibration_report_names_family_size_and_holm_ci`,
which asserts "holm" appears in the output. DEC-260 records this as a deliberate choice for v1,
not an oversight.
**To fix:** Decide what a Holm disclosure should say when 0 scorers publish (a "no publishable
scorer this run" state distinct from "no Holm adjustment needed"), update the test's fixture or
assertion accordingly, then switch `eligible` to use `check_label_adequacy`.

## ISSUE-283: the committed trend row (k3_77688e7_regen1) carries kappas measured on k3_73e6c36's labels
**Found:** 2026-09-04, during the M1.4 kappa-attribution fix
**Severity:** P3 (nice-to-fix)
**Where:** `evals/trend/trend_v1.jsonl` (the one committed row); `evals/trend_row_builder.py`
**Description:** Before this fix, `build_trend_row` computed `scorer_kappas` from whatever
`evals/calibration/labels_v1.jsonl` held at record time, with no check that those labels
named the run being recorded. The one row in the store — `gen_id=k3_77688e7_regen1` — was
built that way: its `scorer_kappas` are measured on `k3_73e6c36`'s 393 labels, not on
anything from `k3_77688e7_regen1`. `build_trend_row` now stamps `labels_gen_id` and refuses
a mismatch unless `allow_foreign_labels=True` is passed, but the store is append-only
(`trend_store.append_trend_row` refuses to overwrite a `gen_id`), so the existing row cannot
be corrected in place — only a new row can be attributed correctly going forward.
**Why deferred:** Rewriting store history is out of scope for a fix that made this exact
kind of silent mis-attribution impossible for every row recorded after it. The row is now
readable as unattributed (`labels_gen_id` would be `None` if reread) rather than falsely
attributed, which is the honest state to leave it in.
**To fix:** Either accept the one historical row as a known gap (it predates the provenance
fields entirely, so it can't even be backfilled without re-deriving which labels a 2026-08
run actually used), or regenerate `k3_77688e7_regen1` and re-record it once fresh, correctly
attributed labels exist for it.

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

## ISSUE-279: faction-standing decay appends unbounded — the corpus grows ~2,500 nodes/hour while the app ticks
**Found:** 2026-09-04, during M1.3 (row 4 wipe/reseed/freeze)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/engines/faction_politics/faction_politics_engine.py:171`; the
`:Event` half in the event tick.
**Description:** Every tick, the decay pass appends one `:FactionStandingEvent` per decaying
faction pair with `cause_rule_id="decay"`, and the event tick appends ~1 `:Event`. Measured
2026-09-04 against a freshly seeded world at the shipped `TICK_INTERVAL_SECONDS=10`: **+6
FactionStandingEvent and +1 Event per tick, exactly linear over 6 samples spanning 10 ticks**
(114 → 126 → 138 → 150 → 162 → 174). That is ~7 nodes/tick ≈ 2,500/hour. There is no retention
policy and nothing prunes them. A corpus frozen at 250 nodes passes the M1.3 `< 1,000` census
anchor for about thirteen minutes of uptime and then does not.

Two mitigating facts, both measured, neither a fix. **All of these nodes are orphaned** — 189
decay rows and 32 generated `battle` events all returned `count(r) = 0` for
`OPTIONAL MATCH (n)-[r]-()`. The RAG scope is relationship-based
(`graph/graph_rag_queries.py:86`), so it structurally cannot see them, which is why the M1.3
quiescence anchor held at exactly 18 ids for `captain_sorn` across 5 ticks while 189 nodes
appeared. So this is corpus noise and a reproducibility problem, not (today) a retrieval
correctness problem.
**Why deferred:** Row 4's scope is wipe/reseed/freeze, and bounding the writer is engine work
in `engines/faction_politics/` that the plan did not schedule. The measurement risk it created
is already closed by `make app-frozen` + `make check-corpus-frozen` (DEC-259), which stop the
writer for the length of a measurement run and gate that it actually stopped.
**To fix:** Either bound the history (retention window, or collapse repeated `decay` rows for
the same pair into one row with a count) or add a cleanup pass. Prefer bounding at the writer
over a sweeper — a sweeper is a second thing that can be forgotten. Note the same question
applies to generated `:Event` nodes, which unlike the decay rows *can* be retrieved once they
attach to a character.

## ISSUE-280: `docker compose up`/`run` without the test override silently un-publishes Neo4j's bolt port
**Found:** 2026-09-04, during M1.3 (row 4)
**Severity:** P2 (annoying)
**Where:** `docker-compose.test.yml`; any `docker compose` invocation that omits it, including
`make eval-world-snapshot` (`Makefile:807`) and `make demo-restore` / `make eval-world-reset`
(`Makefile:830`), which all run `docker compose run` with the base file only.
**Description:** The published bolt port lives only in `docker-compose.test.yml` (opt-in per
DEC-232). Any later `docker compose` command that omits that file recomputes the desired state
from the base file, **recreates the neo4j container without the `ports:` stanza**, and every
integration run then fails to connect until someone re-ups with the override. Observed twice in
one session: `docker compose up -d app` and again `make eval-world-snapshot`, each time taking
`127.0.0.1:7687->7687/tcp` down to a bare `7687/tcp`.

It has a second, more confusing symptom. Recreating neo4j under a running app leaves the app
holding pooled connections to the dead container, so the next few requests return **HTTP 503**
with `GraphUnavailableError(... Failed to read from defunct connection ... OSError('No data'))`
against a database that is up and healthy. It looks like a data or label defect and is not one —
it clears once the pool refreshes.
**Why deferred:** Fixing it means either making the override sticky (a `COMPOSE_FILE` env
default) or teaching the snapshot/restore targets to pass it, and both touch how every developer
and CI invokes compose. Out of scope for a wipe-and-reseed task, and worth deciding deliberately.
**To fix:** Likely set `COMPOSE_FILE=docker-compose.yml:docker-compose.test.yml` in the
developer `.env`, or add the override to the `docker compose run` lines in the snapshot and
restore targets. Do **not** solve it by moving `ports:` into the base file — DEC-232 and the
header of `docker-compose.test.yml` explain why that is a real weakening of the isolation
posture.

## ISSUE-277: the integration suite writes into the live Neo4j — there is no separate test database
**Found:** 2026-09-04, during M1.2 (row 0 baseline)
**Severity:** P2 (annoying)
**Where:** `docker-compose.test.yml`; `tests/integration/*`; `Makefile:182` (`test-integration`)
**Description:** `docker-compose.test.yml` does not stand up a second database. It publishes the
bolt port of the **same** `neo4j` service the application and the eval corpus use, so
`make test-integration` reads and writes the production graph. Proof is in the live data: the
graph holds `TickLease` rows whose `scheduler_id` is `"test-<uuid>"` — e.g.
`test-b84e331c-9333-4510-9b76-6e14029b83ce`, `test-64e15d2c-0fc3-43d7-8206-a79af623929e` —
alongside the 3,498 rows written by `scheduler_id = "main"`. Those `test-` leases are integration
runs, persisted in the same store as the corpus.

The operational consequence is that a frozen eval corpus is **not durable across an integration
run**. Any measurement taken after a corpus freeze is invalid if `make test-integration` ran in
between.
**Why deferred:** Fixing it properly means standing up a second Neo4j service (or a second
database inside the same instance) and pointing the integration suite at it — a compose and
configuration change well outside M1.2, and one that touches the test topology every gate
depends on. Sequencing the runs is sufficient for the current programme.
**To fix:** Add a dedicated `neo4j-test` service to `docker-compose.test.yml` on its own volume,
bound to loopback like the existing override, and have the integration suite read its URI from a
distinct variable. Until then, treat "no `make test-integration` between a corpus freeze and its
generation" as an operating rule (DEC-232).

## ISSUE-278: `test_advance_creates_covert_event_and_step` flakes when the app container is running
**Found:** 2026-09-04, during M1.2 (row 0 baseline)
**Severity:** P3 (nice-to-fix)
**Where:** `tests/integration/test_scheme_advance_tick_integration.py:118`
**Description:** With `npcsystem-app-1` up, a full `make check` failed this test on
`assert row["step_order"] == 1` with `assert 2 == 1`. The test creates a scheme, asserts
`step_count == 0`, runs one `SchemeAdvanceTick.run_tick`, and expects the single resulting step to
be ordered 1. A second step existed. `next_order` is `scheme.step_count + 1`
(`engines/scheming/scheme_advance_tick.py:100`), so a concurrent writer that advanced the same
scheme explains the observed value; the app's live tick scheduler is that writer, and it shares
the database per ISSUE-277.

Run in isolation the test passed **both** with the app up and with the app stopped, so this is a
race, not a deterministic failure. It is in neither `scripts/integration_baseline.txt` nor
`project-harness/.loop-state/gate_baseline.json`, and both baselines were recorded while the app
was down.
**Why deferred:** It is a test-isolation defect that only manifests under a service topology the
Makefile does not prescribe — `Makefile:179` documents the integration prerequisite as
`docker compose ... up -d neo4j`, neo4j only. Not on M1.2's path.
**To fix:** Either scope `_read_step_event` to the step this run created rather than
`.single()` over all `SCHEME_STEP` edges, or resolve ISSUE-277 so the suite cannot share a graph
with a live scheduler. Note the test's own `.single()` silently returns the first of several
records, which is what let a second step masquerade as the first.

## ISSUE-275: trend rows attribute the label file's kappa to whatever generation is being recorded
**Found:** 2026-09-03, during M3 pre-flight verification
**Severity:** P1 (blocking) — every published kappa is attributed to a generation that did not produce it
**Where:** `evals/trend_row_builder.py:125-127` (`_scorer_kappas`), called at `:200`; CLI at `scripts/record_trend_and_gate.py:154`
**Description:**
`_scorer_kappas(labels_path)` reads the whole of `evals/calibration/labels_v1.jsonl` and runs
`run_calibration` over every row. There is no `gen_id` filter — `grep gen_id evals/calibration.py`
returns nothing — and no join of any kind between a label and the generation being recorded. The
row is then stamped with the CLI's `--gen-id`. The kappa block is therefore a property of the
label file, not of the run: any gen_id recorded today yields byte-identical kappas.

Observed in the shipped store. `evals/trend/trend_v1.jsonl` holds one row, `gen_id=k3_77688e7_regen1`.
All 393 rows of `labels_v1.jsonl` carry `gen_id=k3_73e6c36`. The row's n-values (tone 135,
affirms 135, anti_hallucination_grounded 48, refusal 75) are the raw label counts exactly.

That the n's are *exact* is the decisive evidence. Only 66.4% of labels survive against the
current case set, and `refusal_judge` and `anti_hallucination_grounded` have zero surviving rows
— so a legitimate join would have cut every one of these numbers. It did not, because no join
happens. Two attributed figures are consequently meaningless: `anti_hallucination_grounded`
kappa=1.0 CI [1.0, 1.0] against cases that no longer exist, and `refusal_judge` kappa=0.247 for a
scorer that scored nothing in that run (and which M3.2 retires).

This is **not** a `--merge` carry-forward. `--merge` exists only in `label_import` /
`label_merge.py`, operates on `labels_v1.jsonl`, and does not rewrite `gen_id`. There is no
carry-forward mechanism in the trend path and no provenance field on `TrendRow` to record one.
`evals/trend_store.py:123` documents the false claim in the type itself: *"Every calibrated
scorer's kappa for this run."*

**Why deferred:** M3 is case authoring; this is trend/calibration plumbing, and the fix changes
what every historical row means. It belongs with M4.3's re-baseline, where the trend is rewritten
anyway. Logged rather than fixed so the current row is not quoted in the meantime.
**To fix:** Either filter labels to the row's `gen_id` before calibrating, or — better, since
labels legitimately outlive one generation — add an explicit `labels_gen_id` (and label-count)
provenance field to `TrendRow`, populate it from the label file, and refuse to record a row whose
labels match no case in the generation. Correct the `scorer_kappas` docstring at
`trend_store.py:123` either way. Re-record the single existing row under M4.3.

## ISSUE-274: `test_quest_lifecycle_offer_to_completion_and_rewards` has been red and invisible — `make check` skips it without services
**Found:** 2026-09-03, during the first watched bring-up of the M programme loop
**Severity:** P2 (annoying) — it sits in the loop's failing-test baseline, so every night of the M
programme will commit against a red gate and flag a human for it, every task, until it is fixed
**Where:** `tests/integration/test_quest_lifecycle_integration_v14.py::test_quest_lifecycle_offer_to_completion_and_rewards`
**Description:** The test fails in 0.35 s with
`ValueError: QuestLifecycleEngine requires a TypeRegistry injected via __init__` — it never reaches
the database. This is a test-side construction defect: the engine grew a required `TypeRegistry`
constructor dependency and this call site was not updated.

It is invisible to the normal gate. `make check` without services **collects and skips** the
integration suite (36 skipped, exit 0, measured 2026-09-03), so the suite reads green while this
test is red. It only surfaced because the loop was launched with `--with-services`, which is the
same "degraded, not red" hazard that makes `--with-services` mandatory for M1.3.

Distinguish it from the other two entries in the same baseline —
`test_faction_gossip_integration.py::test_hostile_pairs_rank_lower_than_neutral_pairs` and
`::test_same_faction_pairs_rank_higher_than_strangers`. Those fail for a different reason: they
assert a freshly-seeded pair appears in `select_pairs(max_pairs=20)`, and the live graph holds
27,534 nodes of which 23,292 are leaked draft quests (ISSUE-273) against 23 characters, so the
seeded pair cannot make the top-20 cut. **Those two are expected to go green when M1.3 wipes and
reseeds.** This one will not — it is unrelated to graph state.
**Why deferred:** found during a bring-up whose single task was M1.1, and the roadmap's
single-task-focus rule applies. It is also not a blocker: the loop attributes it to the baseline
and commits, rather than halting.
**To fix:** inject a `TypeRegistry` at the test's `QuestLifecycleEngine` construction, matching how
the engine's other call sites build it. Check whether sibling tests in the same file share the
defect. Then confirm the loop's baseline drops from 3 entries to 2.

---

## ISSUE-234: 25 tests call the SUT and assert nothing
**Found:** 2026-08-31, during R1.8
**Severity:** P2 (annoying)
**Where:** 18 files under `tests/unit/`; `make check-test-quality` lists them all
**Description:** `check_test_quality`'s NO_ASSERTION pattern, added in R1.8, found 25 tests
that exercise the system under test and then check nothing. They can only fail by raising.
Some are legitimate does-not-raise tests (`test_exact_fit_is_accepted`,
`test_no_op_when_already_utf8`, `test_exception_does_not_propagate`) and want a
`# quality-ok: <reason>` waiver naming what they prove. Others are probably genuinely weak
and want a real assertion. Which is which is a per-test judgment.
**Why deferred:** R1.8's task was to build the gate, not to spend its findings. Blanket-waiving
all 25 with a generic reason would buy conformance rather than quality — the exact effect
CR-L05-03 measured, and the reason R1.5 was told not to mass-edit.
**To fix:** triage the 25. Each either gains an assertion or a waiver with a specific reason.
Then `printf '0' > scripts/check_test_quality_baseline.txt` and update
`test_real_suite_is_clean` to drop the NO_ASSERTION exclusion, restoring the
zero-findings-plus-explicit-waivers invariant the other five patterns hold.

## ISSUE-235: 42 of 59 engine logger.info calls omit duration_ms
**Found:** 2026-08-31, during R1.8
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/**`; `make check-engine-logs` lists them
**Description:** CLAUDE.md requires `npc_id`, `player_id`, `tick` and `duration_ms` on every
engine log entry. 42 of the 59 `logger.info` calls in `engines/` carry no `duration_ms`, so
per-engine latency cannot be read out of the logs. `scripts/engine_logs_baseline.txt` records
42; the gate reds on 43, so this cannot grow.
**Why deferred:** R1.8 built the gate. Adding a duration to 42 call sites means timing the work
each one reports, which is a behaviour change per site, not a mechanical edit.
**To fix:** work the list down, re-recording with `python scripts/check_engine_logs.py --update`
as it shrinks. The gate only enforces `duration_ms` today — the other three fields CLAUDE.md
names are not yet checked, and widening it is a follow-on decision, not part of this issue.

## ISSUE-223: the dialogue prompt is a process-wide singleton, so it cannot be A/B tested
**Found:** 2026-08-27, during the P0-P9 review that produced `EVAL_P25_TO_P31_PLAN.md`
**Severity:** P2 (annoying) - blocking for Program 5, not for anything shipping today
**Where:** `src/npc_engine/engines/dialogue/prompt_builder.py:32-40`
**Description:** `_PROMPT_PATH = _PROMPTS_DIR / "system_v1.yaml"` and the `llm_config.yaml`
load both run at MODULE level, so the dialogue system prompt is resolved once per process.
Three consequences: (1) no prompt variant can be selected per turn, so prompt-version A/B is
structurally impossible - `DialogueRequest` carries `retrieval_profile` and has no prompt
counterpart, and `paired_arms` makes arm identity *be* the retrieval profile; (2) it is a
module-level load of a stateful resource inside an engine, which CLAUDE.md's
constructor-injection rule forbids; (3) the only way to compare two prompts today is to edit
the YAML and rebuild, which changes `RunConfig.dialogue_prompt_hash` and therefore makes
`compare.py` refuse the pairing outright - so the comparison is not merely unpaired, it is
rejected by the harness.
**Why deferred:** it is the subject of EVAL-P29.2, and it is a `src/` change that collides
with the P9 fence ("no `src/` change lands after P9 goes green"). Sequencing against the P10
regeneration is an open scheduling decision recorded in the plan, not made.
**To fix:** EVAL-P29.1-29.3. Declare `prompt_variants:` in `llm_config.yaml` mirroring
`retrieval_profiles:` with strict resolution; extract
`engines/dialogue/prompt_variant_resolver.py` (required, not optional - `prompt_builder.py`
already carries a 300-line waiver); make the variant an injected per-call argument. Pin with
a byte-identity digest test in the shape of DEC-194's
`test_no_profile_and_explicit_default_profile_are_byte_identical`, written RED first.

## ISSUE-201: `npc.emotion` reports "neutral" while the NPC's character node says otherwise
**Found:** 2026-08-26, during the ISSUE-163 root-cause trace
**Severity:** P2 (annoying)
**Where:** `engines/dialogue/dialogue_handler.py:452` (the `emotion_state` argument) and
`retrieval/context/context_builder.py:176-181` (`_resolve_initial_state`)
**Description:** `npc.emotion` is the default `{"current_mood": "neutral"}` in 100% of the
975 eval rows. It is NOT a budget drop — the emotion item is pinned tier-0 and always
reaches the model; the value itself is neutral. On `mira_innkeeper` the same prompt carries
`npc.profile.emotion_valence = -100`, `emotion_arousal = 100`,
`emotion_mood_label = "agitated"` from the character node, next to
`npc.emotion.current_mood = "neutral"` — the prompt contradicts itself in adjacent fields.
Two candidates, neither confirmed: the handler's `current_emotion` is read from the
in-process emotion store rather than the persisted node, or the store is not seeded from the
graph on a cold start. Also note the whole emotion snapshot is a ONE-KEY dict — valence,
arousal and the mood label never reach the prompt through this path at all.
**Why deferred:** different subsystem (emotion store / dialogue handler), different root
cause from ISSUE-163; logging it separately as instructed rather than widening that fix.
**To fix:** trace `current_emotion` in `dialogue_handler` back to its source, decide whether
the character node or the emotion store is authoritative, and make the tier-0 snapshot carry
valence/arousal/label rather than `current_mood` alone.

## ISSUE-202: `retrieval_runner.main`'s docstring says it takes no options, and it takes two
**Found:** 2026-08-26, during the six A/B plumbing fixes (item 2, Makefile forwarding)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/retrieval_runner.py:269-276` (`main`'s docstring)
**Description:** The docstring states "This runner takes no options today; any argument is
rejected rather than ignored", documents `argv` as "Must be empty", and lists exit code "2 on
unexpected arguments". All three are false: the parser directly below it declares `--gen-dir`
and `--retrieval-profile`, and both are now passed by `make eval-retrieval` and by
`Run-OvernightCombined.ps1` step 4b. Nothing returns 2. The prose is a leftover from before
the flags were added.
**Why deferred:** the task that found it was explicitly scoped "DO NOT change
`evals/retrieval_runner.py` — its CLI already accepts both flags", and a docstring edit there
would have put an unrelated file in one of the six commits.
**To fix:** rewrite the summary to name both options, drop the "Must be empty" Args line and
the phantom exit code 2, and describe the actual contract (0 success, 1 connectivity/setup
failure). One-paragraph edit, no behaviour change.

## ISSUE-195: `retrieved_context` consumers not yet migrated to `context_receipt`
**Found:** 2026-08-21, during the B/C3/C2 landing (DEC-195)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/dashboard/` case pane (renders `retrieved_context` item keys);
`evals/sequence_records.py:63` (`Turn.retrieved_context`)
**Description:** `GenerationRecord.context_receipt` now carries what ACTUALLY reached the
model. `retrieved_context` still carries the older approximation — a second call to
`GET /v1/admin/debug/retrieval` with `session_turns=[]`, describing a different assembly than
the one that produced `npc_response`. Both fields are populated on every new record, and the
two consumers above still read the deprecated one, so the dashboard's context pane is still
reporting over what the retriever RANKED rather than over what SURVIVED the prompt budget.
Those are different numbers, and the gap is the thing the receipt was built to expose.
**Why deferred:** Deleting or repointing them in the same change would have silently altered
what `recall@k` measures at the same moment as the field landed, with no released corpus
carrying `context_receipt` to compare against. The deprecation is marked in
`evals/retrieved_item.py` and in `GenerationRecord`'s docstring, and both fields are written,
so the migration can be measured rather than assumed. Committed corpora
(`evals/generations/k3_73e6c36/`) have no `context_receipt` at all and would read as empty.
**Update (measurement-remediation trim):** `evals/retrieval_join.py` — the third named
consumer above — is deleted; it had zero production callers (imported only by its own test)
and was never wired into `evals/report.py` despite its docstring's "planned" claim. The
recall@k comparison this issue originally asked `retrieval_join` to perform is folded into
the Phase-3/4 per-engine probe framework instead (see the measurement-remediation plan),
which reads `context_receipt` directly rather than resurrecting the deprecated join.
**To fix:** Move the dashboard case pane and `evals/sequence_records.py:63` over to
`context_receipt.item_keys`, then drop `retrieved_context`, `evals/retrieved_item.py` and
`evals/context_capture.py` along with the second debug-endpoint call per turn — which also
removes roughly half of the generation pass's HTTP requests.

## ISSUE-196: generation artifacts are written with platform line endings
**Found:** 2026-08-21, during the B/C3/C2 landing (DEC-195)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/eval_records.py:82-87` (`write_generation_dir`) and `:106`
(`write_transcript`); the same pattern in `evals/judged_persistence.py:167`
**Description:** `Path.write_text` is text mode, so on Windows the `"\n".join(...)` separators
in `outputs.jsonl` and the indentation newlines in `meta.json` are written as CRLF, while the
same code on Linux writes LF. Two runs of the same harness on different platforms therefore
produce byte-different artifacts from identical records. Nothing currently hashes these files
(`harness_version` covers cases, judge prompts and `matchers.py`; `golden_set_version` covers
cases), so no gate is wrong today — but any future content hash over a gen dir, or any diff of
two arms' artifacts, would report a platform difference as a data difference.
**Why deferred:** Not in scope for B/C3/C2, touches persistence shared by the judge pass, and
`evals/generations/` is a frozen path (`scripts/loop_gates.py FROZEN_PATH_PREFIXES`) so a fix
cannot be validated against the committed corpus in the same change.
**To fix:** Pass `newline=""` on every artifact write (the pattern `roadmap_cursor.py` already
uses on both ends, per DEC-151's CRLF hazard note), or write bytes. Add a test asserting `outputs.jsonl` contains
no `\r`.

## ISSUE-173: no mechanical enforcement of phase-level `Depends on:` lines
**Found:** 2026-08-15, during the EVAL-P20-P24 unblock planning session
**Severity:** P2 (annoying — a real gap in loop safety, same family as ISSUE-171 but scoped to
task dependencies rather than the fence marker)
**Where:** `scripts/roadmap_cursor.py` / `_roadmap_cursor_core.compute_next`
**Description:** `compute_next` iterates phases in file order and returns the first task that is
`not done and not skippable` (`⏸️`/`(live` flagged). It never reads a phase's `Depends on:` line —
this was already established by DEC-164 for the *task-flag* mechanism, but its converse was not
separately logged: **a phase-level `Depends on:` is documentation only, not enforced.**
`EVAL-P21`'s own header states `**Depends on:** EVAL-P16.2, EVAL-P18.2, EVAL-P20.4.` but
`EVAL-P21.0` itself carries no `⏸️`/`(live` flag. If `EVAL-P20.3`, `EVAL-P20.3a`, `EVAL-P20.3b` all
land (clearing everything ahead of `EVAL-P21.0` in file order) before `EVAL-P20.4` (regeneration
#1) actually runs — which is entirely possible, since nothing currently stops it — an unattended
loop run would pick up `EVAL-P21.0` and attempt panel-roster work before the artifact its own
phase declares a dependency on exists. Low real-world severity right now (P21.0 is a config/roster
decision that doesn't need the artifact to draft), but the same pattern could bite a future task
whose work *does* require an undelivered dependency.
**Why deferred:** out of scope for a planning session; this is a harness-mechanism gap, not a
single-module bug fix — same class of fix as ISSUE-171 (a `HARNESS-P`-adjacent task), and possibly
worth solving together with it since both are "the roadmap's stated intent isn't mechanically
checked" gaps.
**To fix:** either have `compute_next` refuse a task whose phase's `Depends on:` phases/tasks are
not all done (would need a phase-to-task resolution helper), or extend `check_human_gates.py` to
also validate phase-level `Depends on:` lines against real task-done state, not just the 12
explicit `HUMAN GATE` blocks.

## ISSUE-171: nothing enforced that a `LOOP:QUEUE end` move needs a DECISIONS.md entry
**Found:** 2026-08-15, during the H3-fence-position repair session
**Severity:** P1 (blocking — the exact mechanism HUMAN GATE H3 exists to stop failed silently once)
**Where:** `scripts/expand_loop.sh`, `scripts/roadmap_cursor.py --verify`, `Makefile:check-human-gates`
**Description:** Commit `84ff0f9` ("new task", 2026-08-15 08:43:09 — one second before the
`expand_loop.sh` run named in the day's session log started at 08:43:13) moved
`<!-- LOOP:QUEUE end -->` from the DEC-163 position (above `EVAL-P20`) down to below `EVAL-P24.3`,
reopening `EVAL-P20..P24`, with none of H3's three reopen conditions met (two of three, re-verified
live: `EVAL-P17.6`/`make check-conservation` still exits 3, and `EVAL-P20.0`'s gate measured 62.5%
per DEC-176, landed the day before). No DECISIONS.md entry recorded or justified the move, despite
the marker's own inline text saying to. Nothing mechanical caught this: `roadmap_cursor.py --verify`
only checks grammar (a moved marker is still valid grammar), `check_human_gates.py --verify` only
checks gate *grammar* not fence *position* vs the gates' own stated conditions, and the pytest
tripwire (`test_real_roadmap_fence_state_tripwire`) was itself already red for an unrelated reason
(ISSUE-170, now fixed) and so could not have caught this move even if someone had run it before
committing — see DEC-177 for the full repair. **Reverted** in DEC-177; this issue is about the
missing enforcement, not the one-time move.
**Why deferred:** fixing this means either (a) a new `make` check that diffs the fence marker's line
position against the last position recorded in DECISIONS.md (needs a machine-readable pointer, e.g.
a line in DECISIONS.md itself or a small state file), or (b) having `expand_loop.sh` refuse to
commit any diff touching the `LOOP:QUEUE end` line without a paired DECISIONS.md diff in the same
commit. Either is a new harness mechanism, not a bug fix in the current one, and is out of scope for
a session whose task is restoring the fence position, not redesigning how it's guarded.
**To fix:** design and land one of the two mechanisms above (or a better one), with its own tests,
as a dedicated task — likely a `RET-P0`-adjacent or fresh `HARNESS-P` phase.

## ISSUE-194: the Retrieval Quality Program (RET-P1..P6) is referenced everywhere but exists nowhere
**Found:** 2026-08-21. **CORRECTED the same day — see the correction note below.**
**Severity:** P2 (annoying) — the highest-leverage retrieval fix has no owner and no roadmap entry
**Where:** `project-harness/ROADMAP.md:3289-3342` (`### Phase RET-P0` is the only RET phase)

**⚠️ CORRECTION.** This issue was originally filed as "the dialogue system prompt exceeds
OLLAMA_CONTEXT_LENGTH and PROMPT_TOKEN_BUDGET is silently the clamp floor". **That was a duplicate
of already-recorded work and it is retracted.** The prior art, which the original filing failed to
check for:
- `RET-P0.3` shipped `src/npc_engine/config_prompt_window.py` + `PromptWindowError`, which detect
  exactly this and are fully tested.
- `MEASURED_SYSTEM_PROMPT_TOKENS = 5426` is already recorded as a named constant with its derivation.
- **DEC-175** explicitly decided *not* to wire the check into `Settings`, and gave the reason: today's
  defaults are provably incoherent, so a hard-fail validator would refuse to boot, and "a warning
  nobody reads is not worth a startup-path change on its own". Both hard-fail AND warning-only were
  considered and rejected.
- `tests/unit/config/test_config_prompt_window.py::test_shipped_defaults_do_not_fit_the_default_window`
  already pins the incoherence so the fix has a measurable target.

So the engine defect is known, measured, instrumented and deliberately parked. Nothing about it needed
a new issue.

**What is genuinely new, and is what this issue now tracks:** `RET-P0`'s own header calls it the
"Opening phase of the Retrieval Quality Program (RET-P0...P6)", and both `RET-P0.3` and DEC-175 name
**RET-P6** as the phase that will wire the validator and raise the context window. Grepping
`ROADMAP.md` for `### Phase RET-`, the only entry that exists is `RET-P0`. **RET-P1 through RET-P6
have never been written down.** The consequence: the single largest known retrieval defect — a system
prompt that does not fit its own context window, which plausibly bounds the ~0.3 retrieval precision —
is assigned to a phase with no tasks, no gate, no effort estimate and no owner. It cannot be scheduled,
and `roadmap_cursor.py` cannot see it.

**Why deferred:** writing the RET-P1..P6 phase entries is roadmap authoring — a product-shaping call
about what the retrieval program contains and in what order, which is the maintainer's to make, not a
drive-by edit during metrics work.
**To fix:** author `### Phase RET-P6` (at minimum) in `ROADMAP.md` with the window raise and the
validator wiring as explicit tasks, carrying DEC-175's constraint that the window must be raised
*before* the validator is wired. Decide whether RET-P1..P5 are still wanted or whether the program
should be renumbered. Then the ISSUE-163/ISSUE-145 retrieval defects have somewhere to sit.

## ISSUE-190: `src/npc_engine/config/` (data-only) shadows `config.py` as a namespace package
**Found:** 2026-08-20, during the metrics-pipeline closeout (DEC-193)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/config/` (holds only `llm_config.yaml`) vs `src/npc_engine/config.py`; surfaces at `evals/engine_adapter.py:37,61`
**Description:** the data-only directory wins import RESOLUTION over the module when mypy is
invoked as `mypy evals/`, so `from npc_engine.config import get_settings` reports
`attr-defined` even though `get_settings` exists at runtime (verified: it is in
`dir(npc_engine.config)`). `mypy.ini` excludes the directory from CHECKING, which does not
stop it shadowing. Two narrow `# type: ignore[attr-defined]` suppressions with an explanatory
comment are in place; `make type` over `src/` is unaffected and green.
**Why deferred:** the real fix is renaming the data directory, which touches runtime import
paths across the engine and needs an ask-gate. Not something to do in the hour before a
10-hour regeneration.
**To fix:** rename `src/npc_engine/config/` (e.g. to `config_data/`), update the loader that
reads `llm_config.yaml`, drop the two suppressions, and confirm `warn_unused_ignores` stays quiet.

## ISSUE-191: `check_rules.py` is a regex scanner, so it flags patterns inside comments and docstrings
**Found:** 2026-08-20, during the metrics-pipeline closeout (DEC-193)
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_rules.py:48-50` (`_SWALLOW_RE`, `_PRINT_RE`)
**Description:** the R002/R003 detectors match raw file text, not an AST. Writing the words
`print(` or `` `except: pass` `` inside a comment or docstring — including a comment explaining
why the pattern was removed — re-introduces the violation. Hit twice while fixing R003 this
session: a docstring quoting the anti-pattern, and a comment saying no stdout write happens here.
Both had to be reworded rather than the code changed.
**Why deferred:** cosmetic; the workaround (reword) is trivial and the detector is otherwise
doing its job. `_oversized_functions` already uses `ast`, so the machinery exists.
**To fix:** move R002/R003 onto the `ast` walk that `_oversized_functions` already performs, so
only real `Call`/`ExceptHandler` nodes count.

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
(e.g. "3 rows unparseable"), so a degraded input is visible rather than inferred.

## ISSUE-193: 28 frozen-model tests assert `pytest.raises(Exception)` rather than the specific type
**Found:** 2026-08-20, during the metrics-pipeline closeout (DEC-193)
**Severity:** P3 (nice-to-fix)
**Where:** 28 sites across `tests/unit/` (evals, graph, llm, api, config, engines, retrieval)
**Description:** immutability tests assert that any exception is raised on mutation. The specific
type is knowable per site — pydantic v2 frozen models raise `ValidationError`, frozen dataclasses
raise `FrozenInstanceError` — so a test would still pass if the object raised for an unrelated
reason (a typo'd attribute name, say). All 28 now carry a `# quality-ok:` waiver naming this.
**Why deferred:** maintainer decision (DEC-193 decision A): re-baseline/waive the purely
structural findings rather than make a large mechanical diff across the test suite immediately
before regeneration #1.
**To fix:** narrow each to `ValidationError` or `FrozenInstanceError` per the model family and
delete the waiver comment in the same edit.

## ISSUE-169: `make check-evals-rules` AND `make type-evals` are both red on main
**Found:** 2026-08-14, during `EVAL-P20.0` (running `make check` before committing)
**Severity:** P2 (annoying — two red gates that are not this task's fault mask real regressions)
**Where:** `scripts/evals_baseline.txt` and `scripts/mypy_evals_ratchet.py` vs
`evals/eval_records.py`, `evals/sequence_rates.py`, `evals/scenario_adapters_extra.py`,
`evals/sequence_order_effect.py`, `evals/scenario_adapters.py`
**Description:** Two independent gates are red before this task touches anything. **Both verified
pre-existing** by stashing this task's changes and re-running: identical output either way. They
share a cause — the `EVAL-P12.4` commit (`efbe7ce`) added new evals modules without updating either
baseline.
1. `check-evals-rules`: **6 NEW violations** — R001 `eval_records.py` >300 lines; R002 `print()` in
   `sequence_rates.py`; R006 >40 lines on `make_memory_consolidation`, `make_mood_contagion`,
   `make_time_passage`, `order_effect_check`.
2. `type-evals`: **23 type errors > baseline 16** (+7), concentrated in `scenario_adapters_extra.py`
   (`union-attr` / `operator` on a `dict | None`), plus pre-existing `no-any-return` and two
   `npc_engine.config has no attribute "get_settings"` in `engine_adapter.py`.
Distinct from ISSUE-162, which is the `make lint` E741 in `sequence_order_effect.py` — that is a
third gate. As of this session `make check` therefore has **three** independent pre-existing reds.
**Why deferred:** none of it is caused by or related to `EVAL-P20.0`; single-task focus. Fixing it
means splitting `eval_records.py`, extracting four helpers, and tightening `dict | None` handling —
judgement calls belonging to whoever owns EVAL-P12.4's code.
**To fix:** decide per violation whether to split/extract or waive; fix the `union-attr` errors
properly (they are real latent `None` dereferences, not noise). Do **not** blanket-run
`make check-evals-rules-update` or re-baseline the mypy ratchet: both baseline headers forbid
re-baselining without justification, and doing so would silently absorb whatever else has drifted.

## ISSUE-164: CLAUDE.md stack table claims "no OpenAI adapter ships today" but one exists
**Found:** 2026-08-14, during `EVAL-P20.0`
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/CLAUDE.md` stack table (LLM row) vs
`src/npc_engine/engines/llm/openai_adapter.py`
**Description:** The stack table says the LLM is "pluggable via `LLMClientProtocol` + factory
registry (add a local or API backend by registering an adapter — **no OpenAI adapter ships
today**)". `OpenAICompatibleAdapter` does ship (SHIP-02 / DEC-126), is registered in the factory,
subclasses `LLMClientProtocol`, and has its own test module. The roadmap's `EVAL-P20.0` file list
inherited this error: it named only `protocols.py` and `ollama_adapter.py`, omitting both
`openai_adapter.py` and `mock_adapter.py`, each of which also defines `generate()`.
**Why deferred:** documentation drift found while doing `EVAL-P20.0`; single-task focus. Correcting
CLAUDE.md is not part of adding a seed.
**To fix:** amend the stack table's LLM row to name `OpenAICompatibleAdapter` as shipped, and audit
the table for other claims that have since gone stale (the `prompts/eval/` path row was corrected
the same way on 2026-08-10).

## ISSUE-166: 173 of 228 Cypher queries with RETURN have no ORDER BY
**Found:** 2026-08-14, during `EVAL-P20.0` determinism investigation
**Severity:** P2 (annoying — latent prompt non-determinism)
**Where:** `src/npc_engine/graph/**` (static scan: 228 Cypher blocks containing `RETURN`, 173
without `ORDER BY`)
**Description:** Neo4j does not guarantee row order without `ORDER BY`. Any such query whose rows
are serialized into prompt content can reorder between runs, changing prompt bytes and therefore
the generated text. This was **not** the dominant term in the EVAL-P20.0 measurement — after the
DEC-176 prompt fix, `retrieved_context` drift was 0/145 — but it is unbounded risk that grows with
graph size, and it silently defeats reproducibility when it does bite.
**Why deferred:** not the measured cause of the EVAL-P20.0 gate failure; single-task focus. Fixing
173 queries blind would be churn.
**To fix:** identify the subset whose results reach prompt content (memories, beliefs, goals,
rumors, secrets, items, traits, reputation) and add a deterministic `ORDER BY` — id or an explicit
score then id as a tiebreak — to those first. Add a check-rules rule for new prompt-feeding queries.

## ISSUE-162: `make lint` is red on `main` — E741 ambiguous variable name in `sequence_order_effect.py`
**Found:** 2026-08-14, during `RET-P0` (retrieval quality program)
**Severity:** P2 (annoying)
**Where:** `evals/sequence_order_effect.py:81:46`
**Description:** `make lint` fails with `E741 Ambiguous variable name: 'l'`, which fails the whole
`make check` gate (`lint` is its first target). Pre-existing and unrelated to RET-P0: the file is
untouched by that task (`git diff HEAD -- evals/sequence_order_effect.py` is empty) and was last
modified in `efbe7ce` (EVAL-P12.4). Confirmed the only lint error in the repo.
**Why deferred:** Single-task focus — RET-P0 is scoped to context budget starvation, and this is
stats code owned by the EVAL-P12 line. The variable `l` is deliberate notation for `Lᵢ` from the
Cochran's Q block design documented in DEC-174, so the rename should be made by someone confirming
it stays faithful to `docs/SEQUENCE_STATS_POLICY.md` §4.2 rather than blind-renamed to satisfy ruff.
**To fix:** Rename `l` to a non-ambiguous name that preserves the `Lᵢ` meaning (e.g. `l_i` or
`rep_passes`) and re-run `make lint`. One-line change; the only reason it is not done here is diff
hygiene.

## ISSUE-161: `import npc_engine.retrieval.context` fails standalone with a circular `ImportError`
**Found:** 2026-08-14, during `RET-P0` (retrieval quality program)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/retrieval/context/__init__.py` → `context_builder.py:68` → `retrieval/dialogue_context/__init__.py:13` → `dialogue_context_adapter.py:20`
**Description:** Importing the context package on its own raises
`ImportError: cannot import name 'build_serialized_context' from partially initialized module
'npc_engine.retrieval.context.context_builder' (most likely due to a circular import)`.
Verified directly: `python -c "import npc_engine.retrieval.context"` fails, while
`import npc_engine.retrieval.dialogue_context` followed by `import npc_engine.retrieval.context`
succeeds. The cycle is `context` → `dialogue_context` → `context`. It is invisible today only
because every production entry point happens to import `dialogue_context` first, so import order
is load-bearing but undocumented and unenforced.
**Why deferred:** RET-P0 is scoped to budget starvation (ISSUE-145); single-task focus. The cycle
predates this task and breaks nothing currently shipping.
**To fix:** Break the cycle by having `dialogue_context_adapter` import `build_serialized_context`
lazily inside the calling method, or move the shared entry point into a module both packages can
depend on downward. Add a regression test that imports `npc_engine.retrieval.context` in a fresh
interpreter. **Blocking for RET-P1.3**, whose in-process eval fallback imports the context package
directly and will hit this.

## ISSUE-159: `/v1/npc/{id}/state` and `/v1/npc/{id}/emotion` return their model directly, unlike the rest of the API's `OkEnvelope` convention
**Found:** 2026-08-13, during EVAL-P12.4 (HUMAN GATE H5), while writing `evals/scenario_adapters.py`
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/api/routes/dialogue/npc_state.py` (`npc_state`, `npc_emotion`) and
`src/npc_engine/api/routes/dialogue/dialogue.py` (`dialogue`) — all three declare
`response_model=<Model>` and return the model instance directly, rather than
`response_model=OkEnvelope[<Model>]` + `ok_response(...)` the way every admin/graph/reputation route
in this codebase does.
**Description:** A client written against the API's dominant convention (`{"success": true, "data":
{...}, "meta": null}`) will silently read `None`/`{}`/`0.0` from these three endpoints instead of an
error — the response is still 200 with a well-formed body, just shaped differently. Cost real debugging
time in this task: the first draft of `evals/scenario_adapters.py`'s `gossip_chain` and
`grief_persistence` adapters read `resp.json().get("data", {}).get(...)`, which is correct for every
other endpoint in this file but silently returned `[]`/`0.0` for these three, making two working
scenarios look like they were failing their pass/fail predicate.
**Why deferred:** out of scope for EVAL-P12.4 — fixing it changes a public response shape three routes
have shipped with, which needs a version/compat decision (does `demo_game/client.py` or any other
consumer already depend on the unwrapped shape?) that this task's live-measurement mandate does not
cover.
**To fix:** either (a) wrap all three in `OkEnvelope`/`ok_response` for consistency, coordinating the
breaking change with every known consumer, or (b) if the unwrapped shape is intentional (these are the
only three read-only "current state" endpoints with no `error`/`meta` need), document the split
explicitly in the API conventions doc so the next integrator doesn't rediscover it as a bug.

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
(and `_KIND_ANTI_HALLUCINATION_GROUNDED = "anti_hallucination_grounded"`) into
`tally["hallucination"]` when `is_guard` is true, in `_bucket_expectation`. Add a regression
test asserting a failing `refusal_judge` and a failing `anti_hallucination_grounded` expectation
in a guard case both increment `EvalSummary.hallucination_failures`. Fix this **together with**
ISSUE-155 — fixing one without the other still produces a wrong headline (either right kinds at
k=1, or right k at wrong kinds).

## ISSUE-155: `verdict_sources.load_unified_rows` dedups by `record_id` alone, silently
collapsing k=3 repetitions to k=1 (found while re-measuring EVAL-P17.5)
**Found:** 2026-08-12, during EVAL-P17.5 step 3 (re-running `summarize_from_dir` over the
unchanged `evals/generations/k3_73e6c36` artifact)
**Severity:** P2 (annoying)
**Reclassified:** Downgraded P1→P2 2026-09-02 by DEC-250 — but NOT closed, deliberately. Collapsing k=3 repetitions to k=1 corrupts any number `summarize_from_dir` produces, including regression comparisons the retained tests depend on. It survives the retirement of the claim; only its urgency drops.
including the one EVAL-P17.5 is re-measuring, and by extension `compare`, which also consumes
`load_unified_rows`)
**Where:** `evals/verdict_sources.py:166-171`, function `load_unified_rows`
**Description:** `record_id` (e.g. `case_adv_aldric_black_market:schema:0`) encodes
`case_id:matcher_kind:expectation_index` — it does **not** encode `repetition`. Confirmed by
direct inspection of `outputs.jsonl`: the same `record_id` recurs once per repetition (0, 1, 2)
with `repetition` carried as a *separate* field. `load_unified_rows` builds
`seen: dict[str, VerdictRow] = {}` keyed on `row.record_id` alone
(`seen[row.record_id] = row`), so the three repetitions of every slot collide on the same key
and only the last one written survives — silently discarding 2 of every 3 repetitions before
`to_summarize_results` ever groups by `(case_id, repetition)`.
Measured effect on the unchanged `k3_73e6c36` artifact (`k=3` per `meta.json`):
`summarize_from_dir` reports `guard_turns=78` (== `guard_cases=78`, i.e. exactly 1 turn per
case) instead of the expected 78 × 3 = 234, and the battery-rate design-effect string prints
`k=1.0` where it should print `k=3.0`. Direct check: `case_adv_aldric_black_market` has 4
distinct `record_id`s in `deterministic_judged.jsonl`, each appearing 3 times (once per
`repetition` 0/1/2, all `passed=True` in this sample) — `load_unified_rows` returns only 1 row
per `record_id` for that case, not 3.
This also means `compare` (EVAL-P18.3, same `load_unified_rows` dependency) has been comparing
whichever single repetition happened to be written last per slot, not an aggregate over k
repetitions, since EVAL-P17.1 landed.
**Why deferred:** Out of scope for EVAL-P17.5 (re-measure and retract is read-only arithmetic
over the existing artifact, not a pipeline fix) and out of scope per `project-harness/CLAUDE.md`
single-task-focus — fixing this is a new, separate change to `evals/verdict_sources.py`.
Surfaced to the human via `EVAL-P17.5` step 4 before any Session Log edit, per that phase's "traced,
not hand-waved" gate.
**To fix:** Key `seen` in `load_unified_rows` by `(row.record_id, row.repetition)` instead of
`row.record_id` alone; update `to_summarize_results` grouping if needed (it already groups by
`(case_id, repetition)`, so no change expected there); add a regression test asserting
`len(load_unified_rows(gen_dir)) == 3 * <slots-in-a-single-repetition>` for a fixture with
`k=3`. Re-run `EVAL-P17.5`'s re-measurement afterward — the corrected headline will not match
either the number in this issue or the ISSUE-154 prediction.

## ISSUE-154: EVAL-P17.5 re-measurement — prediction recorded before running (pre-registered)
**Found:** 2026-08-12, during EVAL-P17.5 (re-measure and retract)
**Severity:** P2 (tracking entry — not a bug; a pre-registered prediction, written before the
re-measurement runs, per EVAL-P17.5's "write expected numbers before you run anything" discipline)
**Where:** `evals/generations/k3_73e6c36` (unchanged artifact), read via
`summary.summarize_from_dir` / `summary.format_summary_lines` (no regeneration)
**Description:** Predicted corrected headline: **~18 lore hallucinations across ~234
case-repetitions** (78 guard cases × k=3), superseding the 2026-08-10 audit's floor of "≥10
across ≥186 turns," which itself superseded the currently-published (and now retracted) "3 lore
hallucinations across 111 adversarial turns."

Reasoning: the retracted "3 across 111" and the audit's "≥10 across ≥186" were both undercounts
because both were computed from `judged.jsonl` alone (LLM-judge verdicts only).
- **EVAL-P17.1** (aggregate over both verdict sources) now merges `judged.jsonl` with
  `deterministic_judged.jsonl` via `verdict_sources.load_unified_rows`, which surfaces 8
  previously-invisible failing `anti_hallucination_grounded` deterministic rows that never
  appeared in the old judged-only count.
- **EVAL-P17.2** (unclassifiable cases raise, delegated to `classify_battery`) raises the guard
  battery from the old, incompletely-classified set to **78 cases** (adding the 41 `ah_demo_*`
  cases that previously fell outside any recognized battery prefix), so the denominator becomes
  78 × k=3 = **234 case-repetitions**, not 111 or 186.
- EVAL-P17.3 (infra vs. content separation) and EVAL-P17.4 (skips leave the numerator) affect
  which failures count as content hallucinations vs. inconclusive/skipped, feeding into the same
  headline via `summary.EvalSummary.headline`.
**Why deferred:** N/A — this is not deferred work. It is the pre-registered prediction for
EVAL-P17.5 step 4 (compare actual vs. this prediction). Human-confirmed via AskUserQuestion on
2026-08-12 before being written here, per ROADMAP.md's HUMAN GATE H1.
**To fix:** N/A. Close out (do not mark `[FIXED]`) once EVAL-P17.5 step 4 records the actual
re-measured number next to this prediction and either matches it or traces the delta to a named
`case_id`/line of code.
**Result (2026-08-12):** Confirmed. The shipped pipeline reported "1 lore hallucination across
78 adversarial turns" (not 18/234) due to two now-logged bugs — ISSUE-155 (repetition collision
in `load_unified_rows`) and ISSUE-156 (`refusal_judge`/`anti_hallucination_grounded` excluded
from `hallucination_failures`). With both hand-patched in a scratch script (not committed), the
recomputed headline is exactly **18 lore hallucinations across 234 adversarial turns** — an
exact match to this prediction. Recorded as the corrected headline in ROADMAP.md's Session Log
per human decision 2026-08-12; `EVAL-P17.5` ticked. ISSUE-155/ISSUE-156 remain open — they are
the pipeline fix still required before live tooling (`summarize_from_dir`, `compare`)
reproduces this number.

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
`case_pos_lira_fence_trade`'s judge with one that cannot be satisfied by the prompt, then
delete each repaired id from `GAMEABLE_BASELINE` and confirm `make hedge-probe` exits 0.

## ISSUE-147: capability battery is 16 cases against a target of ~35
**Found:** 2026-08-10, during EVAL-P20.2
**Severity:** P3 (nice-to-fix)
**Where:** `evals/cases/case_pos_*.yaml`
**Description:** EVAL-P20.2 targets ~35 capability cases and was ticked under its own
ratchet clause at 9 authored (7 to 16). The remaining ~19 are unwritten. Coverage of
*demo-world NPCs* is complete — `UNCOVERED_BASELINE` is empty and every grounded demo NPC
has one case — so the remainder is depth (a second and third fact per NPC) plus the
village and tavern eval worlds, which have no capability coverage at all.
**Why deferred:** the ratchet clause exists precisely so this does not have to land in one
sitting; 9 cases clear the gate's authored-set requirement.
**To fix:** author against `docs/CAPABILITY_CASES.md`, one case per remaining grounded
fact. Each must resist the echo and the hedge —
`tests/unit/evals/test_capability_echo_resistance.py` enforces both for any new case.

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

## ISSUE-127: No gate catches Makefile `-m <module>` targets that rot after a package move
**Found:** 2026-08-05, during EVAL-P0.4 setup
**Severity:** P2 (annoying)
**Where:** `Makefile` (every `$(PYTHON) -m ...` target); regression source was PR-5 (827212d)
**Description:** PR-5 split `demo_game/` into sub-packages, moving `demo_game/seed.py` →
`demo_game/seeds/seed.py`, but `make demo-seed` kept invoking `-m demo_game.seed`. The target
failed with `No module named demo_game.seed` for everyone who ran it, and `make check` stayed
green because no gate imports the module paths named in the Makefile. Any future package move
can silently break another target the same way.
**Why deferred:** The broken target itself is fixed (this session). The missing *gate* is
separate work and would have expanded EVAL-P0.4 setup into harness work.
**To fix:** Add a unit test that parses the Makefile for `-m <dotted.module>` occurrences and
asserts `importlib.util.find_spec` resolves each one. Cheap, no I/O, runs in `make check`.

## ISSUE-128: `captain_sorn` invents a warlord name ("bjorn") under adversarial pressure
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Severity:** P2 (annoying)
**Where:** engine dialogue path; reproduced by `evals/cases/case_neg_captain_sorn_no_troop_specifics.yaml`
**Description:** Asked "How many Northmen are massing at the pass, Captain — exact numbers — and
what is their warlord's name?", the NPC replied "...As for their warlord, they ca[ll him bjorn]..."
tripping `keyword_none` on `['bjorn']`. No `bjorn` entity exists in the graph. This is the **single
case-level lore hallucination** in the 2026-08-06 baseline (1 across 37 guard turns) — a real
invention, not a scorer artifact. The NPC correctly hedged the troop-count half of the same
question, so the guard held for numbers but not for a proper noun.
**Why deferred:** EVAL-P0.4 is a *measurement* task — its output is the baseline, and fixing the
engine mid-measurement would invalidate the numbers it exists to produce.
**To fix:** Investigate whether the retrieved context leaks a name-shaped token or whether the
prompt's refusal rubric covers quantities but not named entities. Add the fix's regression case to
the guard battery. Re-measure against the frozen `evaluated_cases` denominator (ROADMAP Session Log
2026-08-06 §g) so the before/after is comparable.

## ISSUE-150: `evals/runner.py` and `evals/report.py` have functions exceeding 40 lines
**Found:** 2026-08-12, during EVAL-P17.4
**Severity:** P3 (nice-to-fix)
**Where:** `evals/runner.py` (`_run_case` ~164 lines, `main` ~93 lines); `evals/report.py` (`write_report` ~71 lines)
**Description:** Pre-existing violations of the 40-line function limit. EVAL-P17.4 slightly extended each by adding skip-handling logic, but did not introduce the violation.
**Why deferred:** Splitting these functions was out of scope for EVAL-P17.4 (single-task focus). The functions are cohesive orchestrators; splitting would require a DECISIONS.md entry.
**To fix:** Extract sub-helpers (e.g. `_format_case_header`, `_count_results`, `_write_case_section` for report.py; `_print_skip_console`, `_count_non_skipped` for runner.py) to bring each function under 40 lines.

---

## ISSUE-083: two voice tone_judge cases fail under epoch=war / stage_b_v2.9 (captain_sorn, mira_innkeeper)
**Found:** 2026-06-09, during eval re-run
**Severity:** P3 (nice-to-fix — voice quality, not anti-hallucination)
**Where:** `case_voice_captain_sorn_001`, `case_voice_mira_innkeeper_001`; possibly influenced by
the `ECHO_GUARD` line in `prompt_builder.py` (stage_b_v2.9).
**Description:** captain_sorn's reply hedges ("no major breakthroughs or setbacks announced yet"),
failing the authoritative-military voice judge (borderline, pre-existing). mira_innkeeper's reply
reads as a dry objective war report rather than warm gossip ("Villagers speak of soldiers
marching...") and now fails the warm-gossip voice judge — it was passing before. The new ECHO_GUARD
("answer only in your own general terms... speak only from the knowledge in your context") may be
nudging NPCs toward terse, factual reporting at the cost of voice colour; could also be LLM variance.
**Why deferred:** Voice polish is a separate axis from the anti-hallucination guarantee this task targets.
**To fix:** Confirm whether ECHO_GUARD is the cause (A/B a couple of runs with the line removed). If
so, soften the guard wording so it constrains echoing without flattening voice, or scope it to only
fire when the player message contains a planted figure/presupposition. Otherwise tune the two voice prompts.
**Update (2026-06-11, S25.1 / DEC-096):** ECHO_GUARD confirmed as *a* cause and softened in
`prompt_builder.py` (`_ECHO_GUARD_TEXT`, `stage_b_v2.13`): dropped the always-on "answer only in your own
general terms" flattener, scoped each directive to an explicit player plant. Live A/B: voice **0/2 → ~1/2**
(mira recovers gossip framing; captain still borderline-fails on "Reports…/our scouts keep us informed"),
anti-hallucination **5/5** guards still pass (no moat regression). **Kept OPEN — narrowed residual:** the
captain_sorn failure is now voice-judge strictness + a secondary-source ("reports/scouts") habit, not the
ECHO_GUARD. Remaining fix is voice-prompt/seed tuning (out of S25.1's prompt-wording scope) — e.g. a
VOICE_DESCRIPTOR nudge away from third-person reporting toward first-person command, or relaxing the
captain tone judge to accept "reports of skirmishes" as a commander relaying field intel.
**Update (2026-06-22, engine-quality remediation):** Reviewed for a deterministic fix; **none exists** —
the residual is voice-judge strictness + LLM variance, and both candidate levers need an Ollama A/B to
verify (not deterministic). Note the demo seed's own descriptor reinforces the disliked habit:
`captain_sorn`'s `voice_descriptor` in `demo_game/seed.py:688` ends "Every sentence lands like a report to
a superior officer" — the "report" framing nudges toward third-person "reports/scouts" relay. Two minimal
levers remain, each LLM-variance-prone: (a) relax the tone judge in `evals/cases/case_voice_captain_sorn.yaml`
to accept a commander relaying field intel ("reports of skirmishes", "my scouts confirm") as authoritative;
(b) reword the seed `voice_descriptor` toward first-person command. **Kept OPEN (no churn)** per the
"recommend OPEN rather than churn prompts when no confident deterministic fix exists" guidance. Anti-
hallucination guards remain unaffected (separate axis).

---

## [WONTFIX] ISSUE-051: Dashboard S12.4 engine cadence/cost controls are read-only (no live mutation)
**Found:** 2026-06-03, during S12.4
**Severity:** P3 (nice-to-fix)
**Where:** `dashboard/js/engines.js`, `src/npc_engine/api/routes/system.py` (`/v1/system/config`)
**Description:** The Engines tab displays runtime cadence/cost config + per-engine status but cannot change them. `Settings` is a frozen `lru_cache` singleton and the autopilot captures `interval_seconds`/`budget_guard` at construction in the lifespan, so there is no runtime-mutation path. See DEC-054.
**Why deferred:** Live mutation requires a `RuntimeConfigStore` injected into the autopilot + a guarded write endpoint — a public-interface/scheduler change needing approval, out of scope for the read-only first slice.
**To fix:** Add a `RuntimeConfigStore` read by the autopilot each loop for interval + LLM budget; expose `PATCH /v1/system/config` (graph_admin scope, bounded values); wire the dashboard inputs to it.
**Closed:** 2026-06-03, S13.2 dropped (DEC-055) — deprioritized below the CRITICAL/HIGH review-remediation backlog; dashboard controls remain read-only. Reopen if a customer needs live tuning.

---

## ISSUE-301: `API_KEY_GRAPH_WRITE`/`API_KEY_GRAPH_ADMIN` have no weak-secret validation
**Found:** 2026-09-07, during full-review (L1-02)
**Severity:** P2
**Where:** `src/npc_engine/config_validators.py`, `src/npc_engine/config.py`
**Description:** `API_KEY_SECRET` has a weak-secret validator rejecting shipped defaults in staging/prod. The two higher-privilege scopes, `API_KEY_GRAPH_WRITE` and `API_KEY_GRAPH_ADMIN`, have none — so the keys granting write and admin access can ship with a dev default while the lowest-privilege key cannot.
**Why deferred:** Not exploitable on the default loopback-bound deployment; the review's five CRITICALs took the slot.
**To fix:** Extend the existing validator to cover both fields. Non-breaking, internal.

## ISSUE-302: admin-scoped `npc_ids`/`location_ids` request lists have no upper bound
**Found:** 2026-09-07, during full-review (L1-03)
**Severity:** P3
**Where:** `src/npc_engine/api/routes/admin/batch.py`, `graph_admin.py`
**Description:** Batch admin endpoints accept unbounded `npc_ids`/`location_ids` lists. CLAUDE.md requires input caps at the API boundary; these have none.
**Why deferred:** Admin-auth gated, so the blast radius is an authenticated operator only.
**To fix:** Add a `max_length` to the list fields, sized from realistic batch use.

## ISSUE-303: `is_public_path` treats `/setup` as a prefix match, not a route allow-list
**Found:** 2026-09-07, during full-review (L1-04)
**Severity:** P3
**Where:** `src/npc_engine/auth/middleware_helpers.py:71-72`
**Description:** The public-path check appears to prefix-match `/setup` rather than matching an explicit route allow-list, so a future route beginning with that prefix would be public by accident. Graded **Suspected** — not confirmed by a live request.
**Why deferred:** Unconfirmed, and the `/setup/*` surface is already env-gated and loopback-bound (CR-L05-11 fixed).
**To fix:** Confirm by adding a route under the prefix and asserting it is NOT public; then convert the check to an exact allow-list.

## ISSUE-304: two god-ports pair a 9- and 11-method interface with a single caller
**Found:** 2026-09-07, during full-review (L2-03)
**Severity:** P3
**Where:** `src/npc_engine/engines/ports/chapter_port.py:21-70`, `quest_generation_port.py:17-76`
**Description:** `ChapterGraphPort` (9 methods, 1 implementor, 1 caller) and `QuestGenerationGraphPort` (11 methods, 1 implementor, 2 callers) provide none of ISP's benefit and all of its cost.
**Why deferred:** Subsumed by the wider port-sizing decision (34 of 44 ports fail the repo's own DIP threshold), which is awaiting a human call.
**To fix:** Fold into whichever direction that decision takes.

## ISSUE-305: two ports import graph-owned types, one an explicitly private Protocol
**Found:** 2026-09-07, during full-review (L2-04)
**Severity:** P2
**Where:** `src/npc_engine/engines/ports/event_port.py:19-20,33`; also `relation_read_port.py:21`, `scheming_port.py:22`
**Description:** `event_port.py` imports `_EventNode` from `graph/event/event_writer.py:20` — a leading-underscore Protocol the writer marks private — and uses it as a parameter type. The port's own docstring (`:6-7`) says engines use it "instead of importing graph writers." The dependency inversion the port exists to create is undone through the type import. Layer-rank direction is legal, so `check-layers` correctly does not flag it; the defect is ownership.
**Why deferred:** No live failure; it is a latent coupling.
**To fix:** Have the port own its DTO (in `event_port.py` or a shared `engines/ports/_dtos.py`) and have the graph writer conform to it.

## ISSUE-306: three sibling quest Protocols redeclare identical methods
**Found:** 2026-09-07, during full-review (L2-05)
**Severity:** P3
**Where:** `src/npc_engine/engines/ports/quest_port.py:21-124`
**Description:** `QuestLifecycleGraphPort`, `QuestOfferGraphPort` and `QuestRewardGraphPort` each redeclare a method a sibling in the same file declares (`get_quest_state`, `update_quest_node_status`), all satisfied by one implementor. Structural typing lets the copies drift with no type-checker cross-check.
**Why deferred:** Cosmetic today.
**To fix:** Extract a shared base Protocol, or record "ISP over DRY" as deliberate in DECISIONS.md.

## ISSUE-307: CLAUDE.md's inline layer diagram omits `observability/` and `setup/`
**Found:** 2026-09-07, during full-review (L2-06)
**Severity:** P3
**Where:** `project-harness/CLAUDE.md` (Architecture section); `scripts/check_layers.py:28-49`
**Description:** `LAYER_RANK` ranks `observability` and `setup` at rank 1 (`:45-49`, SHIP-03/DEC-127). The CLAUDE.md diagram — billed as "the one rule this file states in full" — lists 16 packages and omits both. DEC-249 says layer lists should be pointers precisely because inline copies rot; this one already has, for 2 of 18 ranked packages.
**Why deferred:** Both are leaf rank-1 dirs; no live impact.
**To fix:** Add the two rows, or replace the diagram with a pointer to `LAYER_RANK`.

## ISSUE-308: the WS connection cap is tested at the helper, not at the endpoint
**Found:** 2026-09-07, during full-review (L4-04)
**Severity:** P2
**Where:** `src/npc_engine/api/routes/dialogue/dialogue_ws.py:221-225`; tests for `check_ws_connection_limit()`
**Description:** The guard test exercises the limit helper in isolation. The endpoint's own accounting is untested — which is exactly where the CRITICAL slot leak (SEV-01) lives. Asserted-not-measured.
**Why deferred:** SEV-01's brief includes the sequential-close endpoint test; this entry records the wider pattern for the WS surface.
**To fix:** Add endpoint-level tests via `TestClient(app).websocket_connect`, covering both acquire and release.

## ISSUE-309: repository-passthrough and Cypher-substring test patterns remain asserted-not-measured
**Found:** 2026-09-07, during full-review (L4-05)
**Severity:** P2
**Where:** `tests/unit/graph/` (e.g. `test_story_pacing_repository.py:31-41`)
**Description:** 127 delegate tests prove a mock echoed itself; an executed counterfactual gutting 105 repository passthroughs produced only 66 failures. Restated from CR-L14-02, confirmed unchanged at HEAD `8d30a3e1`. The wrapped Cypher is exercised only by `tests/integration`, which skips 34 of 43 in the default environment.
**Why deferred:** The remedy depends on whether the CI `integration-tests` job is merge-gating — an open question in DECISIONS.
**To fix:** Resolve the CI-gating question, then either rely on CI or add real-Cypher coverage locally.

## ISSUE-310: existence-only tests assert wiring, not behaviour
**Found:** 2026-09-07, during full-review (L4-06)
**Severity:** P3
**Where:** across `tests/unit/`
**Description:** Several tests assert `hasattr(...)` or `iscoroutinefunction(...)` — they prove a symbol exists and is async, not that it does anything. They survive any implementation change that keeps the signature.
**Why deferred:** Low individual value; better fixed opportunistically alongside the modules they cover.
**To fix:** Replace each with a behavioural assertion, or delete it as noise.

## ISSUE-311: ISSUE-107's "wired into the e2e battery" claim is false
**Found:** 2026-09-07, during full-review (L6-02)
**Severity:** P2
**Where:** `e2e/scenarios/scenario_memory_recall_e2e.py`
**Description:** ISSUE-107 was resolved with the claim that the cross-session memory-recall scenario is "wired into the e2e battery". It is not: the file has no `test_*` function or marker and is collected by nothing. The persistent-memory guarantee — the product's headline capability — has no automatic cross-session test. Contradicts a resolved issue, so this is a **regression** of the resolution, not a new gap.
**Why deferred:** Needs a decision on where cross-session e2e runs (it needs live services).
**To fix:** Give the scenario a collectable test entry point and put it in a suite something actually runs.

## ISSUE-312: the entire branch system is one two-option stub, undocumented as final scope
**Found:** 2026-09-07, during full-review (L6-03)
**Severity:** P2
**Where:** `demo_game/branches/`
**Description:** The branching system is a single two-option branch (`garrick_deserter`). Its docstring says "First-slice"; no second slice exists anywhere and no DECISIONS entry records that one-branch is the intended final scope.
**Why deferred:** Product-scope call, not a defect.
**To fix:** Either add branches or record the intended scope in DECISIONS.md so the "First-slice" docstring stops implying unfinished work.

## ISSUE-313: `matchers.py`'s `_DISPATCH` table is a closed seam for new eval-scorer kinds
**Found:** 2026-09-07, during full-review (L7-01)
**Severity:** P3
**Where:** `evals/matchers.py`
**Description:** Adding a scorer kind requires editing the `_DISPATCH` table — a closed module — whereas eval cases and generation are both file-glob open. Deliberate per DEC-145's size waiver, but it is the one closed eval-authoring surface.
**Why deferred:** Deliberate; low churn.
**To fix:** Registry-style registration if scorer kinds start changing often; otherwise leave and note the choice.

## ISSUE-314: `engines/llm/factory.py` docstrings describe a self-registration pattern the code does not use
**Found:** 2026-09-07, during full-review (L7-02)
**Severity:** P3
**Where:** `src/npc_engine/engines/llm/factory.py`
**Description:** The docstrings describe adapter self-registration; the code uses an explicit factory mapping. Documentation asserting capability the code lacks (systemic pattern §3.6).
**Why deferred:** Docs-only.
**To fix:** Correct the docstrings to describe the explicit registry.

## ISSUE-315: adding a tick-driven engine requires editing 4 existing files
**Found:** 2026-09-07, during full-review (L7-03)
**Severity:** P2
**Where:** `scheduler/tick_scheduler.py`, `scheduler/engine_slots.py`, a getter module, `api/dependencies_engines/__init__.py`
**Description:** The OCP verdict for the repo's main expansion axis is **closed**: a new engine is not a new file, it is 4 edits to closed modules. A good introspection-based wiring guard (`_assert_every_engine_slot_wired`) now exists and catches a missed edit, but the edits are still required.
**Why deferred:** A generic-registry refactor is a large change; L7 recommends deferring until a fifth distinct call signature appears.
**To fix:** Either a registry-driven engine table, or accept and document the 4-file cost.

## ISSUE-316: location-connection `kind` is still an unconstrained `str`
**Found:** 2026-09-07, during full-review (L7-04)
**Severity:** P3
**Where:** location graph models
**Description:** A fixed value set typed as `str`, against CLAUDE.md's `Literal`/`Enum` rule. Carried over from the 2026-06-03 L7-04 finding; still live.
**Why deferred:** Blocks nothing today; relevant when the PART_OF location hierarchy lands.
**To fix:** Convert to `Literal`/`Enum` with the hierarchy work.

## ISSUE-317: `distortion_strategy.registry_keys()`'s docstring overclaims openness
**Found:** 2026-09-07, during full-review (L7-06)
**Severity:** P3
**Where:** `src/npc_engine/engines/gossip/distortion_strategy.py`
**Description:** The docstring implies new distortion strategies register themselves; adding one still edits this module. The axis improved from closed to partly-open, but the docstring describes more openness than the code delivers.
**Why deferred:** Docs-only.
**To fix:** Correct the docstring.

## ISSUE-318: `llm_tokens_in_total` excludes the system channel and under-counts input tokens 4.3×
**Found:** 2026-09-07, during full-review (L9-05)
**Severity:** P2
**Where:** `src/npc_engine/engines/llm/llm_metrics.py`
**Description:** Measured live: the counter omits the system channel, so real input tokens are ~4.3× the reported figure. Any prompt-budget reasoning done from this metric is wrong by that factor — directly relevant given the ~4,245-token static system prompt.
**Why deferred:** Observability defect, not a runtime failure.
**To fix:** Include the system channel, and state the change in DECISIONS since it moves a published number.

## ISSUE-319: the latency instrumentation cannot express the budget it exists to defend
**Found:** 2026-09-07, during full-review (L9-06)
**Severity:** P2
**Where:** `src/npc_engine/engines/llm/llm_metrics.py:12-14`
**Description:** `llm_backend_latency_seconds` is a count/sum/min/max summary with **no buckets**, so no p50/p95 is derivable from the metrics endpoint. The 3–7s dialogue budget is a percentile claim that the shipped instrumentation cannot evaluate.
**Why deferred:** DEC-273's instrumentation work just landed; this is the follow-on.
**To fix:** Add histogram buckets sized around the 3–7s budget.

## ISSUE-320: `check-rules` reports a resolved baseline entry on every run and never ratchets it down
**Found:** 2026-09-07, during full-review (L9-07)
**Severity:** P3
**Where:** `scripts/rules_baseline.txt`, `scripts/check_rules.py`
**Description:** A baseline entry whose underlying violation is resolved is still reported each run; the ratchet does not remove it. A baseline that cannot shrink stops being a ratchet.
**Why deferred:** Cosmetic noise.
**To fix:** Prune resolved entries and make the ratchet remove them automatically.

## ISSUE-321: `BASELINE_2026-08-28.md` no longer matches the tree
**Found:** 2026-09-07, during full-review (L9-09)
**Severity:** P2
**Where:** `project-harness/review-2026-08/BASELINE_2026-08-28.md`
**Description:** Measured at HEAD `8d30a3e1`: `make test` is 4,571 passed / 41 skipped (baseline records 4,048 / 36); coverage 88.13% (baseline 87.86%). The file's stated purpose is that "a number that moved without an explanation is a finding" — but it is a point-in-time record that must not be edited, so "no delta" can no longer be used as a check against it.
**Why deferred:** The file is deliberately immutable.
**To fix:** Capture a new dated baseline for the post-review cycle and point `/fix-next` at it, leaving the 2026-08-28 file as history.

## ISSUE-322: the `stream`/`stream_text` call site is dead in the production dialogue path
**Found:** 2026-09-07, during full-review (L11-01)
**Severity:** P2
**Where:** `src/npc_engine/engines/dialogue/`, `engines/llm/` streaming methods
**Description:** The streaming protocol methods are implemented but unreachable from the production dialogue path. Related to ISSUE-299 (docs describe WS streaming frames the code does not send).
**Why deferred:** Deleting a protocol method is a public-interface change.
**To fix:** Either wire streaming into the WS path (which is what the docs already claim) or delete the dead methods and correct the docs.

## ISSUE-323: memory consolidation asks for structured JSON through the unstructured `generate` protocol
**Found:** 2026-09-07, during full-review (L11-04)
**Severity:** P2
**Where:** `src/npc_engine/engines/memory_consolidation/`
**Description:** The engine requests JSON via plain `generate` rather than `generate_structured`, so it gets no schema enforcement and must parse free text. This is precisely the cognitive-demand class a smaller model handles worst without structural constraints.
**Why deferred:** Requires a schema definition and a fallback path for parse failure.
**To fix:** Move to `generate_structured` with a Pydantic schema; keep the existing failure path.

## ISSUE-324: proactive dialogue line generation has zero fallback and no timeout enforcement
**Found:** 2026-09-07, during full-review (L11-05)
**Severity:** P2
**Where:** `src/npc_engine/engines/proactive_dialogue/`
**Description:** Unlike dialogue, the proactive path has no local fallback when the model fails, and its declared timeout is not enforced (see also the `timeouts_ms` dead-config finding). A model failure surfaces as no line at all.
**Why deferred:** Needs a product decision on what a failed proactive line should do (silence is arguably correct).
**To fix:** Decide the failure contract, then implement it explicitly rather than by omission.

## ISSUE-325: two dialogue rules are both numbered 17, and rule 15 is out of sequence
**Found:** 2026-09-07, during full-review (L12-01)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml`, `system_state_v1.yaml`
**Description:** `system_state_v1.yaml`'s appended rule collides with `system_v1.yaml`'s own Rule 17 in the assembled prompt, and Rule 15 is out of sequence. Cosmetic today (no broken cross-reference), but it is evidence the assembled artifact was never proofread as one document.
**Why deferred:** Any prompt edit changes `dialogue_prompt_hash` and breaks eval comparability.
**To fix:** Renumber when the next deliberate prompt change is taken, so the comparability cost is paid once.

## ISSUE-326: Rule 9 (ECHO PROHIBITION) and Rule 5 (verbatim inclusion) can collide
**Found:** 2026-09-07, during full-review (L12-03)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml`
**Description:** When the player's claim matches the NPC's own true account, Rule 9 forbids echoing it while Rule 5 requires including `MY_ACCOUNT_N` verbatim. Graded **Suspected** — not demonstrated in a live turn.
**Why deferred:** Unconfirmed, and prompt edits cost eval comparability.
**To fix:** Construct the colliding case and observe the model's behaviour before editing anything.

## ISSUE-327: the Rule 16 vs Rule 2 tie-break is delegated to model "judgement" with no algorithm
**Found:** 2026-09-07, during full-review (L12-04)
**Severity:** P2
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml`
**Description:** When STANDING (Rule 16) and PLAYER REPUTATION (Rule 2) disagree, the prompt tells the model to use its judgement rather than giving a rule. That is the single instruction most likely to degrade on a smaller model, since it asks for arbitration rather than a lookup.
**Why deferred:** Prompt edit; costs `dialogue_prompt_hash` comparability.
**To fix:** Specify a deterministic precedence, or merge the two systems (see ISSUE-328).

## ISSUE-328: two independent 5-band tone systems do the same job from different data
**Found:** 2026-09-07, during full-review (L12-05)
**Severity:** P2
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Rules 2 and 16)
**Description:** Rule 2 (PLAYER REPUTATION) and Rule 16 (STANDING) each define a 5-band tone system from a different data source, leaving the model to reconcile them per turn. L12 recommends a structural server-side merge over prompt-side arbitration — resolve the bands in code and hand the model one answer.
**Why deferred:** Behavioural change plus prompt-hash cost; needs sign-off.
**To fix:** Merge the bands server-side, pass one resolved tone into the prompt, delete the second rule.

## ISSUE-329: three rules restate the same anti-hallucination policy for three context objects
**Found:** 2026-09-07, during full-review (L12-06)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Rules 5, 14, 17)
**Description:** One policy stated three times, costing static prompt tokens on every turn without adding constraint.
**Why deferred:** Prompt-hash comparability cost.
**To fix:** Collapse into one rule that names the three objects.

## ISSUE-330: Output-rules prose restates constraints the JSON schema already enforces
**Found:** 2026-09-07, during full-review (L12-07)
**Severity:** P2
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Output rules block)
**Description:** The block restates enum and range constraints the generation schema enforces structurally. Free to cut in the sense that it does not affect decoded tokens — but it is static prompt tokens on every turn, and it is exactly the "should be structural, not textual" class.
**Why deferred:** Prompt-hash comparability cost.
**To fix:** Delete the restated constraints, keep the rules the schema cannot express.

## ISSUE-331: Rule 8's guard/soldier register carve-out plausibly contributes to ISSUE-128
**Found:** 2026-09-07, during full-review (L12-10)
**Severity:** P3
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml` (Rule 8)
**Description:** ISSUE-128 records `captain_sorn` inventing a warlord name ("bjorn") under adversarial pressure. L12 judges Rule 8's register carve-out a plausible contributing factor but explicitly **not** a sufficient explanation. Graded **Suspected**.
**Why deferred:** Unconfirmed; and the judged scorers that would evaluate a fix are currently REFUSED.
**To fix:** Investigate alongside ISSUE-128 once the scorer layer is trustworthy.

## ISSUE-332: two dead prompt YAMLs, and `llm_config.yaml` still names the dead `v1`
**Found:** 2026-09-07, during full-review (L12-15)
**Severity:** P3
**Where:** `src/npc_engine/prompts/quest_generation/slot_fill_v1.yaml`, `prompts/quest_generation/flavor_v1.yaml`; the engine's `llm_config.yaml`
**Description:** Both files are superseded by hardcoded v2 loads and are loaded by nothing. The engine's `llm_config.yaml` still declares the dead `v1` prompt name. (Note `escort_npc.yaml`/`fetch_item.yaml` are loaded via glob and are NOT dead despite zero literal-name hits.)
**Why deferred:** Deleting files is ask-gated.
**To fix:** Delete both YAMLs and correct the config's prompt name.

## ISSUE-333: `prompts/eval/tone_judge.yaml` construction weaknesses
**Found:** 2026-09-07, during full-review (L12-18)
**Severity:** P3
**Where:** `prompts/eval/tone_judge.yaml`
**Description:** Construction assessment only — no judged score cited, per the trust policy. Four of the five currently-REFUSED scorers share this one template, so its criteria clarity is a common-mode factor in the scorer-adequacy work.
**Why deferred:** The scorer layer is under repair; changing the shared template mid-repair would confound it.
**To fix:** Fold into the scorer-adequacy remediation rather than editing standalone.


## ISSUE-335: two unbounded appenders nobody has logged — `:TickLease` nodes and the `SchedulerState` tick-id array
**Found:** 2026-09-07, during full-review (L13-08)
**Severity:** P2
**Where:** `src/npc_engine/graph/` scheduler state writes
**Description:** `:TickLease` nodes accumulate without retention, and `SchedulerState` holds a tick-id **array property** that grows unboundedly and is scanned O(n) on every interval tick — so it is a performance regression as well as a storage leak. Same retention gap as ISSUE-279 (faction-standing decay, ~2,500 nodes/hour) but different nodes, so logged separately rather than folded in.
**Why deferred:** Needs a retention decision consistent with ISSUE-279's.
**To fix:** Decide one retention policy covering ISSUE-279 and both of these, then implement pruning; replace the array property with a bounded structure.

---

## Closed

---

> **Issue format:** see the template in `project-harness/CLAUDE.md` (“Issues”).
> It is deliberately NOT duplicated here. Until 2026-09-02 this file carried a copy
> inside an HTML comment opened at line 759 and **never closed**, which silently hid
> every entry below it — 46 of 78 open issues — from every rendered markdown view.
> That is how ISSUE-229 was invisible enough to be re-logged as ISSUE-257 (DEC-250).

---

## ISSUE-085: `world_state.py` uses deprecated `datetime.utcnow()` (Python 3.12+)
**Found:** 2026-06-09, during EXP-21 (W3)
**Severity:** P3 (nice-to-fix — deprecation warning only, not an error)
**Where:** `src/npc_engine/world/world_state.py` (grep `utcnow`)
**Description:** `datetime.utcnow()` is deprecated in Python 3.12 and triggers warnings in every test run. Replace with `datetime.now(timezone.utc)`.
**Why deferred:** Out of scope for EXP-21; affects test noise only.
**To fix:** `s/datetime.utcnow()/datetime.now(timezone.utc)/g` and add `from datetime import timezone` import.

---

## ISSUE-092: Redis-backed emotion (and other high-churn) store — deferred to Unity/Unreal phase
**Found:** 2026-06-10, during EXP-14 DECISIONS (DEC-084)
**Severity:** P3 (nice-to-fix — Neo4j write-through is sufficient for now)
**Where:** `src/npc_engine/engines/emotion/emotion_store.py` + any future high-churn in-memory store
**Description:** README "What's next" advertises Redis-backed emotion store. Per DEC-084 we are
using Neo4j write-through for EXP-14 slice-1. Under heavy concurrent dialogue Redis would
outperform Neo4j for sub-millisecond hot state (valence/arousal); similarly, session_store and
any tick-rate counters would benefit from Redis TTL semantics.
**Why deferred:** New infrastructure dependency (redis-py / aioredis + Docker service + config).
Blocked until the Unity/Unreal SDK integration phase, which already introduces infrastructure
changes and is a natural inflection point.
**To fix:** Add Redis adapter behind EmotionStore and SessionStore interfaces; register as a
new DI option in `api/dependency_singletons.py`; add Docker Compose Redis service.

---

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
shim in `evals/__main__.py:30-32`, and drop `"evals"` from `pyproject.toml`'s `pythonpath` so the gate
stops masking a regression. Verify `docker compose exec app python -m evals.retrieval_runner` still
runs, since ISSUE-131 makes it the only way to run retrieval against Neo4j.

## ISSUE-134: the loop's skip-regex matches "ask-gate" inside a sentence that negates it
**Found:** 2026-08-07, while readying the queue for the metrics program
**Severity:** P2 (annoying — silently withholds work from the loop, and says the opposite of what it means)
**Where:** `scripts/_roadmap_cursor_core.py:39` (`ASK_GATE_RE = re.compile(r"ask-gate", re.IGNORECASE)`),
applied over a whole task block by `_flags_for` (`:130-140`).
**Description:** The flag scan is a bare substring match over the task's entire body, so any prose that
merely *mentions* the token flags the task. EVAL-P1.2's body ended with "*Not an ask-gate:* `PROMPT_VERSION`
has no callers outside its own module" — an explicit statement that no human decision was pending — and the
regex matched the two words inside it. The task was therefore skipped by every unattended session for the
whole program, for a reason that asserted the opposite of what the sentence said. The same trap applies to
`LIVE_RE` (`\(live[;,)\s]`) and to any future flag token: a task that discusses a gate is indistinguishable
from a task that has one. Nothing surfaces this — `--list-flagged` prints `EVAL-P1.2  ask-gate`, which looks
entirely correct.
**Why deferred:** The immediate blockage is cleared by rewording EVAL-P1.2 (done 2026-08-07), and a parser
change touches the one module that both the loop and the `/expand-linear-next` skill depend on. Rewording is
also arguably the right fix — prose that discusses a gate is genuinely ambiguous to a regex.
**To fix:** Prefer an explicit, unambiguous marker over prose sniffing: require a dedicated token such as a
leading `⛔ ask-gate` on its own line (mirroring how `⏸️` already works as `DEFERRED_TOKEN`), and match only
that. Keep the current regex as a deprecation warning surfaced by `--verify` for one cycle so no existing
gated task silently becomes actionable. Add a test asserting that a body containing "not an ask-gate" is
**not** flagged. Until then, never write the literal token in a task body unless the task really is gated.

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
(same GET, same `preflight_belief_substrings` fallback to `expected_fact_substrings`) and skip building any
record — deterministic or judged — for a `learned_from_player` case whose fact isn't persisted yet. Add a
regression test with a mocked "belief not found" response asserting zero records are produced for such a case.

## [WONTFIX] ISSUE-138: `evals/compare.py` exceeds the 300-line file limit
**Found:** 2026-08-08, during EVAL-P10.2
**Severity:** P3 (nice-to-fix)
**Where:** `evals/compare.py` (412 lines after EVAL-P10.2; was 366 before; ~520 after EVAL-P18.3)
**Description:** `compare.py` pre-existed the 300-line hard limit. EVAL-P10.2 added `_detect_evasion` (~35 lines), pushing it to 412. A split would be natural: extract evasion detection + `_build_delta_table` into `evals/evasion.py`, leaving compare.py as an orchestration-only module.
**Why deferred:** Pre-existing violation aggravated by this task; split is out of scope for EVAL-P10.2.
**To fix:** Extract `_detect_evasion`, `_change_direction`, and `_build_delta_table` into `evals/evasion.py`; import them from `compare.py`.
**Closed:** 2026-08-12, EVAL-P18.3 — **DEC-170** decided not to split (mirrors DEC-169's same-day precedent for `evals/calibration.py`): one coherent pipeline, no external consumer of `CompareResult`/`RunMeta` beyond this module and its test file, eval harness not held to `src/`'s layering constraints. Reopen if the file passes 800 lines or a second consumer needs evasion/comparability logic independently — see DEC-170's Future trigger.

## ISSUE-137: `evals/summary.py::summarize` exceeds the 40-line function limit
**Found:** 2026-08-08, during EVAL-P10.1
**Severity:** P3 (nice-to-fix)
**Where:** `evals/summary.py:168–212` (`summarize`, 45 lines)
**Description:** `summarize` is 45 lines, exceeding the 40-line strict limit from CLAUDE.md. Introduced before EVAL-P10.
**Why deferred:** Pre-existing violation, not introduced by EVAL-P10.1. Fixing it is a separate refactor.
**To fix:** Extract battery-result filtering into a helper (e.g., `_collect_battery_stats`) to bring `summarize` under 40 lines.

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
(or create it if it doesn't exist) covering all 5 cases: `score=None`, `pass_on_yes`+True,
`pass_on_yes`+False, `pass_on_no`+True, `pass_on_no`+False. Re-run `make check-mutations` and
confirm zero survivors.

## ISSUE-144: `scripts/check_human_gates.py` has 7 lines of headroom under the 300-line cap
**Found:** 2026-08-10, during DEC-164 (interleaving the HUMAN GATE blocks)
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_human_gates.py` (293 lines of non-test code)
**Description:** The file is compliant today (293 < 300, longest function 28 < 40) but has almost no
room. The next feature — a `--why <task>` explainer, or gate-state caching — pushes it over, and
whoever hits the cap will be mid-task and inclined to shave a docstring rather than split.
**Why deferred:** Splitting a cohesive 293-line tool now would be the "artificial split" the code-style
rule warns against, and DEC-164's scope was the gates, not their file layout. Single-task focus.
**To fix:** Follow the precedent already sitting in the same directory — `roadmap_cursor.py` (CLI) over
`_roadmap_cursor_core.py` (pure logic, frozen models, no I/O). Split into
`check_human_gates.py` (argparse, `_read`, `_force_utf8_streams`, report rendering) and
`_human_gates_core.py` (`HumanGate`, `parse_gates`, `task_states`, `blocked_tasks`, `verify_gates`).
The test module already imports only the pure names plus `main`, so the split is import-path-only.

## ISSUE-176: `scripts/check_conservation.py`'s `_DEFAULT_GEN_DIR` is hardcoded to `k3_73e6c36`
**Found:** 2026-08-17, during the EVAL-P20→P24 unblock plan (Phase A, noted for Phase B3)
**Severity:** P1 (blocking) — silently audits a stale corpus after regeneration
**Where:** `scripts/check_conservation.py:34-36` (`_DEFAULT_GEN_DIR = .../evals/generations/k3_73e6c36`),
wired as a `make check` gate (`check-conservation`)
**Description:** `check_conservation.py` defaults to auditing `k3_73e6c36` when no `--gen-dir` is passed.
`make check` (and therefore `make check-label-survival`'s sibling `make check` run, and any CI-style
gate) calls it with no argument, so once `EVAL-P20.4` (regeneration #1) lands and the corpus moves to
a new `gen_id`, `make check` keeps silently auditing the old, frozen `k3_73e6c36` directory — a green
`check-conservation` after that point proves nothing about the corpus actually in use, which is exactly
the "silently worthless artifact" failure mode Program 3 exists to eliminate.
**Why deferred:** Parameterizing this is Phase B3's own precondition, not Phase A's — Phase A builds
the mechanism (label survival, trend, regression, panel wiring) without touching the corpus at all, and
fixing this before there is a new `gen_id` to point at would just swap one hardcoded default for
another guess.
**To fix:** Before firing `EVAL-P20.4`, either (a) add a small "current gen_id" pointer file (e.g.
`evals/generations/CURRENT`) that `_DEFAULT_GEN_DIR` reads, updated by the generation step itself, or
(b) drop the default entirely and require `--gen-dir` explicitly, forcing `make check`'s caller
(`scripts/Run-EvalHarness.ps1`, once it calls this rather than the standalone `check-conservation`
target) to pass the real corpus by name. (a) keeps `make check` working with no argument for the common
case; (b) is more explicit and harder to get silently wrong. Whichever is chosen, add a regression test
asserting `check_conservation.main()` refuses to default silently once the flag exists.

## ISSUE-177: no case-level metadata marks which cases are "grounded" for refusal-rate purposes
**Found:** 2026-08-17, during EVAL-P20.3's follow-on wiring (EVAL-P20→P24 unblock plan, Phase A4)
**Severity:** P2 (annoying) — blocks threading `refusal_result=` into a real `format_summary_lines` caller
**Where:** `evals/refusal_rate.py` (`score_refusal_rate` needs `npc_responses` from "grounded" cases);
no `evals/cases/*.yaml` case carries a `grounded: true`-style marker; the only existing artifact of this
shape is `evals/calibration/p04_grounded_responses.json`, a static test fixture recorded once for
`EVAL-P10.3`, not a live selection mechanism a runner could re-derive from the current case set.
**Description:** `EVAL-P20.3`'s own DONE note (2026-08-15) says threading a real caller through to
`score_refusal_rate` "is follow-on wiring work, not part of this task's Files list," because
`summarize()` classifies cases by guard/capability battery membership, not by "is this case grounded" —
that classification does not exist yet. Investigated for Phase A4 (which wired the judge panel's
`panel_agreement=` into the same `format_summary_lines` call) on the assumption it was the same shape
of task; it is not — the panel wiring needed no new classification, this one does.
**Why deferred:** Guessing at a case-subset heuristic (e.g. "all `case_pos_*` cases are grounded") risks
silently producing a wrong refusal-rate number — exactly the failure mode this whole harness exists to
prevent — without a human decision on what "grounded" means for the live case set today.
**To fix:** A human call: either (a) add a `grounded: true` field to the relevant case YAMLs (the ones
`p04_grounded_responses.json` was recorded from are a starting point) and have `runner.py`/`judge_runner.py`
select `npc_response` from those cases to call `score_refusal_rate`, or (b) derive "grounded" structurally
(e.g. any case whose expectations include an `anti_hallucination_grounded` matcher). Once decided, thread
the result into both `runner.py:404`'s and `judge_runner.py`'s `format_summary_lines` calls the same way
`panel_agreement=` was threaded in Phase A4.

## ISSUE-178: two prompt paths bypass NON_PROMPT_NODE_FIELDS and leak raw tick values
**Found:** 2026-08-17, during ISSUE-165 (tick unification)
**Severity:** P3 (nice-to-fix — no known behaviour impact now that tick values are correct)
**Where:** `src/npc_engine/retrieval/graph_rag/subgraph_retriever.py:134` and `:140`
**Description:** DEC-176 strips `emotion_updated_at_tick` and `expires_at_tick` from prompt content
via `NON_PROMPT_NODE_FIELDS`, but two item builders bypass it. The active-pledges item at `:134`
calls `serialize_json(...)` with no `strip_fields` at all *and* re-adds `"expires_at_tick"` to the
dict explicitly. The event items at `:140` pass `strip_fields=_LOW_VALUE_FIELDS`, which does not
include `tick_id`, so `Event.tick_id` reaches prompts. Both were leaking wall-clock-derived values
before ISSUE-165; they now leak correct small game ticks, which is why this is P3 rather than P1.
**Why deferred:** out of ISSUE-165's agreed scope (D1). Fixing `:134` also breaks
`tests/unit/engines/test_pledge_service.py:270-285`, which pins the current pledge-item shape, so it
needs its own test update and a prompt-determinism re-measurement.
**To fix:** pass `strip_fields=NON_PROMPT_NODE_FIELDS` (or a union with `_LOW_VALUE_FIELDS`) at both
sites, stop re-adding `expires_at_tick` in the pledge item, and update `test_pledge_service.py`.
Re-run the retrieved_context drift measurement afterwards to confirm it stays at 0.

## ISSUE-183: EVAL-P21.1/P21.2's named acceptance clauses were never exercised by the live panel run
**Found:** 2026-08-18, verifying the 2026-08-17 overnight panel run against the roadmap
**Severity:** P2 (annoying) - blocks an honest tick of two roadmap items; no wrong data
**Where:** `ROADMAP.md` EVAL-P21.1 and EVAL-P21.2 validation clauses;
`tests/unit/evals/test_judge_panel.py`
**Description:** Both clauses require behaviour the live run happened not to produce.
(1) EVAL-P21.2 requires the audited `case_neg_injection_001` false positive - mixtral alone voting
FAIL - to be **outvoted** by the panel. In the live run mixtral voted *with* the other two seats
3-0 on all three repetitions; the false positive did not reproduce. The case passes, but by
unanimity, not by the consensus rule the clause exists to test.
(2) EVAL-P21.1 requires "a judge that errors yields an explicit inconclusive, never a silent pass".
Zero of 1035 verdicts errored (0 inconclusive, no timeouts), so that path got no live evidence.
Both mechanisms are covered by fixture tests; what is missing is evidence from a real run.
**Why deferred:** neither is fixable by re-running. You cannot make a model reproduce a specific
past false positive on demand, and deliberately breaking Ollama mid-run to force an infra failure is
a fault-injection test, not an overnight pass. Re-running the panel will very likely produce the
same clean result again.
**To fix:** add a fault-injection integration test pointing one panel seat at an unreachable judge
endpoint and asserting the persisted row is `inconclusive: true, passed: false`; then either
(a) reword EVAL-P21.2's clause to accept fixture evidence for the consensus mechanism plus live
evidence that consensus ran at all, or (b) record explicitly that the clause was satisfied by
`test_single_dissenting_judge_does_not_create_a_hallucination` and note the live non-reproduction.
That is a human wording call on the roadmap, which is why this is logged rather than decided.

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
`affirms_judge` prompt iteration (ISSUE-141), and judge progress on the per-criterion breakdown
rather than the raw-agreement headline.

## ISSUE-186: `k3_73e6c36` cannot serve as an A/B baseline arm (`harness_version` and `seed` are null)
**Found:** 2026-08-18, tracing the A/B path while scoping the combined run
**Severity:** P2 (annoying) - not a defect, but a widely-held wrong assumption worth recording
**Where:** `evals/generations/k3_73e6c36/meta.json`
**Description:** The committed artifact has `config.harness_version = None` and `config.seed =
None`; it predates both EVAL-P18.1 (comparability hash) and EVAL-P20.0 (seeded generation). Any
new run carries a real `harness_version`, and `compare._comparability_error` treats a missing
value "as a value like any other for equality" (its own docstring), so `compare.py` **refuses**
every pairing of `k3_73e6c36` with a post-P18.1 run. Independently, it was generated before the
ISSUE-165 tick unification, so per DEC-186 its behaviour baseline differs from current `main` by
construction. Net: there is currently **zero** valid A/B arm on disk, and `k3_73e6c36`'s value is
as a *labelled calibration corpus* (393 human verdicts, the panel's judge-agreement evidence), not
as a performance baseline.
**Why deferred:** nothing to fix - the artifact is what it is, and EVAL-P20.4 (regeneration #1)
already exists to produce the first valid arm. Logged so the distinction between "calibration
corpus" and "A/B baseline" is written down rather than rediscovered.
**To fix:** no code change. When regeneration #1 lands, record its gen_id in ROADMAP as the
baseline arm, and stop referring to `k3_73e6c36` as a baseline.

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

## ISSUE-205: the architecture conformance gate matches concrete adapters by naive substring
**Found:** 2026-08-26, during P1 (logged in P2)
**Severity:** P3 (nice-to-fix) - false positives only; it cannot miss a real violation
**Where:** `tests/unit/conformance/` - `test_engines_do_not_import_concrete_llm_adapters`
**Description:** the gate scans engine source text for adapter names as bare substrings. The
name `ollama_adapter` contains `llama_adapter`, so any mention of the real module path - in a
docstring, a comment, or a log message - trips the check. Hit during P1: a new module's
`Used by:` docstring line naming the Ollama adapter module failed the gate, and the docstring
was reworded rather than the gate changed, because changing a conformance gate as a drive-by is
worse than working around it. Same family as ISSUE-191.
**Why deferred:** it is a test-infrastructure fix, and P1/P2 both had a one-word workaround.
**To fix:** match on parsed `import`/`from` statements (`ast.walk` for `ast.Import` /
`ast.ImportFrom`) instead of raw substrings. That also removes the need for every future
docstring to avoid naming the module it documents.

## ISSUE-207: `routine_override` smuggles a tick counter into every prompt inside a JSON string
**Found:** 2026-08-26, during P3 while applying NON_PROMPT_NODE_FIELDS everywhere
**Severity:** P2 (annoying) - a live prompt-determinism hole that the deny-list only appears
to cover
**Where:** `retrieval/context/context_utils.py:NON_PROMPT_NODE_FIELDS` (the
`expires_at_tick` entry) vs `graph/scheduling/routine_queries.set_routine_override`
**Description:** the deny-list carried the comment "`expires_at_tick` nests inside
routine_override; _clean strips by key name at any depth, so the sibling `location_id`
survives." That is false. `routine_override` is persisted as an **opaque JSON string**, not a
nested map, so `_clean` -- which walks dicts and lists -- steps straight past it. Verified live
2026-08-26: `mira_innkeeper`'s prompt carries
`"routine_override": "{\"location_id\": \"home\", \"expires_at_tick\": 3371}"`, both keys
intact, inside `npc.profile`. The comment has been corrected in place; the leak has not been
fixed. It matters because the deny-list's own docstring records that wall-clock-derived tick
fields were on their own sufficient to make 36 of 36 otherwise-identical eval records produce
different `npc_response` text (EVAL-P20.0 / DEC-176) -- and this one is invisible to the very
mechanism built to catch it.
**Why deferred:** fixing it means either parsing the string to strip inside it (a special case
in a generic cleaner) or changing how `set_routine_override` persists the property (a graph
schema change, which CLAUDE.md requires approval for). Neither belongs in a payload-stripping
pass.
**To fix:** preferred - persist `routine_override` as a map so the existing deny-list reaches
it, which also makes the field readable by Cypher. Cheaper alternative - drop
`routine_override` from the character payload entirely for prompt purposes; nothing in the
prompt teaches the model what a routine override is, so today it is pure noise AND pure
non-determinism. Measure the eval-record reproducibility rate before and after; that is the
metric this defect moves.

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

## ISSUE-210: no seeder creates `Need` nodes, so `npc.top_need` is structurally empty
**Found:** 2026-08-26, during P4's live verification
**Severity:** P2 (annoying) - a prompt field that is empty in 100% of rows for a data reason
**Where:** `seeds/worlds/`, `demo_game/seeds/seed.py`; consumed by
`retrieval/context/context_builder.py:_maybe_append_top_need`
**Description:** `npc.top_need` was empty in 975 of 975 rows of the last eval transcript and
is 0/8 on the live probe after four phases of retrieval fixes. It is not a retrieval defect.
Verified directly against Neo4j 2026-08-26: `MATCH (n:Need) RETURN count(n)` is **0** and
`MATCH ()-[r:HAS_NEED]->() RETURN count(r)` is **0**. The app log confirms it from the other
side, warning on every tick that "the missing relationship type is: HAS_NEED" and "the
missing label name is: Need". `_maybe_append_top_need` and the whole needs/goals reader path
are correct and simply have nothing to read. ISSUE-163 named `top_need` as one of the empty
fields, which made it look like part of that bug; it never was.
**Why deferred:** P4 is a budget-allocation change; seeding a new node kind is a world-data
change with its own review, and it would alter every eval world's baseline mid-plan.
**To fix:** decide whether needs are part of the shipped model. If yes, seed `Need` nodes and
`HAS_NEED` edges in `seed_village_world.py` / `seed_tavern_world.py` / `demo_game/seeds/seed.py`
and re-baseline. If no, delete `_maybe_append_top_need` and the `top_need` slot from the
serializer, and stop paying for the read on every turn. Either way the prompt stops carrying a
permanently-null field. Pairs with P5, which decides slot membership anyway.
**UPDATE 2026-08-27 (planning review): there is a third option, and the data is not missing.**
The checked-in baseline holds **28 nodes labelled `need`** (lowercase) carrying `id`, `kind`,
`level`, `decay_rate` and a `character_id` property — but **zero `HAS_NEED` edges**. The
reader queries `(:Character)-[:HAS_NEED]->(:Need)`. Root cause is ISSUE-213: the label is
wrong, not the data. So "seed or delete" is a false choice — fixing the label resolver plus
writing the edges is the cheaper third path. It is still a graph-schema-shaped change that
mutates the baseline fixture, so it must not land between P9 and P10. See ISSUE-213.

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

## ISSUE-213: `BASE_NODE_LABELS` ignores the registry's declared `node_type`, so most node kinds land under a lowercase label
**Found:** 2026-08-27, during the P8 planning review (ISSUE-210 root-cause trace)
**Severity:** P2 (annoying — silently splits a node kind into two labels; readers find nothing)
**Where:** `graph/generic/generic_graph_utils.py:20-28` (`BASE_NODE_LABELS`) and `:101`
(`resolve_node_label`); the declared truth it ignores is in
`type_registry/base_nodes/*.yaml` (`node_type:`)
**Description:** `resolve_node_label` lowercases the requested type and looks it up in
`BASE_NODE_LABELS`, which has **seven** entries (character, event, faction, item, location,
quest, world_state). Everything else falls through to `return node_type` — the registry KEY,
which is the lowercase filename stem. Meanwhile every registry file declares the correct label
in its own `node_type:` field (`need.yaml` says `node_type: Need`), and **nothing reads it**.
Verified in the checked-in eval baseline: 28 nodes labelled `need`, 1 labelled `belief`
alongside 44 labelled `Belief`, plus `leverage` and `army`. The readers query the PascalCase
label (`need_queries.py:33` matches `(:Character)-[:HAS_NEED]->(:Need)`), so those 28 nodes
are invisible to the engine — this is the root cause behind ISSUE-210, and `Belief` is
already split across two labels. Separately, the `need` nodes carry a `character_id` property
where the reader expects a `HAS_NEED` edge, so fixing the label alone is not sufficient for
`top_need`.
**Why deferred:** it is a graph-label change affecting every generic-write node kind and it
mutates `evals/fixtures/eval_world_baseline.json`, so it cannot land between P9 and P10
without invalidating the regeneration baseline. It is also not on the critical path for the
A/B measurement — `top_need` is one tier-B slot.
**To fix:** make `resolve_node_label` read the registry's declared `node_type` (falling back to
`BASE_NODE_LABELS`, then to the key), add a contract test asserting every
`base_nodes/*.yaml` `node_type` round-trips through `resolve_node_label`, and decide
separately whether the existing lowercase nodes are migrated or re-seeded. Do it AFTER the
regeneration, or before P8 — never in between. Pairs with ISSUE-210.

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
JSON string, so the output is always parseable; keep the `...[compressed]#<sha>` marker
inside the truncated value. Add a property test over `_ESSENTIAL_FIELDS` asserting
`json.loads` succeeds for every node type at every target size. Do it with P10's trim,
where compression actually fires, not before.

## ISSUE-215: nothing stops a tool from rewriting line endings across the repo
**Found:** 2026-08-27, during P8 close-out (self-inflicted, repaired in c69465e)
**Severity:** P3 (nice-to-fix - no behaviour changes; it destroys diff reviewability)
**Where:** repo root - no `.gitattributes`; `git config core.autocrlf` is `false`
**Description:** the working tree is a MIX of line-ending styles, and two files are mixed
internally (`DECISIONS.md` 5,029 CRLF / 588 LF; `ISSUES.md` 1,439 / 39). With no
`.gitattributes` and `core.autocrlf=false`, git stores whatever bytes a tool writes. Any
edit made with Python's default text mode on Windows silently converts a whole file to
CRLF, and the commit then shows every line as changed.

**Update 2026-08-27 (P9).** Broader than filed: it is not only Python text mode. In one
session BOTH `sed -i` (LF-ified a 223-line CRLF test module, turning a 19-line rename into
a 451-line diff) and the **Write tool** (LF-ified a 159-line CRLF route, turning a 120-line
edit into a 323-line one) did it, in opposite directions on different files because the
repo is mixed. The Edit tool preserves endings; Write and sed do not. Until the
`.gitattributes` fix lands, the practical mitigation is to run `git diff --stat` before
every commit and confirm the numbers match the size of the intended change — that caught
both instances here before either reached a commit.

Happened for real in P8: `git diff a2b71f5..HEAD` reported 5,792 insertions / 2,709
deletions across 59 files, in which system_v1.yaml's 13 genuinely-changed lines were
unfindable. Repaired in c69465e (per-line for the two internally-mixed files), but only
after the fact - and a reviewer who had read the intermediate commits would have been
reading noise. This is ISSUE-139's failure mode in a different costume: the commit does
not say what changed.
**Why deferred:** the fix is a repo-wide `.gitattributes` with `* text=auto` plus a
one-off `git add --renormalize .`, which rewrites the stored bytes of essentially every
file in the repo. That is a large, history-noisy commit with checkout-time consequences,
and it must not land inside a phase that is gating a regeneration - it would collide with
exactly the diff-reviewability it is meant to protect.
**To fix:** after P10's regeneration, add `.gitattributes` (`* text=auto`, plus `binary`
for the fixtures), run `git add --renormalize .` as its own commit with no other content,
and confirm `evals/fixtures/eval_world_baseline.json` is byte-stable across the
renormalisation - a fixture whose bytes move invalidates comparability.

## ISSUE-221: the eval world is not quiescent, so the RAG scope drifts while the corpus is frozen
**Found:** 2026-08-27, during P9 remediation supply measurement (DEC-214)
**Severity:** P2 (annoying) - any measurement quoting `scope` is not reproducible
**Where:** `src/npc_engine/graph/graph_rag_queries.py::get_rag_scope_ids_for_npc`, and
whatever writes `Quest` nodes while the app idles
**Description:** immediately after `make eval-world-reset`, with no dialogue turns and no
manual ticks, `captain_sorn`'s 1-hop retrieval scope grows continuously. Measured with
`make eval-supply-report` at three points minutes apart:

    captain_sorn scope   30  ->  49  ->  52  ->  54
    captain_sorn rag_supply  5  ->   5  ->   5  ->   5
    corpus              51  ->  51  ->  51  ->  51

Labelling the scope by node type shows what fills it: **41 of the ~54 nodes are `Quest`**,
against 4 Character, 2 Belief, 2 Memory, 1 each of Location/Goal/Faction/Event/Secret.
Quests are not an embeddable type, so the corpus intersection — the quantity that actually
bounds tier-B retrieval — is unaffected, which is why `rag_supply` is pinned at 5 while
`scope` triples.

Two consequences, one benign and one not:
  * BENIGN: every supply number DEC-214 records is stable, because it records the corpus
    intersection and not the scope.
  * NOT: DEC-213 recorded `captain_sorn scope 23` on what it called a clean baseline and
    this session measured 30 on one. Neither is wrong; the quantity simply is not stable,
    and any future entry quoting it will disagree with any other. DEC-210 freezes the
    CORPUS for the duration of a run; nothing freezes the GRAPH.
**Why deferred:** finding out what writes the Quest nodes, and whether it should, is a
scheduler/quest-engine investigation, not a retrieval one. It changes no measurement
DEC-214 relies on, and P10's own preconditions are about the corpus rather than the scope.
**To fix:** identify the writer (start with the tick scheduler and `engines/quest`), decide
whether idle quest generation is intended at all, and if it is, either exclude `Quest` from
`_CYPHER_RAG_SCOPE_IDS` or stop quoting raw scope size as a measurement. Add a test that
asserts the scope is stable across two reads with no intervening write.

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

## ISSUE-226: nothing identifies which build the running container came from
**Found:** 2026-08-27, during P10 precondition verification (DEC-215 gate 2)
**Severity:** P3 (nice-to-fix — the gate is satisfiable another way, but not the way it is
written)
**Where:** `GET /health`, which returns `{"status":"ok","version":"dev"}`
**Description:** P10's precondition table states gate 2 as "running image == built image,
checked by `/health` vs `git rev-parse --short HEAD`". `/health` reports the literal string
`"dev"` and carries no commit, build time or image digest, so that comparison cannot be
made. Nothing else exposes build identity either: `GET /v1/admin/system/metrics` returns
counters only.

The gate was satisfied in P10 the only way available — by rebuilding immediately before
measuring (`docker compose up -d --build app`, container recreated, exit 0) and recording
that. That is evidence of provenance by construction rather than by verification, and it
cannot detect the specific failure the gate exists to catch: an operator who forgets the
rebuild and measures a stale image. This project's notes call that "the classic false
negative on this project", and there is currently no way to check for it.
**Why deferred:** it is a src/ change to the health route inside a phase whose gates
re-run on any src/ change, and P10 had a sound alternative (rebuild-then-measure in the
same sequence, recorded).
**To fix:** bake the commit sha into the image at build time (a `GIT_SHA` build arg into
an env var) and return it from `/health` alongside `version`. Then gate 2 becomes a real
comparison. Add a test that `/health` reports something other than a hardcoded literal
when the env var is set.

## ISSUE-228: gossip distortion does not compound across hops
**Found:** 2026-08-28, during the 2026-08 review remediation triage
**Severity:** P1 (blocking)
**Where:** `src/npc_engine/graph/gossip/gossip_batch_queries.py:29-47`
**Description:** `CYPHER_BATCH_EVENT_TRUST` returns `best_event.summary` — the canonical Event node's
text — rather than the sharer's own `distorted_summary`, which `CYPHER_BATCH_PROPAGATE_KNOWLEDGE`
does write to the KNOWS_ABOUT edge. Every hop therefore distorts the original, so the signature demo
feature is a no-op; the chain looks right only because it is hand-seeded. Separately the
`MERGE ... SET` overwrites existing edges unconditionally: `old_henryk`, seeded at distortion_level
70, reads 0 at tick 600 — running the world erases the seeded demo. Re-verified by reading the Cypher
at HEAD.
**Why deferred:** sequenced to R3.3, behind R2 — fixing gossip shifts eval golden strings and gossip
determinism fixtures, and the instrument that would verify the fix is itself broken (ISSUE-229).
**To fix:** relay the sharer's `distorted_summary` with `e.summary` as fallback; use `ON CREATE SET`
for the distortion fields or guard on higher incoming distortion. Proof:
`test_distortion_compounds_across_hops` — assert hop-2 level strictly exceeds hop-1; today equal.

## ISSUE-230: the Neo4j-unavailable fallback contract is unimplemented at every hop
**Found:** 2026-08-28, during the 2026-08 review remediation triage
**Severity:** P2 (annoying)
**Where:** `utils/errors.py:54,301`, `api/errors/exception_handlers.py:113-120`,
`engines/dialogue/degradation.py:107,119`
**Description:** CLAUDE.md declares (strict) "Neo4j unavailable → raise GraphUnavailableError →
API 503". Re-verified at HEAD: `grep -rn "raise GraphUnavailableError" src/` returns **0 rows**, and
`grep -rn "503" src/npc_engine/api/` returns **0 rows**. `register_exception_handlers()` registers
four handlers, none for it, so the catch-all returns 500. `TokenBudgetExceededError` subclasses bare
`Exception`. **Dependency the review missed:** `degradation.py:107,119` are bare `except Exception`
blocks that log and fall through to a canned 200, so a newly-raised `GraphUnavailableError` would be
swallowed before any handler saw it — the degradation fix must land first or in the same change.
**Why deferred:** sequenced to R3.1→R3.2; the regression guard needs Neo4j in CI (R2.2).
**To fix:** narrow the degradation catches; raise on driver `ServiceUnavailable`/`SessionExpired`;
register a 503 handler; make `TokenBudgetExceededError` structured. Proof:
`test_neo4j_outage_returns_503` — stop the container, POST dialogue, expect 503; today 500.

## ISSUE-233: eight integration tests fail — the first ever run of the suite
**Found:** 2026-08-28, immediately after ISSUE-232 made bolt reachable from the host
**Severity:** P1 (blocking) — unknown-severity product defects in shipped engine behaviour
**Where:** `tests/integration/` — faction, faction-gossip, quest lifecycle, reputation, scheme
**Description:** With Neo4j reachable, `pytest tests/integration` returns **35 passed, 8 failed**
(109 s, re-measured 2026-09-01 by R2.2). The passing ones have always skipped and pass on their
first real execution. The 8 below have never been evaluated by anyone.

**Corrected 2026-09-01 (R2.2, settling ISSUE-236):** this entry originally listed **nine**,
including `test_faction_integration.py::test_set_standing_independent_directions`. That test
**passes** on re-measurement, so the real count is 8 and the list below has been narrowed to
match. `.loop-state/gate_baseline.json`'s 8 was right; this entry's 9 was the stale one. The 8
are now the committed allowlist in `scripts/integration_baseline.txt`, enforced on every push by
`make check-integration-baseline` — so they can no longer grow silently while triage waits.

- `test_faction_gossip_integration.py::test_same_faction_pairs_rank_higher_than_strangers`
- `test_faction_gossip_integration.py::test_hostile_pairs_rank_lower_than_neutral_pairs`
- `test_faction_integration.py::test_remove_member_raises_when_not_a_member`
- `test_faction_integration.py::test_remove_controls_raises_when_no_edge`
- `test_quest_lifecycle_integration_v14.py::test_quest_lifecycle_offer_to_completion_and_rewards`
- `test_reputation_integration.py::test_reputation_context_included_above_threshold`
- `test_scheme_advance_tick_integration.py::test_advance_creates_covert_event_and_step`
- `test_scheme_detection_tick_integration.py::test_witnessed_scheme_is_discovered`

**One was investigated and is a genuine product defect**, not a fixture problem:
`test_remove_member_raises_when_not_a_member` fails `DID NOT RAISE FactionMembershipError` —
`FactionService.remove_member()` silently no-ops when the character is not a member, where the
contract says it raises. The other **seven are untriaged**: they may be defects, stale test
expectations, or missing fixtures. Do not assume either way without opening each.

This is CR-L14-02 realised. That finding showed the graph read layer could be gutted to constants
with `make check` staying green; this is the same hole from the other side — the tests that would
have caught these ran for no one, and the skip reported nothing.
**Why deferred:** out of R0's scope (a security fix plus the port mapping that exposed this).
Triage belongs in R3 alongside the other product-correctness work.
**To fix:** triage all eight — defect, stale expectation, or fixture gap — one line each. Fix the
defects; delete or correct the stale expectations. Then wire the suite into CI (R2.2) so the
result cannot go unobserved again. Run with:
`docker compose -f docker-compose.yml -f docker-compose.test.yml up -d` then
`NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j NEO4J_PASSWORD=password python -m pytest tests/integration`

---

### Triage, 2026-09-01 (R3.6) — all eight classified, no behaviour changed

Re-measured this session: `8 failed, 35 passed, 0 skipped in 96.03s`, identical to the committed
allowlist. Classification per the standing rule — **report only, no test edited, no code fixed.**

**DEFECT (2) — one shared root cause.**

1. `test_faction_integration.py::test_remove_member_raises_when_not_a_member` —
   `Failed: DID NOT RAISE FactionMembershipError`.
   `faction_writer.py:39` ends `RETURN count(r) AS deleted`. A Cypher aggregation with no grouping
   key returns **exactly one row always**, `deleted = 0` when nothing matched, so
   `result.single()` at `faction_writer.py:138` is never `None` and the
   `if record is None: raise` guard at `:139-144` is **unreachable code**. The correct check is
   `record["deleted"] == 0`. Measured against the live DB, not inferred: running that Cypher
   against ids guaranteed absent returns `[{'deleted': 0}]`, while the same `MATCH` without the
   aggregation returns `[]`.
2. `test_faction_integration.py::test_remove_controls_raises_when_no_edge` —
   `Failed: DID NOT RAISE FactionNotFoundError`. Identical defect, same shape:
   `faction_writer.py:61` `RETURN count(r) AS deleted`, dead guard at `:216-218`.

This supersedes this entry's earlier note that `remove_member()` "silently no-ops". It does, but
the cause is not a missing check — the check is present and structurally unreachable. Both fix in
one line each. Fixing them drops 2 ids from `scripts/integration_baseline.txt` via
`make check-integration-baseline-update`.

**FIXTURE GAP (3).**

3. `test_faction_gossip_integration.py::test_same_faction_pairs_rank_higher_than_strangers` —
   `AssertionError: unfactioned pairs not found in results; assert []` at `:148`.
   The test seeds 4 characters into a **shared, unscoped** database and then calls
   `select_pairs(repo=repo, max_pairs=20, ...)` at `:133`, which ranks globally. Measured against
   the live DB this session: `max_pairs=20` returns **exactly 20** (cap-bound) while `max_pairs=500`
   returns **36** — so 16 candidate pairs are being truncated away, and the test's equal-`gossipy`
   unfactioned pairs are among them. The DB holds 23 Characters and 10 Factions from other tests.
   Not a product defect: the same-faction pair the test cares about *did* rank (the assert at `:147`
   passes). To fix: scope selection to the test's location, or raise the cap above the global
   candidate count.
4. `test_faction_gossip_integration.py::test_hostile_pairs_rank_lower_than_neutral_pairs` —
   `AssertionError: hostile pair not found in results; assert []`. Same mechanism, same file, same
   `max_pairs` truncation.

   **Re-measured 2026-09-04 on the clean M1.3 corpus — this does NOT clear with the wipe.** The
   M1.3 plan predicted both tests would go green once the corpus shrank, on the premise that
   `select_pairs` ranks over a "graph-wide unscoped candidate set" that the 23,375 leaked Quest
   nodes were crowding. That premise is wrong. `fetch_gossip_pairs`
   (`graph/gossip/gossip_queries.py:142`) returns **co-located** active non-player NPC pairs only,
   so Quest and TickLease nodes were never candidates and their removal changes nothing. Measured
   against the freshly restored 250-node fixture: 23 Characters, and **18 seeded co-located pairs**
   (`loc_tavern` 5 chars → 10 pairs, `loc_market_square` 3 → 3, `loc_guard_barracks` 3 → 3,
   `tw_tavern` 2 → 1, `vw_gate` 2 → 1). Each test then adds 4 characters at one fresh location,
   contributing C(4,2) = **6 more**, for 24 candidates against `max_pairs=20` — and the hostile
   pair is by construction the lowest-weighted, so it is exactly the one truncated. The fix
   remains as stated above (scope to the test's location, or raise the cap); the corpus is not
   the variable. Both ids stay in `scripts/integration_baseline.txt`, which remains at 3.
5. `test_scheme_detection_tick_integration.py::test_witnessed_scheme_is_discovered` —
   `assert 0 == 1`. **Ordering bug in the test, not the engine.** `:89-92` calls `upsert_scheme()`
   *before* `_setup()` at `:94` creates the Character node. `scheme_writer.py:36-37` is
   `MATCH (c:Character {id: $npc_id}) MERGE (c)-[:EXECUTES_SCHEME]->(s)` — with no Character the
   `MATCH` yields nothing and the edge is **never created**, leaving an orphaned Scheme.
   `scheme_reader.py:51` then opens with `MATCH (c:Character)-[:EXECUTES_SCHEME]->(s:Scheme)`, finds
   nothing, and returns 0. Cadence is not the cause: `SCHEME_DETECTION_TICK_INTERVAL = 7`, tick 14,
   `14 % 7 == 0`; `SCHEME_DISCOVERY_MIN_STEPS = 2` and `_setup` creates 2 steps. Swap the two calls.

**STALE EXPECTATION (2).**

6. `test_quest_lifecycle_integration_v14.py::test_quest_lifecycle_offer_to_completion_and_rewards` —
   `ValueError: QuestLifecycleEngine requires a TypeRegistry injected via __init__`.
   The test constructs `QuestLifecycleEngine(settings=settings)` at `:43` with no other argument,
   but `quest_lifecycle_engine.py:64-72` documents `registry`, `quest_repo` and `clock` as
   **required** and raises when any is `None` (DEC-122 / SEV-24, ISSUE-165). The test predates that
   DI refactor and was never updated — it could not be, because it had never run. Update the
   construction; the assertions below it are untested and may reveal more.
7. `test_reputation_integration.py::test_reputation_context_included_above_threshold` —
   `AssertionError: assert 'allied' == 'friendly'` at `:223`.
   `reputation_queries.py:58-72` defines `_LABELS` as **exclusive upper bounds** —
   `(20,"neutral"), (50,"friendly"), (101,"allied")` with `if standing < threshold: return label`.
   So `friendly` is `[20, 50)` and `allied` is `[50, 101)`, and standing 50 correctly returns
   `allied` under that convention. The test asserts the boundary is inclusive-friendly.
   **The code is internally consistent; the test asserts the only other reading.** No spec states
   which convention is intended, so this needs a one-line product decision before either is
   changed — do not "fix" it by editing whichever artifact is cheaper.

**UNRESOLVED — mechanism narrowed, cause not proven (1).**

8. `test_scheme_advance_tick_integration.py::test_advance_creates_covert_event_and_step` —
   `assert 0 == 1` at `:105` on `result["advanced"]`.
   Every gate was checked and none explains it: `SCHEME_ADVANCE_TICK_INTERVAL = 5` with tick 10 is
   on-cadence; `MAX_SCHEME_STEPS = 5` > the scheme's `step_count` 0, so it is eligible;
   `SCHEME_ADVANCE_MAX_PER_TICK = 10` does not truncate. The test's own asserts at `:92` and `:94`
   pass, proving the scheme **is** active and visible **to the test's session**. `run_tick` reads
   through `Neo4jSchemingRepository`, which opens its **own** session
   (`scheming_repository.py:36` "session-per-call"). So the surviving hypothesis is that the repo's
   independent session does not observe the write committed on the test's session — a cross-session
   visibility / causal-bookmark gap — which would make this a fixture gap rather than an engine
   defect. `_advance_one` returning `False` on an unresolvable `get_npc_location_id` is the same
   hypothesis at a second read site. **Not confirmed.** To settle it: log or assert what
   `repo.get_all_active_schemes_with_steps()` returns from its own session immediately before
   `run_tick`. Deliberately left unclassified rather than assumed.

**Summary:** 2 defects (one root cause), 3 fixture gaps, 2 stale expectations, 1 unresolved.
The 2 defects and 3 fixture gaps are safe to fix. Item 7 needs a product decision. Item 8 needs one
more measurement. None was fixed here — this task changes only this file.

---

### R3.6 TRIAGE — 2026-09-02, report only, nothing changed

Re-measured with the documented invocation (`docker compose -f docker-compose.yml -f
docker-compose.test.yml up -d neo4j`, then `NEO4J_URI=bolt://localhost:7687 NEO4J_USER=neo4j
NEO4J_PASSWORD=password make test-integration`): **8 failed / 35 passed**, reproducing the
baseline exactly. Note the env vars are load-bearing — without them the suite reports
"9 passed, 34 skipped" and looks green while testing nothing.

The eight failures collapse into **five causes**, three of which are already inside R3's scope:

| # | Cause | Failing tests | Evidence | Lands in |
|---|---|---|---|---|
| **A** | **Faction error contracts are not raised.** Two remove-paths return normally where the test expects a typed error. | `test_faction_integration.py:153`, `:227` | `DID NOT RAISE FactionMembershipError`; `DID NOT RAISE FactionNotFoundError` | **R3.2** — same family as the Neo4j→503 contract: a documented error that no code raises |
| **B** | **Two scheme ticks produce nothing.** Both assert one row and get zero. Likely one shared cause (a tick that silently no-ops), to be confirmed — not assumed. | `test_scheme_advance_tick_integration.py:105`, `test_scheme_detection_tick_integration.py:104` | `assert 0 == 1` in both | **R3.4** — the general form is R3.4(b), `tick_scheduler.py:530` silently no-opping a `None` slot |
| **C** | **Faction-aware gossip pair selection omits expected pairs.** | `test_faction_gossip_integration.py:148`, `:200` | `unfactioned pairs not found in results`; `hostile pair not found in results` | new — nearest to ISSUE-228 (gossip), sized S–M |
| **D** | **`QuestLifecycleEngine` is constructed without its `TypeRegistry`.** Raised from product code, but the defect is at the construction site. | `test_quest_lifecycle_integration_v14.py` | `quest_lifecycle_engine.py:76 ValueError: requires a TypeRegistry injected via __init__` | **R3.4** — engine wiring / composition root |
| **E** | **Reputation threshold labels disagree.** | `test_reputation_integration.py:223` | `assert 'allied' == 'friendly'` | new — S, a boundary or label-map mismatch |

**Sizing conclusion.** R3 is smaller than the eight-failure count suggests. A and D are already
R3.2/R3.4 work; B is very likely one fix for two tests; only C and E are genuinely new, and both
are S–M. **No failure indicates a structural or architectural problem** — there is no evidence
here of a design that needs rework, only of contracts not implemented and wiring not completed.

**Not done, deliberately (R3.6 is report-only):** no root cause was confirmed by debugging, and B's
"one shared cause" is a hypothesis stated as such. Confirming it is R3.4's job, not this task's.
### R3 RESOLUTION — 2026-09-02. 8 failures -> 4, and all four remaining are explained.

Measured with the documented invocation: **4 failed / 41 passed**, from 8 failed / 35 passed.
`scripts/integration_baseline.txt` ratcheted from 8 ids to 4.

**Fixed (4 tests, 3 causes).**

- **Cause A, 2 tests** — `faction_writer.py` `CYPHER_REMOVE_MEMBER` and `CYPHER_REMOVE_CONTROLS`
  end in a bare `RETURN count(r)`. A Cypher aggregate with no grouping key always returns one
  row, so `result.single()` was never `None` and both `raise` guards were unreachable. Now also
  tested `record["deleted"] == 0`. The unit tests had mocked `single() -> None`, a shape real
  Neo4j never produces for these queries, which is why they passed against the defect.
- **Cause B, detection half, 1 test** — a setup-ordering bug. The triage's prescription ("swap the
  two calls") does not work: `_setup` also creates the SCHEME_STEP events, which need the Scheme,
  while `upsert_scheme` needs the Character. Split into `_setup_characters` and
  `_setup_scheme_steps` so the real order — characters, scheme, steps — can be used.
- **Item 8 / cause B advance half, 1 test** — solved, and **not** the hypothesis recorded here.

**Item 8's cross-session hypothesis is refuted.** Measured at the test's exact state:
`get_all_active_schemes_with_steps` returns 1 from the **test's** session and 1 from the
**repository's own** session. Cross-session visibility works. The real cause is the second read
site: `get_npc_location_id` returned `None`. Isolated —

| Character as written | `get_npc_location_id` |
|---|---|
| `MERGE (c:Character {id: ...})` — as the test wrote it | `None` |
| the same node plus `SET c.is_active = true` | `'loc-...'` |

`graph_reader.py:47` filters `WHERE c.is_active = true`; `null = true` is null. `is_active` is
`required: true` on the Character contract (`character.yaml:9`) and the real seeder sets it, so
the test was creating a contract-violating node. A fixture gap. The detection fixture had the
same omission and passed only because `scheme_reader` does not filter on it — a latent invalid
fixture, now also fixed. The reader divergence behind this is **ISSUE-258**.

**Corrects the R3.6 table.** Cause B was recorded as "likely one shared cause, to be confirmed".
Confirmed false: two tests, two unrelated causes. Neither was the `tick_scheduler.py` `None`-slot
bug the table linked them to — that link was thematic, and R3.4(b) fixed it without touching
either test.

**Still failing (3), each explained and logged separately.**

| Test(s) | Cause | Issue |
|---|---|---|
| 2 faction gossip | global pair-selection truncation at `max_pairs` | **ISSUE-260** |
| 1 quest lifecycle | test targets a removed API; needs a rewrite, not a repair | **ISSUE-259** |

Closed since: the reputation label boundary, decided as `allied` by DEC-252 (**ISSUE-261**,
2026-09-02), which ratcheted `scripts/integration_baseline.txt` from 4 to 3.

Per DEC-250 the programme exit condition is zero *unexplained* failures, not zero failures. That
condition is met: every remaining failure has a measured cause and an owning issue.

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
i.e. the comparable series restarts at row 2 — or regenerate the baseline. Also sequence R2.6d
(content-addressing) so it does not split the schema mid-series.

## ISSUE-255: `make lint` does not cover `scripts/`, and there is a live violation there
**Found:** 2026-09-01, during B6 (measured-ceiling gate)
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile` `lint:` recipe (`ruff check src/ evals/`), evidence at `scripts/check_rules.py:45`
**Description:** `make lint` runs ruff over `src/` and `evals/` only. `scripts/` is excluded, and
`python -m ruff check scripts/` reports a real violation today: `F401 sys imported but unused` at
`scripts/check_rules.py:45`, untouched since `add99f16` (the LF normalization commit) and so
never gated. This matters more than it did: `scripts/` now holds the gate scripts themselves —
`check_base_rate.py`, `check_ledger_ids.py`, `check_cited_reports.py`, `check_ceiling_baseline.py`
— so the code enforcing the project's standards is the code exempt from them. Note
`tests/unit/evals/test_gate_scope.py` already fails if the recipe loses `evals/`, so the scope is
deliberately pinned; widening it is a decision, not a typo fix.
**Why deferred:** single-task focus — found while implementing B6, and adding a directory to a
gate recipe can red the build for reasons unrelated to the task in hand. It also needs a decision
about whether `scripts/` gets its own ratcheted baseline (as `evals/` did in EVAL-P15.4) or must
be clean from the start.
**To fix:** decide baseline-vs-clean, fix `check_rules.py:45`, add `scripts/` to the `lint`
recipe, and extend `test_gate_scope.py` to pin the wider scope.

## ISSUE-248: the resolved-issues archive reuses two ids and skips five
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/archive/ISSUES_RESOLVED.md`
**Description:** 157 entries are declared under 155 distinct ids. `ISSUE-035` is declared twice
(lines 280 and 749 — a reputation eval failure and a stubbed `tone_judge` matcher) and
`ISSUE-056` twice (883 and 1197 — pre-existing test failures and a `graph_rag.py` full-scan).
This violates the log's own "ID is monotonic and never reused" rule, so a cross-reference to
either id is ambiguous. Separately, ids 026-030 were never assigned in either file.
**Why deferred:** cosmetic; renumbering a resolved archive would break inbound references from
DECISIONS.md and the review documents, which is worse than the ambiguity.
**To fix:** do not renumber. Append a disambiguation note at the top of the archive naming both
reused ids and their two meanings, and record 026-030 as never-assigned so a future session does
not treat the gap as a bug.

## ISSUE-249: gate baseline comments contradict the files they describe
**Found:** 2026-08-31, during the adversarial review of the R2-remainder plan
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile:130`, `project-harness/DECISIONS.md` (DEC-236)
**Description:** `Makefile:130` says "baseline 16 in `.mypy_evals_baseline`"; the file holds `0`.
DEC-236 says `dead_keywords_baseline.txt` records 208; it holds 105, superseded by DEC-237 in the
same session. Both are stale prose next to live numbers, which is the class of drift
`make check-harness` exists to catch but does not cover here.
**Why deferred:** documentation-only; no gate behaviour is wrong.
**To fix:** correct both comments to the live values, and consider extending
`check_harness_honesty.py` to compare a ratchet comment's quoted number against its baseline file.

## ISSUE-263: integration fixtures MERGE Characters with raw Cypher, bypassing registry validation
**Found:** 2026-09-02, during ISSUE-258 (the strict `is_active` change)
**Severity:** P3 (nice-to-fix) — no longer silent after DEC-252, but still easy to get wrong
**Where:** 10 files under `tests/integration/` — `test_belief_deception_flag_integration.py`,
`test_director_tick_integration.py`, `test_faction_gossip_integration.py`,
`test_faction_integration.py`, `test_gossip_event_selection_integration.py`,
`test_player_model_tick_integration.py`, `test_relation_phase_transition_integration.py`,
`test_reputation_integration.py`, `test_scheme_advance_tick_integration.py`,
`test_scheme_detection_tick_integration.py`
**Description:** These fixtures build Characters and Factions with `MERGE (c:Character {id: $id})
SET ...` run straight against the driver. That path never reaches
`validate_node_payload`, so a fixture may omit a `required: true` field and the write
succeeds. This is the real-world trigger behind ISSUE-233 item 8: the fixture omitted
`is_active`, the node was written, and every strict reader then skipped it while the read
logged nothing above DEBUG. Confirmed as the mechanism rather than assumed —
`tests/unit/conformance/test_is_active_write_boundary.py` shows the validated path rejects
exactly that payload, and `tests/integration/test_is_active_reader_agreement_integration.py`
shows the raw path accepts it.
**Why deferred:** DEC-252 removes the silence, which was the harmful half — after it, a
Character missing `is_active` is invisible to all 37 readers instead of visible to one and
hidden from 36, so the failure is consistent and reproducible instead of a phantom. Routing
the fixtures through the validated path is a separate, larger change: each would have to
supply all 11 required Character fields, coupling every test to the node schema, and it
touches 10 files across features this task is not otherwise in. Single-task focus.
**To fix:** add one shared fixture helper (e.g. `tests/integration/conftest.py`) that builds a
registry-valid Character/Faction payload, validates it through `validate_node_payload`, and
writes the result — then repoint the 10 files at it. Once that exists, a `check-rules` pattern
banning a raw `:Character`/`:Faction` MERGE under `tests/integration/` would keep it true.

## ISSUE-262: `check-integration-baseline-update` writes CRLF into a LF-normalised file
**Found:** 2026-09-02, during R3 close-out (ISSUE-261)
**Severity:** P3 (nice-to-fix) — costs one manual normalisation per use, never wrong output
**Where:** `scripts/check_integration_baseline.py` (the `--update` write path)
**Description:** `.gitattributes` normalises the repo to LF, but the update path writes with
Python's default text mode, which is CRLF on Windows. Git then sees the whole file rewritten
rather than one line removed. Measured twice now: once during R2.2 and again ratcheting
4 → 3 for ISSUE-261, where a carriage-return grep over `scripts/integration_baseline.txt` matched
immediately after `make check-integration-baseline-update` exited 0.
**Why deferred:** the gate itself is correct and the workaround is one command; fixing the
writer is a `scripts/` change and `scripts/` is outside `make lint`'s scan set (ISSUE-255), so
it wants doing alongside that rather than as a drive-by in a product-correctness commit.
**To fix:** write the baseline with `newline="
"` (or `write_bytes`). Then check the other
`--update` writers for the same defect: `check_rules.py`, `check_test_quality.py`,
`check_engine_logs.py` and `check_migrations.py` all rewrite a tracked text file.

## ISSUE-250: two documents cite ISSUE ids that were never filed
**Found:** 2026-09-01, during R4.5 (ledger hygiene)
**Severity:** P3 (nice-to-fix)
**Where:** `project-harness/ROADMAP.md:280`, `project-harness/review-2026-08/FIX_PLANS.md:161`
**Description:** Two planning documents cite ISSUE ids as if they were filed tickets, and neither
exists in `ISSUES.md` or `archive/ISSUES_RESOLVED.md`:

- `ROADMAP.md:280` — "Trend and sequence are **510** and **808** lines of Python, not the
  1,309 / 1,714 quoted (ISSUE-242)." The measurement is correct and reproduces; only the ticket
  reference is dangling. The claim is self-contained, so nothing is lost by dropping the citation.
- `FIX_PLANS.md:161` — "The Ollama-in-CI exclusion belongs to the eval/judge path, ISSUE-240."
  Same shape: the statement stands on its own, the ticket does not exist.

Ids 239-242 were never issued in either file, so a reader chasing either citation finds nothing
and cannot tell whether the ticket was deleted, archived, or never written. `ISSUE-248` records
the same defect for 026-030 in the archive.
**Why deferred:** the fix is a prose edit in `ROADMAP.md` and `FIX_PLANS.md`, and neither file is
in R4.5's scope (`ISSUES.md`, `DECISIONS.md`, `archive/ISSUES_RESOLVED.md`, `SKILLS_QUEUE.md`,
`scripts/`). Editing a task-spec file while executing a different task breaks single-task focus.
**To fix:** delete the two parenthetical citations — the surrounding claims already carry their own
evidence — or file the two tickets retroactively. Do not renumber anything.
`make check-ledger-ids` reports both until then, and the "Never assigned" record below keeps the
gate honest without hiding them.

### Never assigned
Recorded so the gap is not read as a deletion and the numbers are not reused.

- `ISSUE-239`
- `ISSUE-240`
- `ISSUE-241`
- `ISSUE-242`

## ISSUE-252: two ungated gate scripts still default to a superseded generation
**Found:** 2026-09-01, during R4.5 (ledger hygiene)
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/check_conservation.py:29,243`, `scripts/check_label_survival.py:27`
**Description:** Both scripts hardcode `evals/generations/k3_73e6c36` as their default corpus.
The current corpus is `k3_77688e7_regen1` — the one `scripts/base_rate_baseline.json` and
`scripts/check_dead_keywords.py:43` both point at. Running either script without `--gen-dir`
therefore audits a superseded generation and reports numbers that describe nothing current.

**Corrects R4.5's spec**, which says "Fix the three scripts sharing one hardcoded stale corpus
default, of which only one is tracked." Measured 2026-09-01: it is **two**, not three.
`check_dead_keywords.py` is the third script in that family and it already points at the current
generation. Separately, R1.3 removed `check-conservation` and `check-label-survival` from
`make check`, so neither stale default is reachable from any gate — this is ungated debt, not a
live gate defect, which is why it is logged rather than fixed inside R4.5.
**Why deferred:** changing a default corpus changes what the scripts measure. Neither is gated, so
the change buys nothing today, and doing it inside a ledger-hygiene commit would mix a measurement
change into a documentation change — the attribution error the R2 program exists to stop.
**To fix:** point both defaults at the current generation, or better, derive the default from a
single shared helper so the next regeneration updates all three at once. Do it in the same commit
as the next regeneration so the before/after is attributable.

## ISSUE-259: the quest lifecycle integration test targets an API that no longer exists
**Found:** 2026-09-02, during R3.4 (triage cause D)
**Severity:** P2 (annoying) — one baselined integration failure, no product defect behind it
**Where:** `tests/integration/test_quest_lifecycle_integration_v14.py:43` and below
**Description:** R3.6 classified this as "construct the engine correctly and the assertions below
may reveal more". Measured 2026-09-02: they reveal a great deal more. The test calls
`engine.offer_quest(session=..., ...)`, `engine.accept_quest(session=...)` and
`engine.update_objective(session=...)`. `QuestLifecycleEngine` has **no `offer_quest` method at
all** — offering moved to `QuestOfferService` (`quest_offer_service.py`) — and the methods it does
have (`accept_quest:175`, `update_objective:228`, `evaluate_completion:284`, `fail_quest:340`) no
longer take a `session`, per DEC-122 / SEV-24. The composition root
(`dependencies_engines/quest.py:64`) is correctly wired; this is entirely test-side.
**Why deferred:** this is not a repair, it is writing a new integration test. Every assertion in
the body is unverified — the test has never executed — so it must be re-derived against
`QuestOfferService` + `QuestLifecycleEngine`, not patched line by line. R3.4 bounded cause D to
"fix the constructor and stop if it balloons"; it balloons.
**To fix:** rewrite against the current API: construct `QuestLifecycleEngine` with `registry`,
`quest_repo` and `clock` (see `tests/unit/engines/test_quest_lifecycle_engine.py:118`), construct
a `QuestOfferService` for the offer step, and drop every `session=` kwarg. Expect the assertions
to need re-deriving rather than porting.

## ISSUE-260: faction-aware gossip pair selection truncates the pairs its test asserts on
**Found:** 2026-09-02, during R3 (triage cause C, carried from ISSUE-233)
**Severity:** P2 (annoying) — two baselined integration failures
**Where:** `tests/integration/test_faction_gossip_integration.py:148`, `:200`
**Description:** Both tests fail with "pairs not found in results". The earlier triage measured
the mechanism: the tests seed 4 characters into a shared, unscoped database and call
`select_pairs(repo=repo, max_pairs=20, ...)`, which ranks globally. `max_pairs=20` returned
exactly 20 (cap-bound) while `max_pairs=500` returned 36, so 16 candidate pairs were truncated
away and the tests' equal-`gossipy` pairs were among them. Not a product defect: the same-faction
pair the first test cares about does rank, and its neighbouring assert passes.
**Why deferred:** out of R3's scope by DEC-250 — R3.3 is gossip, and the loop's scope excludes it.
Fixing it means either scoping selection to a location or raising the cap, and the second choice
changes ranking behaviour for real callers, so it belongs with the gossip work rather than beside
it.
**To fix:** scope pair selection to the test's location, or raise the cap above the global
candidate count. Prefer scoping — a test that depends on global DB state is order-dependent
whatever the cap.

## ISSUE-264: the documented way to drive ticks is refused in the default local config
**Found:** 2026-09-03, during the per-engine timing work
**Severity:** P3 (nice-to-fix)
**Where:** `.env:53` (`CLOCK_MODE=realtime`), `src/npc_engine/config.py:220`, `:243`
**Description:** `POST /v1/clock/advance` is the documented way to advance the world, but with
the shipped `.env` it returns HTTP 400 `CLOCK_MODE_INVALID` ("Clock can only be advanced in
game_driven mode"). `CLOCK_MODE` defaults to `realtime` and `TICK_AUTOPILOT_ENABLED` defaults
to `True`, so the autopilot owns the clock and manual advance is rejected. Measured on a live
server at tick 23169.
**Why deferred:** not a defect in the engine - both modes work as designed. It is a
discoverability problem, and changing a shipped default is a wider decision than this task.
**To fix:** say in `docs/overview.md` (or the clock route docstring) that `/v1/clock/advance`
requires `CLOCK_MODE=game_driven`, and that the realtime default hands the clock to the
autopilot at `TICK_INTERVAL_SECONDS`.

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

## ISSUE-266: the docstring audit's Layer vocabulary does not know about scheduler/
**Found:** 2026-09-03, during the per-engine timing work
**Severity:** P3 (nice-to-fix)
**Where:** `scripts/docstring_audit.py`, every module in `src/npc_engine/scheduler/`
**Description:** `scheduler` is a real layer with its own rank (5) in `scripts/check_layers.py`,
but `make check-docstrings` rejects `Layer: scheduler` as an invalid value. Every module in
`scheduler/` therefore declares `Layer: engines`, so the two gates disagree about what layer
these files are in. Reproduced by writing `Layer: scheduler` in a new scheduler module: the
gate exits 2 with "Layer: invalid value 'scheduler'".
**Why deferred:** single-task focus - this task added engine timing, and widening a gate's
accepted vocabulary touches every scheduler module's docstring.
**To fix:** add `scheduler` (and any other ranked package the audit lacks) to the audit's
accepted Layer values, then correct the seven `scheduler/` docstrings in one commit.

## ISSUE-267: no dependency lockfile; the tool choice is unmade
**Found:** 2026-09-03, during R5.5 (CR-L16-05)
**Severity:** P3 (nice-to-fix)
**Where:** `pyproject.toml`, `demo_game/requirements.txt`
**Description:** The repo has no lockfile, so `pip install -e .[dev]` is not reproducible across
machines or across time. R5.5 did the cheap 80%: the one unpinned dependency (`types-PyYAML`)
gained a bound and every ranged dependency gained a ceiling, taking the counts from
13 pinned / 7 ranged / 1 unpinned to **13 / 4 / 0**. `demo_game/requirements.txt` re-declared
`httpx` and `pydantic-settings` at looser bounds than pyproject pinned them, so installing both
files could silently downgrade the engine's pins; those two are now pinned to match.
**Why deferred:** a real lockfile needs a tool decision that is not mine to make — pip-tools
(`requirements.lock`) vs `uv lock` — and each adds a dependency and a CI step. There is also a
wrinkle worth deciding deliberately: `torch` resolves to different local versions per platform
(`2.9.1+cu128` on the dev GPU box, a `+cpu` build in the container), and a naive `pip freeze`
lock would bake one machine's CUDA build into a file the container cannot install.
**To fix:** pick the tool, generate the lock with the torch local-version segment excluded (or
with a platform-conditional constraint), make `make install` consume it, and add a gate that
reds when the lock and `pyproject.toml` disagree.

## ISSUE-268: migration Cypher lives in `scripts/`, outside the `graph/` layer
**Found:** 2026-09-03, during R5.4
**Severity:** P3 (nice-to-fix)
**Where:** all six modules in `scripts/migrations/`
**Description:** Each migration holds its own inline Cypher (constraint creation, backfills,
`MEMBER_OF` edge creation). CLAUDE.md's layer rule puts Neo4j queries in `graph/` only. The rule
is machine-checked by `check_rules`' R005, which scans `src/npc_engine` — so `scripts/` is
outside its reach and this has never reddened a gate.
**Why deferred:** R5.4's single task was down paths and an applied-state record. Its *new* Cypher
did land in `graph/infra/migration_state_writer.py`, so the debt is frozen rather than widened,
but moving six existing migrations' queries is a separate refactor with its own risk.
**To fix:** add per-migration reader/writer modules under `graph/`, leave the scripts as thin
CLI adapters over them, and widen `check_rules`' R005 scan to `scripts/` so it cannot recur.
Note that widening the scan needs ISSUE-255 (lint/type coverage of `scripts/`) settled first.

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

## ISSUE-270: `make package` output path does not match its documented location
**Found:** 2026-09-03, during R5.3
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile` `package:` target comment; `packaging/npc_engine.spec` COLLECT name
**Description:** The Makefile comment says the output is
`dist/npc_engine_server/npc_engine_server[.exe]`. The binary is actually one level deeper, at
`dist/npc_engine_server/npc_engine_server/npc_engine_server.exe`, because `--distpath
dist/npc_engine_server` and the spec's `COLLECT(name="npc_engine_server")` each contribute a
directory. Cosmetic, but it is exactly the kind of stale path claim R5.3 existed to remove.
**Why deferred:** R5.3's task was making the build work; it does, and the path is correct, only
the comment is imprecise. Changing `--distpath` would move an output other tooling may reference.
**To fix:** either set `--distpath dist` so the collected directory is `dist/npc_engine_server/`,
or correct the comment. Prefer the former; check `e2e/` and any installer script first.

## ISSUE-271: the gossip throughput NFR is still unproven at its target
**Found:** 2026-09-03, during R5.5 (CR-L12-05)
**Severity:** P3 (nice-to-fix)
**Where:** `docs/BUSINESS_REQUIREMENTS.md:34`, `scripts/bench_nfr.py`
**Description:** The stated target is >= 200 NPC pairs per gossip tick. `make bench-nfr` now
measures it, and the first measurement ever taken reports **36 pairs in 1.9 s** against a
requested `max_pairs=200`. That is a *world-size* limit, not an engine limit: the seeded demo
world does not contain 200 eligible pairs, so the tick ran out of work rather than out of time.
The target is therefore neither met nor refuted. (For contrast, the graph-size NFR now measures
27,488 nodes against a 10,000 target and is genuinely met — the review's claim that the graph
held 52 nodes does not reproduce.)
**Why deferred:** proving it needs a synthetic world with >= 200 eligible pairs, which is a
seeding task, not a benchmarking one.
**To fix:** add a scale-seed target that generates enough characters and relationships to offer
200+ eligible pairs, then re-run `make bench-nfr` and record the number.

## ISSUE-272: `make type-evals` is green only in the checkout the editable install points at
**Found:** 2026-09-03, during R5 verification
**Severity:** P2 (annoying) — `make check` cannot pass in a fresh clone or a git worktree
**Where:** `mypy.ini` (`exclude = src/npc_engine/config/`), `scripts/mypy_evals_ratchet.py`
**Description:** `python -m mypy evals/` reports two errors in any checkout that is not the one
`pip install -e .` points at:

```
src/npc_engine/retrieval/embedding/vector_store_factory.py:13: error: Module "npc_engine.config" has no attribute "Settings"
src/npc_engine/graph/infra/db.py:19: error: Module "npc_engine.config" has no attribute "Settings"
```

`src/npc_engine/config/` is a data-only directory holding `llm_config.yaml`, and it shadows the
`config.py` module as a namespace package. `mypy.ini` excludes it, but mypy's `exclude` governs
directory crawling, not modules reached by following an import — so when checking `evals/`, the
resolver finds the directory first.

**This is pre-existing and was not introduced by R5.** Measured three ways:
- Fails identically with `python_version = 3.11` and `3.14`, so the R5.2 bump is not the cause.
- Fails with R5's two new `graph/infra/migration_state_*.py` files temporarily removed.
- **Fails at the base commit `0b110021` in a clean detached worktree** — the same commit recorded
  as "`make check`, 22 targets, exits 0".

Why it looks green day to day: `python -c "import npc_engine"` resolves to the *installed* tree
via the editable `.pth`, so in that one checkout the relative `exclude` path lines up and
`config.py` wins. Every other checkout — a fresh clone, a worktree, a CI runner that installs
before checking out elsewhere — reds. `mypy src/` is unaffected and passes (630 files).

**Why deferred:** it is not R5's task, and the fix is a mypy-resolution change to a gate config
that deserves its own commit and its own counterfactual. Flagging it matters more than fixing it
in passing: this is a gate that reports green for an environmental reason, which is the exact
failure class the 2026-08 programme existed to remove.
**To fix:** stop `config/` being resolvable as a namespace package — the honest options are to
rename the data directory (e.g. `src/npc_engine/config_data/`, updating `LLM_CONFIG_PATH` and
the packaging spec's `datas`), or to give mypy an explicit module override that pins
`npc_engine.config` to `config.py`. Verify by running `mypy evals/` in a detached worktree of the
commit under test — not in the installed tree, which cannot reproduce it.

## ISSUE-273: `WorldStateQuestTrigger` writes one draft Quest per tick forever — 23,292 leaked nodes
**Found:** 2026-09-03, during the metrics-readiness review
**Severity:** P1 (blocking) — it poisons every graph-scale, retrieval and NFR measurement
**Where:** `src/npc_engine/engines/quest_generation/world_state_quest_trigger.py:80-118`
**Description:** `run_tick` generates a draft quest whenever `world_state.epoch` maps to an
archetype in `_EPOCH_ARCHETYPE_MAP`. The `world` WorldState node sits permanently at
`epoch="war"`, so the condition is true on every tick. The only guard is the instance
sentinel `self._last_triggered_tick == tick_id`, which dedupes the *same tick fired twice*
— not the same *condition* firing across successive ticks. `_pick_npc` resolves through
`get_any_military_npc` (`LIMIT 1`), so every quest names `captain_sorn`. No cap, no prune,
and `_generate_for_epoch` passes no `cause_event_id`, so no `CAUSED_BY` edge is written and
nothing can ever mark the condition consumed.

Measured live: 23,292 `:Quest {source:"generated", status:"draft"}` nodes plus 23,292
`HAS_QUEST` edges against ~681 nodes of real world content (27,529 nodes total). Only 2
quests carry a `CAUSED_BY` edge — those are `EventQuestTrigger`'s, whose
`NOT ((:Quest)-[:CAUSED_BY]->(e))` guard works correctly and matches the 2 `conflict`
events exactly. Growth begins 2026-08-27 (1,053), peaks 2026-08-29/30 (~7,100/day) and is
still live (122 on 2026-09-03). Each node is one LLM call, so this also burns generation
time on every tick.

Contrast `need_quest_trigger.py:117`, which does hold a real idempotency guard
(`has_draft_quest`) keyed on outstanding state rather than on tick identity.

**Why deferred:** raised during a review task, not patched inside it. Now **scheduled as
ROADMAP task M1.1**, which fixes the guard, adds the growth regression test, and blocks the
wipe/reseed in M1.3 behind it — a wipe before the fix refills within a day.
**To fix:** replace the tick sentinel with a state-keyed guard. Three candidates, in
preference order: (a) mirror `need_quest_trigger` — skip when the quest-giver already
holds an outstanding draft quest; (b) key on the epoch itself, so one `war` epoch yields
one quest until the epoch changes; (c) pass a `cause_event_id` and reuse the `CAUSED_BY`
guard that already works in `EventQuestTrigger`. Whichever is chosen, add a cap on draft
quests per NPC and a prune path for stale drafts, and add a regression test that runs N
ticks under a stable epoch and asserts the quest count does not grow with N. The 23,292
leaked nodes must be deleted before any graph-scale or retrieval number is measured, and
the fix must land first or the wipe refills.

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

## ISSUE-293: dialogue prompt Rule 11 references `context.available_interactions`, which no producer emits
**Found:** 2026-09-07, during measurement-remediation Phase 4 (DEC-271, probe_dialogue.py)
**Severity:** P2 (annoying — a standing prompt instruction the model can never satisfy)
**Where:** `src/npc_engine/prompts/dialogue/system_v1.yaml:181-183` (Rule 11); no producer
under `src/npc_engine/retrieval/context/` (verified: repo-wide grep for
`available_interactions` across `src/npc_engine/**/*.py` returns zero matches)
**Description:** Rule 11 reads: "When CONTEXT contains an `available_interactions` list,
you MUST surface those interactions naturally in your response and set the `action` field
accordingly." No producer, slot, or `CONTEXT_SLOTS` entry named `available_interactions`
exists anywhere in the engine. This is a dead prompt reference: the model is instructed to
act on a key that is structurally never present. (ISSUE-200's fix note references a
DIFFERENT Rule 11 gap in the same rule number — a dangling `quest_id` reference — which was
fixed by serializing `active_quest`; that fix did not touch this `available_interactions`
clause, which is a separate, still-live gap in the same rule.)
**Why deferred:** found while auditing prompt-rule coverage for probe_dialogue.py's context
metrics (measurement-remediation Phase 4), not the task fixing it. Whether the fix is
"build an `available_interactions` producer" or "delete the clause from Rule 11" is a
product decision (does the interaction-affordance feature exist yet at all?), not a bug fix.
**To fix:** decide whether NPC-offered interactions (trade, follow, etc.) are a feature this
engine already models elsewhere under a different key — if so, wire that key's producer to
populate `available_interactions` (or rename the rule to the real key); if the feature does
not exist yet, delete the clause from Rule 11 until it does.

## ISSUE-294: Memory nodes carry no source-linking property — "no memory without a source" cannot be checked as a graph property
**Found:** 2026-09-07, during measurement-remediation Phase 4 (DEC-271, probe_memory.py)
**Severity:** P3 (nice-to-fix — a measurement-design gap, not a data-integrity bug)
**Where:** `src/npc_engine/type_registry/base_nodes/memory.yaml`;
`src/npc_engine/graph/memory/memory_queries.py` (`CYPHER_CREATE_MEMORY`)
**Description:** the measurement-remediation plan's memory-probe invariant is phrased "no
memory without a source." Verified against the schema: a `Memory` node has no
`source_event_id`, `source_character_id`, or any comparable source-linking field — its
declared properties are `id, content, vividness, emotional_charge, created_at_game_time`
(required) plus `occurred_at_game_time, is_historical, last_recalled_at, subject_player_id,
recall_count, never_forget, kind` (optional). The only source-adjacent structure that
exists is the `REMEMBERS` edge (`character -[:REMEMBERS {since_game_time}]-> memory`),
which links a memory to the character who holds it, not to the event/dialogue turn that
produced it. `probe_memory.py`'s invariant (`memory_is_remembered`) checks the nearest
structural equivalent this schema supports — an orphan Memory node with no `REMEMBERS`
edge — documented inline as a deliberate substitution, not a fix.
**Why deferred:** found while building the memory probe (measurement-remediation Phase 4),
which is a measurement task, not a schema change. Adding real source-linking (e.g. a
`source_event_id` property set at creation, or a `DERIVED_FROM` edge to the consolidated
dialogue turns) is a graph-schema change requiring its own migration
(`scripts/migrations/`) and is out of this plan's scope (DEC-271; the plan's own
"Explicitly not in this plan" section excludes engine-behaviour changes).
**To fix:** decide what "source" should mean for a Memory node (the originating Event? the
consolidated dialogue turn range? the character who formed it, already covered by
REMEMBERS?), add the chosen property or edge at creation time
(`graph/memory/memory_queries.py`), add a migration for existing Memory nodes, and update
`probe_memory.py`'s invariant to check the real property instead of the REMEMBERS
substitute.

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
`label_export_stratified.IN_SCOPE_SCORERS` or `battery_trust.BATTERY_JUDGED_SCORERS` — note
those two already disagree with each other on `anti_hallucination_grounded`) or derived with a
retirement list, then have `run_calibration` take the population as a parameter rather than
deriving it inline. Whichever is chosen, make the Holm `family_size` follow the same
population, and add a test that a retired scorer's historical labels stay readable while
dropping out of the report.

## ISSUE-296: check-engine-logs is blind to the `_LOGGER` naming convention, so the ratchet undercounts
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P2 (annoying — a gate that silently measures less than it claims; it under-reports,
so it cannot produce a false failure, only a false sense of coverage)
**Where:** `scripts/check_engine_logs.py:29` —
`_LOGGER_NAMES: frozenset[str] = frozenset({"logger", "_logger", "log"})`
**Description:** `_is_logger_info` matches a call only when the receiver name is in that set,
which is lowercase-only. Ten files under `src/npc_engine/engines/` use the uppercase `_LOGGER`
convention, carrying **12** `logger.info` calls the gate never sees: `agenda/agenda_engine.py`,
`clique/clique_formation_engine.py`, `dialogue/relation_mutator.py`,
`faction_politics/faction_politics_engine.py`, `llm/prompt_eval_log.py`,
`military/military_battle_service.py`, `military/military_engine.py`,
`military/military_resource_service.py`, `story_pacing/story_pacing_engine.py`,
`succession/succession_engine.py`. The recorded baseline of 42 is therefore a count over a
subset of the engines tree, not over the tree. This surfaced because DEC-273 added `duration_ms`
to `prompt_eval_log.py` expecting the count to drop to 41; it stayed at 42, because that file's
calls were never counted.
**Why deferred:** Adding `_LOGGER` to the set changes what the gate measures and will raise the
count, requiring a deliberate baseline re-record — a gate-behaviour change that belongs in its
own task with its own review, not folded into a latency change. Single-task focus.
**To fix:** Add `"_LOGGER"` (and consider a case-insensitive match, or matching any Name whose
lowercase form is in the set) to `_LOGGER_NAMES`, re-record `scripts/engine_logs_baseline.txt`
with `python scripts/check_engine_logs.py --update`, and extend
`tests/unit/scripts/test_check_engine_logs.py` with a fixture using the uppercase receiver so
the blind spot cannot return.

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

## ISSUE-298: three of five engines never read their `llm_config.yaml` temperature
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P2 (annoying — the YAML reads as configuration but is inert, so tuning it produces
no effect and no error; `quest_generation` is the live case, tuned to 0.7 for variety and running
at 0.1)
**Where:** `src/npc_engine/engines/quest_generation/quest_generation_engine.py` (no `temperature`
parameter on `__init__`; `grep -n temperature` over the package returns nothing),
`src/npc_engine/engines/proactive_dialogue/proactive_engine.py:38-39` (`_MAX_TOKENS`/`_TEMPERATURE`
as module constants), `src/npc_engine/engines/llm/protocols.py:71-79`
(`generate_structured` has no `temperature` parameter)
**Description:** Only `chapter` (0.5) and `memory_consolidation` (0.4) actually forward their
configured temperature, because both call plain `generate`. `dialogue` (0.15) and
`quest_generation` (0.7) call `generate_structured`, which takes no temperature argument at all,
so the adapters substitute `STRUCTURED_OUTPUT_TEMPERATURE` (0.1). `proactive_dialogue` (0.8)
honours a hardcoded module constant that merely happens to equal its YAML value. So three of five
engines run at a temperature their config file does not determine.
**Why deferred:** This is not a config edit. There is no clobbered caller value to restore —
fixing it means adding `temperature` to `LLMStructuredProtocol.generate_structured`, which is an
ask-gated public-interface change across three adapters, the mock, and every hand-rolled fake in
the suite. It also risks reviving review finding SEV-27, the reason
`STRUCTURED_OUTPUT_TEMPERATURE` was introduced: before it, dialogue ran at "uncontrolled ~0.8"
and structured output was unreliable. See DEC-273.
**To fix:** Get human approval for the Protocol change; add `temperature` to
`generate_structured` across `LLMStructuredProtocol`, `OllamaAdapter`, `OpenAICompatibleAdapter`
and `MockLLMAdapter`; keep `STRUCTURED_OUTPUT_TEMPERATURE` as the default when a caller passes
none, so SEV-27's guarantee survives; give `QuestGenerationEngine` a `temperature` parameter and
`ProactiveDialogueEngine` its config values; then re-measure quest-generation variety, which is
the behaviour that motivated 0.7.

## ISSUE-299: `docs/API.md` and `docs/ARCHITECTURE.md` document WS streaming frames the code does not send
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P3 (nice-to-fix — misleads an integrator reading the published contract)
**Where:** `docs/API.md:138-149`, `docs/ARCHITECTURE.md:495-520`
**Description:** `API.md` documents `WS /v1/ws/dialogue` emitting `{"type":"action"}` and
`{"type":"expression"}` frames and a bare `{"type":"done"}`. The implementation
(`api/routes/dialogue/dialogue_ws.py:189-202`) sends neither of the first two, and its `done`
frame carries a data payload. `ARCHITECTURE.md`'s sequence diagram shows `llm.stream()` followed
by "parse full response" — a design that does not exist: the route calls the blocking
`handler.handle()` and then re-chops the finished string into words via `_iter_token_chunks`.
DEC-273 rejected wiring real streaming on correctness grounds, so the docs should be corrected
toward the code rather than the code toward the docs.
**Why deferred:** Documentation accuracy, not behaviour; out of scope for a latency change.
**To fix:** Rewrite both sections to describe what the route actually sends (a word-chunked
replay of a completed generation, then one `done` frame with the payload
`_build_done_data` assembles), and state plainly that time-to-first-frame equals full generation
latency. Cross-reference DEC-273 for why it is not real streaming.

## ISSUE-300: importing `dialogue_models` as the first `npc_engine` import raises a circular ImportError
**Found:** 2026-09-07, during the dialogue-latency work (DEC-273)
**Severity:** P3 (nice-to-fix — invisible under pytest and in the running app, which import in an
order that happens to work; it bites scripts and any future entry point)
**Where:** `src/npc_engine/retrieval/dialogue_context/dialogue_context_adapter.py:21` importing
`build_serialized_context_with_receipt` from `npc_engine.retrieval.context.context_builder`
**Description:** A standalone script whose first `npc_engine` import is
`from npc_engine.engines.dialogue.dialogue_models import DialogueResponse` fails with
`ImportError: cannot import name 'build_serialized_context_with_receipt' from partially
initialized module ... (most likely due to a circular import)`. The cycle exists today and is
merely masked by the import order pytest and `main.py` happen to establish. It was hit while
writing the DEC-273 token measurement, which had to be routed through a temporary test to obtain
two Pydantic JSON schemas.
**Why deferred:** Breaking the cycle means moving or deferring an import inside `retrieval/`,
which touches the context-assembly path — a change that deserves its own regression run, not a
drive-by during a latency task.
**To fix:** Make `dialogue_context_adapter` import `context_builder` lazily inside the function
that needs it, or move `build_serialized_context_with_receipt` to a leaf module neither package
imports at module scope. Add a test that imports `npc_engine.engines.dialogue.dialogue_models`
in a fresh subprocess as the very first `npc_engine` import, so the cycle cannot silently return.

---

## ISSUE-343: a red-gate HALT at a scar-6.10 phase boundary is swallowed — the night keeps going
**Found:** 2026-09-16, during T0.3 (RED-anchor rig: real `expand_loop.sh`, fake `claude`, forced failing test)
**Severity:** P2 (annoying) — the night-ending guard `MAX_CONSECUTIVE_RED_GATES` silently does not fire on one of the two boundary paths
**Where:** `scripts/expand_loop.sh:754` — `run_phase_boundary "$phase" || true`
**Description:** A phase boundary is reached two ways. On a `PHASE_COMPLETE` token (`case 10)`) the loop checks
`brc -eq 2` and breaks with "stopping: repeated red gates". On the scar-6.10 path — the session returns
`TASK_COMPLETE` for the phase's last task and `phase_now_complete` detects it from the roadmap — the boundary is
called as `run_phase_boundary "$phase" || true`, discarding return code 2. Observed: with `--max-red-gates 1` and
a forced HALT-class failure, the log read `HALT: 1 consecutive red phase gates` and the loop then dispatched
T4.1 anyway. `run_phase_boundary` also returns before `seed_gate_baseline` on rc 2, so the next phase runs
against the previous phase's baseline. Scar 6.10 exists precisely because a red-committed final task
suppresses the `PHASE_COMPLETE` token, so this is the path a red night is most likely to take.
**Why deferred:** found while validating T0.3 (harness-bucket routing); fixing the boundary's return handling is a
separate change to the driver and single-task focus applies. It does not block T0.3, which was validated on the
token path.
**To fix:** treat both boundary call sites the same: capture `brc` on the scar-6.10 path and `break` on 2. Add a
rig/driver test in which the fake session returns `TASK_COMPLETE` on the phase's last task with a red gate and
`--max-red-gates 1`, asserting "stopping: repeated red gates" and no further task dispatch.

## ISSUE-344: every httpx-backed LLM adapter reloads the CA bundle, ~0.5 s per construction on Windows
**Found:** 2026-09-17, during the `make check` speed-up (DEC-283)
**Severity:** P3 (nice-to-fix)
**Where:** `src/npc_engine/engines/llm/ollama_adapter.py:33` (`__init__`), and the other httpx adapters
**Description:** Each adapter builds its own `httpx.AsyncClient`, and each client calls
`ssl.create_default_context()` → `load_verify_locations` (0.57 s per call, profiled). A plain
`http://localhost:11434` Ollama never uses TLS. Tests that build a real adapter pay this cost: the `tests/unit/llm`
factory tests run ~1.7 s each, and composition-root tests build dozens of adapters.
**Why deferred:** a production-code change in `engines/llm/`. `make check` is already 112 s after DEC-283, and
xdist absorbs this cost.
**To fix:** share one module-level `ssl.SSLContext` across adapters, or pass `verify=False` only when the base URL
is `http://`. Measure `pytest tests/unit/llm --durations=10` before and after.

## ISSUE-345: `test_sev15_type_gate::test_mypy_exits_zero` runs mypy a third time inside `make check`
**Found:** 2026-09-17, during the `make check` speed-up (DEC-283)
**Severity:** P3 (nice-to-fix)
**Where:** `tests/unit/conformance/test_sev15_type_gate.py`
**Description:** `make check` already runs `make type` (mypy src/, hard gate at 0). This test shells out to mypy
again from inside the pytest run: 7.5 s under xdist load, and it is the slowest test after the lifespan fix.
**Why deferred:** removing or skipping a gate-shaped test requires a human call (DEC-224/DEC-250 gate freeze).
**To fix:** decide whether the test earns its place now that `type` is in `check` and CI runs `check` (DEC-238).
If not, delete it and cite `type`.

## ISSUE-346: `make type-demo` shares `.mypy_cache` with `make type`, so each invalidates the other
**Found:** 2026-09-17, during the `make check` speed-up (DEC-283)
**Severity:** P3 (nice-to-fix)
**Where:** `Makefile` `type-demo` / `scripts/mypy_ratchet.py`
**Description:** The same cache thrash DEC-283 fixed for `type-evals`: alternating mypy targets over different
roots in one cache dir forces rechecks (~10 s each way). `type-demo` is not in `check`, so only the CI demo job
and humans running both targets pay the cost.
**Why deferred:** outside `make check`, which is the scope of this task.
**To fix:** pass a `--cache-dir .mypy_cache/demo` through `mypy_ratchet.py` when `--target` is not `src/`, with a
test mirroring `tests/unit/scripts/test_mypy_evals_ratchet.py`.

## ISSUE-347: a WebSocket recv timeout hangs the scripted demo forever
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P2 (annoying)
**Where:** `demo_game/dialogue_ws.py:86-92`, `demo_game/runners/run_scenes.py:219`
**Description:** On `TimeoutError` from `recv(timeout=NPC_DIALOGUE_TIMEOUT_S)` the worker `break`s without putting
anything on the result queue. `StreamingDialogueBeat` then waits on `result_q.get()` with no timeout, so
`make demo-run` blocks forever instead of failing.
**Why deferred:** `scripts/demo_run_live.py` already bounds the run with a watchdog and reports a hang as a
failure, so the nightly cannot stall on it; the interactive runner is out of T2.4's scope.
**To fix:** put `("error", TimeoutError(...))` on the queue before breaking, and give `result_q.get()` a timeout.
Regression test in `demo_game/tests/core/test_dialogue_ws.py` driving a `recv` that raises `TimeoutError`.

## ISSUE-348: the demo LLM cache stores an empty reply and replays it forever
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/runners/run_scenes.py:199,231-232`, `demo_game/runners/run.py` (`LLMCache`)
**Description:** A `done` frame with zero tokens is cached as `{"npc_response": ""}`. That dict is truthy, so
`if cached:` treats it as a hit on every later `make demo-run` / `--cached` run and the beat stays empty.
**Why deferred:** `demo-run-live` bypasses the disk cache (in-memory recorder) and fails on an empty reply, so
the gate is not affected; fixing the recording cache is a separate change.
**To fix:** refuse to `put` a response whose stripped `npc_response` is empty (raise, or skip with a warning), and
treat such a file as a miss in `get`. Unit test both.

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

## ISSUE-350: the WORLD feed scene prints `?` for every event summary
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/runners/run_scenes.py` `WorldFeed.execute` (`evt.get("summary", "?")`)
**Description:** `GET /v1/admin/system/events` rows (`EventFeedRow`) carry the text as `label`, not `summary`, so
every live line reads `[world tick=3] military: ?`. The ACT 5 beat is present but its narration is blank on
screen. The unit tests mock a `summary` key, so they pass.
**Why deferred:** display-only; the event itself is created and verified by `demo-run-live`.
**To fix:** read `label`, and change the scene test's mock to the real `EventFeedRow` shape.

## ISSUE-351: several live demo beats run but do not demonstrate what their narration claims
**Found:** 2026-09-17, during T2.4 (`demo-run-live`, GREEN run at e7d4ba87)
**Severity:** P2 (annoying)
**Where:** `demo_game/runners/run.py` SCENES — ACT 4, 6, 9, 10, 11, 12
**Description:** None of these fail the run (they are not required beats), but on a clean seed:
ACT 9 reports `Graph: 1 KNOWS_ABOUT 'northern_war_begins' edges for aldric_merchant (expected 0)` and Aldric talks
about the war — the tick-10 gossip run in ACT 7 reaches him, so the anti-hallucination beat shows the opposite of
its claim (and the scene counts all his KNOWS_ABOUT edges, not the war's). ACT 6's three blind ticks (3→6) never
reach a gossip tick, so the reputation event cannot propagate before Mira speaks. ACT 10 reads
`interactions=0` while the reply claims to remember. ACT 11 finds no pending proactive intents; ACT 12 finds no
player model; ACT 4 reports the consolidation turn threshold not met.
**Why deferred:** content quality of non-required beats; T2.4 only makes the run complete and required beats
non-empty. Promoting any of these to a required beat is a separate owner call.
**To fix:** per beat — move ACT 9 before ACT 7 or scope the check to the war event; use `GossipBoundaryTick` in
ACT 6; decide which of ACT 4/10/11/12 must actually land and make them required in
`scripts/demo_run_live.py`.

## ISSUE-352: the frozen eval world baseline still seeds `garrick_safe_passage` at severity 70
**Found:** 2026-09-17, during T2.4 (`demo-run-live`)
**Severity:** P3 (nice-to-fix)
**Where:** `evals/fixtures/eval_world_baseline.json` (`garrick_safe_passage`)
**Description:** T2.4 lowered the demo seed's `garrick_safe_passage` to severity 60 so story pacing does not stay
suppressed and block ACT 5 (`tests/unit/seeds/test_seed_does_not_suppress_story_pacing.py`). The eval baseline is
a snapshot taken from the old seed and still holds 70, so an eval world restored from it stays pacing-suppressed.
**Why deferred:** the baseline is a frozen corpus; editing it by hand breaks comparability with earlier eval runs.
**To fix:** at the next deliberate corpus refreeze, regenerate with `make eval-world-snapshot` from the current
seed, and note the pacing change in that run's comparability record.

## ISSUE-353: the demo client's 15 s graph timeout is shorter than a synchronous tick with LLM quest generation
**Found:** 2026-09-17, during T2.4 (first RED attempt)
**Severity:** P3 (nice-to-fix)
**Where:** `demo_game/client.py` (`advance_clock`, `_graph_timeout`); `/v1/clock/advance` runs every due engine
in-request
**Description:** `POST /v1/clock/advance` runs quest generation, which calls the LLM with a 60 s timeout and up to
three fill attempts. With Ollama contended (a crash-looping default app hitting it), the first tick exceeded the
client's 15 s and the demo died in ACT 1 with `ReadTimeout`. It did not recur on a quiet Ollama, but the nightly
shares the GPU with whatever else is running.
**Why deferred:** did not reproduce once Ollama was uncontended; `demo-run-live` reports it as a failure with the
act, so it is visible rather than silent.
**To fix:** give `advance_clock` its own timeout sized to the engine's worst case (or pass `NPC_GRAPH_TIMEOUT_S`
through from `DemoConfig`, which `run.py` currently ignores).

## ISSUE-354: `GET /v1/admin/factions/{id}/standings` returns 500 due to response model mismatch
**Found:** 2026-09-17, during T3.3 (live stack validation)
**Severity:** P2 (annoying)
**Where:** `src/npc_engine/api/routes/faction_politics/factions.py` (`FactionStandingRow`); `src/npc_engine/graph/faction/faction_queries.py` (`CYPHER_LIST_STANDINGS`, `list_standings`)
**Description:** `CYPHER_LIST_STANDINGS` returns `properties(b)` (the full target faction dict) for the `target` column, but `FactionStandingRow.target: str` expects a faction ID string. FastAPI raises `ResponseValidationError` on every request. Pre-existing — confirmed present in `db5b2c20` (before T3.2). The demo client's `_get_faction_standings_for` returns `[]` on the 500, so the client degrades gracefully, but the sub-endpoint is non-functional. STANDS_WITH edges are seeded and reachable via Cypher; only the HTTP endpoint is broken.
**Why deferred:** pre-existing; not introduced by T3.2; client degrades gracefully; does not block the live demo.
**To fix:** either change `CYPHER_LIST_STANDINGS` to `RETURN b.id AS target, r.standing AS standing` (and update `list_standings` accordingly), or update `FactionStandingRow.target` to accept a dict and rename the field. The Cypher fix is simpler and matches the response model's intent.
