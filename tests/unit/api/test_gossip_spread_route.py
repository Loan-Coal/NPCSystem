"""Unit tests for the POST /gossip/spread route handler."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI

from npc_engine.api.routes.knowledge.gossip_spread import router, SpreadRumorRequest


# ---------------------------------------------------------------------------
# Minimal FastAPI test app — no auth, no DB session dependency override needed
# when we mock at the service level.
# ---------------------------------------------------------------------------


def _make_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="")
    return app


@pytest.fixture
def client_and_mock():
    app = _make_app()
    with patch(
        "npc_engine.api.routes.knowledge.gossip_spread.get_db_session",
        return_value=AsyncMock(),
    ):
        yield TestClient(app)


# ---------------------------------------------------------------------------
# Request model validation
# ---------------------------------------------------------------------------


def test_request_model_requires_target_npc_id() -> None:
    with pytest.raises(Exception):
        SpreadRumorRequest(rumor_text="x", tick_id=1)


def test_request_model_severity_default() -> None:
    req = SpreadRumorRequest(target_npc_id="npc1", rumor_text="text", tick_id=0)
    assert req.severity == 60


def test_request_model_rejects_empty_rumor_text() -> None:
    with pytest.raises(Exception):
        SpreadRumorRequest(target_npc_id="npc1", rumor_text="", tick_id=0)


def test_request_model_rejects_long_rumor_text() -> None:
    with pytest.raises(Exception):
        SpreadRumorRequest(target_npc_id="npc1", rumor_text="x" * 501, tick_id=0)


def test_request_model_rejects_negative_tick() -> None:
    with pytest.raises(Exception):
        SpreadRumorRequest(target_npc_id="npc1", rumor_text="text", tick_id=-1)


def test_request_model_rejects_severity_above_100() -> None:
    with pytest.raises(Exception):
        SpreadRumorRequest(target_npc_id="npc1", rumor_text="text", tick_id=0, severity=101)


# ---------------------------------------------------------------------------
# Route handler
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_spread_route_returns_event_id_and_npc_id() -> None:
    mock_session = AsyncMock()
    mock_result = AsyncMock()
    mock_result.consume = AsyncMock()
    mock_session.run.return_value = mock_result

    with patch(
        "npc_engine.api.routes.knowledge.gossip_spread.inject_rumor_belief",
        new=AsyncMock(return_value="rumor_plant_mira_5"),
    ):
        from npc_engine.api.routes.knowledge.gossip_spread import spread_rumor_route

        result = await spread_rumor_route(
            body=SpreadRumorRequest(
                target_npc_id="mira_innkeeper",
                rumor_text="The captain gambles away guard funds",
                severity=70,
                tick_id=5,
            ),
            session=mock_session,
        )

    assert result["data"]["event_id"] == "rumor_plant_mira_5"
    assert result["data"]["npc_id"] == "mira_innkeeper"
