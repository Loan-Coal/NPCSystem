"""
scenario_demo.py - Full Phase 3 story arc showcasing all World Depth features.

Requires: running NPC Engine API server with seed data loaded (run `make seed-api` first).

Story arc:
  ACT 1 — Morning
    Aldric recalls his memory of the guild fire. His belief about the guild
    shapes his perspective.

  ACT 2 — Midday
    Sera's secret about the tunnel weighs on her. Her goal — gathering enough
    coin to leave — drives her.

  ACT 3 — Afternoon
    Mira's urgent goal (find the missing shipment, urgency=85) leads her to
    seek Garr. Aldric's debt to Sera surfaces. Garr's Silver Dagger is
    confirmed in his possession.

  ACT 4 — Evening
    Aldric fulfills his debt to Mira. Sera achieves her goal. The world is
    richer for the day.

Marks:
  @pytest.mark.demo    — run alone with `make scenario-demo`

Cleanup: removes only demo-created nodes; seed characters and their seeded
Phase 3 entities are left intact. The fulfilled demo debt edge stays in the
graph (fulfillment is its own cleanup).
"""

from __future__ import annotations

import httpx
import pytest

from e2e.scenarios.conftest import char_props

_ADMIN = "/v1/admin"
_GRAPH = "/v1/graph"

_SEED_CHARS = {
    "npc_1": "Aldric",
    "npc_2": "Sera",
    "npc_3": "Mira",
    "npc_4": "Garr",
}

_WIDTH = 64


def _banner(title: str) -> None:
    print(f"\n{'═' * _WIDTH}")
    print(f"  {title}")
    print(f"{'═' * _WIDTH}\n")


def _narrate(text: str) -> None:
    print(f"  > {text}")


def _step(label: str, ok: bool, detail: str = "") -> None:
    sym = "✓" if ok else "✗"
    pad = max(1, 50 - len(label))
    suffix = f"  {detail}" if detail else ""
    print(f"  {sym} {label} {'.' * pad}{suffix}")


