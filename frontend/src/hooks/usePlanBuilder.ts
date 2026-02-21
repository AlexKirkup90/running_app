import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  previewPlan,
  createPlan,
  toggleWeekLock,
  swapSession,
  regenerateWeek,
} from "@/api/client";

export function usePreviewPlan() {
  return useMutation({
    mutationFn: previewPlan,
  });
}

export function useCreatePlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: createPlan,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plans"] });
      queryClient.invalidateQueries({ queryKey: ["plan-weeks"] });
      queryClient.invalidateQueries({ queryKey: ["plan-sessions"] });
    },
  });
}

export function useToggleWeekLock() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, weekNumber }: { planId: number; weekNumber: number }) =>
      toggleWeekLock(planId, weekNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan-weeks"] });
    },
  });
}

export function useSwapSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      planId,
      weekNumber,
      sessionDay,
      newSessionName,
    }: {
      planId: number;
      weekNumber: number;
      sessionDay: string;
      newSessionName: string;
    }) => swapSession(planId, weekNumber, sessionDay, newSessionName),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan-weeks"] });
      queryClient.invalidateQueries({ queryKey: ["plan-sessions"] });
    },
  });
}

export function useRegenerateWeek() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ planId, weekNumber }: { planId: number; weekNumber: number }) =>
      regenerateWeek(planId, weekNumber),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["plan-weeks"] });
      queryClient.invalidateQueries({ queryKey: ["plan-sessions"] });
    },
  });
}
