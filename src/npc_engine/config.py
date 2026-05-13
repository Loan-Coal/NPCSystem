"""
config.py - Defines application settings loaded from environment variables.

Does NOT: initialize runtime services or perform network I/O.

Dependencies injected: None.
"""

from functools import lru_cache
import os
from pathlib import Path
import socket
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from npc_engine.config_validators import (
    check_api_key_secret,
    check_api_v1_prefix,
    check_currency_transfer_limit,
    check_embedding_reconcile_interval,
    check_game_schema_path,
    check_idempotency_header_name,
    check_llm_config_path,
    check_package_data_path,
    check_positive_idempotency_value,
    check_redis_connect_timeout,
    check_redis_url,
    normalize_extension_sources,
)

_PROJECT_ROOT = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Typed environment configuration for the NPC Engine."""

    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="password")

    API_KEY_SECRET: str
    API_KEY_GRAPH_WRITE: str | None = None
    API_KEY_GRAPH_ADMIN: str | None = None
    API_V1_PREFIX: str = "/v1"
    GAME_SCHEMA_PATH: str = "game_schema.yaml"
    TYPE_REGISTRY_EXTENSION_SOURCES: str = ""
    LLM_CONFIG_PATH: str = "config/llm_config.yaml"

    IDEMPOTENCY_ENFORCE_HEADER: bool = False
    IDEMPOTENCY_HEADER_NAME: str = "X-Idempotency-Key"
    IDEMPOTENCY_PENDING_TIMEOUT_SECONDS: int = 30
    IDEMPOTENCY_RETENTION_HOURS: int = 24
    IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS: int = 3600

    REDIS_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 1.0

    LLM_TIMEOUT_SECONDS: float = 10.0
    LLM_CACHE_ENABLED: bool = False
    LLM_FALLBACK_PATH: str = "data/fallback_responses.json"
    CANNED_RESPONSES_DIR: str = "prompts/canned"
    MISTRAL_API_URL: str | None = None
    LLAMA_API_URL: str | None = None
    OLLAMA_API_URL: str = "http://localhost:11434"

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    VECTOR_STORE_BACKEND: Literal["memory", "qdrant"] = "memory"
    QDRANT_URL: str | None = None
    EMBEDDING_REFRESH_ON_WRITE: bool = True
    EMBEDDING_RECONCILE_INTERVAL_SECONDS: int = 300
    PROMPT_TOKEN_BUDGET: int = 800
    RAG_TOP_K: int = 5

    DIALOGUE_SESSION_TURNS: int = 10
    DIALOGUE_SESSION_TTL: int = 300
    DIALOGUE_STREAM_ENABLED: bool = True

    REPUTATION_CONTEXT_THRESHOLD: int = 20

    GOSSIP_DISTORTION_BASE: float = 0.3
    GOSSIP_DISTORTION_MAX: float = 0.9
    GOSSIP_PERSONALITY_FIELDS_ENABLED: bool = True
    GOSSIP_TICK_INTERVAL: int = 10

    EVENT_POOL_PATH: str = "data/event_pool.json"
    EVENT_TICK_INTERVAL: int = 20

    MAX_RELATION_DELTA_PER_TURN: int = 15
    MAX_RELATION_DELTA_PER_WINDOW: int = 40
    RELATION_WINDOW_SIZE: int = 10
    CURRENCY_MAX_PER_TRANSACTION: int = 1000
    CURRENCY_MAX_PER_SESSION: int = 5000

    CLOCK_MODE: Literal["realtime", "game_driven"] = "realtime"

    CONSOLIDATION_TURN_THRESHOLD: int = 10
    CONSOLIDATION_CLEAR_TURNS: bool = False

    MAX_CONCURRENT_TICKS: int = 20

    DISTRIBUTED_TICK_LEASE_ENABLED: bool = True
    TICK_SCHEDULER_ID: str = "main"
    TICK_LEASE_OWNER_ID: str = Field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    TICK_LEASE_TTL_SECONDS: int = 30

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_SECOND: float = Field(default=50.0, gt=0)
    RATE_LIMIT_BURST_SIZE: int = Field(default=100, gt=0)

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_LLM_PROMPTS: bool = False
    ENV: Literal["dev", "staging", "prod"] = "dev"
    GOSSIP_RNG_SEED: int | None = None
    EVENT_RNG_SEED: int | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    @field_validator("API_KEY_SECRET")
    @classmethod
    def validate_api_key_secret(cls, value: str) -> str:
        """Delegate to check_api_key_secret."""
        return check_api_key_secret(value)

    @field_validator("API_V1_PREFIX")
    @classmethod
    def validate_api_v1_prefix(cls, value: str) -> str:
        """Delegate to check_api_v1_prefix."""
        return check_api_v1_prefix(value)

    @field_validator("GAME_SCHEMA_PATH")
    @classmethod
    def validate_game_schema_path(cls, value: str) -> str:
        """Delegate to check_game_schema_path."""
        return check_game_schema_path(value, _PROJECT_ROOT)

    @field_validator("TYPE_REGISTRY_EXTENSION_SOURCES")
    @classmethod
    def normalize_type_registry_extension_sources(cls, value: str) -> str:
        """Delegate to normalize_extension_sources."""
        return normalize_extension_sources(value)

    @field_validator("LLM_CONFIG_PATH")
    @classmethod
    def validate_llm_config_path(cls, value: str) -> str:
        """Delegate to check_llm_config_path."""
        return check_llm_config_path(value, _PROJECT_ROOT)

    @field_validator("IDEMPOTENCY_HEADER_NAME")
    @classmethod
    def validate_idempotency_header_name(cls, value: str) -> str:
        """Delegate to check_idempotency_header_name."""
        return check_idempotency_header_name(value)

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        """Delegate to check_redis_url."""
        return check_redis_url(value)

    @field_validator("REDIS_CONNECT_TIMEOUT_SECONDS")
    @classmethod
    def validate_redis_connect_timeout_seconds(cls, value: float) -> float:
        """Delegate to check_redis_connect_timeout."""
        return check_redis_connect_timeout(value)

    @field_validator(
        "IDEMPOTENCY_PENDING_TIMEOUT_SECONDS",
        "IDEMPOTENCY_RETENTION_HOURS",
        "IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS",
    )
    @classmethod
    def validate_positive_idempotency_values(cls, value: int) -> int:
        """Delegate to check_positive_idempotency_value."""
        return check_positive_idempotency_value(value)

    @field_validator("EMBEDDING_RECONCILE_INTERVAL_SECONDS")
    @classmethod
    def validate_embedding_reconcile_interval_seconds(cls, value: int) -> int:
        """Delegate to check_embedding_reconcile_interval."""
        return check_embedding_reconcile_interval(value)

    @field_validator("CURRENCY_MAX_PER_TRANSACTION", "CURRENCY_MAX_PER_SESSION")
    @classmethod
    def validate_currency_transfer_limits(cls, value: int) -> int:
        """Delegate to check_currency_transfer_limit."""
        return check_currency_transfer_limit(value)

    @field_validator("LLM_FALLBACK_PATH")
    @classmethod
    def validate_llm_fallback_path(cls, value: str) -> str:
        """Delegate to check_package_data_path."""
        return check_package_data_path(value, _PROJECT_ROOT)

    @field_validator("EVENT_POOL_PATH")
    @classmethod
    def validate_event_pool_path(cls, value: str) -> str:
        """Delegate to check_package_data_path."""
        return check_package_data_path(value, _PROJECT_ROOT)


@lru_cache
def get_settings() -> Settings:
    """Create and cache the Settings instance from environment and .env file.

    Returns:
        Singleton Settings instance populated from environment variables.
    """
    return Settings()  # type: ignore[call-arg]
