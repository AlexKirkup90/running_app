import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'

type Plan = {
  id: number
  race_goal: string
  weeks: number
  sessions_per_week: number
  start_date: string
  status: string
}

type PlanWeek = {
  id: number
  week_number: number
  phase: string
  week_start: string
  week_end: string
  target_load: number
  locked: boolean
}

const phaseColor: Record<string, string> = {
  Base: 'bg-sky-600/20 text-sky-400',
  Build: 'bg-amber-600/20 text-amber-400',
  Peak: 'bg-red-600/20 text-red-400',
  Taper: 'bg-purple-600/20 text-purple-400',
  Recovery: 'bg-emerald-600/20 text-emerald-400',
}

export default function PlanPage() {
  const { auth } = useAuth()
  const [plans, setPlans] = useState<Plan[]>([])
  const [selected, setSelected] = useState<Plan | null>(null)
  const [weeks, setWeeks] = useState<PlanWeek[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auth) return
    api<Plan[]>('/plans?status=all', {}, auth.token).then((r) => {
      setPlans(r)
      if (r.length > 0) setSelected(r[0])
      setLoading(false)
    })
  }, [auth])

  useEffect(() => {
    if (!auth || !selected) return
    api<PlanWeek[]>(`/plans/${selected.id}/weeks`, {}, auth.token).then(setWeeks)
  }, [auth, selected])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  if (!plans.length) {
    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold">Training Plan</h2>
        <p className="text-slate-500">No plans assigned yet</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Training Plan</h2>
        {plans.length > 1 && (
          <select
            value={selected?.id ?? ''}
            onChange={(e) => setSelected(plans.find((p) => p.id === Number(e.target.value)) ?? null)}
            className="rounded border border-slate-600 bg-slate-800 px-3 py-1.5 text-sm text-white"
          >
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.race_goal} ({p.status})
              </option>
            ))}
          </select>
        )}
      </div>

      {selected && (
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <StatCard label="Race Goal" value={selected.race_goal} />
          <StatCard label="Total Weeks" value={String(selected.weeks)} />
          <StatCard label="Sessions/Week" value={String(selected.sessions_per_week)} />
          <StatCard label="Start Date" value={selected.start_date} />
        </div>
      )}

      <div>
        <h3 className="mb-3 text-lg font-semibold">Week Schedule</h3>
        <div className="overflow-hidden rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-slate-400">Week</th>
                <th className="px-4 py-2 text-slate-400">Phase</th>
                <th className="px-4 py-2 text-slate-400">Dates</th>
                <th className="px-4 py-2 text-slate-400">Target Load</th>
                <th className="px-4 py-2 text-slate-400">Status</th>
              </tr>
            </thead>
            <tbody>
              {weeks.map((w) => (
                <tr key={w.id} className="border-b border-slate-800">
                  <td className="px-4 py-2">{w.week_number}</td>
                  <td className="px-4 py-2">
                    <span className={`rounded px-2 py-0.5 text-xs ${phaseColor[w.phase] ?? 'bg-slate-600/20 text-slate-400'}`}>
                      {w.phase}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-400">
                    {w.week_start} &mdash; {w.week_end}
                  </td>
                  <td className="px-4 py-2">{w.target_load.toFixed(1)}</td>
                  <td className="px-4 py-2">{w.locked ? 'Locked' : 'Open'}</td>
                </tr>
              ))}
              {!weeks.length && (
                <tr>
                  <td colSpan={5} className="px-4 py-4 text-center text-slate-500">
                    No weeks generated
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
    <div className="rounded-lg border border-slate-700 bg-slate-900 p-3">
      <p className="text-xs text-slate-400">{label}</p>
      <p className="mt-0.5 text-lg font-semibold">{value}</p>
    </div>
  )
}
