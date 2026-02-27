from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any, Optional

from core.services.vdot_methodology import vdot_pace_band


_INTENT_TO_CODE = {
    "easy": "E",
    "endurance": "E",
    "recovery": "E",
    "long_run": "E",
    "marathon": "M",
    "marathon_pace": "M",
    "race_pace": "M",
    "threshold": "T",
    "tempo": "T",
    "lactate_threshold": "T",
    "vo2": "I",
    "interval": "I",
    "intervals": "I",
    "aerobic_power": "I",
    "speed": "R",
    "repetition": "R",
    "neuromuscular": "R",
}

_ZONE_TO_CODE = {
    "Z1": "E",
    "Z2": "E",
    "Z3": "M",
    "Z4": "T",
    "Z5": "I",
}


def _infer_code_from_template_context(
    *,
    target: dict[str, Any],
    block_phase: str,
    template_intent: str,
    session_name: str,
) -> Optional[str]:
    raw = str(target.get("intensity_code") or "").strip().upper()
    if raw in {"E", "M", "T", "I", "R"}:
        return raw

    phase = str(block_phase or "").strip().lower()
    if phase in {"warmup", "cooldown"}:
        return "E"

    # Prefer template intent/name heuristics before pace-zone fallback so legacy
    # templates with generic Z3 main sets (e.g. Easy/Recovery defaults) don't
    # get misclassified as marathon-pace sessions.
    intent_token = str(template_intent or "").strip().lower()
    for key, code in _INTENT_TO_CODE.items():
        if key in intent_token:
            return code

    name_token = str(session_name or "").strip().lower()
    for key, code in _INTENT_TO_CODE.items():
        if key.replace("_", " ") in name_token or key in name_token:
            return code

    pace_zone = str(target.get("pace_zone") or "").strip().upper()
    if pace_zone in _ZONE_TO_CODE:
        code = _ZONE_TO_CODE[pace_zone]
        if code == "M":
            if any(key in intent_token for key in ("threshold", "tempo")):
                return "T"
        return code

    return None


def compile_session_for_athlete(
    *,
    structure_json: dict[str, Any],
    athlete_id: int,
    session_name: str,
    template_name: Optional[str] = None,
    template_intent: str = "",
    vdot: Optional[float] = None,
    context: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    session = deepcopy(structure_json or {})
    blocks = list(session.get("blocks") or [])

    for block in blocks:
        if not isinstance(block, dict):
            continue
        target = dict(block.get("target") or {})
        code = _infer_code_from_template_context(
            target=target,
            block_phase=str(block.get("phase") or ""),
            template_intent=template_intent,
            session_name=session_name,
        )
        if code:
            target["intensity_code"] = code
        if code and vdot is not None:
            band = vdot_pace_band(float(vdot), code)
            if band is not None:
                target["vdot_pace_band"] = {
                    "code": str(band["code"]),
                    "fast_sec_per_km": int(band["fast_sec_per_km"]),
                    "slow_sec_per_km": int(band["slow_sec_per_km"]),
                    "display": str(band["display"]),
                    "methodology": "daniels_vdot",
                }
        block["target"] = target

    session["blocks"] = blocks
    session["compiler_meta"] = {
        "methodology": "daniels_vdot",
        "athlete_id": int(athlete_id),
        "session_name": str(session_name or ""),
        "template_name": str(template_name or ""),
        "template_intent": str(template_intent or ""),
        "vdot": (round(float(vdot), 2) if vdot is not None else None),
        "compiled_at": datetime.utcnow().isoformat(),
        "context": dict(context or {}),
    }
    return session
