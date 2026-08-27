# CR-L14 — Agent-authored code smells

**Lens:** L14 of 16. **Tree:** `eval-ab-context-arms` @ d46ae42. **Mode:** read-only.

**Method note:** all counterfactuals were executed against a full copy of the tree at
`<scratchpad>/cf` (src + tests + demo_game + evals + scripts + seeds). The working tree
was never modified. Baseline in that copy: `3997 passed, 37 failed` (the 37 are copy
artifacts — tests that read `project-harness/` paths not copied), and
`mypy src/` → `Success: no issues found in 627 source files`.

---

## Required measurements

| # | Category | Count | Method |
|---|---|---|---|
| 1 | Abstraction introduced only to satisfy a rule | **45 Protocols** — 44 in `engines/ports/` (40 files, **2088 lines**, 169 method declarations) + `BaseEngine`. **14** have exactly one caller; **10** declare exactly one method; **4** are both. `BaseEngine` is `(*args, **kwargs)` and enforces nothing (proven, CR-L14-04). | AST: extracted every `class X(Protocol)` in `engines/ports/`, then per port counted (a) implementor files under `graph/`, (b) referencing files outside `ports/` and `graph/`, (c) declared methods. Full table in Appendix A. |
| 2 | Tests that assert a constant / would pass with the feature deleted | **15** Confirmed tautologies (`*session_kwarg*`, feature already deleted, all pass — CR-L14-01); **127** passthrough-echo tests (`*_delegates`, `*_opens_one_session`, **1600 lines**) that patch the callee and assert the mock's own return value; **48** tests asserting `==` against a value they set as `return_value`; **47** zero-call zero-fixture tests (of which **12** are pure `CONST == literal`); **23** tests with no assertion of any kind; **18** tests asserting a string literal is `in` an ALLCAPS constant. Sets overlap; union approx **210** of 3857. | Six AST detectors over all 3857 test functions in `tests/`, plus one executed counterfactual (105 source methods gutted) and one direct execution proof. |
| 3 | Docstrings that restate the signature | **Sample = 1551** documented public functions in `src/npc_engine/` (of 1582 total; **31 have no docstring at all** despite the "mandatory" rule). Adding **0** new content words: **12 (0.8%)**. **<=1**: **88 (5.7%)**. **<=2**: **280 (18%)**. **Hypothesis largely disproven** — see CR-L14-07. The real docstring defect is **49 lines that document a parameter or signature that does not exist**. | AST: for each public function, tokenised the docstring summary and subtracted the token set derivable from the function name + parameter names + return annotation (stop-worded). Reported at three thresholds. |
| 4 | Logic scattered across files to respect the 300-line limit | **Disproven as stated.** Median `src/` file = **88 lines**; mean 108; only **28 of 627** files sit in the 250–299 band and **13 already exceed 300**. Files are not clustered against the cap. The fragmentation driver is a *different* rule — DIP-strict + the DEC-122/SEV-24 ports/repositories seam. Worst real cluster: **story_pacing, 5 files / ~610 lines for 2 Cypher queries** (chain traced in CR-L14-03). | `wc -l` over all 627 `src/` files, band histogram; then an end-to-end call-chain trace of one operation. |
| 5 | Near-duplicate helpers in sibling modules | **7** exact AST-shape clone families (19 functions) spanning 2+ different files. Semantic families are far larger: **175** copies of the `await connect(); async with get_session()` preamble across **38** repository files; **3** copies of the Neo4j→native recursive converter **with divergent error paths** (CR-L14-05). | Normalised every function body >=4 statements (names/attrs/constants/args erased), MD5-hashed the AST dump, grouped across files; plus targeted grep for the session preamble. |
| 6 | Defensive try/except around internal invariants | **84** `try` blocks in `src/` whose body calls an `npc_engine`-internal symbol; **17** of those catch bare `Exception`/`BaseException`; **3** swallow with neither a log nor a re-raise. | AST: for each `ast.Try`, resolved every call in the body against (a) names imported from `npc_engine.*` in that module and (b) top-level definitions in the same module; classified handlers. |

---

## Worst 10 overall

