"""
Module: tests.unit.scripts.test_check_dead_keywords
Layer: tests
Purpose: Unit tests for scripts/check_dead_keywords.py — flags keyword_none
         terms that never occur anywhere in a committed corpus (EVAL-P19.3).
Dependencies: json, pathlib, sys, typing, yaml, check_dead_keywords
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Sequence

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_dead_keywords import (  # noqa: E402
    BASELINE_PATH,
    DeadKeyword,
    find_dead_keywords,
    format_report,
    main,
    read_baseline,
)


def _case(case_id: str, keywords: list[str], *, kind: str = "keyword_none") -> dict:
    """Build a minimal case dict with one keyword_none expectation."""
    return {"case_id": case_id, "expected": [{"kind": kind, "keywords": keywords}]}


# ---------------------------------------------------------------------------
# RED anchor
# ---------------------------------------------------------------------------


def test_keyword_never_present_in_corpus_is_flagged() -> None:
    """A keyword with zero corpus hits is a guaranteed pass — flag it."""
    cases = [_case("case_neg_example", ["never said this phrase"])]
    corpus = ["Nothing relevant here.", "Nor here."]

    dead = find_dead_keywords(cases, corpus)

    assert dead == [DeadKeyword(case_id="case_neg_example", keyword="never said this phrase")]


# ---------------------------------------------------------------------------
# Validation — the two measured examples from EVAL-P19.3
# ---------------------------------------------------------------------------


def test_thieves_guild_is_flagged_when_corpus_only_has_the_possessive() -> None:
    """'thieves guild' forbidden, corpus only ever writes "thieves' guild" —
    the exact measured EVAL-P19.3 example."""
    cases = [_case("case_neg_lira_no_trust_disclosure", ["thieves guild"])]
    corpus = ["The thieves' guild runs this district."] * 20

    dead = find_dead_keywords(cases, corpus)

    assert len(dead) == 1
    assert dead[0].keyword == "thieves guild"


def test_i_heard_is_flagged_when_corpus_only_has_ive_heard() -> None:
    """'i heard' forbidden, corpus only ever writes "I've heard" — the second
    measured EVAL-P19.3 example."""
    cases = [_case("case_neg_captain_sorn_no_hedging", ["i heard"])]
    corpus = ["I've heard the north is quiet these days."]

    dead = find_dead_keywords(cases, corpus)

    assert len(dead) == 1
    assert dead[0].keyword == "i heard"


# ---------------------------------------------------------------------------
# A keyword that does occur is never flagged
# ---------------------------------------------------------------------------


def test_keyword_present_in_corpus_is_not_flagged() -> None:
    cases = [_case("case_neg_example", ["stolen goods"])]
    corpus = ["I have no stolen goods here."]

    assert find_dead_keywords(cases, corpus) == []


def test_word_boundary_semantics_match_the_runner() -> None:
    """A single-word keyword that only occurs as a substring of a longer word
    is still dead — check_dead_keywords must use the same word-boundary rule
    as matchers.py, or it would under-report."""
    cases = [_case("case_neg_example", ["war"])]
    corpus = ["The warmth of the hearth was welcome."]

    dead = find_dead_keywords(cases, corpus)

    assert len(dead) == 1
    assert dead[0].keyword == "war"


# ---------------------------------------------------------------------------
# Non-keyword_none expectations are ignored
# ---------------------------------------------------------------------------


def test_non_keyword_none_expectations_are_ignored() -> None:
    cases = [_case("case_pos_example", ["never in corpus"], kind="keyword_any")]
    corpus = ["Anything at all."]

    assert find_dead_keywords(cases, corpus) == []


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------


def test_format_report_names_case_and_keyword() -> None:
    dead = [DeadKeyword(case_id="case_neg_x", keyword="never said")]
    text = format_report(dead)
    assert "case_neg_x" in text
    assert "never said" in text


def test_format_report_clean_corpus_says_none_found() -> None:
    text = format_report([])
    assert "No dead keyword" in text


# ---------------------------------------------------------------------------
# R2.3: ratchet — the gate can now fail, in both directions
# ---------------------------------------------------------------------------

def _fixture_tree(tmp_path: Path, cases: Sequence[dict], responses: Sequence[str]) -> list[str]:
    """Write a case dir and a corpus, and return the argv main() needs to read them."""
    cases_dir = tmp_path / "cases"
    cases_dir.mkdir()
    for case in cases:
        (cases_dir / f"{case['case_id']}.yaml").write_text(yaml.safe_dump(case), encoding="utf-8")
    corpus = tmp_path / "outputs.jsonl"
    corpus.write_text(
        "".join(json.dumps({"npc_response": text}) + "\n" for text in responses), encoding="utf-8"
    )
    return [
        "--cases-dir", str(cases_dir),
        "--corpus", str(corpus),
        "--baseline-file", str(tmp_path / "baseline.txt"),
    ]


def test_the_gate_reds_when_a_dead_keyword_is_added(tmp_path: Path) -> None:
    """The RED direction R2.4's anchor depends on: one more dead term than baseline is 1."""
    argv = _fixture_tree(tmp_path, [_case("case_a", ["never uttered"])], ["Nothing here."])
    (tmp_path / "baseline.txt").write_text("0\n", encoding="utf-8")

    assert main(argv) == 1


def test_the_gate_is_green_at_the_recorded_baseline(tmp_path: Path) -> None:
    """Recorded debt does not red. Only growth does."""
    argv = _fixture_tree(tmp_path, [_case("case_a", ["never uttered"])], ["Nothing here."])
    (tmp_path / "baseline.txt").write_text("1\n", encoding="utf-8")

    assert main(argv) == 0


def test_update_records_the_current_count(tmp_path: Path) -> None:
    """--update writes the count, and the same run is green immediately afterwards."""
    argv = _fixture_tree(tmp_path, [_case("case_a", ["never uttered", "nor this"])], ["Nothing."])

    assert main(argv + ["--update"]) == 0
    assert read_baseline(tmp_path / "baseline.txt") == 2
    assert main(argv) == 0


def test_deleting_a_dead_keyword_lowers_the_count_below_baseline(tmp_path: Path) -> None:
    """The shrink direction: green, with a nudge to re-record. Debt shrinks, never grows."""
    argv = _fixture_tree(tmp_path, [_case("case_a", ["never uttered"])], ["Nothing here."])
    (tmp_path / "baseline.txt").write_text("5\n", encoding="utf-8")

    assert main(argv) == 0
    assert read_baseline(tmp_path / "baseline.txt") == 5


def test_a_missing_baseline_reds_rather_than_passing(tmp_path: Path) -> None:
    """A lost baseline reads as 0, which makes any dead keyword a regression."""
    argv = _fixture_tree(tmp_path, [_case("case_a", ["never uttered"])], ["Nothing here."])

    assert read_baseline(tmp_path / "baseline.txt") == 0
    assert main(argv) == 1


def test_the_committed_case_set_is_green_against_the_committed_baseline() -> None:
    """`make check-dead-keywords` must be green on a clean tree, as a permanent test."""
    assert BASELINE_PATH.exists(), "scripts/dead_keywords_baseline.txt must be committed"
    assert main([]) == 0
