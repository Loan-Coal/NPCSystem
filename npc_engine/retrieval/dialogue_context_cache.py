"""
dialogue_context_cache.py - In-memory per-session dialogue context cache.

Does NOT: connect to Redis or any external cache backend.

Dependencies injected: None.
"""

import time


_CacheKey = tuple[str, str, str, str, str]


class DialogueContextCache:
    """In-memory cache keyed by (npc_id, session_id, npc_last_graph_updated_at, world_last_updated_at, current_mood).

    TTL equals DIALOGUE_SESSION_TTL. Interface is Redis-ready: replace _store with
    a Redis client and this class becomes the adapter.
    """

    def __init__(self, ttl_seconds: int) -> None:
        """Initialise the cache with a fixed TTL.

        Args:
            ttl_seconds: Cache entry lifetime in seconds; must be greater than 0.

        Raises:
            ValueError: If ttl_seconds is not greater than 0.
        """

        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self._ttl = ttl_seconds
        self._store: dict[_CacheKey, tuple[str, float]] = {}

    def build_key(
        self,
        *,
        npc_id: str,
        session_id: str,
        npc_last_graph_updated_at: str,
        world_last_updated_at: str,
        current_mood: str,
    ) -> _CacheKey:
        """Build a cache key from the five cache-busting dimensions.

        Args:
            npc_id: NPC identifier.
            session_id: Dialogue session identifier.
            npc_last_graph_updated_at: ISO timestamp of the NPC's last graph update.
            world_last_updated_at: ISO timestamp of the world state's last update.
            current_mood: Current NPC mood string.

        Returns:
            A 5-tuple used as the cache dict key.
        """

        return (npc_id, session_id, npc_last_graph_updated_at, world_last_updated_at, current_mood)

    def get(self, key: _CacheKey) -> str | None:
        """Retrieve a cached value, evicting it if its TTL has expired.

        Args:
            key: Cache key built via build_key.

        Returns:
            Cached serialized context string, or None if absent or expired.
        """

        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.monotonic() > expires_at:
            del self._store[key]
            return None
        return value

    def set(self, key: _CacheKey, value: str) -> None:
        """Store a value under the given key with the configured TTL.

        Args:
            key: Cache key built via build_key.
            value: Serialized context string to cache.
        """

        self._store[key] = (value, time.monotonic() + self._ttl)

    def size(self) -> int:
        """Return the number of entries currently in the cache (including expired ones).

        Returns:
            Count of entries in the internal store.
        """

        return len(self._store)
