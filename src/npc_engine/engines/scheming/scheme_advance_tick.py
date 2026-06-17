"""
Module: scheme_advance_tick
Layer: engines
Purpose: Tick-scheduler adapter that auto-advances active schemes (F1.6 / DEC-107
         Option A). On its cadence it mints a registry-valid covert Event per
         eligible scheme and links it as the next SCHEME_STEP.
Does NOT: call LLMs, run the public EventHandler.run_tick side effects (awareness,
          reputation, witnessing, world-state), change type_registry YAML, or
          perform scheme detection (that is the investigation engine's job).
Dependencies injected: Settings + TypeRegistry + SchemingGraphPort (constructor).
Used by: scheduler/tick_scheduler.py (scheme_advance_engine slot); wired in
         api/dependencies_engines.get_scheme_advance_tick.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from npc_engine.config import Settings
from npc_engine.engines.ports.scheming_port import SchemingGraphPort
from npc_engine.engines.scheming.covert_event_factory import build_covert_event_props
from npc_engine.graph.scheme_reader import ActiveSchemeProgress
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.node_validator import validate_node_write

_LOGGER = logging.getLogger(__name__)

_EVENT_NODE_TYPE: str = "event"


class SchemeAdvanceTick:
    """Advances active schemes by minting covert Events on a tick cadence (Option A).

    Self-gates on SCHEME_ADVANCE_TICK_INTERVAL, advances at most
    SCHEME_ADVANCE_MAX_PER_TICK schemes per tick, and stops a scheme once it has
    MAX_SCHEME_STEPS steps. Each advance creates a registry-valid, covert
    (is_public=False, low-severity) Event via the validated write path and links
    it as the next SCHEME_STEP atomically (SEV-01 / L2-07).
    """

    def __init__(
        self,
        settings: Settings,
        registry: TypeRegistry,
        scheming_repo: SchemingGraphPort,
    ) -> None:
        """Initialise the scheme-advance tick adapter.

        Args:
            settings: Application settings (cadence + step/per-tick caps).
            registry: Type registry providing the validated ``event`` node model.
            scheming_repo: Graph port for scheme reads and atomic step emission.
        """
        self._interval = settings.SCHEME_ADVANCE_TICK_INTERVAL
        self._max_steps = settings.MAX_SCHEME_STEPS
        self._max_per_tick = settings.SCHEME_ADVANCE_MAX_PER_TICK
        self._registry = registry
        self._repo = scheming_repo

    async def run_tick(self, *, tick_id: int, **_: Any) -> dict[str, Any]:
        """Advance eligible active schemes one covert step, on cadence.

        The scheduler passes ``session=`` as a keyword arg; it is swallowed by
        ``**_`` and ignored — the port manages its own sessions (DEC-122).

        Args:
            tick_id: Current game tick.

        Returns:
            Dict with ``tick_id``, ``advanced`` (count), and ``skipped`` (bool).
        """
        if tick_id % self._interval != 0:
            return {"tick_id": tick_id, "advanced": 0, "skipped": True}

        schemes = await self._repo.get_all_active_schemes_with_steps()
        eligible = [s for s in schemes if s.step_count < self._max_steps]
        advanced = 0
        for scheme in eligible[: self._max_per_tick]:
            if await self._advance_one(scheme, tick_id):
                advanced += 1
        return {"tick_id": tick_id, "advanced": advanced, "skipped": False}

    async def _advance_one(
        self,
        scheme: ActiveSchemeProgress,
        tick_id: int,
    ) -> bool:
        """Mint one covert Event for a scheme and link it as the next SCHEME_STEP.

        Returns True if a step was added; False if the schemer has no resolvable
        location (the covert event cannot be placed this tick).
        """
        location_id = await self._repo.get_npc_location_id(scheme.npc_id)
        if not location_id:
            _LOGGER.debug("scheme_advance: no location for npc=%s — skipped", scheme.npc_id)
            return False

        next_order = scheme.step_count + 1
        event_id = uuid4().hex
        event = self._build_event(scheme, event_id, next_order, location_id, tick_id)
        await self._repo.emit_scheme_step_atomic(
            event=event,
            scheme_id=scheme.scheme_id,
            event_id=event_id,
            step_order=next_order,
            completed=True,
        )
        return True

    def _build_event(
        self,
        scheme: ActiveSchemeProgress,
        event_id: str,
        next_order: int,
        location_id: str,
        tick_id: int,
    ) -> Any:
        """Build + registry-validate the covert Event model for one scheme step."""
        props = build_covert_event_props(
            event_id=event_id,
            npc_id=scheme.npc_id,
            goal=scheme.goal,
            step_order=next_order,
            location_id=location_id,
            tick_id=tick_id,
            now_iso=datetime.now(timezone.utc).isoformat(),
        )
        # .model_dump() is the only place CovertEventProps crosses into graph/ —
        # validate_node_write accepts dict[str, Any] (SEV-03 L3-13).
        validated = validate_node_write(self._registry, _EVENT_NODE_TYPE, props.model_dump())
        return self._registry.node_models[_EVENT_NODE_TYPE](**validated)
