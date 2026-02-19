import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuthStore } from "@/stores/auth";
import { useCheckins, useCreateCheckin } from "@/hooks/useAthlete";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";

const checkinSchema = z.object({
  sleep: z.number().min(1).max(5),
  energy: z.number().min(1).max(5),
  recovery: z.number().min(1).max(5),
  stress: z.number().min(1).max(5),
  training_today: z.boolean(),
});

type CheckInForm = z.infer<typeof checkinSchema>;

const scaleLabels: Record<string, string[]> = {
  sleep: ["Poor", "Fair", "OK", "Good", "Excellent"],
  energy: ["Drained", "Low", "Moderate", "High", "Surging"],
  recovery: ["Sore", "Stiff", "OK", "Good", "Fresh"],
  stress: ["None", "Low", "Moderate", "High", "Extreme"],
};

function bandVariant(band: string | null) {
  if (band === "green") return "success" as const;
  if (band === "amber") return "warning" as const;
  return "danger" as const;
}

function ScaleSelector({
  name,
  label,
  value,
  onChange,
}: {
  name: string;
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  const labels = scaleLabels[name] ?? [];
  return (
    <div className="space-y-2">
      <Label className="text-sm font-medium">{label}</Label>
      <div className="flex gap-2">
        {[1, 2, 3, 4, 5].map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => onChange(v)}
            className={`flex h-12 w-12 flex-col items-center justify-center rounded-lg border text-sm font-medium transition-colors ${
              value === v
                ? "border-primary bg-primary/10 text-primary"
                : "border-input bg-background text-muted-foreground hover:bg-accent"
            }`}
          >
            <span className="text-base font-bold">{v}</span>
          </button>
        ))}
      </div>
      <div className="flex justify-between px-1 text-xs text-muted-foreground">
        <span>{labels[0]}</span>
        <span>{labels[4]}</span>
      </div>
    </div>
  );
}

export function AthleteCheckIn() {
  const { athleteId } = useAuthStore();
  const { data: checkins, isLoading } = useCheckins(athleteId ?? 0, 1);
  const mutation = useCreateCheckin();

  const today = new Date().toISOString().slice(0, 10);
  const todayCheckin = useMemo(
    () => checkins?.find((c) => c.day === today) ?? null,
    [checkins, today],
  );

  const {
    setValue,
    watch,
    handleSubmit,
    reset,
    formState: { isSubmitting },
  } = useForm<CheckInForm>({
    resolver: zodResolver(checkinSchema),
    defaultValues: {
      sleep: 3,
      energy: 3,
      recovery: 3,
      stress: 3,
      training_today: true,
    },
  });

  // Pre-fill form if today's check-in exists
  useEffect(() => {
    if (todayCheckin) {
      reset({
        sleep: todayCheckin.sleep,
        energy: todayCheckin.energy,
        recovery: todayCheckin.recovery,
        stress: todayCheckin.stress,
        training_today: todayCheckin.training_today,
      });
    }
  }, [todayCheckin, reset]);

  const values = watch();

  const onSubmit = (data: CheckInForm) => {
    if (!athleteId) return;
    mutation.mutate({
      athlete_id: athleteId,
      ...data,
    });
  };

  if (isLoading) {
    return <div className="text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Daily Check-In</h1>

      {/* Success feedback */}
      {mutation.isSuccess && mutation.data && (
        <div className="flex items-center gap-3 rounded-md bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span>Check-in saved!</span>
          <Badge variant={bandVariant(mutation.data.readiness_band)}>
            Readiness: {mutation.data.readiness_score} (
            {mutation.data.readiness_band})
          </Badge>
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
            {todayCheckin ? "Update Today's Check-In" : "How are you feeling?"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
            <ScaleSelector
              name="sleep"
              label="Sleep Quality"
              value={values.sleep}
              onChange={(v) => setValue("sleep", v)}
            />
            <ScaleSelector
              name="energy"
              label="Energy Level"
              value={values.energy}
              onChange={(v) => setValue("energy", v)}
            />
            <ScaleSelector
              name="recovery"
              label="Recovery"
              value={values.recovery}
              onChange={(v) => setValue("recovery", v)}
            />
            <ScaleSelector
              name="stress"
              label="Stress Level"
              value={values.stress}
              onChange={(v) => setValue("stress", v)}
            />

            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="training_today"
                checked={values.training_today}
                onChange={(e) => setValue("training_today", e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="training_today">Planning to train today</Label>
            </div>

            <Button
              type="submit"
              disabled={isSubmitting || mutation.isPending}
              className="w-full"
            >
              {mutation.isPending
                ? "Saving..."
                : todayCheckin
                  ? "Update Check-In"
                  : "Save Check-In"}
            </Button>
          </form>
        </CardContent>
      </Card>

      {/* Show existing check-in info */}
      {todayCheckin && !mutation.isSuccess && (
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <span className="text-sm text-muted-foreground">
              Current readiness:
            </span>
            <Badge variant={bandVariant(todayCheckin.readiness_band)}>
              {todayCheckin.readiness_score} ({todayCheckin.readiness_band})
            </Badge>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
