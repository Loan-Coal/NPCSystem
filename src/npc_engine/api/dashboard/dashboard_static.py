"""
Module: dashboard_static
Layer: api
Purpose: Mount the designer web dashboard (Phase 12) as static files served by
         the FastAPI app under DASHBOARD_MOUNT_PATH.
Does NOT: serve API data, enforce auth, or read request bodies.
Dependencies: starlette.staticfiles, fastapi.
Dependencies injected: FastAPI app (via register_dashboard).
Used by: main.create_app.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from starlette.staticfiles import StaticFiles

from npc_engine.utils.logging import get_logger

DASHBOARD_MOUNT_PATH = "/dashboard"
_DASHBOARD_DIR = Path(__file__).resolve().parents[4] / "dashboard"
_LOGGER = get_logger(__name__)


def register_dashboard(app: FastAPI) -> bool:
    """Mount the static designer dashboard if its assets are present on disk.

    The mount is auth-exempt (handled in auth.middleware) because the static
    HTML/CSS/JS contain no secrets; the browser supplies the Bearer token on the
    API calls the dashboard makes. Missing assets are non-fatal — the API still
    serves normally without the dashboard.

    Args:
        app: FastAPI application to mount the dashboard onto.
    Returns:
        True when the dashboard was mounted, False when its directory is absent.
    """
    if not _DASHBOARD_DIR.is_dir():
        _LOGGER.info("dashboard_not_mounted", extra={"reason": "directory_absent", "path": str(_DASHBOARD_DIR)})
        return False
    app.mount(
        DASHBOARD_MOUNT_PATH,
        StaticFiles(directory=str(_DASHBOARD_DIR), html=True),
        name="dashboard",
    )
    _LOGGER.info("dashboard_mounted", extra={"path": DASHBOARD_MOUNT_PATH, "dir": str(_DASHBOARD_DIR)})
    return True
