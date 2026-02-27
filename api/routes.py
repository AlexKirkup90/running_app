import re
from difflib import SequenceMatcher
from datetime import date, datetime, timedelta, timezone
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

import pandas as pd
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request, Response
from fastapi_cache.decorator import cache
from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from core.config import get_settings
from core.models import (
    AppWriteLog,
    Athlete,
    AthletePreference,
    CheckIn,
    CoachIntervention,
    Event,
    Plan,
    PlanDaySession,
    PlanWeek,
    PlanWeekMetric,
    SessionLibrary,
    TrainingLog,
    User,
)
from core.security import account_locked, apply_failed_login, hash_password, verify_password
from core.services.analytics import (
    compute_fitness_fatigue,
    compute_intensity_distribution,
    compute_vdot_history,
    weekly_summary,
)
from core.services.progression_tracks import (
    planner_ruleset_backup_snapshots,
    planner_ruleset_diff_preview,
    planner_ruleset_validation_warnings,
    rollback_planner_ruleset_payload,
    save_planner_ruleset_payload,
    validate_planner_ruleset_payload,
    planner_ruleset_snapshot as get_planner_ruleset_snapshot,
    week_quality_policy as build_week_quality_policy,
    week_progression_tracks as build_week_progression_tracks,
    orchestrate_week_tokens as build_orchestrated_week_tokens,
    WEEK_POLICY_VERSION as TRACK_WEEK_POLICY_VERSION,
)
from core.services.readiness import readiness_band, readiness_score
from core.services.race_predictor import predict_all_distances
from core.services.session_compiler import compile_session_for_athlete
from core.services.session_engine import (
    adapt_session_structure,
    compute_acute_chronic_ratio,
    hr_range_for_label,
    pace_range_for_label,
)
from core.services.session_library import default_structure, validate_session_payload
from core.services.session_library import valid_zone_label
from core.services.planning import assign_week_sessions, generate_plan_weeks
from core.services.vdot_methodology import derived_profile_pace_anchors

from api.deps import get_db
from api.auth import AuthPrincipal, issue_access_token, require_athlete_access, require_roles, get_current_principal
from api.integrations import router as integrations_router
from api.ratelimit import limiter
from api.schemas import (
    AthleteDetailResponse,
    AthleteEventCreate,
    AthleteEventItem,
    AthleteEventListResponse,
    AthleteEventUpdate,
    AthleteListItem,
    AthleteListResponse,
    CoachCreateAthleteRequest,
    CoachCreateAthleteResponse,
    CoachCreateUserRequest,
    CoachCreateUserResponse,
    CoachResetPasswordRequest,
    CoachResetPasswordResponse,
    CoachUserStatusResponse,
    CoachUnlockUserResponse,
    CoachUpdateAthleteRequest,
    CoachAthleteLifecycleResponse,
    AthleteAnalyticsResponse,
    AthletePredictionsResponse,
    AthletePlanStatusResponse,
    AthletePlanStatusPlan,
    AthleteUpcomingSessionItem,
    AthletePreferencesResponse,
    AthletePreferencesUpdate,
    AthleteTodayResponse,
    AthleteWorkloadResponse,
    AthleteWorkloadWeek,
    CheckInInput,
    CheckInResponse,
    AuthTokenRequest,
    AuthTokenResponse,
    ChangePasswordRequest,
    ChangePasswordResponse,
    CoachAuditLogItem,
    CoachAuditLogResponse,
    CoachAutomationPolicyResponse,
    CoachAutomationPolicyUpdate,
    CoachCommandCenterInterventionItem,
    CoachCommandCenterPriorityComponents,
    CoachCommandCenterResponse,
    CoachUserItem,
    CoachUserListResponse,
    CoachUsersQueryResponse,
    CoachPortfolioAnalyticsResponse,
    CoachPlanDaySessionItem,
    CoachPlanDetailResponse,
    CoachPlanListResponse,
    CoachPlanSummary,
    CoachPlanUpdateRequest,
    CoachPlanWeekItem,
    InterventionListItem,
    InterventionListResponse,
    InterventionActionRequest,
    InterventionActionResponse,
    InterventionAutoApplyResponse,
    InterventionAutoApplySkippedItem,
    PlanCreateRequest,
    PlanPreviewRequest,
    PlanPreviewResponse,
    PlanPreviewWeek,
    PlanSessionAssignment,
    PlanWeekLockResponse,
    PlannerRulesetMutationResponse,
    PlannerRulesetUpdateRequest,
    PlannerRulesetResponse,
    PlannerRulesetValidateResponse,
    PlanWeekRegenerateRequest,
    CoachPlanDaySessionPatch,
    PlannerRulesetHistoryResponse,
    PlannerRulesetBackupsResponse,
    SessionLibraryDetailResponse,
    SessionLibraryDuplicateAuditResponse,
    SessionLibraryBulkLegacyDeprecationRequest,
    SessionLibraryBulkLegacyDeprecationResponse,
    SessionLibraryBulkCanonicalizationRequest,
    SessionLibraryBulkCanonicalizationResponse,
    SessionLibraryBulkCanonicalizationDecision,
    SessionLibraryBulkCanonicalizationSkippedItem,
    SessionLibraryFieldChange,
    SessionLibraryGoldStandardPackResponse,
    SessionLibraryGovernanceActionRequest,
    SessionLibraryGovernanceActionResponse,
    SessionLibraryGovernanceReportResponse,
    SessionLibraryMetadataAuditIssue,
    SessionLibraryMetadataAuditResponse,
    SessionLibraryMetadataAuditSummary,
    SessionLibraryMetadataAuditTemplateItem,
    SessionLibraryNormalizeMetadataResponse,
    SessionLibraryDuplicateAuditSummary,
    SessionLibraryDuplicateCandidateItem,
    SessionLibraryListItem,
    SessionLibraryListResponse,
    SessionLibraryPatch,
    SessionLibraryUpsert,
    SessionLibraryValidateResponse,
    SimpleStatusResponse,
    TrainingLogInput,
    TrainingLogResponse,
    WeeklyRollupItem,
    WeeklyRollupResponse,
)
from api.training_logs import persist_training_log

router = APIRouter(prefix="/api/v1")
router.include_router(integrations_router)


def _request_key_builder(func, namespace: str = "", *, request=None, response=None, args=None, kwargs=None):
    if request is None:
        return f"{namespace}:{func.__module__}.{func.__name__}"
    return f"{namespace}:{request.url.path}?{request.url.query}"


def _athlete_or_404(db: Session, athlete_id: int) -> Athlete:
    athlete = db.execute(select(Athlete).where(Athlete.id == athlete_id)).scalar_one_or_none()
    if athlete is None:
        raise HTTPException(status_code=404, detail={"code": "ATHLETE_NOT_FOUND", "athlete_id": athlete_id})
    return athlete


DAY_NAMES = {"Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"}
PLANNER_SELECTION_STRATEGY_VERSION = "jd_canonical_selector_v1"
WEEK_POLICY_VERSION = TRACK_WEEK_POLICY_VERSION


def _normalize_day_labels(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    out: List[str] = []
    seen = set()
    for item in values:
        token = str(item or "").strip()[:3].title()
        if token in DAY_NAMES and token not in seen:
            out.append(token)
            seen.add(token)
    return out


def _event_or_404(db: Session, event_id: int) -> Event:
    row = db.execute(select(Event).where(Event.id == event_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "EVENT_NOT_FOUND", "event_id": event_id})
    return row


def _user_or_404(db: Session, user_id: int) -> User:
    row = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND", "user_id": user_id})
    return row


def _intervention_or_404(db: Session, intervention_id: int) -> CoachIntervention:
    row = db.execute(select(CoachIntervention).where(CoachIntervention.id == intervention_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "INTERVENTION_NOT_FOUND", "intervention_id": intervention_id},
        )
    return row


def _preferences_or_create(db: Session, athlete_id: int) -> AthletePreference:
    row = db.execute(select(AthletePreference).where(AthletePreference.athlete_id == athlete_id)).scalar_one_or_none()
    if row is None:
        row = AthletePreference(athlete_id=athlete_id)
        db.add(row)
        db.flush()
        db.refresh(row)
    return row


def _preferences_response(row: AthletePreference) -> AthletePreferencesResponse:
    preferred_long_run_day = str(getattr(row, "preferred_long_run_day", "") or "").strip()[:3].title()
    if preferred_long_run_day not in DAY_NAMES:
        preferred_long_run_day = None
    return AthletePreferencesResponse(
        athlete_id=int(row.athlete_id),
        reminder_enabled=bool(row.reminder_enabled),
        reminder_training_days=_normalize_day_labels(list(row.reminder_training_days or [])),
        privacy_ack=bool(row.privacy_ack),
        automation_mode=str(row.automation_mode or "manual"),
        auto_apply_low_risk=bool(row.auto_apply_low_risk),
        auto_apply_confidence_min=float(row.auto_apply_confidence_min or 0.0),
        auto_apply_risk_max=float(row.auto_apply_risk_max or 0.0),
        preferred_training_days=_normalize_day_labels(list(getattr(row, "preferred_training_days", []) or [])),
        preferred_long_run_day=preferred_long_run_day,
    )


def _session_library_or_404(db: Session, session_id: int) -> SessionLibrary:
    row = db.execute(select(SessionLibrary).where(SessionLibrary.id == session_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "SESSION_TEMPLATE_NOT_FOUND", "session_id": session_id})
    return row


def _session_library_payload_from_model(row: SessionLibrary) -> Dict[str, Any]:
    return {
        "name": str(row.name or ""),
        "category": str(row.category or ""),
        "intent": str(row.intent or ""),
        "energy_system": str(row.energy_system or ""),
        "tier": str(row.tier or ""),
        "is_treadmill": bool(row.is_treadmill),
        "duration_min": int(row.duration_min or 0),
        "structure_json": dict(row.structure_json or {}),
        "targets_json": dict(row.targets_json or {}),
        "progression_json": dict(row.progression_json or {}),
        "regression_json": dict(row.regression_json or {}),
        "prescription": str(row.prescription or ""),
        "coaching_notes": str(row.coaching_notes or ""),
    }


def _session_library_list_item(row: SessionLibrary) -> SessionLibraryListItem:
    return SessionLibraryListItem.model_validate(
        {
            "id": int(row.id),
            "name": str(row.name or ""),
            "category": str(row.category or ""),
            "intent": str(row.intent or ""),
            "energy_system": str(row.energy_system or ""),
            "tier": str(row.tier or ""),
            "is_treadmill": bool(row.is_treadmill),
            "duration_min": int(row.duration_min or 0),
            "methodology": _session_template_methodology(row) or None,
            "status": str(row.status or "active"),
            "duplicate_of_template_id": (int(row.duplicate_of_template_id) if row.duplicate_of_template_id is not None else None),
        }
    )


def _normalize_session_name_for_similarity(name: str) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(name or "").lower()).strip()
    return re.sub(r"\s+", " ", text)


def _session_structure_fingerprint(row: SessionLibrary) -> str:
    blocks = list((row.structure_json or {}).get("blocks") or [])
    parts: List[str] = []

    def _value_token(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (list, tuple)):
            return "[" + ",".join(_value_token(v) for v in value) + "]"
        return str(value).strip().lower()

    for block in blocks:
        if not isinstance(block, dict):
            continue
        phase = str(block.get("phase") or "").strip().lower()
        dur = str(block.get("duration_min") or "").strip()
        target = block.get("target") or {}
        if isinstance(target, dict):
            pace = str(target.get("pace_zone") or "").strip().lower()
            hr = str(target.get("hr_zone") or "").strip().lower()
            rpe = str(target.get("rpe_range") or "")
            intensity = str(target.get("intensity_code") or "").strip().upper()
        else:
            pace = ""
            hr = ""
            rpe = ""
            intensity = ""

        # Capture interval/block pattern details so JD variants like 3x10 T and 5x6 T
        # are not treated as identical just because total work duration matches.
        pattern_fields = [
            ("repetitions", block.get("repetitions")),
            ("work_duration_min", block.get("work_duration_min")),
            ("work_duration_sec", block.get("work_duration_sec")),
            ("work_distance_m", block.get("work_distance_m")),
            ("recovery_duration_min", block.get("recovery_duration_min")),
            ("recovery_duration_sec", block.get("recovery_duration_sec")),
            ("recovery_distance_m", block.get("recovery_distance_m")),
        ]
        pattern = ",".join(f"{key}={_value_token(value)}" for key, value in pattern_fields if value is not None)
        instruction_kind = ""
        if not pattern:
            instruction_text = str(block.get("instructions") or "").lower()
            if " x " in instruction_text or "x " in instruction_text:
                instruction_kind = "interval_like"
            elif "continuous" in instruction_text:
                instruction_kind = "continuous"
        parts.append(f"{phase}:{dur}:{pace}:{hr}:{rpe}:{intensity}:{pattern}:{instruction_kind}")
    return "|".join(parts)


def _session_exact_fingerprint(row: SessionLibrary) -> str:
    return "||".join(
        [
            _session_template_methodology(row),
            str(row.category or "").strip().lower(),
            str(row.intent or "").strip().lower(),
            str(row.energy_system or "").strip().lower(),
            str(row.tier or "").strip().lower(),
            "1" if bool(row.is_treadmill) else "0",
            str(int(row.duration_min or 0)),
            _session_structure_fingerprint(row),
        ]
    )


def _session_similarity_score(left: SessionLibrary, right: SessionLibrary) -> tuple[float, list[str]]:
    reasons: List[str] = []
    score = 0.0
    if str(left.intent or "").strip().lower() == str(right.intent or "").strip().lower():
        score += 0.22
        reasons.append("same_intent")
    if str(left.energy_system or "").strip().lower() == str(right.energy_system or "").strip().lower():
        score += 0.18
        reasons.append("same_energy_system")
    if str(left.category or "").strip().lower() == str(right.category or "").strip().lower():
        score += 0.12
        reasons.append("same_category")
    if bool(left.is_treadmill) == bool(right.is_treadmill):
        score += 0.06
        reasons.append("same_treadmill_flag")
    duration_delta = abs(int(left.duration_min or 0) - int(right.duration_min or 0))
    if duration_delta == 0:
        score += 0.12
        reasons.append("same_duration")
    elif duration_delta <= 5:
        score += 0.09
        reasons.append("duration_within_5")
    elif duration_delta <= 10:
        score += 0.05
        reasons.append("duration_within_10")
    name_ratio = SequenceMatcher(
        None,
        _normalize_session_name_for_similarity(str(left.name or "")),
        _normalize_session_name_for_similarity(str(right.name or "")),
    ).ratio()
    if name_ratio >= 0.92:
        score += 0.24
        reasons.append("very_high_name_similarity")
    elif name_ratio >= 0.84:
        score += 0.18
        reasons.append("high_name_similarity")
    elif name_ratio >= 0.75:
        score += 0.10
        reasons.append("moderate_name_similarity")

    if _session_structure_fingerprint(left) and _session_structure_fingerprint(left) == _session_structure_fingerprint(right):
        score += 0.20
        reasons.append("identical_structure")

    return round(min(1.0, score), 3), reasons


def _session_library_duplicate_audit(
    rows: List[SessionLibrary],
    *,
    limit: int = 50,
    min_similarity: float = 0.78,
) -> SessionLibraryDuplicateAuditResponse:
    exact_groups: Dict[str, List[SessionLibrary]] = {}
    for row in rows:
        exact_groups.setdefault(_session_exact_fingerprint(row), []).append(row)

    candidates: List[SessionLibraryDuplicateCandidateItem] = []
    exact_pair_keys: set[tuple[int, int]] = set()
    exact_count = 0
    for group in exact_groups.values():
        if len(group) < 2:
            continue
        group_sorted = sorted(group, key=lambda r: int(r.id))
        for i in range(len(group_sorted)):
            for j in range(i + 1, len(group_sorted)):
                left = group_sorted[i]
                right = group_sorted[j]
                pair_key = (int(left.id), int(right.id))
                exact_pair_keys.add(pair_key)
                exact_count += 1
                candidates.append(
                    SessionLibraryDuplicateCandidateItem(
                        kind="exact",
                        score=1.0,
                        reason_tags=["identical_metadata_and_structure"],
                        left=_session_library_list_item(left),
                        right=_session_library_list_item(right),
                    )
                )

    near_count = 0
    sorted_rows = sorted(rows, key=lambda r: int(r.id))
    for i in range(len(sorted_rows)):
        for j in range(i + 1, len(sorted_rows)):
            left = sorted_rows[i]
            right = sorted_rows[j]
            pair_key = (int(left.id), int(right.id))
            if pair_key in exact_pair_keys:
                continue
            score, reasons = _session_similarity_score(left, right)
            if score < float(min_similarity):
                continue
            near_count += 1
            candidates.append(
                SessionLibraryDuplicateCandidateItem(
                    kind="near",
                    score=score,
                    reason_tags=reasons,
                    left=_session_library_list_item(left),
                    right=_session_library_list_item(right),
                )
            )

    candidates.sort(key=lambda c: (0 if c.kind == "exact" else 1, -float(c.score), c.left.id, c.right.id))
    trimmed = candidates[:limit]
    return SessionLibraryDuplicateAuditResponse(
        summary=SessionLibraryDuplicateAuditSummary(
            template_count=len(rows),
            exact_duplicate_pairs=exact_count,
            near_duplicate_pairs=near_count,
            candidate_count=len(candidates),
        ),
        candidates=trimmed,
    )


_CORE_METHOD_INTENTS = {
    "easy",
    "endurance",
    "recovery",
    "long_run",
    "threshold",
    "tempo",
    "lactate_threshold",
    "vo2",
    "intervals",
    "aerobic_power",
    "race_pace",
    "marathon",
    "marathon_pace",
}
_CANONICAL_TIERS = {"low", "easy", "medium", "high", "hard"}


def _normalized_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _session_library_metadata_issues(row: SessionLibrary) -> List[SessionLibraryMetadataAuditIssue]:
    issues: List[SessionLibraryMetadataAuditIssue] = []
    payload = _session_library_payload_from_model(row)

    for err in validate_session_payload(payload):
        issues.append(
            SessionLibraryMetadataAuditIssue(
                code="validation_contract_error",
                severity="error",
                message=str(err),
            )
        )

    for field in ("category", "intent", "energy_system", "tier"):
        raw = str(getattr(row, field, "") or "")
        normalized = _normalized_token(raw)
        if raw and raw != normalized:
            issues.append(
                SessionLibraryMetadataAuditIssue(
                    code=f"noncanonical_{field}_format",
                    severity="warning",
                    message=f"{field} should use canonical lowercase token format ('{normalized}')",
                    field=field,
                )
            )

    tier_token = _normalized_token(str(row.tier or ""))
    if tier_token and tier_token not in _CANONICAL_TIERS:
        issues.append(
            SessionLibraryMetadataAuditIssue(
                code="unknown_tier",
                severity="warning",
                message=f"tier '{row.tier}' is outside canonical set {sorted(_CANONICAL_TIERS)}",
                field="tier",
            )
        )

    name_text = str(row.name or "").strip()
    if len(name_text) < 10:
        issues.append(
            SessionLibraryMetadataAuditIssue(
                code="name_too_short",
                severity="warning",
                message="Template name should be descriptive (10+ chars)",
                field="name",
            )
        )
    if not re.search(r"\d", name_text) and not any(token in name_text.lower() for token in ["long run", "recovery", "easy"]):
        issues.append(
            SessionLibraryMetadataAuditIssue(
                code="name_missing_volume_hint",
                severity="warning",
                message="Template name does not include an obvious duration/rep cue; consider standardizing naming",
                field="name",
            )
        )

    blocks = list((row.structure_json or {}).get("blocks") or [])
    intent_token = _normalized_token(str(row.intent or ""))
    for idx, block in enumerate(blocks):
        if not isinstance(block, dict):
            continue
        phase = str(block.get("phase") or "").strip().lower()
        target = block.get("target") or {}
        if not isinstance(target, dict):
            continue
        if phase == "main_set" and intent_token in _CORE_METHOD_INTENTS:
            intensity_code = str(target.get("intensity_code") or "").strip().upper()
            if intensity_code not in {"E", "M", "T", "I", "R"}:
                issues.append(
                    SessionLibraryMetadataAuditIssue(
                        code="missing_intensity_code_main_set",
                        severity="warning",
                        message="Main set target is missing Daniels/VDOT intensity code (E/M/T/I/R)",
                        field=f"structure_json.blocks[{idx}].target.intensity_code",
                    )
                )
        for zone_field in ("pace_zone", "hr_zone"):
            zone_value = str(target.get(zone_field, "")).strip()
            if zone_value and not valid_zone_label(zone_value):
                issues.append(
                    SessionLibraryMetadataAuditIssue(
                        code=f"invalid_{zone_field}",
                        severity="error",
                        message=f"{zone_field} '{zone_value}' is not a valid zone label",
                        field=f"structure_json.blocks[{idx}].target.{zone_field}",
                    )
                )

    if len(str(row.prescription or "").strip()) < 20:
        issues.append(
            SessionLibraryMetadataAuditIssue(
                code="prescription_too_short",
                severity="warning",
                message="Prescription text is brief; consider adding execution detail",
                field="prescription",
            )
        )
    if len(str(row.coaching_notes or "").strip()) < 12:
        issues.append(
            SessionLibraryMetadataAuditIssue(
                code="coaching_notes_too_short",
                severity="warning",
                message="Coaching notes are brief; consider adding cues or common mistakes",
                field="coaching_notes",
            )
        )
    return issues


def _session_library_metadata_audit(rows: List[SessionLibrary], *, limit: int = 50) -> SessionLibraryMetadataAuditResponse:
    items: List[SessionLibraryMetadataAuditTemplateItem] = []
    error_total = 0
    warning_total = 0

    for row in rows:
        issues = _session_library_metadata_issues(row)
        if not issues:
            continue
        error_count = sum(1 for i in issues if i.severity == "error")
        warning_count = sum(1 for i in issues if i.severity == "warning")
        error_total += error_count
        warning_total += warning_count
        items.append(
            SessionLibraryMetadataAuditTemplateItem(
                template=_session_library_list_item(row),
                issue_count=len(issues),
                error_count=error_count,
                warning_count=warning_count,
                issues=issues,
            )
        )

    items.sort(
        key=lambda x: (
            -int(x.error_count),
            -int(x.warning_count),
            -int(x.issue_count),
            x.template.id,
        )
    )
    trimmed = items[:limit]
    return SessionLibraryMetadataAuditResponse(
        summary=SessionLibraryMetadataAuditSummary(
            template_count=len(rows),
            templates_with_issues=len(items),
            error_count=error_total,
            warning_count=warning_total,
        ),
        items=trimmed,
    )


def _session_library_issue_counts(issues: List[SessionLibraryMetadataAuditIssue]) -> Dict[str, int]:
    return {
        "total": len(issues),
        "errors": sum(1 for i in issues if i.severity == "error"),
        "warnings": sum(1 for i in issues if i.severity == "warning"),
    }


def _infer_intensity_code_for_intent(intent_token: str) -> Optional[str]:
    if intent_token in {"easy", "endurance", "recovery", "long_run"}:
        return "E"
    if intent_token in {"marathon", "marathon_pace", "race_pace"}:
        return "M"
    if intent_token in {"threshold", "tempo", "lactate_threshold"}:
        return "T"
    if intent_token in {"vo2", "intervals", "aerobic_power"}:
        return "I"
    if intent_token in {"repetition", "reps", "strides", "neuromuscular"}:
        return "R"
    return None


def _normalize_session_library_metadata(
    row: SessionLibrary,
) -> tuple[List[SessionLibraryFieldChange], Dict[str, int], Dict[str, int]]:
    before_issues = _session_library_metadata_issues(row)
    changes: List[SessionLibraryFieldChange] = []

    for field in ("category", "intent", "energy_system", "tier"):
        raw = str(getattr(row, field, "") or "")
        normalized = _normalized_token(raw)
        if raw and normalized and raw != normalized:
            changes.append(SessionLibraryFieldChange(field=field, before=raw, after=normalized))
            setattr(row, field, normalized)

    intent_token = _normalized_token(str(row.intent or ""))
    inferred_code = _infer_intensity_code_for_intent(intent_token)
    blocks = list((row.structure_json or {}).get("blocks") or [])
    structure_changed = False
    if inferred_code:
        for idx, block in enumerate(blocks):
            if not isinstance(block, dict):
                continue
            phase = str(block.get("phase") or "").strip().lower()
            if phase != "main_set":
                continue
            target = block.get("target") or {}
            if not isinstance(target, dict):
                continue
            current_code = str(target.get("intensity_code") or "").strip().upper()
            if current_code not in {"E", "M", "T", "I", "R"}:
                target["intensity_code"] = inferred_code
                block["target"] = target
                blocks[idx] = block
                structure_changed = True
                changes.append(
                    SessionLibraryFieldChange(
                        field=f"structure_json.blocks[{idx}].target.intensity_code",
                        before=(current_code or None),
                        after=inferred_code,
                    )
                )
            elif current_code != str(target.get("intensity_code")):
                # normalize lowercase valid codes to uppercase
                before_raw = str(target.get("intensity_code"))
                target["intensity_code"] = current_code
                block["target"] = target
                blocks[idx] = block
                structure_changed = True
                changes.append(
                    SessionLibraryFieldChange(
                        field=f"structure_json.blocks[{idx}].target.intensity_code",
                        before=before_raw,
                        after=current_code,
                    )
                )
    if structure_changed:
        payload = dict(row.structure_json or {})
        payload["blocks"] = blocks
        row.structure_json = payload

    after_issues = _session_library_metadata_issues(row)
    return changes, _session_library_issue_counts(before_issues), _session_library_issue_counts(after_issues)


def _session_template_methodology(row: SessionLibrary) -> str:
    for payload in (row.structure_json, row.targets_json):
        if isinstance(payload, dict):
            token = str(payload.get("methodology") or "").strip().lower()
            if token:
                return token
    return ""


def _legacy_session_candidate(
    row: SessionLibrary,
    *,
    include_non_daniels_active: bool = False,
) -> bool:
    status = str(row.status or "active").strip().lower() or "active"
    if status in {"canonical", "duplicate", "deprecated"}:
        return False
    methodology = _session_template_methodology(row)
    if methodology == "daniels_vdot":
        return bool(include_non_daniels_active)
    return True


