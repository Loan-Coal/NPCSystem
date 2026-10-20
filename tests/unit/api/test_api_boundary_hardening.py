"""
Module: test_api_boundary_hardening
Purpose: T15.3 RED anchor — three API-boundary security findings (ISSUE-301/302/303).

Asserts:
  (1) A weak API_KEY_GRAPH_ADMIN is rejected during Settings construction (ISSUE-301).
  (2) An over-cap npc_ids list on POST /batch/gossip_tick returns 422 (ISSUE-302).
  (3) A path sharing the /setup prefix but not matching a known route is refused (ISSUE-303).

Does NOT: touch Neo4j, start a server with lifespan, or perform I/O.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

pytest.importorskip("neo4j")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _batch_app() -> FastAPI:
    """Minimal FastAPI app with only the admin batch router."""
    from npc_engine.api.routes.admin.batch import router as batch_router

    app = FastAPI()
    app.include_router(batch_router, prefix="/v1/admin")
    return app


# ---------------------------------------------------------------------------
# ISSUE-301: weak optional API keys must be rejected at startup
# ---------------------------------------------------------------------------

def test_weak_api_key_graph_admin_rejected_at_startup() -> None:
    """Settings must reject a short/weak API_KEY_GRAPH_ADMIN value."""
    from npc_engine.config import Settings

    with pytest.raises(ValidationError):
        Settings(  # type: ignore[call-arg]
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            API_KEY_GRAPH_ADMIN="weak",
        )


def test_weak_api_key_graph_write_rejected_at_startup() -> None:
    """Settings must reject a short/weak API_KEY_GRAPH_WRITE value."""
    from npc_engine.config import Settings

    with pytest.raises(ValidationError):
        Settings(  # type: ignore[call-arg]
            API_KEY_SECRET="local_dev_secret_change_this_2026",
            API_KEY_GRAPH_WRITE="bad",
        )


def test_strong_optional_api_keys_accepted() -> None:
    """Settings must accept properly-formed optional keys when provided."""
    from npc_engine.config import Settings

    settings = Settings(  # type: ignore[call-arg]
        API_KEY_SECRET="local_dev_secret_change_this_2026",
        API_KEY_GRAPH_ADMIN="a_strong_admin_key_longer_than_16",
        API_KEY_GRAPH_WRITE="a_strong_write_key_longer_than_16",
    )
    assert settings.API_KEY_GRAPH_ADMIN == "a_strong_admin_key_longer_than_16"
    assert settings.API_KEY_GRAPH_WRITE == "a_strong_write_key_longer_than_16"


def test_none_optional_api_keys_accepted() -> None:
    """Settings must accept None (unset) optional keys — they remain optional."""
    from npc_engine.config import Settings

    settings = Settings(  # type: ignore[call-arg]
        API_KEY_SECRET="local_dev_secret_change_this_2026",
    )
    assert settings.API_KEY_GRAPH_ADMIN is None
    assert settings.API_KEY_GRAPH_WRITE is None


# ---------------------------------------------------------------------------
# ISSUE-302: over-cap id lists must return 422
# ---------------------------------------------------------------------------

def test_gossip_tick_over_cap_npc_ids_returns_422() -> None:
    """POST /batch/gossip_tick with more npc_ids than the cap must return 422."""
    from npc_engine.api.routes.admin.batch import ADMIN_ID_LIST_MAX_LENGTH

    client = TestClient(_batch_app(), raise_server_exceptions=False)
    payload = {"npc_ids": [f"npc_{i}" for i in range(ADMIN_ID_LIST_MAX_LENGTH + 1)]}
    response = client.post("/v1/admin/batch/gossip_tick", json=payload)

    assert response.status_code == 422, (
        f"expected 422 for over-cap npc_ids, got {response.status_code}"
    )


def test_event_tick_over_cap_location_ids_returns_422() -> None:
    """POST /batch/event_tick with more location_ids than the cap must return 422."""
    from npc_engine.api.routes.admin.batch import ADMIN_ID_LIST_MAX_LENGTH

    client = TestClient(_batch_app(), raise_server_exceptions=False)
    payload = {"location_ids": [f"loc_{i}" for i in range(ADMIN_ID_LIST_MAX_LENGTH + 1)]}
    response = client.post("/v1/admin/batch/event_tick", json=payload)

    assert response.status_code == 422, (
        f"expected 422 for over-cap location_ids, got {response.status_code}"
    )


def test_gossip_tick_at_cap_npc_ids_not_rejected_by_validation() -> None:
    """POST /batch/gossip_tick at exactly the cap must not get a 422 from list-size validation."""
    from npc_engine.api.routes.admin.batch import ADMIN_ID_LIST_MAX_LENGTH

    client = TestClient(_batch_app(), raise_server_exceptions=False)
    payload = {"npc_ids": [f"npc_{i}" for i in range(ADMIN_ID_LIST_MAX_LENGTH)]}
    response = client.post("/v1/admin/batch/gossip_tick", json=payload)

    # 422 from list length would be wrong; any other error (500 from missing dep,
    # 200 from handler) is acceptable — what matters is the list was NOT rejected
    # for being too long.
    assert response.status_code != 422 or "npc_ids" not in response.text, (
        "list at the cap must not be rejected by the max_length constraint"
    )


# ---------------------------------------------------------------------------
# ISSUE-303: /setup prefix match must be an exact route allow-list
# ---------------------------------------------------------------------------

def test_setup_prefix_path_not_exempt_from_auth() -> None:
    """A path sharing /setup as a prefix but not a known route must NOT be treated as public."""
    from npc_engine.auth.middleware_helpers import is_public_path

    assert is_public_path("/setupmalicious", env="dev") is False, (
        "/setupmalicious must not be treated as public — only exact /setup routes are"
    )


def test_setup_hyphen_path_not_exempt_from_auth() -> None:
    """A path like /setup-anything must NOT be treated as public."""
    from npc_engine.auth.middleware_helpers import is_public_path

    assert is_public_path("/setup-evil", env="dev") is False


def test_known_setup_routes_still_public_in_dev() -> None:
    """The two known /setup routes must remain public in dev after the fix."""
    from npc_engine.auth.middleware_helpers import is_public_path

    assert is_public_path("/setup/validate", env="dev") is True
    assert is_public_path("/setup/config", env="dev") is True


def test_known_setup_routes_not_public_outside_dev() -> None:
    """/setup routes must NOT be public in prod or staging."""
    from npc_engine.auth.middleware_helpers import is_public_path

    assert is_public_path("/setup/validate", env="prod") is False
    assert is_public_path("/setup/config", env="prod") is False
    assert is_public_path("/setup/validate", env="staging") is False
    assert is_public_path("/setup/config", env="staging") is False
