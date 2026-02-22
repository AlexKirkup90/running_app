import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { useCheckins, useTrainingLogs } from "@/hooks/useAthlete";
import { useSessionBriefing, useTrainingLoadSummary } from "@/hooks/useAthleteIntelligence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  ClipboardCheck,
  Dumbbell,
  Flame,
  Gauge,
  Zap,
} from "lucide-react";

function bandColor(band: string | null) {
  if (band === "green")
    return "bg-emerald-50 border-emerald-200 text-emerald-800";
  if (band === "amber") return "bg-amber-50 border-amber-200 text-amber-800";
  return "bg-red-50 border-red-200 text-red-800";
}

function bandVariant(band: string | null) {
  if (band === "green") return "success" as const;
  if (band === "amber") return "warning" as const;
  return "danger" as const;
}

function riskColor(level: string) {
  if (level === "low") return "text-emerald-600";
  if (level === "moderate") return "text-amber-600";
  return "text-red-600";
}

function riskVariant(level: string) {
  if (level === "low") return "success" as const;
  if (level === "moderate") return "warning" as const;
  return "danger" as const;
}

function formatPace(secPerKm: number | null) {
  if (!secPerKm) return "—";
  const min = Math.floor(secPerKm / 60);
  const sec = Math.round(secPerKm % 60);
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

function paceLabel(label: string) {
  const map: Record<string, string> = { E: "Easy", M: "Marathon", T: "Threshold", I: "Interval", R: "Repetition" };
  return map[label] ?? label;
}

export function AthleteDashboard() {
  const { athleteId } = useAuthStore();
  const { data: checkins, isLoading: checkinsLoading } = useCheckins(
    athleteId ?? 0,
    7,
  );
  const { data: logs, isLoading: logsLoading } = useTrainingLogs(
    athleteId ?? 0,
    5,
  );
  const { data: briefing, isLoading: briefingLoading } = useSessionBriefing(athleteId ?? 0);
  const { data: loadSummary, isLoading: loadLoading } = useTrainingLoadSummary(athleteId ?? 0);

  const today = new Date().toISOString().slice(0, 10);

  const todayCheckin = useMemo(
    () => checkins?.find((c) => c.day === today) ?? null,
    [checkins, today],
  );

  const recentSessionCount = useMemo(() => {
    if (!logs) return 0;
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    const cutoff = weekAgo.toISOString().slice(0, 10);
    return logs.filter((l) => l.date >= cutoff).length;
  }, [logs]);

  const isLoading = checkinsLoading || logsLoading;

  if (isLoading) {
    return <div className="text-muted-foreground">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Today</h1>

      {/* Readiness Hero Card */}
      {todayCheckin ? (
        <div
          className={`rounded-xl border p-6 ${bandColor(todayCheckin.readiness_band)}`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium opacity-80">
                Today's Readiness
              </p>
              <p className="text-4xl font-bold">
                {todayCheckin.readiness_score}
              </p>
              <p className="mt-1 text-sm capitalize">
                {todayCheckin.readiness_band}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
              <span>
                Sleep: <strong>{todayCheckin.sleep}</strong>/5
              </span>
              <span>
                Energy: <strong>{todayCheckin.energy}</strong>/5
              </span>
              <span>
                Recovery: <strong>{todayCheckin.recovery}</strong>/5
              </span>
              <span>
                Stress: <strong>{todayCheckin.stress}</strong>/5
              </span>
            </div>
          </div>
        </div>
      ) : (
        <Card>
          <CardContent className="flex items-center justify-between p-6">
            <div>
              <p className="font-medium">No check-in yet today</p>
              <p className="text-sm text-muted-foreground">
                Start your day with a quick check-in
              </p>
            </div>
            <Button asChild>
              <Link to="/athlete/checkin">Check In Now</Link>
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Quick Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-blue-600">
              <ClipboardCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Check-In</p>
              <p className="text-lg font-bold">
                {todayCheckin ? "Done" : "Pending"}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-emerald-600">
              <Dumbbell className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Today's Session</p>
              <p className="text-lg font-bold">
                {briefing?.today_logged ? "Logged" : "Not yet"}
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-violet-600">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Sessions (7d)</p>
              <p className="text-lg font-bold">{recentSessionCount}</p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-amber-600">
              <Gauge className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">A:C Ratio</p>
              <p className="text-lg font-bold">
                {briefing ? briefing.acute_chronic_ratio.toFixed(2) : "—"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Session Briefing */}
      {!briefingLoading && briefing && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Zap className="h-5 w-5 text-amber-500" />
              Session Briefing
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Physiological Anchors */}
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {briefing.vdot && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">VDOT</p>
                  <p className="text-lg font-bold">{briefing.vdot}</p>
                </div>
              )}
              {briefing.phase && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Training Phase</p>
                  <p className="text-lg font-bold">{briefing.phase}</p>
                </div>
              )}
              {briefing.threshold_pace && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Threshold Pace</p>
                  <p className="text-lg font-bold">{briefing.threshold_pace}</p>
                </div>
              )}
              {briefing.easy_pace && (
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Easy Pace</p>
                  <p className="text-lg font-bold">{briefing.easy_pace}</p>
                </div>
              )}
            </div>

            {/* Planned Session */}
            {briefing.planned_session_name ? (
              <div className="space-y-3">
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
                  <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800">
                    {briefing.adaptation_reason}
                  </div>
                )}

                {/* Adapted Blocks */}
                {briefing.adapted_blocks.length > 0 && (
                  <div className="overflow-auto rounded-lg border">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b bg-muted/50">
                          <th className="p-2 text-left font-medium">Phase</th>
                          <th className="p-2 text-left font-medium">Duration</th>
                          <th className="p-2 text-left font-medium">Target</th>
                          <th className="p-2 text-left font-medium">RPE</th>
                        </tr>
                      </thead>
                      <tbody>
                        {briefing.adapted_blocks.map((block, i) => {
                          const target = block.target as Record<string, unknown> | undefined;
                          const intervals = block.intervals as Record<string, unknown>[] | undefined;
                          return (
                            <tr key={i} className="border-b last:border-0">
                              <td className="p-2 capitalize">{String(block.phase ?? "—")}</td>
                              <td className="p-2">{String(block.duration_min ?? "—")} min</td>
                              <td className="p-2">
                                {target?.pace_display
                                  ? String(target.pace_display) + "/km"
                                  : target?.pace_label
                                    ? paceLabel(String(target.pace_label))
                                    : target?.pace_zone
                                      ? String(target.pace_zone)
                                      : "—"}
                              </td>
                              <td className="p-2">
                                {Array.isArray(target?.rpe_range)
                                  ? `${(target.rpe_range as number[])[0]}-${(target.rpe_range as number[])[1]}`
                                  : "—"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}

                {/* Interval Details */}
                {briefing.adapted_blocks.some((b) => Array.isArray(b.intervals) && (b.intervals as unknown[]).length > 0) && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-muted-foreground">Interval Details</p>
                    {briefing.adapted_blocks
                      .filter((b) => Array.isArray(b.intervals) && (b.intervals as unknown[]).length > 0)
                      .map((block, i) => (
                        <div key={i} className="rounded-lg border p-3 space-y-1">
                          <p className="text-sm font-medium capitalize">{String(block.phase)}</p>
                          {(block.intervals as Record<string, unknown>[]).map((ivl, j) => (
                            <div key={j} className="flex items-center gap-3 text-sm text-muted-foreground">
                              <span>{String(ivl.reps ?? 1)}x</span>
                              <span>{String(ivl.work_duration_min ?? "?")} min work</span>
                              {ivl.work_pace_display && (
                                <Badge variant="outline">{String(ivl.work_pace_display)}/km</Badge>
                              )}
                              <span>{String(ivl.recovery_duration_min ?? "?")} min rec</span>
                            </div>
                          ))}
                        </div>
                      ))}
                  </div>
                )}

                {briefing.coaching_notes && (
                  <div className="rounded-lg bg-blue-50 p-3 text-sm text-blue-800">
                    <strong>Coach Notes:</strong> {briefing.coaching_notes}
                  </div>
                )}
              </div>
            ) : (
              <div className="rounded-lg border-2 border-dashed p-6 text-center text-muted-foreground">
                <p>No session planned for today</p>
                <p className="text-sm">Check your training plan or log a freestyle session</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Training Load Summary */}
      {!loadLoading && loadSummary?.has_data && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Flame className="h-5 w-5 text-orange-500" />
              Training Load (30d)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Monotony</p>
                <p className="text-lg font-bold">{loadSummary.monotony.toFixed(2)}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Strain</p>
                <p className="text-lg font-bold">{loadSummary.strain.toFixed(0)}</p>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Risk Level</p>
                <div className="flex items-center gap-2">
                  {loadSummary.risk_level === "high" ? (
                    <AlertTriangle className={`h-4 w-4 ${riskColor(loadSummary.risk_level)}`} />
                  ) : (
                    <CheckCircle2 className={`h-4 w-4 ${riskColor(loadSummary.risk_level)}`} />
                  )}
                  <Badge variant={riskVariant(loadSummary.risk_level)}>
                    {loadSummary.risk_level}
                  </Badge>
                </div>
              </div>
              <div className="rounded-lg border p-3">
                <p className="text-xs text-muted-foreground">Total Load</p>
                <p className="text-lg font-bold">{loadSummary.total_load.toFixed(0)}</p>
                <p className="text-xs text-muted-foreground">{loadSummary.session_count} sessions</p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Check-ins */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Check-Ins</CardTitle>
          </CardHeader>
          <CardContent>
            {checkins && checkins.length > 0 ? (
              <div className="space-y-2">
                {checkins.map((c) => (
                  <div
                    key={c.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <span className="text-sm">{c.day}</span>
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {c.readiness_score}
                      </span>
                      <Badge variant={bandVariant(c.readiness_band)}>
                        {c.readiness_band}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No check-ins yet
              </p>
            )}
          </CardContent>
        </Card>

        {/* Recent Training Logs */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-base">Recent Sessions</CardTitle>
            <Button variant="ghost" size="sm" asChild>
              <Link to="/athlete/analytics">
                View Analytics <ChevronRight className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          </CardHeader>
          <CardContent>
            {logs && logs.length > 0 ? (
              <div className="space-y-2">
                {logs.map((l) => (
                  <div
                    key={l.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="space-y-0.5">
                      <p className="text-sm font-medium">
                        {l.session_category}
                      </p>
                      <p className="text-xs text-muted-foreground">{l.date}</p>
                    </div>
                    <div className="flex items-center gap-3 text-sm">
                      <span>{l.duration_min}min</span>
                      <span>{l.distance_km}km</span>
                      <Badge
                        variant={
                          l.rpe >= 8
                            ? "danger"
                            : l.rpe >= 5
                              ? "warning"
                              : "success"
                        }
                      >
                        RPE {l.rpe}
                      </Badge>
                      {l.pain_flag && (
                        <Badge variant="destructive">Pain</Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="py-6 text-center text-sm text-muted-foreground">
                No sessions logged yet
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
