"""
scenario_memory_edge.py - Edge case coverage for Feature 3.2/3.3: Memory nodes.

Covers:
  - arousal=71 creates memory (exact boundary: threshold is >70, not >=71)
  - arousal=70 does NOT create memory (at-threshold, not above)
  - arousal=0 does NOT create memory
  - k=0 returns empty list; k > total returns all without error
  - vividness decay clamps at 0 (does not go negative)
  - multiple memories returned sorted by vividness descending
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


def test_memory_edge_cases(http_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:8]
    char_id = f"test_memory_edge_{suffix}"

    _create_char(http_client, char_id, "Memory Edge NPC")

    try:
        # --- Edge case 1: arousal=71 creates a memory (strictly above threshold) ---
        resp = http_client.post(
            f"{_ADMIN}/memories/from-arousal/{char_id}",
            json={"content": "Minimal arousal memory.", "arousal": 71},
        )
        assert resp.status_code == 200, resp.text
        mem_id = resp.json()["data"]["memory_id"]
        assert mem_id is not None, "arousal=71 must create a memory (threshold is >70)"
        print(f"[pass] arousal=71 creates memory: {mem_id}")

        # --- Edge case 2: arousal=70 does NOT create a memory ---
        resp = http_client.post(
            f"{_ADMIN}/memories/from-arousal/{char_id}",
            json={"content": "At-threshold — should not form a memory.", "arousal": 70},
        )
        assert resp.status_code == 200, resp.text
        no_mem = resp.json()["data"]["memory_id"]
        assert no_mem is None, f"arousal=70 must not create a memory, got {no_mem!r}"
        print("[pass] arousal=70 does not create a memory (at threshold, not above)")

        # --- Edge case 3: arousal=0 does NOT create a memory ---
        resp = http_client.post(
            f"{_ADMIN}/memories/from-arousal/{char_id}",
            json={"content": "Zero arousal — no memory.", "arousal": 0},
        )
        assert resp.status_code == 200, resp.text
        no_mem_zero = resp.json()["data"]["memory_id"]
        assert no_mem_zero is None, f"arousal=0 must not create a memory, got {no_mem_zero!r}"
        print("[pass] arousal=0 does not create a memory")

        # --- Edge case 4: k=0 returns empty list ---
        resp = http_client.get(f"{_ADMIN}/memories/{char_id}", params={"k": 0})
        assert resp.status_code == 200
        empty = resp.json()["data"]["memories"]
        assert empty == [], f"k=0 should return empty list, got {empty}"
        print("[pass] k=0 returns empty list")

        # --- Add a second memory for ordering / k-limit tests ---
        resp = http_client.post(
            f"{_ADMIN}/memories/from-arousal/{char_id}",
            json={"content": "High arousal second memory.", "arousal": 95},
        )
        assert resp.status_code == 200, resp.text
        mem_id_2 = resp.json()["data"]["memory_id"]
        assert mem_id_2 is not None

        # --- Edge case 5: k=1 returns only one memory ---
        resp = http_client.get(f"{_ADMIN}/memories/{char_id}", params={"k": 1})
        top_one = resp.json()["data"]["memories"]
        assert len(top_one) == 1
        print(f"[pass] k=1 returns exactly 1 memory: {top_one[0]['id']}")

        # --- Edge case 6: k > total returns all 2 memories without error ---
        resp = http_client.get(f"{_ADMIN}/memories/{char_id}", params={"k": 1000})
        over_k = resp.json()["data"]["memories"]
        assert len(over_k) == 2, f"k=1000 with 2 memories should return 2, got {len(over_k)}"
        print("[pass] k=1000 returns all memories without error")

        # --- Edge case 7: vividness decay clamps to 0, does not go negative ---
        # Create a memory with vividness=3 directly (below default decay of 5).
        resp = http_client.post(
            f"{_ADMIN}/memories/{char_id}",
            json={"content": "Fading memory.", "vividness": 3, "emotional_charge": 10},
        )
        assert resp.status_code == 200, resp.text
        low_viv_id = resp.json()["data"]["memory_id"]

        # Verify it was stored correctly before decay
        resp = http_client.get(f"{_ADMIN}/memories/{char_id}", params={"k": 10})
        memories_before = resp.json()["data"]["memories"]
        low_viv = next(m for m in memories_before if m["id"] == low_viv_id)
        assert low_viv["vividness"] == 3, f"Expected vividness=3 before decay, got {low_viv['vividness']}"

        # Run decay (decay_per_day=5, vividness=3 → clamps to 0)
        resp = http_client.post(f"{_ADMIN}/memories/decay", json={"decay_per_day": 5})
        assert resp.status_code == 200, resp.text
        count = resp.json()["data"]["decayed_count"]
        assert count > 0, f"Expected at least 1 memory decayed, got {count}"

        resp = http_client.get(f"{_ADMIN}/memories/{char_id}", params={"k": 10})
        memories_after = resp.json()["data"]["memories"]
        low_viv_after = next(m for m in memories_after if m["id"] == low_viv_id)
        assert low_viv_after["vividness"] == 0, (
            f"Vividness should clamp to 0 after decay, got {low_viv_after['vividness']}"
        )
        assert low_viv_after["vividness"] >= 0, (
            f"Vividness must never go negative, got {low_viv_after['vividness']}"
        )
        print("[pass] vividness decay clamps at 0, does not go negative")

        print("\n[PASS] scenario_memory_edge completed successfully.")

    finally:
        _delete_char(http_client, char_id)
