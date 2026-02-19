import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuthStore } from "@/stores/auth";
import { useTrainingLogs, useCreateTrainingLog } from "@/hooks/useAthlete";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

const SESSION_CATEGORIES = [
  "Easy Run",
  "Long Run",
  "Recovery Run",
  "Tempo / Threshold",
  "VO2 Intervals",
  "Hill Repeats",
  "Race Pace",
  "Strides / Neuromuscular",
  "Benchmark / Time Trial",
  "Taper / Openers",
  "Cross-Training Optional",
];

const trainingLogSchema = z
  .object({
    session_category: z.string().min(1, "Required").max(80),
    duration_min: z.coerce.number().int().min(0, "Must be 0 or more"),
    distance_km: z.coerce.number().min(0, "Must be 0 or more"),
    avg_hr: z.coerce
      .number()
      .int()
      .min(30)
      .max(250)
      .nullable()
      .optional()
      .or(z.literal("")),
    max_hr: z.coerce
      .number()
      .int()
      .min(30)
      .max(250)
      .nullable()
      .optional()
      .or(z.literal("")),
    avg_pace_sec_per_km: z.coerce
      .number()
      .min(0)
      .nullable()
      .optional()
      .or(z.literal("")),
    rpe: z.coerce.number().int().min(1).max(10),
    notes: z.string().max(2000).default(""),
    pain_flag: z.boolean().default(false),
  })
  .refine(
    (data) => {
      const avg = typeof data.avg_hr === "number" ? data.avg_hr : null;
      const max = typeof data.max_hr === "number" ? data.max_hr : null;
      if (avg && max) return max >= avg;
      return true;
    },
    { message: "Max HR must be >= Avg HR", path: ["max_hr"] },
  );

type TrainingLogForm = z.infer<typeof trainingLogSchema>;

