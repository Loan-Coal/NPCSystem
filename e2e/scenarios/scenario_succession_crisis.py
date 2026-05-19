"""
E2E scenario: Succession Crisis (Phase 7.2).

Seeds a title with a holder and an heir. Removes the HOLDS_TITLE edge to simulate
the holder's death, then runs the SuccessionEngine to verify the heir is granted the title.
Uses mock graph layer to avoid live DB dependency.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.engines.succession.succession_engine import SuccessionEngine


@pytest.mark.asyncio
async def test_succession_crisis_heir_granted_title():
    """After the holder 'dies' (HOLDS_TITLE removed), the heir receives the title."""
    session = AsyncMock()
    engine = SuccessionEngine()

    title_id = "title-duke-iron"
    faction_id = "faction-ironclad"
    heir_id = "char-young-lord"

    vacant_title = {
        "id": title_id,
        "name": "Duke of Iron",
        "faction_id": faction_id,
        "is_inheritable": True,
        "power": 80,
    }
    heir_data = [{"heir": {"id": heir_id}, "priority": 1, "legitimacy": 75}]

    with (
        patch(
            "npc_engine.engines.succession.succession_engine.get_vacant_inheritable_titles",
            new=AsyncMock(return_value=[vacant_title]),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.get_heirs_for_character",
            new=AsyncMock(return_value=heir_data),
        ),
        patch(
            "npc_engine.engines.succession.succession_engine.grant_title",
            new=AsyncMock(),
        ) as mock_grant,
    ):
        result = await engine.run_tick(session, tick_id=42)

    assert result["successions"] == 1
    mock_grant.assert_called_once()
    call_kwargs = mock_grant.call_args.kwargs
    assert call_kwargs["character_id"] == heir_id
    assert call_kwargs["title_id"] == title_id
    assert call_kwargs["tick"] == 42
