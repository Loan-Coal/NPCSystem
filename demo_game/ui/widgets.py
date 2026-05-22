"""
Module: widgets
Layer: demo_game.ui
Purpose: Reusable Pygame UI widgets — InputBox, ScrollableLog, NpcListWidget,
         DegradationBadge. No game-logic, no HTTP, no engine imports.
Dependencies: pygame
Used by: demo_game.ui.game_window
"""

from __future__ import annotations

import pygame

# ---------------------------------------------------------------------------
# Colour palette (shared across widgets)
# ---------------------------------------------------------------------------
_CLR_BG = (18, 18, 24)
_CLR_PANEL = (28, 28, 36)
_CLR_INPUT_BG = (38, 38, 50)
_CLR_INPUT_ACTIVE = (55, 55, 75)
_CLR_TEXT = (220, 220, 220)
_CLR_DIM = (130, 130, 140)
_CLR_HIGHLIGHT = (80, 100, 160)
_CLR_PLAYER_LABEL = (120, 160, 255)
_CLR_NPC_LABEL = (200, 160, 80)
_CLR_ERROR_LABEL = (220, 80, 80)
_CLR_CURSOR = (180, 180, 220)


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
        self._scroll_offset = 0  # lines scrolled up from bottom (0 = bottom)

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
        self._scroll_offset = 0  # snap to bottom on new message

    def handle_event(self, event: pygame.event.Event) -> None:
        """Handle scroll-wheel events."""
        if event.type == pygame.MOUSEWHEEL:
            self._scroll_offset = max(0, self._scroll_offset - event.y)

    def clear(self) -> None:
        """Remove all messages and reset scroll."""
        self._messages.clear()
        self._scroll_offset = 0

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the log onto ``surface`` at ``rect``."""
        pygame.draw.rect(surface, _CLR_PANEL, rect, border_radius=4)
        clip = surface.subsurface(rect)
        clip.fill(_CLR_PANEL)

        line_h = self._font.get_linesize()
        label_h = self._label_font.get_linesize()
        entry_h = label_h + line_h + 6  # label + body + padding

        total_h = len(self._messages) * entry_h
        bottom_y = max(total_h, rect.height)
        start_y = bottom_y - self._scroll_offset * entry_h - rect.height

        for i, (label, body, colour) in enumerate(self._messages):
            y = i * entry_h - start_y
            if y + entry_h < 0 or y > rect.height:
                continue
            lbl_surf = self._label_font.render(label, True, colour)
            clip.blit(lbl_surf, (8, y))
            body_surf = self._font.render(body, True, _CLR_TEXT)
            clip.blit(body_surf, (8, y + label_h))


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
        """Render the NPC list onto ``surface`` at ``rect``."""
        self._rect = rect
        pygame.draw.rect(surface, _CLR_PANEL, rect, border_radius=4)
        for i, npc_id in enumerate(self._npc_ids):
            row = pygame.Rect(rect.x, rect.y + i * self._row_h, rect.width, self._row_h)
            if npc_id == self._active_id:
                pygame.draw.rect(surface, _CLR_HIGHLIGHT, row, border_radius=3)
            label = self._display_names.get(npc_id, npc_id)
            txt = self._font.render(label, True, _CLR_TEXT)
            surface.blit(txt, (row.x + 10, row.centery - txt.get_height() // 2))

    @property
    def active_id(self) -> str | None:
        """Currently selected NPC ID."""
        return self._active_id


class DegradationBadge:
    """Coloured pill showing degradation level and optional emotion text.

    Args:
        font: Font used for the label text.
    """

    def __init__(self, font: pygame.font.Font) -> None:
        self._font = font
        self._level: str = ""
        self._emotion: str | None = None
        self._color: tuple[int, int, int] = (80, 80, 80)

    def set(self, level: str, emotion: str | None, color: tuple[int, int, int]) -> None:
        """Update badge state.

        Args:
            level: Degradation level string (e.g. ``"full"``).
            emotion: Emotion/mood string, or None.
            color: RGB badge background colour.
        """
        self._level = level.upper().replace("_", " ")
        self._emotion = emotion
        self._color = color

    def draw(self, surface: pygame.Surface, rect: pygame.Rect) -> None:
        """Render the badge onto ``surface`` at ``rect``."""
        pygame.draw.rect(surface, self._color, rect, border_radius=6)
        label = self._level or "—"
        if self._emotion:
            label += f"  ·  {self._emotion}"
        txt = self._font.render(label, True, (255, 255, 255))
        surface.blit(txt, (rect.x + 8, rect.centery - txt.get_height() // 2))
