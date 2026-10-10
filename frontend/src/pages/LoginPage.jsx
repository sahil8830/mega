import { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { toast } from 'react-hot-toast'
import { login } from '../api/auth'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'
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
  const [showForgot, setShowForgot] = useState(false)
  const [forgotEmail,  setForgotEmail]  = useState('')
  const [forgotLoading, setForgotLoading] = useState(false)

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

  const handleForgot = async (e) => {
    e.preventDefault()
    if (!forgotEmail) return toast.error('Enter your email address.')
    setForgotLoading(true)
    try {
      await client.post('/api/auth/forgot-password', { email: forgotEmail })
      toast.success('Reset link sent! Check your inbox.')
      setShowForgot(false)
    } catch {
      toast.error('Could not send reset email. Try again.')
    } finally {
      setForgotLoading(false)
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
          {showForgot ? (
            /* ── Forgot password mini-form ── */
            <form id="forgot-form" onSubmit={handleForgot} noValidate>
              <h2 style={{ fontSize:'1.2rem', fontWeight:700, marginBottom:4 }}>Reset password</h2>
              <p style={{ fontSize:'.85rem', color:'#888', marginBottom:20 }}>
                Enter your email and we'll send a reset link.
              </p>
              <div className="form-group">
                <label htmlFor="forgot-email" className="form-label">Email</label>
                <input id="forgot-email" type="email" className="form-input"
                  placeholder="you@example.com" value={forgotEmail} required autoFocus
                  onChange={e => setForgotEmail(e.target.value)} />
              </div>
              <button type="submit" className="btn btn-primary auth-btn" style={{ marginTop:16 }} disabled={forgotLoading}>
                {forgotLoading ? 'Sending…' : 'Send reset link'}
              </button>
              <p className="auth-switch" style={{ marginTop:16 }}>
                <button type="button" className="auth-link" style={{ background:'none', border:'none', cursor:'pointer', padding:0 }}
                  onClick={() => setShowForgot(false)}>← Back to sign in</button>
              </p>
            </form>
          ) : (
            /* ── Normal login form ── */
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
                  <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:6 }}>
                    <label htmlFor="login-password" className="form-label" style={{ margin:0 }}>Password</label>
                    <button type="button" className="auth-link"
                      style={{ background:'none', border:'none', cursor:'pointer', padding:0, fontSize:'.8rem' }}
                      onClick={() => { setShowForgot(true); setForgotEmail(email) }}>
                      Forgot password?
                    </button>
                  </div>
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
          )}

          <p className="auth-switch">No account? <Link to="/register" id="login-register-link" className="auth-link">Create one</Link></p>
        </div>
      </div>
    </main>
  )
}
