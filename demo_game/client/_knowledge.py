"""
Module: client._knowledge
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Character knowledge writes (beliefs, goals, memories, secrets) and related reads.
         Also covers world-state partial update and location containment edges.
Dependencies: demo_game.client._base
Used by: demo_game.client
"""

from __future__ import annotations

from datetime import datetime, timezone

from demo_game.client._base import EngineClientBase


class _KnowledgeMixin(EngineClientBase):
    """Mixin providing character knowledge and world-state write methods.

    Requires EngineClientBase (or compatible) in the MRO.
    """

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

    def get_player_model(self, npc_id: str, player_id: str) -> dict | None:
        """Return the player model an NPC holds about a specific player.

        Calls GET /v1/npc/{npc_id}/player-model/{player_id}. Returns the
        ``data`` sub-dict on 2xx, None on any non-2xx response (including 404
        when the NPC has no model yet) so callers degrade gracefully.

        Args:
            npc_id: The NPC whose perspective to read.
            player_id: The player whose model to fetch (e.g. player_demo).

        Returns:
            Dict from the ``data`` key of the response envelope (contains
            ``npc_id``, ``player_id``, ``perceived_trust``,
            ``perceived_intent``, ``last_updated_at``), or None when the
            endpoint returns a non-2xx status.
        """
        resp = self._client.get(
            f"/v1/npc/{npc_id}/player-model/{player_id}",
            timeout=self._graph_timeout,
        )
        if resp.status_code >= 400:
            return None
        return resp.json().get("data")

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
        occurred_at_game_time: dict | None = None,
        is_historical: bool = False,
    ) -> dict:
        """Create a memory on a character via the typed memories endpoint.

        When node_id is provided the server merges on that ID (idempotent).

        Args:
            character_id: Character node ID.
            content: Memory text (1–1024 chars).
            vividness: How vivid the memory is (0–100).
            emotional_charge: Emotional intensity (-100 to 100; positive=positive).
            game_time: Game time dict with year, season, day, time_of_day (record time).
            node_id: Optional stable ID for idempotent re-seeding.
            occurred_at_game_time: When the remembered event happened (distinct from the
                record time); defaults server-side to game_time when omitted.
            is_historical: True when the memory is of a prior era / long-past event.

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
            "is_historical": is_historical,
        }
        if occurred_at_game_time is not None:
            body["occurred_at_game_time"] = occurred_at_game_time
        if node_id is not None:
            body["id"] = node_id
        resp = self._client.post(
            f"/v1/admin/memories/{character_id}",
            json=body,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/memories/{character_id}")
        return resp.json()

    def consolidate_memory(
        self,
        npc_id: str,
        player_id: str,
        game_time: dict | None = None,
        *,
        turn_threshold: int | None = None,
    ) -> dict:
        """Trigger memory consolidation for an NPC from their dialogue session turns.

        Calls POST /v1/admin/memories/consolidate/{npc_id}. Returns the data
        payload dict containing 'memory_id' (str or None) and 'status'
        ('created', 'threshold_not_met', or 'llm_failed').

        Args:
            npc_id: NPC whose session turns to consolidate.
            player_id: Player session identifier.
            game_time: Optional game-time dict; defaults to spring day 1 morning.
            turn_threshold: Optional override sent to the engine; omitted when None.

        Returns:
            Data dict from the API response.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        if game_time is None:
            game_time = {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
        body: dict = {"player_id": player_id, "game_time": game_time}
        if turn_threshold is not None:
            body["turn_threshold"] = turn_threshold
        resp = self._client.post(
            f"/v1/admin/memories/consolidate/{npc_id}",
            json=body,
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/admin/memories/consolidate/{npc_id}")
        return resp.json().get("data", {})

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
        resp = self._client.patch(
            "/v1/graph/nodes/world_state/world",
            json={"properties": {
                "epoch": epoch,
                "active_conditions": active_conditions,
                "last_updated_at": now,
                "last_graph_updated_at": now,
            }},
            timeout=self._graph_timeout,
        )
        if resp.status_code == 404:
            return None
        self._raise_for_status(resp, "PATCH /v1/graph/nodes/world_state/world")
        return resp.json().get("data")
