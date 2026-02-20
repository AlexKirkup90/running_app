import { useState } from "react";
import { useAuthStore } from "@/stores/auth";
import { useEvents, useCreateEvent } from "@/hooks/usePlans";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CalendarDays, Plus, Trophy } from "lucide-react";

const DISTANCES = ["5K", "10K", "Half Marathon", "Marathon", "Other"] as const;

function daysUntil(dateStr: string) {
  const diff = Math.ceil(
    (new Date(dateStr).getTime() - Date.now()) / (1000 * 60 * 60 * 24),
  );
  return diff;
}

export function AthleteEvents() {
  const { athleteId } = useAuthStore();
  const { data: events, isLoading } = useEvents(athleteId ?? undefined);
  const createEvent = useCreateEvent();

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [eventDate, setEventDate] = useState("");
  const [distance, setDistance] = useState<string>("5K");
  const [formError, setFormError] = useState<string | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    if (!name.trim()) {
      setFormError("Name is required");
      return;
    }
    if (!eventDate) {
      setFormError("Date is required");
      return;
    }

    const today = new Date().toISOString().slice(0, 10);
    if (eventDate <= today) {
      setFormError("Event date must be in the future");
      return;
    }

    createEvent.mutate(
      { name: name.trim(), event_date: eventDate, distance },
      {
        onSuccess: () => {
          setShowForm(false);
          setName("");
          setEventDate("");
          setDistance("5K");
        },
        onError: (err) => {
          setFormError(err instanceof Error ? err.message : "Failed to create event");
        },
      },
    );
  }

  if (isLoading) {
    return <div className="text-muted-foreground">Loading events...</div>;
  }

  const upcoming = events?.filter((e) => daysUntil(e.event_date) >= 0) ?? [];
  const past = events?.filter((e) => daysUntil(e.event_date) < 0) ?? [];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold tracking-tight">Events</h1>
        <Button size="sm" onClick={() => setShowForm(!showForm)}>
          <Plus className="mr-1 h-4 w-4" />
          Add Event
        </Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">New Event</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="mb-1 block text-sm font-medium">Name</label>
                <input
                  type="text"
                  maxLength={140}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  className="w-full rounded-md border px-3 py-2 text-sm"
                  placeholder="e.g. Spring Half Marathon"
                />
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="mb-1 block text-sm font-medium">Date</label>
                  <input
                    type="date"
                    value={eventDate}
                    onChange={(e) => setEventDate(e.target.value)}
                    className="w-full rounded-md border px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-sm font-medium">Distance</label>
                  <select
                    value={distance}
                    onChange={(e) => setDistance(e.target.value)}
                    className="w-full rounded-md border px-3 py-2 text-sm"
                  >
                    {DISTANCES.map((d) => (
                      <option key={d} value={d}>{d}</option>
                    ))}
                  </select>
                </div>
              </div>
              {formError && (
                <p className="text-sm text-destructive">{formError}</p>
              )}
              <div className="flex gap-2">
                <Button type="submit" disabled={createEvent.isPending}>
                  {createEvent.isPending ? "Creating..." : "Create Event"}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setShowForm(false)}
                >
                  Cancel
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      )}

      {/* Upcoming Events */}
      <div>
        <h2 className="mb-3 text-lg font-semibold">Upcoming</h2>
        {upcoming.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <CalendarDays className="mx-auto h-10 w-10 text-muted-foreground" />
              <p className="mt-3 font-medium">No upcoming events</p>
              <p className="text-sm text-muted-foreground">
                Add a race or event to start planning
              </p>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3">
            {upcoming.map((evt) => {
              const days = daysUntil(evt.event_date);
              return (
                <Card key={evt.id}>
                  <CardContent className="flex items-center justify-between p-4">
                    <div className="flex items-center gap-3">
                      <div className="rounded-lg bg-primary/10 p-2 text-primary">
                        <Trophy className="h-5 w-5" />
                      </div>
                      <div>
                        <p className="font-medium">{evt.name}</p>
                        <p className="text-sm text-muted-foreground">
                          {evt.event_date}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-3">
                      <Badge variant="outline">{evt.distance}</Badge>
                      <span className="text-sm font-medium text-primary">
                        {days === 0 ? "Today!" : `${days}d`}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Past Events */}
      {past.length > 0 && (
        <div>
          <h2 className="mb-3 text-lg font-semibold text-muted-foreground">Past</h2>
          <div className="space-y-2">
            {past.map((evt) => (
              <div
                key={evt.id}
                className="flex items-center justify-between rounded-lg border px-4 py-3 text-muted-foreground"
              >
                <div className="flex items-center gap-3">
                  <Trophy className="h-4 w-4" />
                  <span>{evt.name}</span>
                </div>
                <div className="flex items-center gap-3 text-sm">
                  <Badge variant="secondary">{evt.distance}</Badge>
                  <span>{evt.event_date}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
