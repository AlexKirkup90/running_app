"""Adaptive plan modification: auto-adjusts future weeks based on actual performance.

Compares actual vs planned load over recent weeks and triggers adjustments:
- Underperformance (< 70% adherence x2 weeks): insert recovery, compress remaining
- Overperformance (> 110% planned load x2 weeks): consider advancing phase transition
- Pain cluster detection: inject protective recovery week
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class PlanAdjustment:
    """A recommended adjustment to a training plan."""
    adjustment_type: str    # "insert_recovery", "compress", "advance_phase", "reduce_volume", "no_change"
    reason: str
    affected_weeks: list[int]  # week numbers to modify
    volume_factor: float = 1.0  # multiply target_load by this factor
    phase_override: str | None = None


def assess_adherence_trend(
    weekly_actual_loads: list[float],
    weekly_planned_loads: list[float],
) -> list[float]:
    """Compute per-week adherence ratios (actual / planned).

    Returns a list of ratios (0.0 to unbounded). 1.0 = perfect adherence.
    """
    ratios = []
    for actual, planned in zip(weekly_actual_loads, weekly_planned_loads):
        if planned > 0:
            ratios.append(round(actual / planned, 2))
        elif actual > 0:
            ratios.append(1.5)  # did work with no plan = overperformance
        else:
            ratios.append(0.0)
    return ratios


def detect_pain_cluster(pain_flags_14d: list[bool]) -> bool:
    """Detect a pain cluster: 3+ pain flags in the last 14 days."""
    return sum(1 for p in pain_flags_14d if p) >= 3


def recommend_adjustments(
    adherence_ratios: list[float],
    current_week: int,
    total_weeks: int,
    pain_cluster: bool = False,
    current_phase: str = "Base",
) -> list[PlanAdjustment]:
    """Analyse recent adherence and return recommended plan adjustments.

    Looks at the most recent 2-3 weeks of adherence ratios to decide
    whether to insert recovery weeks, reduce volume, or advance phases.
    """
    adjustments: list[PlanAdjustment] = []
    remaining = total_weeks - current_week

    if remaining <= 2:
        # Too close to race to adjust
        return [PlanAdjustment(adjustment_type="no_change", reason="Too close to race for adjustments", affected_weeks=[])]

    recent = adherence_ratios[-2:] if len(adherence_ratios) >= 2 else adherence_ratios
    recent_3 = adherence_ratios[-3:] if len(adherence_ratios) >= 3 else adherence_ratios

    # Pain cluster: immediate recovery
    if pain_cluster:
        adjustments.append(PlanAdjustment(
            adjustment_type="insert_recovery",
            reason="Pain cluster detected (3+ pain flags in 14 days). Inserting protective recovery week.",
            affected_weeks=[current_week + 1],
            volume_factor=0.6,
            phase_override="Recovery",
        ))
        return adjustments

    # Severe underperformance: < 70% adherence for 2 consecutive weeks
    if len(recent) >= 2 and all(r < 0.7 for r in recent):
        adjustments.append(PlanAdjustment(
            adjustment_type="insert_recovery",
            reason=f"Adherence below 70% for 2 consecutive weeks ({recent}). Inserting recovery week.",
            affected_weeks=[current_week + 1],
            volume_factor=0.65,
            phase_override="Recovery",
        ))
        # Also reduce next 2 weeks
        adjustments.append(PlanAdjustment(
            adjustment_type="reduce_volume",
            reason="Post-recovery volume reduction to rebuild consistency.",
            affected_weeks=[current_week + 2, current_week + 3],
            volume_factor=0.85,
        ))
        return adjustments

    # Moderate underperformance: < 80% for 3 weeks
    if len(recent_3) >= 3 and all(r < 0.8 for r in recent_3):
        adjustments.append(PlanAdjustment(
            adjustment_type="reduce_volume",
            reason=f"Adherence below 80% for 3 weeks ({recent_3}). Reducing upcoming volume.",
            affected_weeks=list(range(current_week + 1, min(current_week + 4, total_weeks + 1))),
            volume_factor=0.85,
        ))
        return adjustments

    # Overperformance: > 110% for 2 weeks with good phases remaining
    if len(recent) >= 2 and all(r > 1.1 for r in recent) and current_phase in ("Base", "Build"):
        adjustments.append(PlanAdjustment(
            adjustment_type="advance_phase",
            reason=f"Consistent overperformance ({recent}). Consider advancing to next phase.",
            affected_weeks=[current_week + 1],
            volume_factor=1.05,
        ))
        return adjustments

    return [PlanAdjustment(adjustment_type="no_change", reason="Adherence on track, no adjustments needed.", affected_weeks=[])]


def apply_volume_adjustment(
    week_data: dict[str, Any],
    volume_factor: float,
    phase_override: str | None = None,
) -> dict[str, Any]:
    """Apply a volume adjustment to a plan week dict.

    Multiplies target_load by volume_factor and optionally overrides the phase.
    """
    adjusted = dict(week_data)
    adjusted["target_load"] = round(week_data.get("target_load", 0) * volume_factor, 1)
    if phase_override:
        adjusted["phase"] = phase_override
    return adjusted
