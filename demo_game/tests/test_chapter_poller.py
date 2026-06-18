"""
Module: test_chapter_poller
Layer: demo_game (tests)
Purpose: Unit tests for ChapterPoller.
         No pygame, no network — all engine calls are mocked.
Dependencies: demo_game.chapter_poller, demo_game.client, unittest.mock
Used by: make test-demo
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from demo_game.client import EngineClientError
from demo_game.chapter_poller import ChapterPoller


def _make_client(
    chapter: dict | None = None,
    raises: Exception | None = None,
) -> MagicMock:
    """Return a mock EngineClient with controlled return values."""
    client = MagicMock()
    if raises is not None:
        client.get_current_chapter.side_effect = raises
    else:
        client.get_current_chapter.return_value = chapter
    return client


_SAMPLE_CHAPTER = {
    "id": "chapter_01",
    "name": "The Shadow Conspiracy",
    "started_at_tick": 0,
    "theme": "intrigue",
    "status": "open",
}


class TestChapterPollerInitialState:
    def test_initial_chapter_none(self) -> None:
        """get_chapter() returns None before any poll."""
        poller = ChapterPoller(_make_client(), interval_s=999.0)
        assert poller.get_chapter() is None


class TestChapterPollerPollOnce:
    def test_poll_once_stores_chapter(self) -> None:
        """_poll_once stores the chapter dict from the client."""
        client = _make_client(chapter=_SAMPLE_CHAPTER)
        poller = ChapterPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_chapter() == _SAMPLE_CHAPTER

    def test_poll_once_stores_none_when_no_chapter(self) -> None:
        """_poll_once stores None when the client returns None."""
        client = _make_client(chapter=None)
        poller = ChapterPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_chapter() is None

    def test_poll_once_swallows_engine_client_error(self) -> None:
        """_poll_once does not raise on EngineClientError; chapter stays None."""
        client = _make_client(raises=EngineClientError("boom"))
        poller = ChapterPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_chapter() is None

    def test_poll_once_swallows_generic_exception(self) -> None:
        """_poll_once does not raise on any Exception."""
        client = _make_client(raises=RuntimeError("network down"))
        poller = ChapterPoller(client, interval_s=999.0)
        poller._poll_once()
        assert poller.get_chapter() is None

    def test_poll_once_overwrites_previous_chapter(self) -> None:
        """_poll_once replaces the previous chapter with a new one."""
        chapter_v1 = {**_SAMPLE_CHAPTER, "name": "Act I"}
        chapter_v2 = {**_SAMPLE_CHAPTER, "name": "Act II"}
        client = _make_client(chapter=chapter_v1)
        poller = ChapterPoller(client, interval_s=999.0)
        poller._poll_once()
        client.get_current_chapter.return_value = chapter_v2
        poller._poll_once()
        assert poller.get_chapter()["name"] == "Act II"  # type: ignore[index]


class TestChapterPollerThread:
    def test_start_launches_daemon_thread(self) -> None:
        """start() launches a daemon thread that is alive."""
        poller = ChapterPoller(_make_client(), interval_s=999.0)
        poller.start()
        assert poller._thread is not None
        assert poller._thread.daemon is True
        assert poller._thread.is_alive()
