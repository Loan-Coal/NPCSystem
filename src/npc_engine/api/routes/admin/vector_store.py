"""
Module: vector_store
Layer: api
Purpose: Admin routes that populate the vector store and report what it holds —
         POST /v1/admin/vector-store/rehydrate and GET /v1/admin/debug/vector-store.
Does NOT: perform authentication itself, encode text, or query Neo4j directly.
Dependencies injected: AsyncSession, EmbeddingIndex, Settings (via FastAPI Depends).
Used by: api.router_registry (registered under the admin prefix).

Why a ROUTE and not only a boot step
------------------------------------
`restore-with-app-stopped` waits only on `/health`, so hydration-as-a-lifespan-side-effect
had to finish before health or race the eval run. That constraint is what produced
ISSUE-211's impossible ordering. With an explicit call the harness step becomes ordered
and observable — reset, rehydrate, ASSERT item_count > 0, generate — and boot hydration
degrades from a correctness requirement to a latency optimisation (DEC-208 Decision 3).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from neo4j import AsyncSession

from npc_engine.api.dependencies import get_db_session, get_embedding_index
from npc_engine.api.dependency_singletons import get_graph_db
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.config import Settings, get_settings
from npc_engine.retrieval.embedding import EMBED_DIMENSION, EmbeddingIndex, EmbeddingReconciler
from npc_engine.retrieval.embedding.corpus import ensure_corpus, read_corpus_fingerprint
from npc_engine.schema.corpus_models import CorpusFingerprint, CorpusReport

LOGGER = logging.getLogger(__name__)

rehydrate_router = APIRouter(prefix="/vector-store")
debug_router = APIRouter(prefix="/debug")


def _build_reconciler(embedding_index: EmbeddingIndex, settings: Settings) -> EmbeddingReconciler:
    """Construct the reconciler ensure_corpus drives until dry."""
    return EmbeddingReconciler(
        graph_db=get_graph_db(),
        embedding_index=embedding_index,
        interval_seconds=settings.EMBEDDING_RECONCILE_INTERVAL_SECONDS,
        batch_size=settings.VECTOR_STORE_CORPUS_BATCH_SIZE,
    )


@rehydrate_router.post("/rehydrate", response_model=OkEnvelope[CorpusReport])
async def rehydrate_vector_store(
    session: AsyncSession = Depends(get_db_session),
    embedding_index: EmbeddingIndex = Depends(get_embedding_index),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Reconcile embeddings until dry, load them into the vector store, and report.

    Returns:
        The CorpusReport: nodes_read, upserted, missing_embedding, reconcile_passes and
        the corpus fingerprint. `nodes_read == 0` is logged at ERROR — a silent empty
        corpus costs a night of generation and then reads as a null result.
    """
    report = await ensure_corpus(
        session,
        embedding_index,
        _build_reconciler(embedding_index, settings),
        batch_size=settings.VECTOR_STORE_CORPUS_BATCH_SIZE,
    )
    if report.nodes_read == 0:
        LOGGER.error(
            "vector_store.rehydrate_read_nothing missing_embedding=%s reconcile_passes=%s",
            report.missing_embedding,
            report.reconcile_passes,
        )
    else:
        LOGGER.info(
            "vector_store.rehydrated nodes_read=%s item_count=%s corpus_sha=%s",
            report.nodes_read,
            report.fingerprint.item_count,
            report.fingerprint.corpus_sha,
        )
    return ok_response(report)


async def _liveness_fingerprint(embedding_index: EmbeddingIndex) -> CorpusFingerprint:
    """Report store identity WITHOUT the membership digest — the pre-P9 cheap probe.

    Keeps `include_sha=false` free of the embedded-node scan, for callers that only want
    to know the store is up.
    """
    return CorpusFingerprint(
        item_count=await embedding_index.count(),
        embedding_model=embedding_index.model_name,
        embedding_dim=EMBED_DIMENSION,
        corpus_sha="",
    )


@debug_router.get("/vector-store", response_model=OkEnvelope[CorpusFingerprint])
async def read_vector_store_state(
    include_sha: bool = True,
    session: AsyncSession = Depends(get_db_session),
    embedding_index: EmbeddingIndex = Depends(get_embedding_index),
    settings: Settings = Depends(get_settings),
) -> dict[str, object]:
    """Report what the vector store currently holds, without changing it.

    `corpus_sha` was empty here unconditionally until P9, on the argument that this route
    is a cheap liveness probe. That made DEC-210 Decision 2 unachievable: RunConfig fills
    its four corpus fields from THIS route, so every generation record carried an empty
    sha — and the sha is the only one of the four that can detect the corpus MOVING,
    since swapping one node for another leaves item_count unchanged. The other route that
    knows the sha computes it while WRITING the store, which a mid-run freeze check may
    not do.

    Args:
        include_sha: Compute the membership digest. False skips the embedded-node scan,
            restoring the pre-P9 cost.
        session: Scoped Neo4j session; the embedded-node scan reads through it.
        embedding_index: The vector store.
        settings: Application settings, for the backend label.

    Returns:
        A CorpusFingerprint carrying item_count, the embedding model, the dimension and
        — unless include_sha is false — the membership digest.
    """
    fingerprint = (
        await read_corpus_fingerprint(
            session=session,
            index=embedding_index,
            batch_size=settings.VECTOR_STORE_CORPUS_BATCH_SIZE,
        )
        if include_sha
        else await _liveness_fingerprint(embedding_index)
    )
    return ok_response(fingerprint, meta={"backend": settings.VECTOR_STORE_BACKEND})
