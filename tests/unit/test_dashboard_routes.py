"""
test_dashboard_routes.py - Unit tests for Phase 12 designer dashboard backend:
the read-only /v1/system/config and /v1/system/metrics routes, the auth
public-path exemption, the config view model, and the static mount.

Does NOT: start the full application lifespan or touch Neo4j.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

pytest.importorskip("neo4j")

from npc_engine.api.dashboard_models import DashboardConfigView
from npc_engine.api.dashboard_static import DASHBOARD_MOUNT_PATH, register_dashboard
from npc_engine.api.routes.system import v1_router
from npc_engine.auth.middleware_helpers import is_public_path
from npc_engine.config import Settings, get_settings
from npc_engine.utils.metrics import increment_metric, reset_metrics_registry

_TEST_SECRET = "unit_test_secret_value_123"


def _settings_stub() -> Settings:
    return Settings(API_KEY_SECRET=_TEST_SECRET)


def _app_with_v1_router() -> FastAPI:
    app = FastAPI()
    app.include_router(v1_router, prefix="/v1")
    app.dependency_overrides[get_settings] = _settings_stub
    return app


# --- DashboardConfigView -----------------------------------------------------


def test_config_view_maps_settings_fields() -> None:
    """The view projects cadence/cost settings and omits secret fields."""
    view = DashboardConfigView.from_settings(_settings_stub())
    dumped = view.model_dump()

    assert dumped["world_id"] == "world"
    assert dumped["tick_interval_seconds"] == 10
    assert dumped["tick_llm_calls_per_minute_max"] == 6
    assert "api_key_secret" not in dumped
    assert "API_KEY_SECRET" not in dumped


# --- /v1/system/config -------------------------------------------------------


def test_config_route_returns_curated_envelope() -> None:
    """Config route returns the success envelope with curated tuning knobs."""
    client = TestClient(_app_with_v1_router())
    response = client.get("/v1/system/config")
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["world_id"] == "world"
    assert "tick_autopilot_enabled" in payload["data"]
    # No secret leaks through the curated projection.
    assert all("secret" not in key.lower() for key in payload["data"])


# --- /v1/system/metrics ------------------------------------------------------


def test_metrics_route_reflects_recorded_counters() -> None:
    """Metrics route surfaces in-process counters from the registry snapshot."""
    reset_metrics_registry()
    increment_metric(metric="dashboard_test_metric", amount=3.0)

    client = TestClient(_app_with_v1_router())
    response = client.get("/v1/system/metrics")
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["counters"]["dashboard_test_metric"] == 3.0
    assert "observations" in payload["data"]
    reset_metrics_registry()


# --- /v1/system/engines (ISSUE-062 regression) -------------------------------


def test_engines_route_passes_serialized_records_through() -> None:
    """Engine-status route returns already-serialized dicts without re-dumping.

    Regression for ISSUE-062: the handler called .model_dump() on the property's
    values, but TickScheduler.engine_status already returns dicts → AttributeError
    → HTTP 500 on every poll.
    """
    from types import SimpleNamespace

    from npc_engine.api.dependencies_engines import get_tick_scheduler
    from npc_engine.scheduler.engine_status_store import EngineStatusRecord

    record = EngineStatusRecord(engine_name="gossip", last_tick_id=7, error_count=0)
    app = _app_with_v1_router()
    app.dependency_overrides[get_tick_scheduler] = lambda: SimpleNamespace(
        engine_status={"gossip": record.model_dump()}
    )

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/v1/system/engines")
    payload = response.json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"][0]["engine_name"] == "gossip"
    assert payload["data"][0]["last_tick_id"] == 7


# --- auth public-path exemption ----------------------------------------------


def test_dashboard_paths_are_public() -> None:
    """Static dashboard assets and docs bypass auth; API routes do not."""
    assert is_public_path("/dashboard/") is True
    assert is_public_path("/dashboard/js/api.js") is True
    assert is_public_path("/health") is True
    assert is_public_path("/docs") is True
    assert is_public_path("/v1/graph/nodes/Character") is False
    assert is_public_path("/v1/admin/quests/drafts") is False


# --- static mount ------------------------------------------------------------


def test_register_dashboard_serves_index() -> None:
    """register_dashboard mounts the SPA and serves index.html with all tabs."""
    app = FastAPI()
    mounted = register_dashboard(app)
    assert mounted is True

    client = TestClient(app)
    response = client.get(f"{DASHBOARD_MOUNT_PATH}/")

    assert response.status_code == 200
    body = response.text
    for tab in ("graph", "npcs", "drafts", "engines", "analytics"):
        assert f'data-tab="{tab}"' in body


def test_dashboard_directory_assets_exist() -> None:
    """All SPA asset files referenced by index.html are present on disk."""
    root = Path(__file__).resolve().parents[2] / "dashboard"
    expected = [
        "index.html",
        "css/app.css",
        "js/api.js",
        "js/util.js",
        "js/graph.js",
        "js/npcs.js",
        "js/drafts.js",
        "js/engines.js",
        "js/analytics.js",
        "js/app.js",
    ]
    missing = [name for name in expected if not (root / name).is_file()]
    assert missing == []


def test_api_js_targets_existing_endpoints() -> None:
    """The API wrapper references the engine routes this dashboard depends on."""
    api_js = (Path(__file__).resolve().parents[2] / "dashboard" / "js" / "api.js").read_text(encoding="utf-8")
    for fragment in (
        "/graph/nodes/",
        "/graph/edges/",
        "/quests/drafts",
        "/system/engines",
        "/system/config",
        "/system/metrics",
    ):
        assert fragment in api_js
