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

_CORPUS_PAGE_LIMIT: int = 100_000
"""One page large enough to hold any corpus this harness measures (currently 51 nodes).

A guard, not a tuning value: paging here would let a silently truncated read report a
smaller supply than the world holds, which is the exact class of error DEC-214 exists to
stop. If a corpus ever approaches this, page it deliberately rather than raising this.
"""


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
    """Fetch the model's content digest from Ollama /api/tags.

    Reads GET /api/tags (the model listing) rather than POST /api/show: Ollama
    0.33 dropped the top-level 'digest' key /api/show used to return, which made
    this function return None for every model and R2.1's gate unconditionally
    fatal (ISSUE-286). /api/tags still carries a digest per listed model, so this
    matches the requested tag against each entry's 'model' (falling back to
    'name', since either key holds the tag depending on server version) and
    returns that entry's digest.

    Returns None if Ollama is unavailable or the model tag is not listed. None is
    fatal upstream since R2.1: run_config.resolve_run_config raises
    ModelDigestUnavailableError rather than recording an unattributable run. This
    function stays total so callers that genuinely only want a probe (health
    checks) keep working.

    Args:
        model: Ollama model tag (e.g. 'qwen2.5:7b').
        ollama_url: Ollama base URL (e.g. 'http://localhost:11434').
    Returns:
        Digest string for the matching /api/tags entry, or None on any failure.
    """
    import httpx

    try:
        r = httpx.get(f"{ollama_url}/api/tags", timeout=10.0)
        r.raise_for_status()
        models = r.json().get("models", [])
        for entry in models:
            if entry.get("model") == model or entry.get("name") == model:
                digest = entry.get("digest")
                return str(digest) if digest is not None else None
        return None
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


async def rag_scope_ids(session: Any, npc_id: str) -> set[str]:
    """Return the node ids tier-B retrieval is allowed to range over for this NPC.

    The DEC-209 scope: the NPC's 1-hop subgraph, its location's co-located nodes and its
    faction's fellow members. It does NOT subtract known events — the caller does that,
    because the caller already holds that set.

    Exposed here because the retrieval eval searched the vector store with no filter at
    all. Post-P8 that is an unfiltered sweep of a mixed corpus: the exact defect DEC-209
    removed from the engine, left running inside the instrument measuring it.

    Args:
        session: Active Neo4j AsyncSession.
        npc_id: Character node ID to scope.

    Returns:
        Set of node ID strings. EMPTY means no RAG, never "all of it".
    """
    from npc_engine.graph.graph_rag_queries import get_rag_scope_ids_for_npc

    return await get_rag_scope_ids_for_npc(session, npc_id=npc_id)


async def embedded_node_ids(session: Any) -> set[str]:
    """Return the id of every node that carries an embedding — the corpus, as ids.

    This is the third term in the supply a tier-B arm is bounded by. The vector search
    can only ever return `(scope - known) & corpus`, and the corpus holds only the three
    embeddable node types, so the intersection is far smaller than the scope. Measuring
    the scope alone is what made `wide_rag` look sizeable when its real candidate set was
    3-8 nodes (DEC-214).

    Args:
        session: Active Neo4j AsyncSession.

    Returns:
        Set of node ID strings currently carrying an embedding.
    """
    from npc_engine.graph.infra.embedding_load_queries import select_embedded_nodes

    rows = await select_embedded_nodes(session, skip=0, limit=_CORPUS_PAGE_LIMIT)
    return {str(row["node_id"]) for row in rows}


def declared_retrieval_profiles() -> dict[str, Any]:
    """Return every A/B arm declared in the SHIPPED llm_config.yaml, by name.

    Resolves the path through `Settings.LLM_CONFIG_PATH` — the same value
    `api.dependencies_infra` passes — so the harness cannot enumerate a different set of
    arms than the engine would resolve.

    Returns:
        Mapping of arm name to RetrievalProfile. 'default' is NOT included: it is
        resolved from Settings by build_default_profile and is never declared.
    """
    # Same namespace-package shadowing artifact as build_retrieval_stack above:
    # get_settings exists at runtime, but src/npc_engine/config/ (the YAML directory)
    # shadows config.py during mypy's import resolution.
    from npc_engine.config import get_settings  # type: ignore[attr-defined]
    from npc_engine.schema.llm_schema_loader import load_llm_config

    return load_llm_config(config_path=get_settings().LLM_CONFIG_PATH).retrieval_profiles


def resolve_retrieval_profile(name: str) -> Any:
    """Resolve a named A/B arm to the RetrievalProfile the engine would apply.

    Resolution is STRICT (DEC-194 decision 2): an undeclared name raises rather than
    falling back, so a run cannot record `--retrieval-profile wide_rag` while having
    measured the default.

    Args:
        name: Arm name; 'default' resolves without being declared in YAML.

    Returns:
        The resolved RetrievalProfile.

    Raises:
        RetrievalProfileNotFoundError: When name is neither 'default' nor declared.
    """
    # Same namespace-package shadowing artifact as build_retrieval_stack above.
    from npc_engine.config import get_settings  # type: ignore[attr-defined]
    from npc_engine.schema.retrieval_profile_models import (
        build_default_profile,
        resolve_retrieval_profile as _resolve,
    )

    settings = get_settings()
    return _resolve(
        name,
        profiles=declared_retrieval_profiles(),
        fallback=build_default_profile(
            rag_top_k=settings.RAG_TOP_K,
            cross_encoder_enabled=settings.CROSS_ENCODER_ENABLED,
        ),
    )


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


def structured_output_temperature() -> float:
    """Return the temperature the engine actually uses on structured generation calls.

    LLMStructuredProtocol.generate_structured carries no temperature argument, so the
    adapters substitute Settings.STRUCTURED_OUTPUT_TEMPERATURE for whatever an engine's
    llm_config.yaml declares. Any run recording the YAML value as its provenance is
    recording a number the model never ran at.

    Returns:
        The shipped STRUCTURED_OUTPUT_TEMPERATURE value.
    """
    # See build_retrieval_stack for why get_settings needs the attr-defined suppression.
    from npc_engine.config import get_settings  # type: ignore[attr-defined]

    os.environ.setdefault("API_KEY_SECRET", "eval-key-placeholder")
    return float(get_settings().STRUCTURED_OUTPUT_TEMPERATURE)
