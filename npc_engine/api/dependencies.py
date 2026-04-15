"""
dependencies.py - FastAPI dependency composition root for runtime services.

Does NOT: execute route business logic.

Dependencies injected: Settings.
"""

from functools import lru_cache
from typing import AsyncGenerator

from fastapi import Depends
from neo4j import AsyncSession

from config import Settings, get_settings
from engines.dialogue.dialogue_handler import DialogueHandler
from engines.dialogue.session_store import SessionStore
from engines.emotion.emotion_store import EmotionStore
from engines.emotion.emotion_updater import EmotionUpdater
from engines.events.event_handler import EventHandler
from engines.gossip.gossip_handler import GossipHandler
from engines.llm.factory import create_llm_client
from graph.db import GraphDB
from retrieval.embedding_index import EmbeddingIndex
from retrieval.vector_store_factory import create_vector_store
from scheduler.game_clock import GameClock
from scheduler.tick_scheduler import TickScheduler


@lru_cache
def get_graph_db() -> GraphDB:
    settings = get_settings()
    return GraphDB(settings=settings)


@lru_cache
def get_session_store() -> SessionStore:
    settings = get_settings()
    return SessionStore(ttl_seconds=settings.DIALOGUE_SESSION_TTL, max_turns=settings.DIALOGUE_SESSION_TURNS)


@lru_cache
def get_emotion_store() -> EmotionStore:
    return EmotionStore()


@lru_cache
def get_emotion_updater() -> EmotionUpdater:
    return EmotionUpdater(emotion_store=get_emotion_store())


@lru_cache
def get_embedding_index() -> EmbeddingIndex:
    settings = get_settings()
    vector_store = create_vector_store(settings=settings)
    return EmbeddingIndex(vector_store=vector_store)


@lru_cache
def get_gossip_handler() -> GossipHandler:
    settings = get_settings()
    return GossipHandler(settings=settings, embedding_index=get_embedding_index())


@lru_cache
def get_event_handler() -> EventHandler:
    settings = get_settings()
    return EventHandler(settings=settings, embedding_index=get_embedding_index())


@lru_cache
def get_game_clock() -> GameClock:
    settings = get_settings()
    return GameClock(mode=settings.CLOCK_MODE)


@lru_cache
def get_tick_scheduler() -> TickScheduler:
    settings = get_settings()
    return TickScheduler(
        clock=get_game_clock(),
        gossip_handler=get_gossip_handler(),
        event_handler=get_event_handler(),
        gossip_interval=settings.GOSSIP_TICK_INTERVAL,
        event_interval=settings.EVENT_TICK_INTERVAL,
        distributed_lease_enabled=settings.DISTRIBUTED_TICK_LEASE_ENABLED,
        scheduler_id=settings.TICK_SCHEDULER_ID,
        lease_owner_id=settings.TICK_LEASE_OWNER_ID,
        lease_ttl_seconds=settings.TICK_LEASE_TTL_SECONDS,
    )


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    graph_db = get_graph_db()
    await graph_db.connect()
    async with graph_db.get_session() as session:
        yield session


def get_llm_client(settings: Settings = Depends(get_settings)):
    return create_llm_client(settings=settings)


def get_dialogue_handler(
    session: AsyncSession = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    llm_client=Depends(get_llm_client),
) -> DialogueHandler:
    return DialogueHandler(
        session=session,
        settings=settings,
        llm_client=llm_client,
        session_store=get_session_store(),
        emotion_updater=get_emotion_updater(),
        embedding_index=get_embedding_index(),
    )
