import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../../contexts/AuthContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'

type Athlete = {
  id: number
  first_name: string
  last_name: string
  email: string
  status: string
}

export default function AthleteList() {
  const { auth } = useAuth()
  const [athletes, setAthletes] = useState<Athlete[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!auth) return
    api<{ items: Athlete[] }>('/athletes?status=all&offset=0&limit=100', {}, auth.token).then(
      (r) => {
        setAthletes(r.items)
        setLoading(false)
      },
    )
  }, [auth])

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-64" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Athletes</h2>
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
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${
                      a.status === 'active'
                        ? 'bg-emerald-600/20 text-emerald-400'
                        : 'bg-slate-600/20 text-slate-400'
                    }`}
                  >
                    {a.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
