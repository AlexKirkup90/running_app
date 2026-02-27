from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

WEEK_POLICY_VERSION = "jd_week_policy_v1"
PROGRESSION_TRACK_RULESET_VERSION = "jd_progression_tracks_v1"
TOKEN_ORCHESTRATION_RULESET_VERSION = "jd_token_orchestration_v1"
PROGRESSION_RULESET_SOURCE = "embedded_defaults"
ALLOWED_RACE_FOCUSES = {"5k", "10k", "half_marathon", "marathon", "general"}
ALLOWED_PHASES = {"base", "build", "peak", "taper", "recovery"}


def race_focus_bucket(race_goal: str) -> str:
    token = str(race_goal or "").strip().lower()
    if "marathon" in token and "half" not in token:
        return "marathon"
    if "half" in token:
        return "half_marathon"
    if "10" in token:
        return "10k"
    if "5" in token:
        return "5k"
    return "general"


_QUALITY_POLICY_RULES: dict[str, dict[str, dict[str, Any]]] = {
    "5k": {
        "base": {
            "quality_focus": "threshold_foundation",
            "short_race_mix_mode": "threshold_over_vo2",
            "rationale": "base phase: emphasize threshold foundation before heavier VO2 density",
        },
        "build": {
            "quality_focus": "threshold_vo2_blend",
            "short_race_mix_mode": "diversify_threshold_vo2",
            "rationale": "build phase: diversify threshold and VO2 stimulus across the week",
        },
        "peak": {
            "quality_focus": "vo2_sharpening",
            "short_race_mix_mode": "vo2_bias_with_threshold_support",
            "rationale": "peak phase: bias toward VO2 sharpening while preserving threshold support",
        },
        "taper": {
            "quality_focus": "sharpen_openers",
            "short_race_mix_mode": "openers_or_light_quality",
            "rationale": "taper phase: reduce fatigue and sharpen with openers/light quality",
        },
    },
    "10k": {
        "base": {
            "quality_focus": "threshold_foundation",
            "short_race_mix_mode": "threshold_over_vo2",
            "rationale": "base phase: emphasize threshold foundation before heavier VO2 density",
        },
        "build": {
            "quality_focus": "threshold_vo2_blend",
            "short_race_mix_mode": "diversify_threshold_vo2",
            "rationale": "build phase: diversify threshold and VO2 stimulus across the week",
        },
        "peak": {
            "quality_focus": "vo2_sharpening",
            "short_race_mix_mode": "vo2_bias_with_threshold_support",
            "rationale": "peak phase: bias toward VO2 sharpening while preserving threshold support",
        },
        "taper": {
            "quality_focus": "sharpen_openers",
            "short_race_mix_mode": "openers_or_light_quality",
            "rationale": "taper phase: reduce fatigue and sharpen with openers/light quality",
        },
    },
    "half_marathon": {
        "build": {
            "quality_focus": "threshold_marathon_pace_blend",
            "prefer_m_finish_long_run": True,
            "rationale": "half-marathon build/peak weeks: blend threshold durability and M-pace support",
        },
        "peak": {
            "quality_focus": "threshold_marathon_pace_blend",
            "prefer_m_finish_long_run": True,
            "rationale": "half-marathon build/peak weeks: blend threshold durability and M-pace support",
        },
        "base": {
            "quality_focus": "aerobic_threshold_foundation",
            "rationale": "base phase: aerobic + threshold foundation before race-specific M work",
        },
        "taper": {
            "quality_focus": "specificity_maintenance_taper",
            "rationale": "taper phase: maintain specificity while shedding fatigue",
        },
    },
    "marathon": {
        "build": {
            "quality_focus": "marathon_specific_endurance",
            "prefer_m_finish_long_run": True,
            "rationale": "build/peak marathon weeks: prioritize M-pace specificity and long-run quality",
        },
        "peak": {
            "quality_focus": "marathon_specific_endurance",
            "prefer_m_finish_long_run": True,
            "rationale": "build/peak marathon weeks: prioritize M-pace specificity and long-run quality",
        },
        "base": {
            "quality_focus": "aerobic_threshold_foundation",
            "rationale": "base phase: aerobic + threshold foundation before race-specific M work",
        },
        "taper": {
            "quality_focus": "specificity_maintenance_taper",
            "rationale": "taper phase: maintain specificity while shedding fatigue",
        },
    },
}