def _canonicalization_target_and_duplicate(
    left: SessionLibrary,
    right: SessionLibrary,
) -> tuple[Optional[SessionLibrary], Optional[SessionLibrary], str]:
    left_status = str(left.status or "active").strip().lower()
    right_status = str(right.status or "active").strip().lower()
    left_method = _session_template_methodology(left)
    right_method = _session_template_methodology(right)

    if left_status == "canonical" and right_status == "canonical":
        return None, None, "both_canonical"
    if left_status == "canonical":
        return left, right, "prefer_existing_canonical"
    if right_status == "canonical":
        return right, left, "prefer_existing_canonical"
    if left_method == "daniels_vdot" and right_method != "daniels_vdot":
        return left, right, "prefer_daniels_methodology"
    if right_method == "daniels_vdot" and left_method != "daniels_vdot":
        return right, left, "prefer_daniels_methodology"
    # Prefer active over deprecated/duplicate when neither is canonical.
    status_rank = {"active": 3, "duplicate": 2, "deprecated": 1}
    l_rank = status_rank.get(left_status, 0)
    r_rank = status_rank.get(right_status, 0)
    if l_rank > r_rank:
        return left, right, "prefer_active_status"
    if r_rank > l_rank:
        return right, left, "prefer_active_status"
    # Stable fallback.
    if int(left.id) <= int(right.id):
        return left, right, "prefer_lower_id_stable"
    return right, left, "prefer_lower_id_stable"


def _session_library_governance_report_payload(db: Session, *, recent_limit: int = 10) -> SessionLibraryGovernanceReportResponse:
    rows = db.execute(select(SessionLibrary).order_by(SessionLibrary.id.asc())).scalars().all()
    status_counts: Dict[str, int] = {}
    methodology_counts: Dict[str, int] = {}
    intent_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}

    for row in rows:
        status = str(row.status or "active").strip().lower() or "active"
        status_counts[status] = status_counts.get(status, 0) + 1
        method = _session_template_methodology(row) or "legacy_unknown"
        methodology_counts[method] = methodology_counts.get(method, 0) + 1
        intent = str(row.intent or "unknown").strip().lower() or "unknown"
        category = str(row.category or "unknown").strip().lower() or "unknown"
        intent_counts[intent] = intent_counts.get(intent, 0) + 1
        category_counts[category] = category_counts.get(category, 0) + 1

    governance_scopes = [
        "session_library_gold_standard_pack_upsert",
        "session_library_governance_action",
        "session_library_normalize_metadata",
        "session_library_bulk_deprecate_legacy",
        "session_library_bulk_canonicalize_duplicates",
        "planner_ruleset_update",
        "planner_ruleset_rollback",
    ]
    recent_rows = db.execute(
        select(AppWriteLog, User.username)
        .outerjoin(User, User.id == AppWriteLog.actor_user_id)
        .where(AppWriteLog.scope.in_(governance_scopes))
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
        .limit(max(1, recent_limit))
    ).all()
    recent_scope_counts: Dict[str, int] = {}
    recent_actions = []
    for log_row, actor_username in recent_rows:
        scope = str(log_row.scope or "")
        recent_scope_counts[scope] = recent_scope_counts.get(scope, 0) + 1
        recent_actions.append(_audit_log_list_item(log_row, actor_username=actor_username))

    top_intents = dict(sorted(intent_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8])
    top_categories = dict(sorted(category_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:8])
    return SessionLibraryGovernanceReportResponse(
        generated_at=datetime.utcnow(),
        template_count=len(rows),
        status_counts=status_counts,
        methodology_counts=methodology_counts,
        top_intents=top_intents,
        top_categories=top_categories,
        recent_scope_counts=recent_scope_counts,
        recent_actions=recent_actions,
    )


def _intervention_list_item(
    intervention: CoachIntervention,
    athlete_name: Optional[str] = None,
    auto_apply_eval: Optional[Dict[str, Any]] = None,
    auto_revert_state: Optional[Dict[str, Any]] = None,
) -> InterventionListItem:
    risk_score = float(intervention.risk_score or 0.0)
    risk_band = "low"
    if risk_score >= 0.75:
        risk_band = "high"
    elif risk_score >= 0.45:
        risk_band = "moderate"

    return InterventionListItem(
        id=int(intervention.id),
        athlete_id=int(intervention.athlete_id),
        athlete_name=athlete_name,
        action_type=str(intervention.action_type or ""),
        status=str(intervention.status or ""),
        risk_score=risk_score,
        risk_band=risk_band,
        confidence_score=float(intervention.confidence_score or 0.0),
        created_at=intervention.created_at,
        cooldown_until=intervention.cooldown_until,
        why_factors=[str(item) for item in list(intervention.why_factors or [])],
        expected_impact=dict(intervention.expected_impact or {}),
        guardrail_pass=bool(intervention.guardrail_pass),
        guardrail_reason=str(intervention.guardrail_reason or ""),
        auto_apply_eligible=(
            bool(auto_apply_eval.get("eligible")) if auto_apply_eval is not None and "eligible" in auto_apply_eval else None
        ),
        review_reason=(str(auto_apply_eval.get("reason") or "") if auto_apply_eval is not None else None),
        review_reason_detail=(dict(auto_apply_eval.get("detail") or {}) if auto_apply_eval is not None else {}),
        auto_revert_available=bool(auto_revert_state.get("available")) if auto_revert_state is not None else False,
        auto_revert_block_reason=(
            str(auto_revert_state.get("block_reason") or "") if auto_revert_state is not None else None
        ),
    )


def _intervention_priority_components(intervention: CoachIntervention, *, now: Optional[datetime] = None) -> Dict[str, float]:
    ts_now = now or datetime.utcnow()
    created_at = intervention.created_at or ts_now
    age_hours = max(0.0, (ts_now - created_at).total_seconds() / 3600.0)
    risk_component = round(float(intervention.risk_score or 0.0) * 0.55, 3)
    confidence_component = round(float(intervention.confidence_score or 0.0) * 0.25, 3)
    age_boost = round(min(0.35, age_hours / 72.0), 3)
    guardrail_penalty = 0.0 if bool(intervention.guardrail_pass) else 0.25
    status_value = str(intervention.status or "").lower()
    status_penalty = 0.0 if status_value == "open" else (0.15 if status_value == "snoozed" else 0.35)
    return {
        "risk_component": risk_component,
        "confidence_component": confidence_component,
        "age_boost": age_boost,
        "guardrail_penalty": round(guardrail_penalty, 3),
        "status_penalty": round(status_penalty, 3),
    }


def _intervention_priority_reasons(intervention: CoachIntervention, comps: Dict[str, float]) -> List[str]:
    reasons: List[str] = []
    risk = float(intervention.risk_score or 0.0)
    confidence = float(intervention.confidence_score or 0.0)
    status_value = str(intervention.status or "").lower()

    if risk >= 0.75:
        reasons.append("high_risk_signal")
    elif risk >= 0.45:
        reasons.append("moderate_risk_signal")

    if confidence >= 0.8:
        reasons.append("high_confidence_recommendation")
    elif confidence >= 0.6:
        reasons.append("moderate_confidence_recommendation")

    if comps.get("age_boost", 0.0) >= 0.2:
        reasons.append("aging_queue_item")
    if not bool(intervention.guardrail_pass):
        reasons.append("guardrail_blocked")
    if status_value == "snoozed":
        reasons.append("snoozed_status_penalty")
    elif status_value not in {"", "open"}:
        reasons.append("non_open_status_penalty")
    if not reasons:
        reasons.append("baseline_priority")
    return reasons


def _scored_intervention_list_item(
    intervention: CoachIntervention,
    *,
    athlete_name: Optional[str] = None,
    now: Optional[datetime] = None,
    ranking_version: str = "heuristic_v1",
) -> CoachCommandCenterInterventionItem:
    base = _intervention_list_item(intervention, athlete_name=athlete_name)
    comps = _intervention_priority_components(intervention, now=now)
    score = round(
        comps["risk_component"]
        + comps["confidence_component"]
        + comps["age_boost"]
        - comps["guardrail_penalty"]
        - comps["status_penalty"],
        3,
    )
    return CoachCommandCenterInterventionItem(
        **base.model_dump(),
        priority_score=score,
        priority_components=CoachCommandCenterPriorityComponents(**comps),
        priority_reasons=_intervention_priority_reasons(intervention, comps),
        ranking_version=ranking_version,
    )


def _append_app_write_log(
    db: Session,
    *,
    scope: str,
    actor_user_id: Optional[int],
    payload: Dict[str, Any],
) -> None:
    db.add(
        AppWriteLog(
            scope=scope,
            actor_user_id=actor_user_id,
            payload=payload,
        )
    )


def _coerce_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _same_dt(a: Optional[datetime], b: Optional[datetime]) -> bool:
    if a is None or b is None:
        return a is None and b is None
    return abs((a - b).total_seconds()) < 1.0


def _latest_auto_apply_approval_log(
    db: Session,
    intervention_id: int,
) -> tuple[Optional[AppWriteLog], Optional[Dict[str, Any]]]:
    rows = db.execute(
        select(AppWriteLog)
        .where(AppWriteLog.scope == "coach_intervention_action")
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
    ).scalars()
    for row in rows:
        payload = dict(row.payload or {})
        try:
            payload_intervention_id = int(payload.get("intervention_id"))
        except Exception:
            continue
        if payload_intervention_id != int(intervention_id):
            continue
        if str(payload.get("action") or "").lower() != "approve":
            continue
        if not bool(payload.get("auto_applied")):
            continue
        return row, payload
    return None, None


def _has_revert_for_source_action(
    db: Session,
    *,
    source_action_log_id: int,
) -> bool:
    rows = db.execute(
        select(AppWriteLog)
        .where(AppWriteLog.scope == "coach_intervention_action")
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
    ).scalars()
    for row in rows:
        payload = dict(row.payload or {})
        if str(payload.get("action") or "").lower() != "revert_auto_approve":
            continue
        try:
            if int(payload.get("source_action_log_id")) == int(source_action_log_id):
                return True
        except Exception:
            continue
    return False


