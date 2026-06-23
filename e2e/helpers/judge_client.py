"""
Module: judge_client
Layer: e2e (test harness — not part of src/)
Purpose: Single factory for the LLM-as-judge OllamaAdapter, enforcing the
         judge != generation-model separation invariant via judge_config.
Dependencies: httpx, judge_config (evals/), npc_engine.engines.llm.ollama_adapter.
Used by: e2e/scenarios/scenario_llm_judge.py, scenario_demo_game_judge.py.

Consolidates the previously duplicated ``_make_judge()`` / ``_ollama_reachable()``
helpers so both scenario suites build their judge the same way and inherit the
mixtral:8x7b default + collision guard (DEC-143).
"""

from __future__ import annotations

import httpx

# evals/ is on pytest's pythonpath via pyproject.
import judge_config

_REACHABLE_TIMEOUT_S = 2.0
_DEFAULT_JUDGE_TIMEOUT_S = 60.0


def make_judge(*, model: str | None = None, base_url: str | None = None, timeout_s: float = _DEFAULT_JUDGE_TIMEOUT_S):
    """Create an OllamaAdapter for the LLM judge with the separation invariant applied.

    Args:
        model: Explicit judge model; falls back to env JUDGE_MODEL then mixtral:8x7b.
        base_url: Ollama base URL; falls back to env JUDGE_OLLAMA_URL then default.
        timeout_s: Per-request timeout in seconds.
    Returns:
        A configured OllamaAdapter instance.
    Raises:
        JudgeModelCollisionError: If the resolved judge equals an engine generation model.
    """
    from npc_engine.engines.llm.ollama_adapter import OllamaAdapter

    resolved_model = judge_config.resolve_judge_model(requested=model)
    resolved_url = base_url or judge_config.resolve_judge_url()
    return OllamaAdapter(
        base_url=resolved_url,
        model_name=resolved_model,
        timeout_seconds=timeout_s,
    )


def resolve_judge_model() -> str:
    """Return the resolved judge model name (applies the separation invariant)."""
    return judge_config.resolve_judge_model()


def ollama_reachable(model: str, base_url: str | None = None) -> bool:
    """Return True if Ollama is running AND the judge model is pulled.

    Args:
        model: Judge model name expected in the Ollama tag list.
        base_url: Ollama base URL; falls back to env JUDGE_OLLAMA_URL then default.
    Returns:
        True when the model (or its ``:latest`` alias) is available.
    """
    url = base_url or judge_config.resolve_judge_url()
    try:
        resp = httpx.get(f"{url}/api/tags", timeout=_REACHABLE_TIMEOUT_S)
        resp.raise_for_status()
        available = {m["name"] for m in resp.json().get("models", [])}
        return model in available or f"{model}:latest" in available
    except Exception:  # noqa: BLE001 — reachability probe, any failure means "not reachable"
        return False
