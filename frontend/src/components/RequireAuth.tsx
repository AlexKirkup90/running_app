import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import type { ReactNode } from 'react'

export function RequireAuth({ children, role }: { children: ReactNode; role?: string }) {
  const { auth } = useAuth()
  if (!auth) return <Navigate to="/login" replace />
  if (role && auth.role !== role) return <Navigate to="/" replace />
  return <>{children}</>
}
