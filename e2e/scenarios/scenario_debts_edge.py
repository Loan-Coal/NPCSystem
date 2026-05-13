"""
scenario_debts_edge.py - Edge case coverage for Feature 3.8: Promises and debts.

Covers:
  - all four valid kind values (money, favor, item, service) accepted
  - bidirectional debts: A owes B AND B owes A simultaneously
  - creditor perspective: debts where char is creditor are returned with role='creditor'
  - status transition to defaulted (third valid status)
  - fulfilled debts not returned in pending-only query
  - combined debtor + creditor results in one fetch
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


def test_debts_edge_cases(http_client: httpx.Client) -> None:
    suffix = uuid.uuid4().hex[:8]
    char_a = f"test_debt_edge_a_{suffix}"
    char_b = f"test_debt_edge_b_{suffix}"

    _create_char(http_client, char_a, "Debt Edge A")
    _create_char(http_client, char_b, "Debt Edge B")

    try:
        # --- Edge case 1: all four kind values accepted ---
        for kind in ("money", "item", "service"):
            resp = http_client.post(
                f"{_ADMIN}/debts/{char_a}",
                json={"creditor_id": char_b, "kind": kind, "magnitude": f"some {kind}"},
            )
            assert resp.status_code == 200, f"kind={kind} failed: {resp.text}"

        resp = http_client.get(f"{_ADMIN}/debts/{char_a}")
        assert resp.status_code == 200
        debts_a = resp.json()["data"]["debts"]
        debtor_kinds = {d["kind"] for d in debts_a if d["role"] == "debtor"}
        assert "money" in debtor_kinds, f"kind=money not found: {debtor_kinds}"
        assert "item" in debtor_kinds, f"kind=item not found: {debtor_kinds}"
        assert "service" in debtor_kinds, f"kind=service not found: {debtor_kinds}"
        print(f"[pass] all three kind values accepted and returned: {debtor_kinds}")

        # --- Edge case 2: bidirectional debts (B also owes A) ---
        resp = http_client.post(
            f"{_ADMIN}/debts/{char_b}",
            json={"creditor_id": char_a, "kind": "favor", "magnitude": "a returned favor"},
        )
        assert resp.status_code == 200, resp.text

        resp = http_client.get(f"{_ADMIN}/debts/{char_a}")
        debts_a_full = resp.json()["data"]["debts"]
        roles_a = {d["role"] for d in debts_a_full}
        assert "debtor" in roles_a, "char_a should appear as debtor"
        assert "creditor" in roles_a, "char_a should appear as creditor (B owes A a favor)"
        print("[pass] bidirectional debts: char_a seen as both debtor and creditor")

        # --- Edge case 3: creditor rows have role='creditor' ---
        creditor_rows = [d for d in debts_a_full if d["role"] == "creditor"]
        assert len(creditor_rows) == 1
        assert creditor_rows[0]["kind"] == "favor"
        assert creditor_rows[0]["other_id"] == char_b
        print("[pass] creditor row has role='creditor' and correct other_id")

        # --- Edge case 4: status transition to defaulted ---
        resp = http_client.patch(
            f"{_ADMIN}/debts/{char_a}/{char_b}",
            json={"status": "defaulted"},
        )
        assert resp.status_code == 200, resp.text

        resp = http_client.get(f"{_ADMIN}/debts/{char_a}")
        after_default = resp.json()["data"]["debts"]
        debtor_after = [d for d in after_default if d["role"] == "debtor"]
        assert len(debtor_after) == 0, (
            f"After defaulting, char_a should have 0 pending debtor rows, got {len(debtor_after)}"
        )
        print("[pass] defaulted debts no longer appear in pending query")

        # --- Edge case 5: fulfilled also excluded from pending query ---
        resp = http_client.patch(
            f"{_ADMIN}/debts/{char_b}/{char_a}",
            json={"status": "fulfilled"},
        )
        assert resp.status_code == 200, resp.text

        resp = http_client.get(f"{_ADMIN}/debts/{char_a}")
        after_fulfill = resp.json()["data"]["debts"]
        assert len(after_fulfill) == 0, (
            f"After fulfilling B→A favor, char_a should have 0 pending rows, got {len(after_fulfill)}"
        )
        print("[pass] fulfilled debts no longer appear in pending query")

        print("\n[PASS] scenario_debts_edge completed successfully.")

    finally:
        _delete_char(http_client, char_a)
        _delete_char(http_client, char_b)
