"""
Module: quest_reward_router
Layer: engines
Purpose: Quest reward routing — atomic delivery collection, item grant, and currency transfer
    within a single Neo4j transaction once a quest reaches completed status.
Dependencies: npc_engine.config, npc_engine.engines.quest.models,
    npc_engine.engines.quest.quest_engine_helpers, npc_engine.graph.*,
    npc_engine.type_registry, npc_engine.utils.errors.
Used by: api.routes.quest (via dependency injection).

Does NOT: perform state machine transitions (accept/update/evaluate live in
    quest_lifecycle_engine). Does NOT: handle offer flow.
Dependencies injected: Settings, TypeRegistry (via __init__); AsyncSession (per method).
"""

from __future__ import annotations

import logging

from neo4j import AsyncSession, AsyncTransaction

from npc_engine.config import Settings
from npc_engine.engines.quest.models import (
    QuestStateRecord,
    QuestStatus,
    QuestTransitionMeta,
)
from npc_engine.engines.quest.quest_engine_helpers import (
    build_lifecycle_event,
    ensure_transaction_session,
    is_trusted_reward_source,
    normalize_item_rewards,
)
from npc_engine.graph.currency_writer import execute_currency_transfer_in_tx, get_character_balance
from npc_engine.graph.event_writer import upsert_quest_lifecycle_event
from npc_engine.graph.item_queries import check_item_possession_in_tx
from npc_engine.graph.item_writer import execute_item_transfer_in_tx
from npc_engine.graph.quest_writer import get_quest_state, upsert_quest_state
from npc_engine.graph.transaction_coordinator import run_in_tx
from npc_engine.type_registry.contracts import TypeRegistry
from npc_engine.utils.errors import QuestTransitionError


_logger = logging.getLogger(__name__)


