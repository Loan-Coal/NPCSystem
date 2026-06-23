"""
conftest.py - Shared fixtures and helpers for story/E2E scenario tests.

Provides:
- http_client fixture (session-scoped)
- Narrator class: prints a human-readable story log while recording a transcript
- char_props / loc_props helpers to satisfy required schema fields

UTF-8 note: stdout/stderr are reconfigured to UTF-8 at import time so that
scenario output does not raise UnicodeEncodeError on cp1252 Windows consoles (SEV-41).
"""

from __future__ import annotations

import json
import os
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest


# ---------------------------------------------------------------------------
# UTF-8 stdout enforcement (SEV-41) — inline copy, pure stdlib, no src/ import
# ---------------------------------------------------------------------------

def _reconfigure_if_needed(stream: object) -> None:
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is None:
        return
    current: str = getattr(stream, "encoding", "") or ""
    if current.lower().replace("-", "") == "utf8":
        return
    reconfigure(encoding="utf-8")


_reconfigure_if_needed(sys.stdout)
_reconfigure_if_needed(sys.stderr)


# Phrases emitted by the canned/fallback paths — any dialogue response matching
# one of these indicates the LLM was never reached.
CANNED_PHRASES: frozenset[str] = frozenset({
    "I need a moment to think.",
    "Let us continue this shortly.",
    "I am not ready to answer that yet.",
    "Hmm, let me think on that. Come back later.",
    "I am distracted right now. Ask me again soon.",
    "Give me a moment to gather my thoughts.",
    "Move along, citizen.",
    "I am on duty. Keep moving.",
    "Not now. We can talk later.",
    "Patience, child. Return at dusk.",
    "The answer is not simple. Let me think.",
    "Come back when the bells ring.",
})

BASE_URL_ENV = "NPC_BASE_URL"

def api_post(client: httpx.Client, path: str, payload: dict) -> dict:
    """POST helper with graceful non-JSON fallback."""
    resp = client.post(path, json=payload)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return {"url": str(resp.url), "status": resp.status_code, "body": body}


def api_get(client: httpx.Client, path: str) -> dict:
    """GET helper with graceful non-JSON fallback."""
    resp = client.get(path)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return {"url": str(resp.url), "status": resp.status_code, "body": body}


def api_put(client: httpx.Client, path: str, payload: dict) -> dict:
    """PUT helper with graceful non-JSON fallback."""
    resp = client.put(path, json=payload)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return {"url": str(resp.url), "status": resp.status_code, "body": body}


def api_patch(client: httpx.Client, path: str, payload: dict) -> dict:
    """PATCH helper with graceful non-JSON fallback."""
    resp = client.patch(path, json=payload)
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return {"url": str(resp.url), "status": resp.status_code, "body": body}


API_KEY_ENV = "NPC_API_KEY"
DEFAULT_BASE_URL = "http://localhost:8000"
TRANSCRIPTS_DIR = Path(__file__).resolve().parents[2] / "transcripts"

_WIDTH = 64


# ---------------------------------------------------------------------------
# Story logger
# ---------------------------------------------------------------------------


