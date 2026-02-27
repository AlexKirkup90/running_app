from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
import logging
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class DispatchedEvent:
    event: str
    payload: dict[str, Any]
    created_at: datetime


class InternalWebhookDispatcher:
    def __init__(self, max_history: int = 500) -> None:
        self._subscribers: dict[str, list] = {}
        self._history: deque[DispatchedEvent] = deque(maxlen=max_history)
        self._lock = Lock()

    def subscribe(self, event: str, handler) -> None:
        with self._lock:
            handlers = self._subscribers.setdefault(event, [])
            handlers.append(handler)
            count = len(handlers)
        logger.info("internal_webhook_subscribed", extra={"event_name": event, "subscriber_count": count})

    def dispatch(self, event: str, payload: dict[str, Any]) -> None:
        record = DispatchedEvent(event=event, payload=payload, created_at=datetime.utcnow())
        with self._lock:
            self._history.append(record)
            handlers = list(self._subscribers.get(event, []))
            history_size = len(self._history)
        logger.info(
            "internal_webhook_dispatched",
            extra={
                "event_name": event,
                "subscriber_count": len(handlers),
                "history_size": history_size,
            },
        )
        for handler in handlers:
            handler(record)

    def history_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [asdict(item) for item in self._history]

    def clear_history(self) -> None:
        with self._lock:
            self._history.clear()
        logger.info("internal_webhook_history_cleared")


dispatcher = InternalWebhookDispatcher()
