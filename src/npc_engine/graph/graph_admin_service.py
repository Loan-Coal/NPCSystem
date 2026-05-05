"""
graph_admin_service.py - Admin-only graph operations and destructive mutations.

Does NOT: validate bearer token scopes.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession

from npc_engine.utils.errors import NodeNotFoundError


def _clamp_percent(value: int) -> int:
    return max(0, min(100, value))


class GraphAdminService:
    """Service for admin graph operations such as hard delete and absolute relation set."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def _hard_delete_node(self, *, label: str, node_id: str) -> dict[str, int | str]:
        """Hard delete one node label and all connected edges atomically."""

        result = await self._session.run(
            f"MATCH (n:{label} {{id: $id}}) "
            "OPTIONAL MATCH (n)-[out]-() "
            "OPTIONAL MATCH ()-[inc]->(n) "
            "WITH n, collect(out) + collect(inc) AS rels "
            "FOREACH (r IN rels | DELETE r) "
            "DELETE n "
            "RETURN size(rels) AS deleted_edges",
            id=node_id,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type=label.lower(), node_id=node_id)
        return {
            "deleted_node_id": node_id,
            "deleted_edges": int(record["deleted_edges"]),
            "deleted_nodes": 1,
        }

    async def hard_delete_character(self, character_id: str) -> dict[str, int | str]:
        """Hard delete a character and all connected edges atomically.

        Args:
            character_id: ID of the character node to delete.

        Returns:
            Dict with "deleted_node_id", "deleted_edges", and "deleted_nodes" counts.

        Raises:
            NodeNotFoundError: If no character with the given ID exists.
        """

        return await self._hard_delete_node(label="Character", node_id=character_id)

    async def hard_delete_event(self, event_id: str) -> dict[str, int | str]:
        """Hard delete an event and all connected edges atomically.

        Args:
            event_id: ID of the event node to delete.

        Returns:
            Dict with "deleted_node_id", "deleted_edges", and "deleted_nodes" counts.

        Raises:
            NodeNotFoundError: If no event with the given ID exists.
        """

        return await self._hard_delete_node(label="Event", node_id=event_id)

    async def hard_delete_location(self, location_id: str) -> dict[str, int | str]:
        """Hard delete a location and connected edges atomically.

        Args:
            location_id: ID of the location node to delete.

        Returns:
            Dict with "deleted_node_id", "deleted_edges", and "deleted_nodes" counts.

        Raises:
            NodeNotFoundError: If no location with the given ID exists.
        """

        return await self._hard_delete_node(label="Location", node_id=location_id)

    async def set_relation_absolute(self, src_id: str, dst_id: str, trust: int, fear: int, affection: int) -> dict[str, int]:
        """Set absolute RELATES_TO values for one directed edge.

        Args:
            src_id: ID of the source character node.
            dst_id: ID of the destination character node.
            trust: Absolute trust value; clamped to [0, 100].
            fear: Absolute fear value; clamped to [0, 100].
            affection: Absolute affection value; clamped to [0, 100].

        Returns:
            Dict with "trust", "fear", and "affection" reflecting the values stored.

        Raises:
            NodeNotFoundError: If the RELATES_TO edge between src and dst is missing.
        """

        result = await self._session.run(
            "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
            "SET r.trust = $trust, r.fear = $fear, r.affection = $affection, r.last_updated_at = datetime() "
            "RETURN r.trust AS trust, r.fear AS fear, r.affection AS affection",
            src_id=src_id,
            dst_id=dst_id,
            trust=_clamp_percent(trust),
            fear=_clamp_percent(fear),
            affection=_clamp_percent(affection),
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="relation", node_id=f"{src_id}:{dst_id}")
        return {"trust": int(record["trust"]), "fear": int(record["fear"]), "affection": int(record["affection"])}

    async def apply_unbounded_relation_delta(
        self,
        src_id: str,
        dst_id: str,
        trust_delta: int,
        fear_delta: int,
        affection_delta: int,
    ) -> tuple[dict[str, int], list[str]]:
        """Apply admin relation deltas without bounded-window validation; clamp final values.

        Args:
            src_id: ID of the source character node.
            dst_id: ID of the destination character node.
            trust_delta: Signed delta to add to the current trust value.
            fear_delta: Signed delta to add to the current fear value.
            affection_delta: Signed delta to add to the current affection value.

        Returns:
            Tuple of (new_values dict with "trust"/"fear"/"affection", clamped_fields list
            naming any fields that were clamped to [0, 100]).

        Raises:
            NodeNotFoundError: If the RELATES_TO edge between src and dst is missing.
        """

        read_result = await self._session.run(
            "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
            "RETURN r.trust AS trust, r.fear AS fear, r.affection AS affection",
            src_id=src_id,
            dst_id=dst_id,
        )
        current = await read_result.single()
        if current is None:
            raise NodeNotFoundError(node_type="relation", node_id=f"{src_id}:{dst_id}")

        raw = {
            "trust": int(current["trust"]) + trust_delta,
            "fear": int(current["fear"]) + fear_delta,
            "affection": int(current["affection"]) + affection_delta,
        }
        clamped_fields = [name for name, value in raw.items() if value < 0 or value > 100]
        new_values = {name: _clamp_percent(value) for name, value in raw.items()}

        await self._session.run(
            "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
            "SET r.trust = $trust, r.fear = $fear, r.affection = $affection, r.last_updated_at = datetime()",
            src_id=src_id,
            dst_id=dst_id,
            trust=new_values["trust"],
            fear=new_values["fear"],
            affection=new_values["affection"],
        )
        return new_values, clamped_fields
