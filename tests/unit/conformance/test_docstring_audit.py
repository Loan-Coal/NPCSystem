"""Tests for scripts/docstring_audit.py."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "scripts"))
from docstring_audit import _check_file  # noqa: E402


def _write_tmp(content: str, name: str = "mymod.py", subdir: str | None = None) -> tuple[Path, Path]:
    """Write content to a temp file and return (file_path, src_root)."""
    d = Path(tempfile.mkdtemp())
    if subdir:
        (d / subdir).mkdir(parents=True, exist_ok=True)
        p = d / subdir / name
    else:
        p = d / name
    p.write_text(content, encoding="utf-8")
    return p, d


def test_missing_layer_and_purpose() -> None:
    """File with no docstring at all reports both fields missing."""
    p, src_root = _write_tmp("x = 1\n")
    assert _check_file(p, src_root) == ["Layer:", "Purpose:"]


def test_ok_module_docstring() -> None:
    """File with correct Layer + Purpose passes."""
    src = '"""\nModule: foo\nLayer: graph\nPurpose: Does the thing.\n"""\nx = 1\n'
    p, src_root = _write_tmp(src, subdir="graph")
    assert _check_file(p, src_root) == []


def test_placeholder_purpose_is_rejected() -> None:
    """File whose Purpose is the auto-detected placeholder must be flagged."""
    src = (
        '"""\nfoo.py - Does the thing.\n'
        "Layer: graph\n"
        "Purpose: (auto-detected — review)\n"
        '"""\nx = 1\n'
    )
    p, src_root = _write_tmp(src, subdir="graph")
    result = _check_file(p, src_root)
    assert "Purpose: placeholder" in result, f"Expected placeholder flag, got: {result}"


def test_init_missing_public_surface() -> None:
    """__init__.py without Public surface: is flagged."""
    src = '"""\nPackage: foo\nLayer: graph\nPurpose: Does things.\n"""\n'
    p, src_root = _write_tmp(src, name="__init__.py", subdir="graph")
    assert "Public surface:" in _check_file(p, src_root)


def test_init_ok() -> None:
    """__init__.py with all three fields passes."""
    src = '"""\nPackage: foo\nLayer: graph\nPurpose: Does things.\nPublic surface: Foo.\n"""\n'
    p, src_root = _write_tmp(src, name="__init__.py", subdir="graph")
    assert _check_file(p, src_root) == []


def test_invalid_layer_name_is_rejected() -> None:
    """Layer: value not in DECLARED_LAYERS is flagged."""
    src = '"""\nModule: foo\nLayer: banana\nPurpose: Does the thing.\n"""\nx = 1\n'
    p, src_root = _write_tmp(src, subdir="graph")
    result = _check_file(p, src_root)
    assert any("Layer:" in item for item in result), f"Expected Layer: flag, got: {result}"


def test_layer_mismatch_with_directory_is_rejected() -> None:
    """File in graph/ with Layer: api must be flagged."""
    src = '"""\nModule: foo\nLayer: api\nPurpose: Does the thing.\n"""\nx = 1\n'
    p, src_root = _write_tmp(src, subdir="graph")
    result = _check_file(p, src_root)
    assert any("Layer:" in item for item in result), f"Expected Layer: mismatch flag, got: {result}"


def test_layer_matches_peer_group() -> None:
    """File in auth/ with Layer: api (auth is api-peer) passes."""
    src = '"""\nModule: foo\nLayer: api\nPurpose: Does the thing.\n"""\nx = 1\n'
    p, src_root = _write_tmp(src, subdir="auth")
    assert _check_file(p, src_root) == []


def test_root_level_file_no_directory_constraint() -> None:
    """Root-level file only needs a declared layer; no directory check."""
    src = '"""\nModule: foo\nLayer: config\nPurpose: Does the thing.\n"""\nx = 1\n'
    p, src_root = _write_tmp(src)
    assert _check_file(p, src_root) == []


def test_root_level_file_undeclared_layer_rejected() -> None:
    """Root-level file with undeclared layer is flagged."""
    src = '"""\nModule: foo\nLayer: unknown\nPurpose: Does the thing.\n"""\nx = 1\n'
    p, src_root = _write_tmp(src)
    result = _check_file(p, src_root)
    assert any("Layer:" in item for item in result), f"Expected Layer: flag, got: {result}"
