import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import {
  BarChart3,
  ClipboardList,
  Home,
  LogOut,
  AlertTriangle,
  Calendar,
  Dumbbell,
  Map,
  Users,
} from 'lucide-react'

const coachLinks = [
  { to: '/coach', label: 'Dashboard', icon: Home },
  { to: '/coach/athletes', label: 'Athletes', icon: Users },
  { to: '/coach/interventions', label: 'Interventions', icon: AlertTriangle },
  { to: '/coach/analytics', label: 'Analytics', icon: BarChart3 },
]

const athleteLinks = [
  { to: '/athlete', label: 'Dashboard', icon: Home },
  { to: '/athlete/checkin', label: 'Check-in', icon: ClipboardList },
  { to: '/athlete/training', label: 'Training', icon: Dumbbell },
  { to: '/athlete/plan', label: 'Plan', icon: Calendar },
  { to: '/athlete/events', label: 'Events', icon: Map },
]

export default function DashboardLayout() {
  const { auth, logout } = useAuth()
  const location = useLocation()
  const links = auth?.role === 'coach' ? coachLinks : athleteLinks

  return (
    <div className="flex h-screen">
      <aside className="flex w-56 flex-col border-r border-slate-700 bg-slate-900">
        <div className="border-b border-slate-700 px-4 py-4">
          <h1 className="text-lg font-semibold text-teal-400">Run Season</h1>
          <p className="text-xs text-slate-400">{auth?.role === 'coach' ? 'Coach' : 'Athlete'}</p>
        </div>
        <nav className="flex-1 space-y-1 p-2">
          {links.map(({ to, label, icon: Icon }) => {
            const active = location.pathname === to
            return (
              <Link
                key={to}
                to={to}
                className={`flex items-center gap-2 rounded px-3 py-2 text-sm transition ${
                  active
                    ? 'bg-teal-600/20 text-teal-300'
                    : 'text-slate-300 hover:bg-slate-800 hover:text-white'
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            )
          })}
        </nav>
        <div className="border-t border-slate-700 p-2">
          <button
            onClick={logout}
            className="flex w-full items-center gap-2 rounded px-3 py-2 text-sm text-slate-400 hover:bg-slate-800 hover:text-white"
          >
            <LogOut size={16} />
            Sign out
          </button>
        </div>
      </aside>
      <main className="flex-1 overflow-y-auto bg-slate-950 p-6">
        <Outlet />
      </main>
    </div>
  )
}
