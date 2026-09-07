"""
Module: llm_metrics
Layer: engines
Purpose: Record the call count and wall-clock latency of one LLM backend request, plus the
         model-load time the backend reports, so the dialogue latency budget can be checked
         against a number instead of an impression.
Does NOT: call a backend, log, shape a request, or decide a residency policy.
Dependencies injected: none — every value is passed per call.
Used by: the Ollama HTTP adapter (engines.llm).

Two notes that decide how these numbers may be read.

``observe_metric`` records count/sum/min/max — a summary, not a histogram. There are no
percentiles here, so ``sum / count`` is a mean and must never be quoted as a p50.

``llm_backend_load_latency_seconds`` earns a metric of its own because it is the number
that moves most: a cold load was measured at 10.3s against a 3.49-4.18s warm structured
turn, and it is the only in-process evidence that a model was evicted despite ``keep_alive``.
Its ``min`` is the field to watch — on a warm fleet it sits at zero, and a ``min`` above zero
across a session means eviction is still happening.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Literal

from npc_engine.utils.metrics import increment_metric, observe_metric

LLM_BACKEND_CALLS_METRIC = "llm_backend_calls_total"
LLM_BACKEND_LATENCY_METRIC = "llm_backend_latency_seconds"
LLM_BACKEND_LOAD_LATENCY_METRIC = "llm_backend_load_latency_seconds"

OLLAMA_BACKEND_LABEL = "ollama"

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
    observe_metric(
        metric=LLM_BACKEND_LATENCY_METRIC, value=perf_counter() - started_at, labels=labels
    )
    if isinstance(load_duration_ns, (int, float)) and not isinstance(load_duration_ns, bool):
        observe_metric(
            metric=LLM_BACKEND_LOAD_LATENCY_METRIC,
            value=float(load_duration_ns) / _NS_PER_SECOND,
            labels=labels,
        )
