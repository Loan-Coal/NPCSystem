"""Unit tests for the `python -m evals <verb>` dispatcher (EVAL-P6.3)."""

from __future__ import annotations

import subprocess
import sys
import types
from pathlib import Path

import pytest

from evals.__main__ import VERBS, main


def _stub_module(name: str, recorder: list) -> types.ModuleType:
    """Build a stub module whose main() records the argv it was handed."""
    module = types.ModuleType(name)

    def _main(argv=None):
        recorder.append(argv)
        return 0

    module.main = _main  # type: ignore[attr-defined]
    return module


def test_unknown_verb_exits_2_with_verb_list(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(["frobnicate"])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "frobnicate" in captured.err
    for verb in VERBS:
        assert verb in captured.err


def test_no_verb_exits_2_with_verb_list(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 2
    for verb in VERBS:
        assert verb in captured.err


def test_help_lists_all_six_specced_verbs(capsys: pytest.CaptureFixture[str]) -> None:
    """The six verbs named in EVAL-P6.3 must all appear in --help."""
    exit_code = main(["--help"])
    captured = capsys.readouterr()

    assert exit_code == 0
    for verb in ("generate", "score", "judge", "calibrate", "report", "retrieval"):
        assert verb in captured.out


def test_verb_delegates_remaining_argv_to_module_main(monkeypatch: pytest.MonkeyPatch) -> None:
    recorder: list = []
    module_name = VERBS["generate"].module
    monkeypatch.setitem(sys.modules, module_name, _stub_module(module_name, recorder))

    exit_code = main(["generate", "--k", "2", "--gen-id", "smoke"])

    assert exit_code == 0
    assert recorder == [["--k", "2", "--gen-id", "smoke"]]


def test_main_returning_none_normalises_to_exit_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    """deterministic_pass.main() returns None; the dispatcher must not return None."""
    module_name = VERBS["score"].module
    module = types.ModuleType(module_name)
    module.main = lambda argv=None: None  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)

    assert main(["score", "--transcript", "x.jsonl"]) == 0


def test_help_does_not_import_judge_modules() -> None:
    """`matchers` resolves judge model/URL/timeout at import (matchers.py:117-119).

    `python -m evals --help` must not trigger that, or the CLI is unusable on a machine
    with no judge configured. Checked in a subprocess on purpose: popping these modules
    from sys.modules in-process re-imports `matchers` for the rest of the session, so
    every later test that patches it would patch a stale module object.
    """
    repo_root = Path(__file__).resolve().parents[3]
    code = (
        "import sys; "
        "from evals.__main__ import main; "
        "main(['--help']); "
        "print('MATCHERS_IMPORTED=' + str('matchers' in sys.modules))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=True,
    )

    assert "MATCHERS_IMPORTED=False" in result.stdout


def test_every_verb_maps_to_a_real_module_and_callable() -> None:
    """Each declared verb must name an importable module exposing main()."""
    import importlib

    for verb, target in VERBS.items():
        module = importlib.import_module(target.module)
        assert callable(getattr(module, target.attr)), f"{verb} -> {target.module}.{target.attr}"