@pytest.mark.demo
def test_demo_phase3_story(http_client: httpx.Client) -> None:
    demo_memory_id: str | None = None
    demo_belief_id: str | None = None
    demo_secret_id: str | None = None
    demo_goal_id: str | None = None
    demo_goal_sera_id: str | None = None

    demo_debt_debtor = "npc_1"
    demo_debt_creditor = "npc_3"

    try:
        # ── Verify seed data is present ────────────────────────────────────
        _banner("Demo: Phase 3 Story — World Depth")
        _narrate("Verifying seed characters are present…")
        for char_id, name in _SEED_CHARS.items():
            resp = http_client.get(f"{_ADMIN}/beliefs/{char_id}", params={"k": 1})
            assert resp.status_code == 200, (
                f"Seed character {name!r} ({char_id}) not reachable. "
                "Run `make seed-api` before the demo."
            )
            _step(f"seed char {name}", True, f"id={char_id}")

        # ══════════════════════════════════════════════════════════════════
        # ACT 1 — MORNING: Memory recall + belief context
        # ══════════════════════════════════════════════════════════════════
        _banner("ACT 1 — Morning")
        _narrate(
            "Aldric wakes at the Iron Lantern. A memory of the guild fire "
            "surfaces, reinforced by his long-held belief about the guild."
        )

        # Create a fresh demo memory for Aldric (arousal=88 → above threshold)
        resp = http_client.post(
            f"{_ADMIN}/memories/from-arousal/npc_1",
            json={
                "content": (
                    "Smoke rises from the south warehouse. Guild enforcers "
                    "stand watch while it burns — nobody calls the guard."
                ),
                "arousal": 88,
            },
        )
        assert resp.status_code == 200, resp.text
        demo_memory_id = resp.json()["data"]["memory_id"]
        assert demo_memory_id is not None
        _step("Aldric: memory formed (arousal=88)", True, f"id={demo_memory_id}")

        # Recall memories
        resp = http_client.get(f"{_ADMIN}/memories/npc_1", params={"k": 3})
        assert resp.status_code == 200
        memories = resp.json()["data"]["memories"]
        top_memory = next((m for m in memories if m["id"] == demo_memory_id), None)
        assert top_memory is not None
        _step("Aldric: memory recalled", True, f"vividness={top_memory['vividness']}")
        _narrate(f'  "{top_memory["content"]}"')

        # Fetch seeded belief about the guild (or create a demo belief)
        resp = http_client.get(f"{_ADMIN}/beliefs/npc_1", params={"k": 5})
        assert resp.status_code == 200
        beliefs = resp.json()["data"]["beliefs"]
        guild_belief = next(
            (b for b in beliefs if "guild" in b["content"].lower()), None
        )
        if guild_belief:
            _step(
                "Aldric: guild belief in context",
                True,
                f"confidence={guild_belief['confidence']}",
            )
            _narrate(f'  Belief: "{guild_belief["content"]}"')
        else:
            resp = http_client.post(
                f"{_ADMIN}/beliefs/npc_1",
                json={
                    "content": "The guild will betray the city if it profits them.",
                    "confidence": 80,
                },
            )
            assert resp.status_code == 200, resp.text
            demo_belief_id = resp.json()["data"]["belief_id"]
            _step("Aldric: demo belief created", True)

        # ══════════════════════════════════════════════════════════════════
        # ACT 2 — MIDDAY: Sera's secret + goal
        # ══════════════════════════════════════════════════════════════════
        _banner("ACT 2 — Midday")
        _narrate(
            "Sera patrols the market. The secret about the tunnel presses on "
            "her conscience. Her plan to save enough to leave grows sharper."
        )

        # Fetch seeded secret for Sera (or create demo secret)
        resp = http_client.get(f"{_ADMIN}/secrets/npc_2", params={"k": 3})
        assert resp.status_code == 200
        secrets = resp.json()["data"]["secrets"]
        tunnel_secret = next(
            (s for s in secrets if "tunnel" in s["content"].lower()), None
        )
        if tunnel_secret:
            _step(
                "Sera: tunnel secret retrieved",
                True,
                f"severity={tunnel_secret['severity']}",
            )
            _narrate(f'  Secret: "{tunnel_secret["content"]}"')
        else:
            resp = http_client.post(
                f"{_ADMIN}/secrets/npc_2",
                json={
                    "content": "There is a secret tunnel from the tavern to the docks.",
                    "severity": 60,
                },
            )
            assert resp.status_code == 200, resp.text
            demo_secret_id = resp.json()["data"]["secret_id"]
            _step("Sera: demo secret created", True)

        # Create a fresh goal for Sera to mark achieved in Act 4
        resp = http_client.post(
            f"{_ADMIN}/goals/npc_2",
            json={
                "description": "Save 100 gold by end of season to fund departure.",
                "urgency": 65,
            },
        )
        assert resp.status_code == 200, resp.text
        demo_goal_sera_id = resp.json()["data"]["goal_id"]
        _step("Sera: savings goal created", True, f"id={demo_goal_sera_id}")

        # ══════════════════════════════════════════════════════════════════
        # ACT 3 — AFTERNOON: Mira's goal, Aldric's debt, Garr's dagger
        # ══════════════════════════════════════════════════════════════════
        _banner("ACT 3 — Afternoon")
        _narrate(
            "Mira's missing shipment presses urgency=85. She finds Garr at "
            "the docks. Aldric, meanwhile, owes Mira a debt — payment due soon."
        )

        # Fetch Mira's seeded goal (or create demo goal)
        resp = http_client.get(
            f"{_ADMIN}/goals/npc_3", params={"k": 5, "status": "active"}
        )
        assert resp.status_code == 200
        mira_goals = resp.json()["data"]["goals"]
        shipment_goal = next(
            (g for g in mira_goals if "shipment" in g["description"].lower()), None
        )
        if shipment_goal:
            _step(
                "Mira: shipment goal active",
                True,
                f"urgency={shipment_goal['urgency']}",
            )
            _narrate(f'  Goal: "{shipment_goal["description"]}"')
        else:
            resp = http_client.post(
                f"{_ADMIN}/goals/npc_3",
                json={
                    "description": "Find out what happened to the missing shipment.",
                    "urgency": 85,
                },
            )
            assert resp.status_code == 200, resp.text
            demo_goal_id = resp.json()["data"]["goal_id"]
            _step("Mira: demo goal created (urgency=85)", True)

        # Create a new demo debt: Aldric owes Mira (favor kind)
        resp = http_client.post(
            f"{_ADMIN}/debts/{demo_debt_debtor}",
            json={
                "creditor_id": demo_debt_creditor,
                "kind": "favor",
                "magnitude": "Promised to ask Garr about the missing crates.",
                "due_by": "Year 1, Spring, Day 5",
            },
        )
        assert resp.status_code == 200, resp.text
        _step("Aldric → Mira: favor debt created", True)

        resp = http_client.get(f"{_ADMIN}/debts/{demo_debt_debtor}")
        assert resp.status_code == 200
        aldric_debts = resp.json()["data"]["debts"]
        demo_debt = next(
            (
                d
                for d in aldric_debts
                if d["role"] == "debtor" and d["other_id"] == demo_debt_creditor
            ),
            None,
        )
        assert demo_debt is not None, "Demo debt (Aldric→Mira) not found"
        _step("Aldric: debt to Mira confirmed", True, f"kind={demo_debt['kind']}")
        _narrate(f'  Debt: "{demo_debt["magnitude"]}"')

        # Verify Garr's Silver Dagger
        resp = http_client.get(f"{_ADMIN}/items/npc_4")
        assert resp.status_code == 200
        garr_items = resp.json()["data"]["items"]
        dagger = next(
            (i for i in garr_items if "dagger" in i["name"].lower()), None
        )
        if dagger:
            _step(
                "Garr: Silver Dagger in inventory",
                True,
                f"value={dagger['value']}",
            )
        else:
            _step(
                "Garr: dagger not seeded (run `make seed-api` for full demo)",
                False,
            )

        # ══════════════════════════════════════════════════════════════════
        # ACT 4 — EVENING: Fulfill debt, achieve goal, close the arc
        # ══════════════════════════════════════════════════════════════════
        _banner("ACT 4 — Evening")
        _narrate(
            "Aldric keeps his word and speaks to Garr. The debt is settled. "
            "Sera counts her savings — enough to leave. Her goal is achieved."
        )

        # Fulfill Aldric's demo debt to Mira
        resp = http_client.patch(
            f"{_ADMIN}/debts/{demo_debt_debtor}/{demo_debt_creditor}",
            json={"status": "fulfilled"},
        )
        assert resp.status_code == 200, resp.text

        resp = http_client.get(f"{_ADMIN}/debts/{demo_debt_debtor}")
        aldric_pending = resp.json()["data"]["debts"]
        still_owed = [
            d
            for d in aldric_pending
            if d["role"] == "debtor" and d["other_id"] == demo_debt_creditor
        ]
        assert len(still_owed) == 0, "Fulfilled debt still showing as pending"
        _step("Aldric: debt to Mira fulfilled", True)

        # Achieve Sera's demo goal
        resp = http_client.patch(
            f"{_ADMIN}/goals/{demo_goal_sera_id}/status",
            json={"status": "achieved"},
        )
        assert resp.status_code == 200, resp.text

        resp = http_client.get(
            f"{_ADMIN}/goals/npc_2", params={"k": 10, "status": "active"}
        )
        sera_active = resp.json()["data"]["goals"]
        demo_still_active = any(g["id"] == demo_goal_sera_id for g in sera_active)
        assert not demo_still_active, "Achieved goal still listed as active"
        _step("Sera: savings goal achieved", True)

        _narrate(
            "The day ends. Memories were formed, secrets kept, debts settled, "
            "goals completed. Phase 3 World Depth is fully operational."
        )
        print(f"\n{'═' * _WIDTH}")
        print("  [PASS] scenario_demo completed successfully.")
        print(f"{'═' * _WIDTH}\n")

    finally:
        if demo_memory_id:
            http_client.delete(f"{_ADMIN}/memories/{demo_memory_id}")
        if demo_belief_id:
            http_client.delete(f"{_ADMIN}/beliefs/{demo_belief_id}")
        if demo_secret_id:
            http_client.delete(f"{_ADMIN}/secrets/{demo_secret_id}")
        if demo_goal_id:
            http_client.delete(f"{_ADMIN}/goals/{demo_goal_id}")
        if demo_goal_sera_id:
            http_client.delete(f"{_ADMIN}/goals/{demo_goal_sera_id}")
        # The fulfilled OWES edge (npc_1→npc_3) stays in the graph with
        # status=fulfilled — it won't appear in pending queries on the next run.
