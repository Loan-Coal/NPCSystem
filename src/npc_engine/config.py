"""
config.py - Defines application settings loaded from environment variables.
Layer: unknown
Purpose: (auto-detected — review)

Does NOT: initialize runtime services or perform network I/O.

Dependencies injected: None.
"""

from functools import lru_cache
import os
from pathlib import Path
import socket
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from npc_engine.config_validators import (
    check_api_key_secret,
    check_api_v1_prefix,
    check_currency_transfer_limit,
    check_embedding_reconcile_interval,
    check_game_schema_path,
    check_idempotency_header_name,
    check_llm_config_path,
    check_neo4j_password,
    check_package_data_path,
    check_positive_idempotency_value,
    check_redis_connect_timeout,
    check_redis_url,
    normalize_extension_sources,
)

_PROJECT_ROOT = Path(__file__).resolve().parent

# Module-level constants so request models can import them at field-definition time
# without calling get_settings() (which would trigger env loading during model definition).
MAX_PLAYER_MESSAGE_CHARS: int = 1000
MAX_DELTA_TICKS: int = 1000

# GraphRAG composite-score weights (must sum to 1.0).
# Extracted from graph_rag.py to allow test-time verification and future tuning.
RAG_RELEVANCE_WEIGHT: float = 0.5   # vector-similarity component weight
RAG_TRUST_WEIGHT: float = 0.3       # graph edge-weight (trust/confidence) component weight
RAG_RECENCY_WEIGHT: float = 0.2     # temporal recency component weight

# Recency decay thresholds.
RAG_RECENCY_DAYS_SOFT: float = 365.0   # game-time: full decay over this many game-days
RAG_RECENCY_DAYS_HARD: float = 72.0    # wall-clock: full decay over this many real hours


class Settings(BaseSettings):
    """Typed environment configuration for the NPC Engine."""

    NEO4J_URI: str = Field(default="bolt://localhost:7687")
    NEO4J_USER: str = Field(default="neo4j")
    NEO4J_PASSWORD: str = Field(default="password")

    API_KEY_SECRET: str
    API_KEY_GRAPH_WRITE: str | None = None
    API_KEY_GRAPH_ADMIN: str | None = None
    API_V1_PREFIX: str = "/v1"
    # Build identifier surfaced on GET /health so a stale image is detectable
    # (L9-05). Baked at image build time via the Dockerfile BUILD_SHA arg; "dev"
    # for local/non-container runs.
    BUILD_SHA: str = "dev"
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
    # Must match OLLAMA_CONTEXT_LENGTH passed to `ollama serve`.
    # On RTX 5070 Ti Laptop (9.5 GiB available): 4096 fits cleanly in VRAM.
    # 6144 is usable with a small KV-cache spill (~330 MB to shared memory).
    # Set OLLAMA_CONTEXT_LENGTH=<value> in .env and restart both ollama and the engine.
    OLLAMA_CONTEXT_LENGTH: int = 4096

    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    VECTOR_STORE_BACKEND: Literal["memory", "qdrant"] = "memory"
    QDRANT_URL: str | None = None
    EMBEDDING_REFRESH_ON_WRITE: bool = True
    EMBEDDING_RECONCILE_INTERVAL_SECONDS: int = 300
    # Derived from OLLAMA_CONTEXT_LENGTH. Reserve 1200 tokens for system prompt,
    # prompt headers (NPC_ID, VOICE_DESCRIPTOR, PLAYER_MESSAGE), and model output.
    # Override via PROMPT_TOKEN_BUDGET in .env only if you need a non-standard split.
    PROMPT_TOKEN_BUDGET: int = 0
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

    # Canonical world-state node id (DEC-022). Must match what the seeders write
    # ("world"); the prior "world_demo" default silently desynced the engine from
    # seeded state (L1-07 / SEV-13 config-layer gap).
    WORLD_ID: str = "world"

    TTS_ENABLED: bool = False
    TTS_BACKEND: Literal["piper", "mock"] = "piper"
    PIPER_BASE_URL: str = "http://localhost:5000"
    TTS_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)

    CLOCK_MODE: Literal["realtime", "game_driven"] = "realtime"

    CONSOLIDATION_TURN_THRESHOLD: int = 10
    CONSOLIDATION_CLEAR_TURNS: bool = False

    STRUCTURED_OUTPUT_TEMPERATURE: float = 0.1

    MAX_CONCURRENT_TICKS: int = 20
    MAX_DELTA_TICKS: int = MAX_DELTA_TICKS

    DISTRIBUTED_TICK_LEASE_ENABLED: bool = True
    TICK_SCHEDULER_ID: str = "main"
    TICK_LEASE_OWNER_ID: str = Field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    TICK_LEASE_TTL_SECONDS: int = 30
    TICK_AUTOPILOT_ENABLED: bool = True
    TICK_INTERVAL_SECONDS: int = 10
    TICK_GAME_SECONDS_PER_TICK: int = 1
    TICK_LLM_CALLS_PER_MINUTE_MAX: int = 6
    CHAPTER_TICK_INTERVAL: int = 1

    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS_PER_SECOND: float = Field(default=50.0, gt=0)
    RATE_LIMIT_BURST_SIZE: int = Field(default=100, gt=0)

    WITNESSED_MAX_PER_EVENT: int = 10
    CLIQUE_FORMATION_TICK_INTERVAL: int = 10
    TREATY_LLM_EVAL_ENABLED: bool = False
    CROSS_ENCODER_ENABLED: bool = False
    GRAPH_RAG_ENABLED: bool = False
    RUMOR_DISTORTION_THRESHOLD: int = 50
    RUMOR_EMOTION_SEVERITY_THRESHOLD: int = 50

    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_LLM_PROMPTS: bool = False
    ENV: Literal["dev", "staging", "prod"] = "dev"
    GOSSIP_RNG_SEED: int | None = None
    EVENT_RNG_SEED: int | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)

    @model_validator(mode="after")
    def _derive_prompt_token_budget(self) -> "Settings":
        """Derive PROMPT_TOKEN_BUDGET from OLLAMA_CONTEXT_LENGTH when not explicitly set.

        Reserves 1200 tokens for the system prompt, prompt headers, and model output.
        Override PROMPT_TOKEN_BUDGET in .env only for non-standard splits.
        """
        if self.PROMPT_TOKEN_BUDGET == 0:
            object.__setattr__(self, "PROMPT_TOKEN_BUDGET", self.OLLAMA_CONTEXT_LENGTH - 1200)
        return self

    @model_validator(mode="after")
    def _validate_neo4j_password(self) -> "Settings":
        """Reject the default NEO4J_PASSWORD in staging/prod (SEV-21)."""
        check_neo4j_password(self.NEO4J_PASSWORD, env=self.ENV)
        return self

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
