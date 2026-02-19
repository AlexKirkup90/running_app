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
