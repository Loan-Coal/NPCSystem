"""
Module: test_sev37_demo_hygiene
Layer: demo_game (tests)
Purpose: Regression tests for SEV-37 demo hygiene fixes:
         1. TRADE_INTENT_MESSAGE constant replaces inline magic string
         2. print() removed from pollers (logger used instead)
         3. NPC_API_KEY default no longer has the hardcoded sentinel value
         4. demo_game.config exposes get_demo_config() lazy accessor
         5. post_dialogue caps player_message at DEMO_MAX_MESSAGE_CHARS
Dependencies: demo_game.constants, demo_game.config, demo_game.client
Used by: make test-demo
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

_DEMO_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# 1. TRADE_INTENT_MESSAGE constant
# ---------------------------------------------------------------------------


def test_trade_intent_message_constant_exists() -> None:
    """TRADE_INTENT_MESSAGE must be defined in demo_game.constants."""
    from demo_game import constants
    assert hasattr(constants, "TRADE_INTENT_MESSAGE"), (
        "TRADE_INTENT_MESSAGE constant missing from demo_game.constants"
    )
    assert constants.TRADE_INTENT_MESSAGE == "I'd like to trade."


def test_trade_intent_magic_string_not_in_game_controller() -> None:
    """Inline string must not appear in game_controller source."""
    src = _DEMO_ROOT / "game_controller.py"
    text = src.read_text(encoding="utf-8")
    assert "\"I'd like to trade.\"" not in text, (
        "Magic string still present in game_controller.py — use TRADE_INTENT_MESSAGE"
    )


def test_trade_intent_magic_string_not_in_action_bar() -> None:
    """Inline string must not appear in action_bar source."""
    src = _DEMO_ROOT / "ui" / "widgets" / "action_bar.py"
    text = src.read_text(encoding="utf-8")
    assert "\"I'd like to trade.\"" not in text, (
        "Magic string still present in action_bar.py — use TRADE_INTENT_MESSAGE"
    )


def test_trade_intent_magic_string_not_in_quest_trade_controller() -> None:
    """Inline string must not appear in quest_trade_controller source."""
    src = _DEMO_ROOT / "quest_trade_controller.py"
    text = src.read_text(encoding="utf-8")
    assert "\"I'd like to trade.\"" not in text, (
        "Magic string still present in quest_trade_controller.py — use TRADE_INTENT_MESSAGE"
    )


# ---------------------------------------------------------------------------
# 2. print() removed from pollers
# ---------------------------------------------------------------------------

_POLLER_FILES = [
    _DEMO_ROOT / "pollers" / "gold_poller.py",
    _DEMO_ROOT / "pollers" / "emotion_poller.py",
    _DEMO_ROOT / "pollers" / "game_end_poller.py",
    _DEMO_ROOT / "pollers" / "npc_goals_poller.py",
    _DEMO_ROOT / "pollers" / "npc_needs_poller.py",
    _DEMO_ROOT / "pollers" / "npc_politics_poller.py",
    _DEMO_ROOT / "pollers" / "npc_memory_poller.py",
    _DEMO_ROOT / "pollers" / "world_poller.py",
    _DEMO_ROOT / "pollers" / "world_state_poller.py",
    _DEMO_ROOT / "graph_panel" / "poller.py",
    _DEMO_ROOT / "game_controller.py",
    _DEMO_ROOT / "quest_trade_controller.py",
    _DEMO_ROOT / "workers" / "action_workers.py",
    _DEMO_ROOT / "knowledge_sidebar_fetcher.py",
    _DEMO_ROOT / "ui" / "layout" / "game_window.py",
]


@pytest.mark.parametrize("file_path", _POLLER_FILES, ids=[p.name for p in _POLLER_FILES])
def test_no_print_in_poller(file_path: Path) -> None:
    """Poller/controller modules must not use print() — use logger instead."""
    assert file_path.exists(), f"Module file not found: {file_path}"
    text = file_path.read_text(encoding="utf-8")
    # Detect indented print( calls (inside a function body = not a module-level comment)
    assert "    print(" not in text, (
        f"print() found in {file_path.name} — replace with logger.warning/logger.error"
    )


# ---------------------------------------------------------------------------
# 3. NPC_API_KEY hardcoded default sentinel removed
# ---------------------------------------------------------------------------


def test_npc_api_key_sentinel_removed_from_config() -> None:
    """The hardcoded 'change_this' sentinel must not appear in demo_game/config.py."""
    src = _DEMO_ROOT / "config.py"
    text = src.read_text(encoding="utf-8")
    assert "change_this" not in text, (
        "Hardcoded NPC_API_KEY sentinel 'change_this' still in config.py"
    )


# ---------------------------------------------------------------------------
# 4. get_demo_config() lazy accessor
# ---------------------------------------------------------------------------


def test_get_demo_config_exists() -> None:
    """demo_game.config must expose a get_demo_config() callable."""
    from demo_game import config as cfg_mod
    assert hasattr(cfg_mod, "get_demo_config"), (
        "get_demo_config() function missing from demo_game.config"
    )
    assert callable(cfg_mod.get_demo_config)


def test_module_level_config_instance_removed() -> None:
    """Module-level bare `config = DemoConfig()` must not exist in config.py."""
    src = _DEMO_ROOT / "config.py"
    text = src.read_text(encoding="utf-8")
    assert "config = DemoConfig()" not in text, (
        "Module-level 'config = DemoConfig()' still in config.py — use get_demo_config()"
    )


# ---------------------------------------------------------------------------
# 5. player_message cap in post_dialogue
# ---------------------------------------------------------------------------


def test_demo_max_message_chars_constant_exists() -> None:
    """DEMO_MAX_MESSAGE_CHARS must be defined in demo_game.constants."""
    from demo_game import constants
    assert hasattr(constants, "DEMO_MAX_MESSAGE_CHARS"), (
        "DEMO_MAX_MESSAGE_CHARS missing from demo_game.constants"
    )
    assert isinstance(constants.DEMO_MAX_MESSAGE_CHARS, int)
    assert constants.DEMO_MAX_MESSAGE_CHARS > 0


def test_post_dialogue_caps_player_message() -> None:
    """post_dialogue must truncate player_message to DEMO_MAX_MESSAGE_CHARS."""
    from demo_game.constants import DEMO_MAX_MESSAGE_CHARS  # type: ignore[attr-defined]
    from demo_game.client import EngineClient

    mock_http = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": {}}
    mock_http.post.return_value = resp

    client = EngineClient("http://test", "secret", _http_client=mock_http)
    long_msg = "x" * (DEMO_MAX_MESSAGE_CHARS + 500)
    client.post_dialogue("player_1", "npc_1", long_msg)

    call_kwargs = mock_http.post.call_args
    sent_message = call_kwargs[1]["json"]["player_message"]
    assert len(sent_message) <= DEMO_MAX_MESSAGE_CHARS, (
        f"player_message not capped: got {len(sent_message)}, expected <= {DEMO_MAX_MESSAGE_CHARS}"
    )
