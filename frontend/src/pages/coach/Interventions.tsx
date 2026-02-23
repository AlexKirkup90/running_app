import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'

type Intervention = {
  id: number
  athlete_id: number
  action_type: string
  status: string
  risk_score: number
  confidence_score: number
  expected_impact: Record<string, unknown>
  why_factors: string[]
  guardrail_pass: boolean
  guardrail_reason: string
}

export default function Interventions() {
  const { auth } = useAuth()
  const { toast } = useToast()
  const [items, setItems] = useState<Intervention[]>([])
  const [loading, setLoading] = useState(true)
  const [deciding, setDeciding] = useState<number | null>(null)

  const load = () => {
    if (!auth) return
    api<Intervention[]>('/interventions?status=open', {}, auth.token).then((r) => {
      setItems(r)
      setLoading(false)
    })
  }

  useEffect(load, [auth])

  const decide = async (id: number, decision: string) => {
    if (!auth) return
    setDeciding(id)
    try {
      await api<{ message: string }>(
        `/interventions/${id}/decide`,
        { method: 'POST', body: JSON.stringify({ decision, note: '', modified_action: null }) },
        auth.token,
      )
      toast(`Intervention ${id}: ${decision}`, 'success')
      load()
    } catch {
      toast('Failed to apply decision', 'error')
    } finally {
      setDeciding(null)
    }
  }

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
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">Interventions</h2>
        <button
          onClick={async () => {
            if (!auth) return
            await api<{ message: string }>('/interventions/sync', { method: 'POST' }, auth.token)
            toast('Interventions synced', 'info')
            load()
          }}
          className="rounded bg-slate-700 px-3 py-1.5 text-sm hover:bg-slate-600"
        >
          Sync Queue
        </button>
      </div>

      {!items.length && <p className="text-slate-500">No open interventions</p>}

      <div className="space-y-4">
        {items.map((item) => (
          <div key={item.id} className="rounded-lg border border-slate-700 bg-slate-900 p-4">
            <div className="flex items-start justify-between">
              <div>
                <p className="font-medium">
                  Athlete #{item.athlete_id} &mdash; {item.action_type}
                </p>
                <div className="mt-1 flex gap-4 text-sm text-slate-400">
                  <span>
                    Risk:{' '}
                    <span className={item.risk_score >= 0.7 ? 'text-red-400' : 'text-amber-400'}>
                      {(item.risk_score * 100).toFixed(0)}%
                    </span>
                  </span>
                  <span>Confidence: {(item.confidence_score * 100).toFixed(0)}%</span>
                  <span>
                    Guardrail:{' '}
                    <span className={item.guardrail_pass ? 'text-emerald-400' : 'text-red-400'}>
                      {item.guardrail_pass ? 'Pass' : 'Fail'}
                    </span>
                  </span>
                </div>
                {item.why_factors.length > 0 && (
                  <ul className="mt-2 list-inside list-disc text-sm text-slate-400">
                    {item.why_factors.map((f, i) => (
                      <li key={i}>{String(f)}</li>
                    ))}
                  </ul>
                )}
                {!item.guardrail_pass && (
                  <p className="mt-1 text-sm text-red-400">{item.guardrail_reason}</p>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  disabled={deciding === item.id}
                  onClick={() => decide(item.id, 'approve')}
                  className="rounded bg-emerald-600 px-3 py-1 text-sm hover:bg-emerald-500 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  disabled={deciding === item.id}
                  onClick={() => decide(item.id, 'dismiss')}
                  className="rounded bg-slate-600 px-3 py-1 text-sm hover:bg-slate-500 disabled:opacity-50"
                >
                  Dismiss
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
