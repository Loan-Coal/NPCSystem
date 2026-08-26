"""
Module: prompt_eval_log
Layer: engines
Purpose: Emit the one structured record that says what the LLM backend actually
         tokenised for a request, so prompt truncation is observable.
Does NOT: call the backend, parse generation output, or log prompt text.
Dependencies injected: every value is passed per call; nothing is read from Settings.
Used by: the Ollama HTTP adapter (engines.llm).
"""

from __future__ import annotations

import logging
from typing import Any

__all__ = ["PROMPT_EVAL_LOG_EVENT", "log_prompt_eval"]

_LOGGER = logging.getLogger(__name__)

PROMPT_EVAL_LOG_EVENT = "llm_prompt_eval"
"""Structured-log event name carrying what the backend actually tokenised.

``num_ctx`` is sent on every request and Ollama silently truncates a prompt that
exceeds it, so ``prompt_eval_count`` is the only evidence that the assembled context
reached the model rather than being cut off before it. This record carries token and
character COUNTS only -- never prompt text -- so it is emitted unconditionally and is
independent of ``config.LOG_LLM_PROMPTS``.

Character counts are logged raw rather than converted to tokens: the engine's own
``len // 4`` estimate is exactly the number this record exists to check, so dividing
here would hide the discrepancy it is meant to expose.
"""


def log_prompt_eval(
    *,
    reply: dict[str, Any],
    options: dict[str, Any],
    model: str,
    prompt: str,
    system: str | None,
) -> None:
    """Record the backend's own token accounting for one request.

    Never raises: a missing or malformed counter must not fail a generation that
    otherwise succeeded. ``prompt_eval_count`` is absent from some backend replies
    (and from every streamed chunk but the last), so it is logged as None rather
    than defaulted to zero -- "not reported" and "zero tokens" are different facts.

    Args:
        reply: Parsed backend reply, read for ``prompt_eval_count`` / ``eval_count``.
        options: The ``options`` block sent with the request (``num_ctx``, ``num_predict``).
        model: Model tag the request ran against.
        prompt: Prompt text, measured but never logged.
        system: System prompt text, measured but never logged.
    """
    _LOGGER.info(
        "llm prompt eval",
        extra={
            "event": PROMPT_EVAL_LOG_EVENT,
            "model": model,
            "prompt_eval_count": reply.get("prompt_eval_count"),
            "eval_count": reply.get("eval_count"),
            "num_ctx": options.get("num_ctx"),
            "num_predict": options.get("num_predict"),
            "prompt_chars": len(prompt),
            "system_chars": len(system) if system is not None else 0,
        },
    )
