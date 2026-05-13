"""
llm_judge.py - Lightweight LLM-as-judge helper for opt-in eval tests.

Usage:
    from e2e.helpers.llm_judge import llm_judge, JudgeVerdict

    verdict = await llm_judge(
        content="The shadow of the guild lingers over everything I do.",
        criteria="Does this text hint at a personal mission without stating 'I have a goal'?",
        llm_client=client,
    )
    assert verdict.passed, verdict.reasoning

Notes:
  - Tests marked @pytest.mark.llm_eval are probabilistic by nature.
  - A single retry is built in; treat failures as warnings, not hard blockers.
  - Uses the plain `generate()` call — does not require structured output.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class JudgeVerdict:
    passed: bool
    reasoning: str


_JUDGE_PROMPT = """\
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


async def llm_judge(
    content: str,
    criteria: str,
    llm_client,  # LLMClientProtocol
    *,
    retries: int = 1,
) -> JudgeVerdict:
    """Ask the LLM to evaluate whether `content` satisfies `criteria`.

    Returns a JudgeVerdict with .passed (bool) and .reasoning (str).
    Retries once on parse failure or ambiguous output.
    """
    prompt = _JUDGE_PROMPT.format(criteria=criteria, content=content)
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            raw = await llm_client.generate(
                prompt=prompt,
                max_tokens=80,
                temperature=0.0,
            )
            verdict = _parse_verdict(raw.strip())
            if verdict is not None:
                return verdict
            if attempt < retries:
                continue
            return JudgeVerdict(passed=False, reasoning=f"Unparseable judge response: {raw!r}")
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt < retries:
                continue
            raise RuntimeError(f"LLM judge failed after {retries + 1} attempts") from last_exc
    return JudgeVerdict(passed=False, reasoning="LLM judge exhausted retries without a verdict")


def _parse_verdict(raw: str) -> JudgeVerdict | None:
    """Extract YES/NO and one-sentence reasoning from raw LLM output."""
    upper = raw.upper()
    match = re.match(r"^(YES|NO)\s*[-–—:]?\s*(.*)", upper, re.DOTALL)
    if not match:
        return None
    answer = match.group(1)
    # Extract reasoning from original-case text (not uppercased)
    raw_match = re.match(r"^(?:YES|NO)\s*[-–—:]?\s*(.*)", raw, re.DOTALL | re.IGNORECASE)
    reasoning = raw_match.group(1).strip() if raw_match else ""
    return JudgeVerdict(passed=(answer == "YES"), reasoning=reasoning or raw)
