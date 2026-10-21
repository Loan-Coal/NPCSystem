"""
Module: client._social
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Social graph methods: pledges, reputation, gossip, and pending dialogue intents.
Dependencies: demo_game.client._base
Used by: demo_game.client
"""

from __future__ import annotations

from demo_game.client._base import EngineClientBase


class _SocialMixin(EngineClientBase):
    """Mixin providing pledge, reputation, gossip, and intent methods.

    Requires EngineClientBase (or compatible) in the MRO.
    """

    def post_pledge(
        self,
        pledger_id: str,
        pledgee_id: str,
        pledge_type: str,
        tick: int,
        severity: int = 50,
    ) -> dict:
        """Create a pledge from pledger_id to pledgee_id.

        Args:
            pledger_id: Character making the pledge.
            pledgee_id: Character or faction receiving the pledge.
            pledge_type: One of protect/serve/kill/marry/mentor/fealty/vendetta.
            tick: Current game tick.
            severity: Pledge severity 0–100 (default 50).

        Returns:
            API response dict.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/admin/pledges/characters/{pledger_id}",
            json={"pledgee_id": pledgee_id, "pledge_type": pledge_type, "tick": tick, "severity": severity},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/pledges/characters/{pledger_id}")
        return resp.json()

    def get_pledges_for_npc(self, npc_id: str) -> list[dict]:
        """Return active pledges where npc_id is the pledger.

        Args:
            npc_id: Character node ID.

        Returns:
            List of pledge dicts with pledgee_id, pledge_type, tick, status fields.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/admin/pledges/characters/{npc_id}",
            params={"active_only": True},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/admin/pledges/characters/{npc_id}")
        return resp.json().get("data", {}).get("pledges", [])

    def put_npc_reputation(
        self,
        character_id: str,
        faction_id: str,
        standing: int,
    ) -> dict:
        """Set a character's standing with a faction via a STANDS_WITH edge.

        Used by the P2.5 war-trigger UI.

        Args:
            character_id: Character node ID.
            faction_id: Faction node ID.
            standing: Standing value as integer (typically -100 to 100).

        Returns:
            Full API response dict.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            "/v1/graph/edges/STANDS_WITH",
            json={"src_id": character_id, "dst_id": faction_id,
                  "properties": {"standing": standing, "last_changed_at": "tick_0"}},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "POST /v1/graph/edges/STANDS_WITH")
        return resp.json()

    def adjust_npc_reputation(
        self,
        character_id: str,
        faction_id: str,
        delta: int,
        location_id: str,
        tick_id: int,
    ) -> dict:
        """Apply a standing delta and seed a gossip-propagatable reputation event.

        Calls POST /v1/admin/characters/{character_id}/reputation/{faction_id}/adjust
        with location_id and tick_id so a KNOWS_ABOUT edge is seeded for NPCs
        at location_id, making the standing change visible to the gossip engine.

        Args:
            character_id: Character node ID.
            faction_id: Faction node ID.
            delta: Standing delta (positive = gain).
            location_id: Location where the standing change occurred.
            tick_id: Current game tick.

        Returns:
            Full API response dict containing new standing.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/admin/characters/{character_id}/reputation/{faction_id}/adjust",
            json={"delta": delta, "location_id": location_id, "tick_id": tick_id},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(
            resp,
            f"POST /v1/admin/characters/{character_id}/reputation/{faction_id}/adjust",
        )
        return resp.json()

    def spread_rumor(
        self,
        target_npc_id: str,
        rumor_text: str,
        severity: int,
        tick_id: int,
    ) -> dict:
        """Inject a player-planted rumor into target_npc_id's KNOWS_ABOUT graph.

        Calls POST /v1/admin/gossip/spread.  On the next clock advance, the gossip
        engine propagates and distorts the rumor to co-located NPCs.

        Args:
            target_npc_id: NPC that immediately believes the planted rumor.
            rumor_text: The fabricated belief text (up to 500 chars).
            severity: How serious the rumor is (0–100).
            tick_id: Current game tick.

        Returns:
            Full API response dict containing event_id and npc_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            "/v1/admin/gossip/spread",
            json={
                "target_npc_id": target_npc_id,
                "rumor_text": rumor_text,
                "severity": severity,
                "tick_id": tick_id,
            },
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "POST /v1/admin/gossip/spread")
        return resp.json()

    def trace_rumor(self, event_id: str) -> dict:
        """Return the ordered NPC chain that holds a KNOWS_ABOUT edge to event_id.

        Calls GET /v1/admin/gossip/trace/{event_id}.  The chain is ordered by
        learned_at_tick ascending so the propagation path is visible.

        Args:
            event_id: ID of the fabricated Event node to trace.

        Returns:
            Full API response dict containing event_id and chain list.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/admin/gossip/trace/{event_id}",
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/admin/gossip/trace/{event_id}")
        return resp.json()

    def correct_rumor(self, npc_id: str, event_id: str) -> dict:
        """Mark one NPC's belief in a fabricated event as corrected.

        Calls POST /v1/admin/gossip/correct.  After this call the NPC's
        KNOWS_ABOUT edge has knowledge_state='corrected' and is excluded
        from their dialogue context.  Downstream NPCs are unaffected.

        Args:
            npc_id: NPC whose belief should be corrected.
            event_id: ID of the fabricated Event node.

        Returns:
            Full API response dict containing npc_id, event_id, and corrected flag.

        Raises:
            EngineClientError: On any 4xx or 5xx response (including 404 if the
                edge does not exist).
        """
        resp = self._client.post(
            "/v1/admin/gossip/correct",
            json={"npc_id": npc_id, "event_id": event_id},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "POST /v1/admin/gossip/correct")
        return resp.json()

    def get_pending_intents(self, player_id: str) -> list[dict]:
        """Fetch and consume pending NPC-initiated dialogue intents for a player.

        Calls GET /v1/dialogue/pending. The endpoint is destructive: each call
        marks returned intents as delivered; do not call concurrently.

        Args:
            player_id: Character ID of the player to fetch intents for.

        Returns:
            List of ConversationIntentResponse dicts ordered by score DESC.
            Empty list when no intents are pending.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            "/v1/dialogue/pending",
            params={"player_id": player_id},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "GET /v1/dialogue/pending")
        return resp.json()
