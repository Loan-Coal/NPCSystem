"""
event_handler.py - Orchestrates weighted event generation and awareness seeding.
Layer: engines
Purpose: Orchestrates weighted event generation and awareness seeding.

Does NOT: run periodic scheduler loops, open Neo4j sessions, or hold a transaction.

Dependencies injected: Settings, EmbeddingIndex, TypeRegistry, EventGraphPort,
    WorldStateGraphPort.
"""
from __future__ import annotations

from typing import Any
from datetime import datetime, timezone
import random
from uuid import uuid4
import asyncio
import logging
from pathlib import Path

from pydantic import BaseModel

from npc_engine.config import Settings
from npc_engine.engines.embedding_refresh import (
    CorpusRefresherProtocol,
    refresh_embedding_safely,
)
from npc_engine.engines.events.disruption_loader import DisruptionRule, load_disruption_rules
from npc_engine.engines.events.event_pool import EventTemplate, load_event_pool
from npc_engine.engines.ports.event_port import EventGraphPort
from npc_engine.engines.ports.world_state_port import WorldStateGraphPort
from npc_engine.graph.event.event_emission_service import RoutineOverridePlan
from npc_engine.retrieval.embedding import EmbeddingIndex
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.node_validator import validate_node_write
from npc_engine.utils.errors import EventTemplateNotFoundError


LOGGER = logging.getLogger(__name__)

# Events at or above this severity flag a world condition and are subject to witnessing.
HIGH_SEVERITY_THRESHOLD = 80
# Direct-causation edge parameters (CAUSED_BY) written when an event has a cause.
DIRECT_CAUSATION_STRENGTH = 100
DIRECT_CAUSATION_TYPE = "direct"
# Clarity recorded on WITNESSED edges seeded from a high-severity event.
WITNESS_CLARITY = 70



def _build_rng(settings: Settings) -> random.Random | None:
    if settings.EVENT_RNG_SEED is None:
        return None
    return random.Random(settings.EVENT_RNG_SEED)


def _rng_for_tick(*, configured: random.Random | None, seed: int | None, tick_id: int) -> random.Random:
    """Return the RNG for this tick's event draw, logging the seed behind it.

    Seed logging is strict for event sampling (npc-coding-principles), as it
    already is for gossip pair selection. Without it a surprising draw cannot be
    replayed, and the caller silently alternates between a configured global seed
    and a per-tick one with nothing recording which applied (R3.4c).

    Args:
        configured: The process-wide RNG built from EVENT_RNG_SEED, or None.
        seed: The configured EVENT_RNG_SEED, or None when unset.
        tick_id: Current game tick, used as the seed when none is configured.

    Returns:
        The configured RNG when present, otherwise one seeded from tick_id.
    """
    effective_seed = tick_id if seed is None else seed
    LOGGER.debug(
        "event_sampling_rng seed=%d tick=%d source=%s",
        effective_seed,
        tick_id,
        "config" if seed is not None else "tick_id",
    )
    return configured if configured is not None else random.Random(tick_id)


def _resolve_disruption_rules_path(settings: Settings, override: str | None) -> Path:
    if override is not None:
        return Path(override)
    return Path(settings.EVENT_POOL_PATH).parent / "disruption_rules.yaml"


