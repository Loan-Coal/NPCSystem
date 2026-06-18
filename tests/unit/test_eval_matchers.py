"""
test_eval_matchers.py - Unit tests for the eval-case expectation matchers.

Exercises evals/matchers.py, the standalone eval harness (not under
src/npc_engine). The evals/ directory is on pytest's pythonpath (pyproject)
so the harness's bare-name imports resolve.

Covers every matcher kind: happy path, failure, and edge cases (empty text,
missing field, non-numeric, unicode keyword, fallback line, judge timeout/
unreachable via a monkeypatched httpx.post).
"""

from __future__ import annotations

import httpx
import pytest

import matchers


def _resp(text: str) -> dict:
    return {
        "npc_response": text,
        "relation_deltas": [],
        "action": "idle",
        "facial_expression": "neutral",
    }


# --- schema -----------------------------------------------------------------

def test_schema_all_fields_present() -> None:
    passed, _ = matchers.evaluate({"kind": "schema"}, _resp("Hello there."))
    assert passed is True


def test_schema_missing_field_fails() -> None:
    resp = _resp("hi")
    del resp["action"]
    passed, detail = matchers.evaluate({"kind": "schema"}, resp)
    assert passed is False
    assert "action" in detail


def test_schema_empty_npc_response_fails() -> None:
    passed, detail = matchers.evaluate({"kind": "schema"}, _resp(""))
    assert passed is False
    assert "npc_response" in detail


def test_schema_whitespace_npc_response_fails() -> None:
    passed, _ = matchers.evaluate({"kind": "schema"}, _resp("   \n\t  "))
    assert passed is False


def test_schema_specific_field_present() -> None:
    passed, _ = matchers.evaluate({"kind": "schema", "field": "action"}, _resp("hi"))
    assert passed is True


def test_schema_specific_field_missing() -> None:
    passed, _ = matchers.evaluate({"kind": "schema", "field": "missing_field"}, _resp("hi"))
    assert passed is False


# --- min_length -------------------------------------------------------------

def test_min_length_pass() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "min_length"}, _resp("This is a sufficiently long answer.")
    )
    assert passed is True


def test_min_length_too_short_fails() -> None:
    passed, detail = matchers.evaluate({"kind": "min_length"}, _resp("No."))
    assert passed is False
    assert "min_length" in detail


def test_min_length_empty_fails() -> None:
    passed, _ = matchers.evaluate({"kind": "min_length"}, _resp(""))
    assert passed is False


def test_min_length_whitespace_only_fails() -> None:
    passed, _ = matchers.evaluate({"kind": "min_length"}, _resp("        "))
    assert passed is False


def test_min_length_custom_threshold() -> None:
    passed, _ = matchers.evaluate({"kind": "min_length", "min": 3}, _resp("hey"))
    assert passed is True


# --- keyword_any / all / none ----------------------------------------------

def test_keyword_any_matches() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "keyword_any", "keywords": ["war", "peace"]}, _resp("Talk of WAR spreads.")
    )
    assert passed is True


def test_keyword_any_no_match_fails() -> None:
    # keyword_any requires at least 2 keywords (SEV-38 guard); use 2 here.
    passed, _ = matchers.evaluate(
        {"kind": "keyword_any", "keywords": ["war", "peace"]}, _resp("Quiet day.")
    )
    assert passed is False


def test_keyword_all_missing_fails() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "keyword_all", "keywords": ["war", "peace"]}, _resp("Talk of war.")
    )
    assert passed is False


def test_keyword_none_clean_passes() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "keyword_none", "keywords": ["i confess"]}, _resp("I know nothing of it.")
    )
    assert passed is True


def test_keyword_none_forbidden_present_fails() -> None:
    passed, detail = matchers.evaluate(
        {"kind": "keyword_none", "keywords": ["i confess"]}, _resp("Fine, I confess it all.")
    )
    assert passed is False
    assert "forbidden" in detail


def test_keyword_none_empty_text_passes_vacuously() -> None:
    # Documents the gap min_length/schema must close: keyword_none alone passes "".
    passed, _ = matchers.evaluate(
        {"kind": "keyword_none", "keywords": ["i confess"]}, _resp("")
    )
    assert passed is True


def test_keyword_unicode() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "keyword_none", "keywords": ["café"]}, _resp("We met at the café.")
    )
    assert passed is False


# --- in_set / range ---------------------------------------------------------

def test_in_set_member() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "in_set", "field": "action", "values": ["idle", "wave"]}, _resp("hi")
    )
    assert passed is True