def _evaluate_intervention_auto_apply(
    intervention: CoachIntervention,
    *,
    pref: Optional[AthletePreference],
    coach_policy: CoachAutomationPolicyResponse,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    ts_now = now or datetime.utcnow()
    athlete_id = int(intervention.athlete_id)
    policy_source = "athlete"
    auto_enabled = bool(pref.auto_apply_low_risk) if pref is not None else False
    conf_min = float(pref.auto_apply_confidence_min or 0.8) if pref is not None else 0.8
    risk_max = float(pref.auto_apply_risk_max or 0.3) if pref is not None else 0.3

    if pref is None:
        if coach_policy.enabled and coach_policy.default_auto_apply_low_risk and coach_policy.apply_when_athlete_pref_missing:
            policy_source = "coach_default_missing_pref"
            auto_enabled = True
            conf_min = float(coach_policy.default_auto_apply_confidence_min)
            risk_max = float(coach_policy.default_auto_apply_risk_max)
        else:
            return {
                "eligible": False,
                "athlete_id": athlete_id,
                "policy_source": policy_source,
                "reason": "athlete_policy_missing",
                "detail": {"coach_policy_enabled": bool(coach_policy.enabled)},
            }
    elif not bool(pref.auto_apply_low_risk):
        if coach_policy.enabled and coach_policy.default_auto_apply_low_risk and coach_policy.apply_when_athlete_pref_disabled:
            policy_source = "coach_default_pref_disabled"
            auto_enabled = True
            conf_min = float(coach_policy.default_auto_apply_confidence_min)
            risk_max = float(coach_policy.default_auto_apply_risk_max)

    if intervention.cooldown_until and intervention.cooldown_until > ts_now:
        return {
            "eligible": False,
            "athlete_id": athlete_id,
            "policy_source": policy_source,
            "reason": "cooldown_active",
            "detail": {"cooldown_until": intervention.cooldown_until.isoformat()},
        }

    if not bool(intervention.guardrail_pass):
        return {
            "eligible": False,
            "athlete_id": athlete_id,
            "policy_source": policy_source,
            "reason": "guardrail_blocked",
            "detail": {"guardrail_reason": str(intervention.guardrail_reason or "")},
        }

    if not auto_enabled:
        return {
            "eligible": False,
            "athlete_id": athlete_id,
            "policy_source": policy_source,
            "reason": "athlete_policy_disabled",
            "detail": {"policy_source": policy_source},
        }

    confidence_score = float(intervention.confidence_score or 0.0)
    if confidence_score < conf_min:
        return {
            "eligible": False,
            "athlete_id": athlete_id,
            "policy_source": policy_source,
            "reason": "confidence_below_policy",
            "detail": {
                "confidence_score": confidence_score,
                "min_confidence": conf_min,
                "policy_source": policy_source,
            },
        }

    risk_score = float(intervention.risk_score or 0.0)
    if risk_score > risk_max:
        return {
            "eligible": False,
            "athlete_id": athlete_id,
            "policy_source": policy_source,
            "reason": "risk_above_policy",
            "detail": {
                "risk_score": risk_score,
                "max_risk": risk_max,
                "policy_source": policy_source,
            },
        }

    return {
        "eligible": True,
        "athlete_id": athlete_id,
        "policy_source": policy_source,
        "reason": "eligible",
        "detail": {
            "min_confidence": conf_min,
            "max_risk": risk_max,
            "policy_source": policy_source,
        },
    }


def _auto_apply_eval_map(
    db: Session,
    interventions: List[CoachIntervention],
    *,
    coach_user_id: int,
    now: Optional[datetime] = None,
) -> Dict[int, Dict[str, Any]]:
    if not interventions:
        return {}

    coach_policy = _load_coach_automation_policy(db, coach_user_id)
    athlete_ids = sorted({int(r.athlete_id) for r in interventions if r.athlete_id is not None})
    pref_rows = (
        db.execute(select(AthletePreference).where(AthletePreference.athlete_id.in_(athlete_ids))).scalars().all()
        if athlete_ids
        else []
    )
    prefs_by_athlete = {int(r.athlete_id): r for r in pref_rows}
    ts_now = now or datetime.utcnow()

    out: Dict[int, Dict[str, Any]] = {}
    for intervention in interventions:
        athlete_id = int(intervention.athlete_id)
        eval_item = _evaluate_intervention_auto_apply(
            intervention,
            pref=prefs_by_athlete.get(athlete_id),
            coach_policy=coach_policy,
            now=ts_now,
        )
        out[int(intervention.id)] = eval_item
    return out


def _intervention_revert_state_map(
    db: Session,
    interventions: List[CoachIntervention],
) -> Dict[int, Dict[str, Any]]:
    out: Dict[int, Dict[str, Any]] = {}
    approved_ids = {int(row.id) for row in interventions if str(row.status or "").lower() == "approved"}
    if not approved_ids:
        return out

    reverted_source_ids: set[int] = set()
    source_by_intervention: Dict[int, Dict[str, Any]] = {}
    rows = db.execute(
        select(AppWriteLog)
        .where(AppWriteLog.scope == "coach_intervention_action")
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
    ).scalars()
    for log_row in rows:
        payload = dict(log_row.payload or {})
        action = str(payload.get("action") or "").strip().lower()
        if action == "revert_auto_approve":
            try:
                reverted_source_ids.add(int(payload.get("source_action_log_id")))
            except Exception:
                pass
            continue
        if action != "approve" or not bool(payload.get("auto_applied")):
            continue
        try:
            intervention_id = int(payload.get("intervention_id"))
        except Exception:
            continue
        if intervention_id not in approved_ids or intervention_id in source_by_intervention:
            continue
        source_by_intervention[intervention_id] = {
            "source_action_log_id": int(log_row.id),
            "payload": payload,
        }
        if len(source_by_intervention) >= len(approved_ids):
            break

    interventions_by_id = {int(row.id): row for row in interventions}
    for intervention_id in approved_ids:
        source_item = source_by_intervention.get(intervention_id)
        if source_item is None:
            out[intervention_id] = {"available": False, "block_reason": "auto_apply_source_not_found"}
            continue

        source_action_log_id = int(source_item.get("source_action_log_id"))
        source_payload = dict(source_item.get("payload") or {})
        if source_action_log_id in reverted_source_ids:
            out[intervention_id] = {"available": False, "block_reason": "auto_apply_already_reverted"}
            continue

        source_after = dict(source_payload.get("after") or {})
        expected_status = str(source_after.get("status") or "").strip().lower()
        expected_cooldown = _coerce_iso_datetime(source_after.get("cooldown_until"))
        row = interventions_by_id.get(intervention_id)
        current_status = str(getattr(row, "status", "") or "").strip().lower()
        current_cooldown = getattr(row, "cooldown_until", None)
        status_matches = (not expected_status) or (current_status == expected_status)
        cooldown_matches = _same_dt(current_cooldown, expected_cooldown)
        if not status_matches or not cooldown_matches:
            out[intervention_id] = {"available": False, "block_reason": "intervention_state_changed"}
            continue

        out[intervention_id] = {"available": True, "block_reason": None}
    return out


def _audit_log_list_item(row: AppWriteLog, actor_username: Optional[str] = None) -> CoachAuditLogItem:
    return CoachAuditLogItem(
        id=int(row.id),
        scope=str(row.scope or ""),
        actor_user_id=(int(row.actor_user_id) if row.actor_user_id is not None else None),
        actor_username=actor_username,
        created_at=row.created_at,
        payload=dict(row.payload or {}),
    )


def _planner_ruleset_meta_log(meta: Dict[str, Any]) -> Dict[str, Any]:
    allowed = {
        "source",
        "week_policy_version",
        "progression_track_ruleset_version",
        "token_orchestration_ruleset_version",
        "quality_policy_rule_count",
        "token_orchestration_rule_count",
    }
    return {str(k): v for k, v in dict(meta or {}).items() if str(k) in allowed}


def _planner_ruleset_backup_log_item(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    modified_at = item.get("modified_at")
    if hasattr(modified_at, "isoformat"):
        modified_at = modified_at.isoformat()  # type: ignore[assignment]
    return {
        "kind": item.get("kind"),
        "path": item.get("path"),
        "filename": item.get("filename"),
        "size_bytes": item.get("size_bytes"),
        "modified_at": modified_at,
    }


def _coach_user_item(row: User) -> CoachUserItem:
    return CoachUserItem(
        id=int(row.id),
        username=str(row.username or ""),
        role=str(row.role or ""),
        status=str(row.status or "active"),
        athlete_id=(int(row.athlete_id) if row.athlete_id is not None else None),
        must_change_password=bool(row.must_change_password),
        failed_attempts=int(row.failed_attempts or 0),
        locked_until=row.locked_until,
        last_login_at=row.last_login_at,
    )


def _athlete_detail_response(db: Session, athlete: Athlete) -> AthleteDetailResponse:
    assigned_coach_username: Optional[str] = None
    if getattr(athlete, "assigned_coach_user_id", None):
        coach = db.execute(select(User).where(User.id == athlete.assigned_coach_user_id)).scalar_one_or_none()
        if coach is not None:
            assigned_coach_username = str(coach.username or "")
    return AthleteDetailResponse(
        id=int(athlete.id),
        first_name=str(athlete.first_name or ""),
        last_name=str(athlete.last_name or ""),
        email=str(athlete.email or ""),
        dob=athlete.dob,
        max_hr=(int(athlete.max_hr) if athlete.max_hr is not None else None),
        resting_hr=(int(athlete.resting_hr) if athlete.resting_hr is not None else None),
        vdot_seed=(float(athlete.vdot_seed) if getattr(athlete, "vdot_seed", None) is not None else None),
        threshold_pace_sec_per_km=(int(athlete.threshold_pace_sec_per_km) if athlete.threshold_pace_sec_per_km is not None else None),
        easy_pace_sec_per_km=(int(athlete.easy_pace_sec_per_km) if athlete.easy_pace_sec_per_km is not None else None),
        pace_source=str(getattr(athlete, "pace_source", "") or "manual"),
        assigned_coach_user_id=(int(athlete.assigned_coach_user_id) if getattr(athlete, "assigned_coach_user_id", None) is not None else None),
        assigned_coach_username=assigned_coach_username,
        status=str(athlete.status or "active"),
        created_at=athlete.created_at,
    )


def _athlete_list_item(db: Session, athlete: Athlete) -> AthleteListItem:
    detail = _athlete_detail_response(db, athlete)
    return AthleteListItem(
        id=detail.id,
        first_name=detail.first_name,
        last_name=detail.last_name,
        email=detail.email,
        assigned_coach_user_id=detail.assigned_coach_user_id,
        assigned_coach_username=detail.assigned_coach_username,
        vdot_seed=detail.vdot_seed,
        pace_source=detail.pace_source,
        status=detail.status,
    )


def _normalize_user_status(value: Optional[str], *, fallback: str = "active") -> str:
    token = str(value or fallback).strip().lower()
    if token not in {"active", "inactive"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_USER_STATUS", "status": token})
    return token


def _assigned_coach_or_none(db: Session, coach_user_id: Optional[int]) -> Optional[int]:
    if coach_user_id is None:
        return None
    row = db.execute(select(User).where(User.id == int(coach_user_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "COACH_USER_NOT_FOUND", "user_id": int(coach_user_id)})
    if str(row.role or "").lower() not in {"coach", "admin"}:
        raise HTTPException(status_code=400, detail={"code": "INVALID_ASSIGNED_COACH_ROLE", "user_id": int(coach_user_id), "role": row.role})
    if str(getattr(row, "status", "active") or "active").lower() != "active":
        raise HTTPException(status_code=400, detail={"code": "ASSIGNED_COACH_INACTIVE", "user_id": int(coach_user_id)})
    return int(row.id)


def _apply_vdot_pace_profile(
    *,
    athlete: Athlete,
    vdot_seed: Optional[float],
    derive_paces_from_vdot: bool,
    threshold_pace_sec_per_km: Optional[int],
    easy_pace_sec_per_km: Optional[int],
) -> None:
    athlete.vdot_seed = (float(vdot_seed) if vdot_seed is not None else None)
    manual_threshold = threshold_pace_sec_per_km
    manual_easy = easy_pace_sec_per_km

    if athlete.vdot_seed is not None and derive_paces_from_vdot:
        derived = derived_profile_pace_anchors(float(athlete.vdot_seed))
        if derived is not None:
            athlete.threshold_pace_sec_per_km = int(derived["threshold_pace_sec_per_km"])
            athlete.easy_pace_sec_per_km = int(derived["easy_pace_sec_per_km"])
            athlete.pace_source = "vdot_derived"
            return

    if manual_threshold is not None:
        athlete.threshold_pace_sec_per_km = manual_threshold
    if manual_easy is not None:
        athlete.easy_pace_sec_per_km = manual_easy
    if athlete.vdot_seed is not None and (manual_threshold is not None or manual_easy is not None):
        athlete.pace_source = "manual_override"
    elif manual_threshold is not None or manual_easy is not None:
        athlete.pace_source = "manual"
    elif athlete.vdot_seed is None:
        athlete.pace_source = "manual"


def _coach_automation_policy_defaults() -> Dict[str, Any]:
    return {
        "enabled": False,
        "default_auto_apply_low_risk": False,
        "default_auto_apply_confidence_min": 0.8,
        "default_auto_apply_risk_max": 0.3,
        "apply_when_athlete_pref_missing": True,
        "apply_when_athlete_pref_disabled": False,
    }


def _coach_automation_policy_from_log(row: Optional[AppWriteLog]) -> CoachAutomationPolicyResponse:
    defaults = _coach_automation_policy_defaults()
    payload = dict(row.payload or {}) if row is not None else {}
    effective = {
        "enabled": bool(payload.get("enabled", defaults["enabled"])),
        "default_auto_apply_low_risk": bool(payload.get("default_auto_apply_low_risk", defaults["default_auto_apply_low_risk"])),
        "default_auto_apply_confidence_min": float(payload.get("default_auto_apply_confidence_min", defaults["default_auto_apply_confidence_min"])),
        "default_auto_apply_risk_max": float(payload.get("default_auto_apply_risk_max", defaults["default_auto_apply_risk_max"])),
        "apply_when_athlete_pref_missing": bool(payload.get("apply_when_athlete_pref_missing", defaults["apply_when_athlete_pref_missing"])),
        "apply_when_athlete_pref_disabled": bool(payload.get("apply_when_athlete_pref_disabled", defaults["apply_when_athlete_pref_disabled"])),
    }
    return CoachAutomationPolicyResponse(
        **effective,
        updated_at=(row.created_at if row is not None else None),
        updated_by_user_id=(int(row.actor_user_id) if row is not None and row.actor_user_id is not None else None),
        source=("saved" if row is not None else "default"),
    )


def _load_coach_automation_policy(db: Session, coach_user_id: int) -> CoachAutomationPolicyResponse:
    row = db.execute(
        select(AppWriteLog)
        .where(AppWriteLog.scope == "coach_automation_policy", AppWriteLog.actor_user_id == coach_user_id)
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
    ).scalars().first()
    return _coach_automation_policy_from_log(row)


def _plan_or_404(db: Session, plan_id: int) -> Plan:
    row = db.execute(select(Plan).where(Plan.id == plan_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PLAN_NOT_FOUND", "plan_id": plan_id})
    return row


def _plan_week_or_404(db: Session, plan_id: int, week_number: int) -> PlanWeek:
    row = db.execute(
        select(PlanWeek).where(PlanWeek.plan_id == plan_id, PlanWeek.week_number == week_number)
    ).scalar_one_or_none()
    if row is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PLAN_WEEK_NOT_FOUND", "plan_id": plan_id, "week_number": week_number},
        )
    return row


def _canonical_session_templates(db: Session) -> List[SessionLibrary]:
    rows = db.execute(
        select(SessionLibrary)
        .where(func.lower(SessionLibrary.status) == "canonical")
        .order_by(SessionLibrary.duration_min.asc(), SessionLibrary.id.asc())
    ).scalars().all()
    return list(rows)


def _normalized_name_token(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _template_intensity_codes(template: SessionLibrary) -> set[str]:
    codes: set[str] = set()
    blocks = list((template.structure_json or {}).get("blocks") or [])
    for block in blocks:
        if not isinstance(block, dict):
            continue
        target = block.get("target") or {}
        if not isinstance(target, dict):
            continue
        code = str(target.get("intensity_code") or "").strip().upper()
        if code in {"E", "M", "T", "I", "R"}:
            codes.add(code)
    return codes


def _template_main_set_minutes(template: SessionLibrary) -> int:
    total = 0
    blocks = list((template.structure_json or {}).get("blocks") or [])
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if str(block.get("phase") or "").strip().lower() != "main_set":
            continue
        dur = block.get("duration_min")
        if isinstance(dur, int):
            total += max(0, int(dur))
    return total


def _find_best_canonical_template(
    canonical_rows: List[SessionLibrary],
    *,
    intents: Optional[set[str]] = None,
    require_codes: Optional[set[str]] = None,
    exclude_codes: Optional[set[str]] = None,
    name_contains_all: Optional[List[str]] = None,
    name_contains_any: Optional[List[str]] = None,
    target_duration: Optional[int] = None,
    target_main_set_minutes: Optional[int] = None,
) -> tuple[Optional[SessionLibrary], str]:
    filtered: List[SessionLibrary] = []
    for row in canonical_rows:
        intent_token = str(row.intent or "").strip().lower()
        if intents and intent_token not in intents:
            continue
        name_token = _normalized_name_token(str(row.name or ""))
        if name_contains_all and any(token not in name_token for token in name_contains_all):
            continue
        if name_contains_any and not any(token in name_token for token in name_contains_any):
            continue
        codes = _template_intensity_codes(row)
        if require_codes and not require_codes.issubset(codes):
            continue
        if exclude_codes and codes.intersection(exclude_codes):
            continue
        filtered.append(row)
    if not filtered:
        return None, "no_canonical_match"

    def score(row: SessionLibrary) -> tuple[int, int, int]:
        score_dur = 9999
        if target_duration is not None:
            score_dur = abs(int(row.duration_min or 0) - int(target_duration))
        score_main = 9999
        if target_main_set_minutes is not None:
            score_main = abs(_template_main_set_minutes(row) - int(target_main_set_minutes))
        tier_pref = 0 if str(row.tier or "").lower() in {"medium", "hard", "easy"} else 1
        return (score_main, score_dur, tier_pref)

    chosen = sorted(filtered, key=score)[0]
    reason = "matched_canonical_selector"
    if target_duration is not None:
        reason += f"_dur{target_duration}"
    if target_main_set_minutes is not None:
        reason += f"_main{target_main_set_minutes}"
    return chosen, reason


def _estimate_preview_metrics_from_assignments(
    selected_templates: List[Optional[SessionLibrary]],
    selected_names: List[str],
    target_long_run_minutes: int,
) -> Dict[str, Any]:
    planned_minutes = 0
    planned_load = 0.0
    planned_long_run_minutes: Optional[int] = None
    for idx, name in enumerate(selected_names):
        tmpl = selected_templates[idx] if idx < len(selected_templates) else None
        if tmpl is not None:
            duration = max(0, int(tmpl.duration_min or 0))
            intensity = _infer_intensity_factor(str(tmpl.intent or ""), str(tmpl.tier or ""), str(name or ""))
            intent_token = str(tmpl.intent or "").strip().lower()
        else:
            duration = _infer_session_duration_from_name(str(name or ""))
            intensity = _infer_intensity_factor("", "", str(name or ""))
            intent_token = ""
        planned_minutes += duration
        planned_load += (duration * intensity) / 10.0
        name_token = str(name or "").strip().lower()
        if intent_token == "long_run" or "long run" in name_token:
            planned_long_run_minutes = max(int(planned_long_run_minutes or 0), int(duration))
    if planned_long_run_minutes is None:
        planned_long_run_minutes = int(target_long_run_minutes or 0)
    return {
        "planned_minutes_estimate": int(planned_minutes),
        "planned_load_estimate": round(float(planned_load), 2),
        "planned_long_run_minutes": int(planned_long_run_minutes),
    }


def _estimate_template_session_load(template: SessionLibrary, session_name: str) -> float:
    duration = max(0, int(template.duration_min or 0))
    intensity = _infer_intensity_factor(str(template.intent or ""), str(template.tier or ""), str(session_name or ""))
    return (duration * intensity) / 10.0


def _estimate_token_session_load(token_name: str, *, long_run_minutes: int) -> float:
    token = str(token_name or "")
    name_token = token.strip().lower()
    if "long run" in name_token:
        duration = int(long_run_minutes or _infer_session_duration_from_name(token))
    else:
        duration = _infer_session_duration_from_name(token)
    intensity = _infer_intensity_factor("", "", token)
    return (max(0, int(duration)) * intensity) / 10.0


def _calibrated_preview_target_load(
    *,
    raw_target_load: float,
    sessions_order_tokens: List[str],
    long_run_minutes: int,
) -> float:
    token_estimate = round(
        float(sum(_estimate_token_session_load(t, long_run_minutes=long_run_minutes) for t in (sessions_order_tokens or []))),
        2,
    )
    if token_estimate > 0:
        return token_estimate
    # Fallback only if token-based estimate fails.
    return round(float(raw_target_load or 0.0) * 0.56, 2)


def _template_primary_intensity_code(template: Optional[SessionLibrary]) -> Optional[str]:
    if template is None:
        return None
    targets = template.targets_json if isinstance(template.targets_json, dict) else {}
    primary = targets.get("primary") if isinstance(targets.get("primary"), dict) else {}
    code = str(primary.get("intensity_code") or "").strip().upper()
    if code in {"E", "M", "T", "I", "R"}:
        return code
    codes = _template_intensity_codes(template)
    for c in ["M", "T", "I", "R", "E"]:
        if c in codes:
            return c
    return None


def _week_quality_policy(*, phase: str, race_goal: str, week_number: int, total_weeks: int) -> Dict[str, Any]:
    return build_week_quality_policy(
        phase=phase,
        race_goal=race_goal,
        week_number=week_number,
        total_weeks=total_weeks,
    )


def _week_progression_tracks(
    *,
    phase: str,
    race_goal: str,
    week_number: int,
    total_weeks: int,
    phase_step: int,
    phase_weeks_total: int,
) -> Dict[str, Any]:
    return build_week_progression_tracks(
        phase=phase,
        race_goal=race_goal,
        week_number=week_number,
        total_weeks=total_weeks,
        phase_step=phase_step,
        phase_weeks_total=phase_weeks_total,
    )


def _orchestrate_week_tokens(
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
    return build_orchestrated_week_tokens(
        base_tokens=base_tokens,
        phase=phase,
        race_goal=race_goal,
        week_number=week_number,
        total_weeks=total_weeks,
        phase_step=phase_step,
        phase_weeks_total=phase_weeks_total,
        sessions_per_week=sessions_per_week,
    )


def _apply_week_quality_mix_policy(
    *,
    canonical_rows: List[SessionLibrary],
    selected_templates: List[Optional[SessionLibrary]],
    selected_names: List[str],
    selected_assignments: List[Dict[str, Any]],
    phase: str,
    race_goal: str,
    week_number: int,
    total_weeks: int,
    long_run_minutes: int,
) -> None:
    if not canonical_rows:
        return
    policy = _week_quality_policy(phase=phase, race_goal=race_goal, week_number=week_number, total_weeks=total_weeks)
    race_focus = str(policy.get("race_focus") or "")
    phase_token = str(policy.get("phase") or "")

    codes = [_template_primary_intensity_code(t) for t in selected_templates]
    t_count = sum(1 for c in codes if c == "T")
    i_count = sum(1 for c in codes if c == "I")
    m_count = sum(1 for c in codes if c == "M")

    def apply_swap(idx: int, new_tpl: SessionLibrary, tag: str, note: str) -> None:
        selected_templates[idx] = new_tpl
        selected_names[idx] = str(new_tpl.name or selected_names[idx])
        assignment = selected_assignments[idx]
        assignment["session_name"] = str(new_tpl.name or assignment.get("session_name") or "")
        assignment["source_template_id"] = int(new_tpl.id)
        prior_reason = str(assignment.get("template_selection_reason") or "week_policy")
        assignment["template_selection_reason"] = f"{prior_reason}|{tag}"
        prior_rationale = [str(x) for x in list(assignment.get("template_selection_rationale") or []) if str(x).strip()]
        prior_rationale.append(note)
        assignment["template_selection_rationale"] = prior_rationale[:8]

    # Short-race build/peak weeks: diversify if both quality slots collapsed into threshold.
    if race_focus in {"5k", "10k"} and phase_token in {"build", "peak"} and t_count >= 2 and i_count == 0:
        vo2_ctx = _vo2_ladder_context(phase=phase, race_goal=race_goal, week_number=week_number, total_weeks=total_weeks)
        for idx, assignment in enumerate(selected_assignments):
            planning_token = _normalized_name_token(str(assignment.get("planning_token") or ""))
            if "race pace" not in planning_token and "interval" not in planning_token:
                continue
            tpl, reason = _find_best_canonical_template(
                canonical_rows,
                intents={"vo2"},
                require_codes={"I"},
                name_contains_all=["vo2 intervals"],
                target_main_set_minutes=int(vo2_ctx["target_main_minutes"]),
            )
            if tpl is not None:
                apply_swap(
                    idx,
                    tpl,
                    "mix_policy_diversified",
                    f"week mix policy ({race_focus} {phase_token}): diversified quality split by swapping to VO2 ladder step {vo2_ctx['step']}/{vo2_ctx['steps_total']} ({vo2_ctx['target_main_minutes']} min I, {reason})",
                )
                break

    # Marathon/HM build/peak weeks: ensure race-pace token becomes M-work if a match exists.
    codes = [_template_primary_intensity_code(t) for t in selected_templates]
    m_count = sum(1 for c in codes if c == "M")
    if race_focus in {"half_marathon", "marathon"} and phase_token in {"build", "peak"} and m_count == 0:
        m_ctx = _marathon_pace_ladder_context(phase=phase, race_goal=race_goal, week_number=week_number, total_weeks=total_weeks)
        for idx, assignment in enumerate(selected_assignments):
            planning_token = _normalized_name_token(str(assignment.get("planning_token") or ""))
            if "race pace" not in planning_token and "marathon pace" not in planning_token:
                continue
            tpl, reason = _find_best_canonical_template(
                canonical_rows,
                intents={"marathon_pace"},
                require_codes={"M"},
                name_contains_any=["marathon pace blocks", "marathon pace continuous", "long run", "finish"],
                target_main_set_minutes=int(m_ctx["target_main_minutes"]),
                target_duration=int(long_run_minutes or 0) if "long run" in planning_token else None,
            )
            if tpl is not None:
                apply_swap(
                    idx,
                    tpl,
                    "mix_policy_specificity",
                    f"week mix policy ({race_focus} {phase_token}): ensured race-specific M stimulus using ladder step {m_ctx['step']}/{m_ctx['steps_total']} ({m_ctx['target_main_minutes']} min M, {reason})",
                )
                break


def _retune_week_for_target_load(
    *,
    canonical_rows: List[SessionLibrary],
    selected_templates: List[Optional[SessionLibrary]],
    selected_names: List[str],
    selected_assignments: List[Dict[str, Any]],
    target_load: float,
    phase: str,
) -> None:
    if not canonical_rows or not selected_templates or not selected_names:
        return
    metrics = _estimate_preview_metrics_from_assignments(selected_templates, selected_names, 0)
    current_load = float(metrics.get("planned_load_estimate") or 0.0)
    if current_load <= 0:
        return
    delta = float(target_load or 0.0) - current_load
    # Avoid overfitting tiny differences.
    if abs(delta) < 0.6:
        return

    best_improvement = 0.0
    best_idx: Optional[int] = None
    best_tpl: Optional[SessionLibrary] = None
    best_new_load = current_load

    for idx, tmpl in enumerate(selected_templates):
        if tmpl is None:
            continue
        intent = str(tmpl.intent or "").strip().lower()
        if intent not in {"easy_aerobic", "recovery"}:
            continue
        current_session_load = _estimate_template_session_load(tmpl, selected_names[idx])
        current_duration = int(tmpl.duration_min or 0)
        phase_token = str(phase or "").strip().lower()
        max_shift = 10 if phase_token in {"base", "recovery", "taper"} else (15 if phase_token == "build" else 20)
        same_family: List[SessionLibrary] = []
        for cand in canonical_rows:
            if str(cand.intent or "").strip().lower() != intent:
                continue
            if bool(cand.is_treadmill) != bool(tmpl.is_treadmill):
                continue
            # Keep substitutions within a practical range to avoid wild jumps.
            cand_duration = int(cand.duration_min or 0)
            if abs(cand_duration - current_duration) > max_shift:
                continue
            same_family.append(cand)
        for cand in same_family:
            cand_load = _estimate_template_session_load(cand, str(cand.name or selected_names[idx]))
            new_total = current_load - current_session_load + cand_load
            current_err = abs(float(target_load or 0.0) - current_load)
            new_err = abs(float(target_load or 0.0) - new_total)
            improvement = current_err - new_err
            if improvement > best_improvement + 0.05:
                best_improvement = improvement
                best_idx = idx
                best_tpl = cand
                best_new_load = new_total

    if best_idx is None or best_tpl is None:
        return

    selected_templates[best_idx] = best_tpl
    selected_names[best_idx] = str(best_tpl.name or selected_names[best_idx])
    assignment = selected_assignments[best_idx] if best_idx < len(selected_assignments) else None
    if isinstance(assignment, dict):
        prior_reason = str(assignment.get("template_selection_reason") or "load_alignment")
        assignment["session_name"] = str(best_tpl.name or assignment.get("session_name") or "")
        assignment["source_template_id"] = int(best_tpl.id)
        assignment["template_selection_reason"] = f"{prior_reason}|load_aligned"
        prior_rationale = [str(x) for x in list(assignment.get("template_selection_rationale") or []) if str(x).strip()]
        prior_rationale.append(
            f"load alignment: swapped within {str(best_tpl.intent or '').strip() or 'same'} family to reduce week load drift toward target ({round(best_new_load, 2)} est)"
        )
        assignment["template_selection_rationale"] = prior_rationale[:8]


def _derive_week_quality_focus(
    *,
    intended_focus: Optional[str],
    selected_templates: List[Optional[SessionLibrary]],
    selected_names: List[str],
    race_goal: str,
    phase: str,
) -> tuple[str, Optional[str]]:
    codes: List[str] = []
    for idx, tmpl in enumerate(selected_templates):
        code = _template_primary_intensity_code(tmpl)
        if code is None:
            # Infer from session name as fallback.
            name = str(selected_names[idx] if idx < len(selected_names) else "")
            n = name.lower()
            if "threshold" in n or "tempo" in n:
                code = "T"
            elif "vo2" in n or "interval" in n:
                code = "I"
            elif "marathon pace" in n or "m finish" in n:
                code = "M"
            elif "strides" in n or "repetition" in n:
                code = "R"
            elif "easy" in n or "recovery" in n or "long run" in n:
                code = "E"
        if code:
            codes.append(code)
    t_count = sum(1 for c in codes if c == "T")
    i_count = sum(1 for c in codes if c == "I")
    m_count = sum(1 for c in codes if c == "M")
    r_count = sum(1 for c in codes if c == "R")

    race_focus = _race_focus_bucket(race_goal)
    phase_token = str(phase or "").strip().lower()
    actual_focus = "balanced"
    if t_count == 0 and i_count == 0 and m_count == 0:
        actual_focus = "aerobic_foundation" if phase_token == "base" else "low_intensity_maintenance"
    elif t_count > 0 and i_count > 0:
        actual_focus = "threshold_vo2_blend"
    elif m_count > 0 and race_focus in {"marathon", "half_marathon"}:
        actual_focus = "marathon_specific_endurance" if race_focus == "marathon" else "threshold_marathon_pace_blend"
    elif t_count > 0:
        actual_focus = "threshold_foundation" if phase_token == "base" else "threshold_focused"
    elif i_count > 0:
        actual_focus = "vo2_sharpening" if phase_token in {"peak", "taper"} else "vo2_focused"
    elif r_count > 0:
        actual_focus = "neuromuscular_support"

    note = None
    if intended_focus and str(intended_focus) != actual_focus:
        note = f"quality focus adjusted for actual selected sessions: {actual_focus} (policy intent: {intended_focus})"
    return actual_focus, note


def _template_selection_summary(
    *,
    session_name: str,
    planning_token: Optional[str],
    selection_reason: Optional[str],
    race_goal: str,
    phase: str,
) -> Optional[str]:
    if not session_name:
        return None
    token = str(planning_token or "").strip()
    selected = str(session_name or "").strip()
    reason = str(selection_reason or "").strip()
    race_focus = _race_focus_bucket(race_goal)
    phase_token = str(phase or "").strip().lower()
    if token and token != selected:
        if "load_aligned" in reason:
            return f"Adjusted {token} to canonical template {selected} for {phase_token} load alignment ({race_focus}); full session template structure is retained."
        return f"Mapped {token} to canonical template {selected} for {phase_token} {race_focus} week; this refers to the full session template (not just the main-set label)."
    if token and token == selected and "already_canonical" in reason:
        return f"Kept canonical session {selected}."
    return f"Selected {selected} for {phase_token} {race_focus} week."


def _template_selection_rationale(
    *,
    planning_token: str,
    selection_reason: str,
    phase: str,
    race_goal: str,
    week_number: Optional[int],
    total_weeks: Optional[int],
    long_run_minutes: Optional[int],
    selected_template: Optional[SessionLibrary],
) -> List[str]:
    labels: List[str] = []
    token = str(planning_token or "").strip()
    if token:
        labels.append(f"planning token: {token}")
    phase_token = str(phase or "").strip().lower()
    if phase_token:
        labels.append(f"phase: {phase_token}")
    goal_token = str(race_goal or "").strip()
    if goal_token:
        labels.append(f"goal: {goal_token}")
    if isinstance(week_number, int) and isinstance(total_weeks, int) and total_weeks > 0:
        labels.append(f"week: {week_number}/{total_weeks}")
    if selected_template is not None:
        labels.append(f"canonical template: {selected_template.name}")
        intent = str(selected_template.intent or "").strip()
        if intent:
            labels.append(f"intent: {intent}")
    if selection_reason:
        labels.append(f"selector rule: {selection_reason}")
        if "long_run_marathon_finish" in selection_reason:
            labels.append("marathon/HM build-peak logic prefers long run with M finish")
            if isinstance(long_run_minutes, int) and long_run_minutes > 0:
                labels.append(f"long-run target duration: {long_run_minutes} min")
        elif selection_reason.startswith("long_run_"):
            labels.append("mapped long-run token to easy long-run canonical template")
            if isinstance(long_run_minutes, int) and long_run_minutes > 0:
                labels.append(f"long-run target duration: {long_run_minutes} min")
        elif selection_reason.startswith("threshold_cruise_"):
            labels.append("build/peak threshold progression prefers cruise intervals")
            ladder = _threshold_ladder_context(phase=phase, race_goal=race_goal, week_number=week_number or 1, total_weeks=total_weeks or 1)
            labels.append(
                f"threshold ladder ({ladder['race_focus']} {ladder['phase']}): step {ladder['step']}/{ladder['steps_total']} -> {ladder['target_main_minutes']} min T"
            )
        elif selection_reason.startswith("threshold_continuous_"):
            labels.append("base/taper threshold progression prefers continuous threshold work")
            ladder = _threshold_ladder_context(phase=phase, race_goal=race_goal, week_number=week_number or 1, total_weeks=total_weeks or 1)
            labels.append(
                f"threshold ladder ({ladder['race_focus']} {ladder['phase']}): step {ladder['step']}/{ladder['steps_total']} -> {ladder['target_main_minutes']} min T"
            )
        elif selection_reason.startswith("vo2_"):
            labels.append("VO2 token mapped to interval template with progression target")
            ladder = _vo2_ladder_context(phase=phase, race_goal=race_goal, week_number=week_number or 1, total_weeks=total_weeks or 1)
            labels.append(
                f"VO2 ladder ({ladder['race_focus']} {ladder['phase']}): step {ladder['step']}/{ladder['steps_total']} -> {ladder['target_main_minutes']} min I"
            )
        elif selection_reason.startswith("race_pace_marathon_"):
            labels.append("marathon/HM race-pace token mapped to M-pace canonical workout")
            ladder = _marathon_pace_ladder_context(phase=phase, race_goal=race_goal, week_number=week_number or 1, total_weeks=total_weeks or 1)
            labels.append(
                f"M-pace ladder ({ladder['race_focus']} {ladder['phase']}): step {ladder['step']}/{ladder['steps_total']} -> {ladder['target_main_minutes']} min M"
            )
        elif selection_reason.startswith("race_pace_short_fallback_"):
            labels.append("short-race race-pace token falls back to threshold/VO2 quality")
            ladder = _short_race_race_pace_fallback_context(phase=phase, race_goal=race_goal, week_number=week_number or 1, total_weeks=total_weeks or 1)
            labels.append(
                f"short-race fallback ladder ({ladder['race_focus']}): {ladder['mode']} step {ladder['step']}/{ladder['steps_total']} target {ladder['target_main_minutes']} min"
            )
        elif selection_reason.startswith("strides_") or selection_reason.startswith("hill_placeholder_"):
            labels.append("neuromuscular token mapped to strides/repetition canonical session")
        elif selection_reason == "already_canonical":
            labels.append("existing canonical template preserved")
        elif selection_reason in {"no_selector_rule", "no_canonical_match", "no_canonical_library"}:
            labels.append("no canonical selector match; original session token/name retained")
    return labels[:6]


def _progress_index(progress: float, steps_total: int) -> int:
    if steps_total <= 1:
        return 0
    return min(steps_total - 1, max(0, int(progress * (steps_total - 1))))


def _race_focus_bucket(race_goal: str) -> str:
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


def _threshold_ladder_context(*, phase: str, race_goal: str, week_number: int, total_weeks: int) -> Dict[str, Any]:
    progress = float(week_number) / float(max(total_weeks, 1))
    phase_token = str(phase or "").strip().lower()
    race_focus = _race_focus_bucket(race_goal)
    if phase_token in {"base", "taper"}:
        ladder = [20] if phase_token == "base" else [15]
    else:
        ladder_map = {
            "5k": [24, 28, 30, 32, 36],
            "10k": [24, 30, 32, 36, 40],
            "half_marathon": [24, 30, 36, 40, 45],
            "marathon": [20, 24, 30, 36, 40],
            "general": [24, 30, 32, 36, 40],
        }
        ladder = ladder_map.get(race_focus, ladder_map["general"])
    idx = _progress_index(progress, len(ladder))
    return {
        "phase": phase_token or "unknown",
        "race_focus": race_focus,
        "step": idx + 1,
        "steps_total": len(ladder),
        "target_main_minutes": int(ladder[idx]),
    }


def _vo2_ladder_context(*, phase: str, race_goal: str, week_number: int, total_weeks: int) -> Dict[str, Any]:
    progress = float(week_number) / float(max(total_weeks, 1))
    phase_token = str(phase or "").strip().lower()
    race_focus = _race_focus_bucket(race_goal)
    if phase_token == "base":
        ladder = [12, 15]
    elif phase_token == "taper":
        ladder = [12, 15]
    else:
        ladder_map = {
            "5k": [15, 18, 20, 22, 24],
            "10k": [15, 18, 20, 22, 24],
            "half_marathon": [12, 15, 18, 20],
            "marathon": [12, 15, 18, 20],
            "general": [15, 18, 20, 22],
        }
        ladder = ladder_map.get(race_focus, ladder_map["general"])
    idx = _progress_index(progress, len(ladder))
    return {
        "phase": phase_token or "unknown",
        "race_focus": race_focus,
        "step": idx + 1,
        "steps_total": len(ladder),
        "target_main_minutes": int(ladder[idx]),
    }


def _marathon_pace_ladder_context(*, phase: str, race_goal: str, week_number: int, total_weeks: int) -> Dict[str, Any]:
    progress = float(week_number) / float(max(total_weeks, 1))
    phase_token = str(phase or "").strip().lower()
    race_focus = _race_focus_bucket(race_goal)
    if phase_token == "build":
        ladder = [20, 30, 36, 45]
    elif phase_token == "peak":
        ladder = [30, 36, 45, 60]
    elif phase_token == "taper":
        ladder = [16, 20]
    else:
        ladder = [20, 30]
    idx = _progress_index(progress, len(ladder))
    return {
        "phase": phase_token or "unknown",
        "race_focus": race_focus,
        "step": idx + 1,
        "steps_total": len(ladder),
        "target_main_minutes": int(ladder[idx]),
    }


def _short_race_race_pace_fallback_context(*, phase: str, race_goal: str, week_number: int, total_weeks: int) -> Dict[str, Any]:
    progress = float(week_number) / float(max(total_weeks, 1))
    race_focus = _race_focus_bucket(race_goal)
    if progress < 0.6:
        ladder = [20, 24, 28, 30]
        mode = "threshold"
    else:
        ladder = [15, 18, 20, 22]
        mode = "vo2"
    idx = _progress_index(progress, len(ladder))
    return {
        "phase": str(phase or "").strip().lower() or "unknown",
        "race_focus": race_focus,
        "mode": mode,
        "step": idx + 1,
        "steps_total": len(ladder),
        "target_main_minutes": int(ladder[idx]),
    }


def _pick_canonical_template_for_planning_token(
    *,
    db: Session,
    canonical_rows: List[SessionLibrary],
    planning_token: str,
    phase: str,
    race_goal: str,
    week_number: int,
    total_weeks: int,
    long_run_minutes: int,
) -> tuple[Optional[SessionLibrary], str]:
    token = _normalized_name_token(planning_token)
    # If the token is already a canonical template name (e.g., regenerated existing modern plan), preserve it.
    direct = next((r for r in canonical_rows if _normalized_name_token(str(r.name or "")) == token), None)
    if direct is not None:
        return direct, "already_canonical"

    progress = (float(week_number) / float(max(total_weeks, 1))) if total_weeks else 0.0
    phase_token = str(phase or "").lower()
    race_token = str(race_goal or "").lower()

    if "long run" in token and "finish" not in token and "marathon pace" not in token:
        # Use M-finish long runs primarily for marathon/HM build/peak weeks.
        if race_token in {"marathon", "half marathon"} and phase_token in {"build", "peak"} and progress >= 0.4:
            finish_map = [
                (110, 15),
                (120, 20),
                (130, 25),
                (140, 30),
            ]
            finish_target = 15
            for lr_cutoff, finish_val in finish_map:
                if long_run_minutes >= lr_cutoff:
                    finish_target = finish_val
            finish_tpl, reason = _find_best_canonical_template(
                canonical_rows,
                intents={"marathon_pace"},
                require_codes={"M"},
                name_contains_all=["long run", "finish"],
                target_duration=long_run_minutes,
                target_main_set_minutes=finish_target,
            )
            if finish_tpl is not None:
                return finish_tpl, f"long_run_marathon_finish_{reason}"
        base_tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"long_run"},
            require_codes={"E"},
            exclude_codes={"M", "T", "I"},
            name_contains_all=["long run"],
            target_duration=long_run_minutes,
        )
        return base_tpl, f"long_run_{reason}"

    if "recovery" in token:
        dur = 40 if phase_token in {"build", "peak"} else 35
        tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"recovery"},
            require_codes={"E"},
            name_contains_all=["recovery run"],
            target_duration=dur,
        )
        return tpl, f"recovery_{reason}"

    if "easy run" in token:
        base_dur = 45
        if phase_token == "base":
            base_dur = 55
        elif phase_token in {"build", "peak"}:
            base_dur = 60 if progress >= 0.5 else 50
        elif phase_token == "recovery":
            base_dur = 40
        elif phase_token == "taper":
            base_dur = 35
        tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"easy_aerobic"},
            require_codes={"E"},
            name_contains_all=["easy run"],
            target_duration=base_dur,
        )
        return tpl, f"easy_{reason}"

    if "tempo" in token or "threshold" in token:
        threshold_ctx = _threshold_ladder_context(
            phase=phase,
            race_goal=race_goal,
            week_number=int(week_number),
            total_weeks=int(total_weeks),
        )
        t_minutes = int(threshold_ctx["target_main_minutes"])
        if phase_token in {"base", "taper"}:
            tpl, reason = _find_best_canonical_template(
                canonical_rows,
                intents={"threshold"},
                require_codes={"T"},
                name_contains_all=["threshold continuous"],
                target_main_set_minutes=t_minutes,
            )
            return tpl, f"threshold_continuous_{reason}"
        # Build/Peak: favor cruise intervals and progress volume.
        tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"lactate_threshold", "threshold"},
            require_codes={"T"},
            name_contains_all=["threshold cruise intervals"],
            target_main_set_minutes=t_minutes,
        )
        if tpl is not None:
            return tpl, f"threshold_cruise_{reason}"
        tpl2, reason2 = _find_best_canonical_template(
            canonical_rows,
            intents={"threshold"},
            require_codes={"T"},
            name_contains_all=["threshold continuous"],
            target_main_set_minutes=max(15, t_minutes - 10),
        )
        return tpl2, f"threshold_fallback_{reason2}"

    if "vo2" in token or "interval" in token:
        vo2_ctx = _vo2_ladder_context(
            phase=phase,
            race_goal=race_goal,
            week_number=int(week_number),
            total_weeks=int(total_weeks),
        )
        target_main = int(vo2_ctx["target_main_minutes"])
        tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"vo2"},
            require_codes={"I"},
            name_contains_all=["vo2 intervals"],
            target_main_set_minutes=target_main,
        )
        return tpl, f"vo2_{reason}"

    if "race pace" in token:
        if phase_token == "taper":
            opener_name_tokens = ["openers"]
            if race_token in {"5k", "10k"}:
                opener_name_tokens += ["5k", "10k"]
            elif "half" in race_token:
                opener_name_tokens += ["hm"]
            elif "marathon" in race_token:
                opener_name_tokens += ["marathon"]
            tpl, reason = _find_best_canonical_template(
                canonical_rows,
                name_contains_all=opener_name_tokens,
                target_duration=35 if "marathon" in race_token else 30,
            )
            if tpl is not None:
                return tpl, f"taper_openers_{reason}"
        # Marathon/HM plans get M blocks; short race plans bias to threshold/vo2 if no race-specific template exists.
        if race_token in {"marathon", "half marathon"}:
            m_ctx = _marathon_pace_ladder_context(
                phase=phase,
                race_goal=race_goal,
                week_number=int(week_number),
                total_weeks=int(total_weeks),
            )
            target_main = int(m_ctx["target_main_minutes"])
            tpl, reason = _find_best_canonical_template(
                canonical_rows,
                intents={"marathon_pace"},
                require_codes={"M"},
                name_contains_any=["marathon pace blocks", "marathon pace continuous"],
                target_main_set_minutes=target_main,
            )
            return tpl, f"race_pace_marathon_{reason}"
        # 5k/10k race-specific placeholder -> threshold/VO2 bias (quality over wrong M-workout selection).
        short_ctx = _short_race_race_pace_fallback_context(
            phase=phase,
            race_goal=race_goal,
            week_number=int(week_number),
            total_weeks=int(total_weeks),
        )
        if str(short_ctx["mode"]) == "threshold":
            tpl, reason = _find_best_canonical_template(
                canonical_rows,
                intents={"threshold", "lactate_threshold"},
                require_codes={"T"},
                name_contains_any=["threshold continuous", "threshold cruise intervals"],
                target_main_set_minutes=int(short_ctx["target_main_minutes"]),
            )
            return tpl, f"race_pace_short_fallback_threshold_{reason}"
        tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"vo2"},
            require_codes={"I"},
            name_contains_all=["vo2 intervals"],
            target_main_set_minutes=int(short_ctx["target_main_minutes"]),
        )
        return tpl, f"race_pace_short_fallback_vo2_{reason}"

    if "hill" in token:
        # No dedicated canonical hill pack yet; route to strides/repetition as neuromuscular quality placeholder.
        tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"strides"},
            require_codes={"R"},
            name_contains_any=["strides", "repetition"],
            target_duration=35,
        )
        return tpl, f"hill_placeholder_{reason}"

    if "strides" in token or "neuromuscular" in token:
        dur = 35 if phase_token != "taper" else 30
        tpl, reason = _find_best_canonical_template(
            canonical_rows,
            intents={"strides"},
            require_codes={"R"},
            name_contains_any=["strides", "repetition"],
            target_duration=dur,
        )
        return tpl, f"strides_{reason}"

    if "taper" in token or "openers" in token:
        if race_token in {"marathon"}:
            tpl, reason = _find_best_canonical_template(canonical_rows, name_contains_all=["openers", "marathon"])
            return tpl, f"taper_marathon_{reason}"
        if "half" in race_token:
            tpl, reason = _find_best_canonical_template(canonical_rows, name_contains_all=["openers", "hm"])
            return tpl, f"taper_hm_{reason}"
        tpl, reason = _find_best_canonical_template(canonical_rows, name_contains_all=["openers", "5k", "10k"])
        return tpl, f"taper_short_{reason}"

    return None, "no_selector_rule"


