"""
Module: renderer
Layer: demo_game.graph_panel
Purpose: Render a GraphSnapshot to a new pygame Surface using networkx layout
         and a matplotlib FigureCanvasAgg (off-screen). Returns the Surface;
         does not paint onto an existing one (see decisions.md).
Dependencies: networkx, matplotlib, pygame (all installed via requirements.txt)
Used by: demo_game.graph_panel.poller
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib
import matplotlib.pyplot as plt
import networkx as nx
import pygame

matplotlib.use("Agg")

from matplotlib.backends.backend_agg import FigureCanvasAgg  # noqa: E402

if TYPE_CHECKING:
    from demo_game.graph_panel.fetcher import GraphSnapshot

# ---------------------------------------------------------------------------
# Visual constants
# ---------------------------------------------------------------------------

_NODE_COLORS: dict[str, str] = {
    "Character": "#4472C4",
    "Faction": "#E74C3C",
    "Event": "#FF8C00",
    "Location": "#27AE60",
    "world_state": "#9B59B6",
    "Belief": "#F1C40F",
    "Goal": "#E67E22",
}
_DEFAULT_NODE_COLOR = "#888888"

_INNER_LIFE_TYPES = frozenset({"Belief", "Goal"})
_INNER_LIFE_SIZE = 200
_MAIN_NODE_SIZE = 500

_COLOR_EDGE_NORMAL = "#666688"
_COLOR_EDGE_HIGHLIGHTED = "#FFD700"
_COLOR_EDGE_BELIEVES = "#B8860B"
_COLOR_EDGE_PURSUES = "#CC7722"

_FIG_BG = "#12121A"
_FONT_COLOR = "white"
_MAX_LABEL_LEN = 14

_DPI = 100


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


def render_snapshot(
    snapshot: GraphSnapshot,
    width: int,
    height: int,
    *,
    highlighted_edges: frozenset[tuple[str, str, str]] = frozenset(),
) -> pygame.Surface:
    """Render a GraphSnapshot to a new pygame Surface.

    Builds a directed graph with networkx, applies Kamada-Kawai layout (spring
    fallback for disconnected graphs), renders via matplotlib FigureCanvasAgg,
    and converts the RGBA buffer to a pygame Surface scaled to (width, height).

    Node colors are fixed by type. Edge thickness reflects relationship weight
    where a numeric field is available. Highlighted edges are drawn yellow.
    KNOWS_ABOUT edges are drawn dashed. BELIEVES/PURSUES are dotted.

    Args:
        snapshot: Current graph snapshot to render.
        width: Target surface width in pixels.
        height: Target surface height in pixels.
        highlighted_edges: Set of (src_id, dst_id, edge_type) keys to highlight.

    Returns:
        New pygame.Surface of size (width, height) ready to blit.
    """
    fig_w = width / _DPI
    fig_h = height / _DPI

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=_DPI)
    ax.set_facecolor(_FIG_BG)
    fig.patch.set_facecolor(_FIG_BG)
    ax.axis("off")

    if not snapshot.nodes:
        ax.text(
            0.5, 0.5, "No graph data",
            transform=ax.transAxes,
            ha="center", va="center",
            color=_FONT_COLOR, fontsize=10,
        )
        return _fig_to_surface(fig, width, height)

    G = _build_digraph(snapshot)
    pos = _compute_layout(G)

    _draw_edges(ax, G, pos, highlighted_edges)
    _draw_nodes(ax, G, pos)
    _draw_labels(ax, G, pos)

    return _fig_to_surface(fig, width, height)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_digraph(snapshot: GraphSnapshot) -> nx.DiGraph:
    """Build a networkx DiGraph from a snapshot."""
    G: nx.DiGraph = nx.DiGraph()
    for node in snapshot.nodes:
        label = node.properties.get("name", node.id)
        G.add_node(node.id, node_type=node.node_type, label=str(label))

    for edge in snapshot.edges:
        if G.has_node(edge.src_id) and G.has_node(edge.dst_id):
            G.add_edge(
                edge.src_id,
                edge.dst_id,
                edge_type=edge.edge_type,
                props=edge.properties,
            )
    return G


def _compute_layout(G: nx.DiGraph) -> dict:
    """Return node positions using Kamada-Kawai; fall back to spring if disconnected."""
    if len(G.nodes) == 0:
        return {}
    try:
        return nx.kamada_kawai_layout(G.to_undirected())
    except Exception:
        return nx.spring_layout(G, seed=42)


def _edge_width(props: dict, edge_type: str) -> float:
    """Derive line width from edge properties; default 1.0."""
    weight = None
    if edge_type == "RELATES_TO":
        weight = props.get("trust")
    elif edge_type == "STANDS_WITH":
        weight = props.get("standing")
        if weight is not None:
            weight = max(0, weight)
    elif edge_type == "OPPOSES":
        weight = props.get("intensity")

    if weight is None:
        return 1.0
    try:
        return max(0.5, min(3.0, 1.0 + float(weight) / 100.0 * 2.0))
    except (TypeError, ValueError):
        return 1.0


def _draw_edges(
    ax: object,
    G: nx.DiGraph,
    pos: dict,
    highlighted_edges: frozenset[tuple[str, str, str]],
) -> None:
    """Draw all edges grouped by style."""
    for u, v, data in G.edges(data=True):
        etype = data.get("edge_type", "")
        props = data.get("props", {})
        key = (u, v, etype)

        if key in highlighted_edges:
            color = _COLOR_EDGE_HIGHLIGHTED
        elif etype == "BELIEVES":
            color = _COLOR_EDGE_BELIEVES
        elif etype == "PURSUES":
            color = _COLOR_EDGE_PURSUES
        else:
            color = _COLOR_EDGE_NORMAL

        style = "dashed" if etype == "KNOWS_ABOUT" else (
            "dotted" if etype in ("BELIEVES", "PURSUES") else "solid"
        )
        lw = _edge_width(props, etype)

        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)],
            edge_color=color, style=style, width=lw,
            arrows=True, arrowsize=10,
            connectionstyle="arc3,rad=0.05",
            ax=ax,
        )


def _draw_nodes(ax: object, G: nx.DiGraph, pos: dict) -> None:
    """Draw nodes grouped by type with type-specific colors and sizes."""
    all_types = set(nx.get_node_attributes(G, "node_type").values())
    for node_type in all_types:
        nodelist = [n for n, d in G.nodes(data=True) if d.get("node_type") == node_type]
        if not nodelist:
            continue
        color = _NODE_COLORS.get(node_type, _DEFAULT_NODE_COLOR)
        size = _INNER_LIFE_SIZE if node_type in _INNER_LIFE_TYPES else _MAIN_NODE_SIZE
        nx.draw_networkx_nodes(
            G, pos, nodelist=nodelist,
            node_color=color, node_size=size, ax=ax,
        )


def _draw_labels(ax: object, G: nx.DiGraph, pos: dict) -> None:
    """Draw truncated labels on all nodes."""
    labels = {}
    for n, data in G.nodes(data=True):
        raw = data.get("label", n)
        labels[n] = raw[:_MAX_LABEL_LEN] + "…" if len(raw) > _MAX_LABEL_LEN else raw
    nx.draw_networkx_labels(G, pos, labels, font_size=6, font_color=_FONT_COLOR, ax=ax)


def _fig_to_surface(fig: object, width: int, height: int) -> pygame.Surface:
    """Convert a matplotlib figure to a pygame Surface scaled to (width, height)."""
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    buf = canvas.buffer_rgba()
    raw_w, raw_h = canvas.get_width_height()
    surface = pygame.image.frombuffer(bytes(buf), (raw_w, raw_h), "RGBA")
    plt.close(fig)
    if (raw_w, raw_h) != (width, height):
        surface = pygame.transform.scale(surface, (width, height))
    return surface
