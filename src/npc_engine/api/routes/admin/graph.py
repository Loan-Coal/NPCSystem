"""
graph.py - Registry-driven generic graph_write routes.
Layer: api
Purpose: Registry-driven generic graph_write routes.  The world_state PATCH handler
         additionally applies emotion shock to NPCs at the locations of newly-active
         events (ISSUE-201, T25.4).

Does NOT: execute raw Cypher in route handlers.

Dependencies injected: GenericGraphService, EmotionUpdater (world_state path only).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from neo4j import AsyncSession
from neo4j.exceptions import DriverError, Neo4jError
from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError

from npc_engine.api.dependencies import get_db_session, get_generic_graph_service
from npc_engine.api.dependencies_stores import get_emotion_updater
from npc_engine.api.helpers import attach_warnings_meta, emit_graph_warnings
from npc_engine.api.pagination import resolve_offset_pagination
from npc_engine.api.helpers import OkEnvelope, graph_error_to_http, ok_response, require_node
from npc_engine.config import Settings, get_settings
from npc_engine.engines.emotion.emotion_updater import EmotionUpdater
from npc_engine.graph.event.event_queries import get_characters_at_location
from npc_engine.graph.generic.generic_graph_service import GenericGraphService
from npc_engine.utils.errors import NodeNotFoundError, NPCSystemError, RegistryPayloadValidationError
from npc_engine.utils.logging import get_logger

LOGGER = get_logger(__name__)

_ACTIVE_SUFFIX = "_active"
_SHOCK_ERRORS = (NPCSystemError, Neo4jError, DriverError)
_CONDITIONS_ADAPTER: TypeAdapter[list[str]] = TypeAdapter(list[str])


class NodeWriteBody(BaseModel):
    """Generic node payload wrapper for POST/PATCH operations."""

    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


class EdgeWriteBody(BaseModel):
    """Generic edge payload wrapper for POST operations."""

    src_id: str
    dst_id: str
    properties: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(frozen=True)


router = APIRouter(prefix="/graph")


@router.get("/nodes/{node_type}/{node_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_node(
    node_type: str,
    node_id: str,
    request: Request,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Return one node by type and id with extension warnings."""
    node = require_node(await service.get_node(node_type=node_type, node_id=node_id), node_type=node_type)
    warnings = service.missing_extension_warnings(node_type=node_type, node_payload=node)
    request_id = getattr(request.state, "request_id", "")
    emit_graph_warnings(warnings=warnings, request_id=request_id)
    return ok_response(node, meta=attach_warnings_meta(base_meta=None, warnings=warnings))


