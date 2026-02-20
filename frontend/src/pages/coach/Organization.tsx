import { useQuery } from "@tanstack/react-query";
import { fetchOrganizations } from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Building2, Crown, Users, UserCheck } from "lucide-react";

function tierVariant(tier: string) {
  switch (tier) {
    case "enterprise":
      return "danger" as const;
    case "pro":
      return "warning" as const;
    default:
      return "secondary" as const;
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

export function CoachOrganization() {
  const { data: orgs, isLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: fetchOrganizations,
  });

  if (isLoading) {
    return <div className="text-muted-foreground">Loading organizations...</div>;
  }

  if (!orgs || orgs.length === 0) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Organization</h1>
        <Card>
          <CardContent className="py-10">
            <p className="text-center text-sm text-muted-foreground">
              You are not a member of any organization yet.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Organization</h1>

      {orgs.map((org) => (
        <div key={org.id} className="space-y-6">
          {/* Org Header */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-primary/10 p-2 text-primary">
                    <Building2 className="h-5 w-5" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">{org.name}</CardTitle>
                    <p className="text-sm text-muted-foreground">/{org.slug}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={tierVariant(org.tier)}>
                    {org.tier.toUpperCase()}
                  </Badge>
                  <Badge variant="secondary">
                    <Crown className="mr-1 h-3 w-3" />
                    {roleLabel(org.role)}
                  </Badge>
                </div>
              </div>
            </CardHeader>
          </Card>

          {/* Stats */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="rounded-lg bg-muted p-2 text-blue-600">
                  <Users className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Coaches</p>
                  <p className="text-2xl font-bold">
                    {org.coach_count}
                    <span className="text-sm font-normal text-muted-foreground">
                      /{org.max_coaches}
                    </span>
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="rounded-lg bg-muted p-2 text-emerald-600">
                  <UserCheck className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Athletes</p>
                  <p className="text-2xl font-bold">
                    {org.athlete_count}
                    <span className="text-sm font-normal text-muted-foreground">
                      /{org.max_athletes}
                    </span>
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="rounded-lg bg-muted p-2 text-amber-600">
                  <Building2 className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Plan</p>
                  <p className="text-2xl font-bold capitalize">{org.tier}</p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="flex items-center gap-4 p-6">
                <div className="rounded-lg bg-muted p-2 text-purple-600">
                  <Crown className="h-5 w-5" />
                </div>
                <div>
                  <p className="text-sm text-muted-foreground">Your Role</p>
                  <p className="text-2xl font-bold">{roleLabel(org.role)}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Capacity Bars */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Capacity Usage</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-muted-foreground">Coach Seats</span>
                  <span className="font-medium">
                    {org.coach_count} / {org.max_coaches}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div
                    className="h-2 rounded-full bg-blue-600 transition-all"
                    style={{
                      width: `${Math.min(100, (org.coach_count / org.max_coaches) * 100)}%`,
                    }}
                  />
                </div>
              </div>
              <div>
                <div className="mb-1 flex justify-between text-sm">
                  <span className="text-muted-foreground">Athlete Slots</span>
                  <span className="font-medium">
                    {org.athlete_count} / {org.max_athletes}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-muted">
                  <div
                    className="h-2 rounded-full bg-emerald-600 transition-all"
                    style={{
                      width: `${Math.min(100, (org.athlete_count / org.max_athletes) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  );
}