class EventHandler:
    """Coordinates autonomous event creation for one tick."""

    def __init__(
        self,
        settings: Settings,
        embedding_index: EmbeddingIndex,
        event_repo: EventGraphPort,
        world_state_repo: WorldStateGraphPort,
        registry: TypeRegistry | None = None,
        disruption_rules_path: str | None = None,
        corpus_refresher: CorpusRefresherProtocol | None = None,
    ) -> None:
        """Initialise the event handler.

        Args:
            settings: Application settings (EVENT_POOL_PATH, EVENT_RNG_SEED).
            embedding_index: Vector index invalidated after event creation.
            event_repo: Event graph domain port (atomic emit + witness/causation).
            world_state_repo: World-state port for the severity-cap read.
            registry: Type registry providing the event node model; injected by the
                composition root (``api/dependency_singletons.py``).
            disruption_rules_path: Optional disruption_rules.yaml path; defaults to the
                file co-located with the event pool.
            corpus_refresher: Writes the refreshed vector-store entry after invalidation
                (DEC-210); None means invalidate-only, the pre-P8 behaviour.
        Raises:
            ValueError: If registry is None (must be injected via __init__).
        """
        self._settings = settings
        self._embedding_index = embedding_index
        self._corpus_refresher = corpus_refresher
        self._event_repo = event_repo
        self._world_state_repo = world_state_repo
        if registry is None:
            raise ValueError("EventHandler requires a TypeRegistry injected via __init__")
        self._registry = registry
        self._templates = load_event_pool(settings.EVENT_POOL_PATH)
        self._rng = _build_rng(settings)
        self._lock = asyncio.Lock()
        self._disruption_rules: list[DisruptionRule] = load_disruption_rules(
            _resolve_disruption_rules_path(settings, disruption_rules_path)
        )

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

    def _select_template(self, tick_id: int, template_id: str | None = None) -> EventTemplate:
        """Return the named template when given, else a weighted draw for this tick."""
        if template_id is not None:
            for template in self._templates:
                if template.id == template_id:
                    return template
            raise EventTemplateNotFoundError(template_id=template_id)
        rng = _rng_for_tick(
            configured=self._rng, seed=self._settings.EVENT_RNG_SEED, tick_id=tick_id
        )
        weights = [template.weight for template in self._templates]
        return rng.choices(self._templates, weights=weights, k=1)[0]

    async def run_tick(
        self,
        *,
        tick_id: int,
        location_ids: list[str] | None = None,
        cause_event_id: str | None = None,
        template_id: str | None = None,
    ) -> dict[str, Any]:
        """Create one weighted event, seed NPC awareness, and optionally update world state.

        High-severity events (severity ≥ HIGH_SEVERITY_THRESHOLD) add the event type to the
        world's ``active_conditions`` list. Location embedding is invalidated after creation.
        All graph work is delegated to the injected EventGraphPort (atomic emit) and
        WorldStateGraphPort (severity-cap read); the scheduler's ``session=`` kwarg is
        accepted and ignored during the SEV-24 migration.

        Args:
            tick_id: Current game tick identifier.
            location_ids: Optional override list of location IDs; uses template-matched
                locations when not provided.
            cause_event_id: When provided, writes a CAUSED_BY edge from the new event to
                this event ID (direct causation, strength=DIRECT_CAUSATION_STRENGTH).
            template_id: When provided, use this pool template instead of the weighted
                draw. The severity cap still applies.

        Returns:
            Dict with ``tick_id`` and ``created`` (0 or 1). When created=1, also includes
            ``event_id`` and ``location_id``.

        Raises:
            EventTemplateNotFoundError: If ``template_id`` names no loaded template.
        """

        async with self._lock:
            template = self._select_template(tick_id=tick_id, template_id=template_id)
            world_state_check = await self._world_state_repo.get_world_state(world_id=self._settings.WORLD_ID)
            if template.severity > world_state_check.max_event_severity:
                LOGGER.debug(
                    "event_handler tick %d: skipping event severity=%d (cap=%d)",
                    tick_id,
                    template.severity,
                    world_state_check.max_event_severity,
                )
                return {"tick_id": tick_id, "created": 0}
            scoped_locations = await self._scope_locations(template=template, location_ids=location_ids)
            if len(scoped_locations) == 0:
                return {"tick_id": tick_id, "created": 0}

            location_id = scoped_locations[0]
            event, event_id, raw_props = self._build_event(
                template=template, location_id=location_id, tick_id=tick_id
            )
            high_severity = template.severity >= HIGH_SEVERITY_THRESHOLD
            await self._event_repo.emit_event_atomic(
                event=event,  # type: ignore[arg-type]
                event_id=event_id,
                location_id=location_id,
                tick_id=tick_id,
                faction_id=template.faction_id,
                reputation_delta=template.reputation_delta,
                routine_overrides=self._build_routine_overrides(template=template, tick_id=tick_id),
                world_condition_event_type=template.event_type if high_severity else None,
                world_id=self._settings.WORLD_ID,
            )
            if high_severity:
                await self._record_witnesses(
                    template=template, location_id=location_id, event_id=event_id,
                    tick_id=tick_id, raw_props=raw_props,
                )
            if cause_event_id is not None:
                await self._event_repo.record_causation(
                    effect_node_id=event_id,
                    effect_node_type="event",
                    cause_event_id=cause_event_id,
                    causation_strength=DIRECT_CAUSATION_STRENGTH,
                    cause_type=DIRECT_CAUSATION_TYPE,
                    tick_lag=0,
                )
            await refresh_embedding_safely(
                embedding_index=self._embedding_index,
                refresher=self._corpus_refresher,
                item_id=location_id,
                enabled=self._settings.VECTOR_STORE_INCREMENTAL_UPSERT,
                logger=LOGGER,
                entity_label="location",
            )
            return {"tick_id": tick_id, "created": 1, "event_id": event_id, "location_id": location_id}

    async def _scope_locations(
        self, *, template: EventTemplate, location_ids: list[str] | None
    ) -> list[str]:
        """Return caller-supplied locations, or template-tag-matched ones when absent."""
        if location_ids:
            return location_ids
        return await self._event_repo.get_locations_by_tag(location_tag=template.location_tag)

    def _build_event(
        self, *, template: EventTemplate, location_id: str, tick_id: int
    ) -> tuple[BaseModel, str, dict[str, Any]]:
        """Build the validated Event node model, returning (event, event_id, raw_props)."""
        event_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()
        raw_props: dict[str, Any] = {
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
        if template.src_character_id is not None:
            raw_props["src_character_id"] = template.src_character_id
        validated_props = validate_node_write(self._registry, "event", raw_props)
        event = self._registry.node_models["event"](**validated_props)
        return event, event_id, raw_props

    def _build_routine_overrides(
        self, *, template: EventTemplate, tick_id: int
    ) -> list[RoutineOverridePlan]:
        """Match disruption rules and convert them into routine-override plans."""
        matched_rules = self._apply_disruption_rules(
            self._disruption_rules, template.event_type, template.severity
        )
        return [
            RoutineOverridePlan(
                override_location=rule.override_location,
                expires_at_tick=tick_id + rule.duration_ticks,
            )
            for rule in matched_rules
        ]

    async def _record_witnesses(
        self, *, template: EventTemplate, location_id: str, event_id: str,
        tick_id: int, raw_props: dict[str, Any],
    ) -> None:
        """Seed WITNESSED edges for a high-severity event (skips when no actor present)."""
        witness_ids = await self._event_repo.get_characters_at_location(location_id=location_id)
        actor_id = str(raw_props.get("src_character_id", "")) or None
        if not (actor_id and witness_ids):
            return
        capped = witness_ids[: self._settings.WITNESSED_MAX_PER_EVENT]
        witnesses = [witness_id for witness_id in capped if witness_id != actor_id]
        await self._event_repo.record_witnesses(
            witness_ids=witnesses,
            subject_id=actor_id,
            event_id=event_id,
            action_type=template.event_type,
            tick=tick_id,
            clarity=WITNESS_CLARITY,
            interpretation=template.summary_template,
        )
