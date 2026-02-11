from __future__ import annotations

import re
from typing import Any


ALLOWED_PHASES = {"warmup", "main_set", "cooldown", "strides", "drills"}
SPECIAL_ZONE_LABELS = {"Race Pace", "Benchmark", "Strides", "Hill Effort", "N/A"}
ZONE_TOKEN = re.compile(r"Z[1-5]")


def valid_zone_label(label: str) -> bool:
    text = (label or "").strip()
    if not text:
        return False
    if text in SPECIAL_ZONE_LABELS:
        return True
    tokens = ZONE_TOKEN.findall(text.upper())
    return bool(tokens)


def default_structure(duration_min: int) -> dict[str, Any]:
    total = max(20, int(duration_min))
    warmup = max(10, total // 5)
    cooldown = 8 if total >= 45 else 6
    main_set = max(8, total - warmup - cooldown)
    return {
        "version": 2,
        "blocks": [
            {
                "phase": "warmup",
                "duration_min": warmup,
                "instructions": "Easy jog + mobility drills.",
                "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]},
            },
            {
                "phase": "main_set",
                "duration_min": main_set,
                "instructions": "Primary quality work for the day.",
                "target": {"pace_zone": "Z3", "hr_zone": "Z3", "rpe_range": [6, 7]},
            },
            {
                "phase": "cooldown",
                "duration_min": cooldown,
                "instructions": "Easy jog + down-regulate breathing.",
                "target": {"pace_zone": "Z1", "hr_zone": "Z1", "rpe_range": [2, 3]},
            },
        ],
    }


def default_targets() -> dict[str, Any]:
    return {
        "primary": {"pace_zone": "Z2", "hr_zone": "Z2", "rpe_range": [3, 4]},
        "secondary": {"cadence_spm": [168, 182], "terrain": "flat_or_rolling"},
    }


def default_progression() -> dict[str, str]:
    return {
        "increase_one": "Add 5-10 min if readiness remains >= 3.5.",
        "increase_two": "Add one repeat in the main set when quality remains stable.",
    }


def default_regression() -> dict[str, str]:
    return {
        "reduce_one": "Reduce main-set volume by 15-20% on low readiness.",
        "reduce_two": "Swap to easy aerobic run when pain flag is present.",
    }


def _validate_rpe_range(value: Any, location: str, errors: list[str]) -> None:
    if not isinstance(value, list) or len(value) != 2:
        errors.append(f"{location}.rpe_range must be [low, high]")
        return
    try:
        low, high = int(value[0]), int(value[1])
    except Exception:
        errors.append(f"{location}.rpe_range must contain numeric values")
        return
    if low < 1 or high > 10 or low > high:
        errors.append(f"{location}.rpe_range must be 1..10 with low <= high")


def validate_structure_contract(structure_json: dict[str, Any], duration_min: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(structure_json, dict):
        return ["structure_json must be an object"]
    blocks = structure_json.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return ["structure_json.blocks must be a non-empty list"]

    phases_seen: set[str] = set()
    total_minutes = 0
    for idx, block in enumerate(blocks):
        prefix = f"structure_json.blocks[{idx}]"
        if not isinstance(block, dict):
            errors.append(f"{prefix} must be an object")
            continue
        phase = str(block.get("phase", "")).strip()
        if phase not in ALLOWED_PHASES:
            errors.append(f"{prefix}.phase must be one of {sorted(ALLOWED_PHASES)}")
        else:
            phases_seen.add(phase)

        try:
            minutes = int(block.get("duration_min"))
            if minutes <= 0:
                errors.append(f"{prefix}.duration_min must be > 0")
            total_minutes += max(minutes, 0)
        except Exception:
            errors.append(f"{prefix}.duration_min must be an integer")

        instructions = str(block.get("instructions", "")).strip()
        if len(instructions) < 8:
            errors.append(f"{prefix}.instructions must be descriptive (8+ chars)")

        target = block.get("target")
        if not isinstance(target, dict):
            errors.append(f"{prefix}.target must be an object")
            continue
        pace_zone = str(target.get("pace_zone", "")).strip()
        hr_zone = str(target.get("hr_zone", "")).strip()
        if not valid_zone_label(pace_zone):
            errors.append(f"{prefix}.target.pace_zone is invalid")
        if not valid_zone_label(hr_zone):
            errors.append(f"{prefix}.target.hr_zone is invalid")
        _validate_rpe_range(target.get("rpe_range"), f"{prefix}.target", errors)

    required_phases = {"warmup", "main_set", "cooldown"}
    missing = required_phases - phases_seen
    if missing:
        errors.append(f"structure_json missing required phases: {sorted(missing)}")

    if duration_min > 0 and not (int(duration_min * 0.75) <= total_minutes <= int(duration_min * 1.25)):
        errors.append("sum(block duration_min) must be within 75%-125% of duration_min")
    return errors


def validate_session_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ["name", "category", "intent", "energy_system", "tier", "prescription", "coaching_notes"]:
        val = str(payload.get(field, "")).strip()
        if not val:
            errors.append(f"{field} is required")
    try:
        duration_min = int(payload.get("duration_min"))
        if duration_min <= 0:
            errors.append("duration_min must be > 0")
    except Exception:
        errors.append("duration_min must be an integer")
        duration_min = 0

    targets_json = payload.get("targets_json")
    if not isinstance(targets_json, dict):
        errors.append("targets_json must be an object")
    else:
        primary = targets_json.get("primary")
        if not isinstance(primary, dict):
            errors.append("targets_json.primary must be an object")
        else:
            pace_zone = str(primary.get("pace_zone", "")).strip()
            hr_zone = str(primary.get("hr_zone", "")).strip()
            if not valid_zone_label(pace_zone):
                errors.append("targets_json.primary.pace_zone is invalid")
            if not valid_zone_label(hr_zone):
                errors.append("targets_json.primary.hr_zone is invalid")
            _validate_rpe_range(primary.get("rpe_range"), "targets_json.primary", errors)

    for key in ["progression_json", "regression_json"]:
        if not isinstance(payload.get(key), dict):
            errors.append(f"{key} must be an object")
        elif not payload[key]:
            errors.append(f"{key} cannot be empty")

    errors.extend(validate_structure_contract(payload.get("structure_json"), duration_min))
    return errors
