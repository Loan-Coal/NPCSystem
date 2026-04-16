"""
test_v1_route_versioning.py - Unit tests for v1-prefixed route registration.

Does NOT: test graph business logic.

Dependencies injected: monkeypatch, tmp_path fixtures.
"""

from pathlib import Path

from fastapi.routing import APIRoute, APIWebSocketRoute

from main import create_app


def _write_schema(path: Path) -> None:
    path.write_text(
        """
schema_version: "1.0"
core_types: {}
enum_extensions: {}
""".strip(),
        encoding="utf-8",
    )


def test_create_app_registers_v1_routes(monkeypatch, tmp_path: Path) -> None:
    """Application should register non-health routes under /v1 prefix."""

    schema_path = tmp_path / "game_schema.yaml"
    _write_schema(path=schema_path)

    monkeypatch.setenv("API_KEY_SECRET", "local_dev_secret_change_this_2026")
    monkeypatch.setenv("GAME_SCHEMA_PATH", str(schema_path))
    monkeypatch.setenv("DIALOGUE_STREAM_ENABLED", "true")

    from config import get_settings

    get_settings.cache_clear()
    app = create_app()

    paths = {
        route.path
        for route in app.routes
        if isinstance(route, (APIRoute, APIWebSocketRoute))
    }

    assert "/health" in paths
    assert "/v1/dialogue" in paths
    assert "/v1/ws/dialogue" in paths
    assert "/v1/schema" in paths
    assert "/v1/graph/characters" in paths
    assert "/v1/graph/admin/reindex" in paths
