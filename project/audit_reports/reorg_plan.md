# Phase 0.2 — Repository Reorganization Audit Plan

**Date:** 2026-05-04  
**Branch:** stability_refactor  
**Author:** Claude (Task 1 — Inventory and Plan)

---

## 1. Top-Level Folder/File Inventory

| Current path | Destination | Action |
|---|---|---|
| `.claude/` | `.claude/` | leave alone |
| `.github/` | `.github/` | leave alone (update CI paths in Task 10) |
| `.gitignore` | `.gitignore` | update (Task 3) |
| `.pytest_cache/` | — | delete (Task 9) |
| `.ruff_cache/` | — | delete (Task 9) |
| `.venv/` | `.venv/` | leave alone (gitignored) |
| `CLAUDE.md` | `project/CLAUDE.md` | move |
| `DECISIONS.md` | `project/DECISIONS.md` | merge with `refactor/DECISIONS.md` (see §3) |
| `ISSUES.md` | `project/ISSUES.md` | move |
| `Makefile` | `Makefile` | update paths (Task 10) |
| `PATTERNS.md` | `project/PATTERNS.md` | merge with `refactor/PATTERNS.md` (see §3) |
| `README.md` | `README.md` | leave alone |
| `ROADMAP.md` | `project/ROADMAP.md` | move |
| `docs/RELEVANCE_WEIGHTS.md` | `docs/RELEVANCE_WEIGHTS.md` | leave alone |
| `evals/` | `evals/` | leave alone (already correct) |
| `npc_engine/` | `src/npc_engine/` | move source (Task 4) — see §5 for critical import note |
| `project_md_files/` | distribute (see §4) | delete folder when empty |
| `prompts/` | `prompts/` | leave alone (already correct) |
| `proposals/` | `project/proposals/` | move (Task 7) |
| `refactor/` | `project/` (distribute contents) | delete folder when empty (Task 7) |
| `scripts/migrations/` | `scripts/migrations/` | leave alone |
| `testing.docx` | — | delete (stale binary, no code references) |
| `tests/scenarios/` | `e2e/scenarios/` | move (Task 6) |
| `transcripts/` | `e2e/transcripts/` | move (already gitignored) |

### Inside `npc_engine/` — files that do NOT go to `src/npc_engine/`

| Current path | Destination | Notes |
|---|---|---|
| `npc_engine/.coverage` | — | delete (generated artifact) |
| `npc_engine/.dockerignore` | `.dockerignore` | move to root |
| `npc_engine/.env` | `npc_engine/.env` | leave in place until src move; then move to root (gitignored) |
| `npc_engine/.env.example` | `.env.example` | move to root |
| `npc_engine/.gitignore` | — | delete (merge content into root `.gitignore`) |
| `npc_engine/.mypy_cache/` | — | delete (Task 9) |
| `npc_engine/.pytest_cache/` | — | delete (Task 9) |
| `npc_engine/.ruff_cache/` | — | delete (Task 9) |
| `npc_engine/.vscode/` | `.vscode/` | merge with root `.vscode/` (Task 3) |
| `npc_engine/__pycache__/` | — | delete (Task 9) |
| `npc_engine/Dockerfile` | `Dockerfile` | move to root |
| `npc_engine/Makefile` | `Makefile` | merge into / replace root Makefile |
| `npc_engine/README.md` | `docs/npc_engine_readme.md` or merge with root README | decide at Task 8 |
| `npc_engine/conftest.py` | `tests/conftest.py` | move (Task 5) |
| `npc_engine/docker-compose.yml` | `docker-compose.yml` | move to root |
| `npc_engine/game_schema.yaml` | `src/npc_engine/game_schema.yaml` | moves with source |
| `npc_engine/mypy.ini` | `mypy.ini` | move to root |
| `npc_engine/pytest.ini` | superseded by `pyproject.toml` / root `pytest.ini` | update (Task 4) |
| `npc_engine/requirements.txt` | `requirements.txt` | move to root |
| `npc_engine/tests/` | `tests/` | canonical tests — move (Task 5) |
| `npc_engine/observability/*.yaml,*.json` | `src/npc_engine/observability/` or `docs/observability/` | moves with source; README → docs |

---

## 2. Duplicate / Conflicting Locations

### Two "tests" directories

| Directory | Contents | Verdict |
|---|---|---|
| `npc_engine/tests/` | 63 test files — unit (58), integration (2), engine_contract_tests (3). These are the active tests run by CI and the Makefile. | **Keep — canonical** |
| `tests/` (root) | Only `tests/scenarios/` — 3 e2e scenario scripts + a `conftest.py`. NOT unit tests. | **Not duplicates — these are e2e** |

**Recommendation:** The two directories are not in conflict. `npc_engine/tests/` → `tests/` at root (Task 5). `tests/scenarios/` → `e2e/scenarios/` (Task 6). They never coexist at the same path.

### Two `DECISIONS.md` files

- `DECISIONS.md` at root — template stub with no real entries yet.
- `refactor/DECISIONS.md` — substantial content: 10+ dated decisions from the Phase 0.1 stability refactor.

