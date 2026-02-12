"""Tests for events service."""

from __future__ import annotations

from datetime import date, timedelta

from core.services.events import days_to_event


def test_days_to_event_future():
    today = date(2026, 6, 1)
    event = date(2026, 6, 15)
    assert days_to_event(event, today) == 14


def test_days_to_event_today():
    today = date(2026, 6, 1)
    assert days_to_event(today, today) == 0


def test_days_to_event_past():
    today = date(2026, 6, 15)
    event = date(2026, 6, 1)
    assert days_to_event(event, today) == -14


def test_days_to_event_default_today():
    event = date.today() + timedelta(days=7)
    assert days_to_event(event) == 7
