"""Tests for race time prediction module."""

from __future__ import annotations

from core.services.race_predictor import (
    RacePrediction,
    predict_all_distances,
    predict_race,
    predict_riegel,
    predict_vdot,
)


def test_riegel_5k_to_10k():
    # 20 min 5K → should predict roughly 41-42 min 10K
    predicted = predict_riegel(5000, 20 * 60, 10000)
    assert 40 * 60 < predicted < 43 * 60


def test_riegel_10k_to_half():
    # 42 min 10K → should predict roughly 1:32-1:35 half
    predicted = predict_riegel(10000, 42 * 60, 21097.5)
    assert 90 * 60 < predicted < 100 * 60


def test_riegel_invalid():
    assert predict_riegel(0, 100, 5000) == 0.0
    assert predict_riegel(5000, 0, 10000) == 0.0


def test_predict_vdot_5k():
    # VDOT 50 → ~19:30-20:30 5K
    predicted = predict_vdot(50, 5000)
    assert 18 * 60 < predicted < 22 * 60


def test_predict_vdot_marathon():
    # VDOT 50 → ~3:00-3:40 marathon range (iterative solver)
    predicted = predict_vdot(50, 42195)
    assert 2.75 * 3600 < predicted < 4 * 3600


def test_predict_vdot_invalid():
    assert predict_vdot(0, 5000) == 0.0
    assert predict_vdot(50, 0) == 0.0


def test_predict_race_returns_both_methods():
    results = predict_race("5K", 20 * 60, "10K")
    assert len(results) == 2
    methods = {r.method for r in results}
    assert "riegel" in methods
    assert "vdot" in methods


def test_predict_race_invalid_distance():
    results = predict_race("50K", 100, "10K")
    assert results == []


def test_predict_race_data_fields():
    results = predict_race("5K", 20 * 60, "10K")
    for r in results:
        assert isinstance(r, RacePrediction)
        assert r.distance_label == "10K"
        assert r.predicted_seconds > 0
        assert len(r.predicted_display) > 0


def test_predict_all_distances():
    results = predict_all_distances("5K", 20 * 60)
    assert "10K" in results
    assert "Half Marathon" in results
    assert "Marathon" in results
    assert "5K" not in results  # Excludes source distance
    for preds in results.values():
        assert len(preds) == 2  # Riegel + VDOT


def test_predictions_increase_with_distance():
    results = predict_all_distances("5K", 20 * 60)
    times_riegel = {}
    for label, preds in results.items():
        for p in preds:
            if p.method == "riegel":
                times_riegel[label] = p.predicted_seconds
    assert times_riegel["10K"] > 20 * 60
    assert times_riegel["Half Marathon"] > times_riegel["10K"]
    assert times_riegel["Marathon"] > times_riegel["Half Marathon"]
