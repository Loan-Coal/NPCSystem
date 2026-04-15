"""
middleware.py - FastAPI middleware that enforces API key auth on protected routes.

Does NOT: authenticate individual players or authorize actions by role.

Dependencies injected: Settings.
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from config import Settings
from auth.api_key import validate_bearer_token
from utils.errors import AuthError


HEALTH_PATH = "/health"


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
            validate_bearer_token(
                authorization=authorization,
                expected_secret=self._settings.API_KEY_SECRET,
            )
        except AuthError:
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})

        return await call_next(request)
