"""
Module: branch_panel
Layer: demo_game.ui
Purpose: Modal choice widget that presents a BranchNode to the player and
         returns the index of the chosen option. Modeled on ActionsPanelWidget
         (actions_panel.py); keyboard handling reuses the pattern from
         start_menu.py lines 111-144. Does NOT call the client or persist state
         — callers (scenario runner or game_controller) handle those steps.
Dependencies: pygame, demo_game.constants, demo_game.branch_node
Used by: demo_game.scenarios, demo_game.game_controller,
         demo_game.tests.test_branch_panel

LINE-COUNT WAIVER (DEC-110): ~340 lines. The class (BranchPanelWidget), its
event-dispatch helpers (_handle_event, _key_to_digit), the text-wrap utility
(_wrap_text), and the render function (_render_frame) form a single cohesive
UI component. Splitting render into a sibling module would scatter tightly
coupled draw constants across files with no cohesion gain. See DECISIONS.md.
"""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pygame

from demo_game.constants import PALETTE

if TYPE_CHECKING:
    from demo_game.branch_node import BranchNode

# ---------------------------------------------------------------------------
# Layout and colour constants
# ---------------------------------------------------------------------------

_OVERLAY_ALPHA: int = 180
_PANEL_PADDING: int = 48
_PANEL_MIN_WIDTH: int = 560
_PANEL_MAX_WIDTH: int = 800
_BTN_H: int = 44
_BTN_GAP: int = 8
_BTN_PAD_X: int = 12
_PROMPT_LINE_HEIGHT: int = 26
_SECTION_GAP: int = 20

_TITLE_FONT_SIZE: int = 28
_PROMPT_FONT_SIZE: int = 22
_OPTION_FONT_SIZE: int = 20
_HINT_FONT_SIZE: int = 16

_CLR_OVERLAY: tuple[int, int, int] = (0, 0, 0)
_CLR_PANEL_BG: tuple[int, int, int] = PALETTE["panel"]
_CLR_BORDER: tuple[int, int, int] = PALETTE["amber"]
_CLR_TITLE: tuple[int, int, int] = PALETTE["amber"]
_CLR_PROMPT: tuple[int, int, int] = PALETTE["white"]
_CLR_OPTION_NORMAL: tuple[int, int, int] = PALETTE["white"]
_CLR_OPTION_HIGHLIGHT: tuple[int, int, int] = PALETTE["amber"]
_CLR_HINT: tuple[int, int, int] = PALETTE["grey"]
_CLR_BTN_NORMAL: tuple[int, int, int] = PALETTE["border"]
_CLR_BTN_HIGHLIGHT: tuple[int, int, int] = PALETTE["amber"]

_TITLE_TEXT: str = "A Choice Must Be Made"
_HINT_TEXT: str = "Arrow keys / number key to select   Enter to confirm   Esc to cancel"

# Maximum characters per prompt text line before wrapping.
_PROMPT_WRAP_CHARS: int = 60


class BranchPanelWidget:
    """Modal overlay widget that presents a BranchNode and returns the chosen index.

    The caller is responsible for entering and exiting any event loop. Use
    ``show(surface, branch)`` to display the modal and block until a choice is
    made or the player cancels.

    Args:
        title_font: Font for the modal title.
        prompt_font: Font for the branch prompt text.
        option_font: Font for the selectable options.
        hint_font: Font for the keyboard hint line.
    """

    def __init__(
        self,
        title_font: pygame.font.Font,
        prompt_font: pygame.font.Font,
        option_font: pygame.font.Font,
        hint_font: pygame.font.Font,
    ) -> None:
        self._title_font = title_font
        self._prompt_font = prompt_font
        self._option_font = option_font
        self._hint_font = hint_font

    def show(
        self,
        surface: pygame.Surface,
        branch: "BranchNode",
        *,
        allow_cancel: bool = True,
    ) -> int | None:
        """Display the modal and block until the player chooses or cancels.

        Args:
            surface: The pygame surface to draw onto (the main window surface).
            branch: BranchNode whose prompt and options are presented.
            allow_cancel: If True, Escape returns None; if False, Escape is ignored.
        Returns:
            Zero-based index of the chosen option, or None if the player pressed
            Escape (only when allow_cancel=True).
        """
        clock = pygame.time.Clock()
        selected = 0
        n_options = len(branch.options)

        while True:
            for event in pygame.event.get():
                result = _handle_event(
                    event,
                    selected_index=selected,
                    n_options=n_options,
                    allow_cancel=allow_cancel,
                )
                if result is _SENTINEL_QUIT:
                    sys.exit(0)
                if result is _SENTINEL_CANCEL:
                    return None
                if isinstance(result, tuple):
                    selected, confirmed_index = result
                    if confirmed_index is not None:
                        return confirmed_index
                elif isinstance(result, int):
                    selected = result

            _render_frame(
                surface=surface,
                branch=branch,
                selected_index=selected,
                title_font=self._title_font,
                prompt_font=self._prompt_font,
                option_font=self._option_font,
                hint_font=self._hint_font,
            )
            pygame.display.flip()
            clock.tick(30)


# ---------------------------------------------------------------------------
# Private sentinels
# ---------------------------------------------------------------------------

