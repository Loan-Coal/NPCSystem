"""
api_key.py - Validates Authorization Bearer tokens against configured shared secret.

Does NOT: manage user sessions or token issuance.

Dependencies injected: Settings.
"""

import secrets

from config import Settings
from auth.permissions import SCOPE_GRAPH_ADMIN, SCOPE_GRAPH_WRITE
from utils.errors import AuthError


AUTH_HEADER_PREFIX = "Bearer "


def _extract_bearer_token(authorization: str) -> str:
    """Extract Bearer token from Authorization header."""

    if not authorization.startswith(AUTH_HEADER_PREFIX):
        raise AuthError(reason="missing_bearer_prefix")
    return authorization[len(AUTH_HEADER_PREFIX) :].strip()


def validate_bearer_token(authorization: str, expected_secret: str) -> None:
    """Validate Authorization header against expected secret."""

    token = _extract_bearer_token(authorization=authorization)
    if not secrets.compare_digest(token, expected_secret):
        raise AuthError(reason="invalid_secret")


def resolve_scope_from_authorization(authorization: str, settings: Settings) -> str:
    """Resolve token scope from configured secrets, with fallback compatibility."""

    token = _extract_bearer_token(authorization=authorization)

    if settings.API_KEY_GRAPH_ADMIN and secrets.compare_digest(token, settings.API_KEY_GRAPH_ADMIN):
        return SCOPE_GRAPH_ADMIN

    if settings.API_KEY_GRAPH_WRITE and secrets.compare_digest(token, settings.API_KEY_GRAPH_WRITE):
        return SCOPE_GRAPH_WRITE

    if secrets.compare_digest(token, settings.API_KEY_SECRET):
        return SCOPE_GRAPH_ADMIN

    raise AuthError(reason="invalid_secret")