@router.get("/nodes/{node_type}", response_model=OkEnvelope[list[dict[str, Any]]])
async def list_nodes(
    node_type: str,
    request: Request,
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Return a paginated list of nodes for a given type with extension warnings."""
    page = resolve_offset_pagination(limit=limit, offset=offset)
    try:
        items = await service.list_nodes(node_type=node_type, limit=page.limit, offset=page.offset)
    except RegistryPayloadValidationError as error:
        raise graph_error_to_http(error) from error
    warnings: list[dict[str, Any]] = []
    for item in items:
        warnings.extend(service.missing_extension_warnings(node_type=node_type, node_payload=item))
    request_id = getattr(request.state, "request_id", "")
    emit_graph_warnings(warnings=warnings, request_id=request_id)
    return ok_response(
        items,
        meta=attach_warnings_meta(
            base_meta={
                "limit": page.limit,
                "offset": page.offset,
                "sort": page.sort,
                "strategy": page.strategy,
            },
            warnings=warnings,
        ),
    )


@router.post("/nodes/{node_type}", response_model=OkEnvelope[dict[str, Any]])
async def upsert_node(
    node_type: str,
    body: NodeWriteBody,
    request: Request,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Upsert a node by type using the registry-driven schema."""
    try:
        node = await service.upsert_node(node_type=node_type, payload=body.properties)
    except RegistryPayloadValidationError as error:
        raise graph_error_to_http(error) from error
    warnings = service.missing_extension_warnings(node_type=node_type, node_payload=node)
    request_id = getattr(request.state, "request_id", "")
    emit_graph_warnings(warnings=warnings, request_id=request_id)
    return ok_response(node, meta=attach_warnings_meta(base_meta=None, warnings=warnings))


@router.patch("/nodes/world_state/{node_id}", response_model=OkEnvelope[dict[str, Any]])
async def patch_world_state(
    node_id: str,
    body: NodeWriteBody,
    request: Request,
    service: GenericGraphService = Depends(get_generic_graph_service),
    session: AsyncSession = Depends(get_db_session),
    emotion_updater: EmotionUpdater = Depends(get_emotion_updater),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """Patch world-state fields and shock NPCs at any newly-active severe event location.

    Matches before the generic PATCH handler (FastAPI first-match routing).  The
    emotion-shock side-effect is deterministic and requires no LLM call (rule 8,
    DEC-299, ISSUE-201).  Only conditions absent before the PATCH shock (T25.8):
    callers resend the full list each time.  A shock failure after the write is
    returned as a warning in ``meta``, not a 500, since the write has landed.  The
    read of the previous conditions and the write are not atomic: two concurrent
    PATCHes can both shock (an admin route; ISSUE-385 moves this into an engine).
    """
    conditions = _parse_active_conditions(body.properties)
    previous = await service.get_node(node_type="world_state", node_id=node_id) or {}
    previously_active = set(previous.get("active_conditions") or [])
    try:
        node = await service.patch_node(node_type="world_state", node_id=node_id, payload=body.properties)
    except (NodeNotFoundError, RegistryPayloadValidationError) as error:
        raise graph_error_to_http(error) from error
    shock_warnings = await _apply_world_event_shocks(
        conditions=[c for c in conditions if c not in previously_active],
        service=service,
        session=session,
        emotion_updater=emotion_updater,
        threshold=settings.RUMOR_EMOTION_SEVERITY_THRESHOLD,
        tick=int(node.get("tick_id") or 0),
    )
    warnings = [*service.missing_extension_warnings(node_type="world_state", node_payload=node), *shock_warnings]
    emit_graph_warnings(warnings=warnings, request_id=getattr(request.state, "request_id", ""))
    return ok_response(node, meta=attach_warnings_meta(base_meta=None, warnings=warnings))


def _parse_active_conditions(properties: dict[str, Any]) -> list[str]:
    """Return ``active_conditions`` as a list of strings, or raise 422 on any other shape."""
    raw = properties.get("active_conditions")
    if raw is None:
        return []
    try:
        return _CONDITIONS_ADAPTER.validate_python(raw, strict=True)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail="active_conditions must be a list of strings") from error


async def _apply_world_event_shocks(
    conditions: list[str],
    service: GenericGraphService,
    session: AsyncSession,
    emotion_updater: EmotionUpdater,
    threshold: int,
    tick: int,
) -> list[dict[str, Any]]:
    """Shock NPCs at each location where a newly-active condition maps to a severe event.

    Returns:
        One ``EVENT_SHOCK_FAILED`` warning per NPC whose shock could not be written.
    """
    warnings: list[dict[str, Any]] = []
    for condition in dict.fromkeys(conditions):
        try:
            location_id, severity = await _severe_event_location(condition, service, threshold)
            npc_ids = await get_characters_at_location(session, location_id=location_id) if location_id else []
        except _SHOCK_ERRORS as error:
            warnings.append(_shock_warning(None, condition, error))
            continue
        for npc_id in npc_ids:
            warning = await _shock_one(emotion_updater, npc_id=npc_id, condition=condition, severity=severity, tick=tick)
            if warning is not None:
                warnings.append(warning)
    return warnings


async def _severe_event_location(
    condition: str, service: GenericGraphService, threshold: int
) -> tuple[str | None, int]:
    """Return (location_id, severity) for a condition naming a severe located event, else (None, 0)."""
    if not condition.endswith(_ACTIVE_SUFFIX):
        return None, 0
    event = await service.get_node(node_type="event", node_id=condition.removesuffix(_ACTIVE_SUFFIX))
    if event is None:
        return None, 0
    severity = int(event.get("severity") or 0)
    location_id = str(event.get("location_id") or "")
    if severity < threshold or not location_id:
        return None, 0
    return location_id, severity


async def _shock_one(
    emotion_updater: EmotionUpdater, *, npc_id: str, condition: str, severity: int, tick: int
) -> dict[str, Any] | None:
    """Shock one NPC; return a warning dict if the write fails, else None."""
    try:
        await emotion_updater.apply_event_shock(npc_id=npc_id, severity=severity, tick=tick)
    except _SHOCK_ERRORS as error:
        return _shock_warning(npc_id, condition, error)
    LOGGER.info(
        "world_event_shock npc_id=%s condition=%s severity=%d tick=%d", npc_id, condition, severity, tick,
    )
    return None


@router.patch("/nodes/{node_type}/{node_id}", response_model=OkEnvelope[dict[str, Any]])
async def patch_node(
    node_type: str,
    node_id: str,
    body: NodeWriteBody,
    request: Request,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Patch specific fields on an existing node by type and id."""
    try:
        node = await service.patch_node(node_type=node_type, node_id=node_id, payload=body.properties)
    except (NodeNotFoundError, RegistryPayloadValidationError) as error:
        raise graph_error_to_http(error) from error
    warnings = service.missing_extension_warnings(node_type=node_type, node_payload=node)
    request_id = getattr(request.state, "request_id", "")
    emit_graph_warnings(warnings=warnings, request_id=request_id)
    return ok_response(node, meta=attach_warnings_meta(base_meta=None, warnings=warnings))


@router.get("/edges/{edge_type}/{src_id}/{dst_id}", response_model=OkEnvelope[dict[str, Any]])
async def get_edge(
    edge_type: str,
    src_id: str,
    dst_id: str,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Return one edge by type, source, and destination ids."""
    edge = require_node(await service.get_edge(edge_type=edge_type, src_id=src_id, dst_id=dst_id), node_type=edge_type)
    return ok_response(edge)


@router.get("/edges/{edge_type}", response_model=OkEnvelope[list[dict[str, Any]]])
async def list_edges(
    edge_type: str,
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    src_id: str | None = Query(default=None),
    dst_id: str | None = Query(default=None),
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Return a paginated list of edges for a given type with optional src/dst filters."""
    page = resolve_offset_pagination(limit=limit, offset=offset)
    try:
        edges = await service.list_edges(
            edge_type=edge_type,
            limit=page.limit,
            offset=page.offset,
            src_id=src_id,
            dst_id=dst_id,
        )
    except RegistryPayloadValidationError as error:
        raise graph_error_to_http(error) from error
    return ok_response(
        edges,
        meta={
            "limit": page.limit,
            "offset": page.offset,
            "sort": page.sort,
            "strategy": page.strategy,
        },
    )


@router.post("/edges/{edge_type}", response_model=OkEnvelope[dict[str, Any]])
async def upsert_edge(
    edge_type: str,
    body: EdgeWriteBody,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Upsert an edge between two existing nodes using the registry-driven schema."""
    try:
        edge = await service.upsert_edge(
            edge_type=edge_type,
            src_id=body.src_id,
            dst_id=body.dst_id,
            payload=body.properties,
        )
    except (NodeNotFoundError, RegistryPayloadValidationError) as error:
        raise graph_error_to_http(error) from error
    return ok_response(edge)


@router.delete("/edges/{edge_type}/{src_id}/{dst_id}", response_model=OkEnvelope[dict[str, Any]])
async def delete_edge(
    edge_type: str,
    src_id: str,
    dst_id: str,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict[str, Any]:
    """Delete an edge by type, source, and destination ids."""
    deleted = await service.delete_edge(edge_type=edge_type, src_id=src_id, dst_id=dst_id)
    return ok_response({"deleted": deleted})


def _shock_warning(npc_id: str | None, condition: str, error: Exception) -> dict[str, Any]:
    """Log a failed shock step with its traceback and return its EVENT_SHOCK_FAILED warning."""
    LOGGER.warning("world_event_shock_failed npc_id=%s condition=%s", npc_id, condition, exc_info=error)
    return {
        "warning_code": "EVENT_SHOCK_FAILED",
        "type": "event_shock",
        "npc_id": npc_id,
        "condition": condition,
        "error": type(error).__name__,
    }
