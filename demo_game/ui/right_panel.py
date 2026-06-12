"""
Module: right_panel
Layer: demo_game.ui
Purpose: Right panel renderer — cycles GRAPH → KNOWLEDGE → PLAYER STATUS → CHAIN →
         TRADE → INVENTORY → ACTIONS → INSPECT → WORLD → EMOTION → NEEDS → GOALS
         → POLITICS → MEMORY → RETRIEVAL → FACTION → PLAYER MODEL via Tab.
         Owns all panel widgets; reads the pre-rendered graph surface from GraphPoller.
Does NOT: make HTTP calls or hold business logic.
Dependencies injected: None (pure rendering + callback registration).
Dependencies: pygame, demo_game.graph_panel.poller, demo_game.ui.knowledge_sidebar,
              demo_game.ui.quest_panel, demo_game.ui.gossip_chain, demo_game.ui.trade_panel,
              demo_game.ui.inventory_panel, demo_game.ui.inspect_panel,
              demo_game.ui.world_panel, demo_game.ui.emotion_panel,
              demo_game.ui.needs_panel, demo_game.ui.goals_panel,
              demo_game.ui.politics_panel, demo_game.ui.memory_panel,
              demo_game.ui.retrieval_panel, demo_game.ui.faction_board,
              demo_game.ui.player_model_panel, demo_game.game_end_checker
Used by: demo_game.ui.game_window

NOTE: ~480 lines — accepted over the 300-line limit (see DEC-047). Single cohesive
class; overage grows with each new panel tab. Split trigger: second overlay
workflow of this kind or total > 550 lines.
"""

from __future__ import annotations

import enum
from typing import TYPE_CHECKING, Callable

import pygame

from demo_game.graph_panel.poller import GraphPoller

if TYPE_CHECKING:
    from demo_game.game_end_checker import ObjectiveState
