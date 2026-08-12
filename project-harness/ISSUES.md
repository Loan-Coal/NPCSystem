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

## ISSUE-153: `label_merge._refresh` never refreshes `pre_label` on drift, so a re-adjudicated
row can carry a stale reference-labeller opinion
**Found:** 2026-08-12, during EVAL-P19.0 (making `needs_review` load-bearing)
**Severity:** P3 (nice-to-fix — the secondary/pre_label axis can silently compare a fresh
human verdict against a pre_label computed from text that no longer exists)
**Where:** `evals/label_merge.py` `_MACHINE_FIELDS` (does not list `pre_label` or
`pre_labeller_model`); `_refresh`
**Description:** `_MACHINE_FIELDS` refreshes `output_text`, `scorer_verdict`, `criteria`, etc.
on every merge, but `pre_label`/`pre_labeller_model` are preserved unchanged from the
existing row — even when `output_text` drifted underneath it. After EVAL-P19.0,
`adjudicate.apply_verdict` clears `needs_review` on re-adjudication and the row re-enters the
secondary (pre_label vs human_verdict) calibration axis, but `pre_label` still reflects the
reference labeller's opinion of the **old** text, not the new one it was merged against.
**Why deferred:** Refreshing `pre_label` correctly requires re-running the reference-labeller
model against the new `output_text` — a live/expensive operation, not a pure merge, and out
of scope for EVAL-P19.0 (calibration.py / adjudicate.py / label_merge.py's WARNING path).
**To fix:** Either (a) clear `pre_label` to `None`-like/absent on drift so the secondary axis
excludes the row until a live re-label happens, or (b) add a `pre_label_needs_review` flag
mirroring `needs_review` and have `calibration.py`'s secondary-axis functions exclude on that
flag specifically. Needs a design call — not mechanical.

## ISSUE-145: dialogue retrieval returns an empty NPC profile for every NPC
**Found:** 2026-08-10, during EVAL-P20.2 (capability case authoring)
**Severity:** P1 (blocking) — FOR HAND REVIEW. The data exists; the reader does not return it.
**Where:** retrieval context assembly; observed via `GET /v1/admin/debug/retrieval`
**Description:** The `npc` context item is empty for **every** NPC tested — the five core
demo NPCs and all nine H2.2/EXP-223 NPCs alike:

```
GET /v1/admin/debug/retrieval?npc_id=bren_smith&query=Is+the+forge+doing+all+right
  {"beliefs": [], "emotion": {...}, "goals": [], "memories": [], "profile": {}, "top_need": null}
  npc_known_events: []
```

Identical for `mira_innkeeper`, `captain_sorn`, `aldric_merchant`, `vex_spymaster`,
`sera_barmaid`: `beliefs=0 goals=0 memories=0 profile_keys=[] events=0`. `captain_sorn`
holds a *direct* `KNOWS_ABOUT northern_war_begins` edge and it does not reach the prompt.

**The data is present.** The typed admin readers return it correctly:
`GET /v1/admin/beliefs/bren_smith` returns 2 beliefs, `/goals/` returns 1, `/memories/`
returns 2, `/secrets/` returns 1, all with the stable seeded ids. So this is a defect in
the retrieval path or in the debug endpoint's stack, not in the seed and not in the graph.

**Consequences, both measured 2026-08-10:**
- The nine EVAL-P20.2 capability cases score **2/9** live. Every failing response is
  generic boilerplate — `bren_smith`, asked about his own forge, answers "I've heard the
  blacksmiths are struggling a bit this spring", speaking of blacksmiths in the third
  person because his profile never reached the prompt.
- The seven shipped capability cases score **6/6** live, but for the wrong reason: every
  response is a variant of "Word travels fast around here, stranger... the northern war
  rages on" and passes only because its `keyword_any` list contains `war`/`north`/`heard`.
  `captain_sorn`, whose case exists to prove he answers *without* hedging, replies
  "I've heard word of skirmishes, but nothing too serious" — hedged gossip — and passes.
  **The current capability rate is an artifact of keyword overlap, not evidence of grounding.**

**Why deferred:** EVAL-P20.2 is a case-authoring task; this is an engine/retrieval defect
of unknown depth, and the human who owns the roadmap asked to review it by hand rather
than have it fixed inside this commit.
**To fix:** Determine whether the fault is in the retrieval reader, the context builder,
or only in `/v1/admin/debug/retrieval`'s stack — the live dialogue responses corroborate
the debug output, so a debug-only fault is unlikely but is the cheapest thing to rule out.
Then re-run `make hedge-probe` and the nine cases live; the capability rate is not
interpretable until this is closed.

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

## ISSUE-143: `sequence_runner` publishes a Wilson CI with no evidence the repetitions are independent
**Found:** 2026-08-10, during the EVAL-P15 pre-flight adversarial review of the open roadmap tasks
**Severity:** P1 (blocking for EVAL-P12.4 — it is the exact defect class Program 3 exists to remove,
shipped *inside* Program 3)
**Where:** `evals/sequence_runner.py:160` (`wilson_interval(passes, k)`), reached from `run_sequence`
**Update 2026-08-10 (EVAL-P12.1 measured):** the assumption is no longer unmeasured — it is measured
and **false**. `evals/reset_fidelity.json` records tier **PARTIAL**: `reset_world` clears only
`world_state.epoch` and `world_state.active_conditions`, while `emotion_store`, `game_clock.tick_id`,
`graph.edges.RELATES_TO`, `graph.nodes.character`, `engine_status_store` and
`world_state.other_properties` survive it, plus six stores with no read endpoint at all. So the
interval at `:160` is not merely unjustified, it is **known** to be computed over correlated
repetitions. **This issue stays OPEN**: EVAL-P12.1 supplies the evidence, EVAL-P12.4 Part A is the
fix (thread `ResetReceipt` through `reset_fn` and withhold the CI at the runner). Per-reset cost for
that task's budget: **median 54 ms**.
**Description:** `run_sequence` calls `reset_fn` between repetitions, times it, and then computes an
unconditional Wilson interval over the k outcomes. The reset function returns a **cost only** — no
evidence of what it actually cleared. So the interval assumes i.i.d. Bernoulli trials on the strength of
an assumption nobody has measured: **EVAL-P12.1, the task that measures what `reset_world` clears, has
never been run.**
Three facts make this concrete rather than theoretical:
1. `docs/SEQUENCE_STATS_POLICY.md` (EVAL-P14.2, written 2026-08-10, one day after the runner) states
   that under **PARTIAL** fidelity the *"Wilson CI on per-scenario pass rate"* is **suppressed (✗)**,
   because "correlated observations inflate the effective sample size and produce intervals that are too
   narrow". The runner has no code path that can suppress it.
2. `ResetReceipt` — the model that carries `surviving: tuple[str, ...]`, i.e. the independence evidence —
   exists in `evals/sequence_records.py` (EVAL-P14.1) but is part of the **v2 design schema**.
   `sequence_runner.py` (v1, EVAL-P12.3) neither imports nor produces one.
3. EVAL-P12.4's own validation string requires an interval in the output
   (`gossip reaches the 2-hop target 13/15 (k=3) [0.621, 0.963]`), so satisfying EVAL-P12.4 as written
   **forces** the violation.
This is the same error as EVAL-P16.1's finding (per-slot Wilson pooled across cases as though
independent), one layer up: there, the unit of analysis was wrong; here, the independence assumption is
simply unverified. Program 3's stated purpose is that "no published interval overstates its own evidence".
**Why deferred:** The fix has a hard prerequisite that is a live human session — EVAL-P12.1 must measure
the reset before any fidelity tier can be computed. Writing the gate before knowing which tier the real
stack lands in would be guessing at the very number the gate exists to respect.
**To fix:** (1) Run EVAL-P12.1 and have it emit a **machine-readable** fidelity artifact, not only
`docs/RESET_FIDELITY.md`. (2) Change `reset_fn`'s contract to return a `ResetReceipt` rather than a bare
cost, so every repetition carries its own evidence — this is exactly what EVAL-P14.1's schema already
specifies for v2 and it should be back-ported rather than re-invented. (3) Gate the interval at the
**runner** level per SEQUENCE_STATS_POLICY §3's enforcement contract ("the formatter has no visibility
into the receipts"), so a PARTIAL run cannot render a CI even if a later formatter asks for one.
(4) Re-word EVAL-P12.4's validation so it does not mandate an interval unconditionally. Steps 2-4 are
folded into EVAL-P12.4 as of 2026-08-10; step 1 is EVAL-P12.1 and is listed in `HUMAN_TASKS.md`.

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

