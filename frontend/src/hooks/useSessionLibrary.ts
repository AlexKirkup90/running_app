import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchSessions,
  fetchSession,
  createSession,
  updateSession,
  deleteSession,
  fetchSessionCategories,
} from "@/api/client";
import type { SessionTemplate } from "@/api/types";

export function useSessions(params?: {
  category?: string;
  intent?: string;
  is_treadmill?: boolean;
}) {
  return useQuery({
    queryKey: ["sessions", params],
    queryFn: () => fetchSessions(params),
  });
}

export function useSession(sessionId: number) {
  return useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => fetchSession(sessionId),
    enabled: sessionId > 0,
  });
}

export function useSessionCategories() {
  return useQuery({
    queryKey: ["session-categories"],
    queryFn: fetchSessionCategories,
    staleTime: 5 * 60 * 1000,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Omit<SessionTemplate, "id">) => createSession(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["session-categories"] });
    },
  });
}

export function useUpdateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: Omit<SessionTemplate, "id"> }) =>
      updateSession(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      queryClient.invalidateQueries({ queryKey: ["session"] });
    },
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: deleteSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });
}
