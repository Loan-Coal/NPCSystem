"""
Unit tests for _seed_chain_quests and _seed_source_chain_quests in demo_game/seed.py.

Covers (EXP-19 slice-3):
- Happy path: _seed_chain_quests calls _seed_node and _seed_edge for each entry
- Idempotent: skips nodes that already exist (result != "created")
- Non-fatal: logs warning and continues on exception

Covers (EXP-19 slice-4):
- Happy path: _seed_source_chain_quests calls _seed_node and _seed_edge for each entry
- Idempotent: skips nodes that already exist
- Non-fatal: logs warning and continues on exception
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

from demo_game.seed import _CHAIN_QUESTS, _SOURCE_CHAIN_QUESTS, _seed_chain_quests, _seed_source_chain_quests


def _make_client() -> MagicMock:
    return MagicMock()


def test_seed_chain_quests_creates_nodes_and_edges() -> None:
    """_seed_chain_quests must call _seed_node + _seed_edge for each chain quest."""
    client = _make_client()

    with (
        patch("demo_game.seed._seed_node", return_value="created") as mock_node,
        patch("demo_game.seed._seed_edge", return_value="created") as mock_edge,
        patch("demo_game.seed._now", return_value="2026-01-01T00:00:00Z"),
    ):
        count = _seed_chain_quests(client)

    assert count == len(_CHAIN_QUESTS)
    assert mock_node.call_count == len(_CHAIN_QUESTS)
    assert mock_edge.call_count == len(_CHAIN_QUESTS)

    # Verify HAS_QUEST edges point from giver → quest
    for quest in _CHAIN_QUESTS:
        mock_edge.assert_any_call(client, "HAS_QUEST", quest["quest_giver_id"], quest["id"], {})


def test_seed_chain_quests_skips_existing_nodes() -> None:
    """_seed_chain_quests must not create HAS_QUEST edge when node already existed."""
    client = _make_client()

    with (
        patch("demo_game.seed._seed_node", return_value="skipped") as mock_node,
        patch("demo_game.seed._seed_edge") as mock_edge,
        patch("demo_game.seed._now", return_value="2026-01-01T00:00:00Z"),
    ):
        count = _seed_chain_quests(client)

    assert count == 0
    assert mock_node.call_count == len(_CHAIN_QUESTS)
    mock_edge.assert_not_called()


def test_seed_chain_quests_non_fatal_on_exception() -> None:
    """_seed_chain_quests must log warning and continue when _seed_node raises."""
    client = _make_client()

    with (
        patch("demo_game.seed._seed_node", side_effect=RuntimeError("connection refused")),
        patch("demo_game.seed._seed_edge") as mock_edge,
        patch("demo_game.seed._now", return_value="2026-01-01T00:00:00Z"),
    ):
        count = _seed_chain_quests(client)

    assert count == 0
    mock_edge.assert_not_called()


# ---------------------------------------------------------------------------
# _seed_source_chain_quests (EXP-19 slice-4)
# ---------------------------------------------------------------------------


def test_seed_source_chain_quests_creates_nodes_and_edges() -> None:
    """_seed_source_chain_quests must call _seed_node + _seed_edge for each source quest."""
    client = _make_client()

    with (
        patch("demo_game.seed._seed_node", return_value="created") as mock_node,
        patch("demo_game.seed._seed_edge", return_value="created") as mock_edge,
        patch("demo_game.seed._now", return_value="2026-01-01T00:00:00Z"),
    ):
        count = _seed_source_chain_quests(client)

    assert count == len(_SOURCE_CHAIN_QUESTS)
    assert mock_node.call_count == len(_SOURCE_CHAIN_QUESTS)
    assert mock_edge.call_count == len(_SOURCE_CHAIN_QUESTS)

    for quest in _SOURCE_CHAIN_QUESTS:
        mock_edge.assert_any_call(client, "HAS_QUEST", quest["quest_giver_id"], quest["id"], {})


def test_seed_source_chain_quests_skips_existing_nodes() -> None:
    """_seed_source_chain_quests must not create HAS_QUEST edge when node already existed."""
    client = _make_client()

    with (
        patch("demo_game.seed._seed_node", return_value="skipped") as mock_node,
        patch("demo_game.seed._seed_edge") as mock_edge,
        patch("demo_game.seed._now", return_value="2026-01-01T00:00:00Z"),
    ):
        count = _seed_source_chain_quests(client)

    assert count == 0
    assert mock_node.call_count == len(_SOURCE_CHAIN_QUESTS)
    mock_edge.assert_not_called()


def test_seed_source_chain_quests_non_fatal_on_exception() -> None:
    """_seed_source_chain_quests must log warning and continue when _seed_node raises."""
    client = _make_client()

    with (
        patch("demo_game.seed._seed_node", side_effect=RuntimeError("connection refused")),
        patch("demo_game.seed._seed_edge") as mock_edge,
        patch("demo_game.seed._now", return_value="2026-01-01T00:00:00Z"),
    ):
        count = _seed_source_chain_quests(client)

    assert count == 0
    mock_edge.assert_not_called()
