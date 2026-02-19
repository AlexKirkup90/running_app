import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export function CoachCommandCenter() {
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Command Center</h1>
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Intervention Queue</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="py-10 text-center text-sm text-muted-foreground">
            Command Center migration in progress — coming in Phase 3.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