def _plan_preview_from_request(payload: PlanPreviewRequest, db: Optional[Session] = None) -> PlanPreviewResponse:
    preferred_days = _normalize_day_labels(list(payload.preferred_days or []))
    long_run_day = None
    if payload.preferred_long_run_day:
        token = str(payload.preferred_long_run_day).strip()[:3].title()
        if token in DAY_NAMES:
            long_run_day = token
    weeks_rows = generate_plan_weeks(
        payload.start_date,
        payload.weeks,
        payload.race_goal,
        sessions_per_week=payload.sessions_per_week,
        max_session_min=payload.max_session_min,
    )
    canonical_rows = _canonical_session_templates(db) if db is not None else []
    weeks_detail: List[PlanPreviewWeek] = []
    phase_totals: Dict[str, int] = {}
    for wk in weeks_rows:
        phase_key = str(wk.get("phase") or "")
        phase_totals[phase_key] = int(phase_totals.get(phase_key, 0)) + 1
    phase_seen: Dict[str, int] = {}
    for wk in weeks_rows:
        week_policy = _week_quality_policy(
            phase=str(wk["phase"]),
            race_goal=str(payload.race_goal),
            week_number=int(wk["week_number"]),
            total_weeks=int(payload.weeks),
        )
        phase_key = str(wk.get("phase") or "")
        phase_seen[phase_key] = int(phase_seen.get(phase_key, 0)) + 1
        phase_step = int(phase_seen[phase_key])
        phase_total = int(phase_totals.get(phase_key, 1))
        progression = _week_progression_tracks(
            phase=str(wk["phase"]),
            race_goal=str(payload.race_goal),
            week_number=int(wk["week_number"]),
            total_weeks=int(payload.weeks),
            phase_step=phase_step,
            phase_weeks_total=phase_total,
        )
        orchestration = _orchestrate_week_tokens(
            base_tokens=list(wk.get("sessions_order") or []),
            phase=str(wk["phase"]),
            race_goal=str(payload.race_goal),
            week_number=int(wk["week_number"]),
            total_weeks=int(payload.weeks),
            phase_step=phase_step,
            phase_weeks_total=phase_total,
            sessions_per_week=int(payload.sessions_per_week),
        )
        base_tokens = list(orchestration.get("tokens") or [])
        calibrated_target_load = _calibrated_preview_target_load(
            raw_target_load=float(wk.get("target_load") or 0.0),
            sessions_order_tokens=base_tokens,
            long_run_minutes=int(wk.get("long_run_minutes") or 0),
        )
        week_policy_rationale = [str(x) for x in list(week_policy.get("rationale") or []) if str(x).strip()]
        week_policy_rationale.extend([str(x) for x in list(progression.get("notes") or []) if str(x).strip()])
        week_policy_rationale.extend([str(x) for x in list(orchestration.get("rationale") or []) if str(x).strip()])
        week_policy_rationale.append(
            f"target load calibrated to session-load scale from default token mix: {calibrated_target_load}"
        )
        assignments = assign_week_sessions(
            wk["week_start"],
            list(base_tokens),
            preferred_days=preferred_days or None,
            preferred_long_run_day=long_run_day,
        )
        selected_order: List[str] = []
        selected_assignments: List[Dict[str, Any]] = []
        selected_templates_for_metrics: List[Optional[SessionLibrary]] = []
        for idx, assignment in enumerate(assignments):
            original_token = str(base_tokens[idx]) if idx < len(base_tokens) else str(assignment["session_name"])
            selected_template = None
            selection_reason = "no_canonical_library"
            if canonical_rows:
                selected_template, selection_reason = _pick_canonical_template_for_planning_token(
                    db=db,
                    canonical_rows=canonical_rows,
                    planning_token=original_token,
                    phase=str(wk["phase"]),
                    race_goal=str(payload.race_goal),
                    week_number=int(wk["week_number"]),
                    total_weeks=int(payload.weeks),
                    long_run_minutes=int(wk.get("long_run_minutes") or 0),
                )
            selected_name = str(selected_template.name) if selected_template is not None else str(assignment["session_name"])
            selected_order.append(selected_name)
            selected_templates_for_metrics.append(selected_template)
            selected_assignments.append(
                {
                    "session_day": assignment["session_day"],
                    "session_name": selected_name,
                    "source_template_id": (int(selected_template.id) if selected_template is not None else None),
                    "planning_token": original_token,
                    "template_selection_reason": selection_reason,
                    "template_selection_rationale": _template_selection_rationale(
                        planning_token=original_token,
                        selection_reason=selection_reason,
                        phase=str(wk["phase"]),
                        race_goal=str(payload.race_goal),
                        week_number=int(wk["week_number"]),
                        total_weeks=int(payload.weeks),
                        long_run_minutes=int(wk.get("long_run_minutes") or 0),
                        selected_template=selected_template,
                    ),
                    "template_selection_summary": _template_selection_summary(
                        session_name=selected_name,
                        planning_token=original_token,
                        selection_reason=selection_reason,
                        race_goal=str(payload.race_goal),
                        phase=str(wk["phase"]),
                    ),
                }
            )
        if canonical_rows:
            _apply_week_quality_mix_policy(
                canonical_rows=canonical_rows,
                selected_templates=selected_templates_for_metrics,
                selected_names=selected_order,
                selected_assignments=selected_assignments,
                phase=str(wk["phase"]),
                race_goal=str(payload.race_goal),
                week_number=int(wk["week_number"]),
                total_weeks=int(payload.weeks),
                long_run_minutes=int(wk.get("long_run_minutes") or 0),
            )
            _retune_week_for_target_load(
                canonical_rows=canonical_rows,
                selected_templates=selected_templates_for_metrics,
                selected_names=selected_order,
                selected_assignments=selected_assignments,
                target_load=float(calibrated_target_load),
                phase=str(wk["phase"]),
            )
        actual_quality_focus, focus_note = _derive_week_quality_focus(
            intended_focus=(
                str(orchestration.get("quality_focus_hint"))
                if orchestration.get("quality_focus_hint")
                else (str(week_policy.get("quality_focus")) if week_policy.get("quality_focus") else None)
            ),
            selected_templates=selected_templates_for_metrics,
            selected_names=selected_order,
            race_goal=str(payload.race_goal),
            phase=str(wk["phase"]),
        )
        if focus_note:
            week_policy_rationale.append(focus_note)
        preview_metrics = _estimate_preview_metrics_from_assignments(
            selected_templates_for_metrics,
            selected_order,
            int(wk.get("long_run_minutes") or 0),
        )
        sorted_assignments = sorted(
            selected_assignments,
            key=lambda a: (a.get("session_day"), str(a.get("session_name") or "")),
        )
        weeks_detail.append(
            PlanPreviewWeek(
                week_number=int(wk["week_number"]),
                phase=str(wk["phase"]),
                week_start=wk["week_start"],
                week_end=wk["week_end"],
                target_load=float(calibrated_target_load),
                long_run_minutes=int(wk.get("long_run_minutes") or 0),
                planned_load_estimate=(
                    float(preview_metrics["planned_load_estimate"])
                    if preview_metrics.get("planned_load_estimate") is not None
                    else None
                ),
                planned_minutes_estimate=(
                    int(preview_metrics["planned_minutes_estimate"])
                    if preview_metrics.get("planned_minutes_estimate") is not None
                    else None
                ),
                planned_long_run_minutes=(
                    int(preview_metrics["planned_long_run_minutes"])
                    if preview_metrics.get("planned_long_run_minutes") is not None
                    else None
                ),
                week_policy_version=str(week_policy.get("version") or WEEK_POLICY_VERSION),
                quality_focus=actual_quality_focus,
                coach_summary=(str(progression.get("summary")) if progression.get("summary") else None),
                progression_tracks=[str(x) for x in list(progression.get("tracks") or []) if str(x).strip()],
                week_policy_rationale=week_policy_rationale[:8],
                sessions_order=selected_order,
                assignments=[
                    PlanSessionAssignment(
                        session_day=a["session_day"],
                        session_name=str(a["session_name"]),
                        source_template_id=(int(a["source_template_id"]) if a.get("source_template_id") is not None else None),
                        planning_token=(str(a["planning_token"]) if a.get("planning_token") is not None else None),
                        template_selection_reason=(
                            str(a["template_selection_reason"]) if a.get("template_selection_reason") is not None else None
                        ),
                        template_selection_summary=(
                            str(a["template_selection_summary"]) if a.get("template_selection_summary") is not None else None
                        ),
                        template_selection_rationale=[str(x) for x in list(a.get("template_selection_rationale") or [])],
                    )
                    for a in sorted_assignments
                ],
                selection_strategy_version=(PLANNER_SELECTION_STRATEGY_VERSION if canonical_rows else "generic_fallback_v1"),
            )
        )
    return PlanPreviewResponse(
        athlete_id=int(payload.athlete_id),
        race_goal=str(payload.race_goal),
        weeks=int(payload.weeks),
        start_date=payload.start_date,
        sessions_per_week=int(payload.sessions_per_week),
        max_session_min=int(payload.max_session_min),
        preferred_days=preferred_days,
        preferred_long_run_day=long_run_day,
        weeks_detail=weeks_detail,
    )


def _plan_summary(row: Plan) -> CoachPlanSummary:
    return CoachPlanSummary.model_validate(row)


def _default_plan_name(*, athlete: Athlete, race_goal: str, start_date: date) -> str:
    first = str(getattr(athlete, "first_name", "") or "").strip()
    last = str(getattr(athlete, "last_name", "") or "").strip()
    athlete_name = " ".join([p for p in [first, last] if p]).strip() or f"Athlete #{int(getattr(athlete, 'id', 0) or 0)}"
    year = int(start_date.year) if isinstance(start_date, date) else date.today().year
    goal = str(race_goal or "Plan").strip() or "Plan"
    return f"{athlete_name} {goal} Plan {year}"


def _estimate_current_vdot_for_athlete(db: Session, athlete_id: int) -> Optional[float]:
    rows = db.execute(
        select(
            TrainingLog.id,
            TrainingLog.date,
            TrainingLog.duration_min,
            TrainingLog.distance_km,
            TrainingLog.load_score,
            TrainingLog.rpe,
            TrainingLog.session_category,
            TrainingLog.avg_pace_sec_per_km,
        )
        .where(TrainingLog.athlete_id == athlete_id)
        .order_by(TrainingLog.date.asc(), TrainingLog.id.asc())
    ).mappings().all()
    if not rows:
        return None
    history = compute_vdot_history(pd.DataFrame(rows))
    latest = history.get("latest") if isinstance(history, dict) else None
    if not isinstance(latest, dict):
        return None
    try:
        return round(float(latest.get("vdot")), 2)
    except Exception:
        return None


def _resolve_session_template_for_plan_day(db: Session, row: PlanDaySession) -> Optional[SessionLibrary]:
    if getattr(row, "source_template_id", None):
        template = db.execute(select(SessionLibrary).where(SessionLibrary.id == row.source_template_id)).scalar_one_or_none()
        if template is not None:
            return template
    template_name = str(row.source_template_name or "").strip() or str(row.session_name or "").strip()
    if not template_name:
        return None
    return db.execute(select(SessionLibrary).where(SessionLibrary.name == template_name)).scalar_one_or_none()


def _resolve_session_templates_for_plan_days(
    db: Session, rows: List[PlanDaySession]
) -> Dict[int, Optional[SessionLibrary]]:
    if not rows:
        return {}
    template_ids = {
        int(r.source_template_id)
        for r in rows
        if getattr(r, "source_template_id", None) is not None
    }
    template_names = {
        str(name).strip()
        for r in rows
        for name in [r.source_template_name, r.session_name]
        if str(name or "").strip()
    }
    templates_by_id: Dict[int, SessionLibrary] = {}
    templates_by_name: Dict[str, SessionLibrary] = {}
    if template_ids:
        id_rows = db.execute(
            select(SessionLibrary).where(SessionLibrary.id.in_(sorted(template_ids)))
        ).scalars().all()
        templates_by_id = {int(t.id): t for t in id_rows}
    if template_names:
        name_rows = db.execute(
            select(SessionLibrary).where(SessionLibrary.name.in_(sorted(template_names)))
        ).scalars().all()
        templates_by_name = {str(t.name): t for t in name_rows}
    resolved: Dict[int, Optional[SessionLibrary]] = {}
    for r in rows:
        tmpl = None
        if getattr(r, "source_template_id", None) is not None:
            tmpl = templates_by_id.get(int(r.source_template_id))
        if tmpl is None:
            template_name = str(r.source_template_name or "").strip() or str(r.session_name or "").strip()
            if template_name:
                tmpl = templates_by_name.get(template_name)
        resolved[int(r.id)] = tmpl
    return resolved


def _compile_plan_day_session_snapshot(
    *,
    db: Session,
    row: PlanDaySession,
    athlete: Athlete,
    vdot: Optional[float] = None,
    template: Optional[SessionLibrary] = None,
) -> None:
    tmpl = template or _resolve_session_template_for_plan_day(db, row)
    structure_json: dict[str, Any]
    template_name = None
    template_intent = ""
    if tmpl is not None and isinstance(tmpl.structure_json, dict):
        row.source_template_id = int(tmpl.id)
        row.source_template_name = str(tmpl.name or row.source_template_name or "")
        structure_json = dict(tmpl.structure_json or {})
        template_name = str(tmpl.name or "")
        template_intent = str(tmpl.intent or "")
    else:
        row.source_template_id = None
        structure_json = default_structure(max(20, _infer_session_duration_from_name(str(row.session_name or ""))))
        template_name = str(row.source_template_name or "")
        template_intent = ""

    compiled = compile_session_for_athlete(
        structure_json=structure_json,
        athlete_id=int(athlete.id),
        session_name=str(row.session_name or ""),
        template_name=template_name,
        template_intent=template_intent,
        vdot=vdot,
        context={
            "plan_week_id": int(row.plan_week_id),
            "session_day": row.session_day.isoformat() if row.session_day else None,
            "athlete_threshold_pace_sec_per_km": athlete.threshold_pace_sec_per_km,
            "athlete_easy_pace_sec_per_km": athlete.easy_pace_sec_per_km,
        },
    )
    row.compiled_session_json = dict(compiled or {})
    row.compiled_methodology = "daniels_vdot"
    row.compiled_vdot = (round(float(vdot), 2) if vdot is not None else None)
    row.compiled_at = datetime.utcnow()
    row.compile_context_json = {
        "source_template_id": (int(tmpl.id) if tmpl is not None else None),
        "source_template_name": (str(tmpl.name) if tmpl is not None else str(row.source_template_name or "")),
        "athlete_id": int(athlete.id),
        "athlete_threshold_pace_sec_per_km": athlete.threshold_pace_sec_per_km,
        "athlete_easy_pace_sec_per_km": athlete.easy_pace_sec_per_km,
        "athlete_max_hr": athlete.max_hr,
        "athlete_resting_hr": athlete.resting_hr,
        "vdot": (round(float(vdot), 2) if vdot is not None else None),
    }


def _infer_session_duration_from_name(session_name: str) -> int:
    text = (session_name or "").strip().lower()
    if not text:
        return 45
    if "long run" in text:
        return 90
    if "marathon pace" in text:
        return 80
    if "tempo" in text or "threshold" in text:
        return 55
    if "vo2" in text or "interval" in text:
        return 60
    if "hill" in text:
        return 50
    if "recovery" in text:
        return 35
    if "easy" in text:
        return 45
    if "race pace" in text:
        return 60
    if "strides" in text or "neuromuscular" in text:
        return 40
    return 45


def _infer_intensity_factor(intent: str, tier: str, session_name: str) -> float:
    intent_token = (intent or "").strip().lower()
    tier_token = (tier or "").strip().lower()
    name = (session_name or "").strip().lower()
    base = 5.0
    if intent_token in {"recovery"} or "recovery" in name:
        base = 3.5
    elif intent_token in {"easy", "endurance"} or "easy" in name:
        base = 4.5
    elif intent_token in {"long_run"} or "long run" in name:
        base = 5.5
    elif intent_token in {"threshold", "tempo"} or "tempo" in name or "threshold" in name:
        base = 7.0
    elif intent_token in {"vo2", "intervals", "speed"} or "vo2" in name or "interval" in name:
        base = 8.0
    elif intent_token in {"race_pace"} or "race pace" in name or "marathon pace" in name:
        base = 7.2
    elif intent_token in {"hills", "neuromuscular"} or "hill" in name or "strides" in name:
        base = 6.2
    tier_adjust = {"low": -0.4, "medium": 0.0, "high": 0.5}.get(tier_token, 0.0)
    return max(2.5, min(9.0, base + tier_adjust))


def _recalculate_plan_week_metrics(db: Session, week_id: int) -> None:
    week = db.execute(select(PlanWeek).where(PlanWeek.id == week_id)).scalar_one_or_none()
    if week is None:
        return
    sessions = db.execute(
        select(PlanDaySession).where(PlanDaySession.plan_week_id == week_id)
    ).scalars().all()
    template_names = {
        str(name).strip()
        for s in sessions
        for name in [s.source_template_name, s.session_name]
        if str(name or "").strip()
    }
    template_ids = {int(s.source_template_id) for s in sessions if getattr(s, "source_template_id", None) is not None}
    templates_by_name: Dict[str, SessionLibrary] = {}
    templates_by_id: Dict[int, SessionLibrary] = {}
    if template_names:
        template_rows = db.execute(
            select(SessionLibrary).where(SessionLibrary.name.in_(sorted(template_names)))
        ).scalars().all()
        templates_by_name = {str(t.name): t for t in template_rows}
    if template_ids:
        template_rows_by_id = db.execute(select(SessionLibrary).where(SessionLibrary.id.in_(sorted(template_ids)))).scalars().all()
        templates_by_id = {int(t.id): t for t in template_rows_by_id}

    planned_minutes = 0
    planned_load = 0.0
    for s in sessions:
        tmpl = (
            templates_by_id.get(int(s.source_template_id)) if getattr(s, "source_template_id", None) is not None else None
        ) or templates_by_name.get(str(s.source_template_name or "").strip()) or templates_by_name.get(str(s.session_name or "").strip())
        if tmpl is not None:
            duration = max(0, int(tmpl.duration_min or 0))
            intensity = _infer_intensity_factor(str(tmpl.intent or ""), str(tmpl.tier or ""), str(s.session_name or ""))
        else:
            duration = _infer_session_duration_from_name(str(s.session_name or ""))
            intensity = _infer_intensity_factor("", "", str(s.session_name or ""))
        planned_minutes += duration
        planned_load += (duration * intensity) / 10.0

    metric = db.execute(select(PlanWeekMetric).where(PlanWeekMetric.plan_week_id == week_id)).scalar_one_or_none()
    if metric is None:
        metric = PlanWeekMetric(plan_week_id=int(week_id), planned_minutes=0, planned_load=0.0)
        db.add(metric)
    metric.planned_minutes = int(planned_minutes)
    metric.planned_load = round(float(planned_load), 2)


def _recalculate_plan_metrics_for_plan(db: Session, plan_id: int) -> None:
    week_ids = db.execute(select(PlanWeek.id).where(PlanWeek.plan_id == plan_id)).scalars().all()
    for week_id in week_ids:
        _recalculate_plan_week_metrics(db, int(week_id))


