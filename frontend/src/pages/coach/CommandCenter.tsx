import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  useInterventions,
  useAthletes,
  useSyncInterventions,
  useDecideIntervention,
} from "@/hooks/useInterventions";
import { InterventionFilters } from "@/components/interventions/InterventionFilters";
import { InterventionCard } from "@/components/interventions/InterventionCard";
import { DecideInterventionDialog } from "@/components/interventions/DecideInterventionDialog";
import type { Intervention } from "@/api/types";

export function CoachCommandCenter() {
  // --- State ---
  const [statusFilter, setStatusFilter] = useState("open");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedIntervention, setSelectedIntervention] =
    useState<Intervention | null>(null);
  const [selectedDecision, setSelectedDecision] = useState("");

  // --- Queries ---
  const {
    data: interventions,
    isLoading,
    isError,
    error,
  } = useInterventions(statusFilter);

  const { data: athletes } = useAthletes();

  // --- Mutations ---
  const syncMutation = useSyncInterventions();
  const decideMutation = useDecideIntervention();

  // --- Derived data ---
  const athleteNameMap = useMemo(() => {
    const map = new Map<number, string>();
    if (athletes) {
      for (const a of athletes) {
        map.set(a.id, `${a.first_name} ${a.last_name}`);
      }
    }
    return map;
  }, [athletes]);

  const stats = useMemo(() => {
    if (!interventions) return { high: 0, medium: 0, low: 0 };
    let high = 0;
    let medium = 0;
    let low = 0;
    for (const intv of interventions) {
      if (intv.risk_score >= 0.75) high++;
      else if (intv.risk_score >= 0.5) medium++;
      else low++;
    }
    return { high, medium, low };
  }, [interventions]);

  // --- Handlers ---
  const handleDecide = (intervention: Intervention, action: string) => {
    setSelectedIntervention(intervention);
    setSelectedDecision(action);
    setDialogOpen(true);
  };

  const handleConfirmDecision = (note: string) => {
    if (!selectedIntervention) return;
    decideMutation.mutate(
      {
        interventionId: selectedIntervention.id,
        decision: selectedDecision,
        note,
      },
      {
        onSuccess: () => {
          setDialogOpen(false);
          setSelectedIntervention(null);
          setSelectedDecision("");
        },
      },
    );
  };

  // --- Render ---
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Command Center</h1>

      {/* Summary badges for open queue */}
      {statusFilter === "open" && interventions && interventions.length > 0 && (
        <div className="flex items-center gap-3">
          <Badge variant="danger">{stats.high} high</Badge>
          <Badge variant="warning">{stats.medium} medium</Badge>
          <Badge variant="success">{stats.low} low</Badge>
        </div>
      )}

      {/* Sync feedback */}
      {syncMutation.isSuccess && (
        <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          Queue synced successfully.
        </div>
      )}
      {syncMutation.isError && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
          Sync failed: {(syncMutation.error as Error).message}
        </div>
      )}

      {/* Decision feedback */}
      {decideMutation.isError && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
          Decision failed: {(decideMutation.error as Error).message}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Intervention Queue</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <InterventionFilters
            statusFilter={statusFilter}
            onStatusFilterChange={setStatusFilter}
            onSync={() => syncMutation.mutate()}
            isSyncing={syncMutation.isPending}
            totalCount={interventions?.length ?? 0}
          />

          {/* Loading state */}
          {isLoading && (
            <p className="py-10 text-center text-sm text-muted-foreground">
              Loading interventions...
            </p>
          )}

          {/* Error state */}
          {isError && (
            <p className="py-10 text-center text-sm text-destructive">
              Failed to load interventions:{" "}
              {(error as Error).message}
            </p>
          )}

          {/* Empty state */}
          {!isLoading && !isError && interventions?.length === 0 && (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {statusFilter === "open"
                ? "No open interventions. Queue is clear."
                : `No ${statusFilter} interventions found.`}
            </p>
          )}

          {/* Intervention list */}
          {interventions && interventions.length > 0 && (
            <div className="space-y-3">
              {interventions.map((intv) => (
                <InterventionCard
                  key={intv.id}
                  intervention={intv}
                  athleteName={
                    athleteNameMap.get(intv.athlete_id) ??
                    `Athlete #${intv.athlete_id}`
                  }
                  onDecide={handleDecide}
                />
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Decision confirmation dialog */}
      <DecideInterventionDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        intervention={selectedIntervention}
        decision={selectedDecision}
        onConfirm={handleConfirmDecision}
        isPending={decideMutation.isPending}
      />
    </div>
  );
}
