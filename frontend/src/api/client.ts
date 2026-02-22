import type {
  ActivityFeedItem,
  Athlete,
  Challenge,
  ChallengeEntry,
  CheckIn,
  CoachClientRow,
  CoachDashboard,
  CoachNote,
  Event,
  GroupMember,
  GroupMessage,
  Intervention,
  InterventionStats,
  Kudos,
  LeaderboardEntry,
  MessageResponse,
  OrgAssignment,
  OrgCoach,
  Organization,
  Plan,
  PlanCreateResult,
  PlanDaySession,
  PlanPreview,
  PlanWeek,
  Recommendation,
  SessionTemplate,
  TimelineEntry,
  TokenResponse,
  TrainingGroup,
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

export function createEvent(data: {
  name: string;
  event_date: string;
  distance: string;
}): Promise<Event> {
  return request("/events", {
    method: "POST",
    body: JSON.stringify(data),
  });
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

// Organizations (Phase 6)
export function fetchOrganizations(): Promise<Organization[]> {
  return request("/organizations");
}

export function fetchOrgCoaches(orgId: number): Promise<OrgCoach[]> {
  return request(`/organizations/${orgId}/coaches`);
}

export function fetchOrgAssignments(orgId: number): Promise<OrgAssignment[]> {
  return request(`/organizations/${orgId}/assignments`);
}

export function createAssignment(
  orgId: number,
  coachUserId: number,
  athleteId: number,
): Promise<MessageResponse> {
  return request(`/organizations/${orgId}/assignments`, {
    method: "POST",
    body: JSON.stringify({ coach_user_id: coachUserId, athlete_id: athleteId }),
  });
}

export function transferAssignment(
  orgId: number,
  assignmentId: number,
  newCoachUserId: number,
): Promise<MessageResponse> {
  return request(`/organizations/${orgId}/assignments/${assignmentId}/transfer`, {
    method: "PUT",
    body: JSON.stringify({ new_coach_user_id: newCoachUserId }),
  });
}

export function removeAssignment(
  orgId: number,
  assignmentId: number,
): Promise<MessageResponse> {
  return request(`/organizations/${orgId}/assignments/${assignmentId}`, {
    method: "DELETE",
  });
}

// Community & Social (Phase 7)
export function fetchGroups(): Promise<TrainingGroup[]> {
  return request("/groups");
}

export function discoverGroups(): Promise<TrainingGroup[]> {
  return request("/groups/discover");
}

export function joinGroup(groupId: number): Promise<MessageResponse> {
  return request(`/groups/${groupId}/join`, { method: "POST" });
}

export function syncChallengeProgress(): Promise<MessageResponse> {
  return request("/challenges/sync-progress", { method: "POST" });
}

export function createGroup(data: {
  name: string;
  description?: string;
  privacy?: string;
  max_members?: number;
}): Promise<TrainingGroup> {
  return request("/groups", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function fetchGroupMembers(groupId: number): Promise<GroupMember[]> {
  return request(`/groups/${groupId}/members`);
}

export function addGroupMember(
  groupId: number,
  athleteId: number,
): Promise<MessageResponse> {
  return request(`/groups/${groupId}/members?athlete_id=${athleteId}`, {
    method: "POST",
  });
}

export function removeGroupMember(
  groupId: number,
  athleteId: number,
): Promise<MessageResponse> {
  return request(`/groups/${groupId}/members/${athleteId}`, {
    method: "DELETE",
  });
}

export function fetchGroupMessages(
  groupId: number,
  limit = 30,
): Promise<GroupMessage[]> {
  return request(`/groups/${groupId}/messages?limit=${limit}`);
}

export function postGroupMessage(
  groupId: number,
  content: string,
  messageType = "text",
): Promise<GroupMessage> {
  return request(`/groups/${groupId}/messages`, {
    method: "POST",
    body: JSON.stringify({ content, message_type: messageType }),
  });
}

export function fetchGroupLeaderboard(
  groupId: number,
  metric = "distance",
  days = 7,
): Promise<LeaderboardEntry[]> {
  return request(`/groups/${groupId}/leaderboard?metric=${metric}&days=${days}`);
}

export function fetchChallenges(status = "active"): Promise<Challenge[]> {
  return request(`/challenges?status=${status}`);
}

export function createChallenge(data: {
  name: string;
  challenge_type: string;
  target_value: number;
  start_date: string;
  end_date: string;
  group_id?: number | null;
}): Promise<Challenge> {
  return request("/challenges", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function fetchChallengeEntries(
  challengeId: number,
): Promise<ChallengeEntry[]> {
  return request(`/challenges/${challengeId}/entries`);
}

export function joinChallenge(challengeId: number): Promise<MessageResponse> {
  return request(`/challenges/${challengeId}/join`, { method: "POST" });
}

export function fetchActivityFeed(
  groupId?: number,
  limit = 20,
): Promise<ActivityFeedItem[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (groupId) params.set("group_id", String(groupId));
  return request(`/activity-feed?${params}`);
}

export function fetchKudos(
  athleteId?: number,
  limit = 20,
): Promise<Kudos[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (athleteId) params.set("athlete_id", String(athleteId));
  return request(`/kudos?${params}`);
}

export function giveKudos(
  toAthleteId: number,
  trainingLogId?: number | null,
): Promise<MessageResponse> {
  const params = new URLSearchParams({ to_athlete_id: String(toAthleteId) });
  if (trainingLogId) params.set("training_log_id", String(trainingLogId));
  return request(`/kudos?${params}`, { method: "POST" });
}

// --- Phase 1: Plan Builder ---

export function previewPlan(data: {
  athlete_id: number;
  race_goal: string;
  weeks: number;
  sessions_per_week: number;
  max_session_min: number;
  start_date: string;
}): Promise<PlanPreview> {
  return request("/plans/preview", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function createPlan(data: {
  athlete_id: number;
  race_goal: string;
  weeks: number;
  sessions_per_week: number;
  max_session_min: number;
  start_date: string;
}): Promise<PlanCreateResult> {
  return request("/plans", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function toggleWeekLock(
  planId: number,
  weekNumber: number,
): Promise<MessageResponse> {
  return request(`/plans/${planId}/weeks/${weekNumber}/lock`, {
    method: "PUT",
  });
}

export function swapSession(
  planId: number,
  weekNumber: number,
  sessionDay: string,
  newSessionName: string,
): Promise<MessageResponse> {
  return request(
    `/plans/${planId}/weeks/${weekNumber}/sessions/${sessionDay}?new_session_name=${encodeURIComponent(newSessionName)}`,
    { method: "PUT" },
  );
}

export function regenerateWeek(
  planId: number,
  weekNumber: number,
): Promise<MessageResponse> {
  return request(`/plans/${planId}/weeks/${weekNumber}/regenerate`, {
    method: "POST",
  });
}

// --- Phase 1: Session Library ---

export function fetchSessions(params?: {
  category?: string;
  intent?: string;
  is_treadmill?: boolean;
}): Promise<SessionTemplate[]> {
  const search = new URLSearchParams();
  if (params?.category) search.set("category", params.category);
  if (params?.intent) search.set("intent", params.intent);
  if (params?.is_treadmill !== undefined)
    search.set("is_treadmill", String(params.is_treadmill));
  return request(`/sessions?${search}`);
}

export function fetchSession(sessionId: number): Promise<SessionTemplate> {
  return request(`/sessions/${sessionId}`);
}

export function createSession(
  data: Omit<SessionTemplate, "id">,
): Promise<SessionTemplate> {
  return request("/sessions", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateSession(
  sessionId: number,
  data: Omit<SessionTemplate, "id">,
): Promise<SessionTemplate> {
  return request(`/sessions/${sessionId}`, {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function deleteSession(sessionId: number): Promise<MessageResponse> {
  return request(`/sessions/${sessionId}`, { method: "DELETE" });
}

export function fetchSessionCategories(): Promise<string[]> {
  return request("/sessions/categories");
}

// --- Phase 1: Intervention Stats & Batch ---

export function fetchInterventionStats(): Promise<InterventionStats> {
  return request("/interventions/stats");
}

export function batchDecideInterventions(data: {
  intervention_ids: number[];
  decision: string;
  note?: string;
  modified_action?: string;
}): Promise<MessageResponse> {
  return request("/interventions/batch-decide", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

// --- Phase 1: Casework ---

export function fetchAthleteTimeline(
  athleteId: number,
  limit = 120,
): Promise<TimelineEntry[]> {
  return request(`/athletes/${athleteId}/timeline?limit=${limit}`);
}

export function fetchAthleteNotes(athleteId: number): Promise<CoachNote[]> {
  return request(`/athletes/${athleteId}/notes`);
}

export function createAthleteNote(
  athleteId: number,
  data: { note: string; due_date?: string | null },
): Promise<CoachNote> {
  return request(`/athletes/${athleteId}/notes`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function updateAthleteNote(
  athleteId: number,
  noteId: number,
  completed: boolean,
): Promise<CoachNote> {
  return request(
    `/athletes/${athleteId}/notes/${noteId}?completed=${completed}`,
    { method: "PUT" },
  );
}

export function deleteAthleteNote(
  athleteId: number,
  noteId: number,
): Promise<MessageResponse> {
  return request(`/athletes/${athleteId}/notes/${noteId}`, {
    method: "DELETE",
  });
}

// --- Phase 2: Athlete Intelligence ---

export function fetchSessionBriefing(athleteId: number): Promise<import("./types").SessionBriefing> {
  return request(`/athletes/${athleteId}/session-briefing`);
}

export function fetchTrainingLoadSummary(athleteId: number): Promise<import("./types").TrainingLoadSummary> {
  return request(`/athletes/${athleteId}/training-load-summary`);
}

export function fetchFitnessFatigue(athleteId: number): Promise<import("./types").FitnessFatigue> {
  return request(`/athletes/${athleteId}/analytics/fitness`);
}

export function fetchVdotHistory(athleteId: number): Promise<import("./types").VdotHistory> {
  return request(`/athletes/${athleteId}/analytics/vdot`);
}

export function fetchRacePredictions(athleteId: number): Promise<import("./types").RacePredictions> {
  return request(`/athletes/${athleteId}/race-predictions`);
}

export function fetchAthleteProfile(athleteId: number): Promise<import("./types").AthleteProfile> {
  return request(`/athletes/${athleteId}/profile`);
}

// --- Phase 3: Webhooks ---

export function fetchWebhooks(): Promise<import("./types").Webhook[]> {
  return request("/webhooks");
}

export function registerWebhook(data: {
  url: string;
  events: string[];
  secret?: string;
}): Promise<import("./types").Webhook> {
  return request("/webhooks", {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export function deleteWebhook(hookId: string): Promise<MessageResponse> {
  return request(`/webhooks/${hookId}`, { method: "DELETE" });
}

// --- Phase 3: Wearable Connections ---

export function fetchWearableConnections(): Promise<import("./types").WearableConnection[]> {
  return request("/wearables/connections");
}

export function deleteWearableConnection(connectionId: number): Promise<MessageResponse> {
  return request(`/wearables/connections/${connectionId}`, { method: "DELETE" });
}

export function fetchWearableSyncLogs(): Promise<import("./types").SyncLog[]> {
  return request("/wearables/sync-logs");
}

export { ApiError };
