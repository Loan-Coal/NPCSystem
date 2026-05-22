"""
Module: client
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Synchronous HTTP client wrapping the NPC Engine REST API.
Dependencies: httpx
Used by: demo_game.ui.game_window, demo_game.graph_panel.fetcher, demo_game.seed
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx


class EngineClientError(Exception):
    """Raised on any 4xx or 5xx response from the NPC Engine."""


class EngineClient:
    """Synchronous HTTP client for the NPC Engine API.

    All public methods raise EngineClientError on any non-2xx HTTP response.
    GET methods are safe to call from background threads. POST methods (dialogue,
    clock/advance) should be called from one thread at a time.

    Args:
        base_url: Engine base URL, e.g. http://localhost:8000.
        api_key: Bearer token for authentication.
        dialogue_timeout: Stall-detection timeout for LLM-backed calls (seconds).
        graph_timeout: Stall-detection timeout for graph/clock read calls (seconds).
        _http_client: Injected httpx.Client for testing — do not use in production.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        dialogue_timeout: float = 120.0,
        graph_timeout: float = 15.0,
        *,
        _http_client: httpx.Client | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._dialogue_timeout = dialogue_timeout
        self._graph_timeout = graph_timeout
        self._client = _http_client or httpx.Client(
            base_url=self._base_url,
            headers={"Authorization": f"Bearer {self._api_key}"},
        )

    # ------------------------------------------------------------------
    # Dialogue
    # ------------------------------------------------------------------

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
            "player_message": player_message,
            "location_id": location_id,
            "session_id": session_id,
            "explicit_node_ids": list(explicit_node_ids),
        }
        resp = self._client.post("/v1/dialogue", json=body, timeout=self._dialogue_timeout)
        self._raise_for_status(resp, "POST /v1/dialogue")
        return resp.json()

    # ------------------------------------------------------------------
    # Graph reads
    # ------------------------------------------------------------------

    def get_graph_nodes(
        self,
        node_type: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Return a paginated list of nodes for a registered type.

        Args:
            node_type: Registered node type, e.g. "Character", "Location", "Event".
            limit: Maximum number of results.
            offset: Pagination offset.

        Returns:
            List of node property dicts from the response data field.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/graph/nodes/{node_type}",
            params={"limit": limit, "offset": offset},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/graph/nodes/{node_type}")
        return resp.json().get("data", [])

    def get_graph_edges(
        self,
        edge_type: str,
        limit: int = 100,
        offset: int = 0,
        src_id: str | None = None,
        dst_id: str | None = None,
    ) -> list[dict]:
        """Return edges of a registered type with optional source/destination filter.

        Args:
            edge_type: Registered edge type, e.g. "KNOWS_ABOUT", "STANDS_WITH".
            limit: Maximum number of results.
            offset: Pagination offset.
            src_id: Optional filter by source node ID.
            dst_id: Optional filter by destination node ID.

        Returns:
            List of edge property dicts from the response data field.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        params: dict = {"limit": limit, "offset": offset}
        if src_id is not None:
            params["src_id"] = src_id
        if dst_id is not None:
            params["dst_id"] = dst_id
        resp = self._client.get(
            f"/v1/graph/edges/{edge_type}",
            params=params,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/graph/edges/{edge_type}")
        return resp.json().get("data", [])

    def get_world_state(self) -> dict | None:
        """Return the current WorldState node, or None if world has not been seeded.

        The world_state endpoint returns a paginated list; this method fetches
        limit=1 and returns the first item.

        Returns:
            WorldState property dict, or None if no world state exists yet.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            "/v1/graph/nodes/world_state",
            params={"limit": 1, "offset": 0},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "GET /v1/graph/nodes/world_state")
        items = resp.json().get("data", [])
        return items[0] if items else None

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

    # ------------------------------------------------------------------
    # NPC state
    # ------------------------------------------------------------------

    def get_npc_state(self, npc_id: str) -> dict:
        """Return the NPC state snapshot (character, relations, events).

        Args:
            npc_id: NPC character ID.

        Returns:
            NPCState dict with character, relations, and events fields.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(f"/v1/npc/{npc_id}/state", timeout=self._graph_timeout)
        self._raise_for_status(resp, f"GET /v1/npc/{npc_id}/state")
        return resp.json()

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def advance_clock(
        self,
        delta_ticks: int = 1,
        game_time_seconds: int = 1,
        advance_time_field: str | None = None,
    ) -> dict:
        """Advance the game clock and trigger all due engine ticks.

        Args:
            delta_ticks: Number of ticks to advance (1–200).
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
        resp = self._client.post("/v1/clock/advance", json=body, timeout=self._graph_timeout)
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

    # ------------------------------------------------------------------
    # Graph single-item reads (return None on 404)
    # ------------------------------------------------------------------

    def get_node(self, node_type: str, node_id: str) -> dict | None:
        """Return one node by type and id, or None if it does not exist.

        Args:
            node_type: Registered node type, e.g. "Location", "Character".
            node_id: Node ID to fetch.

        Returns:
            Node property dict, or None if the node was not found (HTTP 404).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/graph/nodes/{node_type}/{node_id}",
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"GET /v1/graph/nodes/{node_type}/{node_id}")
        return resp.json().get("data")

    def get_edge(self, edge_type: str, src_id: str, dst_id: str) -> dict | None:
        """Return one edge by type, source and destination, or None if absent.

        Args:
            edge_type: Registered edge type, e.g. "STANDS_WITH", "OPPOSES".
            src_id: Source node ID.
            dst_id: Destination node ID.

        Returns:
            Edge property dict, or None if the edge was not found (HTTP 404).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/graph/edges/{edge_type}/{src_id}/{dst_id}",
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"GET /v1/graph/edges/{edge_type}/{src_id}/{dst_id}")
        return resp.json().get("data")

    # ------------------------------------------------------------------
    # Graph writes
    # ------------------------------------------------------------------

    def upsert_node(self, node_type: str, properties: dict) -> dict:
        """Upsert a node via the generic graph endpoint.

        Args:
            node_type: Registered node type, e.g. "Location", "Faction".
            properties: Property dict including the node's id field.

        Returns:
            Full API response dict (includes data and meta).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/graph/nodes/{node_type}",
            json={"properties": properties},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/graph/nodes/{node_type}")
        return resp.json()

    def upsert_edge(
        self,
        edge_type: str,
        src_id: str,
        dst_id: str,
        properties: dict | None = None,
    ) -> dict:
        """Upsert an edge between two nodes via the generic graph endpoint.

        Args:
            edge_type: Registered edge type, e.g. "STANDS_WITH", "MEMBER_OF".
            src_id: Source node ID.
            dst_id: Destination node ID.
            properties: Optional edge properties (e.g. standing, role).

        Returns:
            Full API response dict.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/graph/edges/{edge_type}",
            json={"src_id": src_id, "dst_id": dst_id, "properties": properties or {}},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/graph/edges/{edge_type}")
        return resp.json()

    # ------------------------------------------------------------------
    # Typed write endpoints (auto-create character-linked nodes + edges)
    # ------------------------------------------------------------------

    def get_beliefs(self, character_id: str) -> list[dict]:
        """Return all beliefs for a character via the typed beliefs endpoint.

        Args:
            character_id: Character node ID.

        Returns:
            List of belief dicts (may be empty).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/admin/beliefs/{character_id}",
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/admin/beliefs/{character_id}")
        return resp.json().get("data", {}).get("beliefs", [])

    def get_goals(self, character_id: str) -> list[dict]:
        """Return all active goals for a character via the typed goals endpoint.

        Args:
            character_id: Character node ID.

        Returns:
            List of goal dicts (may be empty). Each dict has id, description,
            urgency, status, created_at_game_time, and target_id fields.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/admin/goals/{character_id}",
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/admin/goals/{character_id}")
        return resp.json().get("data", {}).get("goals", [])

    def post_belief(
        self,
        character_id: str,
        content: str,
        confidence: int,
        game_time: dict,
    ) -> dict:
        """Create a belief on a character via the typed beliefs endpoint.

        The endpoint auto-creates the BELIEVES edge from the character to
        the new Belief node.

        Args:
            character_id: Character node ID.
            content: Belief text (1–512 chars).
            confidence: Confidence level (0–100).
            game_time: Game time dict with year, season, day, time_of_day.

        Returns:
            Response dict containing belief_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/admin/beliefs/{character_id}",
            json={"content": content, "confidence": confidence, "game_time": game_time},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/beliefs/{character_id}")
        return resp.json()

    def post_goal(
        self,
        character_id: str,
        description: str,
        urgency: int,
        game_time: dict,
        *,
        target_id: str | None = None,
    ) -> dict:
        """Create a goal on a character via the typed goals endpoint.

        The endpoint auto-creates the PURSUES edge from the character to
        the new Goal node.

        Args:
            character_id: Character node ID.
            description: Goal description (1–512 chars).
            urgency: Urgency level (0–100).
            game_time: Game time dict with year, season, day, time_of_day.
            target_id: Optional target entity ID for the goal.

        Returns:
            Response dict containing goal_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        body: dict = {"description": description, "urgency": urgency, "game_time": game_time}
        if target_id is not None:
            body["target_id"] = target_id
        resp = self._client.post(
            f"/v1/admin/goals/{character_id}",
            json=body,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/goals/{character_id}")
        return resp.json()

    def post_memory(
        self,
        character_id: str,
        content: str,
        vividness: int,
        emotional_charge: int,
        game_time: dict,
    ) -> dict:
        """Create a memory on a character via the typed memories endpoint.

        Args:
            character_id: Character node ID.
            content: Memory text (1–1024 chars).
            vividness: How vivid the memory is (0–100).
            emotional_charge: Emotional intensity (-100 to 100; positive=positive).
            game_time: Game time dict with year, season, day, time_of_day.

        Returns:
            Response dict containing memory_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/admin/memories/{character_id}",
            json={
                "content": content,
                "vividness": vividness,
                "emotional_charge": emotional_charge,
                "game_time": game_time,
            },
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/memories/{character_id}")
        return resp.json()

    def post_secret(
        self,
        character_id: str,
        content: str,
        severity: int,
        game_time: dict,
    ) -> dict:
        """Create a secret on a character via the typed secrets endpoint.

        Args:
            character_id: Character node ID.
            content: Secret text (1–512 chars).
            severity: Severity level (0–100).
            game_time: Game time dict with year, season, day, time_of_day.

        Returns:
            Response dict containing secret_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/admin/secrets/{character_id}",
            json={"content": content, "severity": severity, "game_time": game_time},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/secrets/{character_id}")
        return resp.json()

    # ------------------------------------------------------------------
    # Convenience write wrappers (P2.5 UI trigger surface)
    # ------------------------------------------------------------------

    def put_world_state(self, epoch: str, active_conditions: list[str]) -> dict:
        """Update the world state epoch and active conditions.

        Thin wrapper over upsert_node("world_state") that merges on the
        fixed id "ws_main". Used by the P2.5 war-trigger UI button.

        Args:
            epoch: New epoch string, e.g. "peace" or "war".
            active_conditions: List of active condition IDs.

        Returns:
            Full API response dict.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        now = datetime.now(timezone.utc).isoformat()
        return self.upsert_node(
            "world_state",
            {
                "id": "ws_main",
                "epoch": epoch,
                "active_conditions": active_conditions,
                "faction_standings": {},
                "time_of_day": "morning",
                "weather": "clear",
                "last_updated_at": now,
                "last_graph_updated_at": now,
            },
        )

    def put_npc_reputation(
        self,
        character_id: str,
        faction_id: str,
        standing: int,
    ) -> dict:
        """Set a character's standing with a faction via a STANDS_WITH edge.

        Thin wrapper over upsert_edge. Used by the P2.5 war-trigger UI.

        Args:
            character_id: Character node ID.
            faction_id: Faction node ID.
            standing: Standing value as integer (typically -100 to 100).

        Returns:
            Full API response dict.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        return self.upsert_edge("STANDS_WITH", character_id, faction_id, {
            "standing": standing,
            "last_changed_at": "tick_0",
        })

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _raise_for_status(self, response: httpx.Response, context: str) -> None:
        """Raise EngineClientError when the response status is 4xx or 5xx."""
        if response.status_code >= 400:
            raise EngineClientError(
                f"{context} → HTTP {response.status_code}: {response.text[:200]}"
            )
