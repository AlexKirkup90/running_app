"""Extended tests for session library validation."""

from __future__ import annotations

from core.services.session_library import (
    default_progression,
    default_regression,
    default_structure,
    default_targets,
    valid_zone_label,
    validate_session_payload,
    validate_structure_contract,
)


def test_valid_zone_label_zones():
    assert valid_zone_label("Z1") is True
    assert valid_zone_label("Z5") is True
    assert valid_zone_label("Z1-Z2") is True


def test_valid_zone_label_special():
    assert valid_zone_label("Race Pace") is True
    assert valid_zone_label("Benchmark") is True
    assert valid_zone_label("Strides") is True
    assert valid_zone_label("N/A") is True


def test_valid_zone_label_invalid():
    assert valid_zone_label("") is False
    assert valid_zone_label("Z6") is False
    assert valid_zone_label("fast") is False


def test_default_structure_reasonable():
    s = default_structure(60)
    blocks = s["blocks"]
    assert len(blocks) == 3
    phases = {b["phase"] for b in blocks}
    assert phases == {"warmup", "main_set", "cooldown"}
    total = sum(b["duration_min"] for b in blocks)
    assert 45 <= total <= 75  # within 75-125% of 60


def test_default_structure_short():
    s = default_structure(20)
    blocks = s["blocks"]
    total = sum(b["duration_min"] for b in blocks)
    assert total >= 20


def test_default_targets_has_primary():
    t = default_targets()
    assert "primary" in t
    assert "pace_zone" in t["primary"]
    assert "hr_zone" in t["primary"]
    assert "rpe_range" in t["primary"]


def test_default_progression_not_empty():
    p = default_progression()
    assert len(p) > 0
    assert all(isinstance(v, str) for v in p.values())


def test_default_regression_not_empty():
    r = default_regression()
    assert len(r) > 0


def test_validate_structure_contract_valid():
    s = default_structure(45)
    errors = validate_structure_contract(s, 45)
    assert errors == []


def test_validate_structure_contract_not_dict():
    errors = validate_structure_contract("not a dict", 45)
    assert len(errors) == 1


def test_validate_structure_contract_empty_blocks():
    errors = validate_structure_contract({"blocks": []}, 45)
    assert len(errors) == 1


def test_validate_session_payload_all_required():
    payload = {
        "name": "Test",
        "category": "Easy Run",
        "intent": "easy_aerobic",
        "energy_system": "aerobic_base",
        "tier": "medium",
        "prescription": "Do the run nicely",
        "coaching_notes": "Coach says relax",
        "duration_min": 45,
        "structure_json": default_structure(45),
        "targets_json": default_targets(),
        "progression_json": default_progression(),
        "regression_json": default_regression(),
    }
    errors = validate_session_payload(payload)
    assert errors == []


def test_validate_session_payload_missing_name():
    payload = {
        "name": "",
        "category": "Easy Run",
        "intent": "easy_aerobic",
        "energy_system": "aerobic_base",
        "tier": "medium",
        "prescription": "Do the run",
        "coaching_notes": "Notes here",
        "duration_min": 45,
        "structure_json": default_structure(45),
        "targets_json": default_targets(),
        "progression_json": default_progression(),
        "regression_json": default_regression(),
    }
    errors = validate_session_payload(payload)
    assert any("name" in e for e in errors)
