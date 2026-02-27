from __future__ import annotations

from datetime import date as dt_date
from datetime import datetime as dt_datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TrainingLogInput(BaseModel):
    athlete_id: int
    date: dt_date = Field(default_factory=dt_date.today)
    session_category: str = "run"
    duration_min: int = Field(ge=0)
    distance_km: float = Field(default=0, ge=0)
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_pace_sec_per_km: Optional[float] = None
    rpe: int = Field(default=5, ge=1, le=10)
    load_score: Optional[float] = Field(default=None, ge=0)
    notes: str = ""
    pain_flag: bool = False
    source: str = "manual"
    raw_payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_defaults(self):
        if self.load_score is None:
            self.load_score = round((self.duration_min * self.rpe) / 10.0, 2)
        return self


class TrainingLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    date: dt_date
    session_category: str
    duration_min: int
    distance_km: float
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    avg_pace_sec_per_km: Optional[float] = None
    rpe: int
    load_score: float
    notes: str
    pain_flag: bool


class CheckInInput(BaseModel):
    athlete_id: Optional[int] = None
    day: dt_date = Field(default_factory=dt_date.today)
    sleep: int = Field(ge=1, le=5)
    energy: int = Field(ge=1, le=5)
    recovery: int = Field(ge=1, le=5)
    stress: int = Field(ge=1, le=5)
    training_today: bool = True


class CheckInResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    day: dt_date
    sleep: int
    energy: int
    recovery: int
    stress: int
    training_today: bool


class SimpleStatusResponse(BaseModel):
    status: str


class WeeklyRollupItem(BaseModel):
    week: str
    duration_min: float
    load_score: float
    sessions: int


class WeeklyRollupResponse(BaseModel):
    athlete_id: Optional[int] = None
    weeks: int
    items: list[WeeklyRollupItem]


class AthleteWorkloadWeek(BaseModel):
    week_start: dt_date
    duration_min: int
    load_score: float
    sessions: int


class AthleteWorkloadResponse(BaseModel):
    athlete_id: int
    weeks: int
    acute_load_7d: float
    chronic_load_28d: float
    acute_chronic_ratio: Optional[float]
    series: list[AthleteWorkloadWeek]


class ProviderWebhookAccepted(BaseModel):
    provider: str
    received_at: dt_datetime
    event: str
    training_log: TrainingLogResponse
    status: str = "created"
    deduplicated: bool = False
    event_key: Optional[str] = None
    ingest_scope: Optional[str] = None
    duplicate_of_training_log_id: Optional[int] = None


class AuthTokenRequest(BaseModel):
    username: str
    password: str


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: int
    username: str
    role: str
    athlete_id: Optional[int] = None


class ChangePasswordRequest(BaseModel):
    username: str
    current_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    status: str
    message: str


class AthleteTodayResponse(BaseModel):
    athlete_id: int
    day: dt_date
    readiness_score: Optional[float] = None
    readiness_band: Optional[str] = None
    checkin_present: bool
    planned_session: dict[str, Any]
    adapted_session: dict[str, Any]
    training_load_summary: dict[str, Any]
    context: dict[str, Any]


class AthleteAnalyticsResponse(BaseModel):
    athlete_id: int
    available: bool
    reason: Optional[str] = None
    fitness_fatigue: Optional[dict[str, Any]] = None
    vdot_history: Optional[dict[str, Any]] = None
    intensity_distribution: Optional[dict[str, Any]] = None
    weekly_rollups: Optional[WeeklyRollupResponse] = None


class AthletePredictionsResponse(BaseModel):
    athlete_id: int
    available: bool
    reason: Optional[str] = None
    predictions: dict[str, Any] = Field(default_factory=dict)
    benchmark: Optional[dict[str, Any]] = None


class AthleteUpcomingSessionItem(BaseModel):
    session_day: dt_date
    session_name: str
    status: str
    source_template_name: Optional[str] = None


class AthletePlanStatusPlan(BaseModel):
    id: int
    race_goal: str
    status: str
    start_date: dt_date
    weeks: int
    sessions_per_week: int


