import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { fetchCoachClients } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { TableSkeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ChevronRight } from "lucide-react";

function riskBadgeVariant(label: string) {
  switch (label) {
    case "critical":
      return "danger" as const;
    case "at_risk":
    case "at-risk":
      return "warning" as const;
    case "watch":
      return "secondary" as const;
    default:
      return "success" as const;
  }
}

function formatDate(d: string | null): string {
  if (!d) return "-";
  return new Date(d).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
  });
}

export function CoachClients() {
  const { data: clients, isLoading } = useQuery({
    queryKey: ["coach-clients"],
    queryFn: fetchCoachClients,
  });

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Clients</h1>
        <span className="text-sm text-muted-foreground">
          {clients?.length ?? 0} athletes
        </span>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Active Roster</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <TableSkeleton rows={5} />
          ) : clients && clients.length > 0 ? (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Athlete</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Risk</TableHead>
                  <TableHead className="text-center">Open Interventions</TableHead>
                  <TableHead>Last Check-in</TableHead>
                  <TableHead>Last Log</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {clients.map((c) => (
                  <TableRow key={c.athlete_id} className="cursor-pointer hover:bg-accent/50">
                    <TableCell className="font-medium">
                      <Link to={`/coach/clients/${c.athlete_id}`} className="hover:underline">
                        {c.first_name} {c.last_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {c.email}
                    </TableCell>
                    <TableCell>
                      <Badge variant={riskBadgeVariant(c.risk_label)}>
                        {c.risk_label}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-center">
                      {c.open_interventions > 0 ? (
                        <span className="font-semibold text-amber-600">
                          {c.open_interventions}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">0</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(c.last_checkin)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDate(c.last_log)}
                    </TableCell>
                    <TableCell>
                      <Link to={`/coach/clients/${c.athlete_id}`}>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </Link>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          ) : (
            <p className="py-10 text-center text-sm text-muted-foreground">
              No athletes found
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
