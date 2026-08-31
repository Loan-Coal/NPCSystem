"""
Module: check_dead_keywords
Layer: scripts (dev tooling)
Purpose: Flag forbidden keywords (keyword_none) that never occur anywhere in
         a committed generation corpus. A keyword the engine's idiom can
         never emit is a guaranteed pass no matter how the engine changes —
         it silently inflates the guard battery's pass rate rather than
         testing anything (EVAL-P19.3). Output is a work-list for a human to
         decide what a case should actually forbid (EVAL-P20.1); this script
         never edits a case file.
Enforcement: ratchet (R2.3). The count is recorded in dead_keywords_baseline.txt and
         any increase is RED — a new guaranteed-pass keyword can no longer be added
         unnoticed. Deleting dead terms lowers the count; re-record with --update. Full
         triage to zero is the golden-set rebuild's job (ISSUE-157), not this gate's.
Dependencies: argparse, json, pathlib, sys, pydantic, yaml; evals/keyword_matching
              (contains_keyword — same word-boundary semantics as the runner)
Used by: make check-dead-keywords, tests/unit/scripts/test_check_dead_keywords.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

import yaml
from pydantic import BaseModel, ConfigDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "evals"))
from keyword_matching import contains_keyword  # noqa: E402

_DEFAULT_CASES_DIR = Path(__file__).resolve().parents[1] / "evals" / "cases"

#: Newest committed generation (R2.3). Re-pointing this is a deliberate human step:
#: an automatic re-point would let a corpus with narrower vocabulary launder more
#: keywords into "live" and shrink the count without any case improving.
_DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "generations"
    / "k3_77688e7_regen1"
    / "outputs.jsonl"
)
_KEYWORD_NONE_KIND = "keyword_none"
BASELINE_PATH = Path(__file__).resolve().parent / "dead_keywords_baseline.txt"


class DeadKeyword(BaseModel):
    """One forbidden keyword that never occurs anywhere in the corpus.

    Attributes:
        case_id: The case whose keyword_none expectation names this keyword.
        keyword: The forbidden keyword or phrase, as written in the case file.
    """

    model_config = ConfigDict(frozen=True)

    case_id: str
    keyword: str


def _load_cases(cases_dir: Path) -> list[dict[str, Any]]:
    """Load every case YAML in cases_dir.

    Args:
        cases_dir: Directory of *.yaml case files.
    Returns:
        Parsed case dicts, one per file.
    """
    cases: list[dict[str, Any]] = []
    for path in sorted(cases_dir.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            cases.append(yaml.safe_load(f))
    return cases


def _load_corpus(corpus_path: Path) -> list[str]:
    """Load every npc_response string from a committed outputs.jsonl transcript.

    Args:
        corpus_path: Path to a generation directory's outputs.jsonl.
    Returns:
        List of npc_response strings, one per record.
    """
    responses: list[str] = []
    for line in corpus_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped:
            responses.append(json.loads(stripped)["npc_response"])
    return responses


def _keyword_none_pairs(cases: Sequence[dict[str, Any]]) -> list[tuple[str, str]]:
    """Extract every (case_id, keyword) pair from every keyword_none expectation.

    Args:
        cases: Loaded case dicts.
    Returns:
        (case_id, keyword) pairs in case-then-keyword order.
    """
    pairs: list[tuple[str, str]] = []
    for case in cases:
        case_id = case.get("case_id", "")
        for expectation in case.get("expected", []):
            if expectation.get("kind") == _KEYWORD_NONE_KIND:
                pairs.extend((case_id, kw) for kw in expectation.get("keywords", []))
    return pairs


def find_dead_keywords(
    cases: Sequence[dict[str, Any]],
    corpus: Sequence[str],
) -> list[DeadKeyword]:
    """Return every keyword_none keyword that never occurs anywhere in corpus.

    Uses the same word-boundary semantics as matchers.py (contains_keyword) —
    a keyword flagged dead here is exactly the keyword that could never fail
    a real case, not merely one that looks rare.

    Args:
        cases: Loaded case dicts (see _load_cases).
        corpus: npc_response strings from a committed generation transcript.
    Returns:
        DeadKeyword rows, in case-then-keyword order.
    """
    lowered_corpus = [text.lower() for text in corpus]
    dead: list[DeadKeyword] = []
    for case_id, keyword in _keyword_none_pairs(cases):
        kw = keyword.lower()
        if not any(contains_keyword(text, kw) for text in lowered_corpus):
            dead.append(DeadKeyword(case_id=case_id, keyword=keyword))
    return dead


def format_report(dead: Sequence[DeadKeyword]) -> str:
    """Render a work-list of dead keywords, grouped by case.

    Args:
        dead: Rows from find_dead_keywords.
    Returns:
        Multi-line report string.
    """
    if not dead:
        return "No dead keywords found — every keyword_none term occurs at least once in the corpus."
    by_case: dict[str, list[str]] = {}
    for row in dead:
        by_case.setdefault(row.case_id, []).append(row.keyword)
    lines = [f"{len(dead)} dead keyword(s) found — zero occurrences anywhere in the corpus:"]
    lines.extend(f"  {case_id}: {keywords!r}" for case_id, keywords in by_case.items())
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def read_baseline(path: Path = BASELINE_PATH) -> int:
    """Return the recorded dead-keyword count; 0 when the file is missing or unreadable.

    Args:
        path: Baseline file holding a single integer.
    Returns:
        The recorded count, or 0 — which makes any dead keyword at all a regression, so
        a lost baseline reds rather than silently passing.
    """
    try:
        return int(path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the dead-keyword work-list and ratchet on its size.

    Which keywords a case should forbid is still a human call (EVAL-P20.1) — this gate
    never edits a case file. What it no longer does is exit 0 unconditionally: since
    R2.3 the count is ratcheted against dead_keywords_baseline.txt, so a newly added
    guaranteed-pass term is RED.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    Returns:
        0 at or below the recorded baseline, 1 above it.
    """
    parser = argparse.ArgumentParser(
        description="Gate keyword_none terms with zero hits in a committed corpus (ratchet)."
    )
    parser.add_argument("--cases-dir", type=Path, default=_DEFAULT_CASES_DIR)
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS_PATH)
    parser.add_argument("--baseline-file", type=Path, default=BASELINE_PATH)
    parser.add_argument("--update", action="store_true", help="record the current count")
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases_dir)
    corpus = _load_corpus(args.corpus)
    dead = find_dead_keywords(cases, corpus)
    count = len(dead)

    if args.update:
        args.baseline_file.write_text(f"{count}\n", encoding="utf-8", newline="")
        print(f"check-dead-keywords: baseline recorded at {count}")
        return 0

    print(format_report(dead))
    return _ratchet_verdict(count, read_baseline(args.baseline_file))


def _ratchet_verdict(count: int, baseline: int) -> int:
    """Compare a dead-keyword count against the recorded baseline and report the verdict.

    Args:
        count: Dead keywords found in this run.
        baseline: The recorded count.
    Returns:
        1 when count exceeds baseline, else 0.
    """
    if count > baseline:
        print(
            f"check-dead-keywords: {count} dead keyword(s) exceed baseline of {baseline} — gate RED.",
            file=sys.stderr,
        )
        return 1
    if count < baseline:
        print(f"check-dead-keywords: {count} < baseline {baseline} — re-record with --update.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
