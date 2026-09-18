"""
test_main_encoder_warmup.py - Unit tests for encoder boot warm-up wiring.

Asserts that lifespan calls get_encoder once with settings.EMBEDDING_MODEL when
EMBEDDING_WARMUP_ON_STARTUP=True, makes no call when False, and that an exception
from get_encoder does not propagate (boot continues degraded).

Does NOT: load the real SentenceTransformer model or perform any I/O.

Dependencies injected: monkeypatch fixture.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI

import npc_engine.main as main
import npc_engine.retrieval.embedding.sentence_encoder as sentence_encoder_mod
from npc_engine.config import Settings


# ---------------------------------------------------------------------------
# Stubs shared across tests
# ---------------------------------------------------------------------------


class _GraphDbStub:
    def __init__(self) -> None:
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
    def cache_clear(self) -> None:
        pass

    def __call__(self) -> dict:
        return {"schema_version": "1.0"}


class _RegistryLoaderStub:
    def cache_clear(self) -> None:
        pass

    def __call__(self):
        from types import SimpleNamespace

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
    async def ensure_constraints(self) -> None:
        pass

    async def cleanup_expired(self) -> int:
        return 0


class _RedisRuntimeStub:
    async def connect(self) -> None:
        pass

    async def close(self) -> None:
        pass


class _LlmProbeStub:
    async def health_check(self) -> bool:
        return True


class _ReconcilerStub:
    def __init__(self, **_: object) -> None:
        pass

    async def ensure_corpus_once(self):
        from npc_engine.schema.corpus_models import CorpusFingerprint, CorpusReport

        return CorpusReport(
            nodes_read=1,
            upserted=1,
            missing_embedding=0,
            reconcile_passes=1,
            fingerprint=CorpusFingerprint(
                item_count=1,
                embedding_model="all-MiniLM-L6-v2",
                embedding_dim=384,
                corpus_sha="deadbeef",
            ),
        )

    async def run_forever(self) -> None:
        await asyncio.sleep(3600)


def _lifespan_settings(**overrides: object) -> Settings:
    """Minimal Settings for lifespan tests — no LLM warm-up, no autopilot."""
    return Settings(
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        DISTRIBUTED_TICK_LEASE_ENABLED=False,
        EMBEDDING_RECONCILE_INTERVAL_SECONDS=30,
        LLM_WARMUP_ON_STARTUP=False,
        TICK_AUTOPILOT_ENABLED=False,
        **overrides,
    )


def _wire_lifespan(monkeypatch, *, encoder_warmup: bool, settings_overrides: dict | None = None) -> MagicMock:
    """Patch lifespan collaborators and return the get_encoder mock.

    Args:
        monkeypatch: pytest monkeypatch fixture.
        encoder_warmup: Value for EMBEDDING_WARMUP_ON_STARTUP.
        settings_overrides: Additional Settings overrides.

    Returns:
        MagicMock replacing sentence_encoder_mod.get_encoder.
    """
    overrides = {**(settings_overrides or {}), "EMBEDDING_WARMUP_ON_STARTUP": encoder_warmup}
    graph_db = _GraphDbStub()

    monkeypatch.setattr(main, "get_graph_db", lambda: graph_db)
    monkeypatch.setattr(main, "get_embedding_index", lambda: _EmbeddingIndexStub())
    monkeypatch.setattr(main, "get_game_schema", _SchemaLoaderStub())
    monkeypatch.setattr(main, "get_type_registry", _RegistryLoaderStub())
    monkeypatch.setattr(main, "get_idempotency_service", lambda: _IdempotencyServiceStub())
    monkeypatch.setattr(main, "get_redis_runtime", lambda: _RedisRuntimeStub())
    monkeypatch.setattr(main, "EmbeddingReconciler", _ReconcilerStub)
    monkeypatch.setattr(main, "set_trade_handler", lambda _: None)
    monkeypatch.setattr(main, "create_llm_client_for_engine", lambda **_: _LlmProbeStub())
    monkeypatch.setattr(main, "get_settings", lambda: _lifespan_settings(**overrides))

    mock_encoder = MagicMock()
    monkeypatch.setattr(sentence_encoder_mod, "get_encoder", mock_encoder)
    return mock_encoder


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_encoder_warmup_calls_get_encoder_with_model_name(monkeypatch) -> None:
    """lifespan calls get_encoder once with EMBEDDING_MODEL when warm-up is enabled."""
    mock_encoder = _wire_lifespan(monkeypatch, encoder_warmup=True)

    async with main.lifespan(FastAPI()):
        pass

    mock_encoder.assert_called_once_with("all-MiniLM-L6-v2")


@pytest.mark.asyncio
async def test_encoder_warmup_skipped_when_setting_is_false(monkeypatch) -> None:
    """lifespan does not call get_encoder when EMBEDDING_WARMUP_ON_STARTUP=False."""
    mock_encoder = _wire_lifespan(monkeypatch, encoder_warmup=False)

    async with main.lifespan(FastAPI()):
        pass

    mock_encoder.assert_not_called()


@pytest.mark.asyncio
async def test_encoder_warmup_exception_does_not_abort_boot(monkeypatch) -> None:
    """A failing get_encoder must not propagate — boot continues in degraded mode.

    The encoder IS called (EMBEDDING_WARMUP_ON_STARTUP=True), but the RuntimeError it
    raises is swallowed by warm_up_encoder so lifespan completes normally.
    """
    _wire_lifespan(monkeypatch, encoder_warmup=True)
    # Override the mock set by _wire_lifespan with one that raises, AFTER _wire_lifespan
    # has patched everything else so it runs last and takes effect.
    mock_encoder = MagicMock(side_effect=RuntimeError("torch load failed"))
    monkeypatch.setattr(sentence_encoder_mod, "get_encoder", mock_encoder)

    async with main.lifespan(FastAPI()):
        pass

    mock_encoder.assert_called_once_with("all-MiniLM-L6-v2")