class AthletePlanStatusResponse(BaseModel):
    athlete_id: int
    date: dt_date
    has_plan: bool
    plan: Optional[AthletePlanStatusPlan] = None
    upcoming_week_start: dt_date
    upcoming_week_end: dt_date
    upcoming_sessions: list[AthleteUpcomingSessionItem] = Field(default_factory=list)


class CoachPortfolioAnalyticsResponse(BaseModel):
    athletes_total: int
    athletes_active: int
    average_readiness: Optional[float] = None
    active_interventions: int
    weekly_compliance_rate: Optional[float] = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class AthleteListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    assigned_coach_user_id: Optional[int] = None
    assigned_coach_username: Optional[str] = None
    vdot_seed: Optional[float] = None
    pace_source: Optional[str] = None
    status: str


class AthleteDetailResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    email: str
    dob: Optional[dt_date] = None
    max_hr: Optional[int] = None
    resting_hr: Optional[int] = None
    vdot_seed: Optional[float] = None
    threshold_pace_sec_per_km: Optional[int] = None
    easy_pace_sec_per_km: Optional[int] = None
    pace_source: Optional[str] = None
    assigned_coach_user_id: Optional[int] = None
    assigned_coach_username: Optional[str] = None
    status: str
    created_at: dt_datetime


class AthleteListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[AthleteListItem]


class CoachUserItem(BaseModel):
    id: int
    username: str
    role: str
    status: str = "active"
    athlete_id: Optional[int] = None
    must_change_password: bool
    failed_attempts: int
    locked_until: Optional[dt_datetime] = None
    last_login_at: Optional[dt_datetime] = None


class CoachUserListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[CoachUserItem]


class CoachUsersQueryResponse(CoachUserListResponse):
    pass


class CoachCreateUserRequest(BaseModel):
    username: str
    password: str
    must_change_password: bool = False


class CoachCreateUserResponse(BaseModel):
    status: str
    user: CoachUserItem


class CoachCreateAthleteRequest(BaseModel):
    first_name: str
    last_name: str
    email: str
    username: str
    password: str
    status: str = "active"
    dob: Optional[dt_date] = None
    max_hr: Optional[int] = None
    resting_hr: Optional[int] = None
    vdot_seed: Optional[float] = None
    threshold_pace_sec_per_km: Optional[int] = None
    easy_pace_sec_per_km: Optional[int] = None
    derive_paces_from_vdot: bool = True
    assigned_coach_user_id: Optional[int] = None
    must_change_password: bool = False


class CoachCreateAthleteResponse(BaseModel):
    status: str
    athlete: AthleteDetailResponse
    user: CoachUserItem


class CoachUpdateAthleteRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    status: Optional[str] = None
    dob: Optional[dt_date] = None
    max_hr: Optional[int] = None
    resting_hr: Optional[int] = None
    vdot_seed: Optional[float] = None
    threshold_pace_sec_per_km: Optional[int] = None
    easy_pace_sec_per_km: Optional[int] = None
    derive_paces_from_vdot: Optional[bool] = None
    assigned_coach_user_id: Optional[int] = None


class CoachUnlockUserResponse(BaseModel):
    status: str
    user: CoachUserItem


class CoachResetPasswordRequest(BaseModel):
    new_password: str
    must_change_password: bool = False


class CoachResetPasswordResponse(BaseModel):
    status: str
    user: CoachUserItem


class CoachUserStatusResponse(BaseModel):
    status: str
    user: CoachUserItem


class CoachAthleteLifecycleResponse(BaseModel):
    status: str
    athlete: AthleteDetailResponse


class AthleteEventCreate(BaseModel):
    name: str
    event_date: dt_date
    distance: str


class AthleteEventUpdate(BaseModel):
    name: Optional[str] = None
    event_date: Optional[dt_date] = None
    distance: Optional[str] = None


class AthleteEventItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    name: str
    event_date: dt_date
    distance: str


class AthleteEventListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[AthleteEventItem]


