"""
middleware.py - FastAPI middleware that enforces API key auth on protected routes.

Does NOT: authenticate individual players or authorize actions by role.

Dependencies injected: Settings.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from auth.permissions import SCOPE_GRAPH_ADMIN, SCOPE_GRAPH_WRITE, has_scope
from auth.api_key import resolve_scope_from_authorization
from config import Settings
from utils.errors import AuthError


HEALTH_PATH = "/health"


def _required_scope_for_path(path: str, api_v1_prefix: str) -> str | None:
    """Return required scope for the given path, or None for auth-only paths."""

    graph_admin_prefix = f"{api_v1_prefix}/graph/admin"
    graph_write_prefix = f"{api_v1_prefix}/graph"
    schema_path = f"{api_v1_prefix}/schema"

    if path.startswith(graph_admin_prefix):
        return SCOPE_GRAPH_ADMIN
    if path == schema_path:
        return None
    if path.startswith(graph_write_prefix):
        return SCOPE_GRAPH_WRITE
    return None


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Enforce Bearer auth for all routes except health."""

    def __init__(self, app, settings: Settings):
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next):
        """Validate auth header before forwarding request."""

        if request.url.path == HEALTH_PATH:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        try:
            granted_scope = resolve_scope_from_authorization(
                authorization=authorization,
                settings=self._settings,
            )
            required_scope = _required_scope_for_path(
                path=request.url.path,
                api_v1_prefix=self._settings.API_V1_PREFIX,
            )
            if required_scope and not has_scope(granted_scope=granted_scope, required_scope=required_scope):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
            request.state.api_scope = granted_scope
        except AuthError:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
