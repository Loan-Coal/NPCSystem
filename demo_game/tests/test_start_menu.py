"""
Module: test_start_menu
Layer: demo_game (tests)
Purpose: Unit tests for ArcChoice enum and StartMenu class.
Dependencies: demo_game.arc_choice, demo_game.ui.start_menu, demo_game.ui.game_window, subprocess
Used by: pytest
"""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_arc_choice_has_four_values() -> None:
    """ArcChoice enum must have exactly four values."""
    from demo_game.arc_choice import ArcChoice

    assert len(ArcChoice) == 4


def test_arc_choice_members_exist() -> None:
    """ArcChoice must have MUNICH, VILLAGE, TAVERN, FREE_PLAY members."""
    from demo_game.arc_choice import ArcChoice

    assert hasattr(ArcChoice, "MUNICH")
    assert hasattr(ArcChoice, "VILLAGE")
    assert hasattr(ArcChoice, "TAVERN")
    assert hasattr(ArcChoice, "FREE_PLAY")


def test_start_menu_init_no_display(monkeypatch: pytest.MonkeyPatch) -> None:
    """StartMenu instantiates without a real pygame display."""
    monkeypatch.setattr("pygame.display.set_mode", lambda *a, **kw: MagicMock())
    monkeypatch.setattr("pygame.display.set_caption", lambda *a: None)

    from demo_game.ui.start_menu import StartMenu

    StartMenu()  # should not raise


def test_dispatch_free_play_opens_game_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """FREE_PLAY arc choice calls game_window.run with the window dimensions."""
    from demo_game.arc_choice import ArcChoice

    monkeypatch.setattr(
        "demo_game.ui.start_menu.StartMenu.show",
        lambda *a, **kw: ArcChoice.FREE_PLAY,
    )
    mock_run = MagicMock()
    monkeypatch.setattr("demo_game.ui.game_window.run", mock_run)

    from demo_game import _dispatch

    _dispatch(window_w=1280, window_h=720)

    mock_run.assert_called_once_with(window_w=1280, window_h=720)


def test_dispatch_munich_calls_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """MUNICH arc choice delegates to subprocess running demo_game.run."""
    from demo_game.arc_choice import ArcChoice

    monkeypatch.setattr(
        "demo_game.ui.start_menu.StartMenu.show",
        lambda *a, **kw: ArcChoice.MUNICH,
    )
    mock_sp = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_sp)

    from demo_game import _dispatch

    _dispatch(window_w=1280, window_h=720)

    call_args = mock_sp.call_args
    assert call_args is not None
    cmd: list[str] = call_args[0][0]
    assert "-m" in cmd
    assert any("demo_game.run" in part for part in cmd)


def test_dispatch_village_calls_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """VILLAGE arc choice delegates to subprocess running run_village_crisis."""
    from demo_game.arc_choice import ArcChoice

    monkeypatch.setattr(
        "demo_game.ui.start_menu.StartMenu.show",
        lambda *a, **kw: ArcChoice.VILLAGE,
    )
    mock_sp = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_sp)

    from demo_game import _dispatch

    _dispatch(window_w=1280, window_h=720)

    call_args = mock_sp.call_args
    assert call_args is not None
    cmd: list[str] = call_args[0][0]
    assert any("run_village_crisis" in part for part in cmd)


def test_dispatch_tavern_calls_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    """TAVERN arc choice delegates to subprocess running run_tavern_intrigue."""
    from demo_game.arc_choice import ArcChoice

    monkeypatch.setattr(
        "demo_game.ui.start_menu.StartMenu.show",
        lambda *a, **kw: ArcChoice.TAVERN,
    )
    mock_sp = MagicMock()
    monkeypatch.setattr("subprocess.run", mock_sp)

    from demo_game import _dispatch

    _dispatch(window_w=1280, window_h=720)

    call_args = mock_sp.call_args
    assert call_args is not None
    cmd: list[str] = call_args[0][0]
    assert any("run_tavern_intrigue" in part for part in cmd)