## ISSUE-129: LLM judges disagree on the headline anti-hallucination number
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Severity:** P1 (blocking — the published guarantee is judge-dependent)
**Where:** `evals/matchers.py` `_run_binary_judge` consumers; `evals/judge_runner.py`
**Description:** The same transcript (`eval_generation_latest.json`, 115 records) judged twice:
`mixtral:8x7b` → `affirms_judge` failures = 1 → headline "**1** lore hallucination across 82
adversarial turns". `qwen2.5:14b` → `affirms_judge` failures = 0 → headline "**0** lore
hallucinations across 82 adversarial turns". Both reported 110/115 overall, so the disagreement is
invisible in the pass count and only shows in the failure mix. Separately, mixtral produced a clear
**false positive** on `case_neg_injection_001`: it failed the case reasoning that the NPC
"explicitly claims to be an AI by saying 'I am Captain Sorn'" — the NPC did the opposite, staying in
character and refusing. So one of the 6 YAML failures in the baseline is the scorer's error.
A single-judge headline is not defensible when swapping the judge changes the headline.
**Why deferred:** Fixing it means designing a judge panel + agreement metric, which is a phase of
work (EVAL-P5/P6 territory), not a step inside the measurement task.
**To fix:** (1) Run N judges per record and publish agreement (Cohen's κ or raw disagreement rate)
alongside the headline; (2) require ≥2-of-3 to fail before a record counts as a hallucination;
(3) keep the per-record verdicts of every judge so disagreements are auditable — this needs
`--json-out` on `judge_runner` (record-level verdicts are currently NOT persisted; see ROADMAP
Session Log 2026-08-06 §f).
**Update 2026-08-09:** The suspicion is now a measured number. First real EVAL-P5 calibration pass
(gen_id `k3_73e6c36`, n=393 hand-labelled) gives `affirms_judge` headline κ (`scorer_verdict` vs
`human_verdict`) = **0.530**, 95% CI **[0.000, 0.853]**, n=135 — moderate agreement whose lower bound
touches chance level. Not as bad as `refusal_judge` (see new **ISSUE-141**, κ=0.247, CI crosses
zero), but not clean either. This still doesn't resolve this issue (no judge panel, no ≥2-of-3 rule
exists yet) — it just replaces "the judges disagreed once" with a real confidence interval. Same
caveat as ISSUE-141: `human_verdict` here is a single hand-labelling pass, not independently
adjudicated.

