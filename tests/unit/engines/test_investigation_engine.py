"""Unit tests for InvestigationEngine (Phase 7.1 Detective/Mystery; SEV-24 port-injected)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from npc_engine.engines.investigation.investigation_engine import InvestigationEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _repo(
    *,
    evidence: list | None = None,
    witnesses: list | None = None,
    suspects: list | None = None,
    deductions: list | None = None,
    rumors: list | None = None,
    alibi: list | None = None,
) -> AsyncMock:
    """Return a mock InvestigationGraphPort with the six read methods stubbed."""
    repo = AsyncMock()
    repo.get_evidence_for_event = AsyncMock(return_value=evidence or [])
    repo.get_witnesses_of_event = AsyncMock(return_value=witnesses or [])
    repo.get_suspects_for_event = AsyncMock(return_value=suspects or [])
    repo.get_deductions_for_character = AsyncMock(return_value=deductions or [])
    repo.get_contradicting_rumors = AsyncMock(return_value=rumors or [])
    repo.get_alibi_window = AsyncMock(return_value=alibi or [])
    return repo


# ---------------------------------------------------------------------------
# get_investigation_context — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_investigation_context_returns_expected_keys():
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
        {"investigator": {"id": "char-detective"}, "suspect": {"id": "char-suspect"}, "confidence": 70}
    ]
    repo = _repo(evidence=evidence_data, witnesses=witness_data, suspects=suspect_data)
    engine = InvestigationEngine(investigation_repo=repo)

    result = await engine.get_investigation_context(
        investigator_id="char-detective", event_id="event-murder"
    )

    assert set(result.keys()) == {
        "evidence", "witnesses", "suspects", "deductions",
        "alibi_contradictions", "rumor_contradictions",
    }
    assert result["evidence"] == evidence_data
    assert result["witnesses"] == witness_data
    assert result["suspects"] == suspect_data
    assert result["deductions"] == []
    assert result["rumor_contradictions"] == []


# ---------------------------------------------------------------------------
# Alibi contradiction detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alibi_contradiction_detected_when_was_at_differs():
    """A contradiction is reported when a witness subject has a WAS_AT record at the tick."""
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
        {"location": {"id": "loc-tavern", "name": "The Rusty Flagon"},
         "arrived_at_tick": 8, "departed_at_tick": 12, "reason": "routine"}
    ]
    repo = _repo(witnesses=witness_data, alibi=alibi_data)
    engine = InvestigationEngine(investigation_repo=repo)

    result = await engine.get_investigation_context(
        investigator_id="char-detective", event_id="event-murder"
    )

    contradictions = result["alibi_contradictions"]
    assert len(contradictions) == 1
    c = contradictions[0]
    assert c["character_id"] == "char-suspect"
    assert c["witnessed_at_tick"] == 10
    assert c["was_at_locations"][0]["id"] == "loc-tavern"
    assert "description" in c


@pytest.mark.asyncio
async def test_no_alibi_contradiction_when_no_was_at():
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
    engine = InvestigationEngine(investigation_repo=_repo(witnesses=witness_data))

    result = await engine.get_investigation_context(
        investigator_id="char-detective", event_id="event-murder"
    )

    assert result["alibi_contradictions"] == []


@pytest.mark.asyncio
async def test_empty_result_when_no_witnesses_or_evidence():
    """All lists are empty when there are no witnesses, evidence, or suspects."""
    engine = InvestigationEngine(investigation_repo=_repo())

    result = await engine.get_investigation_context(
        investigator_id="char-detective", event_id="event-nothing"
    )

    assert result["evidence"] == []
    assert result["witnesses"] == []
    assert result["suspects"] == []
    assert result["alibi_contradictions"] == []
    assert result["rumor_contradictions"] == []


@pytest.mark.asyncio
async def test_duplicate_subjects_alibi_checked_once():
    """The same subject in multiple WITNESSED edges is only alibi-checked once."""
    witness_data = [
        {"witness": {"id": "w1"}, "subject": {"id": "char-suspect"},
         "action_type": "stole", "witnessed_at_tick": 5, "clarity": 70, "interpretation": ""},
        {"witness": {"id": "w2"}, "subject": {"id": "char-suspect"},
         "action_type": "stole", "witnessed_at_tick": 5, "clarity": 65, "interpretation": ""},
    ]
    repo = _repo(witnesses=witness_data)
    engine = InvestigationEngine(investigation_repo=repo)

    await engine.get_investigation_context(
        investigator_id="char-detective", event_id="event-theft"
    )

    assert repo.get_alibi_window.await_count == 1
