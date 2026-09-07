"""
Module: ollama_payload
Layer: engines
Purpose: Shape the options and request-body dicts for one Ollama /api/generate call, so
         the three OllamaAdapter methods share one definition of the wire format instead
         of hand-building it three times.
Does NOT: perform I/O, read Settings, choose a temperature, or decide a residency policy —
          every value is resolved by the caller and passed in.
Dependencies: typing (stdlib) only.
Used by: npc_engine.engines.llm.ollama_adapter.
"""

from __future__ import annotations

from typing import Any


def build_ollama_options(
    *,
    max_tokens: int,
    temperature: float,
    num_ctx: int,
    top_p: float | None = None,
    stop_sequences: list[str] | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    """Assemble the Ollama ``options`` block for one generation request.

    Args:
        max_tokens: Maximum tokens to generate (sent as num_predict).
        temperature: Sampling temperature the caller has already resolved.
        num_ctx: KV-cache window for this request.
        top_p: Nucleus sampling mass. None means backend default.
        stop_sequences: Halting sequences (sent as stop). None means backend default.
        seed: Deterministic sampling seed. None means backend default.
    Returns:
        Options dict carrying only the keys the caller actually supplied.
    """
    options: dict[str, Any] = {
        "num_predict": max_tokens,
        "temperature": temperature,
        "num_ctx": num_ctx,
    }
    if top_p is not None:
        options["top_p"] = top_p
    if stop_sequences is not None:
        options["stop"] = stop_sequences
    if seed is not None:
        options["seed"] = seed
    return options


def build_ollama_payload(
    *,
    model: str,
    prompt: str,
    options: dict[str, Any],
    keep_alive: str,
    stream: bool = False,
    schema: dict[str, Any] | None = None,
    system: str | None = None,
) -> dict[str, Any]:
    """Assemble the top-level Ollama /api/generate request body.

    ``keep_alive`` is a TOP-LEVEL field. Placed inside ``options`` it is accepted and
    silently ignored, leaving the model on its default eviction timer.

    Args:
        model: Ollama model tag.
        prompt: Formatted prompt string.
        options: Sampling options from build_ollama_options.
        keep_alive: Go duration string controlling model residency after the request.
        stream: True to request a streamed response.
        schema: JSON schema constraining output shape. None means unconstrained.
        system: System channel text. None means omit the key entirely.
    Returns:
        Request body dict carrying only the keys the caller actually supplied.
    """
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": stream,
        "keep_alive": keep_alive,
        "options": options,
    }
    if schema is not None:
        payload["format"] = schema
    if system is not None:
        payload["system"] = system
    return payload
