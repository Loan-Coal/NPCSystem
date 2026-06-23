"""
Package: layout
Layer: demo_game/ui
Purpose: Top-level layout renderers: game window, left/right panel compositors, relation ticker.
Public surface: GameWindow, LeftPanelRenderer, RightPanelRenderer, RightPanel, RelationTicker.
Does NOT: import from src/.
"""

from .game_window import GameWindow
from .left_panel import LeftPanelRenderer
from .right_panel import RightPanel, RightPanelRenderer
from .relation_ticker import RelationTicker
