"""
Module: memories
Layer: api
Purpose: Admin HTTP routes for creating, retrieving, and managing Memory nodes on characters.
Does NOT: perform authentication or validate auth scopes directly.
Dependencies: graph.memory_service, engines.memory.memory_engine, api.dependencies.get_db_session
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.main (registered at admin_prefix)
"""

from __future__ import annotations

from typing import Any

from neo4j import AsyncSession
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.dependency_singletons import get_memory_consolidation_engine, get_memory_engine
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.graph.memory_service import (
    create_memory,
    decay_all_vividness,
    delete_memory,
    get_memories_for_character_svc,
)
from npc_engine.world.time_utils import TimePoint

# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateMemoryRequest(BaseModel):
    """Request body for creating a memory on a character."""

    content: str = Field(..., min_length=1, max_length=1024)
    vividness: int = Field(..., ge=0, le=100)
    emotional_charge: int = Field(..., ge=-100, le=100)
    game_time: dict[str, Any] = Field(
        default_factory=lambda: {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
    )
    id: str | None = Field(
        default=None,
        description=(
            "Caller-supplied stable ID. When provided the node is merged (idempotent). "
            "When omitted a UUID is auto-generated."
        ),
    )
    occurred_at_game_time: dict[str, Any] | None = Field(
        default=None,
        description=(
            "When the remembered event actually happened (distinct from game_time, the "
            "record time). When omitted it defaults to game_time (S26.3, DEC-094)."
        ),
    )
    is_historical: bool = Field(
        default=False,
        description="True when the memory is of a prior era / long-past event.",
    )

    model_config = ConfigDict(frozen=True)


class CreateMemoryFromArousalRequest(BaseModel):
    """Request body for creating a memory via the arousal-threshold rule."""

    content: str = Field(..., min_length=1, max_length=1024)
    arousal: int = Field(..., ge=0, le=100)
    game_time: dict[str, Any] = Field(
        default_factory=lambda: {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
    )

    model_config = ConfigDict(frozen=True)


class DecayRequest(BaseModel):
    """Request body for running vividness decay."""

    decay_per_day: int = Field(default=5, ge=1)

    model_config = ConfigDict(frozen=True)


class ConsolidateRequest(BaseModel):
    """Request body for triggering memory consolidation from a dialogue session."""

    player_id: str = Field(..., min_length=1)
    game_time: dict[str, Any] = Field(
        default_factory=lambda: {"year": 1, "season": "spring", "day": 1, "time_of_day": "morning"}
    )
    turn_threshold: int = Field(default=5, ge=1)

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class MemoriesPayload(BaseModel):
    """Typed payload for GET /memories/{character_id} (SEV-16).

    The ``memories`` group is fixed; individual rows are heterogeneous graph
    records, so each stays ``dict[str, Any]``.
    """

    memories: list[dict[str, Any]]

    model_config = ConfigDict(frozen=True)


class ConsolidatePayload(BaseModel):
    """Typed payload for POST /memories/consolidate/{npc_id} (SEV-16).

    ``memory_id`` is null when the turn threshold was not met.
    """

    memory_id: str | None = None

    model_config = ConfigDict(frozen=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter(prefix="/memories", tags=["memories"])


@router.post("/decay", response_model=OkEnvelope[dict[str, Any]])
async def run_decay(
    body: DecayRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Reduce vividness of all Memory nodes by decay_per_day, clamped to 0.

    Args:
        body: decay_per_day amount (default 5).

    Returns:
        Envelope with count of affected memories.
    """
    count = await decay_all_vividness(session, decay_per_day=body.decay_per_day)
    return ok_response({"decayed_count": count})


@router.post("/from-arousal/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def seed_memory_from_arousal(
    character_id: str,
    body: CreateMemoryFromArousalRequest,
) -> dict[str, Any]:
    """Create a Memory node only if arousal exceeds the high-arousal threshold (>70).

    Args:
        character_id: ID of the character.
        body: Memory content, arousal level, and optional game-time.

    Returns:
        Envelope with memory_id if created, or null if below threshold.
    """
    gt = body.game_time
    game_time = TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )
    memory_id = await get_memory_engine().create_from_arousal(
        character_id=character_id,
        arousal=body.arousal,
        content=body.content,
        game_time=game_time,
    )
    return ok_response({"memory_id": memory_id})


@router.post("/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def seed_memory(
    character_id: str,
    body: CreateMemoryRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Create a Memory node and link it to a character.

    Args:
        character_id: ID of the character forming the memory.
        body: Memory content, vividness, emotional_charge, and optional game-time.

    Returns:
        Envelope with the new memory_id.
    """
    game_time = _time_point_from_dict(body.game_time)
    occurred = _time_point_from_dict(body.occurred_at_game_time) if body.occurred_at_game_time else None
    memory_id = await create_memory(
        session,
        character_id=character_id,
        content=body.content,
        vividness=body.vividness,
        emotional_charge=body.emotional_charge,
        game_time=game_time,
        node_id=body.id,
        occurred_at_game_time=occurred,
        is_historical=body.is_historical,
    )
    return ok_response({"memory_id": memory_id})


def _time_point_from_dict(gt: dict[str, Any]) -> TimePoint:
    """Build a TimePoint from a partial game-time dict with safe defaults."""
    return TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )


@router.get("/{character_id}", response_model=OkEnvelope[MemoriesPayload])
async def list_memories(
    character_id: str,
    k: int = 5,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List memories for a character ordered by vividness descending.

    Args:
        character_id: ID of the character.
        k: Maximum number of memories to return (default 5).

    Returns:
        Envelope with list of memory dicts.
    """
    memories = await get_memories_for_character_svc(session, character_id=character_id, k=k)
    return ok_response(MemoriesPayload(memories=memories).model_dump())


@router.delete("/{memory_id}", response_model=OkEnvelope[dict[str, Any]])
async def remove_memory(
    memory_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Hard-delete a single Memory node.

    Args:
        memory_id: ID of the Memory node to delete.

    Returns:
        Envelope confirming deletion.
    """
    await delete_memory(session, memory_id=memory_id)
    return ok_response({"memory_id": memory_id})


@router.post("/consolidate/{npc_id}", response_model=OkEnvelope[ConsolidatePayload])
async def consolidate_memories(
    npc_id: str,
    body: ConsolidateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Consolidate recent dialogue turns into a memory via the MemoryConsolidationEngine.

    Reads recent turns from the shared session store for the given npc_id + player_id
    session. If the turn count meets the threshold a new Memory node is created.

    Args:
        npc_id: ID of the NPC whose dialogue session should be consolidated.
        body: player_id, game_time, and optional turn_threshold.

    Returns:
        Envelope with memory_id if a memory was created, or null.
    """
    engine = get_memory_consolidation_engine()
    gt = body.game_time
    game_time = TimePoint(
        year=int(gt.get("year", 1)),
        season=str(gt.get("season", "spring")),
        day=int(gt.get("day", 1)),
        time_of_day=str(gt.get("time_of_day", "morning")),
    )
    memory_id = await engine.consolidate(
        npc_id=npc_id,
        game_time=game_time,
    )
    return ok_response(ConsolidatePayload(memory_id=memory_id).model_dump())
