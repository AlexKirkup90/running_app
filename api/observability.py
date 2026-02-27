from __future__ import annotations

import contextvars
import json
import logging
import sys
import time
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4


_request_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)
_logging_configured = False
_STANDARD_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())


def get_request_id() -> Optional[str]:
    return _request_id_var.get()


def set_request_id(value: Optional[str]):
    return _request_id_var.set(value)


def reset_request_id(token) -> None:
    _request_id_var.reset(token)


def new_request_id() -> str:
    return uuid4().hex


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_FIELDS or key.startswith("_"):
                continue
            if key in payload:
                continue
            payload[key] = value
        return json.dumps(payload, default=str, separators=(",", ":"))


def configure_logging(level: str = "INFO") -> None:
    global _logging_configured
    if _logging_configured:
        return

    root = logging.getLogger()
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))

    # Replace default handler setup so app logs are consistently structured in local/dev/prod.
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True

    _logging_configured = True


def request_log_fields(*, method: str, path: str, status_code: int, duration_ms: float, client_ip: Optional[str]) -> dict[str, object]:
    return {
        "method": method,
        "path": path,
        "status_code": int(status_code),
        "duration_ms": round(float(duration_ms), 2),
        "client_ip": client_ip or "",
    }


def monotonic_ms() -> float:
    return time.perf_counter() * 1000.0
