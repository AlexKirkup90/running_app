import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchOrganizations,
  fetchOrgAssignments,
  fetchOrgCoaches,
  fetchAthletes,
  transferAssignment,
  removeAssignment,
  createAssignment,
} from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Select } from "@/components/ui/select";
import { ArrowRightLeft, Plus, UserMinus, UserPlus } from "lucide-react";
import type { OrgAssignment } from "@/api/types";

export function CoachAssignments() {
  const queryClient = useQueryClient();
  const [transferTarget, setTransferTarget] = useState<{
    assignmentId: number;
    newCoachId: string;
  } | null>(null);
  const [assignForm, setAssignForm] = useState<{
    coachId: string;
    athleteId: string;
  }>({ coachId: "", athleteId: "" });
  const [showAssignForm, setShowAssignForm] = useState(false);

  const { data: orgs } = useQuery({
    queryKey: ["organizations"],
    queryFn: fetchOrganizations,
  });
  const orgId = orgs?.[0]?.id;

  const { data: assignments, isLoading } = useQuery({
    queryKey: ["org-assignments", orgId],
    queryFn: () => fetchOrgAssignments(orgId!),
    enabled: !!orgId,
  });

  const { data: coaches } = useQuery({
    queryKey: ["org-coaches", orgId],
    queryFn: () => fetchOrgCoaches(orgId!),
    enabled: !!orgId,
  });

  const { data: athletes } = useQuery({
    queryKey: ["athletes"],
    queryFn: () => fetchAthletes("active"),
    enabled: !!orgId,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["org-assignments"] });
    queryClient.invalidateQueries({ queryKey: ["org-coaches"] });
    queryClient.invalidateQueries({ queryKey: ["organizations"] });
  };

  const transferMutation = useMutation({
    mutationFn: ({
      assignmentId,
      newCoachId,
    }: {
      assignmentId: number;
      newCoachId: number;
    }) => transferAssignment(orgId!, assignmentId, newCoachId),
    onSuccess: () => {
      invalidateAll();
      setTransferTarget(null);
    },
  });

  const removeMutation = useMutation({
    mutationFn: (assignmentId: number) =>
      removeAssignment(orgId!, assignmentId),
    onSuccess: invalidateAll,
  });

  const assignMutation = useMutation({
    mutationFn: ({
      coachId,
      athleteId,
    }: {
      coachId: number;
      athleteId: number;
    }) => createAssignment(orgId!, coachId, athleteId),
    onSuccess: () => {
      invalidateAll();
      setAssignForm({ coachId: "", athleteId: "" });
      setShowAssignForm(false);
    },
  });

  // Athletes not yet assigned
  const unassignedAthletes = useMemo(() => {
    if (!athletes || !assignments) return [];
    const assignedIds = new Set(
      assignments
        .filter((a) => a.status === "active")
        .map((a) => a.athlete_id),
    );
    return athletes.filter((a) => !assignedIds.has(a.id));
  }, [athletes, assignments]);

  // Group assignments by coach
  const byCoach = useMemo(() => {
    if (!assignments) return new Map<string, OrgAssignment[]>();
    const map = new Map<string, OrgAssignment[]>();
    for (const a of assignments) {
      if (a.status !== "active") continue;
      const key = a.coach_username;
      if (!map.has(key)) map.set(key, []);
      map.get(key)!.push(a);
    }
    return map;
  }, [assignments]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Assignments</h1>
        <Button
          size="sm"
          onClick={() => setShowAssignForm(!showAssignForm)}
          className="gap-1"
        >
          <Plus className="h-4 w-4" />
          Assign Athlete
        </Button>
      </div>

      {/* Feedback messages */}
      {transferMutation.isSuccess && (
        <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          Athlete transferred successfully.
        </div>
      )}
      {removeMutation.isSuccess && (
        <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          Assignment removed.
        </div>
      )}
      {assignMutation.isSuccess && (
        <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
          Athlete assigned successfully.
        </div>
      )}
      {assignMutation.isError && (
        <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
          {(assignMutation.error as Error).message}
        </div>
      )}

      {/* Assign Form */}
      {showAssignForm && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <UserPlus className="h-4 w-4" />
              New Assignment
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-4">
              <div className="flex-1 space-y-1">
                <label className="text-sm font-medium">Coach</label>
                <Select
                  value={assignForm.coachId}
                  onChange={(e) =>
                    setAssignForm((f) => ({ ...f, coachId: e.target.value }))
                  }
                >
                  <option value="">Select coach</option>
                  {coaches?.map((c) => (
                    <option key={c.user_id} value={String(c.user_id)}>
                      {c.username} ({c.assigned_athletes}/{c.caseload_cap})
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex-1 space-y-1">
                <label className="text-sm font-medium">Athlete</label>
                <Select
                  value={assignForm.athleteId}
                  onChange={(e) =>
                    setAssignForm((f) => ({ ...f, athleteId: e.target.value }))
                  }
                >
                  <option value="">Select athlete</option>
                  {unassignedAthletes.map((a) => (
                    <option key={a.id} value={String(a.id)}>
                      {a.first_name} {a.last_name}
                    </option>
                  ))}
                  {unassignedAthletes.length === 0 && (
                    <option disabled>All athletes assigned</option>
                  )}
                </Select>
              </div>
              <Button
                onClick={() =>
                  assignMutation.mutate({
                    coachId: Number(assignForm.coachId),
                    athleteId: Number(assignForm.athleteId),
                  })
                }
                disabled={
                  !assignForm.coachId ||
                  !assignForm.athleteId ||
                  assignMutation.isPending
                }
              >
                {assignMutation.isPending ? "Assigning..." : "Assign"}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Assignments by Coach */}
      {isLoading ? (
        <p className="py-10 text-center text-sm text-muted-foreground">
          Loading assignments...
        </p>
      ) : (
        Array.from(byCoach.entries()).map(([coachName, coachAssignments]) => (
          <Card key={coachName}>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">{coachName}</CardTitle>
                <Badge variant="secondary">
                  {coachAssignments.length} athletes
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Athlete</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {coachAssignments.map((a) => (
                    <TableRow key={a.id}>
                      <TableCell className="font-medium">
                        {a.athlete_name}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={
                            a.status === "active" ? "success" : "secondary"
                          }
                        >
                          {a.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          {transferTarget?.assignmentId === a.id ? (
                            <div className="flex items-center gap-2">
                              <Select
                                className="w-36"
                                value={transferTarget.newCoachId}
                                onChange={(e) =>
                                  setTransferTarget({
                                    assignmentId: a.id,
                                    newCoachId: e.target.value,
                                  })
                                }
                              >
                                <option value="">To coach...</option>
                                {coaches
                                  ?.filter(
                                    (c) => c.user_id !== a.coach_user_id,
                                  )
                                  .map((c) => (
                                    <option
                                      key={c.user_id}
                                      value={String(c.user_id)}
                                    >
                                      {c.username}
                                    </option>
                                  ))}
                              </Select>
                              <Button
                                size="sm"
                                disabled={
                                  !transferTarget.newCoachId ||
                                  transferMutation.isPending
                                }
                                onClick={() =>
                                  transferMutation.mutate({
                                    assignmentId: a.id,
                                    newCoachId: Number(
                                      transferTarget.newCoachId,
                                    ),
                                  })
                                }
                              >
                                Confirm
                              </Button>
                              <Button
                                size="sm"
                                variant="ghost"
                                onClick={() => setTransferTarget(null)}
                              >
                                Cancel
                              </Button>
                            </div>
                          ) : (
                            <>
                              <Button
                                size="sm"
                                variant="outline"
                                className="gap-1"
                                onClick={() =>
                                  setTransferTarget({
                                    assignmentId: a.id,
                                    newCoachId: "",
                                  })
                                }
                              >
                                <ArrowRightLeft className="h-3 w-3" />
                                Transfer
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                className="gap-1 text-red-600 hover:text-red-700"
                                onClick={() => removeMutation.mutate(a.id)}
                                disabled={removeMutation.isPending}
                              >
                                <UserMinus className="h-3 w-3" />
                                Remove
                              </Button>
                            </>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        ))
      )}

      {!isLoading && byCoach.size === 0 && (
        <Card>
          <CardContent className="py-10">
            <p className="text-center text-sm text-muted-foreground">
              No assignments yet. Click "Assign Athlete" to get started.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
