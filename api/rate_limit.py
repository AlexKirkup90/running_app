from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request, status

_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def enforce_rate_limit(request: Request, key: str, max_requests: int, window_seconds: int) -> None:
    now = time.time()
    ip = request.client.host if request.client else "unknown"
    bucket = _BUCKETS[f"{key}:{ip}"]
    while bucket and now - bucket[0] > window_seconds:
        bucket.popleft()
    if len(bucket) >= max_requests:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
    bucket.append(now)
