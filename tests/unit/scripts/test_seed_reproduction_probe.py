"""
Module: test_seed_reproduction_probe
Layer: test (unit)
Purpose: Unit tests for scripts/seed_reproduction_probe.py — EVAL-P20.0's >=95%
         byte-identical reproduction gate. The rules under test are that the probe
         refuses rather than silently intersecting when two runs cover different
         items, that it gates on the per-draw rate rather than the inflated
         per-record rate, and that a mismatched seed is an error not a comparison.
Dependencies: pathlib, sys, pytest, seed_reproduction_probe (scripts/), eval_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "evals"))

from eval_records import GenerationRecord, write_generation_dir  # noqa: E402
from run_config import RunConfig  # noqa: E402
from seed_reproduction_probe import (  # noqa: E402
    REPRODUCTION_GATE,
    SeedReproductionError,
    main,
    measure,
)

_SEED = 20260814


def _config(seed: int | None = _SEED) -> RunConfig:
    return RunConfig(
        prompt_version="v1",
        generation_model="qwen2.5:7b",
        temperature=0.15,
        top_p=0.95,
        max_tokens=512,
        seed=seed,
        judge_model="mixtral:8x7b",
        retrieval_profile="default",
        git_sha="abc1234",
        golden_set_version="aaaaaaaaaaaa",
        harness_version="bbbbbbbbbbbb",
    )


def _record(case: str, index: int, text: str, repetition: int = 0) -> GenerationRecord:
    return GenerationRecord(
        record_id=f"{case}:tone_judge:{index}",
        source="runner",
        npc_id="mira_innkeeper",
        player_id="player_eval",
        player_message="hello",
        npc_response=text,
        criteria="c",
        judge_kind="tone_judge",
        expected_polarity="pass_on_yes",
        repetition=repetition,
    )


def _write(tmp_path: Path, gen_id: str, records, seed: int | None = _SEED) -> Path:
    gen_dir = tmp_path / gen_id
    write_generation_dir(gen_dir, records, gen_id=gen_id, k=1, config=_config(seed))
    return gen_dir / "outputs.jsonl"


def test_identical_runs_report_full_reproduction(tmp_path: Path) -> None:
    records = [_record("case_a", 0, "same"), _record("case_a", 1, "also same")]
    a = _write(tmp_path, "run_a", records)
    b = _write(tmp_path, "run_b", records)

    result, divergent = measure(a, b)

    assert result.rate_records == 1.0
    assert result.rate_calls == 1.0
    assert result.verdict == "MET"
    assert divergent == []


def test_per_draw_rate_is_harsher_than_per_record_rate(tmp_path: Path) -> None:
    """One drifting record out of six in a single draw fails that whole draw.

    This is the reason the gate reads rate_calls: rate_records would report 5/6 = 0.833
    for the same event that rate_calls correctly reports as 0/1.
    """
    a_records = [_record("case_a", i, "same") for i in range(6)]
    b_records = [_record("case_a", i, "same" if i else "drifted") for i in range(6)]
    a = _write(tmp_path, "run_a", a_records)
    b = _write(tmp_path, "run_b", b_records)

    result, divergent = measure(a, b)

    assert result.rate_records == pytest.approx(5 / 6)
    assert result.rate_calls == 0.0
    assert result.n_calls == 1
    assert divergent == ["case_a:tone_judge:0#r0"]


def test_mismatched_item_sets_refuse_rather_than_intersect(tmp_path: Path) -> None:
    """A shrunken denominator is the EVAL-P8.2 defect — refuse, never quietly compare."""
    a = _write(tmp_path, "run_a", [_record("case_a", 0, "x"), _record("case_b", 0, "y")])
    b = _write(tmp_path, "run_b", [_record("case_a", 0, "x")])

    with pytest.raises(SeedReproductionError, match="same items"):
        measure(a, b)


def test_different_seeds_are_an_error_not_a_measurement(tmp_path: Path) -> None:
    records = [_record("case_a", 0, "same")]
    a = _write(tmp_path, "run_a", records, seed=_SEED)
    b = _write(tmp_path, "run_b", records, seed=_SEED + 1)

    with pytest.raises(SeedReproductionError, match="different seeds"):
        measure(a, b)


def test_gate_boundary_is_inclusive(tmp_path: Path) -> None:
    """Exactly 95% of draws reproducing is a pass, matching the roadmap's '>=95%'."""
    a_records = [_record(f"case_{i}", 0, "same") for i in range(20)]
    b_records = [
        _record(f"case_{i}", 0, "same" if i else "drifted") for i in range(20)
    ]
    a = _write(tmp_path, "run_a", a_records)
    b = _write(tmp_path, "run_b", b_records)

    result, _ = measure(a, b)

    assert result.rate_calls == pytest.approx(REPRODUCTION_GATE)
    assert result.verdict == "MET"


def test_main_exits_nonzero_below_the_gate(tmp_path: Path) -> None:
    """The gate is a command that can fail, not a number in prose."""
    a = _write(tmp_path, "run_a", [_record("case_a", 0, "x")])
    b = _write(tmp_path, "run_b", [_record("case_a", 0, "drifted")])

    exit_code = main([
        "--a", str(a.parent), "--b", str(b.parent),
        "--json-out", str(tmp_path / "out.json"),
    ])

    assert exit_code == 1
    assert (tmp_path / "out.json").exists()


def test_main_exits_two_when_runs_are_incomparable(tmp_path: Path) -> None:
    a = _write(tmp_path, "run_a", [_record("case_a", 0, "x"), _record("case_b", 0, "y")])
    b = _write(tmp_path, "run_b", [_record("case_a", 0, "x")])

    exit_code = main([
        "--a", str(a.parent), "--b", str(b.parent),
        "--json-out", str(tmp_path / "out.json"),
    ])

    assert exit_code == 2
    assert not (tmp_path / "out.json").exists()
