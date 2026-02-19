import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  decideIntervention,
  fetchAthletes,
  fetchInterventions,
  fetchRecommendation,
  syncInterventions,
} from "@/api/client";

/** Fetch interventions filtered by status, optionally by athlete. */
export function useInterventions(status = "open", athleteId?: number) {
  return useQuery({
    queryKey: ["interventions", status, athleteId],
    queryFn: () => fetchInterventions(status, athleteId),
  });
}

/** Fetch all active athletes (used for name resolution). */
export function useAthletes() {
  return useQuery({
    queryKey: ["athletes"],
    queryFn: () => fetchAthletes("active"),
    staleTime: 5 * 60 * 1000,
  });
}

/** Fetch a recommendation for a specific athlete. */
export function useRecommendation(athleteId: number) {
  return useQuery({
    queryKey: ["recommendation", athleteId],
    queryFn: () => fetchRecommendation(athleteId),
    enabled: athleteId > 0,
  });
}

/** Mutation: sync (refresh) the intervention queue. */
export function useSyncInterventions() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: syncInterventions,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["interventions"] });
    },
  });
}

/** Mutation: accept/dismiss/defer an intervention. */
export function useDecideIntervention() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      interventionId,
      decision,
      note,
      modifiedAction,
    }: {
      interventionId: number;
      decision: string;
      note?: string;
      modifiedAction?: string;
    }) => decideIntervention(interventionId, decision, note, modifiedAction),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["interventions"] });
      queryClient.invalidateQueries({ queryKey: ["coach-dashboard"] });
    },
  });
}
