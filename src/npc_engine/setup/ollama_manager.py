"""
Module: ollama_manager
Layer: config
Purpose: Manage the Ollama local-inference server lifecycle — detect if installed,
         launch the background daemon, check whether a model is available, and stream
         a model pull (resumable via Ollama's chunked pull API).
Dependencies: stdlib shutil/subprocess, httpx (async HTTP).
Used by: npc_engine.setup.first_run_flow
Does NOT: call any engine, graph, or API layer.
Dependencies injected: api_base URL (OllamaManager constructor).
"""
from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

import httpx

# Default Ollama server address — same as Settings.OLLAMA_API_URL default.
OLLAMA_API_BASE: str = "http://localhost:11434"

# API endpoint paths (no trailing slash, appended to api_base).
_TAGS_PATH: str = "/api/tags"
_PULL_PATH: str = "/api/pull"

# Ollama daemon startup delay (seconds) to await before the first health check.
_LAUNCH_WAIT_SECONDS: float = 3.0

# httpx read-timeout for pull streaming (seconds per chunk; pulls can be slow).
_PULL_READ_TIMEOUT: float = 120.0

# httpx connect-timeout for health checks.
_HEALTH_TIMEOUT: float = 5.0


class OllamaNotInstalledError(Exception):
    """Raised when the ollama binary is not found on PATH and cannot be launched."""


class OllamaManager:
    """Manage the Ollama server process and model lifecycle for SHIP-03.

    All remote calls use httpx.AsyncClient so they are awaitable and fully
    mockable in unit tests without patching the event loop.
    """

    def __init__(self, api_base: str = OLLAMA_API_BASE) -> None:
        """Initialise the manager with the Ollama API base URL.

        Args:
            api_base: Root URL of the Ollama server (trailing slash stripped).
        """
        self._api_base = api_base.rstrip("/")

    # ------------------------------------------------------------------
    # Install / process management (synchronous — subprocess calls)
    # ------------------------------------------------------------------

    def is_installed(self) -> bool:
        """Return True if the ``ollama`` binary is on PATH.

        Returns:
            True if ``shutil.which("ollama")`` finds the binary.
        """
        return shutil.which("ollama") is not None

    def launch(self) -> subprocess.Popen[bytes]:
        """Start ``ollama serve`` as a background process.

        Returns:
            The running ``subprocess.Popen`` instance.

        Raises:
            OllamaNotInstalledError: If the ollama binary is not found on PATH.
        """
        try:
            return subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise OllamaNotInstalledError(
                "ollama binary not found on PATH — install from https://ollama.com/download"
            ) from exc

    # ------------------------------------------------------------------
    # API health / model availability (async — httpx calls)
    # ------------------------------------------------------------------

    async def is_running(self) -> bool:
        """Return True if the Ollama API endpoint responds with HTTP 200.

        Returns:
            True if ``GET /api/tags`` returns 200, False on any error.
        """
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
                resp = await client.get(f"{self._api_base}{_TAGS_PATH}")
                return resp.status_code == 200
        except Exception:
            return False

    async def is_model_available(self, model_name: str) -> bool:
        """Return True if *model_name* is listed in the local Ollama model registry.

        Args:
            model_name: Ollama model tag (e.g. ``"qwen2.5:7b"``).

        Returns:
            True if the model is already pulled, False otherwise or on API error.
        """
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
                resp = await client.get(f"{self._api_base}{_TAGS_PATH}")
            if resp.status_code != 200:
                return False
            payload: dict[str, Any] = resp.json()
            models: list[dict[str, Any]] = payload.get("models", [])
            return any(m.get("name") == model_name for m in models)
        except Exception:
            return False

    async def pull_model(
        self,
        model_name: str,
        progress_callback: Callable[[str], None] | None = None,
    ) -> None:
        """Stream-pull *model_name* from the Ollama registry (resumable).

        Ollama's pull API returns newline-delimited JSON progress chunks; this
        method forwards each ``status`` field to *progress_callback* if provided.
        The pull is inherently resumable — Ollama checks what layers are already
        on disk and only downloads the delta.

        Args:
            model_name: Ollama model tag to pull (e.g. ``"qwen2.5:7b"``).
            progress_callback: Optional callable receiving a human-readable status
                string for each progress chunk (useful for CLI progress display).

        Raises:
            httpx.HTTPError: On connection or HTTP-protocol errors.
        """
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(connect=10.0, read=_PULL_READ_TIMEOUT, write=30.0, pool=5.0)
        ) as client:
            async with client.stream(
                "POST",
                f"{self._api_base}{_PULL_PATH}",
                json={"name": model_name, "stream": True},
            ) as response:
                response.raise_for_status()
                await _consume_pull_stream(response, progress_callback)


async def _consume_pull_stream(
    response: httpx.Response,
    progress_callback: Callable[[str], None] | None,
) -> None:
    """Consume the newline-delimited JSON stream from an Ollama pull response.

    Args:
        response: An open httpx streaming response.
        progress_callback: Optional callable receiving status strings.
    """
    async for line in response.aiter_lines():
        line = line.strip()
        if not line:
            continue
        try:
            chunk: dict[str, Any] = json.loads(line)
        except json.JSONDecodeError:
            continue
        status = chunk.get("status", "")
        if progress_callback is not None and status:
            progress_callback(status)
