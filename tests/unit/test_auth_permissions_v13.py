"""
test_auth_permissions_v13.py - Unit tests for scope inheritance and path-to-scope mapping.

Does NOT: exercise full HTTP middleware pipeline.

Dependencies injected: None.
"""

import pytest
pytest.importorskip("neo4j")

from npc_engine.auth.middleware import _required_scope_for_path
from npc_engine.auth.permissions import SCOPE_GRAPH_ADMIN, SCOPE_GRAPH_WRITE, has_scope


def test_scope_inheritance_admin_includes_write() -> None:
    """Admin scope should satisfy write-level permissions."""

    assert has_scope(granted_scope=SCOPE_GRAPH_ADMIN, required_scope=SCOPE_GRAPH_WRITE)
    assert has_scope(granted_scope=SCOPE_GRAPH_ADMIN, required_scope=SCOPE_GRAPH_ADMIN)


def test_scope_inheritance_write_does_not_include_admin() -> None:
    """Write scope should not satisfy admin-only permissions."""

    assert not has_scope(granted_scope=SCOPE_GRAPH_WRITE, required_scope=SCOPE_GRAPH_ADMIN)


def test_required_scope_game_engine_graph_routes_need_write_scope() -> None:
    """Game-engine graph routes under /v1/graph/ should require graph_write."""

    prefix = "/v1"

    assert _required_scope_for_path(path="/v1/graph/nodes/character", api_v1_prefix=prefix) == SCOPE_GRAPH_WRITE
    assert _required_scope_for_path(path="/v1/graph/edges/RELATES_TO", api_v1_prefix=prefix) == SCOPE_GRAPH_WRITE


def test_required_scope_admin_routes_need_admin_scope() -> None:
    """All /v1/admin/* routes should require graph_admin scope."""

    prefix = "/v1"

    assert _required_scope_for_path(path="/v1/admin/graph/reindex", api_v1_prefix=prefix) == SCOPE_GRAPH_ADMIN
    assert _required_scope_for_path(path="/v1/admin/graph/characters/abc", api_v1_prefix=prefix) == SCOPE_GRAPH_ADMIN
    assert _required_scope_for_path(path="/v1/admin/batch/gossip_tick", api_v1_prefix=prefix) == SCOPE_GRAPH_ADMIN
    assert _required_scope_for_path(path="/v1/admin/schema", api_v1_prefix=prefix) == SCOPE_GRAPH_ADMIN
    assert _required_scope_for_path(path="/v1/admin/protected", api_v1_prefix=prefix) == SCOPE_GRAPH_ADMIN


def test_required_scope_public_game_engine_routes_need_no_scope() -> None:
    """Game-engine routes outside /v1/graph/ and /v1/admin/ need only bearer auth."""

    prefix = "/v1"

    assert _required_scope_for_path(path="/v1/dialogue", api_v1_prefix=prefix) is None
    assert _required_scope_for_path(path="/v1/npc/alice/state", api_v1_prefix=prefix) is None
    assert _required_scope_for_path(path="/v1/quest/offer", api_v1_prefix=prefix) is None
    assert _required_scope_for_path(path="/v1/clock/advance", api_v1_prefix=prefix) is None
    assert _required_scope_for_path(path="/v1/action", api_v1_prefix=prefix) is None
