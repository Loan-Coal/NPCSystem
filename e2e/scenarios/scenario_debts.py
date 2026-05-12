"""
scenario_debts.py - E2E scenario for Feature 3.8: Promises and debts.

Requires: live Neo4j instance.
Run with: python e2e/scenarios/scenario_debts.py

Steps:
  1. Seed two Character nodes.
  2. Create a debt (A owes B a favor).
  3. Fetch debts for A, assert one returned with correct kind and status pending.
  4. Update status to fulfilled.
  5. Fetch debts for A again, assert status is now fulfilled.
  6. Cleanup.
"""

from __future__ import annotations

import asyncio
import os
import uuid

_BOLT = os.getenv("NEO4J_URI", "bolt://localhost:7687")
_AUTH = (os.getenv("NEO4J_USER", "neo4j"), os.getenv("NEO4J_PASSWORD", "password"))

_suffix = uuid.uuid4().hex[:8]
_CHAR_A = f"e2e_debt_char_a_{_suffix}"
_CHAR_B = f"e2e_debt_char_b_{_suffix}"


async def run() -> None:
    from neo4j import AsyncGraphDatabase

    driver = AsyncGraphDatabase.driver(_BOLT, auth=_AUTH)

    from npc_engine.graph.owes_service import (
        create_debt,
        get_debts_for_character_svc,
        update_debt_status,
    )

    try:
        # Step 1: seed characters
        async with driver.session() as session:
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'Debt E2E Char A', c.is_active = true",
                id=_CHAR_A,
            )
            await session.run(
                "MERGE (c:Character {id: $id}) SET c.name = 'Debt E2E Char B', c.is_active = true",
                id=_CHAR_B,
            )
        print(f"[seed] Characters {_CHAR_A} and {_CHAR_B} created.")

        # Step 2: create a debt
        async with driver.session() as session:
            await create_debt(
                session,
                debtor_id=_CHAR_A,
                creditor_id=_CHAR_B,
                kind="favor",
                magnitude="help with the harvest",
                due_by="",
            )
        print(f"[create] Debt created: {_CHAR_A} owes {_CHAR_B} a favor.")

        # Step 3: fetch debts for A — expect one with kind=favor, status=pending
        async with driver.session() as session:
            debts = await get_debts_for_character_svc(session, character_id=_CHAR_A)

        assert len(debts) == 1, f"Expected 1 debt for A, got {len(debts)}"
        assert debts[0]["kind"] == "favor", f"Expected kind=favor, got {debts[0]['kind']}"
        assert debts[0]["status"] == "pending", f"Expected status=pending, got {debts[0]['status']}"
        assert debts[0]["role"] == "debtor", f"Expected role=debtor, got {debts[0]['role']}"
        print(f"[assert] 1 pending favor debt returned for A. OK.")

        # Step 4: update status to fulfilled
        async with driver.session() as session:
            await update_debt_status(
                session,
                debtor_id=_CHAR_A,
                creditor_id=_CHAR_B,
                status="fulfilled",
            )
        print(f"[update] Status set to fulfilled.")

        # Step 5: fetch again — now no pending debts for A
        async with driver.session() as session:
            debts_after = await get_debts_for_character_svc(session, character_id=_CHAR_A)

        assert len(debts_after) == 0, f"Expected 0 pending debts after fulfillment, got {len(debts_after)}"
        print(f"[assert] 0 pending debts after fulfillment. OK.")

        print("\nAll assertions passed. Feature 3.8 E2E scenario: PASS")

    finally:
        async with driver.session() as session:
            await session.run(
                "MATCH (c:Character {id: $id}) DETACH DELETE c",
                id=_CHAR_A,
            )
            await session.run(
                "MATCH (c:Character {id: $id}) DETACH DELETE c",
                id=_CHAR_B,
            )
        await driver.close()
        print("[cleanup] Nodes removed.")


if __name__ == "__main__":
    asyncio.run(run())
