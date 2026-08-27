"""
test_main_reconciler_lifespan.py - Unit tests for reconciler startup and shutdown wiring.

Does NOT: validate graph query behavior.

Dependencies injected: monkeypatch fixture.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI

import npc_engine.main as main
from npc_engine.config import Settings
from npc_engine.schema.corpus_models import CorpusFingerprint, CorpusReport


class _GraphDbStub:
    def __init__(self):
        self.connected = False
        self.closed = False
        self._session = AsyncMock()

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    @asynccontextmanager
    async def get_session(self):
        yield self._session


class _SchemaLoaderStub:
    def __init__(self):
        self.cache_cleared = False
        self.called = False

    def cache_clear(self) -> None:
        self.cache_cleared = True

    def __call__(self):
        self.called = True
        return {"schema_version": "1.0"}


class _RegistryLoaderStub:
    def __init__(self):
        self.cache_cleared = False
        self.called = False

    def cache_clear(self) -> None:
        self.cache_cleared = True

    def __call__(self):
        from types import SimpleNamespace

        self.called = True
        return SimpleNamespace(
            schema_version="1.0",
            core_types={},
            custom_node_types={},
            custom_edge_types={},
        )


class _EmbeddingIndexStub:
    async def upsert(self, item_id: str, text: str, payload: dict) -> None:
        return None


class _IdempotencyServiceStub:
    def __init__(self):
        self.constraints_ensured = False

    async def ensure_constraints(self) -> None:
        self.constraints_ensured = True

    async def cleanup_expired(self) -> int:
        return 0


class _RedisRuntimeStub:
    def __init__(self):
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True


class _ReconcilerStub:
    def __init__(self, graph_db, embedding_index, interval_seconds: int, batch_size: int = 200, nodes_read: int = 51):
        self.graph_db = graph_db
        self.embedding_index = embedding_index
        self.interval_seconds = interval_seconds
        self.batch_size = batch_size
        self.started = False
        self.hydrated_before_start = None
        self._nodes_read = nodes_read

    async def ensure_corpus_once(self) -> CorpusReport:
        self.hydrated_before_start = self.started
        return CorpusReport(
            nodes_read=self._nodes_read,
            upserted=self._nodes_read,
            missing_embedding=0,
            reconcile_passes=2,
            fingerprint=CorpusFingerprint(
                item_count=self._nodes_read,
                embedding_model="all-MiniLM-L6-v2",
                embedding_dim=384,
                corpus_sha="deadbeef",
            ),
        )

    async def run_forever(self) -> None:
        self.started = True
        await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_lifespan_starts_reconciler_task(monkeypatch) -> None:
    graph_db = _GraphDbStub()
    schema_loader = _SchemaLoaderStub()
    registry_loader = _RegistryLoaderStub()
    idempotency_service = _IdempotencyServiceStub()
    redis_runtime = _RedisRuntimeStub()
    reconciler_instance = _ReconcilerStub(graph_db=graph_db, embedding_index=_EmbeddingIndexStub(), interval_seconds=30)

    monkeypatch.setattr(main, "get_graph_db", lambda: graph_db)
    monkeypatch.setattr(main, "get_embedding_index", lambda: _EmbeddingIndexStub())
    monkeypatch.setattr(main, "get_game_schema", schema_loader)
    monkeypatch.setattr(main, "get_type_registry", registry_loader)
    monkeypatch.setattr(main, "get_idempotency_service", lambda: idempotency_service)
    monkeypatch.setattr(main, "get_redis_runtime", lambda: redis_runtime)
    monkeypatch.setattr(main, "EmbeddingReconciler", lambda **_: reconciler_instance)
    monkeypatch.setattr(main, "set_trade_handler", lambda _: None)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            DISTRIBUTED_TICK_LEASE_ENABLED=False,
            EMBEDDING_RECONCILE_INTERVAL_SECONDS=30,
        ),
    )

    async with main.lifespan(FastAPI()):
        assert graph_db.connected is True
        await asyncio.sleep(0)
        assert reconciler_instance.started is True
        assert idempotency_service.constraints_ensured is True
        assert redis_runtime.connected is True


@pytest.mark.asyncio
async def test_lifespan_cancels_reconciler_task_on_shutdown(monkeypatch) -> None:
    graph_db = _GraphDbStub()
    schema_loader = _SchemaLoaderStub()
    registry_loader = _RegistryLoaderStub()
    idempotency_service = _IdempotencyServiceStub()
    redis_runtime = _RedisRuntimeStub()

    task_cancelled = {"value": False}

    class _ReconcilerCancelStub(_ReconcilerStub):
        async def run_forever(self) -> None:
            self.started = True
            try:
                await asyncio.sleep(3600)
            except asyncio.CancelledError:
                task_cancelled["value"] = True
                raise

    reconciler_instance = _ReconcilerCancelStub(
        graph_db=graph_db,
        embedding_index=_EmbeddingIndexStub(),
        interval_seconds=30,
    )

    monkeypatch.setattr(main, "get_graph_db", lambda: graph_db)
    monkeypatch.setattr(main, "get_embedding_index", lambda: _EmbeddingIndexStub())
    monkeypatch.setattr(main, "get_game_schema", schema_loader)
    monkeypatch.setattr(main, "get_type_registry", registry_loader)
    monkeypatch.setattr(main, "get_idempotency_service", lambda: idempotency_service)
    monkeypatch.setattr(main, "get_redis_runtime", lambda: redis_runtime)
    monkeypatch.setattr(main, "EmbeddingReconciler", lambda **_: reconciler_instance)
    monkeypatch.setattr(main, "set_trade_handler", lambda _: None)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            DISTRIBUTED_TICK_LEASE_ENABLED=False,
            EMBEDDING_RECONCILE_INTERVAL_SECONDS=30,
        ),
    )

    async with main.lifespan(FastAPI()):
        await asyncio.sleep(0)

    assert task_cancelled["value"] is True
    assert graph_db.closed is True
    assert redis_runtime.closed is True


@pytest.mark.asyncio
async def test_lifespan_closes_graph_db_when_startup_fails_after_connect(monkeypatch) -> None:
    graph_db = _GraphDbStub()
    schema_loader = _SchemaLoaderStub()
    registry_loader = _RegistryLoaderStub()
    idempotency_service = _IdempotencyServiceStub()
    redis_runtime = _RedisRuntimeStub()

    def _raise_embedding_index_error():
        raise RuntimeError("embedding index init failed")

    monkeypatch.setattr(main, "get_graph_db", lambda: graph_db)
    monkeypatch.setattr(main, "get_game_schema", schema_loader)
    monkeypatch.setattr(main, "get_type_registry", registry_loader)
    monkeypatch.setattr(main, "get_embedding_index", _raise_embedding_index_error)
    monkeypatch.setattr(main, "get_idempotency_service", lambda: idempotency_service)
    monkeypatch.setattr(main, "get_redis_runtime", lambda: redis_runtime)
    monkeypatch.setattr(main, "EmbeddingReconciler", _ReconcilerStub)
    monkeypatch.setattr(main, "set_trade_handler", lambda _: None)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            DISTRIBUTED_TICK_LEASE_ENABLED=False,
            EMBEDDING_RECONCILE_INTERVAL_SECONDS=30,
        ),
    )

    with pytest.raises(RuntimeError, match="embedding index init failed"):
        async with main.lifespan(FastAPI()):
            pass

    assert graph_db.connected is True
    assert graph_db.closed is True
    assert redis_runtime.connected is True
    assert redis_runtime.closed is True


# ---------------------------------------------------------------------------
# Boot hydration (DEC-208 Decision 3 and 4)
# ---------------------------------------------------------------------------


def _wire_lifespan(monkeypatch, *, reconciler, hydrate: bool):
    """Patch the lifespan's collaborators and return the graph-db stub."""
    graph_db = _GraphDbStub()
    monkeypatch.setattr(main, "get_graph_db", lambda: graph_db)
    monkeypatch.setattr(main, "get_embedding_index", lambda: _EmbeddingIndexStub())
    monkeypatch.setattr(main, "get_game_schema", _SchemaLoaderStub())
    monkeypatch.setattr(main, "get_type_registry", _RegistryLoaderStub())
    monkeypatch.setattr(main, "get_idempotency_service", lambda: _IdempotencyServiceStub())
    monkeypatch.setattr(main, "get_redis_runtime", lambda: _RedisRuntimeStub())
    monkeypatch.setattr(main, "EmbeddingReconciler", lambda **_: reconciler)
    monkeypatch.setattr(main, "set_trade_handler", lambda _: None)
    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: Settings(
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            DISTRIBUTED_TICK_LEASE_ENABLED=False,
            EMBEDDING_RECONCILE_INTERVAL_SECONDS=30,
            VECTOR_STORE_HYDRATE_ON_STARTUP=hydrate,
        ),
    )
    return graph_db


