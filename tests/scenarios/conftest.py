"""
conftest.py - Shared fixtures for story/E2E scenario tests.

Provides base_url and transcript helpers. Scenarios are self-contained
and produce transcript files regardless of pass/fail.
"""

from __future__ import annotations

import os
from pathlib import Path

import httpx
import pytest


BASE_URL_ENV = "NPC_BASE_URL"
API_KEY_ENV = "NPC_API_KEY"
DEFAULT_BASE_URL = "http://localhost:8000"
TRANSCRIPTS_DIR = Path(__file__).resolve().parents[2] / "transcripts"


def pytest_addoption(parser):
    parser.addoption("--scenarios-only", action="store_true", default=False)


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--scenarios-only", default=False):
        skip = pytest.mark.skip(reason="scenario tests require --scenarios-only flag")
        for item in items:
            if "scenarios" in str(item.fspath):
                item.add_marker(skip)


@pytest.fixture(scope="session")
def base_url() -> str:
    return os.environ.get(BASE_URL_ENV, DEFAULT_BASE_URL)


@pytest.fixture(scope="session")
def api_key() -> str:
    return os.environ.get(API_KEY_ENV, "eval-key-change-me")


@pytest.fixture(scope="session")
def http_client(base_url: str, api_key: str) -> httpx.Client:
    with httpx.Client(
        base_url=base_url,
        headers={"X-API-Key": api_key},
        timeout=60.0,
    ) as client:
        yield client


@pytest.fixture(autouse=True, scope="session")
def ensure_transcripts_dir():
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
