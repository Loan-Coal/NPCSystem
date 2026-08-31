"""
Module: tests.unit.scripts.test_check_engine_logs
Layer: tests
Purpose: Unit tests for scripts/check_engine_logs.py — pins the R1.8 counterfactual
         (an engine logger.info without duration_ms pushes the count above baseline
         and reds) and the ratchet arithmetic around it.
Dependencies: pathlib, sys, pytest, check_engine_logs
Used by: make test (pytest discovery)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))

from check_engine_logs import (  # noqa: E402
    REQUIRED_LOG_FIELD,
    main,
    scan_engines,
    scan_file,
)

_REPO_ROOT = Path(__file__).resolve().parents[3]

_COMPLIANT = (
    'logger.info("tick_done", extra={"npc_id": n, "duration_ms": d})\n'
)
_NON_COMPLIANT = 'logger.info("tick_done", extra={"npc_id": n})\n'


def _engine(tmp_path: Path, body: str) -> Path:
    """Write a throwaway engines dir containing one module with the given body."""
    engines = tmp_path / "engines"
    engines.mkdir()
    (engines / "some_engine.py").write_text(body, encoding="utf-8")
    return engines


def _baseline(tmp_path: Path, count: int) -> Path:
    """Write a throwaway baseline file holding count."""
    path = tmp_path / "baseline.txt"
    path.write_text(f"{count}\n", encoding="utf-8")
    return path


def _argv(engines: Path, baseline: Path) -> list[str]:
    """Build the CLI argv that points main() at the throwaway world."""
    return ["--engines-dir", str(engines), "--baseline-file", str(baseline)]


# --- the R1.8 counterfactual ------------------------------------------------


def test_a_log_call_without_duration_ms_above_baseline_reds(tmp_path: Path) -> None:
    engines = _engine(tmp_path, _NON_COMPLIANT)
    assert main(_argv(engines, _baseline(tmp_path, 0))) == 1


def test_the_same_call_at_baseline_greens(tmp_path: Path) -> None:
    engines = _engine(tmp_path, _NON_COMPLIANT)
    assert main(_argv(engines, _baseline(tmp_path, 1))) == 0


def test_a_compliant_log_call_is_not_a_finding(tmp_path: Path) -> None:
    engines = _engine(tmp_path, _COMPLIANT)
    assert scan_engines(engines) == []


# --- ratchet arithmetic -----------------------------------------------------


def test_dropping_below_baseline_greens(tmp_path: Path) -> None:
    engines = _engine(tmp_path, _COMPLIANT)
    assert main(_argv(engines, _baseline(tmp_path, 5))) == 0


def test_update_records_the_current_count(tmp_path: Path) -> None:
    engines = _engine(tmp_path, _NON_COMPLIANT * 3)
    baseline = _baseline(tmp_path, 0)
    assert main(_argv(engines, baseline) + ["--update"]) == 0
    assert baseline.read_text(encoding="utf-8").strip() == "3"
    assert main(_argv(engines, baseline)) == 0


def test_a_missing_baseline_file_means_zero(tmp_path: Path) -> None:
    engines = _engine(tmp_path, _NON_COMPLIANT)
    assert main(_argv(engines, tmp_path / "absent.txt")) == 1


# --- scanner behaviour ------------------------------------------------------


def test_non_logger_info_calls_are_ignored(tmp_path: Path) -> None:
    engines = _engine(tmp_path, 'client.info("not a logger")\nlogger.debug("x")\n')
    assert scan_engines(engines) == []


def test_underscore_logger_alias_is_scanned(tmp_path: Path) -> None:
    engines = _engine(tmp_path, '_logger.info("e", extra={"npc_id": n})\n')
    assert len(scan_engines(engines)) == 1


def test_an_unparseable_module_is_skipped_not_crashed(tmp_path: Path) -> None:
    engines = _engine(tmp_path, "def broken(:\n")
    assert scan_file(engines / "some_engine.py") == []


def test_findings_name_the_required_field(tmp_path: Path) -> None:
    engines = _engine(tmp_path, _NON_COMPLIANT)
    assert scan_engines(engines)[0].missing_field == REQUIRED_LOG_FIELD


# --- the shipped tree stays at its recorded baseline ------------------------


def test_the_real_engines_tree_is_at_baseline() -> None:
    assert main([]) == 0


def test_the_baseline_is_not_silently_zero() -> None:
    """A zero baseline here would mean the scanner had stopped finding anything."""
    recorded = (_REPO_ROOT / "scripts" / "engine_logs_baseline.txt").read_text(encoding="utf-8")
    assert int(recorded.strip()) > 0