class QuestRewardRouter:
    """Quest reward coordinator — possession check → delivery → item/currency grants."""

    def __init__(self, settings: Settings, registry: TypeRegistry | None = None) -> None:
        """Initialise the quest reward router.

        Args:
            settings: Application settings (used for currency transfer configuration).
            registry: Type registry providing event node model; must be injected
                by the composition root (``api/dependency_singletons.py``).
        Raises:
            ValueError: If registry is None (must be injected via __init__).
        """
        self._settings = settings
        if registry is None:
            raise ValueError("QuestRewardRouter requires a TypeRegistry injected via __init__")
        self._registry = registry

    async def _require_state(
        self, *, session: AsyncSession, quest_id: str, player_id: str
    ) -> QuestStateRecord:
        payload = await get_quest_state(session=session, quest_id=quest_id, player_id=player_id)
        if payload is None:
            raise QuestTransitionError(
                code="QUEST_NOT_FOUND",
                detail=f"Quest state not found for quest_id={quest_id}, player_id={player_id}",
            )
        return QuestStateRecord.model_validate(payload)

    async def apply_rewards(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> dict:
        """Apply quest rewards atomically: possession check → delivery → grants → state persist.

        Delivery collection, reward grants, and rewards_applied flag are written in
        a single transaction so that partial application on crash is impossible.

        Args:
            session: Active Neo4j async session capable of starting transactions.
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for provenance and idempotency fields.

        Returns:
            Persisted quest state payload dict with ``rewards_applied=True``.

        Raises:
            QuestTransitionError: If quest not completed, reward source invalid,
                player lacks a delivery item, or delivery transfer fails.
        """
        state = await self._require_state(session=session, quest_id=quest_id, player_id=player_id)
        if state.status != QuestStatus.COMPLETED:
            raise QuestTransitionError(
                code="QUEST_TRANSITION_INVALID",
                detail=f"Quest rewards can only be applied from status={QuestStatus.COMPLETED}",
            )
        if state.rewards_applied:
            await self._emit_idempotent_event(
                session=session, quest_id=quest_id, player_id=player_id, state=state, meta=meta
            )
            return state.model_dump(mode="python")

        if not is_trusted_reward_source(state.reward_source_id):
            raise QuestTransitionError(
                code="QUEST_REWARD_SOURCE_INVALID",
                detail="Quest reward source must be a trusted system source",
            )
        if state.currency_reward is not None and state.reward_source_id != "system":
            balance = await get_character_balance(session=session, character_id=state.reward_source_id)
            if balance is None or balance < state.currency_reward.amount:
                raise QuestTransitionError(
                    code="QUEST_REWARD_SOURCE_INSUFFICIENT",
                    detail=f"NPC {state.reward_source_id} cannot afford {state.currency_reward.amount}",
                )

        next_state = state.model_copy(update={"rewards_applied": True})
        ensure_transaction_session(session=session)

        async def _work(tx: AsyncTransaction) -> dict:
            await self._apply_rewards_in_tx(
                tx=tx,
                state=state,
                quest_id=quest_id,
                player_id=player_id,
                meta=meta,
            )
            stored = await upsert_quest_state(
                session=tx,
                quest_id=quest_id,
                player_id=player_id,
                state_payload=next_state.model_dump(mode="python"),
            )
            event = build_lifecycle_event(
                registry=self._registry,
                quest_id=quest_id,
                player_id=player_id,
                event_type="quest_rewards_applied",
                summary=f"Quest rewards applied: {state.title}",
                meta=meta,
            )
            await upsert_quest_lifecycle_event(tx=tx, event=event)
            return stored

        return await run_in_tx(session, _work)

    async def _emit_idempotent_event(
        self,
        *,
        session: AsyncSession,
        quest_id: str,
        player_id: str,
        state: QuestStateRecord,
        meta: QuestTransitionMeta,
    ) -> None:
        ensure_transaction_session(session=session)
        event = build_lifecycle_event(
            registry=self._registry,
            quest_id=quest_id,
            player_id=player_id,
            event_type="quest_rewards_applied",
            summary=f"Quest rewards applied: {state.title}",
            meta=meta,
        )
        async def _work(tx: AsyncTransaction) -> None:
            await upsert_quest_lifecycle_event(tx=tx, event=event)

        await run_in_tx(session, _work)

    async def _apply_rewards_in_tx(
        self,
        *,
        tx: object,
        state: QuestStateRecord,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> None:
        """Sequence possession check, delivery collection, and reward grants within one tx.

        Delivery items are collected BEFORE reward grants so that a failure at
        collection rolls back the entire operation with no partial grant.

        Args:
            tx: Active Neo4j transaction; caller owns commit/rollback.
            state: Current validated quest state record.
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for idempotency and audit fields.

        Raises:
            QuestTransitionError: If player lacks a delivery item or delivery fails.
        """
        if state.reward_source_id != "system":
            await self._collect_delivery_items_in_tx(
                tx=tx, state=state, quest_id=quest_id, player_id=player_id, meta=meta
            )
        normalized_item_rewards = normalize_item_rewards(state.item_rewards)
        for item_reward in normalized_item_rewards:
            idem_key = f"quest:{quest_id}:{player_id}:item:{item_reward.item_id}"
            await execute_item_transfer_in_tx(
                tx,  # type: ignore[arg-type]
                source_id=state.reward_source_id,
                destination_id=player_id,
                item_id=item_reward.item_id,
                quantity=item_reward.quantity,
                reason=f"quest_reward:{quest_id}",
                request_id=meta.request_id,
                idempotency_key=idem_key,
                transfer_kind="quest_reward",
            )
        if state.currency_reward is not None:
            idem_key = f"quest:{quest_id}:{player_id}:currency"
            await execute_currency_transfer_in_tx(
                tx,  # type: ignore[arg-type]
                settings=self._settings,
                source_id=state.reward_source_id,
                destination_id=player_id,
                amount=state.currency_reward.amount,
                reason=f"quest_reward:{quest_id}",
                request_id=meta.request_id,
                idempotency_key=idem_key,
                session_scope=f"quest:{quest_id}:{player_id}",
                transfer_kind="quest_reward",
            )

    async def _collect_delivery_items_in_tx(
        self,
        *,
        tx: object,
        state: QuestStateRecord,
        quest_id: str,
        player_id: str,
        meta: QuestTransitionMeta,
    ) -> None:
        """Check possession and take delivery items from the player within a transaction.

        Args:
            tx: Active Neo4j transaction; caller owns commit/rollback.
            state: Current validated quest state record.
            quest_id: Quest identifier.
            player_id: Player identifier.
            meta: Transition metadata for idempotency and audit fields.

        Raises:
            QuestTransitionError: If player lacks a required delivery item or
                the item transfer fails unexpectedly.
        """
        for obj in state.objectives:
            if obj.objective_type != "deliver" or obj.target_id is None:
                continue
            has_item = await check_item_possession_in_tx(
                tx,  # type: ignore[arg-type]
                player_id=player_id,
                item_id=obj.target_id,
                min_quantity=obj.target_count,
            )
            if not has_item:
                raise QuestTransitionError(
                    code="QUEST_ITEM_NOT_POSSESSED",
                    detail=f"Player {player_id} does not own {obj.target_count}x {obj.target_id}",
                )
            deliver_idem_key = f"quest:{quest_id}:{player_id}:deliver:{obj.objective_id}"
            try:
                await execute_item_transfer_in_tx(
                    tx,  # type: ignore[arg-type]
                    source_id=player_id,
                    destination_id=state.reward_source_id,
                    item_id=obj.target_id,
                    quantity=obj.target_count,
                    reason=f"quest_deliver:{quest_id}",
                    request_id=meta.request_id,
                    idempotency_key=deliver_idem_key,
                    transfer_kind="quest_deliver",
                )
            except QuestTransitionError:
                raise
            except Exception as exc:
                raise QuestTransitionError(
                    code="QUEST_DELIVER_FAILED",
                    detail=f"Failed to collect delivery item {obj.target_id}: {exc}",
                ) from exc
