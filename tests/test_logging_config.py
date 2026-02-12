"""Tests for structured logging configuration."""

from __future__ import annotations

import json
import logging

from core.logging_config import JSONFormatter, get_logger, setup_logging


def test_json_formatter_outputs_valid_json():
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="test.py",
        lineno=1, msg="hello %s", args=("world",), exc_info=None
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["message"] == "hello world"
    assert parsed["level"] == "INFO"
    assert parsed["logger"] == "test"
    assert "timestamp" in parsed


def test_json_formatter_includes_exception():
    formatter = JSONFormatter()
    try:
        raise ValueError("test error")
    except ValueError:
        import sys
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="test.py",
        lineno=1, msg="fail", args=(), exc_info=exc_info
    )
    result = formatter.format(record)
    parsed = json.loads(result)
    assert parsed["exception"]["type"] == "ValueError"
    assert parsed["exception"]["message"] == "test error"


def test_get_logger_returns_named_logger():
    log = get_logger("my.module")
    assert log.name == "my.module"
    assert isinstance(log, logging.Logger)


def test_setup_logging_idempotent():
    root = logging.getLogger()
    initial_count = len(root.handlers)
    setup_logging()
    setup_logging()
    # Should not add duplicate handlers
    assert len(root.handlers) <= initial_count + 1
