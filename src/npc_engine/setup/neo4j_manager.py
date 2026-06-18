"""
Module: neo4j_manager
Layer: config
Purpose: Manage the Neo4j graph-database lifecycle — detect if installed, check whether
         a server is already running, and launch the background process (SHIP-04).
Dependencies: stdlib shutil/subprocess, httpx (async HTTP health check).
Used by: npc_engine.setup.stack_launcher
Does NOT: call any engine, services, graph, or API layer module.
Dependencies injected: http_url and bolt_url (Neo4jManager constructor).
"""
from __future__ import annotations

import shutil
import subprocess

import httpx

# Default Neo4j HTTP browser/REST endpoint (health check target).
NEO4J_HTTP_URL: str = "http://localhost:7474"

# Default Neo4j Bolt connection URL (returned to callers that open a driver).
NEO4J_BOLT_URL: str = "bolt://localhost:7687"

# httpx connect-timeout for health checks (seconds).
_HEALTH_TIMEOUT: float = 5.0

# neo4j console command arguments (launched as a child process).
_NEO4J_LAUNCH_CMD: tuple[str, ...] = ("neo4j", "console")


class Neo4jNotInstalledError(Exception):
    """Raised when the neo4j binary is not found on PATH and cannot be launched."""


class Neo4jStartupError(Exception):
    """Raised when neo4j was launched but did not become healthy within the retry limit."""


class Neo4jManager:
    """Manage the Neo4j server process lifecycle for SHIP-04.

    Mirrors the OllamaManager pattern: sync process management (shutil/subprocess)
    and async HTTP health checks (httpx).
    """

    def __init__(
        self,
        http_url: str = NEO4J_HTTP_URL,
        bolt_url: str = NEO4J_BOLT_URL,
    ) -> None:
        """Initialise the manager with Neo4j endpoint URLs.

        Args:
            http_url: Neo4j HTTP endpoint used for health checks (default: localhost:7474).
            bolt_url: Bolt connection URL returned to callers (default: localhost:7687).
        """
        self._http_url = http_url.rstrip("/")
        self._bolt_url = bolt_url

    # ------------------------------------------------------------------
    # Install / process management (synchronous — subprocess calls)
    # ------------------------------------------------------------------

    def is_installed(self) -> bool:
        """Return True if the ``neo4j`` binary is on PATH.

        Returns:
            True if ``shutil.which("neo4j")`` resolves the binary.
        """
        return shutil.which("neo4j") is not None

    def launch(self) -> subprocess.Popen[bytes]:
        """Start ``neo4j console`` as a child process.

        Running as a foreground child (not detached) means the caller can
        terminate it cleanly when the game exits.

        Returns:
            The running ``subprocess.Popen`` instance.

        Raises:
            Neo4jNotInstalledError: If the neo4j binary is not found on PATH.
        """
        try:
            return subprocess.Popen(
                list(_NEO4J_LAUNCH_CMD),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except FileNotFoundError as exc:
            raise Neo4jNotInstalledError(
                "neo4j binary not found on PATH. "
                "Download Neo4j Community Edition from https://neo4j.com/download/ "
                "and ensure the bin/ directory is on your PATH."
            ) from exc

    # ------------------------------------------------------------------
    # API health (async — httpx calls)
    # ------------------------------------------------------------------

    async def is_running(self) -> bool:
        """Return True if the Neo4j HTTP endpoint responds with HTTP 200.

        Returns:
            True if ``GET <http_url>`` returns 200, False on any error or
            non-200 response (e.g. server still starting up).
        """
        try:
            async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT) as client:
                resp = await client.get(self._http_url)
                return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    # URL accessor
    # ------------------------------------------------------------------

    def get_bolt_url(self) -> str:
        """Return the Bolt connection URL for this Neo4j instance.

        Returns:
            The bolt URL string (e.g. ``"bolt://localhost:7687"``).
        """
        return self._bolt_url
