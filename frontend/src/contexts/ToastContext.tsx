import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

type ToastVariant = 'success' | 'error' | 'warning' | 'info'

type Toast = {
  id: number
  message: string
  variant: ToastVariant
}

type ToastContextValue = {
  toasts: Toast[]
  toast: (message: string, variant?: ToastVariant) => void
  dismiss: (id: number) => void
}

const ToastContext = createContext<ToastContextValue>({
  toasts: [],
  toast: () => {},
  dismiss: () => {},
})

export const useToast = () => useContext(ToastContext)

let nextId = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback(
    (message: string, variant: ToastVariant = 'info') => {
      const id = ++nextId
      setToasts((prev) => [...prev, { id, message, variant }])
      setTimeout(() => dismiss(id), 4000)
    },
    [dismiss],
  )

  return (
    <ToastContext.Provider value={{ toasts, toast, dismiss }}>
      {children}
    </ToastContext.Provider>
  )
}
