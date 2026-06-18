"""
Module: model_tiers
Layer: config
Purpose: Define size-tiered model names and select the appropriate tier based on
         available VRAM (SHIP-03 local-inference path).
Dependencies: stdlib only.
Used by: npc_engine.setup.first_run_flow
Does NOT: perform I/O; all functions are pure.
Dependencies injected: None.
"""
from __future__ import annotations

# VRAM thresholds (MiB) for tier promotion.
# Below VRAM_TIER_7B_MB → 3B model; at or above VRAM_TIER_14B_MB → 14B model.
VRAM_TIER_7B_MB: int = 4_096
VRAM_TIER_14B_MB: int = 8_192

# Ollama model tags for each tier.  All three share the qwen2.5 family so
# engine-prompt behaviour is consistent regardless of the selected tier.
MODEL_3B: str = "qwen2.5:3b"
MODEL_7B: str = "qwen2.5:7b"
MODEL_14B: str = "qwen2.5:14b"

# Ordered list used by the first-run wizard for display purposes.
ALL_TIERS: tuple[str, ...] = (MODEL_3B, MODEL_7B, MODEL_14B)


def select_model_for_vram(vram_mb: int) -> str:
    """Return the model tag best suited for the detected VRAM capacity.

    Args:
        vram_mb: Available VRAM in MiB (0 if no GPU or undetectable).

    Returns:
        An Ollama model tag string (e.g. ``"qwen2.5:7b"``).
    """
    if vram_mb >= VRAM_TIER_14B_MB:
        return MODEL_14B
    if vram_mb >= VRAM_TIER_7B_MB:
        return MODEL_7B
    return MODEL_3B
