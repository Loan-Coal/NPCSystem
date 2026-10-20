"""
Module: llm_metrics
Layer: engines
Purpose: Record the call count, wall-clock latency, and input-token counts of LLM backend
         requests so the dialogue latency budget can be checked against numbers rather than
         impressions.
Does NOT: call a backend, log, shape a request, or decide a residency policy.
Dependencies injected: none — every value is passed per call.
Used by: the Ollama HTTP adapter (engines.llm) and DialogueLLMClient (engines.dialogue).

``llm_backend_latency_seconds`` is a histogram (ISSUE-319 fix) — bucket boundaries in
``LATENCY_BUDGET_BUCKETS`` straddle the 3–7 s dialogue budget so p50/p95 are derivable.

``llm_backend_load_latency_seconds`` stays a summary (count/sum/min/max) because the budget
story for cold loads is different: the ``min`` field is the eviction signal, not a percentile.

``llm_tokens_in_total`` includes both the user prompt and the system channel (ISSUE-318 fix).
Use ``record_llm_input_tokens`` — it ensures neither channel is silently omitted.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Literal, Mapping

from npc_engine.retrieval.context import estimate_tokens
from npc_engine.utils.metrics import increment_metric, observe_histogram_metric, observe_metric

LLM_BACKEND_CALLS_METRIC = "llm_backend_calls_total"
LLM_BACKEND_LATENCY_METRIC = "llm_backend_latency_seconds"
LLM_BACKEND_LOAD_LATENCY_METRIC = "llm_backend_load_latency_seconds"
LLM_BACKEND_QUEUE_WAIT_METRIC = "llm_backend_queue_wait_seconds"
LLM_TOKENS_IN_METRIC = "llm_tokens_in_total"

OLLAMA_BACKEND_LABEL = "ollama"

# Histogram bucket boundaries for llm_backend_latency_seconds.
# Sized around the 3–7 s dialogue budget so a breach is visible without arithmetic.
LATENCY_BUDGET_BUCKETS: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 30.0)

LlmCallMode = Literal["generate", "structured", "stream"]

_NS_PER_SECOND = 1_000_000_000.0


def record_llm_backend_metrics(
    *,
    backend: str,
    engine: str,
    model: str,
    mode: LlmCallMode,
    started_at: float,
    load_duration_ns: Any = None,
) -> None:
    """Count one backend call and observe how long it took.

    Args:
        backend: Adapter family serving the call (e.g. "ollama").
        engine: Engine the adapter was built for, so latency is attributable.
        model: Model tag; sanitised to a label by the registry.
        mode: Which generation method ran.
        started_at: ``perf_counter()`` stamp taken before the request began.
        load_duration_ns: Backend-reported model load time in nanoseconds. Anything
            non-numeric (including an absent field) is skipped rather than observed
            as zero — a faked zero would drag the mean toward "always warm".
    """
    labels = {"backend": backend, "engine": engine, "model": model, "mode": mode}
    increment_metric(metric=LLM_BACKEND_CALLS_METRIC, labels=labels)
    observe_histogram_metric(
        metric=LLM_BACKEND_LATENCY_METRIC,
        value=perf_counter() - started_at,
        buckets=LATENCY_BUDGET_BUCKETS,
        labels=labels,
    )
    if isinstance(load_duration_ns, (int, float)) and not isinstance(load_duration_ns, bool):
        observe_metric(
            metric=LLM_BACKEND_LOAD_LATENCY_METRIC,
            value=float(load_duration_ns) / _NS_PER_SECOND,
            labels=labels,
        )


def record_llm_input_tokens(
    *,
    prompt: str,
    system: str | None,
    labels: Mapping[str, str],
) -> None:
    """Increment llm_tokens_in_total for both prompt and system channels.

    Args:
        prompt: The user/human turn text sent to the model.
        system: The system-channel text, if any (counted separately and added).
        labels: Metric labels; must include engine, backend, and mode.
    """
    token_count = float(estimate_tokens(prompt))
    if system is not None:
        token_count += float(estimate_tokens(system))
    increment_metric(metric=LLM_TOKENS_IN_METRIC, amount=token_count, labels=labels)
