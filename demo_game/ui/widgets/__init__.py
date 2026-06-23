"""
Package: widgets
Layer: demo_game/ui
Purpose: Reusable pygame widgets, font loading, action bar, start menu, and knowledge sidebar.
Public surface: InputBox, ScrollableLog, NpcListWidget, DegradationBadge, EventBanner,
  ActionBarWidget, FontLoader, StartMenu, KnowledgeSidebarWidget.
Does NOT: import from src/.
"""

from .widgets import InputBox, ScrollableLog, NpcListWidget, DegradationBadge, EventBanner
from .action_bar import ActionBarWidget
from .font_loader import FontLoader
from .start_menu import StartMenu
from .knowledge_sidebar import KnowledgeSidebarWidget
