"""
Module: session_store
Layer: engines
Purpose: Async-safe in-memory TTL session store for dialogue turns.
Does NOT: persist sessions across process restarts on its own; uses
          graph/session_persistence helpers for save_to_graph/load_from_graph.
Dependencies: graph/session_persistence (write_session_turns, read_all_session_turns)
Dependencies injected: None.
Used by: engines/dialogue/dialogue_handler, engines/memory_consolidation/memory_consolidation_engine,
         main.py lifespan (save on shutdown, load on startup).
"""

from __future__ import annotations

from typing import Any
import asyncio
import logging
from datetime import datetime, timedelta, timezone

_logger = logging.getLogger(__name__)


class SessionStore:
    """Async-safe store for recent dialogue turns per (player, npc) pair.

    All mutating and reading methods acquire ``_lock`` before accessing
    ``_sessions`` to prevent lost updates across awaits in concurrent
    async handlers (DialogueHandler, MemoryConsolidationEngine).
    """

    def __init__(self, ttl_seconds: int, max_turns: int) -> None:
        """Initialise an empty session store.

        Args:
            ttl_seconds: Seconds before a session entry expires.
            max_turns: Maximum number of turns to retain per session.
        """
        self._ttl_seconds = ttl_seconds
        self._max_turns = max_turns
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    def key(self, player_id: str, npc_id: str) -> str:
        """Build the session dict key from player and NPC identifiers.

        Args:
            player_id: Player identifier.
            npc_id: NPC identifier.

        Returns:
            Composite key string ``"player_id:npc_id"``.
        """
        return f"{player_id}:{npc_id}"

    def _get_turns_no_lock(self, player_id: str, npc_id: str) -> list[str]:
        """Return non-expired turns without acquiring the lock (caller must hold it).

        Args:
            player_id: Player identifier.
            npc_id: NPC identifier.

        Returns:
            Copy of stored turns, or an empty list if absent or expired.
        """
        token = self.key(player_id=player_id, npc_id=npc_id)
        session = self._sessions.get(token)
        if session is None:
            return []
        if session["expires_at"] < datetime.now(timezone.utc):
            self._sessions.pop(token, None)
            return []
        return list(session["turns"])

    async def get_turns(self, player_id: str, npc_id: str) -> list[str]:
        """Return non-expired turns for the given session, or an empty list.

        Args:
            player_id: Player identifier.
            npc_id: NPC identifier.

        Returns:
            Copy of stored turns, or an empty list if the session is absent or expired.
        """
        async with self._lock:
            return self._get_turns_no_lock(player_id, npc_id)

    async def get_all_turns_for_npc(self, npc_id: str) -> list[str]:
        """Return all non-expired turns for an NPC, aggregated across all player sessions.

        Args:
            npc_id: NPC identifier to match against stored session keys.

        Returns:
            Flat list of turn strings across all active player sessions for this NPC.
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            turns: list[str] = []
            for k, sess in self._sessions.items():
                if k.split(":", 1)[1] == npc_id and sess["expires_at"] >= now:
                    turns.extend(sess["turns"])
            return turns

    async def clear_all_turns_for_npc(self, npc_id: str) -> None:
        """Remove all session entries for a given NPC across all player sessions.

        Args:
            npc_id: NPC identifier; all matching ``player_id:npc_id`` keys are removed.
        """
        async with self._lock:
            self._sessions = {
                k: v for k, v in self._sessions.items() if k.split(":", 1)[1] != npc_id
            }

    async def get_active_npc_ids(self, min_turns: int) -> list[str]:
        """Return NPC IDs whose total non-expired turns meet or exceed min_turns.

        Args:
            min_turns: Minimum combined turn count across all players for an NPC.

        Returns:
            List of NPC ID strings with enough turns for consolidation.
        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            npc_counts: dict[str, int] = {}
            for k, sess in self._sessions.items():
                if sess["expires_at"] < now:
                    continue
                nid = k.split(":", 1)[1]
                npc_counts[nid] = npc_counts.get(nid, 0) + len(sess["turns"])
            return [nid for nid, count in npc_counts.items() if count >= min_turns]

    async def append_turns(self, player_id: str, npc_id: str, new_turns: list[str]) -> None:
        """Append new turns to the session and refresh its TTL.

        Trims the combined turn list to max_turns (keeping the most recent entries).

        Args:
            player_id: Player identifier.
            npc_id: NPC identifier.
            new_turns: New turn strings to append.
        """
        async with self._lock:
            current_turns = self._get_turns_no_lock(player_id=player_id, npc_id=npc_id)
            merged_turns = [*current_turns, *new_turns][-self._max_turns :]
            token = self.key(player_id=player_id, npc_id=npc_id)
            self._sessions = {
                **self._sessions,
                token: {
                    "turns": merged_turns,
                    "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds),
                },
            }

    async def save_to_graph(
        self,
        session: object,
        max_persisted_turns: int,
    ) -> None:
        """Persist all active sessions to the graph as JSON blobs on Character nodes.

        Best-effort: any exception from the graph layer is logged at WARNING and
        swallowed so that a database outage cannot crash process shutdown.

        Args:
            session: Active Neo4j ``AsyncSession``.
            max_persisted_turns: Cap on turns written per (player, npc) pair.
        """
        from npc_engine.graph.session_persistence import write_session_turns

        async with self._lock:
            snapshot = dict(self._sessions)

        for composite_key, entry in snapshot.items():
            player_id, npc_id = composite_key.split(":", 1)
            turns: list[str] = entry["turns"][-max_persisted_turns:]
            try:
                await write_session_turns(
                    session=session,  # type: ignore[arg-type]
                    npc_id=npc_id,
                    player_id=player_id,
                    turns=turns,
                )
            except Exception as exc:  # noqa: BLE001
                _logger.warning(
                    "session_store.save_failed",
                    extra={"npc_id": npc_id, "player_id": player_id, "error": str(exc)},
                )

    async def load_from_graph(self, session: object) -> None:
        """Populate this store with session turns previously persisted to the graph.

        Reads all Character nodes carrying ``session_turns_*`` properties and
        inserts the decoded turns via ``append_turns`` so that normal TTL and
        max-turns caps apply.

        Args:
            session: Active Neo4j ``AsyncSession``.
        """
        from npc_engine.graph.session_persistence import read_all_session_turns

        records = await read_all_session_turns(session=session)  # type: ignore[arg-type]
        for rec in records:
            await self.append_turns(
                player_id=rec["player_id"],
                npc_id=rec["npc_id"],
                new_turns=rec["turns"],
            )
