"""
E2E scenario: Murder Mystery Investigation (Phase 7.1).

Seeds an event, evidence, witnesses, a contradicting rumor pair, and then runs
get_investigation_context to verify that the investigation engine correctly
surfaces all data and detects contradictions.

Not intended for live DB; uses stub/mock graph data to verify integration.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.investigation.investigation_engine import InvestigationEngine


@pytest.mark.asyncio
async def test_murder_mystery_full_scenario():
    """Seed a murder event with evidence and a witness, then verify investigation context."""
    session = AsyncMock()
    engine = InvestigationEngine()

    event_id = "event-murder-01"
    investigator_id = "char-detective-01"
    suspect_id = "char-lord-01"
    witness_id = "char-maid-01"
    evidence_id = "ev-dagger-01"

    evidence_list = [
        {
            "id": evidence_id,
            "kind": "physical",
            "description": "Blood-stained dagger",
            "discovered_at_tick": 10,
            "discovered_by_character_id": investigator_id,
            "links_to_event_id": event_id,
            "confidence": 90,
        }
    ]
    witness_list = [
        {
            "witness": {"id": witness_id, "name": "Lady Maid"},
            "subject": {"id": suspect_id, "name": "Lord Harwick"},
            "action_type": "stabbed",
            "witnessed_at_tick": 10,
            "clarity": 85,
            "interpretation": "I saw him clearly — he stabbed the merchant.",
        }
    ]
    suspect_list = [
        {
            "investigator": {"id": investigator_id},
            "suspect": {"id": suspect_id},
            "confidence": 75,
        }
    ]
    # Alibi contradiction: Lord Harwick has a WAS_AT record at a different location at tick 10
    alibi_list = [
        {
            "location": {"id": "loc-castle-gates", "name": "Castle Gates"},
            "arrived_at_tick": 8,
            "departed_at_tick": 12,
            "reason": "routine",
        }
    ]
    # Contradicting rumors about the event
    rumor_pair = [
        {
            "rumor_a": {"id": "r-1", "content": "Lord Harwick did it.", "origin_event_id": event_id},
            "rumor_b": {"id": "r-2", "content": "Lord Harwick was at the castle gate.", "origin_event_id": event_id},
        }
    ]

    with (
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_evidence_for_event",
            new=AsyncMock(return_value=evidence_list),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_witnesses_of_event",
            new=AsyncMock(return_value=witness_list),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_suspects_for_event",
            new=AsyncMock(return_value=suspect_list),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_deductions_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_contradicting_rumors",
            new=AsyncMock(return_value=rumor_pair),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_alibi_window",
            new=AsyncMock(return_value=alibi_list),
        ),
    ):
        context = await engine.get_investigation_context(
            session,
            investigator_id=investigator_id,
            event_id=event_id,
        )

    # Verify all data is present
    assert len(context["evidence"]) == 1
    assert context["evidence"][0]["id"] == evidence_id

    assert len(context["witnesses"]) == 1
    assert context["witnesses"][0]["subject"]["id"] == suspect_id

    assert len(context["suspects"]) == 1
    assert context["suspects"][0]["confidence"] == 75

    # Verify alibi contradiction was detected
    assert len(context["alibi_contradictions"]) == 1
    contradiction = context["alibi_contradictions"][0]
    assert contradiction["character_id"] == suspect_id
    assert contradiction["witnessed_at_tick"] == 10
    assert any(loc["id"] == "loc-castle-gates" for loc in contradiction["was_at_locations"])

    # Verify rumor contradictions surfaced
    assert len(context["rumor_contradictions"]) == 1
    assert context["rumor_contradictions"][0]["rumor_a"]["id"] == "r-1"
