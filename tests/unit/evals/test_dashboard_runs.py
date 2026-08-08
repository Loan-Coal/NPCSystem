"""Unit tests for the eval dashboard runs list (EVAL-P7.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from evals.dashboard.app import make_app


def _write_meta(parent: Path, gen_id: str, generated_at: str, k: int = 3) -> None:
    """Write a minimal meta.json into a new subdirectory of parent."""
    d = parent / gen_id
    d.mkdir()
    meta = {
        "version": 2,
        "gen_id": gen_id,
        "k": k,
        "generated_at": generated_at,
        "config": {
            "prompt_version": "v1.0",
            "git_sha": "abc1234",
        },
    }
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def test_run_list_renders_gen_ids_newest_first(tmp_path: Path) -> None:
    _write_meta(tmp_path, "gen_oldest", "2026-01-01T00:00:00+00:00")
    _write_meta(tmp_path, "gen_middle", "2026-03-01T00:00:00+00:00")
    _write_meta(tmp_path, "gen_newest", "2026-06-01T00:00:00+00:00")

    client = TestClient(make_app(generations_dir=tmp_path))
    response = client.get("/")

    assert response.status_code == 200
    body = response.text
    pos_newest = body.index("gen_newest")
    pos_middle = body.index("gen_middle")
    pos_oldest = body.index("gen_oldest")
    assert pos_newest < pos_middle < pos_oldest


def test_empty_generations_dir_returns_200_with_empty_state_message(tmp_path: Path) -> None:
    client = TestClient(make_app(generations_dir=tmp_path))
    response = client.get("/")

    assert response.status_code == 200
    assert "no eval runs" in response.text.lower()
