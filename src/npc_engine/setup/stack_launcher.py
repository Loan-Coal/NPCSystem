"""
Module: stack_launcher
Layer: config
Purpose: Orchestrate the full NPC Engine stack on an end-user machine: start Neo4j,
         optionally start Ollama (local-inference path), then serve the FastAPI engine
         via uvicorn until shutdown (SHIP-04). Polls GET /readiness after uvicorn
         starts and emits "NPC_ENGINE_READY" to stdout when the engine is ready (INTEG-04).
Dependencies: npc_engine.setup.neo4j_manager, npc_engine.setup.ollama_manager;
              uvicorn, httpx; stdlib asyncio/subprocess.
Used by: scripts/launcher.py (the PyInstaller entry point).
Does NOT: import any engine, services, graph, or API layer module.
Dependencies injected: Neo4jManager, OllamaManager (StackLauncher constructor);
                       engine_host and engine_port (StackLauncher constructor).
"""
from __future__ import annotations

import asyncio
import subprocess
import sys
from collections.abc import Awaitable, Callable

import httpx
import uvicorn

from npc_engine.setup.neo4j_manager import (
    Neo4jManager,
    Neo4jNotInstalledError,
    Neo4jStartupError,
)
from npc_engine.setup.ollama_manager import OllamaManager

# uvicorn import path for the FastAPI app (string avoids a rank-1→rank-6 import).
ENGINE_APP_IMPORT: str = "npc_engine.main:app"

# Default host and port for the packaged engine server.
ENGINE_DEFAULT_HOST: str = "127.0.0.1"
ENGINE_DEFAULT_PORT: int = 8080

# Seconds to wait after launching Neo4j before the first health-check retry.
_NEO4J_STARTUP_WAIT: float = 5.0

# Maximum health-check retries for Neo4j after launch.
_NEO4J_HEALTH_RETRIES: int = 10

# Delay between Neo4j health-check retries (seconds).
_NEO4J_HEALTH_RETRY_DELAY: float = 2.0

# Seconds to wait after launching Ollama before the first health-check retry.
_OLLAMA_STARTUP_WAIT: float = 3.0

# Maximum health-check retries for Ollama after launch.
_OLLAMA_HEALTH_RETRIES: int = 5

# Delay between Ollama health-check retries (seconds).
_OLLAMA_HEALTH_RETRY_DELAY: float = 1.0

# Maximum retries when polling /readiness after uvicorn start.
_ENGINE_READINESS_RETRIES: int = 30

# Delay between /readiness poll attempts (seconds).
_ENGINE_READINESS_RETRY_DELAY: float = 1.0

# Timeout (seconds) per /readiness HTTP request.
_ENGINE_READINESS_TIMEOUT: float = 2.0

# Sentinel written to stdout when the engine is accepting requests.
ENGINE_READY_SIGNAL: str = "NPC_ENGINE_READY"


async def _wait_for_health(
    check: Callable[[], Awaitable[bool]],
    startup_wait: float,
    retries: int,
    retry_delay: float,
) -> bool:
    """Poll a health check until it passes or the retry limit is hit.

    Args:
        check: Async callable returning True when the service is healthy.
        startup_wait: Seconds to sleep before the first attempt.
        retries: Maximum number of attempts.
        retry_delay: Seconds to sleep between attempts.

    Returns:
        True if the service became healthy within the retry limit.
    """
    await asyncio.sleep(startup_wait)
    for _ in range(retries):
        if await check():
            return True
        await asyncio.sleep(retry_delay)
    return False


