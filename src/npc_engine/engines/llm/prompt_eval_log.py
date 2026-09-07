"""
Module: prompt_eval_log
Layer: engines
Purpose: Emit the one structured record that says what the LLM backend actually
         tokenised for a request, so prompt truncation is observable.
Does NOT: call the backend, parse generation output, or log prompt or system text — only
          measure it. This record is emitted unconditionally, independently of
          LOG_LLM_PROMPTS, so content must never enter it. It receives the whole request
          payload, which CONTAINS the prompt; a single extra={"payload": payload} would
          leak every prompt into structured logs. Pinned by
          test_the_record_never_contains_prompt_text.
Dependencies injected: every value is passed per call; nothing is read from Settings.
Used by: the Ollama HTTP adapter (engines.llm).
"""

from __future__ import annotations

import logging
from time import perf_counter
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

The four ``*_duration_ms`` fields are Ollama's own accounting, converted from the
nanoseconds it reports. ``load_duration_ms`` is the keep_alive evidence channel: it is
zero on a resident model, and a nonzero value on a warm system means the model was
evicted and paged back in -- measured at 10.3s against a 3.49-4.18s warm structured turn,
which is why ``keep_alive`` is logged beside it. ``duration_ms`` is this process's own
wall clock and so includes HTTP overhead the backend's ``total_duration_ms`` does not;
the gap between the two is the transport cost. On the streaming path ``duration_ms``
measures the whole stream rather than time-to-first-token, which is a different quantity
from the one the non-streaming paths report under the same field name.
"""


_NS_DURATION_FIELDS = (
    "total_duration",
    "load_duration",
    "prompt_eval_duration",
    "eval_duration",
)


def _ns_to_ms(value: Any) -> float | None:
    """Convert a backend nanosecond counter to milliseconds, preserving absence as None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return round(float(value) / 1_000_000.0, 3)


def _backend_timing_ms(reply: dict[str, Any]) -> dict[str, float | None]:
    """Ollama's nanosecond counters as ``<name>_ms``, absent ones preserved as None."""
    return {f"{name}_ms": _ns_to_ms(reply.get(name)) for name in _NS_DURATION_FIELDS}


def log_prompt_eval(
    *,
    reply: dict[str, Any],
    payload: dict[str, Any],
    started_at: float,
) -> None:
    """Record the backend's own token and timing accounting for one request.

    Never raises: a missing or malformed counter must not fail a generation that
    otherwise succeeded. Counters absent from a backend reply are logged as None
    rather than defaulted to zero -- "not reported" and "zero" are different facts,
    and a faked zero ``load_duration`` would read as "the model was warm".

    Args:
        reply: Parsed backend reply, read for token counts and ns durations.
        payload: The request body that was sent. Measured, never logged: it contains
            the prompt, and this record is emitted independently of LOG_LLM_PROMPTS.
        started_at: ``perf_counter()`` stamp taken before the request began.
    """
    options: dict[str, Any] = payload.get("options", {})
    system = payload.get("system")
    _LOGGER.info(
        "llm prompt eval",
        extra={
            "event": PROMPT_EVAL_LOG_EVENT,
            "model": payload.get("model"),
            "duration_ms": round((perf_counter() - started_at) * 1000.0, 3),
            "keep_alive": payload.get("keep_alive"),
            "prompt_eval_count": reply.get("prompt_eval_count"),
            "eval_count": reply.get("eval_count"),
            "num_ctx": options.get("num_ctx"),
            "num_predict": options.get("num_predict"),
            "prompt_chars": len(str(payload.get("prompt", ""))),
            "system_chars": len(system) if isinstance(system, str) else 0,
            **_backend_timing_ms(reply),
        },
    )
