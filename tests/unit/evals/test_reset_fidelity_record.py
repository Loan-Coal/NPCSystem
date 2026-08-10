"""
Module: test_reset_fidelity_record
Layer: test (unit)
Purpose: Unit tests for reset_fidelity_record.py — the evals/reset_fidelity.json
         artifact model and the tier rule behind it. The rule under test is the
         one docs/SEQUENCE_STATS_POLICY.md §2 states: FULL only if NOTHING
         survives, PARTIAL otherwise, and no third tier. These tests exist
         because "a tier chosen because it keeps a metric alive is the single
         worst outcome available here, and it would be invisible to every gate
         in the repo" (EVAL-P12.1). After this file it is visible to one.
Dependencies: json, pydantic, pytest, reset_fidelity_record, sequence_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from reset_fidelity_record import (
    UNKNOWN_PREFIX,
    ResetFidelityReport,
    assign_tier,
    mark_unknown,
)
from sequence_records import ResetReceipt

_CLEARED = ("world_state.epoch", "world_state.active_conditions")
_MEASURED_AT = "2026-08-10T12:00:00+00:00"
_GIT_SHA = "c0c3836"


def _report(**overrides: object) -> ResetFidelityReport:
    fields: dict[str, object] = {
        "fidelity": "PARTIAL",
        "cleared": _CLEARED,
        "surviving": ("emotion_store",),
        "duration_ms": 12,
        "measured_at": _MEASURED_AT,
        "git_sha": _GIT_SHA,
    }
    fields.update(overrides)
    return ResetFidelityReport(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# The tier rule
# ---------------------------------------------------------------------------


def test_full_requires_that_nothing_survives() -> None:
    assert assign_tier(()) == "FULL"


@pytest.mark.parametrize(
    "surviving",
    [("emotion_store",), ("a", "b"), (mark_unknown("session_store"),)],
)
def test_anything_surviving_is_partial(surviving: tuple[str, ...]) -> None:
    assert assign_tier(surviving) == "PARTIAL"


def test_there_is_no_third_tier() -> None:
    """SEQUENCE_STATS_POLICY §2 admits exactly two. 'mostly full' is how a
    correlated run acquires an interval it has not earned."""
    with pytest.raises(ValidationError):
        _report(fidelity="MOSTLY_FULL", surviving=())


# ---------------------------------------------------------------------------
# The tier cannot be declared against the evidence
# ---------------------------------------------------------------------------


def test_declaring_full_while_something_survives_raises() -> None:
    """The failure mode this whole task exists to prevent, made mechanical."""
    with pytest.raises(ValidationError) as excinfo:
        _report(fidelity="FULL", surviving=("emotion_store",))
    assert "emotion_store" in str(excinfo.value)


def test_declaring_full_while_an_unobservable_store_is_unknown_raises() -> None:
    """An unobservable store is not an absent one. Silently dropping it is
    exactly how PARTIAL becomes a false FULL."""
    with pytest.raises(ValidationError):
        _report(fidelity="FULL", surviving=(mark_unknown("session_store"),))


def test_declaring_partial_while_nothing_survives_raises() -> None:
    """The tier is derived from the evidence in both directions, never asserted."""
    with pytest.raises(ValidationError):
        _report(fidelity="PARTIAL", surviving=())


def test_a_consistent_full_report_is_accepted() -> None:
    report = _report(fidelity="FULL", surviving=())
    assert report.fidelity == "FULL"


def test_a_consistent_partial_report_is_accepted() -> None:
    assert _report().fidelity == "PARTIAL"


# ---------------------------------------------------------------------------
# Unobservable stores
# ---------------------------------------------------------------------------


def test_mark_unknown_prefixes_the_store_name() -> None:
    assert mark_unknown("session_store") == f"{UNKNOWN_PREFIX}session_store"


def test_unknown_entries_are_reported_separately_but_still_count_as_surviving() -> None:
    report = _report(surviving=("emotion_store", mark_unknown("session_store")))
    assert report.unobservable == ("session_store",)
    assert report.observed_surviving == ("emotion_store",)
    assert report.fidelity == "PARTIAL"


def test_a_report_whose_only_survivors_are_unknown_is_still_partial() -> None:
    report = _report(surviving=(mark_unknown("dialogue_context_cache"),))
    assert report.fidelity == "PARTIAL"
    assert report.observed_surviving == ()


# ---------------------------------------------------------------------------
# The EVAL-P12.1 validation: the document parses into ResetReceipt unrenamed
# ---------------------------------------------------------------------------


def test_the_emitted_document_parses_into_reset_receipt_with_no_field_renaming() -> None:
    document = json.loads(_report().model_dump_json())
    receipt = ResetReceipt.model_validate(document)
    assert receipt.cleared == _CLEARED
    assert receipt.surviving == ("emotion_store",)
    assert receipt.duration_ms == 12


def test_reset_receipt_ignores_the_three_envelope_keys_rather_than_rejecting_them() -> None:
    """Pins the extra='ignore' default this shape relies on. If ResetReceipt is
    ever given extra='forbid', evals/reset_fidelity.json stops being readable
    and this test says so instead of EVAL-P12.4 discovering it at runtime."""
    document = json.loads(_report().model_dump_json())
    assert {"fidelity", "measured_at", "git_sha"} <= set(document)
    receipt = ResetReceipt.model_validate(document)
    assert not hasattr(receipt, "fidelity")


def test_the_document_carries_every_field_the_runbook_names() -> None:
    document = json.loads(_report().model_dump_json())
    assert {"fidelity", "surviving", "duration_ms", "measured_at", "git_sha"} <= set(document)
