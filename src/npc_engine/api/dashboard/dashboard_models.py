"""
Module: dashboard_models
Layer: api
Purpose: Read-only view models for the designer dashboard's Engines tab (S12.4) —
         a curated, non-secret projection of runtime cadence/cost settings.
Does NOT: expose secrets, mutate settings, or perform I/O.
Dependencies: pydantic, config.Settings.
Dependencies injected: Settings (via from_settings classmethod).
Used by: api.routes.system (engine config route).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from npc_engine.config import Settings


class DashboardConfigView(BaseModel):
    """Curated read-only projection of cadence and cost settings for the dashboard.

    Exposes only operational tuning knobs (tick cadence, LLM budget, world id,
    feature flags). No secrets, API keys, or connection strings are included.
    """

    world_id: str
    tick_autopilot_enabled: bool
    tick_interval_seconds: int
    tick_game_seconds_per_tick: int
    tick_llm_calls_per_minute_max: int
    gossip_tick_interval: int
    event_tick_interval: int
    chapter_tick_interval: int
    clique_formation_tick_interval: int
    max_concurrent_ticks: int
    consolidation_turn_threshold: int
    dialogue_stream_enabled: bool
    clock_mode: str
    tts_enabled: bool
    tts_backend: str

    model_config = ConfigDict(frozen=True)

    @classmethod
    def from_settings(cls, settings: Settings) -> DashboardConfigView:
        """Build a dashboard config view from application settings.

        Args:
            settings: Application settings singleton.
        Returns:
            DashboardConfigView populated with the curated tuning knobs.
        """
        return cls(
            world_id=settings.WORLD_ID,
            tick_autopilot_enabled=settings.TICK_AUTOPILOT_ENABLED,
            tick_interval_seconds=settings.TICK_INTERVAL_SECONDS,
            tick_game_seconds_per_tick=settings.TICK_GAME_SECONDS_PER_TICK,
            tick_llm_calls_per_minute_max=settings.TICK_LLM_CALLS_PER_MINUTE_MAX,
            gossip_tick_interval=settings.GOSSIP_TICK_INTERVAL,
            event_tick_interval=settings.EVENT_TICK_INTERVAL,
            chapter_tick_interval=settings.CHAPTER_TICK_INTERVAL,
            clique_formation_tick_interval=settings.CLIQUE_FORMATION_TICK_INTERVAL,
            max_concurrent_ticks=settings.MAX_CONCURRENT_TICKS,
            consolidation_turn_threshold=settings.CONSOLIDATION_TURN_THRESHOLD,
            dialogue_stream_enabled=settings.DIALOGUE_STREAM_ENABLED,
            clock_mode=settings.CLOCK_MODE,
            tts_enabled=settings.TTS_ENABLED,
            tts_backend=settings.TTS_BACKEND,
        )