class Narrator:
    """Prints a human-readable story log while recording an API-call transcript."""

    def __init__(self, scenario_id: str) -> None:
        self.scenario_id = scenario_id
        self._lines: list[str] = [
            f"# Transcript: {scenario_id}",
            f"_Generated {datetime.now(timezone.utc).isoformat()}_",
            "",
        ]
        self._canned_failures: list[str] = []
        title = scenario_id.replace("_", " ").title()
        print(f"\n{'═' * _WIDTH}")
        print(f"  {title}")
        print(f"{'═' * _WIDTH}\n")

    def step(self, label: str, call: dict) -> dict:
        """Log one API call: print a summary line and append full JSON to transcript."""
        status = call.get("status", "?")
        body = call.get("body") or {}
        ok = isinstance(status, int) and 200 <= status < 300
        sym = "✓" if ok else "✗"
        pad = max(1, 50 - len(label))
        print(f"  {sym} {label} {'.' * pad} {status}")

        # For dialogue responses print NPC reply prominently
        npc_text = body.get("npc_response") if isinstance(body, dict) else None
        if npc_text:
            wrapped = textwrap.fill(
                npc_text.strip(),
                width=_WIDTH - 8,
                initial_indent="        ",
                subsequent_indent="        ",
            )
            print(wrapped[:600])

            degradation = body.get("degradation_level") if isinstance(body, dict) else None
            is_canned = degradation == "canned" or npc_text.strip() in CANNED_PHRASES
            if is_canned:
                self._canned_failures.append(
                    f"[{label}] degradation_level={degradation!r} response={npc_text!r}"
                )
                print(f"  ! CANNED RESPONSE DETECTED (degradation_level={degradation!r})")

        # For NPC emotion state
        if isinstance(body, dict) and body.get("label"):
            print(f"        mood: {body['label']}  "
                  f"(valence={body.get('valence', '?')}, arousal={body.get('arousal', '?')})")

        self._lines += [f"## {label}", f"```json\n{json.dumps(call, indent=2)}\n```", ""]
        return call

    def assert_no_canned(self) -> None:
        """Fail the test if any dialogue step returned a canned/fallback response."""
        if self._canned_failures:
            failures = "\n  ".join(self._canned_failures)
            raise AssertionError(
                f"{len(self._canned_failures)} canned response(s) detected — LLM was not reached:\n  {failures}"
            )

    def narrate(self, text: str) -> None:
        """Print a story context line between steps."""
        print(f"\n  > {text}\n")
        self._lines += [f"> _{text}_", ""]

    def save(self, suffix: str = "", *, assert_llm_reached: bool = True) -> Path:
        """Write the full JSON transcript to file and print its path.

        Raises AssertionError after saving if any canned responses were detected
        and assert_llm_reached is True (the default).
        """
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = TRANSCRIPTS_DIR / f"{self.scenario_id}{suffix}_{ts}.md"
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(self._lines), encoding="utf-8")
        print(f"\n{'─' * _WIDTH}")
        print(f"  transcript → {path.name}")
        print(f"{'─' * _WIDTH}\n")
        if assert_llm_reached:
            self.assert_no_canned()
        return path


# ---------------------------------------------------------------------------
# Schema helpers — supply required fields the type registry enforces
# ---------------------------------------------------------------------------


def char_props(
    char_id: str,
    name: str,
    *,
    is_player: bool,
    archetype: str = "adventurer",
    biography: str = "A test character.",
    gossipy: int = 50,
    credulity: int = 50,
    honesty: int = 50,
    now: str | None = None,
) -> dict[str, Any]:
    """Return a Character properties dict with all required fields populated."""
    ts = now or datetime.now(timezone.utc).isoformat()
    return {
        "id": char_id,
        "name": name,
        "archetype": archetype,
        "biography": biography,
        "is_player": is_player,
        "is_active": True,
        "created_at": ts,
        "updated_at": ts,
        "last_graph_updated_at": ts,
        "gossipy": gossipy,
        "credulity": credulity,
        "honesty": honesty,
    }


def loc_props(
    loc_id: str,
    name: str,
    *,
    location_tag: str = "plaza",
    region: str = "Central",
    descriptor: str = "A test location.",
    now: str | None = None,
) -> dict[str, Any]:
    """Return a Location properties dict with all required fields populated."""
    ts = now or datetime.now(timezone.utc).isoformat()
    return {
        "id": loc_id,
        "name": name,
        "location_tag": location_tag,
        "region": region,
        "descriptor": descriptor,
        "last_graph_updated_at": ts,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def pytest_addoption(parser):
    parser.addoption("--scenarios-only", action="store_true", default=False)


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--scenarios-only", default=False):
        skip = pytest.mark.skip(reason="scenario tests require --scenarios-only flag")
        for item in items:
            if "scenarios" in str(item.fspath):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL)


@pytest.fixture(scope="session")
def api_key() -> str:
    return os.environ.get(API_KEY_ENV, "local_dev_secret_change_this_2026")


@pytest.fixture(scope="session")
def http_client(base_url: str, api_key: str) -> httpx.Client:
    with httpx.Client(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=90.0,
    ) as client:
        yield client


@pytest.fixture(autouse=True, scope="session")
def ensure_transcripts_dir():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture
def clean_world(http_client: httpx.Client):
    """Reset world_state to the age_of_peace baseline and ensure the player node.

    Reusable clean-state guard (evals/preconditions.prepare). The session-scoped
    http_client already has base_url baked in, so base_url="" yields relative paths.
    Tests that need a non-default epoch (e.g. war) set it AFTER requesting this fixture.
    """
    from preconditions import Preconditions, WorldBaseline, prepare

    prepare(
        http_client,
        "",
        baseline=WorldBaseline(),
        pre=Preconditions(player_id="player_demo"),
    )
