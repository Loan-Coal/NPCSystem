"""
Module: engine_adapter
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: The single sanctioned gateway between the evals harness and src/npc_engine.
         All npc_engine imports live here. Every other evals module imports from this
         module instead of touching npc_engine directly (enforced by test_src_free.py).
Dependencies: npc_engine.config, npc_engine.graph, npc_engine.retrieval.embedding
Used by: evals.retrieval_runner

DEC-147 §2: engine_adapter is the sole point of contact between evals/ and npc_engine.
"""

from __future__ import annotations

import os
from typing import Any


async def build_retrieval_stack() -> tuple[Any, Any]:
    """Bootstrap and return the retrieval infrastructure needed by retrieval_runner.

    Reads Settings from the environment (sets API_KEY_SECRET default if absent),
    builds the embedding index and a connected Neo4j driver.

    Returns:
        A 2-tuple ``(embedding_index, driver)`` ready for use in run_eval().

    Raises:
        Exception: Propagates any Neo4j or embedding store initialisation error.
    """
    from npc_engine.config import get_settings
    from npc_engine.graph.infra.db import GraphDB
    from npc_engine.retrieval.embedding import EmbeddingIndex, create_vector_store

    os.environ.setdefault("API_KEY_SECRET", "eval-key-placeholder")
    settings = get_settings()
    vector_store = create_vector_store(settings=settings)
    embedding_index = EmbeddingIndex(
        vector_store=vector_store, model_name=settings.EMBEDDING_MODEL
    )
    graph_db = GraphDB(settings=settings)
    await graph_db.connect()
    return embedding_index, graph_db.driver


def neo4j_uri() -> str:
    """Return the configured Neo4j URI, for diagnostics in connection-failure messages.

    Kept here rather than importing Settings at the call site: engine_adapter is the
    only module allowed to touch npc_engine (DEC-147 §2).

    Returns:
        The NEO4J_URI value from Settings.
    """
    from npc_engine.config import get_settings

    os.environ.setdefault("API_KEY_SECRET", "eval-key-placeholder")
    return str(get_settings().NEO4J_URI)


async def known_event_ids(session: Any, npc_id: str) -> set[str]:
    """Return event node IDs the NPC has direct graph knowledge of (KNOWS_ABOUT edges).

    Args:
        session: Active Neo4j AsyncSession.
        npc_id: Character node ID to query.

    Returns:
        Set of event node ID strings the NPC knows about.
    """
    from npc_engine.graph.graph_reader import get_known_event_ids_for_npc

    return await get_known_event_ids_for_npc(session=session, npc_id=npc_id)
