import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'

type Athlete = {
  id: number
  first_name: string
  last_name: string
}

type TrainingLog = {
  id: number
  date: string
  session_category: string
  duration_min: number
  distance_km: number
  rpe: number
  load_score: number
}

export default function Analytics() {
  const { auth } = useAuth()
  const [athletes, setAthletes] = useState<Athlete[]>([])
  const [selected, setSelected] = useState<number | null>(null)
  const [logs, setLogs] = useState<TrainingLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auth) return
    api<{ items: Athlete[] }>('/athletes?status=active&offset=0&limit=50', {}, auth.token).then(
      (r) => {
        setAthletes(r.items)
        if (r.items.length > 0) setSelected(r.items[0].id)
        setLoading(false)
      },
    )
  }, [auth])

  useEffect(() => {
    if (!auth || !selected) return
    api<{ items: TrainingLog[] }>(
      `/training-logs?athlete_id=${selected}&limit=30`,
      {},
      auth.token,
    ).then((r) => setLogs(r.items))
  }, [auth, selected])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  const totalLoad = logs.reduce((sum, l) => sum + l.load_score, 0)
  const totalDistance = logs.reduce((sum, l) => sum + l.distance_km, 0)
  const totalDuration = logs.reduce((sum, l) => sum + l.duration_min, 0)
  const avgRpe = logs.length ? (logs.reduce((sum, l) => sum + l.rpe, 0) / logs.length).toFixed(1) : '—'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Analytics</h2>
        <select
          value={selected ?? ''}
          onChange={(e) => setSelected(Number(e.target.value))}
          className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-white"
        >
          {athletes.map((a) => (
            <option key={a.id} value={a.id}>
              {a.first_name} {a.last_name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <StatCard label="Total Load" value={totalLoad.toFixed(1)} />
        <StatCard label="Total Distance" value={`${totalDistance.toFixed(1)} km`} />
        <StatCard label="Total Duration" value={`${totalDuration} min`} />
        <StatCard label="Avg RPE" value={avgRpe} />
      </div>

      <div>
        <h3 className="mb-3 text-lg font-semibold">Recent Sessions</h3>
        <div className="overflow-hidden rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-slate-400">Date</th>
                <th className="px-4 py-2 text-slate-400">Category</th>
                <th className="px-4 py-2 text-slate-400">Duration</th>
                <th className="px-4 py-2 text-slate-400">Distance</th>
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
                  <td className="px-4 py-2">{l.distance_km.toFixed(1)}km</td>
                  <td className="px-4 py-2">{l.rpe}/10</td>
                  <td className="px-4 py-2">{l.load_score.toFixed(1)}</td>
                </tr>
              ))}
              {!logs.length && (
                <tr>
                  <td colSpan={6} className="px-4 py-4 text-center text-slate-500">
                    No training data
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

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </div>
  )
}
