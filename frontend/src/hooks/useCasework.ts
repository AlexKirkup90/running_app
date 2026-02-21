import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchAthleteTimeline,
  fetchAthleteNotes,
  createAthleteNote,
  updateAthleteNote,
  deleteAthleteNote,
  fetchInterventionStats,
  batchDecideInterventions,
} from "@/api/client";

export function useAthleteTimeline(athleteId: number, limit = 120) {
  return useQuery({
    queryKey: ["athlete-timeline", athleteId, limit],
    queryFn: () => fetchAthleteTimeline(athleteId, limit),
    enabled: athleteId > 0,
  });
}

export function useAthleteNotes(athleteId: number) {
  return useQuery({
    queryKey: ["athlete-notes", athleteId],
    queryFn: () => fetchAthleteNotes(athleteId),
    enabled: athleteId > 0,
  });
}

export function useCreateNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      athleteId,
      note,
      dueDate,
    }: {
      athleteId: number;
      note: string;
      dueDate?: string | null;
    }) => createAthleteNote(athleteId, { note, due_date: dueDate }),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["athlete-notes", vars.athleteId] });
      queryClient.invalidateQueries({ queryKey: ["athlete-timeline", vars.athleteId] });
    },
  });
}

export function useToggleNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      athleteId,
      noteId,
      completed,
    }: {
      athleteId: number;
      noteId: number;
      completed: boolean;
    }) => updateAthleteNote(athleteId, noteId, completed),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["athlete-notes", vars.athleteId] });
    },
  });
}

export function useDeleteNote() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ athleteId, noteId }: { athleteId: number; noteId: number }) =>
      deleteAthleteNote(athleteId, noteId),
    onSuccess: (_data, vars) => {
      queryClient.invalidateQueries({ queryKey: ["athlete-notes", vars.athleteId] });
    },
  });
}

export function useInterventionStats() {
  return useQuery({
    queryKey: ["intervention-stats"],
    queryFn: fetchInterventionStats,
    refetchInterval: 60_000,
  });
}

export function useBatchDecide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: batchDecideInterventions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["interventions"] });
      queryClient.invalidateQueries({ queryKey: ["intervention-stats"] });
      queryClient.invalidateQueries({ queryKey: ["coach-dashboard"] });
    },
  });
}