class AthletePreferencesResponse(BaseModel):
    athlete_id: int
    reminder_enabled: bool
    reminder_training_days: list[str]
    privacy_ack: bool
    automation_mode: str
    auto_apply_low_risk: bool
    auto_apply_confidence_min: float
    auto_apply_risk_max: float
    preferred_training_days: list[str]
    preferred_long_run_day: Optional[str] = None


class AthletePreferencesUpdate(BaseModel):
    reminder_enabled: Optional[bool] = None
    reminder_training_days: Optional[list[str]] = None
    privacy_ack: Optional[bool] = None
    automation_mode: Optional[str] = None
    auto_apply_low_risk: Optional[bool] = None
    auto_apply_confidence_min: Optional[float] = None
    auto_apply_risk_max: Optional[float] = None
    preferred_training_days: Optional[list[str]] = None
    preferred_long_run_day: Optional[str] = None


class SessionLibraryUpsert(BaseModel):
    name: str
    category: str
    intent: str
    energy_system: str
    tier: str
    is_treadmill: bool = False
    duration_min: int = Field(gt=0)
    structure_json: dict[str, Any]
    targets_json: dict[str, Any]
    progression_json: dict[str, Any]
    regression_json: dict[str, Any]
    prescription: str
    coaching_notes: str


class SessionLibraryPatch(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    intent: Optional[str] = None
    energy_system: Optional[str] = None
    tier: Optional[str] = None
    is_treadmill: Optional[bool] = None
    duration_min: Optional[int] = Field(default=None, gt=0)
    structure_json: Optional[dict[str, Any]] = None
    targets_json: Optional[dict[str, Any]] = None
    progression_json: Optional[dict[str, Any]] = None
    regression_json: Optional[dict[str, Any]] = None
    prescription: Optional[str] = None
    coaching_notes: Optional[str] = None


class SessionLibraryValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)


class SessionLibraryListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    category: str
    intent: str
    energy_system: str
    tier: str
    is_treadmill: bool
    duration_min: int
    methodology: Optional[str] = None
    status: str = "active"
    duplicate_of_template_id: Optional[int] = None


class SessionLibraryDetailResponse(SessionLibraryListItem):
    structure_json: dict[str, Any]
    targets_json: dict[str, Any]
    progression_json: dict[str, Any]
    regression_json: dict[str, Any]
    prescription: str
    coaching_notes: str


class SessionLibraryListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[SessionLibraryListItem]


class SessionLibraryDuplicateCandidateItem(BaseModel):
    kind: str
    score: float
    reason_tags: list[str] = Field(default_factory=list)
    left: SessionLibraryListItem
    right: SessionLibraryListItem


class SessionLibraryDuplicateAuditSummary(BaseModel):
    template_count: int
    exact_duplicate_pairs: int
    near_duplicate_pairs: int
    candidate_count: int


class SessionLibraryDuplicateAuditResponse(BaseModel):
    summary: SessionLibraryDuplicateAuditSummary
    candidates: list[SessionLibraryDuplicateCandidateItem] = Field(default_factory=list)


class SessionLibraryMetadataAuditIssue(BaseModel):
    code: str
    severity: str
    message: str
    field: Optional[str] = None


class SessionLibraryMetadataAuditTemplateItem(BaseModel):
    template: SessionLibraryListItem
    issue_count: int
    error_count: int
    warning_count: int
    issues: list[SessionLibraryMetadataAuditIssue] = Field(default_factory=list)


class SessionLibraryMetadataAuditSummary(BaseModel):
    template_count: int
    templates_with_issues: int
    error_count: int
    warning_count: int


class SessionLibraryMetadataAuditResponse(BaseModel):
    summary: SessionLibraryMetadataAuditSummary
    items: list[SessionLibraryMetadataAuditTemplateItem] = Field(default_factory=list)


class SessionLibraryGovernanceActionRequest(BaseModel):
    action: str
    duplicate_of_template_id: Optional[int] = None
    note: Optional[str] = None


class SessionLibraryFieldChange(BaseModel):
    field: str
    before: Any = None
    after: Any = None


