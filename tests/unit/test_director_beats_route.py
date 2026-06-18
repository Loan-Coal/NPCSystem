"""
test_director_beats_route.py - Unit tests for the director-beats read route (F2.4).

Overrides get_director_beat_log with a fake log so no scheduler/Neo4j is needed.

Dependencies injected: fake DirectorBeatLog via dependency override.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes.dialogue import router
from npc_engine.api.dependencies_engines import get_director_beat_log
from npc_engine.engines.director.director_beat_log import DirectorBeatRecord


class _FakeBeatLog:
    def __init__(self, beats: list[DirectorBeatRecord]) -> None:
        self._beats = beats
        self.last_limit: int | None = None

    def recent(self, limit: int) -> list[DirectorBeatRecord]:
        self.last_limit = limit
        return self._beats[:limit]


def _client(log: _FakeBeatLog) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_director_beat_log] = lambda: log
    return TestClient(app)


def test_returns_recent_beats() -> None:
    """The route surfaces recorded director beats newest-first."""
    beats = [
        DirectorBeatRecord(beat_kind="re_engage_idle", reason="idle", npc_id="npc_a", player_id="p1", tick=9),
        DirectorBeatRecord(beat_kind="tension_escalation", reason="hostile", npc_id="npc_b", player_id="p1", tick=8),
    ]
    response = _client(_FakeBeatLog(beats)).get("/dialogue/director-beats")

    assert response.status_code == 200
    data = response.json()
    assert [b["beat_kind"] for b in data] == ["re_engage_idle", "tension_escalation"]
    assert data[0]["tick"] == 9


def test_empty_when_no_beats() -> None:
    """No beats yields an empty list."""
    response = _client(_FakeBeatLog([])).get("/dialogue/director-beats")
    assert response.status_code == 200
    assert response.json() == []


def test_limit_query_forwarded() -> None:
    """The limit query param is passed through to the beat log."""
    log = _FakeBeatLog([])
    _client(log).get("/dialogue/director-beats?limit=3")
    assert log.last_limit == 3