| # | file:line | What |
|---|---|---|
| 1 | `tests/unit/engines/test_military_engine.py:109` | `test_run_tick_ignores_scheduler_session_kwarg` — never passes `session=`; the `**_` it guards was deleted; passes anyway. x15 across the suite. |
| 2 | `src/npc_engine/engines/military/military_engine.py:34` | `run_tick` docstring documents a `**_` parameter absent from the signature. x22 engine files, 0 with a real `**kwargs`. |
| 3 | `src/npc_engine/scheduler/tick_scheduler.py:96` | 27 docstring lines promise `run_tick(session, tick_id)`; 0 of 30 engines accept a session. |
| 4 | `tests/unit/graph/test_story_pacing_repository.py:30` | Patches `get_active_high_severity_quests` with `AsyncMock(return_value=rows)`, then `assert result == rows`. x127 tests / 1600 lines. |
| 5 | `src/npc_engine/graph/repositories/story_pacing_repository.py:41` | 3-line passthrough. 117 of 180 repository methods (65%) are identical in shape; gutting 105 of them broke only their own delegate tests. |
| 6 | `src/npc_engine/engines/base_engine.py:24` | `async def run_tick(self, *args: Any, **kwargs: Any)` — types 33 scheduler parameters, enforces no signature. mypy stays clean with an incompatible engine wired in (executed). |
| 7 | `src/npc_engine/retrieval/context/context_builder_helpers.py:41` | `except Exception: return str(value)` around a recursive call to itself. Third copy of the converter; **error path diverges** from the other two. |
| 8 | `src/npc_engine/graph/graph_reader.py:212` | `except Exception: return value` — same helper, same silent swallow, different fallback. |
| 9 | `src/npc_engine/engines/ports/trait_read_port.py:17` | 1-method Protocol, **zero** implementors in `graph/`, one optional caller. |
| 10 | `tests/unit/engines/test_dialogue_models.py:33` | `assert MAX_PLAYER_MESSAGE_CHARS == 1000` — restates the constant's own definition. |

---

## Findings

### [CR-L14-01] Delete the 15 `session_kwarg` tests and the 49 docstring lines describing a parameter that no longer exists

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** The SEV-24 migration removed the `session=` kwarg from every tick engine. The tests and docstrings that guard it were not removed, and they still pass.

  ```
  $ PYTHONPATH=src python -c "...inspect.signature(MilitaryEngine.run_tick)..."
  MilitaryEngine.run_tick signature: (self, *, tick_id: 'int') -> 'dict[str, Any]'
  has **kwargs: False
  bind(session=..., tick_id=...) -> TypeError: got an unexpected keyword argument 'session'

  $ python -m pytest "tests/unit/engines/test_military_engine.py::test_run_tick_ignores_scheduler_session_kwarg" -q
  1 passed, 30 warnings in 0.16s
  ```

  That test's docstring reads *"run_tick accepts and ignores the scheduler's session= kwarg (SEV-24)."* It passes because it never passes `session=`. AST sweep of all 15 such tests: **`tests that DO pass session= to run_tick: 0`** — every one is a tautology. Files: `test_faction_politics_engine.py:222`, `test_goal_former_adapter.py:125`, `test_gossip_n_plus_one.py:170`, `test_intent_formation_engine.py:59`, `test_military_engine.py:109`, `test_mood_contagion_engine.py:111`, `test_need_decay_engine.py:124`, `test_proactive_tick_adapter.py:247`, `test_reputation_engine.py:193`, `test_routine_engine.py:93`, `test_skill_progression_engine.py:61`, `test_story_pacing_engine.py:114`, `test_succession_engine.py:81`, `tests/unit/graph/test_event_handler_port.py:113`, `tests/unit/graph/test_player_model_tick.py:91`.

  The same sweep over `src/`: **22 `run_tick` docstrings document `**_`, and 0 of them have a `**kwargs` in the signature** — `agenda_engine.py:46`, `intent_formation_engine.py:60`, `chapter_engine.py:107`, `clique_formation_engine.py:53`, `faction_politics_engine.py:52`, `gossip_handler.py:110`, `memory_decay_tick.py:40`, `military_engine.py:34`, `mood_contagion_engine.py:80`, `need_decay_engine.py:50`, `oath_engine.py:35`, `goal_former_adapter.py:73`, `player_model_tick.py:64`, `proactive_tick_adapter.py:86`, `reputation_engine.py:78`, `reputation_tick_adapter.py:76`, `routine_engine.py:46`, `scheme_advance_tick.py:63`, `skill_progression_engine.py:42`, `story_pacing_engine.py:57`, `succession_engine.py:45`, `treaty_engine.py:36`.

  And `grep -c 'run_tick(session' src/npc_engine/scheduler/tick_scheduler.py` → **27**, against `grep -rn "async def run_tick" -A2 src/npc_engine/engines/ | grep -c session` → **0**.
