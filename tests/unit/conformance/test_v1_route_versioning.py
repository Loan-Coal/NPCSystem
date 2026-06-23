"""
test_v1_route_versioning.py - Unit tests for route registration layout after audience split.

Does NOT: test graph business logic.

Dependencies injected: monkeypatch, tmp_path fixtures.
"""

from pathlib import Path

import pytest
pytest.importorskip("neo4j")

from fastapi.routing import APIRoute, APIWebSocketRoute

from npc_engine.main import create_app


def _write_schema(path: Path) -> None:
    path.write_text(
        """
schema_version: "1.0"
core_types: {}
enum_extensions: {}
""".strip(),
        encoding="utf-8",
    )


def test_create_app_registers_game_engine_routes_under_v1(monkeypatch, tmp_path: Path) -> None:
    """Game-engine public routes should be registered under /v1/."""

    schema_path = tmp_path / "game_schema.yaml"
    _write_schema(path=schema_path)

    monkeypatch.setenv("API_KEY_SECRET", "local_dev_secret_change_this_2026")
    monkeypatch.setenv("GAME_SCHEMA_PATH", str(schema_path))
    monkeypatch.setenv("DIALOGUE_STREAM_ENABLED", "true")

    from npc_engine.config import get_settings
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
    assert "/v1/quest/offer" in paths
    assert "/v1/quest/reward" in paths
    assert "/v1/graph/nodes/{node_type}" in paths
    assert "/v1/npc/{npc_id}/state" in paths
    assert "/v1/clock/advance" in paths
    assert "/v1/action" in paths


def test_create_app_registers_admin_routes_under_v1_admin(monkeypatch, tmp_path: Path) -> None:
    """Designer/tooling routes should be registered under /v1/admin/."""

    schema_path = tmp_path / "game_schema.yaml"
    _write_schema(path=schema_path)

    monkeypatch.setenv("API_KEY_SECRET", "local_dev_secret_change_this_2026")
    monkeypatch.setenv("GAME_SCHEMA_PATH", str(schema_path))

    from npc_engine.config import get_settings
    get_settings.cache_clear()
    app = create_app()

    paths = {
        route.path
        for route in app.routes
        if isinstance(route, (APIRoute, APIWebSocketRoute))
    }

    assert "/v1/admin/schema" in paths
    assert "/v1/admin/schema/registry" in paths
    assert "/v1/admin/graph/reindex" in paths
    assert "/v1/admin/graph/characters/{character_id}" in paths
    assert "/v1/admin/batch/gossip_tick" in paths
    assert "/v1/admin/batch/event_tick" in paths
    assert "/v1/admin/protected" in paths


def test_create_app_registers_system_routes_under_admin(monkeypatch, tmp_path: Path) -> None:
    """System observability routes move under /v1/admin/system/ (SEV-14, DEC-112)."""

    schema_path = tmp_path / "game_schema.yaml"
    _write_schema(path=schema_path)

    monkeypatch.setenv("API_KEY_SECRET", "local_dev_secret_change_this_2026")
    monkeypatch.setenv("GAME_SCHEMA_PATH", str(schema_path))

    from npc_engine.config import get_settings
    get_settings.cache_clear()
    app = create_app()

    paths = {
        route.path
        for route in app.routes
        if isinstance(route, (APIRoute, APIWebSocketRoute))
    }

    assert "/v1/admin/system/engines" in paths
    assert "/v1/admin/system/config" in paths
    assert "/v1/admin/system/metrics" in paths
    assert "/v1/admin/system/events" in paths


def test_admin_routes_are_not_on_public_prefix(monkeypatch, tmp_path: Path) -> None:
    """Batch and graph-admin routes must not appear under the bare /v1/ prefix."""

    schema_path = tmp_path / "game_schema.yaml"
    _write_schema(path=schema_path)

    monkeypatch.setenv("API_KEY_SECRET", "local_dev_secret_change_this_2026")
    monkeypatch.setenv("GAME_SCHEMA_PATH", str(schema_path))

    from npc_engine.config import get_settings
    get_settings.cache_clear()
    app = create_app()

    paths = {
        route.path
        for route in app.routes
        if isinstance(route, (APIRoute, APIWebSocketRoute))
    }

    assert "/v1/batch/gossip_tick" not in paths
    assert "/v1/batch/event_tick" not in paths
    assert "/v1/graph/admin/reindex" not in paths
    assert "/v1/schema" not in paths
    assert "/v1/schema/registry" not in paths
    # SEV-14: system observability routes left the bare /v1/ prefix.
    assert "/v1/system/engines" not in paths
    assert "/v1/system/config" not in paths
    assert "/v1/system/metrics" not in paths
    assert "/v1/system/events" not in paths
