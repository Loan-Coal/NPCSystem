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
_DEFAULT_CORPUS_PATH = (
    Path(__file__).resolve().parents[1]
    / "evals"
    / "generations"
    / "k3_73e6c36"
    / "outputs.jsonl"
)
_KEYWORD_NONE_KIND = "keyword_none"


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


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the dead-keyword work-list.

    Always exits 0 — this is a work-list for a human (EVAL-P20.1 decides
    what a case should forbid), never an automatic edit or a hard gate.

    Args:
        argv: Command-line arguments; defaults to sys.argv[1:].
    Returns:
        0 always.
    """
    parser = argparse.ArgumentParser(
        description="Flag keyword_none terms with zero hits in a committed corpus (work-list only)."
    )
    parser.add_argument("--cases-dir", type=Path, default=_DEFAULT_CASES_DIR)
    parser.add_argument("--corpus", type=Path, default=_DEFAULT_CORPUS_PATH)
    args = parser.parse_args(argv)

    cases = _load_cases(args.cases_dir)
    corpus = _load_corpus(args.corpus)
    dead = find_dead_keywords(cases, corpus)
    print(format_report(dead))
    return 0


if __name__ == "__main__":
    sys.exit(main())
