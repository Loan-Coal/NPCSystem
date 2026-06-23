"""Tests for npc_engine.setup.path_validator — async LLM-path validators."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.setup.path_validator import (
    ValidationResult,
    ValidationStatus,
    validate_api_url_safety,
    validate_path_a,
    validate_path_b,
)
from npc_engine.setup.wizard_config import LLMPath, WizardConfig


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _local_config(local_model: str = "qwen2.5:7b") -> WizardConfig:
    return WizardConfig(llm_path=LLMPath.LOCAL, local_model=local_model)


def _api_config(
    api_key: str = "sk-test",
    api_url: str = "https://api.openai.com/v1",
) -> WizardConfig:
    return WizardConfig(llm_path=LLMPath.API, api_key=api_key, api_url=api_url)


# ---------------------------------------------------------------------------
# ValidationResult model
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# validate_api_url_safety
# ---------------------------------------------------------------------------

class TestValidateApiUrlSafety:
    def test_https_external_is_safe(self) -> None:
        assert validate_api_url_safety("https://api.openai.com/v1") is None

    def test_http_localhost_is_safe(self) -> None:
        assert validate_api_url_safety("http://localhost:1234/v1") is None

    def test_http_127_is_safe(self) -> None:
        assert validate_api_url_safety("http://127.0.0.1:11434/v1") is None

    def test_http_external_blocked(self) -> None:
        result = validate_api_url_safety("http://api.openai.com/v1")
        assert result is not None
        assert result.status == ValidationStatus.API_UNREACHABLE
        assert "https" in result.message

    def test_private_10_blocked(self) -> None:
        result = validate_api_url_safety("https://10.0.0.1/v1")
        assert result is not None
        assert result.status == ValidationStatus.API_UNREACHABLE

    def test_private_192_168_blocked(self) -> None:
        result = validate_api_url_safety("https://192.168.0.1/v1")
        assert result is not None
        assert result.status == ValidationStatus.API_UNREACHABLE

    def test_link_local_blocked(self) -> None:
        result = validate_api_url_safety("http://169.254.169.254/latest/meta-data/")
        assert result is not None
        assert result.status == ValidationStatus.API_UNREACHABLE

    def test_no_host_blocked(self) -> None:
        result = validate_api_url_safety("https:///v1")
        assert result is not None
        assert result.status == ValidationStatus.API_UNREACHABLE


# ---------------------------------------------------------------------------
# ValidationResult model
# ---------------------------------------------------------------------------

class TestValidationResultModel:
    def test_ok_status(self) -> None:
        r = ValidationResult(status=ValidationStatus.OK)
        assert r.status == ValidationStatus.OK
        assert r.message == ""

    def test_message_field(self) -> None:
        r = ValidationResult(status=ValidationStatus.OLLAMA_NOT_RUNNING, message="down")
        assert r.message == "down"


# ---------------------------------------------------------------------------
# validate_path_a
# ---------------------------------------------------------------------------

class TestValidatePathA:
    def test_ok_when_ollama_running_and_model_present(self) -> None:
        with (
            patch(
                "npc_engine.setup.path_validator.OllamaManager.is_running",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "npc_engine.setup.path_validator.OllamaManager.is_model_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = asyncio.run(validate_path_a(_local_config()))
        assert result.status == ValidationStatus.OK

    def test_ollama_not_running(self) -> None:
        with patch(
            "npc_engine.setup.path_validator.OllamaManager.is_running",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = asyncio.run(validate_path_a(_local_config()))
        assert result.status == ValidationStatus.OLLAMA_NOT_RUNNING

    def test_model_not_present(self) -> None:
        with (
            patch(
                "npc_engine.setup.path_validator.OllamaManager.is_running",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "npc_engine.setup.path_validator.OllamaManager.is_model_available",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            result = asyncio.run(validate_path_a(_local_config("qwen2.5:14b")))
        assert result.status == ValidationStatus.MODEL_NOT_PRESENT

    def test_no_local_model_configured(self) -> None:
        cfg = WizardConfig(llm_path=LLMPath.LOCAL, local_model=None)
        with patch(
            "npc_engine.setup.path_validator.OllamaManager.is_running",
            new_callable=AsyncMock,
            return_value=True,
        ):
            result = asyncio.run(validate_path_a(cfg))
        assert result.status == ValidationStatus.MODEL_NOT_PRESENT


# ---------------------------------------------------------------------------
# validate_path_b
# ---------------------------------------------------------------------------

class TestValidatePathB:
    def test_ok_on_200(self) -> None:
        mock_resp = AsyncMock()
        mock_resp.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch(
            "npc_engine.setup.path_validator.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = asyncio.run(validate_path_b(_api_config()))
        assert result.status == ValidationStatus.OK

    def test_auth_failed_on_401(self) -> None:
        mock_resp = AsyncMock()
        mock_resp.status_code = 401

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch(
            "npc_engine.setup.path_validator.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = asyncio.run(validate_path_b(_api_config()))
        assert result.status == ValidationStatus.API_AUTH_FAILED

    def test_unreachable_on_connection_error(self) -> None:
        import httpx

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))

        with patch(
            "npc_engine.setup.path_validator.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = asyncio.run(validate_path_b(_api_config()))
        assert result.status == ValidationStatus.API_UNREACHABLE

    def test_no_api_key_returns_auth_failed(self) -> None:
        cfg = WizardConfig(llm_path=LLMPath.API, api_key=None)
        result = asyncio.run(validate_path_b(cfg))
        assert result.status == ValidationStatus.API_AUTH_FAILED

    def test_private_ip_is_blocked_ssrf(self) -> None:
        # http:// external — fails on scheme check (before IP check).
        cfg = _api_config(api_url="http://192.168.1.1/v1")
        result = asyncio.run(validate_path_b(cfg))
        assert result.status == ValidationStatus.API_UNREACHABLE

    def test_metadata_ip_is_blocked(self) -> None:
        cfg = _api_config(api_url="http://169.254.169.254/v1")
        result = asyncio.run(validate_path_b(cfg))
        assert result.status == ValidationStatus.API_UNREACHABLE

    def test_non_200_non_401_is_unreachable(self) -> None:
        mock_resp = AsyncMock()
        mock_resp.status_code = 500

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_resp)

        with patch(
            "npc_engine.setup.path_validator.httpx.AsyncClient",
            return_value=mock_client,
        ):
            result = asyncio.run(validate_path_b(_api_config()))
        assert result.status == ValidationStatus.API_UNREACHABLE
