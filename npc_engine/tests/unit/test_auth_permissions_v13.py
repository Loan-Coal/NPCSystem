"""
test_auth_permissions_v13.py - Unit tests for v1.3 scope inheritance and path mapping.

Does NOT: exercise full HTTP middleware pipeline.

Dependencies injected: None.
"""

from auth.middleware import _required_scope_for_path
from auth.permissions import SCOPE_GRAPH_ADMIN, SCOPE_GRAPH_WRITE, has_scope


def test_scope_inheritance_admin_includes_write() -> None:
    """Admin scope should satisfy write-level permissions."""

    assert has_scope(granted_scope=SCOPE_GRAPH_ADMIN, required_scope=SCOPE_GRAPH_WRITE)
    assert has_scope(granted_scope=SCOPE_GRAPH_ADMIN, required_scope=SCOPE_GRAPH_ADMIN)


def test_scope_inheritance_write_does_not_include_admin() -> None:
    """Write scope should not satisfy admin-only permissions."""

    assert not has_scope(granted_scope=SCOPE_GRAPH_WRITE, required_scope=SCOPE_GRAPH_ADMIN)


def test_required_scope_path_resolution() -> None:
    """Path-to-scope mapping should match v1.3 route expectations."""

    prefix = "/v1"

    assert _required_scope_for_path(path="/v1/graph/characters", api_v1_prefix=prefix) == SCOPE_GRAPH_WRITE
    assert _required_scope_for_path(path="/v1/graph/admin/reindex", api_v1_prefix=prefix) == SCOPE_GRAPH_ADMIN
    assert _required_scope_for_path(path="/v1/schema", api_v1_prefix=prefix) is None
    assert _required_scope_for_path(path="/v1/dialogue", api_v1_prefix=prefix) is None
