"""
Module: case_adversary
Layer: evals (eval harness — standalone, outside the npc_engine layer model)
Purpose: EVAL-P26.1. Adversarially review candidate eval CASES against the contract in
         docs/CAPABILITY_CASES.md, so a case that would pass for the wrong reason is
         caught before it is authored into the battery.
Dependencies: json, re, sys, pathlib, typing; pydantic, yaml; evals/case_adversary_contract
         (models and constants), evals/keyword_matching, scripts/hedge_responder_probe.
Used by: `make review-cases`, tests/unit/evals/test_case_adversary.py, EVAL-P26.3's
         coverage + adversary gate.

SCOPE BOUNDARY — read this before extending the module
------------------------------------------------------
**This module reviews CASES. EVAL-P28.1 labels RESPONSES.** They are different jobs and
conflating them is how the reference side of this repo stayed single-rater: reviewing the
stimuli improves what the engine is asked; independently labelling the outputs is what
produces a reference side you can defend. A finding here says "this case is gameable"; it
never says "this reply was good". Nothing in this module reads a transcript.

Two halves, and why
-------------------
1. **Deterministic checks — pure Python, no LLM, and the majority of the value.**
   `review_case` runs them. They reuse the existing adversaries rather than re-deriving
   them: `scripts/hedge_responder_probe.CANNED_HEDGE` is the reference always-hedge
   responder (DEC-167) and `score_case` is the same scorer
   `tests/unit/evals/test_capability_echo_resistance.py` ratchets against, so a case
   cleared here is cleared by the machinery the suite already enforces. Run over the
   shipped battery this reproduces that module's GAMEABLE_BASELINE exactly — the same
   seven cases, no more and no fewer.

2. **Judgment checks — the existing batch/paste workflow.** Is the prompt leading? Does
   it supply its own answer? Is the phrasing insider vocabulary lifted from the graph
   node? None of those is mechanically decidable. **There is no Anthropic client in this
   repo** and adding one is a new dependency, so these are emitted as a batch file
   (`build_review_batch` / `render_batch`), pasted under the prompt in
   `prompts/eval/case_adversary.yaml`, and imported back through `parse_findings` into a
   validated Pydantic model — the same shape as `evals/calibration/oracle_batches/`.

What this module deliberately does NOT do
-----------------------------------------
It never asserts the grounded fact exists in the graph. Checking that the edge type
declared in `notes` is real is a pure string check; the node itself can only be confirmed
live, through `GET /v1/admin/{beliefs,goals,memories,secrets}/{npc_id}` (the generic graph
reader is blind to seeded inner life, ISSUE-148). Every review therefore carries
`live_verification_required=True`, so that step stays visible rather than assumed.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml
from pydantic import ValidationError

_REPO_ROOT = Path(__file__).resolve().parents[1]
for _extra_path in (_REPO_ROOT / "evals", _REPO_ROOT / "scripts"):
    if str(_extra_path) not in sys.path:
        sys.path.insert(0, str(_extra_path))

# `scripts/` is imported deliberately: hedge_responder_probe owns the reference hedge and
# the scorer, and copying either here is the re-derivation this phase forbids.
from case_adversary_contract import (  # noqa: E402
    ADVERSARY_PROMPT_PATH, CAPABILITY_PREFIX, GROUNDED_EDGE_TYPES, JUDGE_KINDS,
    LIVE_VERIFICATION_HINT, RETIRED_EDGE_ALIASES, TOKEN_KINDS, AdversaryFinding,
    CaseReview, CheckName, JudgmentFinding, MalformedFindingsError, ReviewBatchItem,
    Severity,
)
from hedge_responder_probe import CANNED_HEDGE, score_case, synthetic_response  # noqa: E402
from keyword_matching import contains_keyword  # noqa: E402

#: Re-exported so the reviewer's whole public surface is importable from one module.
__all__ = [
    "ADVERSARY_PROMPT_PATH", "GROUNDED_EDGE_TYPES", "JUDGE_KINDS", "LIVE_VERIFICATION_HINT",
    "RETIRED_EDGE_ALIASES", "AdversaryFinding", "CaseReview", "CheckName", "JudgmentFinding",
    "MalformedFindingsError", "ReviewBatchItem", "Severity", "build_review_batch",
    "load_adversary_prompt", "parse_findings", "render_batch", "review_case",
]

#: Matches an ALL-CAPS token in a case's notes, which is how grounding edges are written.
_EDGE_TOKEN_RE: re.Pattern[str] = re.compile(r"\b[A-Z][A-Z_]{2,}\b")


# ---------------------------------------------------------------------------
# Deterministic checks
# ---------------------------------------------------------------------------


def _finding(case_id: str, check: CheckName, severity: Severity, detail: str) -> AdversaryFinding:
    """Build one finding."""
    return AdversaryFinding(case_id=case_id, check=check, severity=severity, detail=detail)


def _declared_tokens(case: dict[str, Any]) -> list[str]:
    """Every keyword listed by a token-based expectation on the case."""
    return [
        str(keyword)
        for exp in case.get("expected", [])
        if exp.get("kind") in TOKEN_KINDS
        for keyword in exp.get("keywords", [])
    ]


def _check_prompt_supplied_tokens(case: dict[str, Any]) -> AdversaryFinding | None:
    """Flag expectation tokens the case's own player_message already supplies.

    This is the exact defect the EVAL-P20.2 audit found: a case that scores on vocabulary
    it handed the NPC measures parroting, not knowledge. `contains_keyword` is used so the
    word-boundary semantics match the live runner's.
    """
    message = str(case.get("input", {}).get("player_message", "")).lower()
    lifted = sorted({t for t in _declared_tokens(case) if contains_keyword(message, t.lower())})
    if not lifted:
        return None
    return _finding(
        str(case.get("case_id", "")),
        CheckName.PROMPT_SUPPLIED_TOKENS,
        Severity.BLOCKER,
        f"expectation tokens also appear in the case's own player_message: {lifted!r} — "
        f"draw the tokens from the grounded fact instead",
    )


def _measurable_case(case: dict[str, Any]) -> dict[str, Any]:
    """A copy of the case with LLM-decided expectations removed.

    Scoring a `tone_judge` expectation would call Ollama over HTTP. This module is pure,
    so judge-decided expectations are dropped here and reported separately as unmeasured.
    A new dict is returned; the caller's case is never mutated.
    """
    return {**case, "expected": [e for e in case.get("expected", []) if e.get("kind") not in JUDGE_KINDS]}


def _beaten_by(case: dict[str, Any], response_text: str) -> bool:
    """True when a knowledge-free response satisfies the case's measurable expectations."""
    return bool(score_case(_measurable_case(case), synthetic_response(response_text))["passed"])


