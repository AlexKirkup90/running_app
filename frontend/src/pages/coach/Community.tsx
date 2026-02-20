import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchGroups,
  createGroup,
  fetchGroupMembers,
  addGroupMember,
  removeGroupMember,
  fetchAthletes,
  fetchChallenges,
  createChallenge,
  fetchChallengeEntries,
  syncChallengeProgress,
} from "@/api/client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Users,
  Plus,
  Trophy,
  UserMinus,
  UserPlus,
  RefreshCw,
} from "lucide-react";

export function CoachCommunity() {
  const queryClient = useQueryClient();
  const [showGroupForm, setShowGroupForm] = useState(false);
  const [showChallengeForm, setShowChallengeForm] = useState(false);
  const [selectedGroupId, setSelectedGroupId] = useState<number | null>(null);
  const [addAthleteGroupId, setAddAthleteGroupId] = useState<number | null>(
    null,
  );
  const [addAthleteId, setAddAthleteId] = useState("");
  const [groupForm, setGroupForm] = useState({
    name: "",
    description: "",
    privacy: "public",
    max_members: "50",
  });
  const [challengeForm, setChallengeForm] = useState({
    name: "",
    challenge_type: "distance",
    target_value: "",
    start_date: "",
    end_date: "",
    group_id: "",
  });

  const { data: groups, isLoading } = useQuery({
    queryKey: ["groups"],
    queryFn: fetchGroups,
  });

  const { data: challenges } = useQuery({
    queryKey: ["challenges"],
    queryFn: () => fetchChallenges("active"),
  });

  const { data: athletes } = useQuery({
    queryKey: ["athletes"],
    queryFn: () => fetchAthletes("active"),
  });

  const { data: members } = useQuery({
    queryKey: ["group-members", selectedGroupId],
    queryFn: () => fetchGroupMembers(selectedGroupId!),
    enabled: !!selectedGroupId,
  });

  const invalidateAll = () => {
    queryClient.invalidateQueries({ queryKey: ["groups"] });
    queryClient.invalidateQueries({ queryKey: ["group-members"] });
    queryClient.invalidateQueries({ queryKey: ["challenges"] });
    queryClient.invalidateQueries({ queryKey: ["challenge-entries"] });
  };

  const createGroupMut = useMutation({
    mutationFn: createGroup,
    onSuccess: () => {
      invalidateAll();
      setShowGroupForm(false);
      setGroupForm({
        name: "",
        description: "",
        privacy: "public",
        max_members: "50",
      });
    },
  });

  const addMemberMut = useMutation({
    mutationFn: ({
      groupId,
      athleteId,
    }: {
      groupId: number;
      athleteId: number;
    }) => addGroupMember(groupId, athleteId),
    onSuccess: () => {
      invalidateAll();
      setAddAthleteId("");
      setAddAthleteGroupId(null);
    },
  });

  const removeMemberMut = useMutation({
    mutationFn: ({
      groupId,
      athleteId,
    }: {
      groupId: number;
      athleteId: number;
    }) => removeGroupMember(groupId, athleteId),
    onSuccess: invalidateAll,
  });

  const createChallengeMut = useMutation({
    mutationFn: createChallenge,
    onSuccess: () => {
      invalidateAll();
      setShowChallengeForm(false);
      setChallengeForm({
        name: "",
        challenge_type: "distance",
        target_value: "",
        start_date: "",
        end_date: "",
        group_id: "",
      });
    },
  });

  const syncProgressMut = useMutation({
    mutationFn: syncChallengeProgress,
    onSuccess: invalidateAll,
  });

  // Athletes not in selected group
  const availableAthletes =
    selectedGroupId && members && athletes
      ? athletes.filter((a) => !members.some((m) => m.athlete_id === a.id))
      : athletes ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Community</h1>
        <p className="text-muted-foreground">
          Manage groups, memberships, and challenges
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
        </TabsList>

        {/* Groups Tab */}
        <TabsContent value="groups" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Training Groups</h2>
            <Button
              size="sm"
              onClick={() => setShowGroupForm(!showGroupForm)}
              className="gap-1"
            >
              <Plus className="h-4 w-4" />
              New Group
            </Button>
          </div>

          {/* Success/Error messages */}
          {createGroupMut.isSuccess && (
            <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
              Group created successfully.
            </div>
          )}
          {createGroupMut.isError && (
            <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
              {(createGroupMut.error as Error).message}
            </div>
          )}
          {addMemberMut.isSuccess && (
            <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
              Member added.
            </div>
          )}
          {addMemberMut.isError && (
            <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
              {(addMemberMut.error as Error).message}
            </div>
          )}

          {/* Create Group Form */}
          {showGroupForm && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Create Group</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Name</label>
                    <Input
                      placeholder="e.g. Morning Runners"
                      value={groupForm.name}
                      onChange={(e) =>
                        setGroupForm((f) => ({ ...f, name: e.target.value }))
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Privacy</label>
                    <Select
                      value={groupForm.privacy}
                      onChange={(e) =>
                        setGroupForm((f) => ({
                          ...f,
                          privacy: e.target.value,
                        }))
                      }
                    >
                      <option value="public">Public</option>
                      <option value="private">Private</option>
                      <option value="invite_only">Invite Only</option>
                    </Select>
                  </div>
                </div>
                <div className="space-y-1">
                  <label className="text-sm font-medium">Description</label>
                  <Textarea
                    placeholder="What's this group about?"
                    value={groupForm.description}
                    onChange={(e) =>
                      setGroupForm((f) => ({
                        ...f,
                        description: e.target.value,
                      }))
                    }
                  />
                </div>
                <div className="flex items-end gap-3">
                  <div className="w-32 space-y-1">
                    <label className="text-sm font-medium">Max Members</label>
                    <Input
                      type="number"
                      min={2}
                      max={500}
                      value={groupForm.max_members}
                      onChange={(e) =>
                        setGroupForm((f) => ({
                          ...f,
                          max_members: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <Button
                    onClick={() =>
                      createGroupMut.mutate({
                        name: groupForm.name,
                        description: groupForm.description,
                        privacy: groupForm.privacy,
                        max_members: Number(groupForm.max_members),
                      })
                    }
                    disabled={!groupForm.name || createGroupMut.isPending}
                  >
                    {createGroupMut.isPending ? "Creating..." : "Create Group"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Groups List */}
          {isLoading ? (
            <p className="py-10 text-center text-sm text-muted-foreground">
              Loading groups...
            </p>
          ) : !groups?.length ? (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                No groups yet. Create one to get started.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {groups.map((g) => (
                <Card key={g.id}>
                  <CardHeader
                    className="cursor-pointer"
                    onClick={() =>
                      setSelectedGroupId(
                        selectedGroupId === g.id ? null : g.id,
                      )
                    }
                  >
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-base">{g.name}</CardTitle>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary">
                          <Users className="mr-1 h-3 w-3" />
                          {g.member_count}/{g.max_members}
                        </Badge>
                        <Badge variant="outline">{g.privacy}</Badge>
                      </div>
                    </div>
                    {g.description && (
                      <p className="text-sm text-muted-foreground">
                        {g.description}
                      </p>
                    )}
                  </CardHeader>

                  {selectedGroupId === g.id && (
                    <CardContent className="space-y-4">
                      {/* Add Member */}
                      <div className="flex items-end gap-3 border-b pb-4">
                        <div className="flex-1 space-y-1">
                          <label className="text-sm font-medium">
                            Add Athlete
                          </label>
                          <Select
                            value={
                              addAthleteGroupId === g.id ? addAthleteId : ""
                            }
                            onChange={(e) => {
                              setAddAthleteGroupId(g.id);
                              setAddAthleteId(e.target.value);
                            }}
                          >
                            <option value="">Select athlete...</option>
                            {availableAthletes.map((a) => (
                              <option key={a.id} value={String(a.id)}>
                                {a.first_name} {a.last_name}
                              </option>
                            ))}
                          </Select>
                        </div>
                        <Button
                          size="sm"
                          className="gap-1"
                          disabled={
                            !addAthleteId ||
                            addAthleteGroupId !== g.id ||
                            addMemberMut.isPending
                          }
                          onClick={() =>
                            addMemberMut.mutate({
                              groupId: g.id,
                              athleteId: Number(addAthleteId),
                            })
                          }
                        >
                          <UserPlus className="h-3 w-3" />
                          {addMemberMut.isPending ? "Adding..." : "Add"}
                        </Button>
                      </div>

                      {/* Members Table */}
                      {members && members.length > 0 ? (
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Athlete</TableHead>
                              <TableHead>Role</TableHead>
                              <TableHead>Joined</TableHead>
                              <TableHead className="text-right">
                                Actions
                              </TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {members.map((m) => (
                              <TableRow key={m.id}>
                                <TableCell className="font-medium">
                                  {m.athlete_name}
                                </TableCell>
                                <TableCell>
                                  <Badge variant="secondary">{m.role}</Badge>
                                </TableCell>
                                <TableCell className="text-sm text-muted-foreground">
                                  {m.joined_at
                                    ? new Date(
                                        m.joined_at,
                                      ).toLocaleDateString()
                                    : "-"}
                                </TableCell>
                                <TableCell className="text-right">
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    className="gap-1 text-red-600 hover:text-red-700"
                                    disabled={removeMemberMut.isPending}
                                    onClick={() =>
                                      removeMemberMut.mutate({
                                        groupId: g.id,
                                        athleteId: m.athlete_id,
                                      })
                                    }
                                  >
                                    <UserMinus className="h-3 w-3" />
                                    Remove
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      ) : (
                        <p className="text-center text-sm text-muted-foreground py-4">
                          No members yet. Add athletes above.
                        </p>
                      )}
                    </CardContent>
                  )}
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Challenges Tab */}
        <TabsContent value="challenges" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Challenges</h2>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                className="gap-1"
                onClick={() => syncProgressMut.mutate()}
                disabled={syncProgressMut.isPending}
              >
                <RefreshCw
                  className={`h-4 w-4 ${syncProgressMut.isPending ? "animate-spin" : ""}`}
                />
                {syncProgressMut.isPending
                  ? "Syncing..."
                  : "Sync Progress"}
              </Button>
              <Button
                size="sm"
                onClick={() => setShowChallengeForm(!showChallengeForm)}
                className="gap-1"
              >
                <Plus className="h-4 w-4" />
                New Challenge
              </Button>
            </div>
          </div>

          {syncProgressMut.isSuccess && (
            <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
              {(syncProgressMut.data as { message: string }).message}
            </div>
          )}
          {createChallengeMut.isSuccess && (
            <div className="rounded-md bg-emerald-50 px-4 py-2 text-sm text-emerald-800">
              Challenge created successfully.
            </div>
          )}
          {createChallengeMut.isError && (
            <div className="rounded-md bg-red-50 px-4 py-2 text-sm text-red-800">
              {(createChallengeMut.error as Error).message}
            </div>
          )}

          {/* Create Challenge Form */}
          {showChallengeForm && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Create Challenge</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid gap-3 md:grid-cols-2">
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Name</label>
                    <Input
                      placeholder="e.g. March Distance Challenge"
                      value={challengeForm.name}
                      onChange={(e) =>
                        setChallengeForm((f) => ({
                          ...f,
                          name: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Type</label>
                    <Select
                      value={challengeForm.challenge_type}
                      onChange={(e) =>
                        setChallengeForm((f) => ({
                          ...f,
                          challenge_type: e.target.value,
                        }))
                      }
                    >
                      <option value="distance">Distance (km)</option>
                      <option value="duration">Duration (min)</option>
                      <option value="elevation">Elevation (m)</option>
                      <option value="streak">Streak (days)</option>
                    </Select>
                  </div>
                </div>
                <div className="grid gap-3 md:grid-cols-3">
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Target Value</label>
                    <Input
                      type="number"
                      min={1}
                      placeholder="e.g. 100"
                      value={challengeForm.target_value}
                      onChange={(e) =>
                        setChallengeForm((f) => ({
                          ...f,
                          target_value: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">Start Date</label>
                    <Input
                      type="date"
                      value={challengeForm.start_date}
                      onChange={(e) =>
                        setChallengeForm((f) => ({
                          ...f,
                          start_date: e.target.value,
                        }))
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-sm font-medium">End Date</label>
                    <Input
                      type="date"
                      value={challengeForm.end_date}
                      onChange={(e) =>
                        setChallengeForm((f) => ({
                          ...f,
                          end_date: e.target.value,
                        }))
                      }
                    />
                  </div>
                </div>
                <div className="flex items-end gap-3">
                  <div className="flex-1 space-y-1">
                    <label className="text-sm font-medium">
                      Group (optional)
                    </label>
                    <Select
                      value={challengeForm.group_id}
                      onChange={(e) =>
                        setChallengeForm((f) => ({
                          ...f,
                          group_id: e.target.value,
                        }))
                      }
                    >
                      <option value="">No group (open to all)</option>
                      {groups?.map((g) => (
                        <option key={g.id} value={String(g.id)}>
                          {g.name}
                        </option>
                      ))}
                    </Select>
                  </div>
                  <Button
                    onClick={() =>
                      createChallengeMut.mutate({
                        name: challengeForm.name,
                        challenge_type: challengeForm.challenge_type,
                        target_value: Number(challengeForm.target_value),
                        start_date: challengeForm.start_date,
                        end_date: challengeForm.end_date,
                        group_id: challengeForm.group_id
                          ? Number(challengeForm.group_id)
                          : null,
                      })
                    }
                    disabled={
                      !challengeForm.name ||
                      !challengeForm.target_value ||
                      !challengeForm.start_date ||
                      !challengeForm.end_date ||
                      createChallengeMut.isPending
                    }
                  >
                    {createChallengeMut.isPending
                      ? "Creating..."
                      : "Create Challenge"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Challenges List */}
          {!challenges?.length ? (
            <Card>
              <CardContent className="py-10 text-center text-muted-foreground">
                No active challenges. Create one to motivate your athletes!
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {challenges.map((c) => (
                <CoachChallengeCard key={c.id} challenge={c} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CoachChallengeCard({
  challenge,
}: {
  challenge: {
    id: number;
    name: string;
    challenge_type: string;
    target_value: number;
    start_date: string;
    end_date: string;
    participant_count: number;
    group_id: number | null;
  };
}) {
  const { data: entries } = useQuery({
    queryKey: ["challenge-entries", challenge.id],
    queryFn: () => fetchChallengeEntries(challenge.id),
  });

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
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">{challenge.name}</CardTitle>
          <div className="flex gap-2">
            <Badge variant="outline">{challenge.challenge_type}</Badge>
            <Badge variant="secondary">
              {challenge.participant_count} participants
            </Badge>
          </div>
        </div>
        <div className="flex gap-4 text-sm text-muted-foreground">
          <span>
            Target: {challenge.target_value} {unit}
          </span>
          <span>{daysLeft}d remaining</span>
        </div>
      </CardHeader>
      {entries && entries.length > 0 && (
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>#</TableHead>
                <TableHead>Athlete</TableHead>
                <TableHead>Progress</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {entries.map((e, i) => (
                <TableRow key={e.id}>
                  <TableCell>{i + 1}</TableCell>
                  <TableCell className="font-medium">
                    {e.athlete_name}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 rounded-full bg-muted overflow-hidden">
                        <div
                          className="h-full rounded-full bg-primary"
                          style={{
                            width: `${Math.min(100, (e.progress / challenge.target_value) * 100)}%`,
                          }}
                        />
                      </div>
                      <span className="text-sm">
                        {e.progress.toFixed(1)}/{challenge.target_value} {unit}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell>
                    <Badge
                      variant={e.completed ? "success" : "secondary"}
                    >
                      {e.completed ? "Completed" : "In Progress"}
                    </Badge>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      )}
    </Card>
  );
}
