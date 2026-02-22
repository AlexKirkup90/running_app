import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  fetchCoachClients,
  fetchCoachDashboard,
  fetchInterventionStats,
} from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DashboardSkeleton } from "@/components/ui/skeleton";
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
  Legend,
} from "recharts";
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Flame,
  Users,
  TrendingUp,
} from "lucide-react";

const RISK_COLORS: Record<string, string> = {
  low: "#10b981",
  moderate: "#f59e0b",
  high: "#ef4444",
};

function riskVariant(level: string) {
  if (level === "low") return "success" as const;
  if (level === "moderate") return "warning" as const;
  return "danger" as const;
}

export function CoachAnalytics() {
  const { data: dashboard, isLoading: dashLoading } = useQuery({
    queryKey: ["coach-dashboard"],
    queryFn: fetchCoachDashboard,
  });

  const { data: clients, isLoading: clientsLoading } = useQuery({
    queryKey: ["coach-clients"],
    queryFn: fetchCoachClients,
  });

  const { data: interventionStats } = useQuery({
    queryKey: ["intervention-stats"],
    queryFn: fetchInterventionStats,
  });

  // Risk distribution
  const riskDistribution = useMemo(() => {
    if (!clients?.length) return [];
    let low = 0, moderate = 0, high = 0;
    for (const c of clients) {
      if (c.risk_label === "low") low++;
      else if (c.risk_label === "moderate") moderate++;
      else high++;
    }
    return [
      { name: "Low Risk", value: low, color: RISK_COLORS.low },
      { name: "Moderate Risk", value: moderate, color: RISK_COLORS.moderate },
      { name: "High Risk", value: high, color: RISK_COLORS.high },
    ].filter((d) => d.value > 0);
  }, [clients]);

  // Engagement tracker
  const engagement = useMemo(() => {
    if (!clients?.length) return { checkedInToday: 0, loggedToday: 0, inactive: 0 };
    const today = new Date().toISOString().slice(0, 10);
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    const cutoff = weekAgo.toISOString().slice(0, 10);

    let checkedInToday = 0, loggedToday = 0, inactive = 0;
    for (const c of clients) {
      if (c.last_checkin === today) checkedInToday++;
      if (c.last_log === today) loggedToday++;
      if (!c.last_log || c.last_log < cutoff) inactive++;
    }
    return { checkedInToday, loggedToday, inactive };
  }, [clients]);

  // Weekly volume chart
  const weeklyVolume = useMemo(() => {
    if (!dashboard?.weekly_load?.length) return [];
    return dashboard.weekly_load.map((w) => ({
      week: w.week.slice(5),
      duration: w.duration_min,
      load: w.load_score,
      sessions: w.sessions,
    }));
  }, [dashboard]);

  // Athletes needing attention
  const needsAttention = useMemo(() => {
    if (!clients?.length) return [];
    return clients
      .filter((c) => c.risk_label === "high" || c.open_interventions > 0)
      .sort((a, b) => b.open_interventions - a.open_interventions)
      .slice(0, 10);
  }, [clients]);

  if (dashLoading || clientsLoading) return <DashboardSkeleton />;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Portfolio Analytics</h1>
        <p className="text-muted-foreground">Overview of your entire athlete roster</p>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-blue-100 p-2 text-blue-600">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Total Athletes</p>
              <p className="text-2xl font-bold">{dashboard?.total_athletes ?? 0}</p>
              <p className="text-xs text-muted-foreground">{dashboard?.active_athletes ?? 0} active</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-amber-100 p-2 text-amber-600">
              <AlertTriangle className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Open Interventions</p>
              <p className="text-2xl font-bold">{interventionStats?.open_count ?? dashboard?.open_interventions ?? 0}</p>
              <p className="text-xs text-muted-foreground">{interventionStats?.high_priority ?? 0} high priority</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-emerald-100 p-2 text-emerald-600">
              <CheckCircle2 className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">Check-Ins Today</p>
              <p className="text-2xl font-bold">{engagement.checkedInToday}</p>
              <p className="text-xs text-muted-foreground">of {clients?.length ?? 0} athletes</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-red-100 p-2 text-red-600">
              <Flame className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">High Risk</p>
              <p className="text-2xl font-bold">{dashboard?.high_risk_count ?? 0}</p>
              <p className="text-xs text-muted-foreground">{engagement.inactive} inactive 7d+</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Risk Distribution */}
        {riskDistribution.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Risk Distribution</CardTitle>
            </CardHeader>
            <CardContent className="flex items-center justify-center">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={riskDistribution}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={90}
                    label={({ name, value }) => `${name}: ${value}`}
                  >
                    {riskDistribution.map((d, i) => (
                      <Cell key={i} fill={d.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        )}

        {/* SLA & Intervention Health */}
        {interventionStats && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Intervention Health</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Actionable Now</p>
                  <p className="text-xl font-bold text-emerald-600">{interventionStats.actionable_now}</p>
                </div>
                <div className="rounded-lg border p-3">
                  <p className="text-xs text-muted-foreground">Snoozed</p>
                  <p className="text-xl font-bold text-muted-foreground">{interventionStats.snoozed}</p>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="flex items-center gap-2">
                    <Clock className="h-3 w-3 text-amber-500" />
                    <p className="text-xs text-muted-foreground">Due &lt; 24h</p>
                  </div>
                  <p className="text-xl font-bold text-amber-600">{interventionStats.sla_due_24h}</p>
                </div>
                <div className="rounded-lg border p-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-3 w-3 text-red-500" />
                    <p className="text-xs text-muted-foreground">Due &lt; 72h</p>
                  </div>
                  <p className="text-xl font-bold text-red-600">{interventionStats.sla_due_72h}</p>
                </div>
              </div>
              <div className="mt-4 flex gap-4 text-sm text-muted-foreground">
                <span>Median age: {interventionStats.median_age_hours.toFixed(0)}h</span>
                <span>Oldest: {interventionStats.oldest_age_hours.toFixed(0)}h</span>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Weekly Volume Chart */}
      {weeklyVolume.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <TrendingUp className="h-5 w-5 text-blue-500" />
              Aggregate Weekly Volume
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={weeklyVolume}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="week" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="left" tick={{ fontSize: 12 }} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar yAxisId="left" dataKey="duration" name="Duration (min)" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                <Bar yAxisId="right" dataKey="sessions" name="Sessions" fill="#10b981" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {/* Needs Attention */}
      {needsAttention.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Activity className="h-5 w-5 text-red-500" />
              Needs Attention
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {needsAttention.map((c) => (
                <Link
                  key={c.athlete_id}
                  to={`/coach/clients/${c.athlete_id}`}
                  className="flex items-center justify-between rounded-lg border p-3 transition-colors hover:bg-accent/50"
                >
                  <div>
                    <p className="text-sm font-medium">
                      {c.first_name} {c.last_name}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Last check-in: {c.last_checkin ?? "never"} | Last log: {c.last_log ?? "never"}
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={riskVariant(c.risk_label)}>{c.risk_label}</Badge>
                    {c.open_interventions > 0 && (
                      <Badge variant="warning">{c.open_interventions} flags</Badge>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
