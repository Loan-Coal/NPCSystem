"""
Module: test_judge_bypass_guard
Layer: test (unit)
Purpose: Mechanically enforce DEC-143 — every judge consumer must resolve its model through
         judge_config.resolve_judge_model(), never by hardcoding a JUDGE_MODEL default or
         building its own OllamaAdapter.
Dependencies: ast, pathlib.
Used by: pytest (make test / make check).

Why this exists: scenario_voice_from_graph.py carried `os.getenv("JUDGE_MODEL", "qwen2.5:14b")`
plus its own adapter for months. Its module docstring claimed DEC-143 compliance it did not
have, and nothing failed — the collision guard simply never ran for that scenario. Code review
missed it repeatedly because the file looked like its compliant siblings. A rule no test
enforces is a rule that silently decays, so this scans the AST instead of trusting review.

The detector is self-tested against synthetic good/bad sources below, so a detector that
stops detecting fails loudly rather than reporting a clean tree by accident.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Directories whose modules may consume an LLM judge.
_SCANNED_DIRS = ("evals", "e2e/scenarios", "e2e/helpers")

# The only modules permitted to construct a judge adapter directly.
# judge_client is the sanctioned factory; judge_config is the resolver itself.
_ADAPTER_ALLOWLIST = frozenset({"judge_client.py", "judge_config.py"})

_JUDGE_MODEL_ENV = "JUDGE_MODEL"
_ADAPTER_NAME = "OllamaAdapter"


def _called_name(node: ast.Call) -> str:
    """Return the simple name of a call target (``f()`` or ``mod.f()``)."""
    func = node.func
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _is_getenv_with_default(node: ast.Call, env_key: str) -> bool:
    """True for ``os.getenv("<env_key>", <default>)`` — an unguarded fallback."""
    if _called_name(node) != "getenv" or len(node.args) < 2:
        return False
    first = node.args[0]
    return isinstance(first, ast.Constant) and first.value == env_key


def find_judge_bypasses(source: str, filename: str) -> list[str]:
    """Return human-readable descriptions of every DEC-143 bypass in one module.

    Args:
        source: Python source text.
        filename: Basename used for allowlist checks and message context.
    Returns:
        A list of violation descriptions; empty means the module is compliant.
    """
    violations: list[str] = []
    for node in ast.walk(ast.parse(source, filename=filename)):
        if not isinstance(node, ast.Call):
            continue
        if _is_getenv_with_default(node, _JUDGE_MODEL_ENV):
            violations.append(
                f"{filename}:{node.lineno} reads {_JUDGE_MODEL_ENV} with a hardcoded default "
                "instead of calling judge_config.resolve_judge_model()"
            )
        if _called_name(node) == _ADAPTER_NAME and filename not in _ADAPTER_ALLOWLIST:
            violations.append(
                f"{filename}:{node.lineno} constructs {_ADAPTER_NAME} directly; "
                "judge adapters must come from e2e.helpers.judge_client.make_judge()"
            )
    return violations


# ── detector self-tests ────────────────────────────────────────────────────────

_BAD_HARDCODED_DEFAULT = '''
import os
_JUDGE_MODEL = os.getenv("JUDGE_MODEL", "qwen2.5:14b")
'''

_BAD_DIRECT_ADAPTER = '''
from npc_engine.engines.llm.ollama_adapter import OllamaAdapter
def _make_judge():
    return OllamaAdapter(base_url="http://x", model_name="qwen2.5:14b", timeout_seconds=60.0)
'''

_GOOD_SANCTIONED = '''
from e2e.helpers.judge_client import make_judge, resolve_judge_model
_JUDGE_MODEL = resolve_judge_model()
def _make_judge():
    return make_judge()
'''


def test_detector_flags_hardcoded_judge_model_default() -> None:
    found = find_judge_bypasses(_BAD_HARDCODED_DEFAULT, "scenario_fake.py")
    assert len(found) == 1 and "hardcoded default" in found[0]


def test_detector_flags_direct_adapter_construction() -> None:
    found = find_judge_bypasses(_BAD_DIRECT_ADAPTER, "scenario_fake.py")
    assert len(found) == 1 and "constructs OllamaAdapter" in found[0]


def test_detector_allows_sanctioned_factory_module() -> None:
    """judge_client.py is allowed to build the adapter — it is the sanctioned factory."""
    assert find_judge_bypasses(_BAD_DIRECT_ADAPTER, "judge_client.py") == []


def test_detector_accepts_compliant_source() -> None:
    assert find_judge_bypasses(_GOOD_SANCTIONED, "scenario_fake.py") == []


# ── the real scan ──────────────────────────────────────────────────────────────


def _scanned_files() -> list[Path]:
    """Every Python module in the judge-consuming directories."""
    return [path for directory in _SCANNED_DIRS for path in sorted((_REPO_ROOT / directory).glob("*.py"))]


def test_scan_covers_the_known_judge_consumers() -> None:
    """Guard the guard: an empty or mis-rooted glob must not read as 'all clean'."""
    names = {path.name for path in _scanned_files()}
    for expected in ("matchers.py", "judge_client.py", "scenario_voice_from_graph.py"):
        assert expected in names, f"{expected} not scanned — glob is wrong, results are meaningless"


def test_no_judge_bypasses_in_repo() -> None:
    violations = [
        problem
        for path in _scanned_files()
        for problem in find_judge_bypasses(path.read_text(encoding="utf-8"), path.name)
    ]
    assert not violations, "DEC-143 bypass(es) found:\n" + "\n".join(violations)