def week_quality_policy(*, phase: str, race_goal: str, week_number: int, total_weeks: int) -> Dict[str, Any]:
    phase_token = str(phase or "").strip().lower() or "unknown"
    race_focus = race_focus_bucket(race_goal)
    progress = float(week_number) / float(max(total_weeks, 1))
    policy: Dict[str, Any] = {
        "version": WEEK_POLICY_VERSION,
        "race_focus": race_focus,
        "phase": phase_token,
        "quality_focus": "balanced",
        "short_race_mix_mode": None,
        "prefer_m_finish_long_run": False,
        "rationale": [f"race focus: {race_focus}", f"phase: {phase_token}", f"week: {week_number}/{max(total_weeks,1)}"],
    }
    phase_rules = _QUALITY_POLICY_RULES.get(race_focus, {}).get(phase_token)
    if phase_rules:
        for key in ("quality_focus", "short_race_mix_mode", "prefer_m_finish_long_run"):
            if key in phase_rules:
                policy[key] = phase_rules[key]
        if phase_rules.get("rationale"):
            policy["rationale"].append(str(phase_rules["rationale"]))
    else:
        policy["rationale"].append("default balanced policy applied")

    if progress >= 0.75 and phase_token in {"peak", "taper"}:
        policy["rationale"].append("late-cycle progression: favor execution quality over added volume")
    return policy


def week_progression_tracks(
    *,
    phase: str,
    race_goal: str,
    week_number: int,
    total_weeks: int,
    phase_step: int,
    phase_weeks_total: int,
) -> Dict[str, Any]:
    race_focus = race_focus_bucket(race_goal)
    phase_token = str(phase or "").strip().lower() or "unknown"
    tracks: List[str] = [f"{race_focus}_{phase_token}_block_v1"]
    summary = f"{str(race_goal)} {phase} week {week_number}/{max(total_weeks,1)}"
    notes: List[str] = [f"phase block step {phase_step}/{max(phase_weeks_total,1)}"]

    if race_focus in {"5k", "10k"} and phase_token == "base":
        if phase_step == 1:
            tracks.append(f"{race_focus}_base_aerobic_foundation_intro_v1")
            summary = f"{str(race_goal)} Base week {phase_step}/{max(phase_weeks_total,1)}: aerobic foundation"
            notes.append("threshold intentionally delayed to later base weeks")
        else:
            tracks.append(f"{race_focus}_base_threshold_introduction_v1")
            summary = f"{str(race_goal)} Base week {phase_step}/{max(phase_weeks_total,1)}: threshold introduction"
            notes.append("introduce threshold support while preserving aerobic base")
    elif race_focus in {"5k", "10k"} and phase_token == "build":
        tracks.append(f"{race_focus}_build_threshold_vo2_progression_v1")
        summary = f"{str(race_goal)} Build week {phase_step}/{max(phase_weeks_total,1)}: threshold/VO2 progression"
        notes.append("quality mix shifts toward threshold+VO2 blend")
    elif race_focus in {"5k", "10k"} and phase_token == "peak":
        tracks.append(f"{race_focus}_peak_sharpening_v1")
        summary = f"{str(race_goal)} Peak week {phase_step}/{max(phase_weeks_total,1)}: sharpening"
        notes.append("VO2 and neuromuscular sharpening emphasized")
    elif race_focus in {"half_marathon", "marathon"} and phase_token == "base":
        tracks.append(f"{race_focus}_base_aerobic_threshold_foundation_v1")
        summary = f"{str(race_goal)} Base week {phase_step}/{max(phase_weeks_total,1)}: aerobic + threshold foundation"
        notes.append("build durability before heavy race-specific blocks")
    elif race_focus in {"half_marathon", "marathon"} and phase_token == "build":
        tracks.append(f"{race_focus}_build_specificity_progression_v1")
        summary = f"{str(race_goal)} Build week {phase_step}/{max(phase_weeks_total,1)}: race-specific progression"
        notes.append("progressively bias toward race-pace specificity")
    elif race_focus in {"half_marathon", "marathon"} and phase_token == "peak":
        tracks.append(f"{race_focus}_peak_specific_endurance_v1")
        summary = f"{str(race_goal)} Peak week {phase_step}/{max(phase_weeks_total,1)}: specific endurance"
        notes.append("maintain specificity, protect execution quality")
    elif phase_token == "recovery":
        tracks.append("global_recovery_cutback_v1")
        summary = f"{str(race_goal)} Recovery week: cutback"
        notes.append("reduce fatigue and preserve rhythm")
    elif phase_token == "taper":
        tracks.append(f"{race_focus}_taper_freshen_sharpen_v1")
        summary = f"{str(race_goal)} Taper week {phase_step}/{max(phase_weeks_total,1)}: freshen + sharpen"
        notes.append("shed fatigue while preserving race-specific feel")

    return {"tracks": tracks, "summary": summary, "notes": notes, "version": PROGRESSION_TRACK_RULESET_VERSION}