def _check_gameability(case: dict[str, Any]) -> list[AdversaryFinding]:
    """Score the case against the echo and the reference hedge.

    Only capability cases are checked: a guard case is *supposed* to be satisfied by a
    reply that says nothing, so flagging one would invert what the check means.
    """
    case_id = str(case.get("case_id", ""))
    if not case_id.startswith(CAPABILITY_PREFIX):
        return []
    adversaries = (
        (CheckName.BEATEN_BY_ECHO, str(case.get("input", {}).get("player_message", "")), "an echo of its own player_message"),
        (CheckName.BEATEN_BY_HEDGE, CANNED_HEDGE, "the reference always-hedge responder"),
    )
    return [
        _finding(case_id, check, Severity.BLOCKER, f"the case passes on {label} — it does not test capability")
        for check, text, label in adversaries
        if _beaten_by(case, text)
    ]


def _check_judge_decided(case: dict[str, Any]) -> AdversaryFinding | None:
    """Report LLM-decided expectations as unmeasured by the offline gameability checks."""
    kinds = sorted({str(e.get("kind")) for e in case.get("expected", []) if e.get("kind") in JUDGE_KINDS})
    if not kinds:
        return None
    return _finding(
        str(case.get("case_id", "")),
        CheckName.JUDGE_DECIDED_UNMEASURED,
        Severity.WARNING,
        f"expectations decided by an LLM judge are invisible to the offline gameability "
        f"checks: {kinds!r} — their gameability is unmeasured, not clean",
    )


