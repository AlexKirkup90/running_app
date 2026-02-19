import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "@/stores/auth";

interface Props {
  children: React.ReactNode;
  role?: string;
}

export function RequireAuth({ children, role }: Props) {
  const { isAuthenticated, role: userRole } = useAuthStore();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (role && userRole !== role) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
}
