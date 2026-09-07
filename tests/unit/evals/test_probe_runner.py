"""
Module: test_probe_runner
Layer: test (unit)
Purpose: Tests for evals/probe_runner.py — the k-repetition EngineProbe loop,
         the free GET /v1/clock/state engine_status snapshot, invariant checking,
         metrics merge precedence, and the `probe` verb's CLI entry point.
         Pure logic + mocked httpx only — no server, no LLM, no I/O.
Dependencies: pytest, unittest.mock, httpx, probe_runner (evals/), probe_protocol
              (evals/), sequence_records (evals/)
Used by: pytest (make test / make check)
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import probe_runner
from probe_runner import (
    EngineStatusSnapshot,
    _check_invariants,
    _merge_status_metrics,
    _run_one_probe_repetition,
    main,
    read_engine_status,
    run_probe,
)
from sequence_records import ResetReceipt

_FULL_RECEIPT = ResetReceipt(cleared=("world_state.epoch",), surviving=(), duration_ms=1)


class _StubProbe:
    """Minimal EngineProbe stub — records call order, returns canned metrics."""

    def __init__(
        self,
        engine_name: str = "gossip",
        metrics: dict[str, float] | None = None,
        invariants: dict[str, object] | None = None,
        raise_in: str | None = None,
    ) -> None:
        self.engine_name = engine_name
        self.invariants = invariants if invariants is not None else {}
        self._metrics = metrics if metrics is not None else {}
        self._raise_in = raise_in
        self.calls: list[str] = []

    def setup(self, client) -> None:  # noqa: ANN001 - matches EngineProbe's structural type
        self.calls.append("setup")
        if self._raise_in == "setup":
            raise RuntimeError("setup blew up")

    def drive(self, client, ticks: int) -> None:  # noqa: ANN001
        self.calls.append(f"drive:{ticks}")
        if self._raise_in == "drive":
            raise RuntimeError("drive blew up")

    def measure(self, client) -> dict[str, float]:  # noqa: ANN001
        self.calls.append("measure")
        if self._raise_in == "measure":
            raise RuntimeError("measure blew up")
        return dict(self._metrics)


def _mock_status_response(status_code: int = 200, engine_status: dict | None = None) -> MagicMock:
    """Build a mock httpx.Response for GET /v1/clock/state."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {"data": {"engine_status": engine_status or {}}}
    return resp


# ---------------------------------------------------------------------------
# read_engine_status
# ---------------------------------------------------------------------------


def test_read_engine_status_parses_the_engine_status_dict() -> None:
    client = MagicMock()
    client.get.return_value = _mock_status_response(
        engine_status={"gossip": {"tick_count": 5, "error_count": 1, "last_duration_ms": 12.5}}
    )
    status = read_engine_status(client)
    assert status["gossip"] == EngineStatusSnapshot(tick_count=5, error_count=1, last_duration_ms=12.5)


def test_read_engine_status_non_200_returns_empty() -> None:
    client = MagicMock()
    client.get.return_value = _mock_status_response(status_code=503)
    assert read_engine_status(client) == {}


def test_read_engine_status_non_dict_status_returns_empty() -> None:
    client = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"data": {"engine_status": "not-a-dict"}}
    client.get.return_value = resp
    assert read_engine_status(client) == {}


def test_read_engine_status_skips_non_dict_entries() -> None:
    client = MagicMock()
    client.get.return_value = _mock_status_response(
        engine_status={"gossip": {"tick_count": 1}, "quest": "garbage"}
    )
    status = read_engine_status(client)
    assert "gossip" in status
    assert "quest" not in status


# ---------------------------------------------------------------------------
# _check_invariants
# ---------------------------------------------------------------------------


def test_check_invariants_all_pass_returns_none() -> None:
    invariants = {"a": lambda client: True, "b": lambda client: True}
    assert _check_invariants(MagicMock(), _StubProbe(invariants=invariants)) is None


def test_check_invariants_returns_first_failing_name() -> None:
    invariants = {"a": lambda client: True, "b": lambda client: False, "c": lambda client: True}
    assert _check_invariants(MagicMock(), _StubProbe(invariants=invariants)) == "b"


# ---------------------------------------------------------------------------
# _merge_status_metrics
# ---------------------------------------------------------------------------


def test_merge_status_metrics_fills_gaps_when_status_present() -> None:
    status = EngineStatusSnapshot(tick_count=3, error_count=0, last_duration_ms=8.0)
    merged = _merge_status_metrics({"reach": 1.0}, status)
    assert merged == {"reach": 1.0, "tick_count": 3.0, "error_count": 0.0, "duration_ms": 8.0}


def test_merge_status_metrics_probe_value_wins_on_collision() -> None:
    status = EngineStatusSnapshot(tick_count=3, error_count=0, last_duration_ms=8.0)
    merged = _merge_status_metrics({"tick_count": 99.0}, status)
    assert merged["tick_count"] == 99.0


def test_merge_status_metrics_none_status_leaves_metrics_unchanged() -> None:
    merged = _merge_status_metrics({"reach": 1.0}, None)
    assert merged == {"reach": 1.0}


def test_merge_status_metrics_does_not_mutate_input() -> None:
    original = {"reach": 1.0}
    _merge_status_metrics(original, EngineStatusSnapshot(tick_count=1))
    assert original == {"reach": 1.0}


