import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Lock,
  Unlock,
  RefreshCw,
  ArrowRightLeft,
  Eye,
  Save,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { useAthletes } from "@/hooks/useInterventions";
import { usePlans, usePlanWeeks, usePlanSessions } from "@/hooks/usePlans";
import {
  usePreviewPlan,
  useCreatePlan,
  useToggleWeekLock,
  useSwapSession,
  useRegenerateWeek,
} from "@/hooks/usePlanBuilder";
import type { PlanPreview, PlanDaySession } from "@/api/types";

const RACE_GOALS = ["5K", "10K", "Half Marathon", "Marathon"];

const PHASE_COLORS: Record<string, string> = {
  Base: "bg-blue-100 text-blue-800",
  Build: "bg-amber-100 text-amber-800",
  Peak: "bg-red-100 text-red-800",
  Taper: "bg-green-100 text-green-800",
  Recovery: "bg-gray-100 text-gray-700",
};

export function CoachPlanBuilder() {
  // --- Tab state ---
  const [tab, setTab] = useState<"create" | "manage">("create");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Plan Builder</h1>

      <div className="flex gap-2 border-b pb-2">
        <button
          className={`px-4 py-2 text-sm font-medium rounded-t-md ${tab === "create" ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground"}`}
          onClick={() => setTab("create")}
        >
          Create Plan
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium rounded-t-md ${tab === "manage" ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground"}`}
          onClick={() => setTab("manage")}
        >
          Manage Weeks
        </button>
      </div>

      {tab === "create" ? <CreatePlanTab /> : <ManageWeeksTab />}
    </div>
  );
}

// ==========================================================================
// Create Plan Tab
// ==========================================================================

