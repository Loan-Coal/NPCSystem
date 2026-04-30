# graph

**Purpose**
Provides graph transaction coordinators and Neo4j access helpers for the NPC Engine.

**Public API**
- `type_registry.runtime_models.build_runtime_models(registry)`: builds dynamic node and edge models from registry contracts.
- `graph.db.GraphDB(settings) -> GraphDB`: manages the Neo4j driver lifecycle.

**Invariants and Side Effects**
- Runtime graph code touches Neo4j and emits structured logs.
- Runtime models are generated from type registry contracts and are immutable after creation.

**Logging Convention**
- Uses `get_logger(__name__)`; common extra fields are `correlation_id`, `npc_id`, `node_type`, `edge_type`, and `duration_ms`.

**Usage Example**
```py
from graph.db import GraphDB
```