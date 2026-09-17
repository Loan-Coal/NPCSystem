"""
Module: llm_warmup
Layer: config
Purpose: Issue one minimal generation at startup so the LLM backend loads the model
         before the first real player request arrives.
Does NOT: implement retry logic, validate output, or import from any engine/graph layer.
Dependencies injected: LLM adapter (any object with a compatible generate() method).
Used by: npc_engine.main lifespan.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Protocol

import yaml

_logger = logging.getLogger(__name__)

# Path to the versioned warm-up prompt YAML (CLAUDE.md forbids prompt strings outside prompts/).
_WARMUP_PROMPT_PATH: Path = (
    Path(__file__).resolve().parent.parent / "prompts" / "warmup" / "warmup_v1.yaml"
)

# One token is enough to force a model load; zero temperature avoids stochastic variance.
_WARMUP_MAX_TOKENS: int = 1
_WARMUP_TEMPERATURE: float = 0.0


class _GenerateCapable(Protocol):
    """Minimal structural protocol — any adapter with a generate() method qualifies.

    Defined locally so this module stays in the setup layer (rank 1) without importing
    from engines (rank 5), per the layer rule in CLAUDE.md / check_layers.py.

    Signature mirrors LLMGenerateProtocol exactly so mypy accepts LLMClientProtocol
    instances without an import from the engines layer.
    """

    async def generate(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> str:
        """Generate plain-text output."""
        ...


def _load_warmup_prompt() -> str:
    """Read the warm-up prompt text from the versioned YAML.

    Returns:
        The prompt string from warmup_v1.yaml.
    """
    data = yaml.safe_load(_WARMUP_PROMPT_PATH.read_text(encoding="utf-8"))
    return str(data["prompt"])


async def warm_up_llm(adapter: _GenerateCapable, *, enabled: bool) -> None:
    """Issue one minimal generation to load the LLM model before the first player turn.

    Fails soft: any exception from the adapter is logged as a warning and swallowed
    so warm-up failure never blocks boot (Finding L9-04, SEV-05).

    Args:
        adapter: An LLM adapter exposing a generate() coroutine.
        enabled: When False, returns immediately without any I/O.
    """
    if not enabled:
        return
    try:
        prompt = _load_warmup_prompt()
        await adapter.generate(
            prompt=prompt,
            max_tokens=_WARMUP_MAX_TOKENS,
            temperature=_WARMUP_TEMPERATURE,
        )
        _logger.info("llm.warmup_complete")
    except Exception:
        _logger.warning("llm.warmup_failed — continuing without pre-loaded model")
