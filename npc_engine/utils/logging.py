"""
logging.py - Configures structured application logging with prompt redaction control.

Does NOT: emit business events or persist logs externally.

Dependencies injected: None.
"""

import json
import logging
from datetime import datetime, timezone


LOGGER_NAME = "npc_engine"


class JsonFormatter(logging.Formatter):
    """Formats log records as JSON for structured observability."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=True)


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
