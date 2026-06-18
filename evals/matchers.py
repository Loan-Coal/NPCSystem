"""
matchers.py - Expectation evaluators for eval cases.

Supported kinds: schema, min_length, keyword_any, keyword_all, keyword_none,
in_set, range, substring, regex, tone_judge, affirms_judge, context_block_expected.

affirms_judge is a polarity-inverted reuse of the tone_judge LLM plumbing: it
passes when the NPC does NOT affirm a supplied false claim (per-case ``claim`` or a
global lore rubric via ``description``). Both judges share _run_binary_judge.

SEV-38 changes:
- Added EvalConfigError for configuration-time validation failures.
- Added JudgeResult dataclass so tone_judge can signal infra failure distinctly.
- tone_judge infra failure now returns JudgeResult(score=None, error="infra_failure")
  instead of a plain (False, ...) tuple; callers treat score=None as "inconclusive".
- keyword_any raises EvalConfigError when fewer than 2 keywords (near-tautological guard).
- context_block_expected raises EvalConfigError when no runner context is provided.
- Shared judge-prompt template loaded from prompts/eval/tone_judge.yaml (no inline string).
"""

from __future__ import annotations

import logging as _logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml


# ---------------------------------------------------------------------------
# Public exceptions and return types
# ---------------------------------------------------------------------------


class EvalConfigError(Exception):
    """Raised when an eval expectation is mis-configured (e.g. too few keywords)."""


@dataclass
class JudgeResult:
    """Result from tone_judge that can carry an infra-failure signal.

    Attributes:
        score: True (pass) / False (fail) / None (infra failure — inconclusive).
        error: Human-readable error string when score is None or False.
    """

    score: bool | None
    error: str = ""


# ---------------------------------------------------------------------------
# Judge-prompt template (loaded from prompts/eval/tone_judge.yaml)
# ---------------------------------------------------------------------------

_PROMPT_YAML_PATH = Path(__file__).resolve().parents[1] / "prompts" / "eval" / "tone_judge.yaml"


def _load_judge_prompt_template() -> str:
    """Load the shared tone_judge prompt template from YAML.

    Returns:
        The raw template string with {criteria} and {content} placeholders.

    Raises:
        FileNotFoundError: If prompts/eval/tone_judge.yaml does not exist.
    """
    with _PROMPT_YAML_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return str(data["template"])


_JUDGE_PROMPT_TMPL: str = _load_judge_prompt_template()

# ---------------------------------------------------------------------------
# Structured logger
# ---------------------------------------------------------------------------

_logger = _logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Judge config
# ---------------------------------------------------------------------------

# Guard cases must produce a substantive answer: an empty or near-empty response
# can never demonstrate the anti-hallucination guarantee. Override via env for tuning.
MIN_GUARD_RESPONSE_CHARS = int(os.getenv("MIN_GUARD_RESPONSE_CHARS", "20"))

_JUDGE_URL = os.getenv("JUDGE_OLLAMA_URL", "http://localhost:11434")
_JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen2.5:14b")
_JUDGE_TIMEOUT = float(os.getenv("JUDGE_TIMEOUT_SECONDS", "30"))


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _get_nested(obj: dict, field: str) -> Any:
    """Resolve dot-notation field path from a dict."""
    parts = field.split(".")
    cur: Any = obj
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _parse_judge_verdict(raw: str) -> tuple[bool, str]:
    match = re.match(r"^(YES|NO)\s*[-–—:]?\s*(.*)", raw.strip(), re.IGNORECASE | re.DOTALL)
    if not match:
        return False, f"tone_judge: unparseable verdict: {raw[:80]!r}"
    passed = match.group(1).upper() == "YES"
    reasoning = match.group(2).strip()
    return passed, reasoning[:200] if reasoning else raw.strip()[:200]


# ---------------------------------------------------------------------------
# Public evaluate dispatcher
# ---------------------------------------------------------------------------


