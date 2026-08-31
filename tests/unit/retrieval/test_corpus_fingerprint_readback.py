"""
Module: test_corpus_fingerprint_readback
Layer: test (unit)
Purpose: Pin that the corpus MEMBERSHIP digest is readable without mutating the store,
         so P9's gate 2 and P10's gate 5 can compare it across arms and across a run.
Dependencies: pytest; npc_engine.retrieval.embedding.corpus
Used by: pytest (make test / make check)

WHY THIS EXISTS
DEC-210 Decision 2 writes {item_count, embedding_model, dim, corpus_sha} into every
generation record so that "two arms are provably comparable or provably not", and so that
a P10 gate can assert the corpus did not move between a run's first turn and its last.

RunConfig fills those four fields from GET /v1/admin/debug/vector-store, and that route
returned `corpus_sha=""` unconditionally. So the ONE field that carries membership — the
only one that can detect the corpus moving, since item_count is unchanged by swapping a
node for another — was empty in every record that decision produced. The other route that
knows the sha, POST /rehydrate, computes it as a side effect of WRITING the store, which
is not something a mid-run gate may do.

`read_corpus_fingerprint` is the missing read-only half.

Does NOT: hit Neo4j, encode text, or touch a real vector store.
"""

from __future__ import annotations

from typing import Any

import pytest

from npc_engine.retrieval.embedding import corpus as corpus_module


class _FakeIndex:
    """Minimal CorpusStoreProtocol stand-in that records whether it was written to."""

    model_name = "all-MiniLM-L6-v2"

    def __init__(self, item_count: int = 51) -> None:
        self._item_count = item_count
        self.upserts: list[str] = []

    async def count(self) -> int:
        return self._item_count

    async def upsert_vector(self, *, item_id: str, vector: Any, payload: Any) -> None:
        self.upserts.append(item_id)


def _rows(*node_ids: str) -> list[dict[str, Any]]:
    return [
        {
            "node_id": node_id,
            "embedding": [0.1, 0.2, 0.3],
            "embedding_model": "all-MiniLM-L6-v2",
            "embedding_dim": 384,
            "payload": {"id": node_id},
        }
        for node_id in node_ids
    ]


@pytest.fixture
def loaded(monkeypatch: pytest.MonkeyPatch):
    """Install a row loader and return a setter for what it yields."""
    state: dict[str, list[dict[str, Any]]] = {"rows": []}

    async def fake_load(_session: Any, _batch_size: int) -> list[dict[str, Any]]:
        return state["rows"]

    monkeypatch.setattr(corpus_module, "_load_all_embedded_nodes", fake_load)
    return state


@pytest.mark.asyncio
async def test_the_membership_digest_is_readable_without_writing_the_store(loaded) -> None:
    """A mid-run freeze check must not itself mutate the thing it is checking."""
    loaded["rows"] = _rows("captain_sorn", "old_henryk")
    index = _FakeIndex()

    fingerprint = await corpus_module.read_corpus_fingerprint(
        session=None, index=index, batch_size=200
    )

    assert fingerprint.corpus_sha, "an empty sha cannot detect the corpus moving"
    assert index.upserts == [], "reading the fingerprint must not write the store"
    assert fingerprint.item_count == 51
    assert fingerprint.embedding_model == "all-MiniLM-L6-v2"
    assert fingerprint.embedding_dim == 384


@pytest.mark.asyncio
async def test_the_digest_is_stable_across_two_reads_of_one_corpus(loaded) -> None:
    """Gate 2 asserts the fingerprint is IDENTICAL across arms; a digest that varied
    between two reads of one unchanged corpus would make that assertion meaningless."""
    loaded["rows"] = _rows("captain_sorn", "old_henryk", "mira_innkeeper")
    index = _FakeIndex()

    first = await corpus_module.read_corpus_fingerprint(
        session=None, index=index, batch_size=200
    )
    second = await corpus_module.read_corpus_fingerprint(
        session=None, index=index, batch_size=200
    )
    assert first.corpus_sha == second.corpus_sha


@pytest.mark.asyncio
async def test_swapping_one_node_for_another_moves_the_digest(loaded) -> None:
    """The property the whole field exists for.

    item_count cannot see this: 3 nodes before, 3 nodes after. Only membership can, and
    'the corpus did not move during the run' is exactly the claim P10 gate 5 makes.
    """
    index = _FakeIndex(item_count=3)
    loaded["rows"] = _rows("a", "b", "c")
    before = await corpus_module.read_corpus_fingerprint(
        session=None, index=index, batch_size=200
    )
    loaded["rows"] = _rows("a", "b", "d")
    after = await corpus_module.read_corpus_fingerprint(
        session=None, index=index, batch_size=200
    )

    assert before.item_count == after.item_count == 3
    assert before.corpus_sha != after.corpus_sha


@pytest.mark.asyncio
async def test_an_empty_corpus_still_produces_a_digest(loaded) -> None:
    """An empty corpus must be REPORTABLE, not indistinguishable from an unreachable one.

    The gate reads item_count for emptiness; the sha must not raise on the way there.
    """
    loaded["rows"] = []
    fingerprint = await corpus_module.read_corpus_fingerprint(
        session=None, index=_FakeIndex(item_count=0), batch_size=200
    )
    assert fingerprint.item_count == 0
    assert fingerprint.corpus_sha
