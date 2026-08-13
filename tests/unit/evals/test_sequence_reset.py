"""
Module: test_sequence_reset
Layer: test (unit)
Purpose: Tests for evals/sequence_reset.py — building a ResetFn from the EVAL-P12.1
         measurement artifact plus a live-timed reset_world() call.
Dependencies: pytest, sequence_reset (evals/), reset_fidelity_record (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from reset_fidelity_record import ResetFidelityReport
from sequence_reset import load_reset_fidelity_report, make_reset_fn


class _FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code


class _FakeClient:
    """Stands in for httpx.Client: records PATCH calls, always returns 200."""

    def __init__(self) -> None:
        self.patch_calls: list[tuple[str, dict]] = []

    def patch(self, url: str, json: dict, timeout: float) -> _FakeResponse:
        self.patch_calls.append((url, json))
        return _FakeResponse(200)


_SAMPLE_REPORT = ResetFidelityReport(
    fidelity="PARTIAL",
    cleared=("world_state.epoch", "world_state.active_conditions"),
    surviving=("emotion_store", "unknown:session_store"),
    duration_ms=54,
    measured_at="2026-08-10T13:02:13.036302+00:00",
    git_sha="c0c3836",
)


# ---------------------------------------------------------------------------
# load_reset_fidelity_report
# ---------------------------------------------------------------------------


def test_load_reset_fidelity_report_reads_committed_artifact() -> None:
    """The real evals/reset_fidelity.json parses into a ResetFidelityReport."""
    report = load_reset_fidelity_report()
    assert report.fidelity == "PARTIAL"
    assert "emotion_store" in report.surviving


def test_load_reset_fidelity_report_missing_file_raises(tmp_path: Path) -> None:
    """A missing artifact must fail loudly rather than assume a tier."""
    with pytest.raises(FileNotFoundError):
        load_reset_fidelity_report(tmp_path / "does_not_exist.json")


# ---------------------------------------------------------------------------
# make_reset_fn
# ---------------------------------------------------------------------------


def test_reset_fn_calls_patch_and_returns_receipt() -> None:
    """The built ResetFn calls the world_state PATCH endpoint and returns a receipt."""
    client = _FakeClient()
    reset_fn = make_reset_fn(client, "http://localhost:8000", report=_SAMPLE_REPORT)

    receipt = reset_fn()

    assert len(client.patch_calls) == 1
    assert receipt.cleared == _SAMPLE_REPORT.cleared
    assert receipt.surviving == _SAMPLE_REPORT.surviving
    assert receipt.duration_ms >= 0


def test_reset_fn_carries_measured_report_not_a_fabricated_full_tier() -> None:
    """A PARTIAL-fidelity report's surviving set is never silently dropped to ()."""
    client = _FakeClient()
    reset_fn = make_reset_fn(client, "http://localhost:8000", report=_SAMPLE_REPORT)

    receipt = reset_fn()

    assert receipt.surviving != ()


def test_reset_fn_repeated_calls_each_patch_once() -> None:
    """Each call to the returned ResetFn issues exactly one PATCH."""
    client = _FakeClient()
    reset_fn = make_reset_fn(client, "http://localhost:8000", report=_SAMPLE_REPORT)

    reset_fn()
    reset_fn()
    reset_fn()

    assert len(client.patch_calls) == 3
