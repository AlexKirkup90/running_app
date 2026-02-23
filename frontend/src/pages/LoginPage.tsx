import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

export default function LoginPage() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await login(username, password)
      navigate('/')
    } catch {
      setError('Invalid username or password')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4 rounded-lg border border-slate-700 bg-slate-900 p-8">
        <div>
          <h1 className="text-2xl font-bold text-teal-400">Run Season Command</h1>
          <p className="text-sm text-slate-400">Sign in to your account</p>
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-300">Username</label>
          <input
            className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:border-teal-500 focus:outline-none"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoFocus
          />
        </div>
        <div>
          <label className="mb-1 block text-sm text-slate-300">Password</label>
          <input
            type="password"
            className="w-full rounded border border-slate-600 bg-slate-800 px-3 py-2 text-sm text-white focus:border-teal-500 focus:outline-none"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-red-400">{error}</p>}
        <button
          type="submit"
          disabled={loading}
          className="w-full rounded bg-teal-600 py-2 text-sm font-medium text-white hover:bg-teal-500 disabled:opacity-50"
        >
          {loading ? 'Signing in...' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
