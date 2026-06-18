"""
Module: transaction_coordinator
Layer: graph
Purpose: Own the Neo4j transaction lifecycle for multi-statement engine writes (begin/commit/rollback).
Does NOT: build Cypher, validate payloads, or contain domain logic; it only runs a caller-provided
          unit-of-work inside one transaction and commits it.
Dependencies injected: AsyncSession (passed per call).
Used by: engines that perform multi-writer atomic units (event_handler, faction_politics_engine,
         quest_lifecycle_engine, quest_offer_service, quest_reward_router).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from neo4j import AsyncSession, AsyncTransaction

T = TypeVar("T")


async def run_in_tx(
    session: AsyncSession,
    work: Callable[[AsyncTransaction], Awaitable[T]],
) -> T:
    """Run ``work`` inside a single transaction owned by this coordinator.

    Opens a transaction on ``session``, awaits ``work(tx)``, commits, and returns the
    work's result. On any exception the transaction is rolled back (via the ``async with``
    exit) and the original exception is re-raised unwrapped — mirroring the engine-owned
    ``async with tx: …; await tx.commit()`` pattern this replaces (DEC-087).

    Args:
        session: Active Neo4j async session.
        work: Async callable receiving the open transaction; performs the graph writes.

    Returns:
        Whatever ``work`` returns.

    Raises:
        Exception: Re-raises any exception raised by ``work`` (transaction rolled back first).
    """
    tx = await session.begin_transaction()
    async with tx:
        result = await work(tx)
        await tx.commit()
        return result
