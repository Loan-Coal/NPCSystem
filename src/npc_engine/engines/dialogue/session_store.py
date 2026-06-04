"""
Module: session_store
Layer: engines
Purpose: Async-safe in-memory TTL session store for dialogue turns.
Does NOT: persist sessions across process restarts.
Dependencies: none
Dependencies injected: None.
Used by: engines/dialogue/dialogue_handler, engines/memory_consolidation/memory_consolidation_engine
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone


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
        self._sessions: dict[str, dict] = {}
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
