# FIX-SEV-16 — Stop leaking internal exception detail in HTTP responses

**Severity:** HIGH · **Confidence:** Confirmed · **Effort:** S
**Category:** security · **Absorbs:** PY-08, SEC-07, SEC-08

## Problem
Several routes serialize raw exception text (class name + message) into the HTTP response body, exposing the DB driver, hostnames, Neo4j error codes, internal field names, and node IDs to any caller.

## Current shape (all instances)
- `api/routes/clock.py:100-101`:
  ```python
  except Exception as exc:
      raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}") from exc
  ```
- `api/routes/debts.py:81` and `:127` — `detail=str(exc)`
- `api/routes/groups.py:151` — `detail=str(exc)`
- `api/routes/quest_generation.py:54` — `detail=str(exc)` (`str(NodeNotFoundError)` echoes `node_type`/`node_id`)

The correct pattern already exists: `api/route_helpers.py:79` `graph_error_to_http` and `error_response(error_code=..., message=...)`.

## Target shape
Clients receive a static, safe message + error code; full detail is logged server-side only.

## Steps
1. **Generic 500s** (`clock.py:100-101`): replace with
   ```python
   except Exception as exc:
       logger.exception("clock_advance_failed", extra={"error": type(exc).__name__})
       raise HTTPException(status_code=500,
           detail=error_response(error_code="INTERNAL_ERROR", message="An internal error occurred.")) from exc
   ```
2. **Domain exceptions** (`debts`, `groups`, `quest_generation`): route through `graph_error_to_http(exc)` (already imported in most files) which maps typed errors to status + safe envelope.
3. **`ValueError`/validation**: return a static `"Invalid request parameter"` and log the detail.
4. Grep-audit all routes for `str(exc)` / `{exc}` in `detail=` and fix any others.

## Verification
- Inject a `RuntimeError("bolt://internal:7687 refused")` into the clock path → response body contains no class name / Neo4j code / hostname.
- A malformed debt request → body has no Python exception text.
- `make smoke` still green (it already checks "403 not 500").

## Blast radius
clock, debts, groups, quest_generation routes (+ any others the grep surfaces). Low-risk, high-value; pairs with SEV-33 (one consistent error envelope).
