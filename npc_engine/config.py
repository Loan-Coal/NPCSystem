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
    LLM_CONFIG_PATH: str = "config/llm_config.yaml"

    IDEMPOTENCY_ENFORCE_HEADER: bool = False
    IDEMPOTENCY_HEADER_NAME: str = "X-Idempotency-Key"
    IDEMPOTENCY_PENDING_TIMEOUT_SECONDS: int = 30
    IDEMPOTENCY_RETENTION_HOURS: int = 24
    IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS: int = 3600

    REDIS_ENABLED: bool = False
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CONNECT_TIMEOUT_SECONDS: float = 1.0

    LLM_BACKEND: Literal["mistral7b", "llama8b", "ollama", "mock"] = "mock"
    LLM_TIMEOUT_SECONDS: float = 10.0
    LLM_CACHE_ENABLED: bool = False
    LLM_FALLBACK_PATH: str = "data/fallback_responses.json"
    MISTRAL_API_URL: str | None = None
    LLAMA_API_URL: str | None = None
    OLLAMA_API_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mixtral:8x7b"

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

    MAX_CONCURRENT_TICKS: int = 20

    DISTRIBUTED_TICK_LEASE_ENABLED: bool = True
    TICK_SCHEDULER_ID: str = "main"
    TICK_LEASE_OWNER_ID: str = Field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    TICK_LEASE_TTL_SECONDS: int = 30

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_LLM_PROMPTS: bool = False
    ENV: Literal["dev", "staging", "prod"] = "dev"
    GOSSIP_RNG_SEED: int | None = None
    EVENT_RNG_SEED: int | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @field_validator("API_KEY_SECRET")
    @classmethod
    def validate_api_key_secret(cls, value: str) -> str:
        """Reject weak or placeholder API secrets."""

        stripped_value = value.strip()
        blocked_values = {"change-me", "replace_with_strong_secret", ""}
        if len(stripped_value) < 16 or stripped_value in blocked_values:
            raise ValueError("API_KEY_SECRET must be a non-placeholder secret with length >= 16")
        return stripped_value

    @field_validator("API_V1_PREFIX")
    @classmethod
    def validate_api_v1_prefix(cls, value: str) -> str:
        """Ensure API prefix is a stable absolute path segment."""

        prefix = value.strip()
        if not prefix.startswith("/"):
            raise ValueError("API_V1_PREFIX must start with '/'")
        if prefix == "/":
            raise ValueError("API_V1_PREFIX cannot be '/'")
        return prefix.rstrip("/")

    @field_validator("GAME_SCHEMA_PATH")
    @classmethod
    def validate_game_schema_path(cls, value: str) -> str:
        """Reject empty schema paths so startup can fail fast with clear errors."""

        path = value.strip()
        if not path:
            raise ValueError("GAME_SCHEMA_PATH cannot be empty")
        return path

    @field_validator("LLM_CONFIG_PATH")
    @classmethod
    def validate_llm_config_path(cls, value: str) -> str:
        """Reject empty llm config paths so startup can fail fast."""

        path = value.strip()
        if not path:
            raise ValueError("LLM_CONFIG_PATH cannot be empty")
        candidate = Path(path)
        if candidate.is_absolute():
            return str(candidate)

        project_root = Path(__file__).resolve().parent
        return str((project_root / candidate).resolve())

    @field_validator("IDEMPOTENCY_HEADER_NAME")
    @classmethod
    def validate_idempotency_header_name(cls, value: str) -> str:
        """Ensure idempotency header setting is non-empty."""

        header_name = value.strip()
        if not header_name:
            raise ValueError("IDEMPOTENCY_HEADER_NAME cannot be empty")
        return header_name

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, value: str) -> str:
        """Ensure Redis URL is non-empty when runtime integration is enabled."""

        redis_url = value.strip()
        if not redis_url:
            raise ValueError("REDIS_URL cannot be empty")
        return redis_url

    @field_validator("REDIS_CONNECT_TIMEOUT_SECONDS")
    @classmethod
    def validate_redis_connect_timeout_seconds(cls, value: float) -> float:
        """Ensure Redis connection timeout is positive."""

        if value <= 0:
            raise ValueError("REDIS_CONNECT_TIMEOUT_SECONDS must be greater than 0")
        return value

    @field_validator(
        "IDEMPOTENCY_PENDING_TIMEOUT_SECONDS",
        "IDEMPOTENCY_RETENTION_HOURS",
        "IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS",
    )
    @classmethod
    def validate_positive_idempotency_values(cls, value: int) -> int:
        """Ensure idempotency timing values are positive integers."""

        if value <= 0:
            raise ValueError("idempotency timing values must be greater than 0")
        return value

    @field_validator("EMBEDDING_RECONCILE_INTERVAL_SECONDS")
    @classmethod
    def validate_embedding_reconcile_interval_seconds(cls, value: int) -> int:
        """Ensure reconciler interval is a positive number of seconds."""

        if value <= 0:
            raise ValueError("EMBEDDING_RECONCILE_INTERVAL_SECONDS must be greater than 0")
        return value

    @field_validator("CURRENCY_MAX_PER_TRANSACTION", "CURRENCY_MAX_PER_SESSION")
    @classmethod
    def validate_currency_transfer_limits(cls, value: int) -> int:
        """Ensure configurable currency limits are positive integers."""

        if value <= 0:
            raise ValueError("currency limits must be greater than 0")
        return value


@lru_cache
def get_settings() -> Settings:
    """Create settings from environment and .env file."""

    return Settings()  # type: ignore[call-arg]