**Recommendation:** `refactor/DECISIONS.md` is authoritative. Move it to `project/DECISIONS.md`. Append the root `DECISIONS.md` template comment block to the top of the merged file, then delete the root file.

### Two `PATTERNS.md` files

- `PATTERNS.md` at root — not read; content unknown.
- `refactor/PATTERNS.md` — working patterns from Phase 0.1.

**Recommendation:** Read both during Task 7 and merge; `project/PATTERNS.md` is the destination.

### Two `Makefile` files

- Root `Makefile` — contains `eval`, `scenarios`, and `test` targets that delegate to `npc_engine/`. Minimal.
- `npc_engine/Makefile` — canonical: all lint, type-check, test slice, coverage, contract, and seed targets.

**Recommendation:** Merge into a single root `Makefile` that runs everything from root. The `npc_engine/Makefile` becomes the authoritative content; the root one is absorbed. Update `working-directory` assumptions accordingly.

### Two `docker-compose.yml` files

- `npc_engine/docker-compose.yml` — the real one (references service config).
- No root `docker-compose.yml` yet.

**Recommendation:** Move `npc_engine/docker-compose.yml` to root. Dockerfile and compose always live at root.

---

## 3. Working Markdown — `refactor/` contents

| File | Destination |
|---|---|
| `refactor/DECISIONS.md` | `project/DECISIONS.md` (merge with root DECISIONS.md) |
| `refactor/NEXT_SESSION.md` | `project/NEXT_SESSION.md` |
| `refactor/PATTERNS.md` | `project/PATTERNS.md` (merge with root PATTERNS.md) |
| `refactor/SKILLS_QUEUE.md` | `project/SKILLS_QUEUE.md` |
| `refactor/STATUS.md` | `project/STATUS.md` |
| `refactor/interfaces/common.md` | `project/interfaces/common.md` |
| `refactor/interfaces/utils.md` | `project/interfaces/utils.md` |

After moving all files, `refactor/` should be empty → delete it.

---

## 4. `project_md_files/` — Distribution Plan

| File | Destination | Rationale |
|---|---|---|
| `ARCHITECTURE.md` | `docs/ARCHITECTURE.md` | Reference doc (static, human-readable) |
| `BUSINESS_REQUIREMENTS.md` | `docs/BUSINESS_REQUIREMENTS.md` | Reference doc |
| `DATA_MODELS.md` | `docs/DATA_MODELS.md` | Reference doc |
| `RELEVANCE_WEIGHTS.md` | already in `docs/` | already correct |
| `CODING_PRINCIPLES.xml` | `project/CODING_PRINCIPLES.xml` | Working/process doc |
| `IMPLEMENTATION_TRACKER.md` | `project/IMPLEMENTATION_TRACKER.md` | Working tracker |
| `LLM_GENERATION_GUIDE.md` | `docs/LLM_GENERATION_GUIDE.md` | Reference guide |
| `PROMPT_DESIGN.md` | `docs/PROMPT_DESIGN.md` | Reference doc |
| `PROJECT_PLAN_v1.0.xml` | `project/proposals/PROJECT_PLAN_v1.0.xml` | Historical plan |
| `PROJECT_PLAN_v1.2.xml` | `project/proposals/PROJECT_PLAN_v1.2.xml` | Historical plan |
| `PROJECT_PLAN_v1.3.xml` | `project/proposals/PROJECT_PLAN_v1.3.xml` | Historical plan |
| `PROJECT_PLAN_v1.4.xml` | `project/proposals/PROJECT_PLAN_v1.4.xml` | Historical plan |
| `WRITE_PATH_CONVERGENCE_P0.md` | `project/proposals/WRITE_PATH_CONVERGENCE_P0.md` | Planning artifact |
| `improvements.md` | `project/proposals/improvements.md` | Planning artifact |
| `refactor.md` | `project/proposals/refactor.md` | Planning artifact |

After moving, `project_md_files/` should be empty → delete it.

---

## 5. Cache Directories to Delete

| Path |
|---|
| `.pytest_cache/` (root) |
| `.ruff_cache/` (root) |
| `npc_engine/.mypy_cache/` |
| `npc_engine/.pytest_cache/` |
| `npc_engine/.ruff_cache/` |
| `npc_engine/__pycache__/` |
| All `**/__pycache__/` under `npc_engine/` recursively |

These will regenerate on next run. Covered by updated `.gitignore`.

---

## 6. ⚠️ Critical: Import Strategy for `src/` Layout

**This is the highest-risk part of the reorg. Read carefully.**

### Current import style

All source files use bare package imports:
```python
from api.schemas import DialogueRequest
from graph.db import GraphDB
from retrieval.context_builder import build_context
```

This works because CI runs `cd npc_engine && python -m pytest tests/unit/` — the working directory is `npc_engine/`, making `api/`, `graph/`, etc. top-level packages.

### Target layout: `src/npc_engine/`

If we move to `src/npc_engine/api/`, `src/npc_engine/graph/`, etc., there are two options:

