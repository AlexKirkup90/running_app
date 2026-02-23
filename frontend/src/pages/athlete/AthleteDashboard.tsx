import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'
import { ClipboardList, Dumbbell, Calendar } from 'lucide-react'

type CheckIn = {
  id: number
  day: string
  readiness_score?: number
  readiness_band?: string
}

type TrainingLog = {
  id: number
  date: string
  session_category: string
  duration_min: number
  rpe: number
  load_score: number
}

const bandColor: Record<string, string> = {
  green: 'text-emerald-400 bg-emerald-600/20',
  amber: 'text-amber-400 bg-amber-600/20',
  red: 'text-red-400 bg-red-600/20',
}

export default function AthleteDashboard() {
  const { auth } = useAuth()
  const [checkins, setCheckins] = useState<CheckIn[]>([])
  const [logs, setLogs] = useState<TrainingLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auth) return
    Promise.all([
      api<{ items: CheckIn[] }>('/checkins?limit=7', {}, auth.token),
      api<{ items: TrainingLog[] }>('/training-logs?limit=7', {}, auth.token),
    ]).then(([c, l]) => {
      setCheckins(c.items)
      setLogs(l.items)
      setLoading(false)
    })
  }, [auth])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-3 gap-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      </div>
    )
  }

  const latest = checkins[0]
  const weekLoad = logs.reduce((sum, l) => sum + l.load_score, 0)

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Athlete Dashboard</h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Link to="/athlete/checkin" className="rounded-lg border border-slate-700 bg-slate-900 p-4 hover:border-teal-600">
          <div className="flex items-center gap-2 text-slate-400">
            <ClipboardList size={16} />
            <span className="text-sm">Today's Readiness</span>
          </div>
          {latest?.readiness_band ? (
            <span className={`mt-1 inline-block rounded px-2 py-0.5 text-lg font-bold ${bandColor[latest.readiness_band] ?? ''}`}>
              {latest.readiness_score?.toFixed(1)} ({latest.readiness_band})
            </span>
          ) : (
            <p className="mt-1 text-lg font-bold text-slate-500">No check-in today</p>
          )}
        </Link>

        <Link to="/athlete/training" className="rounded-lg border border-slate-700 bg-slate-900 p-4 hover:border-teal-600">
          <div className="flex items-center gap-2 text-slate-400">
            <Dumbbell size={16} />
            <span className="text-sm">Recent Load (7 sessions)</span>
          </div>
          <p className="mt-1 text-3xl font-bold">{weekLoad.toFixed(1)}</p>
        </Link>

        <Link to="/athlete/plan" className="rounded-lg border border-slate-700 bg-slate-900 p-4 hover:border-teal-600">
          <div className="flex items-center gap-2 text-slate-400">
            <Calendar size={16} />
            <span className="text-sm">Sessions This Week</span>
          </div>
          <p className="mt-1 text-3xl font-bold">{logs.length}</p>
        </Link>
      </div>

      <div>
        <h3 className="mb-3 text-lg font-semibold">Recent Sessions</h3>
        <div className="overflow-hidden rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-slate-400">Date</th>
                <th className="px-4 py-2 text-slate-400">Session</th>
                <th className="px-4 py-2 text-slate-400">Duration</th>
                <th className="px-4 py-2 text-slate-400">RPE</th>
                <th className="px-4 py-2 text-slate-400">Load</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((l) => (
                <tr key={l.id} className="border-b border-slate-800">
                  <td className="px-4 py-2">{l.date}</td>
                  <td className="px-4 py-2">{l.session_category}</td>
                  <td className="px-4 py-2">{l.duration_min}m</td>
                  <td className="px-4 py-2">{l.rpe}/10</td>
                  <td className="px-4 py-2">{l.load_score.toFixed(1)}</td>
                </tr>
              ))}
              {!logs.length && (
                <tr>
                  <td colSpan={5} className="px-4 py-4 text-center text-slate-500">
                    No recent sessions
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