def _plan_detail(db: Session, plan: Plan) -> CoachPlanDetailResponse:
    weeks = db.execute(
        select(PlanWeek).where(PlanWeek.plan_id == plan.id).order_by(PlanWeek.week_number.asc())
    ).scalars().all()
    phase_totals: Dict[str, int] = {}
    for wk in weeks:
        phase_key = str(wk.phase or "")
        phase_totals[phase_key] = int(phase_totals.get(phase_key, 0)) + 1
    phase_seen: Dict[str, int] = {}
    metrics_rows = db.execute(
        select(PlanWeekMetric).where(PlanWeekMetric.plan_week_id.in_([w.id for w in weeks])) if weeks else select(PlanWeekMetric).where(False)
    ).scalars().all()
    metrics_by_week_id = {m.plan_week_id: m for m in metrics_rows}
    session_rows = db.execute(
        select(PlanDaySession)
        .where(PlanDaySession.plan_week_id.in_([w.id for w in weeks])) if weeks else select(PlanDaySession).where(False)
    ).scalars().all()
    sessions_by_week: Dict[int, List[PlanDaySession]] = {}
    for row in session_rows:
        sessions_by_week.setdefault(int(row.plan_week_id), []).append(row)
    resolved_templates_by_session_id = _resolve_session_templates_for_plan_days(db, session_rows)
    week_items: List[CoachPlanWeekItem] = []
    for wk in weeks:
        phase_key = str(wk.phase or "")
        phase_seen[phase_key] = int(phase_seen.get(phase_key, 0)) + 1
        phase_step = int(phase_seen[phase_key])
        phase_total = int(phase_totals.get(phase_key, 1))
        sessions = sorted(sessions_by_week.get(int(wk.id), []), key=lambda r: (r.session_day, r.id))
        metric = metrics_by_week_id.get(int(wk.id))
        week_policy = _week_quality_policy(
            phase=str(wk.phase or ""),
            race_goal=str(plan.race_goal or ""),
            week_number=int(wk.week_number),
            total_weeks=int(plan.weeks or 1),
        )
        progression = _week_progression_tracks(
            phase=str(wk.phase or ""),
            race_goal=str(plan.race_goal or ""),
            week_number=int(wk.week_number),
            total_weeks=int(plan.weeks or 1),
            phase_step=phase_step,
            phase_weeks_total=phase_total,
        )
        session_templates_for_focus = [resolved_templates_by_session_id.get(int(s.id)) for s in sessions]
        session_names_for_focus = [str(s.session_name or "") for s in sessions]
        actual_quality_focus, focus_note = _derive_week_quality_focus(
            intended_focus=(str(week_policy.get("quality_focus")) if week_policy.get("quality_focus") else None),
            selected_templates=session_templates_for_focus,
            selected_names=session_names_for_focus,
            race_goal=str(plan.race_goal or ""),
            phase=str(wk.phase or ""),
        )
        week_policy_rationale = [str(x) for x in list(week_policy.get("rationale") or []) if str(x).strip()]
        week_policy_rationale.extend([str(x) for x in list(progression.get("notes") or []) if str(x).strip()])
        if focus_note:
            week_policy_rationale.append(focus_note)
        week_items.append(
            CoachPlanWeekItem(
                id=int(wk.id),
                week_number=int(wk.week_number),
                phase=str(wk.phase),
                week_start=wk.week_start,
                week_end=wk.week_end,
                sessions_order=list(wk.sessions_order or []),
                target_load=float(wk.target_load or 0.0),
                locked=bool(wk.locked),
                planned_minutes=(int(metric.planned_minutes) if metric is not None else None),
                planned_load=(float(metric.planned_load) if metric is not None else None),
                week_policy_version=str(week_policy.get("version") or WEEK_POLICY_VERSION),
                quality_focus=actual_quality_focus,
                coach_summary=(str(progression.get("summary")) if progression.get("summary") else None),
                progression_tracks=[str(x) for x in list(progression.get("tracks") or []) if str(x).strip()],
                week_policy_rationale=week_policy_rationale[:8],
                sessions=[_coach_plan_day_session_item(s) for s in sessions],
            )
        )
    return CoachPlanDetailResponse(plan=_plan_summary(plan), weeks=week_items)


def _coach_plan_day_session_item(row: PlanDaySession) -> CoachPlanDaySessionItem:
    compiled = dict(getattr(row, "compiled_session_json", None) or {})
    compile_ctx = dict(getattr(row, "compile_context_json", None) or {})
    planning_ctx = compile_ctx.get("planning") if isinstance(compile_ctx.get("planning"), dict) else {}
    planning_token_value = (
        str(planning_ctx.get("planning_token"))
        if planning_ctx.get("planning_token") is not None and str(planning_ctx.get("planning_token")).strip()
        else None
    )
    selection_reason_value = (
        str(planning_ctx.get("template_selection_reason"))
        if planning_ctx.get("template_selection_reason") is not None and str(planning_ctx.get("template_selection_reason")).strip()
        else None
    )
    planning_phase = str(planning_ctx.get("phase") or "")
    planning_race_goal = str(planning_ctx.get("race_goal") or "")
    intensity_codes: List[str] = []
    summary_parts: List[str] = []
    blocks = list(compiled.get("blocks") or [])
    for block in blocks:
        if not isinstance(block, dict):
            continue
        if str(block.get("phase") or "").strip().lower() != "main_set":
            continue
        target = block.get("target") or {}
        if not isinstance(target, dict):
            target = {}
        code = str(target.get("intensity_code") or "").strip().upper()
        if code in {"E", "M", "T", "I", "R"} and code not in intensity_codes:
            intensity_codes.append(code)
        reps = block.get("repetitions")
        work_min = block.get("work_duration_min")
        work_sec = block.get("work_duration_sec")
        duration_min = block.get("duration_min")
        if isinstance(reps, int) and reps > 0 and isinstance(work_min, int) and work_min > 0:
            part = f"{reps}x{work_min}min"
        elif isinstance(reps, int) and reps > 0 and isinstance(work_sec, int) and work_sec > 0:
            part = f"{reps}x{work_sec}s"
        elif isinstance(duration_min, int) and duration_min > 0:
            part = f"{duration_min}min"
        else:
            continue
        if code in {"E", "M", "T", "I", "R"}:
            part = f"{part} {code}"
        summary_parts.append(part)
    compiled_summary = " + ".join(summary_parts[:3]) if summary_parts else None
    return CoachPlanDaySessionItem(
        id=int(row.id),
        plan_week_id=int(row.plan_week_id),
        athlete_id=int(row.athlete_id),
        session_day=row.session_day,
        session_name=str(row.session_name or ""),
        source_template_id=(int(row.source_template_id) if row.source_template_id is not None else None),
        source_template_name=str(row.source_template_name or ""),
        status=str(row.status or ""),
        compiled_methodology=(str(row.compiled_methodology or "") or None),
        compiled_vdot=(round(float(row.compiled_vdot), 2) if row.compiled_vdot is not None else None),
        compiled_intensity_codes=intensity_codes,
        compiled_summary=compiled_summary,
        planning_token=planning_token_value,
        template_selection_reason=selection_reason_value,
        template_selection_summary=_template_selection_summary(
            session_name=str(row.session_name or ""),
            planning_token=planning_token_value,
            selection_reason=selection_reason_value,
            race_goal=planning_race_goal,
            phase=planning_phase,
        ),
        template_selection_rationale=[str(x) for x in list(planning_ctx.get("template_selection_rationale") or []) if str(x).strip()],
    )


def _daily_loads(db: Session, athlete_id: int, days: int) -> List[float]:
    today = date.today()
    since = today - timedelta(days=days - 1)
    rows = db.execute(
        select(TrainingLog.date, func.sum(TrainingLog.load_score))
        .where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= since, TrainingLog.date <= today)
        .group_by(TrainingLog.date)
        .order_by(TrainingLog.date.asc())
    ).all()
    by_day = {row[0]: float(row[1] or 0.0) for row in rows}
    return [round(by_day.get(since + timedelta(days=offset), 0.0), 2) for offset in range(days)]


def _load_summary(loads_7d: List[float], loads_28d: List[float], readiness_value: Optional[float], pain_recent: bool) -> Dict[str, Any]:
    weekly_total = round(sum(loads_7d), 2)
    avg_daily = round(mean(loads_7d), 2) if loads_7d else 0.0
    std_daily = round(pstdev(loads_7d), 2) if len(loads_7d) > 1 else 0.0
    monotony = round((avg_daily / std_daily), 2) if std_daily > 0 else None
    strain = round((weekly_total * monotony), 2) if monotony is not None else None
    ac_ratio = compute_acute_chronic_ratio(loads_28d)
    risk = "low"
    if pain_recent or (readiness_value is not None and readiness_value < 3.0) or ac_ratio >= 1.5:
        risk = "high"
    elif ac_ratio >= 1.2 or (readiness_value is not None and readiness_value < 3.6):
        risk = "moderate"
    return {
        "acute_chronic_ratio": ac_ratio,
        "weekly_load_total": weekly_total,
        "avg_daily_load": avg_daily,
        "monotony": monotony,
        "strain": strain,
        "risk": risk,
    }


def _planned_session_for_today(db: Session, athlete_id: int, today: date) -> Dict[str, Any]:
    row = db.execute(
        select(PlanDaySession).where(PlanDaySession.athlete_id == athlete_id, PlanDaySession.session_day == today)
    ).scalar_one_or_none()
    if row is None:
        return {
            "exists": False,
            "date": today.isoformat(),
            "session_name": None,
            "source_template_name": None,
            "status": None,
            "structure_json": default_structure(45),
        }
    template = _resolve_session_template_for_plan_day(db, row)
    if isinstance(getattr(row, "compiled_session_json", None), dict) and row.compiled_session_json:
        structure = dict(row.compiled_session_json or {})
    else:
        structure = template.structure_json if template and isinstance(template.structure_json, dict) else default_structure(45)
    return {
        "exists": True,
        "date": row.session_day.isoformat(),
        "session_name": row.session_name,
        "source_template_name": row.source_template_name,
        "status": row.status,
        "template_found": template is not None,
        "template_id": getattr(template, "id", None),
        "structure_json": structure,
    }


def _next_event_context(db: Session, athlete_id: int, today: date) -> Dict[str, Any]:
    event_row = db.execute(
        select(Event).where(Event.athlete_id == athlete_id, Event.event_date >= today).order_by(Event.event_date.asc())
    ).scalar_one_or_none()
    if event_row is None:
        return {"next_event": None, "days_to_event": None}
    return {
        "next_event": {
            "id": event_row.id,
            "name": event_row.name,
            "distance": event_row.distance,
            "event_date": event_row.event_date.isoformat(),
        },
        "days_to_event": max(0, (event_row.event_date - today).days),
    }


def _latest_checkin(db: Session, athlete_id: int, today: date) -> Optional[CheckIn]:
    return db.execute(
        select(CheckIn)
        .where(CheckIn.athlete_id == athlete_id, CheckIn.day <= today)
        .order_by(CheckIn.day.desc())
    ).scalars().first()


def _pain_recent(db: Session, athlete_id: int, today: date) -> bool:
    since = today - timedelta(days=6)
    return bool(
        db.execute(
            select(TrainingLog.id).where(
                TrainingLog.athlete_id == athlete_id,
                TrainingLog.date >= since,
                TrainingLog.date <= today,
                TrainingLog.pain_flag.is_(True),
            )
        ).first()
    )


def _enrich_adapted_blocks(blocks: List[Dict[str, Any]], athlete: Athlete) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    code_to_hr_label = {"E": "Z1-Z2", "M": "Z3", "T": "Z4", "I": "Z5", "R": "Z5"}
    for block in blocks:
        row = dict(block)
        target = dict(row.get("target") or {})
        pace_label = target.get("pace_zone")
        hr_label = target.get("hr_zone")
        intensity_code = str(target.get("intensity_code") or "").strip().upper()
        row["target"] = target
        vdot_band = target.get("vdot_pace_band") if isinstance(target.get("vdot_pace_band"), dict) else None
        if isinstance(vdot_band, dict) and str(vdot_band.get("display") or "").strip():
            row["target_pace_range"] = str(vdot_band.get("display"))
        else:
            row["target_pace_range"] = pace_range_for_label(
                str(pace_label or ""),
                threshold_pace_sec_per_km=athlete.threshold_pace_sec_per_km,
                easy_pace_sec_per_km=athlete.easy_pace_sec_per_km,
            )
        row["target_hr_range"] = hr_range_for_label(
            str(hr_label or code_to_hr_label.get(intensity_code, "")),
            max_hr=athlete.max_hr,
            resting_hr=athlete.resting_hr,
        )
        row["intervals"] = row.get("intervals") or []
        output.append(row)
    return output


def _weekly_rollups_for_athlete(db: Session, athlete_id: int, weeks: int) -> WeeklyRollupResponse:
    since = date.today() - timedelta(days=(weeks * 7))
    rows = db.execute(
        select(TrainingLog.id, TrainingLog.athlete_id, TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score)
        .where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= since)
    ).mappings().all()
    df = pd.DataFrame(rows)
    weekly = weekly_summary(df)
    items = [
        WeeklyRollupItem(
            week=str(row["week"]),
            duration_min=float(row["duration_min"]),
            load_score=float(row["load_score"]),
            sessions=int(row["sessions"]),
        )
        for _, row in weekly.iterrows()
    ] if not weekly.empty else []
    return WeeklyRollupResponse(athlete_id=athlete_id, weeks=weeks, items=items)


def _coach_portfolio_analytics_payload(db: Session) -> CoachPortfolioAnalyticsResponse:
    today = date.today()
    week_start = today - timedelta(days=6)

    athletes_total = int(db.execute(select(func.count(Athlete.id))).scalar_one() or 0)
    athletes_active = int(
        db.execute(select(func.count(Athlete.id)).where(Athlete.status == "active")).scalar_one() or 0
    )

    latest_by_athlete = db.execute(
        select(CheckIn).order_by(CheckIn.athlete_id.asc(), CheckIn.day.desc())
    ).scalars().all()
    seen = set()
    readiness_values: List[float] = []
    for row in latest_by_athlete:
        if row.athlete_id in seen:
            continue
        seen.add(row.athlete_id)
        readiness_values.append(readiness_score(row.sleep, row.energy, row.recovery, row.stress))
    avg_readiness = round(mean(readiness_values), 2) if readiness_values else None

    active_interventions = int(
        db.execute(select(func.count(CoachIntervention.id)).where(CoachIntervention.status == "open")).scalar_one() or 0
    )
    planned_count = int(
        db.execute(
            select(func.count(PlanDaySession.id)).where(
                PlanDaySession.session_day >= week_start,
                PlanDaySession.session_day <= today,
            )
        ).scalar_one()
        or 0
    )
    completed_count = int(
        db.execute(
            select(func.count(PlanDaySession.id)).where(
                PlanDaySession.session_day >= week_start,
                PlanDaySession.session_day <= today,
                PlanDaySession.status == "completed",
            )
        ).scalar_one()
        or 0
    )
    compliance = round(completed_count / planned_count, 3) if planned_count > 0 else None

    return CoachPortfolioAnalyticsResponse(
        athletes_total=athletes_total,
        athletes_active=athletes_active,
        average_readiness=avg_readiness,
        active_interventions=active_interventions,
        weekly_compliance_rate=compliance,
        metrics={
            "week_start": week_start.isoformat(),
            "week_end": today.isoformat(),
            "planned_sessions_week": planned_count,
            "completed_sessions_week": completed_count,
        },
    )


@router.get("/health")
def health():
    return {"status": "ok"}


def _issue_access_token(user: User) -> AuthTokenResponse:
    settings = get_settings()
    token = issue_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        athlete_id=user.athlete_id,
        expires_in_seconds=int(settings.jwt_access_token_expire_minutes * 60),
    )
    return AuthTokenResponse(
        access_token=token,
        expires_in=int(settings.jwt_access_token_expire_minutes * 60),
        user_id=user.id,
        username=user.username,
        role=user.role,
        athlete_id=user.athlete_id,
    )


@router.post("/auth/token", response_model=AuthTokenResponse)
@limiter.limit(get_settings().auth_token_rate_limit)
def auth_token(request: Request, response: Response, payload: AuthTokenRequest = Body(...), db: Session = Depends(get_db)):
    del request, response
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS"})
    if str(getattr(user, "status", "active") or "active").lower() != "active":
        raise HTTPException(status_code=403, detail={"code": "ACCOUNT_INACTIVE"})
    if str(user.role or "").lower() == "client" and user.athlete_id is not None:
        athlete = db.execute(select(Athlete).where(Athlete.id == user.athlete_id)).scalar_one_or_none()
        if athlete is not None and str(athlete.status or "active").lower() != "active":
            raise HTTPException(status_code=403, detail={"code": "ATHLETE_INACTIVE"})
    if account_locked(user.locked_until):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "ACCOUNT_LOCKED",
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            },
        )
    if not verify_password(payload.password, user.password_hash):
        threshold = 5
        lock_minutes = 15
        user.failed_attempts, lock_until = apply_failed_login(
            int(user.failed_attempts or 0),
            threshold=threshold,
            lock_minutes=lock_minutes,
        )
        if lock_until is not None:
            user.locked_until = lock_until
        raise HTTPException(
            status_code=401,
            detail={
                "code": "INVALID_CREDENTIALS",
                "failed_attempts": int(user.failed_attempts or 0),
                "locked_until": user.locked_until.isoformat() if user.locked_until else None,
            },
        )
    if user.must_change_password:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PASSWORD_CHANGE_REQUIRED",
                "username": user.username,
                "user_id": user.id,
            },
        )
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    return _issue_access_token(user)


@router.post("/auth/change-password", response_model=ChangePasswordResponse)
@limiter.limit(get_settings().auth_token_rate_limit)
def change_password(
    request: Request,
    response: Response,
    payload: ChangePasswordRequest = Body(...),
    db: Session = Depends(get_db),
):
    del request, response
    user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail={"code": "USER_NOT_FOUND"})
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail={"code": "INVALID_CREDENTIALS"})
    try:
        user.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "PASSWORD_POLICY", "message": str(exc)})
    user.must_change_password = False
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.utcnow()
    return ChangePasswordResponse(status="ok", message="Password changed")


@router.post("/training-logs", response_model=TrainingLogResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def create_training_log(
    request: Request,
    response: Response,
    payload: TrainingLogInput = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    del request, response
    if principal.role.lower() not in {"coach", "admin"} and (principal.athlete_id is None or int(principal.athlete_id) != int(payload.athlete_id)):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ATHLETE_SCOPE", "athlete_id": payload.athlete_id, "principal_athlete_id": principal.athlete_id},
        )
    row = persist_training_log(db, payload)
    return TrainingLogResponse.model_validate(row)


@router.post("/checkins", response_model=CheckInResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def create_or_update_checkin(
    request: Request,
    response: Response,
    payload: CheckInInput = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    del request, response
    target_athlete_id = int(payload.athlete_id or principal.athlete_id or 0)
    if target_athlete_id <= 0:
        raise HTTPException(status_code=400, detail={"code": "ATHLETE_ID_REQUIRED"})
    if principal.role.lower() not in {"coach", "admin"} and (principal.athlete_id is None or int(principal.athlete_id) != target_athlete_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ATHLETE_SCOPE", "athlete_id": target_athlete_id, "principal_athlete_id": principal.athlete_id},
        )
    _athlete_or_404(db, target_athlete_id)
    row = db.execute(
        select(CheckIn).where(CheckIn.athlete_id == target_athlete_id, CheckIn.day == payload.day)
    ).scalar_one_or_none()
    if row is None:
        row = CheckIn(
            athlete_id=target_athlete_id,
            day=payload.day,
            sleep=payload.sleep,
            energy=payload.energy,
            recovery=payload.recovery,
            stress=payload.stress,
            training_today=payload.training_today,
        )
        db.add(row)
        db.flush()
        db.refresh(row)
    else:
        row.sleep = payload.sleep
        row.energy = payload.energy
        row.recovery = payload.recovery
        row.stress = payload.stress
        row.training_today = payload.training_today
        db.flush()
        db.refresh(row)
    return CheckInResponse.model_validate(row)


@router.get("/athletes", response_model=AthleteListResponse)
def list_athletes(
    status: Optional[str] = Query(default=None),
    assigned_coach_user_id: Optional[int] = Query(default=None, ge=1),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    base_stmt = select(Athlete)
    count_stmt = select(func.count(Athlete.id))
    if status:
        base_stmt = base_stmt.where(Athlete.status == status)
        count_stmt = count_stmt.where(Athlete.status == status)
    if assigned_coach_user_id is not None:
        base_stmt = base_stmt.where(Athlete.assigned_coach_user_id == assigned_coach_user_id)
        count_stmt = count_stmt.where(Athlete.assigned_coach_user_id == assigned_coach_user_id)
    total = int(db.execute(count_stmt).scalar_one() or 0)
    rows = db.execute(base_stmt.order_by(Athlete.last_name.asc(), Athlete.first_name.asc()).offset(offset).limit(limit)).scalars().all()
    return AthleteListResponse(total=total, offset=offset, limit=limit, items=[_athlete_list_item(db, r) for r in rows])


@router.post("/coach/athletes", response_model=CoachCreateAthleteResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_create_athlete(
    request: Request,
    response: Response,
    payload: CoachCreateAthleteRequest = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    if db.execute(select(User.id).where(User.username == payload.username.strip())).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail={"code": "USERNAME_TAKEN", "username": payload.username.strip()})
    if db.execute(select(Athlete.id).where(Athlete.email == payload.email.strip().lower())).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail={"code": "ATHLETE_EMAIL_TAKEN", "email": payload.email.strip().lower()})
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "PASSWORD_POLICY", "message": str(exc)}) from exc

    athlete = Athlete(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        email=payload.email.strip().lower(),
        dob=payload.dob,
        status=payload.status.strip() or "active",
        max_hr=payload.max_hr,
        resting_hr=payload.resting_hr,
        assigned_coach_user_id=_assigned_coach_or_none(db, payload.assigned_coach_user_id),
    )
    _apply_vdot_pace_profile(
        athlete=athlete,
        vdot_seed=payload.vdot_seed,
        derive_paces_from_vdot=bool(payload.derive_paces_from_vdot),
        threshold_pace_sec_per_km=payload.threshold_pace_sec_per_km,
        easy_pace_sec_per_km=payload.easy_pace_sec_per_km,
    )
    db.add(athlete)
    db.flush()
    user = User(
        username=payload.username.strip(),
        password_hash=password_hash,
        role="client",
        athlete_id=int(athlete.id),
        status="active",
        must_change_password=bool(payload.must_change_password),
        failed_attempts=0,
        locked_until=None,
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"code": "CREATE_ATHLETE_CONFLICT"}) from exc

    db.refresh(athlete)
    db.refresh(user)
    _append_app_write_log(
        db,
        scope="coach_create_athlete",
        actor_user_id=principal.user_id,
        payload={
            "athlete_id": int(athlete.id),
            "username": user.username,
            "email": athlete.email,
            "status": athlete.status,
            "assigned_coach_user_id": athlete.assigned_coach_user_id,
            "vdot_seed": athlete.vdot_seed,
            "pace_source": athlete.pace_source,
            "actor_user_id": int(principal.user_id),
        },
    )
    db.flush()
    return CoachCreateAthleteResponse(status="ok", athlete=_athlete_detail_response(db, athlete), user=_coach_user_item(user))


@router.get("/coach/coaches", response_model=CoachUserListResponse)
def list_coaches(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del principal
    total = int(db.execute(select(func.count(User.id)).where(User.role == "coach")).scalar_one() or 0)
    rows = db.execute(
        select(User).where(User.role == "coach").order_by(User.username.asc()).offset(offset).limit(limit)
    ).scalars().all()
    return CoachUserListResponse(total=total, offset=offset, limit=limit, items=[_coach_user_item(r) for r in rows])


@router.post("/coach/coaches", response_model=CoachCreateUserResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_create_coach_user(
    request: Request,
    response: Response,
    payload: CoachCreateUserRequest = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    username = payload.username.strip()
    if db.execute(select(User.id).where(User.username == username)).scalar_one_or_none() is not None:
        raise HTTPException(status_code=409, detail={"code": "USERNAME_TAKEN", "username": username})
    try:
        password_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "PASSWORD_POLICY", "message": str(exc)}) from exc
    row = User(
        username=username,
        password_hash=password_hash,
        role="coach",
        status="active",
        must_change_password=bool(payload.must_change_password),
        failed_attempts=0,
        locked_until=None,
    )
    db.add(row)
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"code": "CREATE_COACH_CONFLICT"}) from exc
    db.refresh(row)
    _append_app_write_log(
        db,
        scope="coach_create_user",
        actor_user_id=principal.user_id,
        payload={
            "user_id": int(row.id),
            "username": row.username,
            "role": row.role,
            "actor_user_id": int(principal.user_id),
        },
    )
    db.flush()
    return CoachCreateUserResponse(status="ok", user=_coach_user_item(row))


