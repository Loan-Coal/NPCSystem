"""Unit tests for the eval dashboard per-case drill-down page (EVAL-P7.3)."""

from __future__ import annotations

import json
from pathlib import Path

from starlette.testclient import TestClient

from evals.dashboard.app import make_app


# ---------------------------------------------------------------------------
# Fixture helpers
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


def _write_outputs(run_dir: Path, rows: list[dict]) -> None:
    """Write outputs.jsonl into run_dir."""
    text = "\n".join(json.dumps(r) for r in rows)
    (run_dir / "outputs.jsonl").write_text(text, encoding="utf-8")


def _write_judged(run_dir: Path, rows: list[dict]) -> None:
    """Write judged.jsonl into run_dir."""
    text = "\n".join(json.dumps(r) for r in rows)
    (run_dir / "judged.jsonl").write_text(text, encoding="utf-8")


def _make_k3_case_fixture(tmp_path: Path) -> tuple[str, str, TestClient]:
    """Create a k=3 generation dir where each repetition has distinct context keys."""
    gen_id = "run_case_test"
    record_id = "my_case:tone_judge:0"
    run_dir = tmp_path / gen_id
    run_dir.mkdir()
    _write_meta(run_dir, gen_id, k=3)

    outputs = [
        {
            "record_id": record_id,
            "repetition": i,
            "source": "runner",
            "npc_id": "test_npc",
            "player_id": "player_1",
            "player_message": "Hello?",
            "npc_response": f"Response rep{i}",
            "criteria": "Be helpful.",
            "judge_kind": "tone_judge",
            "expected_polarity": "pass_on_yes",
            "retrieved_context": [
                {"key": f"ctx_key_{i}_a", "tier": "tier1", "priority": 0, "text": "data"},
                {"key": f"ctx_key_{i}_b", "tier": "tier2", "priority": 1, "text": "more"},
            ],
            "metadata": {},
            "duration_ms": 100,
            "world_epoch": "age_of_peace",
            "active_conditions": [],
            "matcher_kind": None,
        }
        for i in range(3)
    ]
    judged = [
        {
            "record_id": record_id,
            "repetition": i,
            "passed": i < 2,
            "score": i < 2,
            "reasoning": f"Reasoning for rep {i}",
        }
        for i in range(3)
    ]
    _write_outputs(run_dir, outputs)
    _write_judged(run_dir, judged)

    client = TestClient(make_app(generations_dir=tmp_path))
    return gen_id, record_id, client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_all_k_outputs_render_side_by_side(tmp_path: Path) -> None:
    gen_id, record_id, client = _make_k3_case_fixture(tmp_path)

    response = client.get(f"/runs/{gen_id}/case", params={"record_id": record_id})

    assert response.status_code == 200
    body = response.text
    # 3 distinct panes, each labelled with its repetition index
    for rep in range(3):
        assert f'data-rep="{rep}"' in body
    # Each pane lists that repetition's retrieved_context item keys
    for rep in range(3):
        assert f"ctx_key_{rep}_a" in body
        assert f"ctx_key_{rep}_b" in body


def test_case_judge_reasoning_per_repetition(tmp_path: Path) -> None:
    gen_id, record_id, client = _make_k3_case_fixture(tmp_path)

    response = client.get(f"/runs/{gen_id}/case", params={"record_id": record_id})

    assert response.status_code == 200
    body = response.text
    for rep in range(3):
        assert f"Reasoning for rep {rep}" in body


def test_case_not_found_returns_404(tmp_path: Path) -> None:
    gen_id = "run_case_nf"
    run_dir = tmp_path / gen_id
    run_dir.mkdir()
    _write_meta(run_dir, gen_id)
    _write_outputs(run_dir, [])

    client = TestClient(make_app(generations_dir=tmp_path))
    response = client.get(f"/runs/{gen_id}/case", params={"record_id": "nonexistent:tone_judge:0"})

    assert response.status_code == 404


def test_case_without_judged_renders_gracefully(tmp_path: Path) -> None:
    gen_id = "run_no_judged_case"
    record_id = "case_a:tone_judge:0"
    run_dir = tmp_path / gen_id
    run_dir.mkdir()
    _write_meta(run_dir, gen_id)
    outputs = [
        {
            "record_id": record_id,
            "repetition": 0,
            "source": "runner",
            "npc_id": "npc_a",
            "player_id": "player_1",
            "player_message": "Hi",
            "npc_response": "Hello",
            "criteria": "",
            "judge_kind": "tone_judge",
            "expected_polarity": "pass_on_yes",
            "retrieved_context": [{"key": "world_key", "tier": "t0", "priority": 0, "text": "x"}],
            "metadata": {},
            "duration_ms": 50,
            "world_epoch": "age_of_peace",
            "active_conditions": [],
            "matcher_kind": None,
        }
    ]
    _write_outputs(run_dir, outputs)

    client = TestClient(make_app(generations_dir=tmp_path))
    response = client.get(f"/runs/{gen_id}/case", params={"record_id": record_id})

    assert response.status_code == 200
    assert "world_key" in response.text
