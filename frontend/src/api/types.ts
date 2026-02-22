// Mirror of Pydantic schemas from api/schemas.py

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: string;
  user_id: number;
  athlete_id: number | null;
}

export interface TokenData {
  user_id: number;
  username: string;
  role: string;
  athlete_id: number | null;
}

export interface Athlete {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  dob: string | null;
  max_hr: number | null;
  resting_hr: number | null;
  threshold_pace_sec_per_km: number | null;
  easy_pace_sec_per_km: number | null;
  status: string;
}

export interface CheckIn {
  id: number;
  athlete_id: number;
  day: string;
  sleep: number;
  energy: number;
  recovery: number;
  stress: number;
  training_today: boolean;
  readiness_score: number | null;
  readiness_band: string | null;
}

export interface TrainingLog {
  id: number;
  athlete_id: number;
  date: string;
  session_category: string;
  duration_min: number;
  distance_km: number;
  avg_hr: number | null;
  max_hr: number | null;
  avg_pace_sec_per_km: number | null;
  rpe: number;
  load_score: number;
  notes: string;
  pain_flag: boolean;
}

export interface Event {
  id: number;
  athlete_id: number;
  name: string;
  event_date: string;
  distance: string;
}

export interface Plan {
  id: number;
  athlete_id: number;
  race_goal: string;
  weeks: number;
  sessions_per_week: number;
  max_session_min: number;
  start_date: string;
  status: string;
}

export interface PlanWeek {
  id: number;
  plan_id: number;
  week_number: number;
  phase: string;
  week_start: string;
  week_end: string;
  sessions_order: string[];
  target_load: number;
  locked: boolean;
}

export interface PlanDaySession {
  id: number;
  plan_week_id: number;
  athlete_id: number;
  session_day: string;
  session_name: string;
  source_template_name: string;
  status: string;
}

export interface Intervention {
  id: number;
  athlete_id: number;
  action_type: string;
  status: string;
  risk_score: number;
  confidence_score: number;
  expected_impact: Record<string, unknown>;
  why_factors: string[];
  guardrail_pass: boolean;
  guardrail_reason: string;
  cooldown_until: string | null;
  created_at: string | null;
}

export interface Recommendation {
  action: string;
  risk_score: number;
  confidence_score: number;
  expected_impact: Record<string, unknown>;
  why: string[];
  guardrail_pass: boolean;
  guardrail_reason: string;
}

export interface CoachDashboard {
  total_athletes: number;
  active_athletes: number;
  open_interventions: number;
  high_risk_count: number;
  weekly_load: WeeklyLoad[];
}

export interface WeeklyLoad {
  week: string;
  duration_min: number;
  load_score: number;
  sessions: number;
}

export interface CoachClientRow {
  athlete_id: number;
  first_name: string;
  last_name: string;
  email: string;
  status: string;
  open_interventions: number;
  risk_label: string;
  last_checkin: string | null;
  last_log: string | null;
}

export interface MessageResponse {
  message: string;
}

// --- Organizations (Phase 6) ---

export interface Organization {
  id: number;
  name: string;
  slug: string;
  tier: string;
  role: string;
  max_coaches: number;
  max_athletes: number;
  coach_count: number;
  athlete_count: number;
}

export interface OrgCoach {
  user_id: number;
  username: string;
  role: string;
  caseload_cap: number;
  assigned_athletes: number;
}

export interface OrgAssignment {
  id: number;
  coach_user_id: number;
  coach_username: string;
  athlete_id: number;
  athlete_name: string;
  status: string;
}

// --- Community & Social (Phase 7) ---

export interface TrainingGroup {
  id: number;
  name: string;
  description: string;
  owner_user_id: number;
  privacy: string;
  max_members: number;
  member_count: number;
  created_at: string | null;
}

export interface GroupMember {
  id: number;
  group_id: number;
  athlete_id: number;
  athlete_name: string;
  role: string;
  joined_at: string | null;
}

export interface Challenge {
  id: number;
  group_id: number | null;
  name: string;
  challenge_type: string;
  target_value: number;
  start_date: string;
  end_date: string;
  status: string;
  created_by: number;
  participant_count: number;
  created_at: string | null;
}

export interface ChallengeEntry {
  id: number;
  challenge_id: number;
  athlete_id: number;
  athlete_name: string;
  progress: number;
  completed: boolean;
  last_updated: string | null;
}

export interface GroupMessage {
  id: number;
  group_id: number;
  author_athlete_id: number;
  author_name: string;
  content: string;
  message_type: string;
  created_at: string | null;
}

