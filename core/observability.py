from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StatusStrip:
    status: str
    message: str


def system_status(samples: int, slow_queries: int) -> StatusStrip:
    if samples < 5:
        return StatusStrip("OK", f"Warmup ({samples} samples)")
    if slow_queries > 10:
        return StatusStrip("WARN", "Slow query threshold exceeded")
    return StatusStrip("OK", "Nominal")
