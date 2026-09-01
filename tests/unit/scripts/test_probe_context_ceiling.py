"""
Module: tests.unit.scripts.test_probe_context_ceiling
Layer: test (unit)
Purpose: Pin the context-ceiling probe's PARSE against a recorded debug-retrieval
         response, so the number P10's window trim is derived from cannot silently
         become a different number.
Dependencies: pytest; scripts.probe_context_ceiling
Used by: make test (pytest discovery)

WHY THIS MODULE EXISTS
`GET /v1/admin/debug/retrieval` returns TWO totals that differ, and the trim decision
changes depending on which one is read:

  * `total_tokens` at the TOP LEVEL is the estimate of the SERIALIZED context blob --
    the quantity `_trim_to_serialized_budget` actually enforces against the budget.
  * `context_receipt.total_tokens` is the SUM OF PER-ITEM estimates, which the comment
    above `_tier_a_cap_with_reclaim` records as OVER-counting the serialized size more
    often than it under-counts.

Measured live on captain_sorn at corpus_sha 2b19e47a: 978 serialized against 995 summed.
A probe that reported one of them as "the ceiling" would understate or overstate the
headroom a window has to hold, so this module requires BOTH to be reported and requires
them to stay distinct.

It is the same defect class as ISSUE-216, which is why it is pinned before use rather
than after: `scripts/probe_inner_life.py` was rebuilt from prose twice and reported a
false 0/8 both times.

Does NOT: perform HTTP, hit the engine, or read the graph.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load(name: str):
    """Load a scripts/*.py module by PATH, without touching sys.path.

    `scripts/` has no `__init__.py`, so a normal import would put the REPO ROOT on
    sys.path, which makes `evals` resolvable as a top-level package and drops measured
    coverage by ~19 points (recorded in test_probe_inner_life._load_probe). A path-based
    load has no such reach.
    """
    path = Path(__file__).resolve().parents[3] / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"_{name}_under_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(name="probe")
def _probe():
    return _load("probe_context_ceiling")


def _body(**overrides) -> dict:
    """A recorded captain_sorn response at corpus_sha 2b19e47a, window 32768."""
    body = {
        "npc_id": "captain_sorn",
        "query": "what news",
        "player_id": "player_demo",
        "retrieval_profile": "default",
        "context_items": [],
        "total_tokens": 978,
        "context_receipt": {
            "retrieval_profile": "default",
            "item_keys": ["world", "npc", "npc_known_events"],
            "dropped": [],
            "tier_spend": [
                {"tier": "tier0", "items": 2, "tokens": 75},
                {"tier": "tierA", "items": 8, "tokens": 687},
                {"tier": "tierB", "items": 2, "tokens": 93},
                {"tier": "tierC", "items": 3, "tokens": 140},
            ],
            "total_tokens": 995,
            "prompt_token_budget": 25638,
            "budget_trimmed": False,
        },
    }
    body.update(overrides)
    return body


def test_the_two_totals_are_reported_separately_and_are_not_conflated(probe):
    row = probe.extract_ceiling(_body())
    assert row.serialized_tokens == 978
    assert row.summed_tokens == 995
    assert row.serialized_tokens != row.summed_tokens


def test_the_ceiling_is_the_larger_of_the_two_totals(probe):
    """The window must hold whichever estimate is bigger, or the headroom is a fiction."""
    assert probe.extract_ceiling(_body()).ceiling_tokens == 995
    body = _body(total_tokens=1200)
    assert probe.extract_ceiling(body).ceiling_tokens == 1200


def test_every_reported_tier_is_read_including_empty_ones(probe):
    row = probe.extract_ceiling(_body())
    assert row.tiers == {"tier0": (2, 75), "tierA": (8, 687), "tierB": (2, 93), "tierC": (3, 140)}


def test_the_budget_the_assembly_was_held_to_is_carried_through(probe):
    assert probe.extract_ceiling(_body()).prompt_token_budget == 25638


def test_a_missing_receipt_raises_instead_of_reporting_zeros(probe):
    """A cached assembly publishes no receipt (DEC-195). Zeros would read as 'no spend'."""
    with pytest.raises(ValueError, match="no context receipt"):
        probe.extract_ceiling(_body(context_receipt=None))


def test_a_tier_a_soft_cap_drop_is_issue_209_evidence(probe):
    receipt = _body()["context_receipt"] | {
        "dropped": [{"key": "nearby_npcs", "tier": "tierA", "reason": "tier_soft_cap"}],
        "budget_trimmed": True,
    }
    row = probe.extract_ceiling(_body(context_receipt=receipt))
    assert row.issue_209_drops == ("nearby_npcs:tier_soft_cap",)


def test_a_tier_a_prompt_budget_drop_is_also_issue_209_evidence(probe):
    """`_fill_tier_a` skips-rather-than-stops too, so both stages are the same mechanism."""
    receipt = _body()["context_receipt"] | {
        "dropped": [{"key": "memories", "tier": "tierA", "reason": "prompt_budget"}],
        "budget_trimmed": True,
    }
    assert probe.extract_ceiling(_body(context_receipt=receipt)).issue_209_drops == (
        "memories:prompt_budget",
    )


def test_a_final_trim_drop_is_NOT_issue_209_evidence(probe):
    """The serialized trim loop only ever removes; ISSUE-197 misattributed the bug to it."""
    receipt = _body()["context_receipt"] | {
        "dropped": [{"key": "rag:e1", "tier": "tierA", "reason": "final_trim"}],
        "budget_trimmed": True,
    }
    row = probe.extract_ceiling(_body(context_receipt=receipt))
    assert row.issue_209_drops == ()
    assert row.dropped == ("rag:e1:tierA:final_trim",)


def test_a_tier_b_drop_is_not_issue_209_evidence(probe):
    """ISSUE-209 is a TIER-A selection defect; tier B is compressed, not greedily skipped."""
    receipt = _body()["context_receipt"] | {
        "dropped": [{"key": "rag:e1", "tier": "tierB", "reason": "tier_soft_cap"}],
        "budget_trimmed": True,
    }
    assert probe.extract_ceiling(_body(context_receipt=receipt)).issue_209_drops == ()


def test_the_roster_is_identical_to_the_inner_life_probe(probe):
    """Two probes reporting on different NPCs cannot be read as one measurement."""
    assert probe.PROBE_NPCS == _load("probe_inner_life").PROBE_NPCS


# ---------------------------------------------------------------------------
# --record: writing the gated ceiling artifact (B6/R2.7b)
# ---------------------------------------------------------------------------


def _row(probe, npc_id: str, ceiling: int, tier_a: int = 100):
    """One CeilingRow with only the fields the recorder reads."""
    return probe.CeilingRow(
        npc_id=npc_id,
        retrieval_profile="default",
        serialized_tokens=ceiling,
        summed_tokens=ceiling,
        ceiling_tokens=ceiling,
        tiers={"tier0": (1, 10), "tierA": (1, tier_a), "tierB": (1, 20), "tierC": (1, 30)},
        prompt_token_budget=5158,
        dropped=(),
        issue_209_drops=(),
    )


def test_the_recorded_ceiling_is_the_roster_maximum(probe, tmp_path):
    """A per-NPC number would under-record the window the roster actually needs."""
    rows = [_row(probe, "bren_smith", 832), _row(probe, "mira_innkeeper", 1151)]

    probe._record_baseline(rows, tmp_path / "b.json", "2b19e47a")

    written = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert written["roster_ceiling_tokens"] == 1151


def test_the_recorded_npc_is_the_one_that_produced_the_ceiling(probe, tmp_path):
    """A ceiling attributed to the wrong NPC cannot be reproduced by re-probing it."""
    rows = [_row(probe, "bren_smith", 832), _row(probe, "mira_innkeeper", 1151)]

    probe._record_baseline(rows, tmp_path / "b.json", "2b19e47a")

    assert json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))["npc_id"] == "mira_innkeeper"


def test_tier_maxima_are_per_tier_maxima_not_the_peak_npcs_row(probe, tmp_path):
    """Each tier's worst case can land on a different NPC than the roster ceiling does."""
    rows = [_row(probe, "bren_smith", 832, tier_a=900), _row(probe, "mira_innkeeper", 1151, tier_a=100)]

    probe._record_baseline(rows, tmp_path / "b.json", "2b19e47a")

    written = json.loads((tmp_path / "b.json").read_text(encoding="utf-8"))
    assert written["tier_maxima"]["tier_a"] == 900


def test_recording_without_a_corpus_sha_is_refused(probe, tmp_path):
    """The ISSUE-246 shape, refused at write time rather than found a release later.

    A ceiling is a property of the corpus as much as of the code, so one recorded without
    naming its corpus cannot be compared to any later measurement — exactly how
    `trend_v1.jsonl`'s single null-digest row became permanently uncomparable.
    """
    with pytest.raises(ValueError, match="corpus-sha"):
        probe._record_baseline([_row(probe, "mira_innkeeper", 1151)], tmp_path / "b.json", "  ")

    assert not (tmp_path / "b.json").exists(), "a refused record must write nothing"


def test_the_recorded_artifact_is_written_with_lf_endings(probe, tmp_path):
    """.gitattributes normalizes to LF; a CRLF write rewrites the whole file in git's eyes."""
    probe._record_baseline([_row(probe, "mira_innkeeper", 1151)], tmp_path / "b.json", "2b19e47a")

    assert b"\r\n" not in (tmp_path / "b.json").read_bytes()
