import { useToast } from '../contexts/ToastContext'
import { X } from 'lucide-react'

const variantClasses: Record<string, string> = {
  success: 'bg-emerald-600',
  error: 'bg-red-600',
  warning: 'bg-amber-600',
  info: 'bg-sky-600',
}

export function ToastContainer() {
  const { toasts, dismiss } = useToast()
  if (!toasts.length) return null
  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col gap-2">
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`${variantClasses[t.variant] ?? variantClasses.info} flex items-center gap-2 rounded px-4 py-2 text-sm text-white shadow-lg`}
        >
          <span className="flex-1">{t.message}</span>
          <button onClick={() => dismiss(t.id)}>
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
