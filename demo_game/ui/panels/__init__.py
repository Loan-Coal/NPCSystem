"""
Package: panels
Layer: demo_game/ui
Purpose: All side-panel widgets for the pygame demo UI.
Public surface: ActionsPanelWidget, BranchPanelWidget, EmotionPanelWidget,
  GoalsPanelWidget, InspectPanelWidget, InvestigationPanelWidget,
  InventoryPanelWidget, MemoryPanelWidget, NeedsPanelWidget, OathPanelWidget,
  PlayerModelPanelWidget, PoliticsPanelWidget, QuestPanelWidget,
  RetrievalPanelWidget, SchemeBoardPanelWidget, TradePanelWidget,
  TreatyPanelWidget, WorldPanelWidget.
Does NOT: import from src/.
"""

from .actions_panel import ActionsPanelWidget
from .branch_panel import BranchPanelWidget
from .emotion_panel import EmotionPanelWidget
from .goals_panel import GoalsPanelWidget
from .inspect_panel import InspectPanelWidget
from .investigation_panel import InvestigationPanelWidget
from .inventory_panel import InventoryPanelWidget
from .memory_panel import MemoryPanelWidget
from .needs_panel import NeedsPanelWidget
from .oath_panel import OathPanelWidget
from .player_model_panel import PlayerModelPanelWidget
from .politics_panel import PoliticsPanelWidget
from .quest_panel import QuestPanelWidget
from .retrieval_panel import RetrievalPanelWidget
from .scheme_board_panel import SchemeBoardPanelWidget
from .trade_panel import TradePanelWidget
from .treaty_panel import TreatyPanelWidget
from .world_panel import WorldPanelWidget
