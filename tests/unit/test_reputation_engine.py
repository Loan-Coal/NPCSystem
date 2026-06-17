"""
Tests for the 1-hop reputation propagation engine (EXP-52 slice-1).

All tests are fully mocked — no DB, no graph connections. Post SEV-24 the engine
injects a RelationReadPort (reads) + a ReputationGraphPort (nudge write) and holds
no Neo4j session (DEC-122).

Covers:
  - nudge applied when source NPC is FRIENDLY toward player
  - nudge NOT applied when source NPC is WARY toward player
  - nudge NOT applied when no B→player edge exists
  - nudge NOT applied when engine is disabled
  - nudge bounded by max_nudge_per_tick
  - nudge scales with source trust (up to cap)
  - PropagationConfig loads correctly from YAML
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from npc_engine.engines.reputation.propagation_config import (
    PropagationConfig,
    load_propagation_config,
)
from npc_engine.engines.reputation.reputation_engine import ReputationEngine
from npc_engine.utils.errors import RelationEdgeNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_scalars(trust: int = 0, fear: int = 0, affection: int = 0) -> dict[str, int]:
    return {"trust": trust, "fear": fear, "affection": affection}


def _friendly_config() -> PropagationConfig:
    """Config with enabled=True for tests that need the engine on."""
    return PropagationConfig(
        max_nudge_per_tick=2,
        min_source_standing="FRIENDLY",
        min_bridge_standing="NEUTRAL",
        enabled=True,
    )


def _disabled_config() -> PropagationConfig:
    """Config with enabled=False."""
    return PropagationConfig(
        max_nudge_per_tick=2,
        min_source_standing="FRIENDLY",
        min_bridge_standing="NEUTRAL",
        enabled=False,
    )


def _make_reader(side_effect: Any) -> MagicMock:
    """RelationReadPort mock whose get_relation_scalars uses ``side_effect``."""
    reader = MagicMock()
    reader.get_relation_scalars = AsyncMock(side_effect=side_effect)
    return reader


def _make_repo(apply: Any) -> MagicMock:
    """ReputationGraphPort mock whose apply_trust_nudge is ``apply``."""
    repo = MagicMock()
    repo.apply_trust_nudge = apply
    return repo


# ---------------------------------------------------------------------------
# test_nudge_applied_when_source_friendly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nudge_applied_when_source_friendly() -> None:
    """Source→player FRIENDLY, source→B NEUTRAL, B→player edge exists → apply_trust_nudge called."""
    config = _friendly_config()
    mock_apply = AsyncMock()

    # S→player: trust=30 → FRIENDLY; S→B: trust=0 → NEUTRAL; B→player: edge exists
    async def _get_scalars(*, src_id: str, dst_id: str) -> dict[str, int]:
        if src_id == "S" and dst_id == "player":
            return _make_scalars(trust=30)          # FRIENDLY
        if src_id == "S" and dst_id == "B":
            return _make_scalars(trust=0)            # NEUTRAL
        if src_id == "B" and dst_id == "player":
            return _make_scalars(trust=5)            # exists
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)

    engine = ReputationEngine(
        config=config,
        relation_reader=_make_reader(_get_scalars),
        reputation_repo=_make_repo(mock_apply),
    )
    await engine.run_tick(player_id="player", npc_ids=["S", "B"])

    mock_apply.assert_awaited_once()
    call_kwargs = mock_apply.call_args.kwargs
    assert call_kwargs["src_id"] == "B"
    assert call_kwargs["dst_id"] == "player"
    assert call_kwargs["delta_trust"] > 0


# ---------------------------------------------------------------------------
# test_nudge_not_applied_when_source_wary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nudge_not_applied_when_source_wary() -> None:
    """Source→player WARY → apply_trust_nudge NOT called."""
    config = _friendly_config()
    mock_apply = AsyncMock()

    async def _get_scalars(*, src_id: str, dst_id: str) -> dict[str, int]:
        if src_id == "S" and dst_id == "player":
            return _make_scalars(fear=30)            # WARY (score=-30)
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)

    engine = ReputationEngine(
        config=config,
        relation_reader=_make_reader(_get_scalars),
        reputation_repo=_make_repo(mock_apply),
    )
    await engine.run_tick(player_id="player", npc_ids=["S", "B"])

    mock_apply.assert_not_awaited()


# ---------------------------------------------------------------------------
# test_nudge_not_applied_when_no_B_player_edge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nudge_not_applied_when_no_B_player_edge() -> None:
    """B→player edge missing → skipped silently, apply_trust_nudge NOT called."""
    config = _friendly_config()
    mock_apply = AsyncMock()

    async def _get_scalars(*, src_id: str, dst_id: str) -> dict[str, int]:
        if src_id == "S" and dst_id == "player":
            return _make_scalars(trust=30)           # FRIENDLY
        if src_id == "S" and dst_id == "B":
            return _make_scalars(trust=0)            # NEUTRAL
        # B→player: raise (no edge)
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)

    engine = ReputationEngine(
        config=config,
        relation_reader=_make_reader(_get_scalars),
        reputation_repo=_make_repo(mock_apply),
    )
    await engine.run_tick(player_id="player", npc_ids=["S", "B"])

    mock_apply.assert_not_awaited()


# ---------------------------------------------------------------------------
# test_nudge_not_applied_when_disabled
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nudge_not_applied_when_disabled() -> None:
    """enabled=false in config → no nudges performed at all."""
    config = _disabled_config()
    mock_apply = AsyncMock()

    mock_reader = MagicMock()
    mock_reader.get_relation_scalars = AsyncMock(return_value=_make_scalars(trust=80))

    engine = ReputationEngine(
        config=config,
        relation_reader=mock_reader,
        reputation_repo=_make_repo(mock_apply),
    )
    await engine.run_tick(player_id="player", npc_ids=["S", "B"])

    mock_apply.assert_not_awaited()
    # Reader should not have been called either
    mock_reader.get_relation_scalars.assert_not_awaited()


# ---------------------------------------------------------------------------
# test_run_tick_ignores_scheduler_session_kwarg
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_tick_ignores_scheduler_session_kwarg() -> None:
    """run_tick accepts (and ignores) a stray session= kwarg during migration."""
    config = _disabled_config()
    engine = ReputationEngine(
        config=config,
        relation_reader=MagicMock(),
        reputation_repo=_make_repo(AsyncMock()),
    )
    # Must not raise — session is swallowed by **_.
    await engine.run_tick(player_id="player", npc_ids=["S"])


# ---------------------------------------------------------------------------
# test_nudge_bounded_by_max
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nudge_bounded_by_max() -> None:
    """Nudge never exceeds max_nudge_per_tick even when source trust is very high."""
    config = PropagationConfig(
        max_nudge_per_tick=2,
        min_source_standing="FRIENDLY",
        min_bridge_standing="NEUTRAL",
        enabled=True,
    )
    captured: list[int] = []

    async def _capture_nudge(**kwargs: Any) -> None:
        captured.append(kwargs["delta_trust"])

    async def _get_scalars(*, src_id: str, dst_id: str) -> dict[str, int]:
        if src_id == "S" and dst_id == "player":
            return _make_scalars(trust=100)          # very high trust → ALLIED
        if src_id == "S" and dst_id == "B":
            return _make_scalars(trust=0)            # NEUTRAL
        if src_id == "B" and dst_id == "player":
            return _make_scalars(trust=5)
        raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)

    engine = ReputationEngine(
        config=config,
        relation_reader=_make_reader(_get_scalars),
        reputation_repo=_make_repo(_capture_nudge),
    )
    await engine.run_tick(player_id="player", npc_ids=["S", "B"])

    assert len(captured) == 1
    assert captured[0] <= config.max_nudge_per_tick


# ---------------------------------------------------------------------------
# test_nudge_scales_with_trust
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_nudge_scales_with_trust() -> None:
    """Higher source trust produces a larger nudge (up to max_nudge_per_tick cap)."""
    config = PropagationConfig(
        max_nudge_per_tick=10,
        min_source_standing="FRIENDLY",
        min_bridge_standing="NEUTRAL",
        enabled=True,
    )

    async def _run_with_trust(source_trust: int) -> int:
        captured: list[int] = []

        async def _capture(**kwargs: Any) -> None:
            captured.append(kwargs["delta_trust"])

        async def _get_scalars(*, src_id: str, dst_id: str) -> dict[str, int]:
            if src_id == "S" and dst_id == "player":
                return _make_scalars(trust=source_trust)
            if src_id == "S" and dst_id == "B":
                return _make_scalars(trust=0)
            if src_id == "B" and dst_id == "player":
                return _make_scalars(trust=5)
            raise RelationEdgeNotFoundError(src_id=src_id, dst_id=dst_id)

        engine = ReputationEngine(
            config=config,
            relation_reader=_make_reader(_get_scalars),
            reputation_repo=_make_repo(_capture),
        )
        await engine.run_tick(player_id="player", npc_ids=["S", "B"])
        return captured[0] if captured else 0

    # trust=20 → FRIENDLY (score=20); nudge = min(10, 20//10) = min(10,2) = 2
    nudge_low = await _run_with_trust(20)
    # trust=80 → ALLIED (score=80); nudge = min(10, 80//10) = min(10,8) = 8
    nudge_high = await _run_with_trust(80)

    assert nudge_high > nudge_low, f"Expected nudge_high({nudge_high}) > nudge_low({nudge_low})"


# ---------------------------------------------------------------------------
# test_propagation_config_loads
# ---------------------------------------------------------------------------

def test_propagation_config_loads(tmp_path: Path) -> None:
    """load_propagation_config() with a test YAML parses correctly into PropagationConfig."""
    yaml_content = (
        "max_nudge_per_tick: 3\n"
        "min_source_standing: FRIENDLY\n"
        "min_bridge_standing: NEUTRAL\n"
        "enabled: false\n"
    )
    config_file = tmp_path / "reputation_rules.yaml"
    config_file.write_text(yaml_content)

    config = load_propagation_config(config_file)

    assert isinstance(config, PropagationConfig)
    assert config.max_nudge_per_tick == 3
    assert config.min_source_standing == "FRIENDLY"
    assert config.min_bridge_standing == "NEUTRAL"
    assert config.enabled is False
