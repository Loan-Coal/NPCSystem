"""
Tests for evals/anti_hallucination_runner.py.

All tests use mock httpx — no live HTTP calls.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add evals/ to path so the runner module is importable without installing it
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "evals"))

from anti_hallucination_runner import (
    AntiHallucinationSummary,
    _REFUSAL_KEYWORDS,
    format_summary,
    run,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GROUNDED_CASE = {
    "id": "test_grounded_pass",
    "world": "demo",
    "npc_id": "captain_sorn",
    "question": "What's happening in the north?",
    "expected_verdict": "grounded",
    "knowledge_basis": "KNOWS_ABOUT northern_war_begins",
    "expected_fact_substrings": ["war", "north"],
    "category": "should_know",
}

GROUNDED_NO_MATCH_CASE = {
    "id": "test_grounded_fail",
    "world": "demo",
    "npc_id": "captain_sorn",
    "question": "What's happening in the north?",
    "expected_verdict": "grounded",
    "knowledge_basis": "KNOWS_ABOUT northern_war_begins",
    "expected_fact_substrings": ["war", "north"],
    "category": "should_know",
}

REFUSAL_PASS_CASE = {
    "id": "test_refusal_pass",
    "world": "demo",
    "npc_id": "captain_sorn",
    "question": "Tell me about the plague at the eastern docks.",
    "expected_verdict": "refusal",
    "knowledge_basis": "No plague knowledge.",
    "expected_fact_substrings": [],
    "category": "should_refuse",
}

REFUSAL_FAIL_CASE = {
    "id": "test_refusal_fail",
    "world": "demo",
    "npc_id": "captain_sorn",
    "question": "Tell me about the plague at the eastern docks.",
    "expected_verdict": "refusal",
    "knowledge_basis": "No plague knowledge.",
    "expected_fact_substrings": [],
    "category": "should_refuse",
}

COMMENT_OBJECT = {
    "_comment": "This is a fixture comment — no id key.",
    "_comment2": "Should be skipped by the runner.",
}


def _make_dialogue_response(npc_text: str) -> MagicMock:
    """Return a mock httpx Response for a dialogue call."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "npc_response": npc_text,
        "relation_deltas": [],
        "action": "idle",
        "facial_expression": "neutral",
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _make_404_response() -> MagicMock:
    """Return a mock httpx Response for a 404 NPC-not-found."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    return mock_resp


def _make_health_response() -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _write_fixture(tmp_path: Path, cases: list) -> Path:
    fixture = tmp_path / "anti_hallucination_demo.json"
    fixture.write_text(json.dumps(cases), encoding="utf-8")
    return fixture


# ---------------------------------------------------------------------------
# Test 1: grounded case — response contains expected substring → PASS
# ---------------------------------------------------------------------------


def test_grounded_case_passes_when_substring_present(tmp_path: Path) -> None:
    """grounded case: response contains expected_fact_substring → grounded_passed += 1, PASS."""
    fixture = _write_fixture(tmp_path, [COMMENT_OBJECT, GROUNDED_CASE])
    report_dir = tmp_path / "reports"

    dialogue_resp = _make_dialogue_response("There is a war to the north, soldier.")
    health_resp = _make_health_response()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = health_resp
        mock_client.post.return_value = dialogue_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 2: grounded case — response missing all substrings → FAIL, over_refusal_count += 1
# ---------------------------------------------------------------------------


def test_grounded_case_fails_when_no_substring_present(tmp_path: Path) -> None:
    """grounded case: response missing all substrings → over_refusal_count += 1, FAIL."""
    fixture = _write_fixture(tmp_path, [COMMENT_OBJECT, GROUNDED_NO_MATCH_CASE])
    report_dir = tmp_path / "reports"

    # Response contains none of ["war", "north"]
    dialogue_resp = _make_dialogue_response("I cannot say anything about that matter.")
    health_resp = _make_health_response()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = health_resp
        mock_client.post.return_value = dialogue_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Test 3: refusal case — response contains "don't know" → PASS, refusal_passed += 1
# ---------------------------------------------------------------------------


def test_refusal_case_passes_when_refusal_keyword_present(tmp_path: Path) -> None:
    """refusal case: response contains 'don't know' → refusal_passed += 1, PASS."""
    fixture = _write_fixture(tmp_path, [COMMENT_OBJECT, REFUSAL_PASS_CASE])
    report_dir = tmp_path / "reports"

    dialogue_resp = _make_dialogue_response("I don't know anything about a plague.")
    health_resp = _make_health_response()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = health_resp
        mock_client.post.return_value = dialogue_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 4: refusal case — response non-empty, no refusal keyword → FAIL, hallucination_count += 1
