"""
Module: transcript
Layer: demo_game (runners)
Purpose: TranscriptRecorder captures HTTP request/response pairs as JSONL entries.
         RecordingClientWrapper intercepts httpx-style HTTP calls and forwards each
         to a TranscriptRecorder so callers need no extra instrumentation.
Dependencies: json, pathlib
Used by: demo_game.runners.run (DemoRunner)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TranscriptRecorder:
    """Append-only log of HTTP request/response pairs as JSONL entries.

    Each entry carries: method, path, status, body.  Entries are kept in
    memory and, when a *path* is provided, also written to a JSONL file.
    """

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else None
        self._entries: list[dict[str, Any]] = []

    def record(self, method: str, path: str, status: int, body: object) -> None:
        """Append one entry for a completed HTTP request/response pair.

        Args:
            method: HTTP verb (GET, POST, PATCH, …).
            path: Request path, e.g. ``/v1/dialogue``.
            status: HTTP status code of the response.
            body: Parsed JSON body of the response, or a fallback string excerpt.
        """
        entry: dict[str, Any] = {
            "method": method,
            "path": path,
            "status": status,
            "body": body,
        }
        self._entries.append(entry)
        if self._path is not None:
            with self._path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry) + "\n")

    @property
    def entries(self) -> list[dict[str, Any]]:
        """Return a shallow copy of all recorded entries."""
        return list(self._entries)


class RecordingClientWrapper:
    """Duck-typed wrapper around an httpx.Client that records every call.

    Intercepts ``get``, ``post``, and ``patch`` calls, delegates to the
    wrapped client, then appends one entry per call to *recorder*.  The
    original response object is returned unchanged so callers behave
    identically with or without recording.

    Args:
        inner: The real httpx.Client (or any compatible duck-typed client).
        recorder: Transcript sink that receives each completed call.
    """

    def __init__(self, inner: Any, recorder: TranscriptRecorder) -> None:
        self._inner = inner
        self._recorder = recorder

    def _capture(self, method: str, url: str, resp: Any) -> Any:
        try:
            body: object = resp.json()
        except Exception:
            body = resp.text[:500]
        self._recorder.record(method=method, path=str(url), status=resp.status_code, body=body)
        return resp

    def get(self, url: str, **kwargs: Any) -> Any:
        """Delegate to inner.get and record the result."""
        return self._capture("GET", url, self._inner.get(url, **kwargs))

    def post(self, url: str, **kwargs: Any) -> Any:
        """Delegate to inner.post and record the result."""
        return self._capture("POST", url, self._inner.post(url, **kwargs))

    def patch(self, url: str, **kwargs: Any) -> Any:
        """Delegate to inner.patch and record the result."""
        return self._capture("PATCH", url, self._inner.patch(url, **kwargs))
