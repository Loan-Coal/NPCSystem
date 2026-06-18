"""
Module: launcher
Layer: harness (repo-level entry point, outside the package layer model)
Purpose: Full-stack launcher for the packaged NPC Engine (SHIP-04). Starts Neo4j,
         optionally Ollama (local-inference path), then serves the FastAPI engine
         via uvicorn. Intended to be compiled by PyInstaller into a standalone binary
         that the Unity game process spawns on startup and kills on exit.
Dependencies: npc_engine.setup.stack_launcher, npc_engine.setup.neo4j_manager,
              npc_engine.setup.ollama_manager; stdlib asyncio/sys.
Used by: PyInstaller packaging (packaging/npc_engine.spec); direct dev invocation.
"""
from __future__ import annotations

import asyncio
import os
import sys

from npc_engine.setup.neo4j_manager import Neo4jManager, Neo4jNotInstalledError, Neo4jStartupError
from npc_engine.setup.ollama_manager import OllamaManager, OllamaNotInstalledError
from npc_engine.setup.stack_launcher import ENGINE_DEFAULT_HOST, ENGINE_DEFAULT_PORT, StackLauncher

# Environment variable to disable the local Ollama path (API-key mode).
_ENV_DISABLE_OLLAMA: str = "NPC_ENGINE_NO_OLLAMA"

# Exit codes for well-known failure modes.
_EXIT_NEO4J_NOT_INSTALLED: int = 2
_EXIT_NEO4J_STARTUP_FAILED: int = 3
_EXIT_OLLAMA_NOT_INSTALLED: int = 4
_EXIT_UNKNOWN_ERROR: int = 1


def _build_launcher() -> StackLauncher:
    """Construct a StackLauncher using environment-driven configuration.

    Returns:
        A StackLauncher ready to call ``.launch()``.
    """
    neo4j = Neo4jManager()
    ollama: OllamaManager | None = None
    if not os.environ.get(_ENV_DISABLE_OLLAMA):
        ollama = OllamaManager()
    return StackLauncher(
        neo4j_manager=neo4j,
        ollama_manager=ollama,
        engine_host=ENGINE_DEFAULT_HOST,
        engine_port=ENGINE_DEFAULT_PORT,
    )


async def _main() -> int:
    """Run the full stack and return an exit code.

    Returns:
        0 on clean exit; a non-zero exit code on known failure modes.
    """
    print("NPC Engine — starting stack...", flush=True)
    launcher = _build_launcher()
    try:
        await launcher.launch()
        return 0
    except Neo4jNotInstalledError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return _EXIT_NEO4J_NOT_INSTALLED
    except Neo4jStartupError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return _EXIT_NEO4J_STARTUP_FAILED
    except OllamaNotInstalledError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        return _EXIT_OLLAMA_NOT_INSTALLED
    except Exception as exc:
        print(f"FATAL: unexpected error — {exc}", file=sys.stderr, flush=True)
        return _EXIT_UNKNOWN_ERROR
    finally:
        launcher.shutdown()


def main() -> None:
    """Synchronous entry point — wraps ``_main`` with ``asyncio.run``."""
    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
