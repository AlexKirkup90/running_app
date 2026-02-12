"""Tests for adaptive plan modification."""

from __future__ import annotations

from core.services.plan_adjuster import (
    apply_volume_adjustment,
    assess_adherence_trend,
    detect_pain_cluster,
    recommend_adjustments,
)


def test_assess_adherence_trend_perfect():
    actual = [100, 200, 150]
    planned = [100, 200, 150]
    ratios = assess_adherence_trend(actual, planned)
    assert ratios == [1.0, 1.0, 1.0]


def test_assess_adherence_trend_underperformance():
    actual = [50, 80]
    planned = [100, 200]
    ratios = assess_adherence_trend(actual, planned)
    assert ratios == [0.5, 0.4]


def test_assess_adherence_trend_overperformance():
    actual = [150, 250]
    planned = [100, 200]
    ratios = assess_adherence_trend(actual, planned)
    assert ratios == [1.5, 1.25]


def test_assess_adherence_no_plan():
    actual = [100, 0]
    planned = [0, 0]
    ratios = assess_adherence_trend(actual, planned)
    assert ratios[0] == 1.5  # work with no plan = overperformance
    assert ratios[1] == 0.0


def test_detect_pain_cluster_true():
    flags = [True, False, True, True, False, False, False, False, False, False, False, False, False, False]
    assert detect_pain_cluster(flags) is True


def test_detect_pain_cluster_false():
    flags = [True, False, True, False, False, False, False, False, False, False, False, False, False, False]
    assert detect_pain_cluster(flags) is False


def test_recommend_no_change():
    ratios = [0.95, 0.90, 1.0]
    adjustments = recommend_adjustments(ratios, current_week=5, total_weeks=16)
    assert len(adjustments) == 1
    assert adjustments[0].adjustment_type == "no_change"


def test_recommend_recovery_on_severe_underperformance():
    ratios = [0.85, 0.6, 0.5]
    adjustments = recommend_adjustments(ratios, current_week=5, total_weeks=16)
    types = {a.adjustment_type for a in adjustments}
    assert "insert_recovery" in types


def test_recommend_volume_reduction_on_moderate_underperformance():
    ratios = [0.75, 0.78, 0.72]
    adjustments = recommend_adjustments(ratios, current_week=5, total_weeks=16)
    types = {a.adjustment_type for a in adjustments}
    assert "reduce_volume" in types


def test_recommend_advance_on_overperformance():
    ratios = [1.15, 1.2]
    adjustments = recommend_adjustments(ratios, current_week=5, total_weeks=16, current_phase="Base")
    types = {a.adjustment_type for a in adjustments}
    assert "advance_phase" in types


def test_recommend_recovery_on_pain_cluster():
    ratios = [0.95, 0.90]
    adjustments = recommend_adjustments(ratios, current_week=5, total_weeks=16, pain_cluster=True)
    assert adjustments[0].adjustment_type == "insert_recovery"
    assert adjustments[0].volume_factor == 0.6
    assert adjustments[0].phase_override == "Recovery"


def test_recommend_no_change_near_race():
    ratios = [0.5, 0.4]  # Would normally trigger recovery
    adjustments = recommend_adjustments(ratios, current_week=14, total_weeks=16)
    assert adjustments[0].adjustment_type == "no_change"
    assert "Too close" in adjustments[0].reason


def test_apply_volume_adjustment():
    week = {"week_number": 5, "phase": "Build", "target_load": 1000.0}
    adjusted = apply_volume_adjustment(week, 0.85)
    assert adjusted["target_load"] == 850.0
    assert adjusted["phase"] == "Build"  # No override


def test_apply_volume_adjustment_with_phase_override():
    week = {"week_number": 5, "phase": "Build", "target_load": 1000.0}
    adjusted = apply_volume_adjustment(week, 0.65, phase_override="Recovery")
    assert adjusted["target_load"] == 650.0
    assert adjusted["phase"] == "Recovery"
