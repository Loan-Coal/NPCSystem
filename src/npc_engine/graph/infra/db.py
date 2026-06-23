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

from npc_engine.config import Settings


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

        Returns:
            AsyncIterator yielding a single AsyncSession for the duration of the block.

        Raises:
            RuntimeError: If connect() has not been called before this method.
        """
        if self._driver is None:
            raise RuntimeError("GraphDB is not connected")
        async with self._driver.session() as session:
            yield session
