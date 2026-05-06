"""
session_store.py - In-memory TTL session store for dialogue turns.

Does NOT: persist sessions across process restarts.

Dependencies injected: None.
"""

from datetime import datetime, timedelta, timezone


class SessionStore:
    """Stores recent dialogue turns per (player, npc) pair."""

    def __init__(self, ttl_seconds: int, max_turns: int) -> None:
        """Initialise an empty session store.

        Args:
            ttl_seconds: Seconds before a session entry expires.
            max_turns: Maximum number of turns to retain per session.
        """

        self._ttl_seconds = ttl_seconds
        self._max_turns = max_turns
        self._sessions: dict[str, dict] = {}

    def key(self, player_id: str, npc_id: str) -> str:
        """Build the session dict key from player and NPC identifiers.

        Args:
            player_id: Player identifier.
            npc_id: NPC identifier.

        Returns:
            Composite key string ``"player_id:npc_id"``.
        """

        return f"{player_id}:{npc_id}"

    def get_turns(self, player_id: str, npc_id: str) -> list[str]:
        """Return non-expired turns for the given session, or an empty list.

        Args:
            player_id: Player identifier.
            npc_id: NPC identifier.

        Returns:
            Copy of stored turns, or an empty list if the session is absent or expired.
        """

        token = self.key(player_id=player_id, npc_id=npc_id)
        session = self._sessions.get(token)
        if session is None:
            return []
        if session["expires_at"] < datetime.now(timezone.utc):
            self._sessions.pop(token, None)
            return []
        return list(session["turns"])

    def append_turns(self, player_id: str, npc_id: str, new_turns: list[str]) -> None:
        """Append new turns to the session and refresh its TTL.

        Trims the combined turn list to max_turns (keeping the most recent entries).

        Args:
            player_id: Player identifier.
            npc_id: NPC identifier.
            new_turns: New turn strings to append.
        """

        token = self.key(player_id=player_id, npc_id=npc_id)
        current_turns = self.get_turns(player_id=player_id, npc_id=npc_id)
        merged_turns = [*current_turns, *new_turns][-self._max_turns :]
        self._sessions = {
            **self._sessions,
            token: {
                "turns": merged_turns,
                "expires_at": datetime.now(timezone.utc) + timedelta(seconds=self._ttl_seconds),
            },
        }
