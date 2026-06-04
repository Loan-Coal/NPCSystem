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
from pathlib import Path

from neo4j import AsyncSession

from npc_engine.config import Settings
from npc_engine.engines.embedding_invalidation import invalidate_embedding_safely
from npc_engine.engines.events.awareness_seeder import seed_awareness_tx
from npc_engine.engines.events.disruption_loader import DisruptionRule, load_disruption_rules
from npc_engine.engines.events.event_pool import EventTemplate, load_event_pool
from npc_engine.engines.events.location_scoper import resolve_locations
from npc_engine.engines.routine.routine_queries import set_routine_override
from npc_engine.graph.causality_service import record_causation
from npc_engine.graph.event_queries import get_characters_at_location
from npc_engine.graph.event_writer import upsert_event
from npc_engine.graph.reputation_writer import adjust_reputation_for_event
from npc_engine.utils.errors import ReputationNotFoundError
from npc_engine.graph.witnessed_service import record_witness
from npc_engine.retrieval.embedding_index import EmbeddingIndex
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.node_validator import validate_node_write
from npc_engine.world.world_reader import get_world_state
from npc_engine.world.world_writer import upsert_world_state_tx


LOGGER = logging.getLogger(__name__)


class EventHandler:
    """Coordinates autonomous event creation for one tick."""

    def __init__(
        self,
        settings: Settings,
        embedding_index: EmbeddingIndex,
        registry: TypeRegistry | None = None,
        disruption_rules_path: str | None = None,
    ) -> None:
        """Initialise the event handler.

        Args:
            settings: Application settings (EVENT_POOL_PATH, EVENT_RNG_SEED).
            embedding_index: Vector index invalidated after event creation.
            registry: Type registry providing the event node model; must be injected
                by the composition root (``api/dependency_singletons.py``).
            disruption_rules_path: Optional path to disruption_rules.yaml.  Defaults to the
                file co-located with the event pool when None.
        Raises:
            ValueError: If registry is None (must be injected via __init__).
        """

        self._settings = settings
        self._embedding_index = embedding_index
        if registry is None:
            raise ValueError("EventHandler requires a TypeRegistry injected via __init__")
        self._registry = registry
        self._templates = load_event_pool(settings.EVENT_POOL_PATH)
        self._rng = random.Random(settings.EVENT_RNG_SEED) if settings.EVENT_RNG_SEED is not None else None
        self._lock = asyncio.Lock()
        rules_path = (
            Path(disruption_rules_path)
            if disruption_rules_path is not None
            else Path(settings.EVENT_POOL_PATH).parent / "disruption_rules.yaml"
        )
        self._disruption_rules: list[DisruptionRule] = load_disruption_rules(rules_path)

    @staticmethod
    def _apply_disruption_rules(
        rules: list[DisruptionRule],
        event_type: str,
        severity: int,
    ) -> list[DisruptionRule]:
        """Return the subset of rules that match the given event type or severity.

        Args:
            rules: Full list of loaded DisruptionRule objects.
            event_type: Type string of the created event.
            severity: Numeric severity of the created event.

        Returns:
            List of matching rules (may be empty).
        """
        return [
            rule for rule in rules
            if (event_type in rule.trigger_event_types)
            or (rule.trigger_severity_min is not None and severity >= rule.trigger_severity_min)
        ]

    def _select_template(self, tick_id: int) -> EventTemplate:
        rng = self._rng or random.Random(tick_id)
        weights = [template.weight for template in self._templates]
        return rng.choices(self._templates, weights=weights, k=1)[0]

    async def run_tick(self, session: AsyncSession, tick_id: int, location_ids: list[str] | None = None, cause_event_id: str | None = None) -> dict:
        """Create one weighted event, seed NPC awareness, and optionally update world state.

        High-severity events (severity ≥ 80) add the event type to the world's
        ``active_conditions`` list. Location embedding is invalidated after creation.

        Args:
            session: Active Neo4j async session.
            tick_id: Current game tick identifier.
            location_ids: Optional override list of location IDs; uses template-matched
                locations when not provided.
            cause_event_id: When provided, writes a CAUSED_BY edge from the new event to
                this event ID (direct causation, strength=100, tick_lag=0).

        Returns:
            Dict with ``tick_id`` and ``created`` (0 or 1). When created=1, also includes
            ``event_id`` and ``location_id``.
        """

        async with self._lock:
            template = self._select_template(tick_id=tick_id)
            world_state_check = await get_world_state(session=session, world_id=self._settings.WORLD_ID)
            if template.severity > world_state_check.max_event_severity:
                LOGGER.debug(
                    "event_handler tick %d: skipping event severity=%d (cap=%d)",
                    tick_id,
                    template.severity,
                    world_state_check.max_event_severity,
                )
                return {"tick_id": tick_id, "created": 0}
            template_locations = await resolve_locations(session=session, location_tag=template.location_tag)
            scoped_locations = location_ids if location_ids is not None and len(location_ids) > 0 else template_locations
            if len(scoped_locations) == 0:
                return {"tick_id": tick_id, "created": 0}

            location_id = scoped_locations[0]
            event_id = str(uuid4())
            now = datetime.now(timezone.utc).isoformat()
            raw_props = {
                "id": event_id,
                "summary": template.summary_template,
                "severity": template.severity,
                "location_id": location_id,
                "occurred_at": now,
                "tick_id": tick_id,
                "event_type": template.event_type,
                "is_public": True,
                "last_graph_updated_at": now,
            }
            validated_props = validate_node_write(self._registry, "event", raw_props)
            event = self._registry.node_models["event"](**validated_props)
            tx = await session.begin_transaction()
            async with tx:
                await upsert_event(tx=tx, event=event)  # type: ignore[arg-type]
                await seed_awareness_tx(tx=tx, event_id=event_id, location_id=location_id, tick_id=tick_id)
                if template.faction_id is not None and template.reputation_delta is not None:
                    rep_char_ids = await get_characters_at_location(tx, location_id=location_id)  # type: ignore[arg-type]
                    for char_id in rep_char_ids:
                        try:
                            await adjust_reputation_for_event(
                                tx,
                                character_id=char_id,
                                faction_id=template.faction_id,
                                delta=template.reputation_delta,
                            )
                        except ReputationNotFoundError:
                            LOGGER.debug(
                                "event_handler: no reputation edge for char=%s faction=%s — skipped",
                                char_id,
                                template.faction_id,
                            )
                matched_rules = self._apply_disruption_rules(
                    self._disruption_rules, template.event_type, template.severity
                )
                if matched_rules:
                    char_ids = await get_characters_at_location(tx, location_id=location_id)  # type: ignore[arg-type]
                    for rule in matched_rules:
                        for char_id in char_ids:
                            await set_routine_override(
                                session=tx,  # type: ignore[arg-type]
                                character_id=char_id,
                                location_id=rule.override_location,
                                expires_at_tick=tick_id + rule.duration_ticks,
                            )
                if template.severity >= 80:
                    world_state = await get_world_state(tx, world_id=self._settings.WORLD_ID)
                    if template.event_type not in world_state.active_conditions:
                        updated_world = world_state.model_copy(
                            update={"active_conditions": [*world_state.active_conditions, template.event_type]}
                        )
                        await upsert_world_state_tx(tx=tx, world_state=updated_world)
                await tx.commit()

            if template.severity >= 80:
                witness_ids = await get_characters_at_location(session, location_id=location_id)
                actor_id = str(raw_props.get("src_character_id", "")) or None
                if actor_id and witness_ids:
                    max_witnesses = self._settings.WITNESSED_MAX_PER_EVENT
                    for witness_id in witness_ids[:max_witnesses]:
                        if witness_id != actor_id:
                            await record_witness(
                                session,
                                witness_id=witness_id,
                                subject_id=actor_id,
                                event_id=event_id,
                                action_type=template.event_type,
                                tick=tick_id,
                                clarity=70,
                                interpretation=template.summary_template,
                            )
            if cause_event_id is not None:
                await record_causation(
                    session,
                    effect_node_id=event_id,
                    effect_node_type="event",
                    cause_event_id=cause_event_id,
                    causation_strength=100,
                    cause_type="direct",
                    tick_lag=0,
                )
            await invalidate_embedding_safely(
                embedding_index=self._embedding_index,
                item_id=location_id,
                logger=LOGGER,
                entity_label="location",
            )
            return {"tick_id": tick_id, "created": 1, "event_id": event_id, "location_id": location_id}
