"""
matchers.py - Expectation evaluators for eval cases.

Supported kinds: schema, keyword_any, keyword_all, keyword_none, in_set, range, substring, regex, tone_judge.
"""

from __future__ import annotations

import os
import re
from typing import Any

import httpx


_JUDGE_URL = os.getenv("JUDGE_OLLAMA_URL", "http://localhost:11434")
_JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen2.5:14b")
_JUDGE_TIMEOUT = float(os.getenv("JUDGE_TIMEOUT_SECONDS", "30"))

_JUDGE_PROMPT_TMPL = """\
You are a strict YES/NO evaluator. Your task:

Criterion: {criteria}

Text to evaluate:
---
{content}
---

Answer with exactly one of:
YES - <one-sentence explanation>
NO  - <one-sentence explanation>

Do not write anything else."""


def _get_nested(obj: dict, field: str) -> Any:
    """Resolve dot-notation field path from a dict."""
    parts = field.split(".")
    cur = obj
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def evaluate(expectation: dict, response: dict) -> tuple[bool, str]:
    """
    Evaluate one expectation against an API response dict.

    Returns (passed: bool, detail: str).
    """
    kind = expectation.get("kind", "")

    if kind == "schema":
        return _eval_schema(expectation, response)
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

    return False, f"unknown expectation kind: {kind!r}"


def _parse_judge_verdict(raw: str) -> tuple[bool, str]:
    match = re.match(r"^(YES|NO)\s*[-–—:]?\s*(.*)", raw.strip(), re.IGNORECASE | re.DOTALL)
    if not match:
        return False, f"tone_judge: unparseable verdict: {raw[:80]!r}"
    passed = match.group(1).upper() == "YES"
    reasoning = match.group(2).strip()
    return passed, reasoning[:200] if reasoning else raw.strip()[:200]


def _eval_tone_judge(exp: dict, resp: dict) -> tuple[bool, str]:
    npc_response: str = _get_nested(resp, "npc_response") or ""
    if not npc_response:
        return False, "tone_judge: npc_response is empty"

    criteria = exp.get("judge_prompt") or exp.get("description", "")
    if not criteria:
        return False, "tone_judge: no judge_prompt or description in expectation"

    prompt = _JUDGE_PROMPT_TMPL.format(criteria=criteria.strip(), content=npc_response)
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
    except httpx.TimeoutException:
        return False, f"tone_judge: Ollama timed out after {_JUDGE_TIMEOUT}s"
    except Exception as exc:
        return False, f"tone_judge: Ollama unreachable: {exc}"

    return _parse_judge_verdict(raw)


def _eval_schema(exp: dict, resp: dict) -> tuple[bool, str]:
    """Check that expected fields are present and non-empty."""
    field = exp.get("field")
    if field is None:
        required_fields = ["npc_response", "relation_deltas", "action", "facial_expression"]
        missing = [f for f in required_fields if _get_nested(resp, f) is None]
        if missing:
            return False, f"missing required fields: {missing}"
        return True, "schema OK"
    value = _get_nested(resp, field)
    if value is None:
        return False, f"field {field!r} is missing or null"
    return True, f"field {field!r} present: {value!r}"


def _eval_keyword_any(exp: dict, resp: dict) -> tuple[bool, str]:
    """At least one keyword must appear in npc_response (case-insensitive)."""
    text: str = (_get_nested(resp, "npc_response") or "").lower()
    keywords: list[str] = [kw.lower() for kw in exp.get("keywords", [])]
    matched = [kw for kw in keywords if kw in text]
    if matched:
        return True, f"keyword_any matched: {matched}"
    return False, f"none of {keywords!r} found in response: {text[:120]!r}"


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
        numeric = float(value)  # type: ignore[arg-type]
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
