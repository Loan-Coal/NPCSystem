"""
Module: case_adversary_contract
Layer: evals (eval harness — standalone, outside the npc_engine layer model)
Purpose: The data model for EVAL-P26.1's adversarial case reviewer — the contract
         constants it checks against, the check/severity vocabularies, and every Pydantic
         model that crosses a module boundary. Holds no logic.
Dependencies: enum, pathlib; pydantic.
Used by: evals/case_adversary.py (which re-exports this module's public names),
         tests/unit/evals/test_case_adversary.py.

Split from `case_adversary.py` to keep both files inside CLAUDE.md's 300-line limit and
to keep each to one category: this module is the data model, `case_adversary` is the
handler. The public surface is unchanged — import either from here or from
`case_adversary`, which re-exports all of it.
"""

from __future__ import annotations

import enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Contract constants
# ---------------------------------------------------------------------------

#: The prompt for the judgment half. CLAUDE.md: nothing passed to an LLM is a Python
#: string literal.
ADVERSARY_PROMPT_PATH: Path = _REPO_ROOT / "prompts" / "eval" / "case_adversary.yaml"

#: The five relationship types docs/CAPABILITY_CASES.md accepts as grounding, as named by
#: the registry (GET /v1/admin/schema/registry).
GROUNDED_EDGE_TYPES: frozenset[str] = frozenset(
    {"KNOWS_ABOUT", "BELIEVES", "REMEMBERS", "PURSUES", "KNOWS_SECRET"}
)

#: Names that read like grounding edges but do not exist. Kept so a case using one is told
#: what to write instead rather than only that it is wrong. `evals/case_drafts.py` still
#: carries these three and returns HTTP 422 for them — ISSUE-148.
RETIRED_EDGE_ALIASES: dict[str, str] = {
    "HAS_MEMORY": "REMEMBERS",
    "HAS_GOAL": "PURSUES",
    "HAS_SECRET": "KNOWS_SECRET",
}

#: Expectation kinds whose verdict comes from an LLM. Excluded from the offline
#: gameability checks and reported as unmeasured, never as clean.
JUDGE_KINDS: frozenset[str] = frozenset({"tone_judge", "refusal_judge", "affirms_judge"})

#: Expectation kinds carrying a token list that should be drawn from the grounded fact.
TOKEN_KINDS: frozenset[str] = frozenset({"keyword_any", "keyword_all"})

#: Only capability cases claim to demonstrate knowledge, so only they can be gamed by a
#: knowledge-free reply. A guard case beating the hedge is the guard working.
CAPABILITY_PREFIX: str = "case_pos_"

#: Named in every review so the remaining live step stays visible rather than assumed.
#: The generic graph reader is blind to seeded inner life (ISSUE-148), so the typed admin
#: endpoints are the only safe route to "does this NPC actually hold this fact".
LIVE_VERIFICATION_HINT: str = (
    "confirm the grounded node exists via GET /v1/admin/{beliefs,goals,memories,secrets}/"
    "{npc_id} — the generic graph reader is blind to seeded inner life (ISSUE-148)"
)


class MalformedFindingsError(ValueError):
    """Raised when an imported findings line is not a valid JudgmentFinding.

    A batch that half-imports is worse than one that does not import at all: the missing
    findings look like clean cases. Every line is validated or the whole import fails.
    """


class CheckName(enum.Enum):
    """The deterministic checks `case_adversary.review_case` runs."""

    PROMPT_SUPPLIED_TOKENS = "prompt_supplied_tokens"
    BEATEN_BY_ECHO = "beaten_by_echo"
    BEATEN_BY_HEDGE = "beaten_by_hedge"
    UNDECLARED_GROUNDING_EDGE = "undeclared_grounding_edge"
    JUDGE_DECIDED_UNMEASURED = "judge_decided_unmeasured"


class Severity(enum.Enum):
    """How badly a finding compromises what the case measures."""

    BLOCKER = "blocker"
    WARNING = "warning"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AdversaryFinding(BaseModel):
    """One deterministic defect found in one case.

    Attributes:
        case_id: The case the finding is against.
        check: Which deterministic check fired.
        severity: BLOCKER when a knowledge-free reply could pass the case.
        detail: The specific evidence, naming the offending tokens or adversary.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    check: CheckName
    severity: Severity
    detail: str


class CaseReview(BaseModel):
    """The deterministic review of one case.

    Attributes:
        case_id: The reviewed case.
        findings: Every deterministic defect found; empty means the offline checks pass.
        live_verification_required: Always True — an offline module cannot confirm that
            the grounded node exists, only that the declared edge type is real.
        live_verification_hint: What the remaining live step is.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    findings: tuple[AdversaryFinding, ...]
    live_verification_required: bool = True
    live_verification_hint: str = LIVE_VERIFICATION_HINT


class ReviewBatchItem(BaseModel):
    """One case as presented to the judgment pass.

    Carries only what a judgment check needs. The expectation is summarised rather than
    dumped so the reviewer reads the case as a player would, not as a matcher would.

    Attributes:
        case_id: The case id, copied verbatim into the returned findings.
        description: The case's own statement of what it tests.
        player_message: The eliciting prompt under review.
        expectation_summary: Compact rendering of the `expected` list.
        notes: The case's authoring notes, which name the grounding.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    description: str
    player_message: str
    expectation_summary: str
    notes: str


class JudgmentFinding(BaseModel):
    """One finding imported back from the judgment pass.

    Attributes:
        case_id: The case the finding is against.
        check: The check name, as declared in prompts/eval/case_adversary.yaml.
        severity: BLOCKER or WARNING, decided by the reviewer.
        detail: The reviewer's evidence.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    check: str
    severity: Severity
    detail: str