export interface Kudos {
  id: number;
  from_athlete_id: number;
  from_name: string;
  to_athlete_id: number;
  to_name: string;
  training_log_id: number | null;
  created_at: string | null;
}

export interface LeaderboardEntry {
  athlete_id: number;
  name: string;
  value: number;
  rank: number;
}

export interface ActivityFeedItem {
  athlete_id: number;
  athlete_name: string;
  activity_summary: string;
  date: string;
  training_log_id: number;
  kudos_count: number;
}

// --- Phase 1: Plan Builder ---

export interface PlanPreviewWeek {
  week_number: number;
  phase: string;
  week_start: string;
  week_end: string;
  target_load: number;
  sessions_order: string[];
}

export interface PlanPreviewDay {
  week_number: number;
  session_day: string;
  session_name: string;
  phase: string;
}

export interface PlanPreview {
  weeks: PlanPreviewWeek[];
  days: PlanPreviewDay[];
}

export interface PlanCreateResult {
  plan_id: number;
  message: string;
}

// --- Phase 1: Session Library ---

export interface SessionTemplate {
  id: number;
  name: string;
  category: string;
  intent: string;
  energy_system: string;
  tier: string;
  is_treadmill: boolean;
  duration_min: number;
  structure_json: Record<string, unknown>;
  targets_json: Record<string, unknown>;
  progression_json: Record<string, unknown>;
  regression_json: Record<string, unknown>;
  prescription: string;
  coaching_notes: string;
}

// --- Phase 1: Intervention Stats ---

export interface InterventionStats {
  open_count: number;
  high_priority: number;
  actionable_now: number;
  snoozed: number;
  sla_due_24h: number;
  sla_due_72h: number;
  median_age_hours: number;
  oldest_age_hours: number;
}

// --- Phase 1: Casework ---

export interface TimelineEntry {
  when: string;
  source: string;
  title: string;
  detail: string;
}

export interface CoachNote {
  id: number;
  athlete_id: number;
  note: string;
  due_date: string | null;
  completed: boolean;
}

// --- Phase 2: Athlete Intelligence ---

export interface SessionBriefing {
  has_checkin: boolean;
  readiness_score: number | null;
  readiness_band: string | null;
  acute_chronic_ratio: number;
  vdot: number | null;
  phase: string | null;
  max_hr: number | null;
  resting_hr: number | null;
  threshold_pace: string | null;
  easy_pace: string | null;
  planned_session_name: string | null;
  planned_session_status: string | null;
  has_template: boolean;
  prescription: string | null;
  coaching_notes: string | null;
  adaptation_action: string | null;
  adaptation_reason: string | null;
  adapted_blocks: Record<string, unknown>[];
  progression_rules: Record<string, unknown> | null;
  regression_rules: Record<string, unknown> | null;
  today_logged: boolean;
}

export interface TrainingLoadSummary {
  has_data: boolean;
  monotony: number;
  strain: number;
  risk_level: string;
  total_load: number;
  session_count: number;
  avg_daily_load: number;
}

export interface FitnessFatigue {
  points: { day: string; ctl: number; atl: number; tsb: number; load: number }[];
  current_ctl: number;
  current_atl: number;
  current_tsb: number;
  readiness: string;
}

export interface VdotHistory {
  points: { date: string; vdot: number; source: string; distance_m: number }[];
  current_vdot: number | null;
  peak_vdot: number | null;
  trend: string;
  improvement_per_month: number;
}

export interface RacePredictions {
  predictions: Record<string, { distance_label: string; predicted_display: string; method: string; vdot_used: number | null }[]>;
  source_vdot: number | null;
  source_event: string | null;
}

export interface AthleteProfile {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  dob: string | null;
  max_hr: number | null;
  resting_hr: number | null;
  threshold_pace_sec_per_km: number | null;
  easy_pace_sec_per_km: number | null;
  vdot_score: number | null;
  status: string;
  wearable_connections: WearableConnection[];
  sync_logs: SyncLog[];
}

// --- Phase 3: Integrations ---

export interface Webhook {
  hook_id: string;
  url: string;
  events: string[];
  created_at: string;
}

export interface WearableConnection {
  id: number;
  service: string;
  sync_status: string;
  last_sync_at: string | null;
  external_athlete_id: string | null;
}

export interface SyncLog {
  id: number;
  service: string;
  status: string;
  activities_found: number;
  activities_imported: number;
  started_at: string | null;
}
