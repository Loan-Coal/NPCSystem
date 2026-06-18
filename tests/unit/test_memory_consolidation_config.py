"""
test_memory_consolidation_config.py - Unit tests for MemoryConsolidationEngine LLM config.

Does NOT: call live LLM services or start the application.
"""

from __future__ import annotations

import pytest

from npc_engine.engines.llm_runtime_config import get_config
from npc_engine.engines.llm_config_models import EngineModelConfig
from npc_engine.utils.errors import EngineModelConfigMisconfiguredError


def test_load_memory_consolidation_config_succeeds() -> None:
    config = get_config("memory_consolidation")
    assert isinstance(config, EngineModelConfig)
    assert config.engine == "memory_consolidation"
    assert config.llm.backend == "ollama"
    assert config.llm.max_tokens == 300
    assert config.llm.temperature == 0.4
    assert config.timeouts_ms.full == 30000


def test_load_memory_consolidation_config_missing_engine_raises() -> None:
    with pytest.raises(EngineModelConfigMisconfiguredError):
        get_config("nonexistent_engine_xyz")
