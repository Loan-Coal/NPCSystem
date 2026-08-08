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
