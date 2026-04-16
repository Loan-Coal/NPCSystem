"""
graph.py - v1 graph_write routes for core graph resources.

Does NOT: execute raw Cypher in route handlers.

Dependencies injected: GraphEditService.
"""

from fastapi import APIRouter, Depends, HTTPException, Query

from api.dependencies import get_graph_edit_service
from api.schemas import (
    CharacterMoveBody,
    CharacterPatchBody,
    EventPatchBody,
    KnowsAboutEdgeBody,
    LocatedAtEdgeBody,
    LocationPatchBody,
    ParticipatedInEdgeBody,
    RelatesToEdgeBody,
    WorldStatePatchBody,
)
from graph.graph_edit_service import GraphEditService
from graph.node_schemas import CharacterNode, EventNode, LocationNode
from utils.errors import ImmutableFieldError, NodeNotFoundError, SchemaValidationError


router = APIRouter(prefix="/graph")


@router.get("/characters/{character_id}")
async def get_character(character_id: str, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    node = await service.get_character(character_id=character_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"success": True, "data": node, "meta": None}


@router.get("/characters")
async def list_characters(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    items = await service.list_characters(limit=limit, offset=offset)
    return {"success": True, "data": items, "meta": {"limit": limit, "offset": offset}}


@router.post("/characters")
async def upsert_character(character: CharacterNode, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    await service.upsert_character(character=character)
    return {"success": True, "data": {"id": character.id}, "meta": None}


@router.patch("/characters/{character_id}")
async def patch_character(
    character_id: str,
    body: CharacterPatchBody,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    try:
        node = await service.patch_character(character_id=character_id, body=body)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ImmutableFieldError, SchemaValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"success": True, "data": node, "meta": None}


@router.delete("/characters/{character_id}")
async def soft_delete_character(character_id: str, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    try:
        await service.soft_delete_character(character_id=character_id)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": {"id": character_id, "deleted": True}, "meta": None}


@router.post("/characters/{character_id}/move")
async def move_character(
    character_id: str,
    body: CharacterMoveBody,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    try:
        await service.move_character(character_id=character_id, location_id=body.location_id)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": {"id": character_id, "location_id": body.location_id}, "meta": None}


@router.get("/events/{event_id}")
async def get_event(event_id: str, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    node = await service.get_event(event_id=event_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return {"success": True, "data": node, "meta": None}


@router.get("/events")
async def list_events(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    items = await service.list_events(limit=limit, offset=offset)
    return {"success": True, "data": items, "meta": {"limit": limit, "offset": offset}}


@router.post("/events")
async def upsert_event(event: EventNode, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    await service.upsert_event(event=event)
    return {"success": True, "data": {"id": event.id}, "meta": None}


@router.patch("/events/{event_id}")
async def patch_event(event_id: str, body: EventPatchBody, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    try:
        node = await service.patch_event(event_id=event_id, body=body)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ImmutableFieldError, SchemaValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"success": True, "data": node, "meta": None}


@router.get("/locations/{location_id}")
async def get_location(location_id: str, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    node = await service.get_location(location_id=location_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Location not found")
    return {"success": True, "data": node, "meta": None}


@router.get("/locations")
async def list_locations(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    items = await service.list_locations(limit=limit, offset=offset)
    return {"success": True, "data": items, "meta": {"limit": limit, "offset": offset}}


@router.post("/locations")
async def upsert_location(location: LocationNode, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    await service.upsert_location(location=location)
    return {"success": True, "data": {"id": location.id}, "meta": None}


@router.patch("/locations/{location_id}")
async def patch_location(
    location_id: str,
    body: LocationPatchBody,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    try:
        node = await service.patch_location(location_id=location_id, body=body)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (ImmutableFieldError, SchemaValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return {"success": True, "data": node, "meta": None}


@router.patch("/world_state")
async def patch_world_state(body: WorldStatePatchBody, service: GraphEditService = Depends(get_graph_edit_service)) -> dict:
    node = await service.patch_world_state(body=body)
    return {"success": True, "data": node, "meta": None}


@router.post("/edges/relates_to")
async def upsert_relates_to_edge(
    body: RelatesToEdgeBody,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    try:
        edge = await service.upsert_relates_to_edge(body=body)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": edge, "meta": None}


@router.post("/edges/knows_about")
async def upsert_knows_about_edge(
    body: KnowsAboutEdgeBody,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    try:
        edge = await service.upsert_knows_about_edge(body=body)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": edge, "meta": None}


@router.post("/edges/located_at")
async def upsert_located_at_edge(
    body: LocatedAtEdgeBody,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    try:
        edge = await service.upsert_located_at_edge(body=body)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": edge, "meta": None}


@router.post("/edges/participated_in")
async def upsert_participated_in_edge(
    body: ParticipatedInEdgeBody,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    try:
        edge = await service.upsert_participated_in_edge(body=body)
    except NodeNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {"success": True, "data": edge, "meta": None}


@router.delete("/edges/relates_to/{src_id}/{dst_id}")
async def delete_relates_to_edge(
    src_id: str,
    dst_id: str,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    deleted = await service.delete_relates_to_edge(src_id=src_id, dst_id=dst_id)
    return {"success": True, "data": {"deleted": deleted}, "meta": None}


@router.delete("/edges/knows_about/{character_id}/{event_id}")
async def delete_knows_about_edge(
    character_id: str,
    event_id: str,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    deleted = await service.delete_knows_about_edge(character_id=character_id, event_id=event_id)
    return {"success": True, "data": {"deleted": deleted}, "meta": None}


@router.delete("/edges/located_at/{character_id}/{location_id}")
async def delete_located_at_edge(
    character_id: str,
    location_id: str,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    deleted = await service.delete_located_at_edge(character_id=character_id, location_id=location_id)
    return {"success": True, "data": {"deleted": deleted}, "meta": None}


@router.delete("/edges/participated_in/{character_id}/{event_id}")
async def delete_participated_in_edge(
    character_id: str,
    event_id: str,
    service: GraphEditService = Depends(get_graph_edit_service),
) -> dict:
    deleted = await service.delete_participated_in_edge(character_id=character_id, event_id=event_id)
    return {"success": True, "data": {"deleted": deleted}, "meta": None}
