import { NavLink } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  AlertTriangle,
  LogOut,
  ClipboardCheck,
  Dumbbell,
  CalendarDays,
  Target,
  TrendingUp,
  Building2,
  Shield,
  ArrowRightLeft,
  HeartHandshake,
  Hammer,
  BookOpen,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { cn } from "@/lib/utils";

const coachLinks = [
  { to: "/coach", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/coach/clients", icon: Users, label: "Clients" },
  { to: "/coach/plan-builder", icon: Hammer, label: "Plan Builder" },
  { to: "/coach/session-library", icon: BookOpen, label: "Session Library" },
  { to: "/coach/command-center", icon: AlertTriangle, label: "Command Center" },
  { to: "/coach/community", icon: HeartHandshake, label: "Community" },
  { to: "/coach/organization", icon: Building2, label: "Organization" },
  { to: "/coach/team", icon: Shield, label: "Team" },
  { to: "/coach/assignments", icon: ArrowRightLeft, label: "Assignments" },
];

const athleteLinks = [
  { to: "/athlete", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/athlete/checkin", icon: ClipboardCheck, label: "Check-In" },
  { to: "/athlete/log", icon: Dumbbell, label: "Log Session" },
  { to: "/athlete/plans", icon: Target, label: "Plans" },
  { to: "/athlete/events", icon: CalendarDays, label: "Events" },
  { to: "/athlete/analytics", icon: TrendingUp, label: "Analytics" },
  { to: "/athlete/community", icon: HeartHandshake, label: "Community" },
];

export function Sidebar() {
  const { role, username, logout } = useAuthStore();
  const links = role === "coach" ? coachLinks : athleteLinks;

  return (
    <aside className="flex h-screen w-64 flex-col border-r bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <span className="text-lg font-bold tracking-tight text-primary">
          Run Season
        </span>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        {links.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/coach" || to === "/athlete"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
              )
            }
          >
            <Icon className="h-4 w-4" />
            {label}
          </NavLink>
        ))}
      </nav>

      <div className="border-t p-3">
        <div className="mb-2 px-3 text-xs text-muted-foreground">
          {username} ({role})
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
