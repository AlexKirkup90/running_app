import { useState } from "react";
import { useAuthStore } from "@/stores/auth";
import { usePlans, usePlanWeeks, usePlanSessions } from "@/hooks/usePlans";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Calendar, Target } from "lucide-react";

function phaseColor(phase: string) {
  const p = phase.toLowerCase();
  if (p.includes("base")) return "bg-blue-100 text-blue-800";
  if (p.includes("build")) return "bg-amber-100 text-amber-800";
  if (p.includes("peak") || p.includes("race")) return "bg-red-100 text-red-800";
  if (p.includes("taper")) return "bg-emerald-100 text-emerald-800";
  if (p.includes("recovery")) return "bg-violet-100 text-violet-800";
  return "bg-gray-100 text-gray-800";
}

function statusVariant(status: string) {
  if (status === "completed") return "success" as const;
  if (status === "planned") return "secondary" as const;
  return "default" as const;
}

function PlanWeeksDetail({ planId }: { planId: number }) {
  const { data: weeks, isLoading: weeksLoading } = usePlanWeeks(planId);
  const { data: sessions, isLoading: sessionsLoading } = usePlanSessions(planId);

  if (weeksLoading || sessionsLoading) {
    return <p className="py-4 text-sm text-muted-foreground">Loading plan details...</p>;
  }

  if (!weeks || weeks.length === 0) {
    return <p className="py-4 text-sm text-muted-foreground">No weeks scheduled yet.</p>;
  }

  return (
    <div className="space-y-3">
      {weeks.map((week) => {
        const weekSessions = sessions?.filter(
          (s) => s.plan_week_id === week.id,
        ) ?? [];

        return (
          <div key={week.id} className="rounded-lg border p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="font-medium">Week {week.week_number}</span>
                <Badge className={phaseColor(week.phase)}>{week.phase}</Badge>
                {week.locked && (
                  <Badge variant="outline">Locked</Badge>
                )}
              </div>
              <span className="text-sm text-muted-foreground">
                {week.week_start} — {week.week_end}
              </span>
            </div>

            {weekSessions.length > 0 && (
              <div className="mt-3 space-y-1">
                {weekSessions.map((s) => (
                  <div
                    key={s.id}
                    className="flex items-center justify-between rounded border px-3 py-2 text-sm"
                  >
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{s.session_name}</span>
                      <span className="text-xs text-muted-foreground">
                        {s.source_template_name}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-muted-foreground">{s.session_day}</span>
                      <Badge variant={statusVariant(s.status)}>
                        {s.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {weekSessions.length === 0 && (
              <p className="mt-2 text-sm text-muted-foreground">
                No sessions this week
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

export function AthletePlans() {
  const { athleteId } = useAuthStore();
  const [showAll, setShowAll] = useState(false);
  const [expandedPlan, setExpandedPlan] = useState<number | null>(null);

  const status = showAll ? "all" : "active";
  const { data: plans, isLoading } = usePlans(athleteId ?? undefined, status);

  if (isLoading) {
    return <div className="text-muted-foreground">Loading plans...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Training Plans</h1>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowAll(!showAll)}
        >
          {showAll ? "Active Only" : "Show All"}
        </Button>
      </div>

      {!plans || plans.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <Target className="mx-auto h-10 w-10 text-muted-foreground" />
            <p className="mt-3 font-medium">No training plans</p>
            <p className="text-sm text-muted-foreground">
              Your coach hasn't created a plan yet.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {plans.map((plan) => {
            const isExpanded = expandedPlan === plan.id;
            return (
              <Card key={plan.id}>
                <CardHeader
                  className="cursor-pointer"
                  onClick={() => setExpandedPlan(isExpanded ? null : plan.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      {isExpanded ? (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-muted-foreground" />
                      )}
                      <div>
                        <CardTitle className="text-base">
                          {plan.race_goal} Plan
                        </CardTitle>
                        <p className="mt-0.5 text-sm text-muted-foreground">
                          {plan.weeks} weeks &middot; {plan.sessions_per_week} sessions/week &middot; max {plan.max_session_min}min
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Calendar className="h-4 w-4" />
                        {plan.start_date}
                      </div>
                      <Badge
                        variant={plan.status === "active" ? "default" : "secondary"}
                      >
                        {plan.status}
                      </Badge>
                    </div>
                  </div>
                </CardHeader>
                {isExpanded && (
                  <CardContent>
                    <PlanWeeksDetail planId={plan.id} />
                  </CardContent>
                )}
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
