"""
Module: widgets
Layer: demo_game.ui
Purpose: Reusable Pygame UI widgets — InputBox, ScrollableLog, NpcListWidget,
         DegradationBadge. No game-logic, no HTTP, no engine imports.
Dependencies: pygame, demo_game.constants
Used by: demo_game.ui.game_window

300-line exception: all widgets share colour constants and the _MockFont test
pattern; splitting would require a shared _widget_colours module with no
cohesion benefit. See DECISIONS.md DEC-029 for rationale.
"""

from __future__ import annotations

import time

import pygame

from demo_game.constants import FACTION_COLOURS, NPC_FACTIONS, PALETTE

# Emotion label colours used in DegradationBadge.
_CLR_EMOTION_GREEN = (80, 200, 80)
_CLR_EMOTION_AMBER = (200, 160, 80)
_CLR_EMOTION_RED   = (200, 80, 80)

# UI palette aliases — values from constants.PALETTE, names kept for minimal diff.
_CLR_BG          = PALETTE["bg"]
_CLR_PANEL       = PALETTE["panel"]
_CLR_TEXT        = PALETTE["white"]
_CLR_DIM         = PALETTE["grey"]
_CLR_NPC_LABEL   = PALETTE["amber"]

# Widget-specific colours with no direct palette equivalent.
_CLR_INPUT_BG     = (38, 38, 50)
_CLR_INPUT_ACTIVE = (55, 55, 75)
_CLR_HIGHLIGHT    = (80, 100, 160)
_CLR_PLAYER_LABEL = (120, 160, 255)
_CLR_ERROR_LABEL  = (220, 80, 80)
_CLR_CURSOR       = (180, 180, 220)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _emotion_colour(valence: float) -> tuple[int, int, int]:
    """Return an RGB colour for an emotion valence value.

    Args:
        valence: Emotion valence in [-1.0, 1.0]. Positive = positive emotion.

    Returns:
        Green for valence > 0.3, red for valence < -0.3, amber otherwise.
    """
    if valence > 0.3:
        return _CLR_EMOTION_GREEN
    if valence < -0.3:
        return _CLR_EMOTION_RED
    return _CLR_EMOTION_AMBER


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------


