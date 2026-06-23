"""
Tests for OutputModerationService (S16.3).

All pure unit tests — no I/O.
"""
from __future__ import annotations

from npc_engine.services.output_moderation import (
    OutputModerationService,
    build_output_moderation_service,
)

_EVERYONE_BLOCKLIST: frozenset[str] = frozenset({"murder", "gore", "pornography"})


def test_is_over_ceiling_clean_response() -> None:
    svc = OutputModerationService(blocklist=_EVERYONE_BLOCKLIST)
    assert svc.is_over_ceiling("It is a fine evening, traveller.") is False


def test_is_over_ceiling_flags_blocked_term() -> None:
    svc = OutputModerationService(blocklist=_EVERYONE_BLOCKLIST)
    assert svc.is_over_ceiling("There was murder in the village square.") is True


def test_is_over_ceiling_case_insensitive() -> None:
    svc = OutputModerationService(blocklist=_EVERYONE_BLOCKLIST)
    assert svc.is_over_ceiling("Beware the GORE ahead.") is True


def test_mature_rating_never_flags() -> None:
    svc = build_output_moderation_service("mature")
    assert svc.is_over_ceiling("murder gore pornography") is False
