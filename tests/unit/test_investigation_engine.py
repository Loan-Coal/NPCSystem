"""Unit tests for InvestigationEngine (Phase 7.1 Detective/Mystery)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.engines.investigation.investigation_engine import InvestigationEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine() -> InvestigationEngine:
    return InvestigationEngine()


@pytest.fixture
def session() -> AsyncMock:
    return AsyncMock()


# ---------------------------------------------------------------------------
# get_investigation_context — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_investigation_context_returns_expected_keys(engine, session):
    """get_investigation_context returns a dict with all expected top-level keys."""
    evidence_data = [{"id": "ev-1", "kind": "physical", "description": "Dagger"}]
    witness_data = [
        {
            "witness": {"id": "char-witness"},
            "subject": {"id": "char-suspect"},
            "action_type": "attacked",
            "witnessed_at_tick": 5,
            "clarity": 80,
            "interpretation": "He stabbed him.",
        }
    ]
    suspect_data = [
        {
            "investigator": {"id": "char-detective"},
            "suspect": {"id": "char-suspect"},
            "confidence": 70,
        }
    ]
    deduction_data = []
    rumor_data = []

    with (
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_evidence_for_event",
            new=AsyncMock(return_value=evidence_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_witnesses_of_event",
            new=AsyncMock(return_value=witness_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_suspects_for_event",
            new=AsyncMock(return_value=suspect_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_deductions_for_character",
            new=AsyncMock(return_value=deduction_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_contradicting_rumors",
            new=AsyncMock(return_value=rumor_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_alibi_window",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await engine.get_investigation_context(
            session,
            investigator_id="char-detective",
            event_id="event-murder",
        )

    assert set(result.keys()) == {
        "evidence",
        "witnesses",
        "suspects",
        "deductions",
        "alibi_contradictions",
        "rumor_contradictions",
    }
    assert result["evidence"] == evidence_data
    assert result["witnesses"] == witness_data
    assert result["suspects"] == suspect_data
    assert result["deductions"] == deduction_data
    assert result["rumor_contradictions"] == rumor_data


# ---------------------------------------------------------------------------
# Alibi contradiction detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alibi_contradiction_detected_when_was_at_differs(engine, session):
    """An alibi contradiction is reported when a witness subject has a WAS_AT record
    covering the same tick as the witnessed event."""
    witness_data = [
        {
            "witness": {"id": "char-witness"},
            "subject": {"id": "char-suspect"},
            "action_type": "stabbed",
            "witnessed_at_tick": 10,
            "clarity": 90,
            "interpretation": "Clear view.",
        }
    ]
    alibi_data = [
        {
            "location": {"id": "loc-tavern", "name": "The Rusty Flagon"},
            "arrived_at_tick": 8,
            "departed_at_tick": 12,
            "reason": "routine",
        }
    ]

    with (
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_evidence_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_witnesses_of_event",
            new=AsyncMock(return_value=witness_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_suspects_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_deductions_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_contradicting_rumors",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_alibi_window",
            new=AsyncMock(return_value=alibi_data),
        ),
    ):
        result = await engine.get_investigation_context(
            session,
            investigator_id="char-detective",
            event_id="event-murder",
        )

    contradictions = result["alibi_contradictions"]
    assert len(contradictions) == 1
    c = contradictions[0]
    assert c["character_id"] == "char-suspect"
    assert c["witnessed_at_tick"] == 10
    assert len(c["was_at_locations"]) == 1
    assert c["was_at_locations"][0]["id"] == "loc-tavern"
    assert "description" in c


@pytest.mark.asyncio
async def test_no_alibi_contradiction_when_no_was_at(engine, session):
    """No contradiction is reported when the subject has no WAS_AT records."""
    witness_data = [
        {
            "witness": {"id": "char-witness"},
            "subject": {"id": "char-suspect"},
            "action_type": "fled",
            "witnessed_at_tick": 7,
            "clarity": 60,
            "interpretation": "Ran away.",
        }
    ]

    with (
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_evidence_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_witnesses_of_event",
            new=AsyncMock(return_value=witness_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_suspects_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_deductions_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_contradicting_rumors",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_alibi_window",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await engine.get_investigation_context(
            session,
            investigator_id="char-detective",
            event_id="event-murder",
        )

    assert result["alibi_contradictions"] == []


@pytest.mark.asyncio
async def test_empty_result_when_no_witnesses_or_evidence(engine, session):
    """All lists are empty when there are no witnesses, evidence, or suspects."""
    with (
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_evidence_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_witnesses_of_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_suspects_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_deductions_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_contradicting_rumors",
            new=AsyncMock(return_value=[]),
        ),
    ):
        result = await engine.get_investigation_context(
            session,
            investigator_id="char-detective",
            event_id="event-nothing",
        )

    assert result["evidence"] == []
    assert result["witnesses"] == []
    assert result["suspects"] == []
    assert result["alibi_contradictions"] == []
    assert result["rumor_contradictions"] == []


@pytest.mark.asyncio
async def test_duplicate_subjects_alibi_checked_once(engine, session):
    """The same subject appearing in multiple WITNESSED edges is only alibi-checked once."""
    witness_data = [
        {
            "witness": {"id": "w1"},
            "subject": {"id": "char-suspect"},
            "action_type": "stole",
            "witnessed_at_tick": 5,
            "clarity": 70,
            "interpretation": "",
        },
        {
            "witness": {"id": "w2"},
            "subject": {"id": "char-suspect"},
            "action_type": "stole",
            "witnessed_at_tick": 5,
            "clarity": 65,
            "interpretation": "",
        },
    ]
    alibi_mock = AsyncMock(return_value=[])

    with (
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_evidence_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_witnesses_of_event",
            new=AsyncMock(return_value=witness_data),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_suspects_for_event",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_deductions_for_character",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_contradicting_rumors",
            new=AsyncMock(return_value=[]),
        ),
        patch(
            "npc_engine.engines.investigation.investigation_engine.get_alibi_window",
            new=alibi_mock,
        ),
    ):
        await engine.get_investigation_context(
            session,
            investigator_id="char-detective",
            event_id="event-theft",
        )

    assert alibi_mock.call_count == 1