def _wrap_text(font: pygame.font.Font, text: str, max_width: int) -> list[str]:
    """Split text into lines that each fit within max_width pixels.

    Args:
        font: Pygame font used to measure text width.
        text: The text to wrap.
        max_width: Maximum line width in pixels.

    Returns:
        List of line strings. Always has at least one element.
    """
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if font.size(candidate)[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines if lines else [""]


class InputBox:
    """Single-line text input widget with cursor blink and Enter detection.

    Args:
        font: Pygame font used to render input text.
        placeholder: Greyed-out hint shown when the box is empty and idle.
    """

    CURSOR_BLINK_MS = 530

    def __init__(self, font: pygame.font.Font, placeholder: str = "Type a message…") -> None:
        self._font = font
        self._placeholder = placeholder
        self._text = ""
        self._cursor_visible = True
        self._last_blink = pygame.time.get_ticks()
        self.disabled = False  # set True while waiting for LLM response

    # ------------------------------------------------------------------
    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Process one Pygame event.

        Returns:
            Submitted text string if Enter was pressed (and box not disabled),
            None otherwise.
        """
        if self.disabled:
            return None
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_RETURN:
                submitted = self._text.strip()
                if submitted:
                    self._text = ""
                    return submitted
            elif event.key == pygame.K_BACKSPACE:
                self._text = self._text[:-1]
            else:
                ch = event.unicode
                if ch and ch.isprintable():
                    self._text += ch
        return None

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the input box onto ``surface`` at ``rect``."""
        now = pygame.time.get_ticks()
        if now - self._last_blink >= self.CURSOR_BLINK_MS:
            self._cursor_visible = not self._cursor_visible
            self._last_blink = now

        bg = _CLR_INPUT_ACTIVE if not self.disabled else _CLR_INPUT_BG
        pygame.draw.rect(surface, bg, rect, border_radius=4)
        pygame.draw.rect(surface, _CLR_DIM, rect, 1, border_radius=4)

        if self.disabled:
            label = self._font.render("Waiting for response…", True, _CLR_DIM)
            surface.blit(label, (rect.x + 8, rect.centery - label.get_height() // 2))
            return

        display = self._text if self._text else self._placeholder
        colour = _CLR_TEXT if self._text else _CLR_DIM
        text_surf = self._font.render(display, True, colour)
        surface.blit(text_surf, (rect.x + 8, rect.centery - text_surf.get_height() // 2))

        if self._cursor_visible and self._text:
            cx = rect.x + 8 + text_surf.get_width() + 2
            cy = rect.centery - text_surf.get_height() // 2
            pygame.draw.line(surface, _CLR_CURSOR, (cx, cy), (cx, cy + text_surf.get_height()), 2)

    def set_text(self, text: str) -> None:
        """Pre-fill the input box without submitting."""
        self._text = text

    @property
    def text(self) -> str:
        """Current text in the input box."""
        return self._text


class ScrollableLog:
    """Scrollable message log with alternating player/NPC label colours.

    Args:
        font: Pygame font for message body text.
        label_font: Smaller font used for the sender label.
        max_messages: Maximum number of messages kept in memory.
    """

    def __init__(
        self,
        font: pygame.font.Font,
        label_font: pygame.font.Font,
        max_messages: int = 200,
    ) -> None:
        self._font = font
        self._label_font = label_font
        self._max = max_messages
        self._messages: list[tuple[str, str, tuple[int, int, int]]] = []  # (label, body, colour)
        self._scroll_px: int = 0  # pixels scrolled up from bottom (0 = bottom)

    def add_message(self, label: str, body: str, *, is_player: bool = False, is_error: bool = False) -> None:
        """Append a message to the log and scroll to bottom.

        Args:
            label: Sender name shown above the message.
            body: Message body text.
            is_player: If True, uses player label colour.
            is_error: If True, uses error label colour.
        """
        if is_error:
            colour = _CLR_ERROR_LABEL
        elif is_player:
            colour = _CLR_PLAYER_LABEL
        else:
            colour = _CLR_NPC_LABEL
        self._messages.append((label, body, colour))
        if len(self._messages) > self._max:
            self._messages.pop(0)
        self._scroll_px = 0  # snap to bottom on new message

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle scroll-wheel events."""
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_px = max(0, self._scroll_px + event.y * self._font.get_linesize())

    def clear(self) -> None:
        """Remove all messages and reset scroll."""
        self._messages.clear()
        self._scroll_px = 0

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the log onto ``surface`` at ``rect``, wrapping long lines.

        Each message is prefixed with ``[LABEL]:`` in the sender colour.
        An amber 1px border frames the entire log area.
        """
        pygame.draw.rect(surface, _CLR_PANEL, rect, border_radius=4)
        clip = surface.subsurface(rect)
        clip.fill(_CLR_PANEL)

        line_h = self._font.get_linesize()
        label_h = self._label_font.get_linesize()
        max_w = rect.width - 16

        # Pre-compute wrapped lines per message (O(n) per frame; negligible at 30 FPS)
        entries: list[tuple[str, list[str], tuple[int, int, int]]] = [
            (label, _wrap_text(self._font, body, max_w), colour)
            for label, body, colour in self._messages
        ]

        total_h = sum(label_h + len(lines) * line_h + 6 for _, lines, _ in entries)
        max_scroll = max(0, total_h - rect.height)
        scroll_px = min(self._scroll_px, max_scroll)
        viewport_top = max(total_h, rect.height) - scroll_px - rect.height

        content_y = 0
        for label, lines, colour in entries:
            entry_h = label_h + len(lines) * line_h + 6
            rel_y = content_y - viewport_top
            if rel_y + entry_h >= 0 and rel_y < rect.height:
                lbl_surf = self._label_font.render(f"[{label}]:", True, colour)
                clip.blit(lbl_surf, (8, rel_y))
                for i, line in enumerate(lines):
                    line_surf = self._font.render(line, True, _CLR_TEXT)
                    clip.blit(line_surf, (8, rel_y + label_h + i * line_h))
            content_y += entry_h

        # Amber 1px border drawn last so it sits on top of any content overflow.
        pygame.draw.rect(surface, PALETTE["amber"], rect, 1)


class NpcListWidget:
    """Clickable list of NPC names with active-row highlight.

    Args:
        font: Font used to render NPC names.
        row_height: Pixel height of each row.
    """

    def __init__(self, font: pygame.font.Font, row_height: int = 36) -> None:
        self._font = font
        self._row_h = row_height
        self._npc_ids: list[str] = []
        self._display_names: dict[str, str] = {}
        self._active_id: str | None = None
        self._rect = pygame.Rect(0, 0, 0, 0)

    def set_npcs(self, npc_ids: list[str], display_names: dict[str, str], active_id: str | None = None) -> None:
        """Replace the NPC list.

        Args:
            npc_ids: Ordered list of NPC IDs.
            display_names: Map of npc_id → display name.
            active_id: Initially selected NPC ID.
        """
        self._npc_ids = npc_ids
        self._display_names = display_names
        self._active_id = active_id or (npc_ids[0] if npc_ids else None)

    def handle_event(self, event: pygame.event.Event) -> str | None:
        """Return the clicked NPC ID, or None if no NPC was clicked.

        Args:
            event: Pygame event to inspect.

        Returns:
            NPC ID string if a row was clicked, None otherwise.
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            mx, my = event.pos
            if self._rect.collidepoint(mx, my):
                rel_y = my - self._rect.y
                idx = rel_y // self._row_h
                if 0 <= idx < len(self._npc_ids):
                    clicked = self._npc_ids[idx]
                    self._active_id = clicked
                    return clicked
        return None

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the NPC list onto ``surface`` at ``rect``.

        Each row shows an 8px faction-coloured dot at x+8, an amber ▶ prefix on
        the selected row, then the NPC name.
        """
        self._rect = rect
        pygame.draw.rect(surface, _CLR_PANEL, rect, border_radius=4)
        for i, npc_id in enumerate(self._npc_ids):
            row = pygame.Rect(rect.x, rect.y + i * self._row_h, rect.width, self._row_h)
            is_active = npc_id == self._active_id
            if is_active:
                pygame.draw.rect(surface, _CLR_HIGHLIGHT, row, border_radius=3)
            faction = NPC_FACTIONS.get(npc_id, "neutral")
            dot_clr = FACTION_COLOURS.get(faction, (96, 96, 96))
            pygame.draw.circle(surface, dot_clr, (row.x + 8, row.centery), 4)
            text_x = row.x + 20
            if is_active:
                arrow = self._font.render("▶", True, PALETTE["amber"])
                surface.blit(arrow, (text_x, row.centery - arrow.get_height() // 2))
                text_x += arrow.get_width() + 4
            label = self._display_names.get(npc_id, npc_id)
            txt = self._font.render(label, True, _CLR_TEXT)
            surface.blit(txt, (text_x, row.centery - txt.get_height() // 2))

    @property
    def active_id(self) -> str | None:
        """Currently selected NPC ID."""
        return self._active_id


class DegradationBadge:
    """Coloured pill showing degradation tier and live emotion label.

    The degradation tier and background colour are set from dialogue responses
    via ``set()``. The live emotion label and valence are set from the
    EmotionPoller via ``set_emotion()`` and rendered in a valence-matched colour.

    Args:
        font: Font used for the label text.
    """

    def __init__(self, font: pygame.font.Font) -> None:
        self._font = font
        self._level: str = ""
        self._color: tuple[int, int, int] = (80, 80, 80)
        self._emotion_label: str = ""
        self._emotion_valence: float = 0.0

    def set(self, level: str, emotion: str | None, color: tuple[int, int, int]) -> None:
        """Update degradation tier and badge background colour from a dialogue response.

        Args:
            level: Degradation level string (e.g. ``"full"``).
            emotion: Ignored — live emotion comes from ``set_emotion()``.
            color: RGB badge background colour.
        """
        self._level = level.upper().replace("_", " ")
        self._color = color

    def set_emotion(self, label: str, valence: float) -> None:
        """Update the live emotion label from the EmotionPoller.

        Args:
            label: Emotion label string (e.g. ``"happy"``).
            valence: Emotion valence in [-1.0, 1.0].
        """
        self._emotion_label = label
        self._emotion_valence = valence

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the badge onto ``surface`` at ``rect``.

        Tier text is drawn in white. The emotion label is drawn in a
        valence-matched colour: green (>0.3), amber (neutral), red (<-0.3).
        """
        pygame.draw.rect(surface, self._color, rect, border_radius=6)
        x = rect.x + 8
        cy = rect.centery

        tier_surf = self._font.render(self._level or "—", True, (255, 255, 255))
        surface.blit(tier_surf, (x, cy - tier_surf.get_height() // 2))

        if self._emotion_label:
            x += tier_surf.get_width()
            sep_surf = self._font.render("  ·  ", True, (180, 180, 180))
            surface.blit(sep_surf, (x, cy - sep_surf.get_height() // 2))
            x += sep_surf.get_width()
            emo_clr = _emotion_colour(self._emotion_valence)
            emo_surf = self._font.render(self._emotion_label, True, emo_clr)
            surface.blit(emo_surf, (x, cy - emo_surf.get_height() // 2))


# ---------------------------------------------------------------------------
# EventBanner
# ---------------------------------------------------------------------------

_BANNER_H = 36


class EventBanner:
    """2-second flash banner for world event notifications.

    Renders a full-width 36px strip at the bottom of the given rect,
    amber text on PALETTE["red"] background. No-op when not active.

    Args:
        font: Font used to render the event label.
    """

    def __init__(self, font: pygame.font.Font) -> None:
        self._font = font
        self._label: str = ""
        self._until: float = 0.0

    def show(self, label: str, duration_s: float = 2.0) -> None:
        """Activate the banner with the given label for duration_s seconds.

        Args:
            label: Event description to display.
            duration_s: How long the banner stays visible. Defaults to 2.0 s.
        """
        self._label = label
        self._until = time.monotonic() + duration_s

    def is_active(self) -> bool:
        """Return True if the banner is currently visible."""
        return time.monotonic() < self._until

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Draw the banner strip at the bottom of rect if active; no-op otherwise.

        Args:
            surface: Target pygame surface.
            rect: Bounding rect of the panel that owns this banner.
        """
        if not self.is_active():
            return
        banner_rect = pygame.Rect(rect.x, rect.bottom - _BANNER_H, rect.width, _BANNER_H)
        pygame.draw.rect(surface, PALETTE["red"], banner_rect)
        text_surf = self._font.render(self._label, True, PALETTE["amber"])
        cy = banner_rect.centery
        surface.blit(text_surf, (banner_rect.x + 8, cy - text_surf.get_height() // 2))
