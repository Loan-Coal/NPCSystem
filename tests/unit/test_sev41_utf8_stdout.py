"""
Module: test_sev41_utf8_stdout
Layer: tests/unit
Purpose: Regression tests for SEV-41 — ensure ensure_utf8_stdout() is
         idempotent, safe on streams lacking reconfigure, and calls
         reconfigure when the stream supports it and is not already UTF-8.
Dependencies: demo_game.encoding_utils
Used by: pytest unit suite
"""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest


class _FakeStreamNoReconfigure:
    """Mimics a stream with no reconfigure method (older Python/io wrapper)."""

    def write(self, s: str) -> int:
        return len(s)


class _FakeStreamAlreadyUtf8:
    """Mimics a stream already configured with UTF-8 encoding."""

    encoding: str = "utf-8"

    def reconfigure(self, *, encoding: str) -> None:
        raise AssertionError("reconfigure must NOT be called when encoding is already utf-8")


class _FakeStreamCp1252:
    """Mimics a Windows cp1252 stream that supports reconfigure."""

    encoding: str = "cp1252"
    reconfigure_calls: list[dict[str, str]]

    def __init__(self) -> None:
        self.reconfigure_calls = []

    def reconfigure(self, *, encoding: str) -> None:
        self.encoding = encoding
        self.reconfigure_calls.append({"encoding": encoding})


class TestEnsureUtf8Stdout:
    """ensure_utf8_stdout() is idempotent and safe."""

    def test_no_op_when_stream_has_no_reconfigure(self) -> None:
        from demo_game.encoding_utils import _reconfigure_stream_if_needed
        stream = _FakeStreamNoReconfigure()
        _reconfigure_stream_if_needed(stream)  # must not raise

    def test_no_op_when_already_utf8(self) -> None:
        from demo_game.encoding_utils import _reconfigure_stream_if_needed
        stream = _FakeStreamAlreadyUtf8()
        _reconfigure_stream_if_needed(stream)  # must not call reconfigure

    def test_reconfigures_cp1252_stream(self) -> None:
        from demo_game.encoding_utils import _reconfigure_stream_if_needed
        stream = _FakeStreamCp1252()
        _reconfigure_stream_if_needed(stream)
        assert stream.reconfigure_calls == [{"encoding": "utf-8"}]
        assert stream.encoding == "utf-8"

    def test_idempotent_second_call_is_no_op(self) -> None:
        from demo_game.encoding_utils import _reconfigure_stream_if_needed
        stream = _FakeStreamCp1252()
        _reconfigure_stream_if_needed(stream)
        _reconfigure_stream_if_needed(stream)  # second call — already utf-8
        assert len(stream.reconfigure_calls) == 1

    def test_ensure_utf8_stdout_reconfigures_both_streams(self) -> None:
        from demo_game.encoding_utils import ensure_utf8_stdout
        stdout = _FakeStreamCp1252()
        stderr = _FakeStreamCp1252()
        with patch("demo_game.encoding_utils.sys") as mock_sys:
            mock_sys.stdout = stdout
            mock_sys.stderr = stderr
            ensure_utf8_stdout()
        assert stdout.encoding == "utf-8"
        assert stderr.encoding == "utf-8"
