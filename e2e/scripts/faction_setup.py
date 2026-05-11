"""
faction_setup.py - E2E script that creates a small faction graph and queries it.

Assumption: the stack is already running (docker compose up, or make run).
            Pass --base-url and --api-key to target a non-default endpoint.

Usage:
    python e2e/scripts/faction_setup.py
    python e2e/scripts/faction_setup.py --base-url http://localhost:8000 --api-key mysecret
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


@dataclass
class _Result:
    passed: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)

    def ok(self, name: str) -> None:
        self.passed.append(name)
        print(f"  [PASS] {name}")

    def fail(self, name: str, reason: str) -> None:
        self.failed.append(name)
        print(f"  [FAIL] {name} — {reason}")

    def summary(self) -> int:
        total = len(self.passed) + len(self.failed)
        print(f"\n{len(self.passed)}/{total} checks passed")
        return 1 if self.failed else 0


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _request(
    method: str,
    url: str,
    api_key: str,
    body: dict | None = None,
) -> tuple[int, dict[str, Any]]:
    data = json.dumps(body).encode() if body is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def _post(base: str, path: str, key: str, body: dict) -> tuple[int, dict]:
    return _request("POST", f"{base}{path}", key, body)


def _get(base: str, path: str, key: str) -> tuple[int, dict]:
    return _request("GET", f"{base}{path}", key)


def _put(base: str, path: str, key: str, body: dict) -> tuple[int, dict]:
    return _request("PUT", f"{base}{path}", key, body)


def _delete(base: str, path: str, key: str) -> tuple[int, dict]:
    return _request("DELETE", f"{base}{path}", key)


# ---------------------------------------------------------------------------
# Scenario
# ---------------------------------------------------------------------------


def run(base_url: str, api_key: str) -> int:
    """Run the faction setup scenario and return exit code."""
    r = _Result()
    admin = f"{base_url}/v1/admin"

    # --- Create factions ---
    status, body = _post(admin, "/factions/", api_key, {
        "id": "faction-iron-hand",
        "name": "Iron Hand",
        "archetype": "military",
        "is_active": True,
    })
    if status == 201:
        r.ok("Create faction: Iron Hand")
    else:
        r.fail("Create faction: Iron Hand", f"HTTP {status}")

    status, body = _post(admin, "/factions/", api_key, {
        "id": "faction-silver-tongue",
        "name": "Silver Tongue",
        "archetype": "mercantile",
        "is_active": True,
    })
    if status == 201:
        r.ok("Create faction: Silver Tongue")
    else:
        r.fail("Create faction: Silver Tongue", f"HTTP {status}")

    # --- Set standings (bidirectional, may differ) ---
    status, _ = _put(admin, "/factions/faction-iron-hand/standings/faction-silver-tongue", api_key, {"standing": -40})
    if status == 200:
        r.ok("Set standing Iron Hand -> Silver Tongue (-40)")
    else:
        r.fail("Set standing Iron Hand -> Silver Tongue", f"HTTP {status}")

    status, _ = _put(admin, "/factions/faction-silver-tongue/standings/faction-iron-hand", api_key, {"standing": 10})
    if status == 200:
        r.ok("Set standing Silver Tongue -> Iron Hand (+10)")
    else:
        r.fail("Set standing Silver Tongue -> Iron Hand", f"HTTP {status}")

    # --- List factions ---
    status, body = _get(admin, "/factions/", api_key)
    if status == 200 and body.get("success"):
        ids = {f["id"] for f in body.get("data", [])}
        if "faction-iron-hand" in ids and "faction-silver-tongue" in ids:
            r.ok("List factions includes both created factions")
        else:
            r.fail("List factions", f"Expected both faction ids, got: {ids}")
    else:
        r.fail("List factions", f"HTTP {status}")

    # --- Get single faction ---
    status, body = _get(admin, "/factions/faction-iron-hand", api_key)
    if status == 200 and body.get("data", {}).get("name") == "Iron Hand":
        r.ok("Get faction by ID: Iron Hand")
    else:
        r.fail("Get faction by ID", f"HTTP {status} body={body}")

    # --- List standings ---
    status, body = _get(admin, "/factions/faction-iron-hand/standings", api_key)
    if status == 200 and body.get("success"):
        standings = body.get("data", [])
        if standings and standings[0].get("standing") == -40:
            r.ok("List standings for Iron Hand (standing=-40 toward Silver Tongue)")
        else:
            r.fail("List standings", f"Unexpected data: {standings}")
    else:
        r.fail("List standings", f"HTTP {status}")

    return r.summary()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Faction E2E setup script")
    parser.add_argument("--base-url", default="http://localhost:8000", help="API base URL")
    parser.add_argument("--api-key", default="local_dev_secret_change_this_2026", help="Bearer API key")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    sys.exit(run(base_url=args.base_url, api_key=args.api_key))
