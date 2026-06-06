"""
Module: distortion_strategy
Layer: engines
Purpose: DistortionStrategy Protocol and STRATEGY_REGISTRY mapping stable keys to callables.
Does NOT: perform I/O, call LLMs, or access the graph.
Dependencies: engines/gossip/strategies/*
Dependencies injected: None.
Used by: gossip_distort.py
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from npc_engine.engines.gossip.strategies.omission import omission
from npc_engine.engines.gossip.strategies.exaggeration import exaggeration
from npc_engine.engines.gossip.strategies.role_swap import role_swap
from npc_engine.engines.gossip.strategies.timeline_shift import timeline_shift


@runtime_checkable
class DistortionStrategy(Protocol):
    """Callable that applies a single distortion type to a raw event summary.

    Implementors receive the raw summary string and return the distorted version.
    The Protocol is ``runtime_checkable`` so ``isinstance`` checks work in tests.
    """

    def __call__(self, summary: str) -> str:
        """Apply the distortion and return the modified summary.

        Args:
            summary: Raw event summary text.

        Returns:
            Distorted summary string.
        """
        ...


# Index order must match the legacy distortion_types list in gossip_distort.py:
#   index 0 → omission
#   index 1 → exaggeration
#   index 2 → role_swap
#   index 3 → timeline_shift
# Changing this order would alter the seed→strategy mapping and break determinism.
STRATEGY_REGISTRY: dict[str, DistortionStrategy] = {
    "omission": omission,
    "exaggeration": exaggeration,
    "role_swap": role_swap,
    "timeline_shift": timeline_shift,
}

REGISTRY_KEYS: tuple[str, ...] = tuple(STRATEGY_REGISTRY)