@router.get("/coach/users", response_model=CoachUsersQueryResponse)
def list_coach_users(
    role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    athlete_id: Optional[int] = Query(default=None, ge=1),
    q: Optional[str] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del principal
    stmt = select(User)
    count_stmt = select(func.count(User.id))

    role_filter = (role or "").strip().lower()
    if role_filter:
        if role_filter == "athlete":
            role_filter = "client"
        stmt = stmt.where(User.role == role_filter)
        count_stmt = count_stmt.where(User.role == role_filter)
    if status:
        normalized_status = _normalize_user_status(status)
        stmt = stmt.where(User.status == normalized_status)
        count_stmt = count_stmt.where(User.status == normalized_status)
    if athlete_id is not None:
        stmt = stmt.where(User.athlete_id == athlete_id)
        count_stmt = count_stmt.where(User.athlete_id == athlete_id)
    if q:
        q_token = f"%{q.strip()}%"
        stmt = stmt.where(User.username.ilike(q_token))
        count_stmt = count_stmt.where(User.username.ilike(q_token))

    total = int(db.execute(count_stmt).scalar_one() or 0)
    rows = db.execute(stmt.order_by(User.username.asc()).offset(offset).limit(limit)).scalars().all()
    return CoachUsersQueryResponse(total=total, offset=offset, limit=limit, items=[_coach_user_item(r) for r in rows])


@router.post("/coach/users/{user_id}/unlock", response_model=CoachUnlockUserResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_unlock_user(
    user_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    row = _user_or_404(db, user_id)
    row.failed_attempts = 0
    row.locked_until = None
    db.flush()
    db.refresh(row)
    _append_app_write_log(
        db,
        scope="coach_unlock_user",
        actor_user_id=principal.user_id,
        payload={
            "user_id": int(row.id),
            "username": row.username,
            "role": row.role,
            "actor_user_id": int(principal.user_id),
        },
    )
    db.flush()
    return CoachUnlockUserResponse(status="ok", user=_coach_user_item(row))


@router.post("/coach/users/{user_id}/reset-password", response_model=CoachResetPasswordResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_reset_user_password(
    user_id: int,
    request: Request,
    response: Response,
    payload: CoachResetPasswordRequest = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    row = _user_or_404(db, user_id)
    try:
        row.password_hash = hash_password(payload.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"code": "PASSWORD_POLICY", "message": str(exc)}) from exc
    row.failed_attempts = 0
    row.locked_until = None
    row.must_change_password = bool(payload.must_change_password)
    db.flush()
    db.refresh(row)
    _append_app_write_log(
        db,
        scope="coach_reset_user_password",
        actor_user_id=principal.user_id,
        payload={
            "user_id": int(row.id),
            "username": row.username,
            "role": row.role,
            "must_change_password": bool(row.must_change_password),
            "actor_user_id": int(principal.user_id),
        },
    )
    db.flush()
    return CoachResetPasswordResponse(status="ok", user=_coach_user_item(row))


@router.post("/coach/users/{user_id}/archive", response_model=CoachUserStatusResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_archive_user(
    user_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    row = _user_or_404(db, user_id)
    if int(row.id) == int(principal.user_id):
        raise HTTPException(status_code=400, detail={"code": "CANNOT_ARCHIVE_SELF"})
    if str(row.role or "").lower() not in {"coach", "admin"}:
        raise HTTPException(status_code=400, detail={"code": "USER_NOT_COACH_OR_ADMIN", "role": row.role})
    row.status = "inactive"
    db.flush()
    db.refresh(row)
    _append_app_write_log(
        db,
        scope="coach_archive_user",
        actor_user_id=principal.user_id,
        payload={"user_id": int(row.id), "username": row.username, "role": row.role, "status": row.status},
    )
    db.flush()
    return CoachUserStatusResponse(status="ok", user=_coach_user_item(row))


@router.post("/coach/users/{user_id}/reactivate", response_model=CoachUserStatusResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_reactivate_user(
    user_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    row = _user_or_404(db, user_id)
    if str(row.role or "").lower() not in {"coach", "admin"}:
        raise HTTPException(status_code=400, detail={"code": "USER_NOT_COACH_OR_ADMIN", "role": row.role})
    row.status = "active"
    db.flush()
    db.refresh(row)
    _append_app_write_log(
        db,
        scope="coach_reactivate_user",
        actor_user_id=principal.user_id,
        payload={"user_id": int(row.id), "username": row.username, "role": row.role, "status": row.status},
    )
    db.flush()
    return CoachUserStatusResponse(status="ok", user=_coach_user_item(row))


@router.patch("/coach/athletes/{athlete_id}", response_model=AthleteDetailResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_update_athlete(
    athlete_id: int,
    request: Request,
    response: Response,
    payload: CoachUpdateAthleteRequest = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del request, response
    athlete = _athlete_or_404(db, athlete_id)
    updates = payload.model_dump(exclude_unset=True)
    if "email" in updates and updates["email"] is not None:
        normalized_email = str(updates["email"]).strip().lower()
        existing = db.execute(select(Athlete.id).where(Athlete.email == normalized_email, Athlete.id != athlete_id)).scalar_one_or_none()
        if existing is not None:
            raise HTTPException(status_code=409, detail={"code": "ATHLETE_EMAIL_TAKEN", "email": normalized_email})
        athlete.email = normalized_email
    if "first_name" in updates and updates["first_name"] is not None:
        athlete.first_name = str(updates["first_name"]).strip()
    if "last_name" in updates and updates["last_name"] is not None:
        athlete.last_name = str(updates["last_name"]).strip()
    if "status" in updates and updates["status"] is not None:
        athlete.status = str(updates["status"]).strip() or athlete.status
    if "assigned_coach_user_id" in updates:
        athlete.assigned_coach_user_id = _assigned_coach_or_none(db, updates["assigned_coach_user_id"])
    if any(k in updates for k in ("vdot_seed", "derive_paces_from_vdot", "threshold_pace_sec_per_km", "easy_pace_sec_per_km")):
        derive_flag = updates.get("derive_paces_from_vdot")
        if derive_flag is None:
            derive_flag = bool("vdot_seed" in updates and updates.get("vdot_seed") is not None and not any(k in updates for k in ("threshold_pace_sec_per_km", "easy_pace_sec_per_km")))
        _apply_vdot_pace_profile(
            athlete=athlete,
            vdot_seed=updates.get("vdot_seed", athlete.vdot_seed),
            derive_paces_from_vdot=bool(derive_flag),
            threshold_pace_sec_per_km=updates.get("threshold_pace_sec_per_km"),
            easy_pace_sec_per_km=updates.get("easy_pace_sec_per_km"),
        )
    for field in (
        "dob",
        "max_hr",
        "resting_hr",
    ):
        if field in updates:
            setattr(athlete, field, updates[field])

    db.flush()
    db.refresh(athlete)
    _append_app_write_log(
        db,
        scope="coach_update_athlete",
        actor_user_id=principal.user_id,
        payload={
            "athlete_id": int(athlete.id),
            "actor_user_id": int(principal.user_id),
            "fields": sorted(list(updates.keys())),
        },
    )
    db.flush()
    return _athlete_detail_response(db, athlete)


@router.post("/coach/athletes/{athlete_id}/archive", response_model=CoachAthleteLifecycleResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_archive_athlete(
    athlete_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    athlete = _athlete_or_404(db, athlete_id)
    athlete.status = "inactive"
    db.flush()
    db.refresh(athlete)
    _append_app_write_log(db, scope="coach_archive_athlete", actor_user_id=principal.user_id, payload={"athlete_id": athlete_id, "status": "inactive"})
    db.flush()
    return CoachAthleteLifecycleResponse(status="ok", athlete=_athlete_detail_response(db, athlete))


@router.post("/coach/athletes/{athlete_id}/reactivate", response_model=CoachAthleteLifecycleResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_reactivate_athlete(
    athlete_id: int,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("admin")),
):
    del request, response
    athlete = _athlete_or_404(db, athlete_id)
    athlete.status = "active"
    db.flush()
    db.refresh(athlete)
    _append_app_write_log(db, scope="coach_reactivate_athlete", actor_user_id=principal.user_id, payload={"athlete_id": athlete_id, "status": "active"})
    db.flush()
    return CoachAthleteLifecycleResponse(status="ok", athlete=_athlete_detail_response(db, athlete))


@router.get("/athletes/{athlete_id}", response_model=AthleteDetailResponse)
def get_athlete_detail(
    athlete_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    athlete = _athlete_or_404(db, athlete_id)
    return _athlete_detail_response(db, athlete)


@router.get("/athletes/{athlete_id}/events", response_model=AthleteEventListResponse)
def list_athlete_events(
    athlete_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    _athlete_or_404(db, athlete_id)
    total = int(db.execute(select(func.count(Event.id)).where(Event.athlete_id == athlete_id)).scalar_one() or 0)
    rows = db.execute(
        select(Event)
        .where(Event.athlete_id == athlete_id)
        .order_by(Event.event_date.asc(), Event.id.asc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return AthleteEventListResponse(total=total, offset=offset, limit=limit, items=[AthleteEventItem.model_validate(r) for r in rows])


@router.post("/athletes/{athlete_id}/events", response_model=AthleteEventItem)
def create_athlete_event(
    athlete_id: int,
    payload: AthleteEventCreate,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    _athlete_or_404(db, athlete_id)
    row = Event(
        athlete_id=athlete_id,
        name=payload.name.strip(),
        event_date=payload.event_date,
        distance=payload.distance.strip(),
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    return AthleteEventItem.model_validate(row)


@router.patch("/events/{event_id}", response_model=AthleteEventItem)
def update_event(
    event_id: int,
    payload: AthleteEventUpdate,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    row = _event_or_404(db, event_id)
    if principal.role.lower() not in {"coach", "admin"} and int(principal.athlete_id or 0) != int(row.athlete_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ATHLETE_SCOPE", "athlete_id": row.athlete_id, "principal_athlete_id": principal.athlete_id},
        )
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        row.name = str(updates["name"]).strip()
    if "event_date" in updates and updates["event_date"] is not None:
        row.event_date = updates["event_date"]
    if "distance" in updates and updates["distance"] is not None:
        row.distance = str(updates["distance"]).strip()
    db.flush()
    db.refresh(row)
    return AthleteEventItem.model_validate(row)


@router.delete("/events/{event_id}", response_model=SimpleStatusResponse)
def delete_event(
    event_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    row = _event_or_404(db, event_id)
    if principal.role.lower() not in {"coach", "admin"} and int(principal.athlete_id or 0) != int(row.athlete_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ATHLETE_SCOPE", "athlete_id": row.athlete_id, "principal_athlete_id": principal.athlete_id},
        )
    db.delete(row)
    db.flush()
    return SimpleStatusResponse(status="ok")


@router.get("/athletes/{athlete_id}/preferences", response_model=AthletePreferencesResponse)
def get_athlete_preferences(
    athlete_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    _athlete_or_404(db, athlete_id)
    row = _preferences_or_create(db, athlete_id)
    return _preferences_response(row)


@router.patch("/athletes/{athlete_id}/preferences", response_model=AthletePreferencesResponse)
def update_athlete_preferences(
    athlete_id: int,
    payload: AthletePreferencesUpdate,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    _athlete_or_404(db, athlete_id)
    row = _preferences_or_create(db, athlete_id)
    updates = payload.model_dump(exclude_unset=True)
    if "reminder_enabled" in updates:
        row.reminder_enabled = bool(updates["reminder_enabled"])
    if "reminder_training_days" in updates and updates["reminder_training_days"] is not None:
        row.reminder_training_days = _normalize_day_labels(list(updates["reminder_training_days"]))
    if "privacy_ack" in updates:
        row.privacy_ack = bool(updates["privacy_ack"])
    if "automation_mode" in updates and updates["automation_mode"] is not None:
        row.automation_mode = str(updates["automation_mode"])
    if "auto_apply_low_risk" in updates:
        row.auto_apply_low_risk = bool(updates["auto_apply_low_risk"])
    if "auto_apply_confidence_min" in updates and updates["auto_apply_confidence_min"] is not None:
        row.auto_apply_confidence_min = float(updates["auto_apply_confidence_min"])
    if "auto_apply_risk_max" in updates and updates["auto_apply_risk_max"] is not None:
        row.auto_apply_risk_max = float(updates["auto_apply_risk_max"])
    if "preferred_training_days" in updates and updates["preferred_training_days"] is not None:
        row.preferred_training_days = _normalize_day_labels(list(updates["preferred_training_days"]))
    if "preferred_long_run_day" in updates:
        token = str(updates["preferred_long_run_day"] or "").strip()[:3].title()
        row.preferred_long_run_day = token if token in DAY_NAMES else None
    db.flush()
    db.refresh(row)
    return _preferences_response(row)


@router.get("/coach/session-library", response_model=SessionLibraryListResponse)
def list_session_library(
    q: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    intent: Optional[str] = Query(default=None),
    energy_system: Optional[str] = Query(default=None),
    tier: Optional[str] = Query(default=None),
    is_treadmill: Optional[bool] = Query(default=None),
    methodology: Optional[str] = Query(default=None),
    min_duration: Optional[int] = Query(default=None, ge=1),
    max_duration: Optional[int] = Query(default=None, ge=1),
    status_in: Optional[str] = Query(default=None, description="Comma-separated statuses"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    stmt = select(SessionLibrary)
    count_stmt = select(func.count(SessionLibrary.id))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(SessionLibrary.name.ilike(pattern))
        count_stmt = count_stmt.where(SessionLibrary.name.ilike(pattern))
    if category:
        stmt = stmt.where(SessionLibrary.category == category)
        count_stmt = count_stmt.where(SessionLibrary.category == category)
    if intent:
        stmt = stmt.where(SessionLibrary.intent == intent)
        count_stmt = count_stmt.where(SessionLibrary.intent == intent)
    if energy_system:
        stmt = stmt.where(SessionLibrary.energy_system == energy_system)
        count_stmt = count_stmt.where(SessionLibrary.energy_system == energy_system)
    if tier:
        stmt = stmt.where(SessionLibrary.tier == tier)
        count_stmt = count_stmt.where(SessionLibrary.tier == tier)
    if is_treadmill is not None:
        stmt = stmt.where(SessionLibrary.is_treadmill.is_(bool(is_treadmill)))
        count_stmt = count_stmt.where(SessionLibrary.is_treadmill.is_(bool(is_treadmill)))
    if min_duration is not None:
        stmt = stmt.where(SessionLibrary.duration_min >= int(min_duration))
        count_stmt = count_stmt.where(SessionLibrary.duration_min >= int(min_duration))
    if max_duration is not None:
        stmt = stmt.where(SessionLibrary.duration_min <= int(max_duration))
        count_stmt = count_stmt.where(SessionLibrary.duration_min <= int(max_duration))
    if status_in:
        statuses = [token.strip().lower() for token in str(status_in).split(",") if token.strip()]
        if statuses:
            stmt = stmt.where(func.lower(SessionLibrary.status).in_(statuses))
            count_stmt = count_stmt.where(func.lower(SessionLibrary.status).in_(statuses))
    if methodology:
        method_token = str(methodology).strip().lower()
        rows_all = db.execute(stmt.order_by(SessionLibrary.id.desc())).scalars().all()
        filtered_rows = [row for row in rows_all if _session_template_methodology(row) == method_token]
        total = len(filtered_rows)
        rows = filtered_rows[offset : offset + limit]
    else:
        total = int(db.execute(count_stmt).scalar_one() or 0)
        rows = db.execute(stmt.order_by(SessionLibrary.id.desc()).offset(offset).limit(limit)).scalars().all()
    return SessionLibraryListResponse(
        total=total,
        offset=offset,
        limit=limit,
        items=[_session_library_list_item(row) for row in rows],
    )


@router.post("/coach/session-library/gold-standard-pack", response_model=SessionLibraryGoldStandardPackResponse)
def upsert_gold_standard_session_pack_endpoint(
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    from db.seed import upsert_gold_standard_session_pack

    result = upsert_gold_standard_session_pack(_session=db)
    _append_app_write_log(
        db,
        scope="session_library_gold_standard_pack_upsert",
        actor_user_id=int(principal.user_id),
        payload=dict(result),
    )
    return SessionLibraryGoldStandardPackResponse(
        status="ok",
        message="Gold-standard JD/VDOT session template pack installed/refreshed",
        created_count=int(result.get("created", 0)),
        updated_count=int(result.get("updated", 0)),
        template_count=int(result.get("template_count", 0)),
    )


@router.post(
    "/coach/session-library/governance/bulk-deprecate-legacy",
    response_model=SessionLibraryBulkLegacyDeprecationResponse,
)
def bulk_deprecate_legacy_session_templates(
    payload: SessionLibraryBulkLegacyDeprecationRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    rows = db.execute(select(SessionLibrary).order_by(SessionLibrary.id.asc())).scalars().all()
    candidates = [
        row
        for row in rows
        if _legacy_session_candidate(
            row,
            include_non_daniels_active=bool(payload.include_non_daniels_active),
        )
    ]
    sample_limit = int(payload.sample_limit or 10)
    changed_count = 0
    if not bool(payload.dry_run):
        for row in candidates:
            if str(row.status or "active").strip().lower() != "deprecated":
                row.status = "deprecated"
                changed_count += 1
        if changed_count:
            db.flush()
    _append_app_write_log(
        db,
        scope="session_library_bulk_deprecate_legacy",
        actor_user_id=int(principal.user_id),
        payload={
            "dry_run": bool(payload.dry_run),
            "include_non_daniels_active": bool(payload.include_non_daniels_active),
            "template_count_scanned": len(rows),
            "candidate_count": len(candidates),
            "changed_count": changed_count,
            "sample_ids": [int(row.id) for row in candidates[:sample_limit]],
        },
    )
    return SessionLibraryBulkLegacyDeprecationResponse(
        status="ok",
        action="bulk_deprecate_legacy",
        message=(
            "Legacy template deprecation preview generated"
            if bool(payload.dry_run)
            else "Legacy templates deprecated (soft deprecation, reversible via governance actions)"
        ),
        dry_run=bool(payload.dry_run),
        template_count_scanned=len(rows),
        candidate_count=len(candidates),
        changed_count=changed_count,
        unchanged_count=max(0, len(candidates) - changed_count),
        sample_limit=sample_limit,
        samples=[SessionLibraryListItem.model_validate(row) for row in candidates[:sample_limit]],
    )


@router.post(
    "/coach/session-library/governance/bulk-canonicalize-duplicates",
    response_model=SessionLibraryBulkCanonicalizationResponse,
)
def bulk_canonicalize_duplicate_session_templates(
    payload: SessionLibraryBulkCanonicalizationRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    rows = db.execute(select(SessionLibrary).order_by(SessionLibrary.id.asc())).scalars().all()
    row_by_id = {int(r.id): r for r in rows}
    audit = _session_library_duplicate_audit(
        rows,
        limit=int(payload.candidate_limit or 200),
        min_similarity=float(payload.min_similarity or 0.9),
    )
    candidates = list(audit.candidates or [])
    if bool(payload.exact_only):
        candidates = [c for c in candidates if str(c.kind or "") == "exact"]

    applied: list[SessionLibraryBulkCanonicalizationDecision] = []
    skipped: list[SessionLibraryBulkCanonicalizationSkippedItem] = []
    touched: set[int] = set()

    for candidate in candidates:
        left_row = row_by_id.get(int(candidate.left.id))
        right_row = row_by_id.get(int(candidate.right.id))
        if left_row is None or right_row is None:
            skipped.append(
                SessionLibraryBulkCanonicalizationSkippedItem(
                    candidate_kind=candidate.kind,
                    score=float(candidate.score),
                    reason_tags=list(candidate.reason_tags or []),
                    reason_code="MISSING_TEMPLATE",
                    message="Candidate references missing template row",
                    left=candidate.left,
                    right=candidate.right,
                )
            )
            continue
        if int(left_row.id) in touched or int(right_row.id) in touched:
            skipped.append(
                SessionLibraryBulkCanonicalizationSkippedItem(
                    candidate_kind=candidate.kind,
                    score=float(candidate.score),
                    reason_tags=list(candidate.reason_tags or []),
                    reason_code="ALREADY_TOUCHED_THIS_BATCH",
                    message="One or both templates were already modified by a prior candidate in this batch",
                    left=SessionLibraryListItem.model_validate(left_row),
                    right=SessionLibraryListItem.model_validate(right_row),
                )
            )
            continue

        left_method = _session_template_methodology(left_row)
        right_method = _session_template_methodology(right_row)
        if left_method == "daniels_vdot" and right_method == "daniels_vdot" and str(candidate.kind or "") == "near":
            skipped.append(
                SessionLibraryBulkCanonicalizationSkippedItem(
                    candidate_kind=candidate.kind,
                    score=float(candidate.score),
                    reason_tags=list(candidate.reason_tags or []),
                    reason_code="JD_VARIANT_MANUAL_REVIEW",
                    message="Near-match Daniels templates require manual review to avoid collapsing valid progression variants",
                    left=SessionLibraryListItem.model_validate(left_row),
                    right=SessionLibraryListItem.model_validate(right_row),
                )
            )
            continue

        target_row, dup_row, decision_reason = _canonicalization_target_and_duplicate(left_row, right_row)
        if target_row is None or dup_row is None:
            skipped.append(
                SessionLibraryBulkCanonicalizationSkippedItem(
                    candidate_kind=candidate.kind,
                    score=float(candidate.score),
                    reason_tags=list(candidate.reason_tags or []),
                    reason_code=str(decision_reason).upper(),
                    message="Both templates are canonical; resolve manually",
                    left=SessionLibraryListItem.model_validate(left_row),
                    right=SessionLibraryListItem.model_validate(right_row),
                )
            )
            continue

        already_linked = (
            str(dup_row.status or "").strip().lower() == "duplicate"
            and int(dup_row.duplicate_of_template_id or 0) == int(target_row.id)
        )
        if already_linked:
            skipped.append(
                SessionLibraryBulkCanonicalizationSkippedItem(
                    candidate_kind=candidate.kind,
                    score=float(candidate.score),
                    reason_tags=list(candidate.reason_tags or []),
                    reason_code="ALREADY_DUPLICATE_OF_TARGET",
                    message=f"Template #{int(dup_row.id)} is already marked duplicate of #{int(target_row.id)}",
                    left=SessionLibraryListItem.model_validate(left_row),
                    right=SessionLibraryListItem.model_validate(right_row),
                )
            )
            continue

        if not bool(payload.dry_run):
            dup_row.status = "duplicate"
            dup_row.duplicate_of_template_id = int(target_row.id)
            db.flush()
        touched.add(int(target_row.id))
        touched.add(int(dup_row.id))
        applied.append(
            SessionLibraryBulkCanonicalizationDecision(
                candidate_kind=candidate.kind,
                score=float(candidate.score),
                reason_tags=list(candidate.reason_tags or []),
                action="mark_duplicate",
                decision_reason=decision_reason,
                target=SessionLibraryListItem.model_validate(target_row),
                duplicate=SessionLibraryListItem.model_validate(dup_row),
            )
        )

    sample_limit = int(payload.sample_limit or 10)
    if applied or skipped:
        _append_app_write_log(
            db,
            scope="session_library_bulk_canonicalize_duplicates",
            actor_user_id=int(principal.user_id),
            payload={
                "dry_run": bool(payload.dry_run),
                "candidate_count": len(candidates),
                "reviewed_count": len(applied) + len(skipped),
                "applied_count": len(applied),
                "skipped_count": len(skipped),
                "exact_only": bool(payload.exact_only),
                "min_similarity": float(payload.min_similarity),
                "candidate_limit": int(payload.candidate_limit),
                "sample_applied": [
                    {
                        "target_id": int(item.target.id),
                        "duplicate_id": int(item.duplicate.id),
                        "decision_reason": item.decision_reason,
                    }
                    for item in applied[:sample_limit]
                ],
            },
        )
    return SessionLibraryBulkCanonicalizationResponse(
        status="ok",
        action="bulk_canonicalize_duplicates",
        message=(
            "Duplicate canonicalization preview generated"
            if bool(payload.dry_run)
            else "Duplicate canonicalization applied (templates marked duplicate of preferred canonical targets)"
        ),
        dry_run=bool(payload.dry_run),
        candidate_count=len(candidates),
        reviewed_count=len(applied) + len(skipped),
        applied_count=len(applied),
        skipped_count=len(skipped),
        sample_limit=sample_limit,
        applied=applied[:sample_limit],
        skipped=skipped[:sample_limit],
    )


@router.get(
    "/coach/session-library/governance/report",
    response_model=SessionLibraryGovernanceReportResponse,
)
def session_library_governance_report(
    recent_limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    return _session_library_governance_report_payload(db, recent_limit=recent_limit)


@router.get("/coach/session-library/audit/duplicates", response_model=SessionLibraryDuplicateAuditResponse)
def audit_session_library_duplicates(
    limit: int = Query(default=50, ge=1, le=200),
    min_similarity: float = Query(default=0.78, ge=0.5, le=1.0),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    rows = db.execute(select(SessionLibrary).order_by(SessionLibrary.id.asc())).scalars().all()
    return _session_library_duplicate_audit(rows, limit=limit, min_similarity=min_similarity)


@router.get("/coach/session-library/audit/metadata", response_model=SessionLibraryMetadataAuditResponse)
def audit_session_library_metadata(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    rows = db.execute(select(SessionLibrary).order_by(SessionLibrary.id.asc())).scalars().all()
    return _session_library_metadata_audit(rows, limit=limit)


@router.post("/coach/session-library/{session_id}/normalize-metadata", response_model=SessionLibraryNormalizeMetadataResponse)
def normalize_session_template_metadata(
    session_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    row = _session_library_or_404(db, session_id)
    changes, before_counts, after_counts = _normalize_session_library_metadata(row)
    if changes:
        db.flush()
        db.refresh(row)
    _append_app_write_log(
        db,
        scope="session_library_normalize_metadata",
        actor_user_id=int(principal.user_id),
        payload={
            "session_id": int(row.id),
            "applied_change_count": len(changes),
            "applied_changes": [c.model_dump() for c in changes],
            "issue_counts_before": before_counts,
            "issue_counts_after": after_counts,
        },
    )
    return SessionLibraryNormalizeMetadataResponse(
        status="ok",
        message=("Applied metadata/JD normalization changes" if changes else "No normalization changes were needed"),
        template=SessionLibraryDetailResponse.model_validate(row),
        applied_change_count=len(changes),
        applied_changes=changes,
        issue_counts_before=before_counts,
        issue_counts_after=after_counts,
    )


@router.post("/coach/session-library/{session_id}/governance-action", response_model=SessionLibraryGovernanceActionResponse)
def session_library_governance_action(
    session_id: int,
    payload: SessionLibraryGovernanceActionRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    row = _session_library_or_404(db, session_id)
    action = str(payload.action or "").strip().lower()
    valid_actions = {"mark_canonical", "mark_duplicate", "deprecate", "reactivate"}
    if action not in valid_actions:
        raise HTTPException(
            status_code=400,
            detail={"code": "SESSION_GOVERNANCE_ACTION_INVALID", "action": action, "allowed": sorted(valid_actions)},
        )

    before = {
        "status": str(row.status or ""),
        "duplicate_of_template_id": (int(row.duplicate_of_template_id) if row.duplicate_of_template_id is not None else None),
    }
    message = ""

    if action == "mark_duplicate":
        target_id = int(payload.duplicate_of_template_id or 0)
        if target_id <= 0:
            raise HTTPException(
                status_code=400,
                detail={"code": "DUPLICATE_TARGET_REQUIRED", "session_id": int(row.id)},
            )
        if target_id == int(row.id):
            raise HTTPException(status_code=400, detail={"code": "DUPLICATE_TARGET_SELF"})
        target = _session_library_or_404(db, target_id)
        if int(target.id) == int(row.id):
            raise HTTPException(status_code=400, detail={"code": "DUPLICATE_TARGET_SELF"})
        row.status = "duplicate"
        row.duplicate_of_template_id = int(target.id)
        message = f"Template marked as duplicate of #{int(target.id)}"
    elif action == "mark_canonical":
        row.status = "canonical"
        row.duplicate_of_template_id = None
        message = "Template marked as canonical"
    elif action == "deprecate":
        row.status = "deprecated"
        message = "Template deprecated"
    elif action == "reactivate":
        row.status = "active"
        row.duplicate_of_template_id = None
        message = "Template reactivated"

    db.flush()
    db.refresh(row)

    _append_app_write_log(
        db,
        scope="session_library_governance_action",
        actor_user_id=int(principal.user_id),
        payload={
            "session_id": int(row.id),
            "action": action,
            "note": str(payload.note or ""),
            "before": before,
            "after": {
                "status": str(row.status or ""),
                "duplicate_of_template_id": (int(row.duplicate_of_template_id) if row.duplicate_of_template_id is not None else None),
            },
        },
    )

    return SessionLibraryGovernanceActionResponse(
        status="ok",
        action=action,
        message=message,
        template=SessionLibraryDetailResponse.model_validate(row),
    )


@router.post("/coach/session-library/validate", response_model=SessionLibraryValidateResponse)
def validate_session_template(
    payload: SessionLibraryUpsert,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del db, principal
    errors = validate_session_payload(payload.model_dump())
    return SessionLibraryValidateResponse(valid=(len(errors) == 0), errors=errors)


@router.post("/coach/session-library", response_model=SessionLibraryDetailResponse)
def create_session_template(
    payload: SessionLibraryUpsert,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    data = payload.model_dump()
    errors = validate_session_payload(data)
    if errors:
        raise HTTPException(status_code=400, detail={"code": "SESSION_TEMPLATE_INVALID", "errors": errors})
    row = SessionLibrary(**data)
    db.add(row)
    db.flush()
    db.refresh(row)
    return SessionLibraryDetailResponse.model_validate(row)


@router.get("/coach/session-library/{session_id}", response_model=SessionLibraryDetailResponse)
def get_session_template(
    session_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    row = _session_library_or_404(db, session_id)
    return SessionLibraryDetailResponse.model_validate(row)


@router.patch("/coach/session-library/{session_id}", response_model=SessionLibraryDetailResponse)
def update_session_template(
    session_id: int,
    payload: SessionLibraryPatch,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    row = _session_library_or_404(db, session_id)
    updates = payload.model_dump(exclude_unset=True)
    merged = _session_library_payload_from_model(row)
    merged.update({k: v for k, v in updates.items() if v is not None})
    errors = validate_session_payload(merged)
    if errors:
        raise HTTPException(status_code=400, detail={"code": "SESSION_TEMPLATE_INVALID", "errors": errors})
    for key, value in merged.items():
        setattr(row, key, value)
    db.flush()
    db.refresh(row)
    return SessionLibraryDetailResponse.model_validate(row)


@router.delete("/coach/session-library/{session_id}", response_model=SimpleStatusResponse)
def delete_session_template(
    session_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    row = _session_library_or_404(db, session_id)
    db.delete(row)
    db.flush()
    return SimpleStatusResponse(status="ok")


@router.post("/coach/plans/preview", response_model=PlanPreviewResponse)
def preview_plan(
    payload: PlanPreviewRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    _athlete_or_404(db, int(payload.athlete_id))
    return _plan_preview_from_request(payload, db=db)


@router.post("/coach/plans", response_model=CoachPlanSummary)
def create_plan(
    payload: PlanCreateRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    athlete = _athlete_or_404(db, int(payload.athlete_id))
    preview = _plan_preview_from_request(payload, db=db)
    plan = Plan(
        athlete_id=int(payload.athlete_id),
        name=(
            str(payload.plan_name).strip()
            if getattr(payload, "plan_name", None) is not None and str(payload.plan_name).strip()
            else _default_plan_name(athlete=athlete, race_goal=str(payload.race_goal), start_date=payload.start_date)
        ),
        race_goal=str(payload.race_goal),
        weeks=int(payload.weeks),
        sessions_per_week=int(payload.sessions_per_week),
        max_session_min=int(payload.max_session_min),
        start_date=payload.start_date,
        locked_until_week=0,
        status="active",
    )
    db.add(plan)
    db.flush()
    planned_dates = [a.session_day for wk in preview.weeks_detail for a in wk.assignments]
    if planned_dates:
        conflicts = db.execute(
            select(PlanDaySession.session_day)
            .where(
                PlanDaySession.athlete_id == int(plan.athlete_id),
                PlanDaySession.session_day.in_(planned_dates),
            )
            .order_by(PlanDaySession.session_day.asc())
        ).scalars().all()
        if conflicts:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "PLAN_DAY_CONFLICT",
                    "athlete_id": int(plan.athlete_id),
                    "conflict_days": [d.isoformat() for d in conflicts],
                },
            )
    assignment_template_names = {
        str(a.session_name).strip()
        for week in preview.weeks_detail
        for a in week.assignments
        if str(a.session_name or "").strip()
    }
    template_rows = (
        db.execute(select(SessionLibrary).where(SessionLibrary.name.in_(sorted(assignment_template_names)))).scalars().all()
        if assignment_template_names
        else []
    )
    templates_by_name = {str(t.name): t for t in template_rows}
    athlete_vdot = _estimate_current_vdot_for_athlete(db, int(athlete.id))

    for week in preview.weeks_detail:
        wk = PlanWeek(
            plan_id=int(plan.id),
            week_number=int(week.week_number),
            phase=str(week.phase),
            week_start=week.week_start,
            week_end=week.week_end,
            sessions_order=list(week.sessions_order),
            target_load=float(week.target_load),
            locked=False,
        )
        db.add(wk)
        db.flush()
        for assignment in week.assignments:
            template = templates_by_name.get(str(assignment.session_name))
            row = PlanDaySession(
                plan_week_id=int(wk.id),
                athlete_id=int(plan.athlete_id),
                session_day=assignment.session_day,
                session_name=str(assignment.session_name),
                source_template_id=(int(template.id) if template is not None else None),
                source_template_name=(str(template.name) if template is not None else str(assignment.session_name)),
                status="planned",
            )
            _compile_plan_day_session_snapshot(
                db=db,
                row=row,
                athlete=athlete,
                vdot=athlete_vdot,
                template=template,
            )
            compile_ctx = dict(getattr(row, "compile_context_json", None) or {})
            compile_ctx["planning"] = {
                "strategy_version": PLANNER_SELECTION_STRATEGY_VERSION,
                "planning_token": (str(assignment.planning_token) if assignment.planning_token else None),
                "template_selection_reason": (
                    str(assignment.template_selection_reason) if assignment.template_selection_reason else None
                ),
                "template_selection_rationale": [str(x) for x in list(assignment.template_selection_rationale or [])],
                "phase": str(week.phase),
                "race_goal": str(plan.race_goal),
            }
            row.compile_context_json = compile_ctx
            db.add(row)
    db.flush()
    _recalculate_plan_metrics_for_plan(db, int(plan.id))
    db.flush()
    db.refresh(plan)
    return _plan_summary(plan)


@router.get("/coach/athletes/{athlete_id}/plans", response_model=CoachPlanListResponse)
def list_athlete_plans(
    athlete_id: int,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    _athlete_or_404(db, athlete_id)
    total = int(db.execute(select(func.count(Plan.id)).where(Plan.athlete_id == athlete_id)).scalar_one() or 0)
    rows = db.execute(
        select(Plan)
        .where(Plan.athlete_id == athlete_id)
        .order_by(Plan.start_date.desc(), Plan.id.desc())
        .offset(offset)
        .limit(limit)
    ).scalars().all()
    return CoachPlanListResponse(total=total, offset=offset, limit=limit, items=[_plan_summary(r) for r in rows])


@router.get("/coach/plans/{plan_id}", response_model=CoachPlanDetailResponse)
def get_plan_detail(
    plan_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    plan = _plan_or_404(db, plan_id)
    return _plan_detail(db, plan)


@router.patch("/coach/plans/{plan_id}", response_model=CoachPlanSummary)
def update_plan(
    plan_id: int,
    payload: CoachPlanUpdateRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    plan = _plan_or_404(db, plan_id)
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and updates["name"] is not None:
        next_name = str(updates["name"]).strip()
        if not next_name:
            raise HTTPException(status_code=400, detail={"code": "PLAN_NAME_REQUIRED"})
        plan.name = next_name[:200]
    if "status" in updates and updates["status"] is not None:
        plan.status = str(updates["status"])
    if "locked_until_week" in updates and updates["locked_until_week"] is not None:
        plan.locked_until_week = int(updates["locked_until_week"])
    db.flush()
    db.refresh(plan)
    return _plan_summary(plan)


@router.patch("/coach/plan-day-sessions/{session_id}", response_model=CoachPlanDaySessionItem)
def update_plan_day_session(
    session_id: int,
    payload: CoachPlanDaySessionPatch,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    row = db.execute(select(PlanDaySession).where(PlanDaySession.id == session_id)).scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail={"code": "PLAN_DAY_SESSION_NOT_FOUND", "session_id": session_id})
    week = db.execute(select(PlanWeek).where(PlanWeek.id == row.plan_week_id)).scalar_one_or_none()
    if week is not None and bool(week.locked):
        raise HTTPException(status_code=409, detail={"code": "PLAN_WEEK_LOCKED", "week_id": int(week.id)})
    athlete = _athlete_or_404(db, int(row.athlete_id))
    updates = payload.model_dump(exclude_unset=True)
    prior_compile_ctx = dict(getattr(row, "compile_context_json", None) or {})
    prior_planning_ctx = prior_compile_ctx.get("planning") if isinstance(prior_compile_ctx.get("planning"), dict) else None
    explicit_template: Optional[SessionLibrary] = None
    if "source_template_id" in updates and updates["source_template_id"] is not None:
        explicit_template = _session_library_or_404(db, int(updates["source_template_id"]))
        row.source_template_id = int(explicit_template.id)
        row.source_template_name = str(explicit_template.name or row.source_template_name or "")
    if "session_day" in updates and updates["session_day"] is not None:
        row.session_day = updates["session_day"]
    if "session_name" in updates and updates["session_name"] is not None:
        row.session_name = str(updates["session_name"])
    if "source_template_name" in updates and updates["source_template_name"] is not None:
        row.source_template_name = str(updates["source_template_name"])
        if explicit_template is None:
            explicit_template = db.execute(
                select(SessionLibrary).where(SessionLibrary.name == row.source_template_name)
            ).scalar_one_or_none()
            row.source_template_id = int(explicit_template.id) if explicit_template is not None else None
    if "status" in updates and updates["status"] is not None:
        row.status = str(updates["status"])
    athlete_vdot = _estimate_current_vdot_for_athlete(db, int(athlete.id))
    _compile_plan_day_session_snapshot(db=db, row=row, athlete=athlete, vdot=athlete_vdot, template=explicit_template)
    compile_ctx = dict(getattr(row, "compile_context_json", None) or {})
    if any(k in updates for k in ("session_name", "source_template_id", "source_template_name")):
        compile_ctx["planning"] = {
            "strategy_version": "manual_edit_v1",
            "planning_token": (str(row.session_name or "") or None),
            "template_selection_reason": "manual_edit",
            "template_selection_rationale": ["coach manually edited plan-day session template or name"],
            "phase": (str(week.phase) if week is not None and getattr(week, "phase", None) else None),
            "race_goal": (str(_plan_or_404(db, int(week.plan_id)).race_goal) if week is not None else None),
        }
    elif prior_planning_ctx is not None:
        compile_ctx["planning"] = prior_planning_ctx
    row.compile_context_json = compile_ctx
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"code": "PLAN_DAY_CONFLICT"}) from exc
    _recalculate_plan_week_metrics(db, int(row.plan_week_id))
    db.flush()
    db.refresh(row)
    return _coach_plan_day_session_item(row)


@router.post("/coach/plans/{plan_id}/weeks/{week_number}/regenerate", response_model=CoachPlanDetailResponse)
def regenerate_plan_week(
    plan_id: int,
    week_number: int,
    payload: PlanWeekRegenerateRequest,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    plan = _plan_or_404(db, plan_id)
    week = _plan_week_or_404(db, plan_id, week_number)
    athlete = _athlete_or_404(db, int(plan.athlete_id))
    if bool(week.locked):
        raise HTTPException(status_code=409, detail={"code": "PLAN_WEEK_LOCKED", "week_number": week_number})

    rows = db.execute(
        select(PlanDaySession)
        .where(PlanDaySession.plan_week_id == week.id)
        .order_by(PlanDaySession.session_day.asc(), PlanDaySession.id.asc())
    ).scalars().all()
    session_names = list(week.sessions_order or [r.session_name for r in rows])
    generated_weeks = generate_plan_weeks(
        plan.start_date,
        int(plan.weeks),
        str(plan.race_goal),
        sessions_per_week=int(plan.sessions_per_week or 4),
        max_session_min=int(plan.max_session_min or 120),
    )
    generated_week = next((w for w in generated_weeks if int(w.get("week_number") or 0) == int(week_number)), None)
    long_run_minutes = int((generated_week or {}).get("long_run_minutes") or 0)
    assignments = assign_week_sessions(
        week.week_start,
        session_names,
        preferred_days=_normalize_day_labels(list(payload.preferred_days or [])) or None,
        preferred_long_run_day=(
            str(payload.preferred_long_run_day).strip()[:3].title() if payload.preferred_long_run_day else None
        ),
    )
    canonical_rows = _canonical_session_templates(db)
    selected_session_names: List[str] = []
    assignment_planning_meta: List[Dict[str, Any]] = []
    for idx, assignment in enumerate(assignments):
        token = str(session_names[idx]) if idx < len(session_names) else str(assignment["session_name"])
        selected_template, selection_reason = _pick_canonical_template_for_planning_token(
            db=db,
            canonical_rows=canonical_rows,
            planning_token=token,
            phase=str(week.phase),
            race_goal=str(plan.race_goal),
            week_number=int(week_number),
            total_weeks=int(plan.weeks),
            long_run_minutes=long_run_minutes,
        )
        selected_name = str(selected_template.name) if selected_template is not None else str(assignment["session_name"])
        assignment["session_name"] = selected_name
        selected_session_names.append(selected_name)
        assignment_planning_meta.append(
            {
                "planning_token": token,
                "template_selection_reason": selection_reason,
                "template_selection_rationale": _template_selection_rationale(
                    planning_token=token,
                    selection_reason=selection_reason,
                    phase=str(week.phase),
                    race_goal=str(plan.race_goal),
                    week_number=int(week_number),
                    total_weeks=int(plan.weeks),
                    long_run_minutes=int(long_run_minutes or 0),
                    selected_template=selected_template,
                ),
            }
        )
    week.sessions_order = selected_session_names

    completed_rows = [r for r in rows if r.status == "completed"] if payload.preserve_completed else []
    completed_days = {r.session_day for r in completed_rows}
    assignment_pool = [
        {
            **a,
            "_planning_meta": assignment_planning_meta[idx] if idx < len(assignment_planning_meta) else None,
        }
        for idx, a in enumerate(assignments)
        if a["session_day"] not in completed_days
    ]
    assignment_pool = sorted(assignment_pool, key=lambda a: (a["session_day"], str(a.get("session_name") or "")))
    if len(assignment_pool) < max(0, len(rows) - len(completed_rows)):
        week_days = [week.week_start + timedelta(days=i) for i in range(7)]
        remaining_days = [d for d in week_days if d not in completed_days]
        assignment_pool = []
        for idx, name in enumerate([r.session_name for r in rows if r not in completed_rows]):
            assignment_pool.append(
                {
                    "session_day": remaining_days[idx % len(remaining_days)],
                    "session_name": name,
                    "_planning_meta": {
                        "planning_token": name,
                        "template_selection_reason": "regenerate_fallback_day_reassignment",
                        "template_selection_rationale": [
                            "week day reassignment fallback preserved session name due limited assignment slots"
                        ],
                    },
                },
            )
        assignment_pool = sorted(assignment_pool, key=lambda a: (a["session_day"], str(a.get("session_name") or "")))

    non_completed_rows = [r for r in rows if r not in completed_rows]
    athlete_vdot = _estimate_current_vdot_for_athlete(db, int(athlete.id))
    for row, assignment in zip(non_completed_rows, assignment_pool):
        row.session_day = assignment["session_day"]
        row.session_name = str(assignment["session_name"])
        row.source_template_name = str(assignment["session_name"])
        row.source_template_id = None
        template = _resolve_session_template_for_plan_day(db, row)
        _compile_plan_day_session_snapshot(db=db, row=row, athlete=athlete, vdot=athlete_vdot, template=template)
        compile_ctx = dict(getattr(row, "compile_context_json", None) or {})
        planning_meta = assignment.get("_planning_meta") if isinstance(assignment.get("_planning_meta"), dict) else {}
        compile_ctx["planning"] = {
            "strategy_version": PLANNER_SELECTION_STRATEGY_VERSION,
            "planning_token": (str(planning_meta.get("planning_token")) if planning_meta.get("planning_token") else None),
            "template_selection_reason": (
                str(planning_meta.get("template_selection_reason"))
                if planning_meta.get("template_selection_reason")
                else None
            ),
            "template_selection_rationale": [str(x) for x in list(planning_meta.get("template_selection_rationale") or [])],
            "phase": str(week.phase),
            "race_goal": str(plan.race_goal),
        }
        row.compile_context_json = compile_ctx
    try:
        db.flush()
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail={"code": "PLAN_DAY_CONFLICT"}) from exc
    _recalculate_plan_week_metrics(db, int(week.id))
    db.flush()
    return _plan_detail(db, plan)


@router.post("/coach/plans/{plan_id}/weeks/{week_number}/lock", response_model=PlanWeekLockResponse)
def lock_plan_week(
    plan_id: int,
    week_number: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    plan = _plan_or_404(db, plan_id)
    week = _plan_week_or_404(db, plan_id, week_number)
    week.locked = True
    plan.locked_until_week = max(int(plan.locked_until_week or 0), int(week_number))
    db.flush()
    return PlanWeekLockResponse(status="ok", plan_id=int(plan.id), week_number=int(week_number), locked=True)


@router.post("/coach/plans/{plan_id}/weeks/{week_number}/unlock", response_model=PlanWeekLockResponse)
def unlock_plan_week(
    plan_id: int,
    week_number: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    plan = _plan_or_404(db, plan_id)
    week = _plan_week_or_404(db, plan_id, week_number)
    week.locked = False
    locked_weeks = db.execute(select(PlanWeek.week_number).where(PlanWeek.plan_id == plan_id, PlanWeek.locked.is_(True))).scalars().all()
    plan.locked_until_week = max([int(w) for w in locked_weeks], default=0)
    db.flush()
    return PlanWeekLockResponse(status="ok", plan_id=int(plan.id), week_number=int(week_number), locked=False)


@router.get("/coach/interventions", response_model=InterventionListResponse)
def list_coach_interventions(
    status: Optional[str] = Query(default=None),
    review_state: Optional[str] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    requested_status = str(status or "").strip().lower() or None
    requested_review_state = str(review_state or "").strip().lower() or None
    if requested_review_state and requested_review_state not in {"needs_review", "auto_eligible"}:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_REVIEW_STATE_FILTER",
                "review_state": review_state,
                "allowed": ["needs_review", "auto_eligible"],
            },
        )

    if requested_review_state is not None and requested_status not in {None, "open"}:
        return InterventionListResponse(total=0, offset=offset, limit=limit, items=[])

    base_stmt = (
        select(CoachIntervention, Athlete.first_name, Athlete.last_name)
        .join(Athlete, Athlete.id == CoachIntervention.athlete_id)
    )

    if requested_review_state is not None:
        rows = db.execute(
            base_stmt.where(CoachIntervention.status == "open")
            .order_by(CoachIntervention.created_at.desc(), CoachIntervention.id.desc())
        ).all()
        open_rows = [intervention for intervention, _, _ in rows]
        eval_map = _auto_apply_eval_map(db, open_rows, coach_user_id=principal.user_id)
        filtered = []
        for intervention, first_name, last_name in rows:
            item_eval = eval_map.get(int(intervention.id)) or {}
            is_eligible = bool(item_eval.get("eligible"))
            if requested_review_state == "auto_eligible" and not is_eligible:
                continue
            if requested_review_state == "needs_review" and is_eligible:
                continue
            filtered.append((intervention, first_name, last_name))
        total = len(filtered)
        rows_page = filtered[offset : offset + limit]
    else:
        stmt = base_stmt
        count_stmt = select(func.count(CoachIntervention.id))
        if requested_status:
            stmt = stmt.where(CoachIntervention.status == requested_status)
            count_stmt = count_stmt.where(CoachIntervention.status == requested_status)
        total = int(db.execute(count_stmt).scalar_one() or 0)
        rows_page = db.execute(
            stmt.order_by(CoachIntervention.created_at.desc(), CoachIntervention.id.desc()).offset(offset).limit(limit)
        ).all()
        open_rows = [intervention for intervention, _, _ in rows_page if str(intervention.status or "").lower() == "open"]
        eval_map = _auto_apply_eval_map(db, open_rows, coach_user_id=principal.user_id) if open_rows else {}

    interventions_in_page = [intervention for intervention, _, _ in rows_page]
    revert_map = _intervention_revert_state_map(db, interventions_in_page) if interventions_in_page else {}
    items = [
        _intervention_list_item(
            intervention,
            athlete_name=f"{first_name} {last_name}",
            auto_apply_eval=eval_map.get(int(intervention.id)),
            auto_revert_state=revert_map.get(int(intervention.id)),
        )
        for intervention, first_name, last_name in rows_page
    ]
    return InterventionListResponse(total=total, offset=offset, limit=limit, items=items)


@router.get("/coach/audit-logs", response_model=CoachAuditLogResponse)
def list_coach_audit_logs(
    scope: Optional[str] = Query(default=None),
    actor_user_id: Optional[int] = Query(default=None),
    intervention_id: Optional[int] = Query(default=None),
    created_from: Optional[date] = Query(default=None),
    created_to: Optional[date] = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    stmt = (
        select(AppWriteLog, User.username)
        .outerjoin(User, User.id == AppWriteLog.actor_user_id)
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
    )
    if scope:
        stmt = stmt.where(AppWriteLog.scope == scope)
    if actor_user_id is not None:
        stmt = stmt.where(AppWriteLog.actor_user_id == actor_user_id)
    if created_from is not None:
        stmt = stmt.where(AppWriteLog.created_at >= datetime.combine(created_from, datetime.min.time()))
    if created_to is not None:
        stmt = stmt.where(AppWriteLog.created_at < datetime.combine(created_to + timedelta(days=1), datetime.min.time()))

    rows = db.execute(stmt).all()
    filtered = []
    for log_row, actor_username in rows:
        payload = dict(log_row.payload or {})
        if intervention_id is not None:
            payload_intervention_id = payload.get("intervention_id")
            try:
                if int(payload_intervention_id) != int(intervention_id):
                    continue
            except Exception:
                continue
        filtered.append((log_row, actor_username))

    total = len(filtered)
    page = filtered[offset : offset + limit]
    items = [_audit_log_list_item(log_row, actor_username=actor_username) for log_row, actor_username in page]
    return CoachAuditLogResponse(total=total, offset=offset, limit=limit, items=items)


@router.get("/coach/automation-policy", response_model=CoachAutomationPolicyResponse)
def get_coach_automation_policy(
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    return _load_coach_automation_policy(db, principal.user_id)


@router.patch("/coach/automation-policy", response_model=CoachAutomationPolicyResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def update_coach_automation_policy(
    request: Request,
    response: Response,
    payload: CoachAutomationPolicyUpdate = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del request, response
    current = _load_coach_automation_policy(db, principal.user_id)
    updates = payload.model_dump(exclude_unset=True)
    next_payload = current.model_dump(
        include={
            "enabled",
            "default_auto_apply_low_risk",
            "default_auto_apply_confidence_min",
            "default_auto_apply_risk_max",
            "apply_when_athlete_pref_missing",
            "apply_when_athlete_pref_disabled",
        }
    )
    next_payload.update(updates)
    _append_app_write_log(
        db,
        scope="coach_automation_policy",
        actor_user_id=principal.user_id,
        payload=next_payload,
    )
    db.flush()
    return _load_coach_automation_policy(db, principal.user_id)


@router.get("/coach/command-center", response_model=CoachCommandCenterResponse)
def get_coach_command_center(
    queue_limit: int = Query(default=8, ge=1, le=50),
    recent_decisions_limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    now = datetime.utcnow()
    ranking_version = "heuristic_v1"

    portfolio = _coach_portfolio_analytics_payload(db)

    intervention_rows = db.execute(
        select(CoachIntervention, Athlete.first_name, Athlete.last_name)
        .join(Athlete, Athlete.id == CoachIntervention.athlete_id)
        .where(CoachIntervention.status == "open")
        .order_by(CoachIntervention.created_at.desc(), CoachIntervention.id.desc())
        .limit(200)
    ).all()
    ranked = [
        _scored_intervention_list_item(
            row,
            athlete_name=f"{first_name} {last_name}",
            now=now,
            ranking_version=ranking_version,
        )
        for row, first_name, last_name in intervention_rows
    ]
    ranked.sort(key=lambda item: item.priority_score, reverse=True)

    recent_rows = db.execute(
        select(AppWriteLog, User.username)
        .outerjoin(User, User.id == AppWriteLog.actor_user_id)
        .where(AppWriteLog.scope.in_(["coach_intervention_action", "coach_intervention_auto_apply_batch"]))
        .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
        .limit(recent_decisions_limit)
    ).all()
    recent_items = [_audit_log_list_item(log_row, actor_username=username) for log_row, username in recent_rows]

    return CoachCommandCenterResponse(
        portfolio=portfolio,
        open_interventions_total=len(intervention_rows),
        ranked_queue_limit=queue_limit,
        ranked_queue=ranked[:queue_limit],
        recent_decisions=recent_items,
        ranking_version=ranking_version,
    )


@router.get("/coach/planner-ruleset", response_model=PlannerRulesetResponse)
def get_coach_planner_ruleset(
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    return PlannerRulesetResponse.model_validate(get_planner_ruleset_snapshot())


@router.get("/coach/planner-ruleset/history", response_model=PlannerRulesetHistoryResponse)
def list_coach_planner_ruleset_history(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    scopes = ("planner_ruleset_update", "planner_ruleset_rollback")
    rows = (
        db.execute(
            select(AppWriteLog, User.username)
            .outerjoin(User, User.id == AppWriteLog.actor_user_id)
            .where(AppWriteLog.scope.in_(scopes))
            .order_by(AppWriteLog.created_at.desc(), AppWriteLog.id.desc())
        )
        .all()
    )
    scope_counts: Dict[str, int] = {}
    for log_row, _username in rows:
        scope_key = str(log_row.scope or "")
        scope_counts[scope_key] = int(scope_counts.get(scope_key, 0)) + 1
    total = len(rows)
    page = rows[offset : offset + limit]
    items = [_audit_log_list_item(log_row, actor_username=username) for log_row, username in page]
    return PlannerRulesetHistoryResponse(
        total=total,
        offset=offset,
        limit=limit,
        scope_counts=scope_counts,
        items=items,
    )


@router.get("/coach/planner-ruleset/backups", response_model=PlannerRulesetBackupsResponse)
def list_coach_planner_ruleset_backups(
    limit: int = Query(default=20, ge=1, le=100),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    items = planner_ruleset_backup_snapshots(limit=limit)
    return PlannerRulesetBackupsResponse(total=len(items), limit=limit, items=items)


@router.post("/coach/planner-ruleset/validate", response_model=PlannerRulesetValidateResponse)
def validate_coach_planner_ruleset(
    payload: PlannerRulesetUpdateRequest,
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    baseline = get_planner_ruleset_snapshot()
    errors = validate_planner_ruleset_payload(payload.ruleset)
    warnings = planner_ruleset_validation_warnings(payload.ruleset, baseline=baseline)
    diff_preview = planner_ruleset_diff_preview(payload.ruleset, baseline=baseline)
    return PlannerRulesetValidateResponse(
        valid=(len(errors) == 0),
        errors=errors,
        warnings=warnings,
        diff_preview=diff_preview,
    )


@router.put("/coach/planner-ruleset", response_model=PlannerRulesetMutationResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def update_coach_planner_ruleset(
    request: Request,
    response: Response,
    payload: PlannerRulesetUpdateRequest = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del request, response
    baseline = get_planner_ruleset_snapshot()
    errors = validate_planner_ruleset_payload(payload.ruleset)
    if errors:
        raise HTTPException(status_code=400, detail={"code": "PLANNER_RULESET_INVALID", "errors": errors})
    warnings = planner_ruleset_validation_warnings(payload.ruleset, baseline=baseline)
    diff_preview = planner_ruleset_diff_preview(payload.ruleset, baseline=baseline)
    snapshot = save_planner_ruleset_payload(payload.ruleset)
    backup_items = planner_ruleset_backup_snapshots(limit=3)
    latest_backup = next((item for item in backup_items if str(item.get("kind")) == "latest_backup"), None)
    _append_app_write_log(
        db,
        scope="planner_ruleset_update",
        actor_user_id=int(principal.user_id),
        payload={
            "submitted_meta": _planner_ruleset_meta_log(dict((payload.ruleset or {}).get("meta") or {})),
            "before_meta": _planner_ruleset_meta_log(dict((baseline or {}).get("meta") or {})),
            "after_meta": _planner_ruleset_meta_log(dict((snapshot or {}).get("meta") or {})),
            "warning_count": len(warnings),
            "warnings": list(warnings[:10]),
            "diff_preview": diff_preview,
            "latest_backup_snapshot": _planner_ruleset_backup_log_item(latest_backup),
            "error_count": len(errors),
        },
    )
    return PlannerRulesetMutationResponse(
        status="ok",
        message="Planner ruleset updated and reloaded",
        ruleset=PlannerRulesetResponse.model_validate(snapshot),
    )


@router.post("/coach/planner-ruleset/rollback", response_model=PlannerRulesetMutationResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def rollback_coach_planner_ruleset(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del request, response
    baseline = get_planner_ruleset_snapshot()
    try:
        snapshot = rollback_planner_ruleset_payload()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail={"code": "PLANNER_RULESET_BACKUP_NOT_FOUND"})
    diff_preview = planner_ruleset_diff_preview(snapshot, baseline=baseline)
    backup_items = planner_ruleset_backup_snapshots(limit=3)
    latest_backup = next((item for item in backup_items if str(item.get("kind")) == "latest_backup"), None)
    _append_app_write_log(
        db,
        scope="planner_ruleset_rollback",
        actor_user_id=int(principal.user_id),
        payload={
            "status": "ok",
            "before_meta": _planner_ruleset_meta_log(dict((baseline or {}).get("meta") or {})),
            "after_meta": _planner_ruleset_meta_log(dict((snapshot or {}).get("meta") or {})),
            "diff_preview": diff_preview,
            "latest_backup_snapshot": _planner_ruleset_backup_log_item(latest_backup),
        },
    )
    return PlannerRulesetMutationResponse(
        status="ok",
        message="Planner ruleset rolled back from backup",
        ruleset=PlannerRulesetResponse.model_validate(snapshot),
    )


@router.post("/coach/interventions/{intervention_id}/action", response_model=InterventionActionResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_intervention_action(
    request: Request,
    response: Response,
    intervention_id: int,
    payload: InterventionActionRequest = Body(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del request, response
    row = _intervention_or_404(db, intervention_id)
    action = str(payload.action or "").strip().lower()
    now = datetime.utcnow()
    before = {
        "status": str(row.status or ""),
        "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
    }

    if action == "approve":
        row.status = "approved"
        row.cooldown_until = None
        message = "Intervention approved"
    elif action == "resolve":
        row.status = "resolved"
        row.cooldown_until = None
        message = "Intervention resolved"
    elif action in {"snooze", "cooldown"}:
        minutes = int(payload.cooldown_minutes or 24 * 60)
        row.cooldown_until = now + timedelta(minutes=minutes)
        row.status = "snoozed" if action == "snooze" else "open"
        message = f"Intervention {action} applied for {minutes} minutes"
    else:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_INTERVENTION_ACTION",
                "action": payload.action,
                "allowed_actions": ["approve", "resolve", "snooze", "cooldown"],
            },
        )

    db.flush()
    athlete = _athlete_or_404(db, int(row.athlete_id))
    _append_app_write_log(
        db,
        scope="coach_intervention_action",
        actor_user_id=principal.user_id,
        payload={
            "intervention_id": int(row.id),
            "athlete_id": int(row.athlete_id),
            "action": action,
            "note": str(payload.note or ""),
            "before": before,
            "after": {
                "status": str(row.status or ""),
                "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
            },
            "actor": {
                "user_id": int(principal.user_id),
                "username": principal.username,
                "role": principal.role,
            },
            "acted_at": now.isoformat(),
        },
    )
    db.flush()

    return InterventionActionResponse(
        status="ok",
        message=message,
        intervention=_intervention_list_item(row, athlete_name=f"{athlete.first_name} {athlete.last_name}"),
    )


@router.post("/coach/interventions/{intervention_id}/revert-auto-approval", response_model=InterventionActionResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_revert_intervention_auto_approval(
    request: Request,
    response: Response,
    intervention_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del request, response
    row = _intervention_or_404(db, intervention_id)
    source_log, source_payload = _latest_auto_apply_approval_log(db, intervention_id)
    if source_log is None or source_payload is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "AUTO_APPLY_REVERT_NOT_AVAILABLE",
                "intervention_id": int(intervention_id),
                "message": "No auto-applied approval audit record is available to revert.",
            },
        )
    if _has_revert_for_source_action(db, source_action_log_id=int(source_log.id)):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "AUTO_APPLY_ALREADY_REVERTED",
                "intervention_id": int(intervention_id),
                "source_action_log_id": int(source_log.id),
            },
        )

    source_before = dict(source_payload.get("before") or {})
    source_after = dict(source_payload.get("after") or {})
    expected_status = str(source_after.get("status") or "").strip().lower()
    expected_cooldown = _coerce_iso_datetime(source_after.get("cooldown_until"))
    current_status = str(row.status or "").strip().lower()
    current_cooldown = row.cooldown_until

    status_matches = (not expected_status) or (current_status == expected_status)
    cooldown_matches = _same_dt(current_cooldown, expected_cooldown)
    if not status_matches or not cooldown_matches:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "INTERVENTION_STATE_CHANGED",
                "intervention_id": int(intervention_id),
                "expected": {
                    "status": expected_status or None,
                    "cooldown_until": source_after.get("cooldown_until"),
                },
                "current": {
                    "status": current_status or None,
                    "cooldown_until": current_cooldown.isoformat() if current_cooldown else None,
                },
            },
        )

    restore_status = str(source_before.get("status") or "open").strip().lower() or "open"
    if restore_status not in {"open", "snoozed", "approved", "resolved"}:
        restore_status = "open"
    restore_cooldown = _coerce_iso_datetime(source_before.get("cooldown_until"))

    now = datetime.utcnow()
    before = {
        "status": str(row.status or ""),
        "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
    }
    row.status = restore_status
    row.cooldown_until = restore_cooldown
    db.flush()

    athlete = _athlete_or_404(db, int(row.athlete_id))
    _append_app_write_log(
        db,
        scope="coach_intervention_action",
        actor_user_id=principal.user_id,
        payload={
            "intervention_id": int(row.id),
            "athlete_id": int(row.athlete_id),
            "action": "revert_auto_approve",
            "note": "manual_revert_auto_apply",
            "auto_reverted": True,
            "source_action_log_id": int(source_log.id),
            "source_action_created_at": source_log.created_at.isoformat() if source_log.created_at else None,
            "source_policy_source": source_payload.get("policy_source"),
            "source_before": source_before,
            "source_after": source_after,
            "before": before,
            "after": {
                "status": str(row.status or ""),
                "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
            },
            "actor": {
                "user_id": int(principal.user_id),
                "username": principal.username,
                "role": principal.role,
            },
            "acted_at": now.isoformat(),
        },
    )
    db.flush()

    return InterventionActionResponse(
        status="ok",
        message="Auto-applied approval reverted",
        intervention=_intervention_list_item(row, athlete_name=f"{athlete.first_name} {athlete.last_name}"),
    )


@router.post("/coach/interventions/auto-apply-low-risk", response_model=InterventionAutoApplyResponse)
@limiter.limit(get_settings().write_endpoint_rate_limit)
def coach_auto_apply_low_risk_interventions(
    request: Request,
    response: Response,
    dry_run: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del request, response
    now = datetime.utcnow()
    coach_policy = _load_coach_automation_policy(db, principal.user_id)
    rows = db.execute(
        select(CoachIntervention)
        .where(CoachIntervention.status == "open")
        .order_by(CoachIntervention.created_at.asc(), CoachIntervention.id.asc())
        .limit(limit)
    ).scalars().all()

    athlete_ids = sorted({int(r.athlete_id) for r in rows if r.athlete_id is not None})
    athlete_rows = (
        db.execute(select(Athlete).where(Athlete.id.in_(athlete_ids))).scalars().all()
        if athlete_ids
        else []
    )
    athlete_names = {int(a.id): f"{a.first_name} {a.last_name}" for a in athlete_rows}
    eval_map = _auto_apply_eval_map(db, rows, coach_user_id=principal.user_id, now=now)

    skipped: List[InterventionAutoApplySkippedItem] = []
    eligible_rows: List[CoachIntervention] = []
    eligible_policy_source: Dict[int, str] = {}
    for row in rows:
        eval_item = eval_map.get(int(row.id)) or {}
        athlete_id = int(eval_item.get("athlete_id") or row.athlete_id)
        if not bool(eval_item.get("eligible")):
            skipped.append(
                InterventionAutoApplySkippedItem(
                    intervention_id=int(row.id),
                    athlete_id=athlete_id,
                    reason=str(eval_item.get("reason") or "not_eligible"),
                    detail=dict(eval_item.get("detail") or {}),
                )
            )
            continue
        eligible_rows.append(row)
        eligible_policy_source[int(row.id)] = str(eval_item.get("policy_source") or "athlete")

    applied_items: List[InterventionListItem] = []
    if not dry_run:
        for row in eligible_rows:
            before = {
                "status": str(row.status or ""),
                "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
            }
            row.status = "approved"
            row.cooldown_until = None
            db.flush()
            athlete_name = athlete_names.get(int(row.athlete_id))
            applied_items.append(_intervention_list_item(row, athlete_name=athlete_name))
            _append_app_write_log(
                db,
                scope="coach_intervention_action",
                actor_user_id=principal.user_id,
                payload={
                    "intervention_id": int(row.id),
                    "athlete_id": int(row.athlete_id),
                    "action": "approve",
                    "note": "auto_apply_low_risk_policy",
                    "auto_applied": True,
                    "policy_source": eligible_policy_source.get(int(row.id), "athlete"),
                    "before": before,
                    "after": {
                        "status": str(row.status or ""),
                        "cooldown_until": row.cooldown_until.isoformat() if row.cooldown_until else None,
                    },
                    "actor": {
                        "user_id": int(principal.user_id),
                        "username": principal.username,
                        "role": principal.role,
                    },
                    "acted_at": now.isoformat(),
                },
            )
        _append_app_write_log(
            db,
            scope="coach_intervention_auto_apply_batch",
            actor_user_id=principal.user_id,
            payload={
                "scanned_count": len(rows),
                "eligible_count": len(eligible_rows),
                "applied_count": len(applied_items),
                "skipped_count": len(skipped),
                "dry_run": False,
                "coach_policy": coach_policy.model_dump(mode="json"),
                "actor": {"user_id": int(principal.user_id), "username": principal.username, "role": principal.role},
                "executed_at": now.isoformat(),
            },
        )
        db.flush()
    else:
        applied_items = [_intervention_list_item(row, athlete_name=athlete_names.get(int(row.athlete_id))) for row in eligible_rows]

    return InterventionAutoApplyResponse(
        status="ok",
        scanned_count=len(rows),
        eligible_count=len(eligible_rows),
        applied_count=(0 if dry_run else len(applied_items)),
        skipped_count=len(skipped),
        dry_run=bool(dry_run),
        applied=applied_items,
        skipped=skipped,
    )


@router.get("/athletes/{athlete_id}/today", response_model=AthleteTodayResponse)
def get_athlete_today(
    athlete_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    athlete = _athlete_or_404(db, athlete_id)
    today = date.today()
    checkin = _latest_checkin(db, athlete_id, today)
    readiness_value: Optional[float] = None
    readiness_bucket: Optional[str] = None
    if checkin is not None:
        readiness_value = readiness_score(checkin.sleep, checkin.energy, checkin.recovery, checkin.stress)
        readiness_bucket = readiness_band(readiness_value)

    loads_7d = _daily_loads(db, athlete_id, 7)
    loads_28d = _daily_loads(db, athlete_id, 28)
    pain_recent = _pain_recent(db, athlete_id, today)
    planned = _planned_session_for_today(db, athlete_id, today)
    event_ctx = _next_event_context(db, athlete_id, today)

    adapted = adapt_session_structure(
        planned.get("structure_json") or default_structure(45),
        readiness=readiness_value,
        pain_flag=pain_recent,
        acute_chronic_ratio=compute_acute_chronic_ratio(loads_28d),
        days_to_event=event_ctx.get("days_to_event"),
    )
    adapted_session = dict(adapted or {})
    session_payload = dict(adapted_session.get("session") or {})
    session_payload["blocks"] = _enrich_adapted_blocks(list(session_payload.get("blocks") or []), athlete)
    adapted_session["session"] = session_payload

    return AthleteTodayResponse(
        athlete_id=athlete_id,
        day=today,
        readiness_score=readiness_value,
        readiness_band=readiness_bucket,
        checkin_present=checkin is not None and checkin.day == today,
        planned_session=planned,
        adapted_session=adapted_session,
        training_load_summary=_load_summary(loads_7d, loads_28d, readiness_value, pain_recent),
        context={
            "checkin_day": checkin.day.isoformat() if checkin is not None else None,
            "pain_recent": pain_recent,
            **event_ctx,
        },
    )


@router.get("/athletes/{athlete_id}/analytics", response_model=AthleteAnalyticsResponse)
@cache(expire=3600, namespace="athlete_analytics", key_builder=_request_key_builder)
def get_athlete_analytics(
    request: Request,
    athlete_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    _athlete_or_404(db, athlete_id)
    weekly = _weekly_rollups_for_athlete(db, athlete_id, weeks=12)
    logs = db.execute(
        select(
            TrainingLog.id,
            TrainingLog.date,
            TrainingLog.duration_min,
            TrainingLog.load_score,
            TrainingLog.rpe,
            TrainingLog.session_category,
            TrainingLog.distance_km,
            TrainingLog.avg_pace_sec_per_km,
        )
        .where(TrainingLog.athlete_id == athlete_id)
        .order_by(TrainingLog.date.asc())
    ).mappings().all()
    logs_df = pd.DataFrame(logs)
    return AthleteAnalyticsResponse(
        athlete_id=athlete_id,
        available=True,
        fitness_fatigue=compute_fitness_fatigue(logs_df),
        vdot_history=compute_vdot_history(logs_df),
        intensity_distribution=compute_intensity_distribution(logs_df),
        weekly_rollups=weekly,
    )


@router.get("/athletes/{athlete_id}/predictions", response_model=AthletePredictionsResponse)
def get_athlete_predictions(
    athlete_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    _athlete_or_404(db, athlete_id)
    latest = db.execute(
        select(TrainingLog).where(TrainingLog.athlete_id == athlete_id).order_by(TrainingLog.date.desc(), TrainingLog.id.desc())
    ).scalars().first()
    benchmark = None
    if latest is not None:
        benchmark = {
            "log_id": latest.id,
            "date": latest.date.isoformat(),
            "distance_km": float(latest.distance_km or 0.0),
            "duration_min": int(latest.duration_min or 0),
            "avg_pace_sec_per_km": float(latest.avg_pace_sec_per_km) if latest.avg_pace_sec_per_km is not None else None,
            "load_score": float(latest.load_score or 0.0),
        }
    if benchmark is None:
        return AthletePredictionsResponse(
            athlete_id=athlete_id,
            available=False,
            reason="No benchmark training log available for prediction",
            benchmark=benchmark,
        )

    return AthletePredictionsResponse(
        athlete_id=athlete_id,
        available=True,
        predictions=predict_all_distances(benchmark),
        benchmark=benchmark,
    )


@router.get("/athletes/{athlete_id}/plan-status", response_model=AthletePlanStatusResponse)
def get_athlete_plan_status(
    athlete_id: int,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    _athlete_or_404(db, athlete_id)
    today = date.today()
    week_end = today + timedelta(days=6)

    candidate_plan = (
        db.execute(
            select(Plan)
            .where(Plan.athlete_id == athlete_id)
            .where(Plan.status.in_(["active", "draft"]))
            .order_by(
                case((Plan.status == "active", 0), else_=1),
                Plan.start_date.desc(),
                Plan.id.desc(),
            )
        )
        .scalars()
        .first()
    )

    if candidate_plan is None:
        return AthletePlanStatusResponse(
            athlete_id=athlete_id,
            date=today,
            has_plan=False,
            plan=None,
            upcoming_week_start=today,
            upcoming_week_end=week_end,
            upcoming_sessions=[],
        )

    session_rows = (
        db.execute(
            select(PlanDaySession)
            .join(PlanWeek, PlanWeek.id == PlanDaySession.plan_week_id)
            .where(PlanWeek.plan_id == candidate_plan.id)
            .where(PlanDaySession.athlete_id == athlete_id)
            .where(PlanDaySession.session_day >= today)
            .where(PlanDaySession.session_day <= week_end)
            .order_by(PlanDaySession.session_day.asc(), PlanDaySession.id.asc())
        )
        .scalars()
        .all()
    )

    return AthletePlanStatusResponse(
        athlete_id=athlete_id,
        date=today,
        has_plan=True,
        plan=AthletePlanStatusPlan(
            id=int(candidate_plan.id),
            race_goal=str(candidate_plan.race_goal or ""),
            status=str(candidate_plan.status or ""),
            start_date=candidate_plan.start_date,
            weeks=int(candidate_plan.weeks or 0),
            sessions_per_week=int(candidate_plan.sessions_per_week or 0),
        ),
        upcoming_week_start=today,
        upcoming_week_end=week_end,
        upcoming_sessions=[
            AthleteUpcomingSessionItem(
                session_day=row.session_day,
                session_name=str(row.session_name or ""),
                status=str(row.status or ""),
                source_template_name=(str(row.source_template_name) if row.source_template_name else None),
            )
            for row in session_rows
        ],
    )


@router.get("/coach/portfolio-analytics", response_model=CoachPortfolioAnalyticsResponse)
@cache(expire=3600, namespace="coach_portfolio", key_builder=_request_key_builder)
def get_coach_portfolio_analytics(
    request: Request,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_roles("coach")),
):
    del principal
    return _coach_portfolio_analytics_payload(db)


@router.get("/analytics/weekly-rollups", response_model=WeeklyRollupResponse)
@cache(
    expire=get_settings().analytics_cache_ttl_seconds,
    namespace="analytics",
    key_builder=_request_key_builder,
)
def get_weekly_rollups(
    request: Request,
    athlete_id: Optional[int] = Query(default=None),
    weeks: int = Query(default=8, ge=1, le=52),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(get_current_principal),
):
    if athlete_id is None:
        if principal.role.lower() not in {"coach", "admin"}:
            raise HTTPException(status_code=403, detail={"code": "FORBIDDEN_ROLE", "required_roles": ["coach"], "role": principal.role})
    elif principal.role.lower() not in {"coach", "admin"} and int(principal.athlete_id or 0) != int(athlete_id):
        raise HTTPException(
            status_code=403,
            detail={"code": "FORBIDDEN_ATHLETE_SCOPE", "athlete_id": athlete_id, "principal_athlete_id": principal.athlete_id},
        )
    since = date.today() - timedelta(days=(weeks * 7))
    stmt = select(
        TrainingLog.id,
        TrainingLog.athlete_id,
        TrainingLog.date,
        TrainingLog.duration_min,
        TrainingLog.load_score,
    ).where(TrainingLog.date >= since)
    if athlete_id is not None:
        stmt = stmt.where(TrainingLog.athlete_id == athlete_id)

    rows = db.execute(stmt).mappings().all()
    df = pd.DataFrame(rows)
    weekly = weekly_summary(df)
    items = [
        WeeklyRollupItem(
            week=str(row["week"]),
            duration_min=float(row["duration_min"]),
            load_score=float(row["load_score"]),
            sessions=int(row["sessions"]),
        )
        for _, row in weekly.iterrows()
    ] if not weekly.empty else []
    return WeeklyRollupResponse(athlete_id=athlete_id, weeks=weeks, items=items)


@router.get("/athletes/{athlete_id}/workload", response_model=AthleteWorkloadResponse)
@cache(
    expire=get_settings().workload_cache_ttl_seconds,
    namespace="workload",
    key_builder=_request_key_builder,
)
def get_athlete_multiweek_workload(
    request: Request,
    athlete_id: int,
    weeks: int = Query(default=6, ge=1, le=26),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_athlete_access),
):
    del principal
    # Ensure athlete exists and fail fast with clean 404-like payload if needed.
    athlete_exists = db.execute(select(Athlete.id).where(Athlete.id == athlete_id)).scalar_one_or_none()
    if athlete_exists is None:
        raise HTTPException(status_code=404, detail={"code": "ATHLETE_NOT_FOUND", "athlete_id": athlete_id})

    today = date.today()
    since = today - timedelta(days=weeks * 7)
    rows = db.execute(
        select(TrainingLog.date, TrainingLog.duration_min, TrainingLog.load_score)
        .where(TrainingLog.athlete_id == athlete_id, TrainingLog.date >= since)
        .order_by(TrainingLog.date.asc())
    ).all()

    by_week: dict[date, dict] = {}
    acute_load = 0.0
    chronic_load = 0.0
    for log_date, duration_min, load_score in rows:
        week_start = log_date - timedelta(days=log_date.weekday())
        bucket = by_week.setdefault(
            week_start,
            {"week_start": week_start, "duration_min": 0, "load_score": 0.0, "sessions": 0},
        )
        bucket["duration_min"] += int(duration_min or 0)
        bucket["load_score"] += float(load_score or 0.0)
        bucket["sessions"] += 1
        age_days = (today - log_date).days
        if age_days <= 6:
            acute_load += float(load_score or 0.0)
        if age_days <= 27:
            chronic_load += float(load_score or 0.0)

    series = [
        AthleteWorkloadWeek(
            week_start=wk["week_start"],
            duration_min=int(wk["duration_min"]),
            load_score=round(float(wk["load_score"]), 2),
            sessions=int(wk["sessions"]),
        )
        for wk in sorted(by_week.values(), key=lambda item: item["week_start"])
    ]
    ratio = round(acute_load / (chronic_load / 4), 2) if chronic_load > 0 else None
    return AthleteWorkloadResponse(
        athlete_id=athlete_id,
        weeks=weeks,
        acute_load_7d=round(acute_load, 2),
        chronic_load_28d=round(chronic_load, 2),
        acute_chronic_ratio=ratio,
        series=series,
    )
