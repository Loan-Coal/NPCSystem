"""
Module: start_menu
Layer: demo_game.ui
Purpose: Pygame splash/start-menu screen presented before the game window.
         Keyboard-navigable (1-4 keys or arrow keys + Enter); Escape/Q quits.
Dependencies: pygame, demo_game.arc_choice
Used by: demo_game.__main__
"""

from __future__ import annotations

import sys

import pygame

from demo_game.arc_choice import ArcChoice

# --- Layout constants ----------------------------------------------------------

_TITLE_FONT_SIZE = 54
_ITEM_FONT_SIZE = 36
_SUBTITLE_FONT_SIZE = 22
_ITEM_PADDING = 16
_HIGHLIGHT_RADIUS = 8

# Palette — intentionally self-contained; no import from demo_game.constants
_COLOUR_BG = (18, 18, 28)
_COLOUR_TITLE = (220, 200, 255)
_COLOUR_ITEM = (180, 180, 200)
_COLOUR_HIGHLIGHT_BG = (60, 40, 100)
_COLOUR_HIGHLIGHT_TEXT = (255, 240, 100)
_COLOUR_SUBTITLE = (120, 120, 140)
_COLOUR_KEY_BADGE = (80, 60, 120)
_COLOUR_KEY_TEXT = (200, 180, 255)

# Menu option definitions: (display_number, ArcChoice, label, sublabel)
_MENU_OPTIONS: list[tuple[str, ArcChoice, str, str]] = [
    ("1", ArcChoice.MUNICH, "Munich Demo Arc", "Scripted 5-min sales scenario"),
    ("2", ArcChoice.VILLAGE, "Village Crisis", "Siege & faction eval world"),
    ("3", ArcChoice.TAVERN, "Tavern Intrigue", "Thieves-guild negotiation world"),
    ("4", ArcChoice.FREE_PLAY, "Free Play", "Interactive sandbox window"),
]

_TITLE_TEXT = "NPC Engine"
_SUBTITLE_TEXT = "Select a demo arc to begin"
_QUIT_HINT = "Q / Escape  —  quit"

# Key → index mapping for 1-4 shortcuts
_KEY_TO_INDEX: dict[int, int] = {
    pygame.K_1: 0,
    pygame.K_2: 1,
    pygame.K_3: 2,
    pygame.K_4: 3,
}


class StartMenu:
    """Pygame start-menu rendered in a full-window surface before the game loop.

    Usage::

        choice = StartMenu().show(window_w=1280, window_h=720)

    The ``show`` method blocks until the user makes a selection or quits.
    """

    def show(self, window_w: int, window_h: int) -> ArcChoice:
        """Display the menu and return the chosen ArcChoice.

        Blocks until a valid selection is made.  Quits the process on
        Escape / Q or window-close event.

        Args:
            window_w: Width of the pygame window to create.
            window_h: Height of the pygame window to create.
        Returns:
            The ArcChoice value selected by the user.
        """
        pygame.init()
        surface = pygame.display.set_mode((window_w, window_h))
        pygame.display.set_caption(_TITLE_TEXT)
        clock = pygame.time.Clock()

        selected_index = 0
        title_font = pygame.font.Font(None, _TITLE_FONT_SIZE)
        item_font = pygame.font.Font(None, _ITEM_FONT_SIZE)
        sub_font = pygame.font.Font(None, _SUBTITLE_FONT_SIZE)

        while True:
            for event in pygame.event.get():
                selected_index, choice = _handle_event(event, selected_index)
                if choice is not None:
                    return choice

            _render_frame(
                surface=surface,
                window_w=window_w,
                window_h=window_h,
                selected_index=selected_index,
                title_font=title_font,
                item_font=item_font,
                sub_font=sub_font,
            )
            pygame.display.flip()
            clock.tick(30)


# --- Private helpers -----------------------------------------------------------


def _handle_event(
    event: pygame.event.Event,
    selected_index: int,
) -> tuple[int, ArcChoice | None]:
    """Process a single pygame event and return (new_index, choice_or_None).

    Args:
        event: The pygame event to process.
        selected_index: Current highlighted menu index (0-3).
    Returns:
        Tuple of (updated_index, ArcChoice or None if no selection yet).
    """
    if event.type == pygame.QUIT:
        sys.exit(0)

    if event.type != pygame.KEYDOWN:
        return selected_index, None

    if event.key in (pygame.K_ESCAPE, pygame.K_q):
        sys.exit(0)

    if event.key in _KEY_TO_INDEX:
        return selected_index, _MENU_OPTIONS[_KEY_TO_INDEX[event.key]][1]

    if event.key == pygame.K_RETURN:
        return selected_index, _MENU_OPTIONS[selected_index][1]

    if event.key == pygame.K_UP:
        return (selected_index - 1) % len(_MENU_OPTIONS), None

    if event.key == pygame.K_DOWN:
        return (selected_index + 1) % len(_MENU_OPTIONS), None

    return selected_index, None


