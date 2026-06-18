# FIX-SEV-42 — Rename duplicate `llm_config_loader.py`; relocate `reindex_job_service.py`

**Severity:** LOW · **Confidence:** Confirmed · **Effort:** S
**Category:** architecture · **Absorbs:** ARCH-10, ARCH-03

## Problem
1. Two files named `llm_config_loader.py` in different packages require import aliasing everywhere:
   - `schema/llm_config_loader.py` — loads YAML schema config
   - `engines/llm_config_loader.py` — loads engine-runtime model config
2. `graph/reindex_job_service.py` contains no Neo4j writes, is a job manager, and imports `retrieval.embedding_index` — a confirmed upward layer violation (`graph/` → `retrieval/`).

## Current shape
- `src/npc_engine/schema/llm_config_loader.py` — imported as `from npc_engine.schema.llm_config_loader import ...`
- `src/npc_engine/engines/llm_config_loader.py` — imported in `dependency_singletons.py` as `from npc_engine.engines.llm_config_loader import get_config as get_engine_model_config_for`
- `src/npc_engine/graph/reindex_job_service.py` — `ReindexJobService`, no graph writes, imports `retrieval.embedding_index`

## Steps
1. Rename `schema/llm_config_loader.py` → `schema/llm_schema_loader.py`; update all import sites.
2. Rename `engines/llm_config_loader.py` → `engines/llm_runtime_config.py`; update all import sites (including the alias in `dependency_singletons.py`).
3. Move `graph/reindex_job_service.py` → `retrieval/reindex_job_service.py`; update all import sites (including `dependency_singletons.py` which has `get_reindex_job_service`).
4. Verify with `rg "from.*graph.reindex_job" src/` → 0 matches (all updated).
5. If SEV-31 (`check-layers`) is already done: run `make check-layers` to confirm the layer violation is gone.

## Verification
- `rg "from.*llm_config_loader" src/` → 0 matches
- `rg "from.*graph.reindex_job" src/` → 0 matches
- `make type` passes
- `make test` passes

## Blast radius
Import sites of both `llm_config_loader` files and `reindex_job_service` (expect ~5-10 call sites total).
