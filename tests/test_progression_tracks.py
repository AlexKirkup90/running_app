from core.services import progression_tracks as pt


def test_progression_ruleset_loads_from_json_file():
    assert isinstance(pt.PROGRESSION_RULESET_SOURCE, str)
    assert pt.PROGRESSION_RULESET_SOURCE
    assert pt.PROGRESSION_RULESET_SOURCE.endswith(".json")
    assert pt.WEEK_POLICY_VERSION.startswith("jd_")
    assert pt.PROGRESSION_TRACK_RULESET_VERSION.startswith("jd_")
    assert pt.TOKEN_ORCHESTRATION_RULESET_VERSION.startswith("jd_")


def test_progression_ruleset_behavior_still_operates():
    policy = pt.week_quality_policy(phase="Base", race_goal="10K", week_number=1, total_weeks=8)
    assert policy["race_focus"] == "10k"
    assert policy["phase"] == "base"
    assert isinstance(policy["rationale"], list)

    prog = pt.week_progression_tracks(
        phase="Base",
        race_goal="10K",
        week_number=2,
        total_weeks=8,
        phase_step=2,
        phase_weeks_total=3,
    )
    assert isinstance(prog["tracks"], list)
    assert prog["tracks"]
    assert isinstance(prog["summary"], str)

    orchestration = pt.orchestrate_week_tokens(
        base_tokens=["Easy Run", "Long Run", "Strides / Neuromuscular", "Recovery Run"],
        phase="base",
        race_goal="10K",
        week_number=2,
        total_weeks=8,
        phase_step=2,
        phase_weeks_total=3,
        sessions_per_week=4,
    )
    assert isinstance(orchestration["tokens"], list)
    assert isinstance(orchestration["rationale"], list)
    assert isinstance(orchestration["rule_ids"], list)


def test_progression_ruleset_semantic_validation_catches_bad_values():
    snapshot = pt.planner_ruleset_snapshot()
    payload = dict(snapshot)
    payload["quality_policy_rules"] = dict(snapshot["quality_policy_rules"])
    payload["quality_policy_rules"]["bad_focus"] = {
        "nophase": {"quality_focus": "", "prefer_m_finish_long_run": "yes"}
    }
    token_rules = list(snapshot["token_orchestration_rules"])
    token_rules.append(
        {
            "name": token_rules[0]["name"],  # duplicate on purpose
            "race_focuses": ["unknown_focus"],
            "phase": "nophase",
            "phase_step_gte": 0,
            "sessions_per_week_gte": 8,
            "phase_step_even": "true",
            "action": {"replace_first": ["", 42]},
        }
    )
    payload["token_orchestration_rules"] = token_rules

    errors = pt.validate_planner_ruleset_payload(payload)
    joined = "\n".join(errors)
    assert "unsupported race focus" in joined
    assert "unsupported phase" in joined
    assert "quality_focus must be a non-empty string" in joined
    assert "prefer_m_finish_long_run must be a boolean" in joined
    assert "duplicates a prior rule name" in joined
    assert "sessions_per_week_gte must be <= 7" in joined


def test_progression_ruleset_save_writes_backup_snapshots(tmp_path, monkeypatch):
    ruleset_path = tmp_path / "planner_ruleset.json"
    monkeypatch.setenv("PROGRESSION_TRACK_RULESET_PATH", str(ruleset_path))
    pt._load_ruleset_from_json()
    try:
        snapshot = pt.planner_ruleset_snapshot()
        pt.save_planner_ruleset_payload(snapshot)
        backups = pt.planner_ruleset_backup_snapshots(limit=10)
        assert backups
        assert any(item["kind"] == "latest_backup" for item in backups)
        assert any(item["kind"] == "archive" for item in backups)
    finally:
        monkeypatch.delenv("PROGRESSION_TRACK_RULESET_PATH", raising=False)
        pt._load_ruleset_from_json()