def evaluate(expectation: dict, response: dict) -> tuple[bool, str] | JudgeResult:
    """Evaluate one expectation against an API response dict.

    Returns:
        (passed: bool, detail: str) for most matchers.
        JudgeResult for tone_judge (score=None signals infra failure).

    Raises:
        EvalConfigError: If the expectation is mis-configured.
    """
    kind = expectation.get("kind", "")

    if kind == "schema":
        return _eval_schema(expectation, response)
    if kind == "min_length":
        return _eval_min_length(expectation, response)
    if kind == "keyword_any":
        return _eval_keyword_any(expectation, response)
    if kind == "keyword_all":
        return _eval_keyword_all(expectation, response)
    if kind == "keyword_none":
        return _eval_keyword_none(expectation, response)
    if kind == "in_set":
        return _eval_in_set(expectation, response)
    if kind == "range":
        return _eval_range(expectation, response)
    if kind == "substring":
        return _eval_substring(expectation, response)
    if kind == "regex":
        return _eval_regex(expectation, response)
    if kind == "tone_judge":
        return _eval_tone_judge(expectation, response)
    if kind == "affirms_judge":
        return _eval_affirms_judge(expectation, response)
    if kind == "context_block_expected":
        return _eval_context_block_expected(expectation, response)

    return False, f"unknown expectation kind: {kind!r}"


# ---------------------------------------------------------------------------
# Matcher implementations
# ---------------------------------------------------------------------------


# Affirmation-judge wrapper: turns a per-case ``claim`` or global rubric into a
# strict YES/NO affirmation question. Polarity is inverted at the call site
# (_eval_affirms_judge), so YES (NPC affirms the false claim) is a FAIL. The
# reusable YES/NO envelope itself lives in prompts/eval/tone_judge.yaml.
_AFFIRMATION_CRITERIA_TMPL: str = (
    "Answer YES only if the NPC affirms, confirms, asserts, or proceeds as if the "
    "following is established fact: {claim}. "
    "Answer NO if the NPC denies it, doubts it, deflects, hedges, treats it as the "
    "player's unverified claim, says it has not heard of it, or does not raise it."
)


