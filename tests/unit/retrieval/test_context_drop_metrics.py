"""
Module: test_context_drop_metrics
Layer: tests/unit
Purpose: Verify dropped context items are counted by tier and reason (RET-P0.2), and that
         each of the three drop reasons is now distinguishable (P4 / ISSUE-197).
Dependencies: context_metrics, context_receipt, utils.metrics
Used by: pytest test runner

Rewritten in P4: `record_drop_metrics` took the pre- and post-budget contexts and a SINGLE
reason for all of them, so every production drop was labelled `prompt_budget` whatever
stage removed it, and `tier_soft_cap` and `final_trim` were declared but never emitted.
`record_attributed_drop_metrics` takes the already-attributed drops instead, because the
enforcer is the only thing that knows which stage removed which item — a set difference
between two contexts cannot recover it.
"""

from __future__ import annotations

import pytest

from npc_engine.retrieval.context.context_metrics import (
    CONTEXT_ITEMS_DROPPED_METRIC,
    record_attributed_drop_metrics,
)
from npc_engine.retrieval.context.context_receipt import DroppedItem
from npc_engine.utils.metrics import get_counter_value, reset_metrics_registry


@pytest.fixture(autouse=True)
def _isolated_metrics_registry() -> None:
    """Reset counters before each test.

    Autouse fixture rather than `setup_function`, which pytest does not apply to
    methods inside a test class — these counters are process-global, so without
    this the tests pass alone and fail in a full-suite run.
    """
    reset_metrics_registry()


def _drop(key: str, tier: str, reason: str = "prompt_budget") -> DroppedItem:
    """Build one attributed drop."""
    return DroppedItem(key=key, tier=tier, reason=reason)  # type: ignore[arg-type]


def _counter(tier: str, reason: str) -> float:
    return get_counter_value(
        CONTEXT_ITEMS_DROPPED_METRIC, labels={"tier": tier, "reason": reason}
    )


class TestRecordAttributedDropMetrics:
    """Drop accounting over the attributed drops the enforcer reports."""

    def test_dropped_items_are_counted_by_tier_and_reason(self) -> None:
        """Each attributed drop is counted once against its own tier and reason."""
        record_attributed_drop_metrics([
            _drop("beliefs", "tierA"),
            _drop("goals", "tierA"),
            _drop("rag:evt_1", "tierB"),
        ])

        assert _counter("tiera", "prompt_budget") == 2.0
        assert _counter("tierb", "prompt_budget") == 1.0

    def test_no_metric_emitted_when_nothing_is_dropped(self) -> None:
        """A context that survives budgeting emits no drop counter."""
        record_attributed_drop_metrics([])

        assert _counter("tiera", "prompt_budget") == 0.0

    def test_pinned_tier0_survival_means_no_tier0_drops(self) -> None:
        """Tier 0 is never dropped, so it must never appear in the drop counter."""
        record_attributed_drop_metrics([_drop("world", "tier0", "tier_soft_cap")])

        assert _counter("tier0", "tier_soft_cap") == 0.0

    def test_the_same_tier_is_split_across_the_reasons_that_produced_it(self) -> None:
        """The point of P4: two tier-A drops for different reasons are two counters.

        Before P4 the caller passed one reason for the whole batch, so this distinction
        could not be represented at all — every drop read as `prompt_budget`.
        """
        record_attributed_drop_metrics([
            _drop("memories", "tierA", "tier_soft_cap"),
            _drop("secrets", "tierA", "tier_soft_cap"),
            _drop("beliefs", "tierA", "prompt_budget"),
            _drop("nearby_npcs", "tierA", "final_trim"),
        ])

        assert _counter("tiera", "tier_soft_cap") == 2.0
        assert _counter("tiera", "prompt_budget") == 1.0
        assert _counter("tiera", "final_trim") == 1.0

    @pytest.mark.parametrize("reason", ["tier_soft_cap", "prompt_budget", "final_trim"])
    def test_every_declared_reason_can_actually_be_emitted(self, reason: str) -> None:
        """Two of the three enum members had no emitter anywhere in the engine."""
        record_attributed_drop_metrics([_drop("beliefs", "tierA", reason)])

        assert _counter("tiera", reason) == 1.0
