import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { fetchCoachDashboard, fetchInterventions } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Users, AlertTriangle, Activity, TrendingUp } from "lucide-react";

function riskVariant(score: number) {
  if (score >= 0.7) return "danger" as const;
  if (score >= 0.4) return "warning" as const;
  return "success" as const;
}

export function CoachDashboard() {
  const { data: dashboard, isLoading } = useQuery({
    queryKey: ["coach-dashboard"],
    queryFn: fetchCoachDashboard,
  });

  const { data: interventions } = useQuery({
    queryKey: ["interventions", "open"],
    queryFn: () => fetchInterventions("open"),
  });

  if (isLoading) {
    return <div className="text-muted-foreground">Loading dashboard...</div>;
  }

  const stats = [
    {
      label: "Total Athletes",
      value: dashboard?.total_athletes ?? 0,
      icon: Users,
      color: "text-blue-600",
    },
    {
      label: "Active Athletes",
      value: dashboard?.active_athletes ?? 0,
      icon: Activity,
      color: "text-emerald-600",
    },
    {
      label: "Open Interventions",
      value: dashboard?.open_interventions ?? 0,
      icon: AlertTriangle,
      color: "text-amber-600",
    },
    {
      label: "High Risk",
      value: dashboard?.high_risk_count ?? 0,
      icon: TrendingUp,
      color: "text-red-600",
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Coach Dashboard</h1>

      {/* Stat Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map(({ label, value, icon: Icon, color }) => (
          <Card key={label}>
            <CardContent className="flex items-center gap-4 p-6">
              <div className={`rounded-lg bg-muted p-2 ${color}`}>
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">{label}</p>
                <p className="text-2xl font-bold">{value}</p>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Weekly Load Chart */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Weekly Training Load</CardTitle>
          </CardHeader>
          <CardContent>
            {dashboard?.weekly_load && dashboard.weekly_load.length > 0 ? (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={dashboard.weekly_load}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-border" />
                  <XAxis
                    dataKey="week"
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v: string) => v.slice(5)}
                  />
                  <YAxis tick={{ fontSize: 11 }} />
                  <Tooltip />
                  <Bar dataKey="load_score" fill="hsl(220, 70%, 50%)" radius={[4, 4, 0, 0]} name="Load" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No training data yet
              </p>
            )}
          </CardContent>
        </Card>

        {/* Open Interventions */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Open Interventions</CardTitle>
          </CardHeader>
          <CardContent>
            {interventions && interventions.length > 0 ? (
              <div className="space-y-3">
                {interventions.slice(0, 8).map((intv) => (
                  <div
                    key={intv.id}
                    className="flex items-center justify-between rounded-lg border p-3"
                  >
                    <div className="space-y-1">
                      <p className="text-sm font-medium">
                        Athlete #{intv.athlete_id}
                      </p>
                      <p className="text-xs text-muted-foreground">
                        {intv.action_type}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={riskVariant(intv.risk_score)}>
                        {(intv.risk_score * 100).toFixed(0)}%
                      </Badge>
                      {!intv.guardrail_pass && (
                        <Badge variant="destructive">Blocked</Badge>
                      )}
                    </div>
                  </div>
                ))}
                {interventions.length > 8 && (
                  <p className="text-center text-xs text-muted-foreground">
                    +{interventions.length - 8} more
                  </p>
                )}
              </div>
            ) : (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No open interventions
              </p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