# ---------------------------------------------------------------------------


def test_refusal_case_fails_when_npc_asserts_without_basis(tmp_path: Path) -> None:
    """refusal case: non-empty response with no refusal keyword → hallucination_count += 1, FAIL."""
    fixture = _write_fixture(tmp_path, [COMMENT_OBJECT, REFUSAL_FAIL_CASE])
    report_dir = tmp_path / "reports"

    # Confident assertion — no refusal keyword
    dialogue_resp = _make_dialogue_response(
        "Yes, the plague has spread from the eastern docks to the market district."
    )
    health_resp = _make_health_response()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = health_resp
        mock_client.post.return_value = dialogue_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    assert exit_code == 1


# ---------------------------------------------------------------------------
# Test 5: NPC 404 → case skipped, counts unchanged
# ---------------------------------------------------------------------------


def test_npc_404_skips_case_and_does_not_affect_counts(tmp_path: Path) -> None:
    """NPC 404 on character check → case skipped, counts unaffected (exit 0)."""
    fixture = _write_fixture(tmp_path, [COMMENT_OBJECT, GROUNDED_CASE])
    report_dir = tmp_path / "reports"

    health_resp = _make_health_response()
    not_found_resp = _make_404_response()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = health_resp
        mock_client.post.return_value = not_found_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    # All cases skipped (404) — no failures, exit 0
    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 6: format_summary with known values → output lines contain expected strings
# ---------------------------------------------------------------------------


def test_format_summary_contains_expected_strings() -> None:
    """format_summary with known AntiHallucinationSummary values → correct lines."""
    summary = AntiHallucinationSummary(
        total=10,
        grounded_total=5,
        grounded_passed=4,
        refusal_total=5,
        refusal_passed=3,
        hallucination_count=2,
        over_refusal_count=1,
    )

    lines = format_summary(summary)
    joined = "\n".join(lines)

    assert "grounded" in joined.lower()
    assert "4/5" in joined
    assert "refusal" in joined.lower()
    assert "3/5" in joined
    assert "hallucination" in joined.lower()
    assert "2" in joined
    assert "over_refusal" in joined.lower() or "over-refusal" in joined.lower() or "over refusal" in joined.lower()


# ---------------------------------------------------------------------------
# Test 7: _REFUSAL_KEYWORDS constant contains required keywords
# ---------------------------------------------------------------------------


def test_refusal_keywords_constant_contains_required_entries() -> None:
    """_REFUSAL_KEYWORDS must be a tuple and contain the canonical refusal phrases."""
    assert isinstance(_REFUSAL_KEYWORDS, tuple)
    assert "don't know" in _REFUSAL_KEYWORDS
    assert "do not know" in _REFUSAL_KEYWORDS
    assert "uncertain" in _REFUSAL_KEYWORDS
    assert "unaware" in _REFUSAL_KEYWORDS
    assert "no idea" in _REFUSAL_KEYWORDS


# ---------------------------------------------------------------------------
# Test 8: comment objects (no "id" key) are skipped
# ---------------------------------------------------------------------------


def test_comment_objects_are_skipped(tmp_path: Path) -> None:
    """Objects without 'id' key (fixture comments) must be skipped silently."""
    fixture = _write_fixture(
        tmp_path,
        [
            {"_comment": "header comment"},
            {"_comment2": "another comment"},
            GROUNDED_CASE,
        ],
    )
    report_dir = tmp_path / "reports"

    dialogue_resp = _make_dialogue_response("There is a war to the north.")
    health_resp = _make_health_response()

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = health_resp
        mock_client.post.return_value = dialogue_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    # Only one real case (grounded, passes) → exit 0
    assert exit_code == 0