class StackLauncher:
    """Start and supervise the full NPC Engine stack for SHIP-04 packaging.

    Launch order: Neo4j → Ollama (if configured) → FastAPI engine (uvicorn).
    Only processes actually started by this instance are terminated on shutdown.
    """

    _neo4j_process: subprocess.Popen[bytes] | None
    _ollama_process: subprocess.Popen[bytes] | None

    def __init__(
        self,
        neo4j_manager: Neo4jManager,
        ollama_manager: OllamaManager | None = None,
        engine_host: str = ENGINE_DEFAULT_HOST,
        engine_port: int = ENGINE_DEFAULT_PORT,
    ) -> None:
        """Initialise the launcher with injected service managers.

        Args:
            neo4j_manager: Manages Neo4j lifecycle (required).
            ollama_manager: Manages Ollama lifecycle (None → local LLM path skipped).
            engine_host: Host for the uvicorn server.
            engine_port: Port for the uvicorn server.
        """
        self._neo4j = neo4j_manager
        self._ollama_manager = ollama_manager
        self._engine_host = engine_host
        self._engine_port = engine_port
        self._neo4j_process = None
        self._ollama_process = None

    async def launch(self) -> None:
        """Start all stack components and block until the engine server exits.

        Raises:
            Neo4jNotInstalledError: If Neo4j is not running and not found on PATH.
            Neo4jStartupError: If Neo4j was launched but did not become healthy.
            OllamaNotInstalledError: If Ollama is configured but not on PATH.
        """
        await self._start_neo4j()
        if self._ollama_manager is not None:
            await self._start_ollama()
        await self._run_engine_server()

    async def _start_neo4j(self) -> None:
        """Ensure Neo4j is running; launch it if not and wait for health.

        Raises:
            Neo4jNotInstalledError: Binary not found.
            Neo4jStartupError: Launched but did not respond in time.
        """
        if await self._neo4j.is_running():
            return
        if not self._neo4j.is_installed():
            raise Neo4jNotInstalledError(
                "Neo4j is not running and not found on PATH. "
                "Install from https://neo4j.com/download/ and add bin/ to PATH."
            )
        self._neo4j_process = self._neo4j.launch()
        healthy = await _wait_for_health(
            self._neo4j.is_running,
            _NEO4J_STARTUP_WAIT,
            _NEO4J_HEALTH_RETRIES,
            _NEO4J_HEALTH_RETRY_DELAY,
        )
        if not healthy:
            raise Neo4jStartupError(
                "Neo4j did not respond after launch — check for port conflicts on :7474/:7687."
            )

    async def _start_ollama(self) -> None:
        """Ensure Ollama is running; launch it if not and wait for health.

        Raises:
            OllamaNotInstalledError: Binary not found on PATH.
        """
        assert self._ollama_manager is not None
        if await self._ollama_manager.is_running():
            return
        self._ollama_process = self._ollama_manager.launch()
        await _wait_for_health(
            self._ollama_manager.is_running,
            _OLLAMA_STARTUP_WAIT,
            _OLLAMA_HEALTH_RETRIES,
            _OLLAMA_HEALTH_RETRY_DELAY,
        )

    async def _check_ready(self, url: str) -> bool:
        """Return True if a single GET to url responds with HTTP 200."""
        try:
            async with httpx.AsyncClient(timeout=_ENGINE_READINESS_TIMEOUT) as client:
                resp = await client.get(url)
            return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def _poll_readiness(self) -> bool:
        """Poll GET /readiness until the engine accepts requests or retries are exhausted.

        Returns:
            True if the engine became ready within the retry limit, False otherwise.
        """
        url = f"http://{self._engine_host}:{self._engine_port}/readiness"
        for _ in range(_ENGINE_READINESS_RETRIES):
            if await self._check_ready(url):
                return True
            await asyncio.sleep(_ENGINE_READINESS_RETRY_DELAY)
        return False

    async def _run_engine_server(self) -> None:
        """Start the FastAPI engine via uvicorn, poll /readiness, then block until exit.

        Emits ENGINE_READY_SIGNAL to stdout once the engine is accepting requests so
        that the Unity game process can begin its first REST call. If readiness is not
        confirmed within the retry window, the process continues (degraded start).
        """
        config = uvicorn.Config(
            ENGINE_APP_IMPORT,
            host=self._engine_host,
            port=self._engine_port,
        )
        server = uvicorn.Server(config)
        server_task = asyncio.create_task(server.serve())
        ready = await self._poll_readiness()
        if ready:
            sys.stdout.write(f"{ENGINE_READY_SIGNAL}\n")
            sys.stdout.flush()
        else:
            sys.stderr.write("WARNING: engine did not become ready in time\n")
            sys.stderr.flush()
        await server_task

    def shutdown(self) -> None:
        """Terminate any processes started by this launcher (Neo4j and/or Ollama)."""
        if self._neo4j_process is not None:
            self._neo4j_process.terminate()
        if self._ollama_process is not None:
            self._ollama_process.terminate()