**Option A — Full rename (all imports change)**  
Set `pythonpath = ["src"]` in pytest config. Every import becomes:
```python
from npc_engine.api.schemas import DialogueRequest
from npc_engine.graph.db import GraphDB
```
- **Scope:** ~800+ import statements across ~130 files.
- **Risk:** High — any missed import breaks the entire test suite.
- **Benefit:** Cleaner, installable package. Standard Python packaging.

**Option B — Shallow pythonpath (zero import changes)**  
Set `pythonpath = ["src/npc_engine"]` in pytest config. Imports stay exactly as-is.
- **Scope:** 0 import changes.
- **Risk:** Low, but non-standard. Package is not installable as `npc_engine` from outside.
- **Benefit:** Files move, structure is clean, tests still pass.

**Option C — Defer src/ move entirely**  
Keep source at `npc_engine/` root (not under `src/`). Only do the markdown/test/e2e reorganization. Add `pyproject.toml` with `pythonpath` pointing to the repo root.
- **Scope:** 0 import changes, ~10 config file changes.
- **Risk:** Lowest. Tests definitely pass.
- **Benefit:** All other tasks (markdown, e2e, project/) can proceed without touching source.

**Recommendation: Option C for Task 4, with Option B as a follow-up.**

Do the src/ move only after all markdown/test consolidation is verified green. The import rename (Option A) is a dedicated future task, not part of Phase 0.2. This minimizes blast radius while still achieving the structural cleanup goals.

**⚠️ STOP — This decision requires human confirmation before Task 4 proceeds.**

---

## 7. Imports That Will Need Updating

### If Option A (full rename) is chosen:

- Every `from api.` → `from npc_engine.api.`
- Every `from auth.` → `from npc_engine.auth.`
- Every `from cache.` → `from npc_engine.cache.`
- Every `from common.` → `from npc_engine.common.`
- Every `from config import` / `from config.` → `from npc_engine.config`
- Every `from data.` → `from npc_engine.data.`
- Every `from engines.` → `from npc_engine.engines.`
- Every `from graph.` → `from npc_engine.graph.`
- Every `from mutation.` → `from npc_engine.mutation.`
- Every `from retrieval.` → `from npc_engine.retrieval.`
- Every `from scheduler.` → `from npc_engine.scheduler.`
- Every `from schema.` → `from npc_engine.schema.`
- Every `from scripts.` → `from npc_engine.scripts.`
- Every `from type_registry.` → `from npc_engine.type_registry.`
- Every `from utils.` → `from npc_engine.utils.`
- Every `from world.` → `from npc_engine.world.`
- `uvicorn main:app` → `uvicorn npc_engine.main:app`
- `python -m scripts.check_contracts` → `python -m npc_engine.scripts.check_contracts`
- `python -m data.seed` → `python -m npc_engine.data.seed`

Estimated count: **800+ import lines** across ~130 Python files + Makefile + CI YAML + conftest.

### If Option B or C is chosen:
- **0 import changes.**
- Makefile test commands update from `cd npc_engine && python -m pytest tests/unit/` to `python -m pytest tests/unit/`.
- CI `working-directory: npc_engine` removed.

---

## 8. File Move Estimate

| Category | File count |
|---|---|
| Python source files (`npc_engine/` → `src/npc_engine/`) | ~150 |
| Test files (`npc_engine/tests/` → `tests/`) | ~65 |
| E2E scenarios (`tests/scenarios/` → `e2e/scenarios/`) | 4 |
| Working markdown (`refactor/` → `project/`) | 7 |
| Reference docs (`project_md_files/` → `docs/` + `project/`) | 14 |
| Root working docs (`CLAUDE.md`, `ISSUES.md`, `PATTERNS.md`, `ROADMAP.md`, `DECISIONS.md`) | 5 |
| Config/packaging files (Makefile, docker-compose, Dockerfile, requirements.txt) | 6 |
| **Total files to move** | **~251** |

Import updates (if Option A): ~800+ lines in ~130 files  
Import updates (if Option B or C): **0**

---

## 9. Pre-Existing Test State (baseline)

From `refactor/STATUS.md` (run date 2026-04-30, updated through 2026-05-04):
- **291 passed, 0 failed** as of Service #27 (last session)
- Command used: `cd npc_engine && python -m pytest -q`
- All 27 services in the stability refactor are marked Done
- Integration tests require a live Neo4j instance (not run in CI without DB fixture)

The reorg must end with **291+ tests passing** via the new paths.

---

## 10. Decisions Required Before Proceeding

1. **Task 4 — Import strategy (§6):** Option A (full rename), B (shallow pythonpath), or C (defer src/ move)?  
   *Recommendation: C — defer src/ move. Do markdown/test reorg first, src/ move as a separate task.*

2. **Task 2 — Which tests directory is canonical?**  
   *Already answered: `npc_engine/tests/` is canonical. `tests/scenarios/` is e2e, not a duplicate.*

3. **DECISIONS.md merge:** Root vs. refactor/ version — merge with refactor/ as authoritative?  
   *Recommendation: yes, `refactor/DECISIONS.md` is authoritative.*
