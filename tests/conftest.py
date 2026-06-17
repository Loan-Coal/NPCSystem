"""
conftest.py - Pytest fixtures shared across the unit and integration test suites.

Does NOT: connect to Neo4j, call LLM services, or modify production data.

Dependencies injected: None.
"""

from __future__ import annotations

import pytest

from npc_engine.scheduler.game_clock import GameClock
from npc_engine.api.dependency_singletons import (
    get_context_cache,
    get_dialogue_engine_model_config,
    get_embedding_index,
    get_emotion_store,
    get_emotion_updater,
    get_event_handler,
    get_faction_politics_engine,
    get_game_clock,
    get_game_schema,
    get_gossip_handler,
    get_graph_db,
    get_idempotency_service,
    get_llm_config,
    get_memory_consolidation_engine,
    get_pricing_engine,
    get_quest_generation_engine,
    get_quest_lifecycle_engine,
    get_redis_runtime,
    get_reindex_job_service,
    get_routine_engine,
    get_session_store,
    get_story_pacing_engine,
    get_tick_scheduler,
    get_type_registry,
)


@pytest.fixture
def fake_clock() -> GameClock:
    """Return a deterministic GameClock at tick 0 for tick-dependent tests.

    Use this fixture instead of constructing GameClock inline so tests are
    self-documenting about clock behaviour. The clock is purely counter-based
    and never blocks on real time — safe to use without sleeps.
    """
    return GameClock(mode="manual")


@pytest.fixture(autouse=True)
def _clear_singleton_caches():
    """Clear all lru_cache singletons before and after each test.

    Prevents state leakage between test modules that monkeypatch singletons
    or construct engines with different configurations.
    """
    _clear_all()
    yield
    _clear_all()


def _clear_all() -> None:
    get_graph_db.cache_clear()
    get_session_store.cache_clear()
    get_emotion_store.cache_clear()
    get_emotion_updater.cache_clear()
    get_embedding_index.cache_clear()
    get_gossip_handler.cache_clear()
    get_event_handler.cache_clear()
    get_quest_lifecycle_engine.cache_clear()
    get_game_clock.cache_clear()
    get_faction_politics_engine.cache_clear()
    get_story_pacing_engine.cache_clear()
    get_quest_generation_engine.cache_clear()
    get_routine_engine.cache_clear()
    get_tick_scheduler.cache_clear()
    get_redis_runtime.cache_clear()
    get_game_schema.cache_clear()
    get_type_registry.cache_clear()
    get_llm_config.cache_clear()
    get_dialogue_engine_model_config.cache_clear()
    get_idempotency_service.cache_clear()
    get_reindex_job_service.cache_clear()
    get_pricing_engine.cache_clear()
    # get_trade_engine is per-request (not lru_cache) since SEV-24 — no cache to clear.
    get_context_cache.cache_clear()
    get_memory_consolidation_engine.cache_clear()
