"""
test_subgraph_retriever.py - Unit tests for subgraph_retriever helpers.

Does NOT: execute real Neo4j queries.

Dependencies injected: None.
"""

from __future__ import annotations

import json

import pytest

from npc_engine.retrieval.subgraph_retriever import _flatten_event_row


class TestFlattenEventRow:
    def test_no_distortion_preserves_summary(self):
        row = {
            "event": {"id": "evt_1", "summary": "Armies crossed the border", "event_type": "conflict"},
            "knowledge_state": "knows",
            "distorted_summary": None,
        }
        result = _flatten_event_row(row)
        assert result["summary"] == "Armies crossed the border"
        assert result["knowledge_state"] == "knows"
        assert "distorted_summary" not in result
        assert "event" not in result

    def test_distortion_suppresses_ground_truth_but_keeps_knowledge_state(self):
        # S26.1 (ISSUE-093): keep the rumour signal (knowledge_state) alongside the
        # distorted account so the prompt can frame it as hearsay, not firsthand —
        # while still suppressing the competing ground-truth summary.
        row = {
            "event": {"id": "evt_1", "summary": "Armies crossed the border", "event_type": "conflict"},
            "knowledge_state": "rumor",
            "distorted_summary": "northmen have poured through the king's pass",
        }
        result = _flatten_event_row(row)
        assert result["distorted_summary"] == "northmen have poured through the king's pass"
        assert result["knowledge_state"] == "rumor"
        assert "summary" not in result
        assert "event" not in result

    def test_distortion_returns_distorted_summary_and_state_only(self):
        row = {
            "event": {"id": "evt_1", "summary": "...", "event_type": "conflict", "severity": 90},
            "knowledge_state": "rumor",
            "distorted_summary": "garbled account",
        }
        result = _flatten_event_row(row)
        assert result == {"distorted_summary": "garbled account", "knowledge_state": "rumor"}

    def test_missing_event_key_returns_empty_base(self):
        row = {"event": None, "knowledge_state": "knows", "distorted_summary": None}
        result = _flatten_event_row(row)
        assert result == {"knowledge_state": "knows"}

    def test_empty_row_returns_empty_dict(self):
        result = _flatten_event_row({})
        assert result == {}
