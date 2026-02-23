import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'
import { AlertTriangle, Users } from 'lucide-react'

type Athlete = {
  id: number
  first_name: string
  last_name: string
  email: string
  status: string
}

type Intervention = {
  id: number
  athlete_id: number
  action_type: string
  status: string
  risk_score: number
}

export default function CoachDashboard() {
  const { auth } = useAuth()
  const [athletes, setAthletes] = useState<Athlete[]>([])
  const [interventions, setInterventions] = useState<Intervention[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auth) return
    Promise.all([
      api<{ items: Athlete[] }>('/athletes?status=active&offset=0&limit=50', {}, auth.token),
      api<Intervention[]>('/interventions?status=open', {}, auth.token),
    ]).then(([a, i]) => {
      setAthletes(a.items)
      setInterventions(i)
      setLoading(false)
    })
  }, [auth])

  useEffect(() => {
    const ws = new WebSocket(`ws://${location.hostname}:8000/api/v1/ws/coach`)
    ws.onmessage = () => {
      if (!auth) return
      api<{ items: Athlete[] }>('/athletes?status=active&offset=0&limit=50', {}, auth.token).then((r) =>
        setAthletes(r.items),
      )
    }
    return () => ws.close()
  }, [auth])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <div className="grid grid-cols-2 gap-4">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
        <Skeleton className="h-64" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Coach Command Center</h2>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <Users size={16} />
            <span className="text-sm">Active Athletes</span>
          </div>
          <p className="mt-1 text-3xl font-bold">{athletes.length}</p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="flex items-center gap-2 text-slate-400">
            <AlertTriangle size={16} />
            <span className="text-sm">Open Interventions</span>
          </div>
          <p className="mt-1 text-3xl font-bold">{interventions.length}</p>
        </div>
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <AlertTriangle size={16} />
            <span className="text-sm">High Risk</span>
          </div>
          <p className="mt-1 text-3xl font-bold">
            {interventions.filter((i) => i.risk_score >= 0.7).length}
          </p>
        </div>
      </div>

      <div>
        <h3 className="mb-3 text-lg font-semibold">Athletes</h3>
        <div className="overflow-hidden rounded-lg border border-slate-700">
          <table className="w-full text-left text-sm">
            <thead className="border-b border-slate-700 bg-slate-900">
              <tr>
                <th className="px-4 py-2 text-slate-400">Name</th>
                <th className="px-4 py-2 text-slate-400">Email</th>
                <th className="px-4 py-2 text-slate-400">Status</th>
              </tr>
            </thead>
            <tbody>
              {athletes.map((a) => (
                <tr key={a.id} className="border-b border-slate-800 hover:bg-slate-900/50">
                  <td className="px-4 py-2">
                    <Link to={`/coach/athletes/${a.id}`} className="text-teal-400 hover:underline">
                      {a.first_name} {a.last_name}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-slate-400">{a.email}</td>
                  <td className="px-4 py-2">
                    <span className="rounded bg-emerald-600/20 px-2 py-0.5 text-xs text-emerald-400">
                      {a.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