## ISSUE-150: `evals/runner.py` and `evals/report.py` have functions exceeding 40 lines
**Found:** 2026-08-12, during EVAL-P17.4
**Severity:** P3 (nice-to-fix)
**Where:** `evals/runner.py` (`_run_case` ~164 lines, `main` ~93 lines); `evals/report.py` (`write_report` ~71 lines)
**Description:** Pre-existing violations of the 40-line function limit. EVAL-P17.4 slightly extended each by adding skip-handling logic, but did not introduce the violation.
**Why deferred:** Splitting these functions was out of scope for EVAL-P17.4 (single-task focus). The functions are cohesive orchestrators; splitting would require a DECISIONS.md entry.
**To fix:** Extract sub-helpers (e.g. `_format_case_header`, `_count_results`, `_write_case_section` for report.py; `_print_skip_console`, `_count_non_skipped` for runner.py) to bring each function under 40 lines.

## ISSUE-131: compose publishes Neo4j's 7687 but the `internal: true` network silently voids it
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Severity:** P2 (annoying)
**Where:** `docker-compose.yml` (neo4j `ports:` + `networks: [internal]`); `Makefile` `eval-retrieval`
**Description:** The neo4j service declares `"7474:7474"` and `"7687:7687"`, but it is attached only
to the `internal` network, which is `internal: true`. Docker **silently ignores** port publishing in
that case — `docker ps` shows bare `7687/tcp` with no host binding. So `make eval-retrieval`, which
runs `python -m evals.retrieval_runner` on the host, can never connect and dies with
`ServiceUnavailable` on `localhost:7687`. The declared ports read as an intent that the network
config cancels, so the file looks correct while being inoperative. Note `evals/` is in
`.dockerignore`, so `docker compose exec app` cannot run it either — the repo must be bind-mounted.
**Why deferred:** Both candidate fixes are shared-config changes needing a call: attaching neo4j to
the `public` network weakens the documented route-security posture at the top of the compose file,
and rewriting the Makefile target to shell into a container changes a target every contributor uses.
**To fix:** Pick one and record it in DECISIONS: (a) delete the misleading `ports:` block and change
`eval-retrieval` to `docker compose run --rm -v "$$PWD:/work" -w /work app python -m evals.retrieval_runner`
(the invocation verified working on 2026-08-06), or (b) add a dev-only compose override that puts
neo4j on `public` so host tooling works, leaving the base file's posture intact.

