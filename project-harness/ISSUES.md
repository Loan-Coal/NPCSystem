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

## ISSUE-130: Anti-hallucination runner prints "SKIP (NPC not found)" for every skip cause
**Found:** 2026-08-06, during EVAL-P0.4 measured baseline
**Severity:** P3 (nice-to-fix)
**Where:** `evals/anti_hallucination_runner.py` (the `outcome == "skipped"` console branch, ~line 380)
**Description:** `ah_demo_mira_player_taught` printed `SKIP (NPC not found)`, but `mira_innkeeper`
exists and answered 8 other cases in the same run. The real cause is the `learned_from_player`
belief pre-flight (ISSUE-090 / DEC-095) finding no persisted player-taught fact. The console prints
one hardcoded reason for every skip, so the message actively misdirects — it sent this session
looking for an unseeded world that was already seeded.
**Why deferred:** Cosmetic; it cost diagnosis time but not correctness, and EVAL-P0.4 was mid-run.
**To fix:** Print the `skip_detail` already present on the result dict instead of the hardcoded
string. The correct text is already computed — it is simply not the one displayed.

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

## ISSUE-124: `evals/` is not covered by `mypy`, `check-rules`, or `check-docstrings`
**Found:** 2026-07-31, during eval-program planning
**Severity:** P3 (nice-to-fix — no current defect, but zero enforcement on the directory intended for publication)
**Where:** `Makefile` (`lint`, `type` recipes), `scripts/check_rules.py:108`, `scripts/docstring_audit.py`,
`scripts/rules_baseline.txt`
**Description:** Every quality gate scopes to `src/` only: `lint` is `ruff check src/`, `type` is `mypy src/`,
`check_rules.py` iterates `_iter_py("src/npc_engine")`, `docstring_audit.py` scans `src/`, and
`rules_baseline.txt` contains zero `evals/` entries. `test-cov` measures only
`npc_engine + matchers + summary + runner`, so the other 10 `evals/` modules have no coverage floor either.
Net effect: the 13 modules in `evals/` — the directory the project intends to publish standalone as its
portfolio artifact — carry no lint, type, file-size, function-length, nesting, or docstring enforcement,
while `src/` carries all six.
**Why deferred:** `EVAL-P0.3` brings `evals/` under `ruff` only, deliberately time-boxed to 30 minutes,
because the true violation count across 13 pre-existing modules is unknown and extending `mypy` +
`check-docstrings` at the same time risks turning one roadmap step into an unbounded cleanup sweep.
Tracked as a `Parked (out of budget)` line in the `EVAL-P0..P7` program.
**To fix:** After `EVAL-P0.3` establishes the ruff baseline and the real violation count is visible:
(1) add `evals/` to the `type` recipe and drive mypy to zero (or record a ratchet baseline, mirroring
`scripts/mypy_ratchet.py`); (2) extend `docstring_audit.py`'s scan root to include `evals/` — most modules
already carry the `Module:/Layer:/Purpose:` header, so this should be small; (3) extend
`check_rules.py:_iter_py` to `evals/` and record any R001 file-size / R006 function-length residue in
`rules_baseline.txt` under a dedicated `# evals/` section, per the DEC-140 documented-waiver convention.

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

