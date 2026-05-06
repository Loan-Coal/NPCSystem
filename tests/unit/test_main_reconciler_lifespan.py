"""
test_main_reconciler_lifespan.py - Unit tests for reconciler startup and shutdown wiring.

Does NOT: validate graph query behavior.

Dependencies injected: monkeypatch fixture.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import cast

import pytest
from fastapi import FastAPI

import npc_engine.main as main
from npc_engine.config import Settings


class _GraphDbStub:
    def __init__(self):
        self.connected = False
        self.closed = False

    async def connect(self) -> None:
        self.connected = True

    async def close(self) -> None:
        self.closed = True

    @asynccontextmanager
    async def get_session(self):
        yield cast(object, None)


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
    def __init__(self, graph_db, embedding_index, interval_seconds: int):
        self.graph_db = graph_db
        self.embedding_index = embedding_index
        self.interval_seconds = interval_seconds
        self.started = False

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
