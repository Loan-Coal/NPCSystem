"""
Module: test_demo_raw_paths_are_mounted
Layer: tests/unit/conformance
Purpose: Every raw URL path a demo scene posts to directly (bypassing EngineClient) must be a
    route the app actually mounts.

DeterminismBeat posted to `/v1/batch/gossip_tick`, but the batch router is mounted under the
admin prefix, so ACT 8 died with HTTP 404 in the first live `make demo-run-live` (T2.4). Its
unit test imported the same constant it was checking, so it could never see the mismatch;
this test checks the constants against the real route table instead.
"""

from __future__ import annotations

import pytest

from demo_game.beats.determinism_beat import _GOSSIP_TICK_PATH
from demo_game.runners.run_scenes import _EVENT_TICK_PATH
from npc_engine.main import app


def _mounted_paths() -> set[str]:
    return {path for route in app.routes if (path := getattr(route, "path", None))}


@pytest.mark.parametrize("raw_path", [_GOSSIP_TICK_PATH, _EVENT_TICK_PATH])
def test_demo_raw_path_is_a_mounted_route(raw_path: str) -> None:
    assert raw_path in _mounted_paths(), f"demo posts to unmounted route {raw_path!r}"