def _render_frame(
    surface: pygame.Surface,
    window_w: int,
    window_h: int,
    selected_index: int,
    title_font: pygame.font.Font,
    item_font: pygame.font.Font,
    sub_font: pygame.font.Font,
) -> None:
    """Draw one frame of the start menu onto ``surface``.

    Args:
        surface: The pygame surface to draw onto.
        window_w: Surface width in pixels.
        window_h: Surface height in pixels.
        selected_index: Currently highlighted option index.
        title_font: Font used for the title heading.
        item_font: Font used for menu item labels.
        sub_font: Font used for sublabels and hints.
    """
    surface.fill(_COLOUR_BG)
    cx = window_w // 2

    title_surf = title_font.render(_TITLE_TEXT, True, _COLOUR_TITLE)
    surface.blit(title_surf, title_surf.get_rect(centerx=cx, top=window_h // 8))

    sub_surf = sub_font.render(_SUBTITLE_TEXT, True, _COLOUR_SUBTITLE)
    surface.blit(sub_surf, sub_surf.get_rect(centerx=cx, top=window_h // 8 + 70))

    _render_menu_items(
        surface=surface,
        window_w=window_w,
        window_h=window_h,
        selected_index=selected_index,
        item_font=item_font,
        sub_font=sub_font,
    )

    quit_surf = sub_font.render(_QUIT_HINT, True, _COLOUR_SUBTITLE)
    surface.blit(quit_surf, quit_surf.get_rect(centerx=cx, bottom=window_h - 24))


def _render_menu_items(
    surface: pygame.Surface,
    window_w: int,
    window_h: int,
    selected_index: int,
    item_font: pygame.font.Font,
    sub_font: pygame.font.Font,
) -> None:
    """Draw the four arc-choice rows onto ``surface``.

    Args:
        surface: Pygame surface to draw onto.
        window_w: Surface width in pixels.
        window_h: Surface height in pixels.
        selected_index: Index of the highlighted option.
        item_font: Font for the option label.
        sub_font: Font for the option sublabel.
    """
    row_height = 80
    total_height = row_height * len(_MENU_OPTIONS)
    start_y = (window_h - total_height) // 2

    for idx, (key_str, _arc, label, sublabel) in enumerate(_MENU_OPTIONS):
        row_y = start_y + idx * row_height
        is_selected = idx == selected_index

        _render_single_item(
            surface=surface,
            window_w=window_w,
            row_y=row_y,
            row_height=row_height,
            key_str=key_str,
            label=label,
            sublabel=sublabel,
            is_selected=is_selected,
            item_font=item_font,
            sub_font=sub_font,
        )


def _render_single_item(
    surface: pygame.Surface,
    window_w: int,
    row_y: int,
    row_height: int,
    key_str: str,
    label: str,
    sublabel: str,
    is_selected: bool,
    item_font: pygame.font.Font,
    sub_font: pygame.font.Font,
) -> None:
    """Draw a single menu row with optional highlight.

    Args:
        surface: Pygame surface to draw onto.
        window_w: Surface width used to centre and size the row.
        row_y: Top y-coordinate for this row.
        row_height: Pixel height of the row.
        key_str: Keyboard shortcut label (e.g. "1").
        label: Primary text for the arc option.
        sublabel: Secondary description text.
        is_selected: Whether this row is currently highlighted.
        item_font: Font for the primary label.
        sub_font: Font for the sublabel.
    """
    item_w = int(window_w * 0.55)
    item_x = (window_w - item_w) // 2

    if is_selected:
        bg_rect = pygame.Rect(item_x, row_y + 4, item_w, row_height - 8)
        pygame.draw.rect(surface, _COLOUR_HIGHLIGHT_BG, bg_rect, border_radius=_HIGHLIGHT_RADIUS)

    badge_rect = pygame.Rect(item_x + _ITEM_PADDING, row_y + row_height // 2 - 16, 32, 32)
    pygame.draw.rect(surface, _COLOUR_KEY_BADGE, badge_rect, border_radius=4)
    key_surf = sub_font.render(key_str, True, _COLOUR_KEY_TEXT)
    surface.blit(key_surf, key_surf.get_rect(center=badge_rect.center))

    text_x = item_x + _ITEM_PADDING + 48
    text_colour = _COLOUR_HIGHLIGHT_TEXT if is_selected else _COLOUR_ITEM

    label_surf = item_font.render(label, True, text_colour)
    surface.blit(label_surf, (text_x, row_y + _ITEM_PADDING))

    sub_surf = sub_font.render(sublabel, True, _COLOUR_SUBTITLE)
    surface.blit(sub_surf, (text_x, row_y + _ITEM_PADDING + 36))