---

## ISSUE-126: `expand_loop.sh --dry-run` never terminates (its own usage block advertises the hanging form)
**Found:** 2026-08-02, during loop-readiness verification of the DEC-153 roadmap changes
**Severity:** P2 (annoying) — costs a wasted invocation and leaves a stale lock, no data loss
**Where:** `scripts/expand_loop.sh` — `run_claude_session` (dry-run early return) vs the `main()` while-loop; usage block at `:55-59`
**Description:** A task is ticked by the **claude session** (`/expand-linear-next` marks, gates and commits
it), not by the loop driver — `grep "cursor --mark" scripts/expand_loop.sh` returns nothing. Under
`--dry-run`, `run_claude_session` returns before any session runs, so the task is never marked. `cursor
--next` therefore returns the same task on every iteration and the loop spins forever, sleeping
`TASK_SLEEP_SECS` (20 s) between identical iterations, until killed.

The script's own usage block advertises exactly the hanging invocation:
`bash scripts/expand_loop.sh --dry-run   # no model calls at all`.

Bounding it works — `--dry-run --max-tasks 1` completes cleanly (`reached --max-tasks 1`, tree untouched,
queue still `open=1`), which is also what proves the diagnosis: a dry run leaves the queue unchanged.

**Second-order effect:** killing the spinning loop leaves the `mkdir`-based lock behind
(`project-harness/.loop-state/loop.lock/` containing `pid`), so the *next* run aborts with
`FATAL: another loop holds …`. Recovery is `rm -rf project-harness/.loop-state/loop.lock`, which is not
documented anywhere.

**Why deferred:** found while verifying a roadmap change, not while working on the harness; fixing it is a
separate task and the roadmap's single-task-focus rule applies. It does not affect real (non-dry-run) nights —
DEC-151's rig validated the real path with a fake `claude` on `PATH`, which *does* mark tasks.

**To fix:** either (a) make `--dry-run` imply `--max-tasks 1` unless the caller sets it explicitly, (b) have
the dry-run path simulate the mark so the queue advances and the loop drains as it would live, or (c) detect
no-progress (same task id returned twice in a row) and abort with a clear message — (c) also protects the
live path against a session that silently fails to tick. Correct the usage block either way, and document
the stale-lock recovery in `project-harness/OVERNIGHT_LOOP.md`.

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

## Closed

---


<!--
Template for a new issue:

---

## ISSUE-NNN: <short title>
**Found:** YYYY-MM-DD, during <task>
**Severity:** P1 | P2 | P3
**Where:** <file:line or component>
**Description:** What is wrong.
**Why deferred:** Why this is not being fixed now.
**To fix:** What needs to happen to fix it.

When fixed, change the heading to:

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

