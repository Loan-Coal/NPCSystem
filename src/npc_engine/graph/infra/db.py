"""
db.py - Manages Neo4j driver lifecycle and async session access.
Layer: graph
Purpose: Manages Neo4j driver lifecycle and async session access.

Does NOT: execute graph domain queries.

Dependencies injected: Settings.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator
import asyncio

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession
from neo4j.exceptions import ServiceUnavailable, SessionExpired

from npc_engine.config import Settings
from npc_engine.utils.errors import GraphUnavailableError


class GraphDB:
    """Neo4j driver holder for app lifecycle management."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._driver: AsyncDriver | None = None
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize the Neo4j async driver from configured settings.

        Uses a lock to ensure the driver is created exactly once even under
        concurrent startup calls.
        """
        async with self._connect_lock:
            if self._driver is not None:
                return
            self._driver = AsyncGraphDatabase.driver(
                self._settings.NEO4J_URI,
                auth=(self._settings.NEO4J_USER, self._settings.NEO4J_PASSWORD),
            )

    @property
    def driver(self) -> AsyncDriver:
        """Return the connected Neo4j driver.

        Raises:
            RuntimeError: If connect() has not been called yet.
        """
        if self._driver is None:
            raise RuntimeError("GraphDB is not connected")
        return self._driver

    async def close(self) -> None:
        """Close the Neo4j driver and release its connection pool."""
        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Yield an async Neo4j session for graph operations.

        This is the single driver boundary: because it is an async context manager,
        an exception raised in any caller's ``async with`` body is thrown back in at
        the ``yield``. Translating the driver's outage exceptions here therefore
        covers every repository session and every run_in_tx write path without
        touching their ~300 individual ``session.run`` calls (R3.2).

        The catch is deliberately narrow. FastAPI rethrows route-body exceptions
        into this same ``yield``, so a broad catch would relabel every unrelated
        route error as a graph outage.

        Returns:
            AsyncIterator yielding a single AsyncSession for the duration of the block.

        Raises:
            RuntimeError: If connect() has not been called before this method.
            GraphUnavailableError: If the Neo4j driver cannot reach the server, or
                the session expired mid-operation. Mapped to HTTP 503 by
                api.errors.exception_handlers so clients can distinguish "retry"
                from "your request is broken".
        """
        if self._driver is None:
            raise RuntimeError("GraphDB is not connected")
        try:
            async with self._driver.session() as session:
                yield session
        except (ServiceUnavailable, SessionExpired) as exc:
            raise GraphUnavailableError(uri=self._settings.NEO4J_URI, cause=str(exc)) from exc