## ISSUE-133: calibration confusion matrix has no scorer axis — `make eval-calibrate` cannot calibrate a scorer
**Found:** 2026-08-07, while planning EVAL-P5 adjudication
**Severity:** P1 (blocking — invalidates the phase's stated goal, and wastes 4–6 h of maintainer time if
adjudication starts before it is fixed)
**Where:** `evals/calibration.py:73-88` (`confusion_counts`), `:115-149` (`cohens_kappa`), `:261` (the
printed header), `evals/calibration_records.py:50-57` (`CalibrationLabel` fields).
**Description:** EVAL-P5's goal is "every scorer measured separately as a full confusion matrix plus
Cohen's κ". As built, both axes of the matrix are `pre_label` (the reference labeller) and
`human_verdict` (the maintainer) — the scorer's own verdict is never compared to anything.
`CalibrationLabel` has no field to hold it, and `scorer` is used only as a grouping key
(`calibration.py:231`). So `make eval-calibrate` answers "how often does claude-opus-5 agree with the
maintainer, partitioned by which scorer's criteria were in play" — which the ROADMAP describes as the
*free secondary* number — while the headline question ("can I trust `tone_judge`?") is not computed at
all. P0.4 already produced one confirmed scorer false positive (`case_neg_injection_001`, ISSUE-129),
so the untrustworthy-scorer risk is measured-real, not hypothetical.
**Why deferred:** Not deferred — scheduled. It must land before any adjudication session, and after
EVAL-P6.1, since labels bind to one generation and re-generating after P6.1 would invalidate them.
**To fix:** Add `scorer_verdict: bool` to `CalibrationLabel` (joined from the judged transcript, never
supplied by the labeller). Make `scorer_verdict × human_verdict` the headline matrix and keep
`pre_label × human_verdict` as the secondary reference-labeller agreement number. Update
`confusion_counts`, `cohens_kappa`, `kappa_interval`, `ScorerReport`, `_print_scorer_report` and
`tests/unit/evals/test_calibration.py`. Decision recorded 2026-08-07 (option A, chosen by maintainer).

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

## ISSUE-136: roadmap fence tripwire snapshot goes stale mid-phase when a phase commits more than one task
**Found:** 2026-08-07, during overnight loop review of phase EVAL-P1
**Severity:** P2 (annoying — trips a false-positive HALT on the overnight loop, not a real regression)
**Where:** `tests/unit/harness/test_roadmap_cursor.py::test_real_roadmap_fence_state_tripwire`
**Description:** The test is a hand-maintained snapshot of the roadmap's pending-task-id list, deliberately
updated by whoever's commit changes which tasks are pending (DEC-153-era design: "UPDATE DELIBERATELY when
the fence moves"). In practice the update rides whichever task's commit happens to touch the file — usually
the first task worked in a phase — not the last. EVAL-P1.2's commit updated the snapshot correctly for the
state at that moment, but EVAL-P1.5 and EVAL-P1.6 landed afterward in the same `expand_loop.sh` run without
a further update, so the phase-boundary `make check` gate went red on a stale assertion rather than a real
failure. The same pattern is recorded in the test's own docstring for EVAL-P4 and EVAL-P5 — this is the
fourth occurrence, all false positives, all costing a "FLAGGED FOR HUMAN" halt and a soft-review cycle.
**Why deferred:** Each occurrence so far has been cheap to diagnose and fix by hand (see commit 86254cb for
the EVAL-P1 instance), and redesigning the tripwire is out of scope for a mid-phase review pass.
**To fix:** Either (a) derive the assertion from `git diff` against the phase's start-of-phase baseline
instead of a hardcoded literal list, so it self-updates with whatever the phase actually completed, or
(b) move the snapshot-update responsibility into `expand_loop.sh`'s phase-boundary step itself (it already
knows the phase just closed) rather than leaving it to whichever task's author remembers. Either fix should
keep the "assert sorted id lists, not bare counts" property the current test already has, since that part
works as intended.

## ISSUE-137: `evals/summary.py::summarize` exceeds the 40-line function limit
**Found:** 2026-08-08, during EVAL-P10.1
**Severity:** P3 (nice-to-fix)
**Where:** `evals/summary.py:168–212` (`summarize`, 45 lines)
**Description:** `summarize` is 45 lines, exceeding the 40-line strict limit from CLAUDE.md. Introduced before EVAL-P10.
**Why deferred:** Pre-existing violation, not introduced by EVAL-P10.1. Fixing it is a separate refactor.
**To fix:** Extract battery-result filtering into a helper (e.g., `_collect_battery_stats`) to bring `summarize` under 40 lines.