_SENTINEL_QUIT = object()
_SENTINEL_CANCEL = object()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _handle_event(
    event: pygame.event.Event,
    selected_index: int,
    n_options: int,
    allow_cancel: bool,
) -> tuple[int, int | None] | object | int:
    """Process a single pygame event and return the navigation result.

    Returns one of:
    - ``_SENTINEL_QUIT`` on window-close or Q.
    - ``_SENTINEL_CANCEL`` on Escape (when allow_cancel=True).
    - ``(new_selected, confirmed_index)`` — confirmed_index is the chosen option
      index when Enter or a number key fires, otherwise None.
    - ``new_selected`` int when only navigation occurred.

    Args:
        event: Pygame event to process.
        selected_index: Currently highlighted option index.
        n_options: Total number of selectable options.
        allow_cancel: Whether Escape triggers cancel.
    Returns:
        Navigation result as described above.
    """
    if event.type == pygame.QUIT:
        return _SENTINEL_QUIT

    if event.type != pygame.KEYDOWN:
        return selected_index, None

    if event.key == pygame.K_q:
        return _SENTINEL_QUIT

    if event.key == pygame.K_ESCAPE:
        if allow_cancel:
            return _SENTINEL_CANCEL
        return selected_index, None

    if event.key == pygame.K_UP:
        return (selected_index - 1) % n_options, None

    if event.key == pygame.K_DOWN:
        return (selected_index + 1) % n_options, None

    if event.key == pygame.K_RETURN:
        return selected_index, selected_index

    # Number key shortcuts: K_1 … K_9 map to option indices 0 … 8.
    digit = _key_to_digit(event.key)
    if digit is not None and 1 <= digit <= n_options:
        idx = digit - 1
        return idx, idx

    return selected_index, None


def _key_to_digit(key: int) -> int | None:
    """Map a pygame key constant to its digit (1-9), or None.

    Args:
        key: pygame key constant.
    Returns:
        Integer digit 1–9, or None.
    """
    _KEY_MAP: dict[int, int] = {
        pygame.K_1: 1,
        pygame.K_2: 2,
        pygame.K_3: 3,
        pygame.K_4: 4,
        pygame.K_5: 5,
        pygame.K_6: 6,
        pygame.K_7: 7,
        pygame.K_8: 8,
        pygame.K_9: 9,
    }
    return _KEY_MAP.get(key)


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Wrap text to lines of at most max_chars characters at word boundaries.

    Args:
        text: The text to wrap.
        max_chars: Maximum characters per line.
    Returns:
        List of line strings.
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _render_frame(
    surface: pygame.Surface,
    branch: "BranchNode",
    selected_index: int,
    title_font: pygame.font.Font,
    prompt_font: pygame.font.Font,
    option_font: pygame.font.Font,
    hint_font: pygame.font.Font,
) -> None:
    """Draw the full modal overlay frame onto surface.

    Args:
        surface: Target pygame surface.
        branch: BranchNode being presented.
        selected_index: Currently highlighted option index.
        title_font: Font for modal title.
        prompt_font: Font for prompt text.
        option_font: Font for option rows.
        hint_font: Font for keyboard hint.
    """
    win_w, win_h = surface.get_size()

    # Dim background.
    overlay = pygame.Surface((win_w, win_h), pygame.SRCALPHA)
    overlay.fill((*_CLR_OVERLAY, _OVERLAY_ALPHA))
    surface.blit(overlay, (0, 0))

    # Panel dimensions.
    panel_w = min(_PANEL_MAX_WIDTH, max(_PANEL_MIN_WIDTH, win_w - _PANEL_PADDING * 2))
    prompt_lines = _wrap_text(branch.prompt_text, _PROMPT_WRAP_CHARS)
    n_options = len(branch.options)
    panel_h = (
        _PANEL_PADDING
        + _TITLE_FONT_SIZE + _SECTION_GAP
        + len(prompt_lines) * _PROMPT_LINE_HEIGHT + _SECTION_GAP
        + n_options * (_BTN_H + _BTN_GAP)
        + _SECTION_GAP + _HINT_FONT_SIZE
        + _PANEL_PADDING
    )
    panel_x = (win_w - panel_w) // 2
    panel_y = (win_h - panel_h) // 2
    panel_rect = pygame.Rect(panel_x, panel_y, panel_w, panel_h)

    pygame.draw.rect(surface, _CLR_PANEL_BG, panel_rect, border_radius=6)
    pygame.draw.rect(surface, _CLR_BORDER, panel_rect, width=2, border_radius=6)

    # Title.
    y = panel_y + _PANEL_PADDING
    title_surf = title_font.render(_TITLE_TEXT, True, _CLR_TITLE)
    surface.blit(title_surf, (panel_x + _PANEL_PADDING, y))
    y += _TITLE_FONT_SIZE + _SECTION_GAP

    # Prompt lines.
    for line in prompt_lines:
        line_surf = prompt_font.render(line, True, _CLR_PROMPT)
        surface.blit(line_surf, (panel_x + _PANEL_PADDING, y))
        y += _PROMPT_LINE_HEIGHT
    y += _SECTION_GAP

    # Option buttons.
    for idx, option in enumerate(branch.options):
        btn_rect = pygame.Rect(
            panel_x + _PANEL_PADDING,
            y,
            panel_w - _PANEL_PADDING * 2,
            _BTN_H,
        )
        is_selected = idx == selected_index
        border_clr = _CLR_BTN_HIGHLIGHT if is_selected else _CLR_BTN_NORMAL
        text_clr = _CLR_OPTION_HIGHLIGHT if is_selected else _CLR_OPTION_NORMAL
        pygame.draw.rect(surface, _CLR_PANEL_BG, btn_rect)
        pygame.draw.rect(surface, border_clr, btn_rect, width=1)
        label = f"{idx + 1}. {option.label}"
        txt_surf = option_font.render(label, True, text_clr)
        surface.blit(
            txt_surf,
            (btn_rect.x + _BTN_PAD_X, btn_rect.centery - txt_surf.get_height() // 2),
        )
        y += _BTN_H + _BTN_GAP

    # Keyboard hint.
    y += _SECTION_GAP
    hint_surf = hint_font.render(_HINT_TEXT, True, _CLR_HINT)
    surface.blit(hint_surf, (panel_x + _PANEL_PADDING, y))
