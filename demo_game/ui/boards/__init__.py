"""
Package: boards
Layer: demo_game/ui
Purpose: Board-style overlay widgets (faction standings, gossip chain visualiser).
Public surface: FactionBoardWidget, GossipChainWidget.
Does NOT: import from src/.
"""

from .faction_board import FactionBoardWidget
from .gossip_chain import GossipChainWidget
