import { useQuery } from "@tanstack/react-query";
import {
  fetchSessionBriefing,
  fetchTrainingLoadSummary,
  fetchFitnessFatigue,
  fetchVdotHistory,
  fetchRacePredictions,
  fetchAthleteProfile,
} from "@/api/client";

export function useSessionBriefing(athleteId: number) {
  return useQuery({
    queryKey: ["session-briefing", athleteId],
    queryFn: () => fetchSessionBriefing(athleteId),
    enabled: athleteId > 0,
  });
}

export function useTrainingLoadSummary(athleteId: number) {
  return useQuery({
    queryKey: ["training-load-summary", athleteId],
    queryFn: () => fetchTrainingLoadSummary(athleteId),
    enabled: athleteId > 0,
  });
}

export function useFitnessFatigue(athleteId: number) {
  return useQuery({
    queryKey: ["fitness-fatigue", athleteId],
    queryFn: () => fetchFitnessFatigue(athleteId),
    enabled: athleteId > 0,
  });
}

export function useVdotHistory(athleteId: number) {
  return useQuery({
    queryKey: ["vdot-history", athleteId],
    queryFn: () => fetchVdotHistory(athleteId),
    enabled: athleteId > 0,
  });
}

export function useRacePredictions(athleteId: number) {
  return useQuery({
    queryKey: ["race-predictions", athleteId],
    queryFn: () => fetchRacePredictions(athleteId),
    enabled: athleteId > 0,
  });
}

export function useAthleteProfile(athleteId: number) {
  return useQuery({
    queryKey: ["athlete-profile", athleteId],
    queryFn: () => fetchAthleteProfile(athleteId),
    enabled: athleteId > 0,
  });
}
