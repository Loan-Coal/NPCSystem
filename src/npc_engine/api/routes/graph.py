"""
graph.py - Registry-driven generic graph_write routes.

Does NOT: execute raw Cypher in route handlers.

Dependencies injected: GenericGraphService.
"""

from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from npc_engine.api.dependencies import get_generic_graph_service
from npc_engine.api.graph_warning_helpers import attach_warnings_meta, emit_graph_warnings
from npc_engine.api.pagination import resolve_offset_pagination
from npc_engine.api.route_helpers import graph_error_to_http, ok_response, require_node
from npc_engine.graph.generic_graph_service import GenericGraphService
from npc_engine.utils.errors import NodeNotFoundError, RegistryPayloadValidationError


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


@router.get("/nodes/{node_type}/{node_id}")
async def get_node(
    node_type: str,
    node_id: str,
    request: Request,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
    """Return one node by type and id with extension warnings."""
    node = require_node(await service.get_node(node_type=node_type, node_id=node_id), node_type=node_type)
    warnings = service.missing_extension_warnings(node_type=node_type, node_payload=node)
    request_id = getattr(request.state, "request_id", "")
    emit_graph_warnings(warnings=warnings, request_id=request_id)
    return ok_response(node, meta=attach_warnings_meta(base_meta=None, warnings=warnings))


@router.get("/nodes/{node_type}")
async def list_nodes(
    node_type: str,
    request: Request,
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
    """Return a paginated list of nodes for a given type with extension warnings."""
    page = resolve_offset_pagination(limit=limit, offset=offset)
    items = await service.list_nodes(node_type=node_type, limit=page.limit, offset=page.offset)
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


@router.post("/nodes/{node_type}")
async def upsert_node(
    node_type: str,
    body: NodeWriteBody,
    request: Request,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
    """Upsert a node by type using the registry-driven schema."""
    try:
        node = await service.upsert_node(node_type=node_type, payload=body.properties)
    except RegistryPayloadValidationError as error:
        raise graph_error_to_http(error) from error
    warnings = service.missing_extension_warnings(node_type=node_type, node_payload=node)
    request_id = getattr(request.state, "request_id", "")
    emit_graph_warnings(warnings=warnings, request_id=request_id)
    return ok_response(node, meta=attach_warnings_meta(base_meta=None, warnings=warnings))


@router.patch("/nodes/{node_type}/{node_id}")
async def patch_node(
    node_type: str,
    node_id: str,
    body: NodeWriteBody,
    request: Request,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
    """Patch specific fields on an existing node by type and id."""
    try:
        node = await service.patch_node(node_type=node_type, node_id=node_id, payload=body.properties)
    except (NodeNotFoundError, RegistryPayloadValidationError) as error:
        raise graph_error_to_http(error) from error
    warnings = service.missing_extension_warnings(node_type=node_type, node_payload=node)
    request_id = getattr(request.state, "request_id", "")
    emit_graph_warnings(warnings=warnings, request_id=request_id)
    return ok_response(node, meta=attach_warnings_meta(base_meta=None, warnings=warnings))


@router.get("/edges/{edge_type}/{src_id}/{dst_id}")
async def get_edge(
    edge_type: str,
    src_id: str,
    dst_id: str,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
    """Return one edge by type, source, and destination ids."""
    edge = require_node(await service.get_edge(edge_type=edge_type, src_id=src_id, dst_id=dst_id), node_type=edge_type)
    return ok_response(edge)


@router.get("/edges/{edge_type}")
async def list_edges(
    edge_type: str,
    limit: int | None = Query(default=None, ge=1),
    offset: int | None = Query(default=None, ge=0),
    src_id: str | None = Query(default=None),
    dst_id: str | None = Query(default=None),
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
    """Return a paginated list of edges for a given type with optional src/dst filters."""
    page = resolve_offset_pagination(limit=limit, offset=offset)
    edges = await service.list_edges(
        edge_type=edge_type,
        limit=page.limit,
        offset=page.offset,
        src_id=src_id,
        dst_id=dst_id,
    )
    return ok_response(
        edges,
        meta={
            "limit": page.limit,
            "offset": page.offset,
            "sort": page.sort,
            "strategy": page.strategy,
        },
    )


@router.post("/edges/{edge_type}")
async def upsert_edge(
    edge_type: str,
    body: EdgeWriteBody,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
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


@router.delete("/edges/{edge_type}/{src_id}/{dst_id}")
async def delete_edge(
    edge_type: str,
    src_id: str,
    dst_id: str,
    service: GenericGraphService = Depends(get_generic_graph_service),
) -> dict:
    """Delete an edge by type, source, and destination ids."""
    deleted = await service.delete_edge(edge_type=edge_type, src_id=src_id, dst_id=dst_id)
    return ok_response({"deleted": deleted})
