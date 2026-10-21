"""
Module: client
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Synchronous HTTP client wrapping the NPC Engine REST API.
         Assembled from domain mixins; imports EngineClient and EngineClientError.
Dependencies: httpx, demo_game.constants
Used by: demo_game.seeds.seed, demo_game.runners, demo_game.beats, demo_game.branches
"""

from __future__ import annotations

from demo_game.client._base import EngineClientBase, EngineClientError
from demo_game.client._clock import _ClockMixin
from demo_game.client._graph import _GraphMixin
from demo_game.client._knowledge import _KnowledgeMixin
from demo_game.client._npc import _NpcMixin
from demo_game.client._quest import _QuestMixin
from demo_game.client._social import _SocialMixin
from demo_game.constants import DEMO_MAX_MESSAGE_CHARS


class EngineClient(
    _SocialMixin,
    _QuestMixin,
    _KnowledgeMixin,
    _ClockMixin,
    _NpcMixin,
    _GraphMixin,
    EngineClientBase,
):
    """Synchronous HTTP client for the NPC Engine API.

    All public methods raise EngineClientError on any non-2xx HTTP response.
    GET methods are safe to call from background threads. POST methods (dialogue,
    clock/advance) should be called from one thread at a time.

    Args:
        base_url: Engine base URL, e.g. http://localhost:8000.
        api_key: Bearer token for authentication.
        dialogue_timeout: Stall-detection timeout for LLM-backed calls, incl. clock/advance (s).
        graph_timeout: Stall-detection timeout for graph/clock read calls (seconds).
        _http_client: Injected httpx.Client for testing — do not use in production.
    """

    def post_dialogue(
        self,
        player_id: str,
        npc_id: str,
        player_message: str,
        location_id: str | None = None,
        session_id: str | None = None,
        explicit_node_ids: tuple[str, ...] = (),
    ) -> dict:
        """Submit one dialogue turn and return the engine's structured response.

        Args:
            player_id: ID of the player character.
            npc_id: ID of the NPC being addressed.
            player_message: What the player says.
            location_id: Optional current location ID.
            session_id: Optional session continuity token.
            explicit_node_ids: Graph node IDs to pin as high-priority context.

        Returns:
            Parsed response dict matching the DialogueResponse schema.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        body = {
            "player_id": player_id,
            "npc_id": npc_id,
            "player_message": player_message[:DEMO_MAX_MESSAGE_CHARS],
            "location_id": location_id,
            "session_id": session_id,
            "explicit_node_ids": list(explicit_node_ids),
        }
        resp = self._client.post("/v1/dialogue", json=body, timeout=self._dialogue_timeout)
        self._raise_for_status(resp, "POST /v1/dialogue")
        return resp.json()


__all__ = ["EngineClient", "EngineClientError"]
