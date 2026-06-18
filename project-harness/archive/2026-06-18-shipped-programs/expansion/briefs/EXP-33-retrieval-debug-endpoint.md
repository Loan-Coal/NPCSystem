# EXP-33 — Retrieval debug endpoint (Phase 15 S15.1)

**Goal / rationale:** EXP-31 proved retrieval *math* works. S15.1 needs a live API surface so the
eval runner and developers can retrieve ranked context-item IDs for an (npc_id, query) pair without
reading source code. This is the "retrieval inspection surface" from ROADMAP Phase 15 S15.1.

**First slice (worker scope):** New `GET /v1/debug/retrieval` route (graph_admin scope) that calls
the retrieval pipeline for a given `npc_id` and `query` and returns the ranked context items with
their scores. Route registered under the existing admin prefix in `main.py`.

**Current state (verified):**
- No debug retrieval route exists: `grep -r "debug/retrieval" src/` → 0 hits.
- `src/npc_engine/api/routes/` directory has 30+ route files; add one more.
- `src/npc_engine/main.py:331–355` registers all admin routes via `app.include_router(..., prefix=admin_prefix)`.
  Pattern: `from npc_engine.api.routes.graph_admin import router as graph_admin_router` then
  `app.include_router(graph_admin_router, prefix=admin_prefix)`.
- `build_serialized_context()` is the retrieval entry point: `src/npc_engine/retrieval/context_builder.py:95`.
  It takes `(npc_id, player_message, session, embedding_index, settings, ...)` and returns a JSON string.
  For the debug route, the `player_message` can be the `query` param.
- Auth pattern: `get_db_session` + `get_embedding_index` from `src/npc_engine/api/dependencies.py`
  (same as other admin routes). No separate graph_admin_scope middleware — admin prefix is sufficient.

**Files:**
- NEW `src/npc_engine/api/routes/debug_retrieval.py` — `GET /debug/retrieval?npc_id=&query=` route.
  Returns `{"npc_id": str, "query": str, "context_items": [...], "total_tokens": int}`.
  Each item: `{"key": str, "tier": str, "priority": int, "text": str}`.
  Parse `build_serialized_context()` output (JSON) to build the item list.
- EDIT `src/npc_engine/main.py` — add import + `app.include_router(debug_retrieval_router, prefix=admin_prefix)`.
- NEW `tests/unit/test_debug_retrieval_route.py` — unit test with mocked `build_serialized_context`.

**Graph/API surface:** New admin GET endpoint. No schema change. Response is a Pydantic v2 model.
Route shape: `GET /admin/debug/retrieval?npc_id=mira_innkeeper&query=war+news`
Response:
```json
{
  "npc_id": "mira_innkeeper",
  "query": "war news",
  "context_items": [
    {"key": "npc_known_events:0", "tier": "tierA", "priority": 90, "text": "..."}
  ],
  "total_tokens": 842
}
```

**Architecture fit:** New-file-add for the route. `main.py` edit is a one-line `include_router` add —
same pattern as every other admin route. Route imports from `retrieval/` layer (allowed: api → retrieval).
Pydantic v2 response model in the route file.

**Test plan:**
Write `tests/unit/test_debug_retrieval_route.py` FIRST:
- Patch `build_serialized_context` to return a known JSON string with one context item.
- Call the route handler directly (not via HTTP client) with a `MockAsyncSession`.
- Assert the response contains the expected `context_items` entry.
Run: `pytest tests/unit/test_debug_retrieval_route.py -q`

**Done when:** Unit test green AND a manual `curl /admin/debug/retrieval?npc_id=mira_innkeeper&query=war`
against the live stack returns a JSON list of ranked items (not an empty list, not a 500).
