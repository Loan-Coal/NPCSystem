"""
Tests for SEV-40: structured logging + fail-fast api key in seeder.

Verifies:
- No bare print() calls remain in api_seeder.py or seed_http.py
- resolve_api_key() fails fast (SystemExit) when NPC_API_KEY is unset
- resolve_api_key() returns the value when NPC_API_KEY is set
"""

from __future__ import annotations

import ast
import os
from pathlib import Path
from unittest import mock

import pytest


_DATA_DIR = Path(__file__).parent.parent.parent / "src" / "npc_engine" / "data"
_API_SEEDER_PATH = _DATA_DIR / "api_seeder.py"
_SEED_HTTP_PATH = _DATA_DIR / "seed_http.py"


def _collect_print_calls(source: str) -> list[int]:
    """Return line numbers of bare print() calls in source."""
    tree = ast.parse(source)
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "print":
                lines.append(node.lineno)
    return lines


class TestNoPrintCalls:
    """Source-level AST check: no bare print() calls in seeder files."""

    def test_api_seeder_has_no_print_calls(self) -> None:
        source = _API_SEEDER_PATH.read_text(encoding="utf-8")
        lines = _collect_print_calls(source)
        assert lines == [], f"api_seeder.py still has print() at lines: {lines}"

    def test_seed_http_has_no_print_calls(self) -> None:
        source = _SEED_HTTP_PATH.read_text(encoding="utf-8")
        lines = _collect_print_calls(source)
        assert lines == [], f"seed_http.py still has print() at lines: {lines}"


class TestResolveApiKey:
    """resolve_api_key() fails fast or returns the key."""

    def test_fails_with_systemexit_when_env_not_set(self) -> None:
        from npc_engine.data.api_seeder import resolve_api_key
        with mock.patch.dict(os.environ, {}, clear=True):
            os.environ.pop("NPC_API_KEY", None)
            with pytest.raises(SystemExit):
                resolve_api_key(None)

    def test_returns_env_value_when_set(self) -> None:
        from npc_engine.data.api_seeder import resolve_api_key
        with mock.patch.dict(os.environ, {"NPC_API_KEY": "test-key-abc"}):
            assert resolve_api_key(None) == "test-key-abc"

    def test_args_key_takes_priority_over_env(self) -> None:
        from npc_engine.data.api_seeder import resolve_api_key
        with mock.patch.dict(os.environ, {"NPC_API_KEY": "env-key"}):
            assert resolve_api_key("args-key") == "args-key"

    def test_empty_string_args_key_falls_back_to_env(self) -> None:
        from npc_engine.data.api_seeder import resolve_api_key
        with mock.patch.dict(os.environ, {"NPC_API_KEY": "env-key"}):
            assert resolve_api_key("") == "env-key"