_TOKEN_ORCHESTRATION_RULES: list[dict[str, Any]] = [
    {
        "name": "short_race_base_w1_aerobic_foundation",
        "race_focuses": {"5k", "10k"},
        "phase": "base",
        "phase_step_eq": 1,
        "quality_focus_hint": "aerobic_foundation",
        "rationale": "short-race base week 1: aerobic foundation before threshold introduction",
        "action": None,
    },
    {
        "name": "short_race_base_threshold_intro",
        "race_focuses": {"5k", "10k"},
        "phase": "base",
        "phase_step_gte": 2,
        "quality_focus_hint": "threshold_foundation",
        "rationale": "short-race base progression: replace one easy run with threshold session",
        "action": {"replace_first": ["easy run", "Tempo / Threshold"]},
    },
    {
        "name": "endurance_base_threshold_support",
        "race_focuses": {"half_marathon", "marathon"},
        "phase": "base",
        "phase_step_gte": 2,
        "sessions_per_week_gte": 4,
        "quality_focus_hint": "aerobic_threshold_foundation",
        "rationale": "endurance base progression: introduce threshold support in later base weeks",
        "action": {"replace_first": ["easy run", "Tempo / Threshold"]},
    },
    {
        "name": "endurance_build_specificity_shift",
        "race_focuses": {"half_marathon", "marathon"},
        "phase": "build",
        "phase_step_gte": 2,
        "quality_focus_hint": None,  # resolved dynamically by race focus
        "rationale": "build block progression: shift one VO2 token toward race-pace specificity",
        "action": {"replace_first": ["vo2 intervals", "Race Pace"]},
    },
    {
        "name": "short_race_peak_threshold_support_alt",
        "race_focuses": {"5k", "10k"},
        "phase": "peak",
        "sessions_per_week_gte": 5,
        "phase_step_even": True,
        "quality_focus_hint": "vo2_sharpening",
        "rationale": "peak block progression: add threshold support on alternating peak weeks",
        "action": {"replace_first": ["easy run", "Tempo / Threshold"]},
    },
]


