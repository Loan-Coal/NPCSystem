"""
event_pool.py - Loads weighted event templates from JSON file.

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

    model_config = ConfigDict(frozen=True)


def load_event_pool(path: str) -> list[EventTemplate]:
    """Load and validate event templates from JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("event_pool.json must contain a list")
    return [EventTemplate.model_validate(item) for item in payload]
