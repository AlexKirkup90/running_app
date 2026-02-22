import { useMemo } from "react";
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  fetchAthlete,
  fetchCheckins,
  fetchTrainingLogs,
  fetchAthleteProfile,
  fetchSessionBriefing,
  fetchTrainingLoadSummary,
  fetchFitnessFatigue,
  fetchVdotHistory,
  fetchRacePredictions,
  fetchAthleteNotes,
  fetchAthleteTimeline,
  fetchInterventions,
} from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DashboardSkeleton } from "@/components/ui/skeleton";
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  Clock,
  Flame,
  Heart,
  Zap,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart,
  Area,
  Legend,
} from "recharts";

function bandVariant(band: string | null) {
  if (band === "green") return "success" as const;
  if (band === "amber") return "warning" as const;
  return "danger" as const;
}

function riskVariant(level: string) {
  if (level === "low") return "success" as const;
  if (level === "moderate") return "warning" as const;
  return "danger" as const;
}

function readinessVariant(r: string) {
  if (r === "race_ready" || r === "fresh") return "success" as const;
  if (r === "slightly_fatigued" || r === "detrained") return "warning" as const;
  if (r === "fatigued" || r === "overreached") return "danger" as const;
  return "secondary" as const;
}

function readinessLabel(r: string) {
  const map: Record<string, string> = {
    race_ready: "Race Ready", fresh: "Fresh",
    slightly_fatigued: "Slightly Fatigued", fatigued: "Fatigued",
    overreached: "Overreached", detrained: "Detrained",
    insufficient_data: "Insufficient Data",
  };
  return map[r] ?? r;
}

