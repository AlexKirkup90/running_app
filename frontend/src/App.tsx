import { useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/auth";
import { AppLayout } from "@/components/layout/AppLayout";
import { RequireAuth } from "@/components/layout/RequireAuth";
import { LoginPage } from "@/pages/Login";
import { CoachDashboard } from "@/pages/coach/Dashboard";
import { CoachClients } from "@/pages/coach/Clients";
import { CoachCommandCenter } from "@/pages/coach/CommandCenter";
import { CoachOrganization } from "@/pages/coach/Organization";
import { CoachTeam } from "@/pages/coach/Team";
import { CoachAssignments } from "@/pages/coach/Assignments";
import { CoachCommunity } from "@/pages/coach/Community";
import { CoachPlanBuilder } from "@/pages/coach/PlanBuilder";
import { CoachSessionLibrary } from "@/pages/coach/SessionLibrary";
import { AthleteDashboard } from "@/pages/athlete/Dashboard";
import { AthleteCheckIn } from "@/pages/athlete/CheckIn";
import { AthleteLog } from "@/pages/athlete/Log";
import { AthletePlans } from "@/pages/athlete/Plans";
import { AthleteEvents } from "@/pages/athlete/Events";
import { AthleteAnalytics } from "@/pages/athlete/Analytics";
import { AthleteCommunity } from "@/pages/athlete/Community";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

function AppRoutes() {
  const { isAuthenticated, role, hydrate } = useAuthStore();

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      {/* Coach routes */}
      <Route
        element={
          <RequireAuth role="coach">
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/coach" element={<CoachDashboard />} />
        <Route path="/coach/clients" element={<CoachClients />} />
        <Route path="/coach/command-center" element={<CoachCommandCenter />} />
        <Route path="/coach/plan-builder" element={<CoachPlanBuilder />} />
        <Route path="/coach/session-library" element={<CoachSessionLibrary />} />
        <Route path="/coach/organization" element={<CoachOrganization />} />
        <Route path="/coach/team" element={<CoachTeam />} />
        <Route path="/coach/assignments" element={<CoachAssignments />} />
        <Route path="/coach/community" element={<CoachCommunity />} />
      </Route>

      {/* Athlete routes */}
      <Route
        element={
          <RequireAuth role="client">
            <AppLayout />
          </RequireAuth>
        }
      >
        <Route path="/athlete" element={<AthleteDashboard />} />
        <Route path="/athlete/checkin" element={<AthleteCheckIn />} />
        <Route path="/athlete/log" element={<AthleteLog />} />
        <Route path="/athlete/plans" element={<AthletePlans />} />
        <Route path="/athlete/events" element={<AthleteEvents />} />
        <Route path="/athlete/analytics" element={<AthleteAnalytics />} />
        <Route path="/athlete/community" element={<AthleteCommunity />} />
      </Route>

      {/* Root redirect */}
      <Route
        path="/"
        element={
          isAuthenticated ? (
            <Navigate to={role === "coach" ? "/coach" : "/athlete"} replace />
          ) : (
            <Navigate to="/login" replace />
          )
        }
      />

      {/* Catch-all */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  );
}
