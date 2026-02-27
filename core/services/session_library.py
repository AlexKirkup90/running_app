from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Optional


ALLOWED_PHASES = {"warmup", "main_set", "cooldown", "strides", "drills"}
SPECIAL_ZONE_LABELS = {"Race Pace", "Benchmark", "Strides", "Hill Effort", "N/A"}
ZONE_TOKEN = re.compile(r"Z[1-5]")
VALID_INTENSITY_CODES = {"E", "M", "T", "I", "R"}
CORE_JD_INTENT_TO_CODE = {
    "long_run": "E",
    "recovery": "E",
    "easy_aerobic": "E",
    "easy": "E",
    "marathon_pace": "M",
    "race_specific": "M",
    "threshold": "T",
    "tempo": "T",
    "lactate_threshold": "T",
    "vo2": "I",
    "vo2max": "I",
    "repetition": "R",
    "strides": "R",
    "neuromuscular": "R",
}


def _token(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


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
        "primary": {"pace_zone": "Z2", "hr_zone": "Z2", "rpe_range": [3, 4], "intensity_code": "E"},
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
            primary_intensity = str(primary.get("intensity_code", "")).strip().upper()
            if primary_intensity and primary_intensity not in VALID_INTENSITY_CODES:
                errors.append("targets_json.primary.intensity_code must be one of E/M/T/I/R")

    for key in ["progression_json", "regression_json"]:
        if not isinstance(payload.get(key), dict):
            errors.append(f"{key} must be an object")
        elif not payload[key]:
            errors.append(f"{key} cannot be empty")

    errors.extend(validate_structure_contract(payload.get("structure_json"), duration_min))
    errors.extend(_validate_daniels_methodology_contract(payload))
    return errors


def _validate_daniels_methodology_contract(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    targets_json = payload.get("targets_json") if isinstance(payload.get("targets_json"), dict) else {}
    structure = payload.get("structure_json") if isinstance(payload.get("structure_json"), dict) else {}
    methodology = _token(targets_json.get("methodology") or structure.get("methodology"))
    if methodology not in {"daniels_vdot", "jack_daniels_vdot"}:
        return errors

    intent_token = _token(payload.get("intent"))
    required_code = CORE_JD_INTENT_TO_CODE.get(intent_token)
    if not required_code:
        return errors

    primary = targets_json.get("primary") if isinstance(targets_json.get("primary"), dict) else {}
    primary_code = str(primary.get("intensity_code", "")).strip().upper()
    if primary_code not in VALID_INTENSITY_CODES:
        errors.append("targets_json.primary.intensity_code is required for Daniels-coded core intents (E/M/T/I/R)")
    elif primary_code != required_code:
        errors.append(f"targets_json.primary.intensity_code should align with intent '{intent_token}' (expected {required_code})")

    blocks = structure.get("blocks") if isinstance(structure.get("blocks"), list) else []
    main_set_found = False
    expected_code_seen = False
    for idx, block in enumerate(blocks):
        if not isinstance(block, dict) or str(block.get("phase", "")).strip().lower() != "main_set":
            continue
        main_set_found = True
        target = block.get("target")
        if not isinstance(target, dict):
            continue
        code = str(target.get("intensity_code", "")).strip().upper()
        if code not in VALID_INTENSITY_CODES:
            errors.append(f"structure_json.blocks[{idx}].target.intensity_code is required for Daniels-coded main_set blocks")
        elif code == required_code:
            expected_code_seen = True
    if not main_set_found:
        # structure validator already handles this, avoid duplicate message here
        return errors
    if main_set_found and not expected_code_seen:
        errors.append(f"At least one main_set block intensity_code should align with intent '{intent_token}' (expected {required_code})")
    return errors


def _jd_block(
    *,
    phase: str,
    duration_min: int,
    instructions: str,
    pace_zone: str,
    hr_zone: str,
    rpe_range: list[int],
    intensity_code: str,
    extra: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    block = {
        "phase": phase,
        "duration_min": int(duration_min),
        "instructions": instructions,
        "target": {
            "pace_zone": pace_zone,
            "hr_zone": hr_zone,
            "rpe_range": rpe_range,
            "intensity_code": intensity_code,
        },
    }
    if extra:
        block.update(deepcopy(extra))
    return block


def gold_standard_session_templates_v1() -> list[dict[str, Any]]:
    # Canonical JD/VDOT-coded templates for the highest-value running sessions.
    templates: list[dict[str, Any]] = [
        {
            "name": "Long Run (E) 90min",
            "category": "run",
            "intent": "long_run",
            "energy_system": "aerobic_durability",
            "tier": "medium",
            "is_treadmill": False,
            "duration_min": 90,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=15, instructions="Easy warmup jog, mobility, settle cadence.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                    _jd_block(phase="main_set", duration_min=65, instructions="Steady aerobic long run at E effort. Keep form relaxed and fueling on schedule.", pace_zone="Z2", hr_zone="Z2", rpe_range=[3, 4], intensity_code="E"),
                    _jd_block(phase="cooldown", duration_min=10, instructions="Ease down and finish with light mobility.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
                ],
                "fueling_hint": "Take carbs every 30-35 min; fluids based on conditions.",
                "success_criteria": "Even effort, stable mechanics, no late drift beyond intended E effort.",
            },
            "targets_json": {"primary": {"pace_zone": "Z2", "hr_zone": "Z2", "rpe_range": [3, 4], "intensity_code": "E"}},
            "progression_json": {"increase_one": "Extend main set by 10-15 min every 1-2 weeks if recovery remains stable.", "increase_two": "Add terrain variation only after duration progression is stable."},
            "regression_json": {"reduce_one": "Reduce total duration by 15-20% on low readiness or elevated soreness.", "reduce_two": "Replace with easy aerobic run if pain flag is present."},
            "prescription": "Aerobic durability long run at Daniels E effort with fueling practice and controlled pacing.",
            "coaching_notes": "Prioritize relaxed mechanics and hydration; avoid turning E effort into marathon pace.",
            "status": "canonical",
        },
        {
            "name": "Long Run (E to M Finish) 100min",
            "category": "run",
            "intent": "marathon_pace",
            "energy_system": "race_specific_endurance",
            "tier": "hard",
            "is_treadmill": False,
            "duration_min": 100,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=15, instructions="Easy warmup jog and mobility prep.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                    _jd_block(phase="main_set", duration_min=68, instructions="Run steady at E effort, fuel and stay patient.", pace_zone="Z2", hr_zone="Z2", rpe_range=[3, 4], intensity_code="E"),
                    _jd_block(phase="main_set", duration_min=12, instructions="Finish strong at marathon pace/effort if readiness and mechanics are stable.", pace_zone="Race Pace", hr_zone="Z3-Z4", rpe_range=[5, 6], intensity_code="M"),
                    _jd_block(phase="cooldown", duration_min=5, instructions="Short easy cooldown jog.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
                ],
                "fueling_hint": "Practice race-day carbs and fluids.",
                "success_criteria": "Controlled E pacing early, smooth transition to M effort without form breakdown.",
            },
            "targets_json": {"primary": {"pace_zone": "Race Pace", "hr_zone": "Z3-Z4", "rpe_range": [5, 6], "intensity_code": "M"}},
            "progression_json": {"increase_one": "Progress M-finish block from 10 -> 20 min over build phase.", "increase_two": "Add total duration only if recovery quality remains high."},
            "regression_json": {"reduce_one": "Keep full run at E effort when readiness is low.", "reduce_two": "Shorten total duration by 10-20% if cumulative fatigue is elevated."},
            "prescription": "Long run with controlled marathon-pace finish; only apply M-finish when readiness and pain checks are green.",
            "coaching_notes": "This is quality work. Do not force M finish on compromised recovery days.",
            "status": "canonical",
        },
        {
            "name": "Threshold Continuous (T) 20min",
            "category": "run",
            "intent": "threshold",
            "energy_system": "lactate_threshold",
            "tier": "medium",
            "is_treadmill": False,
            "duration_min": 55,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=15, instructions="Easy run + drills + 4 x 20s strides.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 4], intensity_code="E"),
                    _jd_block(phase="main_set", duration_min=20, instructions="Continuous threshold at controlled T effort; avoid overreaching.", pace_zone="Z4", hr_zone="Z3-Z4", rpe_range=[6, 7], intensity_code="T"),
                    _jd_block(phase="cooldown", duration_min=20, instructions="Easy cooldown jog and reset breathing.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                ],
                "success_criteria": "Even threshold effort and posture stability; finish feeling controlled, not maxed.",
            },
            "targets_json": {"primary": {"pace_zone": "Z4", "hr_zone": "Z3-Z4", "rpe_range": [6, 7], "intensity_code": "T"}},
            "progression_json": {"increase_one": "Build continuous T duration by 5 min up to 30 min total.", "increase_two": "Convert to cruise intervals when heat/terrain limits continuous pacing."},
            "regression_json": {"reduce_one": "Split into 2 x 10 min T with short float recovery.", "reduce_two": "Run aerobic steady (E/M bridge) on low readiness days."},
            "prescription": "Daniels T session emphasizing controlled threshold effort, not race effort.",
            "coaching_notes": "Threshold should feel strong but sustainable; avoid drifting into VO2 intensity.",
            "status": "canonical",
        },
        {
            "name": "Threshold Cruise Intervals (T) 3x10min",
            "category": "run",
            "intent": "lactate_threshold",
            "energy_system": "lactate_threshold",
            "tier": "hard",
            "is_treadmill": False,
            "duration_min": 70,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=18, instructions="Easy run + drills + strides.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 4], intensity_code="E"),
                    _jd_block(
                        phase="main_set",
                        duration_min=30,
                        instructions="3 x 10 min at T effort with 2 min easy float between reps.",
                        pace_zone="Z4",
                        hr_zone="Z3-Z4",
                        rpe_range=[6, 7],
                        intensity_code="T",
                        extra={"repetitions": 3, "work_duration_min": 10, "recovery_duration_min": 2},
                    ),
                    _jd_block(phase="cooldown", duration_min=22, instructions="Easy cooldown jog.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                ],
            },
            "targets_json": {"primary": {"pace_zone": "Z4", "hr_zone": "Z3-Z4", "rpe_range": [6, 7], "intensity_code": "T"}},
            "progression_json": {"increase_one": "Progress to 4 x 10 min or 3 x 12 min at same T effort.", "increase_two": "Shorten recoveries only after pacing quality is stable."},
            "regression_json": {"reduce_one": "2 x 10 min T or 3 x 8 min T when fatigue is elevated.", "reduce_two": "Swap to threshold continuous 20 min if logistics favor uninterrupted pacing."},
            "prescription": "Cruise intervals at Daniels T pace with short float recoveries; quality and control over speed.",
            "coaching_notes": "Keep floats truly easy to preserve threshold quality.",
            "status": "canonical",
        },
        {
            "name": "VO2 Intervals (I) 5x3min",
            "category": "run",
            "intent": "vo2",
            "energy_system": "vo2max",
            "tier": "hard",
            "is_treadmill": False,
            "duration_min": 60,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=18, instructions="Easy warmup + drills + strides.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 4], intensity_code="E"),
                    _jd_block(
                        phase="main_set",
                        duration_min=25,
                        instructions="5 x 3 min at I effort with 2-3 min easy jog recoveries.",
                        pace_zone="Z5",
                        hr_zone="Z4-Z5",
                        rpe_range=[8, 9],
                        intensity_code="I",
                        extra={"repetitions": 5, "work_duration_min": 3, "recovery_duration_min": 3},
                    ),
                    _jd_block(phase="cooldown", duration_min=17, instructions="Easy cooldown jog, relaxed breathing.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                ],
            },
            "targets_json": {"primary": {"pace_zone": "Z5", "hr_zone": "Z4-Z5", "rpe_range": [8, 9], "intensity_code": "I"}},
            "progression_json": {"increase_one": "Progress to 6 reps before extending rep duration.", "increase_two": "Use 4-min reps only if athlete has tolerated prior I blocks well."},
            "regression_json": {"reduce_one": "4 x 3 min at I effort with full recovery.", "reduce_two": "Shift to T intervals when readiness or soreness is marginal."},
            "prescription": "VO2 interval session at Daniels I effort with full aerobic support and controlled recoveries.",
            "coaching_notes": "Target high-quality reps; stop if mechanics deteriorate.",
            "status": "canonical",
        },
        {
            "name": "Marathon Pace Blocks (M) 3x15min",
            "category": "run",
            "intent": "marathon_pace",
            "energy_system": "race_specific",
            "tier": "hard",
            "is_treadmill": False,
            "duration_min": 85,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=15, instructions="Easy warmup + mobility prep.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                    _jd_block(
                        phase="main_set",
                        duration_min=51,
                        instructions="3 x 15 min at M effort with 2 min easy jog recoveries.",
                        pace_zone="Race Pace",
                        hr_zone="Z3-Z4",
                        rpe_range=[5, 6],
                        intensity_code="M",
                        extra={"repetitions": 3, "work_duration_min": 15, "recovery_duration_min": 2},
                    ),
                    _jd_block(phase="cooldown", duration_min=19, instructions="Easy cooldown run and mobility reset.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                ],
            },
            "targets_json": {"primary": {"pace_zone": "Race Pace", "hr_zone": "Z3-Z4", "rpe_range": [5, 6], "intensity_code": "M"}},
            "progression_json": {"increase_one": "Increase total M time before increasing pace demand.", "increase_two": "Reduce recoveries slightly only after stable completion."},
            "regression_json": {"reduce_one": "2 x 15 min M or 3 x 10 min M on low readiness.", "reduce_two": "Convert to E run if pain or acute fatigue flags are present."},
            "prescription": "Race-specific M effort blocks with controlled recoveries and fueling practice.",
            "coaching_notes": "Pacing discipline is the goal; avoid threshold drift.",
            "status": "canonical",
        },
        {
            "name": "Recovery Run (E) 40min + Strides",
            "category": "run",
            "intent": "recovery",
            "energy_system": "active_recovery",
            "tier": "easy",
            "is_treadmill": False,
            "duration_min": 40,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=10, instructions="Very easy jog and loosen up.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
                    _jd_block(phase="main_set", duration_min=20, instructions="Keep recovery effort truly easy.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                    _jd_block(
                        phase="strides",
                        duration_min=5,
                        instructions="5 x 20s relaxed strides with full walk/jog recovery.",
                        pace_zone="Strides",
                        hr_zone="Z2-Z4",
                        rpe_range=[4, 6],
                        intensity_code="R",
                        extra={"repetitions": 5, "work_duration_sec": 20},
                    ),
                    _jd_block(phase="cooldown", duration_min=5, instructions="Easy shuffle cooldown.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
                ],
            },
            "targets_json": {"primary": {"pace_zone": "Z1-Z2", "hr_zone": "Z1-Z2", "rpe_range": [2, 3], "intensity_code": "E"}},
            "progression_json": {"increase_one": "Add 5 min easy volume before increasing strides.", "increase_two": "Progress strides to 8 reps if athlete absorbs quality well."},
            "regression_json": {"reduce_one": "Remove strides first when residual fatigue is high.", "reduce_two": "Shorten run by 10-15 min if soreness is elevated."},
            "prescription": "Low-stress recovery run with optional relaxed strides to maintain rhythm.",
            "coaching_notes": "Recovery means recovery; strides should feel fast but smooth, not hard.",
            "status": "canonical",
        },
        {
            "name": "Strides / Repetition (R) 8x20s",
            "category": "run",
            "intent": "strides",
            "energy_system": "neuromuscular_speed",
            "tier": "easy",
            "is_treadmill": False,
            "duration_min": 35,
            "structure_json": {
                "version": 2,
                "methodology": "daniels_vdot",
                "blocks": [
                    _jd_block(phase="warmup", duration_min=15, instructions="Easy run and form drills.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                    _jd_block(
                        phase="main_set",
                        duration_min=8,
                        instructions="8 x 20s relaxed fast strides with full recovery.",
                        pace_zone="Strides",
                        hr_zone="Z2-Z4",
                        rpe_range=[4, 6],
                        intensity_code="R",
                        extra={"repetitions": 8, "work_duration_sec": 20},
                    ),
                    _jd_block(phase="cooldown", duration_min=12, instructions="Easy jog cooldown.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
                ],
            },
            "targets_json": {"primary": {"pace_zone": "Strides", "hr_zone": "Z2-Z4", "rpe_range": [4, 6], "intensity_code": "R"}},
            "progression_json": {"increase_one": "Progress to 10-12 strides before lengthening reps.", "increase_two": "Keep recoveries full to protect quality and mechanics."},
            "regression_json": {"reduce_one": "Reduce reps to 4-6 when residual fatigue is present.", "reduce_two": "Swap to easy run only when neuromuscular strain is contraindicated."},
            "prescription": "Neuromuscular speed maintenance with relaxed repetition mechanics, not sprinting.",
            "coaching_notes": "Focus on rhythm and posture; full recovery between reps is essential.",
            "status": "canonical",
        },
    ]
    templates.extend(_gold_standard_progressive_variants())
    deduped: dict[str, dict[str, Any]] = {}
    for tpl in templates:
        deduped[str(tpl.get("name") or "").strip()] = tpl
    return list(deduped.values())


