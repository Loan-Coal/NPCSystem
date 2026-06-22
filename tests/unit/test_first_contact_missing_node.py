"""
test_first_contact_missing_node.py - Regression for ISSUE-118.

When a player Character node does not exist, first-contact dialogue used to 500:
ensure_relation_edge's `MATCH (a),(b) MERGE ...` silently matched nothing, then the
re-read raised RelationEdgeNotFoundError unhandled. The fix makes ensure_relation_edge
raise a typed NodeNotFoundError (naming the missing node), and the dialogue route maps
it to a redacted HTTP 422 instead of a 500.

Does NOT: touch a real Neo4j (the session/tx are mocked).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.routes import dialogue
from npc_engine.config import Settings
from npc_engine.graph.graph_writer import ensure_relation_edge
from npc_engine.utils.errors import NodeNotFoundError

_AUTH_SECRET = "local_dev_secret_change_this_2026"


class _FakeResult:
    def __init__(self, record: object) -> None:
        self._record = record

    async def single(self) -> object:
        return self._record


class _FakeTx:
    def __init__(self, results: list[object]) -> None:
        self.run = AsyncMock(side_effect=[_FakeResult(r) for r in results])
        self.commit = AsyncMock()

    async def __aenter__(self) -> "_FakeTx":
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False


class _FakeSession:
    def __init__(self, results: list[object]) -> None:
        self._tx = _FakeTx(results)

    async def begin_transaction(self) -> _FakeTx:
        return self._tx


@pytest.mark.asyncio
async def test_ensure_relation_edge_raises_when_node_missing() -> None:
    # MERGE returns no row (missing node), then the diagnostic query reports only src present.
    session = _FakeSession(results=[None, {"present": ["npc_x"]}])
    with pytest.raises(NodeNotFoundError) as err:
        await ensure_relation_edge(session=session, src_id="npc_x", dst_id="player")  # type: ignore[arg-type]
    assert "player" in err.value.node_id


@pytest.mark.asyncio
async def test_ensure_relation_edge_ok_when_edge_returned() -> None:
    # MERGE returns the edge row -> both nodes exist -> no error.
    session = _FakeSession(results=[{"r": "edge"}])
    await ensure_relation_edge(session=session, src_id="npc_x", dst_id="player_demo")  # type: ignore[arg-type]


def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(dialogue.router, prefix="/v1")

    async def _db_stub() -> AsyncIterator[object]:
        yield object()

    app.dependency_overrides[get_db_session] = _db_stub
    app.dependency_overrides[dialogue.get_settings] = lambda: Settings(API_KEY_SECRET=_AUTH_SECRET)
    return app


def test_dialogue_route_returns_422_when_character_missing() -> None:
    handler = AsyncMock()
    handler.handle = AsyncMock(side_effect=NodeNotFoundError(node_type="Character", node_id="player"))
    app = _build_app()
    app.dependency_overrides[dialogue.get_dialogue_handler] = lambda: handler

    with patch(f"{dialogue.__name__}.resolve_system_state", new=AsyncMock(return_value=None)):
        client = TestClient(app)
        resp = client.post(
            "/v1/dialogue",
            json={"player_id": "player", "npc_id": "mira_innkeeper", "player_message": "hello"},
        )

    assert resp.status_code == 422
    body = resp.text
    assert "not found" in body.lower()
    # Redaction (L8-02): the internal node id must not leak to the client.
    assert "player" not in body
