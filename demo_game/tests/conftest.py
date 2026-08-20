"""
Package: demo_game.tests
Layer: demo_game (test fixtures)
Purpose: Shared pytest fixtures for demo_game unit tests.
Dependencies: unittest.mock, demo_game.restore_guard
Used by: demo_game.tests.core.test_client, demo_game.tests.scenarios.test_snapshot,
    demo_game.tests.scenarios.test_restore_guard
"""

from __future__ import annotations

from typing import Any, Callable
from unittest.mock import MagicMock

import pytest

from demo_game import restore_guard


def _make_response(status_code: int, body: dict) -> MagicMock:
    """Build a mock httpx.Response with the given status and JSON body."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.text = str(body)
    return resp


@pytest.fixture
def mock_http() -> MagicMock:
    """Mock httpx.Client for injection into EngineClient."""
    return MagicMock()


@pytest.fixture
def make_response():
    """Factory fixture returning mock httpx.Response objects."""
    return _make_response


# ---------------------------------------------------------------------------
# Neo4j fakes for snapshot / restore-guard tests (ISSUE-188)
# ---------------------------------------------------------------------------

class FakeResult:
    """Stand-in for a neo4j Result: iterable, with single()."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def single(self) -> dict[str, Any]:
        return self._rows[0]

    def __iter__(self):
        return iter(self._rows)


class FakeTx:
    """Managed-transaction stand-in that records every statement it runs."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._fail_on = fail_on

    def run(self, cypher: str, **params: Any) -> FakeResult:
        self.calls.append((cypher, params))
        if self._fail_on is not None and self._fail_on in cypher:
            raise _constraint_error()
        return FakeResult([])

    @property
    def cyphers(self) -> list[str]:
        """The Cypher statements run in this transaction, in order."""
        return [cypher for cypher, _ in self.calls]


def _constraint_error() -> Exception:
    from neo4j.exceptions import ConstraintError

    return ConstraintError("Node already exists with label `WorldState` and property `id` = 'world'")


class FakeSession:
    """Fake neo4j session: serves scripted probe reads and captures the write tx.

    Each entry in *states* (``node_count``, ``rel_count``, ``clocks``) is served to
    one probe round; the last entry is reused if probed more often than scripted.

    Attributes:
        session_calls: Cypher run through auto-commit ``session.run``.
        tx: The FakeTx handed to the work function, or None if none ran.
        execute_write_count: How many managed write transactions were opened.
    """

    def __init__(
        self,
        states: list[dict[str, Any]] | None = None,
        fail_on: str | None = None,
    ) -> None:
        self.states = states or [{"node_count": 0, "rel_count": 0, "clocks": []}]
        self.round = -1
        self.session_calls: list[str] = []
        self.tx: FakeTx | None = None
        self.execute_write_count = 0
        self._fail_on = fail_on

    def _state(self) -> dict[str, Any]:
        return self.states[min(max(self.round, 0), len(self.states) - 1)]

    def run(self, cypher: str, **params: Any) -> FakeResult:
        """Serve a scripted probe read, or an empty result for anything else."""
        self.session_calls.append(cypher)
        if cypher == restore_guard.CYPHER_COUNT_NODES:
            self.round += 1
            return FakeResult([{"node_count": self._state()["node_count"]}])
        if cypher == restore_guard.CYPHER_COUNT_RELS:
            return FakeResult([{"rel_count": self._state()["rel_count"]}])
        if cypher == restore_guard.CYPHER_WORLD_STATE_CLOCKS:
            return FakeResult(list(self._state()["clocks"]))
        return FakeResult([])

    def execute_write(self, work: Callable[..., Any], *args: Any) -> Any:
        """Run *work* against a fresh FakeTx, as the neo4j driver would."""
        self.execute_write_count += 1
        self.tx = FakeTx(self._fail_on)
        return work(self.tx, *args)

    def __enter__(self) -> FakeSession:
        return self

    def __exit__(self, *exc: Any) -> bool:
        return False


class FakeDriver:
    """Driver stand-in handing out one fixed session."""

    def __init__(self, session: FakeSession) -> None:
        self._session = session
        self.closed = False

    def session(self) -> FakeSession:
        """Return the single session this driver owns."""
        return self._session

    def close(self) -> None:
        """Record that the driver was closed."""
        self.closed = True


def world_clock_row(
    world_id: str,
    tick_id: int | None,
    updated: str | None = "2026-08-20T00:00:00Z",
) -> dict[str, Any]:
    """Build one :WorldState probe row as the guard's Cypher would return it."""
    return {"id": world_id, "tick_id": tick_id, "last_updated_at": updated}


@pytest.fixture
def no_probe_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the live-writer probe's wait instant."""
    monkeypatch.setattr(restore_guard.time, "sleep", lambda _seconds: None)


@pytest.fixture
def stable_graph() -> list[dict[str, Any]]:
    """Probe states for a graph that nothing is writing to."""
    return [{"node_count": 248, "rel_count": 233, "clocks": [world_clock_row("world", 41)]}]
