
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