- **Cost of inaction:** The next person to add a tick engine reads `tick_scheduler.py:96-134` and 22 engine docstrings, all of which state the scheduler passes a session, and writes `run_tick(self, session, *, tick_id)`. The scheduler calls `engine.run_tick(tick_id=tick_id)` (`tick_scheduler.py:379`), so that engine raises `TypeError` on its first real tick — and the `BaseEngine` annotation will not catch it (CR-L14-04). This is a live trap, not latent debt.
- **Fix sketch:** Delete the 15 tests; strip the `**_:` lines from the 22 `Args:` blocks; rewrite the 27 `tick_scheduler.py` parameter docstrings to the real `run_tick(*, tick_id)` contract.
- **Effort:** S
- **Removes:** ~150 lines of tests + ~49 docstring lines
- **Blast radius:** Docstrings and tests only; no runtime behaviour changes.

### [CR-L14-02] The 127 `*_delegates` tests test only that a passthrough passes through — gutting 105 repository methods broke nothing above the repository layer

- **Severity:** HIGH
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** AST over `graph/repositories/` (39 files, 3778 lines): **117 of 180 public methods (65%)** have a body that is exactly `await self._graph_db.connect()` + `async with get_session() as s: return await <query>(s, ...)`. The `connect()+get_session()` preamble appears **175 times across 38 files**.

  The test guarding each one is `tests/unit/graph/test_story_pacing_repository.py:36-41`:

  ```python
  with patch(f"{_MOD}.get_active_high_severity_quests", new=AsyncMock(return_value=rows)) as mock_fn:
      result = await repo.get_active_high_severity_quests(threshold=70)

  assert result == rows                       # the mock's own return value
  assert db.connect_calls == 1
  mock_fn.assert_awaited_once_with(session, 70)
  ```

  It patches away the only thing that carries risk (the Cypher), then asserts the mock echoed itself.

  **Executed counterfactual:** in the tree copy I rewrote all 105 type-safely-guttable passthrough bodies to a constant empty return (`return []` / `None` / `0` / `False`).

  - `python -m mypy src/` → `Success: no issues found in 627 source files`
  - `pytest tests/unit` → `103 failed, 3931 passed` vs baseline `37 failed, 3997 passed` = **66 new failures**, and **every one is in `tests/unit/graph/test_*_repository.py` or `tests/unit/retrieval/test_proactive_memory_read_repository.py`**. Zero engine, API, scheduler, or conformance tests noticed that the entire graph read layer had started returning nothing.
  - 105 methods gutted produced 66 failures, so roughly 39 gutted methods have no test at all.

  The Cypher those repositories exist to reach — **183 query functions** in `graph/*/*queries*.py` — is exercised only by `tests/integration/`, and `pytest tests/integration -q` in the default environment prints **`9 passed, 34 skipped`** (every DB test guards on `NEO4J_URI`, e.g. `tests/integration/test_faction_integration.py:30`). `make check` → `test-cov` → `pytest tests/`, so CI runs the skipping version.
- **Cost of inaction:** Ships now. A Cypher regression — a renamed property, a dropped `WHERE`, a wrong `MERGE` — is caught by no test that runs in `make check`. 1600 lines of test are spent proving that 3-line passthroughs pass through, which reads as coverage and is not.
- **Fix sketch:** Delete the 127 delegate tests; replace the per-domain repositories with one generic `SessionPerCall` helper that wraps any query function; move the freed test budget to running `tests/integration` against a Dockerised Neo4j in `make check`.
- **Effort:** L
- **Removes:** ~1600 lines of tests + ~470 lines of passthrough bodies (~2070)
- **Blast radius:** All 44 ports, 39 repositories, and the `api/dependencies_engines/` composition root; requires Neo4j in CI to be a net gain rather than a net loss.

