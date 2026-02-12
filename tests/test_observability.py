"""Tests for observability module."""

from __future__ import annotations

from core.observability import StatusStrip, system_status


def test_system_status_warmup():
    s = system_status(samples=2, slow_queries=0)
    assert s.status == "OK"
    assert "Warmup" in s.message


def test_system_status_nominal():
    s = system_status(samples=10, slow_queries=0)
    assert s.status == "OK"
    assert s.message == "Nominal"


def test_system_status_warn():
    s = system_status(samples=10, slow_queries=15)
    assert s.status == "WARN"
    assert "Slow query" in s.message


def test_status_strip_dataclass():
    ss = StatusStrip(status="OK", message="test")
    assert ss.status == "OK"
    assert ss.message == "test"
