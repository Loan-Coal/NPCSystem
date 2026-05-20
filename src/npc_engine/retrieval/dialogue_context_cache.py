"""
dialogue_context_cache.py - In-memory sub-decomposed dialogue context cache.

Replaces the single monolithic 6-tuple key (which included current_mood and caused
near-100% cache misses on every turn) with three independent sub-caches, each with
its own invalidation key and TTL.

Sub-caches:
  world_state     — invalidates when world_last_updated_at changes
  npc_profile     — invalidates when npc_last_graph_updated_at changes (per NPC)
  npc_beliefs_goals — invalidates when npc_last_graph_updated_at changes (per NPC)

The dynamic tier (emotion snapshot, session turns, RAG results) is never cached.

Does NOT: connect to Redis or any external cache backend.
Dependencies injected: None.
"""

import time
from typing import Any


class PartialDialogueContextCache:
    """Three-slot partial cache with independent invalidation per sub-cache.

    All three sub-caches share the same TTL but invalidate on different keys,
    so a mood change no longer evicts graph data that hasn't changed.
    """

    def __init__(self, ttl_seconds: int) -> None:
        """Initialise the cache with a fixed TTL applied to all three sub-caches.

        Args:
            ttl_seconds: Cache entry lifetime in seconds; must be greater than 0.

        Raises:
            ValueError: If ttl_seconds is not greater than 0.
        """
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self._ttl = ttl_seconds
        # key → (value, expires_at)
        self._world: dict[str, tuple[Any, float]] = {}
        self._profile: dict[str, tuple[Any, float]] = {}
        self._beliefs_goals: dict[str, tuple[Any, float]] = {}

    # ------------------------------------------------------------------
    # world_state sub-cache — key: world_last_updated_at
    # ------------------------------------------------------------------

    def build_world_key(self, *, world_last_updated_at: str) -> str:
        return world_last_updated_at

    def get_world(self, key: str) -> Any | None:
        return self._get(self._world, key)

    def set_world(self, key: str, value: Any) -> None:
        self._set(self._world, key, value)

    # ------------------------------------------------------------------
    # npc_profile sub-cache — key: (npc_id, npc_last_graph_updated_at)
    # ------------------------------------------------------------------

    def build_profile_key(self, *, npc_id: str, npc_last_graph_updated_at: str) -> str:
        return f"{npc_id}:{npc_last_graph_updated_at}"

    def get_profile(self, key: str) -> Any | None:
        return self._get(self._profile, key)

    def set_profile(self, key: str, value: Any) -> None:
        self._set(self._profile, key, value)

    # ------------------------------------------------------------------
    # npc_beliefs_goals sub-cache — key: (npc_id, npc_last_graph_updated_at)
    # ------------------------------------------------------------------

    def build_beliefs_goals_key(self, *, npc_id: str, npc_last_graph_updated_at: str) -> str:
        return f"{npc_id}:{npc_last_graph_updated_at}"

    def get_beliefs_goals(self, key: str) -> Any | None:
        return self._get(self._beliefs_goals, key)

    def set_beliefs_goals(self, key: str, value: Any) -> None:
        self._set(self._beliefs_goals, key, value)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _get(self, store: dict[str, tuple[Any, float]], key: str) -> Any | None:
        entry = store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del store[key]
            return None
        return value

    def _set(self, store: dict[str, tuple[Any, float]], key: str, value: Any) -> None:
        store[key] = (value, time.monotonic() + self._ttl)

    def size(self) -> int:
        """Return total number of entries across all three sub-caches (including expired)."""
        return len(self._world) + len(self._profile) + len(self._beliefs_goals)


# ---------------------------------------------------------------------------
# Backward-compatibility alias for tests that import DialogueContextCache.
# ---------------------------------------------------------------------------

_CacheKey = tuple[str, str, str, str, str, str]


class DialogueContextCache:
    """Legacy monolithic cache — retained for test backward-compatibility only.

    New code should use PartialDialogueContextCache.
    The old key included current_mood which caused near-100% cache misses; kept
    here so existing unit tests continue to compile without modification.
    """

    def __init__(self, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self._ttl = ttl_seconds
        self._store: dict[_CacheKey, tuple[str, float]] = {}

    def build_key(
        self,
        *,
        npc_id: str,
        session_id: str,
        player_id: str,
        npc_last_graph_updated_at: str,
        world_last_updated_at: str,
        current_mood: str,
    ) -> _CacheKey:
        return (npc_id, session_id, player_id, npc_last_graph_updated_at, world_last_updated_at, current_mood)

    def get(self, key: _CacheKey) -> str | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: _CacheKey, value: str) -> None:
        self._store[key] = (value, time.monotonic() + self._ttl)

    def size(self) -> int:
        return len(self._store)
