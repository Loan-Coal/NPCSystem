"""
Module: first_run_flow
Layer: config
Purpose: Orchestrate the SHIP-03 local-inference first-run flow: detect VRAM, pick
         a model tier, ensure Ollama is running, pull the model if absent.
Dependencies: npc_engine.setup.vram_detector, model_tiers, ollama_manager; asyncio; pydantic.
Used by: scripts/setup_local.py (CLI entry point).
Does NOT: import any engine, graph, or API layer.
Dependencies injected: api_base URL (FirstRunFlow constructor).
"""
from __future__ import annotations

import asyncio
import enum
from collections.abc import Callable

from pydantic import BaseModel

from npc_engine.setup.model_tiers import select_model_for_vram
from npc_engine.setup.ollama_manager import OllamaManager, OllamaNotInstalledError
from npc_engine.setup.vram_detector import detect_vram_mb

# How long (seconds) to wait for Ollama to start after launching.
_OLLAMA_STARTUP_WAIT: float = 3.0

# How many times to retry the health check after launching Ollama.
_HEALTH_CHECK_RETRIES: int = 5

# Delay between health-check retries (seconds).
_HEALTH_RETRY_DELAY: float = 1.0


class FirstRunStatus(str, enum.Enum):
    """Outcome codes returned by FirstRunFlow.run()."""

    READY = "ready"
    NOT_INSTALLED = "not_installed"
    LAUNCH_FAILED = "launch_failed"
    PULL_FAILED = "pull_failed"


class FirstRunResult(BaseModel):
    """Result of a first-run flow execution.

    Attributes:
        status: Outcome code — ``READY`` means the engine can connect to Ollama
            and the model is available.
        model_name: The Ollama model tag that was selected or already available.
        message: Human-readable explanation (empty string on success).
    """

    status: FirstRunStatus
    model_name: str
    message: str = ""


class FirstRunFlow:
    """Orchestrate local-inference first-run setup for SHIP-03.

    Steps:
    1. Detect VRAM and pick the right model tier.
    2. Check if Ollama is already running; if not, check if it's installed and launch.
    3. Check if the selected model is already pulled; pull it if not.
    4. Return a ``FirstRunResult`` with status ``READY`` when done.
    """

    def __init__(
        self,
        api_base: str = "http://localhost:11434",
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Initialise the flow.

        Args:
            api_base: Ollama server URL. Defaults to the localhost standard.
            progress_callback: Optional callable receiving human-readable progress
                strings during model pull.
        """
        self._manager = OllamaManager(api_base=api_base)
        self._progress_callback = progress_callback

    async def run(self) -> FirstRunResult:
        """Execute the full first-run flow and return the outcome.

        Returns:
            FirstRunResult with status READY if everything succeeded, or a
            non-READY status with a descriptive message on failure.
        """
        vram_mb = detect_vram_mb()
        model_name = select_model_for_vram(vram_mb)

        running = await self._manager.is_running()
        if not running:
            result = await self._ensure_ollama_running(model_name)
            if result is not None:
                return result

        if not await self._manager.is_model_available(model_name):
            result = await self._pull_model(model_name)
            if result is not None:
                return result

        return FirstRunResult(status=FirstRunStatus.READY, model_name=model_name)

    async def _ensure_ollama_running(self, model_name: str) -> FirstRunResult | None:
        """Try to launch Ollama and wait for it to become ready.

        Args:
            model_name: Selected model (used only in the error result).

        Returns:
            A non-READY FirstRunResult on failure, or None if Ollama is now up.
        """
        if not self._manager.is_installed():
            return FirstRunResult(
                status=FirstRunStatus.NOT_INSTALLED,
                model_name=model_name,
                message=(
                    "Ollama is not installed. "
                    "Download from https://ollama.com/download and re-run."
                ),
            )
        try:
            self._manager.launch()
        except OllamaNotInstalledError as exc:
            return FirstRunResult(
                status=FirstRunStatus.NOT_INSTALLED,
                model_name=model_name,
                message=str(exc),
            )
        await asyncio.sleep(_OLLAMA_STARTUP_WAIT)
        for _ in range(_HEALTH_CHECK_RETRIES):
            if await self._manager.is_running():
                return None
            await asyncio.sleep(_HEALTH_RETRY_DELAY)
        return FirstRunResult(
            status=FirstRunStatus.LAUNCH_FAILED,
            model_name=model_name,
            message="Ollama did not respond after launch — check for port conflicts.",
        )

    async def _pull_model(self, model_name: str) -> FirstRunResult | None:
        """Pull *model_name* via Ollama. Returns a non-READY result on failure.

        Args:
            model_name: Ollama model tag to pull.

        Returns:
            A PULL_FAILED FirstRunResult on error, or None on success.
        """
        try:
            await self._manager.pull_model(
                model_name, progress_callback=self._progress_callback
            )
            return None
        except Exception as exc:
            return FirstRunResult(
                status=FirstRunStatus.PULL_FAILED,
                model_name=model_name,
                message=f"Model pull failed: {exc}",
            )
