"""
test_dependencies_engines_singletons.py - Locks ISSUE-098: the four tick-slot
factories must share one PlayerLocationReader singleton, not build their own.

Does NOT: touch Neo4j or the network. get_graph_db is stubbed and the shared
location-reader getter is replaced with a sentinel so factory wiring is the only
thing under test.

Dependencies injected: None (monkeypatch only).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from npc_engine.api import dependencies_infra
from npc_engine.api.dependencies_engines import tick_slots

# Factories that must inject the shared location reader, paired with nothing —
# each adapter stores it on the private `_location_reader` attribute.
_FACTORY_NAMES = (
    "get_proactive_dialogue_engine",
    "get_intent_formation_engine",
    "get_player_model_tick",
    "get_director_tick",
)


def _clear_caches() -> None:
    """Reset every lru_cache this test exercises so construction is fresh."""
    tick_slots.get_player_location_reader.cache_clear()
    tick_slots.get_relation_reader.cache_clear()
    tick_slots.get_proactive_queue.cache_clear()
    tick_slots.get_director_beat_log.cache_clear()
    for name in _FACTORY_NAMES:
        getattr(tick_slots, name).cache_clear()
    dependencies_infra.get_graph_db.cache_clear()


@pytest.fixture(autouse=True)
def _isolate_caches():
    """Clear caches before and after so other tests see pristine singletons."""
    _clear_caches()
    yield
    _clear_caches()


def test_player_location_reader_is_cached_singleton(monkeypatch) -> None:
    monkeypatch.setattr(dependencies_infra, "get_graph_db", lambda: MagicMock())
    first = tick_slots.get_player_location_reader()
    second = tick_slots.get_player_location_reader()
    assert first is second


def test_all_four_factories_share_one_location_reader(monkeypatch) -> None:
    sentinel = object()
    monkeypatch.setattr(tick_slots, "get_player_location_reader", lambda: sentinel)
    monkeypatch.setattr(dependencies_infra, "get_graph_db", lambda: MagicMock())
    monkeypatch.setattr(
        tick_slots, "create_llm_client_for_engine", lambda *a, **k: MagicMock()
    )
    monkeypatch.setattr(tick_slots, "_register_adapter", lambda adapter: adapter)

    readers = {
        name: getattr(tick_slots, name)()._location_reader for name in _FACTORY_NAMES
    }

    for name, reader in readers.items():
        assert reader is sentinel, f"{name} did not inject the shared location reader"
