import { useAuthStore } from "@/stores/auth";
import { useAthleteProfile } from "@/hooks/useAthleteIntelligence";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Heart,
  Mail,
  Ruler,
  Timer,
  User,
  Watch,
  Zap,
  RefreshCw,
  CheckCircle2,
  XCircle,
} from "lucide-react";

function formatPace(secPerKm: number | null) {
  if (!secPerKm || secPerKm <= 0) return "—";
  const min = Math.floor(secPerKm / 60);
  const sec = Math.round(secPerKm % 60);
  return `${min}:${sec.toString().padStart(2, "0")}/km`;
}

export function AthleteProfile() {
  const { athleteId } = useAuthStore();
  const { data: profile, isLoading } = useAthleteProfile(athleteId ?? 0);

  if (isLoading) {
    return <div className="text-muted-foreground">Loading profile...</div>;
  }

  if (!profile) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">Profile</h1>
        <Card>
          <CardContent className="py-12 text-center">
            <User className="mx-auto h-10 w-10 text-muted-foreground" />
            <p className="mt-3 font-medium">Profile not found</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">Profile</h1>

      {/* Basic Info */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <User className="h-5 w-5 text-blue-500" />
            Personal Information
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border p-4">
              <p className="text-xs text-muted-foreground">Name</p>
              <p className="text-lg font-medium">{profile.first_name} {profile.last_name}</p>
            </div>
            <div className="rounded-lg border p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Mail className="h-3 w-3" /> Email
              </div>
              <p className="text-sm font-medium mt-1">{profile.email}</p>
            </div>
            {profile.dob && (
              <div className="rounded-lg border p-4">
                <p className="text-xs text-muted-foreground">Date of Birth</p>
                <p className="text-sm font-medium mt-1">{profile.dob}</p>
              </div>
            )}
            <div className="rounded-lg border p-4">
              <p className="text-xs text-muted-foreground">Status</p>
              <Badge variant={profile.status === "active" ? "success" : "secondary"} className="mt-1">
                {profile.status}
              </Badge>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Physiological Data */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Heart className="h-5 w-5 text-red-500" />
            Physiological Data
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="rounded-lg border p-4">
              <p className="text-xs text-muted-foreground">Max Heart Rate</p>
              <p className="text-lg font-bold">{profile.max_hr ?? "—"} <span className="text-sm font-normal text-muted-foreground">bpm</span></p>
            </div>
            <div className="rounded-lg border p-4">
              <p className="text-xs text-muted-foreground">Resting Heart Rate</p>
              <p className="text-lg font-bold">{profile.resting_hr ?? "—"} <span className="text-sm font-normal text-muted-foreground">bpm</span></p>
            </div>
            <div className="rounded-lg border p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Zap className="h-3 w-3" /> VDOT
              </div>
              <p className="text-lg font-bold mt-1">{profile.vdot_score ?? "—"}</p>
            </div>
            <div className="rounded-lg border p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Timer className="h-3 w-3" /> Threshold Pace
              </div>
              <p className="text-lg font-bold mt-1">{formatPace(profile.threshold_pace_sec_per_km)}</p>
            </div>
            <div className="rounded-lg border p-4">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Ruler className="h-3 w-3" /> Easy Pace
              </div>
              <p className="text-lg font-bold mt-1">{formatPace(profile.easy_pace_sec_per_km)}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Wearable Connections */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Watch className="h-5 w-5 text-violet-500" />
            Wearable Connections
          </CardTitle>
        </CardHeader>
        <CardContent>
          {profile.wearable_connections.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed p-8 text-center text-muted-foreground">
              <Watch className="mx-auto h-8 w-8 mb-2" />
              <p>No wearable devices connected</p>
              <p className="text-sm mt-1">Connect a Garmin, Strava, or other device to auto-import activities</p>
            </div>
          ) : (
            <div className="space-y-3">
              {profile.wearable_connections.map((conn) => (
                <div
                  key={conn.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-3">
                    <div className="rounded-lg bg-muted p-2 text-violet-600">
                      <Watch className="h-5 w-5" />
                    </div>
                    <div>
                      <p className="font-medium capitalize">{conn.service}</p>
                      {conn.external_athlete_id && (
                        <p className="text-xs text-muted-foreground">ID: {conn.external_athlete_id}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <Badge
                      variant={conn.sync_status === "active" ? "success" : conn.sync_status === "error" ? "danger" : "secondary"}
                    >
                      {conn.sync_status}
                    </Badge>
                    {conn.last_sync_at && (
                      <span className="text-xs text-muted-foreground">
                        Last sync: {conn.last_sync_at.slice(0, 16).replace("T", " ")}
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Recent Sync Logs */}
      {profile.sync_logs.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <RefreshCw className="h-5 w-5 text-emerald-500" />
              Recent Sync Activity
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {profile.sync_logs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center justify-between rounded-lg border p-3"
                >
                  <div className="flex items-center gap-3">
                    {log.status === "success" ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <XCircle className="h-4 w-4 text-red-500" />
                    )}
                    <div>
                      <p className="text-sm font-medium capitalize">{log.service}</p>
                      {log.started_at && (
                        <p className="text-xs text-muted-foreground">
                          {log.started_at.slice(0, 16).replace("T", " ")}
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <span>{log.activities_found} found</span>
                    <span>{log.activities_imported} imported</span>
                    <Badge variant={log.status === "success" ? "success" : "danger"}>
                      {log.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
