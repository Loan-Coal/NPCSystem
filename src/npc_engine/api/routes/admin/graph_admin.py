"""
graph_admin.py - v1 graph_admin routes for privileged graph operations.
Layer: api
Purpose: v1 graph_admin routes for privileged graph operations.

Does NOT: perform authentication itself.

Dependencies injected: GraphAdminService.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_embedding_index, get_graph_admin_service, get_reindex_job_service
from npc_engine.api.helpers import OkEnvelope, graph_error_to_http, ok_response
from npc_engine.graph.graph_admin_service import GraphAdminService
from npc_engine.retrieval.graph_rag.reindex_job_service import ReindexJobService
from npc_engine.retrieval.embedding import EmbeddingIndex
from npc_engine.utils.errors import NodeNotFoundError


class AbsoluteRelationRequest(BaseModel):
    """Admin absolute relation set request."""

    src_id: str
    dst_id: str
    trust: int = Field(ge=0, le=100)
    fear: int = Field(ge=0, le=100)
    affection: int = Field(ge=0, le=100)

    model_config = ConfigDict(frozen=True)


class DeltaRelationRequest(BaseModel):
    """Admin unbounded relation delta request."""

    src_id: str
    dst_id: str
    trust: int = 0
    fear: int = 0
    affection: int = 0

    model_config = ConfigDict(frozen=True)


class ReindexRequest(BaseModel):
    """Admin reindex submission request."""

    npc_ids: list[str] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


router = APIRouter(prefix="/graph")


@router.delete("/characters/{character_id}", response_model=OkEnvelope[dict[str, Any]])
async def hard_delete_character(character_id: str, service: GraphAdminService = Depends(get_graph_admin_service)) -> dict[str, Any]:
    """Hard-delete a character and all associated edges from the graph."""
    try:
        data = await service.hard_delete_character(character_id=character_id)
    except NodeNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(data)


@router.delete("/events/{event_id}", response_model=OkEnvelope[dict[str, Any]])
async def hard_delete_event(event_id: str, service: GraphAdminService = Depends(get_graph_admin_service)) -> dict[str, Any]:
    """Hard-delete an event and all associated edges from the graph."""
    try:
        data = await service.hard_delete_event(event_id=event_id)
    except NodeNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(data)


@router.delete("/locations/{location_id}", response_model=OkEnvelope[dict[str, Any]])
async def hard_delete_location(location_id: str, service: GraphAdminService = Depends(get_graph_admin_service)) -> dict[str, Any]:
    """Hard-delete a location and all associated edges from the graph."""
    try:
        data = await service.hard_delete_location(location_id=location_id)
    except NodeNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(data)


@router.put("/relations/absolute", response_model=OkEnvelope[dict[str, Any]])
async def set_relation_absolute(
    request: AbsoluteRelationRequest,
    service: GraphAdminService = Depends(get_graph_admin_service),
) -> dict[str, Any]:
    """Set absolute relation values between two characters, bypassing delta constraints."""
    try:
        data = await service.set_relation_absolute(
            src_id=request.src_id,
            dst_id=request.dst_id,
            trust=request.trust,
            fear=request.fear,
            affection=request.affection,
        )
    except NodeNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(data)


@router.post("/relations/delta", response_model=OkEnvelope[dict[str, Any]])
async def apply_relation_delta(
    request: DeltaRelationRequest,
    service: GraphAdminService = Depends(get_graph_admin_service),
) -> dict[str, Any]:
    """Apply an unbounded admin relation delta and return clamped field metadata."""
    try:
        data, clamped_fields = await service.apply_unbounded_relation_delta(
            src_id=request.src_id,
            dst_id=request.dst_id,
            trust_delta=request.trust,
            fear_delta=request.fear,
            affection_delta=request.affection,
        )
    except NodeNotFoundError as error:
        raise graph_error_to_http(error) from error
    return ok_response(data, meta={"clamped_fields": clamped_fields})


@router.post("/reindex", status_code=202, response_model=OkEnvelope[dict[str, Any]])
async def submit_reindex(
    request: ReindexRequest,
    embedding_index: EmbeddingIndex = Depends(get_embedding_index),
    reindex_jobs: ReindexJobService = Depends(get_reindex_job_service),
) -> dict[str, Any]:
    """Submit an async reindex job for the given NPC ids and return a job id."""
    job_id = reindex_jobs.submit_reindex(npc_ids=request.npc_ids, embedding_index=embedding_index)
    return ok_response({"job_id": job_id}, meta={"status": "accepted"})


@router.get("/reindex/{job_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_reindex_job(job_id: str, reindex_jobs: ReindexJobService = Depends(get_reindex_job_service)) -> dict[str, Any]:
    """Return the status of a previously submitted reindex job."""
    job = reindex_jobs.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return ok_response(job)


@router.get("/audit_log", response_model=OkEnvelope[list[dict[str, Any]]])
async def audit_log(limit: int = 100) -> dict[str, Any]:
    """Return placeholder audit entries until persistent audit storage is implemented."""

    return ok_response([], meta={"limit": limit, "note": "persistent audit log pending"})
