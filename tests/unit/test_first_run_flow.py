"""Tests for npc_engine.setup.first_run_flow — first-run orchestration."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from npc_engine.setup.first_run_flow import (
    FirstRunFlow,
    FirstRunResult,
    FirstRunStatus,
)


def _make_flow(api_base: str = "http://localhost:11434") -> FirstRunFlow:
    return FirstRunFlow(api_base=api_base)


class TestFirstRunResultModel:
    def test_has_status_and_model_name(self) -> None:
        result = FirstRunResult(status=FirstRunStatus.READY, model_name="qwen2.5:7b")
        assert result.status == FirstRunStatus.READY
        assert result.model_name == "qwen2.5:7b"

    def test_has_message_field(self) -> None:
        result = FirstRunResult(
            status=FirstRunStatus.READY,
            model_name="qwen2.5:7b",
            message="All good",
        )
        assert result.message == "All good"


class TestFirstRunFlowAlreadyReady:
    def test_returns_ready_when_model_already_available(self) -> None:
        flow = _make_flow()
        with (
            patch(
                "npc_engine.setup.first_run_flow.detect_vram_mb", return_value=8192
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_running",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_model_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
        ):
            result = asyncio.run(flow.run())
        assert result.status == FirstRunStatus.READY
        assert result.model_name == "qwen2.5:14b"


class TestFirstRunFlowPullModel:
    def test_pulls_model_when_not_available(self) -> None:
        flow = _make_flow()
        pulled: list[str] = []

        async def fake_pull(model_name: str, progress_callback=None) -> None:
            pulled.append(model_name)

        with (
            patch("npc_engine.setup.first_run_flow.detect_vram_mb", return_value=0),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_running",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_model_available",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.pull_model",
                side_effect=fake_pull,
            ),
        ):
            result = asyncio.run(flow.run())
        assert "qwen2.5:3b" in pulled
        assert result.status == FirstRunStatus.READY
        assert result.model_name == "qwen2.5:3b"


class TestFirstRunFlowOllamaNotRunning:
    def test_launches_ollama_when_not_running(self) -> None:
        flow = _make_flow()
        launched: list[bool] = []

        def fake_launch() -> MagicMock:
            launched.append(True)
            return MagicMock()

        async def is_running_sequence(*args: object, **kwargs: object) -> bool:
            # First call: not running; second call: running after launch
            return bool(launched)

        with (
            patch("npc_engine.setup.first_run_flow.detect_vram_mb", return_value=0),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_running",
                side_effect=is_running_sequence,
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_installed",
                return_value=True,
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.launch",
                side_effect=fake_launch,
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_model_available",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            result = asyncio.run(flow.run())
        assert launched == [True]
        assert result.status == FirstRunStatus.READY


class TestFirstRunFlowNotInstalled:
    def test_returns_not_installed_when_binary_missing_and_not_running(self) -> None:
        flow = _make_flow()
        with (
            patch("npc_engine.setup.first_run_flow.detect_vram_mb", return_value=0),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_running",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch(
                "npc_engine.setup.first_run_flow.OllamaManager.is_installed",
                return_value=False,
            ),
        ):
            result = asyncio.run(flow.run())
        assert result.status == FirstRunStatus.NOT_INSTALLED
