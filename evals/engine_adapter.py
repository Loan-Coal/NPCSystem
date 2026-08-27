"""
Module: engine_adapter
Layer: evals (evaluation harness — standalone, outside npc_engine layer model)
Purpose: The single sanctioned gateway between the evals harness and src/npc_engine.
         All npc_engine imports live here. Every other evals module imports from this
         module instead of touching npc_engine directly (enforced by test_src_free.py).
         Also provides synchronous Ollama probe helpers (fetch_model_digest,
         fetch_ollama_version) used by run_config to capture model identity.
Dependencies: npc_engine.config, npc_engine.graph, npc_engine.retrieval.embedding,
              httpx (for Ollama probes — no npc_engine import needed)
Used by: evals.retrieval_runner, evals.run_config

DEC-147 §2: engine_adapter is the sole point of contact between evals/ and npc_engine.
"""

from __future__ import annotations

import logging
import os
from typing import Any

_logger = logging.getLogger(__name__)


async def build_retrieval_stack() -> tuple[Any, Any]:
    """Bootstrap and return the retrieval infrastructure needed by retrieval_runner.

    Reads Settings from the environment (sets API_KEY_SECRET default if absent),
    builds the embedding index and a connected Neo4j driver.

    Returns:
        A 2-tuple ``(embedding_index, driver)`` ready for use in run_eval().

    Raises:
        Exception: Propagates any Neo4j or embedding store initialisation error.
    """
    # The attr-defined suppression below is a resolution artifact, not a missing symbol:
    # get_settings EXISTS at runtime (it is in dir(npc_engine.config)). mypy cannot see
    # it when invoked as `mypy evals/` because
    # the data-only directory src/npc_engine/config/ (it holds llm_config.yaml) shadows
    # src/npc_engine/config.py as a namespace package. mypy.ini excludes that directory
    # from CHECKING, which does not stop it winning import RESOLUTION here. Narrow
    # suppression rather than a shared-config change; the shadowing itself is logged.
    from npc_engine.config import get_settings  # type: ignore[attr-defined]
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
    # Same shadowing artifact as build_retrieval_stack above.
    from npc_engine.config import get_settings  # type: ignore[attr-defined]

    os.environ.setdefault("API_KEY_SECRET", "eval-key-placeholder")
    return str(get_settings().NEO4J_URI)


def fetch_model_digest(model: str, ollama_url: str) -> str | None:
    """Fetch the model's content digest from Ollama /api/show.

    Returns None if Ollama is unavailable — callers treat None as "digest unknown"
    and the omission is explicit in the RunConfig rather than silently missing.

    Args:
        model: Ollama model tag (e.g. 'qwen2.5:7b').
        ollama_url: Ollama base URL (e.g. 'http://localhost:11434').
    Returns:
        Digest string from the /api/show response, or None on any failure.
    """
    import httpx

    try:
        r = httpx.post(
            f"{ollama_url}/api/show",
            json={"name": model},
            timeout=10.0,
        )
        r.raise_for_status()
        value = r.json().get("digest")
        return str(value) if value is not None else None
    except Exception as exc:
        _logger.warning("fetch_model_digest model=%s error=%r", model, exc)
        return None


def fetch_ollama_version(ollama_url: str) -> str | None:
    """Fetch the Ollama server version string from /api/version.

    Returns None if Ollama is unavailable.

    Args:
        ollama_url: Ollama base URL (e.g. 'http://localhost:11434').
    Returns:
        Version string (e.g. '0.1.47'), or None on any failure.
    """
    import httpx

    try:
        r = httpx.get(f"{ollama_url}/api/version", timeout=10.0)
        r.raise_for_status()
        value = r.json().get("version")
        return str(value) if value is not None else None
    except Exception as exc:
        _logger.warning("fetch_ollama_version url=%s error=%r", ollama_url, exc)
        return None


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


def fetch_corpus_fingerprint(base_url: str, api_key: str) -> dict[str, Any] | None:
    """Fetch the vector store's identity from GET /v1/admin/debug/vector-store.

    DEC-210 Decision 2: the corpus is the retrieval SUBSTRATE, and DEC-194's rule —
    never record a config you did not run — has covered only the profile NAME. Without
    this, "was RAG live during this run?" is an inference from tierB.items rather than a
    recorded fact, and two arms are neither provably comparable nor provably not.

    Args:
        base_url: Engine base URL (e.g. 'http://localhost:8000').
        api_key: Admin API key.
    Returns:
        Dict with item_count, embedding_model, embedding_dim, corpus_sha; None when the
        engine is unreachable. None is DELIBERATELY distinct from a zero item_count: a
        run that could not ask must not look like a run that asked and got nothing.
    """
    import httpx

    try:
        response = httpx.get(
            f"{base_url}/v1/admin/debug/vector-store",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json().get("data")
        return dict(data) if isinstance(data, dict) else None
    except Exception as exc:
        _logger.warning("fetch_corpus_fingerprint url=%s error=%r", base_url, exc)
        return None
