from db.seed import build_session_contract


def test_session_contract_contains_required_sections():
    contract = build_session_contract("Tempo Run", 55, "outdoor", "medium")
    assert contract["intent"] == "lactate_threshold"
    assert contract["energy_system"] == "lactate_threshold"
    assert "structure_json" in contract
    assert "targets_json" in contract
    assert "progression_json" in contract
    assert "regression_json" in contract
    blocks = contract["structure_json"]["blocks"]
    assert len(blocks) == 3
    assert [b["phase"] for b in blocks] == ["warmup", "main_set", "cooldown"]


def test_session_contract_targets_include_pace_label():
    contract = build_session_contract("VO2max Intervals", 45, "treadmill", "long")
    primary = contract["targets_json"]["primary"]
    assert "pace_label" in primary
    assert primary["pace_label"] == "I"
    assert "rpe_range" in primary
