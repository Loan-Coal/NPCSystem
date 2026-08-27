"""
dialogue_context_cache.py - In-memory sub-decomposed dialogue context cache.
Layer: retrieval
Purpose: In-memory sub-decomposed dialogue context cache.

Replaces the single monolithic 6-tuple key (which included current_mood and caused
near-100% cache misses on every turn) with three independent sub-caches, each with
its own invalidation key and TTL.

Sub-caches:
  npc_profile       — invalidates on npc_last_graph_updated_at, per (NPC, retrieval profile)
  npc_beliefs_goals — invalidates on npc_last_graph_updated_at, per NPC

The profile slot is keyed by retrieval profile and the beliefs/goals slot is not, and that
asymmetry is deliberate: the profile slot stores an event list read with the profile's own
`events_limit`, so two A/B arms must not share an entry; the beliefs/goals slot stores reads
that take no profile argument at all, so keying it by profile would only cost hit rate.

A third sub-cache, world_state, was deleted -- it had no callers, and `size()` was counting
a dict nothing ever wrote to.

The dynamic tier (emotion snapshot, session turns, RAG results) is never cached.

Does NOT: connect to Redis or any external cache backend.
Dependencies injected: None.
"""
from __future__ import annotations

import time
from typing import Any


class PartialDialogueContextCache:
    """Two-slot partial cache with independent invalidation per sub-cache.

    Both sub-caches share the same TTL but invalidate on different keys, so a mood change no
    longer evicts graph data that hasn't changed.
    """

    def __init__(self, ttl_seconds: int) -> None:
        """Initialise the cache with a fixed TTL applied to both sub-caches.

        Args:
            ttl_seconds: Cache entry lifetime in seconds; must be greater than 0.

        Raises:
            ValueError: If ttl_seconds is not greater than 0.
        """
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be greater than 0")
        self._ttl = ttl_seconds
        # key → (value, expires_at)
        self._profile: dict[str, tuple[Any, float]] = {}
        self._beliefs_goals: dict[str, tuple[Any, float]] = {}

    # ------------------------------------------------------------------
    # npc_profile sub-cache — key: (npc_id, npc_last_graph_updated_at, profile_name)
    # ------------------------------------------------------------------

    def build_profile_key(
        self, *, npc_id: str, npc_last_graph_updated_at: str, profile_name: str
    ) -> str:
        """Return the cache key for one NPC's profile reads under one retrieval profile.

        `profile_name` is part of the key because the VALUE stored here is
        `_fetch_npc_profile_data(...)`, whose `events` list is read with
        `limit=profile.events_limit` -- a retrieval-profile field. Without it, two turns for
        the same NPC at the same graph timestamp collide, and since this cache is a
        process-wide singleton shared by the HTTP and WebSocket paths, and `paired_arms`
        interleaves the arms inside one run, the second arm is served the first arm's event
        list and the run records a profile it did not retrieve under.

        The NAME rather than `events_limit` itself: keying on the field would maximise hit
        rate across arms that happen to share a value, but it would silently go stale the
        moment `_fetch_npc_profile_data` starts reading a second profile field -- which is
        exactly the bug this fixes, one level down.

        Args:
            npc_id: The NPC whose profile reads are cached.
            npc_last_graph_updated_at: Graph timestamp that invalidates the entry.
            profile_name: Resolved retrieval-profile name for this turn.
        Returns:
            The cache key.
        """
        return f"{npc_id}:{npc_last_graph_updated_at}:{profile_name}"

    def get_profile(self, key: str) -> Any | None:
        return self._get(self._profile, key)

    def set_profile(self, key: str, value: Any) -> None:
        self._set(self._profile, key, value)

    # ------------------------------------------------------------------
    # npc_beliefs_goals sub-cache — key: (npc_id, npc_last_graph_updated_at)
    # ------------------------------------------------------------------

    def build_beliefs_goals_key(self, *, npc_id: str, npc_last_graph_updated_at: str) -> str:
        """Return the cache key for one NPC's beliefs, goals, secrets and obligations.

        Deliberately carries NO profile name, unlike `build_profile_key`. Audited: the value
        stored here is `_fetch_beliefs_goals_data(session, npc_id)`, which takes no profile
        argument and reads no profile field, so two arms genuinely produce the same bytes.
        Adding an unnecessary key component here would be a pure cache-hit-rate regression
        that nothing in the suite would notice.

        Args:
            npc_id: The NPC whose beliefs and goals are cached.
            npc_last_graph_updated_at: Graph timestamp that invalidates the entry.
        Returns:
            The cache key.
        """
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
        """Return total number of entries across both sub-caches (including expired).

        Two, not three: the world_state sub-cache and its build/get/set trio were deleted.
        They had zero callers anywhere in the codebase, so `size()` was summing a dict
        nothing ever wrote to.
        """
        return len(self._profile) + len(self._beliefs_goals)


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
