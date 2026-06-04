# FIX-SEV-33 — Consistent error envelope for integrators

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** M
**Category:** api · **Absorbs:** GAME-07

## Problem
The API returns four incompatible error shapes:
- **Middleware errors**: `{"detail": "Forbidden"}` (FastAPI default)
- **Idempotency errors**: `{"error_code": "..."}` (custom, inconsistent key)
- **FastAPI validation errors**: `{"detail": [{"loc":..., "msg":..., "type":...}]}`
- **Success**: `{"data": ..., "meta": ...}` via `ok_response()` — correct shape

`demo_game/client.py:1400-1407` defensively probes all four shapes. Any integrator must do the same. The SEV-16 carry-forward already established the `error_response(...)` pattern with `get_logger` for route-level errors — this fix unifies the envelope at the middleware/exception-handler level.

## Target shape
All errors return `{"error": {"code": "...", "message": "...", "details": [...]}}`.

## Steps

### 1. Define the envelope model
Add `src/npc_engine/api/schemas/error_envelope.py`:
```python
class ErrorDetail(BaseModel):
    field: str | None = None
    reason: str

class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = []

class ErrorEnvelope(BaseModel):
    error: ErrorBody
```

### 2. Add FastAPI exception handlers in `main.py`
```python
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request, exc):
    details = [ErrorDetail(field=str(e["loc"]), reason=e["msg"]) for e in exc.errors()]
    return JSONResponse(status_code=422,
        content=ErrorEnvelope(error=ErrorBody(code="validation_error",
            message="request validation failed", details=details)).model_dump())

@app.exception_handler(HTTPException)
async def http_error_handler(request, exc):
    return JSONResponse(status_code=exc.status_code,
        content=ErrorEnvelope(error=ErrorBody(code=f"http_{exc.status_code}",
            message=exc.detail)).model_dump())

@app.exception_handler(Exception)
async def internal_error_handler(request, exc):
    get_logger().error("unhandled_exception", exc=str(exc))
    return JSONResponse(status_code=500,
        content=ErrorEnvelope(error=ErrorBody(code="internal_error",
            message="internal error")).model_dump())
```

### 3. Update existing error sites
- `auth/middleware_helpers.py` 401/403 responses: use `ErrorEnvelope`.
- Idempotency middleware: replace `{"error_code": ...}` with `ErrorEnvelope`.
- Any route using `{"detail": ...}` directly: replace with `error_response(...)` (SEV-16 pattern).

### 4. Update `demo_game/client.py`
Replace the four-shape probe in the error handler (`:1400-1407`) with a single read of `response["error"]["code"]`.

### 5. Document in `docs/API.md`
Add a "Error responses" section showing the `ErrorEnvelope` schema and the code values.

## Verification
- `tests/unit/test_error_envelope_sev33.py`:
  - Mock a 422 validation error → response is `ErrorEnvelope` shape, code is `"validation_error"`.
  - Mock a 401 → `{"error": {"code": "http_401", ...}}`.
  - Mock an unhandled exception → 500 with no stack trace in body.
- `rg '"detail"' demo_game/client.py` within error-parsing context → 0 matches
- `make test` passes

## Blast radius
All API error paths; `demo_game/client.py` error handling; any integrator parsing error responses.
