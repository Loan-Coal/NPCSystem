"""
Module: right_panel
Layer: demo_game.ui
Purpose: Right panel renderer — cycles GRAPH → KNOWLEDGE → PLAYER STATUS → CHAIN →
         TRADE → INVENTORY via Tab. Owns KnowledgeSidebarWidget, QuestPanelWidget,
         GossipChainWidget, TradePanelWidget, and InventoryPanelWidget; reads the
         pre-rendered graph surface from GraphPoller.
Does NOT: make HTTP calls or hold business logic.
Dependencies injected: None (pure rendering + callback registration).
Dependencies: pygame, demo_game.graph_panel.poller, demo_game.ui.knowledge_sidebar,
              demo_game.ui.quest_panel, demo_game.ui.gossip_chain, demo_game.ui.trade_panel,
              demo_game.ui.inventory_panel
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import enum
from typing import Callable

import pygame

from demo_game.graph_panel.poller import GraphPoller
from demo_game.ui.gossip_chain import GossipChainWidget
from demo_game.ui.knowledge_sidebar import KnowledgeSidebarWidget
from demo_game.ui.inventory_panel import InventoryPanelWidget
from demo_game.ui.quest_panel import QuestPanelWidget
from demo_game.ui.trade_panel import TradePanelWidget

PANEL_HEADER_H = 24  # Height of the tab-name header strip at the top of the right panel.

_CLR_RIGHT_PLACEHOLDER = (30, 30, 40)
_CLR_PLACEHOLDER_TEXT = (70, 70, 90)
_CLR_TIMESTAMP = (120, 120, 140)
_CLR_NPC_HEADER_BG = (22, 22, 32)
_CLR_NPC_HEADER_TEXT = (200, 160, 80)


class RightPanel(enum.Enum):
    """Tabs available in the right panel, cycled by the Tab key."""

    GRAPH = "GRAPH"
    KNOWLEDGE = "KNOWLEDGE"
    PLAYER_STATUS = "PLAYER STATUS"
    CHAIN = "CHAIN"
    TRADE = "TRADE"
    PLAYER_INVENTORY = "INVENTORY"


class RightPanelRenderer:
    """Renders the right panel with a Tab-cycling view header.

    Current tabs: GRAPH (default), KNOWLEDGE, PLAYER STATUS, and CHAIN.
    Cycling uses index arithmetic so adding a new tab only requires
    appending a value to RightPanel (see SKILLS_QUEUE.md pygame-n-panel-cycle).

    Args:
        graph_poller: Provides the pre-rendered graph surface each frame.
        font_nav: Font for header text and status labels.
        font_body: Monospace font for sidebar and quest body text.
        font_label: Monospace font for sidebar field labels and badges.
    """

    def __init__(
        self,
        graph_poller: GraphPoller,
        font_nav: pygame.font.Font,
        font_body: pygame.font.Font,
        font_label: pygame.font.Font,
    ) -> None:
        self._graph_poller = graph_poller
        self._font_nav = font_nav
        self._sidebar = KnowledgeSidebarWidget(font_body, font_label)
        self._quest_panel = QuestPanelWidget(font_body, font_label)
        self._chain = GossipChainWidget(font_body, font_label)
        self._trade_panel = TradePanelWidget(font_body, font_label)
        self._inventory_panel = InventoryPanelWidget(font_body, font_label)
        self._active: RightPanel = RightPanel.GRAPH

    # ------------------------------------------------------------------
    # Tab control
    # ------------------------------------------------------------------

    @property
    def active(self) -> RightPanel:
        """The currently active tab."""
        return self._active

    @property
    def show_sidebar(self) -> bool:
        """True when the KNOWLEDGE tab is the active view (DEC-027 scroll routing)."""
        return self._active == RightPanel.KNOWLEDGE

    @property
    def show_quest_panel(self) -> bool:
        """True when the PLAYER STATUS tab is the active view."""
        return self._active == RightPanel.PLAYER_STATUS

    @property
    def show_trade_panel(self) -> bool:
        """True when the TRADE tab is the active view."""
        return self._active == RightPanel.TRADE

    def cycle_tab(self) -> None:
        """Advance to the next tab (Tab key handler)."""
        panels = list(RightPanel)
        self._active = panels[(panels.index(self._active) + 1) % len(panels)]

    def switch_to(self, tab: RightPanel) -> None:
        """Jump directly to the named tab."""
        self._active = tab

    def set_sidebar_data(self, npc_name: str, data: list[dict]) -> None:
        """Push freshly fetched KNOWS_ABOUT pairs into the sidebar widget."""
        self._sidebar.set_data(npc_name, data)

    def clear_sidebar(self) -> None:
        """Clear the sidebar widget (called on fetch error)."""
        self._sidebar.clear()

    def set_quest(self, data: dict | None) -> None:
        """Update the quest data shown in the PLAYER STATUS tab."""
        self._quest_panel.set_quest(data)

    def set_quest_status(self, status: str) -> None:
        """Override the displayed quest status without a full data refresh."""
        self._quest_panel.set_status(status)

    def set_quest_accept_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when the [ACCEPT QUEST] button is clicked."""
        self._quest_panel.set_accept_callback(cb)

    def set_quest_complete_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when the [COMPLETE QUEST] button is clicked."""
        self._quest_panel.set_complete_callback(cb)

    def set_quest_reward_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when the [ACCEPT REWARD] button is clicked."""
        self._quest_panel.set_reward_callback(cb)

    def set_chain_data(self, edges: list[dict]) -> None:
        """Update the gossip chain shown in the CHAIN tab."""
        self._chain.set_chain(edges)

    def set_negotiation_state(self, state: dict | None) -> None:
        """Push a negotiation state snapshot into the trade panel."""
        self._trade_panel.set_negotiation_state(state)

    def get_trade_state(self) -> dict | None:
        """Return the current trade negotiation state, or None."""
        return self._trade_panel.get_state()

    def set_inventory(self, items: list[dict]) -> None:
        """Push a fresh item list into the inventory panel."""
        self._inventory_panel.set_items(items)

    def set_trade_offer_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback for the [OFFER ASKING PRICE] trade button."""
        self._trade_panel.set_offer_callback(cb)

    def set_trade_confirm_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback for the [CONFIRM TRADE] button."""
        self._trade_panel.set_confirm_callback(cb)

    def handle_scroll(self, event: pygame.event.Event) -> None:
        """Route MOUSEWHEEL events to the active scrollable widget."""
        if self._active == RightPanel.KNOWLEDGE:
            self._sidebar.handle_event(event)

    def handle_quest_click(self, event: pygame.event.Event) -> None:
        """Forward an event to the quest panel (for accept-button detection)."""
        self._quest_panel.handle_event(event)

    def handle_trade_click(self, event: pygame.event.Event) -> None:
        """Forward an event to the trade panel (for button detection)."""
        self._trade_panel.handle_event(event)

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def draw(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the right panel (tab header + active view) onto screen.

        Args:
            screen: Target surface.
            rect: Full right-panel rect including the header strip.
        """
        label = f"{self._active.value}  [TAB to switch]"
        self._draw_header(screen, rect, label)
        content_rect = pygame.Rect(
            rect.x, rect.y + PANEL_HEADER_H,
            rect.width, rect.height - PANEL_HEADER_H,
        )
        if self._active == RightPanel.KNOWLEDGE:
            self._sidebar.draw(screen, content_rect)
        elif self._active == RightPanel.PLAYER_STATUS:
            self._quest_panel.draw(screen, content_rect)
        elif self._active == RightPanel.CHAIN:
            self._chain.draw(screen, content_rect)
        elif self._active == RightPanel.TRADE:
            self._trade_panel.draw(screen, content_rect)
        elif self._active == RightPanel.PLAYER_INVENTORY:
            self._inventory_panel.draw(screen, content_rect)
        else:
            self._draw_graph(screen, rect)

    def _draw_header(
        self, screen: pygame.Surface, rect: pygame.Rect, label: str
    ) -> None:
        hdr = pygame.Rect(rect.x, rect.y, rect.width, PANEL_HEADER_H)
        pygame.draw.rect(screen, _CLR_NPC_HEADER_BG, hdr)
        txt = self._font_nav.render(label, True, _CLR_NPC_HEADER_TEXT)
        screen.blit(txt, (rect.x + 10, hdr.centery - txt.get_height() // 2))

    def _draw_graph(self, screen: pygame.Surface, rect: pygame.Rect) -> None:
        surface, last_updated = self._graph_poller.get_surface()
        if surface is None:
            pygame.draw.rect(screen, _CLR_RIGHT_PLACEHOLDER, rect)
            msg = self._font_nav.render("Waiting for data…", True, _CLR_PLACEHOLDER_TEXT)
            screen.blit(msg, (
                rect.centerx - msg.get_width() // 2,
                rect.centery - msg.get_height() // 2,
            ))
            return
        screen.blit(surface, (rect.x, rect.y + PANEL_HEADER_H))
        if last_updated:
            ts = self._font_nav.render(f"Updated: {last_updated}", True, _CLR_TIMESTAMP)
            screen.blit(ts, (
                rect.right - ts.get_width() - 6,
                rect.bottom - ts.get_height() - 4,
            ))
