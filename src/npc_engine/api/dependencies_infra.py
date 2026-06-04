"""
Module: dependencies_infra
Layer: api
Purpose: Singleton factory providers for infrastructure dependencies —
         graph DB, Redis, game schema, type registry, LLM configs.
         Zero cross-singleton deps; everything else builds on these.
Does NOT: create session-scoped or per-request dependencies.
Dependencies injected: Settings (via get_settings).
Used by: api.dependency_singletons (re-exporter), api.dependencies_stores,
         api.dependencies_engines, api.dependencies_advanced
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from npc_engine.cache.redis_runtime import RedisRuntime
from npc_engine.config import Settings, get_settings
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.engines.llm_runtime_config import get_config as get_engine_model_config_for
from npc_engine.graph.db import GraphDB
from npc_engine.schema.context_config_models import LLMConfig
from npc_engine.schema.llm_schema_loader import load_llm_config
from npc_engine.schema.schema_loader import load_game_schema
from npc_engine.schema.schema_models import SchemaConfig
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.type_registry.registry import build_type_registry


REGISTRY_SOURCES_SEPARATOR = ","

_llm_adapters_to_close: list = []

_T = TypeVar("_T")


def _register_adapter(adapter: _T) -> _T:
    """Register an LLM adapter for teardown and return it unchanged."""
    _llm_adapters_to_close.append(adapter)
    return adapter


async def close_registered_llm_adapters() -> None:
    """Close all registered LLM adapters; called from lifespan teardown."""
    for adapter in _llm_adapters_to_close:
        if hasattr(adapter, "close"):
            await adapter.close()
    _llm_adapters_to_close.clear()


@lru_cache
def get_graph_db() -> GraphDB:
    """Create singleton GraphDB connection manager.

    Returns:
        GraphDB instance configured from application settings.
    """
    settings = get_settings()
    return GraphDB(settings=settings)


@lru_cache
def get_redis_runtime() -> RedisRuntime:
    """Create optional Redis runtime manager for non-idempotency caches.

    Returns:
        RedisRuntime instance; connection is deferred until connect() is called.
    """
    return RedisRuntime(settings=get_settings())


@lru_cache
def get_game_schema() -> SchemaConfig:
    """Load singleton game schema from configured path.

    Returns:
        Parsed SchemaConfig loaded from the GAME_SCHEMA_PATH setting.
    """
    settings = get_settings()
    return load_game_schema(schema_path=settings.GAME_SCHEMA_PATH)


def _resolve_registry_extension_sources(*, settings: Settings) -> tuple[str, ...]:
    """Resolve comma-delimited registry extension source values relative to project root.

    Args:
        settings: Application settings.

    Returns:
        Tuple of resolved absolute path strings for each extension source.
    """
    configured_sources = settings.TYPE_REGISTRY_EXTENSION_SOURCES
    if not configured_sources:
        return tuple()

    project_root = Path(__file__).resolve().parent.parent
    resolved_sources: list[str] = []
    for source in configured_sources.split(REGISTRY_SOURCES_SEPARATOR):
        source_value = source.strip()
        if not source_value:
            continue
        source_path = Path(source_value)
        if source_path.is_absolute():
            resolved_sources.append(str(source_path))
            continue
        resolved_sources.append(str((project_root / source_path).resolve(strict=False)))
    return tuple(resolved_sources)


@lru_cache
def get_type_registry() -> TypeRegistry:
    """Build immutable type registry singleton from base schema and extension sources.

    Returns:
        Fully resolved TypeRegistry singleton.
    """
    settings = get_settings()
    return build_type_registry(
        base_schema=get_game_schema(),
        extension_sources=_resolve_registry_extension_sources(settings=settings),
    )


@lru_cache
def get_llm_config() -> LLMConfig:
    """Load typed LLM configuration for prompt policy settings.

    Returns:
        LLMConfig loaded from the LLM_CONFIG_PATH setting.
    """
    settings = get_settings()
    return load_llm_config(config_path=settings.LLM_CONFIG_PATH)


@lru_cache
def get_dialogue_engine_model_config() -> EngineModelConfig:
    """Load the per-engine LLM config for the dialogue engine.

    Returns:
        EngineModelConfig from engines/dialogue/llm_config.yaml.
    """
    return get_engine_model_config_for("dialogue")
