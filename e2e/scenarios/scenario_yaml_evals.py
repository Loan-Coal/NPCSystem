"""
Module: scenario_yaml_evals
Layer: e2e
Purpose: Run all YAML eval cases from evals/cases/ as parametrized pytest tests.
         Complements the standalone CLI runner (evals/runner.py) with pytest
         integration: marks, skip semantics, and unified reporting.
Dependencies: evals.matchers (via sys.path), evals.cases/*.yaml
Used by: make eval-e2e

Marks:
  @pytest.mark.eval  — all YAML eval cases (non-LLM matchers)
  @pytest.mark.eval_judge — cases with tone_judge expectations (requires Ollama)

Skip semantics (soft skip, not failure):
  - Case has no 'input' field → SKIP (targets non-dialogue endpoint, ISSUE-042)
  - NPC returns 404 → SKIP with requires_world hint (wrong world seeded)
  - Connection error → SKIP (server not running)

This does NOT replace evals/runner.py. Use `make eval` for the fast CLI smoke
test; use `make eval-e2e` for pytest-integrated reporting and CI compatibility.

Run with:
    make eval-e2e
    pytest e2e/scenarios/scenario_yaml_evals.py -v -m eval --scenarios-only
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

# ---------------------------------------------------------------------------
# sys.path patch: evals/ uses bare imports (from matchers import evaluate).
# Add evals/ to sys.path so matchers.py is importable from this file.
# ---------------------------------------------------------------------------
_EVALS_DIR = Path(__file__).resolve().parents[2] / "evals"
if str(_EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(_EVALS_DIR))

from matchers import evaluate  # noqa: E402 (after sys.path patch)

from e2e.scenarios.conftest import api_post  # noqa: E402

# ---------------------------------------------------------------------------
# Case loader — runs at collection time so parametrize sees all IDs
# ---------------------------------------------------------------------------

_CASES_DIR = _EVALS_DIR / "cases"


def _load_cases() -> list[dict[str, Any]]:
    """Load all .yaml eval cases sorted by filename."""
    cases: list[dict[str, Any]] = []
    for path in sorted(_CASES_DIR.glob("*.yaml")):
        with path.open(encoding="utf-8") as f:
            cases.append(yaml.safe_load(f))
    return cases


_ALL_CASES: list[dict[str, Any]] = _load_cases()


# ---------------------------------------------------------------------------
# Reputation helper (mirrors evals/runner.py _setup_reputation)
# ---------------------------------------------------------------------------


def _setup_reputation(case: dict, client: httpx.Client) -> None:
    """Pre-seed player faction reputation before the dialogue call, if declared."""
    seed = case.get("seed", {})
    player_id: str = seed.get("player_id", "player_eval")
    faction_id: str | None = seed.get("faction_id")
    standing: str | None = seed.get("player_reputation_standing")
    if faction_id is None or standing is None:
        return

    check = client.get(f"/v1/graph/nodes/Character/{player_id}", timeout=10.0)
    if check.status_code == 404:
        now = datetime.now(timezone.utc).isoformat()
        client.post(
            "/v1/graph/nodes/Character",
            json={"properties": {
                "id": player_id,
                "name": player_id,
                "archetype": "player",
                "biography": "The player character.",
                "is_player": True,
                "is_active": True,
                "gossipy": 50,
                "credulity": 50,
                "honesty": 50,
                "current_mood": "neutral",
                "voice_descriptor": None,
                "created_at": now,
                "updated_at": now,
                "last_graph_updated_at": now,
            }},
            timeout=10.0,
        )

    client.put(
        f"/v1/admin/characters/{player_id}/reputation/{faction_id}",
        json={"standing": standing},
        timeout=10.0,
    )


# ---------------------------------------------------------------------------
# Parametrized test
# ---------------------------------------------------------------------------


@pytest.mark.eval
@pytest.mark.parametrize("case", _ALL_CASES, ids=lambda c: c.get("case_id", "unknown"))
def test_eval_case(case: dict, http_client: httpx.Client) -> None:
    """Run a single YAML eval case against the live NPC Engine API.

    Args:
        case: Loaded YAML eval case dict.
        http_client: Session-scoped httpx.Client from conftest.
    """
    case_id: str = case.get("case_id", "unknown")
    seed: dict = case.get("seed", {})
    inp: dict | None = case.get("input")
    requires_world: str | None = seed.get("requires_world")

    # Cases without an 'input' field target non-dialogue endpoints (ISSUE-042)
    if inp is None:
        pytest.skip(f"{case_id}: no 'input' field — targets non-dialogue endpoint")

    _setup_reputation(case, http_client)

    payload: dict[str, Any] = {
        "player_id": seed.get("player_id", "player_eval"),
        "npc_id": seed.get("npc_id", "npc_eval"),
        "player_message": inp["player_message"],
        "session_id": f"eval:{case_id}",
    }
    if seed.get("location_id"):
        payload["location_id"] = seed["location_id"]

    try:
        result = api_post(http_client, "/v1/dialogue", payload)
    except Exception as exc:
        if requires_world:
            seed_cmd = "make demo-seed" if requires_world == "demo" else f"make seed-{requires_world}-world"
            pytest.skip(f"{case_id}: connection error — ensure {requires_world!r} world is seeded ({seed_cmd}): {exc}")
        raise

    # 404 almost always means the NPC belongs to a different world seed
    if result["status"] == 404:
        if requires_world:
            seed_cmd = "make demo-seed" if requires_world == "demo" else f"make seed-{requires_world}-world"
            pytest.skip(
                f"{case_id}: NPC {payload['npc_id']!r} not found — "
                f"requires world {requires_world!r}. Run: {seed_cmd}"
            )
        pytest.fail(f"{case_id}: 404 with no requires_world — NPC {payload['npc_id']!r} missing")

    assert result["status"] == 200, (
        f"{case_id}: dialogue endpoint returned {result['status']}: {result['body']}"
    )
    response_body: dict = result["body"]

    failures: list[str] = []
    for exp in case.get("expected", []):
        if exp.get("skip_until_implemented"):
            continue
        passed, detail = evaluate(expectation=exp, response=response_body)
        if not passed:
            failures.append(f"  [{exp['kind']}] FAIL: {detail}")

    assert not failures, (
        f"{case_id} — {len(failures)} expectation(s) failed:\n" + "\n".join(failures)
        + f"\n\nNPC response: {response_body.get('npc_response', '')!r}"
    )