### [CR-L14-03] The DIP-strict ports seam costs 8565 lines and 107 files to move calls from engines to query functions

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Debt
- **Evidence:** Traced end to end, one operation — "get recent major events":

  1. `src/npc_engine/engines/story_pacing/story_pacing_engine.py:71` → `self._get_recent_major_events(tick_id)`
  2. `story_pacing_engine.py:128` → `self._story_pacing_repo.get_recent_major_events(min_tick_id=..., floor=...)`
  3. type declared at `src/npc_engine/engines/ports/story_pacing_port.py:29` (re-states the signature verbatim)
  4. concrete at `src/npc_engine/graph/repositories/story_pacing_repository.py:41` (opens a session, delegates)
  5. Cypher at `src/npc_engine/graph/narrative/story_pacing_queries.py:63`, constant at `:29`
  6. wired at `src/npc_engine/api/dependencies_engines/core.py:167-182`

  **5 files** to run one query; the whole `engines/story_pacing/` domain is 230 lines across 4 files. Aggregate cost of the seam: `engines/ports/` 40 files / **2088 lines** / 169 re-declared signatures + `graph/repositories/` 39 files / **3778 lines** + `tests/unit/graph/test_*_repository.py` 28 files / **2699 lines** = **107 files, 8565 lines**.

  The seam is *not* free of value — mypy does catch adapter drift. Executed: renaming `floor` to `severity_floor` and changing the return type on `Neo4jStoryPacingRepository.get_recent_major_events` produced

  ```
  src\npc_engine\api\dependencies_engines\core.py:182: note:     Expected:
  src\npc_engine\api\dependencies_engines\core.py:182: note:         def get_recent_major_events(self, *, min_tick_id: int, floor: int) -> Coroutine[Any, Any, list[dict[str, Any]]]
  src\npc_engine\api\dependencies_engines\core.py:182: note:     Got:
  src\npc_engine\api\dependencies_engines\core.py:182: note:         def get_recent_major_events(self, *, min_tick_id: int, severity_floor: int) -> Coroutine[Any, Any, list[str]]
  Found 1 error in 1 file (checked 627 source files)
  ```

  So the port earns its keep for *signature* conformance at the composition root. It buys nothing for *behaviour* (CR-L14-02).

  Least-justified ports — one caller, one method, and for `TraitReadPort` no implementor at all: `engines/ports/trait_read_port.py:17` (0 impl / 1 caller / 1 method), `emotion_bootstrap_port.py:19` (1/1/1), `emotion_port.py:18` (1/1/1), `player_model_port.py:18` (1/1/1), `quest_port.py:52` `QuestOfferGraphPort` (1/1/3), `quest_port.py:75` `QuestRewardGraphPort` (1/1/4), `quest_port.py:21` `QuestLifecycleGraphPort` (1/1/5), `story_pacing_port.py:20` (1/1/2), `routine_port.py:19` (1/1/4), `faction_politics_port.py:21` (1/1/4).
- **Cost of inaction:** Every new graph read costs 4 file edits and a mypy round-trip. At the observed commit rate this is the single largest recurring tax in the tree.
- **Fix sketch:** Keep ports where there is real substitution or 3+ callers (`ClockPort` 16 callers, `WorldStateGraphPort` 6, `RelationReadPort` 6, `PlayerLocationReadPort` 6); collapse the 14 one-caller ports into the engine module that consumes them, and reach the query function directly.
- **Effort:** L
- **Removes:** ~552 lines across the 10 named single-caller port files (more if the full seam goes with CR-L14-02)
- **Blast radius:** `engines/ports/__init__.py` public surface, the composition root, and the layer checker's allow-list.

### [CR-L14-04] `BaseEngine` types 33 scheduler parameters and enforces no signature — mypy stays clean with an incompatible engine

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Risk
- **Evidence:** `src/npc_engine/engines/base_engine.py:24`:

  ```python
  async def run_tick(self, *args: Any, **kwargs: Any) -> dict[str, Any]: ...
  ```

  Its own docstring concedes the point: *"without enforcing a specific signature, since each engine's required parameters differ."* It is nonetheless the declared type of 33 constructor parameters (`tick_scheduler.py:52-82`) and 4 helper parameters (`:342`, `:375`, `:405`, `:424`), and the scheduler always calls `engine.run_tick(tick_id=tick_id)` (`tick_scheduler.py:379`, `:410`).

  **Executed counterfactual:** changed `MilitaryEngine.run_tick(self, *, tick_id: int)` to `(self, *, at_tick: int)` with an internal alias so the body still typechecks. `python -m mypy src/` → **`Success: no issues found in 627 source files`**, with a scheduler call site that would raise `TypeError` on the first military tick. The only tests that failed were `MilitaryEngine`'s own four — the safety came from the engine's unit tests, not from the protocol that exists to provide it.
