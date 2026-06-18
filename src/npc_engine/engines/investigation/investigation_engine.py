"""
Module: investigation_engine
Layer: engines
Purpose: Query-based investigation engine for Detective/Mystery scenarios (Phase 7.1).
         Aggregates evidence, witnesses, suspects, alibi windows, and rumor contradictions
         for a given event and surfaces structural inconsistencies for LLM narration.
Does NOT: call LLMs directly, modify graph state, hold a Neo4j session, or run on a tick.
Dependencies injected: InvestigationGraphPort (via __init__).
Used by: npc_engine.api.dependency_singletons (singleton), API routes (future)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from npc_engine.engines.ports.investigation_port import InvestigationGraphPort

_LOGGER = logging.getLogger(__name__)


class InvestigationEngine:
    """Surfaces investigation context and structural inconsistencies for a crime event.

    This engine is query-only — it does not write to the graph. Call
    ``get_investigation_context`` from API routes or other engines to obtain a structured
    payload suitable for LLM narration. Graph reads go through the injected
    InvestigationGraphPort (DEC-122 / SEV-24); the engine holds no session.
    """

    def __init__(self, investigation_repo: InvestigationGraphPort) -> None:
        """Initialise with the injected investigation graph port.

        Args:
            investigation_repo: Read-only graph port for crime-event aggregation.
        """
        self._repo = investigation_repo

    async def get_investigation_context(
        self,
        *,
        investigator_id: str,
        event_id: str,
    ) -> dict[str, Any]:
        """Aggregate investigation data and detect inconsistencies for a crime event.

        Runs six parallel graph queries and compares results to surface:
        - Alibi contradictions: a suspect's current location vs. WAS_AT history
          at the event tick.
        - Rumor contradictions: CONTRADICTS-linked Rumor pairs about the event.

        Args:
            investigator_id: ID of the Character conducting the investigation.
            event_id: ID of the Event being investigated (the crime).

        Returns:
            Dict with keys:
            - ``evidence``: list of Evidence property dicts linked to the event.
            - ``witnesses``: list of WITNESSED edge dicts for the event.
            - ``suspects``: list of SUSPECTS edge dicts for the event.
            - ``deductions``: list of Deduction dicts held by the investigator.
            - ``alibi_contradictions``: list of inconsistency dicts.
            - ``rumor_contradictions``: list of conflicting rumor pairs.
        """
        evidence = await self._repo.get_evidence_for_event(event_id=event_id)
        witnesses = await self._repo.get_witnesses_of_event(event_id=event_id)
        suspects = await self._repo.get_suspects_for_event(event_id=event_id)
        deductions = await self._repo.get_deductions_for_character(character_id=investigator_id)
        rumor_contradictions = await self._repo.get_contradicting_rumors(event_id=event_id)

        alibi_contradictions = await self._detect_alibi_contradictions(
            witnesses=witnesses, event_id=event_id
        )

        _LOGGER.debug(
            "investigation_context: event=%s evidence=%d witnesses=%d suspects=%d "
            "alibi_contradictions=%d rumor_contradictions=%d",
            event_id,
            len(evidence),
            len(witnesses),
            len(suspects),
            len(alibi_contradictions),
            len(rumor_contradictions),
        )

        return {
            "evidence": evidence,
            "witnesses": witnesses,
            "suspects": suspects,
            "deductions": deductions,
            "alibi_contradictions": alibi_contradictions,
            "rumor_contradictions": rumor_contradictions,
        }

    async def _detect_alibi_contradictions(
        self,
        *,
        witnesses: list[dict[str, Any]],
        event_id: str,
    ) -> list[dict[str, Any]]:
        """Detect alibi contradictions for all characters witnessed at the event.

        A contradiction exists when a WITNESSED edge places a character at the event
        tick but their WAS_AT history shows them at a different location during that
        window. This is a best-effort check: characters with no WAS_AT history cannot
        be contradicted.

        Args:
            witnesses: List of witness dicts from get_witnesses_of_event.
            event_id: ID of the event being investigated.

        Returns:
            List of contradiction dicts, each with keys:
            - ``character_id``: ID of the character with the contradiction.
            - ``witnessed_at_tick``: Tick when the WITNESSED edge was recorded.
            - ``was_at_locations``: Locations from WAS_AT during that tick.
            - ``description``: Human-readable summary of the contradiction.
        """
        contradictions: list[dict[str, Any]] = []
        seen_character_ids: set[str] = set()

        for witness_entry in witnesses:
            subject = witness_entry.get("subject", {})
            character_id = subject.get("id")
            witnessed_at_tick = witness_entry.get("witnessed_at_tick")

            if not character_id or witnessed_at_tick is None:
                continue
            if character_id in seen_character_ids:
                continue
            seen_character_ids.add(character_id)

            alibi = await self._repo.get_alibi_window(
                character_id=character_id,
                from_tick=witnessed_at_tick,
                to_tick=witnessed_at_tick,
            )

            if alibi:
                contradictions.append({
                    "character_id": character_id,
                    "witnessed_at_tick": witnessed_at_tick,
                    "was_at_locations": [entry["location"] for entry in alibi],
                    "description": (
                        f"Character {character_id!r} was witnessed at event {event_id!r} "
                        f"at tick {witnessed_at_tick}, but WAS_AT records show them at "
                        f"{[e['location'].get('name', e['location'].get('id')) for e in alibi]}."
                    ),
                })

        return contradictions
