# FIX-SEV-02 — Residual error-message leakage in 3 route sites

**Severity:** HIGH · **Lens:** L1 (L1-08), L8 (L8-02). Prior SEV-16 / L1-02 = PARTIAL.

## Problem
The shared `graph_error_to_http` redaction landed, but three sites bypass it and echo internal details to
HTTP clients:
1. `require_node` echoes the user-controlled URL `node_type` into the 404 `detail` string (L1-08).
2. `locations.py` returns `str(exc)` of a `ValueError` (may contain internal schema paths) in a 422 body (L8-02).
3. `economy.py` returns `exc.node_id` (an internal graph node identifier) in a 400/422 body (L8-02).
The redaction guard test covers only 4 of the 6 route files and does not reach these.

## Current shape (verify line numbers against code now)
- `src/npc_engine/api/route_helpers.py:120` — `require_node` 404 detail includes `node_type`. Call sites `api/routes/graph.py:53,138`.
- `src/npc_engine/api/routes/locations.py:88` — `raise HTTPException(..., detail=str(exc))`.
- `src/npc_engine/api/routes/economy.py:129` — detail includes `exc.node_id`.
- Guard test: `tests/.../test_route_error_redaction.py` (covers 4/6 route files).

## Steps
1. In `require_node`, replace the interpolated `node_type` with a fixed constant string (e.g. `"resource not found"`); log the real `node_type` server-side via structured logging only.
2. In `locations.py` and `economy.py`, route the error through `graph_error_to_http` (or a fixed client-safe detail), keeping the internal value in a server-side log, not the HTTP body.
3. Extend `test_route_error_redaction.py` to cover all 6 route files including `locations` and `economy`, asserting the response body does **not** contain the internal value.

## Verification
- `pytest tests/ -k route_error_redaction -q` — assert the 422/404 bodies contain only the fixed string, NOT the node id / node type / `str(exc)`.
- `make check`.

## Blast radius
`api/route_helpers.py`, `api/routes/locations.py`, `api/routes/economy.py`, one test file. No interface/schema change (response bodies were never part of a typed contract).
