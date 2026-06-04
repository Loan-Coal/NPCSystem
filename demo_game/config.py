"""
Module: config
Layer: demo_game (external client)
Purpose: Load demo game runtime configuration from .env.demo.
Dependencies: functools, pydantic-settings
Used by: demo_game.client (via make demo), demo_game.graph_panel.fetcher,
         demo_game.ui.game_window, demo_game.run, demo_game.scenarios
"""

from __future__ import annotations

import functools

from pydantic_settings import BaseSettings, SettingsConfigDict


class DemoConfig(BaseSettings):
    """Demo game runtime configuration.

    Loaded from .env.demo in the working directory. NPC_API_KEY has no
    default — the process raises KeyError at startup if it is absent from
    the environment or .env.demo (fail-fast per SEV-37).

    Set NPC_API_KEY in .env.demo or in the environment before running the demo.
    """

    NPC_BASE_URL: str = "http://localhost:8000"
    NPC_API_KEY: str  # no default — must be supplied via env / .env.demo
    DEMO_GRAPH_POLL_INTERVAL: int = 5
    # Fixed player identity for POST /v1/dialogue — no real player in demo.
    DEMO_PLAYER_ID: str = "player_demo"
    # Stall-detection timeouts: far above expected worst-case latency.
    NPC_DIALOGUE_TIMEOUT_S: float = 120.0
    NPC_GRAPH_TIMEOUT_S: float = 15.0

    model_config = SettingsConfigDict(env_file=".env.demo", extra="ignore")


@functools.lru_cache(maxsize=None)
def get_demo_config() -> DemoConfig:
    """Return the singleton DemoConfig, loaded lazily on first call.

    Raises:
        ValidationError: If NPC_API_KEY is not set in the environment or .env.demo.
    """
    return DemoConfig()