export function CoachAthleteDetail() {
  const { athleteId } = useParams<{ athleteId: string }>();
  const id = Number(athleteId);

  const { data: athlete, isLoading: athleteLoading } = useQuery({
    queryKey: ["athlete", id],
    queryFn: () => fetchAthlete(id),
    enabled: id > 0,
  });

  const { data: profile } = useQuery({
    queryKey: ["athlete-profile", id],
    queryFn: () => fetchAthleteProfile(id),
    enabled: id > 0,
  });

  const { data: checkins } = useQuery({
    queryKey: ["checkins", id, 14],
    queryFn: () => fetchCheckins(id, 14),
    enabled: id > 0,
  });

  const { data: logs } = useQuery({
    queryKey: ["training-logs", id, 30],
    queryFn: () => fetchTrainingLogs(id, 30),
    enabled: id > 0,
  });

  const { data: briefing } = useQuery({
    queryKey: ["session-briefing", id],
    queryFn: () => fetchSessionBriefing(id),
    enabled: id > 0,
  });

  const { data: loadSummary } = useQuery({
    queryKey: ["training-load-summary", id],
    queryFn: () => fetchTrainingLoadSummary(id),
    enabled: id > 0,
  });

  const { data: fitness } = useQuery({
    queryKey: ["fitness-fatigue", id],
    queryFn: () => fetchFitnessFatigue(id),
    enabled: id > 0,
  });

  const { data: vdotData } = useQuery({
    queryKey: ["vdot-history", id],
    queryFn: () => fetchVdotHistory(id),
    enabled: id > 0,
  });

  const { data: predictions } = useQuery({
    queryKey: ["race-predictions", id],
    queryFn: () => fetchRacePredictions(id),
    enabled: id > 0,
  });

  const { data: notes } = useQuery({
    queryKey: ["athlete-notes", id],
    queryFn: () => fetchAthleteNotes(id),
    enabled: id > 0,
  });

  const { data: timeline } = useQuery({
    queryKey: ["athlete-timeline", id],
    queryFn: () => fetchAthleteTimeline(id, 30),
    enabled: id > 0,
  });

  const { data: interventions } = useQuery({
    queryKey: ["interventions", "open", id],
    queryFn: () => fetchInterventions("open", id),
    enabled: id > 0,
  });

  const fitnessChart = useMemo(() => {
    if (!fitness?.points?.length) return [];
    const pts = fitness.points;
    const step = Math.max(1, Math.floor(pts.length / 60));
    return pts.filter((_, i) => i % step === 0 || i === pts.length - 1).map((p) => ({
      day: p.day.slice(5), CTL: p.ctl, ATL: p.atl, TSB: p.tsb,
    }));
  }, [fitness]);

  const readinessTrend = useMemo(() => {
    if (!checkins?.length) return [];
    return [...checkins]
      .sort((a, b) => a.day.localeCompare(b.day))
      .map((c) => ({ day: c.day.slice(5), score: c.readiness_score ?? 0 }));
  }, [checkins]);

  if (athleteLoading) return <DashboardSkeleton />;

  if (!athlete) {
    return (
      <div className="space-y-4">
        <Button variant="ghost" size="sm" asChild>
          <Link to="/coach/clients"><ArrowLeft className="mr-2 h-4 w-4" />Back to Clients</Link>
        </Button>
        <p className="text-muted-foreground">Athlete not found.</p>
      </div>
    );
  }

  const today = new Date().toISOString().slice(0, 10);
  const todayCheckin = checkins?.find((c) => c.day === today);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="sm" asChild>
            <Link to="/coach/clients"><ArrowLeft className="h-4 w-4" /></Link>
          </Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">
              {athlete.first_name} {athlete.last_name}
            </h1>
            <p className="text-sm text-muted-foreground">{athlete.email}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={athlete.status === "active" ? "success" : "secondary"}>
            {athlete.status}
          </Badge>
          {todayCheckin && (
            <Badge variant={bandVariant(todayCheckin.readiness_band)}>
              Readiness: {todayCheckin.readiness_score} ({todayCheckin.readiness_band})
            </Badge>
          )}
        </div>
      </div>

      {/* Quick Stats Row */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Zap className="h-5 w-5 text-amber-500" />
            <div>
              <p className="text-xs text-muted-foreground">VDOT</p>
              <p className="text-lg font-bold">{profile?.vdot_score ?? vdotData?.current_vdot ?? "—"}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Activity className="h-5 w-5 text-blue-500" />
            <div>
              <p className="text-xs text-muted-foreground">A:C Ratio</p>
              <p className="text-lg font-bold">{briefing?.acute_chronic_ratio?.toFixed(2) ?? "—"}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Heart className="h-5 w-5 text-red-500" />
            <div>
              <p className="text-xs text-muted-foreground">Form (TSB)</p>
              <p className="text-lg font-bold">{fitness?.current_tsb?.toFixed(1) ?? "—"}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <Flame className="h-5 w-5 text-orange-500" />
            <div>
              <p className="text-xs text-muted-foreground">Load Risk</p>
              {loadSummary?.has_data ? (
                <Badge variant={riskVariant(loadSummary.risk_level)}>{loadSummary.risk_level}</Badge>
              ) : (
                <p className="text-lg font-bold">—</p>
              )}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <AlertTriangle className="h-5 w-5 text-red-500" />
            <div>
              <p className="text-xs text-muted-foreground">Open Flags</p>
              <p className="text-lg font-bold">{interventions?.length ?? 0}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="training">Training</TabsTrigger>
          <TabsTrigger value="analytics">Analytics</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
        </TabsList>

        {/* Overview Tab */}
        <TabsContent value="overview" className="space-y-6">
          {/* Session Briefing */}
          {briefing?.planned_session_name && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Today's Session</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium">{briefing.planned_session_name}</p>
                    {briefing.prescription && (
                      <p className="text-sm text-muted-foreground">{briefing.prescription}</p>
                    )}
                  </div>
                  {briefing.adaptation_action && briefing.adaptation_action !== "keep" && (
                    <Badge variant={briefing.adaptation_action === "progress" ? "success" : "warning"}>
                      {briefing.adaptation_action}
                    </Badge>
                  )}
                </div>
                {briefing.adaptation_reason && briefing.adaptation_action !== "keep" && (
                  <div className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                    {briefing.adaptation_reason}
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Open Interventions */}
          {interventions && interventions.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Open Interventions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {interventions.slice(0, 5).map((iv) => (
                  <div key={iv.id} className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <p className="text-sm font-medium">{iv.action_type}</p>
                      <p className="text-xs text-muted-foreground">
                        Risk: {(iv.risk_score * 100).toFixed(0)}% | Confidence: {(iv.confidence_score * 100).toFixed(0)}%
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      {iv.guardrail_pass ? (
                        <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      ) : (
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                      )}
                      <Badge variant={iv.status === "open" ? "warning" : "secondary"}>{iv.status}</Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Coach Notes */}
          {notes && notes.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Notes & Tasks</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {notes.slice(0, 5).map((n) => (
                  <div key={n.id} className="flex items-center justify-between rounded-lg border p-3">
                    <span className={`text-sm ${n.completed ? "line-through text-muted-foreground" : ""}`}>
                      {n.note}
                    </span>
                    <div className="flex items-center gap-2">
                      {n.due_date && (
                        <span className="text-xs text-muted-foreground">{n.due_date}</span>
                      )}
                      <Badge variant={n.completed ? "success" : "secondary"}>
                        {n.completed ? "Done" : "Open"}
                      </Badge>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          )}

          {/* Race Predictions */}
          {predictions?.predictions && Object.keys(predictions.predictions).length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Race Predictions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="overflow-auto rounded-lg border">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b bg-muted/50">
                        <th className="p-2 text-left font-medium">Distance</th>
                        <th className="p-2 text-left font-medium">VDOT</th>
                        <th className="p-2 text-left font-medium">Riegel</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(predictions.predictions).map(([label, preds]) => {
                        const vdotPred = preds.find((p) => p.method === "vdot");
                        const riegelPred = preds.find((p) => p.method === "riegel");
                        return (
                          <tr key={label} className="border-b last:border-0">
                            <td className="p-2 font-medium">{label}</td>
                            <td className="p-2">{vdotPred?.predicted_display ?? "—"}</td>
                            <td className="p-2">{riegelPred?.predicted_display ?? "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Training Tab */}
        <TabsContent value="training" className="space-y-6">
          {/* Recent Checkins */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent Check-Ins</CardTitle>
            </CardHeader>
            <CardContent>
              {checkins && checkins.length > 0 ? (
                <div className="space-y-2">
                  {checkins.map((c) => (
                    <div key={c.id} className="flex items-center justify-between rounded-lg border p-3">
                      <span className="text-sm">{c.day}</span>
                      <div className="flex items-center gap-4 text-sm">
                        <span>S:{c.sleep}</span>
                        <span>E:{c.energy}</span>
                        <span>R:{c.recovery}</span>
                        <span>St:{c.stress}</span>
                        <Badge variant={bandVariant(c.readiness_band)}>
                          {c.readiness_score} ({c.readiness_band})
                        </Badge>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-6 text-center text-sm text-muted-foreground">No recent check-ins</p>
              )}
            </CardContent>
          </Card>

          {/* Recent Sessions */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Recent Training Logs</CardTitle>
            </CardHeader>
            <CardContent>
              {logs && logs.length > 0 ? (
                <div className="space-y-2">
                  {logs.map((l) => (
                    <div key={l.id} className="flex items-center justify-between rounded-lg border p-3">
                      <div>
                        <p className="text-sm font-medium">{l.session_category}</p>
                        <p className="text-xs text-muted-foreground">{l.date}</p>
                      </div>
                      <div className="flex items-center gap-3 text-sm">
                        <span>{l.duration_min}min</span>
                        <span>{l.distance_km}km</span>
                        <Badge variant={l.rpe >= 8 ? "danger" : l.rpe >= 5 ? "warning" : "success"}>
                          RPE {l.rpe}
                        </Badge>
                        <span className="text-muted-foreground">Load: {l.load_score.toFixed(0)}</span>
                        {l.pain_flag && <Badge variant="destructive">Pain</Badge>}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="py-6 text-center text-sm text-muted-foreground">No training logs</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Analytics Tab */}
        <TabsContent value="analytics" className="space-y-6">
          {/* Fitness/Fatigue */}
          {fitnessChart.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">Fitness & Fatigue</CardTitle>
                  {fitness && (
                    <Badge variant={readinessVariant(fitness.readiness)}>
                      {readinessLabel(fitness.readiness)}
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={280}>
                  <ComposedChart data={fitnessChart}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Legend />
                    <Line type="monotone" dataKey="CTL" name="Fitness" stroke="#3b82f6" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="ATL" name="Fatigue" stroke="#ef4444" strokeWidth={2} dot={false} />
                    <Area type="monotone" dataKey="TSB" name="Form" fill="#10b98133" stroke="#10b981" strokeWidth={1} />
                  </ComposedChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* VDOT Progression */}
          {vdotData && vdotData.points.length > 0 && (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-base">VDOT Progression</CardTitle>
                  <div className="flex gap-3 text-sm">
                    {vdotData.current_vdot && <span>Current: <strong>{vdotData.current_vdot}</strong></span>}
                    <Badge variant={vdotData.trend === "improving" ? "success" : vdotData.trend === "declining" ? "danger" : "secondary"}>
                      {vdotData.trend}
                    </Badge>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={vdotData.points.map((p) => ({ date: p.date.slice(5), vdot: p.vdot }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                    <YAxis domain={["dataMin - 2", "dataMax + 2"]} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="vdot" name="VDOT" stroke="#f59e0b" strokeWidth={2} dot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}

          {/* Readiness Trend */}
          {readinessTrend.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Readiness Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={readinessTrend}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                    <YAxis domain={[1, 5]} tick={{ fontSize: 12 }} />
                    <Tooltip />
                    <Line type="monotone" dataKey="score" name="Readiness" stroke="#8b5cf6" strokeWidth={2} dot={{ r: 3 }} />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          )}
        </TabsContent>

        {/* Timeline Tab */}
        <TabsContent value="timeline" className="space-y-4">
          {!timeline?.length ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                No timeline events yet.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {timeline.map((entry, i) => (
                <div key={i} className="flex gap-4 rounded-lg border p-4">
                  <div className="flex flex-col items-center">
                    <Clock className="h-4 w-4 text-muted-foreground" />
                    <div className="mt-1 flex-1 w-px bg-border" />
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium">{entry.title}</p>
                      <Badge variant="outline" className="text-xs">{entry.source}</Badge>
                    </div>
                    <p className="text-sm text-muted-foreground">{entry.detail}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{entry.when}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
