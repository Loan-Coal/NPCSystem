"""
Module: test_sequence_fidelity
Layer: test (unit)
Purpose: Tests for evals/sequence_fidelity.py — deriving a SequenceRun's reset-fidelity
         tier from its repetitions' ResetReceipts, and withholding the Wilson interval
         at the runner level (ISSUE-143) whenever the tier is PARTIAL.
Dependencies: pytest, sequence_fidelity (evals/), sequence_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import pytest

from sequence_fidelity import SequenceStat, derive_fidelity, sequence_stat
from sequence_records import ResetReceipt

_FULL_RECEIPT = ResetReceipt(cleared=("world_state.epoch",), surviving=(), duration_ms=54)
_PARTIAL_RECEIPT = ResetReceipt(
    cleared=("world_state.epoch",), surviving=("emotion_store",), duration_ms=54
)


# ---------------------------------------------------------------------------
# RED anchor: PARTIAL fidelity withholds the interval
# ---------------------------------------------------------------------------


def test_partial_fidelity_run_has_no_interval() -> None:
    """A run with at least one PARTIAL receipt reports fidelity=PARTIAL and interval=None."""
    receipts = (_FULL_RECEIPT, _PARTIAL_RECEIPT, _FULL_RECEIPT)
    stat = sequence_stat("scenario_gossip_chain", passes=2, receipts=receipts)

    assert stat.fidelity == "PARTIAL"
    assert stat.interval is None


# ---------------------------------------------------------------------------
# FULL fidelity still reports an interval
# ---------------------------------------------------------------------------


def test_full_fidelity_run_has_interval() -> None:
    """A run where every receipt cleared everything reports fidelity=FULL with an interval."""
    receipts = (_FULL_RECEIPT, _FULL_RECEIPT, _FULL_RECEIPT)
    stat = sequence_stat("scenario_reputation_drift", passes=3, receipts=receipts)

    assert stat.fidelity == "FULL"
    assert stat.interval is not None
    lo, hi = stat.interval
    assert 0.0 <= lo <= hi <= 1.0


# ---------------------------------------------------------------------------
# derive_fidelity: one PARTIAL receipt demotes the whole run
# ---------------------------------------------------------------------------


def test_one_partial_receipt_demotes_entire_run() -> None:
    """Per SEQUENCE_STATS_POLICY §1: the run's fidelity is the minimum across receipts."""
    receipts = (_FULL_RECEIPT, _FULL_RECEIPT, _PARTIAL_RECEIPT)
    assert derive_fidelity(receipts) == "PARTIAL"


def test_all_full_receipts_yield_full_fidelity() -> None:
    """Only unanimous FULL receipts produce a FULL run."""
    receipts = (_FULL_RECEIPT, _FULL_RECEIPT)
    assert derive_fidelity(receipts) == "FULL"


def test_derive_fidelity_empty_receipts_raises() -> None:
    """A run's fidelity is undefined with zero repetitions."""
    with pytest.raises(ValueError):
        derive_fidelity(())


# ---------------------------------------------------------------------------
# SequenceStat carries k, passes, pass_rate and classification regardless of tier
# ---------------------------------------------------------------------------


def test_sequence_stat_fields_present_at_partial_fidelity() -> None:
    """Descriptive fields (k, passes, pass_rate, classification) survive the downgrade."""
    receipts = (_PARTIAL_RECEIPT, _PARTIAL_RECEIPT, _PARTIAL_RECEIPT)
    stat = sequence_stat("scenario_grief_persistence", passes=2, receipts=receipts)

    assert stat.k == 3
    assert stat.passes == 2
    assert stat.pass_rate == pytest.approx(2 / 3)
    assert stat.classification == "flaky"
    assert stat.interval is None


def test_sequence_stat_is_immutable() -> None:
    """SequenceStat is frozen — attribute assignment raises."""
    stat = sequence_stat("scenario_x", passes=1, receipts=(_FULL_RECEIPT,))
    with pytest.raises(Exception):
        stat.passes = 99  # type: ignore[misc]


def test_sequence_stat_empty_receipts_raises() -> None:
    """sequence_stat cannot compute k from zero receipts."""
    with pytest.raises(ValueError):
        sequence_stat("scenario_x", passes=0, receipts=())
