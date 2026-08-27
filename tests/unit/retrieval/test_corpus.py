"""
test_corpus.py - Unit tests for ensure_corpus, the vector store's only insert path.

Pins DEC-208: one owner, reconcile UNTIL DRY, no re-encode, and a report that cannot
say "fine" about an empty corpus.

Does NOT: connect to Neo4j or run a sentence encoder.

Dependencies injected: monkeypatched load queries, fake store, fake reconciler.
"""

import pytest

from npc_engine.retrieval.embedding import corpus as corpus_module
from npc_engine.retrieval.embedding.corpus import MAX_RECONCILE_PASSES, ensure_corpus

_MODEL = "all-MiniLM-L6-v2"


class FakeStore:
    """Records what was written, so a re-encode would be visible as a changed vector."""

    def __init__(self) -> None:
        self.entries: dict[str, dict] = {}

    async def upsert_vector(self, item_id, vector, payload) -> None:
        self.entries[item_id] = {"vector": list(vector), "payload": dict(payload)}

    async def count(self) -> int:
        return len(self.entries)

    @property
    def model_name(self) -> str:
        return _MODEL


class FakeReconciler:
    """Returns a scripted sequence of per-pass processed counts."""

    def __init__(self, processed_per_pass: list[int]) -> None:
        self._script = list(processed_per_pass)
        self.passes = 0

    async def reconcile_in_session(self, session) -> dict[str, int]:
        self.passes += 1
        processed = self._script.pop(0) if self._script else 0
        return {"processed": processed, "failed": 0}


def _row(node_id: str, *, kind: str = "Event", dim: int = 4) -> dict:
    return {
        "node_id": node_id,
        "kind": kind,
        "embedding": [0.5] * dim,
        "embedding_model": _MODEL,
        "embedding_dim": dim,
        "payload": {"id": node_id, "summary": f"summary of {node_id}", "severity": None},
    }


def _patch_load(monkeypatch, rows: list[dict], *, missing: int = 0) -> None:
    async def fake_select(session, *, skip: int, limit: int):
        return rows[skip: skip + limit]

    async def fake_missing(session):
        return missing

    monkeypatch.setattr(corpus_module, "select_embedded_nodes", fake_select)
    monkeypatch.setattr(corpus_module, "count_nodes_missing_embedding", fake_missing)


@pytest.mark.asyncio
async def test_ensure_corpus_upserts_every_embedded_node_into_the_vector_store(monkeypatch) -> None:
    """The deliverable. Nothing in src/ had ever written the vector store before this."""
    rows = [_row(f"evt_{index}") for index in range(5)]
    _patch_load(monkeypatch, rows)
    store = FakeStore()

    report = await ensure_corpus(None, store, FakeReconciler([0]), batch_size=2)

    assert set(store.entries) == {f"evt_{index}" for index in range(5)}
    assert report.nodes_read == 5
    assert report.upserted == 5
    assert report.fingerprint.item_count == 5


@pytest.mark.asyncio
async def test_ensure_corpus_reconciles_until_dry_not_one_batch(monkeypatch) -> None:
    """select_stale_nodes has no ORDER BY and caps at batch_size.

    One sweep therefore leaves a partial corpus in undefined row order the moment a world
    exceeds the batch. 51 embeddable nodes fit today; the demo world will not.
    """
    _patch_load(monkeypatch, [_row("evt_1")])
    reconciler = FakeReconciler([200, 200, 17, 0])

    report = await ensure_corpus(None, FakeStore(), reconciler, batch_size=200)

    assert reconciler.passes == 4
    assert report.reconcile_passes == 4


@pytest.mark.asyncio
async def test_ensure_corpus_stores_the_persisted_vector_verbatim(monkeypatch) -> None:
    """No re-encode: two encode paths that can disagree are a silent-divergence factory."""
    row = _row("evt_1")
    row["embedding"] = [0.1, 0.2, 0.3, 0.4]
    _patch_load(monkeypatch, [row])
    store = FakeStore()

    await ensure_corpus(None, store, FakeReconciler([0]), batch_size=10)

    assert store.entries["evt_1"]["vector"] == [0.1, 0.2, 0.3, 0.4]


@pytest.mark.asyncio
async def test_the_upserted_payload_carries_no_embedding_and_no_nulls(monkeypatch) -> None:
    """A payload is prompt-bound. A 384-float vector in it is 384 floats in the prompt."""
    _patch_load(monkeypatch, [_row("evt_1")])
    store = FakeStore()

    await ensure_corpus(None, store, FakeReconciler([0]), batch_size=10)

    payload = store.entries["evt_1"]["payload"]
    assert "embedding" not in payload
    assert "severity" not in payload, "null fields must not be carried into the prompt"
    assert payload["summary"] == "summary of evt_1"


@pytest.mark.asyncio
async def test_an_empty_corpus_reports_zero_rather_than_reporting_nothing(monkeypatch) -> None:
    """HYDRATE_ON_STARTUP=true with nodes_read == 0 must be visible, not silent (DEC-208 D4)."""
    _patch_load(monkeypatch, [], missing=51)
    store = FakeStore()

    report = await ensure_corpus(None, store, FakeReconciler([0]), batch_size=10)

    assert report.nodes_read == 0
    assert report.upserted == 0
    assert report.missing_embedding == 51
    assert report.fingerprint.item_count == 0


@pytest.mark.asyncio
async def test_the_fingerprint_changes_when_corpus_membership_changes(monkeypatch) -> None:
    """Two arms are provably comparable, or provably not (DEC-210 D2)."""
    _patch_load(monkeypatch, [_row("evt_1"), _row("evt_2")])
    first = await ensure_corpus(None, FakeStore(), FakeReconciler([0]), batch_size=10)

    _patch_load(monkeypatch, [_row("evt_1"), _row("evt_2"), _row("evt_3")])
    second = await ensure_corpus(None, FakeStore(), FakeReconciler([0]), batch_size=10)

    assert first.fingerprint.corpus_sha != second.fingerprint.corpus_sha


@pytest.mark.asyncio
async def test_the_fingerprint_is_stable_across_row_order(monkeypatch) -> None:
    _patch_load(monkeypatch, [_row("evt_1"), _row("evt_2")])
    forward = await ensure_corpus(None, FakeStore(), FakeReconciler([0]), batch_size=10)

    _patch_load(monkeypatch, [_row("evt_2"), _row("evt_1")])
    reversed_rows = await ensure_corpus(None, FakeStore(), FakeReconciler([0]), batch_size=10)

    assert forward.fingerprint.corpus_sha == reversed_rows.fingerprint.corpus_sha


@pytest.mark.asyncio
async def test_reconcile_until_dry_is_bounded(monkeypatch) -> None:
    """A node that cannot clear its own staleness must not hang boot forever."""
    _patch_load(monkeypatch, [])
    reconciler = FakeReconciler([1] * (MAX_RECONCILE_PASSES + 50))

    report = await ensure_corpus(None, FakeStore(), reconciler, batch_size=10)

    assert report.reconcile_passes == MAX_RECONCILE_PASSES


@pytest.mark.asyncio
async def test_ensure_corpus_rejects_a_non_positive_batch_size() -> None:
    with pytest.raises(ValueError):
        await ensure_corpus(None, FakeStore(), FakeReconciler([0]), batch_size=0)