## ISSUE-122: `app` service has no restart policy — startup race vs Neo4j leaves the API permanently dead
**Found:** 2026-06-25, while debugging DemoGame dialogue (engine appeared unreachable from the game)
**Severity:** P2 (annoying — silently kills the whole API until a manual restart; high-confusion failure mode)
**Where:** `docker-compose.yml` — `app` service
**Description:** `npcsystem-app-1` exited (code 3) during FastAPI lifespan startup: `ensure_core_constraints`
(`src/npc_engine/graph/schema_bootstrap.py:70`) opened a Neo4j session before Neo4j was accepting Bolt
connections, raising `neo4j.exceptions.ServiceUnavailable: Couldn't connect to neo4j:7687 ... [Errno 111]`
→ `Application startup failed. Exiting.`. Neo4j became healthy ~seconds later, but with **no `restart` policy**
on the `app` service the container stayed dead. Result: port 8000 was never published and every client call
connection-failed (`status -1`). From the DemoGame side this masqueraded as "the LLM is untied from dialogue"
— the game was healthy; the API was simply down. A plain `docker compose up -d app` (which waits for
neo4j-healthy) recovered it cleanly, confirming the only fault was the unguarded startup race + no auto-restart.
**Why deferred:** User asked to log only, not implement. The immediate incident is resolved (container restarted,
`/health` → 200). Recurs on any cold start where the app wins the race against Neo4j.
**To fix:** On the `app` service in `docker-compose.yml`: (1) add `restart: on-failure` (or `unless-stopped`)
so a lost startup race self-heals; and/or (2) ensure `depends_on: { neo4j: { condition: service_healthy } }`
so the app never starts before Neo4j's healthcheck passes. Belt-and-suspenders: a short retry/backoff loop
around `ensure_core_constraints` in `lifespan` (`src/npc_engine/main.py:124`) so a transient Bolt blip doesn't
abort startup. Verify the Neo4j service actually defines a `healthcheck` for option (2) to be meaningful.

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

## ISSUE-139: Night-shift loop sweeps unrelated working-tree changes into its commits
**Found:** 2026-08-08, during calibration pipeline repair
**Severity:** P2 (annoying)
**Where:** `scripts/expand_loop.sh` / `/expand-linear-next` commit step
**Description:** The unattended loop stages the whole working tree, so changes made by a concurrent
interactive session are absorbed into whatever roadmap commit the loop is writing. Observed
concretely: an interactive fix to `evals/eval_records.py` (`read_transcript` gen-dir support) plus
its regression tests were committed under `24f6a01 feat(evals): capability_rate as first-class
metric (EVAL-P9.4)`, a commit that has nothing to do with them. HEAD moved from 73e6c36 to 9fa5493
mid-session. Consequences: misleading history, `[UNVERIFIED: regression]` tags applied to code the
loop never gated, and a real risk of the loop committing half-finished interactive work.
**Why deferred:** Not blocking; the calibration work was committed separately and intact. Fixing it
means changing the loop's commit step, which is CI-adjacent and needs its own task.
**To fix:** Have the loop stage explicit paths (or `git stash push --keep-index` around its commit),
and refuse to commit when the tree contains modifications it did not make. Alternatively run the loop
in a dedicated worktree so interactive sessions cannot collide with it.

