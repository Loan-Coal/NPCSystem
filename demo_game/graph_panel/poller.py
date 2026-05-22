"""
Module: poller
Layer: demo_game.graph_panel
Purpose: Background daemon thread that polls the engine on a fixed interval,
         renders the graph to a pygame Surface, and exposes the latest surface
         via a thread-safe get_surface() call.
         Extracted from game_window.py to keep that module under 300 lines
         (see decisions.md — GraphPoller extraction).
Dependencies: threading, demo_game.graph_panel.fetcher, demo_game.graph_panel.renderer,
              demo_game.client, demo_game.config
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime
from typing import TYPE_CHECKING

import pygame

from demo_game.graph_panel.fetcher import (
    GraphDelta,
    GraphSnapshot,
    compute_delta,
    fetch_snapshot,
)
from demo_game.graph_panel.renderer import render_snapshot

if TYPE_CHECKING:
    from demo_game.client import EngineClient
    from demo_game.config import DemoConfig


class GraphPoller:
    """Background daemon thread that periodically fetches and renders the graph.

    Polls the engine every cfg.DEMO_GRAPH_POLL_INTERVAL seconds. After each
    successful fetch the rendered pygame Surface is stored thread-safely and
    returned on each call to get_surface().

    Delta highlights: edges that appear in a new poll's GraphDelta are drawn
    yellow for two consecutive poll cycles, then revert to their normal colour.

    Args:
        client: Initialised EngineClient.
        cfg: Demo runtime configuration.
        panel_width: Width of the right panel in pixels.
        panel_height: Height of the right panel in pixels.
    """

    def __init__(
        self,
        client: EngineClient,
        cfg: DemoConfig,
        panel_width: int,
        panel_height: int,
    ) -> None:
        self._client = client
        self._poll_interval: float = float(cfg.DEMO_GRAPH_POLL_INTERVAL)
        self._panel_width = panel_width
        self._panel_height = panel_height

        self._lock = threading.Lock()
        self._surface: pygame.Surface | None = None
        self._last_updated: str = ""

        self._prev_snapshot: GraphSnapshot | None = None
        # Maps (src_id, dst_id, edge_type) → remaining highlight cycles
        self._highlighted: dict[tuple[str, str, str], int] = {}

        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Launch the background polling daemon thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def get_surface(self) -> tuple[pygame.Surface | None, str]:
        """Return the latest rendered surface and its timestamp string.

        Returns:
            (surface, last_updated) where surface is None until the first fetch
            completes, and last_updated is "HH:MM:SS" or "".
        """
        with self._lock:
            return self._surface, self._last_updated

    # ------------------------------------------------------------------
    # Background thread
    # ------------------------------------------------------------------

    def _run(self) -> None:
        """Main polling loop: immediate first fetch, then interval-based."""
        self._poll_once()
        while not self._stop_event.wait(self._poll_interval):
            self._poll_once()

    def _poll_once(self) -> None:
        """Fetch, compute delta, render, update shared state."""
        try:
            curr = fetch_snapshot(self._client)
            delta = compute_delta(self._prev_snapshot, curr)

            highlighted_set = self._update_highlights(delta)
            surface = render_snapshot(
                curr,
                self._panel_width,
                self._panel_height,
                highlighted_edges=highlighted_set,
            )
            timestamp = datetime.now().strftime("%H:%M:%S")

            self._prev_snapshot = curr
            with self._lock:
                self._surface = surface
                self._last_updated = timestamp
        except Exception as exc:
            print(f"[GraphPoller] poll error: {exc}", file=sys.stderr)

    def _update_highlights(self, delta: GraphDelta) -> frozenset[tuple[str, str, str]]:
        """Decrement countdown for existing highlights; add new delta edges at 2.

        Returns:
            frozenset of (src_id, dst_id, edge_type) keys still in highlight window.
        """
        new_highlighted = {k: v - 1 for k, v in self._highlighted.items() if v > 1}
        for edge in delta.new_edges:
            key = (edge.src_id, edge.dst_id, edge.edge_type)
            new_highlighted[key] = 2
        self._highlighted = new_highlighted
        return frozenset(new_highlighted.keys())
