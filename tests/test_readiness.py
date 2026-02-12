"""Tests for readiness scoring service."""

from __future__ import annotations

from core.services.readiness import readiness_band, readiness_score


def test_readiness_score_high():
    score = readiness_score(5, 5, 5, 1)
    assert score == 5.0


def test_readiness_score_low():
    score = readiness_score(1, 1, 1, 5)
    assert score == 1.0


def test_readiness_score_mid():
    score = readiness_score(3, 3, 3, 3)
    assert score == 3.0


def test_readiness_score_formula():
    # (4 + 3 + 5 + (6-2)) / 4 = (4+3+5+4)/4 = 16/4 = 4.0
    score = readiness_score(4, 3, 5, 2)
    assert score == 4.0


def test_readiness_band_green():
    assert readiness_band(4.0) == "green"
    assert readiness_band(5.0) == "green"


def test_readiness_band_amber():
    assert readiness_band(3.0) == "amber"
    assert readiness_band(3.5) == "amber"


def test_readiness_band_red():
    assert readiness_band(2.9) == "red"
    assert readiness_band(1.0) == "red"
