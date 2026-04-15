"""
config.py - Defines application settings loaded from environment variables.

Does NOT: initialize runtime services or perform network I/O.

Dependencies injected: None.
"""

from functools import lru_cache
import os
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


@lru_cache
def get_settings() -> Settings:
    """Create settings from environment and .env file."""

    return Settings()  # type: ignore[call-arg]
