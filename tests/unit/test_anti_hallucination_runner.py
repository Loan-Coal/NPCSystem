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
    _belief_fact_persisted,
    _classify_case,
    format_summary,
    run,
)


def _make_belief_response(content: str, is_deception: bool) -> MagicMock:
    """Mock GET /beliefs response carrying one belief with an is_deception flag (F2.5/F3.3)."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": {"beliefs": [{"content": content, "confidence": 80, "is_deception": is_deception}]},
        "meta": None,
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def test_planted_deception_not_scored_as_hallucination() -> None:
    """F3.3: an NPC voicing a planted is_deception belief is 'intended', not refusal_fail."""
    lie = "the eastern road is perfectly safe"
    case = {"id": "dcp", "npc_id": "npc_a", "question": "is the eastern road safe?", "expected_verdict": "refusal"}
    client = MagicMock()
    client.post.return_value = _make_dialogue_response(lie)
    client.get.return_value = _make_belief_response(lie, is_deception=True)

    result, outcome = _classify_case(case, client, "http://x")

    assert outcome == "deception_intended"
    assert result["passed"] is True


def test_ordinary_unsupported_claim_still_fails() -> None:
    """An unsupported claim with no is_deception belief is still a refusal_fail (hallucination)."""
    claim = "the eastern road is perfectly safe"
    case = {"id": "hal", "npc_id": "npc_a", "question": "is the eastern road safe?", "expected_verdict": "refusal"}
    client = MagicMock()
    client.post.return_value = _make_dialogue_response(claim)
    client.get.return_value = _make_belief_response(claim, is_deception=False)

    result, outcome = _classify_case(case, client, "http://x")

    assert outcome == "refusal_fail"
    assert result["passed"] is False


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

LEARNED_FROM_PLAYER_CASE = {
    "id": "test_learned_player",
    "world": "demo",
    "npc_id": "mira_innkeeper",
    "question": "Do you remember what I told you about the eastern road?",
    "expected_verdict": "grounded",
    "knowledge_basis": "Player-taught BELIEVES edge (player_sourced=true).",
    "expected_fact_substrings": ["eastern", "road"],
    "preflight_belief_substrings": ["eastern", "road"],
    "category": "learned_from_player",
    "notes": "Player-taught fact: grounded if the NPC recalls it.",
}


def _make_beliefs_response(contents: list[str]) -> MagicMock:
    """Return a mock httpx Response for GET /v1/admin/beliefs/{npc_id}."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "success": True,
        "data": {"beliefs": [{"content": c, "confidence": 80} for c in contents]},
        "meta": None,
    }
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _get_router(health_resp: MagicMock, beliefs_resp: MagicMock):
    """Build a side_effect routing GET /health vs the beliefs pre-flight endpoint."""

    def _route(url: str, **_kwargs: object) -> MagicMock:
        return health_resp if url.endswith("/health") else beliefs_resp

    return _route


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


# ---------------------------------------------------------------------------
# Test 9: learned_from_player — fact persisted → scored as grounded, PASS
# ---------------------------------------------------------------------------


def test_learned_from_player_runs_grounded_when_belief_persisted(tmp_path: Path) -> None:
    """learned_from_player: pre-flight finds the persisted belief → grounded PASS, exit 0."""
    fixture = _write_fixture(tmp_path, [LEARNED_FROM_PLAYER_CASE])
    report_dir = tmp_path / "reports"

    health_resp = _make_health_response()
    beliefs_resp = _make_beliefs_response(["the eastern road is washed out"])
    dialogue_resp = _make_dialogue_response("Aye, you told me the eastern road is washed out.")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = _get_router(health_resp, beliefs_resp)
        mock_client.post.return_value = dialogue_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 10: learned_from_player — fact not persisted → SKIP (counts unaffected)
# ---------------------------------------------------------------------------


def test_learned_from_player_skips_when_belief_absent(tmp_path: Path) -> None:
    """learned_from_player: pre-flight finds no matching belief → skipped, exit 0 (not scored)."""
    fixture = _write_fixture(tmp_path, [LEARNED_FROM_PLAYER_CASE])
    report_dir = tmp_path / "reports"

    health_resp = _make_health_response()
    beliefs_resp = _make_beliefs_response([])  # nothing persisted
    # A non-grounded answer that WOULD fail if scored — proves the case was skipped, not scored.
    dialogue_resp = _make_dialogue_response("The weather is fine today.")

    with patch("httpx.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = _get_router(health_resp, beliefs_resp)
        mock_client.post.return_value = dialogue_resp

        exit_code = run(
            base_url="http://localhost:8000",
            api_key="test-key",
            fixture_path=fixture,
            report_dir=report_dir,
        )

    assert exit_code == 0


# ---------------------------------------------------------------------------
# Test 11: _belief_fact_persisted helper — match / no-match / empty / error
# ---------------------------------------------------------------------------


def test_belief_fact_persisted_matches_content() -> None:
    """Returns True when a belief content contains one of the substrings."""
    client = MagicMock()
    client.get.return_value = _make_beliefs_response(["the eastern road is washed out"])
    assert _belief_fact_persisted(
        "mira_innkeeper", client, "http://localhost:8000", ["eastern", "road"]
    )


def test_belief_fact_persisted_false_when_no_match() -> None:
    """Returns False when no belief content matches any substring."""
    client = MagicMock()
    client.get.return_value = _make_beliefs_response(["the price of bread rose"])
    assert not _belief_fact_persisted(
        "mira_innkeeper", client, "http://localhost:8000", ["eastern", "road"]
    )


def test_belief_fact_persisted_false_when_no_substrings() -> None:
    """Returns False (cannot verify) when the case supplies no pre-flight substrings."""
    client = MagicMock()
    assert not _belief_fact_persisted("mira_innkeeper", client, "http://localhost:8000", [])


def test_belief_fact_persisted_false_on_query_error() -> None:
    """Returns False (→ skip) when the beliefs query raises."""
    client = MagicMock()
    client.get.side_effect = RuntimeError("connection refused")
    assert not _belief_fact_persisted(
        "mira_innkeeper", client, "http://localhost:8000", ["eastern"]
    )
