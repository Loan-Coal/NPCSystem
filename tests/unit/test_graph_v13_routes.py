"""
test_graph_v13_routes.py - Route contract tests for v1.3 graph endpoints.

Does NOT: validate database side effects.

Dependencies injected: monkeypatch and tmp_path fixtures.
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


def test_graph_generic_routes_are_registered(monkeypatch, tmp_path: Path) -> None:
    """Generic graph node/edge routes should be registered under /v1."""

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

    assert "/v1/graph/nodes/{node_type}" in paths
    assert "/v1/graph/nodes/{node_type}/{node_id}" in paths
    assert "/v1/graph/edges/{edge_type}" in paths
    assert "/v1/graph/edges/{edge_type}/{src_id}/{dst_id}" in paths
