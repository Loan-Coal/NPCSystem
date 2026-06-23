"""
test_dialogue_context_cache.py - Unit tests for dialogue context cache hit/miss behaviour.

Does NOT: connect to Neo4j or any external service.

Dependencies injected: None.
"""

from __future__ import annotations

import time
import pytest

from npc_engine.retrieval.dialogue_context import DialogueContextCache


def _make_key(
    npc_id: str = "npc_1",
    session_id: str = "sess_1",
    player_id: str = "player_1",
    npc_ts: str = "2026-04-30T10:00:00+00:00",
    world_ts: str = "2026-04-30T09:00:00+00:00",
    mood: str = "neutral",
):
    cache = DialogueContextCache(ttl_seconds=300)
    return cache.build_key(
        npc_id=npc_id,
        session_id=session_id,
        player_id=player_id,
        npc_last_graph_updated_at=npc_ts,
        world_last_updated_at=world_ts,
        current_mood=mood,
    )


def test_cache_hit_on_same_key() -> None:
    cache = DialogueContextCache(ttl_seconds=300)
    key = _make_key()
    cache.set(key, "cached_context_v1")
    assert cache.get(key) == "cached_context_v1"


def test_cache_miss_when_key_absent() -> None:
    cache = DialogueContextCache(ttl_seconds=300)
    key = _make_key()
    assert cache.get(key) is None


def test_cache_miss_after_npc_mutation() -> None:
    cache = DialogueContextCache(ttl_seconds=300)
    key_before = _make_key(npc_ts="2026-04-30T10:00:00+00:00")
    cache.set(key_before, "old_context")

    key_after = _make_key(npc_ts="2026-04-30T10:05:00+00:00")
    assert cache.get(key_after) is None


def test_cache_miss_after_world_state_change() -> None:
    cache = DialogueContextCache(ttl_seconds=300)
    key_before = _make_key(world_ts="2026-04-30T09:00:00+00:00")
    cache.set(key_before, "old_context")

    key_after = _make_key(world_ts="2026-04-30T11:00:00+00:00")
    assert cache.get(key_after) is None


def test_cache_miss_after_ttl_expiry() -> None:
    cache = DialogueContextCache(ttl_seconds=1)
    key = _make_key()
    cache.set(key, "context")
    time.sleep(1.1)
    assert cache.get(key) is None


def test_cache_size_tracks_entries() -> None:
    cache = DialogueContextCache(ttl_seconds=300)
    assert cache.size() == 0
    cache.set(_make_key(npc_id="npc_1"), "ctx1")
    cache.set(_make_key(npc_id="npc_2"), "ctx2")
    assert cache.size() == 2


def test_cache_rejects_zero_ttl() -> None:
    with pytest.raises(ValueError):
        DialogueContextCache(ttl_seconds=0)
