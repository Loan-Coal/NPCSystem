"""
degradation.py - Tiered executor for graceful dialogue degradation.
Layer: engines
Purpose: Tiered executor for graceful dialogue degradation.

Does NOT: call LLM or graph services directly.

Dependencies injected: coroutine factories for full and graph-only tiers.
"""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal

import yaml

from npc_engine.engines.dialogue.dialogue_models import ActionModel, DialogueResponse, FacialExpressionModel, RelationDeltas
from npc_engine.utils.metrics import increment_metric


_logger = logging.getLogger(__name__)

DegradationLevel = Literal["full", "graph_only", "canned"]
DEGRADATION_METRIC = "dialogue_degradation_level_total"


def _load_canned_text(archetype: str, canned_dir: Path) -> str:
    for name in (archetype, "default"):
        candidate = canned_dir / f"{name}.yaml"
        if candidate.exists():
            try:
                data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
                responses: list[str] = data.get("responses", [])
                if responses:
                    return random.choice(responses)
            except Exception as exc:
                _logger.warning(
                    "canned_response_load_failed",
                    extra={"archetype": name, "path": str(candidate), "error": str(exc)},
                )
    return "I need a moment to think."


def _canned_dialogue_response(archetype: str, canned_dir: Path) -> DialogueResponse:
    text = _load_canned_text(archetype=archetype, canned_dir=canned_dir)
    return DialogueResponse(
        npc_response=text,
        relation_deltas=RelationDeltas(),
        action=ActionModel(),
        facial_expression=FacialExpressionModel(),
        degradation_level="canned",
    )


def get_canned_response(archetype: str, canned_dir: Path) -> DialogueResponse:
    """Return a canned DialogueResponse for the given archetype.

    Public helper so the dialogue handler can substitute a canned response
    when output moderation flags an over-ceiling LLM reply.

    Args:
        archetype: NPC archetype key; falls back to "default" if not found.
        canned_dir: Directory containing per-archetype YAML files.

    Returns:
        DialogueResponse with degradation_level="canned".
    """
    return _canned_dialogue_response(archetype=archetype, canned_dir=canned_dir)


async def execute_with_degradation(
    *,
    full_factory: Callable[[], Awaitable[DialogueResponse]],
    graph_only_factory: Callable[[], Awaitable[DialogueResponse]],
    archetype: str,
    canned_dir: Path,
    full_timeout: float,
    graph_only_timeout: float,
) -> tuple[DialogueResponse, DegradationLevel]:
    """Execute dialogue with tiered degradation: full → graph_only → canned.

    Each tier is attempted in order; the first success is returned. Failures
    are logged as warnings and the next tier is tried immediately.

    Args:
        full_factory: Async factory for the full LLM + RAG tier.
        graph_only_factory: Async factory for the graph-only (no RAG) tier.
        archetype: NPC archetype string used to select canned response file.
        canned_dir: Directory containing per-archetype canned response YAML files.
        full_timeout: Timeout in seconds for the full tier.
        graph_only_timeout: Timeout in seconds for the graph-only tier.

    Returns:
        Tuple of (DialogueResponse, DegradationLevel) where DegradationLevel
        indicates which tier produced the response.
    """

    try:
        result = await asyncio.wait_for(full_factory(), timeout=full_timeout)
        increment_metric(DEGRADATION_METRIC, labels={"level": "full"})
        return result, "full"
    except Exception as exc:
        _logger.warning(
            "Dialogue full tier failed (%s: %s), trying graph_only",
            type(exc).__name__,
            exc,
            exc_info=True,
        )

    try:
        result = await asyncio.wait_for(graph_only_factory(), timeout=graph_only_timeout)
        increment_metric(DEGRADATION_METRIC, labels={"level": "graph_only"})
        return result, "graph_only"
    except Exception as exc:
        _logger.warning(
            "Dialogue graph_only tier failed (%s: %s), using canned response",
            type(exc).__name__,
            exc,
            exc_info=True,
        )

    increment_metric(DEGRADATION_METRIC, labels={"level": "canned"})
    return _canned_dialogue_response(archetype=archetype, canned_dir=canned_dir), "canned"
