"""
Module: corpus_models
Layer: schema
Purpose: The report `ensure_corpus` returns and the fingerprint an eval run records —
         what the vector store holds, produced by which embedding model, at what size.
Dependencies: pydantic.
Used by: retrieval.embedding.corpus (produces it), api.routes.admin.vector_store
         (serves it), evals (records it beside retrieval_profile).

Does NOT: read settings, touch the graph, or perform retrieval.
Dependencies injected: None — pure data models.

Why a report and not a log line
-------------------------------
Corpus population used to be an implicit ordering contract between two asyncio tasks,
findable only by reading main.py's lifespan. DEC-208 replaced it with a function that
returns a value; this is that value. DEC-210 then makes the fingerprint half of it part
of the generation record, so "was RAG live during this run?" is a recorded fact rather
than an inference from tierB.items.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["CorpusFingerprint", "CorpusReport"]


class CorpusFingerprint(BaseModel):
    """Identity of the corpus a measurement ran against.

    Attributes:
        item_count: Entries currently held by the vector store.
        embedding_model: The model that produced the stored vectors.
        embedding_dim: Vector width, in floats.
        corpus_sha: Digest over the corpus MEMBERSHIP (sorted node ids and their model),
            not over the vectors. Two runs with the same sha retrieved from the same set
            of nodes; a changed sha means the arms are not comparable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_count: int = Field(ge=0)
    embedding_model: str
    embedding_dim: int = Field(ge=0)
    corpus_sha: str


class CorpusReport(BaseModel):
    """Outcome of one ensure_corpus run.

    Attributes:
        nodes_read: Embedded nodes read back out of Neo4j.
        upserted: Entries written into the vector store.
        missing_embedding: Embeddable nodes that still carry no embedding after
            reconcile-until-dry. Non-zero means the corpus is incomplete.
        reconcile_passes: Reconciliation cycles run before the reader went dry.
        fingerprint: The corpus identity, for the generation record.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    nodes_read: int = Field(ge=0)
    upserted: int = Field(ge=0)
    missing_embedding: int = Field(ge=0)
    reconcile_passes: int = Field(ge=0)
    fingerprint: CorpusFingerprint
