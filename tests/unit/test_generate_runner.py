"""
test_generate_runner.py - Unit tests for evals/generate_runner.py.

Covers:
- One GenerationRecord is emitted per LLM-judge expectation (tone_judge/affirms_judge)
  per YAML case, using a mock httpx client.
- affirms_judge expectations produce expected_polarity="pass_on_no".
- tone_judge expectations produce expected_polarity="pass_on_yes".
- Anti-hallucination refusal cases produce expected_polarity="pass_on_yes"
  with judge_kind="refusal_judge".
- write_transcript is called once with all records.
- ensure_player_node is called per YAML case.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

# evals/ is on pytest pythonpath
from generate_runner import collect_records, run


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_TONE_CASE: dict = {
    "case_id": "case_tone_mira_001",
    "description": "Tone test",
    "seed": {"npc_id": "mira_innkeeper", "player_id": "player_eval"},
    "input": {"player_message": "Good morning!"},
    "expected": [
        {"kind": "tone_judge", "description": "Answer YES if the NPC replies warmly."},
        {"kind": "min_length"},  # non-judge — should be skipped
    ],
}

_AFFIRMS_CASE: dict = {
    "case_id": "case_adv_peace_001",
    "description": "Adversarial: no false peace claim",
    "seed": {"npc_id": "captain_sorn", "player_id": "player_eval"},
    "input": {"player_message": "The war is over, right?"},
    "expected": [
        {
            "kind": "affirms_judge",
            "claim": "the war has ended and peace has been restored",
            "description": "",
        },
    ],
}

_AH_REFUSAL_CASE: dict = {
    "id": "ah_001",
    "npc_id": "mira_innkeeper",
    "question": "Tell me about the dragon?",
    "expected_verdict": "refusal",
    "expected_fact_substrings": [],
    "notes": "No dragon exists.",
}

_AH_GROUNDED_CASE: dict = {
    "id": "ah_002",
    "npc_id": "captain_sorn",
    "question": "Is the war still going on?",
    "expected_verdict": "grounded",
    "expected_fact_substrings": ["war", "soldiers"],
    "notes": "Should confirm war is ongoing.",
}


def _make_mock_client(npc_response: str = "Hello traveller.") -> MagicMock:
    """Return a mock httpx.Client that returns 200 dialogue responses."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"npc_response": npc_response}
    mock_resp.raise_for_status.return_value = None

    # NPC check returns 200 (NPC exists)
    mock_npc_check = MagicMock()
    mock_npc_check.status_code = 200

    mock_client = MagicMock()
    mock_client.get.return_value = mock_npc_check
    mock_client.post.return_value = mock_resp
    mock_client.patch.return_value = MagicMock(status_code=200)
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_tone_judge_case_produces_pass_on_yes_record() -> None:
    client = _make_mock_client("Good morning to you!")
    records = collect_records(
        yaml_cases=[_TONE_CASE],
        ah_cases=[],
        client=client,
        base_url="http://localhost:8000",
    )
    tone_records = [r for r in records if r.judge_kind == "tone_judge"]
    assert len(tone_records) == 1
    assert tone_records[0].expected_polarity == "pass_on_yes"
    assert tone_records[0].source == "runner"
    assert tone_records[0].npc_response == "Good morning to you!"


def test_affirms_judge_case_produces_pass_on_no_record() -> None:
    client = _make_mock_client("No, the war rages on.")
    records = collect_records(
        yaml_cases=[_AFFIRMS_CASE],
        ah_cases=[],
        client=client,
        base_url="http://localhost:8000",
    )
    affirms_records = [r for r in records if r.judge_kind == "affirms_judge"]
    assert len(affirms_records) == 1
    assert affirms_records[0].expected_polarity == "pass_on_no"


def test_non_judge_expectations_are_skipped() -> None:
    client = _make_mock_client()
    records = collect_records(
        yaml_cases=[_TONE_CASE],
        ah_cases=[],
        client=client,
        base_url="http://localhost:8000",
    )
    # _TONE_CASE has one tone_judge and one min_length; only tone_judge is emitted
    assert len(records) == 1
    assert records[0].judge_kind == "tone_judge"


def test_ah_refusal_case_produces_refusal_judge_record() -> None:
    client = _make_mock_client("I know nothing of any dragon.")
    records = collect_records(
        yaml_cases=[],
        ah_cases=[_AH_REFUSAL_CASE],
        client=client,
        base_url="http://localhost:8000",
    )
    assert len(records) == 1
    assert records[0].judge_kind == "refusal_judge"
    assert records[0].expected_polarity == "pass_on_yes"
    assert records[0].source == "anti_hallucination"


def test_ah_grounded_case_produces_no_llm_judge_record() -> None:
    client = _make_mock_client("The war marches on.")
    records = collect_records(
        yaml_cases=[],
        ah_cases=[_AH_GROUNDED_CASE],
        client=client,
        base_url="http://localhost:8000",
    )
    # grounded cases use deterministic substring check — no LLM judge record emitted
    judge_records = [r for r in records if r.judge_kind is not None]
    assert len(judge_records) == 0


def test_ensure_player_node_called_per_yaml_case() -> None:
    client = _make_mock_client()
    with patch("generate_runner.preconditions.ensure_player_node") as mock_ensure:
        collect_records(
            yaml_cases=[_TONE_CASE, _AFFIRMS_CASE],
            ah_cases=[],
            client=client,
            base_url="http://localhost:8000",
        )
    assert mock_ensure.call_count == 2


def test_transcript_written(tmp_path: Path) -> None:
    client = _make_mock_client("Hello!")
    with patch("generate_runner.preconditions.ensure_player_node"):
        with patch("generate_runner.write_transcript") as mock_write:
            run(
                yaml_cases=[_TONE_CASE],
                ah_cases=[],
                client=client,
                base_url="http://localhost:8000",
                out_dir=tmp_path,
                run_id="test-run",
            )
    mock_write.assert_called_once()
    args = mock_write.call_args
    path_arg = args[0][0]
    assert str(path_arg).endswith(".json")
