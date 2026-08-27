"""
test_embedding_model_identity.py - DEC-211 Decisions 1 and 2.

Changing EMBEDDING_MODEL used to silently invalidate every stored vector and every prior
measurement, with nothing anywhere that would say so: the reconciler compares
last_embedding_indexed_at against last_graph_updated_at and never model identity. That
is a missing field, not a law of the system.

Does NOT: connect to Neo4j — the session is a recording stub.

Dependencies injected: a fake AsyncSession capturing query text and parameters.
"""

from __future__ import annotations

import pytest

from npc_engine.graph.infra.embedding_sync_queries import batch_set_embeddings, select_stale_nodes


class _Result:
    def __init__(self, rows: list[dict] | None = None) -> None:
        self._rows = rows or []

    def __aiter__(self):
        async def gen():
            for row in self._rows:
                yield row
        return gen()

    async def consume(self) -> None:
        return None


class FakeSession:
    """Records the Cypher and parameters each call made."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.queries: list[str] = []
        self.params: list[dict] = []
        self._rows = rows or []

    async def run(self, query: str, **params):
        self.queries.append(query)
        self.params.append(params)
        return _Result(self._rows)


@pytest.mark.asyncio
async def test_batch_set_embeddings_records_the_model_that_produced_the_vector() -> None:
    session = FakeSession()

    await batch_set_embeddings(
        session,  # type: ignore[arg-type]
        [{"id": "npc_1", "embedding": [0.1, 0.2], "indexed_at": "2026-08-27T00:00:00+00:00",
          "embedding_model": "all-MiniLM-L6-v2", "embedding_dim": 2}],
    )

    assert "embedding_model" in session.queries[0]
    assert "embedding_dim" in session.queries[0]


@pytest.mark.asyncio
async def test_a_model_mismatch_makes_a_node_stale() -> None:
    """Otherwise a changed EMBEDDING_MODEL leaves a mixed-model store ranking nonsense."""
    session = FakeSession()

    await select_stale_nodes(session, 10, embedding_model="bge-small-en")  # type: ignore[arg-type]

    assert session.params[0]["embedding_model"] == "bge-small-en"
    assert "n.embedding_model" in session.queries[0]
