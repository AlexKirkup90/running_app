import { useQuery } from "@tanstack/react-query";
import { fetchOrganizations, fetchOrgCoaches } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Shield, Users } from "lucide-react";

function roleBadge(role: string) {
  switch (role) {
    case "owner":
      return "danger" as const;
    case "head_coach":
      return "warning" as const;
    case "coach":
      return "secondary" as const;
    default:
      return "success" as const;
  }
}

function roleLabel(role: string) {
  switch (role) {
    case "owner":
      return "Owner";
    case "head_coach":
      return "Head Coach";
    case "coach":
      return "Coach";
    case "assistant":
      return "Assistant";
    default:
      return role;
  }
}

export function CoachTeam() {
  const { data: orgs } = useQuery({
    queryKey: ["organizations"],
    queryFn: fetchOrganizations,
  });

  const orgId = orgs?.[0]?.id;

  const { data: coaches, isLoading } = useQuery({
    queryKey: ["org-coaches", orgId],
    queryFn: () => fetchOrgCoaches(orgId!),
    enabled: !!orgId,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Team</h1>
        <span className="text-sm text-muted-foreground">
          {coaches?.length ?? 0} coaches
        </span>
      </div>

      {/* Coach Summary Cards */}
      {coaches && coaches.length > 0 && (
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
                      <Badge variant={roleBadge(coach.role)} className="mt-1">
                        {roleLabel(coach.role)}
                      </Badge>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="text-2xl font-bold">
                      {coach.assigned_athletes}
                    </p>
                    <p className="text-xs text-muted-foreground">athletes</p>
                  </div>
                </div>

                {/* Caseload bar */}
                <div className="mt-4">
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="text-muted-foreground">Caseload</span>
                    <span>
                      {coach.assigned_athletes} / {coach.caseload_cap}
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted">
                    <div
                      className={`h-1.5 rounded-full transition-all ${
                        coach.assigned_athletes / coach.caseload_cap > 0.8
                          ? "bg-red-500"
                          : coach.assigned_athletes / coach.caseload_cap > 0.5
                            ? "bg-amber-500"
                            : "bg-emerald-500"
                      }`}
                      style={{
                        width: `${Math.min(100, (coach.assigned_athletes / coach.caseload_cap) * 100)}%`,
                      }}
                    />
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Full Table */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <CardTitle className="text-base">Coaching Roster</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              Loading team...
            </p>
          ) : coaches && coaches.length > 0 ? (
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
                  const util = Math.round(
                    (coach.assigned_athletes / coach.caseload_cap) * 100,
                  );
                  return (
                    <TableRow key={coach.user_id}>
                      <TableCell className="font-medium">
                        <div className="flex items-center gap-2">
                          <Users className="h-4 w-4 text-muted-foreground" />
                          {coach.username}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={roleBadge(coach.role)}>
                          {roleLabel(coach.role)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-center font-medium">
                        {coach.assigned_athletes}
                      </TableCell>
                      <TableCell className="text-center text-muted-foreground">
                        {coach.caseload_cap}
                      </TableCell>
                      <TableCell className="text-center">
                        <span
                          className={`font-medium ${
                            util > 80
                              ? "text-red-600"
                              : util > 50
                                ? "text-amber-600"
                                : "text-emerald-600"
                          }`}
                        >
                          {util}%
                        </span>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No team members found
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
