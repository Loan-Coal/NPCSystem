"""
graph_admin_service.py - Admin-only graph operations and destructive mutations.

Does NOT: validate bearer token scopes.

Dependencies injected: AsyncSession.
"""

from neo4j import AsyncSession

from utils.errors import NodeNotFoundError


class GraphAdminService:
    """Service for admin graph operations such as hard delete and absolute relation set."""

    def __init__(self, session: AsyncSession):
        self._session = session

    async def hard_delete_character(self, character_id: str) -> dict[str, int | str]:
        """Hard delete a character and all connected edges atomically."""

        result = await self._session.run(
            "MATCH (c:Character {id: $id}) "
            "OPTIONAL MATCH (c)-[out]-() "
            "OPTIONAL MATCH ()-[inc]->(c) "
            "WITH c, collect(out) + collect(inc) AS rels "
            "FOREACH (r IN rels | DELETE r) "
            "DELETE c "
            "RETURN size(rels) AS deleted_edges",
            id=character_id,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="character", node_id=character_id)
        return {"deleted_node_id": character_id, "deleted_edges": int(record["deleted_edges"]), "deleted_nodes": 1}

    async def hard_delete_event(self, event_id: str) -> dict[str, int | str]:
        """Hard delete an event and all connected edges atomically."""

        result = await self._session.run(
            "MATCH (e:Event {id: $id}) "
            "OPTIONAL MATCH (e)-[out]-() "
            "OPTIONAL MATCH ()-[inc]->(e) "
            "WITH e, collect(out) + collect(inc) AS rels "
            "FOREACH (r IN rels | DELETE r) "
            "DELETE e "
            "RETURN size(rels) AS deleted_edges",
            id=event_id,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="event", node_id=event_id)
        return {"deleted_node_id": event_id, "deleted_edges": int(record["deleted_edges"]), "deleted_nodes": 1}

    async def hard_delete_location(self, location_id: str) -> dict[str, int | str]:
        """Hard delete a location and connected edges atomically."""

        result = await self._session.run(
            "MATCH (loc:Location {id: $id}) "
            "OPTIONAL MATCH (loc)-[out]-() "
            "OPTIONAL MATCH ()-[inc]->(loc) "
            "WITH loc, collect(out) + collect(inc) AS rels "
            "FOREACH (r IN rels | DELETE r) "
            "DELETE loc "
            "RETURN size(rels) AS deleted_edges",
            id=location_id,
        )
        record = await result.single()
        if record is None:
            raise NodeNotFoundError(node_type="location", node_id=location_id)
        return {"deleted_node_id": location_id, "deleted_edges": int(record["deleted_edges"]), "deleted_nodes": 1}

    async def set_relation_absolute(self, src_id: str, dst_id: str, trust: int, fear: int, affection: int) -> dict[str, int]:
        """Set absolute RELATES_TO values for one directed edge."""

        result = await self._session.run(
            "MATCH (a:Character {id: $src_id})-[r:RELATES_TO]->(b:Character {id: $dst_id}) "
            "SET r.trust = $trust, r.fear = $fear, r.affection = $affection, r.last_updated_at = datetime() "
            "RETURN r.trust AS trust, r.fear AS fear, r.affection AS affection",
            src_id=src_id,
            dst_id=dst_id,
            trust=max(0, min(100, trust)),
            fear=max(0, min(100, fear)),
            affection=max(0, min(100, affection)),
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
        """Apply admin relation deltas without bounded-window validation; clamp final values."""

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
        new_values = {name: max(0, min(100, value)) for name, value in raw.items()}

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
