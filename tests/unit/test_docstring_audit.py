"""Tests for scripts/docstring_audit.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
from docstring_audit import _check_file  # noqa: E402


def _write_tmp(content: str, name: str = "mymod.py") -> Path:
    """Write content to a temp file and return its path."""
    d = tempfile.mkdtemp()
    p = Path(d) / name
    p.write_text(content, encoding="utf-8")
    return p


def test_missing_layer_and_purpose() -> None:
    """File with no docstring at all reports both fields missing."""
    p = _write_tmp("x = 1\n")
    assert _check_file(p) == ["Layer:", "Purpose:"]


def test_ok_module_docstring() -> None:
    """File with correct Layer + Purpose passes."""
    src = '"""\nModule: foo\nLayer: graph\nPurpose: Does the thing.\n"""\nx = 1\n'
    p = _write_tmp(src)
    assert _check_file(p) == []


def test_placeholder_purpose_is_rejected() -> None:
    """File whose Purpose is the auto-detected placeholder must be flagged."""
    src = (
        '"""\nfoo.py - Does the thing.\n'
        "Layer: graph\n"
        "Purpose: (auto-detected — review)\n"
        '"""\nx = 1\n'
    )
    p = _write_tmp(src)
    result = _check_file(p)
    assert "Purpose: placeholder" in result, f"Expected placeholder flag, got: {result}"


def test_init_missing_public_surface() -> None:
    """__init__.py without Public surface: is flagged."""
    src = '"""\nPackage: foo\nLayer: graph\nPurpose: Does things.\n"""\n'
    p = _write_tmp(src, name="__init__.py")
    assert "Public surface:" in _check_file(p)


def test_init_ok() -> None:
    """__init__.py with all three fields passes."""
    src = '"""\nPackage: foo\nLayer: graph\nPurpose: Does things.\nPublic surface: Foo.\n"""\n'
    p = _write_tmp(src, name="__init__.py")
    assert _check_file(p) == []
