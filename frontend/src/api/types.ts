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