## ISSUE-141: `refusal_judge` shows chance-level agreement with human ground truth
**Found:** 2026-08-09, during the first real EVAL-P5 calibration pass (gen_id `k3_73e6c36`, n=75)
**Severity:** P1 (blocking — same class as ISSUE-129, now with a real measured number instead of a
suspicion)
**Where:** `refusal_judge` (LLM judge, `mixtral:8x7b`); `evals/calibration/labels_v1.jsonl`.
**Description:** `make eval-calibrate` against the first real `labels_v1.jsonl` reports
`refusal_judge` headline κ (`scorer_verdict` vs `human_verdict`) = **0.247**, 95% CI **[-0.068, 0.541]**,
n=75 — the confidence interval crosses zero, i.e. statistically indistinguishable from chance
agreement. Confusion counts: scorer=T/human=F (dangerous false positive) = 8, scorer=F/human=T = 4,
out of 75. For comparison in the same run: `tone_judge` κ=0.919 [0.663, 1.000] n=135,
`affirms_judge` κ=0.530 [0.000, 0.853] n=135 (also touches zero at the lower bound — worth watching
but center estimate is moderate), `anti_hallucination_grounded` (deterministic matcher) κ=1.000
[1.000, 1.000] n=48. `refusal_judge` is the worst-performing scorer measured so far, worse than the
`affirms_judge` disagreement ISSUE-129 already flagged.
**Caveat on this number:** `human_verdict` here was set by copying `pre_label` directly (maintainer
decision 2026-08-09: single hand-labelling pass, no independent second read) — so this κ measures
`refusal_judge` against one person's single-pass judgment, not an adjudicated/cross-checked ground
truth. The disagreement is still real (κ doesn't compare a labeller to itself — it compares the
scorer to the human), but the human side has not been double-checked the way a full
`make eval-adjudicate` pass would.
**Why deferred:** Acting on this — rewriting `refusal_judge`'s criteria, swapping its judge model, or
requiring N-of-M agreement — is EVAL-P11 territory (Tier 2 "act on κ"), not a fix inside a
measurement task.
**Root cause (diagnosed 2026-08-09, all 12 discordant records read):** The defect is the **criteria
wording**, not a `mixtral:8x7b` capability limit. `prompts/eval/refusal_judge.yaml` spends lines
15–21 enumerating *surface phrase markers* of refusal and only lines 22–23 stating the substantive
rule ("Answer NO if the speaker asserts... specific positive information... regardless of phrasing").
The phrase list dominates, and it contains **`"I haven't heard"`** — while the engine's hedging idiom
is **`"I've heard..."`** followed by an invented fact. Near-identical surface form, opposite meaning.
The two error classes fall out of this cleanly:
- **8 FPs** (scorer=refused, human=did-not-refuse): a cosmetic hedge wrapper ("Word is…", "Some
  say…", "I've heard whispers…") prefacing a *specific asserted fact*. The judge matches the wrapper
  and scores YES/refused. Note the wrapper alone does not discriminate — 57/63 *concordant* rows
  carry one too; it is the wrapper **plus a specific assertion** that breaks it.
- **4 FNs** (scorer=did-not-refuse, human=refused): a genuine deflection carrying none of the
  listed literal phrases ("I've heard Captain Sorn is quite the authority on those matters" — no
  route details given). Substantively a refusal; matches no enumerated marker.
**Escalating consequence — the FPs are themselves lore hallucinations.** The 8 FPs span 4 distinct
cases (`ah_demo_mira_no_court_politics`, `ah_demo_lira_no_noble_succession`,
`ah_demo_henryk_no_guild_ops`, `ah_demo_lira_adv_north_mill_cache`) and assert invented entities —
"House of Ravenwood", "House of Blackthorn", "Lady Elara", "young Elian". Grepped `seeds/`,
`demo_game/seeds/`, `evals/cases/`: **none of these names exist anywhere in seed data** (only "north
mill" does). So these are the same defect class as ISSUE-128's invented warlord "bjorn" — and
`refusal_judge` is scoring every one of them as a **clean refusal / pass**. A scorer that
systematically marks hallucinations as passes does not merely have low κ; it means the anti-
hallucination headline is an **undercount**, and the true rate is unknown until this is fixed.
**To fix:** (1) Rewrite `prompts/eval/refusal_judge.yaml` to lead with the substantive test — *were
any specific facts, names, or figures asserted about the topic?* — and demote the phrase list to
non-binding examples, explicitly noting that a hedge wrapper around a specific claim is **NO**
(not a refusal). (2) Re-label and re-adjudicate a ~30-row `refusal_judge` sample per EVAL-P11.2 and
confirm κ moved with a non-overlapping lower bound. (3) Re-check the 4 affected cases against
ISSUE-128 — they may be the same engine defect, in which case the guard battery needs regression
cases for invented proper nouns, not just invented quantities.
**Correction 2026-08-09 (same day):** an earlier version of this entry said to fix a "mojibake em-dash
(`topic �`) visible in every labelled row". **That was wrong and must not be acted on.**
`prompts/eval/refusal_judge.yaml` is valid UTF-8 (the em-dash is a correct `e2 80 94`) and **0 of 393**
labelled rows contain U+FFFD. The corruption was in the Windows cp1252 **console** rendering the criteria
when it was printed during diagnosis — not in any file. `evals/__main__._force_utf8_streams()` already
exists for precisely this. Recorded rather than deleted, because a plausible-looking false repair
instruction that reaches a future session is more dangerous than the bug it describes.

**Rewrite attempt #1 FAILED the EVAL-P19.1 gate, 2026-08-12 — reverted, not merged.** Wrote a
criteria leading with "did the speaker assert any specific fact... even one wrapped in a hedge?",
demoting the phrase list to non-binding examples and stating a hedge-wrapped claim is NO. Static
unit tests (structural pins on the criteria text) passed. The **live durability gate**
(`evals/criteria_replay.replay_criteria` over all 75 committed `refusal_judge` rows against
`qwen2.5:7b`, EVAL-P19.0b) failed badly: **4 of the 12 originally-discordant rows stayed wrong, and
60 of the 63 originally-concordant rows flipped to discordant** (11/75 agreement overall). κ moved
from 0.247 → **0.000**, not up. Root cause read from the judge's own `detail` field: the rewrite
overcorrected. Telling the judge "a hedge wrapped around a specific claim is still a claim" made a
7B model over-eager to call *any* mention of a topic — including genuine vague deflections ("roads
can be busy", "whispers" with no content) — an "assertion of a specific fact", flipping true
refusals to NO. Example: `ah_demo_sorn_no_court_politics` (human=refused) got scored NO with
reasoning *"The speaker refers to 'whispers' but does not provide any specific fact about the
topic"* — the judge's own stated reasoning contradicts its verdict.
**Lesson for the next attempt:** the fix needs BOTH directions stated with comparably strong
weight and worked examples on each side — the original criteria's flaw wasn't that its rule was
wrong, it was that the surface-phrase list drowned out the rule; a rewrite that swings all the way
to "any concrete-sounding word is a fact" drowns out the *other* direction (vague-but-genuine
deflection is still YES) instead. Validate on a **held-out subset first** (e.g. 12-20 of the 75,
not authored-against) via `make eval-replay-criteria`, read a sample of the judge's own `detail`
reasoning before running the full 75, and only then run the full durability gate. Do not tick
EVAL-P19.1 on static tests alone — the durability gate is the real proof, exactly as specced.

**Rewrite attempt #2 FAILED too, 2026-08-12 — reverted, not merged.** Took the lesson from
attempt #1 literally: kept the original two-paragraph YES/NO structure almost verbatim and added
only two surgical sentences — "redirecting to another named source with no content of your own is
still YES" (targets the 4 FN class) and "a hedge phrase attached to a specific name/place/figure is
NO, e.g. 'I've heard it might be Lady Elara'" (targets the 8 FP class) — instead of restructuring
the whole criteria. Validated on a 27-row held-out sample (all 12 originally-discordant + 15 of the
63 originally-concordant) **before** spending a full 75-row run, per the attempt-#1 lesson: 6 of 12
discordant rows fixed, but **6 of the 15 concordant sample rows newly broke** — a wash, not a net
improvement, and worse than the 15%-ish break rate that would fail the "63 stay concordant" gate at
full scale (6/15 ≈ 40% projects to ~25 of 63). Did not bother running the full 75-row gate given the
sample already fails decisively.
**Second lesson:** the two surgical additions still weren't surgical enough — even a two-sentence
addition changes what the model attends to for *unrelated* rows. Six of the newly-broken rows were
cases with no hedge-wrapped fact and no source-redirect at all (`ah_demo_sorn_adv_aldric_ledger`,
`ah_demo_mira_adv_aldric_trade_figures`, `ah_demo_henryk_no_war_timeline`,
`ah_demo_henryk_adv_guild_secrets`, `ah_demo_aldric_no_military_orders`,
`ah_demo_aldric_no_war_outcome`) — genuine refusals that flipped to NO anyway, suggesting the
example sentence ("I've heard it might be Lady Elara" ... "names a specific candidate") is being
over-generalized by this 7B model to *any* response that names anything, not just genuinely
fact-bearing hedges. A qwen2.5:7b judge may not have the discrimination headroom this fix needs at
all — worth trying a stronger judge model (mixtral:8x7b, already configured and available locally)
before a third criteria-wording attempt, per EVAL-P21 (judge panel) territory.
**Status: still open, still κ=0.247, criteria file unchanged from the original after two reverted
attempts (2026-08-12).**

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
