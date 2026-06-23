"""
Module: chapters
Layer: api
Purpose: Read-only HTTP route for the current open chapter node (Phase H0.4).
Does NOT: run chapter transitions or call LLMs.
Dependencies: graph.chapter_queries.get_current_chapter,
              api.dependencies.get_db_session, api.route_helpers.
Dependencies injected: AsyncSession (via FastAPI Depends).
Used by: npc_engine.api.router_registry (registered at API_V1_PREFIX).

Note: ChapterEngine has no dedicated read method — it is a tick-driven writer.
The clean read is graph.chapter_queries.get_current_chapter which is a pure
graph reader. Calling it directly from the route is correct per the layer model
(api → graph is allowed). See DECISIONS.md note on H0.4.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from neo4j import AsyncSession
from pydantic import BaseModel, ConfigDict

from npc_engine.api.dependencies import get_db_session
from npc_engine.api.helpers import OkEnvelope, ok_response
from npc_engine.graph.narrative.chapter_queries import get_current_chapter

router = APIRouter(prefix="/chapters", tags=["chapters"])


class ChapterPayload(BaseModel):
    """Typed response payload for GET /chapters/current (SEV-16).

    Mirrors the fields returned by graph.chapter_queries.get_current_chapter.
    """

    id: str
    name: str
    started_at_tick: int
    theme: str | None = None
    status: str

    model_config = ConfigDict(frozen=True)


@router.get("/current", response_model=OkEnvelope[ChapterPayload])
async def get_current_chapter_route(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return the currently open chapter node.

    Reads the most recently opened CHAPTER node from the graph (status='open').
    ChapterEngine has no read method — it is a tick-driven writer; the graph
    reader (graph.chapter_queries.get_current_chapter) is the correct call site.

    Args:
        session: Scoped Neo4j session injected by FastAPI.

    Returns:
        JSON envelope with id, name, started_at_tick, theme, and status fields.

    Raises:
        HTTPException 404: When no chapter node with status='open' exists yet.
    """
    chapter = await get_current_chapter(session)
    if chapter is None:
        raise HTTPException(status_code=404, detail="No open chapter found")
    return ok_response(ChapterPayload(**chapter).model_dump())
