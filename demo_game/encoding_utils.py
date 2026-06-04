"""
Module: encoding_utils
Layer: demo_game (external client)
Purpose: Ensure stdout and stderr are configured for UTF-8 output so that
         non-ASCII content (NPC dialogue, em-dashes, Unicode symbols) does not
         cause UnicodeEncodeError on cp1252 Windows consoles.
Dependencies: sys (stdlib only — no src/ imports)
Used by: demo_game.run (main entry point), e2e/scenarios/conftest.py
"""

from __future__ import annotations

import sys


def ensure_utf8_stdout() -> None:
    """Reconfigure stdout and stderr to UTF-8, idempotently.

    Safe on any Python version and stream type:
    - If the stream already reports ``encoding == 'utf-8'`` the call is skipped.
    - If the stream lacks a ``reconfigure`` method (e.g. older io wrappers,
      StringIO) the call is silently skipped — no crash.

    This function is a pure side-effectful helper; it returns None and has no
    observable output of its own.
    """
    _reconfigure_stream_if_needed(sys.stdout)
    _reconfigure_stream_if_needed(sys.stderr)


def _reconfigure_stream_if_needed(stream: object) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    current_encoding: str = getattr(stream, "encoding", "") or ""
    if current_encoding.lower().replace("-", "") == "utf8":
        return
    reconfigure(encoding="utf-8")
