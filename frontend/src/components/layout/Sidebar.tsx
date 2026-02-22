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
  HeartHandshake,
  Hammer,
  BookOpen,
  UserCircle,
  BarChart3,
  Link2,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth";
import { cn } from "@/lib/utils";

const coachLinks = [
  { to: "/coach", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/coach/clients", icon: Users, label: "Clients" },
  { to: "/coach/plan-builder", icon: Hammer, label: "Plan Builder" },
  { to: "/coach/session-library", icon: BookOpen, label: "Session Library" },
  { to: "/coach/command-center", icon: AlertTriangle, label: "Command Center" },
  { to: "/coach/analytics", icon: BarChart3, label: "Analytics" },
  { to: "/coach/community", icon: HeartHandshake, label: "Community" },
  { to: "/coach/organization", icon: Building2, label: "Organization" },
  { to: "/coach/integrations", icon: Link2, label: "Integrations" },
];

const athleteLinks = [
  { to: "/athlete", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/athlete/checkin", icon: ClipboardCheck, label: "Check-In" },
  { to: "/athlete/log", icon: Dumbbell, label: "Log Session" },
  { to: "/athlete/plans", icon: Target, label: "Plans" },
  { to: "/athlete/events", icon: CalendarDays, label: "Events" },
  { to: "/athlete/analytics", icon: TrendingUp, label: "Analytics" },
  { to: "/athlete/community", icon: HeartHandshake, label: "Community" },
  { to: "/athlete/profile", icon: UserCircle, label: "Profile" },
];

export function Sidebar() {
  const { role, username, logout } = useAuthStore();
  const links = role === "coach" ? coachLinks : athleteLinks;
  const roleLabel = role === "coach" ? "Coach" : "Athlete";

  return (
    <aside className="flex h-screen w-64 shrink-0 flex-col border-r bg-card">
      <div className="flex h-14 items-center justify-between border-b px-4">
        <span className="text-lg font-bold tracking-tight text-primary">
          Run Season
        </span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
            role === "coach"
              ? "bg-blue-100 text-blue-700"
              : "bg-emerald-100 text-emerald-700",
          )}
        >
          {roleLabel}
        </span>
      </div>

      <nav className="flex-1 overflow-y-auto space-y-1 p-3">
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
          {username}
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
