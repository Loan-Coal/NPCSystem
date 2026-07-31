"""
Module: test_model_identity
Layer: test (unit)
Purpose: Pin the shipped generation model so config and documentation cannot drift apart,
         and keep the DEC-143 judge-separation invariant honest under the current fleet.
Dependencies: pathlib, re, yaml, judge_config (evals/, on pytest pythonpath).
Used by: pytest (make test / make check).

Rationale (EVAL-P0.1): every eval number is only interpretable if the model that produced
it is knowable. An unstaged llm_config.yaml edit against a stale CLAUDE.md Stack table made
that unanswerable. These tests fail loudly the next time the two diverge.
"""

from __future__ import annotations

import re
from pathlib import Path

import judge_config
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CLAUDE_MD = _REPO_ROOT / "project-harness" / "CLAUDE.md"
_ENGINE_CONFIGS = sorted((_REPO_ROOT / "src" / "npc_engine" / "engines").glob("*/llm_config.yaml"))

# Matches the Stack-table LLM row in CLAUDE.md, e.g. "| LLM | Ollama (`qwen2.5:7b`); ..."
_DOCUMENTED_MODEL_PATTERN = re.compile(r"^\|\s*LLM\s*\|\s*Ollama\s*\(`([^`]+)`\)", re.MULTILINE)


def _documented_model() -> str:
    """Return the generation model named in the CLAUDE.md Stack table."""
    match = _DOCUMENTED_MODEL_PATTERN.search(_CLAUDE_MD.read_text(encoding="utf-8"))
    assert match is not None, f"No 'Ollama (`<model>`)' Stack-table row found in {_CLAUDE_MD}"
    return match.group(1)


def _declared_model(config_path: Path) -> str:
    """Return the llm.model declared by one engine's llm_config.yaml."""
    data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return str(data["llm"]["model"])


def test_engine_configs_exist() -> None:
    assert _ENGINE_CONFIGS, "No engine llm_config.yaml files discovered — glob is wrong"


def test_documented_generation_model_matches_config() -> None:
    documented = _documented_model()
    mismatches = {
        path.parent.name: declared
        for path in _ENGINE_CONFIGS
        if (declared := _declared_model(path)) != documented
    }
    assert not mismatches, (
        f"CLAUDE.md documents {documented!r} but these engines declare otherwise: {mismatches}. "
        "Update both together — the documented model is authoritative."
    )


def test_all_engines_share_one_generation_model() -> None:
    """One resident model across the fleet (DEC-149): keeps eval numbers attributable."""
    declared = {path.parent.name: _declared_model(path) for path in _ENGINE_CONFIGS}
    assert len(set(declared.values())) == 1, (
        f"Engines declare more than one generation model: {declared}. A mixed fleet makes "
        "'which model produced this number' unanswerable and blocks judge-model choices."
    )


def test_default_judge_does_not_collide_with_generation_fleet() -> None:
    """DEC-143 separation invariant holds for the shipped default judge."""
    generation_models = judge_config.discover_generation_models(repo_root=_REPO_ROOT)
    assert generation_models, "discover_generation_models() found nothing"
    assert judge_config.DEFAULT_JUDGE_MODEL not in generation_models
