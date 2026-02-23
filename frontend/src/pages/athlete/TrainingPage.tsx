import { useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { api } from '../../api'

const categories = [
  'easy_run',
  'long_run',
  'tempo_run',
  'interval',
  'hill_repeats',
  'recovery_run',
  'fartlek',
  'race_pace',
  'progression_run',
  'cross_training',
  'rest',
]

export default function TrainingPage() {
  const { auth } = useAuth()
  const { toast } = useToast()
  const [category, setCategory] = useState('easy_run')
  const [duration, setDuration] = useState(45)
  const [distance, setDistance] = useState(8)
  const [avgHr, setAvgHr] = useState(145)
  const [maxHr, setMaxHr] = useState(160)
  const [pace, setPace] = useState(335)
  const [rpe, setRpe] = useState(5)
  const [notes, setNotes] = useState('')
  const [pain, setPain] = useState(false)
  const [submitting, setSubmitting] = useState(false)

  const submit = async () => {
    if (!auth) return
    setSubmitting(true)
    try {
      await api(
        '/training-logs',
        {
          method: 'POST',
          body: JSON.stringify({
            session_category: category,
            duration_min: duration,
            distance_km: distance,
            avg_hr: avgHr,
            max_hr: maxHr,
            avg_pace_sec_per_km: pace,
            rpe,
            notes,
            pain_flag: pain,
          }),
        },
        auth.token,
      )
      toast('Session logged', 'success')
    } catch {
      toast('Failed to log session', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="mx-auto max-w-lg space-y-6">
      <h2 className="text-2xl font-bold">Log Training Session</h2>

      <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-6">
        <Field label="Session Category">
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
          >
            {categories.map((c) => (
              <option key={c} value={c}>
                {c.replace(/_/g, ' ')}
              </option>
            ))}
          </select>
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Duration (min)">
            <NumInput value={duration} onChange={setDuration} />
          </Field>
          <Field label="Distance (km)">
            <NumInput value={distance} onChange={setDistance} step={0.1} />
          </Field>
          <Field label="Avg HR">
            <NumInput value={avgHr} onChange={setAvgHr} />
          </Field>
          <Field label="Max HR">
            <NumInput value={maxHr} onChange={setMaxHr} />
          </Field>
          <Field label="Pace (sec/km)">
            <NumInput value={pace} onChange={setPace} />
          </Field>
          <Field label={`RPE: ${rpe}/10`}>
            <input
              type="range"
              min={1}
              max={10}
              value={rpe}
              onChange={(e) => setRpe(Number(e.target.value))}
              className="w-full accent-teal-500"
            />
          </Field>
        </div>

        <Field label="Notes">
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            rows={2}
          />
        </Field>

        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="pain"
            checked={pain}
            onChange={(e) => setPain(e.target.checked)}
            className="accent-red-500"
          />
          <label htmlFor="pain" className="text-sm text-red-400">
            Pain flag
          </label>
        </div>

        <button
          onClick={submit}
          disabled={submitting}
          className="w-full rounded bg-teal-600 py-2 text-sm font-medium text-white hover:bg-teal-500 disabled:opacity-50"
        >
          {submitting ? 'Logging...' : 'Log Session'}
        </button>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="mb-1 block text-sm text-slate-300">{label}</label>
      {children}
    </div>
  )
}

function NumInput({
  value,
  onChange,
  step = 1,
}: {
  value: number
  onChange: (v: number) => void
  step?: number
}) {
  return (
    <input
      type="number"
      step={step}
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
    />
  )
}