class SessionLibraryGovernanceActionResponse(BaseModel):
    status: str
    action: str
    message: str
    template: SessionLibraryDetailResponse


class SessionLibraryNormalizeMetadataResponse(BaseModel):
    status: str
    message: str
    template: SessionLibraryDetailResponse
    applied_change_count: int
    applied_changes: list[SessionLibraryFieldChange] = Field(default_factory=list)
    issue_counts_before: dict[str, int] = Field(default_factory=dict)
    issue_counts_after: dict[str, int] = Field(default_factory=dict)


class SessionLibraryGoldStandardPackResponse(BaseModel):
    status: str
    message: str
    created_count: int
    updated_count: int
    template_count: int


class SessionLibraryBulkLegacyDeprecationRequest(BaseModel):
    dry_run: bool = True
    sample_limit: int = Field(default=10, ge=1, le=50)
    include_non_daniels_active: bool = False


class SessionLibraryBulkLegacyDeprecationResponse(BaseModel):
    status: str
    action: str
    message: str
    dry_run: bool
    template_count_scanned: int
    candidate_count: int
    changed_count: int
    unchanged_count: int
    sample_limit: int
    samples: list[SessionLibraryListItem] = Field(default_factory=list)


class SessionLibraryBulkCanonicalizationRequest(BaseModel):
    dry_run: bool = True
    sample_limit: int = Field(default=10, ge=1, le=50)
    candidate_limit: int = Field(default=200, ge=1, le=500)
    min_similarity: float = Field(default=0.9, ge=0.5, le=1.0)
    exact_only: bool = False


class SessionLibraryBulkCanonicalizationDecision(BaseModel):
    candidate_kind: str
    score: float
    reason_tags: list[str] = Field(default_factory=list)
    action: str
    decision_reason: str
    target: SessionLibraryListItem
    duplicate: SessionLibraryListItem


class SessionLibraryBulkCanonicalizationSkippedItem(BaseModel):
    candidate_kind: str
    score: float
    reason_tags: list[str] = Field(default_factory=list)
    reason_code: str
    message: str
    left: SessionLibraryListItem
    right: SessionLibraryListItem


class SessionLibraryBulkCanonicalizationResponse(BaseModel):
    status: str
    action: str
    message: str
    dry_run: bool
    candidate_count: int
    reviewed_count: int
    applied_count: int
    skipped_count: int
    sample_limit: int
    applied: list[SessionLibraryBulkCanonicalizationDecision] = Field(default_factory=list)
    skipped: list[SessionLibraryBulkCanonicalizationSkippedItem] = Field(default_factory=list)


class PlannerRulesetMeta(BaseModel):
    source: str
    week_policy_version: str
    progression_track_ruleset_version: str
    token_orchestration_ruleset_version: str
    quality_policy_rule_count: int
    token_orchestration_rule_count: int


class PlannerRulesetResponse(BaseModel):
    meta: PlannerRulesetMeta
    quality_policy_rules: dict[str, dict[str, dict[str, Any]]] = Field(default_factory=dict)
    token_orchestration_rules: list[dict[str, Any]] = Field(default_factory=list)


class PlannerRulesetUpdateRequest(BaseModel):
    ruleset: dict[str, Any]


