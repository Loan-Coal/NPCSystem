"""
Module: quest_reward_repository
Layer: graph
Purpose: Neo4j adapter for atomic quest reward delivery — possession check, delivery
         collection, item/currency grants, and QuestState persistence in a single
         transaction. Implements QuestRewardGraphPort structurally.
Does NOT: contain engine-level business logic (reward eligibility is validated by the
          engine before calling this adapter), call LLMs, or import from engines/.
Dependencies injected: GraphDB.
Used by: api composition root (dependencies_engines.py).
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncTransaction

from npc_engine.config import Settings
from npc_engine.graph.economy.currency_writer import execute_currency_transfer_in_tx, get_character_balance
from npc_engine.graph.db import GraphDB
from npc_engine.graph.event.event_writer import upsert_quest_lifecycle_event
from npc_engine.graph.economy.item_queries import check_item_possession_in_tx
from npc_engine.graph.economy.item_writer import execute_item_transfer_in_tx
from npc_engine.graph.quest_writer import get_quest_state, upsert_quest_state
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.utils.errors import QuestTransitionError


class Neo4jQuestRewardRepository:
    """Session-per-call adapter for quest reward delivery (QuestRewardGraphPort)."""

    def __init__(self, graph_db: GraphDB) -> None:
        """Store the injected driver holder.

        Args:
            graph_db: Neo4j driver holder providing connect() + get_session().
        """
        self._graph_db = graph_db

    async def get_quest_state(self, *, quest_id: str, player_id: str) -> dict[str, Any] | None:
        """Return the persisted QuestState dict[str, Any] or None if absent."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_quest_state(session=session, quest_id=quest_id, player_id=player_id)

    async def get_character_balance(self, *, character_id: str) -> int | None:
        """Return the character's current currency balance, or None if not found."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            return await get_character_balance(session, character_id=character_id)

    async def emit_lifecycle_event(self, *, event_node: Any) -> None:
        """Atomically write one quest lifecycle event node (idempotent path)."""
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            async def _work(tx: AsyncTransaction) -> None:
                await upsert_quest_lifecycle_event(tx=tx, event=event_node)

            await run_in_tx(session, _work)

    async def apply_rewards_atomic(
        self,
        *,
        quest_id: str,
        player_id: str,
        request_id: str,
        state_dict: dict[str, Any],
        next_state_payload: dict[str, Any],
        event_node: Any,
        settings: Settings,
    ) -> dict[str, Any]:
        """Atomically collect delivery items, grant rewards, persist state+event; return stored.

        Raises:
            QuestTransitionError: If a delivery item is missing or item transfer fails.
        """
        await self._graph_db.connect()
        async with self._graph_db.get_session() as session:
            async def _work(tx: AsyncTransaction) -> dict[str, Any]:
                return await self._do_reward_work(
                    tx,
                    quest_id=quest_id,
                    player_id=player_id,
                    request_id=request_id,
                    state_dict=state_dict,
                    next_state_payload=next_state_payload,
                    event_node=event_node,
                    settings=settings,
                )

            return await run_in_tx(session, _work)

    async def _do_reward_work(
        self,
        tx: AsyncTransaction,
        *,
        quest_id: str,
        player_id: str,
        request_id: str,
        state_dict: dict[str, Any],
        next_state_payload: dict[str, Any],
        event_node: Any,
        settings: Settings,
    ) -> dict[str, Any]:
        """Execute reward collection, state persistence, and event write within one transaction."""
        await self._apply_in_tx(
            tx=tx,
            quest_id=quest_id,
            player_id=player_id,
            request_id=request_id,
            state_dict=state_dict,
            settings=settings,
        )
        stored = await upsert_quest_state(
            session=tx,
            quest_id=quest_id,
            player_id=player_id,
            state_payload=next_state_payload,
        )
        await upsert_quest_lifecycle_event(tx=tx, event=event_node)
        return stored

    async def _apply_in_tx(
        self,
        *,
        tx: Any,
        quest_id: str,
        player_id: str,
        request_id: str,
        state_dict: dict[str, Any],
        settings: Settings,
    ) -> None:
        """Collect delivery items and grant rewards within an existing transaction."""
        reward_source_id: str = state_dict["reward_source_id"]
        if reward_source_id != "system":
            await self._collect_delivery_in_tx(
                tx=tx,
                quest_id=quest_id,
                player_id=player_id,
                reward_source_id=reward_source_id,
                objectives=state_dict.get("objectives", []),
                request_id=request_id,
            )
        await self._grant_item_rewards_in_tx(
            tx,
            reward_source_id=reward_source_id,
            player_id=player_id,
            item_rewards=state_dict.get("item_rewards", []),
            quest_id=quest_id,
            request_id=request_id,
        )
        await self._grant_currency_reward_in_tx(
            tx,
            settings=settings,
            reward_source_id=reward_source_id,
            player_id=player_id,
            currency_reward=state_dict.get("currency_reward"),
            quest_id=quest_id,
            request_id=request_id,
        )

    async def _grant_item_rewards_in_tx(
        self,
        tx: Any,
        *,
        reward_source_id: str,
        player_id: str,
        item_rewards: list[dict[str, Any]],
        quest_id: str,
        request_id: str,
    ) -> None:
        """Transfer each item reward from source to player within the active transaction."""
        for item_reward in _normalize_item_rewards(item_rewards):
            idem_key = f"quest:{quest_id}:{player_id}:item:{item_reward['item_id']}"
            await execute_item_transfer_in_tx(
                tx,
                source_id=reward_source_id,
                destination_id=player_id,
                item_id=item_reward["item_id"],
                quantity=item_reward["quantity"],
                reason=f"quest_reward:{quest_id}",
                request_id=request_id,
                idempotency_key=idem_key,
                transfer_kind="quest_reward",
            )

    async def _grant_currency_reward_in_tx(
        self,
        tx: Any,
        *,
        settings: Settings,
        reward_source_id: str,
        player_id: str,
        currency_reward: dict[str, Any] | None,
        quest_id: str,
        request_id: str,
    ) -> None:
        """Transfer currency reward from source to player within the active transaction."""
        if currency_reward is None:
            return
        idem_key = f"quest:{quest_id}:{player_id}:currency"
        await execute_currency_transfer_in_tx(
            tx,
            settings=settings,
            source_id=reward_source_id,
            destination_id=player_id,
            amount=currency_reward["amount"],
            reason=f"quest_reward:{quest_id}",
            request_id=request_id,
            idempotency_key=idem_key,
            session_scope=f"quest:{quest_id}:{player_id}",
            transfer_kind="quest_reward",
        )

    async def _collect_delivery_in_tx(
        self,
        *,
        tx: Any,
        quest_id: str,
        player_id: str,
        reward_source_id: str,
        objectives: list[dict[str, Any]],
        request_id: str,
    ) -> None:
        """Check possession and transfer delivery items within an existing transaction."""
        for obj in objectives:
            if obj.get("objective_type") != "deliver" or obj.get("target_id") is None:
                continue
            target_id: str = obj["target_id"]
            target_count: int = int(obj.get("target_count", 1))
            has_item = await check_item_possession_in_tx(
                tx, player_id=player_id, item_id=target_id, min_quantity=target_count
            )
            if not has_item:
                raise QuestTransitionError(
                    code="QUEST_ITEM_NOT_POSSESSED",
                    detail=f"Player {player_id} does not own {target_count}x {target_id}",
                )
            await self._execute_delivery_transfer_in_tx(
                tx,
                player_id=player_id,
                reward_source_id=reward_source_id,
                obj=obj,
                quest_id=quest_id,
                request_id=request_id,
            )

    async def _execute_delivery_transfer_in_tx(
        self,
        tx: Any,
        *,
        player_id: str,
        reward_source_id: str,
        obj: dict[str, Any],
        quest_id: str,
        request_id: str,
    ) -> None:
        """Transfer a single delivery item from player to source; raise on failure."""
        target_id: str = obj["target_id"]
        target_count: int = int(obj.get("target_count", 1))
        deliver_idem = f"quest:{quest_id}:{player_id}:deliver:{obj.get('objective_id', target_id)}"
        try:
            await execute_item_transfer_in_tx(
                tx,
                source_id=player_id,
                destination_id=reward_source_id,
                item_id=target_id,
                quantity=target_count,
                reason=f"quest_deliver:{quest_id}",
                request_id=request_id,
                idempotency_key=deliver_idem,
                transfer_kind="quest_deliver",
            )
        except QuestTransitionError:
            raise
        except Exception as exc:
            raise QuestTransitionError(
                code="QUEST_DELIVER_FAILED",
                detail=f"Failed to collect delivery item {target_id}: {exc}",
            ) from exc


def _normalize_item_rewards(item_rewards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate and merge item rewards by item_id, summing quantities."""
    merged: dict[str, int] = {}
    for reward in item_rewards:
        item_id = reward.get("item_id", "")
        quantity = int(reward.get("quantity", 1))
        merged[item_id] = merged.get(item_id, 0) + quantity
    return [{"item_id": iid, "quantity": qty} for iid, qty in merged.items()]
