"""
Module: interaction
Layer: api
Purpose: Public HTTP route for interaction proposal dispatch — opens trade sessions,
         processes move grammar, handles quest proposals and completion claims,
         and returns current interaction state.
Does NOT: write currency transfers (those go through /admin/economy/trade),
          perform authentication key validation (handled by middleware).
Dependencies injected: AsyncSession, PricingEngine, NegotiationStore,
                       QuestLifecycleEngine (via FastAPI Depends).
Used by: npc_engine.main (registered at API_V1_PREFIX)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.dependency_singletons import (
    get_negotiation_store,
    get_pricing_engine,
    get_quest_lifecycle_engine,
)
from npc_engine.api.route_helpers import ok_response
from npc_engine.engines.economy.pricing_engine import PricingEngine
from npc_engine.engines.interaction.models import InteractionProposal
from npc_engine.engines.interaction.negotiation_store import NegotiationStore
from npc_engine.engines.interaction.quest_handler import (
    handle_claim_completion,
    handle_give_item_as_quest_claim,
    handle_propose_quest,
)
from npc_engine.engines.interaction.trade_handler import (
    apply_band_update,
    handle_offer_at_asking_price,
    open_or_resume_trade,
)
from npc_engine.engines.quest.quest_lifecycle_engine import QuestLifecycleEngine
from npc_engine.graph.interaction_queries import write_debt_edge
from npc_engine.graph.pricing_queries import (
    get_active_event_types_at_location,
    get_character_location_id,
    get_character_location_type,
)

_logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interaction", tags=["interaction"])


class ProposalBody(BaseModel):
    """Serialised InteractionProposal from the demo client."""

    kind: str = Field(..., min_length=1)
    target_id: str | None = None
    payload: dict = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class InteractionRequest(BaseModel):
    """Request body for POST /interaction."""

    player_id: str = Field(..., min_length=1)
    npc_id: str = Field(..., min_length=1)
    proposal: ProposalBody

    model_config = ConfigDict(frozen=True)


class BandUpdateRequest(BaseModel):
    """Request body for POST /interaction/band — update disposition band after a turn."""

    player_id: str = Field(..., min_length=1)
    trust: int = Field(default=0)
    affection: int = Field(default=0)

    model_config = ConfigDict(frozen=True)


async def _compute_center_price(
    session: AsyncSession,
    pricing_engine: PricingEngine,
    npc_id: str,
    item_type: str,
) -> int:
    """Compute fair price for item_type at the NPC's current location."""
    location_type = await get_character_location_type(session, npc_id) or "unknown"
    location_id = await get_character_location_id(session, npc_id)
    active_events: list[str] = []
    if location_id is not None:
        active_events = await get_active_event_types_at_location(session, location_id, since_tick=0)
    return pricing_engine.compute_price(
        item_type=item_type,
        location_type=location_type,
        active_event_types=active_events,
        is_faction_member=False,
    )


