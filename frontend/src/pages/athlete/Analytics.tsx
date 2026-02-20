import { useMemo } from "react";
import { useAuthStore } from "@/stores/auth";
import { useCheckins, useTrainingLogs } from "@/hooks/useAthlete";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
  Legend,
} from "recharts";
import { Activity, Clock, Flame, TrendingUp } from "lucide-react";

const COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899"];

function formatPace(secPerKm: number | null) {
  if (!secPerKm) return "—";
  const min = Math.floor(secPerKm / 60);
  const sec = Math.round(secPerKm % 60);
  return `${min}:${sec.toString().padStart(2, "0")}`;
}

export function AthleteAnalytics() {
  const { athleteId } = useAuthStore();
  const { data: logs, isLoading: logsLoading } = useTrainingLogs(
    athleteId ?? 0,
    90,
  );
  const { data: checkins, isLoading: checkinsLoading } = useCheckins(
    athleteId ?? 0,
    30,
  );

  // Weekly aggregation
  const weeklyData = useMemo(() => {
    if (!logs || logs.length === 0) return [];
    const weeks = new Map<string, { duration: number; load: number; sessions: number; distance: number }>();
    for (const log of logs) {
      const d = new Date(log.date);
      const dayOfWeek = d.getDay();
      const monday = new Date(d);
      monday.setDate(d.getDate() - ((dayOfWeek + 6) % 7));
      const key = monday.toISOString().slice(0, 10);
      const entry = weeks.get(key) ?? { duration: 0, load: 0, sessions: 0, distance: 0 };
      entry.duration += log.duration_min;
      entry.load += log.load_score;
      entry.sessions += 1;
      entry.distance += log.distance_km;
      weeks.set(key, entry);
    }
    return Array.from(weeks.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([week, data]) => ({
        week: week.slice(5),
        ...data,
      }));
  }, [logs]);

  // Category distribution (volume by category)
  const categoryData = useMemo(() => {
    if (!logs || logs.length === 0) return [];
    const cats = new Map<string, number>();
    let total = 0;
    for (const log of logs) {
      const cur = cats.get(log.session_category) ?? 0;
      cats.set(log.session_category, cur + log.duration_min);
      total += log.duration_min;
    }
    return Array.from(cats.entries()).map(([name, value]) => ({
      name,
      value: Math.round((value / total) * 100),
      minutes: value,
    }));
  }, [logs]);

  // Intensity distribution (by RPE)
  const intensityData = useMemo(() => {
    if (!logs || logs.length === 0) return [];
    let easy = 0, moderate = 0, hard = 0;
    for (const log of logs) {
      if (log.rpe <= 4) easy += log.duration_min;
      else if (log.rpe <= 7) moderate += log.duration_min;
      else hard += log.duration_min;
    }
    const total = easy + moderate + hard;
    if (total === 0) return [];
    return [
      { name: "Easy (1-4)", value: Math.round((easy / total) * 100), minutes: easy },
      { name: "Moderate (5-7)", value: Math.round((moderate / total) * 100), minutes: moderate },
      { name: "Hard (8-10)", value: Math.round((hard / total) * 100), minutes: hard },
    ];
  }, [logs]);

  // Readiness trend
  const readinessTrend = useMemo(() => {
    if (!checkins || checkins.length === 0) return [];
    return [...checkins]
      .sort((a, b) => a.day.localeCompare(b.day))
      .map((c) => ({
        day: c.day.slice(5),
        score: c.readiness_score ?? 0,
      }));
  }, [checkins]);

  // Summary stats
  const stats = useMemo(() => {
    if (!logs || logs.length === 0) {
      return { totalSessions: 0, totalDuration: 0, totalDistance: 0, avgPace: null };
    }
    const totalSessions = logs.length;
    const totalDuration = logs.reduce((s, l) => s + l.duration_min, 0);
    const totalDistance = logs.reduce((s, l) => s + l.distance_km, 0);
    const paced = logs.filter((l) => l.avg_pace_sec_per_km);
    const avgPace = paced.length > 0
      ? paced.reduce((s, l) => s + (l.avg_pace_sec_per_km ?? 0), 0) / paced.length
      : null;
    return { totalSessions, totalDuration, totalDistance: Math.round(totalDistance * 10) / 10, avgPace };
  }, [logs]);

  const isLoading = logsLoading || checkinsLoading;

  if (isLoading) {
    return <div className="text-muted-foreground">Loading analytics...</div>;
  }

  if (!logs || logs.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>
        <Card>
          <CardContent className="py-12 text-center">
            <TrendingUp className="mx-auto h-10 w-10 text-muted-foreground" />
            <p className="mt-3 font-medium">No training data yet</p>
            <p className="text-sm text-muted-foreground">
              Log some sessions to see your analytics
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Analytics</h1>

      {/* Summary stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-blue-600">
              <Activity className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Sessions</p>
              <p className="text-lg font-bold">{stats.totalSessions}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-emerald-600">
              <Clock className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Duration</p>
              <p className="text-lg font-bold">{Math.round(stats.totalDuration / 60)}h {stats.totalDuration % 60}m</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-amber-600">
              <TrendingUp className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Distance</p>
              <p className="text-lg font-bold">{stats.totalDistance} km</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-violet-600">
              <Flame className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Avg Pace</p>
              <p className="text-lg font-bold">{formatPace(stats.avgPace)} /km</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Weekly Volume Chart */}
      {weeklyData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Weekly Training Volume</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={weeklyData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar yAxisId="left" dataKey="duration" name="Duration (min)" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar yAxisId="right" dataKey="load" name="Load" fill="#f59e0b" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Category Distribution */}
        {categoryData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Volume by Category</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-center">
              <ResponsiveContainer width="100%" height={220}>
                <PieChart>
                  <Pie
                    data={categoryData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ name, value }) => `${name} ${value}%`}
                  >
                    {categoryData.map((_, i) => (
                      <Cell key={i} fill={COLORS[i % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value, name) => [`${value}%`, name]} />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* Intensity Distribution */}
        {intensityData.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Intensity Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {intensityData.map((item, i) => (
                  <div key={item.name}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span>{item.name}</span>
                      <span className="font-medium">{item.value}%</span>
                    </div>
                    <div className="h-3 rounded-full bg-muted">
                      <div
                        className="h-3 rounded-full transition-all"
                        style={{
                          width: `${item.value}%`,
                          backgroundColor: ["#10b981", "#f59e0b", "#ef4444"][i],
                        }}
                      />
                    </div>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex gap-2">
                {intensityData.map((item) => (
                  <Badge key={item.name} variant="outline">
                    {item.name}: {item.minutes}min
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Readiness Trend */}
      {readinessTrend.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Readiness Trend (30d)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={readinessTrend}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="day" tick={{ fontSize: 12 }} />
                <YAxis domain={[1, 5]} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="score"
                  name="Readiness"
                  stroke="#8b5cf6"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
