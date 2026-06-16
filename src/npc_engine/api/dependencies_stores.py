"""
Module: dependencies_stores
Layer: api
Purpose: Singleton factory providers for in-process store and index dependencies —
         session store, emotion store, embedding index, game clock, caches, idempotency.
Does NOT: create session-scoped or per-request dependencies.
Dependencies injected: infra singletons from dependencies_infra.
Used by: api.dependency_singletons (re-exporter), api.dependencies_engines
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from npc_engine.api.dependencies_infra import get_graph_db
from npc_engine.config import get_settings
from npc_engine.engines.dialogue.session_store import SessionStore
from npc_engine.engines.emotion.emotion_model_factory import build_emotion_model
from npc_engine.engines.emotion.emotion_store import EmotionStore
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.engines.knowledge_learning.knowledge_extraction_engine import (
    KnowledgeExtractionEngine,
)
from npc_engine.graph.repositories.emotion_repository import Neo4jEmotionRepository
from npc_engine.graph.repositories.knowledge_repository import Neo4jKnowledgeRepository
from npc_engine.graph.repositories.relation_phase_write_repository import (
    Neo4jRelationPhaseWriteRepository,
)
from npc_engine.graph.repositories.relation_read_repository import (
    Neo4jRelationReadRepository,
)
from npc_engine.engines.idempotency.service import IdempotencyService
from npc_engine.graph.idempotency_writer import Neo4jIdempotencyStore
from npc_engine.retrieval.dialogue_context_cache import PartialDialogueContextCache
from npc_engine.retrieval.embedding_index import EmbeddingIndex
from npc_engine.retrieval.reindex_job_service import ReindexJobService
from npc_engine.retrieval.vector_store_factory import create_vector_store
from npc_engine.scheduler.engine_status_store import EngineStatusStore
from npc_engine.scheduler.game_clock import GameClock


@lru_cache
def get_session_store() -> SessionStore:
    """Create singleton dialogue session store.

    Returns:
        SessionStore configured with TTL and max-turns from application settings.
    """
    settings = get_settings()
    return SessionStore(ttl_seconds=settings.DIALOGUE_SESSION_TTL, max_turns=settings.DIALOGUE_SESSION_TURNS)


@lru_cache
def get_emotion_store() -> EmotionStore:
    """Create singleton in-memory emotion store.

    Returns:
        EmotionStore instance.
    """
    return EmotionStore()


@lru_cache
def get_emotion_updater() -> EmotionUpdater:
    """Create singleton emotion updater bound to the shared emotion store.

    The emotion model is selected from settings (F1.3): VAD baseline or
    trait-modulated, via ``build_emotion_model``.

    Returns:
        EmotionUpdater wired to the singleton EmotionStore and configured model.
    """
    return EmotionUpdater(
        emotion_store=get_emotion_store(),
        model=build_emotion_model(get_settings()),
        writer=Neo4jEmotionRepository(get_graph_db()),
    )


@lru_cache
def get_knowledge_extraction_engine() -> KnowledgeExtractionEngine:
    """Create the singleton KnowledgeExtractionEngine wired to the Neo4j belief adapter.

    Gated at runtime by Settings.KNOWLEDGE_LEARNING_ENABLED inside DialogueHandler
    (default False) — this wiring is inert until the feature flag is enabled.

    Returns:
        KnowledgeExtractionEngine depending on the KnowledgeGraphPort abstraction.
    """
    return KnowledgeExtractionEngine(
        knowledge_repo=Neo4jKnowledgeRepository(get_graph_db()),
    )


def get_dialogue_graph_ports() -> dict[str, Any]:
    """Build the DialogueHandler graph-port kwargs (knowledge engine + relation phase ports).

    Bundles the optional knowledge engine with the relation read/write ports the phase
    applier depends on (DEC-122 / SEV-24), so the api composition root injects one set of
    graph-backed kwargs and DialogueHandler holds no Neo4j session for phase transitions.

    Returns:
        A kwargs mapping with keys ``knowledge_engine``, ``relation_reader``, and
        ``relation_phase_writer`` ready to splat into DialogueHandler.
    """
    graph_db = get_graph_db()
    return {
        "knowledge_engine": get_knowledge_extraction_engine(),
        "relation_reader": Neo4jRelationReadRepository(graph_db),
        "relation_phase_writer": Neo4jRelationPhaseWriteRepository(graph_db),
    }


@lru_cache
def get_embedding_index() -> EmbeddingIndex:
    """Create singleton embedding index backed by the configured vector store.

    Returns:
        EmbeddingIndex wrapping the configured VectorStore implementation.
    """
    settings = get_settings()
    vector_store = create_vector_store(settings=settings)
    return EmbeddingIndex(vector_store=vector_store, model_name=settings.EMBEDDING_MODEL)


@lru_cache
def get_engine_status_store() -> EngineStatusStore:
    """Create singleton engine status store for per-engine tick tracking.

    Returns:
        EngineStatusStore instance shared by TickScheduler and observability routes.
    """
    return EngineStatusStore()


@lru_cache
def get_game_clock() -> GameClock:
    """Create singleton game clock.

    Returns:
        GameClock configured with the application clock mode.
    """
    settings = get_settings()
    return GameClock(mode=settings.CLOCK_MODE)


@lru_cache
def get_idempotency_store() -> Neo4jIdempotencyStore:
    """Create singleton idempotency persistence backend.

    Returns:
        Neo4jIdempotencyStore instance.
    """
    return Neo4jIdempotencyStore()


@lru_cache
def get_idempotency_service() -> IdempotencyService:
    """Create singleton idempotency service for middleware preflight and finalization.

    Returns:
        IdempotencyService wired to the singleton GraphDB and idempotency store.
    """
    return IdempotencyService(
        settings=get_settings(),
        graph_db=get_graph_db(),
        store=get_idempotency_store(),
    )


@lru_cache
def get_context_cache() -> PartialDialogueContextCache:
    """Create singleton dialogue context cache.

    Returns:
        PartialDialogueContextCache configured with the session TTL from application settings.
    """
    settings = get_settings()
    return PartialDialogueContextCache(ttl_seconds=settings.DIALOGUE_SESSION_TTL)


@lru_cache
def get_reindex_job_service() -> ReindexJobService:
    """Create singleton reindex job lifecycle manager.

    Returns:
        ReindexJobService instance.
    """
    return ReindexJobService()
