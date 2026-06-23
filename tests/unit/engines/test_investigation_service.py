"""
test_investigation_service.py — Unit tests for graph/investigation_service.py writers.

Tests the MERGE-based idempotent contract (SEV-20 / DEC-118): node writers MERGE on a
stable id (caller-suppliable for retry idempotency); edges already MERGE.
All Neo4j I/O is replaced by a fake AsyncSession whose .run() is an AsyncMock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, call, patch

import pytest

from npc_engine.graph.intrigue.investigation_service import (
    _CYPHER_CREATE_DEDUCTION,
    _CYPHER_CREATE_EVIDENCE,
    _CYPHER_CREATE_IMPLICATES,
    _CYPHER_CREATE_PRESENT_AT,
    _CYPHER_CREATE_SUPPORTED_BY,
    _CYPHER_RECORD_SUSPECT,
    _CYPHER_UPDATE_DEDUCTION_STATUS,
    create_deduction,
    create_evidence,
    implicate,
    record_suspect,
    set_evidence_location,
    update_deduction_status,
)
from npc_engine.utils.errors import GraphUnavailableError


# ---------------------------------------------------------------------------
# Fake AsyncSession
# ---------------------------------------------------------------------------


def _make_session() -> AsyncMock:
    """Return a minimal AsyncSession mock whose .run() is awaitable."""
    session = AsyncMock()
    session.run = AsyncMock(return_value=AsyncMock())
    return session


def _make_failing_session(exc: Exception) -> AsyncMock:
    """Return an AsyncSession mock whose .run() raises exc."""
    session = AsyncMock()
    session.run = AsyncMock(side_effect=exc)
    return session


# ---------------------------------------------------------------------------
# SEV-20 — MERGE idempotency
# ---------------------------------------------------------------------------


async def test_evidence_and_deduction_cypher_use_merge_not_create() -> None:
    """Node writes must MERGE on id (idempotent) rather than CREATE (duplicates on retry)."""
    assert "MERGE" in _CYPHER_CREATE_EVIDENCE and "CREATE (" not in _CYPHER_CREATE_EVIDENCE
    assert "MERGE" in _CYPHER_CREATE_DEDUCTION and "CREATE (" not in _CYPHER_CREATE_DEDUCTION


async def test_create_evidence_honors_supplied_id_for_idempotency() -> None:
    """A caller-supplied evidence_id is used as the MERGE key, so a retry hits one node."""
    session = _make_session()
    id1 = await create_evidence(
        session, kind="physical", description="d", discovered_at_tick=1,
        discovered_by_character_id="c", evidence_id="ev-fixed",
    )
    id2 = await create_evidence(
        session, kind="physical", description="d", discovered_at_tick=1,
        discovered_by_character_id="c", evidence_id="ev-fixed",
    )
    assert id1 == id2 == "ev-fixed"
    assert all(c[1]["id"] == "ev-fixed" for c in session.run.call_args_list)


async def test_create_deduction_honors_supplied_id_for_idempotency() -> None:
    """A caller-supplied deduction_id is used as the MERGE key."""
    session = _make_session()
    did = await create_deduction(
        session, held_by_character_id="c", claim="x", confidence=50, deduction_id="ded-fixed",
    )
    assert did == "ded-fixed"
    assert session.run.call_args_list[0][1]["id"] == "ded-fixed"


# ---------------------------------------------------------------------------
# create_evidence — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_evidence_calls_session_run() -> None:
    session = _make_session()

    result_id = await create_evidence(
        session,
        kind="physical",
        description="A bloody dagger",
        discovered_at_tick=5,
        discovered_by_character_id="char-detective",
        links_to_event_id="event-murder",
        confidence=90,
    )

    session.run.assert_called_once()
    call_args = session.run.call_args
    assert call_args[0][0] == _CYPHER_CREATE_EVIDENCE
    params = call_args[1]
    assert params["kind"] == "physical"
    assert params["description"] == "A bloody dagger"
    assert params["discovered_at_tick"] == 5
    assert params["discovered_by_character_id"] == "char-detective"
    assert params["links_to_event_id"] == "event-murder"
    assert params["confidence"] == 90
    assert isinstance(params["id"], str) and len(params["id"]) > 0
    assert result_id == params["id"]


@pytest.mark.asyncio
async def test_create_evidence_returns_unique_ids() -> None:
    session = _make_session()
    id1 = await create_evidence(
        session,
        kind="testimonial",
        description="Witness saw the thief",
        discovered_at_tick=1,
        discovered_by_character_id="char-witness",
    )
    session2 = _make_session()
    id2 = await create_evidence(
        session2,
        kind="testimonial",
        description="Another witness",
        discovered_at_tick=2,
        discovered_by_character_id="char-witness-2",
    )
    assert id1 != id2


@pytest.mark.asyncio
async def test_create_evidence_defaults_confidence_100() -> None:
    session = _make_session()
    await create_evidence(
        session,
        kind="documentary",
        description="A letter",
        discovered_at_tick=3,
        discovered_by_character_id="char-1",
    )
    params = session.run.call_args[1]
    assert params["confidence"] == 100
    assert params["links_to_event_id"] is None


# ---------------------------------------------------------------------------
# create_evidence — failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_evidence_propagates_graph_error() -> None:
    exc = GraphUnavailableError(uri="bolt://localhost:7687", cause="connection refused")
    session = _make_failing_session(exc)

    with pytest.raises(GraphUnavailableError):
        await create_evidence(
            session,
            kind="physical",
            description="Test",
            discovered_at_tick=1,
            discovered_by_character_id="char-1",
        )


# ---------------------------------------------------------------------------
# implicate — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_implicate_calls_session_run_with_correct_params() -> None:
    session = _make_session()

    await implicate(
        session,
        evidence_id="ev-1",
        character_id="char-suspect",
        weight=80,
        is_misleading=False,
    )

    session.run.assert_called_once()
    call_args = session.run.call_args
    assert call_args[0][0] == _CYPHER_CREATE_IMPLICATES
    params = call_args[1]
    assert params["evidence_id"] == "ev-1"
    assert params["character_id"] == "char-suspect"
    assert params["weight"] == 80
    assert params["is_misleading"] is False


@pytest.mark.asyncio
async def test_implicate_misleading_flag_true() -> None:
    session = _make_session()
    await implicate(
        session,
        evidence_id="ev-red-herring",
        character_id="char-innocent",
        weight=50,
        is_misleading=True,
    )
    assert session.run.call_args[1]["is_misleading"] is True


# ---------------------------------------------------------------------------
# implicate — failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_implicate_propagates_graph_error() -> None:
    exc = GraphUnavailableError(uri="bolt://localhost:7687", cause="timeout")
    session = _make_failing_session(exc)

    with pytest.raises(GraphUnavailableError):
        await implicate(session, evidence_id="ev-1", character_id="char-1", weight=50)


# ---------------------------------------------------------------------------
# set_evidence_location — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_evidence_location_calls_session_run() -> None:
    session = _make_session()

    await set_evidence_location(
        session,
        evidence_id="ev-2",
        location_id="loc-tavern",
    )

    session.run.assert_called_once()
    call_args = session.run.call_args
    assert call_args[0][0] == _CYPHER_CREATE_PRESENT_AT
    params = call_args[1]
    assert params["evidence_id"] == "ev-2"
    assert params["location_id"] == "loc-tavern"


# ---------------------------------------------------------------------------
# set_evidence_location — failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_evidence_location_propagates_graph_error() -> None:
    exc = GraphUnavailableError(uri="bolt://localhost:7687", cause="unavailable")
    session = _make_failing_session(exc)

    with pytest.raises(GraphUnavailableError):
        await set_evidence_location(session, evidence_id="ev-1", location_id="loc-1")


# ---------------------------------------------------------------------------
# create_deduction — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_deduction_without_evidence_calls_session_once() -> None:
    session = _make_session()

    deduction_id = await create_deduction(
        session,
        held_by_character_id="char-detective",
        claim="The butler did it",
        confidence=75,
    )

    # Only one run call: CREATE deduction; no SUPPORTED_BY edges
    session.run.assert_called_once()
    call_args = session.run.call_args
    assert call_args[0][0] == _CYPHER_CREATE_DEDUCTION
    params = call_args[1]
    assert params["held_by_character_id"] == "char-detective"
    assert params["claim"] == "The butler did it"
    assert params["confidence"] == 75
    assert params["status"] == "open"
    assert isinstance(params["id"], str) and len(params["id"]) > 0
    assert deduction_id == params["id"]


@pytest.mark.asyncio
async def test_create_deduction_with_evidence_calls_session_multiple_times() -> None:
    session = _make_session()

    deduction_id = await create_deduction(
        session,
        held_by_character_id="char-detective",
        claim="Poison was used",
        confidence=60,
        supporting_evidence_ids=["ev-1", "ev-2"],
    )

    # 1 CREATE + 2 SUPPORTED_BY
    assert session.run.call_count == 3
    create_call = session.run.call_args_list[0]
    assert create_call[0][0] == _CYPHER_CREATE_DEDUCTION

    supported_calls = session.run.call_args_list[1:]
    for c in supported_calls:
        assert c[0][0] == _CYPHER_CREATE_SUPPORTED_BY
        assert c[1]["deduction_id"] == deduction_id

    evidence_ids_passed = {c[1]["evidence_id"] for c in supported_calls}
    assert evidence_ids_passed == {"ev-1", "ev-2"}


@pytest.mark.asyncio
async def test_create_deduction_returns_unique_ids() -> None:
    session1, session2 = _make_session(), _make_session()
    id1 = await create_deduction(session1, held_by_character_id="c1", claim="X", confidence=50)
    id2 = await create_deduction(session2, held_by_character_id="c2", claim="Y", confidence=50)
    assert id1 != id2


# ---------------------------------------------------------------------------
# create_deduction — failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_deduction_propagates_graph_error() -> None:
    exc = GraphUnavailableError(uri="bolt://localhost:7687", cause="unavailable")
    session = _make_failing_session(exc)

    with pytest.raises(GraphUnavailableError):
        await create_deduction(
            session,
            held_by_character_id="char-1",
            claim="Claim",
            confidence=50,
        )


# ---------------------------------------------------------------------------
# update_deduction_status — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_deduction_status_calls_session_run() -> None:
    session = _make_session()

    await update_deduction_status(
        session,
        deduction_id="ded-1",
        status="confirmed",
    )

    session.run.assert_called_once()
    call_args = session.run.call_args
    assert call_args[0][0] == _CYPHER_UPDATE_DEDUCTION_STATUS
    params = call_args[1]
    assert params["deduction_id"] == "ded-1"
    assert params["status"] == "confirmed"


@pytest.mark.asyncio
async def test_update_deduction_status_refuted() -> None:
    session = _make_session()
    await update_deduction_status(session, deduction_id="ded-2", status="refuted")
    assert session.run.call_args[1]["status"] == "refuted"


# ---------------------------------------------------------------------------
# update_deduction_status — failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_deduction_status_propagates_graph_error() -> None:
    exc = GraphUnavailableError(uri="bolt://localhost:7687", cause="unavailable")
    session = _make_failing_session(exc)

    with pytest.raises(GraphUnavailableError):
        await update_deduction_status(session, deduction_id="ded-1", status="open")


# ---------------------------------------------------------------------------
# record_suspect — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_suspect_calls_session_run_with_correct_params() -> None:
    session = _make_session()

    await record_suspect(
        session,
        suspecting_character_id="char-detective",
        suspect_character_id="char-butler",
        event_id="event-murder",
        confidence=85,
    )

    session.run.assert_called_once()
    call_args = session.run.call_args
    assert call_args[0][0] == _CYPHER_RECORD_SUSPECT
    params = call_args[1]
    assert params["suspecting_character_id"] == "char-detective"
    assert params["suspect_character_id"] == "char-butler"
    assert params["event_id"] == "event-murder"
    assert params["confidence"] == 85


# ---------------------------------------------------------------------------
# record_suspect — failure propagates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_suspect_propagates_graph_error() -> None:
    exc = GraphUnavailableError(uri="bolt://localhost:7687", cause="unavailable")
    session = _make_failing_session(exc)

    with pytest.raises(GraphUnavailableError):
        await record_suspect(
            session,
            suspecting_character_id="char-1",
            suspect_character_id="char-2",
            event_id="event-1",
            confidence=50,
        )
