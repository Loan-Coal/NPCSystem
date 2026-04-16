"""
graph_admin.py - v1 graph_admin routes for privileged graph operations.

Does NOT: perform authentication itself.

Dependencies injected: GraphAdminService.
"""

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.dependencies import get_embedding_index, get_graph_admin_service
from graph.graph_admin_service import GraphAdminService
from retrieval.embedding_index import EmbeddingIndex
from utils.errors import NodeNotFoundError


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


_REINDEX_JOBS: dict[str, dict] = {}


async def _run_reindex_job(job_id: str, npc_ids: list[str], embedding_index: EmbeddingIndex) -> None:
    """Execute in-memory reindex work asynchronously and update job status."""

    job = _REINDEX_JOBS.get(job_id)
    if job is None:
        return

    job["status"] = "running"
    job["started_at"] = datetime.now(timezone.utc).isoformat()
    try:
        for npc_id in npc_ids:
            await embedding_index.invalidate(item_id=npc_id)
        job["status"] = "completed"
        job["processed_ids"] = list(npc_ids)
        job["failed_count"] = 0
    except Exception as error:
        job["status"] = "failed"
        job["error"] = str(error)
        job["failed_count"] = 1
    finally:
        job["finished_at"] = datetime.now(timezone.utc).isoformat()


router = APIRouter(prefix="/graph/admin")


@router.delete("/characters/{character_id}")
async def hard_delete_character(character_id: str, service: GraphAdminService = Depends(get_graph_admin_service)) -> dict:
    try:
        data = await service.hard_delete_character(character_id=character_id)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": data, "meta": None}


@router.delete("/events/{event_id}")
async def hard_delete_event(event_id: str, service: GraphAdminService = Depends(get_graph_admin_service)) -> dict:
    try:
        data = await service.hard_delete_event(event_id=event_id)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": data, "meta": None}


@router.delete("/locations/{location_id}")
async def hard_delete_location(location_id: str, service: GraphAdminService = Depends(get_graph_admin_service)) -> dict:
    try:
        data = await service.hard_delete_location(location_id=location_id)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": data, "meta": None}


@router.put("/relations/absolute")
async def set_relation_absolute(
    request: AbsoluteRelationRequest,
    service: GraphAdminService = Depends(get_graph_admin_service),
) -> dict:
    try:
        data = await service.set_relation_absolute(
            src_id=request.src_id,
            dst_id=request.dst_id,
            trust=request.trust,
            fear=request.fear,
            affection=request.affection,
        )
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": data, "meta": None}


@router.post("/relations/delta")
async def apply_relation_delta(
    request: DeltaRelationRequest,
    service: GraphAdminService = Depends(get_graph_admin_service),
) -> dict:
    try:
        data, clamped_fields = await service.apply_unbounded_relation_delta(
            src_id=request.src_id,
            dst_id=request.dst_id,
            trust_delta=request.trust,
            fear_delta=request.fear,
            affection_delta=request.affection,
        )
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": data, "meta": {"clamped_fields": clamped_fields}}


@router.post("/reindex", status_code=202)
async def submit_reindex(
    request: ReindexRequest,
    embedding_index: EmbeddingIndex = Depends(get_embedding_index),
) -> dict:
    job_id = str(uuid4())
    submitted_at = datetime.now(timezone.utc).isoformat()
    target_ids = request.npc_ids

    _REINDEX_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "submitted_at": submitted_at,
        "processed_ids": [],
        "failed_count": 0,
    }
    asyncio.create_task(_run_reindex_job(job_id=job_id, npc_ids=target_ids, embedding_index=embedding_index))
    return {"success": True, "data": {"job_id": job_id}, "meta": {"status": "accepted"}}


@router.get("/reindex/{job_id}")
async def get_reindex_job(job_id: str) -> dict:
    job = _REINDEX_JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"success": True, "data": job, "meta": None}


@router.get("/audit_log")
async def audit_log(limit: int = 100) -> dict:
    """Return placeholder audit entries until persistent audit storage is implemented."""

    return {
        "success": True,
        "data": [],
        "meta": {"limit": limit, "note": "persistent audit log pending"},
    }
