"""Tests for npc_engine.setup.path_validator — async LLM-path validators."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from npc_engine.setup.path_validator import (
    ValidationResult,
    ValidationStatus,
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
