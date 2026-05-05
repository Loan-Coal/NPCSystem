"""
test_logging.py - Unit tests for utils/logging.py.

Does NOT: test log output destinations or external log shipping.

Dependencies injected: None.
"""

# Tests for: utils.logging
# Coverage targets:
#   - JsonFormatter.format: happy path (valid JSON with required fields)
#   - JsonFormatter.format: exception info included when present
#   - _extract_extra_fields: reserved fields excluded, extra fields included
#   - configure_logging: idempotent (no duplicate handlers on repeated call)
#   - get_logger: returns Logger bound to correct name

import json
import logging

from npc_engine.utils.logging import JsonFormatter, configure_logging, get_logger, LOGGER_NAME


def test_json_formatter_emits_valid_json() -> None:
    """Format output must be parseable JSON."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="hello world", args=(), exc_info=None,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["message"] == "hello world"
    assert parsed["level"] == "INFO"
    assert "timestamp" in parsed


def test_json_formatter_includes_extra_fields() -> None:
    """Extra kwargs passed to logger must appear in the JSON output."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="tick done", args=(), exc_info=None,
    )
    record.npc_id = "npc_01"
    record.tick = 5
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["npc_id"] == "npc_01"
    assert parsed["tick"] == 5


def test_json_formatter_excludes_reserved_fields() -> None:
    """LogRecord internals must not leak into the JSON payload."""
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="/app/x.py", lineno=42,
        msg="test", args=(), exc_info=None,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert "pathname" not in parsed
    assert "lineno" not in parsed
    assert "args" not in parsed


def test_json_formatter_includes_exception_when_present() -> None:
    """Exception info must be included in JSON output when exc_info is set."""
    formatter = JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        exc_info = sys.exc_info()

    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="error occurred", args=(), exc_info=exc_info,
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert "exception" in parsed
    assert "ValueError" in parsed["exception"]


def test_configure_logging_is_idempotent() -> None:
    """Calling configure_logging twice must not add duplicate handlers."""
    configure_logging("INFO")
    configure_logging("INFO")
    logger = logging.getLogger(LOGGER_NAME)
    assert len(logger.handlers) == 1


def test_get_logger_returns_logger_with_correct_name() -> None:
    """get_logger() must return a Logger bound to the module name."""
    logger = get_logger("npc_engine.test")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "npc_engine.test"


def test_get_logger_defaults_to_npc_engine_name() -> None:
    """Default logger name must be LOGGER_NAME."""
    logger = get_logger()
    assert logger.name == LOGGER_NAME
