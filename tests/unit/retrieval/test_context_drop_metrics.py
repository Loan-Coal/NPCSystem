"""
Module: test_context_drop_metrics
Layer: tests/unit
Purpose: Verify dropped context items are counted by tier and reason (RET-P0.2).
Dependencies: context_merger, context_metrics, utils.metrics
Used by: pytest test runner
"""

from __future__ import annotations

import pytest

from npc_engine.retrieval.context import ContextItem, MergedContext
from npc_engine.retrieval.context.context_metrics import (
    CONTEXT_ITEMS_DROPPED_METRIC,
    record_drop_metrics,
)
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


@pytest.fixture(autouse=True)
def _isolated_metrics_registry() -> None:
    """Reset counters before each test.

    Autouse fixture rather than `setup_function`, which pytest does not apply to
    methods inside a test class — these counters are process-global, so without
    this the tests pass alone and fail in a full-suite run.
    """
    reset_metrics_registry()


def _item(key: str, tier: str, priority: int = 50) -> ContextItem:
    """Build a small context item for drop accounting."""
    return ContextItem(key=key, text=f"{key}-payload", tier=tier, priority=priority)


class TestRecordDropMetrics:
    """Drop accounting between the pre-budget and post-budget contexts."""

    def test_dropped_items_are_counted_by_tier_and_reason(self) -> None:
        """Each item present before budgeting and absent after is counted once."""
        pre = MergedContext(
            items=[
                _item("world", "tier0"),
                _item("beliefs", "tierA"),
                _item("goals", "tierA"),
                _item("rag:evt_1", "tierB"),
            ]
        )
        post = MergedContext(items=[_item("world", "tier0")])

        record_drop_metrics(
            pre_budget_context=pre,
            post_budget_context=post,
            reason="prompt_budget",
        )

        assert (
            get_counter_value(
                CONTEXT_ITEMS_DROPPED_METRIC,
                labels={"tier": "tiera", "reason": "prompt_budget"},
            )
            == 2.0
        )
        assert (
            get_counter_value(
                CONTEXT_ITEMS_DROPPED_METRIC,
                labels={"tier": "tierb", "reason": "prompt_budget"},
            )
            == 1.0
        )

    def test_no_metric_emitted_when_nothing_is_dropped(self) -> None:
        """A context that survives budgeting emits no drop counter."""
        context = MergedContext(items=[_item("world", "tier0"), _item("beliefs", "tierA")])

        record_drop_metrics(
            pre_budget_context=context,
            post_budget_context=context,
            reason="prompt_budget",
        )

        assert (
            get_counter_value(
                CONTEXT_ITEMS_DROPPED_METRIC,
                labels={"tier": "tiera", "reason": "prompt_budget"},
            )
            == 0.0
        )

    def test_pinned_tier0_survival_means_no_tier0_drops(self) -> None:
        """Tier 0 is never dropped, so it must never appear in the drop counter."""
        pre = MergedContext(items=[_item("world", "tier0"), _item("beliefs", "tierA")])
        post = MergedContext(items=[_item("world", "tier0")])

        record_drop_metrics(
            pre_budget_context=pre,
            post_budget_context=post,
            reason="tier_soft_cap",
        )

        assert (
            get_counter_value(
                CONTEXT_ITEMS_DROPPED_METRIC,
                labels={"tier": "tier0", "reason": "tier_soft_cap"},
            )
            == 0.0
        )
