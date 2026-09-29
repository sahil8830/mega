import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { login } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import './AuthPage.css'

export default function LoginPage() {
  const navigate  = useNavigate()
  const location  = useLocation()
  const { login: storeLogin } = useAuthStore()
  const from = location.state?.from?.pathname ?? '/search'

  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const data = await login({ email, password })
      storeLogin(data.user, data.token)
      navigate(from, { replace: true })
    } catch (err) {
      setError(err.response?.data?.message ?? 'Wrong email or password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page page">
      <div className="auth-wrap fade-up">
        <div className="auth-left">
          <p className="eyebrow">Welcome back</p>
          <h1 className="auth-heading">Sign in to<br />your account</h1>
          <p className="auth-pitch">Search any moment in your video library using natural language.</p>
        </div>

        <div className="auth-card">
          <form id="login-form" onSubmit={handleSubmit} noValidate>
            <div className="auth-fields">
              <div className="form-group">
                <label htmlFor="login-email" className="form-label">Email</label>
                <input id="login-email" type="email" className="form-input"
                  placeholder="you@example.com" value={email} required
                  autoComplete="email" autoFocus
                  onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="form-group">
                <label htmlFor="login-password" className="form-label">Password</label>
                <input id="login-password" type="password" className="form-input"
                  placeholder="••••••••" value={password} required
                  autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)} />
              </div>
            </div>

            {error && <p className="auth-error form-error" role="alert">{error}</p>}

            <button id="login-submit-btn" type="submit" className="btn btn-primary auth-btn" disabled={loading}>
              {loading ? <><div className="spinner spinner-sm" aria-hidden="true" /> Signing in…</> : 'Sign in'}
            </button>
          </form>

          <p className="auth-switch">No account? <Link to="/register" id="login-register-link" className="auth-link">Create one</Link></p>
        </div>
      </div>
    </main>
  )
}
