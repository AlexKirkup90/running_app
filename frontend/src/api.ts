const API_BASE = 'http://localhost:8000/api/v1'

export type Token = { access_token: string; token_type: string; role: string; user_id: number; athlete_id?: number }

export async function api<T>(path: string, opts: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json', ...(opts.headers as Record<string, string> || {}) }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function login(username: string, password: string): Promise<Token> {
  const form = new URLSearchParams({ username, password })
  const res = await fetch(`${API_BASE}/auth/token`, { method: 'POST', body: form })
  if (!res.ok) throw new Error('login failed')
  return res.json()
}
