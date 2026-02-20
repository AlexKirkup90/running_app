import { useQuery } from "@tanstack/react-query";
import {
  fetchPlans,
  fetchPlanWeeks,
  fetchPlanSessions,
  fetchEvents,
  createEvent,
} from "@/api/client";
import { useMutation, useQueryClient } from "@tanstack/react-query";

export function usePlans(athleteId?: number, status = "active") {
  return useQuery({
    queryKey: ["plans", athleteId, status],
    queryFn: () => fetchPlans(athleteId, status),
    enabled: athleteId === undefined || athleteId > 0,
  });
}

export function usePlanWeeks(planId: number) {
  return useQuery({
    queryKey: ["plan-weeks", planId],
    queryFn: () => fetchPlanWeeks(planId),
    enabled: planId > 0,
  });
}

export function usePlanSessions(planId: number) {
  return useQuery({
    queryKey: ["plan-sessions", planId],
    queryFn: () => fetchPlanSessions(planId),
    enabled: planId > 0,
  });
}

export function useEvents(athleteId?: number) {
  return useQuery({
    queryKey: ["events", athleteId],
    queryFn: () => fetchEvents(athleteId),
    enabled: athleteId === undefined || athleteId > 0,
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["events"] });
    },
  });
}
