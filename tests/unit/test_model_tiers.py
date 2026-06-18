"""Tests for npc_engine.setup.model_tiers — model tier selection logic."""
from __future__ import annotations

import pytest

from npc_engine.setup.model_tiers import (
    MODEL_3B,
    MODEL_7B,
    MODEL_14B,
    VRAM_TIER_7B_MB,
    VRAM_TIER_14B_MB,
    select_model_for_vram,
)


def test_select_model_tier_no_gpu_returns_3b() -> None:
    assert select_model_for_vram(0) == MODEL_3B


def test_select_model_tier_below_7b_threshold_returns_3b() -> None:
    assert select_model_for_vram(VRAM_TIER_7B_MB - 1) == MODEL_3B


def test_select_model_tier_exactly_7b_threshold_returns_7b() -> None:
    assert select_model_for_vram(VRAM_TIER_7B_MB) == MODEL_7B


def test_select_model_tier_between_thresholds_returns_7b() -> None:
    assert select_model_for_vram(VRAM_TIER_7B_MB + 512) == MODEL_7B


def test_select_model_tier_exactly_14b_threshold_returns_14b() -> None:
    assert select_model_for_vram(VRAM_TIER_14B_MB) == MODEL_14B


def test_select_model_tier_high_vram_returns_14b() -> None:
    assert select_model_for_vram(24_576) == MODEL_14B


def test_model_names_are_qwen_family() -> None:
    for model in (MODEL_3B, MODEL_7B, MODEL_14B):
        assert model.startswith("qwen"), f"{model!r} is not a qwen model"


def test_vram_thresholds_are_ordered() -> None:
    assert VRAM_TIER_7B_MB < VRAM_TIER_14B_MB
