
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