def test_in_set_non_member_fails() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "in_set", "field": "action", "values": ["wave"]}, _resp("hi")
    )
    assert passed is False


def test_range_within() -> None:
    resp = _resp("hi")
    resp["score"] = 5
    passed, _ = matchers.evaluate({"kind": "range", "field": "score", "min": 0, "max": 10}, resp)
    assert passed is True


def test_range_non_numeric_fails() -> None:
    passed, detail = matchers.evaluate({"kind": "range", "field": "action", "min": 0}, _resp("hi"))
    assert passed is False
    assert "not numeric" in detail


def test_range_below_min_fails() -> None:
    resp = _resp("hi")
    resp["score"] = -1
    passed, _ = matchers.evaluate({"kind": "range", "field": "score", "min": 0}, resp)
    assert passed is False


def test_range_above_max_fails() -> None:
    resp = _resp("hi")
    resp["score"] = 11
    passed, _ = matchers.evaluate({"kind": "range", "field": "score", "max": 10}, resp)
    assert passed is False


# --- substring / regex ------------------------------------------------------

def test_substring_found() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "substring", "substring": "Moment"}, _resp("Give me a moment.")
    )
    assert passed is True


def test_substring_missing_fails() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "substring", "substring": "dragon"}, _resp("Give me a moment.")
    )
    assert passed is False


def test_regex_match() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "regex", "pattern": r"\bmoment\b"}, _resp("Give me a moment.")
    )
    assert passed is True


def test_regex_no_match_fails() -> None:
    passed, _ = matchers.evaluate(
        {"kind": "regex", "pattern": r"\bdragon\b"}, _resp("Give me a moment.")
    )
    assert passed is False


# --- unknown ----------------------------------------------------------------

def test_unknown_kind_fails() -> None:
    passed, detail = matchers.evaluate({"kind": "telepathy"}, _resp("hi"))
    assert passed is False
    assert "unknown" in detail


# --- tone_judge (monkeypatched httpx) --------------------------------------

class _FakeResponse:
    def __init__(self, text: str) -> None:
        self._text = text

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"response": self._text}


def test_tone_judge_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        matchers.httpx, "post", lambda *a, **k: _FakeResponse("YES - stays in character")
    )
    result = matchers.evaluate(
        {"kind": "tone_judge", "description": "in character"}, _resp("I heard whispers, friend.")
    )
    # tone_judge returns JudgeResult (SEV-38); score=True means passed.
    assert isinstance(result, matchers.JudgeResult)
    assert result.score is True


def test_tone_judge_no(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        matchers.httpx, "post", lambda *a, **k: _FakeResponse("NO - breaks character")
    )
    result = matchers.evaluate(
        {"kind": "tone_judge", "description": "in character"}, _resp("As an AI model...")
    )
    assert isinstance(result, matchers.JudgeResult)
    assert result.score is False


def test_tone_judge_empty_response_fails_without_calling_judge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*a: object, **k: object) -> None:
        raise AssertionError("judge must not be called for empty npc_response")

    monkeypatch.setattr(matchers.httpx, "post", _boom)
    result = matchers.evaluate({"kind": "tone_judge", "description": "x"}, _resp(""))
    assert isinstance(result, matchers.JudgeResult)
    assert result.score is False


def test_tone_judge_timeout_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _timeout(*a: object, **k: object) -> None:
        raise httpx.TimeoutException("slow")

    monkeypatch.setattr(matchers.httpx, "post", _timeout)
    result = matchers.evaluate({"kind": "tone_judge", "description": "x"}, _resp("hello"))
    # Infra failure → score=None, error="infra_failure" (SEV-38)
    assert isinstance(result, matchers.JudgeResult)
    assert result.score is None
    assert result.error == "infra_failure"


def test_tone_judge_unreachable_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    def _down(*a: object, **k: object) -> None:
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(matchers.httpx, "post", _down)
    result = matchers.evaluate({"kind": "tone_judge", "description": "x"}, _resp("hello"))
    assert isinstance(result, matchers.JudgeResult)
    assert result.score is None
    assert result.error == "infra_failure"


def test_tone_judge_unparseable_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(matchers.httpx, "post", lambda *a, **k: _FakeResponse("maybe?"))
    result = matchers.evaluate({"kind": "tone_judge", "description": "x"}, _resp("hello"))
    assert isinstance(result, matchers.JudgeResult)
    assert result.score is False
