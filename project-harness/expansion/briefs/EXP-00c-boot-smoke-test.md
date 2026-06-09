# EXP-00c — Boot + smoke test (no CI yaml touch)

**Goal / rationale:** There is no automated test that verifies the FastAPI app builds without import
errors, and no quick `make smoke` target that a developer can run without standing up Neo4j/Ollama.
A green smoke test gates every PR from boot-time regressions. Scope of this slice: **unit-level only**
(no live DB/Ollama). CI yaml is intentionally NOT touched — a human must add the make target to CI
after reviewing the test output.

**First slice (worker scope):** A unit test that imports `create_app` from `src/npc_engine/main.py`,
calls it with mocked settings (no real Neo4j URL needed), and asserts the returned FastAPI instance
has at least a `/health` route. Also add a `make smoke` Makefile target that runs this test.

**Current state (verified):**
- `src/npc_engine/main.py`: has `create_app()` function (line ~300+) that builds and returns the
  FastAPI app. It reads settings via `get_settings()`.
- `GET /health` route is registered on the app without the API prefix (confirmed via grep on main.py).
- Existing unit tests in `tests/unit/` use `pytest` with `mock.patch` for DB/Ollama dependencies —
  same approach required here.
- Makefile has `test`, `test-demo`, `eval-retrieval` etc. — add `smoke` target.
- NO `.github/workflows/` or other CI config should be edited in this slice.

**Files:**
- NEW `tests/unit/test_boot_smoke.py`
  — `test_create_app_returns_fastapi_instance()`: `from npc_engine.main import create_app`, patch
    `get_settings()` to return a minimal `Settings(NEO4J_URI="bolt://localhost:7687", API_KEY="test")`,
    call `create_app()`, assert `isinstance(app, FastAPI)`.
  — `test_health_route_registered()`: from the app built above, inspect `app.routes` (or use
    `TestClient` from `httpx`) to assert a route at `/health` exists and returns 200 with a static
    response (no DB needed — health route must not call Neo4j).
  — Keep the test file < 60 lines. No `@pytest.mark.integration` — these are pure unit tests.
- EDIT `Makefile` — add:
  ```
  smoke:
  	$(PYTHON) -m pytest tests/unit/test_boot_smoke.py -q
  ```

**Graph/API surface:** None. Test-layer only.

**Architecture fit:** New test file + Makefile target only. No src/ edits.

**Test plan:**
The test IS the deliverable. Run:
`pytest tests/unit/test_boot_smoke.py -q`

**Done when:** Both tests green; `make smoke` exits 0; the test does not require Docker/Ollama/Neo4j.
