"""
test_ollama_keep_alive_setting.py - The shipped model-residency window, and the values
Ollama's duration parser would silently reject.

Why this exists: nothing sent keep_alive before this setting, so Ollama's 5-minute default
evicted the model between play sessions. A cold load was measured at 10.3s against a
3.49-4.18s warm structured turn, so an eviction roughly triples the turn a player waits on.
A malformed value does not fail loudly -- the backend drops the field and the model is back
on the 5-minute timer with nothing in the logs -- so the value is validated at load.

Does NOT: construct an adapter, call a backend, or read the real environment.

Dependencies injected: None.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from npc_engine.config import Settings


def _base_settings() -> dict:
    return {
        "API_KEY_SECRET": "npc_dev_secret_2026_alpha",
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "password",
    }


def test_keep_alive_defaults_to_thirty_minutes() -> None:
    """The shipped default spans a play session without pinning VRAM overnight."""
    assert Settings(**_base_settings()).OLLAMA_KEEP_ALIVE == "30m"


def test_keep_alive_accepts_a_negative_duration_meaning_forever() -> None:
    """Ollama reads a negative duration as 'never unload'."""
    settings = Settings(**{**_base_settings(), "OLLAMA_KEEP_ALIVE": "-1m"})

    assert settings.OLLAMA_KEEP_ALIVE == "-1m"


@pytest.mark.parametrize("value", ["30s", "90s", "1h", "500ms", "1.5h"])
def test_keep_alive_accepts_go_duration_units(value: str) -> None:
    """Every unit Go's time.ParseDuration understands is allowed."""
    assert Settings(**{**_base_settings(), "OLLAMA_KEEP_ALIVE": value}).OLLAMA_KEEP_ALIVE == value


def test_keep_alive_rejects_a_bare_number() -> None:
    """A unitless value is not a Go duration; the backend would drop it."""
    with pytest.raises(ValidationError):
        Settings(**{**_base_settings(), "OLLAMA_KEEP_ALIVE": "30"})


def test_keep_alive_rejects_an_english_duration() -> None:
    """'30 minutes' is the obvious typo and is not a duration."""
    with pytest.raises(ValidationError):
        Settings(**{**_base_settings(), "OLLAMA_KEEP_ALIVE": "30 minutes"})


def test_keep_alive_rejects_a_day_unit_go_does_not_have() -> None:
    """The non-obvious one: Go has no day unit, so '30d' fails to parse."""
    with pytest.raises(ValidationError):
        Settings(**{**_base_settings(), "OLLAMA_KEEP_ALIVE": "30d"})


def test_keep_alive_rejects_an_empty_value() -> None:
    """An empty string would leave residency to the backend default, silently."""
    with pytest.raises(ValidationError):
        Settings(**{**_base_settings(), "OLLAMA_KEEP_ALIVE": "   "})
