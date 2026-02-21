import { useState, useMemo } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  AlertTriangle,
  Clock,
  CheckCircle2,
  BarChart3,
  Plus,
  Trash2,
  MessageSquare,
} from "lucide-react";
import {
  useInterventions,
  useAthletes,
  useSyncInterventions,
  useDecideIntervention,
} from "@/hooks/useInterventions";
import {
  useInterventionStats,
  useBatchDecide,
  useAthleteTimeline,
  useAthleteNotes,
  useCreateNote,
  useToggleNote,
  useDeleteNote,
} from "@/hooks/useCasework";
import { InterventionFilters } from "@/components/interventions/InterventionFilters";
import { InterventionCard } from "@/components/interventions/InterventionCard";
import { DecideInterventionDialog } from "@/components/interventions/DecideInterventionDialog";
import type { Intervention } from "@/api/types";

export function CoachCommandCenter() {
  const [tab, setTab] = useState<"queue" | "casework">("queue");

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Command Center</h1>

      <div className="flex gap-2 border-b pb-2">
        <button
          className={`px-4 py-2 text-sm font-medium rounded-t-md ${tab === "queue" ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground"}`}
          onClick={() => setTab("queue")}
        >
          Queue
        </button>
        <button
          className={`px-4 py-2 text-sm font-medium rounded-t-md ${tab === "casework" ? "bg-primary/10 text-primary border-b-2 border-primary" : "text-muted-foreground"}`}
          onClick={() => setTab("casework")}
        >
          Casework
        </button>
      </div>

      {tab === "queue" ? <QueueTab /> : <CaseworkTab />}
    </div>
  );
}

// ==========================================================================
// Queue Tab (enhanced with stats + batch)
// ==========================================================================