@router.post("")
async def post_interaction(
    body: InteractionRequest,
    session: AsyncSession = Depends(get_db_session),
    pricing_engine: PricingEngine = Depends(get_pricing_engine),
    negotiation_store: NegotiationStore = Depends(get_negotiation_store),
    quest_engine: QuestLifecycleEngine = Depends(get_quest_lifecycle_engine),
) -> dict:
    """Dispatch an interaction proposal and return the resulting state.

    For ``propose_trade``: opens or resumes a NegotiationSession and
    processes any move in the proposal payload.
    For ``defer_payment`` move: writes the HAS_DEBT edge before returning.
    For ``propose_quest``: loads quest state and returns show_quest_panel.
    For ``claim_completion``: verifies objectives and progresses lifecycle.
    For ``give_item``: checked for quest deliver intercept before falling through.
    For unknown kinds: returns a no-op open state.

    Args:
        body: Player ID, NPC ID, and serialised proposal.
        session: Active Neo4j async session.
        pricing_engine: Singleton pricing engine.
        negotiation_store: Singleton in-memory negotiation store.
        quest_engine: Singleton quest lifecycle engine.

    Returns:
        Envelope containing status, ui_directive, narration_hint, and
        negotiation_state snapshot.
    """
    proposal = InteractionProposal(
        kind=body.proposal.kind,
        target_id=body.proposal.target_id,
        payload=dict(body.proposal.payload),
    )

    if proposal.kind == "propose_quest":
        state = await handle_propose_quest(
            session=session,
            proposal=proposal,
            player_id=body.player_id,
            npc_id=body.npc_id,
            engine=quest_engine,
        )
        return ok_response({
            "status": state.status,
            "ui_directive": state.ui_directive,
            "narration_hint": state.narration_hint,
            "negotiation_state": state.data,
        })

    if proposal.kind == "claim_completion":
        state = await handle_claim_completion(
            session=session,
            proposal=proposal,
            player_id=body.player_id,
            npc_id=body.npc_id,
            engine=quest_engine,
        )
        return ok_response({
            "status": state.status,
            "ui_directive": state.ui_directive,
            "narration_hint": state.narration_hint,
            "negotiation_state": state.data,
        })

    if proposal.kind == "give_item":
        intercepted = await handle_give_item_as_quest_claim(
            session=session,
            proposal=proposal,
            player_id=body.player_id,
            npc_id=body.npc_id,
            engine=quest_engine,
        )
        if intercepted is not None:
            return ok_response({
                "status": intercepted.status,
                "ui_directive": intercepted.ui_directive,
                "narration_hint": intercepted.narration_hint,
                "negotiation_state": intercepted.data,
            })

    if proposal.kind == "propose_trade":
        item_type = proposal.payload.get("item_type", "unknown")
        if item_type == "unknown" and proposal.target_id:
            item_type = "spice"

        center_price = await _compute_center_price(
            session, pricing_engine, npc_id=body.npc_id, item_type=item_type
        )

        state = open_or_resume_trade(
            proposal=proposal,
            player_id=body.player_id,
            seller_id=body.npc_id,
            center_price=center_price,
            store=negotiation_store,
        )

        if state.status == "accepted" and proposal.payload.get("move") == "defer_payment":
            neg = negotiation_store.get(body.player_id)
            if neg is not None:
                try:
                    await write_debt_edge(
                        session,
                        debtor_id=body.player_id,
                        creditor_id=body.npc_id,
                        item_id=neg.item_id,
                        amount=neg.center_price,
                        current_tick=0,
                    )
                except Exception as exc:
                    _logger.warning("debt edge write failed: %s", exc)

        return ok_response({
            "status": state.status,
            "ui_directive": state.ui_directive,
            "narration_hint": state.narration_hint,
            "negotiation_state": state.data,
        })

    if proposal.kind == "currency_offer_asking":
        state = handle_offer_at_asking_price(
            player_id=body.player_id,
            store=negotiation_store,
        )
        return ok_response({
            "status": state.status,
            "ui_directive": state.ui_directive,
            "narration_hint": state.narration_hint,
            "negotiation_state": state.data,
        })

    return ok_response({
        "status": "open",
        "ui_directive": "none",
        "narration_hint": None,
        "negotiation_state": None,
    })


@router.post("/band")
async def update_band(
    body: BandUpdateRequest,
    negotiation_store: NegotiationStore = Depends(get_negotiation_store),
) -> dict:
    """Shift the disposition band for an open session after a dialogue turn.

    Called by the demo after each dialogue response that contains relation_deltas.

    Args:
        body: Player ID and trust/affection deltas from the dialogue turn.
        negotiation_store: Singleton in-memory negotiation store.

    Returns:
        Envelope with updated negotiation_state or null if no session is open.
    """
    apply_band_update(
        player_id=body.player_id,
        trust=body.trust,
        affection=body.affection,
        store=negotiation_store,
    )
    session = negotiation_store.get(body.player_id)
    return ok_response({
        "negotiation_state": session.to_dict() if session else None,
    })
