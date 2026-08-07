
## 2026-08-05 14:16:46 — phase EVAL-P0

**5 findings from EVAL-P0.2 diff:**

1. **Import path mismatch in engine_adapter.py** — Line 31 imports from `npc_engine.retrieval.embedding`, but retrieval_runner.py originally imported from `npc_engine.retrieval.embedding_index` and `npc_engine.retrieval.vector_store_factory` (two separate modules). Verify these new consolidated import paths actually exist in npc_engine; if the real modules haven't been refactored, this will fail at runtime.

2. **test_src_free.py guard checks wrong filenames** — Line 104 asserts files `retrieval_runner.py`, `runner.py`, and `matchers.py` exist. But:
   - retrieval_runner.py imports from `retrieval_matchers`, not `matchers.py`
   - `runner.py` isn't created by this task and likely doesn't exist
   
   Guard test will fail when run unless these files match expectations.

3. **Type hints collapse to `Any`** — `build_retrieval_stack() → tuple[Any, Any]` and `known_event_ids(..., session: Any)` are correctly generic to avoid importing npc_engine types, but callers have no type guidance on what's returned or what session type is accepted. Consider TypeVar or forward refs to preserve some contract.

4. **No input validation** — `known_event_ids(session, npc_id)` passes both directly to npc_engine without checking session is a Neo4j AsyncSession or npc_id is a valid node ID. Boundary validation at the adapter's entry point would fail fast.

5. **Unsafe dict access in retrieval_runner** — Line 103 does `ranked: list[str] = [r["id"] for r in vector_results]` without guarding that each result dict contains "id". If embedding index changes its response schema, this raises KeyError silently until runtime.

## 2026-08-06 13:55:08 — phase EVAL-P1

Now reviewing the EVAL-P1.4 / EVAL-P1.3 / EVAL-P1.1 diffs. Here are my findings:

## Concrete Findings

1. **Module docstring missing** in `evals/context_capture.py:1-40`. Adds a new module `context_capture` that doesn't follow the standard module-docstring pattern (should have `Module:`, `Layer:`, `Purpose:`, `Dependencies:`, `Used by:` fields per CLAUDE.md §Documentation). The file has a partial docstring but doesn't conform to the strict format.

2. **Exception handling overly broad** in `evals/context_capture.py:183`. `except Exception: return ()` silently swallows all errors (network timeouts, malformed JSON, etc.) when capturing retrieval context. Should catch specific exceptions (httpx.HTTPError, json.JSONDecodeError) and log failures, per CLAUDE.md §Error handling "never swallow errors."

3. **Immutability violation** in `evals/generate_runner.py:525-526`. Uses `.model_copy(update={...})` to patch fields on GenerationRecords during the k-repeat loop. This is correct, but the pattern chains multiple `update` calls on the same record — should verify no in-place mutation happens in nested context_capture calls.

4. **TranscriptVersionError exception not used** in tests. The new `TranscriptVersionError` is defined in `evals/eval_records.py:250-264` but there's no integration test confirming `read_transcript()` actually raises it when version mismatches occur (v1 → v2). Schema version enforcement works, but error path is untested.

5. **Project-rule violation: Makefile output directory change is silent**. `eval-generate` switched default `--out` from `e2e/transcripts/` to `evals/generations/` without updating downstream consumers. Judge pass still reads from legacy location by default — coupling risk if eval-generate output path diverges. Should verify judge_runner defaults match or add explicit path coordination in CI recipes.

## 2026-08-06 23:52:52 — phase EVAL-P3

**EVAL-P3 Diff Review: 5 Findings**

1. **CLI can't score knowledge meaningfully** — `deterministic_pass.py:237` hardcodes `npc_known_events={}`, so the CLI always reports 100% knowledge_rate (assuming event mentions). The main() function has no parameter to supply NPC known-events, limiting real-world CLI use to entity scoring only. Documented limitations should be in the module docstring, not buried in the score_transcript() params.

2. **Redundant denominator field** — `summary.py:127-128` introduces `evaluated_cases` (total_cases - skipped_cases) then immediately sets `total_turns = evaluated_cases`, making the two fields identical. While this clarifies intent, the docstring at line 49 should explain why both fields exist instead of just renaming total_turns.

