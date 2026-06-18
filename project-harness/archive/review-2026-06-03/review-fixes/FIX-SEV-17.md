# FIX-SEV-17 — Sanitize dynamic Cypher labels with `cypher_identifier()`

**Severity:** HIGH · **Confidence:** Confirmed (latent injection; current callers use literals) · **Effort:** S
**Category:** security · **Absorbs:** SEC-06, GRAPH-09
**Folds into:** SEV-04 (when these queries move to `graph/`).

## Problem
Two code paths interpolate a label into Cypher via an unsanitized f-string, bypassing the `cypher_identifier()` helper every other dynamic-label query uses. Current callers pass literals/registry values, but the methods accept `label: str` with no protection — a future caller sourcing it from user/registry input would inject.

## Current shape
- `graph/graph_admin_service.py:27-35`:
  ```python
  result = await self._session.run(
      f"MATCH (n:{label} {{id: $id}}) "
      "OPTIONAL MATCH (n)-[out]-() ... DELETE n RETURN size(rels) AS deleted_edges",
      id=node_id,
  )
  ```
  (callers `hard_delete_character/event/location` pass `"Character"/"Event"/"Location"`).
- `engines/quest_generation/quest_generation_engine.py:61` `_CYPHER_GET_NODES_BY_TYPE = "MATCH (n:{label}) RETURN n.id AS id LIMIT 20"` and `:381-382` `cypher = f"MATCH (n:{label}) ..."` where `label = node_type.capitalize()` (`:380`).
- Correct pattern: `graph/generic_node_service.py:73` uses `cypher_identifier(node_label)` (backtick-escaping); helper in `graph/generic_graph_utils.py:159-169`.

## Target shape
Every dynamic label is wrapped in `cypher_identifier()` and validated against the known label set.

## Steps
1. `graph_admin_service.py`: `from npc_engine.graph.generic_graph_utils import cypher_identifier`; change to `f"MATCH (n:{cypher_identifier(label)} {{id: $id}}) ..."`.
2. `quest_generation_engine.py`: validate `node_type` against `BASE_NODE_LABELS` first; build the query with `cypher_identifier(resolve_node_label(node_type))`. (When SEV-04 lands, move this into a `graph/` query function.)

## Verification
- Unit test: call `_hard_delete_node` with `label = "Character`}-MATCH (n2) DELETE n2 //"` → escaped/rejected, no unintended match/delete.
- Unit test: quest-gen with a label containing a backtick → escaped or rejected.

## Blast radius
Low today (literals), but removes a latent injection and an inconsistency. Trivial change; do it now and again when consolidating Cypher under SEV-04.
