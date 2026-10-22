"""
Module: test_transcript
Layer: demo_game (tests)
Purpose: Unit tests for TranscriptRecorder and RecordingClientWrapper — one JSONL
         line per HTTP request on a stubbed client.
Dependencies: demo_game.runners.transcript, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from demo_game.runners.transcript import RecordingClientWrapper, TranscriptRecorder


class TestTranscriptRecorder:
    def test_record_appends_one_entry_in_memory(self) -> None:
        """record() appends exactly one entry to the in-memory list."""
        recorder = TranscriptRecorder()
        recorder.record(method="POST", path="/v1/dialogue", status=200, body={"x": 1})
        assert len(recorder.entries) == 1
        entry = recorder.entries[0]
        assert entry["method"] == "POST"
        assert entry["path"] == "/v1/dialogue"
        assert entry["status"] == 200

    def test_one_jsonl_line_per_record_call(self) -> None:
        """Each record() writes exactly one line to the JSONL file."""
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            path = Path(f.name)
        try:
            recorder = TranscriptRecorder(path=path)
            recorder.record(method="GET", path="/v1/graph/nodes", status=200, body={})
            recorder.record(method="POST", path="/v1/events", status=201, body={"id": "e1"})
            lines = path.read_text(encoding="utf-8").splitlines()
            assert len(lines) == 2
            assert json.loads(lines[0])["path"] == "/v1/graph/nodes"
            assert json.loads(lines[1])["path"] == "/v1/events"
        finally:
            path.unlink(missing_ok=True)

    def test_entries_returns_immutable_copy(self) -> None:
        """entries property returns a copy — external mutation does not affect recorder state."""
        recorder = TranscriptRecorder()
        recorder.record(method="GET", path="/v1/x", status=200, body={})
        snapshot = recorder.entries
        snapshot.clear()
        assert len(recorder.entries) == 1

    def test_no_file_written_without_path(self) -> None:
        """Recorder with no path does not write to disk."""
        recorder = TranscriptRecorder()
        recorder.record(method="GET", path="/v1/x", status=200, body={})
        assert len(recorder.entries) == 1


class TestRecordingClientWrapper:
    def test_one_entry_per_get_request(self) -> None:
        """GET call through wrapper records exactly one entry with method GET."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"data": []}
        inner = MagicMock()
        inner.get.return_value = resp

        recorder = TranscriptRecorder()
        wrapper = RecordingClientWrapper(inner, recorder)
        wrapper.get("/v1/graph/nodes", timeout=5)

        assert len(recorder.entries) == 1
        assert recorder.entries[0]["method"] == "GET"
        assert recorder.entries[0]["status"] == 200

    def test_one_entry_per_post_request(self) -> None:
        """POST call through wrapper records exactly one entry with method POST."""
        resp = MagicMock()
        resp.status_code = 201
        resp.json.return_value = {"id": "e1"}
        inner = MagicMock()
        inner.post.return_value = resp

        recorder = TranscriptRecorder()
        wrapper = RecordingClientWrapper(inner, recorder)
        wrapper.post("/v1/events", json={"type": "fire"})

        assert len(recorder.entries) == 1
        assert recorder.entries[0]["method"] == "POST"
        assert recorder.entries[0]["status"] == 201

    def test_one_entry_per_patch_request(self) -> None:
        """PATCH call through wrapper records exactly one entry with method PATCH."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"updated": True}
        inner = MagicMock()
        inner.patch.return_value = resp

        recorder = TranscriptRecorder()
        wrapper = RecordingClientWrapper(inner, recorder)
        wrapper.patch("/v1/npc/sorn/rep", json={"delta": 5})

        assert len(recorder.entries) == 1
        assert recorder.entries[0]["method"] == "PATCH"
        assert recorder.entries[0]["status"] == 200

    def test_response_body_captured_in_entry(self) -> None:
        """Response JSON body is stored in the entry's body field."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"npc_response": "Hello, traveler."}
        inner = MagicMock()
        inner.post.return_value = resp

        recorder = TranscriptRecorder()
        wrapper = RecordingClientWrapper(inner, recorder)
        wrapper.post("/v1/dialogue", json={})

        assert recorder.entries[0]["body"] == {"npc_response": "Hello, traveler."}

    def test_returns_original_response(self) -> None:
        """Wrapper returns the original response object unchanged."""
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {}
        inner = MagicMock()
        inner.get.return_value = resp

        recorder = TranscriptRecorder()
        wrapper = RecordingClientWrapper(inner, recorder)
        result = wrapper.get("/v1/x")

        assert result is resp
