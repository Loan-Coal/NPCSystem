"""
Module: client
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Synchronous HTTP client wrapping the NPC Engine REST API.
Dependencies: httpx
Used by: demo_game.ui.game_window, demo_game.graph_panel.fetcher, demo_game.seed,
         demo_game.ui.game_window (quest cache load)
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from demo_game.constants import DEMO_MAX_MESSAGE_CHARS


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
    # URL helpers
    # ------------------------------------------------------------------

    @property
    def ws_url(self) -> str:
        """WebSocket base URL derived from base_url (http→ws, https→wss)."""
        return self._base_url.replace("https://", "wss://").replace("http://", "ws://")

    @property
    def api_key(self) -> str:
        """Bearer token used for authentication."""
        return self._api_key

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
            "player_message": player_message[:DEMO_MAX_MESSAGE_CHARS],
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

    def get_engine_status(self) -> list[dict]:
        """Return per-engine status records from the observability endpoint.

        Returns:
            List of dicts each containing engine_name, last_tick_id, last_error,
            last_error_tick, and error_count. Empty list if no engines have run.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get("/v1/system/engines", timeout=self._graph_timeout)
        self._raise_for_status(resp, "GET /v1/system/engines")
        return resp.json().get("data", [])

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
            "/v1/system/events",
            params={"limit": limit},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "GET /v1/system/events")
        return resp.json().get("data", [])

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

    def delete_edge(self, edge_type: str, src_id: str, dst_id: str) -> bool:
        """Delete an edge by type, source, and destination. Returns False if not found.

        Args:
            edge_type: Registered edge type, e.g. "LOCATED_AT".
            src_id: Source node ID.
            dst_id: Destination node ID.

        Returns:
            True if the edge was deleted, False if it did not exist (HTTP 404).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.delete(
            f"/v1/graph/edges/{edge_type}/{src_id}/{dst_id}",
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return False
        self._raise_for_status(resp, f"DELETE /v1/graph/edges/{edge_type}/{src_id}/{dst_id}")
        return resp.json().get("data", {}).get("deleted", True)

    # ------------------------------------------------------------------
    # Graph writes
    # ------------------------------------------------------------------

    def patch_node(self, node_type: str, node_id: str, properties: dict) -> dict | None:
        """Partially update a node; returns the updated node dict or None on 404.

        Args:
            node_type: Registered node type, e.g. "Character".
            node_id: Node ID to patch.
            properties: Partial property dict; only supplied fields are updated.

        Returns:
            Node property dict reflecting the state after the patch, or None if not found.

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.patch(
            f"/v1/graph/nodes/{node_type}/{node_id}",
            json={"properties": properties},
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"PATCH /v1/graph/nodes/{node_type}/{node_id}")
        return resp.json().get("data")

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
        *,
        node_id: str | None = None,
    ) -> dict:
        """Create a belief on a character via the typed beliefs endpoint.

        The endpoint auto-creates the BELIEVES edge from the character to
        the new Belief node. When node_id is provided the server merges on
        that ID, making the call idempotent.

        Args:
            character_id: Character node ID.
            content: Belief text (1–512 chars).
            confidence: Confidence level (0–100).
            game_time: Game time dict with year, season, day, time_of_day.
            node_id: Optional stable ID. When provided the node is merged
                (idempotent re-seeding). When omitted a UUID is generated.

        Returns:
            Response dict containing belief_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        body: dict = {"content": content, "confidence": confidence, "game_time": game_time}
        if node_id is not None:
            body["id"] = node_id
        resp = self._client.post(
            f"/v1/admin/beliefs/{character_id}",
            json=body,
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
        node_id: str | None = None,
    ) -> dict:
        """Create a goal on a character via the typed goals endpoint.

        The endpoint auto-creates the PURSUES edge from the character to
        the new Goal node. When node_id is provided the server merges on
        that ID, making the call idempotent.

        Args:
            character_id: Character node ID.
            description: Goal description (1–512 chars).
            urgency: Urgency level (0–100).
            game_time: Game time dict with year, season, day, time_of_day.
            target_id: Optional target entity ID for the goal.
            node_id: Optional stable ID for idempotent re-seeding.

        Returns:
            Response dict containing goal_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        body: dict = {"description": description, "urgency": urgency, "game_time": game_time}
        if target_id is not None:
            body["target_id"] = target_id
        if node_id is not None:
            body["id"] = node_id
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
        *,
        node_id: str | None = None,
    ) -> dict:
        """Create a memory on a character via the typed memories endpoint.

        When node_id is provided the server merges on that ID (idempotent).

        Args:
            character_id: Character node ID.
            content: Memory text (1–1024 chars).
            vividness: How vivid the memory is (0–100).
            emotional_charge: Emotional intensity (-100 to 100; positive=positive).
            game_time: Game time dict with year, season, day, time_of_day.
            node_id: Optional stable ID for idempotent re-seeding.

        Returns:
            Response dict containing memory_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        body: dict = {
            "content": content,
            "vividness": vividness,
            "emotional_charge": emotional_charge,
            "game_time": game_time,
        }
        if node_id is not None:
            body["id"] = node_id
        resp = self._client.post(
            f"/v1/admin/memories/{character_id}",
            json=body,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/memories/{character_id}")
        return resp.json()

    def get_memories(self, character_id: str, k: int = 10) -> list[dict]:
        """Return memories for a character ordered by vividness descending.

        Args:
            character_id: Character node ID.
            k: Maximum number of memories to return (default 10).

        Returns:
            List of memory dicts. Each has id, content, vividness, emotional_charge,
            and created_at_game_time fields.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/admin/memories/{character_id}",
            params={"k": k},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/admin/memories/{character_id}")
        return resp.json().get("data", {}).get("memories", [])

    def consolidate_memory(
        self,
        npc_id: str,
        player_id: str,
        game_time: dict | None = None,
    ) -> str | None:
        """Trigger memory consolidation for an NPC from their dialogue session turns.

        Calls POST /v1/admin/memories/consolidate/{npc_id}. Returns the new
        memory ID if consolidation occurred, or None if the turn threshold was not met.

        Args:
            npc_id: NPC whose session turns to consolidate.
            player_id: Player session identifier.
            game_time: Optional game-time dict; defaults to spring day 1 morning.

        Returns:
            Memory ID string if a memory was created, else None.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        if game_time is None:
            game_time = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
        resp = self._client.post(
            f"/v1/admin/memories/consolidate/{npc_id}",
            json={"player_id": player_id, "game_time": game_time},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/memories/consolidate/{npc_id}")
        return resp.json().get("data", {}).get("memory_id")

    def post_secret(
        self,
        character_id: str,
        content: str,
        severity: int,
        game_time: dict,
        *,
        node_id: str | None = None,
    ) -> dict:
        """Create a secret on a character via the typed secrets endpoint.

        When node_id is provided the server merges on that ID (idempotent).

        Args:
            character_id: Character node ID.
            content: Secret text (1–512 chars).
            severity: Severity level (0–100).
            game_time: Game time dict with year, season, day, time_of_day.
            node_id: Optional stable ID for idempotent re-seeding.

        Returns:
            Response dict containing secret_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        body: dict = {"content": content, "severity": severity, "game_time": game_time}
        if node_id is not None:
            body["id"] = node_id
        resp = self._client.post(
            f"/v1/admin/secrets/{character_id}",
            json=body,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/secrets/{character_id}")
        return resp.json()

    def post_part_of(
        self,
        child_id: str,
        parent_id: str,
        hierarchy_level: int,
    ) -> dict:
        """Create or update a PART_OF containment edge between two Location nodes.

        Uses MERGE semantics — idempotent on repeated calls.

        Args:
            child_id: ID of the child Location node.
            parent_id: ID of the parent Location node.
            hierarchy_level: Depth level (0=venue, 1=district, 2=city, 3=region, 4=world).

        Returns:
            Response dict confirming the edge was written.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/admin/locations/{child_id}/part_of",
            json={"parent_id": parent_id, "hierarchy_level": hierarchy_level},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/locations/{child_id}/part_of")
        return resp.json()

    # ------------------------------------------------------------------
    # Convenience write wrappers (P2.5 UI trigger surface)
    # ------------------------------------------------------------------

    def put_world_state(self, epoch: str, active_conditions: list[str]) -> dict | None:
        """Partially update the world state epoch and active conditions.

        PATCHes the canonical "world" node (DEC-022). A partial update is required:
        the generic create path (upsert_node) re-validates ALL required fields
        (faction_standings, time_of_day, weather) and 422s on an existing node,
        and re-sending them would clobber live state (SEV-13). patch_node validates
        only the supplied fields against the existing node. Used by the P2.5
        war-trigger UI button. The world_state node is created by the seeder first.

        Args:
            epoch: New epoch string, e.g. "peace" or "war".
            active_conditions: List of active condition IDs.

        Returns:
            Updated node property dict, or None if the "world" node does not exist
            (i.e. the world was never seeded).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        now = datetime.now(timezone.utc).isoformat()
        return self.patch_node(
            "world_state",
            "world",
            {
                "epoch": epoch,
                "active_conditions": active_conditions,
                "last_updated_at": now,
                "last_graph_updated_at": now,
            },
        )

    # ------------------------------------------------------------------
    # Quest engine
    # ------------------------------------------------------------------

    def post_quest_generate(self, quest_giver_id: str) -> dict:
        """Generate a quest for the given NPC via the quest engine.

        This is an LLM-backed call — uses dialogue_timeout.

        Args:
            quest_giver_id: Character node ID of the NPC giving the quest.

        Returns:
            Dict with quest_id and description fields.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            "/v1/admin/quests/generate",
            json={"quest_giver_id": quest_giver_id},
            timeout=self._dialogue_timeout,
        )
        self._raise_for_status(resp, "POST /v1/admin/quests/generate")
        return resp.json().get("data", {})

    def get_quest_drafts(self, quest_giver_id: str | None = None) -> list[dict]:
        """Return all draft quests, optionally filtered by quest giver.

        Args:
            quest_giver_id: Optional character ID to filter drafts by giver.

        Returns:
            List of quest property dicts with status='draft'.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        params: dict = {}
        if quest_giver_id is not None:
            params["quest_giver_id"] = quest_giver_id
        resp = self._client.get(
            "/v1/admin/quests/drafts",
            params=params,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "GET /v1/admin/quests/drafts")
        return resp.json().get("data", {}).get("drafts", [])

    def get_quest(self, quest_id: str) -> dict | None:
        """Fetch a quest by ID, or None if it does not exist.

        Args:
            quest_id: Quest node ID to fetch.

        Returns:
            Quest property dict, or None if the quest was not found (HTTP 404).

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(f"/v1/admin/quests/{quest_id}", timeout=self._graph_timeout)
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, f"GET /v1/admin/quests/{quest_id}")
        return (resp.json().get("data") or {}).get("quest")

    def _quest_headers(self, method: str, path: str, payload: dict) -> dict:
        """Generate the three idempotency headers required by quest lifecycle routes.

        ``X-Idempotency-Request-Hash`` is SHA-256 of
        ``"METHOD|path||body_bytes"`` (deterministic for the same inputs).
        ``X-Request-ID`` and ``X-Idempotency-Key`` are fresh uuid4 each call.

        Args:
            method: HTTP method string (e.g. ``"POST"``).
            path: Request path (e.g. ``"/v1/quests/offer"``).
            payload: Request body dict — serialised deterministically for the hash.

        Returns:
            Dict with ``X-Request-ID``, ``X-Idempotency-Key``, and
            ``X-Idempotency-Request-Hash`` keys.
        """
        import hashlib
        import json
        import uuid

        body_bytes = json.dumps(payload, sort_keys=True).encode()
        hash_val = hashlib.sha256(
            b"|".join([method.encode(), path.encode(), b"", body_bytes])
        ).hexdigest()
        return {
            "X-Request-ID": str(uuid.uuid4()),
            "X-Idempotency-Key": str(uuid.uuid4()),
            "X-Idempotency-Request-Hash": hash_val,
        }

    def post_quest_accept(self, quest_id: str, player_id: str) -> dict:
        """Accept a previously-offered quest on behalf of the player.

        Args:
            quest_id: The quest node ID to accept.
            player_id: Character ID of the accepting player.

        Returns:
            Full API response dict (quest at ``"active"`` status).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        path = "/v1/quest/accept"
        payload = {"quest_id": quest_id, "player_id": player_id}
        resp = self._client.post(
            path,
            json=payload,
            headers=self._quest_headers("POST", path, payload),
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST {path}")
        return resp.json()

    def post_quest_offer(
        self,
        quest_id: str,
        player_id: str,
        title: str,
        objectives: list[dict],
        item_rewards: list[dict],
        currency_reward: dict | None,
        reward_source_id: str = "system",
    ) -> dict:
        """Seed an offered quest state for a player (lifecycle /v1/quest/offer).

        Used by seed.py to create deterministic demo quests without LLM generation.

        Args:
            quest_id: Stable quest node ID.
            player_id: Accepting player character ID.
            title: Human-readable quest title.
            objectives: List of objective dicts (objective_id, target_count, objective_type, target_id).
            item_rewards: List of item reward dicts (item_id, quantity).
            currency_reward: Optional {amount: int} dict or None.
            reward_source_id: Reward source character ID or ``"system"``.

        Returns:
            API response dict with quest state.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        path = "/v1/quest/offer"
        payload: dict = {
            "quest_id": quest_id,
            "player_id": player_id,
            "title": title,
            "objectives": objectives,
            "item_rewards": item_rewards,
        }
        if currency_reward is not None:
            payload["currency_reward"] = currency_reward
        if reward_source_id != "system":
            payload["reward_source_id"] = reward_source_id
        resp = self._client.post(
            path,
            json=payload,
            headers=self._quest_headers("POST", path, payload),
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST {path}")
        return resp.json()

    def post_quest_objective(
        self,
        quest_id: str,
        player_id: str,
        objective_id: str,
        progress_delta: int,
    ) -> dict:
        """Apply one objective progress delta.

        Args:
            quest_id: Quest node ID.
            player_id: Character ID of the player.
            objective_id: Objective to update.
            progress_delta: Signed integer added to current progress.

        Returns:
            Updated quest state dict.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        path = "/v1/quest/objective"
        payload = {
            "quest_id": quest_id,
            "player_id": player_id,
            "objective_id": objective_id,
            "progress_delta": progress_delta,
        }
        resp = self._client.post(
            path,
            json=payload,
            headers=self._quest_headers("POST", path, payload),
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST {path}")
        return resp.json()

    def post_quest_evaluate(self, quest_id: str, player_id: str) -> dict:
        """Evaluate quest completion and transition to completed if objectives met.

        Args:
            quest_id: Quest node ID.
            player_id: Character ID of the player.

        Returns:
            Updated quest state dict (status=completed or in_progress).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        path = "/v1/quest/evaluate"
        payload = {"quest_id": quest_id, "player_id": player_id}
        resp = self._client.post(
            path,
            json=payload,
            headers=self._quest_headers("POST", path, payload),
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST {path}")
        return resp.json()

    def post_quest_reward(self, quest_id: str, player_id: str) -> dict:
        """Apply rewards for a completed quest.

        Args:
            quest_id: Quest node ID.
            player_id: Character ID of the player.

        Returns:
            Updated quest state dict with rewards_applied=True.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        path = "/v1/quest/reward"
        payload = {"quest_id": quest_id, "player_id": player_id}
        resp = self._client.post(
            path,
            json=payload,
            headers=self._quest_headers("POST", path, payload),
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST {path}")
        return resp.json()

    # ------------------------------------------------------------------
    # Interaction (trade / quest proposals)
    # ------------------------------------------------------------------

    def post_interaction(
        self,
        player_id: str,
        npc_id: str,
        proposal: dict,
    ) -> dict:
        """Dispatch an interaction proposal and return the resulting InteractionState.

        Args:
            player_id: ID of the player character.
            npc_id: ID of the NPC being engaged.
            proposal: Dict with keys ``kind``, ``target_id`` (nullable), and
                ``payload`` (free-form params).

        Returns:
            Dict with ``status``, ``ui_directive``, ``narration_hint``, and
            ``negotiation_state`` (nullable).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            "/v1/interaction",
            json={"player_id": player_id, "npc_id": npc_id, "proposal": proposal},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "POST /v1/interaction")
        return resp.json()

    def post_interaction_band(
        self,
        player_id: str,
        trust: int,
        affection: int,
    ) -> None:
        """Update the disposition band for the player's open negotiation session.

        Non-fatal — a missing or closed session is silently ignored by the server.

        Args:
            player_id: ID of the player whose band to update.
            trust: Trust delta from the last dialogue turn.
            affection: Affection delta from the last dialogue turn.

        Raises:
            EngineClientError: On any non-2xx response other than 404.
        """
        resp = self._client.post(
            "/v1/interaction/band",
            json={"player_id": player_id, "trust": trust, "affection": affection},
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return
        self._raise_for_status(resp, "POST /v1/interaction/band")

    # ------------------------------------------------------------------
    # Economy
    # ------------------------------------------------------------------

    def get_item_price(self, item_type: str, character_id: str) -> int | None:
        """Fetch the current market price for an item type. Returns None on 404.

        Args:
            item_type: Item category string, e.g. ``"spice"``.
            character_id: NPC selling the item (used for dynamic pricing).

        Returns:
            Price as an integer, or None if the item/NPC is not found.

        Raises:
            EngineClientError: On any non-404 4xx or 5xx response.
        """
        resp = self._client.get(
            "/v1/admin/economy/price",
            params={"item_type": item_type, "character_id": character_id},
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, "GET /v1/admin/economy/price")
        return resp.json().get("data", {}).get("price")

    def post_trade(
        self,
        buyer_id: str,
        seller_id: str,
        item_id: str,
        item_type: str,
        offered_price: int,
        tick: int,
    ) -> dict:
        """Submit a trade offer and return the trade result.

        Args:
            buyer_id: ID of the buying character.
            seller_id: ID of the selling character.
            item_id: Specific item node ID.
            item_type: Item category (e.g. ``"spice"``).
            offered_price: Price the buyer is offering.
            tick: Current game tick.

        Returns:
            Full API response dict (includes ``accepted`` and optionally
            ``rejection_reason``).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            "/v1/admin/economy/trade",
            json={
                "buyer_id": buyer_id,
                "seller_id": seller_id,
                "item_id": item_id,
                "item_type": item_type,
                "offered_price": offered_price,
                "current_tick": tick,
            },
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, "POST /v1/admin/economy/trade")
        return resp.json()

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

    def get_leverage_for_npc(self, npc_id: str) -> list[dict]:
        """Return Leverage nodes held by npc_id via HAS_LEVERAGE edges.

        Fetches HAS_LEVERAGE edges where src_id=npc_id, then cross-references
        all Leverage nodes client-side — appropriate for demo scale.

        Args:
            npc_id: Character node ID.

        Returns:
            List of Leverage node dicts with id, demand, status, created_at_tick.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        edges = self.get_graph_edges("HAS_LEVERAGE", src_id=npc_id)
        if not edges:
            return []
        leverage_ids = {e.get("dst_id") for e in edges if e.get("dst_id")}
        all_leverage = self.get_graph_nodes("Leverage", limit=200)
        return [lv for lv in all_leverage if lv.get("id") in leverage_ids]

    def get_needs_for_npc(self, npc_id: str) -> list[dict]:
        """Return all Need nodes for the given NPC, filtered by character_id.

        Fetches all Need nodes via the generic graph endpoint and filters
        client-side — appropriate for demo scale (few NPCs, few needs each).

        Args:
            npc_id: Character node ID to filter by.

        Returns:
            List of Need node dicts with id, kind, level, decay_rate, character_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        all_needs = self.get_graph_nodes("Need", limit=200)
        return [n for n in all_needs if n.get("character_id") == npc_id]

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

    def get_items_for_character(self, character_id: str) -> list[dict]:
        """Return all items owned by a character.

        Args:
            character_id: Character node ID.

        Returns:
            List of item property dicts (id, name, description, value, rarity, type).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.get(
            f"/v1/admin/items/{character_id}",
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"GET /v1/admin/items/{character_id}")
        return resp.json().get("data", {}).get("items", [])

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

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _raise_for_status(self, response: httpx.Response, context: str) -> None:
        """Raise EngineClientError when the response status is 4xx or 5xx.

        Reads the canonical ErrorEnvelope shape: ``{"error": {"code": ..., "message": ...}}``.

        Args:
            response: HTTP response to inspect.
            context: Human-readable description of the call (method + path).

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        if response.status_code >= 400:
            try:
                body = response.json()
                error_block = body.get("error") or {}
                msg = error_block.get("message") or response.text[:200]
            except Exception:
                msg = response.text[:200]
            raise EngineClientError(f"{context} → HTTP {response.status_code}: {msg}")
