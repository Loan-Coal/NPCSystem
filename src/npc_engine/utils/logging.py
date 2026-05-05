"""
logging.py - Configures structured application logging with prompt redaction control.

Does NOT: emit business events or persist logs externally.

Dependencies injected: None.
"""

import json
import logging
from datetime import datetime, timezone


LOGGER_NAME = "npc_engine"

RESERVED_LOG_RECORD_FIELDS = {
    "name",
    "msg",
    "args",
    "levelname",
    "levelno",
    "pathname",
    "filename",
    "module",
    "exc_info",
    "exc_text",
    "stack_info",
    "lineno",
    "funcName",
    "created",
    "msecs",
    "relativeCreated",
    "thread",
    "threadName",
    "processName",
    "process",
    "message",
}


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON for structured observability."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, str | int | float | bool] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        payload.update(_extract_extra_fields(record=record))
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


def _extract_extra_fields(record: logging.LogRecord) -> dict[str, str | int | float | bool]:
    """Extract user-provided extra logging fields from one record."""

    payload: dict[str, str | int | float | bool] = {}
    for key, value in record.__dict__.items():
        if key in RESERVED_LOG_RECORD_FIELDS:
            continue
        if isinstance(value, (str, int, float, bool)):
            payload[key] = value
        else:
            payload[key] = str(value)
    return payload


def configure_logging(level: str) -> None:
    """Configure root logging once using a JSON formatter."""

    root_logger = logging.getLogger(LOGGER_NAME)
    root_logger.handlers.clear()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    root_logger.propagate = False


def get_logger(name: str = LOGGER_NAME) -> logging.Logger:
    """Return a module logger."""

    return logging.getLogger(name)
