from __future__ import annotations

from time import time


class TTLCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, object]] = {}

    def set(self, key: str, value: object) -> None:
        self._store[key] = (time(), value)

    def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        ts, val = item
        if time() - ts > self.ttl:
            self._store.pop(key, None)
            return None
        return val
