"""
Module: test_no_silent_drops
Layer: test (unit)
Purpose: EVAL-P15.5 — verify that the 16 silent-drop sites in evals/ either raise a
         domain error or log with the dropped item's identity rather than discarding data
         without signal.  A fixture with one corrupt line must produce a loud failure,
         not a quietly smaller n.
Dependencies: pytest, compare, context_capture, calibration, calibration_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from calibration_records import CalibrationLabel
from verdict_sources import load_unified_rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_calibration_label(*, scorer_verdict: bool, human_verdict: bool) -> CalibrationLabel:
    """Build a minimal CalibrationLabel with all required fields set."""
    return CalibrationLabel(
        record_id="r0",
        scorer="tone_judge",
        output_text="hi",
        scorer_verdict=scorer_verdict,
        pre_label=scorer_verdict,
        pre_labeller_model="oracle",
        human_verdict=human_verdict,
        adjudicated_at="2026-01-01T00:00:00Z",
        notes="",
    )


# ---------------------------------------------------------------------------
# RED anchor — compare.py:133
# ---------------------------------------------------------------------------


def test_malformed_judged_row_raises_rather_than_shrinking_the_denominator(
    tmp_path: Path,
) -> None:
    """A malformed line in judged.jsonl must raise rather than silently shrink the row count.

    verdict_sources.load_unified_rows delegates to _read_judged_file which raises ValueError
    on any row missing required fields — a corrupt row must never silently shrink the
    denominator that compare and summarize rely on.
    """
    gen_dir = tmp_path / "gen"
    gen_dir.mkdir()
    valid_row = json.dumps({
        "record_id": "case_001:tone_judge:0",
        "case_id": "case_001",
        "judge_kind": "tone_judge",
        "passed": True,
        "score": True,
        "detail": "",
        "judge_model": "m",
        "repetition": 0,
    })
    malformed_row = '{"x": 1}'  # missing required fields record_id and passed
    (gen_dir / "judged.jsonl").write_text(
        f"{valid_row}\n{malformed_row}\n", encoding="utf-8"
    )

    with pytest.raises(ValueError):
        load_unified_rows(gen_dir)


# ---------------------------------------------------------------------------
# context_capture.py:59
# ---------------------------------------------------------------------------


def test_context_capture_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """An HTTP failure in context_capture must produce a log entry, not a silent empty tuple."""
    from context_capture import capture_retrieval_context

    mock_client: MagicMock = MagicMock(spec=httpx.Client)
    mock_client.get.side_effect = ConnectionError("connection refused")

    with caplog.at_level(logging.WARNING, logger="context_capture"):
        result = capture_retrieval_context(mock_client, "http://nowhere", "npc_test", "hello")

    assert result == ()
    assert caplog.records, "expected at least one log record on HTTP failure"
    combined = " ".join(r.getMessage() for r in caplog.records)
    assert "npc_test" in combined, "log must identify the NPC whose retrieval failed"


# ---------------------------------------------------------------------------
# calibration.py:232 and :268
# ---------------------------------------------------------------------------


def test_degenerate_bootstrap_sample_drop_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Degenerate bootstrap samples dropped from kappa_interval must be logged."""
    from calibration import kappa_interval

    rows = [
        _make_calibration_label(scorer_verdict=True, human_verdict=True)
        for _ in range(5)
    ]

    with patch("calibration.cohens_kappa", side_effect=ValueError("Pe=1 degenerate")):
        with caplog.at_level(logging.WARNING, logger="calibration"):
            with pytest.raises(ValueError):
                # All samples degenerate → kappas empty → should raise and log
                kappa_interval(rows, resamples=3, seed=0)

    assert caplog.records, "expected a log entry for dropped degenerate bootstrap samples"


def test_pre_label_degenerate_bootstrap_sample_drop_is_logged(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Degenerate bootstrap samples dropped from pre_label_kappa_interval must be logged."""
    from calibration import pre_label_kappa_interval

    rows = [
        _make_calibration_label(scorer_verdict=True, human_verdict=True)
        for _ in range(5)
    ]

    with patch("calibration.pre_label_kappa", side_effect=ValueError("Pe=1 degenerate")):
        with caplog.at_level(logging.WARNING, logger="calibration"):
            with pytest.raises(ValueError):
                pre_label_kappa_interval(rows, resamples=3, seed=0)

    assert caplog.records, "expected a log entry for dropped pre-label degenerate bootstrap samples"


# ---------------------------------------------------------------------------
# generation_collection.post_dialogue (was generate_runner._post_dialogue)
# ---------------------------------------------------------------------------


def test_post_dialogue_failure_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    """A network failure in post_dialogue must produce a log entry, not a silent empty dict."""
    from generation_collection import post_dialogue

    mock_client: MagicMock = MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = ConnectionError("refused")

    with caplog.at_level(logging.WARNING, logger="generation_collection"):
        result = post_dialogue("npc_a", "player_1", "hi", mock_client, "http://nowhere")

    assert result == {}
    assert caplog.records, "expected a log entry on post_dialogue failure"


# ---------------------------------------------------------------------------
# calibration_records.py:146
# ---------------------------------------------------------------------------


def test_unreadable_calibration_file_is_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A corrupt labels file treated as containing human work must be logged."""
    from calibration_records import _holds_human_work as _has_human_work

    corrupt = tmp_path / "labels.jsonl"
    corrupt.write_bytes(b"\xff\xfe")  # invalid UTF-8, will raise on read

    with caplog.at_level(logging.WARNING, logger="calibration_records"):
        result = _has_human_work(corrupt)

    assert result is True  # conservative: treat as human work
    assert caplog.records, "expected a log entry for the unreadable calibration file"
