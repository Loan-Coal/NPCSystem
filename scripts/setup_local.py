"""
Module: setup_local
Layer: harness (repo-level dev tool, outside the package layer model)
Purpose: CLI entry point for SHIP-03 first-run local-inference setup. Detects VRAM,
         ensures Ollama is running, and pulls the appropriate model tier.
Dependencies: npc_engine.setup.first_run_flow.
Used by: game launcher (SHIP-04) and manual dev invocation.
"""
from __future__ import annotations

import asyncio
import sys

from npc_engine.setup.first_run_flow import FirstRunFlow, FirstRunStatus

# Exit codes: 0 = ready, 1 = not installed, 2 = launch failed, 3 = pull failed.
_EXIT_CODES: dict[FirstRunStatus, int] = {
    FirstRunStatus.READY: 0,
    FirstRunStatus.NOT_INSTALLED: 1,
    FirstRunStatus.LAUNCH_FAILED: 2,
    FirstRunStatus.PULL_FAILED: 3,
}


def _progress(msg: str) -> None:
    """Print a pull-progress line to stdout."""
    print(f"  [{msg}]", flush=True)


async def _main() -> int:
    """Run the first-run flow and return an exit code.

    Returns:
        Integer exit code (0 = success).
    """
    print("NPC Engine — local inference setup", flush=True)
    print("Detecting VRAM and checking Ollama...", flush=True)

    flow = FirstRunFlow(progress_callback=_progress)
    result = await flow.run()

    if result.status == FirstRunStatus.READY:
        print(f"Ready. Model: {result.model_name}", flush=True)
    else:
        print(f"Setup failed ({result.status.value}): {result.message}", file=sys.stderr, flush=True)

    return _EXIT_CODES.get(result.status, 1)


def main() -> None:
    """Synchronous entry point — wraps ``_main`` with ``asyncio.run``."""
    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main()
