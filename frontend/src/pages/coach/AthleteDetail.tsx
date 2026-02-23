import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'

type Athlete = {
  id: number
  first_name: string
  last_name: string
  email: string
  status: string
  max_hr?: number
  resting_hr?: number
  threshold_pace_sec_per_km?: number
  easy_pace_sec_per_km?: number
}

type CheckIn = {
  id: number
  day: string
  sleep: number
  energy: number
  recovery: number
  stress: number
  readiness_score?: number
  readiness_band?: string
}

type TrainingLog = {
  id: number
  date: string
  session_category: string
  duration_min: number
  distance_km: number
  rpe: number
  load_score: number
  pain_flag: boolean
}

const bandColor: Record<string, string> = {
  green: 'text-emerald-400',
  amber: 'text-amber-400',
  red: 'text-red-400',
}

export default function AthleteDetail() {
  const { id } = useParams<{ id: string }>()
  const { auth } = useAuth()
  const [athlete, setAthlete] = useState<Athlete | null>(null)
  const [checkins, setCheckins] = useState<CheckIn[]>([])
  const [logs, setLogs] = useState<TrainingLog[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auth || !id) return
    Promise.all([
      api<Athlete>(`/athletes/${id}`, {}, auth.token),
      api<{ items: CheckIn[] }>(`/checkins?athlete_id=${id}&limit=14`, {}, auth.token),
      api<{ items: TrainingLog[] }>(`/training-logs?athlete_id=${id}&limit=14`, {}, auth.token),
    ]).then(([a, c, l]) => {
      setAthlete(a)
      setCheckins(c.items)
      setLogs(l.items)
      setLoading(false)
    })
  }, [auth, id])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-48" />
        <Skeleton className="h-48" />
      </div>
    )
  }

  if (!athlete) return <p>Athlete not found</p>

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">
          {athlete.first_name} {athlete.last_name}
        </h2>
        <p className="text-sm text-slate-400">{athlete.email}</p>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Max HR" value={athlete.max_hr ?? '—'} />
        <Stat label="Resting HR" value={athlete.resting_hr ?? '—'} />
        <Stat label="Threshold Pace" value={athlete.threshold_pace_sec_per_km ? formatPace(athlete.threshold_pace_sec_per_km) : '—'} />
        <Stat label="Easy Pace" value={athlete.easy_pace_sec_per_km ? formatPace(athlete.easy_pace_sec_per_km) : '—'} />
      </div>

      <div>
        <h3 className="mb-3 text-lg font-semibold">Recent Check-ins</h3>
        <div className="overflow-hidden rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-slate-400">Date</th>
                <th className="px-4 py-2 text-slate-400">Sleep</th>
                <th className="px-4 py-2 text-slate-400">Energy</th>
                <th className="px-4 py-2 text-slate-400">Recovery</th>
                <th className="px-4 py-2 text-slate-400">Stress</th>
                <th className="px-4 py-2 text-slate-400">Readiness</th>
              </tr>
            </thead>
            <tbody>
              {checkins.map((c) => (
                <tr key={c.id} className="border-b border-slate-800">
                  <td className="px-4 py-2">{c.day}</td>
                  <td className="px-4 py-2">{c.sleep}</td>
                  <td className="px-4 py-2">{c.energy}</td>
                  <td className="px-4 py-2">{c.recovery}</td>
                  <td className="px-4 py-2">{c.stress}</td>
                  <td className={`px-4 py-2 font-medium ${bandColor[c.readiness_band ?? ''] ?? ''}`}>
                    {c.readiness_score?.toFixed(1) ?? '—'} {c.readiness_band ?? ''}
                  </td>
                </tr>
              ))}
              {!checkins.length && (
                <tr>
                  <td colSpan={6} className="px-4 py-4 text-center text-slate-500">
                    No check-ins yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-lg font-semibold">Recent Training Logs</h3>
        <div className="overflow-hidden rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-slate-400">Date</th>
                <th className="px-4 py-2 text-slate-400">Session</th>
                <th className="px-4 py-2 text-slate-400">Duration</th>
                <th className="px-4 py-2 text-slate-400">Distance</th>
                <th className="px-4 py-2 text-slate-400">RPE</th>
                <th className="px-4 py-2 text-slate-400">Load</th>
                <th className="px-4 py-2 text-slate-400">Pain</th>
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
                  <td className="px-4 py-2">{l.pain_flag ? '⚠' : '—'}</td>
                </tr>
              ))}
              {!logs.length && (
                <tr>
                  <td colSpan={7} className="px-4 py-4 text-center text-slate-500">
                    No logs yet
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

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="text-lg font-semibold">{value}</p>
    </div>
  )
}

function formatPace(secPerKm: number): string {
  const min = Math.floor(secPerKm / 60)
  const sec = Math.round(secPerKm % 60)
  return `${min}:${sec.toString().padStart(2, '0')}/km`
}
