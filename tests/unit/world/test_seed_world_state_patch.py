"""
Module: test_seed_world_state_patch
Layer: tests/unit
Purpose: Verify that _force_patch_world_state always calls patch_node with
         the correct epoch and active_conditions even when the world_state node
         already exists (skip path in _seed_node).
Dependencies: demo_game.seed, unittest.mock
Used by: pytest
"""
from __future__ import annotations

from unittest.mock import MagicMock, call

from demo_game.seeds.seed import _force_patch_world_state


def test_force_patch_world_state_calls_patch_node_with_war_epoch() -> None:
    """patch_node is called once with epoch=war and active_conditions=[northern_war]."""
    mock_client = MagicMock()
    mock_client.get_node.return_value = {
        "id": "world",
        "epoch": "age_of_peace",
        "active_conditions": [],
    }
    mock_client.patch_node.return_value = {
        "id": "world",
        "epoch": "war",
        "active_conditions": ["northern_war"],
    }

    _force_patch_world_state(mock_client)

    assert mock_client.patch_node.call_count == 1
    args, kwargs = mock_client.patch_node.call_args
    node_type, node_id, properties = args
    assert node_type == "world_state"
    assert node_id == "world"
    assert properties["epoch"] == "war"
    assert properties["active_conditions"] == ["northern_war"]


def test_force_patch_world_state_always_patches_even_when_node_absent() -> None:
    """patch_node is also called when get_node returns None (fresh seed)."""
    mock_client = MagicMock()
    mock_client.get_node.return_value = None
    mock_client.patch_node.return_value = {
        "id": "world",
        "epoch": "war",
        "active_conditions": ["northern_war"],
    }

    _force_patch_world_state(mock_client)

    assert mock_client.patch_node.call_count == 1
    _, _, properties = mock_client.patch_node.call_args[0]
    assert properties["epoch"] == "war"
    assert properties["active_conditions"] == ["northern_war"]
