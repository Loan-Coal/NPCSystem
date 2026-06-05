# FIX-SEV-31 — Layer model: rank all packages; add CI layer-violation checker

**Severity:** MEDIUM · **Confidence:** Confirmed · **Effort:** M
**Category:** architecture · **Absorbs:** ARCH-04, ARCH-02, ARCH-03, ARCH-11
**Blocks:** SEV-04 (Cypher/tx into graph/)

## Problem
CLAUDE.md defines 6 layers but 9 real packages have no assigned rank: `mutation/`, `scheduler/`, `cache/`, `auth/`, `common/`, `data/`, `world/`, `type_registry/`, `schema/`. Two confirmed upward violations exist (engines importing api): `engines/events/event_handler.py:89` and `engines/quest/quest_lifecycle_engine.py:61` import `npc_engine.api.dependencies`. `graph/reindex_job_service.py:14` imports `retrieval.embedding_index` (graph → retrieval, upward). `make check-contracts` PASSes because it does not encode the topology — violations are CI-invisible. This means SEV-04 fixes cannot be verified by CI until SEV-31 lands.

## Current shape
- `project-harness/CLAUDE.md` Architecture section: lists 6 layers, no mention of the 9 unnamed packages
- `scripts/check_contracts.py` (or equivalent): validates YAML field presence only
- `engines/events/event_handler.py:89`: `from npc_engine.api.dependencies import ...`
- `engines/quest/quest_lifecycle_engine.py:61`: `from npc_engine.api.dependencies import ...`
- `graph/reindex_job_service.py:14`: `from npc_engine.retrieval.embedding_index import ...`

## Target shape
Every package has a documented layer rank. `make check-layers` fails CI on any upward import, making SEV-04's cleanup verifiable.

## Steps

### 1. Update layer table in CLAUDE.md
Add the 9 packages with ranks (verify actual import edges before finalising — adjust if an edge forces a different rank):
| Package | Layer rank |
|---------|-----------|
| `auth/` | api (peer) |
| `data/` | api (peer — admin endpoints + seeders) |
| `scheduler/` | engines (peer) |
| `mutation/` | services (peer) |
| `cache/` | services (peer) |
| `world/` | services (peer) |
| `common/` | config (shared zero-dep utils) |
| `type_registry/` | config (peer) |
| `schema/` | config (peer) |

### 2. Fix the three known violations
- `engines/events/event_handler.py:89`: the import of `api.dependencies` means the handler reaches up for an injected dependency. Instead, inject that dependency via `__init__` (the correct DIP pattern). Read the specific symbol imported and inject it at the composition root (`dependency_singletons.py`).
- `engines/quest/quest_lifecycle_engine.py:61`: same — inject via `__init__`, remove the upward import.
- `graph/reindex_job_service.py:14`: this file will be relocated in SEV-42 to `retrieval/` — after that move, the `retrieval.embedding_index` import is legal. If SEV-42 has not run yet when this fix runs, move the file as part of this fix (it's small scope), or note in DECISIONS that the violation will be resolved by SEV-42 and add it to the CI exception list until then.

### 3. Create `scripts/check_layers.py`
Parse all `src/npc_engine/**/*.py` imports, resolve each imported module to its package, look up both packages' ranks, and fail if the importing package's rank is lower (closer to api) than the imported package's rank. Exit 1 with file+line+message on any violation.

Logic sketch:
```python
LAYER_RANK = {
    "api": 6, "auth": 6, "data": 6,
    "engines": 5, "scheduler": 5,
    "services": 4, "mutation": 4, "cache": 4, "world": 4,
    "retrieval": 3,
    "graph": 2,
    "config": 1, "common": 1, "type_registry": 1, "schema": 1,
    "utils": 1,
}
```
Higher rank = higher layer. Violation = `importer_rank < imported_rank`.

### 4. Wire into CI
- `Makefile`: add `check-layers: python scripts/check_layers.py`
- Add `check-layers` to the `check` target (after `check-rules`).
- `ci.yml` `static-analysis` job: add `make check-layers` step.

## Verification
- `make check-layers` passes on the fixed tree.
- Reintroduce one of the removed upward imports → `make check-layers` exits 1 with clear file+line message.
- `make check` passes end-to-end.

## Blast radius
- Two engine files lose an upward import (injection pattern added).
- CI gets a new gate.
- CLAUDE.md architecture section updated.
