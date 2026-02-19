import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createCheckin,
  createTrainingLog,
  fetchCheckins,
  fetchRecommendation,
  fetchTrainingLogs,
} from "@/api/client";

/** Fetch check-ins for an athlete. */
export function useCheckins(athleteId: number, limit = 30) {
  return useQuery({
    queryKey: ["checkins", athleteId, limit],
    queryFn: () => fetchCheckins(athleteId, limit),
    enabled: athleteId > 0,
  });
}

/** Fetch training logs for an athlete. */
export function useTrainingLogs(athleteId: number, limit = 30) {
  return useQuery({
    queryKey: ["training-logs", athleteId, limit],
    queryFn: () => fetchTrainingLogs(athleteId, limit),
    enabled: athleteId > 0,
  });
}

/** Fetch recommendation for an athlete. */
export function useRecommendation(athleteId: number) {
  return useQuery({
    queryKey: ["recommendation", athleteId],
    queryFn: () => fetchRecommendation(athleteId),
    enabled: athleteId > 0,
  });
}

/** Mutation: create/upsert today's check-in. */
export function useCreateCheckin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createCheckin,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["checkins"] });
    },
  });
}

/** Mutation: create/upsert today's training log. */
export function useCreateTrainingLog() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createTrainingLog,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["training-logs"] });
    },
  });
}