- **Cost of inaction:** A new engine wired into the scheduler with a mismatched `run_tick` passes `make check` and fails at the first tick in staging. `_run_distributed_interval` catches the `TypeError` and logs `tick_engine_error` (`tick_scheduler.py:387`), so the engine silently never runs.
- **Fix sketch:** Narrow `BaseEngine.run_tick` to the signature the scheduler actually calls — `async def run_tick(self, *, tick_id: int) -> dict[str, Any]` — and give the few engines with different needs their own protocols (ISP), rather than widening the shared one to `Any`.
- **Effort:** M
- **Blast radius:** 33 `tick_scheduler.py` parameters and ~30 engine signatures; mypy will name every mismatch, which is the point.

### [CR-L14-05] Three copies of the Neo4j-to-native converter with divergent error paths, each silently swallowing around a call to itself

- **Severity:** MEDIUM
- **Confidence:** Confirmed
- **Kind:** Defect
- **Evidence:** The same recursive converter exists in three layers with identical structure:

  - `src/npc_engine/graph/graph_reader.py:199` `_to_native` → `except Exception: return value`
  - `src/npc_engine/graph/generic/generic_graph_utils.py:134` `to_native` → `except Exception: return value`
  - `src/npc_engine/retrieval/context/context_builder_helpers.py:21` `to_json_safe` → `except Exception: return str(value)`

  The AST-shape scan groups the first two as an exact clone family; the third escapes exact matching *only* because of the divergent fallback. So the same Neo4j value that reaches a prompt via `context_builder` serialises as `str(value)`, and via `graph_reader` as the raw driver object.

  All three violate two strict CLAUDE.md rules at once: *"No try/except around internal invariants"* (the `try` wraps a recursive call to the function itself, on an in-memory value) and *"Never swallow errors"* (no re-raise, no log). These are 3 of the 84 internal-call `try` blocks and 3 of the 17 with a bare `Exception` handler. Companions: `src/npc_engine/engines/dialogue/session_store.py:178` (logs, does not re-raise), `src/npc_engine/engines/dialogue/degradation.py:103` and `:115` (broad `except Exception` around `increment_metric` — a metrics counter, not a boundary), `src/npc_engine/api/routes/dialogue/interaction.py:216`, `src/npc_engine/api/routes/economy/groups.py:151`, `src/npc_engine/graph/graph_writer.py:182` and `:258`, `src/npc_engine/graph/relations/relation_delta_writer.py:140`, `src/npc_engine/main.py:242`.
- **Cost of inaction:** A driver type that fails `to_native()` produces two different prompt payloads depending on the read path, with no log line anywhere. Debugging that costs a day and starts from a silent divergence.
- **Fix sketch:** Keep `generic_graph_utils.to_native` as the single implementation, delete the other two, and drop the `try` entirely — a `to_native()` that raises is a driver bug that should surface, not be papered over.
- **Effort:** S
- **Removes:** ~30 lines and 2 functions
- **Blast radius:** `graph_reader`, `context_builder_helpers`, and the `retrieval → graph` import edge.

### [CR-L14-06] 47 zero-call tests and 23 assertion-free tests, of which 12 restate a constant's own definition

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Waste
- **Evidence:** AST over all 3857 test functions: **47** have an `assert` but make no call at all and take no fixture; **23** have no `assert`, no `pytest.raises`, no `fail()`, and no `mock.assert_*`. The purest tautologies:

  - `tests/unit/engines/test_dialogue_models.py:33` — `assert MAX_PLAYER_MESSAGE_CHARS == 1000`
  - `tests/unit/retrieval/test_sentence_encoder.py:44` — `assert EMBED_DIMENSION == 384`
  - `tests/unit/engines/test_relationship_standing.py:74` — `assert HOSTILE_MAX == -50` ... `assert ALLIED_MIN == 50`, docstring *"Band cutoffs must be exposed as named module constants (not magic numbers)"*, which is what the `import` at the top of the file already proves
  - `tests/unit/engines/test_knowledge_types.py:20` — `assert KNOWLEDGE_STATE_KNOWS == "knows"`
  - `tests/unit/conformance/test_ocp_residuals.py:117` — `assert SchemeStepKind.ADVANCE == "scheme_advance"`
  - `tests/unit/conformance/test_clock_port_conformance.py:41,46` — `assert not hasattr(ClockPort, "advance")`, asserting on the content of a Protocol declaration file

  Related family: **18** tests assert a string literal is `in` an ALLCAPS constant — e.g. `tests/unit/world/test_world_state_clock_fields.py:62` asserts `"w.tick_id = CASE WHEN" in CYPHER_MERGE_WORLD_STATE`, and `tests/unit/conformance/test_sev04_gossip_graph_layer.py:30-45` asserts `"MERGE" in CYPHER_PROPAGATE_KNOWLEDGE`. These pass whether or not the query is ever executed, and would pass if the caller were deleted — which, per CR-L14-02, is exactly the situation the repository layer is already in.
