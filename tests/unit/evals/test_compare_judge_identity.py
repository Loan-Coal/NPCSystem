"""
Module: test_compare_judge_identity
Layer: test (unit)
Purpose: RED anchors for ISSUE-185 — compare.py's comparability gate must reject two
         A/B arms scored by DIFFERENT judge passes. meta.json's config.judge_model is
         a generation-time snapshot and is identical whether a directory was later
         scored by one judge or by the 3-model panel, so the gate as written cannot
         see the difference and reports a confident McNemar verdict whose delta is
         partly the instrument changing rather than the engine.
Dependencies: pytest, json, pathlib; compare (evals/)
Used by: pytest (make test / make check)
"""
from __future__ import annotations

import json
from pathlib import Path

from compare import _comparability_error, _read_run_meta

_HARNESS = "abc123def456"


def _arm(
    tmp_path: Path,
    name: str,
    *,
    configured_judge: str = "mixtral:8x7b",
    run_status: dict | None = None,
) -> Path:
    """Build a generation directory with a meta.json and optional run_status.json."""
    gen_dir = tmp_path / name
    gen_dir.mkdir(parents=True)
    (gen_dir / "meta.json").write_text(
        json.dumps(
            {
                "gen_id": name,
                "k": 3,
                "config": {"harness_version": _HARNESS, "judge_model": configured_judge},
            }
        ),
        encoding="utf-8",
    )
    if run_status is not None:
        (gen_dir / "run_status.json").write_text(json.dumps(run_status), encoding="utf-8")
    return gen_dir


# ---------------------------------------------------------------------------
# RED anchor — ISSUE-185
# ---------------------------------------------------------------------------


def test_panel_arm_is_not_comparable_against_single_judge_arm(tmp_path: Path) -> None:
    """Two arms with identical meta.json but different ACTUAL judge passes must refuse.

    This is the confound the gate exists to prevent: same generation config, one
    directory scored by the 3-model panel and the other by a single judge.
    """
    panel_arm = _arm(
        tmp_path,
        "arm_panel",
        run_status={
            "status": "ok",
            "judge_panel": ["mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"],
            "judge_model": "",
        },
    )
    single_arm = _arm(
        tmp_path,
        "arm_single",
        run_status={"status": "ok", "judge_panel": [], "judge_model": "mixtral:8x7b"},
    )

    reason = _comparability_error(_read_run_meta(panel_arm), _read_run_meta(single_arm), 40)

    assert reason is not None, "a panel arm and a single-judge arm are not comparable"
    assert "judge" in reason.lower()


def test_two_panel_arms_with_the_same_roster_are_comparable(tmp_path: Path) -> None:
    """The gate must not over-refuse: identical panels compare cleanly."""
    roster = ["mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"]
    before = _arm(tmp_path, "b", run_status={"status": "ok", "judge_panel": roster, "judge_model": ""})
    after = _arm(tmp_path, "a", run_status={"status": "gate_failed", "judge_panel": roster, "judge_model": ""})

    assert _comparability_error(_read_run_meta(before), _read_run_meta(after), 40) is None


def test_panel_roster_order_or_membership_change_is_a_mismatch(tmp_path: Path) -> None:
    """Swapping a seat changes the instrument, so the arms must not compare."""
    before = _arm(
        tmp_path, "b",
        run_status={"status": "ok", "judge_panel": ["mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"], "judge_model": ""},
    )
    after = _arm(
        tmp_path, "a",
        run_status={"status": "ok", "judge_panel": ["mixtral:8x7b", "qwen2.5:14b", "gemma2:9b"], "judge_model": ""},
    )

    reason = _comparability_error(_read_run_meta(before), _read_run_meta(after), 40)
    assert reason is not None
    assert "judge" in reason.lower()


# ---------------------------------------------------------------------------
# Backward compatibility — runs predating run_status.json (DEC-189)
# ---------------------------------------------------------------------------


def test_falls_back_to_meta_json_when_no_run_status_exists(tmp_path: Path) -> None:
    """Pre-DEC-189 directories still resolve their judge identity from meta.json."""
    before = _arm(tmp_path, "b", configured_judge="mixtral:8x7b")
    after = _arm(tmp_path, "a", configured_judge="mixtral:8x7b")

    assert _read_run_meta(before).judge_model == "mixtral:8x7b"
    assert _comparability_error(_read_run_meta(before), _read_run_meta(after), 40) is None


def test_legacy_arm_and_panel_arm_do_not_compare(tmp_path: Path) -> None:
    """A pre-DEC-189 single-judge run must not compare clean against a panel run."""
    legacy = _arm(tmp_path, "legacy", configured_judge="mixtral:8x7b")
    panel = _arm(
        tmp_path, "panel",
        run_status={"status": "ok", "judge_panel": ["mixtral:8x7b", "qwen2.5:14b", "llama3.1:8b"], "judge_model": ""},
    )

    assert _comparability_error(_read_run_meta(legacy), _read_run_meta(panel), 40) is not None


def test_unreadable_run_status_falls_back_rather_than_crashing(tmp_path: Path) -> None:
    """A corrupt run_status.json degrades to meta.json, it does not abort the compare."""
    gen_dir = _arm(tmp_path, "b", configured_judge="mixtral:8x7b")
    (gen_dir / "run_status.json").write_text("{not json", encoding="utf-8")

    assert _read_run_meta(gen_dir).judge_model == "mixtral:8x7b"
