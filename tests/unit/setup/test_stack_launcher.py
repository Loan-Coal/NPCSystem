"""Tests for npc_engine.setup.stack_launcher — full-stack process orchestrator."""
from __future__ import annotations

import asyncio
import subprocess
from contextlib import contextmanager
from typing import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from npc_engine.setup.neo4j_manager import Neo4jManager, Neo4jNotInstalledError
from npc_engine.setup.ollama_manager import OllamaManager
from npc_engine.setup.stack_launcher import StackLauncher


def _make_launcher(
    neo4j_running: bool = True,
    neo4j_installed: bool = True,
    ollama_manager: OllamaManager | None = None,
) -> StackLauncher:
    neo4j = MagicMock(spec=Neo4jManager)
    neo4j.is_running = AsyncMock(return_value=neo4j_running)
    neo4j.is_installed = MagicMock(return_value=neo4j_installed)
    neo4j.launch = MagicMock(return_value=MagicMock(spec=subprocess.Popen))
    return StackLauncher(neo4j_manager=neo4j, ollama_manager=ollama_manager)


@contextmanager
def _engine_patches() -> Generator[None, None, None]:
    """Patch uvicorn.Server.serve + StackLauncher._poll_readiness for unit tests."""
    with (
        patch("asyncio.sleep", new_callable=AsyncMock),
        patch("uvicorn.Server.serve", new_callable=AsyncMock),
        patch.object(StackLauncher, "_poll_readiness", new_callable=AsyncMock, return_value=True),
    ):
        yield


class TestStackLauncherNeo4j:
    def test_skips_neo4j_launch_if_already_running(self) -> None:
        launcher = _make_launcher(neo4j_running=True)

        with _engine_patches():
            asyncio.run(launcher.launch())

        launcher._neo4j.launch.assert_not_called()

    def test_starts_neo4j_if_not_running(self) -> None:
        launched: list[bool] = []

        neo4j = MagicMock(spec=Neo4jManager)
        # First call (before launch): not running; subsequent calls: running.
        neo4j.is_running = AsyncMock(side_effect=lambda: bool(launched))
        neo4j.is_installed = MagicMock(return_value=True)

        def fake_launch() -> MagicMock:
            launched.append(True)
            return MagicMock(spec=subprocess.Popen)

        neo4j.launch = MagicMock(side_effect=fake_launch)
        launcher = StackLauncher(neo4j_manager=neo4j)

        with _engine_patches():
            asyncio.run(launcher.launch())

        assert launched == [True]

    def test_raises_not_installed_if_not_running_and_not_installed(self) -> None:
        launcher = _make_launcher(neo4j_running=False, neo4j_installed=False)

        with (
            _engine_patches(),
            pytest.raises(Neo4jNotInstalledError),
        ):
            asyncio.run(launcher.launch())


class TestStackLauncherOllama:
    def test_skips_ollama_if_no_ollama_manager(self) -> None:
        launcher = _make_launcher(ollama_manager=None)
        with _engine_patches():
            asyncio.run(launcher.launch())
        # No error means Ollama section was gracefully skipped.

    def test_skips_ollama_launch_if_already_running(self) -> None:
        ollama = MagicMock(spec=OllamaManager)
        ollama.is_running = AsyncMock(return_value=True)
        ollama.launch = MagicMock(return_value=MagicMock(spec=subprocess.Popen))
        launcher = _make_launcher(ollama_manager=ollama)

        with _engine_patches():
            asyncio.run(launcher.launch())

        ollama.launch.assert_not_called()

    def test_starts_ollama_if_configured_and_not_running(self) -> None:
        launched: list[bool] = []
        ollama = MagicMock(spec=OllamaManager)
        ollama.is_running = AsyncMock(side_effect=lambda: bool(launched))
        ollama.is_installed = MagicMock(return_value=True)

        def fake_launch() -> MagicMock:
            launched.append(True)
            return MagicMock(spec=subprocess.Popen)

        ollama.launch = MagicMock(side_effect=fake_launch)
        launcher = _make_launcher(ollama_manager=ollama)

        with _engine_patches():
            asyncio.run(launcher.launch())

        assert launched == [True]


class TestStackLauncherShutdown:
    def test_shutdown_terminates_started_processes(self) -> None:
        fake_proc = MagicMock(spec=subprocess.Popen)
        launcher = _make_launcher(neo4j_running=False)
        launcher._neo4j.is_running = AsyncMock(side_effect=[False, True])
        launcher._neo4j.launch = MagicMock(return_value=fake_proc)

        with _engine_patches():
            asyncio.run(launcher.launch())

        launcher.shutdown()
        fake_proc.terminate.assert_called_once()

    def test_shutdown_is_noop_when_nothing_started(self) -> None:
        launcher = _make_launcher(neo4j_running=True)
        with _engine_patches():
            asyncio.run(launcher.launch())
        launcher.shutdown()  # must not raise


class TestStackLauncherReadiness:
    def test_emits_ready_signal_when_engine_responds(self, capsys) -> None:
        """ENGINE_READY_SIGNAL printed to stdout when /readiness returns 200."""
        launcher = _make_launcher()
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("uvicorn.Server.serve", new_callable=AsyncMock),
            patch.object(StackLauncher, "_poll_readiness", new_callable=AsyncMock, return_value=True),
        ):
            asyncio.run(launcher.launch())
        assert "NPC_ENGINE_READY" in capsys.readouterr().out

    def test_emits_warning_when_engine_not_ready(self, capsys) -> None:
        """Warning written to stderr when /readiness never responds."""
        launcher = _make_launcher()
        with (
            patch("asyncio.sleep", new_callable=AsyncMock),
            patch("uvicorn.Server.serve", new_callable=AsyncMock),
            patch.object(StackLauncher, "_poll_readiness", new_callable=AsyncMock, return_value=False),
        ):
            asyncio.run(launcher.launch())
        assert "WARNING" in capsys.readouterr().err
