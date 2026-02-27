from __future__ import annotations

from typing import Any

from tests.test_api_fastapi import _auth_headers, _build_client


def _assert_exact_keys(obj: dict[str, Any], expected: set[str]) -> None:
    assert isinstance(obj, dict)
    assert set(obj.keys()) == expected


def _assert_number(value: Any) -> None:
    assert isinstance(value, (int, float))


def test_today_endpoint_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "athlete1", "AthletePass!234")
        resp = client.get("/api/v1/athletes/1/today", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        _assert_exact_keys(
            body,
            {
                "athlete_id",
                "day",
                "readiness_score",
                "readiness_band",
                "checkin_present",
                "planned_session",
                "adapted_session",
                "training_load_summary",
                "context",
            },
        )
        assert isinstance(body["athlete_id"], int)
        assert isinstance(body["day"], str)
        assert isinstance(body["readiness_score"], (int, float))
        assert isinstance(body["readiness_band"], str)
        assert isinstance(body["checkin_present"], bool)

        planned = body["planned_session"]
        _assert_exact_keys(
            planned,
            {"exists", "date", "session_name", "source_template_name", "status", "template_found", "template_id", "structure_json"},
        )
        assert isinstance(planned["structure_json"], dict)

        adapted = body["adapted_session"]
        _assert_exact_keys(adapted, {"action", "reason", "session"})
        assert isinstance(adapted["action"], str)
        assert isinstance(adapted["reason"], str)
        _assert_exact_keys(adapted["session"], {"version", "blocks"})
        assert isinstance(adapted["session"]["blocks"], list)
        assert adapted["session"]["blocks"]

        first_block = adapted["session"]["blocks"][0]
        _assert_exact_keys(
            first_block,
            {"phase", "duration_min", "instructions", "target", "target_pace_range", "target_hr_range", "intervals"},
        )
        assert isinstance(first_block["phase"], str)
        assert isinstance(first_block["duration_min"], int)
        assert isinstance(first_block["instructions"], str)
        assert isinstance(first_block["target"], dict)
        assert isinstance(first_block["target_pace_range"], str)
        assert isinstance(first_block["target_hr_range"], str)
        assert isinstance(first_block["intervals"], list)
        _assert_exact_keys(first_block["target"], {"pace_zone", "hr_zone", "rpe_range"})
        assert isinstance(first_block["target"]["pace_zone"], str)
        assert isinstance(first_block["target"]["hr_zone"], str)
        assert isinstance(first_block["target"]["rpe_range"], list)

        tls = body["training_load_summary"]
        _assert_exact_keys(
            tls,
            {"acute_chronic_ratio", "weekly_load_total", "avg_daily_load", "monotony", "strain", "risk"},
        )
        _assert_number(tls["acute_chronic_ratio"])
        _assert_number(tls["weekly_load_total"])
        _assert_number(tls["avg_daily_load"])
        assert tls["monotony"] is None or isinstance(tls["monotony"], (int, float))
        assert tls["strain"] is None or isinstance(tls["strain"], (int, float))
        assert isinstance(tls["risk"], str)

        context = body["context"]
        _assert_exact_keys(context, {"checkin_day", "pain_recent", "next_event", "days_to_event"})
        assert isinstance(context["checkin_day"], str)
        assert isinstance(context["pain_recent"], bool)
        assert isinstance(context["days_to_event"], int)
        _assert_exact_keys(context["next_event"], {"id", "name", "distance", "event_date"})
        assert isinstance(context["next_event"]["id"], int)
        assert isinstance(context["next_event"]["name"], str)
        assert isinstance(context["next_event"]["distance"], str)
        assert isinstance(context["next_event"]["event_date"], str)


def test_analytics_endpoint_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "athlete1", "AthletePass!234")
        resp = client.get("/api/v1/athletes/1/analytics", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        _assert_exact_keys(
            body,
            {
                "athlete_id",
                "available",
                "reason",
                "fitness_fatigue",
                "vdot_history",
                "intensity_distribution",
                "weekly_rollups",
            },
        )
        assert isinstance(body["athlete_id"], int)
        assert isinstance(body["available"], bool)
        assert body["available"] is True
        assert body["reason"] is None or isinstance(body["reason"], str)

        ff = body["fitness_fatigue"]
        _assert_exact_keys(ff, {"series", "latest", "params"})
        assert isinstance(ff["series"], list)
        assert ff["series"]
        ff_item = ff["series"][0]
        _assert_exact_keys(ff_item, {"date", "load_score", "duration_min", "ctl", "atl", "tsb"})
        assert isinstance(ff_item["date"], str)
        _assert_number(ff_item["load_score"])
        assert isinstance(ff_item["duration_min"], int)
        _assert_number(ff_item["ctl"])
        _assert_number(ff_item["atl"])
        _assert_number(ff_item["tsb"])
        _assert_exact_keys(ff["latest"], {"date", "load_score", "duration_min", "ctl", "atl", "tsb"})
        _assert_exact_keys(ff["params"], {"ctl_tau_days", "atl_tau_days"})
        assert isinstance(ff["params"]["ctl_tau_days"], int)
        assert isinstance(ff["params"]["atl_tau_days"], int)

        vdot = body["vdot_history"]
        _assert_exact_keys(vdot, {"series", "latest"})
        assert isinstance(vdot["series"], list)
        assert vdot["series"]
        vdot_item = vdot["series"][0]
        _assert_exact_keys(vdot_item, {"date", "vdot", "distance_km", "duration_min"})
        assert isinstance(vdot_item["date"], str)
        _assert_number(vdot_item["vdot"])
        _assert_number(vdot_item["distance_km"])
        _assert_number(vdot_item["duration_min"])

        intensity = body["intensity_distribution"]
        _assert_exact_keys(intensity, {"buckets", "total_minutes", "basis"})
        assert isinstance(intensity["buckets"], list)
        assert len(intensity["buckets"]) == 3
        for bucket in intensity["buckets"]:
            _assert_exact_keys(bucket, {"label", "value", "percent"})
            assert isinstance(bucket["label"], str)
            _assert_number(bucket["value"])
            _assert_number(bucket["percent"])
        _assert_number(intensity["total_minutes"])
        assert isinstance(intensity["basis"], str)

        rollups = body["weekly_rollups"]
        _assert_exact_keys(rollups, {"athlete_id", "weeks", "items"})
        assert isinstance(rollups["athlete_id"], int)
        assert isinstance(rollups["weeks"], int)
        assert isinstance(rollups["items"], list)
        assert rollups["items"]
        rollup_item = rollups["items"][0]
        _assert_exact_keys(rollup_item, {"week", "duration_min", "load_score", "sessions"})
        assert isinstance(rollup_item["week"], str)
        _assert_number(rollup_item["duration_min"])
        _assert_number(rollup_item["load_score"])
        assert isinstance(rollup_item["sessions"], int)


def test_predictions_endpoint_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "athlete1", "AthletePass!234")
        resp = client.get("/api/v1/athletes/1/predictions", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        _assert_exact_keys(body, {"athlete_id", "available", "reason", "predictions", "benchmark"})
        assert isinstance(body["athlete_id"], int)
        assert isinstance(body["available"], bool)
        assert body["available"] is True
        assert body["reason"] is None or isinstance(body["reason"], str)

        benchmark = body["benchmark"]
        _assert_exact_keys(
            benchmark,
            {"log_id", "date", "distance_km", "duration_min", "avg_pace_sec_per_km", "load_score"},
        )
        assert isinstance(benchmark["log_id"], int)
        assert isinstance(benchmark["date"], str)
        _assert_number(benchmark["distance_km"])
        assert isinstance(benchmark["duration_min"], int)
        assert benchmark["avg_pace_sec_per_km"] is None or isinstance(benchmark["avg_pace_sec_per_km"], (int, float))
        _assert_number(benchmark["load_score"])

        preds = body["predictions"]
        _assert_exact_keys(preds, {"method", "vdot", "benchmark_distance_km", "benchmark_time", "distances"})
        assert isinstance(preds["method"], str)
        assert preds["vdot"] is None or isinstance(preds["vdot"], (int, float))
        _assert_number(preds["benchmark_distance_km"])
        assert isinstance(preds["benchmark_time"], str)
        _assert_exact_keys(preds["distances"], {"5K", "10K", "Half Marathon", "Marathon"})
        for _, row in preds["distances"].items():
            _assert_exact_keys(
                row,
                {"distance_km", "predicted_seconds", "predicted_time", "riegel_seconds", "daniels_seconds", "method"},
            )
            _assert_number(row["distance_km"])
            assert isinstance(row["predicted_seconds"], int)
            assert isinstance(row["predicted_time"], str)
            assert isinstance(row["riegel_seconds"], int)
            assert row["daniels_seconds"] is None or isinstance(row["daniels_seconds"], int)
            assert isinstance(row["method"], str)


def test_athlete_plan_status_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "athlete1", "AthletePass!234")
        resp = client.get("/api/v1/athletes/1/plan-status", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        _assert_exact_keys(
            body,
            {"athlete_id", "date", "has_plan", "plan", "upcoming_week_start", "upcoming_week_end", "upcoming_sessions"},
        )
        assert isinstance(body["athlete_id"], int)
        assert isinstance(body["date"], str)
        assert isinstance(body["has_plan"], bool)
        assert isinstance(body["upcoming_week_start"], str)
        assert isinstance(body["upcoming_week_end"], str)
        assert isinstance(body["upcoming_sessions"], list)
        if body["plan"] is not None:
            _assert_exact_keys(body["plan"], {"id", "race_goal", "status", "start_date", "weeks", "sessions_per_week"})
            assert isinstance(body["plan"]["id"], int)
        if body["upcoming_sessions"]:
            row = body["upcoming_sessions"][0]
            _assert_exact_keys(row, {"session_day", "session_name", "status", "source_template_name"})


def test_coach_command_center_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        resp = client.get("/api/v1/coach/command-center?queue_limit=5&recent_decisions_limit=5", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        _assert_exact_keys(
            body,
            {"portfolio", "open_interventions_total", "ranked_queue_limit", "ranked_queue", "recent_decisions", "ranking_version"},
        )
        assert isinstance(body["open_interventions_total"], int)
        assert isinstance(body["ranked_queue_limit"], int)
        assert isinstance(body["ranking_version"], str)

        portfolio = body["portfolio"]
        _assert_exact_keys(
            portfolio,
            {
                "athletes_total",
                "athletes_active",
                "average_readiness",
                "active_interventions",
                "weekly_compliance_rate",
                "metrics",
            },
        )
        assert isinstance(portfolio["athletes_total"], int)
        assert isinstance(portfolio["athletes_active"], int)
        assert portfolio["average_readiness"] is None or isinstance(portfolio["average_readiness"], (int, float))
        assert isinstance(portfolio["active_interventions"], int)
        assert portfolio["weekly_compliance_rate"] is None or isinstance(portfolio["weekly_compliance_rate"], (int, float))
        assert isinstance(portfolio["metrics"], dict)

        assert isinstance(body["ranked_queue"], list)
        if body["ranked_queue"]:
            first = body["ranked_queue"][0]
            _assert_exact_keys(
                first,
                {
                    "id",
                    "athlete_id",
                    "athlete_name",
                    "action_type",
                    "status",
                    "risk_score",
                    "confidence_score",
                    "created_at",
                    "cooldown_until",
                    "why_factors",
                    "expected_impact",
                    "guardrail_pass",
                    "guardrail_reason",
                    "risk_band",
                    "auto_apply_eligible",
                    "review_reason",
                    "review_reason_detail",
                    "auto_revert_available",
                    "auto_revert_block_reason",
                    "priority_score",
                    "priority_components",
                    "priority_reasons",
                    "ranking_version",
                },
            )
            _assert_number(first["priority_score"])
            assert isinstance(first["ranking_version"], str)


def test_coach_planner_ruleset_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        resp = client.get("/api/v1/coach/planner-ruleset", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()

        _assert_exact_keys(body, {"meta", "quality_policy_rules", "token_orchestration_rules"})
        meta = body["meta"]
        _assert_exact_keys(
            meta,
            {
                "source",
                "week_policy_version",
                "progression_track_ruleset_version",
                "token_orchestration_ruleset_version",
                "quality_policy_rule_count",
                "token_orchestration_rule_count",
            },
        )
        assert isinstance(meta["source"], str)
        assert isinstance(meta["week_policy_version"], str)
        assert isinstance(meta["progression_track_ruleset_version"], str)
        assert isinstance(meta["token_orchestration_ruleset_version"], str)
        assert isinstance(meta["quality_policy_rule_count"], int)
        assert isinstance(meta["token_orchestration_rule_count"], int)
        assert isinstance(body["quality_policy_rules"], dict)
        assert isinstance(body["token_orchestration_rules"], list)
        if body["token_orchestration_rules"]:
            assert isinstance(body["token_orchestration_rules"][0], dict)

        validate_resp = client.post("/api/v1/coach/planner-ruleset/validate", json={"ruleset": body}, headers=headers)
        assert validate_resp.status_code == 200, validate_resp.text
        validate_body = validate_resp.json()
        _assert_exact_keys(validate_body, {"valid", "errors", "warnings", "diff_preview"})
        assert isinstance(validate_body["valid"], bool)
        assert isinstance(validate_body["errors"], list)
        assert isinstance(validate_body["warnings"], list)
        assert isinstance(validate_body["diff_preview"], dict)

        history_resp = client.get("/api/v1/coach/planner-ruleset/history?offset=0&limit=5", headers=headers)
        assert history_resp.status_code == 200, history_resp.text
        history = history_resp.json()
        _assert_exact_keys(history, {"total", "offset", "limit", "scope_counts", "items"})
        assert isinstance(history["total"], int)
        assert isinstance(history["offset"], int)
        assert isinstance(history["limit"], int)
        assert isinstance(history["scope_counts"], dict)
        assert isinstance(history["items"], list)
        if history["items"]:
            first = history["items"][0]
            _assert_exact_keys(first, {"id", "scope", "actor_user_id", "actor_username", "created_at", "payload"})

        backups_resp = client.get("/api/v1/coach/planner-ruleset/backups?limit=5", headers=headers)
        assert backups_resp.status_code == 200, backups_resp.text
        backups = backups_resp.json()
        _assert_exact_keys(backups, {"total", "limit", "items"})
        assert isinstance(backups["total"], int)
        assert isinstance(backups["limit"], int)
        assert isinstance(backups["items"], list)
        if backups["items"]:
            first = backups["items"][0]
            _assert_exact_keys(first, {"kind", "path", "filename", "size_bytes", "modified_at"})


def test_coach_automation_policy_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        resp = client.get("/api/v1/coach/automation-policy", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        _assert_exact_keys(
            body,
            {
                "enabled",
                "default_auto_apply_low_risk",
                "default_auto_apply_confidence_min",
                "default_auto_apply_risk_max",
                "apply_when_athlete_pref_missing",
                "apply_when_athlete_pref_disabled",
                "updated_at",
                "updated_by_user_id",
                "source",
            },
        )
        assert isinstance(body["enabled"], bool)
        assert isinstance(body["default_auto_apply_low_risk"], bool)
        _assert_number(body["default_auto_apply_confidence_min"])
        _assert_number(body["default_auto_apply_risk_max"])
        assert isinstance(body["apply_when_athlete_pref_missing"], bool)
        assert isinstance(body["apply_when_athlete_pref_disabled"], bool)
        assert body["updated_at"] is None or isinstance(body["updated_at"], str)
        assert body["updated_by_user_id"] is None or isinstance(body["updated_by_user_id"], int)
        assert isinstance(body["source"], str)


def test_events_and_preferences_contracts(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        athlete_headers = _auth_headers(client, "athlete1", "AthletePass!234")

        events_resp = client.get("/api/v1/athletes/1/events", headers=athlete_headers)
        assert events_resp.status_code == 200, events_resp.text
        events = events_resp.json()
        _assert_exact_keys(events, {"total", "offset", "limit", "items"})
        assert isinstance(events["total"], int)
        assert isinstance(events["offset"], int)
        assert isinstance(events["limit"], int)
        assert isinstance(events["items"], list)
        assert events["items"]
        event_item = events["items"][0]
        _assert_exact_keys(event_item, {"id", "athlete_id", "name", "event_date", "distance"})
        assert isinstance(event_item["id"], int)
        assert isinstance(event_item["athlete_id"], int)
        assert isinstance(event_item["name"], str)
        assert isinstance(event_item["event_date"], str)
        assert isinstance(event_item["distance"], str)

        prefs_resp = client.get("/api/v1/athletes/1/preferences", headers=athlete_headers)
        assert prefs_resp.status_code == 200, prefs_resp.text
        prefs = prefs_resp.json()
        _assert_exact_keys(
            prefs,
            {
                "athlete_id",
                "reminder_enabled",
                "reminder_training_days",
                "privacy_ack",
                "automation_mode",
                "auto_apply_low_risk",
                "auto_apply_confidence_min",
                "auto_apply_risk_max",
                "preferred_training_days",
                "preferred_long_run_day",
            },
        )
        assert isinstance(prefs["athlete_id"], int)
        assert isinstance(prefs["reminder_enabled"], bool)
        assert isinstance(prefs["reminder_training_days"], list)
        assert isinstance(prefs["privacy_ack"], bool)
        assert isinstance(prefs["automation_mode"], str)
        assert isinstance(prefs["auto_apply_low_risk"], bool)
        _assert_number(prefs["auto_apply_confidence_min"])
        _assert_number(prefs["auto_apply_risk_max"])
        assert isinstance(prefs["preferred_training_days"], list)
        assert prefs["preferred_long_run_day"] is None or isinstance(prefs["preferred_long_run_day"], str)


def test_session_library_contracts(tmp_path, monkeypatch):
    from core.services.session_library import default_progression, default_regression, default_structure, default_targets

    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")

        list_resp = client.get("/api/v1/coach/session-library", headers=coach_headers)
        assert list_resp.status_code == 200, list_resp.text
        body = list_resp.json()
        _assert_exact_keys(body, {"total", "offset", "limit", "items"})
        assert isinstance(body["items"], list)
        assert body["items"]
        item = body["items"][0]
        _assert_exact_keys(
            item,
            {"id", "name", "category", "intent", "energy_system", "tier", "is_treadmill", "duration_min", "methodology", "status", "duplicate_of_template_id"},
        )
        assert isinstance(item["id"], int)
        assert isinstance(item["name"], str)
        assert isinstance(item["is_treadmill"], bool)
        assert isinstance(item["duration_min"], int)
        assert isinstance(item["status"], str)
        assert item["duplicate_of_template_id"] is None or isinstance(item["duplicate_of_template_id"], int)

        detail_resp = client.get("/api/v1/coach/session-library/1", headers=coach_headers)
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()
        _assert_exact_keys(
            detail,
            {
                "id",
                "name",
                "category",
                "intent",
                "energy_system",
                "tier",
                "is_treadmill",
                "duration_min",
                "methodology",
                "status",
                "duplicate_of_template_id",
                "structure_json",
                "targets_json",
                "progression_json",
                "regression_json",
                "prescription",
                "coaching_notes",
            },
        )
        assert isinstance(detail["structure_json"], dict)
        assert isinstance(detail["targets_json"], dict)
        assert isinstance(detail["progression_json"], dict)
        assert isinstance(detail["regression_json"], dict)
        assert isinstance(detail["prescription"], str)
        assert isinstance(detail["coaching_notes"], str)

        normalize_resp = client.post("/api/v1/coach/session-library/1/normalize-metadata", headers=coach_headers)
        assert normalize_resp.status_code == 200, normalize_resp.text
        normalize_body = normalize_resp.json()
        _assert_exact_keys(
            normalize_body,
            {
                "status",
                "message",
                "template",
                "applied_change_count",
                "applied_changes",
                "issue_counts_before",
                "issue_counts_after",
            },
        )
        assert isinstance(normalize_body["status"], str)
        assert isinstance(normalize_body["message"], str)
        assert isinstance(normalize_body["applied_change_count"], int)
        assert isinstance(normalize_body["applied_changes"], list)
        assert isinstance(normalize_body["issue_counts_before"], dict)
        assert isinstance(normalize_body["issue_counts_after"], dict)
        if normalize_body["applied_changes"]:
            change = normalize_body["applied_changes"][0]
            _assert_exact_keys(change, {"field", "before", "after"})

        gov_resp = client.post(
            "/api/v1/coach/session-library/1/governance-action",
            json={"action": "mark_canonical"},
            headers=coach_headers,
        )
        assert gov_resp.status_code == 200, gov_resp.text
        gov_body = gov_resp.json()
        _assert_exact_keys(gov_body, {"status", "action", "message", "template"})
        assert isinstance(gov_body["status"], str)
        assert isinstance(gov_body["action"], str)
        assert isinstance(gov_body["message"], str)
        assert isinstance(gov_body["template"], dict)

        validate_payload = {
            "name": "Contract Session",
            "category": "Run",
            "intent": "easy_aerobic",
            "energy_system": "aerobic_base",
            "tier": "easy",
            "is_treadmill": False,
            "duration_min": 45,
            "structure_json": default_structure(45),
            "targets_json": default_targets(),
            "progression_json": default_progression(),
            "regression_json": default_regression(),
            "prescription": "Easy run with structure.",
            "coaching_notes": "Stay smooth.",
        }
        validate_resp = client.post("/api/v1/coach/session-library/validate", json=validate_payload, headers=coach_headers)
        assert validate_resp.status_code == 200, validate_resp.text
        validate_body = validate_resp.json()
        _assert_exact_keys(validate_body, {"valid", "errors"})
        assert isinstance(validate_body["valid"], bool)
        assert isinstance(validate_body["errors"], list)

        gold_pack_resp = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=coach_headers)
        assert gold_pack_resp.status_code == 200, gold_pack_resp.text
        gold_pack = gold_pack_resp.json()
        _assert_exact_keys(gold_pack, {"status", "message", "created_count", "updated_count", "template_count"})
        assert isinstance(gold_pack["status"], str)
        assert isinstance(gold_pack["message"], str)
        assert isinstance(gold_pack["created_count"], int)
        assert isinstance(gold_pack["updated_count"], int)
        assert isinstance(gold_pack["template_count"], int)

        bulk_legacy_resp = client.post(
            "/api/v1/coach/session-library/governance/bulk-deprecate-legacy",
            json={"dry_run": True, "sample_limit": 5},
            headers=coach_headers,
        )
        assert bulk_legacy_resp.status_code == 200, bulk_legacy_resp.text
        bulk_legacy = bulk_legacy_resp.json()
        _assert_exact_keys(
            bulk_legacy,
            {
                "status",
                "action",
                "message",
                "dry_run",
                "template_count_scanned",
                "candidate_count",
                "changed_count",
                "unchanged_count",
                "sample_limit",
                "samples",
            },
        )
        assert isinstance(bulk_legacy["status"], str)
        assert isinstance(bulk_legacy["action"], str)
        assert isinstance(bulk_legacy["message"], str)
        assert isinstance(bulk_legacy["dry_run"], bool)
        for k in ("template_count_scanned", "candidate_count", "changed_count", "unchanged_count", "sample_limit"):
            assert isinstance(bulk_legacy[k], int)
        assert isinstance(bulk_legacy["samples"], list)
        if bulk_legacy["samples"]:
            _assert_exact_keys(
                bulk_legacy["samples"][0],
                {"id", "name", "category", "intent", "energy_system", "tier", "is_treadmill", "duration_min", "status", "duplicate_of_template_id"},
            )

        bulk_canon_resp = client.post(
            "/api/v1/coach/session-library/governance/bulk-canonicalize-duplicates",
            json={"dry_run": True, "sample_limit": 5},
            headers=coach_headers,
        )
        assert bulk_canon_resp.status_code == 200, bulk_canon_resp.text
        bulk_canon = bulk_canon_resp.json()
        _assert_exact_keys(
            bulk_canon,
            {
                "status",
                "action",
                "message",
                "dry_run",
                "candidate_count",
                "reviewed_count",
                "applied_count",
                "skipped_count",
                "sample_limit",
                "applied",
                "skipped",
            },
        )
        assert isinstance(bulk_canon["status"], str)
        assert isinstance(bulk_canon["action"], str)
        assert isinstance(bulk_canon["message"], str)
        assert isinstance(bulk_canon["dry_run"], bool)
        for k in ("candidate_count", "reviewed_count", "applied_count", "skipped_count", "sample_limit"):
            assert isinstance(bulk_canon[k], int)
        assert isinstance(bulk_canon["applied"], list)
        assert isinstance(bulk_canon["skipped"], list)
        if bulk_canon["applied"]:
            item = bulk_canon["applied"][0]
            _assert_exact_keys(
                item,
                {"candidate_kind", "score", "reason_tags", "action", "decision_reason", "target", "duplicate"},
            )
            _assert_exact_keys(
                item["target"],
                {"id", "name", "category", "intent", "energy_system", "tier", "is_treadmill", "duration_min", "status", "duplicate_of_template_id"},
            )
            _assert_exact_keys(
                item["duplicate"],
                {"id", "name", "category", "intent", "energy_system", "tier", "is_treadmill", "duration_min", "status", "duplicate_of_template_id"},
            )
        if bulk_canon["skipped"]:
            item = bulk_canon["skipped"][0]
            _assert_exact_keys(
                item,
                {"candidate_kind", "score", "reason_tags", "reason_code", "message", "left", "right"},
            )


def test_plan_preview_and_detail_contracts(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        payload = {
            "athlete_id": 1,
            "race_goal": "10K",
            "weeks": 4,
            "start_date": "2026-01-05",
            "sessions_per_week": 4,
            "max_session_min": 120,
            "preferred_days": ["Mon", "Wed", "Fri", "Sun"],
            "preferred_long_run_day": "Sun",
        }

        preview_resp = client.post("/api/v1/coach/plans/preview", json=payload, headers=coach_headers)
        assert preview_resp.status_code == 200, preview_resp.text
        preview = preview_resp.json()
        _assert_exact_keys(
            preview,
            {
                "athlete_id",
                "race_goal",
                "weeks",
                "start_date",
                "sessions_per_week",
                "max_session_min",
                "preferred_days",
                "preferred_long_run_day",
                "weeks_detail",
            },
        )
        assert isinstance(preview["weeks_detail"], list)
        assert preview["weeks_detail"]
        w = preview["weeks_detail"][0]
        _assert_exact_keys(
            w,
            {
                "week_number",
                "phase",
                "week_start",
                "week_end",
                "target_load",
                "long_run_minutes",
                "planned_load_estimate",
                "planned_minutes_estimate",
                "planned_long_run_minutes",
                "week_policy_version",
                "quality_focus",
                "coach_summary",
                "progression_tracks",
                "week_policy_rationale",
                "sessions_order",
                "assignments",
                "selection_strategy_version",
            },
        )
        assert isinstance(w["assignments"], list)
        assert w["assignments"]
        assert w["planned_load_estimate"] is None or isinstance(w["planned_load_estimate"], (int, float))
        assert w["planned_minutes_estimate"] is None or isinstance(w["planned_minutes_estimate"], int)
        assert w["planned_long_run_minutes"] is None or isinstance(w["planned_long_run_minutes"], int)
        assert w["week_policy_version"] is None or isinstance(w["week_policy_version"], str)
        assert w["quality_focus"] is None or isinstance(w["quality_focus"], str)
        assert w["coach_summary"] is None or isinstance(w["coach_summary"], str)
        assert isinstance(w["progression_tracks"], list)
        assert isinstance(w["week_policy_rationale"], list)
        a = w["assignments"][0]
        _assert_exact_keys(
            a,
            {
                "session_day",
                "session_name",
                "source_template_id",
                "planning_token",
                "template_selection_reason",
                "template_selection_summary",
                "template_selection_rationale",
            },
        )

        create_resp = client.post("/api/v1/coach/plans", json=payload, headers=coach_headers)
        assert create_resp.status_code == 200, create_resp.text
        plan_id = create_resp.json()["id"]

        detail_resp = client.get(f"/api/v1/coach/plans/{plan_id}", headers=coach_headers)
        assert detail_resp.status_code == 200, detail_resp.text
        detail = detail_resp.json()
        _assert_exact_keys(detail, {"plan", "weeks"})
        _assert_exact_keys(
            detail["plan"],
            {"id", "name", "athlete_id", "race_goal", "weeks", "sessions_per_week", "max_session_min", "start_date", "locked_until_week", "status"},
        )
        assert isinstance(detail["weeks"], list)
        assert detail["weeks"]
        dw = detail["weeks"][0]
        _assert_exact_keys(
            dw,
            {
                "id",
                "week_number",
                "phase",
                "week_start",
                "week_end",
                "sessions_order",
                "target_load",
                "locked",
                "planned_minutes",
                "planned_load",
                "week_policy_version",
                "quality_focus",
                "coach_summary",
                "progression_tracks",
                "week_policy_rationale",
                "sessions",
            },
        )
        assert isinstance(dw["sessions"], list)
        assert dw["week_policy_version"] is None or isinstance(dw["week_policy_version"], str)
        assert dw["quality_focus"] is None or isinstance(dw["quality_focus"], str)
        assert dw["coach_summary"] is None or isinstance(dw["coach_summary"], str)
        assert isinstance(dw["progression_tracks"], list)
        assert isinstance(dw["week_policy_rationale"], list)
        if dw["sessions"]:
            ds = dw["sessions"][0]
            _assert_exact_keys(
                ds,
                {
                    "id",
                    "plan_week_id",
                    "athlete_id",
                    "session_day",
                    "session_name",
                    "source_template_id",
                    "source_template_name",
                    "status",
                    "compiled_methodology",
                    "compiled_vdot",
                    "compiled_intensity_codes",
                    "compiled_summary",
                    "planning_token",
                    "template_selection_reason",
                    "template_selection_summary",
                    "template_selection_rationale",
                },
            )
            assert ds["compiled_methodology"] is None or isinstance(ds["compiled_methodology"], str)
            assert ds["compiled_vdot"] is None or isinstance(ds["compiled_vdot"], (int, float))
            assert isinstance(ds["compiled_intensity_codes"], list)
            assert ds["compiled_summary"] is None or isinstance(ds["compiled_summary"], str)
            assert ds["planning_token"] is None or isinstance(ds["planning_token"], str)
            assert ds["template_selection_reason"] is None or isinstance(ds["template_selection_reason"], str)
            assert ds["template_selection_summary"] is None or isinstance(ds["template_selection_summary"], str)
            assert isinstance(ds["template_selection_rationale"], list)


def test_session_library_duplicate_audit_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        resp = client.get("/api/v1/coach/session-library/audit/duplicates?limit=10", headers=coach_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        _assert_exact_keys(body, {"summary", "candidates"})

        summary = body["summary"]
        _assert_exact_keys(
            summary,
            {"template_count", "exact_duplicate_pairs", "near_duplicate_pairs", "candidate_count"},
        )
        assert isinstance(summary["template_count"], int)
        assert isinstance(summary["exact_duplicate_pairs"], int)
        assert isinstance(summary["near_duplicate_pairs"], int)
        assert isinstance(summary["candidate_count"], int)

        assert isinstance(body["candidates"], list)
        if body["candidates"]:
            candidate = body["candidates"][0]
            _assert_exact_keys(candidate, {"kind", "score", "reason_tags", "left", "right"})
            assert isinstance(candidate["kind"], str)
            _assert_number(candidate["score"])
            assert isinstance(candidate["reason_tags"], list)
            for side_key in ("left", "right"):
                side = candidate[side_key]
                _assert_exact_keys(
                    side,
                    {"id", "name", "category", "intent", "energy_system", "tier", "is_treadmill", "duration_min", "status", "duplicate_of_template_id"},
                )


def test_session_library_metadata_audit_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        coach_headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        resp = client.get("/api/v1/coach/session-library/audit/metadata?limit=10", headers=coach_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        _assert_exact_keys(body, {"summary", "items"})

        summary = body["summary"]
        _assert_exact_keys(summary, {"template_count", "templates_with_issues", "error_count", "warning_count"})
        assert isinstance(summary["template_count"], int)
        assert isinstance(summary["templates_with_issues"], int)
        assert isinstance(summary["error_count"], int)
        assert isinstance(summary["warning_count"], int)

        assert isinstance(body["items"], list)
        if body["items"]:
            item = body["items"][0]
            _assert_exact_keys(item, {"template", "issue_count", "error_count", "warning_count", "issues"})
            _assert_exact_keys(
                item["template"],
                {"id", "name", "category", "intent", "energy_system", "tier", "is_treadmill", "duration_min", "methodology", "status", "duplicate_of_template_id"},
            )
            assert isinstance(item["issues"], list)
            if item["issues"]:
                issue = item["issues"][0]
                _assert_exact_keys(issue, {"code", "severity", "message", "field"})
                assert isinstance(issue["code"], str)
                assert isinstance(issue["severity"], str)
                assert isinstance(issue["message"], str)
                assert issue["field"] is None or isinstance(issue["field"], str)


def test_session_library_governance_report_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        resp = client.get("/api/v1/coach/session-library/governance/report?recent_limit=5", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        _assert_exact_keys(
            body,
            {
                "generated_at",
                "template_count",
                "status_counts",
                "methodology_counts",
                "top_intents",
                "top_categories",
                "recent_scope_counts",
                "recent_actions",
            },
        )
        assert isinstance(body["generated_at"], str)
        assert isinstance(body["template_count"], int)
        assert isinstance(body["status_counts"], dict)
        assert isinstance(body["methodology_counts"], dict)
        assert isinstance(body["top_intents"], dict)
        assert isinstance(body["top_categories"], dict)
        assert isinstance(body["recent_scope_counts"], dict)
        assert isinstance(body["recent_actions"], list)
        if body["recent_actions"]:
            item = body["recent_actions"][0]
            _assert_exact_keys(item, {"id", "scope", "actor_user_id", "actor_username", "created_at", "payload"})


def test_session_library_quality_closeout_contract(tmp_path, monkeypatch):
    with _build_client(tmp_path, monkeypatch) as client:
        headers = _auth_headers(client, "coach_ok", "CoachOkay!234")
        seed = client.post("/api/v1/coach/session-library/gold-standard-pack", headers=headers)
        assert seed.status_code == 200, seed.text

        resp = client.get("/api/v1/coach/session-library/governance/quality-closeout?min_similarity=0.78", headers=headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        _assert_exact_keys(
            body,
            {
                "generated_at",
                "ready_for_stage_exit",
                "expected_template_count",
                "installed_gold_template_count",
                "missing_template_count",
                "missing_template_names",
                "canonical_mismatch_count",
                "methodology_mismatch_count",
                "duplicate_audit_summary",
                "metadata_audit_summary",
                "core_category_coverage",
                "checks",
                "recommendations",
            },
        )
        assert isinstance(body["generated_at"], str)
        assert isinstance(body["ready_for_stage_exit"], bool)
        assert isinstance(body["expected_template_count"], int)
        assert isinstance(body["installed_gold_template_count"], int)
        assert isinstance(body["missing_template_count"], int)
        assert isinstance(body["missing_template_names"], list)
        assert isinstance(body["canonical_mismatch_count"], int)
        assert isinstance(body["methodology_mismatch_count"], int)
        assert isinstance(body["core_category_coverage"], dict)
        assert isinstance(body["checks"], list)
        assert isinstance(body["recommendations"], list)

        dup = body["duplicate_audit_summary"]
        _assert_exact_keys(dup, {"template_count", "exact_duplicate_pairs", "near_duplicate_pairs", "candidate_count"})
        meta = body["metadata_audit_summary"]
        _assert_exact_keys(meta, {"template_count", "templates_with_issues", "error_count", "warning_count"})

        if body["checks"]:
            check = body["checks"][0]
            _assert_exact_keys(check, {"code", "passed", "expected", "observed", "details"})
            assert isinstance(check["code"], str)
            assert isinstance(check["passed"], bool)
            assert isinstance(check["details"], str)
