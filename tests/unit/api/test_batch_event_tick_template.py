"""
Module: test_batch_event_tick_template
Layer: tests/unit/api
Purpose: Verify POST /v1/admin/batch/event_tick forwards an optional template_id to the
         event handler and maps an unknown template to 422.
Does NOT: touch Neo4j or run the real EventHandler.
Dependencies: unittest.mock.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from npc_engine.api.routes.admin.batch import EventTickRequest, run_event_tick
from npc_engine.utils.errors import EventTemplateNotFoundError


def _clock() -> MagicMock:
    clock = MagicMock()
    clock.current_tick = 3
    return clock


async def test_template_id_is_forwarded_to_the_handler() -> None:
    handler = MagicMock()
    handler.run_tick = AsyncMock(return_value={"tick_id": 3, "created": 1})

    await run_event_tick(
        EventTickRequest(template_id="evt_21_iron_legion_advance", tick_override=3),
        event_handler=handler,
        clock=_clock(),
    )

    assert handler.run_tick.await_args.kwargs["template_id"] == "evt_21_iron_legion_advance"


async def test_unknown_template_id_returns_422() -> None:
    handler = MagicMock()
    handler.run_tick = AsyncMock(side_effect=EventTemplateNotFoundError(template_id="evt_nope"))

    with pytest.raises(HTTPException) as exc_info:
        await run_event_tick(
            EventTickRequest(template_id="evt_nope", tick_override=3),
            event_handler=handler,
            clock=_clock(),
        )

    assert exc_info.value.status_code == 422


def test_empty_template_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        EventTickRequest(template_id="")
