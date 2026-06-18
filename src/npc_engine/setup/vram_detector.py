"""
Module: vram_detector
Layer: config
Purpose: Detect available GPU VRAM in MiB using platform-appropriate tools
         (nvidia-smi on NVIDIA hardware; returns 0 for CPU-only or undetectable).
Dependencies: stdlib subprocess only.
Used by: npc_engine.setup.first_run_flow
Does NOT: call any engine, graph, or LLM layer.
Dependencies injected: None.
"""
from __future__ import annotations

import subprocess

# Timeout (seconds) for the nvidia-smi subprocess call.
_NVIDIA_SMI_TIMEOUT: int = 10


def detect_vram_mb() -> int:
    """Return available VRAM in MiB; 0 if no GPU is detected or detectable.

    Tries NVIDIA first (via nvidia-smi). Additional GPU vendors (AMD, Intel Arc)
    are not queried in this slice — they fall through to 0, which maps to the 3B
    model tier (safe default on any hardware).

    Returns:
        VRAM in MiB (>= 0). 0 means "no GPU" or "detection failed".
    """
    nvidia = _detect_nvidia_vram_mb()
    if nvidia > 0:
        return nvidia
    return 0


def _detect_nvidia_vram_mb() -> int:
    """Query nvidia-smi for total VRAM on the first GPU. Returns 0 on any failure.

    Returns:
        VRAM of the first NVIDIA GPU in MiB, or 0 if nvidia-smi is unavailable,
        times out, or returns a non-zero exit code.
    """
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=_NVIDIA_SMI_TIMEOUT,
        )
        if result.returncode != 0:
            return 0
        lines = result.stdout.strip().splitlines()
        if not lines:
            return 0
        return int(lines[0].strip())
    except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
        return 0
