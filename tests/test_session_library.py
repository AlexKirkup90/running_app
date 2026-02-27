from copy import deepcopy

from core.services.session_library import default_progression, default_regression, default_structure, default_targets, validate_session_payload


def _valid_payload():
    return {
        "name": "Easy Run 45min outdoor medium",
        "category": "Easy Run",
        "intent": "easy_aerobic",
        "energy_system": "aerobic_base",
        "tier": "medium",
        "duration_min": 45,
        "structure_json": default_structure(45),
        "targets_json": default_targets(),
        "progression_json": default_progression(),
        "regression_json": default_regression(),
        "prescription": "Easy run with clear warmup, main set and cooldown.",
        "coaching_notes": "Adjust by readiness and recent load trends.",
    }


def test_validate_session_payload_valid_contract():
    payload = _valid_payload()
    errors = validate_session_payload(payload)
    assert errors == []


def test_validate_session_payload_missing_main_set_fails():
    payload = _valid_payload()
    payload["structure_json"] = deepcopy(payload["structure_json"])
    payload["structure_json"]["blocks"] = [b for b in payload["structure_json"]["blocks"] if b["phase"] != "main_set"]
    errors = validate_session_payload(payload)
    assert any("missing required phases" in e for e in errors)


def test_validate_session_payload_invalid_rpe_range_fails():
    payload = _valid_payload()
    payload["targets_json"] = deepcopy(payload["targets_json"])
    payload["targets_json"]["primary"]["rpe_range"] = [8, 4]
    errors = validate_session_payload(payload)
    assert any("rpe_range" in e for e in errors)


def test_validate_session_payload_daniels_methodology_requires_main_set_intensity_code():
    payload = _valid_payload()
    payload["intent"] = "threshold"
    payload["energy_system"] = "lactate_threshold"
    payload["targets_json"] = deepcopy(payload["targets_json"])
    payload["targets_json"]["methodology"] = "daniels_vdot"
    payload["targets_json"]["primary"]["intensity_code"] = "T"
    errors = validate_session_payload(payload)
    assert any("main_set" in e and "intensity_code" in e for e in errors)


def test_validate_session_payload_daniels_methodology_valid_when_coded():
    payload = _valid_payload()
    payload["intent"] = "threshold"
    payload["energy_system"] = "lactate_threshold"
    payload["structure_json"] = deepcopy(payload["structure_json"])
    payload["structure_json"]["methodology"] = "daniels_vdot"
    for block in payload["structure_json"]["blocks"]:
        target = dict(block["target"])
        if block["phase"] == "main_set":
            target["intensity_code"] = "T"
        else:
            target["intensity_code"] = "E"
        block["target"] = target
    payload["targets_json"] = deepcopy(payload["targets_json"])
    payload["targets_json"]["methodology"] = "daniels_vdot"
    payload["targets_json"]["primary"]["pace_zone"] = "Z4"
    payload["targets_json"]["primary"]["hr_zone"] = "Z3-Z4"
    payload["targets_json"]["primary"]["rpe_range"] = [6, 7]
    payload["targets_json"]["primary"]["intensity_code"] = "T"
    errors = validate_session_payload(payload)
    assert errors == []
