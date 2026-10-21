"""
Module: client._npc
Layer: demo_game (external client — zero npc_engine imports)
Purpose: NPC state reads: reputation, emotion snapshot, and relationship standing.
Dependencies: demo_game.client._base
Used by: demo_game.client
"""

from __future__ import annotations

from demo_game.client._base import EngineClientBase


class _NpcMixin(EngineClientBase):
    """Mixin providing NPC state read methods.

    Requires EngineClientBase (or compatible) in the MRO.
    """

    def get_npc_reputation(self, character_id: str) -> list[dict]:
        """Return all faction reputation records for a character.

        Args:
            character_id: Character node ID.

        Returns:
            List of dicts each containing faction_id and standing fields.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/graph/characters/{character_id}/reputation",
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/graph/characters/{character_id}/reputation")
        return resp.json().get("data", [])

    def get_npc_emotion(self, npc_id: str) -> dict | None:
        """Return the current in-memory emotion snapshot for an NPC.

        Args:
            npc_id: NPC character ID.

        Returns:
            Dict with npc_id, label, valence, arousal, updated_at fields,
            or None if the NPC is not found (HTTP 404).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(f"/v1/npc/{npc_id}/emotion", timeout=self._graph_timeout)
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"GET /v1/npc/{npc_id}/emotion")
        return resp.json()

    def get_npc_relationship(self, npc_id: str, other_id: str) -> dict | None:
        """Fetch RELATES_TO edge properties between two characters via EXP-50 route.

        Args:
            npc_id: Source character node ID.
            other_id: Target character node ID.

        Returns:
            Dict with trust, fear, affection, interaction_count fields, or None on 404.

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/npc/{npc_id}/relationship/{other_id}",
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"GET /v1/npc/{npc_id}/relationship/{other_id}")
        return resp.json().get("data")
