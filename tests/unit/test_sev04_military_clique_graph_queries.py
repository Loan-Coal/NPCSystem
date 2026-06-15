"""
SEV-04 regression: military and clique Cypher must live in graph/, not engines/.

Verifies that:
- emit_battle_event exists in graph.military_writer and is called by the
  engine's _emit_battle_event (session.run not called on the engine side).
- get_high_affection_pairs, get_existing_shared_group, get_stale_cliques exist
  in graph.group_queries and are called by CliqueFormationEngine.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Military — emit_battle_event lives in graph layer
# ---------------------------------------------------------------------------


def test_emit_battle_event_importable_from_graph():
    """emit_battle_event must be importable from graph.military_writer."""
    from npc_engine.graph.military_writer import emit_battle_event  # noqa: F401

    assert callable(emit_battle_event)


@pytest.mark.asyncio
async def test_military_battle_service_delegates_to_graph_emit():
    """_emit_battle_event must call graph.emit_battle_event, not session.run."""
    mock_session = AsyncMock()

    with patch(
        "npc_engine.engines.military.military_battle_service.emit_battle_event",
        new_callable=AsyncMock,
    ) as mock_emit:
        from npc_engine.engines.military.military_battle_service import (
            _emit_battle_event,
        )

        await _emit_battle_event(
            mock_session,
            location_id="loc-1",
            winner_faction_id="faction-a",
            loser_faction_id="faction-b",
            tick_id=5,
        )

    mock_emit.assert_awaited_once()
    mock_session.run.assert_not_called()


# ---------------------------------------------------------------------------
# Clique — graph wrapper functions live in graph layer
# ---------------------------------------------------------------------------


def test_clique_graph_wrappers_importable():
    """get_high_affection_pairs, get_existing_shared_group, get_stale_cliques
    must be importable from graph.group_queries."""
    from npc_engine.graph.group_queries import (  # noqa: F401
        get_existing_shared_group,
        get_high_affection_pairs,
        get_stale_cliques,
    )

    assert callable(get_high_affection_pairs)
    assert callable(get_existing_shared_group)
    assert callable(get_stale_cliques)


@pytest.mark.asyncio
async def test_clique_engine_calls_graph_get_high_affection_pairs():
    """CliqueFormationEngine must delegate pair lookup to the graph layer via its port.

    Post-SEV-24 the engine imports no graph symbol at all — it depends on the injected
    GroupGraphPort (whose Neo4j adapter lives in graph/), so the delegation guarantee is
    even stronger.
    """
    settings = MagicMock()
    settings.CLIQUE_FORMATION_TICK_INTERVAL = 5
    settings.CLIQUE_AFFECTION_THRESHOLD = 70
    settings.CLIQUE_INITIAL_COHESION = 10
    settings.CLIQUE_STALE_AGE_TICKS = 50

    from npc_engine.engines.clique.clique_formation_engine import CliqueFormationEngine

    repo = AsyncMock()
    repo.get_high_affection_pairs = AsyncMock(return_value=[])
    repo.get_stale_cliques = AsyncMock(return_value=[])

    engine = CliqueFormationEngine(settings=settings, group_repo=repo)
    await engine.run_tick(tick_id=5)

    repo.get_high_affection_pairs.assert_awaited_once()
