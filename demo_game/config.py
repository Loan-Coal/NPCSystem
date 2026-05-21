"""
Module: config
Layer: demo_game (external client)
Purpose: Load demo game runtime configuration from .env.demo.
Dependencies: pydantic-settings
Used by: demo_game.client (via make demo), demo_game.graph_panel.fetcher
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class DemoConfig(BaseSettings):
    """Demo game runtime configuration.

    Loaded from .env.demo in the working directory. All fields have safe
    defaults so the game runs against localhost without a .env.demo file.
    """

    NPC_BASE_URL: str = "http://localhost:8000"
    NPC_API_KEY: str = "local_dev_secret_change_this_2026"
    DEMO_GRAPH_POLL_INTERVAL: int = 5
    # Stall-detection timeouts: far above expected worst-case latency.
    NPC_DIALOGUE_TIMEOUT_S: float = 120.0
    NPC_GRAPH_TIMEOUT_S: float = 15.0

    model_config = SettingsConfigDict(env_file=".env.demo", extra="ignore")


config = DemoConfig()
