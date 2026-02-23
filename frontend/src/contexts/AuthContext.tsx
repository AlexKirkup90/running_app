import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'
import { login as apiLogin, type Token } from '../api'

export type Auth = {
  token: string
  role: string
  userId: number
  athleteId?: number
}

type AuthContextValue = {
  auth?: Auth
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue>({
  login: async () => {},
  logout: () => {},
})

export const useAuth = () => useContext(AuthContext)

function hydrateFromStorage(): Auth | undefined {
  const token = localStorage.getItem('token')
  const role = localStorage.getItem('role')
  const userId = localStorage.getItem('user_id')
  if (!token || !role || !userId) return undefined
  const athleteId = localStorage.getItem('athlete_id')
  return {
    token,
    role,
    userId: Number(userId),
    athleteId: athleteId ? Number(athleteId) : undefined,
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuth] = useState<Auth | undefined>(hydrateFromStorage)

  const login = useCallback(async (username: string, password: string) => {
    const t: Token = await apiLogin(username, password)
    localStorage.setItem('token', t.access_token)
    localStorage.setItem('role', t.role)
    localStorage.setItem('user_id', String(t.user_id))
    localStorage.setItem('athlete_id', String(t.athlete_id ?? ''))
    setAuth({
      token: t.access_token,
      role: t.role,
      userId: t.user_id,
      athleteId: t.athlete_id,
    })
  }, [])

  const logout = useCallback(() => {
    localStorage.clear()
    setAuth(undefined)
  }, [])

  return (
    <AuthContext.Provider value={{ auth, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
