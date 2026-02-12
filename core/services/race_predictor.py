"""Race time prediction using Riegel formula and VDOT-based estimates.

Provides two complementary prediction methods:
- Riegel: simple power-law extrapolation from one race to another distance
- VDOT: uses Daniels' oxygen cost model for physiologically-grounded predictions
"""

from __future__ import annotations

from dataclasses import dataclass

from core.services.vdot import (
    RACE_DISTANCES_M,
    _percent_max,
    _vo2_from_velocity,
    estimate_vdot,
    get_paces,
)


@dataclass(frozen=True)
class RacePrediction:
    """Predicted finish time for a target distance."""
    distance_label: str
    distance_m: float
    predicted_seconds: float
    predicted_display: str
    method: str
    vdot_used: int | None = None


def _format_time(seconds: float) -> str:
    """Format seconds as H:MM:SS or M:SS."""
    total = int(round(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def predict_riegel(
    known_distance_m: float,
    known_time_seconds: float,
    target_distance_m: float,
    fatigue_factor: float = 1.06,
) -> float:
    """Predict finish time using Riegel's formula: T2 = T1 * (D2/D1)^fatigue_factor.

    Default fatigue_factor=1.06 is standard; adjust 1.07-1.08 for less trained runners.
    """
    if known_distance_m <= 0 or known_time_seconds <= 0 or target_distance_m <= 0:
        return 0.0
    ratio = target_distance_m / known_distance_m
    return known_time_seconds * (ratio ** fatigue_factor)


def predict_vdot(vdot: int, target_distance_m: float) -> float:
    """Predict finish time from VDOT using the Daniels/Gilbert VO2 model.

    Iteratively solves for time given VDOT and distance using the oxygen
    cost and percent-max equations.
    """
    if vdot <= 0 or target_distance_m <= 0:
        return 0.0

    paces = get_paces(vdot)
    # Initial estimate: marathon pace * distance ratio
    est_seconds = paces.marathon * (target_distance_m / 1000.0)

    # Newton-ish iteration: solve for time where estimated VDOT matches target
    for _ in range(50):
        t_min = est_seconds / 60.0
        if t_min <= 0:
            break
        velocity = target_distance_m / t_min
        vo2 = _vo2_from_velocity(velocity)
        pct = _percent_max(t_min)
        if pct <= 0:
            break
        est_vdot = vo2 / pct
        error = est_vdot - vdot
        if abs(error) < 0.05:
            break
        # Adjust: if estimated VDOT is too high, we're running too fast → slow down
        est_seconds *= 1 + error * 0.01

    return max(0.0, round(est_seconds, 1))


def predict_race(
    known_distance_label: str,
    known_time_seconds: float,
    target_distance_label: str,
) -> list[RacePrediction]:
    """Generate race predictions for a target distance using both methods.

    Returns a list with Riegel and VDOT predictions.
    """
    known_m = RACE_DISTANCES_M.get(known_distance_label)
    target_m = RACE_DISTANCES_M.get(target_distance_label)
    if known_m is None or target_m is None:
        return []

    results = []

    # Riegel prediction
    riegel_secs = predict_riegel(known_m, known_time_seconds, target_m)
    results.append(RacePrediction(
        distance_label=target_distance_label,
        distance_m=target_m,
        predicted_seconds=riegel_secs,
        predicted_display=_format_time(riegel_secs),
        method="riegel",
    ))

    # VDOT prediction
    vdot = round(estimate_vdot(known_m, known_time_seconds))
    vdot_secs = predict_vdot(vdot, target_m)
    results.append(RacePrediction(
        distance_label=target_distance_label,
        distance_m=target_m,
        predicted_seconds=vdot_secs,
        predicted_display=_format_time(vdot_secs),
        method="vdot",
        vdot_used=vdot,
    ))

    return results


def predict_all_distances(
    known_distance_label: str,
    known_time_seconds: float,
    vdot_override: int | None = None,
) -> dict[str, list[RacePrediction]]:
    """Predict times for all standard distances from a single race result.

    If vdot_override is provided, uses that VDOT directly instead of
    estimating from the known result (useful when only VDOT is available).
    """
    results: dict[str, list[RacePrediction]] = {}
    for target_label in RACE_DISTANCES_M:
        if target_label == known_distance_label:
            continue
        if vdot_override and known_time_seconds <= 0:
            # VDOT-only mode: skip Riegel, use VDOT prediction directly
            target_m = RACE_DISTANCES_M[target_label]
            vdot_secs = predict_vdot(vdot_override, target_m)
            results[target_label] = [RacePrediction(
                distance_label=target_label,
                distance_m=target_m,
                predicted_seconds=vdot_secs,
                predicted_display=_format_time(vdot_secs),
                method="vdot",
                vdot_used=vdot_override,
            )]
        else:
            preds = predict_race(known_distance_label, known_time_seconds, target_label)
            if preds:
                results[target_label] = preds
    return results