def _run_binary_judge(criteria: str, content: str) -> JudgeResult:
    """Call the Ollama YES/NO judge and return a JudgeResult (YES → score=True).

    Shared transport+parse for every LLM matcher. Infra failures (network errors,
    timeouts) return JudgeResult(score=None, error="infra_failure") — callers must
    NOT count these as passing guard turns. Polarity inversion (if any) is the
    caller's responsibility.

    Args:
        criteria: The YES/NO criterion embedded in the judge prompt.
        content: The text being judged (the NPC response).

    Returns:
        JudgeResult(score=True) on a YES verdict, score=False on NO, score=None
        on infra failure.
    """
    prompt = _JUDGE_PROMPT_TMPL.format(criteria=criteria.strip(), content=content)
    payload: dict = {
        "model": _JUDGE_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 80, "temperature": 0.0},
    }

    try:
        r = httpx.post(f"{_JUDGE_URL}/api/generate", json=payload, timeout=_JUDGE_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        raw = str(data.get("response", ""))
    except Exception as exc:
        _logger.warning("binary_judge_infra_failure", extra={"error": str(exc)})
        return JudgeResult(score=None, error="infra_failure")

    passed, reasoning = _parse_judge_verdict(raw)
    return JudgeResult(score=passed, error="" if passed else reasoning)


def _eval_tone_judge(exp: dict, resp: dict) -> JudgeResult:
    """Voice/engagement judge: passes when the LLM verdict is YES.

    Args:
        exp: Expectation dict with judge_prompt or description field.
        resp: API response dict.

    Returns:
        JudgeResult with score=True/False on success, score=None on infra failure.
    """
    npc_response: str = _get_nested(resp, "npc_response") or ""
    if not npc_response:
        return JudgeResult(score=False, error="npc_response is empty")

    criteria = exp.get("judge_prompt") or exp.get("description", "")
    if not criteria:
        return JudgeResult(score=False, error="no judge_prompt or description in expectation")

    return _run_binary_judge(criteria=criteria, content=npc_response)


def _eval_affirms_judge(exp: dict, resp: dict) -> JudgeResult:
    """Affirmation judge: passes when the NPC does NOT affirm the false claim.

    Polarity is inverted relative to tone_judge — a YES verdict (the NPC affirmed
    the claim as fact) is a FAILURE; a NO verdict (denied/deflected/hedged/silent)
    is a PASS. Used per-case via ``claim`` and globally via ``description`` (a fixed
    lore rubric). An empty npc_response is a fail.

    Args:
        exp: Expectation dict with a ``claim`` (per-case) or ``description`` (rubric).
        resp: API response dict.

    Returns:
        JudgeResult: score=True when not affirmed, score=False when affirmed,
        score=None on infra failure (inconclusive).
    """
    npc_response: str = _get_nested(resp, "npc_response") or ""
    if not npc_response:
        return JudgeResult(score=False, error="npc_response is empty")

    claim = exp.get("claim")
    if claim:
        criteria = _AFFIRMATION_CRITERIA_TMPL.format(claim=str(claim).strip())
    else:
        criteria = exp.get("description", "")
    if not criteria:
        return JudgeResult(score=False, error="no claim or description in expectation")

    verdict = _run_binary_judge(criteria=criteria, content=npc_response)
    if verdict.score is None:
        return verdict  # infra failure — preserve inconclusive signal
    affirmed = verdict.score  # YES (True) means the NPC affirmed the claim
    if affirmed:
        return JudgeResult(score=False, error=f"NPC affirmed false claim: {verdict.error}")
    return JudgeResult(score=True, error="")


def _eval_context_block_expected(exp: dict, resp: dict) -> tuple[bool, str]:
    """Check that expected strings appear in the runner-injected context block.

    Args:
        exp: Expectation dict; must contain ``_runner_context`` (injected by
             the runner before evaluate() is called) and ``expected_strings``.
        resp: API response dict (not used; context lives in exp).

    Returns:
        (True, detail) if all expected_strings found; (False, detail) otherwise.

    Raises:
        EvalConfigError: If ``_runner_context`` key is absent (runner did not
            inject context — configuration error, not a soft failure).
    """
    context: str | None = exp.get("_runner_context")
    if context is None:
        raise EvalConfigError(
            "context_block_expected matcher requires runner context: "
            "the runner must inject '_runner_context' before calling evaluate(). "
            "This is a configuration error — the eval case cannot be evaluated."
        )
    expected_strings: list[str] = exp.get("expected_strings", [])
    missing = [s for s in expected_strings if s not in context]
    if missing:
        return False, f"context_block_expected: missing strings {missing!r}"
    return True, f"context_block_expected: all {len(expected_strings)} string(s) found"


def _eval_schema(exp: dict, resp: dict) -> tuple[bool, str]:
    """Check that expected fields are present and non-empty.

    A blank/whitespace-only ``npc_response`` is treated as missing: an empty
    string must not satisfy the schema, or the anti-hallucination guarantee
    could be met vacuously by an NPC that says nothing.
    """
    field = exp.get("field")
    if field is None:
        required_fields = ["npc_response", "relation_deltas", "action", "facial_expression"]
        missing = [f for f in required_fields if _get_nested(resp, f) is None]
        if missing:
            return False, f"missing required fields: {missing}"
        npc_response = _get_nested(resp, "npc_response")
        if not isinstance(npc_response, str) or not npc_response.strip():
            return False, "npc_response is empty or whitespace-only"
        return True, "schema OK"
    value = _get_nested(resp, field)
    if value is None:
        return False, f"field {field!r} is missing or null"
    return True, f"field {field!r} present: {value!r}"


def _eval_min_length(exp: dict, resp: dict) -> tuple[bool, str]:
    """npc_response (trimmed) must be at least ``min`` characters long.

    Defaults to MIN_GUARD_RESPONSE_CHARS. Fails empty, whitespace-only, and
    terse responses so a guard case cannot pass without a substantive answer.
    """
    minimum: int = exp.get("min", MIN_GUARD_RESPONSE_CHARS)
    text: str = (_get_nested(resp, "npc_response") or "").strip()
    if len(text) >= minimum:
        return True, f"min_length OK ({len(text)} >= {minimum})"
    return False, f"min_length: response too short ({len(text)} < {minimum}): {text[:80]!r}"


def _eval_keyword_any(exp: dict, resp: dict) -> tuple[bool, str]:
    """At least one keyword must appear in npc_response (case-insensitive).

    Args:
        exp: Expectation dict with ``keywords`` list (minimum 2 items).
        resp: API response dict.

    Raises:
        EvalConfigError: If fewer than 2 keywords are supplied (near-tautological).
    """
    keywords: list[str] = exp.get("keywords", [])
    if len(keywords) < 2:
        raise EvalConfigError(
            f"keyword_any requires at least 2 keywords to be meaningful; "
            f"got {len(keywords)}: {keywords!r}"
        )
    text: str = (_get_nested(resp, "npc_response") or "").lower()
    lowered = [kw.lower() for kw in keywords]
    matched = [kw for kw in lowered if kw in text]
    if matched:
        return True, f"keyword_any matched: {matched}"
    return False, f"none of {lowered!r} found in response: {text[:120]!r}"


def _eval_keyword_all(exp: dict, resp: dict) -> tuple[bool, str]:
    """All keywords must appear in npc_response (case-insensitive)."""
    text: str = (_get_nested(resp, "npc_response") or "").lower()
    keywords: list[str] = [kw.lower() for kw in exp.get("keywords", [])]
    missing = [kw for kw in keywords if kw not in text]
    if not missing:
        return True, f"keyword_all matched all: {keywords}"
    return False, f"missing keywords {missing!r} in response: {text[:120]!r}"


def _eval_keyword_none(exp: dict, resp: dict) -> tuple[bool, str]:
    """None of the keywords may appear in npc_response (case-insensitive)."""
    text: str = (_get_nested(resp, "npc_response") or "").lower()
    keywords: list[str] = [kw.lower() for kw in exp.get("keywords", [])]
    found = [kw for kw in keywords if kw in text]
    if not found:
        return True, f"keyword_none: none of {keywords!r} found"
    return False, f"keyword_none: forbidden keywords found: {found!r} in: {text[:120]!r}"


def _eval_in_set(exp: dict, resp: dict) -> tuple[bool, str]:
    """Field value must be one of the allowed values."""
    field: str = exp.get("field", "")
    allowed: list = exp.get("values", [])
    value = _get_nested(resp, field)
    if value in allowed:
        return True, f"{field}={value!r} in {allowed}"
    return False, f"{field}={value!r} not in {allowed}"


def _eval_range(exp: dict, resp: dict) -> tuple[bool, str]:
    """Numeric field value must fall within [min, max]."""
    field: str = exp.get("field", "")
    min_val = exp.get("min")
    max_val = exp.get("max")
    value = _get_nested(resp, field)
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return False, f"{field}={value!r} is not numeric"
    if min_val is not None and numeric < min_val:
        return False, f"{field}={numeric} < min {min_val}"
    if max_val is not None and numeric > max_val:
        return False, f"{field}={numeric} > max {max_val}"
    return True, f"{field}={numeric} in [{min_val}, {max_val}]"


def _eval_substring(exp: dict, resp: dict) -> tuple[bool, str]:
    """npc_response must contain the given substring (case-insensitive)."""
    text: str = (_get_nested(resp, "npc_response") or "").lower()
    substring: str = exp.get("substring", "").lower()
    if substring in text:
        return True, f"substring {substring!r} found"
    return False, f"substring {substring!r} not found in: {text[:120]!r}"


def _eval_regex(exp: dict, resp: dict) -> tuple[bool, str]:
    """npc_response must match the given regex pattern."""
    text: str = _get_nested(resp, "npc_response") or ""
    pattern: str = exp.get("pattern", "")
    if re.search(pattern, text, re.IGNORECASE):
        return True, f"regex {pattern!r} matched"
    return False, f"regex {pattern!r} did not match: {text[:120]!r}"
