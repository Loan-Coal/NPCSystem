"""
Module: client._quest
Layer: demo_game (external client — zero npc_engine imports)
Purpose: Quest lifecycle methods: generate, fetch, offer, and choose quest branches.
Dependencies: demo_game.client._base
Used by: demo_game.client
"""

from __future__ import annotations

import hashlib
import json
import uuid

from demo_game.client._base import EngineClientBase


class _QuestMixin(EngineClientBase):
    """Mixin providing quest engine methods.

    Requires EngineClientBase (or compatible) in the MRO.
    """

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
        body_bytes = json.dumps(payload, sort_keys=True).encode()
        hash_val = hashlib.sha256(
            b"|".join([method.encode(), path.encode(), b"", body_bytes])
        ).hexdigest()
        return {
            "X-Request-ID": str(uuid.uuid4()),
            "X-Idempotency-Key": str(uuid.uuid4()),
            "X-Idempotency-Request-Hash": hash_val,
        }

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

    def post_quest_choice(
        self,
        quest_id: str,
        choice_id: str,
        player_id: str,
    ) -> dict:
        """Resolve the player's choice for a branching quest.

        Args:
            quest_id: Source quest node ID.
            choice_id: Identifier of the player's chosen branch option.
            player_id: Player character ID.

        Returns:
            API response dict with quest_id, player_id, and next_quest_id.

        Raises:
            EngineClientError: On any 4xx or 5xx response.
        """
        resp = self._client.post(
            f"/v1/quest/{quest_id}/choose",
            json={"player_id": player_id, "choice_id": choice_id},
            timeout=self._graph_timeout,
        )
        self._raise_for_status(resp, f"POST /v1/quest/{quest_id}/choose")
        return resp.json()
