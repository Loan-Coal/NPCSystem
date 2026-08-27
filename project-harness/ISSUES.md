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
**Where:** `evals/retrieval_join.py:93-103` (`node_id_from_key` over `record.retrieved_context`);
`evals/dashboard/` case pane (renders `retrieved_context` item keys);
`evals/sequence_records.py:63` (`Turn.retrieved_context`)
**Description:** `GenerationRecord.context_receipt` now carries what ACTUALLY reached the
model. `retrieved_context` still carries the older approximation — a second call to
`GET /v1/admin/debug/retrieval` with `session_turns=[]`, describing a different assembly than
the one that produced `npc_response`. Both fields are populated on every new record, and the
three consumers above still read the deprecated one, so `recall@k` and the dashboard's context
pane are still reporting over what the retriever RANKED rather than over what SURVIVED the
prompt budget. Those are different numbers, and the gap is the thing the receipt was built to
expose.
**Why deferred:** Deleting or repointing them in the same change would have silently altered
what `recall@k` measures at the same moment as the field landed, with no released corpus
carrying `context_receipt` to compare against. The deprecation is marked in
`evals/retrieved_item.py` and in `GenerationRecord`'s docstring, and both fields are written,
so the migration can be measured rather than assumed. Committed corpora
(`evals/generations/k3_73e6c36/`) have no `context_receipt` at all and would read as empty.
**To fix:** After regeneration #1 has produced at least one corpus carrying `context_receipt`,
repoint `retrieval_join` at `context_receipt.item_keys`, compare the two recall@k numbers on
the same corpus and record the delta (it is a finding, not a migration detail), move the
dashboard pane over, then drop `retrieved_context` and `evals/context_capture.py` along with
the second debug-endpoint call per turn — which also removes roughly half of the generation
pass's HTTP requests.

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
**Severity:** P1 (blocking — the published "N lore hallucinations across M adversarial turns"
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
**Severity:** P1 (blocking — corrupts every headline number computed via `summarize_from_dir`,
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

**Correction 2026-08-12 (before attempt #3): the "try mixtral:8x7b instead" premise above is
wrong — mixtral:8x7b was already the judge for attempts #1 and #2.** `evals/judge_config.py`'s
`DEFAULT_JUDGE_MODEL` has been `"mixtral:8x7b"` since DEC-143 (2026-06-23, predates both attempts
by weeks); `resolve_judge_model()` only overrides it via a `JUDGE_MODEL` env var, and a repo-wide
grep of `.env`/`.env.demo`/`.env.example` plus a fresh-process check
(`judge_config.resolve_judge_model()` → `'mixtral:8x7b'`) found no override anywhere. Neither prior
attempt's scratchpad script (`eval_p19_1_durability_check.py`, `eval_p19_1_sample_check.py`) set
`JUDGE_MODEL` either — both called `matchers._run_binary_judge` directly, which always resolves the
module-level `_JUDGE_MODEL` at import time. So both `qwen2.5:7b` mentions in this issue were a
misdiagnosis (the *generation* models are qwen2.5:7b per DEC-149, which was likely conflated with
the judge). The "swap to mixtral" lever was already spent before attempt #3 ran. Recorded rather
than silently corrected, same rationale as the mojibake correction above: a plausible-looking wrong
lever is worse left unflagged than described honestly.

**Rewrite attempt #3 FAILED too, 2026-08-12 — reverted, not merged.** Took the attempt #1 lesson
("both directions need comparably strong weight") literally: a full restructure giving YES and NO
each a parallel worked example built on the *same* hedge phrasing ("I've heard the roads have been
busier than usual, but nothing more than that" → YES vs. "I've heard whispers it might be the
Ravenwood family..." → NO), plus an explicit closing test ("strip the hedge phrases — is a specific
name/place/number/date/concrete claim left over?"). Validated on a 27-row held-out sample (all 12
originally-discordant + 15 originally-concordant, this time deliberately weighted toward the
generic-guard-activity rows most likely to be misread) before spending a full run: **8 of 12
discordant fixed (best of the three attempts on this axis) but 11 of the 15 concordant sample rows
newly broke (73% break rate — worse than attempt #2's 40%)**. Sample agreement 12/27 (44%), *below*
the 15/27 (56%) baseline the sample started at. Did not run the full 75-row gate — a sample this
decisively negative cannot pass gate condition (b) (0 of 63 broken) at full scale, same call as
attempt #2.
**Third lesson:** "strip the hedge, is anything specific left" is still too coarse — it cannot tell
a genuinely *new* invented specific ("succession is being contested", "the cache is under the old
mill") from the NPC merely *repeating the topic entity the player already named* in vaguer terms
(e.g. `ah_demo_henryk_no_eyewitness`, human=refused, broke: "I've heard the tales of **King's
Pass**, stranger. But I was but a humble blacksmith..." — "King's Pass" is the player's own query
topic, not a new fact, but the criteria's "specific proper noun → NO" test can't see that
distinction). Two of the three attempts now independently show the same shape: any single strong
new directional cue this criteria's wording can express gets over-applied by the judge model to
unrelated rows. Combined with the mixtral correction above, the "wording problem vs. model
capability problem" question from attempt #2 is now more settled toward capability — three
differently-shaped rewrites, all against mixtral:8x7b, all failed the same way (fix some
discordant, break disproportionately more concordant).
**Recommendation for the next attempt: do not attempt a fourth wording rewrite.** Move to EVAL-P21
territory (a 2-of-3 or 3-of-5 judge panel with majority vote, or an ensemble across mixtral:8x7b +
qwen2.5:14b) — the wording lever appears exhausted at n=3 attempts across 2 structurally distinct
strategies (full restructure, surgical patch, balanced-parallel-examples restructure), all against
the same (correctly-configured, already-strongest-available) judge model.
**Status: still open, still κ=0.247, criteria file unchanged from the original after three reverted
attempts (2026-08-12).**
**Formally deferred to EVAL-P21, 2026-08-13 (DEC-172).** `EVAL-P19.1` is flagged `⏸️ deferred` in
ROADMAP.md rather than retried a fourth time. `HUMAN GATE H2`'s `Ready when` no longer requires
`EVAL-P19.1` ticked (was unreachable — its own fix, EVAL-P21, depends on EVAL-P20.4, which is
downstream of H2) — it now requires `EVAL-P19.2` instead, a real criteria change already shipped.
`EVAL-P19.4` proceeds and is expected to report `refusal_judge` unchanged at κ≈0.247; that is not
a new failure, it is this issue staying open on schedule. `refusal_judge`'s rate remains refused
for publication until EVAL-P21's judge panel (2-of-3, out-of-family third judge) lands.

**`EVAL-P19.4` ran, 2026-08-13 (`HUMAN GATE H2` cleared) — confirms the expected result.**
Re-judged the unchanged `k3_73e6c36` transcript (`JUDGE_MODEL=mixtral:8x7b`) and merged
(`MERGE=1`) against the real 393-row label file: **393 human verdicts preserved, 0 new rows, 0
hash-drifted rows** (deterministic pass also regenerated via `make eval-deterministic-verdicts` to
actually exercise EVAL-P19.2's word-boundary fix — confirmed 0 of 576 deterministic verdicts
flipped in this corpus; the fix is real but this corpus contains no case whose keyword match it
changes). `refusal_judge` re-measured: **κ = 0.247, 95% CI [-0.123, 0.703], n=75, n_clusters=25**
— point estimate exactly unchanged from the original ISSUE-141 measurement, confusion matrix
identical (60 TT / 8 FP / 4 FN / 3 TT-neg). Confirms DEC-172's prediction. `refusal_judge` stays
unfixed, its rate stays refused for publication, and this issue stays open, deferred to EVAL-P21 —
exactly as scheduled, not a new finding. (Blocking infra defect hit and fixed en route: ISSUE-158.
Unrelated tone_judge LLM non-determinism noticed and accepted, not reverted: ISSUE-160.)

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
