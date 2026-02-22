import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchWebhooks,
  registerWebhook,
  deleteWebhook,
  fetchWearableConnections,
  deleteWearableConnection,
  fetchWearableSyncLogs,
} from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { TableSkeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";
import {
  CheckCircle2,
  Link2,
  Plus,
  Trash2,
  Watch,
  Webhook,
  XCircle,
  RefreshCw,
} from "lucide-react";

const WEBHOOK_EVENTS = [
  "checkin.created",
  "training_log.created",
  "intervention.created",
  "intervention.closed",
  "plan.published",
  "athlete.created",
];

export function CoachIntegrations() {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [showWebhookForm, setShowWebhookForm] = useState(false);
  const [webhookUrl, setWebhookUrl] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [selectedEvents, setSelectedEvents] = useState<string[]>([]);

  const { data: webhooks, isLoading: webhooksLoading } = useQuery({
    queryKey: ["webhooks"],
    queryFn: fetchWebhooks,
  });

  const { data: connections, isLoading: connectionsLoading } = useQuery({
    queryKey: ["wearable-connections"],
    queryFn: fetchWearableConnections,
  });

  const { data: syncLogs, isLoading: syncLoading } = useQuery({
    queryKey: ["sync-logs"],
    queryFn: fetchWearableSyncLogs,
  });

  const registerMut = useMutation({
    mutationFn: (data: { url: string; events: string[]; secret?: string }) =>
      registerWebhook(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      toast("Webhook registered", "success");
      setShowWebhookForm(false);
      setWebhookUrl("");
      setWebhookSecret("");
      setSelectedEvents([]);
    },
    onError: (err) => {
      toast(err instanceof Error ? err.message : "Failed to register webhook", "error");
    },
  });

  const deleteWebhookMut = useMutation({
    mutationFn: deleteWebhook,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["webhooks"] });
      toast("Webhook removed", "success");
    },
    onError: (err) => {
      toast(err instanceof Error ? err.message : "Failed to delete webhook", "error");
    },
  });

  const disconnectMut = useMutation({
    mutationFn: deleteWearableConnection,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["wearable-connections"] });
      toast("Device disconnected", "success");
    },
    onError: (err) => {
      toast(err instanceof Error ? err.message : "Failed to disconnect", "error");
    },
  });

  function toggleEvent(event: string) {
    setSelectedEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event],
    );
  }

  function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!webhookUrl.trim() || selectedEvents.length === 0) return;
    registerMut.mutate({
      url: webhookUrl.trim(),
      events: selectedEvents,
      secret: webhookSecret.trim() || undefined,
    });
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Integrations</h1>
        <p className="text-muted-foreground">
          Manage webhooks, wearable connections, and data sync
        </p>
      </div>

      <Tabs defaultValue="webhooks">
        <TabsList>
          <TabsTrigger value="webhooks">
            <Webhook className="mr-1 h-4 w-4" />
            Webhooks
          </TabsTrigger>
          <TabsTrigger value="wearables">
            <Watch className="mr-1 h-4 w-4" />
            Wearables
          </TabsTrigger>
          <TabsTrigger value="sync">
            <RefreshCw className="mr-1 h-4 w-4" />
            Sync Logs
          </TabsTrigger>
        </TabsList>

        {/* Webhooks Tab */}
        <TabsContent value="webhooks" className="space-y-4">
          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={() => setShowWebhookForm(!showWebhookForm)}
            >
              <Plus className="mr-1 h-4 w-4" />
              Add Webhook
            </Button>
          </div>

          {showWebhookForm && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Register Webhook</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleRegister} className="space-y-4">
                  <div className="space-y-1.5">
                    <Label>Endpoint URL</Label>
                    <Input
                      type="url"
                      placeholder="https://your-server.com/webhook"
                      value={webhookUrl}
                      onChange={(e) => setWebhookUrl(e.target.value)}
                      required
                    />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Secret (optional, for HMAC verification)</Label>
                    <Input
                      type="text"
                      placeholder="your-webhook-secret"
                      value={webhookSecret}
                      onChange={(e) => setWebhookSecret(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Events</Label>
                    <div className="flex flex-wrap gap-2">
                      {WEBHOOK_EVENTS.map((event) => (
                        <button
                          key={event}
                          type="button"
                          onClick={() => toggleEvent(event)}
                          className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                            selectedEvents.includes(event)
                              ? "border-primary bg-primary/10 text-primary"
                              : "border-input text-muted-foreground hover:bg-accent"
                          }`}
                        >
                          {event}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" disabled={registerMut.isPending || !webhookUrl || selectedEvents.length === 0}>
                      {registerMut.isPending ? "Registering..." : "Register"}
                    </Button>
                    <Button type="button" variant="outline" onClick={() => setShowWebhookForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          )}

          {webhooksLoading ? (
            <TableSkeleton rows={3} />
          ) : !webhooks?.length ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Link2 className="mx-auto h-10 w-10 text-muted-foreground" />
                <p className="mt-3 font-medium">No webhooks configured</p>
                <p className="text-sm text-muted-foreground">
                  Add a webhook to receive real-time event notifications
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {webhooks.map((hook) => (
                <Card key={hook.hook_id}>
                  <CardContent className="flex items-center justify-between p-4">
                    <div>
                      <p className="text-sm font-medium font-mono">{hook.url}</p>
                      <div className="mt-1 flex flex-wrap gap-1">
                        {hook.events.map((evt) => (
                          <Badge key={evt} variant="outline" className="text-xs">
                            {evt}
                          </Badge>
                        ))}
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        ID: {hook.hook_id}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-600 hover:text-red-700"
                      onClick={() => deleteWebhookMut.mutate(hook.hook_id)}
                      disabled={deleteWebhookMut.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Wearables Tab */}
        <TabsContent value="wearables" className="space-y-4">
          {connectionsLoading ? (
            <TableSkeleton rows={3} />
          ) : !connections?.length ? (
            <Card>
              <CardContent className="py-12 text-center">
                <Watch className="mx-auto h-10 w-10 text-muted-foreground" />
                <p className="mt-3 font-medium">No wearable connections</p>
                <p className="text-sm text-muted-foreground">
                  Athletes connect their Garmin, Strava, or other devices from their profile
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {connections.map((conn) => (
                <Card key={conn.id}>
                  <CardContent className="flex items-center justify-between p-4">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-violet-100 p-2 text-violet-600">
                        <Watch className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-medium capitalize">{conn.service}</p>
                        {conn.external_athlete_id && (
                          <p className="text-xs text-muted-foreground">
                            External ID: {conn.external_athlete_id}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge
                        variant={
                          conn.sync_status === "active"
                            ? "success"
                            : conn.sync_status === "error"
                              ? "danger"
                              : "secondary"
                        }
                      >
                        {conn.sync_status}
                      </Badge>
                      {conn.last_sync_at && (
                        <span className="text-xs text-muted-foreground">
                          {conn.last_sync_at.slice(0, 16).replace("T", " ")}
                        </span>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-600 hover:text-red-700"
                        onClick={() => disconnectMut.mutate(conn.id)}
                        disabled={disconnectMut.isPending}
                      >
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Sync Logs Tab */}
        <TabsContent value="sync" className="space-y-4">
          {syncLoading ? (
            <TableSkeleton rows={5} />
          ) : !syncLogs?.length ? (
            <Card>
              <CardContent className="py-12 text-center">
                <RefreshCw className="mx-auto h-10 w-10 text-muted-foreground" />
                <p className="mt-3 font-medium">No sync activity</p>
                <p className="text-sm text-muted-foreground">
                  Sync logs will appear here when wearable data is imported
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {syncLogs.map((log) => (
                <div
                  key={log.id}
                  className="flex items-center justify-between rounded-lg border p-4"
                >
                  <div className="flex items-center gap-3">
                    {log.status === "success" ? (
                      <CheckCircle2 className="h-5 w-5 text-emerald-500" />
                    ) : (
                      <XCircle className="h-5 w-5 text-red-500" />
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
                  <div className="flex items-center gap-4 text-sm">
                    <span>{log.activities_found} found</span>
                    <span>{log.activities_imported} imported</span>
                    <Badge variant={log.status === "success" ? "success" : "danger"}>
                      {log.status}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