class PlannerRulesetValidateResponse(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    diff_preview: dict[str, Any] = Field(default_factory=dict)


class PlannerRulesetMutationResponse(BaseModel):
    status: str
    message: str
    ruleset: PlannerRulesetResponse


class PlannerRulesetHistoryResponse(BaseModel):
    total: int
    offset: int
    limit: int
    scope_counts: dict[str, int] = Field(default_factory=dict)
    items: list[CoachAuditLogItem] = Field(default_factory=list)


class PlannerRulesetBackupItem(BaseModel):
    kind: str
    path: str
    filename: str
    size_bytes: int
    modified_at: dt_datetime


class PlannerRulesetBackupsResponse(BaseModel):
    total: int
    limit: int
    items: list[PlannerRulesetBackupItem] = Field(default_factory=list)


class SessionLibraryGovernanceReportResponse(BaseModel):
    generated_at: dt_datetime
    template_count: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    methodology_counts: dict[str, int] = Field(default_factory=dict)
    top_intents: dict[str, int] = Field(default_factory=dict)
    top_categories: dict[str, int] = Field(default_factory=dict)
    recent_scope_counts: dict[str, int] = Field(default_factory=dict)
    recent_actions: list[CoachAuditLogItem] = Field(default_factory=list)


class PlanPreviewRequest(BaseModel):
    athlete_id: int
    plan_name: Optional[str] = Field(default=None, max_length=200)
    race_goal: str
    weeks: int = Field(ge=1, le=52)
    start_date: dt_date
    sessions_per_week: int = Field(default=4, ge=1, le=7)
    max_session_min: int = Field(default=120, ge=20, le=480)
    preferred_days: Optional[list[str]] = None
    preferred_long_run_day: Optional[str] = None


class PlanCreateRequest(PlanPreviewRequest):
    pass


class PlanSessionAssignment(BaseModel):
    session_day: dt_date
    session_name: str
    source_template_id: Optional[int] = None
    planning_token: Optional[str] = None
    template_selection_reason: Optional[str] = None
    template_selection_summary: Optional[str] = None
    template_selection_rationale: list[str] = Field(default_factory=list)


class PlanPreviewWeek(BaseModel):
    week_number: int
    phase: str
    week_start: dt_date
    week_end: dt_date
    target_load: float
    long_run_minutes: int
    planned_load_estimate: Optional[float] = None
    planned_minutes_estimate: Optional[int] = None
    planned_long_run_minutes: Optional[int] = None
    week_policy_version: Optional[str] = None
    quality_focus: Optional[str] = None
    coach_summary: Optional[str] = None
    progression_tracks: list[str] = Field(default_factory=list)
    week_policy_rationale: list[str] = Field(default_factory=list)
    sessions_order: list[str]
    assignments: list[PlanSessionAssignment]
    selection_strategy_version: Optional[str] = None


class PlanPreviewResponse(BaseModel):
    athlete_id: int
    race_goal: str
    weeks: int
    start_date: dt_date
    sessions_per_week: int
    max_session_min: int
    preferred_days: list[str] = Field(default_factory=list)
    preferred_long_run_day: Optional[str] = None
    weeks_detail: list[PlanPreviewWeek]


class CoachPlanSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    athlete_id: int
    name: str
    race_goal: str
    weeks: int
    sessions_per_week: int
    max_session_min: int
    start_date: dt_date
    locked_until_week: int
    status: str


class CoachPlanListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[CoachPlanSummary]


class CoachPlanDaySessionItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan_week_id: int
    athlete_id: int
    session_day: dt_date
    session_name: str
    source_template_id: Optional[int] = None
    source_template_name: str
    status: str
    compiled_methodology: Optional[str] = None
    compiled_vdot: Optional[float] = None
    compiled_intensity_codes: list[str] = Field(default_factory=list)
    compiled_summary: Optional[str] = None
    planning_token: Optional[str] = None
    template_selection_reason: Optional[str] = None
    template_selection_summary: Optional[str] = None
    template_selection_rationale: list[str] = Field(default_factory=list)


class CoachPlanWeekItem(BaseModel):
    id: int
    week_number: int
    phase: str
    week_start: dt_date
    week_end: dt_date
    sessions_order: list[str]
    target_load: float
    locked: bool
    planned_minutes: Optional[int] = None
    planned_load: Optional[float] = None
    week_policy_version: Optional[str] = None
    quality_focus: Optional[str] = None
    coach_summary: Optional[str] = None
    progression_tracks: list[str] = Field(default_factory=list)
    week_policy_rationale: list[str] = Field(default_factory=list)
    sessions: list[CoachPlanDaySessionItem] = Field(default_factory=list)


class CoachPlanDetailResponse(BaseModel):
    plan: CoachPlanSummary
    weeks: list[CoachPlanWeekItem]


class CoachPlanUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    status: Optional[str] = None
    locked_until_week: Optional[int] = Field(default=None, ge=0)


class CoachPlanDaySessionPatch(BaseModel):
    session_day: Optional[dt_date] = None
    session_name: Optional[str] = None
    source_template_id: Optional[int] = None
    source_template_name: Optional[str] = None
    status: Optional[str] = None


class PlanWeekRegenerateRequest(BaseModel):
    preferred_days: Optional[list[str]] = None
    preferred_long_run_day: Optional[str] = None
    preserve_completed: bool = True


class PlanWeekLockResponse(BaseModel):
    status: str
    plan_id: int
    week_number: int
    locked: bool


class InterventionListItem(BaseModel):
    id: int
    athlete_id: int
    athlete_name: Optional[str] = None
    action_type: str
    status: str
    risk_score: float
    risk_band: str
    confidence_score: float
    created_at: dt_datetime
    cooldown_until: Optional[dt_datetime] = None
    why_factors: list[str] = Field(default_factory=list)
    expected_impact: dict[str, Any] = Field(default_factory=dict)
    guardrail_pass: bool
    guardrail_reason: str
    auto_apply_eligible: Optional[bool] = None
    review_reason: Optional[str] = None
    review_reason_detail: dict[str, Any] = Field(default_factory=dict)
    auto_revert_available: bool = False
    auto_revert_block_reason: Optional[str] = None


class InterventionListResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[InterventionListItem]


class InterventionActionRequest(BaseModel):
    action: str
    cooldown_minutes: Optional[int] = Field(default=None, ge=1, le=60 * 24 * 14)
    note: Optional[str] = None


class InterventionActionResponse(BaseModel):
    status: str
    message: str
    intervention: InterventionListItem


class InterventionAutoApplySkippedItem(BaseModel):
    intervention_id: int
    athlete_id: int
    reason: str
    detail: dict[str, Any] = Field(default_factory=dict)


class InterventionAutoApplyResponse(BaseModel):
    status: str
    scanned_count: int
    eligible_count: int
    applied_count: int
    skipped_count: int
    dry_run: bool = False
    applied: list[InterventionListItem] = Field(default_factory=list)
    skipped: list[InterventionAutoApplySkippedItem] = Field(default_factory=list)


class CoachAuditLogItem(BaseModel):
    id: int
    scope: str
    actor_user_id: Optional[int] = None
    actor_username: Optional[str] = None
    created_at: dt_datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class CoachAuditLogResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[CoachAuditLogItem]


class CoachAutomationPolicyResponse(BaseModel):
    enabled: bool
    default_auto_apply_low_risk: bool
    default_auto_apply_confidence_min: float
    default_auto_apply_risk_max: float
    apply_when_athlete_pref_missing: bool
    apply_when_athlete_pref_disabled: bool
    updated_at: Optional[dt_datetime] = None
    updated_by_user_id: Optional[int] = None
    source: str = "default"


class CoachAutomationPolicyUpdate(BaseModel):
    enabled: Optional[bool] = None
    default_auto_apply_low_risk: Optional[bool] = None
    default_auto_apply_confidence_min: Optional[float] = Field(default=None, ge=0, le=1)
    default_auto_apply_risk_max: Optional[float] = Field(default=None, ge=0, le=1)
    apply_when_athlete_pref_missing: Optional[bool] = None
    apply_when_athlete_pref_disabled: Optional[bool] = None


class CoachCommandCenterPriorityComponents(BaseModel):
    risk_component: float
    confidence_component: float
    age_boost: float
    guardrail_penalty: float
    status_penalty: float


class CoachCommandCenterInterventionItem(InterventionListItem):
    priority_score: float
    priority_components: CoachCommandCenterPriorityComponents
    priority_reasons: list[str] = Field(default_factory=list)
    ranking_version: str


class CoachCommandCenterResponse(BaseModel):
    portfolio: CoachPortfolioAnalyticsResponse
    open_interventions_total: int
    ranked_queue_limit: int
    ranked_queue: list[CoachCommandCenterInterventionItem] = Field(default_factory=list)
    recent_decisions: list[CoachAuditLogItem] = Field(default_factory=list)
    ranking_version: str