function CreatePlanTab() {
  const { data: athletes } = useAthletes();
  const previewMutation = usePreviewPlan();
  const createMutation = useCreatePlan();

  const [athleteId, setAthleteId] = useState(0);
  const [raceGoal, setRaceGoal] = useState("5K");
  const [weeks, setWeeks] = useState(12);
  const [sessionsPerWeek, setSessionsPerWeek] = useState(4);
  const [maxSessionMin, setMaxSessionMin] = useState(120);
  const [startDate, setStartDate] = useState(
    new Date().toISOString().split("T")[0] as string,
  );
  const [preview, setPreview] = useState<PlanPreview | null>(null);

  const formData = {
    athlete_id: athleteId,
    race_goal: raceGoal,
    weeks,
    sessions_per_week: sessionsPerWeek,
    max_session_min: maxSessionMin,
    start_date: startDate,
  };

  const handlePreview = () => {
    if (!athleteId) return;
    previewMutation.mutate(formData, {
      onSuccess: (data) => setPreview(data),
    });
  };

  const handleCreate = () => {
    if (!athleteId) return;
    createMutation.mutate(formData, {
      onSuccess: () => {
        setPreview(null);
      },
    });
  };

  return (
    <div className="space-y-6">
      {/* Form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Plan Parameters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Athlete
              </label>
              <Select
                value={String(athleteId)}
                onChange={(e) => setAthleteId(Number(e.target.value))}
              >
                <option value="0">Select athlete...</option>
                {athletes?.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.first_name} {a.last_name}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Race Goal
              </label>
              <Select
                value={raceGoal}
                onChange={(e) => setRaceGoal(e.target.value)}
              >
                {RACE_GOALS.map((g) => (
                  <option key={g} value={g}>
                    {g}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Weeks
              </label>
              <Input
                type="number"
                min={4}
                max={52}
                value={weeks}
                onChange={(e) => setWeeks(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Sessions/Week
              </label>
              <Input
                type="number"
                min={2}
                max={7}
                value={sessionsPerWeek}
                onChange={(e) => setSessionsPerWeek(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Max Session (min)
              </label>
              <Input
                type="number"
                min={30}
                max={300}
                value={maxSessionMin}
                onChange={(e) => setMaxSessionMin(Number(e.target.value))}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">
                Start Date
              </label>
              <Input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
              />
            </div>
          </div>

          <div className="mt-4 flex gap-3">
            <Button
              variant="outline"
              disabled={!athleteId || previewMutation.isPending}
              onClick={handlePreview}
            >
              <Eye className="mr-2 h-4 w-4" />
              {previewMutation.isPending ? "Generating..." : "Preview"}
            </Button>
            <Button
              disabled={!athleteId || !preview || createMutation.isPending}
              onClick={handleCreate}
            >
              <Save className="mr-2 h-4 w-4" />
              {createMutation.isPending ? "Creating..." : "Create Plan"}
            </Button>
          </div>

          {createMutation.isSuccess && (
            <div className="mt-3 rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
              Plan created successfully (ID: {createMutation.data.plan_id})
            </div>
          )}
          {createMutation.isError && (
            <div className="mt-3 rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
              {(createMutation.error as Error).message}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Preview */}
      {preview && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              Preview: {preview.weeks.length} weeks, {preview.days.length} sessions
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {preview.weeks.map((week) => {
                const weekDays = preview.days.filter(
                  (d) => d.week_number === week.week_number,
                );
                return (
                  <div key={week.week_number} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium">
                          Week {week.week_number}
                        </span>
                        <Badge
                          className={PHASE_COLORS[week.phase] ?? ""}
                          variant="secondary"
                        >
                          {week.phase}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          Load: {week.target_load}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground">
                        {week.week_start} — {week.week_end}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {weekDays.map((d, i) => (
                        <Badge key={i} variant="outline" className="text-xs">
                          {d.session_day.slice(5)}: {d.session_name}
                        </Badge>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ==========================================================================
// Manage Weeks Tab
// ==========================================================================

function ManageWeeksTab() {
  const { data: athletes } = useAthletes();
  const [athleteId, setAthleteId] = useState(0);
  const { data: plans } = usePlans(athleteId || undefined, "active");
  const activePlan = plans?.[0];
  const { data: planWeeks, isLoading: weeksLoading } = usePlanWeeks(
    activePlan?.id ?? 0,
  );
  const { data: planSessions } = usePlanSessions(activePlan?.id ?? 0);

  const lockMutation = useToggleWeekLock();
  const swapMutation = useSwapSession();
  const regenMutation = useRegenerateWeek();

  const [expandedWeek, setExpandedWeek] = useState<number | null>(null);
  const [swapDay, setSwapDay] = useState("");
  const [swapName, setSwapName] = useState("");

  const sessionsByWeek = useMemo(() => {
    const map = new Map<number, PlanDaySession[]>();
    if (planSessions && planWeeks) {
      for (const pw of planWeeks) {
        map.set(
          pw.week_number,
          planSessions
            .filter((s) => s.plan_week_id === pw.id)
            .sort(
              (a, b) =>
                new Date(a.session_day).getTime() -
                new Date(b.session_day).getTime(),
            ),
        );
      }
    }
    return map;
  }, [planSessions, planWeeks]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-4">
        <Select
          value={String(athleteId)}
          onChange={(e) => setAthleteId(Number(e.target.value))}
          className="w-64"
        >
          <option value="0">Select athlete...</option>
          {athletes?.map((a) => (
            <option key={a.id} value={a.id}>
              {a.first_name} {a.last_name}
            </option>
          ))}
        </Select>
        {activePlan && (
          <span className="text-sm text-muted-foreground">
            Plan #{activePlan.id} — {activePlan.race_goal} — {activePlan.weeks} wk
          </span>
        )}
      </div>

      {!activePlan && athleteId > 0 && (
        <p className="text-sm text-muted-foreground">
          No active plan. Use the Create tab to build one.
        </p>
      )}

      {weeksLoading && (
        <p className="text-sm text-muted-foreground">Loading weeks...</p>
      )}

      {planWeeks && planWeeks.length > 0 && (
        <div className="space-y-2">
          {planWeeks.map((week) => {
            const isExpanded = expandedWeek === week.week_number;
            const weekSessions = sessionsByWeek.get(week.week_number) ?? [];
            return (
              <div key={week.id} className="rounded-lg border bg-card">
                {/* Header */}
                <button
                  type="button"
                  className="flex w-full items-center justify-between p-3 text-left"
                  onClick={() =>
                    setExpandedWeek(isExpanded ? null : week.week_number)
                  }
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">
                      Week {week.week_number}
                    </span>
                    <Badge
                      className={PHASE_COLORS[week.phase] ?? ""}
                      variant="secondary"
                    >
                      {week.phase}
                    </Badge>
                    {week.locked && (
                      <Lock className="h-3.5 w-3.5 text-amber-500" />
                    )}
                    <span className="text-xs text-muted-foreground">
                      {week.week_start} — {week.week_end}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      Load: {week.target_load}
                    </span>
                    {isExpanded ? (
                      <ChevronUp className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </button>

                {/* Expanded */}
                {isExpanded && (
                  <div className="space-y-3 border-t px-4 pb-4 pt-3">
                    {/* Actions */}
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          lockMutation.mutate({
                            planId: activePlan!.id,
                            weekNumber: week.week_number,
                          })
                        }
                        disabled={lockMutation.isPending}
                      >
                        {week.locked ? (
                          <Unlock className="mr-1.5 h-3.5 w-3.5" />
                        ) : (
                          <Lock className="mr-1.5 h-3.5 w-3.5" />
                        )}
                        {week.locked ? "Unlock" : "Lock"}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() =>
                          regenMutation.mutate({
                            planId: activePlan!.id,
                            weekNumber: week.week_number,
                          })
                        }
                        disabled={regenMutation.isPending || week.locked}
                      >
                        <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                        Regenerate
                      </Button>
                    </div>

                    {regenMutation.isSuccess && (
                      <div className="rounded bg-emerald-50 px-3 py-1 text-xs text-emerald-700">
                        {regenMutation.data.message}
                      </div>
                    )}

                    {/* Sessions table */}
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-xs text-muted-foreground">
                          <th className="pb-1">Day</th>
                          <th className="pb-1">Session</th>
                          <th className="pb-1">Status</th>
                          <th className="pb-1" />
                        </tr>
                      </thead>
                      <tbody>
                        {weekSessions.map((sess) => (
                          <tr key={sess.id} className="border-t">
                            <td className="py-1.5">{sess.session_day}</td>
                            <td className="py-1.5">{sess.session_name}</td>
                            <td className="py-1.5">
                              <Badge variant="outline" className="text-xs">
                                {sess.status}
                              </Badge>
                            </td>
                            <td className="py-1.5 text-right">
                              {!week.locked && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="h-6 text-xs"
                                  onClick={() => {
                                    setSwapDay(sess.session_day);
                                    setSwapName(sess.session_name);
                                  }}
                                >
                                  <ArrowRightLeft className="mr-1 h-3 w-3" />
                                  Swap
                                </Button>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>

                    {/* Swap inline form */}
                    {swapDay && !week.locked && (
                      <div className="flex items-end gap-2 rounded bg-muted/50 p-2">
                        <div className="flex-1">
                          <label className="mb-1 block text-xs text-muted-foreground">
                            Swap {swapDay} session to:
                          </label>
                          <Input
                            value={swapName}
                            onChange={(e) => setSwapName(e.target.value)}
                            placeholder="New session name"
                          />
                        </div>
                        <Button
                          size="sm"
                          onClick={() => {
                            swapMutation.mutate(
                              {
                                planId: activePlan!.id,
                                weekNumber: week.week_number,
                                sessionDay: swapDay,
                                newSessionName: swapName,
                              },
                              { onSuccess: () => setSwapDay("") },
                            );
                          }}
                          disabled={swapMutation.isPending}
                        >
                          Confirm
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          onClick={() => setSwapDay("")}
                        >
                          Cancel
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