3. **API response format assumption** — `graph_vocabulary.py:100` assumes the JSON response has a `"data"` key without validation: `resp.json()["data"]`. If the endpoint returns unexpected structure, this raises an uncaught KeyError. No docstring states the expected response schema.

4. **Missing entity-rate edge case test** — All alias tests use known entities. No test covers a scenario where an entity mention has no alias in the table at all (e.g., an NPC name spoken for the first time). This is documented as "out of scope" but should have an explicit test confirming zero mentions for unaliased text.

5. **Knowledge scorer false-positive risk not tested** — `knowledge_scorer.py:18-22` warns that beliefs/goals/memories aren't in npc_known_event_ids, causing false violations. No test verifies this edge case or documents which knowledge sources ARE included. The docstring should reference a test that demonstrates the risk.

**All tests pass.** No file exceeds 300 lines. Module docstrings present.

## 2026-08-07 00:57:53 — phase EVAL-P4

## Findings (EVAL-P4 commits)

**1. Layer not defined (CLAUDE.md violation)**  
Module docstrings declare `Layer: evals (evaluation harness)`, but evals is not in CLAUDE.md's official layer model (which lists: api, auth, data, engines, scheduler, services, cache, retrieval, graph, mutation, world, config, common, type_registry, schema, utils). Either add evals to CLAUDE.md or reassign files to data/.

**2. Precision computed but unused**  
retrieval_join.py:126 computes `precision_at_k`, but only `recall` determines `retrieval_hit` (line 129). Precision is exposed in `PerRecordResult` but never used. Design choice is undocumented.

**3. RECALL_HIT_THRESHOLD=0.0 not tested for value**  
Threshold set to 0.0 means any recall > 0 is a hit. Tests validate boundary cases (0 vs >0) but not the threshold value itself. If threshold changes, no test catches it.

**4. record_id format not validated**  
`_case_id_from_record_id()` assumes format `<case_id>:<judge_kind>:<index>` but doesn't validate. Malformed record_ids (e.g., no colon) silently produce incorrect case_id values.

**5. Hard-coded case count in regression test**  
`test_guard_case_total_is_37()` requires manual update whenever cases are added/deleted, making it brittle despite being intentional.

## 2026-08-07 17:34:02 — phase EVAL-P1

Looking at EVAL-P1.6 (persist judge pass verdicts), here are 5 concrete findings:

**1. Missing path validation for --json-out** — `main()` validates `--transcript` exists upfront but skips validation for `--json-out`. If the parent directory can't be created (permission, path issues), file I/O fails deep in `_write_judged_jsonl()` with a generic exception instead of a clear error message. Should check write-ability early or catch and report clearly (inconsistent with line 234-235 error handling for transcript).

**2. Unexplained rsplit magic in case_id extraction** — Line in `_write_judged_jsonl()`:
```python
"case_id": r.record_id.rsplit(":", _RECORD_ID_COLON_SEGMENTS)[0],
```
The constant `_RECORD_ID_COLON_SEGMENTS=2` extracts the prefix correctly but lacks a comment explaining why this works. The name `_RECORD_ID_COLON_SEGMENTS` is ambiguous (could mean segment count, not rsplit maxsplit). One-line comment needed per CLAUDE.md rule.

**3. Test gap: nested directory creation untested** — `test_json_out_writes_one_row_per_judged_record()` writes to `tmp_path / "judged.jsonl"` (single level), never testing `mkdir(parents=True, exist_ok=True)` on deeply nested paths like `tmp_path / "a/b/c/judged.jsonl"`.

**4. No test for write failures** — Test suite doesn't cover permission errors, disk full, or path-is-a-file scenarios when calling `_write_judged_jsonl()`. If `path.write_text()` fails, the exception propagates uncaught, crashing the judge run.

**5. Inconsistent encoding constant usage in tests** — `test_judged_records.py` hardcodes `encoding="utf-8"` instead of using the module-level `_JSONL_ENCODING` constant. Test should import and use the same constant.