def _load_ruleset_from_json() -> None:
    global WEEK_POLICY_VERSION
    global PROGRESSION_TRACK_RULESET_VERSION
    global TOKEN_ORCHESTRATION_RULESET_VERSION
    global PROGRESSION_RULESET_SOURCE
    global _QUALITY_POLICY_RULES
    global _TOKEN_ORCHESTRATION_RULES

    candidate_paths: list[Path] = []
    env_path = os.getenv("PROGRESSION_TRACK_RULESET_PATH", "").strip()
    if env_path:
        candidate_paths.append(Path(env_path).expanduser())
    candidate_paths.append(Path(__file__).with_name("progression_tracks_ruleset_v1.json"))

    for path in candidate_paths:
        try:
            if not path.exists() or not path.is_file():
                continue
            payload = json.loads(path.read_text())
            if not isinstance(payload, dict):
                continue
            meta = payload.get("meta") or {}
            if not isinstance(meta, dict):
                meta = {}
            quality_rules = payload.get("quality_policy_rules") or {}
            token_rules = payload.get("token_orchestration_rules") or []
            if not isinstance(quality_rules, dict) or not isinstance(token_rules, list):
                continue

            normalized_token_rules: list[dict[str, Any]] = []
            for raw in token_rules:
                if not isinstance(raw, dict):
                    continue
                rule = dict(raw)
                focuses = rule.get("race_focuses")
                if isinstance(focuses, list):
                    rule["race_focuses"] = {str(item) for item in focuses if str(item).strip()}
                normalized_token_rules.append(rule)

            _QUALITY_POLICY_RULES = quality_rules
            _TOKEN_ORCHESTRATION_RULES = normalized_token_rules
            WEEK_POLICY_VERSION = str(meta.get("week_policy_version") or WEEK_POLICY_VERSION)
            PROGRESSION_TRACK_RULESET_VERSION = str(
                meta.get("progression_track_ruleset_version") or PROGRESSION_TRACK_RULESET_VERSION
            )
            TOKEN_ORCHESTRATION_RULESET_VERSION = str(
                meta.get("token_orchestration_ruleset_version") or TOKEN_ORCHESTRATION_RULESET_VERSION
            )
            PROGRESSION_RULESET_SOURCE = str(path)
            return
        except Exception:
            continue


_load_ruleset_from_json()


def _default_ruleset_file_path() -> Path:
    env_path = os.getenv("PROGRESSION_TRACK_RULESET_PATH", "").strip()
    if env_path:
        return Path(env_path).expanduser()
    return Path(__file__).with_name("progression_tracks_ruleset_v1.json")


def _ruleset_backup_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}.bak{path.suffix}")


def _ruleset_backup_archive_dir(path: Path) -> Path:
    return path.with_name(f"{path.stem}.history")


def _write_ruleset_backup_snapshots(path: Path, content: str) -> Path:
    backup = _ruleset_backup_path(path)
    backup.write_text(content)
    archive_dir = _ruleset_backup_archive_dir(path)
    archive_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = archive_dir / f"{path.stem}.{ts}.bak{path.suffix}"
    archive.write_text(content)
    return archive


