"""Unit tests for the eval dashboard run-detail page (EVAL-P7.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from evals.dashboard.app import make_app


# ---------------------------------------------------------------------------
# Fixtures helpers
# ---------------------------------------------------------------------------


def _write_meta(run_dir: Path, gen_id: str, k: int = 3) -> None:
    """Write a minimal meta.json into run_dir."""
    meta = {
        "version": 2,
        "gen_id": gen_id,
        "k": k,
        "generated_at": "2026-08-08T00:00:00+00:00",
        "config": {
            "prompt_version": "v1.0",
            "generation_model": "qwen2.5:7b",
            "git_sha": "abc1234",
            "judge_model": "mixtral:8x7b",
        },
    }
    (run_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _write_judged(run_dir: Path, rows: list[dict]) -> None:
    """Write judged.jsonl into run_dir."""
    text = "\n".join(json.dumps(r) for r in rows)
    (run_dir / "judged.jsonl").write_text(text, encoding="utf-8")


def _make_k3_fixture(tmp_path: Path) -> tuple[Path, TestClient]:
    """Create a k=3 generation directory with one flaky (2/3) and one stable_pass (3/3) case."""
    gen_id = "run_k3"
    run_dir = tmp_path / gen_id
    run_dir.mkdir()
    _write_meta(run_dir, gen_id, k=3)
    rows = [
        {"record_id": "case_flaky:tone_judge:0", "passed": True, "repetition": 0},
        {"record_id": "case_flaky:tone_judge:0", "passed": True, "repetition": 1},
        {"record_id": "case_flaky:tone_judge:0", "passed": False, "repetition": 2},
        {"record_id": "case_pass:tone_judge:0", "passed": True, "repetition": 0},
        {"record_id": "case_pass:tone_judge:0", "passed": True, "repetition": 1},
        {"record_id": "case_pass:tone_judge:0", "passed": True, "repetition": 2},
    ]
    _write_judged(run_dir, rows)
    return tmp_path, TestClient(make_app(generations_dir=tmp_path))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_headline_renders_k_adjacent_to_rate(tmp_path: Path) -> None:
    _, client = _make_k3_fixture(tmp_path)

    response = client.get("/runs/run_k3")

    assert response.status_code == 200
    body = response.text
    # The literal string "k=3" must appear in the body
    assert "k=3" in body
    # It must appear within the headline element — find that element and confirm
    assert 'class="headline"' in body
    headline_start = body.index('class="headline"')
    # The headline paragraph ends at the first </p> after it
    headline_end = body.index("</p>", headline_start)
    headline_fragment = body[headline_start:headline_end]
    assert "k=3" in headline_fragment


def test_flaky_cases_appear_before_stable_pass(tmp_path: Path) -> None:
    _, client = _make_k3_fixture(tmp_path)

    response = client.get("/runs/run_k3")

    body = response.text
    # case_flaky (2/3 passes → flaky) must appear before case_pass (3/3 → stable_pass)
    pos_flaky = body.index("case_flaky")
    pos_pass = body.index("case_pass")
    assert pos_flaky < pos_pass


def test_run_not_found_returns_404(tmp_path: Path) -> None:
    client = TestClient(make_app(generations_dir=tmp_path))

    response = client.get("/runs/nonexistent_gen")

    assert response.status_code == 404


def test_no_judged_file_renders_gracefully(tmp_path: Path) -> None:
    run_dir = tmp_path / "no_judged"
    run_dir.mkdir()
    _write_meta(run_dir, "no_judged", k=5)

    client = TestClient(make_app(generations_dir=tmp_path))
    response = client.get("/runs/no_judged")

    assert response.status_code == 200
    body = response.text
    assert "k=5" in body
    # Pass rate should indicate no data available
    assert "n/a" in body.lower() or "no judged" in body.lower() or "0/0" in body


def test_headline_card_shows_both_rates_and_judge(tmp_path: Path) -> None:
    """Headline card shows both LLM-judge and deterministic rates, n's, k, judge model, SHA."""
    gen_id = "run_headline"
    run_dir = tmp_path / gen_id
    run_dir.mkdir()
    _write_meta(run_dir, gen_id, k=3)

    # 1 pass out of 2 LLM-judged records; judge_kind enables scorer lookup
    _write_judged(
        run_dir,
        [
            {"record_id": "c1:tone_judge:0", "passed": True, "repetition": 0, "judge_kind": "tone_judge"},
            {"record_id": "c2:tone_judge:0", "passed": False, "repetition": 0, "judge_kind": "tone_judge"},
        ],
    )
    # 2 pass out of 2 deterministic records
    det_rows = [
        {"record_id": "c1:schema:0", "passed": True, "repetition": 0},
        {"record_id": "c2:schema:0", "passed": True, "repetition": 0},
    ]
    (run_dir / "deterministic_judged.jsonl").write_text(
        "\n".join(json.dumps(r) for r in det_rows), encoding="utf-8"
    )

    # No calibration dir provided in tmp_path → no kappa check → rates shown as-is
    client = TestClient(make_app(generations_dir=tmp_path, calibration_dir=tmp_path))
    response = client.get(f"/runs/{gen_id}")

    assert response.status_code == 200
    body = response.text
    # Headline card element must exist
    assert 'class="headline-card"' in body
    # LLM-judge n: 1 pass of 2 total
    assert "1/2" in body
    # Deterministic n: 2 pass of 2 total (not currently shown — must be added)
    assert "2/2" in body
    # k, judge model, git SHA from meta.json config
    assert "k=3" in body
    assert "mixtral:8x7b" in body
    assert "abc1234" in body


def test_headline_card_refusal_when_kappa_below_threshold(tmp_path: Path) -> None:
    """LLM-judge rate is replaced by EVAL-P11.1 refusal when kappa fails publication threshold."""
    gen_id = "run_refusal"
    run_dir = tmp_path / gen_id
    run_dir.mkdir()
    _write_meta(run_dir, gen_id, k=3)
    # Single judged row with a known scorer so calibration check fires
    _write_judged(
        run_dir,
        [{"record_id": "c1:low_kappa:0", "passed": True, "repetition": 0, "judge_kind": "low_kappa_scorer"}],
    )
    # Calibration with kappa ≈ 0 (all scorer=True, human=False → FP=3, TP=1)
    cal_dir = tmp_path / "cal"
    cal_dir.mkdir()
    cal_labels = [
        {"scorer": "low_kappa_scorer", "scorer_verdict": True, "human_verdict": True},
        {"scorer": "low_kappa_scorer", "scorer_verdict": True, "human_verdict": False},
        {"scorer": "low_kappa_scorer", "scorer_verdict": True, "human_verdict": False},
        {"scorer": "low_kappa_scorer", "scorer_verdict": True, "human_verdict": False},
    ]
    (cal_dir / "labels_v1.jsonl").write_text(
        "\n".join(json.dumps(r) for r in cal_labels), encoding="utf-8"
    )
    client = TestClient(make_app(generations_dir=tmp_path, calibration_dir=cal_dir))
    response = client.get(f"/runs/{gen_id}")

    assert response.status_code == 200
    body = response.text
    assert 'class="refusal"' in body
    assert "calibration does not license" in body
