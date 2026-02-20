import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchGroups,
  fetchChallenges,
  fetchActivityFeed,
  fetchGroupLeaderboard,
  fetchChallengeEntries,
  fetchGroupMessages,
  postGroupMessage,
  discoverGroups,
  joinGroup,
  joinChallenge,
} from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Users,
  Trophy,
  Activity,
  Medal,
  MessageCircle,
  Flame,
  Clock,
  Send,
  Search,
  UserPlus,
} from "lucide-react";
import type { ChallengeEntry } from "@/api/types";
import { useAuthStore } from "@/stores/auth";

export function AthleteCommunity() {
  const queryClient = useQueryClient();
  const { athleteId } = useAuthStore();
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [messageText, setMessageText] = useState("");
  const [showDiscover, setShowDiscover] = useState(false);

  const { data: groups, isLoading: groupsLoading } = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
  });

  const { data: challenges, isLoading: challengesLoading } = useQuery({
    queryKey: ["challenges"],
    queryFn: () => fetchChallenges("active"),
  });

  const { data: feed } = useQuery({
    queryKey: ["activity-feed", selectedGroupId],
    queryFn: () => fetchActivityFeed(selectedGroupId ?? undefined, 20),
  });

  const { data: leaderboard } = useQuery({
    queryKey: ["leaderboard", selectedGroupId],
    queryFn: () => fetchGroupLeaderboard(selectedGroupId!, "distance", 7),
    enabled: !!selectedGroupId,
  });

  const { data: messages } = useQuery({
    queryKey: ["group-messages", selectedGroupId],
    queryFn: () => fetchGroupMessages(selectedGroupId!, 20),
    enabled: !!selectedGroupId,
  });

  const { data: discoverableGroups } = useQuery({
    queryKey: ["discover-groups"],
    queryFn: discoverGroups,
    enabled: showDiscover,
  });

  const sendMessageMut = useMutation({
    mutationFn: (content: string) =>
      postGroupMessage(selectedGroupId!, content),
    onSuccess: () => {
      setMessageText("");
      queryClient.invalidateQueries({
        queryKey: ["group-messages", selectedGroupId],
      });
    },
  });

  const joinGroupMut = useMutation({
    mutationFn: joinGroup,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["groups"] });
      queryClient.invalidateQueries({ queryKey: ["discover-groups"] });
    },
  });

  const joinChallengeMut = useMutation({
    mutationFn: joinChallenge,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["challenges"] });
      queryClient.invalidateQueries({ queryKey: ["challenge-entries"] });
    },
  });

  // Auto-select first group
  const firstGroup = groups?.[0];
  if (firstGroup && !selectedGroupId) {
    setSelectedGroupId(firstGroup.id);
  }

  if (groupsLoading || challengesLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="text-muted-foreground">Loading community...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Community</h1>
        <p className="text-muted-foreground">
          Groups, challenges, and leaderboards
        </p>
      </div>

      <Tabs defaultValue="groups">
        <TabsList>
          <TabsTrigger value="groups">
            <Users className="mr-1 h-4 w-4" />
            Groups
          </TabsTrigger>
          <TabsTrigger value="challenges">
            <Trophy className="mr-1 h-4 w-4" />
            Challenges
          </TabsTrigger>
          <TabsTrigger value="feed">
            <Activity className="mr-1 h-4 w-4" />
            Activity Feed
          </TabsTrigger>
        </TabsList>

        {/* Groups Tab */}
        <TabsContent value="groups" className="space-y-4">
          {/* Discover Groups Toggle */}
          <div className="flex justify-end">
            <Button
              size="sm"
              variant={showDiscover ? "default" : "outline"}
              className="gap-1"
              onClick={() => setShowDiscover(!showDiscover)}
            >
              <Search className="h-4 w-4" />
              {showDiscover ? "Back to My Groups" : "Discover Groups"}
            </Button>
          </div>

          {joinGroupMut.isSuccess && (
            <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
              Joined group!
            </div>
          )}

          {/* Discover Mode */}
          {showDiscover ? (
            <div className="space-y-3">
              <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
                Public Groups You Can Join
              </h3>
              {!discoverableGroups?.length ? (
                <Card>
                  <CardContent className="py-10 text-center text-muted-foreground">
                    No new groups to discover right now.
                  </CardContent>
                </Card>
              ) : (
                discoverableGroups.map((g) => (
                  <Card key={g.id}>
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{g.name}</div>
                          {g.description && (
                            <div className="text-sm text-muted-foreground mt-1">
                              {g.description}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary">
                            <Users className="mr-1 h-3 w-3" />
                            {g.member_count}/{g.max_members}
                          </Badge>
                          <Button
                            size="sm"
                            className="gap-1"
                            onClick={() => joinGroupMut.mutate(g.id)}
                            disabled={joinGroupMut.isPending}
                          >
                            <UserPlus className="h-3 w-3" />
                            Join
                          </Button>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))
              )}
            </div>
          ) : !groups?.length ? (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                No groups yet. Use "Discover Groups" to find and join one!
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2">
              {/* Group List */}
              <div className="space-y-3">
                <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wide">
                  Your Groups
                </h3>
                {groups.map((g) => (
                  <Card
                    key={g.id}
                    className={`cursor-pointer transition-colors ${
                      selectedGroupId === g.id
                        ? "border-primary bg-primary/5"
                        : "hover:bg-accent/50"
                    }`}
                    onClick={() => setSelectedGroupId(g.id)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium">{g.name}</div>
                          {g.description && (
                            <div className="text-sm text-muted-foreground mt-1">
                              {g.description}
                            </div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge variant="secondary">
                            <Users className="mr-1 h-3 w-3" />
                            {g.member_count}
                          </Badge>
                          <Badge variant="outline">{g.privacy}</Badge>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              {/* Group Details */}
              {selectedGroupId && (
                <div className="space-y-4">
                  {/* Leaderboard */}
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <Medal className="h-4 w-4" />
                        Weekly Leaderboard
                      </CardTitle>
                    </CardHeader>
                    <CardContent>
                      {!leaderboard?.length ? (
                        <p className="text-sm text-muted-foreground">
                          No activity this week
                        </p>
                      ) : (
                        <div className="space-y-2">
                          {leaderboard.map((entry) => (
                            <div
                              key={entry.athlete_id}
                              className="flex items-center justify-between rounded-lg bg-accent/30 px-3 py-2"
                            >
                              <div className="flex items-center gap-3">
                                <span
                                  className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                                    entry.rank === 1
                                      ? "bg-yellow-500 text-white"
                                      : entry.rank === 2
                                        ? "bg-gray-400 text-white"
                                        : entry.rank === 3
                                          ? "bg-amber-700 text-white"
                                          : "bg-muted text-muted-foreground"
                                  }`}
                                >
                                  {entry.rank}
                                </span>
                                <span className="text-sm font-medium">
                                  {entry.name}
                                </span>
                              </div>
                              <span className="text-sm font-semibold">
                                {entry.value.toFixed(1)} km
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>

                  {/* Group Chat */}
                  <Card>
                    <CardHeader className="pb-3">
                      <CardTitle className="flex items-center gap-2 text-base">
                        <MessageCircle className="h-4 w-4" />
                        Group Chat
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {!messages?.length ? (
                        <p className="text-sm text-muted-foreground">
                          No messages yet. Be the first to say something!
                        </p>
                      ) : (
                        <div className="space-y-3 max-h-64 overflow-y-auto">
                          {messages.map((msg) => (
                            <div key={msg.id} className="text-sm">
                              <div className="flex items-center gap-2">
                                <span className="font-medium">
                                  {msg.author_name}
                                </span>
                                {msg.message_type !== "text" && (
                                  <Badge
                                    variant="outline"
                                    className="text-xs"
                                  >
                                    {msg.message_type}
                                  </Badge>
                                )}
                                <span className="text-xs text-muted-foreground">
                                  {msg.created_at
                                    ? new Date(
                                        msg.created_at,
                                      ).toLocaleDateString()
                                    : ""}
                                </span>
                              </div>
                              <p className="text-muted-foreground mt-0.5">
                                {msg.content}
                              </p>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Message Input */}
                      <div className="flex gap-2 border-t pt-3">
                        <Input
                          placeholder="Type a message..."
                          value={messageText}
                          onChange={(e) => setMessageText(e.target.value)}
                          onKeyDown={(e) => {
                            if (
                              e.key === "Enter" &&
                              !e.shiftKey &&
                              messageText.trim()
                            ) {
                              e.preventDefault();
                              sendMessageMut.mutate(messageText.trim());
                            }
                          }}
                        />
                        <Button
                          size="icon"
                          disabled={
                            !messageText.trim() || sendMessageMut.isPending
                          }
                          onClick={() =>
                            sendMessageMut.mutate(messageText.trim())
                          }
                        >
                          <Send className="h-4 w-4" />
                        </Button>
                      </div>
                      {sendMessageMut.isError && (
                        <p className="text-xs text-red-600">
                          Failed to send message. Try again.
                        </p>
                      )}
                    </CardContent>
                  </Card>
                </div>
              )}
            </div>
          )}
        </TabsContent>

        {/* Challenges Tab */}
        <TabsContent value="challenges" className="space-y-4">
          {joinChallengeMut.isSuccess && (
            <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
              Joined challenge!
            </div>
          )}
          {joinChallengeMut.isError && (
            <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
              {(joinChallengeMut.error as Error).message}
            </div>
          )}
          {!challenges?.length ? (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                No active challenges right now. Check back soon!
              </CardContent>
            </Card>
          ) : (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {challenges.map((c) => (
                <ChallengeCard
                  key={c.id}
                  challenge={c}
                  athleteId={athleteId}
                  onJoin={() => joinChallengeMut.mutate(c.id)}
                  isJoining={joinChallengeMut.isPending}
                />
              ))}
            </div>
          )}
        </TabsContent>

        {/* Activity Feed Tab */}
        <TabsContent value="feed" className="space-y-4">
          {!feed?.length ? (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                No recent activity to show
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {feed.map((item) => (
                <Card key={`${item.training_log_id}`}>
                  <CardContent className="flex items-center justify-between p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                        <Activity className="h-4 w-4 text-primary" />
                      </div>
                      <div>
                        <div className="text-sm font-medium">
                          {item.athlete_name}
                        </div>
                        <div className="text-sm text-muted-foreground">
                          {item.activity_summary}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-sm text-muted-foreground">
                      {item.kudos_count > 0 && (
                        <span className="flex items-center gap-1">
                          <Flame className="h-3 w-3 text-orange-500" />
                          {item.kudos_count}
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {item.date}
                      </span>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ChallengeCard({
  challenge,
  athleteId,
  onJoin,
  isJoining,
}: {
  challenge: {
    id: number;
    name: string;
    challenge_type: string;
    target_value: number;
    start_date: string;
    end_date: string;
    participant_count: number;
  };
  athleteId: number | null;
  onJoin: () => void;
  isJoining: boolean;
}) {
  const { data: entries } = useQuery({
    queryKey: ["challenge-entries", challenge.id],
    queryFn: () => fetchChallengeEntries(challenge.id),
  });

  const alreadyJoined = entries?.some(
    (e: ChallengeEntry) => e.athlete_id === athleteId,
  );

  const daysLeft = Math.max(
    0,
    Math.ceil(
      (new Date(challenge.end_date).getTime() - Date.now()) / 86_400_000,
    ),
  );

  const unit =
    challenge.challenge_type === "distance"
      ? "km"
      : challenge.challenge_type === "duration"
        ? "min"
        : challenge.challenge_type === "elevation"
          ? "m"
          : "days";

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{challenge.name}</CardTitle>
          <Badge variant="outline">{challenge.challenge_type}</Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex justify-between text-sm">
          <span className="text-muted-foreground">
            Target: {challenge.target_value} {unit}
          </span>
          <span className="text-muted-foreground">{daysLeft}d left</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <div className="flex items-center gap-2">
            <Users className="h-3 w-3" />
            <span>{challenge.participant_count} participants</span>
          </div>
          {!alreadyJoined ? (
            <Button
              size="sm"
              className="gap-1"
              onClick={onJoin}
              disabled={isJoining}
            >
              <UserPlus className="h-3 w-3" />
              {isJoining ? "Joining..." : "Join"}
            </Button>
          ) : (
            <Badge variant="success">Joined</Badge>
          )}
        </div>
        {entries && entries.length > 0 && (
          <div className="space-y-1.5 border-t pt-3">
            <div className="text-xs font-medium text-muted-foreground uppercase">
              Rankings
            </div>
            {entries.slice(0, 5).map((e: ChallengeEntry, i: number) => (
              <div
                key={e.id}
                className="flex items-center justify-between text-sm"
              >
                <span>
                  {i + 1}. {e.athlete_name}
                </span>
                <div className="flex items-center gap-2">
                  <div className="h-1.5 w-16 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full rounded-full bg-primary"
                      style={{
                        width: `${Math.min(100, (e.progress / challenge.target_value) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs text-muted-foreground w-12 text-right">
                    {e.progress.toFixed(1)} {unit}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
