"""
test_setup_routes.py - Unit tests for the first-run setup routes (INTEG-01/02).

POST /setup/validate — validates LLM path A or B.
GET  /setup/config   — loads persisted wizard config.
POST /setup/config   — saves wizard config.

All tests use FastAPI's TestClient with monkeypatched validators/loaders so no
filesystem or network I/O happens.
"""
from __future__ import annotations

import pathlib
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from npc_engine.api.routes.setup import setup_router
from npc_engine.setup.path_validator import ValidationResult, ValidationStatus
from npc_engine.setup.wizard_config import LLMPath, WizardConfig


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def app() -> FastAPI:
    """Minimal FastAPI app with only the setup router mounted."""
    _app = FastAPI()
    _app.include_router(setup_router)
    return _app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


def _local_body() -> dict:
    return {
        "path": "a",
        "config": {
            "llm_path": "local",
            "local_model": "qwen2.5:7b",
        },
    }


def _api_body(api_url: str = "https://api.openai.com/v1") -> dict:
    return {
        "path": "b",
        "config": {
            "llm_path": "api",
            "api_key": "sk-test",
            "api_url": api_url,
        },
    }


# ---------------------------------------------------------------------------
# POST /setup/validate — path A
# ---------------------------------------------------------------------------

class TestValidatePathA:
    def test_ok_returns_200_with_ok_status(self, client: TestClient, monkeypatch) -> None:
        ok_result = ValidationResult(status=ValidationStatus.OK)
        monkeypatch.setattr(
            "npc_engine.api.routes.setup.setup.validate_path_a",
            AsyncMock(return_value=ok_result),
        )
        resp = client.post("/setup/validate", json=_local_body())
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ok"

    def test_ollama_not_running_returns_200_with_error_status(
        self, client: TestClient, monkeypatch
    ) -> None:
        fail_result = ValidationResult(
            status=ValidationStatus.OLLAMA_NOT_RUNNING,
            message="Ollama is not running.",
        )
        monkeypatch.setattr(
            "npc_engine.api.routes.setup.setup.validate_path_a",
            AsyncMock(return_value=fail_result),
        )
        resp = client.post("/setup/validate", json=_local_body())
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "ollama_not_running"
        assert "Ollama" in data["message"]


# ---------------------------------------------------------------------------
# POST /setup/validate — path B
# ---------------------------------------------------------------------------

class TestValidatePathB:
    def test_ok_returns_200_with_ok_status(self, client: TestClient, monkeypatch) -> None:
        ok_result = ValidationResult(status=ValidationStatus.OK)
        monkeypatch.setattr(
            "npc_engine.api.routes.setup.setup.validate_path_b",
            AsyncMock(return_value=ok_result),
        )
        resp = client.post("/setup/validate", json=_api_body())
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "ok"

    def test_auth_failed_returns_200_with_error_status(
        self, client: TestClient, monkeypatch
    ) -> None:
        fail_result = ValidationResult(
            status=ValidationStatus.API_AUTH_FAILED,
            message="Key rejected.",
        )
        monkeypatch.setattr(
            "npc_engine.api.routes.setup.setup.validate_path_b",
            AsyncMock(return_value=fail_result),
        )
        resp = client.post("/setup/validate", json=_api_body())
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "api_auth_failed"

    def test_invalid_path_value_returns_422(self, client: TestClient) -> None:
        body = {"path": "c", "config": {"llm_path": "api", "api_key": "sk-x"}}
        resp = client.post("/setup/validate", json=body)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /setup/config
# ---------------------------------------------------------------------------

class TestGetConfig:
    def test_returns_config_when_file_exists(
        self, client: TestClient, monkeypatch
    ) -> None:
        cfg = WizardConfig(llm_path=LLMPath.LOCAL, local_model="qwen2.5:7b")
        monkeypatch.setattr(
            "npc_engine.api.routes.setup.setup.load_wizard_config",
            lambda **_kw: cfg,
        )
        resp = client.get("/setup/config")
        assert resp.status_code == 200
        assert resp.json()["data"]["llm_path"] == "local"

    def test_returns_404_when_config_missing(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "npc_engine.api.routes.setup.setup.load_wizard_config",
            lambda **_kw: None,
        )
        resp = client.get("/setup/config")
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /setup/config
# ---------------------------------------------------------------------------

class TestPostConfig:
    def test_saves_and_echoes_config(self, client: TestClient, monkeypatch) -> None:
        saved: list[WizardConfig] = []

        def _fake_save(cfg: WizardConfig, **_kw) -> None:
            saved.append(cfg)

        monkeypatch.setattr(
            "npc_engine.api.routes.setup.setup.save_wizard_config",
            _fake_save,
        )
        body = {"llm_path": "api", "api_key": "sk-test", "api_url": "https://api.openai.com/v1"}
        resp = client.post("/setup/config", json=body)
        assert resp.status_code == 200
        assert resp.json()["data"]["llm_path"] == "api"
        assert len(saved) == 1
        assert saved[0].api_key == "sk-test"

    def test_invalid_body_returns_422(self, client: TestClient) -> None:
        resp = client.post("/setup/config", json={"not_a_field": True})
        assert resp.status_code == 422