export function AthleteLog() {
  const { athleteId } = useAuthStore();
  const { data: logs, isLoading } = useTrainingLogs(athleteId ?? 0, 1);
  const mutation = useCreateTrainingLog();

  const today = new Date().toISOString().slice(0, 10);
  const todayLog = useMemo(
    () => logs?.find((l) => l.date === today) ?? null,
    [logs, today],
  );

  const {
    register,
    handleSubmit,
    reset,
    watch,
    setValue,
    formState: { errors },
  } = useForm<TrainingLogForm>({
    resolver: zodResolver(trainingLogSchema),
    defaultValues: {
      session_category: SESSION_CATEGORIES[0],
      duration_min: 45,
      distance_km: 8,
      avg_hr: "",
      max_hr: "",
      avg_pace_sec_per_km: "",
      rpe: 5,
      notes: "",
      pain_flag: false,
    },
  });

  // Pre-fill form if today's log exists
  useEffect(() => {
    if (todayLog) {
      reset({
        session_category: todayLog.session_category,
        duration_min: todayLog.duration_min,
        distance_km: todayLog.distance_km,
        avg_hr: todayLog.avg_hr ?? "",
        max_hr: todayLog.max_hr ?? "",
        avg_pace_sec_per_km: todayLog.avg_pace_sec_per_km ?? "",
        rpe: todayLog.rpe,
        notes: todayLog.notes,
        pain_flag: todayLog.pain_flag,
      });
    }
  }, [todayLog, reset]);

  const rpeValue = watch("rpe");

  const onSubmit = (data: TrainingLogForm) => {
    if (!athleteId) return;
    mutation.mutate({
      athlete_id: athleteId,
      session_category: data.session_category,
      duration_min: data.duration_min,
      distance_km: data.distance_km,
      avg_hr:
        typeof data.avg_hr === "number" && data.avg_hr >= 30
          ? data.avg_hr
          : null,
      max_hr:
        typeof data.max_hr === "number" && data.max_hr >= 30
          ? data.max_hr
          : null,
      avg_pace_sec_per_km:
        typeof data.avg_pace_sec_per_km === "number" &&
        data.avg_pace_sec_per_km > 0
          ? data.avg_pace_sec_per_km
          : null,
      rpe: data.rpe,
      notes: data.notes ?? "",
      pain_flag: data.pain_flag ?? false,
    });
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Log Session</h1>

      {/* Success feedback */}
      {mutation.isSuccess && mutation.data && (
        <div className="rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          Session saved! Load score: {mutation.data.load_score.toFixed(1)}
        </div>
      )}

      {/* Error feedback */}
      {mutation.isError && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
          Failed to save: {(mutation.error as Error).message}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {todayLog ? "Update Today's Session" : "Record Your Training"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
            {/* Session Category */}
            <div className="space-y-1.5">
              <Label htmlFor="session_category">Session Type</Label>
              <Select id="session_category" {...register("session_category")}>
                {SESSION_CATEGORIES.map((cat) => (
                  <option key={cat} value={cat}>
                    {cat}
                  </option>
                ))}
              </Select>
              {errors.session_category && (
                <p className="text-xs text-destructive">
                  {errors.session_category.message}
                </p>
              )}
            </div>

            {/* Duration + Distance row */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="duration_min">Duration (min)</Label>
                <Input
                  id="duration_min"
                  type="number"
                  min={0}
                  {...register("duration_min")}
                />
                {errors.duration_min && (
                  <p className="text-xs text-destructive">
                    {errors.duration_min.message}
                  </p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="distance_km">Distance (km)</Label>
                <Input
                  id="distance_km"
                  type="number"
                  min={0}
                  step={0.1}
                  {...register("distance_km")}
                />
                {errors.distance_km && (
                  <p className="text-xs text-destructive">
                    {errors.distance_km.message}
                  </p>
                )}
              </div>
            </div>

            {/* Heart Rate row */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="avg_hr">Avg HR (optional)</Label>
                <Input
                  id="avg_hr"
                  type="number"
                  min={30}
                  max={250}
                  placeholder="e.g. 145"
                  {...register("avg_hr")}
                />
                {errors.avg_hr && (
                  <p className="text-xs text-destructive">
                    {errors.avg_hr.message}
                  </p>
                )}
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="max_hr">Max HR (optional)</Label>
                <Input
                  id="max_hr"
                  type="number"
                  min={30}
                  max={250}
                  placeholder="e.g. 172"
                  {...register("max_hr")}
                />
                {errors.max_hr && (
                  <p className="text-xs text-destructive">
                    {errors.max_hr.message}
                  </p>
                )}
              </div>
            </div>

            {/* Pace */}
            <div className="space-y-1.5">
              <Label htmlFor="avg_pace_sec_per_km">
                Avg Pace (sec/km, optional)
              </Label>
              <Input
                id="avg_pace_sec_per_km"
                type="number"
                min={0}
                placeholder="e.g. 330 for 5:30/km"
                {...register("avg_pace_sec_per_km")}
              />
            </div>

            {/* RPE */}
            <div className="space-y-2">
              <Label>RPE (Rate of Perceived Exertion)</Label>
              <div className="flex gap-1.5">
                {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((v) => (
                  <button
                    key={v}
                    type="button"
                    onClick={() => setValue("rpe", v)}
                    className={`flex h-10 w-10 items-center justify-center rounded-lg border text-sm font-medium transition-colors ${
                      rpeValue === v
                        ? v <= 4
                          ? "border-emerald-500 bg-emerald-50 text-emerald-700"
                          : v <= 7
                            ? "border-amber-500 bg-amber-50 text-amber-700"
                            : "border-red-500 bg-red-50 text-red-700"
                        : "border-input bg-background text-muted-foreground hover:bg-accent"
                    }`}
                  >
                    {v}
                  </button>
                ))}
              </div>
              <div className="flex justify-between px-1 text-xs text-muted-foreground">
                <span>Easy</span>
                <span>Moderate</span>
                <span>Max effort</span>
              </div>
              {errors.rpe && (
                <p className="text-xs text-destructive">
                  {errors.rpe.message}
                </p>
              )}
            </div>

            {/* Notes */}
            <div className="space-y-1.5">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                rows={3}
                placeholder="How did the session feel? Any observations..."
                {...register("notes")}
              />
              {errors.notes && (
                <p className="text-xs text-destructive">
                  {errors.notes.message}
                </p>
              )}
            </div>

            {/* Pain flag */}
            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="pain_flag"
                {...register("pain_flag")}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="pain_flag" className="text-sm">
                Pain or discomfort during session
              </Label>
            </div>

            <Button
              type="submit"
              disabled={mutation.isPending}
              className="w-full"
            >
              {mutation.isPending
                ? "Saving..."
                : todayLog
                  ? "Update Session"
                  : "Save Session"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
