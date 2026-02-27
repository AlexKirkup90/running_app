from __future__ import annotations

import math
from typing import Any

from core.services.analytics import estimate_vdot


TARGET_DISTANCES_KM = {
    "5K": 5.0,
    "10K": 10.0,
    "Half Marathon": 21.0975,
    "Marathon": 42.195,
}


def _format_hhmmss(total_seconds: float) -> str:
    seconds = max(1, int(round(total_seconds)))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:d}:{s:02d}"


def _riegel_predict_seconds(benchmark_distance_km: float, benchmark_seconds: float, target_distance_km: float, exponent: float = 1.06) -> float:
    return float(benchmark_seconds) * ((float(target_distance_km) / float(benchmark_distance_km)) ** float(exponent))


def _vdot_vo2(speed_m_per_min: float) -> float:
    return -4.60 + (0.182258 * speed_m_per_min) + (0.000104 * (speed_m_per_min**2))


def _vdot_percent_vo2max(time_min: float) -> float:
    return 0.8 + (0.1894393 * math.exp(-0.012778 * time_min)) + (0.2989558 * math.exp(-0.1932605 * time_min))


def _predict_time_from_vdot(vdot: float, distance_km: float) -> float | None:
    if not vdot or vdot <= 0 or not distance_km or distance_km <= 0:
        return None
    distance_m = float(distance_km) * 1000.0
    lo, hi = 6.0, 400.0  # minutes
    for _ in range(50):
        mid = (lo + hi) / 2.0
        speed = distance_m / mid
        predicted_vdot = _vdot_vo2(speed) / _vdot_percent_vo2max(mid)
        if predicted_vdot > vdot:
            lo = mid
        else:
            hi = mid
    return round(hi * 60.0, 1)


def _coerce_benchmark(benchmark: dict[str, Any] | None) -> dict[str, Any] | None:
    if not benchmark:
        return None
    try:
        distance_km = float(benchmark.get("distance_km") or 0.0)
        duration_min = float(benchmark.get("duration_min") or 0.0)
    except Exception:
        return None
    if distance_km <= 0 or duration_min <= 0:
        return None
    return {
        **benchmark,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "duration_seconds": duration_min * 60.0,
    }


def predict_all_distances(benchmark: dict[str, Any] | None) -> dict[str, Any]:
    bmk = _coerce_benchmark(benchmark)
    if bmk is None:
        return {
            "method": "unavailable",
            "vdot": None,
            "benchmark_distance_km": None,
            "benchmark_time": None,
            "distances": {},
        }

    benchmark_distance_km = float(bmk["distance_km"])
    benchmark_seconds = float(bmk["duration_seconds"])
    vdot = estimate_vdot(benchmark_distance_km, float(bmk["duration_min"]))
    predictions: dict[str, Any] = {}
    for label, target_km in TARGET_DISTANCES_KM.items():
        riegel_sec = _riegel_predict_seconds(benchmark_distance_km, benchmark_seconds, target_km)
        daniels_sec = _predict_time_from_vdot(float(vdot), target_km) if vdot is not None else None
        if daniels_sec is None:
            blended = riegel_sec
            method = "riegel"
        else:
            # Blend both models to dampen extrapolation error.
            blended = (0.55 * daniels_sec) + (0.45 * riegel_sec)
            method = "blended_vdot_riegel"
        predictions[label] = {
            "distance_km": round(target_km, 3),
            "predicted_seconds": int(round(blended)),
            "predicted_time": _format_hhmmss(blended),
            "riegel_seconds": int(round(riegel_sec)),
            "daniels_seconds": int(round(daniels_sec)) if daniels_sec is not None else None,
            "method": method,
        }

    return {
        "method": "blended_vdot_riegel" if vdot is not None else "riegel",
        "vdot": vdot,
        "benchmark_distance_km": round(benchmark_distance_km, 3),
        "benchmark_time": _format_hhmmss(benchmark_seconds),
        "distances": predictions,
    }
