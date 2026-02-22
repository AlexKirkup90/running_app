import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchOrganizations,
  fetchOrgCoaches,
  fetchOrgAssignments,
  fetchAthletes,
  transferAssignment,
  removeAssignment,
  createAssignment,
} from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select } from "@/components/ui/select";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowRightLeft,
  Building2,
  Crown,
  Plus,
  Shield,
  UserCheck,
  UserMinus,
  UserPlus,
  Users,
} from "lucide-react";
import type { OrgAssignment } from "@/api/types";

function tierVariant(tier: string) {
  if (tier === "enterprise") return "danger" as const;
  if (tier === "pro") return "warning" as const;
  return "secondary" as const;
}

function roleLabel(role: string) {
  const map: Record<string, string> = {
    owner: "Owner", head_coach: "Head Coach", coach: "Coach", assistant: "Assistant",
  };
  return map[role] ?? role;
}

function roleBadge(role: string) {
  if (role === "owner") return "danger" as const;
  if (role === "head_coach") return "warning" as const;
  if (role === "coach") return "secondary" as const;
  return "success" as const;
}

export function CoachOrganization() {
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const { data: orgs, isLoading: orgsLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: fetchOrganizations,
  });

  const orgId = orgs?.[0]?.id;
  const org = orgs?.[0];

  const { data: coaches, isLoading: coachesLoading } = useQuery({
    queryKey: ["org-coaches", orgId],
    queryFn: () => fetchOrgCoaches(orgId!),
    enabled: !!orgId,
  });

  const { data: assignments, isLoading: assignmentsLoading } = useQuery({
    queryKey: ["org-assignments", orgId],
    queryFn: () => fetchOrgAssignments(orgId!),
    enabled: !!orgId,
  });

  const { data: athletes } = useQuery({
    queryKey: ["athletes"],
    queryFn: () => fetchAthletes("active"),
    enabled: !!orgId,
  });

  const [transferTarget, setTransferTarget] = useState<{
    assignmentId: number;
    newCoachId: string;
  } | null>(null);
  const [assignForm, setAssignForm] = useState({ coachId: "", athleteId: "" });
  const [showAssignForm, setShowAssignForm] = useState(false);

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["org-assignments"] });
    queryClient.invalidateQueries({ queryKey: ["org-coaches"] });
    queryClient.invalidateQueries({ queryKey: ["organizations"] });
  };

  const transferMutation = useMutation({
    mutationFn: ({ assignmentId, newCoachId }: { assignmentId: number; newCoachId: number }) =>
      transferAssignment(orgId!, assignmentId, newCoachId),
    onSuccess: () => { invalidateAll(); setTransferTarget(null); toast("Athlete transferred", "success"); },
    onError: (err) => toast(err instanceof Error ? err.message : "Transfer failed", "error"),
  });

  const removeMutation = useMutation({
    mutationFn: (assignmentId: number) => removeAssignment(orgId!, assignmentId),
    onSuccess: () => { invalidateAll(); toast("Assignment removed", "success"); },
    onError: (err) => toast(err instanceof Error ? err.message : "Remove failed", "error"),
  });

  const assignMutation = useMutation({
    mutationFn: ({ coachId, athleteId }: { coachId: number; athleteId: number }) =>
      createAssignment(orgId!, coachId, athleteId),
    onSuccess: () => {
      invalidateAll();
      setAssignForm({ coachId: "", athleteId: "" });
      setShowAssignForm(false);
      toast("Athlete assigned", "success");
    },
    onError: (err) => toast(err instanceof Error ? err.message : "Assignment failed", "error"),
  });

  const unassignedAthletes = useMemo(() => {
    if (!athletes || !assignments) return [];
    const assignedIds = new Set(assignments.filter((a) => a.status === "active").map((a) => a.athlete_id));
    return athletes.filter((a) => !assignedIds.has(a.id));
  }, [athletes, assignments]);

  const byCoach = useMemo(() => {
    if (!assignments) return new Map<string, OrgAssignment[]>();
    const map = new Map<string, OrgAssignment[]>();
    for (const a of assignments) {
      if (a.status !== "active") continue;
      if (!map.has(a.coach_username)) map.set(a.coach_username, []);
      map.get(a.coach_username)!.push(a);
    }
    return map;
  }, [assignments]);

  if (orgsLoading) return <TableSkeleton rows={3} />;

  if (!org) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Organization</h1>
        <Card>
          <CardContent className="py-10 text-center text-muted-foreground">
            You are not a member of any organization yet.
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="rounded-lg bg-primary/10 p-2 text-primary">
            <Building2 className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">{org.name}</h1>
            <p className="text-sm text-muted-foreground">/{org.slug}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={tierVariant(org.tier)}>{org.tier.toUpperCase()}</Badge>
          <Badge variant="secondary"><Crown className="mr-1 h-3 w-3" />{roleLabel(org.role)}</Badge>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-blue-600"><Users className="h-5 w-5" /></div>
            <div>
              <p className="text-sm text-muted-foreground">Coaches</p>
              <p className="text-2xl font-bold">{org.coach_count}<span className="text-sm font-normal text-muted-foreground">/{org.max_coaches}</span></p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-emerald-600"><UserCheck className="h-5 w-5" /></div>
            <div>
              <p className="text-sm text-muted-foreground">Athletes</p>
              <p className="text-2xl font-bold">{org.athlete_count}<span className="text-sm font-normal text-muted-foreground">/{org.max_athletes}</span></p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-amber-600"><Building2 className="h-5 w-5" /></div>
            <div>
              <p className="text-sm text-muted-foreground">Plan</p>
              <p className="text-2xl font-bold capitalize">{org.tier}</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-4 p-6">
            <div className="rounded-lg bg-muted p-2 text-purple-600"><Crown className="h-5 w-5" /></div>
            <div>
              <p className="text-sm text-muted-foreground">Your Role</p>
              <p className="text-2xl font-bold">{roleLabel(org.role)}</p>
            </div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="team">
        <TabsList>
          <TabsTrigger value="team"><Shield className="mr-1 h-4 w-4" />Team</TabsTrigger>
          <TabsTrigger value="assignments"><ArrowRightLeft className="mr-1 h-4 w-4" />Assignments</TabsTrigger>
          <TabsTrigger value="capacity"><Building2 className="mr-1 h-4 w-4" />Capacity</TabsTrigger>
        </TabsList>

        <TabsContent value="team" className="space-y-4">
          {coachesLoading ? <TableSkeleton rows={3} /> : coaches && coaches.length > 0 ? (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {coaches.map((coach) => (
                  <Card key={coach.user_id}>
                    <CardContent className="p-6">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-sm font-bold text-primary">
                            {coach.username.charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-medium">{coach.username}</p>
                            <Badge variant={roleBadge(coach.role)} className="mt-1">{roleLabel(coach.role)}</Badge>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-2xl font-bold">{coach.assigned_athletes}</p>
                          <p className="text-xs text-muted-foreground">athletes</p>
                        </div>
                      </div>
                      <div className="mt-4">
                        <div className="mb-1 flex justify-between text-xs">
                          <span className="text-muted-foreground">Caseload</span>
                          <span>{coach.assigned_athletes} / {coach.caseload_cap}</span>
                        </div>
                        <div className="h-1.5 rounded-full bg-muted">
                          <div
                            className={`h-1.5 rounded-full transition-all ${
                              coach.assigned_athletes / coach.caseload_cap > 0.8 ? "bg-red-500"
                                : coach.assigned_athletes / coach.caseload_cap > 0.5 ? "bg-amber-500" : "bg-emerald-500"
                            }`}
                            style={{ width: `${Math.min(100, (coach.assigned_athletes / coach.caseload_cap) * 100)}%` }}
                          />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
              <Card>
                <CardHeader><CardTitle className="text-base">Coaching Roster</CardTitle></CardHeader>
                <CardContent>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Coach</TableHead>
                        <TableHead>Role</TableHead>
                        <TableHead className="text-center">Assigned</TableHead>
                        <TableHead className="text-center">Capacity</TableHead>
                        <TableHead className="text-center">Utilization</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {coaches.map((coach) => {
                        const util = Math.round((coach.assigned_athletes / coach.caseload_cap) * 100);
                        return (
                          <TableRow key={coach.user_id}>
                            <TableCell className="font-medium">
                              <div className="flex items-center gap-2"><Users className="h-4 w-4 text-muted-foreground" />{coach.username}</div>
                            </TableCell>
                            <TableCell><Badge variant={roleBadge(coach.role)}>{roleLabel(coach.role)}</Badge></TableCell>
                            <TableCell className="text-center font-medium">{coach.assigned_athletes}</TableCell>
                            <TableCell className="text-center text-muted-foreground">{coach.caseload_cap}</TableCell>
                            <TableCell className="text-center">
                              <span className={`font-medium ${util > 80 ? "text-red-600" : util > 50 ? "text-amber-600" : "text-emerald-600"}`}>{util}%</span>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </CardContent>
              </Card>
            </>
          ) : (
            <Card><CardContent className="py-10 text-center text-muted-foreground">No team members found</CardContent></Card>
          )}
        </TabsContent>

        <TabsContent value="assignments" className="space-y-4">
          <div className="flex justify-end">
            <Button size="sm" onClick={() => setShowAssignForm(!showAssignForm)} className="gap-1">
              <Plus className="h-4 w-4" />Assign Athlete
            </Button>
          </div>
          {showAssignForm && (
            <Card>
              <CardHeader><CardTitle className="flex items-center gap-2 text-base"><UserPlus className="h-4 w-4" />New Assignment</CardTitle></CardHeader>
              <CardContent>
                <div className="flex items-end gap-4">
                  <div className="flex-1 space-y-1">
                    <label className="text-sm font-medium">Coach</label>
                    <Select value={assignForm.coachId} onChange={(e) => setAssignForm((f) => ({ ...f, coachId: e.target.value }))}>
                      <option value="">Select coach</option>
                      {coaches?.map((c) => <option key={c.user_id} value={String(c.user_id)}>{c.username} ({c.assigned_athletes}/{c.caseload_cap})</option>)}
                    </Select>
                  </div>
                  <div className="flex-1 space-y-1">
                    <label className="text-sm font-medium">Athlete</label>
                    <Select value={assignForm.athleteId} onChange={(e) => setAssignForm((f) => ({ ...f, athleteId: e.target.value }))}>
                      <option value="">Select athlete</option>
                      {unassignedAthletes.map((a) => <option key={a.id} value={String(a.id)}>{a.first_name} {a.last_name}</option>)}
                    </Select>
                  </div>
                  <Button
                    onClick={() => assignMutation.mutate({ coachId: Number(assignForm.coachId), athleteId: Number(assignForm.athleteId) })}
                    disabled={!assignForm.coachId || !assignForm.athleteId || assignMutation.isPending}
                  >
                    {assignMutation.isPending ? "Assigning..." : "Assign"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
          {assignmentsLoading ? <TableSkeleton rows={5} /> : byCoach.size === 0 ? (
            <Card><CardContent className="py-10 text-center text-muted-foreground">No assignments yet. Click "Assign Athlete" to get started.</CardContent></Card>
          ) : (
            Array.from(byCoach.entries()).map(([coachName, coachAssignments]) => (
              <Card key={coachName}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{coachName}</CardTitle>
                    <Badge variant="secondary">{coachAssignments.length} athletes</Badge>
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
                          <TableCell className="font-medium">{a.athlete_name}</TableCell>
                          <TableCell><Badge variant={a.status === "active" ? "success" : "secondary"}>{a.status}</Badge></TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-2">
                              {transferTarget?.assignmentId === a.id ? (
                                <div className="flex items-center gap-2">
                                  <Select className="w-36" value={transferTarget.newCoachId} onChange={(e) => setTransferTarget({ assignmentId: a.id, newCoachId: e.target.value })}>
                                    <option value="">To coach...</option>
                                    {coaches?.filter((c) => c.user_id !== a.coach_user_id).map((c) => <option key={c.user_id} value={String(c.user_id)}>{c.username}</option>)}
                                  </Select>
                                  <Button size="sm" disabled={!transferTarget.newCoachId || transferMutation.isPending}
                                    onClick={() => transferMutation.mutate({ assignmentId: a.id, newCoachId: Number(transferTarget.newCoachId) })}>Confirm</Button>
                                  <Button size="sm" variant="ghost" onClick={() => setTransferTarget(null)}>Cancel</Button>
                                </div>
                              ) : (
                                <>
                                  <Button size="sm" variant="outline" className="gap-1" onClick={() => setTransferTarget({ assignmentId: a.id, newCoachId: "" })}>
                                    <ArrowRightLeft className="h-3 w-3" />Transfer
                                  </Button>
                                  <Button size="sm" variant="outline" className="gap-1 text-red-600 hover:text-red-700"
                                    onClick={() => removeMutation.mutate(a.id)} disabled={removeMutation.isPending}>
                                    <UserMinus className="h-3 w-3" />Remove
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
        </TabsContent>

        <TabsContent value="capacity" className="space-y-4">
          <Card>
            <CardHeader><CardTitle className="text-base">Capacity Usage</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-muted-foreground">Coach Seats</span>
                  <span className="font-medium">{org.coach_count} / {org.max_coaches}</span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-blue-600 transition-all" style={{ width: `${Math.min(100, (org.coach_count / org.max_coaches) * 100)}%` }} />
                </div>
              </div>
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-muted-foreground">Athlete Slots</span>
                  <span className="font-medium">{org.athlete_count} / {org.max_athletes}</span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div className="h-2 rounded-full bg-emerald-600 transition-all" style={{ width: `${Math.min(100, (org.athlete_count / org.max_athletes) * 100)}%` }} />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
