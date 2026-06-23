"""Tests for npc_engine.setup.ollama_manager — Ollama lifecycle management."""
from __future__ import annotations

import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.setup.ollama_manager import (
    OllamaManager,
    OllamaNotInstalledError,
    OLLAMA_API_BASE,
)


def _make_manager() -> OllamaManager:
    return OllamaManager(api_base=OLLAMA_API_BASE)


def _mock_async_client(status_code: int = 200, json_body: dict | None = None, exc: Exception | None = None) -> MagicMock:
    """Build a context-manager mock for httpx.AsyncClient."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    if json_body is not None:
        mock_resp.json.return_value = json_body

    mock_client = AsyncMock()
    if exc is not None:
        mock_client.get = AsyncMock(side_effect=exc)
    else:
        mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


class TestIsOllamaRunning:
    def test_returns_true_when_api_responds(self) -> None:
        manager = _make_manager()
        mock_client = _mock_async_client(status_code=200)
        with patch("npc_engine.setup.ollama_manager.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(manager.is_running())
        assert result is True

    def test_returns_false_when_api_unreachable(self) -> None:
        manager = _make_manager()
        mock_client = _mock_async_client(exc=Exception("connection refused"))
        with patch("npc_engine.setup.ollama_manager.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(manager.is_running())
        assert result is False


class TestIsModelAvailable:
    def test_returns_true_when_model_listed(self) -> None:
        manager = _make_manager()
        mock_client = _mock_async_client(
            status_code=200, json_body={"models": [{"name": "qwen2.5:7b"}]}
        )
        with patch("npc_engine.setup.ollama_manager.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(manager.is_model_available("qwen2.5:7b"))
        assert result is True

    def test_returns_false_when_model_not_listed(self) -> None:
        manager = _make_manager()
        mock_client = _mock_async_client(
            status_code=200, json_body={"models": [{"name": "llama3:8b"}]}
        )
        with patch("npc_engine.setup.ollama_manager.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(manager.is_model_available("qwen2.5:7b"))
        assert result is False

    def test_returns_false_on_api_error(self) -> None:
        manager = _make_manager()
        mock_client = _mock_async_client(exc=Exception("timeout"))
        with patch("npc_engine.setup.ollama_manager.httpx.AsyncClient", return_value=mock_client):
            result = asyncio.run(manager.is_model_available("qwen2.5:7b"))
        assert result is False


class TestIsOllamaInstalled:
    def test_returns_true_when_binary_on_path(self) -> None:
        manager = _make_manager()
        with patch("shutil.which", return_value="/usr/local/bin/ollama"):
            assert manager.is_installed() is True

    def test_returns_false_when_binary_not_on_path(self) -> None:
        manager = _make_manager()
        with patch("shutil.which", return_value=None):
            assert manager.is_installed() is False


class TestLaunchOllama:
    def test_launch_starts_subprocess(self) -> None:
        manager = _make_manager()
        mock_proc = MagicMock()
        with patch("subprocess.Popen", return_value=mock_proc) as mock_popen:
            proc = manager.launch()
        assert proc is mock_proc
        mock_popen.assert_called_once()

    def test_launch_raises_when_not_installed(self) -> None:
        manager = _make_manager()
        with patch("subprocess.Popen", side_effect=FileNotFoundError()):
            with pytest.raises(OllamaNotInstalledError):
                manager.launch()


class TestOllamaNotInstalledError:
    def test_is_exception(self) -> None:
        err = OllamaNotInstalledError("ollama not found")
        assert isinstance(err, Exception)
        assert "ollama not found" in str(err)
