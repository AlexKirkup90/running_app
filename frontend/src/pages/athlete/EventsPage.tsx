import { useEffect, useState } from 'react'
import { useAuth } from '../../contexts/AuthContext'
import { useToast } from '../../contexts/ToastContext'
import { api } from '../../api'
import { Skeleton } from '../../components/Skeleton'

type Event = {
  id: number
  name: string
  event_date: string
  distance: string
}

export default function EventsPage() {
  const { auth } = useAuth()
  const { toast } = useToast()
  const [events, setEvents] = useState<Event[]>([])
  const [loading, setLoading] = useState(true)
  const [name, setName] = useState('')
  const [eventDate, setEventDate] = useState('')
  const [distance, setDistance] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const load = () => {
    if (!auth) return
    api<Event[]>('/events', {}, auth.token).then((r) => {
      setEvents(r)
      setLoading(false)
    })
  }

  useEffect(load, [auth])

  const submit = async () => {
    if (!auth || !name || !eventDate || !distance) return
    setSubmitting(true)
    try {
      await api(
        '/events',
        {
          method: 'POST',
          body: JSON.stringify({ name, event_date: eventDate, distance }),
        },
        auth.token,
      )
      toast('Event created', 'success')
      setName('')
      setEventDate('')
      setDistance('')
      load()
    } catch {
      toast('Failed to create event', 'error')
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-48" />
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h2 className="text-2xl font-bold">Events</h2>

      <div className="space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-6">
        <h3 className="text-lg font-semibold">Add Race Event</h3>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          <div>
            <label className="mb-1 block text-sm text-slate-300">Event Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              placeholder="Spring Marathon"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-300">Date</label>
            <input
              type="date"
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
              className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
            />
          </div>
          <div>
            <label className="mb-1 block text-sm text-slate-300">Distance</label>
            <input
              value={distance}
              onChange={(e) => setDistance(e.target.value)}
              className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white"
              placeholder="marathon"
            />
          </div>
        </div>
        <button
          onClick={submit}
          disabled={submitting || !name || !eventDate || !distance}
          className="rounded bg-teal-600 px-4 py-2 text-sm font-medium text-white hover:bg-teal-500 disabled:opacity-50"
        >
          {submitting ? 'Creating...' : 'Add Event'}
        </button>
      </div>

      <div className="overflow-hidden rounded-lg border border-slate-700">
        <table className="w-full text-left text-sm">
          <thead className="border-b border-slate-700 bg-slate-900">
            <tr>
              <th className="px-4 py-2 text-slate-400">Event</th>
              <th className="px-4 py-2 text-slate-400">Date</th>
              <th className="px-4 py-2 text-slate-400">Distance</th>
            </tr>
          </thead>
          <tbody>
            {events.map((e) => (
              <tr key={e.id} className="border-b border-slate-800">
                <td className="px-4 py-2">{e.name}</td>
                <td className="px-4 py-2">{e.event_date}</td>
                <td className="px-4 py-2">{e.distance}</td>
              </tr>
            ))}
            {!events.length && (
              <tr>
                <td colSpan={3} className="px-4 py-4 text-center text-slate-500">
                  No events yet
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}
