import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import {
  Plus,
  Search,
  Edit2,
  Trash2,
  ChevronDown,
  ChevronUp,
  X,
} from "lucide-react";
import {
  useSessions,
  useSessionCategories,
  useCreateSession,
  useUpdateSession,
  useDeleteSession,
} from "@/hooks/useSessionLibrary";
import type { SessionTemplate } from "@/api/types";

const TIER_COLORS: Record<string, string> = {
  easy: "bg-green-100 text-green-800",
  medium: "bg-amber-100 text-amber-800",
  hard: "bg-red-100 text-red-800",
};

const ENERGY_OPTIONS = ["aerobic", "anaerobic", "mixed", "recovery"];
const INTENT_OPTIONS = [
  "general",
  "quality",
  "endurance",
  "speed",
  "recovery",
  "race_prep",
];
const TIER_OPTIONS = ["easy", "medium", "hard"];

export function CoachSessionLibrary() {
  const [categoryFilter, setCategoryFilter] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingSession, setEditingSession] = useState<SessionTemplate | null>(
    null,
  );
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const { data: categories } = useSessionCategories();
  const { data: sessions, isLoading } = useSessions(
    categoryFilter ? { category: categoryFilter } : undefined,
  );
  const deleteMutation = useDeleteSession();

  const filtered = sessions?.filter((s) =>
    searchTerm
      ? s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
        s.category.toLowerCase().includes(searchTerm.toLowerCase())
      : true,
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Session Library</h1>
        <Button
          onClick={() => {
            setEditingSession(null);
            setShowForm(true);
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          New Session
        </Button>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search sessions..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-9"
          />
        </div>
        <Select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="w-48"
        >
          <option value="">All categories</option>
          {categories?.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </div>

      {/* Session Form */}
      {showForm && (
        <SessionForm
          session={editingSession}
          onClose={() => {
            setShowForm(false);
            setEditingSession(null);
          }}
        />
      )}

      {/* Loading */}
      {isLoading && (
        <p className="py-10 text-center text-sm text-muted-foreground">
          Loading sessions...
        </p>
      )}

      {/* List */}
      {filtered && filtered.length === 0 && (
        <p className="py-10 text-center text-sm text-muted-foreground">
          No sessions found.
        </p>
      )}

      {filtered && filtered.length > 0 && (
        <div className="space-y-2">
          {filtered.map((session) => {
            const isExpanded = expandedId === session.id;
            return (
              <div key={session.id} className="rounded-lg border bg-card">
                <button
                  type="button"
                  className="flex w-full items-center justify-between p-3 text-left"
                  onClick={() =>
                    setExpandedId(isExpanded ? null : session.id)
                  }
                >
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium">{session.name}</span>
                    <Badge variant="outline" className="text-xs">
                      {session.category}
                    </Badge>
                    <Badge
                      className={TIER_COLORS[session.tier] ?? ""}
                      variant="secondary"
                    >
                      {session.tier}
                    </Badge>
                    <span className="text-xs text-muted-foreground">
                      {session.duration_min} min
                    </span>
                    {session.is_treadmill && (
                      <Badge variant="outline" className="text-xs">
                        Treadmill
                      </Badge>
                    )}
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>

                {isExpanded && (
                  <div className="space-y-3 border-t px-4 pb-4 pt-3">
                    <div className="grid grid-cols-2 gap-4 text-sm">
                      <div>
                        <p className="text-xs font-medium text-muted-foreground">
                          Intent
                        </p>
                        <p>{session.intent}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-muted-foreground">
                          Energy System
                        </p>
                        <p>{session.energy_system}</p>
                      </div>
                    </div>

                    {session.prescription && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground">
                          Prescription
                        </p>
                        <p className="text-sm">{session.prescription}</p>
                      </div>
                    )}

                    {session.coaching_notes && (
                      <div>
                        <p className="text-xs font-medium text-muted-foreground">
                          Coaching Notes
                        </p>
                        <p className="text-sm">{session.coaching_notes}</p>
                      </div>
                    )}

                    {/* Structure blocks */}
                    {(() => {
                      const sj = session.structure_json as { blocks?: Array<{ phase: string; duration_min: number }> };
                      if (!sj?.blocks) return null;
                      return (
                        <div>
                          <p className="mb-1 text-xs font-medium text-muted-foreground">
                            Structure
                          </p>
                          <div className="flex flex-wrap gap-1.5">
                            {sj.blocks.map((block, i) => (
                              <Badge
                                key={i}
                                variant="outline"
                                className="text-xs"
                              >
                                {block.phase} ({block.duration_min}m)
                              </Badge>
                            ))}
                          </div>
                        </div>
                      );
                    })()}

                    <div className="flex gap-2 pt-1">
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => {
                          setEditingSession(session);
                          setShowForm(true);
                        }}
                      >
                        <Edit2 className="mr-1.5 h-3.5 w-3.5" />
                        Edit
                      </Button>
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => {
                          if (
                            confirm(
                              `Delete "${session.name}"?`,
                            )
                          ) {
                            deleteMutation.mutate(session.id);
                          }
                        }}
                        disabled={deleteMutation.isPending}
                      >
                        <Trash2 className="mr-1.5 h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </div>
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

// ==========================================================================
// Session Form (Create / Edit)
// ==========================================================================

function SessionForm({
  session,
  onClose,
}: {
  session: SessionTemplate | null;
  onClose: () => void;
}) {
  const createMutation = useCreateSession();
  const updateMutation = useUpdateSession();
  const isEditing = !!session;

  const [name, setName] = useState(session?.name ?? "");
  const [category, setCategory] = useState(session?.category ?? "");
  const [intent, setIntent] = useState(session?.intent ?? "general");
  const [energySystem, setEnergySystem] = useState(
    session?.energy_system ?? "aerobic",
  );
  const [tier, setTier] = useState(session?.tier ?? "medium");
  const [isTreadmill, setIsTreadmill] = useState(session?.is_treadmill ?? false);
  const [durationMin, setDurationMin] = useState(session?.duration_min ?? 45);
  const [prescription, setPrescription] = useState(
    session?.prescription ?? "",
  );
  const [coachingNotes, setCoachingNotes] = useState(
    session?.coaching_notes ?? "",
  );

  const handleSubmit = () => {
    const data = {
      name,
      category,
      intent,
      energy_system: energySystem,
      tier,
      is_treadmill: isTreadmill,
      duration_min: durationMin,
      structure_json: session?.structure_json ?? {},
      targets_json: session?.targets_json ?? {},
      progression_json: session?.progression_json ?? {},
      regression_json: session?.regression_json ?? {},
      prescription,
      coaching_notes: coachingNotes,
    };

    if (isEditing) {
      updateMutation.mutate(
        { id: session.id, data },
        { onSuccess: onClose },
      );
    } else {
      createMutation.mutate(data, { onSuccess: onClose });
    }
  };

  const isPending = createMutation.isPending || updateMutation.isPending;
  const error = createMutation.error || updateMutation.error;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">
          {isEditing ? "Edit Session" : "New Session"}
        </CardTitle>
        <Button size="sm" variant="ghost" onClick={onClose}>
          <X className="h-4 w-4" />
        </Button>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          <div className="col-span-2">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Name
            </label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Category
            </label>
            <Input
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. Tempo, Easy, Intervals"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Intent
            </label>
            <Select
              value={intent}
              onChange={(e) => setIntent(e.target.value)}
            >
              {INTENT_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Energy System
            </label>
            <Select
              value={energySystem}
              onChange={(e) => setEnergySystem(e.target.value)}
            >
              {ENERGY_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Tier
            </label>
            <Select value={tier} onChange={(e) => setTier(e.target.value)}>
              {TIER_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o}
                </option>
              ))}
            </Select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Duration (min)
            </label>
            <Input
              type="number"
              min={10}
              max={300}
              value={durationMin}
              onChange={(e) => setDurationMin(Number(e.target.value))}
            />
          </div>
          <div className="flex items-end">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={isTreadmill}
                onChange={(e) => setIsTreadmill(e.target.checked)}
                className="rounded"
              />
              Treadmill
            </label>
          </div>
          <div className="col-span-2 md:col-span-3">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Prescription
            </label>
            <textarea
              value={prescription}
              onChange={(e) => setPrescription(e.target.value)}
              rows={2}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="col-span-2 md:col-span-3">
            <label className="mb-1 block text-xs font-medium text-muted-foreground">
              Coaching Notes
            </label>
            <textarea
              value={coachingNotes}
              onChange={(e) => setCoachingNotes(e.target.value)}
              rows={2}
              className="w-full rounded-md border bg-background px-3 py-2 text-sm"
            />
          </div>
        </div>

        {error && (
          <div className="mt-3 rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
            {(error as Error).message}
          </div>
        )}

        <div className="mt-4 flex gap-3">
          <Button onClick={handleSubmit} disabled={isPending || !name || !category}>
            {isPending ? "Saving..." : isEditing ? "Update" : "Create"}
          </Button>
          <Button variant="outline" onClick={onClose}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
