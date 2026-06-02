"""
Module: inspect_panel
Layer: demo_game.ui
Purpose: Scrollable NPC data card for the INSPECT right-panel tab. Renders
         character properties, faction standings, current location, items,
         known events, goals, beliefs, and emotion — all fetched from the
         NPC Engine graph.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.right_panel
"""

from __future__ import annotations

import pygame

from demo_game.constants import PALETTE

# Layout constants.
_PAD = 8
_ROW_H = 18
_SECTION_GAP = 10
_HEADER_H = 28

# Colours.
_CLR_BG = PALETTE["bg"]
_CLR_HEADER_BG = (22, 22, 32)
_CLR_HEADER_TEXT = PALETTE["amber"]
_CLR_LABEL = (140, 140, 160)
_CLR_VALUE = (220, 220, 220)
_CLR_SECTION = (100, 120, 180)
_CLR_DIM = (80, 80, 100)
_CLR_DIVIDER = (50, 50, 70)

_NO_NPC_MSG = "Select an NPC, then click [Inspect]"


class InspectPanelWidget:
    """Scrollable NPC data card shown in the INSPECT tab.

    Renders a structured view of the NPC's graph state: character properties,
    faction standings, location, items, known events, goals, beliefs, and emotion.

    Args:
        font: Body font for values.
        label_font: Smaller font for field labels and section headers.
    """

    def __init__(self, font: pygame.font.Font, label_font: pygame.font.Font) -> None:
        self._font = font
        self._label_font = label_font
        self._npc_id: str = ""
        self._data: dict = {}
        self._scroll_y: int = 0
        self._content_h: int = 0

    def set_data(self, npc_id: str, data: dict) -> None:
        """Replace displayed data and reset scroll to top.

        Args:
            npc_id: NPC character ID used in the header.
            data: Aggregated inspect dict (see game_controller._inspect_worker).
        """
        self._npc_id = npc_id
        self._data = data
        self._scroll_y = 0

    def clear(self) -> None:
        """Clear all data (called on fetch error or deselection)."""
        self._npc_id = ""
        self._data = {}
        self._scroll_y = 0

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle MOUSEWHEEL scroll events.

        Args:
            event: A pygame event (only MOUSEWHEEL is acted on).
        """
        if event.type == pygame.MOUSEWHEEL:
            max_scroll = max(0, self._content_h - _ROW_H * 4)
            self._scroll_y = max(0, min(self._scroll_y - event.y * 20, max_scroll))

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the NPC data card inside rect.

        Args:
            surface: Target pygame surface.
            rect: Content area rect (below the tab header strip).
        """
        pygame.draw.rect(surface, _CLR_BG, rect)
        if not self._npc_id:
            self._draw_empty(surface, rect)
            return
        self._draw_header(surface, rect)
        content_rect = pygame.Rect(rect.x, rect.y + _HEADER_H, rect.width, rect.height - _HEADER_H)
        rows = self._build_rows()
        self._content_h = len(rows) * (_ROW_H + 2)
        clip = surface.subsurface(content_rect)
        clip.fill(_CLR_BG)
        y = _PAD - self._scroll_y
        for row in rows:
            self._draw_row(clip, row, content_rect.width, y)
            y += _ROW_H + 2

    def _draw_empty(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        msg = self._font.render(_NO_NPC_MSG, True, _CLR_DIM)
        surface.blit(msg, (rect.centerx - msg.get_width() // 2, rect.centery - msg.get_height() // 2))

    def _draw_header(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        hdr = pygame.Rect(rect.x, rect.y, rect.width, _HEADER_H)
        pygame.draw.rect(surface, _CLR_HEADER_BG, hdr)
        char = self._data.get("character") or {}
        name = char.get("name") or self._npc_id
        archetype = char.get("archetype") or ""
        label = f"{name}  [{archetype}]" if archetype else name
        txt = self._font.render(label, True, _CLR_HEADER_TEXT)
        surface.blit(txt, (rect.x + _PAD, hdr.centery - txt.get_height() // 2))

    def _draw_row(
        self,
        clip: pygame.Surface,
        row: tuple[str, str, str],
        width: int,
        y: int,
    ) -> None:
        kind, label, value = row
        if kind == "section":
            pygame.draw.line(clip, _CLR_DIVIDER, (_PAD, y + _ROW_H // 2), (width - _PAD, y + _ROW_H // 2))
            txt = self._label_font.render(f"  {label}  ", True, _CLR_SECTION)
            clip.blit(txt, (_PAD * 2, y))
        elif kind == "field":
            lbl = self._label_font.render(label + ":", True, _CLR_LABEL)
            val = self._font.render(value, True, _CLR_VALUE)
            clip.blit(lbl, (_PAD, y))
            clip.blit(val, (_PAD + lbl.get_width() + 4, y))
        elif kind == "item":
            val = self._font.render("  • " + value, True, _CLR_VALUE)
            clip.blit(val, (_PAD, y))

    def _build_rows(self) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = []
        char = self._data.get("character") or {}

        rows += self._section_rows("CHARACTER", [
            ("Archetype", char.get("archetype") or "—"),
            ("Traits", _join(char.get("personality_traits"))),
            ("Location", char.get("location_id") or "—"),
            ("Voice", _truncate(char.get("voice_descriptor") or "", 50)),
            ("Emotion", self._emotion_label()),
            ("Currency", str(char.get("currency_balance") or 0)),
        ])

        factions = self._data.get("factions") or []
        if factions:
            rows.append(("section", "FACTION STANDINGS", ""))
            for f in factions:
                faction_id = f.get("faction_id") or "?"
                standing = f.get("standing")
                rows.append(("item", "", f"{faction_id}  standing={standing}"))

        items = self._data.get("items") or []
        if items:
            rows.append(("section", "ITEMS", ""))
            for it in items:
                name = it.get("name") or it.get("id") or "?"
                itype = it.get("type") or ""
                val = it.get("value")
                desc = f"{name}  [{itype}]  value={val}" if itype else name
                rows.append(("item", "", desc))

        events = self._data.get("events") or []
        if events:
            rows.append(("section", "KNOWN EVENTS", ""))
            for ev in events:
                ev_id = ev.get("id") or ev.get("event_id") or "?"
                rows.append(("item", "", ev_id))

        goals = self._data.get("goals") or []
        if goals:
            rows.append(("section", "GOALS", ""))
            for g in goals:
                desc = _truncate(g.get("description") or "", 60)
                urgency = g.get("urgency")
                rows.append(("item", "", f"[u={urgency}] {desc}"))

        beliefs = self._data.get("beliefs") or []
        if beliefs:
            rows.append(("section", "BELIEFS", ""))
            for b in beliefs:
                content = _truncate(b.get("content") or "", 60)
                conf = b.get("confidence")
                rows.append(("item", "", f"[c={conf}] {content}"))

        relations = self._data.get("relations") or []
        if relations:
            rows.append(("section", "GRAPH EDGES", ""))
            for r in relations:
                rtype = r.get("type") or r.get("relation_type") or "?"
                target = r.get("target_id") or r.get("other_id") or "?"
                rows.append(("item", "", f"{rtype} → {target}"))

        return rows

    def _section_rows(
        self,
        title: str,
        fields: list[tuple[str, str]],
    ) -> list[tuple[str, str, str]]:
        rows: list[tuple[str, str, str]] = [("section", title, "")]
        rows += [("field", label, value) for label, value in fields]
        return rows

    def _emotion_label(self) -> str:
        em = self._data.get("emotion") or {}
        if not em:
            return "—"
        label = em.get("label") or "?"
        valence = em.get("valence")
        return f"{label}  (v={valence})" if valence is not None else label


def _join(value: object) -> str:
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) if value else "—"
    return str(value) if value else "—"


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
