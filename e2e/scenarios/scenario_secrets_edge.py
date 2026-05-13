"""
scenario_secrets_edge.py - Edge case coverage for Feature 3.7: Secret nodes.

Covers:
  - severity=0 and severity=100 stored correctly (boundary values)
  - k=1 returns only highest-severity secret
  - k=0 returns empty list
  - k > total returns all without error
  - multiple secrets sorted by severity descending
"""

from __future__ import annotations

import uuid

import httpx
import pytest

from e2e.scenarios.conftest import char_props

_ADMIN = "/v1/admin"
_GRAPH = "/v1/graph"


def _create_char(client: httpx.Client, char_id: str, name: str) -> None:
    resp = client.post(f"{_GRAPH}/nodes/Character", json={"properties": char_props(char_id, name, is_player=False)})
    assert resp.status_code == 200, f"Character creation failed: {resp.text}"


def _delete_char(client: httpx.Client, char_id: str) -> None:
    client.delete(f"{_ADMIN}/graph/characters/{char_id}")


def test_secrets_edge_cases(http_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:8]
    char_id = f"test_secret_edge_{suffix}"

    _create_char(http_client, char_id, "Secret Edge NPC")

    try:
        # --- Edge case 1: severity=0 (lower bound) stored correctly ---
        resp = http_client.post(
            f"{_ADMIN}/secrets/{char_id}",
            json={"content": "Minor embarrassment.", "severity": 0},
        )
        assert resp.status_code == 200, resp.text
        id_zero = resp.json()["data"]["secret_id"]

        resp = http_client.get(f"{_ADMIN}/secrets/{char_id}", params={"k": 10})
        assert resp.status_code == 200
        secrets = resp.json()["data"]["secrets"]
        zero_secret = next(s for s in secrets if s["id"] == id_zero)
        assert zero_secret["severity"] == 0, f"severity=0 not stored: got {zero_secret['severity']}"
        print("[pass] severity=0 stored correctly")

        # --- Edge case 2: severity=100 (upper bound) stored correctly ---
        resp = http_client.post(
            f"{_ADMIN}/secrets/{char_id}",
            json={"content": "World-ending revelation.", "severity": 100},
        )
        assert resp.status_code == 200, resp.text
        id_hundred = resp.json()["data"]["secret_id"]

        resp = http_client.get(f"{_ADMIN}/secrets/{char_id}", params={"k": 10})
        secrets = resp.json()["data"]["secrets"]
        hundred_secret = next(s for s in secrets if s["id"] == id_hundred)
        assert hundred_secret["severity"] == 100, f"severity=100 not stored: got {hundred_secret['severity']}"
        print("[pass] severity=100 stored correctly")

        # --- Add a mid-severity secret for ordering tests ---
        resp = http_client.post(
            f"{_ADMIN}/secrets/{char_id}",
            json={"content": "Midrange secret.", "severity": 50},
        )
        assert resp.status_code == 200, resp.text

        # --- Edge case 3: secrets sorted descending by severity ---
        resp = http_client.get(f"{_ADMIN}/secrets/{char_id}", params={"k": 10})
        all_secrets = resp.json()["data"]["secrets"]
        severities = [s["severity"] for s in all_secrets]
        assert severities == sorted(severities, reverse=True), (
            f"Secrets not sorted by severity desc: {severities}"
        )
        print("[pass] secrets sorted descending by severity")

        # --- Edge case 4: k=1 returns only the highest-severity secret ---
        resp = http_client.get(f"{_ADMIN}/secrets/{char_id}", params={"k": 1})
        top_one = resp.json()["data"]["secrets"]
        assert len(top_one) == 1
        assert top_one[0]["id"] == id_hundred, (
            f"k=1 should return severity=100 secret, got id={top_one[0]['id']}"
        )
        print("[pass] k=1 returns only highest-severity secret")

        # --- Edge case 5: k=0 returns empty list ---
        resp = http_client.get(f"{_ADMIN}/secrets/{char_id}", params={"k": 0})
        empty = resp.json()["data"]["secrets"]
        assert empty == [], f"k=0 should return empty list, got {empty}"
        print("[pass] k=0 returns empty list")

        # --- Edge case 6: k > total returns all 3 without error ---
        resp = http_client.get(f"{_ADMIN}/secrets/{char_id}", params={"k": 1000})
        over_k = resp.json()["data"]["secrets"]
        assert len(over_k) == 3, f"k=1000 with 3 secrets should return 3, got {len(over_k)}"
        print("[pass] k=1000 returns all secrets without error")

        print("\n[PASS] scenario_secrets_edge completed successfully.")

    finally:
        _delete_char(http_client, char_id)
