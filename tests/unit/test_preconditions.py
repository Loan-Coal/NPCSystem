"""
test_preconditions.py — Unit tests for the eval clean-state + precondition guard.

Covers (evals/preconditions.py):
- reset_world PATCHes world_state with the declared baseline body; raises on non-200
- ensure_player_node POSTs a player Character on 404; is a no-op on 200
- assert_preconditions raises on a missing node / empty edge
- prepare runs reset -> ensure_player_node -> assert_preconditions in order
- WorldBaseline rejects an unknown epoch literal
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

# evals/ is on pytest's pythonpath via pyproject.
from preconditions import (
    PreconditionError,
    Preconditions,
    WorldBaseline,
    assert_preconditions,
    ensure_player_node,
    prepare,
    reset_world,
)


def _resp(status: int, body: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = body if body is not None else {}
    return r


def test_reset_world_patches_baseline_body() -> None:
    client = MagicMock()
    client.patch.return_value = _resp(200)
    reset_world(client, "", WorldBaseline())
    _, kwargs = client.patch.call_args
    assert kwargs["json"] == {"properties": {"epoch": "age_of_peace", "active_conditions": []}}


def test_reset_world_raises_on_non_200() -> None:
    client = MagicMock()
    client.patch.return_value = _resp(500)
    with pytest.raises(PreconditionError) as exc:
        reset_world(client, "", WorldBaseline())
    assert exc.value.kind == "world_condition"


def test_ensure_player_node_creates_on_404() -> None:
    client = MagicMock()
    client.get.return_value = _resp(404)
    client.post.return_value = _resp(200)
    ensure_player_node(client, "", "player_eval")
    _, kwargs = client.post.call_args
    props = kwargs["json"]["properties"]
    assert props["id"] == "player_eval"
    assert props["is_player"] is True


def test_ensure_player_node_noop_on_200() -> None:
    client = MagicMock()
    client.get.return_value = _resp(200)
    ensure_player_node(client, "", "player_demo")
    client.post.assert_not_called()


def test_assert_preconditions_raises_on_missing_node() -> None:
    client = MagicMock()
    client.get.return_value = _resp(404)
    pre = Preconditions(required_nodes=(("Character", "ghost"),))
    with pytest.raises(PreconditionError) as exc:
        assert_preconditions(client, "", pre)
    assert exc.value.kind == "node"
    assert "Character:ghost" in exc.value.missing


def test_assert_preconditions_raises_on_empty_edge() -> None:
    client = MagicMock()
    client.get.return_value = _resp(200, {"data": []})
    pre = Preconditions(required_edges=("KNOWS_ABOUT",))
    with pytest.raises(PreconditionError) as exc:
        assert_preconditions(client, "", pre)
    assert exc.value.kind == "edge"


def test_prepare_runs_reset_then_player_then_assert() -> None:
    client = MagicMock()
    client.patch.return_value = _resp(200)
    client.get.return_value = _resp(200, {"data": [{"id": "x"}]})
    prepare(client, "", baseline=WorldBaseline(), pre=Preconditions(player_id="player_demo"))
    method_order = [c[0] for c in client.method_calls]
    assert method_order[0] == "patch"  # reset_world first
    assert "get" in method_order  # ensure_player_node + asserts query


def test_worldbaseline_rejects_bad_epoch() -> None:
    with pytest.raises(ValidationError):
        WorldBaseline(epoch="apocalypse")
