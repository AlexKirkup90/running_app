import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { api } from '../../api'

type CheckInResponse = {
  id: number
  readiness_score?: number
  readiness_band?: string
}

const labels = ['Sleep', 'Energy', 'Recovery', 'Stress'] as const

export default function CheckinPage() {
  const { auth } = useAuth()
  const { toast } = useToast()
  const [sleep, setSleep] = useState(3)
  const [energy, setEnergy] = useState(3)
  const [recovery, setRecovery] = useState(3)
  const [stress, setStress] = useState(3)
  const [trainingToday, setTrainingToday] = useState(true)
  const [result, setResult] = useState<CheckInResponse | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const values = [sleep, energy, recovery, stress]
  const setters = [setSleep, setEnergy, setRecovery, setStress]

  const submit = async () => {
    if (!auth) return
    setSubmitting(true)
    try {
      const r = await api<CheckInResponse>(
        '/checkins',
        {
          method: 'POST',
          body: JSON.stringify({
            sleep,
            energy,
            recovery,
            stress,
            training_today: trainingToday,
          }),
        },
        auth.token,
      )
      setResult(r)
      toast('Check-in submitted', 'success')
    } catch {
      toast('Failed to submit check-in', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  const bandColor: Record<string, string> = {
    green: 'text-emerald-400',
    amber: 'text-amber-400',
    red: 'text-red-400',
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h2 className="text-2xl font-bold">Daily Check-in</h2>

      <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-6">
        {labels.map((label, i) => (
          <div key={label}>
            <div className="mb-1 flex justify-between text-sm">
              <span className="text-slate-300">{label}</span>
              <span className="font-medium">{values[i]}/5</span>
            </div>
            <input
              type="range"
              min={1}
              max={5}
              value={values[i]}
              onChange={(e) => setters[i](Number(e.target.value))}
              className="w-full accent-teal-500"
            />
          </div>
        ))}

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="training"
            checked={trainingToday}
            onChange={(e) => setTrainingToday(e.target.checked)}
            className="accent-teal-500"
          />
          <label htmlFor="training" className="text-sm text-slate-300">
            Training today
          </label>
        </div>

        <button
          onClick={submit}
          disabled={submitting}
          className="w-full rounded bg-teal-600 py-2 text-sm font-medium text-white hover:bg-teal-500 disabled:opacity-50"
        >
          {submitting ? 'Submitting...' : 'Submit Check-in'}
        </button>
      </div>

      {result && (
        <div className="rounded-lg border border-slate-700 bg-slate-900 p-4 text-center">
          <p className="text-sm text-slate-400">Your readiness</p>
          <p className={`text-3xl font-bold ${bandColor[result.readiness_band ?? ''] ?? ''}`}>
            {result.readiness_score?.toFixed(1)} &mdash; {result.readiness_band ?? 'unknown'}
          </p>
        </div>
      )}
    </div>
  )
}
