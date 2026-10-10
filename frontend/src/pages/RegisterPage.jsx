import { useState, useRef } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { toast } from 'react-hot-toast'
import { useAuthStore } from '../store/authStore'
import client from '../api/client'
import './AuthPage.css'
import './RegisterPage.css'

export default function RegisterPage() {
  const navigate = useNavigate()
  const { login: storeLogin } = useAuthStore()

  // Step 1 fields
  const [name,     setName]     = useState('')
  const [email,    setEmail]    = useState('')
  const [password, setPassword] = useState('')

  // Step state
  const [step,    setStep]    = useState(1)   // 1 = details, 2 = OTP
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')

  // OTP — 6 individual digit inputs
  const [otp,    setOtp]    = useState(['', '', '', '', '', ''])
  const otpRefs = useRef([])

  /* ── Step 1: send OTP ───────────────────────────────────────────────────── */
  const handleSendOtp = async (e) => {
    e.preventDefault()
    setError('')
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return }
    setLoading(true)
    try {
      await client.post('/api/auth/send-otp', { name, email, password })
      toast.success('OTP sent! Check your inbox.')
      setStep(2)
    } catch (err) {
      setError(err.response?.data?.message ?? 'Failed to send OTP.')
    } finally {
      setLoading(false)
    }
  }

  /* ── OTP input helpers ──────────────────────────────────────────────────── */
  const handleOtpChange = (idx, val) => {
    if (!/^\d?$/.test(val)) return
    const next = [...otp]
    next[idx] = val
    setOtp(next)
    if (val && idx < 5) otpRefs.current[idx + 1]?.focus()
  }

  const handleOtpKey = (idx, e) => {
    if (e.key === 'Backspace' && !otp[idx] && idx > 0) {
      otpRefs.current[idx - 1]?.focus()
    }
  }

  const handleOtpPaste = (e) => {
    const text = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    if (!text) return
    const next = text.split('')
    while (next.length < 6) next.push('')
    setOtp(next)
    otpRefs.current[Math.min(text.length, 5)]?.focus()
    e.preventDefault()
  }

  /* ── Step 2: verify OTP + register ─────────────────────────────────────── */
  const handleVerify = async (e) => {
    e.preventDefault()
    const code = otp.join('')
    if (code.length < 6) { setError('Enter all 6 digits.'); return }
    setError('')
    setLoading(true)
    try {
      const { data } = await client.post('/api/auth/register', { email, otp: code })
      storeLogin(data.user, data.token)
      toast.success('Account created! Welcome to MEGA.')
      navigate('/search', { replace: true })
    } catch (err) {
      setError(err.response?.data?.message ?? 'Verification failed.')
    } finally {
      setLoading(false)
    }
  }

  const handleResend = async () => {
    setError('')
    setOtp(['', '', '', '', '', ''])
    try {
      await client.post('/api/auth/send-otp', { name, email, password })
      toast.success('New OTP sent!')
    } catch (err) {
      toast.error(err.response?.data?.message ?? 'Failed to resend OTP.')
    }
  }

  return (
    <main className="auth-page page">
      <div className="auth-wrap fade-up">
        <div className="auth-left">
          <p className="eyebrow">{step === 1 ? 'Get started' : 'Verify email'}</p>
          <h1 className="auth-heading">
            {step === 1 ? <>Create your<br />account</> : <>Enter the<br />6-digit code</>}
          </h1>
          <p className="auth-pitch">
            {step === 1
              ? 'Index your videos once, search them forever — by sight, sound, or on-screen text.'
              : `We sent a code to ${email}. Enter it below to verify your email.`}
          </p>
        </div>

        <div className="auth-card">
          <AnimatePresence mode="wait">
            {step === 1 ? (
              /* ── Step 1: Registration details ─────────────────────────── */
              <motion.form
                key="step1"
                id="register-form"
                onSubmit={handleSendOtp}
                noValidate
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={{ duration: 0.22 }}
              >
                <div className="auth-fields">
                  <div className="form-group">
                    <label htmlFor="register-name" className="form-label">Full name</label>
                    <input id="register-name" type="text" className="form-input"
                      placeholder="Sahil Patil" value={name} required autoFocus
                      autoComplete="name" onChange={e => setName(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label htmlFor="register-email" className="form-label">Email</label>
                    <input id="register-email" type="email" className="form-input"
                      placeholder="you@example.com" value={email} required
                      autoComplete="email" onChange={e => setEmail(e.target.value)} />
                  </div>
                  <div className="form-group">
                    <label htmlFor="register-password" className="form-label">Password</label>
                    <input id="register-password" type="password" className="form-input"
                      placeholder="Min. 6 characters" value={password} required
                      autoComplete="new-password" onChange={e => setPassword(e.target.value)} />
                  </div>
                </div>

                {error && <p className="auth-error form-error" role="alert">{error}</p>}

                <button id="register-send-otp-btn" type="submit"
                  className="btn btn-primary auth-btn" disabled={loading}>
                  {loading
                    ? <><div className="spinner spinner-sm" aria-hidden="true" /> Sending code…</>
                    : 'Send verification code →'}
                </button>
              </motion.form>
            ) : (
              /* ── Step 2: OTP entry ────────────────────────────────────── */
              <motion.form
                key="step2"
                id="otp-form"
                onSubmit={handleVerify}
                noValidate
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -24 }}
                transition={{ duration: 0.22 }}
              >
                <p className="otp-hint">
                  Code sent to <strong>{email}</strong>
                </p>

                {/* 6-digit OTP boxes */}
                <div className="otp-boxes" onPaste={handleOtpPaste}>
                  {otp.map((digit, i) => (
                    <input
                      key={i}
                      ref={el => otpRefs.current[i] = el}
                      id={`otp-digit-${i}`}
                      type="text"
                      inputMode="numeric"
                      maxLength={1}
                      className="otp-box"
                      value={digit}
                      autoFocus={i === 0}
                      onChange={e => handleOtpChange(i, e.target.value)}
                      onKeyDown={e => handleOtpKey(i, e)}
                    />
                  ))}
                </div>

                {error && <p className="auth-error form-error" role="alert">{error}</p>}

                <button id="register-verify-btn" type="submit"
                  className="btn btn-primary auth-btn" disabled={loading}>
                  {loading
                    ? <><div className="spinner spinner-sm" aria-hidden="true" /> Verifying…</>
                    : 'Verify & create account'}
                </button>

                <div className="otp-footer">
                  <button type="button" className="auth-link"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    onClick={() => { setStep(1); setError(''); setOtp(['','','','','','']) }}>
                    ← Change email
                  </button>
                  <button type="button" className="auth-link"
                    style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
                    onClick={handleResend}>
                    Resend code
                  </button>
                </div>
              </motion.form>
            )}
          </AnimatePresence>

          <p className="auth-switch">
            Already have an account?{' '}
            <Link to="/login" id="register-login-link" className="auth-link">Sign in</Link>
          </p>
        </div>
      </div>
    </main>
  )
}
