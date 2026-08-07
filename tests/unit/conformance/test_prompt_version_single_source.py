"""
Module: test_prompt_version_single_source
Layer: tests/unit/conformance
Purpose: Conformance test ensuring prompt version has a single source of truth (EVAL-P1.2).
         PROMPT_VERSION in prompt_builder.py must equal prompt.version in llm_config.yaml.
Dependencies: yaml, pathlib, npc_engine.engines.dialogue.prompt_builder
Used by: pytest conformance suite
"""

from __future__ import annotations

from pathlib import Path

import yaml

from npc_engine.engines.dialogue.prompt_builder import PROMPT_VERSION

_LLM_CONFIG = (
    Path(__file__).resolve().parents[3]
    / "src"
    / "npc_engine"
    / "engines"
    / "dialogue"
    / "llm_config.yaml"
)


def test_prompt_version_matches_llm_config() -> None:
    """PROMPT_VERSION in prompt_builder must equal prompt.version in llm_config.yaml.

    Single-source enforcement: the YAML is authoritative, prompt_builder.py reads it.
    A mismatch means the Python constant drifted from the YAML — fix the YAML (EVAL-P1.2).
    """
    with _LLM_CONFIG.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    yaml_version = str(data["prompt"]["version"])
    assert PROMPT_VERSION == yaml_version, (
        f"prompt_builder.PROMPT_VERSION={PROMPT_VERSION!r} does not match "
        f"llm_config.yaml prompt.version={yaml_version!r}. "
        "The YAML is authoritative — update llm_config.yaml to change the version."
    )