function QueueTab() {
  const [statusFilter, setStatusFilter] = useState("open");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [selectedIntervention, setSelectedIntervention] =
    useState<Intervention | null>(null);
  const [selectedDecision, setSelectedDecision] = useState("");
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  const {
    data: interventions,
    isLoading,
    isError,
    error,
  } = useInterventions(statusFilter);
  const { data: athletes } = useAthletes();
  const { data: stats } = useInterventionStats();

  const syncMutation = useSyncInterventions();
  const decideMutation = useDecideIntervention();
  const batchMutation = useBatchDecide();

  const athleteNameMap = useMemo(() => {
    const map = new Map<number, string>();
    if (athletes) {
      for (const a of athletes) {
        map.set(a.id, `${a.first_name} ${a.last_name}`);
      }
    }
    return map;
  }, [athletes]);

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

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleBatchDecide = (decision: string) => {
    if (selectedIds.size === 0) return;
    batchMutation.mutate(
      {
        intervention_ids: Array.from(selectedIds),
        decision,
      },
      {
        onSuccess: () => setSelectedIds(new Set()),
      },
    );
  };

  return (
    <div className="space-y-6">
      {/* Stats dashboard */}
      {stats && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <StatCard label="Open" value={stats.open_count} icon={AlertTriangle} variant="default" />
          <StatCard label="High Priority" value={stats.high_priority} icon={AlertTriangle} variant="danger" />
          <StatCard label="Actionable Now" value={stats.actionable_now} icon={CheckCircle2} variant="success" />
          <StatCard label="Snoozed" value={stats.snoozed} icon={Clock} variant="warning" />
          <StatCard label="Due 24h" value={stats.sla_due_24h} icon={Clock} variant="warning" />
          <StatCard label="Due 72h" value={stats.sla_due_72h} icon={Clock} variant="danger" />
          <StatCard label="Median Age" value={`${stats.median_age_hours}h`} icon={BarChart3} variant="default" />
          <StatCard label="Oldest" value={`${stats.oldest_age_hours}h`} icon={BarChart3} variant="default" />
        </div>
      )}

      {/* Sync feedback */}
      {syncMutation.isSuccess && (
        <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          Queue synced successfully.
        </div>
      )}

      {/* Batch actions */}
      {selectedIds.size > 0 && (
        <div className="flex items-center gap-3 rounded-lg border bg-muted/50 p-3">
          <span className="text-sm font-medium">
            {selectedIds.size} selected
          </span>
          <Button
            size="sm"
            onClick={() => handleBatchDecide("accept_and_close")}
            disabled={batchMutation.isPending}
          >
            Accept All
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => handleBatchDecide("defer_24h")}
            disabled={batchMutation.isPending}
          >
            Defer 24h
          </Button>
          <Button
            size="sm"
            variant="destructive"
            onClick={() => handleBatchDecide("dismiss")}
            disabled={batchMutation.isPending}
          >
            Dismiss All
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setSelectedIds(new Set())}
          >
            Clear
          </Button>
          {batchMutation.isSuccess && (
            <span className="text-xs text-emerald-600">
              {batchMutation.data.message}
            </span>
          )}
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

          {isLoading && (
            <p className="py-10 text-center text-sm text-muted-foreground">
              Loading interventions...
            </p>
          )}

          {isError && (
            <p className="py-10 text-center text-sm text-destructive">
              Failed to load: {(error as Error).message}
            </p>
          )}

          {!isLoading && !isError && interventions?.length === 0 && (
            <p className="py-10 text-center text-sm text-muted-foreground">
              {statusFilter === "open"
                ? "No open interventions. Queue is clear."
                : `No ${statusFilter} interventions found.`}
            </p>
          )}

          {interventions && interventions.length > 0 && (
            <div className="space-y-3">
              {interventions.map((intv) => (
                <div key={intv.id} className="flex items-start gap-2">
                  {statusFilter === "open" && (
                    <input
                      type="checkbox"
                      checked={selectedIds.has(intv.id)}
                      onChange={() => toggleSelect(intv.id)}
                      className="mt-4 rounded"
                    />
                  )}
                  <div className="flex-1">
                    <InterventionCard
                      intervention={intv}
                      athleteName={
                        athleteNameMap.get(intv.athlete_id) ??
                        `Athlete #${intv.athlete_id}`
                      }
                      onDecide={handleDecide}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

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

// ==========================================================================
// Casework Tab
// ==========================================================================

function CaseworkTab() {
  const { data: athletes } = useAthletes();
  const [athleteId, setAthleteId] = useState(0);
  const { data: timeline, isLoading: timelineLoading } =
    useAthleteTimeline(athleteId);
  const { data: notes } = useAthleteNotes(athleteId);
  const createNoteMutation = useCreateNote();
  const toggleNoteMutation = useToggleNote();
  const deleteNoteMutation = useDeleteNote();

  const [newNote, setNewNote] = useState("");
  const [newDueDate, setNewDueDate] = useState("");

  const handleAddNote = () => {
    if (!newNote.trim() || !athleteId) return;
    createNoteMutation.mutate(
      {
        athleteId,
        note: newNote,
        dueDate: newDueDate || null,
      },
      {
        onSuccess: () => {
          setNewNote("");
          setNewDueDate("");
        },
      },
    );
  };

  const SOURCE_COLORS: Record<string, string> = {
    coach_action: "bg-purple-100 text-purple-800",
    training_log: "bg-blue-100 text-blue-800",
    checkin: "bg-green-100 text-green-800",
    event: "bg-amber-100 text-amber-800",
    note: "bg-gray-100 text-gray-700",
  };

  return (
    <div className="space-y-6">
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
      </div>

      {athleteId > 0 && (
        <div className="grid gap-6 lg:grid-cols-3">
          {/* Timeline (2 cols) */}
          <div className="lg:col-span-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Clock className="h-4 w-4" />
                  Timeline
                </CardTitle>
              </CardHeader>
              <CardContent>
                {timelineLoading && (
                  <p className="text-sm text-muted-foreground">Loading...</p>
                )}
                {timeline && timeline.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    No timeline entries.
                  </p>
                )}
                {timeline && timeline.length > 0 && (
                  <div className="space-y-2 max-h-[600px] overflow-y-auto">
                    {timeline.map((entry, i) => (
                      <div
                        key={i}
                        className="flex items-start gap-3 border-b pb-2 last:border-0"
                      >
                        <Badge
                          className={`mt-0.5 text-xs shrink-0 ${SOURCE_COLORS[entry.source] ?? ""}`}
                          variant="secondary"
                        >
                          {entry.source.replace("_", " ")}
                        </Badge>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-medium">{entry.title}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {entry.detail}
                          </p>
                        </div>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {new Date(entry.when).toLocaleDateString("en-GB", {
                            day: "numeric",
                            month: "short",
                          })}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Notes (1 col) */}
          <div>
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <MessageSquare className="h-4 w-4" />
                  Notes & Tasks
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {/* Add note form */}
                <div className="space-y-2">
                  <textarea
                    value={newNote}
                    onChange={(e) => setNewNote(e.target.value)}
                    placeholder="Add a note..."
                    rows={2}
                    className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                  />
                  <div className="flex gap-2">
                    <Input
                      type="date"
                      value={newDueDate}
                      onChange={(e) => setNewDueDate(e.target.value)}
                      placeholder="Due date"
                      className="flex-1"
                    />
                    <Button
                      size="sm"
                      onClick={handleAddNote}
                      disabled={
                        createNoteMutation.isPending || !newNote.trim()
                      }
                    >
                      <Plus className="mr-1 h-3.5 w-3.5" />
                      Add
                    </Button>
                  </div>
                </div>

                {/* Notes list */}
                {notes && notes.length > 0 && (
                  <div className="space-y-2 max-h-[400px] overflow-y-auto">
                    {notes.map((note) => (
                      <div
                        key={note.id}
                        className={`flex items-start gap-2 rounded-lg border p-2 ${note.completed ? "opacity-50" : ""}`}
                      >
                        <input
                          type="checkbox"
                          checked={note.completed}
                          onChange={() =>
                            toggleNoteMutation.mutate({
                              athleteId,
                              noteId: note.id,
                              completed: !note.completed,
                            })
                          }
                          className="mt-1 rounded"
                        />
                        <div className="min-w-0 flex-1">
                          <p
                            className={`text-sm ${note.completed ? "line-through" : ""}`}
                          >
                            {note.note}
                          </p>
                          {note.due_date && (
                            <p className="text-xs text-muted-foreground">
                              Due: {note.due_date}
                            </p>
                          )}
                        </div>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-6 w-6 p-0"
                          onClick={() =>
                            deleteNoteMutation.mutate({
                              athleteId,
                              noteId: note.id,
                            })
                          }
                        >
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </div>
                    ))}
                  </div>
                )}

                {notes && notes.length === 0 && (
                  <p className="text-xs text-muted-foreground">
                    No notes yet.
                  </p>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

// ==========================================================================
// StatCard
// ==========================================================================

function StatCard({
  label,
  value,
  icon: Icon,
  variant,
}: {
  label: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  variant: "default" | "danger" | "warning" | "success";
}) {
  const variantStyles = {
    default: "text-foreground",
    danger: "text-red-600",
    warning: "text-amber-600",
    success: "text-emerald-600",
  };

  return (
    <Card>
      <CardContent className="flex items-center gap-3 p-4">
        <Icon className={`h-5 w-5 ${variantStyles[variant]}`} />
        <div>
          <p className={`text-lg font-bold ${variantStyles[variant]}`}>
            {value}
          </p>
          <p className="text-xs text-muted-foreground">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}