def validate_planner_ruleset_payload(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["ruleset must be a JSON object"]
    meta = payload.get("meta")
    if not isinstance(meta, dict):
        errors.append("meta must be an object")
    else:
        for key in (
            "week_policy_version",
            "progression_track_ruleset_version",
            "token_orchestration_ruleset_version",
        ):
            if not isinstance(meta.get(key), str) or not str(meta.get(key)).strip():
                errors.append(f"meta.{key} must be a non-empty string")

    quality = payload.get("quality_policy_rules")
    if not isinstance(quality, dict):
        errors.append("quality_policy_rules must be an object")
    else:
        for race_focus, phase_map in quality.items():
            race_focus_key = str(race_focus or "").strip()
            if race_focus_key not in ALLOWED_RACE_FOCUSES:
                errors.append(
                    f"quality_policy_rules.{race_focus} has unsupported race focus (allowed: {sorted(ALLOWED_RACE_FOCUSES)})"
                )
            if not isinstance(phase_map, dict):
                errors.append(f"quality_policy_rules.{race_focus} must be an object")
                continue
            for phase, rule in phase_map.items():
                phase_key = str(phase or "").strip().lower()
                if phase_key not in ALLOWED_PHASES:
                    errors.append(
                        f"quality_policy_rules.{race_focus}.{phase} has unsupported phase (allowed: {sorted(ALLOWED_PHASES)})"
                    )
                if not isinstance(rule, dict):
                    errors.append(f"quality_policy_rules.{race_focus}.{phase} must be an object")
                    continue
                if not isinstance(rule.get("quality_focus"), str) or not str(rule.get("quality_focus")).strip():
                    errors.append(f"quality_policy_rules.{race_focus}.{phase}.quality_focus must be a non-empty string")
                if "rationale" in rule and rule.get("rationale") is not None:
                    if not isinstance(rule.get("rationale"), str) or not str(rule.get("rationale")).strip():
                        errors.append(f"quality_policy_rules.{race_focus}.{phase}.rationale must be a non-empty string")
                if "short_race_mix_mode" in rule and rule.get("short_race_mix_mode") is not None:
                    if not isinstance(rule.get("short_race_mix_mode"), str) or not str(rule.get("short_race_mix_mode")).strip():
                        errors.append(
                            f"quality_policy_rules.{race_focus}.{phase}.short_race_mix_mode must be a non-empty string"
                        )
                if "prefer_m_finish_long_run" in rule and rule.get("prefer_m_finish_long_run") is not None:
                    if not isinstance(rule.get("prefer_m_finish_long_run"), bool):
                        errors.append(
                            f"quality_policy_rules.{race_focus}.{phase}.prefer_m_finish_long_run must be a boolean"
                        )

    token_rules = payload.get("token_orchestration_rules")
    if not isinstance(token_rules, list):
        errors.append("token_orchestration_rules must be an array")
    else:
        seen_rule_names: set[str] = set()
        for idx, rule in enumerate(token_rules):
            if not isinstance(rule, dict):
                errors.append(f"token_orchestration_rules[{idx}] must be an object")
                continue
            if not isinstance(rule.get("name"), str) or not str(rule.get("name")).strip():
                errors.append(f"token_orchestration_rules[{idx}].name must be a non-empty string")
                rule_name = ""
            else:
                rule_name = str(rule.get("name")).strip()
                if rule_name in seen_rule_names:
                    errors.append(f"token_orchestration_rules[{idx}].name duplicates a prior rule name: {rule_name}")
                seen_rule_names.add(rule_name)
            if "race_focuses" in rule and not isinstance(rule.get("race_focuses"), (list, set, tuple)):
                errors.append(f"token_orchestration_rules[{idx}].race_focuses must be an array")
            else:
                focuses = rule.get("race_focuses")
                if focuses is not None:
                    normalized_focuses = [str(item or "").strip() for item in list(focuses)]
                    if not normalized_focuses or any(not token for token in normalized_focuses):
                        errors.append(f"token_orchestration_rules[{idx}].race_focuses must contain non-empty values")
                    bad_focuses = [token for token in normalized_focuses if token not in ALLOWED_RACE_FOCUSES]
                    if bad_focuses:
                        errors.append(
                            f"token_orchestration_rules[{idx}].race_focuses has unsupported values: {sorted(set(bad_focuses))}"
                        )
            if not isinstance(rule.get("phase"), str) or not str(rule.get("phase")).strip():
                errors.append(f"token_orchestration_rules[{idx}].phase must be a non-empty string")
            else:
                phase_token = str(rule.get("phase")).strip().lower()
                if phase_token not in ALLOWED_PHASES:
                    errors.append(
                        f"token_orchestration_rules[{idx}].phase has unsupported value '{phase_token}' (allowed: {sorted(ALLOWED_PHASES)})"
                    )
            for numeric_key in ("phase_step_eq", "phase_step_gte", "sessions_per_week_gte"):
                if numeric_key in rule and rule.get(numeric_key) is not None:
                    try:
                        value = int(rule.get(numeric_key))
                    except Exception:
                        errors.append(f"token_orchestration_rules[{idx}].{numeric_key} must be an integer")
                        continue
                    if value < 1:
                        errors.append(f"token_orchestration_rules[{idx}].{numeric_key} must be >= 1")
                    if numeric_key == "sessions_per_week_gte" and value > 7:
                        errors.append(f"token_orchestration_rules[{idx}].sessions_per_week_gte must be <= 7")
            if "phase_step_even" in rule and rule.get("phase_step_even") is not None and not isinstance(
                rule.get("phase_step_even"), bool
            ):
                errors.append(f"token_orchestration_rules[{idx}].phase_step_even must be a boolean")
            if "quality_focus_hint" in rule and rule.get("quality_focus_hint") is not None:
                if not isinstance(rule.get("quality_focus_hint"), str) or not str(rule.get("quality_focus_hint")).strip():
                    errors.append(f"token_orchestration_rules[{idx}].quality_focus_hint must be a non-empty string or null")
            if "rationale" in rule and rule.get("rationale") is not None:
                if not isinstance(rule.get("rationale"), str) or not str(rule.get("rationale")).strip():
                    errors.append(f"token_orchestration_rules[{idx}].rationale must be a non-empty string")
            if "action" in rule and rule.get("action") is not None and not isinstance(rule.get("action"), dict):
                errors.append(f"token_orchestration_rules[{idx}].action must be an object or null")
            elif isinstance(rule.get("action"), dict):
                action = rule.get("action") or {}
                action_keys = set(action.keys())
                unknown_action_keys = sorted(action_keys - {"replace_first"})
                if unknown_action_keys:
                    errors.append(
                        f"token_orchestration_rules[{idx}].action has unsupported keys: {unknown_action_keys}"
                    )
                if "replace_first" in action:
                    value = action.get("replace_first")
                    if not isinstance(value, (list, tuple)) or len(value) != 2:
                        errors.append(
                            f"token_orchestration_rules[{idx}].action.replace_first must be a 2-item array [old_contains, new_token]"
                        )
                    else:
                        old_contains, new_token = value
                        if not isinstance(old_contains, str) or not old_contains.strip():
                            errors.append(
                                f"token_orchestration_rules[{idx}].action.replace_first[0] must be a non-empty string"
                            )
                        if not isinstance(new_token, str) or not new_token.strip():
                            errors.append(
                                f"token_orchestration_rules[{idx}].action.replace_first[1] must be a non-empty string"
                            )
    return errors


def save_planner_ruleset_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    errors = validate_planner_ruleset_payload(payload)
    if errors:
        raise ValueError("; ".join(errors))
    path = _default_ruleset_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_file():
        _write_ruleset_backup_snapshots(path, path.read_text())
    else:
        _write_ruleset_backup_snapshots(path, json.dumps(planner_ruleset_snapshot(), indent=2) + "\n")
    path.write_text(json.dumps(payload, indent=2) + "\n")
    _load_ruleset_from_json()
    return planner_ruleset_snapshot()


def rollback_planner_ruleset_payload() -> Dict[str, Any]:
    path = _default_ruleset_file_path()
    backup = _ruleset_backup_path(path)
    if not backup.exists() or not backup.is_file():
        raise FileNotFoundError(str(backup))
    path.write_text(backup.read_text())
    _load_ruleset_from_json()
    return planner_ruleset_snapshot()


def planner_ruleset_backup_snapshots(*, limit: int = 20) -> list[dict[str, Any]]:
    path = _default_ruleset_file_path()
    archive_dir = _ruleset_backup_archive_dir(path)
    latest_backup = _ruleset_backup_path(path)
    items: list[dict[str, Any]] = []

    if latest_backup.exists() and latest_backup.is_file():
        stat = latest_backup.stat()
        items.append(
            {
                "kind": "latest_backup",
                "path": str(latest_backup),
                "filename": latest_backup.name,
                "size_bytes": int(stat.st_size),
                "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
            }
        )

    if archive_dir.exists() and archive_dir.is_dir():
        archives = sorted(
            [p for p in archive_dir.iterdir() if p.is_file()],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for p in archives[: max(0, int(limit))]:
            stat = p.stat()
            items.append(
                {
                    "kind": "archive",
                    "path": str(p),
                    "filename": p.name,
                    "size_bytes": int(stat.st_size),
                    "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
                }
            )

    items.sort(key=lambda item: str(item.get("modified_at")), reverse=True)
    return items[: max(0, int(limit))]


def _quality_rule_paths(payload: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    quality = (payload or {}).get("quality_policy_rules") if isinstance(payload, dict) else None
    if not isinstance(quality, dict):
        return result
    for race_focus, phase_map in quality.items():
        if not isinstance(phase_map, dict):
            continue
        for phase, rule in phase_map.items():
            key = f"{race_focus}.{phase}"
            result[key] = rule
    return result


def _token_rule_name_map(payload: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    token_rules = (payload or {}).get("token_orchestration_rules") if isinstance(payload, dict) else None
    if not isinstance(token_rules, list):
        return result
    for idx, rule in enumerate(token_rules):
        if not isinstance(rule, dict):
            continue
        name = str(rule.get("name") or f"rule_{idx}").strip()
        if not name:
            name = f"rule_{idx}"
        result[name] = rule
    return result


def planner_ruleset_diff_preview(payload: Any, *, baseline: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    current = baseline or planner_ruleset_snapshot()
    incoming = payload if isinstance(payload, dict) else {}
    current_meta = dict(current.get("meta") or {}) if isinstance(current, dict) else {}
    incoming_meta = dict(incoming.get("meta") or {}) if isinstance(incoming, dict) else {}

    meta_changed_keys = sorted(
        key
        for key in set(current_meta.keys()) | set(incoming_meta.keys())
        if key in {"week_policy_version", "progression_track_ruleset_version", "token_orchestration_ruleset_version"}
        and current_meta.get(key) != incoming_meta.get(key)
    )

    current_quality = _quality_rule_paths(current)
    incoming_quality = _quality_rule_paths(incoming)
    quality_added = sorted(set(incoming_quality.keys()) - set(current_quality.keys()))
    quality_removed = sorted(set(current_quality.keys()) - set(incoming_quality.keys()))
    quality_changed = sorted(
        key
        for key in set(current_quality.keys()) & set(incoming_quality.keys())
        if json.dumps(current_quality.get(key), sort_keys=True, default=str)
        != json.dumps(incoming_quality.get(key), sort_keys=True, default=str)
    )

    current_tokens = _token_rule_name_map(current)
    incoming_tokens = _token_rule_name_map(incoming)
    token_added = sorted(set(incoming_tokens.keys()) - set(current_tokens.keys()))
    token_removed = sorted(set(current_tokens.keys()) - set(incoming_tokens.keys()))
    token_changed = sorted(
        key
        for key in set(current_tokens.keys()) & set(incoming_tokens.keys())
        if json.dumps(current_tokens.get(key), sort_keys=True, default=str)
        != json.dumps(incoming_tokens.get(key), sort_keys=True, default=str)
    )

    has_changes = any(
        [
            meta_changed_keys,
            quality_added,
            quality_removed,
            quality_changed,
            token_added,
            token_removed,
            token_changed,
        ]
    )

    return {
        "has_changes": bool(has_changes),
        "meta_changed_keys": meta_changed_keys,
        "quality_policy": {
            "before_count": len(current_quality),
            "after_count": len(incoming_quality),
            "added_paths": quality_added[:20],
            "removed_paths": quality_removed[:20],
            "changed_paths": quality_changed[:20],
            "added_count": len(quality_added),
            "removed_count": len(quality_removed),
            "changed_count": len(quality_changed),
        },
        "token_orchestration": {
            "before_count": len(current_tokens),
            "after_count": len(incoming_tokens),
            "added_rules": token_added[:20],
            "removed_rules": token_removed[:20],
            "changed_rules": token_changed[:20],
            "added_count": len(token_added),
            "removed_count": len(token_removed),
            "changed_count": len(token_changed),
        },
    }


def planner_ruleset_validation_warnings(payload: Any, *, baseline: Optional[Dict[str, Any]] = None) -> list[str]:
    warnings: list[str] = []
    if not isinstance(payload, dict):
        return warnings
    current = baseline or planner_ruleset_snapshot()
    diff = planner_ruleset_diff_preview(payload, baseline=current)
    if not bool(diff.get("has_changes")):
        warnings.append("No effective changes detected compared to the active ruleset.")
        return warnings

    meta = dict(payload.get("meta") or {})
    if not diff.get("meta_changed_keys"):
        warnings.append("Rules changed but version strings were not updated in meta.*_version fields.")

    token_info = dict(diff.get("token_orchestration") or {})
    quality_info = dict(diff.get("quality_policy") or {})
    if abs(int(token_info.get("after_count") or 0) - int(token_info.get("before_count") or 0)) >= 3:
        warnings.append("Token orchestration rule count changed significantly (>= 3). Review plan-preview outputs before saving to production.")
    if abs(int(quality_info.get("after_count") or 0) - int(quality_info.get("before_count") or 0)) >= 4:
        warnings.append("Quality policy rule count changed significantly (>= 4). Validate race/phase coverage before saving.")

    token_rules = payload.get("token_orchestration_rules")
    if isinstance(token_rules, list):
        missing_rationale = 0
        for rule in token_rules:
            if not isinstance(rule, dict):
                continue
            rationale = rule.get("rationale")
            if rationale is None or not str(rationale).strip():
                missing_rationale += 1
        if missing_rationale:
            warnings.append(f"{missing_rationale} token orchestration rules have empty rationale text (reduces coach explainability).")

    return warnings


def planner_ruleset_snapshot() -> Dict[str, Any]:
    token_rules: list[dict[str, Any]] = []
    for raw in _TOKEN_ORCHESTRATION_RULES:
        if not isinstance(raw, dict):
            continue
        rule = dict(raw)
        focuses = rule.get("race_focuses")
        if isinstance(focuses, set):
            rule["race_focuses"] = sorted(str(item) for item in focuses)
        token_rules.append(rule)
    return {
        "meta": {
            "source": PROGRESSION_RULESET_SOURCE,
            "week_policy_version": WEEK_POLICY_VERSION,
            "progression_track_ruleset_version": PROGRESSION_TRACK_RULESET_VERSION,
            "token_orchestration_ruleset_version": TOKEN_ORCHESTRATION_RULESET_VERSION,
            "quality_policy_rule_count": sum(len(v or {}) for v in (_QUALITY_POLICY_RULES or {}).values()),
            "token_orchestration_rule_count": len(token_rules),
        },
        "quality_policy_rules": _QUALITY_POLICY_RULES,
        "token_orchestration_rules": token_rules,
    }


def orchestrate_week_tokens(
    *,
    base_tokens: List[str],
    phase: str,
    race_goal: str,
    week_number: int,
    total_weeks: int,
    phase_step: int,
    phase_weeks_total: int,
    sessions_per_week: int,
) -> Dict[str, Any]:
    del week_number, total_weeks
    tokens = list(base_tokens or [])
    if not tokens:
        return {"tokens": tokens, "rationale": [], "quality_focus_hint": None, "rule_ids": [], "version": TOKEN_ORCHESTRATION_RULESET_VERSION}

    race_focus = race_focus_bucket(race_goal)
    phase_token = str(phase or "").strip().lower()
    rationale: List[str] = [f"phase block step: {phase_step}/{max(phase_weeks_total,1)}"]
    rule_ids: List[str] = []
    quality_focus_hint: Optional[str] = None

    def replace_first(old_contains: str, new_token: str) -> bool:
        needle = old_contains.strip().lower()
        for i, tok in enumerate(tokens):
            if needle in str(tok or "").lower():
                tokens[i] = new_token
                return True
        return False

    for rule in _TOKEN_ORCHESTRATION_RULES:
        if race_focus not in set(rule.get("race_focuses") or []):
            continue
        if str(rule.get("phase") or "") != phase_token:
            continue
        if rule.get("phase_step_eq") is not None and int(phase_step) != int(rule["phase_step_eq"]):
            continue
        if rule.get("phase_step_gte") is not None and int(phase_step) < int(rule["phase_step_gte"]):
            continue
        if rule.get("sessions_per_week_gte") is not None and int(sessions_per_week) < int(rule["sessions_per_week_gte"]):
            continue
        if bool(rule.get("phase_step_even")) and (int(phase_step) % 2 != 0):
            continue

        action = rule.get("action")
        applied = True
        if isinstance(action, dict) and "replace_first" in action:
            old_contains, new_token = action["replace_first"]
            applied = replace_first(str(old_contains), str(new_token))
        if not applied:
            continue

        rule_ids.append(str(rule.get("name") or "rule"))
        rationale.append(str(rule.get("rationale") or "orchestration rule applied"))
        hint = rule.get("quality_focus_hint")
        if hint is None and str(rule.get("name") or "") == "endurance_build_specificity_shift":
            hint = "marathon_specific_endurance" if race_focus == "marathon" else "threshold_marathon_pace_blend"
        if hint:
            quality_focus_hint = str(hint)

    return {
        "tokens": tokens,
        "rationale": rationale,
        "quality_focus_hint": quality_focus_hint,
        "rule_ids": rule_ids,
        "version": TOKEN_ORCHESTRATION_RULESET_VERSION,
    }
