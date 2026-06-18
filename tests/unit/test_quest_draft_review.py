"""
Tests for S3.3 draft-review endpoints in api.routes.quest_generation and
the backing service functions in graph.quest_node_service.

Covers:
- GET /drafts returns all drafts
- GET /drafts?quest_giver_id=X passes filter to service
- GET /drafts returns empty list when no drafts exist
- POST /{id}/offer transitions draft to offered
- POST /{id}/offer returns 404 when quest not found / not a draft
- graph.quest_node_service.get_draft_quests — happy path
- graph.quest_node_service.offer_quest — happy path + not-found
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.routes import quest_generation


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(quest_generation.router, prefix="/v1/admin")

    async def _db_stub() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db_session] = _db_stub
    return app


# ---------------------------------------------------------------------------
# GET /drafts — list all draft quests
# ---------------------------------------------------------------------------


def test_list_draft_quests_returns_all_drafts() -> None:
    drafts = [
        {"id": "q-1", "status": "draft", "quest_giver_id": "mira_innkeeper", "description": "Buy supplies"},
        {"id": "q-2", "status": "draft", "quest_giver_id": "aldric_merchant", "description": "Find herbs"},
    ]

    with patch(
        "npc_engine.api.routes.quest_generation.get_draft_quests",
        new=AsyncMock(return_value=drafts),
    ):
        client = TestClient(_build_app(), raise_server_exceptions=True)
        resp = client.get("/v1/admin/quests/drafts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 2
    assert len(body["data"]["drafts"]) == 2


def test_list_draft_quests_empty_when_no_drafts() -> None:
    with patch(
        "npc_engine.api.routes.quest_generation.get_draft_quests",
        new=AsyncMock(return_value=[]),
    ):
        client = TestClient(_build_app(), raise_server_exceptions=True)
        resp = client.get("/v1/admin/quests/drafts")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["count"] == 0
    assert body["data"]["drafts"] == []


def test_list_draft_quests_passes_giver_id_filter() -> None:
    captured: list[dict] = []

    async def _mock_get_drafts(session, quest_giver_id=None):
        captured.append({"quest_giver_id": quest_giver_id})
        return []

    with patch(
        "npc_engine.api.routes.quest_generation.get_draft_quests",
        side_effect=_mock_get_drafts,
    ):
        client = TestClient(_build_app(), raise_server_exceptions=True)
        client.get("/v1/admin/quests/drafts?quest_giver_id=mira_innkeeper")

    assert captured[0]["quest_giver_id"] == "mira_innkeeper"


# ---------------------------------------------------------------------------
# POST /{id}/offer — transition draft to offered
# ---------------------------------------------------------------------------


def test_offer_draft_quest_returns_offered_status() -> None:
    with patch(
        "npc_engine.api.routes.quest_generation.offer_quest",
        new=AsyncMock(return_value={"quest_id": "q-1", "status": "offered"}),
    ):
        client = TestClient(_build_app(), raise_server_exceptions=True)
        resp = client.post("/v1/admin/quests/q-1/offer")

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["quest_id"] == "q-1"
    assert body["data"]["status"] == "offered"


def test_offer_draft_quest_returns_404_when_not_found() -> None:
    with patch(
        "npc_engine.api.routes.quest_generation.offer_quest",
        new=AsyncMock(return_value=None),
    ):
        client = TestClient(_build_app(), raise_server_exceptions=False)
        resp = client.post("/v1/admin/quests/missing-quest/offer")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# graph.quest_node_service.get_draft_quests — unit tests
# ---------------------------------------------------------------------------


class _ResultStub:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def __aiter__(self):
        return self._iter()

    async def _iter(self):
        for r in self._rows:
            yield r

    async def consume(self) -> None:
        pass


class _SessionStub:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows
        self.last_query: str = ""
        self.last_params: dict = {}

    async def run(self, query: str, **params) -> _ResultStub:
        self.last_query = query
        self.last_params = params
        return _ResultStub(self._rows)


@pytest.mark.asyncio
async def test_get_draft_quests_returns_rows() -> None:
    from npc_engine.graph.quest_node_service import get_draft_quests

    rows = [{"id": "q-1", "status": "draft", "quest_giver_id": "mira_innkeeper"}]
    session = _SessionStub(rows)
    result = await get_draft_quests(session, quest_giver_id=None)  # type: ignore[arg-type]
    assert result == rows


@pytest.mark.asyncio
async def test_get_draft_quests_passes_giver_id() -> None:
    from npc_engine.graph.quest_node_service import get_draft_quests

    session = _SessionStub([])
    await get_draft_quests(session, quest_giver_id="mira_innkeeper")  # type: ignore[arg-type]
    assert session.last_params.get("quest_giver_id") == "mira_innkeeper"


@pytest.mark.asyncio
async def test_get_draft_quests_empty_returns_empty_list() -> None:
    from npc_engine.graph.quest_node_service import get_draft_quests

    session = _SessionStub([])
    result = await get_draft_quests(session)  # type: ignore[arg-type]
    assert result == []


# ---------------------------------------------------------------------------
# graph.quest_node_service.offer_quest — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_offer_quest_returns_dict_on_success() -> None:
    from npc_engine.graph.quest_node_service import offer_quest

    session = _SessionStub([{"quest_id": "q-1", "status": "offered"}])
    result = await offer_quest(session, quest_id="q-1")  # type: ignore[arg-type]
    assert result is not None
    assert result["status"] == "offered"


@pytest.mark.asyncio
async def test_offer_quest_returns_none_when_not_found() -> None:
    from npc_engine.graph.quest_node_service import offer_quest

    session = _SessionStub([])
    result = await offer_quest(session, quest_id="missing")  # type: ignore[arg-type]
    assert result is None
