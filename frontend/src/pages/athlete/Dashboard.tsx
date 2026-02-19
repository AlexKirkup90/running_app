import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";
import { useCheckins, useTrainingLogs } from "@/hooks/useAthlete";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Activity,
  ClipboardCheck,
  Dumbbell,
} from "lucide-react";

function bandColor(band: string | null) {
  if (band === "green") return "bg-emerald-50 border-emerald-200 text-emerald-800";
  if (band === "amber") return "bg-amber-50 border-amber-200 text-amber-800";
  return "bg-red-50 border-red-200 text-red-800";
}

function bandVariant(band: string | null) {
  if (band === "green") return "success" as const;
  if (band === "amber") return "warning" as const;
  return "danger" as const;
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

  const today = new Date().toISOString().slice(0, 10);

  const todayCheckin = useMemo(
    () => checkins?.find((c) => c.day === today) ?? null,
    [checkins, today],
  );

  const todayLog = useMemo(
    () => logs?.find((l) => l.date === today) ?? null,
    [logs, today],
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
        {/* Quick Stats */}
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
                {todayLog ? "Logged" : "Not yet"}
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
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Training Today</p>
              <p className="text-lg font-bold">
                {todayCheckin?.training_today ? "Yes" : "—"}
              </p>
            </div>
          </CardContent>
        </Card>
      </div>

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
          <CardHeader>
            <CardTitle className="text-base">Recent Sessions</CardTitle>
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
                      <Badge variant={l.rpe >= 8 ? "danger" : l.rpe >= 5 ? "warning" : "success"}>
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
