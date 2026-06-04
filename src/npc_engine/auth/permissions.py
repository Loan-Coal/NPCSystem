"""
permissions.py - Scope hierarchy helpers for route authorization.
Layer: api
Purpose: (auto-detected — review)

Does NOT: validate bearer secrets.

Dependencies injected: None.
"""

SCOPE_GRAPH_WRITE = "graph_write"
SCOPE_GRAPH_ADMIN = "graph_admin"

_SCOPE_INHERITANCE = {
    SCOPE_GRAPH_WRITE: {SCOPE_GRAPH_WRITE},
    SCOPE_GRAPH_ADMIN: {SCOPE_GRAPH_ADMIN, SCOPE_GRAPH_WRITE},
}


def has_scope(granted_scope: str, required_scope: str) -> bool:
    """Return True if granted scope satisfies required scope.

    Args:
        granted_scope: Scope string resolved from the bearer token.
        required_scope: Scope string required to access the target route.

    Returns:
        True when the granted scope covers the required scope via the inheritance map.
    """
    return required_scope in _SCOPE_INHERITANCE.get(granted_scope, set())
