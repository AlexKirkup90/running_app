import type {
  Athlete,
  CheckIn,
  CoachClientRow,
  CoachDashboard,
  Event,
  Intervention,
  MessageResponse,
  Plan,
  PlanDaySession,
  PlanWeek,
  Recommendation,
  TokenResponse,
  TrainingLog,
} from "./types";

const BASE = "/api/v1";

class ApiError extends Error {
  constructor(
    public status: number,
    public detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = localStorage.getItem("token");
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}${path}`, { ...options, headers });

  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new ApiError(res.status, body.detail ?? res.statusText);
  }

  return res.json() as Promise<T>;
}

// Auth
export async function login(
  username: string,
  password: string,
): Promise<TokenResponse> {
  const body = new URLSearchParams({ username, password });
  const res = await fetch(`${BASE}/auth/token`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "Login failed" }));
    throw new ApiError(res.status, err.detail ?? "Login failed");
  }
  return res.json() as Promise<TokenResponse>;
}

export function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<MessageResponse> {
  return request("/auth/change-password", {
    method: "POST",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
}

// Coach
export function fetchCoachDashboard(): Promise<CoachDashboard> {
  return request("/coach/dashboard");
}

export function fetchCoachClients(): Promise<CoachClientRow[]> {
  return request("/coach/clients");
}

// Athletes
export function fetchAthletes(status = "active"): Promise<Athlete[]> {
  return request(`/athletes?status=${status}`);
}

export function fetchAthlete(id: number): Promise<Athlete> {
  return request(`/athletes/${id}`);
}

// Check-ins
export function fetchCheckins(
  athleteId?: number,
  limit = 30,
): Promise<CheckIn[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (athleteId) params.set("athlete_id", String(athleteId));
  return request(`/checkins?${params}`);
}

export function createCheckin(data: {
  athlete_id: number;
  sleep: number;
  energy: number;
  recovery: number;
  stress: number;
  training_today: boolean;
}): Promise<CheckIn> {
  return request("/checkins", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Training Logs
export function fetchTrainingLogs(
  athleteId?: number,
  limit = 30,
): Promise<TrainingLog[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (athleteId) params.set("athlete_id", String(athleteId));
  return request(`/training-logs?${params}`);
}

export function createTrainingLog(data: {
  athlete_id: number;
  session_category: string;
  duration_min: number;
  distance_km: number;
  avg_hr?: number | null;
  max_hr?: number | null;
  avg_pace_sec_per_km?: number | null;
  rpe: number;
  notes: string;
  pain_flag: boolean;
}): Promise<TrainingLog> {
  return request("/training-logs", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// Events
export function fetchEvents(athleteId?: number): Promise<Event[]> {
  const params = new URLSearchParams();
  if (athleteId) params.set("athlete_id", String(athleteId));
  return request(`/events?${params}`);
}

// Plans
export function fetchPlans(
  athleteId?: number,
  status = "active",
): Promise<Plan[]> {
  const params = new URLSearchParams({ status });
  if (athleteId) params.set("athlete_id", String(athleteId));
  return request(`/plans?${params}`);
}

export function fetchPlanWeeks(planId: number): Promise<PlanWeek[]> {
  return request(`/plans/${planId}/weeks`);
}

export function fetchPlanSessions(planId: number): Promise<PlanDaySession[]> {
  return request(`/plans/${planId}/sessions`);
}

// Interventions
export function fetchInterventions(
  status = "open",
  athleteId?: number,
): Promise<Intervention[]> {
  const params = new URLSearchParams({ status });
  if (athleteId) params.set("athlete_id", String(athleteId));
  return request(`/interventions?${params}`);
}

export function syncInterventions(): Promise<MessageResponse> {
  return request("/interventions/sync", { method: "POST" });
}

export function decideIntervention(
  interventionId: number,
  decision: string,
  note = "",
  modifiedAction?: string,
): Promise<MessageResponse> {
  return request(`/interventions/${interventionId}/decide`, {
    method: "POST",
    body: JSON.stringify({
      intervention_id: interventionId,
      decision,
      note,
      modified_action: modifiedAction,
    }),
  });
}

// Recommendations
export function fetchRecommendation(
  athleteId: number,
): Promise<Recommendation> {
  return request(`/athletes/${athleteId}/recommendation`);
}

export { ApiError };