def _gold_standard_progressive_variants() -> list[dict[str, Any]]:
    templates: list[dict[str, Any]] = []

    def add_template(
        *,
        name: str,
        duration_min: int,
        intent: str,
        energy_system: str,
        tier: str,
        primary_code: str,
        primary_pace_zone: str,
        primary_hr_zone: str,
        primary_rpe: list[int],
        blocks: list[dict[str, Any]],
        prescription: str,
        coaching_notes: str,
        is_treadmill: bool = False,
    ) -> None:
        templates.append(
            {
                "name": name,
                "category": "run",
                "intent": intent,
                "energy_system": energy_system,
                "tier": tier,
                "is_treadmill": is_treadmill,
                "duration_min": duration_min,
                "structure_json": {
                    "version": 2,
                    "methodology": "daniels_vdot",
                    "blocks": blocks,
                },
                "targets_json": {
                    "methodology": "daniels_vdot",
                    "primary": {
                        "pace_zone": primary_pace_zone,
                        "hr_zone": primary_hr_zone,
                        "rpe_range": primary_rpe,
                        "intensity_code": primary_code,
                    }
                },
                "progression_json": {
                    "increase_one": "Progress volume before increasing intensity demand.",
                    "increase_two": "Advance only when execution quality and recovery remain stable.",
                },
                "regression_json": {
                    "reduce_one": "Trim main-set volume on low readiness or elevated soreness.",
                    "reduce_two": "Shift to easier intensity when pain or fatigue flags are present.",
                },
                "prescription": prescription,
                "coaching_notes": coaching_notes,
                "status": "canonical",
            }
        )

    # Easy aerobic runs (including treadmill variants)
    for dur in [35, 45, 55, 65, 75, 85, 95, 105]:
        for treadmill in [False, True]:
            warm = 12 if dur >= 55 else 10
            cool = 8 if dur >= 55 else 6
            main = max(12, dur - warm - cool)
            env_label = "Treadmill" if treadmill else "Outdoor"
            add_template(
                name=f"Easy Run (E) {dur}min {env_label}",
                duration_min=dur,
                intent="easy_aerobic",
                energy_system="aerobic_base",
                tier="easy" if dur <= 45 else ("medium" if dur <= 65 else "hard"),
                primary_code="E",
                primary_pace_zone="Z2",
                primary_hr_zone="Z2",
                primary_rpe=[3, 4],
                is_treadmill=treadmill,
                blocks=[
                    _jd_block(phase="warmup", duration_min=warm, instructions="Easy warmup jog and mobility prep.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                    _jd_block(phase="main_set", duration_min=main, instructions="Steady aerobic E-effort running with relaxed form.", pace_zone="Z2", hr_zone="Z2", rpe_range=[3, 4], intensity_code="E"),
                    _jd_block(phase="cooldown", duration_min=cool, instructions="Easy cooldown jog and reset breathing.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
                ],
                prescription=f"Daniels E-effort aerobic run for {dur} min with steady, controlled pacing.",
                coaching_notes="Keep effort conversational; this is not a progression run.",
            )

    # Long runs (E)
    for dur in [50, 55, 60, 65, 70, 75, 80, 90, 95, 100, 110, 120, 130, 140, 150]:
        warm = 12 if dur < 90 else 15
        cool = 8 if dur < 100 else 10
        main = dur - warm - cool
        add_template(
            name=f"Long Run (E) {dur}min",
            duration_min=dur,
            intent="long_run",
            energy_system="aerobic_durability",
            tier="medium" if dur <= 100 else "hard",
            primary_code="E",
            primary_pace_zone="Z2",
            primary_hr_zone="Z2",
            primary_rpe=[3, 4],
            blocks=[
                _jd_block(phase="warmup", duration_min=warm, instructions="Easy warmup and settle into cadence.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=main, instructions="Sustained E-effort long run with fueling practice.", pace_zone="Z2", hr_zone="Z2", rpe_range=[3, 4], intensity_code="E"),
                _jd_block(phase="cooldown", duration_min=cool, instructions="Ease down to finish.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription=f"Aerobic durability long run at Daniels E effort for {dur} minutes.",
            coaching_notes="Fuel early and stay patient; avoid creeping above E effort.",
        )

    # Long runs with marathon finish (mixed E + M)
    for total, finish in [(85, 10), (90, 10), (95, 15), (100, 15), (105, 20), (110, 20), (120, 20), (125, 25), (130, 30), (140, 30)]:
        warm = 15
        cool = 5
        e_block = max(20, total - warm - finish - cool)
        add_template(
            name=f"Long Run (E to M Finish) {total}min ({finish}min M)",
            duration_min=total,
            intent="marathon_pace",
            energy_system="race_specific_endurance",
            tier="hard",
            primary_code="M",
            primary_pace_zone="Race Pace",
            primary_hr_zone="Z3-Z4",
            primary_rpe=[5, 6],
            blocks=[
                _jd_block(phase="warmup", duration_min=warm, instructions="Easy warmup and mobility prep.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=e_block, instructions="Steady E-effort long-run segment.", pace_zone="Z2", hr_zone="Z2", rpe_range=[3, 4], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=finish, instructions="Finish at controlled marathon effort if readiness is green.", pace_zone="Race Pace", hr_zone="Z3-Z4", rpe_range=[5, 6], intensity_code="M"),
                _jd_block(phase="cooldown", duration_min=cool, instructions="Short easy cooldown.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription=f"Long run with {finish} min controlled marathon-pace finish, total {total} min.",
            coaching_notes="Only complete the M finish if mechanics and fueling remain stable.",
        )

    # Recovery runs
    for dur, strides in [(25, 0), (30, 0), (35, 4), (40, 6), (45, 6), (50, 8), (55, 8), (60, 8)]:
        warm = 8 if dur <= 35 else 10
        cool = 6
        stride_block = 0 if strides == 0 else 4
        main = max(12, dur - warm - cool - stride_block)
        blocks = [
            _jd_block(phase="warmup", duration_min=warm, instructions="Very easy warmup jog.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
            _jd_block(phase="main_set", duration_min=main, instructions="Keep recovery effort truly easy and relaxed.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
        ]
        if strides:
            blocks.append(
                _jd_block(
                    phase="strides",
                    duration_min=stride_block,
                    instructions=f"{strides} x 20s relaxed strides with full recovery.",
                    pace_zone="Strides",
                    hr_zone="Z2-Z4",
                    rpe_range=[4, 6],
                    intensity_code="R",
                    extra={"repetitions": strides, "work_duration_sec": 20},
                )
            )
        blocks.append(_jd_block(phase="cooldown", duration_min=cool, instructions="Easy cooldown shuffle.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"))
        add_template(
            name=(f"Recovery Run (E) {dur}min" + (f" + {strides}x20s Strides" if strides else "")),
            duration_min=dur,
            intent="recovery",
            energy_system="active_recovery",
            tier="easy",
            primary_code="E",
            primary_pace_zone="Z1-Z2",
            primary_hr_zone="Z1-Z2",
            primary_rpe=[2, 3],
            blocks=blocks,
            prescription="Low-stress recovery session to absorb training load and restore rhythm.",
            coaching_notes="Keep the aerobic part very easy; strides are smooth, not hard.",
        )

    # Threshold continuous
    for t_minutes in [15, 20, 25, 30, 35]:
        total = t_minutes + 35
        add_template(
            name=f"Threshold Continuous (T) {t_minutes}min",
            duration_min=total,
            intent="threshold",
            energy_system="lactate_threshold",
            tier="medium" if t_minutes <= 20 else "hard",
            primary_code="T",
            primary_pace_zone="Z4",
            primary_hr_zone="Z3-Z4",
            primary_rpe=[6, 7],
            blocks=[
                _jd_block(phase="warmup", duration_min=15, instructions="Easy run, drills, strides.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 4], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=t_minutes, instructions="Continuous Daniels T effort, controlled and even.", pace_zone="Z4", hr_zone="Z3-Z4", rpe_range=[6, 7], intensity_code="T"),
                _jd_block(phase="cooldown", duration_min=20, instructions="Easy cooldown jog.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription=f"Continuous threshold work: {t_minutes} min at Daniels T effort.",
            coaching_notes="Controlled threshold, not race effort. Finish with good form.",
        )

    # Threshold cruise intervals
    for reps, work, rec in [(3, 8, 2), (3, 10, 2), (4, 8, 2), (4, 10, 2), (5, 6, 1), (6, 5, 1), (3, 12, 2), (5, 8, 1), (2, 12, 2), (4, 6, 1)]:
        main_total = reps * work
        total = main_total + 40
        add_template(
            name=f"Threshold Cruise Intervals (T) {reps}x{work}min",
            duration_min=total,
            intent="lactate_threshold",
            energy_system="lactate_threshold",
            tier="medium" if main_total <= 30 else "hard",
            primary_code="T",
            primary_pace_zone="Z4",
            primary_hr_zone="Z3-Z4",
            primary_rpe=[6, 7],
            blocks=[
                _jd_block(phase="warmup", duration_min=18, instructions="Easy run + drills + strides.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 4], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=main_total, instructions=f"{reps} x {work} min at T effort with {rec} min easy float recovery.", pace_zone="Z4", hr_zone="Z3-Z4", rpe_range=[6, 7], intensity_code="T", extra={"repetitions": reps, "work_duration_min": work, "recovery_duration_min": rec}),
                _jd_block(phase="cooldown", duration_min=max(12, total - 18 - main_total), instructions="Easy cooldown jog.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription=f"Cruise intervals: {reps} x {work} min at Daniels T effort with short floats.",
            coaching_notes="Floats stay easy so the work reps remain high quality.",
        )

    # Marathon pace workouts
    for reps, work, rec in [(2, 15, 3), (3, 15, 2), (2, 20, 3), (3, 20, 2), (4, 10, 2), (2, 25, 3), (3, 12, 2), (1, 30, 0), (2, 12, 2), (1, 40, 0)]:
        main_total = reps * work
        total = main_total + 34
        instructions = f"{reps} x {work} min at M effort" + (f" with {rec} min easy jog recoveries." if reps > 1 else " continuous.")
        extra = {"repetitions": reps, "work_duration_min": work}
        if reps > 1:
            extra["recovery_duration_min"] = rec
        add_template(
            name=(f"Marathon Pace Blocks (M) {reps}x{work}min" if reps > 1 else f"Marathon Pace Continuous (M) {work}min"),
            duration_min=total,
            intent="marathon_pace",
            energy_system="race_specific",
            tier="hard" if main_total >= 30 else "medium",
            primary_code="M",
            primary_pace_zone="Race Pace",
            primary_hr_zone="Z3-Z4",
            primary_rpe=[5, 6],
            blocks=[
                _jd_block(phase="warmup", duration_min=15, instructions="Easy warmup and mobility prep.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=main_total, instructions=instructions, pace_zone="Race Pace", hr_zone="Z3-Z4", rpe_range=[5, 6], intensity_code="M", extra=extra),
                _jd_block(phase="cooldown", duration_min=max(10, total - 15 - main_total), instructions="Easy cooldown run.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription=f"Race-specific marathon-pace work: {instructions}",
            coaching_notes="Target pacing discipline and fueling practice, not threshold effort.",
        )

    # VO2 / I sessions
    for reps, work, rec in [(5, 3, 3), (6, 3, 3), (4, 4, 3), (5, 4, 3), (6, 2, 2), (8, 2, 2), (4, 5, 4), (5, 5, 4), (7, 2, 2), (3, 6, 4)]:
        main_total = reps * work
        total = main_total + 35
        add_template(
            name=f"VO2 Intervals (I) {reps}x{work}min",
            duration_min=total,
            intent="vo2",
            energy_system="vo2max",
            tier="hard",
            primary_code="I",
            primary_pace_zone="Z5",
            primary_hr_zone="Z4-Z5",
            primary_rpe=[8, 9],
            blocks=[
                _jd_block(phase="warmup", duration_min=18, instructions="Easy warmup + drills + strides.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 4], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=main_total, instructions=f"{reps} x {work} min at I effort with {rec} min easy jog recoveries.", pace_zone="Z5", hr_zone="Z4-Z5", rpe_range=[8, 9], intensity_code="I", extra={"repetitions": reps, "work_duration_min": work, "recovery_duration_min": rec}),
                _jd_block(phase="cooldown", duration_min=max(12, total - 18 - main_total), instructions="Easy cooldown jog.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription=f"Daniels I-pace intervals: {reps} x {work} min with full recovery support.",
            coaching_notes="Stop if mechanics break down; quality is more important than completing all reps.",
        )

    # Strides / repetition
    for reps, secs, total in [(6, 20, 30), (8, 20, 35), (10, 20, 40), (12, 20, 45), (6, 30, 38), (8, 30, 45), (10, 15, 34), (6, 15, 28)]:
        warm = 15
        cool = max(8, total - warm - 8)
        add_template(
            name=f"Strides / Repetition (R) {reps}x{secs}s",
            duration_min=total,
            intent="strides",
            energy_system="neuromuscular_speed",
            tier="easy",
            primary_code="R",
            primary_pace_zone="Strides",
            primary_hr_zone="Z2-Z4",
            primary_rpe=[4, 6],
            blocks=[
                _jd_block(phase="warmup", duration_min=warm, instructions="Easy run + drills + mobility.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=8, instructions=f"{reps} x {secs}s relaxed fast strides with full recovery.", pace_zone="Strides", hr_zone="Z2-Z4", rpe_range=[4, 6], intensity_code="R", extra={"repetitions": reps, "work_duration_sec": secs}),
                _jd_block(phase="cooldown", duration_min=cool, instructions="Easy cooldown jog.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription=f"Neuromuscular rhythm session with {reps} x {secs}s relaxed R-effort strides.",
            coaching_notes="Fast but smooth. Full recovery and posture-first execution.",
        )

    # Taper / openers (light M/T/R mixes, tagged by primary intent M or T depending focus)
    for name, total, main_desc, main_code, pace_zone, hr_zone, rpe in [
        ("Openers (R) 5K/10K 30min", 30, "4 x 20s R-effort strides + 2 x 60s at T effort.", "R", "Strides", "Z2-Z4", [4, 6]),
        ("Openers (T) HM 35min", 35, "2 x 5 min at T effort with easy float + 4 strides.", "T", "Z4", "Z3-Z4", [5, 7]),
        ("Openers (M) Marathon 40min", 40, "2 x 8 min at M effort with easy recovery + 4 strides.", "M", "Race Pace", "Z3-Z4", [4, 6]),
        ("Benchmark Tune-Up (T) 45min", 45, "3 x 6 min T effort with short float recoveries.", "T", "Z4", "Z3-Z4", [6, 7]),
        ("Openers (R) HM/Marathon 35min", 35, "6 x 20s relaxed strides + 4 min at M effort.", "R", "Strides", "Z2-Z4", [4, 6]),
        ("Openers (I) 5K 35min", 35, "4 x 60s at I effort with full recovery + relaxed strides.", "I", "Z5", "Z4-Z5", [7, 8]),
    ]:
        warm = 12
        cool = 10
        main = total - warm - cool
        add_template(
            name=name,
            duration_min=total,
            intent=("threshold" if main_code == "T" else "marathon_pace" if main_code == "M" else "vo2" if main_code == "I" else "strides"),
            energy_system="race_priming",
            tier="easy",
            primary_code=main_code,
            primary_pace_zone=pace_zone,
            primary_hr_zone=hr_zone,
            primary_rpe=rpe,
            blocks=[
                _jd_block(phase="warmup", duration_min=warm, instructions="Easy warmup + drills.", pace_zone="Z1-Z2", hr_zone="Z1-Z2", rpe_range=[2, 3], intensity_code="E"),
                _jd_block(phase="main_set", duration_min=main, instructions=main_desc, pace_zone=pace_zone, hr_zone=hr_zone, rpe_range=rpe, intensity_code=main_code),
                _jd_block(phase="cooldown", duration_min=cool, instructions="Easy cooldown and mobility.", pace_zone="Z1", hr_zone="Z1", rpe_range=[2, 3], intensity_code="E"),
            ],
            prescription="Taper/openers session designed to sharpen rhythm without carrying fatigue.",
            coaching_notes="Finish feeling better than you started; no hero efforts.",
        )

    return templates