@pytest.mark.asyncio
async def test_boot_hydration_finishes_before_the_reconciler_task_starts(monkeypatch) -> None:
    """The corpus is populated by an AWAITED call, not by task-start ordering.

    ISSUE-211 was exactly this: the hydrator was specced to run before the only thing
    that writes embeddings, and the sequencing lived in a lifespan rather than in a
    function that returns a value.
    """
    reconciler = _ReconcilerStub(graph_db=None, embedding_index=_EmbeddingIndexStub(), interval_seconds=30)
    _wire_lifespan(monkeypatch, reconciler=reconciler, hydrate=True)

    async with main.lifespan(FastAPI()):
        await asyncio.sleep(0)

    assert reconciler.hydrated_before_start is False


@pytest.mark.asyncio
async def test_boot_hydration_is_skipped_when_the_flag_is_off(monkeypatch) -> None:
    """HYDRATE_ON_STARTUP=false is a legitimate posture, not a broken one (DEC-208 D3)."""
    reconciler = _ReconcilerStub(graph_db=None, embedding_index=_EmbeddingIndexStub(), interval_seconds=30)
    _wire_lifespan(monkeypatch, reconciler=reconciler, hydrate=False)

    async with main.lifespan(FastAPI()):
        await asyncio.sleep(0)

    assert reconciler.hydrated_before_start is None


@pytest.mark.asyncio
async def test_boot_hydration_that_reads_nothing_logs_at_error(monkeypatch) -> None:
    """A silent item_count of 0 costs a night of generation (DEC-208 D4)."""
    reconciler = _ReconcilerStub(
        graph_db=None, embedding_index=_EmbeddingIndexStub(), interval_seconds=30, nodes_read=0,
    )
    _wire_lifespan(monkeypatch, reconciler=reconciler, hydrate=True)

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _Capture(level=logging.ERROR)
    main._logger.addHandler(handler)
    try:
        async with main.lifespan(FastAPI()):
            await asyncio.sleep(0)
    finally:
        main._logger.removeHandler(handler)

    assert [r.getMessage() for r in records if r.levelno >= logging.ERROR
            and "boot_hydration_read_nothing" in r.getMessage()]