from demo_game.ui.actions_panel import ActionsPanelWidget
from demo_game.ui.emotion_panel import EmotionPanelWidget
from demo_game.ui.goals_panel import GoalsPanelWidget
from demo_game.ui.gossip_chain import GossipChainWidget
from demo_game.ui.memory_panel import MemoryPanelWidget
from demo_game.ui.faction_board import FactionBoardWidget
from demo_game.ui.retrieval_panel import RetrievalPanelWidget
from demo_game.ui.politics_panel import PoliticsPanelWidget
from demo_game.ui.player_model_panel import PlayerModelPanelWidget
from demo_game.ui.inspect_panel import InspectPanelWidget
from demo_game.ui.knowledge_sidebar import KnowledgeSidebarWidget
from demo_game.ui.inventory_panel import InventoryPanelWidget
from demo_game.ui.needs_panel import NeedsPanelWidget
from demo_game.ui.quest_panel import QuestPanelWidget
from demo_game.ui.trade_panel import TradePanelWidget
from demo_game.ui.world_panel import WorldPanelWidget

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
    ACTIONS = "ACTIONS"
    INSPECT = "INSPECT"
    WORLD = "WORLD"
    EMOTION = "EMOTION"
    NEEDS = "NEEDS"
    GOALS = "GOALS"
    POLITICS = "POLITICS"
    MEMORY = "MEMORY"
    RETRIEVAL = "RETRIEVAL"
    FACTION = "FACTION"
    PLAYER_MODEL = "PLAYER MODEL"


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
        self._actions_panel = ActionsPanelWidget(font_label)
        self._inspect_panel = InspectPanelWidget(font_body, font_label)
        self._world_panel = WorldPanelWidget(font_body, font_label)
        self._emotion_panel = EmotionPanelWidget(font_body, font_label)
        self._needs_panel = NeedsPanelWidget(font_body, font_label)
        self._goals_panel = GoalsPanelWidget(font_body, font_label)
        self._politics_panel = PoliticsPanelWidget(font_body, font_label)
        self._memory_panel = MemoryPanelWidget(font_body, font_label)
        self._retrieval_panel = RetrievalPanelWidget(font_body, font_label)
        self._faction_board = FactionBoardWidget(font_body, font_label)
        self._player_model_panel = PlayerModelPanelWidget(font_body, font_label)
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

    def set_player_gold(self, gold: int | None) -> None:
        """Push the player's currency balance into the inventory panel."""
        self._inventory_panel.set_gold(gold)

    def set_npc_trade_gold(self, gold: int | None) -> None:
        """Push the NPC seller's currency balance into the trade panel."""
        self._trade_panel.set_npc_gold(gold)

    def set_trade_offer_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback for the [OFFER ASKING PRICE] trade button."""
        self._trade_panel.set_offer_callback(cb)

    def set_trade_confirm_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback for the [CONFIRM TRADE] button."""
        self._trade_panel.set_confirm_callback(cb)

    def set_npc_selected(self, selected: bool) -> None:
        """Propagate NPC selection state to the actions panel."""
        self._actions_panel.set_npc_selected(selected)

    def set_generate_quest_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Generate Quest] is clicked."""
        self._actions_panel.set_generate_quest_callback(cb)

    def set_inspect_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Inspect] is clicked."""
        self._actions_panel.set_inspect_callback(cb)

    def set_give_item_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Give item] is clicked."""
        self._actions_panel.set_give_item_callback(cb)

    def set_travel_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Travel] is clicked."""
        self._actions_panel.set_travel_callback(cb)

    def set_bribe_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Bribe] is clicked."""
        self._actions_panel.set_bribe_callback(cb)

    def start_item_pick(self, on_selected: Callable[[dict], None]) -> None:
        """Enter give mode: switch to INVENTORY tab with clickable rows.

        Wraps on_selected and a cancel handler so both stop give mode and
        return to the ACTIONS tab automatically before firing the caller's
        callback.

        Args:
            on_selected: Called with the chosen item dict after state is cleaned up.
        """
        def _wrapped_selected(item: dict) -> None:
            self._inventory_panel.stop_give_mode()
            self._active = RightPanel.ACTIONS
            on_selected(item)

        def _wrapped_cancel() -> None:
            self._inventory_panel.stop_give_mode()
            self._active = RightPanel.ACTIONS

        self._inventory_panel.start_give_mode(_wrapped_selected, _wrapped_cancel)
        self._active = RightPanel.PLAYER_INVENTORY

    def handle_inventory_event(self, event: pygame.event.Event) -> None:
        """Forward an event to the inventory panel (give-mode click detection)."""
        self._inventory_panel.handle_event(event)

    def handle_actions_event(self, event: pygame.event.Event) -> None:
        """Forward an event to the actions panel (for button and scroll detection)."""
        self._actions_panel.handle_event(event)

    @property
    def show_inventory_panel(self) -> bool:
        """True when the PLAYER_INVENTORY tab is the active view."""
        return self._active == RightPanel.PLAYER_INVENTORY

    @property
    def show_actions_panel(self) -> bool:
        """True when the ACTIONS tab is the active view."""
        return self._active == RightPanel.ACTIONS

    @property
    def show_inspect_panel(self) -> bool:
        """True when the INSPECT tab is the active view."""
        return self._active == RightPanel.INSPECT

    def set_inspect_data(self, npc_id: str, data: dict) -> None:
        """Push fetched NPC data into the inspect panel and switch to INSPECT tab."""
        self._inspect_panel.set_data(npc_id, data)
        self._active = RightPanel.INSPECT

    def clear_inspect(self) -> None:
        """Clear the inspect panel (called on fetch error)."""
        self._inspect_panel.clear()

    def set_world_engines(self, engines: list[dict]) -> None:
        """Push a fresh engine-status list into the WORLD panel."""
        self._world_panel.set_engines(engines)

    def set_world_events(self, events: list[dict]) -> None:
        """Push a fresh event list into the WORLD panel."""
        self._world_panel.set_events(events)

    def set_objective_state(self, state: ObjectiveState) -> None:
        """Push the latest ObjectiveState into the WORLD panel's OBJECTIVE section."""
        self._world_panel.set_objective(state)

    @property
    def show_world_panel(self) -> bool:
        """True when the WORLD tab is active."""
        return self._active == RightPanel.WORLD

    def set_emotion(self, label: str, valence: float, arousal: float) -> None:
        """Push the latest emotion snapshot into the EMOTION panel widget."""
        self._emotion_panel.set_emotion(label, valence, arousal)

    def set_needs(self, needs: list[dict]) -> None:
        """Push a fresh needs list into the NEEDS panel widget."""
        self._needs_panel.set_needs(needs)

    def set_goals(self, goals: list[dict]) -> None:
        """Push a fresh goals list into the GOALS panel widget."""
        self._goals_panel.set_goals(goals)

    def set_politics(self, pledges: list[dict], leverage: list[dict]) -> None:
        """Push fresh pledges + leverage into the POLITICS panel widget."""
        self._politics_panel.set_politics(pledges, leverage)

    def set_memories(self, memories: list[dict]) -> None:
        """Push a fresh memories list into the MEMORY panel widget."""
        self._memory_panel.set_memories(memories)

    def set_retrieval_payload(self, payload: dict | None) -> None:
        """Push a fresh retrieval-debug payload into the RETRIEVAL panel widget.

        Args:
            payload: Parsed DebugRetrievalResponse dict, or None to clear.
        """
        self._retrieval_panel.set_payload(payload)

    @property
    def show_retrieval_panel(self) -> bool:
        """True when the RETRIEVAL tab is active."""
        return self._active == RightPanel.RETRIEVAL

    def set_faction_standings(self, standings: list[dict] | None) -> None:
        """Push fresh faction standing data into the FACTION panel widget.

        Args:
            standings: List of dicts from EngineClient.get_faction_standings(),
                       or None to clear.
        """
        self._faction_board.set_standings(standings)

    @property
    def show_faction_board(self) -> bool:
        """True when the FACTION tab is active."""
        return self._active == RightPanel.FACTION

    def set_player_model(self, model: dict | None) -> None:
        """Push a fresh player-model snapshot into the PLAYER MODEL panel widget.

        Args:
            model: Dict with perceived_trust/perceived_intent, or None to clear.
        """
        self._player_model_panel.set_model(model)

    @property
    def show_player_model_panel(self) -> bool:
        """True when the PLAYER MODEL tab is active."""
        return self._active == RightPanel.PLAYER_MODEL

    def set_consolidate_memory_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Consolidate Memory] is clicked."""
        self._actions_panel.set_consolidate_memory_callback(cb)

    def set_spread_rumor_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Spread Rumor] is clicked."""
        self._actions_panel.set_spread_rumor_callback(cb)

    def set_correct_rumor_callback(self, cb: Callable[[], None]) -> None:
        """Register the callback fired when [Correct Rumor] is clicked."""
        self._actions_panel.set_correct_rumor_callback(cb)

    @property
    def show_memory_panel(self) -> bool:
        """True when the MEMORY tab is active."""
        return self._active == RightPanel.MEMORY

    @property
    def show_emotion_panel(self) -> bool:
        """True when the EMOTION tab is active."""
        return self._active == RightPanel.EMOTION

    @property
    def show_needs_panel(self) -> bool:
        """True when the NEEDS tab is active."""
        return self._active == RightPanel.NEEDS

    @property
    def show_goals_panel(self) -> bool:
        """True when the GOALS tab is active."""
        return self._active == RightPanel.GOALS

    @property
    def show_politics_panel(self) -> bool:
        """True when the POLITICS tab is active."""
        return self._active == RightPanel.POLITICS

    def handle_scroll(self, event: pygame.event.Event) -> None:
        """Route MOUSEWHEEL events to the active scrollable widget."""
        if self._active == RightPanel.KNOWLEDGE:
            self._sidebar.handle_event(event)
        elif self._active == RightPanel.ACTIONS:
            self._actions_panel.handle_event(event)
        elif self._active == RightPanel.INSPECT:
            self._inspect_panel.handle_event(event)
        elif self._active == RightPanel.WORLD:
            self._world_panel.handle_event(event)

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
        elif self._active == RightPanel.ACTIONS:
            self._actions_panel.draw(screen, content_rect)
        elif self._active == RightPanel.INSPECT:
            self._inspect_panel.draw(screen, content_rect)
        elif self._active == RightPanel.WORLD:
            self._world_panel.draw(screen, content_rect)
        elif self._active == RightPanel.EMOTION:
            self._emotion_panel.draw(screen, content_rect)
        elif self._active == RightPanel.NEEDS:
            self._needs_panel.draw(screen, content_rect)
        elif self._active == RightPanel.GOALS:
            self._goals_panel.draw(screen, content_rect)
        elif self._active == RightPanel.POLITICS:
            self._politics_panel.draw(screen, content_rect)
        elif self._active == RightPanel.MEMORY:
            self._memory_panel.draw(screen, content_rect)
        elif self._active == RightPanel.RETRIEVAL:
            self._retrieval_panel.draw(screen, content_rect)
        elif self._active == RightPanel.FACTION:
            self._faction_board.draw(screen, content_rect)
        elif self._active == RightPanel.PLAYER_MODEL:
            self._player_model_panel.draw(screen, content_rect)
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
