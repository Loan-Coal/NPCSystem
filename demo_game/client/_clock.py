"""
Module: client._clock
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Clock methods: advance ticks, read clock state, and fetch recent events.
Dependencies: demo_game.client._base
Used by: demo_game.client
"""

from __future__ import annotations

from demo_game.client._base import EngineClientBase


class _ClockMixin(EngineClientBase):
    """Mixin providing clock and observability methods.

    Requires EngineClientBase (or compatible) in the MRO.
    """

    def advance_clock(
        self,
        delta_ticks: int = 1,
        game_time_seconds: int = 1,
        advance_time_field: str | None = None,
    ) -> dict:
        """Advance the clock and run due engine ticks (LLM-backed: uses the dialogue timeout).

        Args:
            delta_ticks: Number of ticks to advance (1–1000).
            game_time_seconds: Simulated seconds per tick delta.
            advance_time_field: Optional structured time field to also advance
                (e.g. "day", "season"). Must be a valid WorldState time field.

        Returns:
            Parsed response dict with current_tick and optional world_state.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        body: dict = {"delta_ticks": delta_ticks, "game_time_seconds": game_time_seconds}
        if advance_time_field is not None:
            body["advance_time_field"] = advance_time_field
        resp = self._client.post("/v1/clock/advance", json=body, timeout=self._dialogue_timeout)
        self._raise_for_status(resp, "POST /v1/clock/advance")
        return resp.json()

    def get_clock_state(self) -> dict:
        """Return the current clock snapshot.

        Returns:
            Dict with current_tick, next_gossip_tick, next_event_tick fields.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get("/v1/clock/state", timeout=self._graph_timeout)
        self._raise_for_status(resp, "GET /v1/clock/state")
        return resp.json()

    def get_recent_events(self, limit: int = 20) -> list[dict]:
        """Return the most recent Event nodes ordered by tick descending.

        Args:
            limit: Maximum number of events to return (1–100).

        Returns:
            List of event dicts with event_id, event_type, label, severity,
            tick_id, location_id, src_character_id keys.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            "/v1/admin/system/events",
            params={"limit": limit},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "GET /v1/admin/system/events")
        return resp.json().get("data", [])
