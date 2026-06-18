> **ARCHIVED** — Implemented in Phase 0.2 (completed 2026-05-04). See `project/STATUS.md` § "Phase 0.2 — Repository Reorganization" and the full service-by-service refactor log.

---

## Graph Registry Source-of-Truth Refactor

### Goal
Make `npc_engine/type_registry` the source of truth for graph node and edge contracts, build runtime classes dynamically from registry data, remove `graph/node_schemas.py` and `graph/edge_schemas.py`, and keep graph services in small per-type modules.

### Decisions
- Hybrid model: thin generic registry helpers plus specialized per-type services where business logic is unique.
- `game_schema.yaml` expands base nodes and edges or adds new nodes and edges.
- Base node and edge YAML files own the canonical base graph fields.
- ISO-8601 strings are the standard timestamp representation in registry-backed graph payloads.
- Primitive-typed dictionaries remain supported through registry `dict_value_type`.

### Execution Order
1. Canonicalize registry contracts in `type_registry/base_nodes/*.yaml` and `type_registry/base_edges/*.yaml`.
2. Keep `game_schema.yaml` as the extension layer for base node and edge models and custom node/edge types.
3. Build runtime node/edge classes dynamically from `type_registry` and replace static graph schema imports.
4. Split graph runtime into per-type services, only splitting read/write/patch when a file exceeds 200 LOC.
5. Update docs and existing tests for import/path changes only.

### Notes
- Complex non-registry DTOs such as relation delta entries and gossip distortions remain in feature modules.
- Every package must carry a README.md and use `get_logger(__name__)` for structured logs.
- Targeted pytest collection is currently blocked in the available environment by missing `neo4j`.

### Checkpoints
- Registry canonicalization: done
- Runtime schema replacement: done
- Graph package split: done
- Docs/tests updates: done
