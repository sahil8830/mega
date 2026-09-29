import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { register } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import './AuthPage.css'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { login: storeLogin } = useAuthStore()

  const [name,     setName]     = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')
  const [error,    setError]    = useState('')
  const [loading,  setLoading]  = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return }
    setLoading(true)
    try {
      const data = await register({ name, email, password })
      storeLogin(data.user, data.token)
      navigate('/search', { replace: true })
    } catch (err) {
      setError(err.response?.data?.message ?? 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page page">
      <div className="auth-wrap fade-up">
        <div className="auth-left">
          <p className="eyebrow">Get started</p>
          <h1 className="auth-heading">Create your<br />account</h1>
          <p className="auth-pitch">Index your videos once, search them forever — by sight, sound, or on-screen text.</p>
        </div>

        <div className="auth-card">
          <form id="register-form" onSubmit={handleSubmit} noValidate>
            <div className="auth-fields">
              <div className="form-group">
                <label htmlFor="register-name" className="form-label">Full name</label>
                <input id="register-name" type="text" className="form-input"
                  placeholder="Sahil Patil" value={name} required
                  autoComplete="name" autoFocus
                  onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="form-group">
                <label htmlFor="register-email" className="form-label">Email</label>
                <input id="register-email" type="email" className="form-input"
                  placeholder="you@example.com" value={email} required
                  autoComplete="email"
                  onChange={(e) => setEmail(e.target.value)} />
              </div>
              <div className="form-group">
                <label htmlFor="register-password" className="form-label">Password</label>
                <input id="register-password" type="password" className="form-input"
                  placeholder="Min. 6 characters" value={password} required
                  autoComplete="new-password"
                  onChange={(e) => setPassword(e.target.value)} />
              </div>
            </div>

            {error && <p className="auth-error form-error" role="alert">{error}</p>}

            <button id="register-submit-btn" type="submit" className="btn btn-primary auth-btn" disabled={loading}>
              {loading ? <><div className="spinner spinner-sm" aria-hidden="true" /> Creating account…</> : 'Create account'}
            </button>
          </form>

          <p className="auth-switch">Already have an account? <Link to="/login" id="register-login-link" className="auth-link">Sign in</Link></p>
        </div>
      </div>
    </main>
  )
}
