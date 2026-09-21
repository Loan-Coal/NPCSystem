
## 2026-09-16 15:17:11 — phase T1

**FINDINGS - T1 Phase Review**

1. **T1.1 logic redundancy**: `_poll_for_disconnect` checks for `msg.get("type") == "websocket.disconnect"` (line 191) but Starlette signals WebSocket disconnect via exception, not message type—this condition is unreachable. The fix still works (disconnect raises exception → propagates → caught), but the check is dead code.

2. **T1.1 nesting depth claim unmet**: Commit says extracted `_poll_for_disconnect` "keeps nesting within the 3-level limit," but the while loop body contains `if await _poll_for_disconnect(...)` at level 4 (function → try → while → if). Same depth as before extraction.

3. **T1.2 seed fix incomplete**: Army repositioning (iron_legion: loc_guard_barracks → loc_north_gate) prevents tick-0 defeat via its location change, but the test only validates the seed state at tick 0. Missing verification that the new `evt_21_iron_legion_advance` event (which replaces military engine's Act 5 behavior) actually fires and uses the events engine—test doesn't confirm events engine processes it.

4. **T1.2 dependencies cleanup verified**: No remaining imports of `engines.military`, `graph.military`, or wiring sites missed. All factory singletons (`get_military_engine`, `MilitaryEngine` type imports) removed cleanly.

5. **T1.1 test isolation concern**: Mock `websocket.receive = AsyncMock(side_effect=WebSocketDisconnect())` bypasses actual Starlette WS behavior. Test validates slot management but not that the fix works with real WebSocket implementations or actual message receive loops.

## 2026-09-17 21:29:53 — phase T3

## Findings

1. **ISSUE-354 contradicts T3.3 completion**: The issue documents `GET /v1/admin/factions/{id}/standings` returning 500 due to response model mismatch (Cypher returns dict, model expects string). Task T3.3 requires "the kept faction and treaty read paths still return data" — a 500 error is a validation failure, not a pass. Deferring it because the client "degrades gracefully" misses that the endpoint itself is broken at the API contract level.

2. **Deferred work not isolated to ISSUES.md**: The issue correctly lives in `ISSUES.md`, but the task tick in `ROADMAP.md` (T3.3) should probably include a note linking back to ISSUE-354 rather than silently marking the validation complete when a read path is non-functional.

3. **Pre-existing diagnosis is correct but incomplete**: The issue traces the root cause correctly (`CYPHER_LIST_STANDINGS` returns `properties(b)` instead of `b.id`), but doesn't note whether this was supposed to be deleted in T3.2 or is a kept service. If it's kept, the response model is the bug; if it was supposed to be deleted, that's a gap in T3.2.

4. **Response validation error not logged when found**: ISSUE-354 cites a `ResponseValidationError` from FastAPI, which suggests active testing of the live stack occurred. The finding was correctly logged, but the task completion marker doesn't reflect that validation caught a failure.

5. **No code changes in this commit**: The commit only logs a finding and ticks tasks. The actual T3.2 deletion work is in the prior commit (`68e796bc`). Verify that prior commit removed `treaty` and `faction_politics` engines cleanly without leaving dangling callers.

## 2026-09-17 23:20:38 — phase T4

Looking at the T4.2 commit diff (the only T4 commit in the latest history), I've identified concrete issues:

## Findings

1. **Quote detection limited to double quotes** (`check_engine_census.py:147`): The `_tick_name_present()` function searches for tick names only with double quotes: `r'"' + re.escape(tick_name) + r'"'`. If `tick_scheduler.py` uses single quotes (`'gossip'`), the gate will incorrectly fail with "tick name not found" for valid engines.

2. **Substring matching false positive with overlapping engine names** (`check_engine_census.py:145`): The regex pattern `r"engines\." + re.escape(dir_name)` uses substring matching. The engine `"quest"` (non-tick) will incorrectly match imports of `"quest_generation"` (tick engine). If only `quest_generation` is imported but `quest` is checked, the gate will falsely report `quest` as imported.

3. **Empty/dead engine directories pass classification** (`check_engine_census.py:220-235`): The script verifies engines are classified and referenced but never checks that directories contain actual code. An empty directory classified as a tick engine could pass if its tick name exists in the scheduler, hiding dead code.

4. **DIR_TO_TICK_NAMES mappings lack validation** (`check_engine_census.py:58-77`): The tick name mappings (e.g., `"need" → ["need_decay"]`) are manually maintained. Incorrect or stale mappings only fail when the gate runs against the live scheduler—no early detection.

5. **ROADMAP.md entry marked done but dependencies unclear**: T4.2 is marked complete but doesn't verify that other T4 phases (T4.1 deletion, T4.3 refactor) completed successfully or that their changes don't invalidate the census gate assumptions.

**All functions comply with file size, length, docstring, and type annotation rules.**

## 2026-09-18 00:14:38 — phase T5

## T5 Phase Review

**Finding 1 — T5.2: Missing location_id validation test (edge case)**
- **File:** `demo_game/tests/seeds/test_seed_needs.py`
- **Issue:** Tests validate that `SATISFIES_NEED` edges reference valid Need IDs (`test_satisfies_need_edges_reference_known_need_ids`), but do NOT validate that location_ids are seeded/valid.
- **Comparison:** `test_seed_schedules.py` (T5.1) includes `test_schedule_entries_reference_valid_location_ids()` with a comprehensively built `_ALL_LOCATION_IDS` set. T5.2 should match this rigor.
- **Edge case:** Typo'd or non-existent location IDs in `_SATISFIES_NEED_EDGES` or `H2_SATISFIES_NEED_EDGES` would pass tests today.

**Finding 2 — T5.3: Gossip distortion query — edge validation sound**
- The `coalesce(best_distorted_summary, best_event.summary)` fallback correctly handles first-hand witnesses (no distorted edge field) returning canonical text. Test RED anchors (query-string assertions) are well-designed. No correctness issues detected.

**Finding 3 — All phases: Documentation and file size within bounds**
- `_seed_schedules()` ~25 lines, `_seed_needs()` ~38 lines, all well under 40-line function limit.
- Module docstrings present; function docstrings complete.
- No layer rule violations (graph queries in graph layer; seed IO at correct step; no LLM calls).

**Summary:** One concrete edge case — add location_id validation to T5.2's test suite. Otherwise T5 is solid: TDD RED anchors present, immutability respected, pre-approvals cited, roadmap checkmarks accurate.

## 2026-09-18 01:53:53 — phase T6

## T6 Diff Review — 5 Findings

**All three T6 commits are correct and follow project rules.** Top findings:

1. **ISSUE-355 acknowledged but unfixed (T6.1)**: Docstring in `demo_game/client.py:292` says `delta_ticks` accepts "1–1000" but MAX_DELTA_TICKS was lowered to 10. Logged in ISSUES.md (P3, deferred per scope). Not a violation, but represents technical debt.

2. **MAX_DELTA_TICKS boundary tests are gated (T6.1)**: Test hardcodes values `_NEW_CAP=10` and `_OVER_NEW_CAP=11` instead of importing from config. Intentional (per comment) — forces test update if cap changes, preventing silent drift. Design is sound.

3. **Engine execution order sequence is intentionally hardcoded (T6.2)**: `_EXPECTED_SEQUENCE` in `test_tick_order.py` is not imported to avoid circular imports and force deliberate updates. Correct pattern; the ten pairwise dependency tests validate every read-after-write constraint independently.

4. **Integration test defensive on eval stack availability (T6.3)**: `_skip_if_no_eval_stack()` properly skips if `/health` unreachable. Good, though test assumes stack is running before HTTP calls proceed — reasonable for an integration test designed for isolated stack only.

5. **File organization clean**: All three test files ≤322 lines (well under 800-line limit), proper module docstrings, layer rules followed (no Neo4j outside graph, no violations). Carry-forward notes added to ROADMAP.

**No correctness bugs or project-rule violations found.**

## 2026-09-18 12:31:21 — phase T7

**Findings (T7 phase review):**

1. **T7.1 — metric collection race condition**: `_record_budget_calls()` reads `get_metric_total()` *after* advances complete; if multiple workers call `advance()` concurrently, the delta is wrong (both see the same pre-value, both add the same delta twice). Test `test_tick_budget_guard_counts_calls` only runs single-threaded. Fix: snapshot pre-calls *inside* a lock if distributed mode is enabled, or document this as single-worker only.

2. **T7.2 — TickLLMBudget tick_id mismatch vulnerability**: If a quest trigger's `generate()` straddles a tick boundary (awaits across ticks), the second `consume_for_tick` call resets the counter mid-invocation, allowing budgets to slip. The structure assumes all three triggers run *within* a single tick body, but if one is awaited after a tick completes, the budget is silently reset. No test covers cross-tick awaits.

3. **T7.3 — receiver_ids collection assumes all pairs succeed through side_effects**: `_batch_refresh_receivers()` collects receiver_ids only from pairs that don't raise in the loop, but if `_maybe_propagate_secret()` or emotion distortion fails mid-pair, that receiver is omitted from the batch refresh. The comment says "best-effort" but the doc doesn't clarify if stale embeddings for skipped receivers are acceptable (likely yes, but unspecified).

4. **T7.5 — encoder warmup timeout not bounded**: `asyncio.to_thread(warm_up_encoder, ...)` has no timeout. If the model download stalls (network hiccup, missing model), boot blocks indefinitely. The 30s `start_period` in healthcheck will eventually fail it, but there's no per-warmup timeout. Recommend: wrap with `asyncio.wait_for(..., timeout=30)`.

5. **T7.4 documentation inconsistency**: The ROADMAP now reports warm tick as 1,322 ms after T7.3, but the T7.2 test expects a cap of 40 calls max (10 invocations × 4 calls each). If warm gossip takes 1,322 ms *and* 40+ LLM calls fire in other quest triggers that tick, the gossip tick will be delayed or preempted by LLM call exhaustion — no trace in the measurements explains which tick's LLM budget was charged.

## 2026-09-18 13:18:07 — phase T8

**T8 Phase Review — 5 Findings**

**1. Missing edge case test for gate initialization**
`admission_control.py:124-128` documents that `LLMAdmissionGate(max_concurrent < 2)` raises ValueError, but `test_admission_control.py` has no test covering this documented error path (RED → test must exist to confirm the guard).

**2. Private attribute access in public tests**
`test_llm_factory.py:718,727,737,747` access `client._inner` (a private attribute). Should test through public `model_name()` or `health_check()` instead, or make `_inner` public if it's part of the contract.

**3. No validation on per-engine timeout values**
`factory.py:370-378` and `test_per_engine_timeout_wiring.py` verify that `timeouts_ms.full` is *wired*, but don't validate that the timeout is positive. A zero or negative value in `llm_config.yaml` would pass tests but fail at runtime in the adapter layer (shedding all calls).

**4. Gate singleton is not thread-safe**
`admission_control.py:344-347` uses check-then-set pattern without locking. In asyncio it's safe (no context switch in sync code), but if called from multiple threads, two gates could be created. Document this or add a lock if threading is possible.

**5. Unreachable condition in background shedding**
`admission_control.py:185-191` checks `_interactive_count > 0`, then later `_background_held >= _background_max`. If an interactive call is pending (waiting for semaphore), a fresh background call will be shed at line 187. Correct behavior, but the `_background_held >= _background_max` check on line 188 is now unreachable (any arrival while interactive is pending hits line 187 first).  This is semantically OK, but suggests redundant logic—consider reordering or removing the second check for clarity.

## 2026-09-18 15:16:13 — phase T9

Looking at the T9 roadmap phase commits, here are 5 concrete findings:

### 1. **Misleading parameter name in SlotValidator**
`slot_validator.py:22` — Parameter named `quest_gen_repo` but receives `SlotValidationGraphPort`. Should be `slot_validation_repo` for semantic clarity. Names should reflect actual types (NPC project rule: clear naming).

### 2. **Incomplete protocol split in docstring**
`quest_generation_port.py:3-7` — Docstring promises protocols for "trigger reads for the three trigger classes" (EventTriggerGraphPort, NeedTriggerGraphPort listed in "Used by"), but these are not defined in this file. Either the split is incomplete, or the docstring overstates what's present.

### 3. **No type-checker guard for dual-protocol repository**
`dependencies_engines/quest.py:141-143` and test files — Both `quest_gen_repo` and `slot_validation_repo` receive the same `Neo4jQuestGenerationRepository` instance. Nothing verifies the repository actually implements both `QuestContextGraphPort` *and* `SlotValidationGraphPort`. If the implementation later drops one protocol, this coupling breaks silently.

### 4. **Redeclared-method test has a gap**
`test_ports_t9_2.py:46-76` — Test correctly checks that no method is directly declared twice across the four quest_port siblings using `vars()`. But it doesn't verify that the mixin protocols themselves don't declare the same method (e.g., both `_QuestStateMixin` and `_QuestEventMixin` defining a method). Should add a check for mixin-to-mixin collision.

### 5. **Confusing parameter wiring at callsite**
`quest_generation_engine.py:147` — Passes `self._slot_validation_repo` with parameter name `quest_gen_repo`. While the type is correct, the naming mismatch at the callsite obscures what's happening. Parameter name in SlotValidator should match the semantic role.

## 2026-09-19 21:21:14 — phase T10

**REVIEW FINDINGS (T10 Phase Commits)**

Based on diff analysis of the 4 T10 commits (`617b094b`, `ffd0ca7f`, `6e4019b0`, `b7cb101c`), here are the concrete findings:

---

1. **Graph module reachability uses substring-only matching**: `_compute_alive_graph_modules()` in `check_dead_surface.py:366` detects imports via `stem in text` (line 360, 367). This is vulnerable to false positives if a module stem appears in comments, docstrings, or string literals. Example: a comment `# graph_edit_validator is no longer used` would mark the module alive. **Severity: Low** — unlikely in practice, but correctness issue.

2. **LOC ratchet baseline budget already spent**: `loc_baseline.txt:3–4` reserves +700 LOC for T12.1, T15.1, T16.2. T10 added ~1058 LOC in three gate scripts, spending `1058 - 682 headroom = 376 of the 700` budget in one phase. No violation yet, but only 324 LOC remains for three future phases. **Severity: Planning** — not a rule break, but tight.

3. **DIP threshold waivers require DEC-NNN but do not validate it exists**: `check_dip_threshold.py:238` enforces the pattern is present, not that the DEC citation is real or open. A typo like `DEC-99999` passes the gate. **Severity: Low** — waiver entries are human-reviewed before commit anyway.

4. **No gate on Rule 5 (test must fail)**: CLAUDE.md line 140 lists Rule 5 as `"No gate on this tree"`. The new tests for the three gate scripts don't explicitly verify they'd fail on malformed input (e.g., baseline file with syntax error). **Severity: Process** — low priority, since AUTOFIX gates skip harness tests per loop_gates.py:62–66.

5. **Settings field reader detection is regex-based**: `check_dead_surface.py:123` finds readers via word-boundary regex on field names. A field appearing in a quoted string outside the config layer (e.g., in a CLI help string or error message) marks it alive. **Severity: Low** — rare in practice, but could mask genuinely dead config.

**Summary**: No rule violations of CLAUDE.md's strict rules. All three gate scripts are <800 lines, all functions <40 lines, docstrings present, tests comprehensive. The three tools are frozen in `loop_gates.py`. LOC ratchet is green (+682 headroom). No blocking issues.

## 2026-09-21 11:55:45 — phase T11

Now reviewing the T11 phase diffs. Looking at commits 902f34bd (T11.3), ed2a64f0 (T11.2), dc8933b0 (T11.1c), 44273a9a (T11.1b), 751cb993 (T11.1a).

**Five concrete findings:**

1. **Integration test environment isolation risk** (project-harness/CLAUDE.md, Memory: project_integration_tests_share_live_neo4j.md): DEC-287 gates integration tests on `NEO4J_URI=bolt://localhost:7688` (eval stack Neo4j). The decision correctly skips tests when the env var is absent, but `make check-integration-baseline` enforces ≥34 executed tests. **Risk:** If someone runs integration tests before the eval stack is built (`bash scripts/eval_stack_at.sh HEAD --reset`), all 56 tests silently skip and `make check-integration-baseline` passes a false-negative (34 tests is the floor, not a real count). The gate enforces count, not *real* Neo4j I/O. Tests should check connectivity first, not just env var presence.

2. **Exception specificity regression in 3 modules** (tests/unit/config/, tests/unit/evals/, tests/unit/graph/): Caught by the narrowing: `pytest.raises(Exception)` → `pytest.raises(ValidationError)` in ~20 locations is correct. **However**, multiple tests still catch `Exception` where they should be specific. E.g., `test_generate_runner_k.py:2279` now catches `ModelDigestUnavailableError` (good), but `test_gossip_repository.py`, `test_memory_repository.py`, `test_scheming_repository.py` deleted their "vacuous" delegate tests entirely (3 test files removed from graph/). **Finding**: The deletions are correct (those mocks proved nothing), but removing tests without integration coverage leaves those repository methods uncovered until T11.3 adds integration tests — which it does (56 new integration tests added across 5 files). Correct coverage flow, but risk if someone skips integration tests.

3. **Mock assertion narrowing incomplete** (tests/unit/engines/, tests/unit/graph/): Replaced `mock.assert_not_called()` with `assert not mock.called, "reason"` in ~10 places. This is good (captures intent). **Finding**: Two sites still use the old pattern:
   - `test_intent_queue_writer.py:2059` says `assert not mock_delete.called, "drop path must not evict..."` but the comment still says "reachability proven in this file" (old waiver language). The assertion is now real and captures the actual behavior; the comment should be removed.
   - `test_gossip_repository.py:2686` has the same pattern. These are fine, just stale comment text.

4. **File size baseline not updated** (CLAUDE.md rule 1, DEC-226): The ROADMAP shows 5 commits across T11.1a–T11.3. LOC ratchet was gated in T10.2b (682 LOC headroom). **Finding**: No evidence in the diff that any file grew or the baseline was bumped. The 56 new integration tests are in new files (test_*_repository_integration.py), so they don't affect the ratchet (tests/ is not counted). But deletions in conformance/ and graph/ (test files) lower the non-test count. This should pass the gate, but the commit message should record the delta for the record (ROADMAP "Calibration: headroom is 1,486 statements at 88.13%" is from T11.1c).

5. **Existence-only test deletion validation gap**: T11.1c deleted `test_sev04_routine_skill_graph_queries.py` and `test_player_model_repository.py` and `test_relation_phase_write_repository.py` (3 files, ~130 lines total). The deleted `test_all_gossip_query_functions_are_async()` from `test_sev04_gossip_graph_layer.py` checked `inspect.iscoroutinefunction()` — a pure existence check, correctly identified as vacuous by rule 5. **However**: `test_scheme_reader.py:2873–2878` also deleted `test_scheme_status_literal_exists_in_reader_module()`, which checked `hasattr(scheme_reader, "SchemeStatus")`. This is also vacuous (the field exists in the import statement 1 line above). The deletion is correct. But `test_shared_read_repositories.py` docstring says "Neo4jRelationReadRepository tests removed: get_relation_scalars and get_relation_phase_row are covered by integration tests (T11.2)." This is **not** verified in the diff — no integration test file explicitly covers those two repository methods (they're not listed in ISSUE-363). **Risk**: Two reader methods may have fallen through the integration test net.

---

**Summary:** Integration tests risk false-green on env-var-only gating; relation reader coverage may be incomplete; otherwise T11 phase execution is sound (narrowed exceptions, deleted vacuous tests, added 56 real integration tests).
