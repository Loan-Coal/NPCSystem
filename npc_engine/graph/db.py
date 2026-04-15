"""
db.py - Manages Neo4j driver lifecycle and async session access.

Does NOT: execute graph domain queries.

Dependencies injected: Settings.
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator
import asyncio

from neo4j import AsyncDriver, AsyncGraphDatabase, AsyncSession

from config import Settings


class GraphDB:
    """Neo4j driver holder for app lifecycle management."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._driver: AsyncDriver | None = None
        self._connect_lock = asyncio.Lock()

    async def connect(self) -> None:
        """Initialize the Neo4j async driver."""

        async with self._connect_lock:
            if self._driver is not None:
                return
            self._driver = AsyncGraphDatabase.driver(
                self._settings.NEO4J_URI,
                auth=(self._settings.NEO4J_USER, self._settings.NEO4J_PASSWORD),
            )

    async def close(self) -> None:
        """Close the Neo4j driver if it exists."""

        if self._driver is not None:
            await self._driver.close()
            self._driver = None

    @asynccontextmanager
    async def get_session(self) -> AsyncIterator[AsyncSession]:
        """Yield an async session for graph operations."""

        if self._driver is None:
            raise RuntimeError("GraphDB is not connected")
        async with self._driver.session() as session:
            yield session
