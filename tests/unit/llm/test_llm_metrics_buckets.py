"""
test_llm_metrics_buckets.py - Verify ISSUE-318 and ISSUE-319 fixes.

Two defects in the metrics DEC-273 introduced:
(1) llm_backend_latency_seconds had no histogram buckets, so p50/p95 were not derivable.
(2) llm_tokens_in_total excluded the system channel (4.3x under-count).

Does NOT: call a live LLM backend or access Neo4j.

Dependencies injected: FakeLLMClient, monkeypatched metrics registry.
"""

from __future__ import annotations

from pathlib import Path
from time import perf_counter
from typing import Any, AsyncIterator

import pytest

from npc_engine.engines.dialogue.llm_client import DialogueLLMClient
from npc_engine.engines.llm.llm_metrics import LATENCY_BUDGET_BUCKETS, record_llm_backend_metrics
from npc_engine.utils.metrics import get_counter_value, get_metrics_registry, reset_metrics_registry

_FALLBACK_PATH = str(
    Path(__file__).resolve().parents[3] / "src" / "npc_engine" / "data" / "fallback_responses.json"
)
_LABELS = {"backend": "ollama", "engine": "dialogue", "model": "qwen2_5_7b", "mode": "generate"}


class _FakeLLMClient:
    """Minimal fake LLM client for token-counting tests."""

    async def generate_structured(
        self,
        prompt: str,
        schema: dict[str, Any],
        max_tokens: int,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> dict[str, Any]:
        """Return a minimal valid DialogueGeneration payload."""
        return {
            "npc_response": "hello",
            "relation_deltas": {"trust": 0, "fear": 0, "affection": 0},
            "mood_update": None,
            "action": {"type": "speak", "target_id": None, "parameters": {}},
            "facial_expression": {"type": "neutral", "intensity": 20},
        }

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
        return "ok"

    async def stream(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        top_p: float | None = None,
        stop_sequences: list[str] | None = None,
        system: str | None = None,
        seed: int | None = None,
    ) -> AsyncIterator[str]:
        yield "ok"

    def model_name(self) -> str:
        return "mock"


def setup_function() -> None:
    reset_metrics_registry()


# ---------------------------------------------------------------------------
# ISSUE-319 — latency metric must expose histogram buckets spanning the budget
# ---------------------------------------------------------------------------


def test_latency_metric_snapshot_contains_histograms_key() -> None:
    """record_llm_backend_metrics must write to the histograms, not observations."""
    record_llm_backend_metrics(
        backend="ollama",
        engine="dialogue",
        model="qwen2.5:7b",
        mode="generate",
        started_at=perf_counter() - 0.1,
    )
    snap = get_metrics_registry().snapshot()
    assert "histograms" in snap, "snapshot must have a 'histograms' key (ISSUE-319)"


def test_latency_budget_buckets_straddle_three_and_seven_seconds() -> None:
    """Bucket boundaries must include both 3.0 and 7.0 so budget breaches are visible."""
    assert 3.0 in LATENCY_BUDGET_BUCKETS, "budget lower bound 3s must be a bucket boundary"
    assert 7.0 in LATENCY_BUDGET_BUCKETS, "budget upper bound 7s must be a bucket boundary"


def test_latency_observation_lands_in_correct_bucket() -> None:
    """A 4.5s observation must fall in ≤5.0 but not ≤3.0."""
    record_llm_backend_metrics(
        backend="ollama",
        engine="dialogue",
        model="qwen2.5:7b",
        mode="generate",
        started_at=perf_counter() - 4.5,
    )
    snap = get_metrics_registry().snapshot()
    hist_key = next(k for k in snap["histograms"] if k.startswith("llm_backend_latency_seconds"))
    buckets = snap["histograms"][hist_key]["buckets"]

    assert "3.0" in buckets, "3.0s bucket boundary must be present"
    assert "7.0" in buckets, "7.0s bucket boundary must be present"
    assert buckets["3.0"] == 0.0, "4.5s must not land in ≤3.0 bucket"
    assert buckets.get("5.0", 0.0) == 1.0 or buckets.get("7.0", 0.0) == 1.0, (
        "4.5s must appear in ≤5.0 or ≤7.0 bucket"
    )


# ---------------------------------------------------------------------------
# ISSUE-318 — llm_tokens_in_total must include system channel
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tokens_in_includes_system_channel() -> None:
    """When system is provided, llm_tokens_in_total must count both prompt and system tokens."""
    # 400 chars / 4 = 100 token estimate; 40 chars / 4 = 10 token estimate
    system = "s" * 400
    prompt = "p" * 40
    client = DialogueLLMClient(
        llm_client=_FakeLLMClient(),
        fallback_path=_FALLBACK_PATH,
        max_tokens=512,
        temperature=0.7,
        top_p=0.95,
        stop_sequences=[],
    )
    await client.generate_response(prompt=prompt, system=system)

    tokens_in = get_counter_value(
        "llm_tokens_in_total",
        labels={"engine": "dialogue", "backend": "mock", "mode": "structured"},
    )
    # 100 system + 10 prompt = 110; today only 10 (prompt only) → fails
    assert tokens_in == 110.0, (
        f"llm_tokens_in_total must include system channel tokens, got {tokens_in} (ISSUE-318)"
    )


@pytest.mark.asyncio
async def test_tokens_in_without_system_unchanged() -> None:
    """When system is None, llm_tokens_in_total must still count only the prompt."""
    prompt = "p" * 40
    client = DialogueLLMClient(
        llm_client=_FakeLLMClient(),
        fallback_path=_FALLBACK_PATH,
        max_tokens=512,
        temperature=0.7,
        top_p=0.95,
        stop_sequences=[],
    )
    await client.generate_response(prompt=prompt, system=None)

    tokens_in = get_counter_value(
        "llm_tokens_in_total",
        labels={"engine": "dialogue", "backend": "mock", "mode": "structured"},
    )
    assert tokens_in == 10.0
