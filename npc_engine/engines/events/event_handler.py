"""
event_handler.py - Orchestrates weighted event generation and awareness seeding.

Does NOT: run periodic scheduler loops.

Dependencies injected: Settings, EmbeddingIndex.
"""

from datetime import datetime, timezone
import random
from uuid import uuid4
import asyncio
import logging

from neo4j import AsyncSession

from common.json_utils import dump_json, parse_json_list, parse_json_object
from config import Settings
from engines.embedding_invalidation import invalidate_embedding_safely
from engines.events.awareness_seeder import seed_awareness_tx
from engines.events.event_pool import EventTemplate, load_event_pool
from engines.events.location_scoper import resolve_locations
from graph.event_writer import upsert_event
from retrieval.embedding_index import EmbeddingIndex
from type_registry.contracts import TypeRegistry
from world.world_state import WorldState


LOGGER = logging.getLogger(__name__)


CYPHER_GET_WORLD_STATE = """
MATCH (w:WorldState {id: $world_id})
RETURN properties(w) AS world
"""


CYPHER_MERGE_WORLD_STATE = """
MERGE (w:WorldState {id: $id})
SET w.epoch = $epoch,
    w.faction_standings = $faction_standings,
    w.active_conditions = $active_conditions,
    w.weather = $weather,
    w.last_updated_at = datetime()
"""


class EventHandler:
    """Coordinates autonomous event creation for one tick."""

    def __init__(self, settings: Settings, embedding_index: EmbeddingIndex, registry: TypeRegistry | None = None) -> None:
        """Initialise the event handler.

        Args:
            settings: Application settings (EVENT_POOL_PATH, EVENT_RNG_SEED).
            embedding_index: Vector index invalidated after event creation.
            registry: Type registry providing the event node model; resolved via
                ``api.dependencies.get_type_registry()`` if not provided.
        """

        self._settings = settings
        self._embedding_index = embedding_index
        if registry is None:
            from api.dependencies import get_type_registry

            registry = get_type_registry()
        self._registry = registry
        self._templates = load_event_pool(settings.EVENT_POOL_PATH)
        self._rng = random.Random(settings.EVENT_RNG_SEED) if settings.EVENT_RNG_SEED is not None else None
        self._lock = asyncio.Lock()

    def _select_template(self, tick_id: int) -> EventTemplate:
        rng = self._rng or random.Random(tick_id)
        weights = [template.weight for template in self._templates]
        return rng.choices(self._templates, weights=weights, k=1)[0]

    async def run_tick(self, session: AsyncSession, tick_id: int, location_ids: list[str] | None = None) -> dict:
        """Create one weighted event, seed NPC awareness, and optionally update world state.

        High-severity events (severity ≥ 80) add the event type to the world's
        ``active_conditions`` list. Location embedding is invalidated after creation.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier.
            location_ids: Optional override list of location IDs; uses template-matched
                locations when not provided.

        Returns:
            Dict with ``tick_id`` and ``created`` (0 or 1). When created=1, also includes
            ``event_id`` and ``location_id``.
        """

        async with self._lock:
            template = self._select_template(tick_id=tick_id)
            template_locations = await resolve_locations(session=session, location_tag=template.location_tag)
            scoped_locations = location_ids if location_ids is not None and len(location_ids) > 0 else template_locations
            if len(scoped_locations) == 0:
                return {"tick_id": tick_id, "created": 0}

            location_id = scoped_locations[0]
            event_id = str(uuid4())
            event_model = self._registry.node_models["event"]
            now = datetime.now(timezone.utc).isoformat()
            event = event_model(
                id=event_id,
                summary=template.summary_template,
                severity=template.severity,
                location_id=location_id,
                occurred_at=now,
                tick_id=tick_id,
                event_type=template.event_type,
                is_public=True,
                last_graph_updated_at=now,
            )
            tx = await session.begin_transaction()
            async with tx:
                await upsert_event(tx=tx, event=event)
                await seed_awareness_tx(tx=tx, event_id=event_id, location_id=location_id, tick_id=tick_id)
                if template.severity >= 80:
                    world_result = await tx.run(CYPHER_GET_WORLD_STATE, world_id="world")
                    world_record = await world_result.single()
                    if world_record is None:
                        world_state = WorldState()
                    else:
                        payload = dict(world_record["world"])
                        world_state = WorldState(
                            id=payload.get("id", "world"),
                            epoch=payload.get("epoch", "age_of_peace"),
                            faction_standings=parse_json_object(payload.get("faction_standings", {})),
                            active_conditions=parse_json_list(payload.get("active_conditions", [])),
                            weather=payload.get("weather", "clear"),
                        )
                    updated_world = world_state
                    if template.event_type not in world_state.active_conditions:
                        updated_world = world_state.model_copy(
                            update={"active_conditions": [*world_state.active_conditions, template.event_type]}
                        )
                    await tx.run(
                        CYPHER_MERGE_WORLD_STATE,
                        id=updated_world.id,
                        epoch=updated_world.epoch,
                        faction_standings=dump_json(updated_world.faction_standings),
                        active_conditions=dump_json(updated_world.active_conditions),
                        weather=updated_world.weather,
                    )
                await tx.commit()

            await invalidate_embedding_safely(
                embedding_index=self._embedding_index,
                item_id=location_id,
                logger=LOGGER,
                entity_label="location",
            )
            return {"tick_id": tick_id, "created": 1, "event_id": event_id, "location_id": location_id}
