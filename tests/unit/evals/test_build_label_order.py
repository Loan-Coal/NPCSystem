"""
Module: test_build_label_order
Layer: test (unit)
Purpose: Tests for scripts/build_label_order.py — EVAL-P22.1's CLI wiring. The
         behaviour under test is the loud-partial contract: a generation directory
         with no judge verdicts must not yield a silently deterministic-only
         "full corpus" labelling order.
Dependencies: pytest, json, pathlib, sys; scripts/build_label_order
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from build_label_order import build, collect_rows  # noqa: E402


def _write(gen_dir: Path, name: str, rows: list[dict]) -> None:
    gen_dir.mkdir(parents=True, exist_ok=True)
    (gen_dir / name).write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def _judged(n: int) -> list[dict]:
    return [
        {"record_id": f"case_{i}:tone_judge:0", "judge_kind": "tone_judge", "score": i % 2 == 0}
        for i in range(n)
    ]


def _deterministic(n: int) -> list[dict]:
    return [
        {"record_id": f"case_{i}:schema:0", "matcher_kind": "schema", "score": i % 3 != 0}
        for i in range(n)
    ]


def test_collects_rows_from_both_verdict_sources(tmp_path: Path) -> None:
    """Both judged.jsonl and deterministic_judged.jsonl feed the ordering."""
    gen = tmp_path / "gen"
    _write(gen, "judged.jsonl", _judged(4))
    _write(gen, "deterministic_judged.jsonl", _deterministic(6))

    rows, warnings = collect_rows(gen)

    assert len(rows) == 10
    assert not warnings
    assert {r[1] for r in rows} == {"tone_judge", "schema"}


def test_missing_judged_file_is_reported_not_silently_dropped(tmp_path: Path) -> None:
    """A deterministic-only directory yields a warning naming what is absent."""
    gen = tmp_path / "gen"
    _write(gen, "deterministic_judged.jsonl", _deterministic(6))

    rows, warnings = collect_rows(gen)

    assert len(rows) == 6
    assert len(warnings) == 1
    assert "judged.jsonl" in warnings[0]
    assert "LLM-judge" in warnings[0]


def test_require_both_refuses_to_write_a_partial_ordering(tmp_path: Path) -> None:
    """Unattended runs can demand a complete corpus rather than a quiet partial one."""
    gen = tmp_path / "gen"
    _write(gen, "deterministic_judged.jsonl", _deterministic(6))

    code = build(gen, tmp_path / "out", require_both=True)

    assert code == 1
    assert not (tmp_path / "out.order.txt").exists()


def test_partial_ordering_is_written_when_not_required_to_be_complete(tmp_path: Path) -> None:
    """Without --require-both the artifact is still produced, flagged PARTIAL."""
    gen = tmp_path / "gen"
    _write(gen, "deterministic_judged.jsonl", _deterministic(6))

    assert build(gen, tmp_path / "out", require_both=False) == 0
    assert (tmp_path / "out.order.txt").read_text(encoding="utf-8").strip()


def test_empty_directory_fails(tmp_path: Path) -> None:
    """Nothing to order is an error, not an empty success."""
    gen = tmp_path / "gen"
    gen.mkdir()
    assert build(gen, tmp_path / "out", require_both=False) == 1


def test_order_is_deterministic_for_the_same_input(tmp_path: Path) -> None:
    """A fixed seed means the same gen dir always produces the same order."""
    gen = tmp_path / "gen"
    _write(gen, "judged.jsonl", _judged(8))
    _write(gen, "deterministic_judged.jsonl", _deterministic(9))

    assert build(gen, tmp_path / "a", require_both=False) == 0
    first = (tmp_path / "a.order.txt").read_text(encoding="utf-8")
    assert build(gen, tmp_path / "b", require_both=False) == 0
    assert (tmp_path / "b.order.txt").read_text(encoding="utf-8") == first
