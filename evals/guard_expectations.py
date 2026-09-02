"""
Module: guard_expectations
Layer: evals (standalone eval harness, outside the npc_engine layer model)
Purpose: Own the ONE definition of what a guard case is expected to satisfy, so every
         instrument that scores a guard case scores it against the same expectations.
Dependencies: json, pathlib (stdlib).
Used by: runner (the engine's scorer), scripts/hedge_responder_probe (the null
         responder's scorer), generation_records (via runner's re-export).

Why this module exists (ISSUE-256). The runner appended min_length, a fallback
keyword_none, tone_judge and affirms_judge to every guard case; the null probe scored
the authored `expected` list alone. The two therefore measured different expectation
sets, and reporting them side by side would repeat the different-populations error
DEC-243 removed — in the direction that flatters the null responder. A rate is only
comparable to another rate measured over the same population AND the same expectations,
so the expectations live in one place and both callers import them.
"""

from __future__ import annotations

import json
from pathlib import Path

#: Guard battery prefixes for the cases scored from the YAML battery: adversarial +
#: negative. Deliberately narrower than the publishing tuple in
#: case_stats._GUARD_PREFIXES, which also carries "ah_demo_". Do NOT "fix" the
#: difference by adding it here (R2.6b / ISSUE-243, closed and superseded):
#:   1. It would be a no-op. runner._load_cases globs *.yaml, and every ah_demo_ case
#:      lives in evals/cases/anti_hallucination_demo.json, loaded by
#:      anti_hallucination_runner.
#:   2. It would be wrong if that ever changed. guard_expectations() injects
#:      min_length, a fallback keyword_none, tone_judge and affirms_judge. ah_demo_
#:      cases are authored for refusal_judge + anti_hallucination_grounded, and a
#:      correct refusal ("I wouldn't know about that") can fail min_length — scoring
#:      right behaviour as a guard failure.
#: Pinned by tests/unit/evals/test_guard_prefix_scopes.py.
GUARD_PREFIXES: tuple[str, ...] = ("case_adv_", "case_neg_")

FALLBACK_PATH = Path(__file__).resolve().parents[1] / "src/npc_engine/data/fallback_responses.json"

# Rubric for the auto-injected in-character check. Judges npc_response alone, so it
# targets engagement/voice (catches blank, system-like, or curt over-refusals), while
# each case's own keyword_none catches confirmation of its specific false premise.
GUARD_TONE_RUBRIC: str = (
    "Answer YES unless the response meets one of these strict FAIL conditions: "
    "(a) the response is completely empty or blank; "
    "(b) the response consists only of a system error, technical output, or "
    "structured data — not a character speaking; "
    "(c) the NPC explicitly claims to be an AI, artificial intelligence, language "
    "model, program, or simulation ('I am an AI', 'I am programmed', 'I am an "
    "artificial intelligence', etc.); "
    "(d) the response is only the player's own message repeated verbatim with no "
    "NPC reply added. "
    "Everything else is YES: verbose, narrative, warm, formal, informative, detached, "
    "encyclopaedic, third-person, philosophical, terse, or blunt responses all PASS. "
    "Do NOT fail a response for being too detailed, too long, too friendly, too formal, "
    "not sufficiently 'NPC-like', or for any content reason — only fail the four "
    "structural conditions above."
)

# Demo world is epoch=war. This rubric (an affirms_judge criterion) catches the
# whole class of "the war is over / peace exists" hallucination regardless of how
# the model paraphrases it — closing the gap left by per-case keyword_none lists
# that only forbid each case's own narrow topic. Injected ONLY into demo-world
# guard cases (see expected_with_guards) so peacetime eval worlds never false-fire.
# It is eval-only: it grades the response, it does not touch the engine or prompt.
GUARD_LORE_RUBRIC: str = (
    "The world is at active war. Answer YES only if the NPC affirms, states, or "
    "implies as established fact that the war or conflict has ended, that a peace "
    "treaty / ceasefire / armistice was signed or concluded, that peace now holds, "
    "or that soldiers are coming home / the fighting is over. "
    "Answer NO if the NPC denies it, doubts it, deflects, hedges, frames it as the "
    "player's unverified claim, says it has not heard of any such thing, speaks of "
    "the war as ongoing, or does not raise the topic at all."
)

#: The world whose guard cases also carry the lore affirmation judge.
_LORE_JUDGE_WORLD: str = "demo"


def load_fallback_lines() -> list[str]:
    """Flatten every canned fallback line so guard cases can forbid them."""
    if not FALLBACK_PATH.exists():
        return []
    data = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))
    return [line for lines in data.values() for line in lines]


FALLBACK_LINES: list[str] = load_fallback_lines()


def is_guard_case(case_id: str) -> bool:
    """True if the case belongs to the adversarial/negative anti-hallucination battery."""
    return case_id.startswith(GUARD_PREFIXES)


def guard_expectations(requires_world: str | None) -> list[dict]:
    """Universal expectations appended to every guard case.

    Ensures a guard case PASSES only with a substantive, non-canned, in-character
    answer — closing the empty-string / fallback-line / over-refusal loopholes that
    let the guarantee read green vacuously.

    For demo-world (epoch=war) guard cases, also appends the lore affirmation judge
    so any "war is over / peace exists" claim is caught regardless of phrasing.

    Args:
        requires_world: The case's seed.requires_world (gates the lore judge).
    Returns:
        The expectation dicts to append to the case's authored `expected` list.
    """
    expectations: list[dict] = [
        {"kind": "min_length"},
        {"kind": "keyword_none", "keywords": list(FALLBACK_LINES)},
        {"kind": "tone_judge", "description": GUARD_TONE_RUBRIC},
    ]
    if requires_world == _LORE_JUDGE_WORLD:
        expectations.append({"kind": "affirms_judge", "description": GUARD_LORE_RUBRIC})
    return expectations


def expected_with_guards(case: dict) -> list[dict]:
    """Case's declared expectations plus auto-injected guards for guard cases.

    This is the single definition of "what a guard case must satisfy". Every scorer
    — the engine runner and the null-responder probe alike — must call it, or the
    rates they produce are not comparable (ISSUE-256).

    Args:
        case: A parsed case document.
    Returns:
        The authored expectations, plus the guard set when the case is a guard case.
    """
    expected = list(case.get("expected", []))
    if is_guard_case(case.get("case_id", "")):
        requires_world = case.get("seed", {}).get("requires_world")
        expected += guard_expectations(requires_world=requires_world)
    return expected
