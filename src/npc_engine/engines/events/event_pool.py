"""
event_pool.py - Loads weighted event templates from JSON file.
Layer: engines
Purpose: (auto-detected — review)

Does NOT: persist generated events.

Dependencies injected: event_pool_path.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class EventTemplate(BaseModel):
    """One event template row from event pool file."""

    id: str
    weight: int = Field(ge=1)
    severity: int = Field(ge=0, le=100)
    location_tag: str
    summary_template: str
    event_type: str
    faction_id: str | None = None
    reputation_delta: int | None = None

    model_config = ConfigDict(frozen=True)


def load_event_pool(path: str) -> list[EventTemplate]:
    """Load and validate event templates from a JSON file.

    Args:
        path: Filesystem path to the event pool JSON file.

    Returns:
        List of validated EventTemplate instances.

    Raises:
        ValueError: If the JSON root is not a list.
        FileNotFoundError: If the file does not exist at path.
        json.JSONDecodeError: If the file content is not valid JSON.
    """

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("event_pool.json must contain a list")
    return [EventTemplate.model_validate(item) for item in payload]
