"""Tests for npc_engine.setup.vram_detector — VRAM detection logic."""
from __future__ import annotations

from unittest.mock import patch, MagicMock
import subprocess

import pytest

from npc_engine.setup.vram_detector import detect_vram_mb, _detect_nvidia_vram_mb


class TestDetectNvidiaVramMb:
    def test_returns_parsed_vram_on_success(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "8192\n"
        with patch("subprocess.run", return_value=mock_result):
            assert _detect_nvidia_vram_mb() == 8192

    def test_returns_zero_on_nonzero_returncode(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert _detect_nvidia_vram_mb() == 0

    def test_returns_zero_when_nvidia_smi_not_found(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError()):
            assert _detect_nvidia_vram_mb() == 0

    def test_returns_zero_on_timeout(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("nvidia-smi", 10)):
            assert _detect_nvidia_vram_mb() == 0

    def test_returns_zero_on_empty_output(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            assert _detect_nvidia_vram_mb() == 0

    def test_handles_multiple_gpu_output_takes_first(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "8192\n4096\n"
        with patch("subprocess.run", return_value=mock_result):
            assert _detect_nvidia_vram_mb() == 8192


class TestDetectVramMb:
    def test_returns_nvidia_vram_when_gpu_present(self) -> None:
        with patch("npc_engine.setup.vram_detector._detect_nvidia_vram_mb", return_value=8192):
            assert detect_vram_mb() == 8192

    def test_returns_zero_when_no_gpu(self) -> None:
        with patch("npc_engine.setup.vram_detector._detect_nvidia_vram_mb", return_value=0):
            assert detect_vram_mb() == 0

    def test_return_type_is_int(self) -> None:
        with patch("npc_engine.setup.vram_detector._detect_nvidia_vram_mb", return_value=4096):
            result = detect_vram_mb()
        assert isinstance(result, int)
