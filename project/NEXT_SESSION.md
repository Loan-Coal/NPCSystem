# Next Session Instructions

## Phase 0.2 Complete

Repository reorganization is done. All working markdown is in `project/`, reference docs in `docs/`, tests in `tests/` at repo root, e2e scenarios in `e2e/scenarios/`.

## Current state

- `pytest tests/unit/ -q` from repo root: **291 passed, 0 failed**
- Root `Makefile` is canonical — all make targets work from repo root
- CI updated to match new layout

## Phase 0.3 — src/ Layout Move (next)

**Goal:** Move source from `npc_engine/` to `src/npc_engine/` using a proper `pyproject.toml`.

**Steps:**
1. Write `pyproject.toml` (setuptools or hatchling) with `[tool.setuptools.packages.find] where = ["src"]` and all deps ported from `npc_engine/requirements.txt`.
2. Move all Python source from `npc_engine/` into `src/npc_engine/` (~150 files).
3. Update `pytest.ini` to `pythonpath = ["src"]` and `testpaths = ["tests"]`.
4. Update all ~800 bare imports to `npc_engine.xxx`.
5. Update `Makefile` and CI: `pip install -e .` instead of `pip install -r npc_engine/requirements.txt`.
6. Update `uvicorn main:app` → `uvicorn npc_engine.main:app`.
7. Update `python -m scripts.xxx` → `python -m npc_engine.scripts.xxx`, `python -m data.seed` → `python -m npc_engine.data.seed`.
8. Move `.env` and `.env.example` to repo root; update any path references in `config.py`.
9. Run `pytest tests/unit/` — must be green.

**Key files to update:** Every `*.py` file in `src/npc_engine/` (all imports), `pytest.ini`, `Makefile`, `.github/workflows/ci.yml`.

**Stop and ask if:** The import rename surfaces unexpected circular imports or circular re-export patterns.

## Known deferred items

- No open ISSUES.md entries.
- `npc_engine/requirements.txt` is still the dep file; will be superseded by `pyproject.toml` in Phase 0.3.