def _grounding_detail(named: set[str]) -> str:
    """The remediation text for notes that name no real grounding edge type."""
    retired = sorted(named & set(RETIRED_EDGE_ALIASES))
    if retired:
        return "; ".join(
            f"{alias} does not exist — the registry names it {RETIRED_EDGE_ALIASES[alias]}" for alias in retired
        )
    return (
        f"notes name no grounding edge type; one of {sorted(GROUNDED_EDGE_TYPES)} must appear "
        f"so the case is traceable to the graph"
    )


def _check_grounding_edge(case: dict[str, Any]) -> AdversaryFinding | None:
    """Flag notes that name no real grounding edge type, naming the fix when one exists."""
    named = set(_EDGE_TOKEN_RE.findall(str(case.get("notes", ""))))
    if named & GROUNDED_EDGE_TYPES:
        return None
    return _finding(
        str(case.get("case_id", "")),
        CheckName.UNDECLARED_GROUNDING_EDGE,
        Severity.BLOCKER,
        _grounding_detail(named),
    )


def review_case(case: dict[str, Any]) -> CaseReview:
    """Run every deterministic check over one parsed case document.

    Args:
        case: A parsed eval case YAML document.
    Returns:
        The CaseReview. Empty `findings` means the offline checks pass — it does not mean
        the case is verified; `live_verification_required` is always True.
    """
    optional = (_check_prompt_supplied_tokens(case), _check_judge_decided(case), _check_grounding_edge(case))
    findings = [f for f in optional if f is not None] + _check_gameability(case)
    return CaseReview(case_id=str(case.get("case_id", "")), findings=tuple(findings))


# ---------------------------------------------------------------------------
# Judgment half — batch out, findings in
# ---------------------------------------------------------------------------


def _summarize_expectation(exp: dict[str, Any]) -> str:
    """One expectation as a short human-readable phrase."""
    keywords = exp.get("keywords")
    kind = str(exp.get("kind", "unknown"))
    return f"{kind}[{', '.join(str(k) for k in keywords)}]" if keywords else kind


def build_review_batch(cases: Sequence[dict[str, Any]]) -> tuple[ReviewBatchItem, ...]:
    """Build the batch the judgment pass reviews.

    Args:
        cases: Parsed case documents.
    Returns:
        One ReviewBatchItem per case, in input order.
    """
    return tuple(
        ReviewBatchItem(
            case_id=str(case.get("case_id", "")),
            description=str(case.get("description", "")).strip(),
            player_message=str(case.get("input", {}).get("player_message", "")),
            expectation_summary="; ".join(_summarize_expectation(e) for e in case.get("expected", [])),
            notes=str(case.get("notes", "")).strip(),
        )
        for case in cases
    )


def render_batch(items: Sequence[ReviewBatchItem]) -> str:
    """Render a batch as the JSON array the paste workflow expects.

    Args:
        items: The batch items.
    Returns:
        A JSON array, the same on-disk shape as evals/calibration/oracle_batches/*.json.
    """
    return json.dumps([item.model_dump() for item in items], indent=2, ensure_ascii=False)


def load_adversary_prompt() -> str:
    """Load the judgment-pass prompt template from prompts/eval/case_adversary.yaml.

    Returns:
        The raw template string, piped verbatim ahead of the rendered batch.
    Raises:
        FileNotFoundError: If the prompt YAML is absent.
    """
    doc = yaml.safe_load(ADVERSARY_PROMPT_PATH.read_text(encoding="utf-8"))
    return str(doc["template"])


def parse_findings(text: str) -> tuple[JudgmentFinding, ...]:
    """Parse the pasted JSONL result into validated findings.

    Args:
        text: The reviewer's JSONL output; blank lines are ignored.
    Returns:
        The findings, in input order.
    Raises:
        MalformedFindingsError: On any line that is not a valid JudgmentFinding. The
            whole import fails rather than dropping a finding, because a dropped finding
            is indistinguishable from a clean case.
    """
    findings: list[JudgmentFinding] = []
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            findings.append(JudgmentFinding.model_validate(json.loads(stripped)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise MalformedFindingsError(f"line {number} is not a valid finding: {stripped[:120]!r}") from exc
    return tuple(findings)