- **Cost of inaction:** Low direct harm; the cost is that these inflate the apparent test count (70 of 3857) and read as behavioural coverage to the loop that generated them, which then does not write the real test.
- **Fix sketch:** Delete the 12 constant-restating tests. Replace the 18 Cypher-substring tests with integration tests that run the query (blocked on CR-L14-02's CI Neo4j).
- **Effort:** S
- **Removes:** ~120 lines
- **Blast radius:** None.

### [CR-L14-07] The docstring mandate is enforced by a gate that never reads a function docstring — and vacuity is not the problem

- **Severity:** LOW
- **Confidence:** Confirmed
- **Kind:** Process
- **Evidence:** CLAUDE.md requires a docstring on *"every public function"*, *"every public class"*, and every `__init__.py`. `make check-docstrings` runs `scripts/docstring_audit.py`, whose entire contract is `_extract_module_docstring` plus a substring check for `Layer:` and `Purpose:` (`scripts/docstring_audit.py:17`, `:38`, `:44`). It never visits a `FunctionDef`. Consequently **31 public functions in `src/npc_engine/` have no docstring at all** and the gate is green.

  The vacuity hypothesis is largely **disproven**: over a sample of all **1551** documented public functions, only **12 (0.8%)** add zero content words beyond the name/params/return type, **88 (5.7%)** add <=1, **280 (18%)** add <=2. Representative of the worst: `engines/tts/mock_adapter.py:43` `def backend_name` → *"Return 'mock'."*; `engines/ports/military_port.py:39` `def set_army_strength` → *"Update the strength of an army."*; `api/routes/knowledge/beliefs.py:86` `def seed_belief` → *"Seed a new belief on a character."*

  The real docstring defect in this tree is not emptiness but **falsity** — 49 lines that describe a parameter and a call convention that do not exist (CR-L14-01). No gate can see that either.
- **Cost of inaction:** The mandate produces volume the gate cannot grade, so the gate certifies nothing while implying it certifies a lot.
- **Fix sketch:** Either extend `docstring_audit.py` to check public functions (and to fail when an `Args:` entry names a parameter absent from the signature — that one check catches all 22 of CR-L14-01), or relax the CLAUDE.md rule to "module + public class" and stop claiming per-function coverage.
- **Effort:** S
- **Blast radius:** `scripts/docstring_audit.py` and `make check`; extending it will fail the build on 31 files until they are fixed.

---

## CLAUDE.md rules to change

These smells are consequences of the rules, not deviations from them. Changing the rule is worth more than fixing the instances.

1. **"DIP (strict): engines import `LLMClientProtocol`, never `MistralAdapter`... All concrete dependencies injected via `__init__`."** — Read as "every graph read needs a Protocol", it produced 44 ports / 2088 lines / 169 re-declared signatures, 14 of them with a single caller and 10 with a single method. **Change to:** require a Protocol only where there are 2+ implementors or 3+ callers, or a declared intent to substitute. Single-caller graph reads call the query function directly.
2. **"ISP (strict): protocols must be small."** — Combined with SRP-strict it produced 40 port files averaging 52 lines. `BaseEngine` shows the failure mode from the other side: when one protocol *must* cover 33 call sites, "small" became `(*args, **kwargs)`, which is not a contract. **Change to:** protocols must be *precise*; `Any`-typed varargs in a Protocol are a rule violation, not a compromise.
3. **"Hard limit: 300 lines of non-test code per file."** — **Keep it.** The data does not support blaming it: median file is 88 lines and only 28 of 627 sit in the 250–299 band. It is not what fragmented this tree; rules 1 and 2 are.
4. **"Every public function has a docstring."** — Unenforceable by the gate that claims to enforce it (CR-L14-07), and the failure mode it produced is stale docstrings, not missing ones. **Change to:** add "an `Args:` entry must name a parameter that exists in the signature" and make `docstring_audit.py` check it. That single rule would have caught all 22 phantom `**_` blocks and the 27 `tick_scheduler.py` lines.
5. **"No try/except around internal invariants" / "Never swallow errors."** — Correctly stated, unenforced: 84 internal-call `try` blocks, 17 with bare `Exception`. `tests/unit/conformance/test_error_swallowing_sev18.py` exists but did not stop any of the three in CR-L14-05. **Change:** nothing in the rule; add the AST check to `make check`.

**Total proposed for deletion: ~4,320 lines** at the full-seam ceiling. Conservative floor, excluding the full ports/repositories collapse: **~2,970 lines** — 1600 (delegate tests) + 552 (single-caller ports) + 470 (passthrough bodies) + 150 (session-kwarg tests) + 120 (constant tests) + 49 (false docstring lines) + 30 (duplicate converters).

---

## Appendix A — ports: implementors x callers x methods

`IMPL` counts files under `graph/` naming the port (2 = the repository plus `repositories/__init__.py`, i.e. one real implementor). `CALLERS` counts files outside `ports/` and `graph/`.

| Port | IMPL | CALLERS | METHODS |
|---|---|---|---|
| TraitReadPort | 0 | 1 | 1 |
| DialogueContextPort | 0 | 3 | 1 |
| ClockPort | 0 | 16 | 1 |
| QuestLifecycleGraphPort | 1 | 1 | 5 |
| QuestOfferGraphPort | 1 | 1 | 3 |
| QuestRewardGraphPort | 1 | 1 | 4 |
| QuestChainGraphPort | 1 | 2 | 3 |
| EmotionBootstrapGraphPort | 2 | 1 | 1 |
| EmotionGraphPort | 2 | 1 | 1 |
| FactionPoliticsGraphPort | 2 | 1 | 4 |
| InvestigationGraphPort | 2 | 1 | 6 |
| MemoryGraphPort | 2 | 1 | 3 |
| NeedTriggerGraphPort | 2 | 1 | 2 |
| PlayerModelGraphPort | 2 | 1 | 1 |
| RoutineGraphPort | 2 | 1 | 4 |
| StoryPacingGraphPort | 2 | 1 | 2 |
| EventGraphPort | 5 | 1 | 5 |
| ChapterGraphPort | 2 | 2 | 9 |
| CharacterReadPort | 2 | 2 | 1 |
| EconomyGraphPort | 2 | 2 | 6 |
| EventTriggerGraphPort | 2 | 2 | 3 |
| GroupGraphPort | 2 | 2 | 6 |
| MemoryConsolidationGraphPort | 2 | 2 | 4 |
| MoodGraphPort | 2 | 2 | 3 |
| NeedGraphPort | 2 | 2 | 2 |
| PledgeGraphPort | 2 | 2 | 4 |
| ProactiveMemoryReadPort | 2 | 2 | 1 |
| QuestGenerationGraphPort | 2 | 2 | 10 |
| RelationPhaseWritePort | 2 | 2 | 1 |
| ReputationGraphPort | 2 | 2 | 1 |
| TreatyGraphPort | 2 | 2 | 4 |
| DialogueGraphPort | 2 | 3 | 5 |
| GossipGraphPort | 2 | 3 | 10 |
| IntentGraphPort | 2 | 3 | 7 |
| KnowledgeGraphPort | 5 | 3 | 2 |
| PoliticalGraphPort | 2 | 3 | 6 |
| SchemingGraphPort | 2 | 3 | 8 |
| SkillGraphPort | 2 | 3 | 2 |
| InteractionGraphPort | 2 | 4 | 7 |
| PlanningGraphPort | 2 | 4 | 5 |
| MilitaryGraphPort | 2 | 5 | 9 |
| PlayerLocationReadPort | 2 | 6 | 2 |
| RelationReadPort | 2 | 6 | 2 |
| WorldStateGraphPort | 2 | 6 | 2 |
