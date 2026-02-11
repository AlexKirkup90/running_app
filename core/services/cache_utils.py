from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class CacheCounter:
    hits: int = 0
    misses: int = 0


_cache: dict[str, tuple[float, object]] = {}
counter = CacheCounter()


def ttl_get(key: str, ttl_s: int):
    item = _cache.get(key)
    if not item:
        counter.misses += 1
        return None
    ts, val = item
    if time.time() - ts > ttl_s:
        counter.misses += 1
        return None
    counter.hits += 1
    return val


def ttl_set(key: str, value: object):
    _cache[key] = (time.time(), value)