def test_merge_status_metrics_omits_duration_when_never_run() -> None:
    """last_duration_ms is None for an engine that has never run — no duration_ms key added."""
    status = EngineStatusSnapshot(tick_count=0, error_count=0, last_duration_ms=None)
    merged = _merge_status_metrics({}, status)
    assert "duration_ms" not in merged


# ---------------------------------------------------------------------------
# _run_one_probe_repetition
# ---------------------------------------------------------------------------


def test_run_one_probe_repetition_happy_path_calls_in_order() -> None:
    probe = _StubProbe(metrics={"reach": 1.0}, invariants={"ok": lambda client: True})
    client = MagicMock()
    client.get.return_value = _mock_status_response(engine_status={})

    record = _run_one_probe_repetition(0, client, probe, ticks=2, reset_receipt=_FULL_RECEIPT)

    assert probe.calls == ["setup", "drive:2", "measure"]
    assert record.passed is True
    assert record.error is None
    assert record.metrics["reach"] == 1.0
    assert record.reset_receipt == _FULL_RECEIPT


def test_run_one_probe_repetition_failing_invariant_records_error_and_fails() -> None:
    probe = _StubProbe(invariants={"reach_ok": lambda client: False})
    client = MagicMock()
    client.get.return_value = _mock_status_response(engine_status={})

    record = _run_one_probe_repetition(0, client, probe, ticks=1, reset_receipt=_FULL_RECEIPT)

    assert record.passed is False
    assert record.error == "invariant failed: reach_ok"


@pytest.mark.parametrize("raise_in", ["setup", "drive", "measure"])
def test_run_one_probe_repetition_exception_is_recorded_not_raised(raise_in: str) -> None:
    """A raising probe step is recorded as a failed repetition (record-not-abort)."""
    probe = _StubProbe(raise_in=raise_in)
    client = MagicMock()
    client.get.return_value = _mock_status_response(engine_status={})

    record = _run_one_probe_repetition(0, client, probe, ticks=1, reset_receipt=_FULL_RECEIPT)

    assert record.passed is False
    assert record.error is not None
    assert "blew up" in record.error
    assert record.metrics == {}


# ---------------------------------------------------------------------------
# run_probe
# ---------------------------------------------------------------------------


def test_run_probe_calls_reset_exactly_k_times() -> None:
    probe = _StubProbe(metrics={"reach": 1.0}, invariants={"ok": lambda client: True})
    client = MagicMock()
    client.get.return_value = _mock_status_response(engine_status={})
    reset_calls = []

    def reset_fn() -> ResetReceipt:
        reset_calls.append(1)
        return _FULL_RECEIPT

    result = run_probe(client, probe, k=3, ticks=1, reset_fn=reset_fn)

    assert len(reset_calls) == 3
    assert result.k == 3
    assert len(result.repetitions) == 3
    assert result.engine_name == "gossip"


def test_run_probe_stat_metrics_summary_averages_across_repetitions() -> None:
    probe = _StubProbe(metrics={"reach": 2.0}, invariants={"ok": lambda client: True})
    client = MagicMock()
    client.get.return_value = _mock_status_response(engine_status={})

    result = run_probe(client, probe, k=2, ticks=1, reset_fn=lambda: _FULL_RECEIPT)

    assert result.stat.metrics_summary["reach"] == 2.0
    assert result.stat.fidelity == "FULL"
    assert result.stat.passes == 2


def test_run_probe_k_zero_raises_value_error() -> None:
    probe = _StubProbe()
    client = MagicMock()
    with pytest.raises(ValueError):
        run_probe(client, probe, k=0, reset_fn=lambda: _FULL_RECEIPT)


# ---------------------------------------------------------------------------
# CLI main()
# ---------------------------------------------------------------------------


def _stub_client_factory(status_engine_status: dict) -> MagicMock:
    """Build a stub httpx.Client class usable as `with httpx.Client(...) as client:`."""
    client = MagicMock()
    client.get.return_value = _mock_status_response(engine_status=status_engine_status)
    client.post.return_value = MagicMock(status_code=200)
    client_cm = MagicMock()
    client_cm.__enter__.return_value = client
    client_cm.__exit__.return_value = False
    factory = MagicMock(return_value=client_cm)
    return factory


def test_main_prints_free_engine_status_with_no_probes_registered(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = _stub_client_factory({"gossip": {"tick_count": 1, "error_count": 0, "last_duration_ms": 5.0}})
    monkeypatch.setattr(probe_runner.httpx, "Client", factory)
    monkeypatch.setattr(probe_runner, "PROBE_FACTORIES", {})

    exit_code = main(["--base-url", "http://localhost:8000", "--k", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "ENGINE STATUS" in captured.out
    assert "gossip: tick_count=1 error_count=0 last_duration=5.0ms" in captured.out
    assert "No probes registered" in captured.out


def test_main_runs_registered_probes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    factory = _stub_client_factory({})
    monkeypatch.setattr(probe_runner.httpx, "Client", factory)
    stub_probe = _StubProbe(metrics={"reach": 1.0}, invariants={"ok": lambda client: True})
    monkeypatch.setattr(
        probe_runner, "PROBE_FACTORIES", {"gossip": lambda client: stub_probe}
    )
    monkeypatch.setattr(probe_runner, "make_reset_fn", lambda client, base_url: (lambda: _FULL_RECEIPT))

    exit_code = main(["--k", "1"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "PROBE RESULTS" in captured.out
    assert "gossip reaches 1/1" in captured.out
