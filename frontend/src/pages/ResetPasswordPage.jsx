import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Lock, CheckCircle } from 'lucide-react'
import { toast } from 'react-hot-toast'
import client from '../api/client'
import './AuthPage.css'

export default function ResetPasswordPage() {
  const [params]   = useSearchParams()
  const navigate   = useNavigate()
  const token      = params.get('token') || ''
  const [password, setPassword]   = useState('')
  const [confirm,  setConfirm]    = useState('')
  const [loading,  setLoading]    = useState(false)
  const [done,     setDone]       = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (password.length < 8) return toast.error('Password must be at least 8 characters.')
    if (password !== confirm)  return toast.error('Passwords do not match.')
    if (!token)                return toast.error('Reset token is missing from the URL.')

    setLoading(true)
    try {
      await client.post('/api/auth/reset-password', { token, password })
      setDone(true)
      toast.success('Password reset successfully!')
    } catch (err) {
      toast.error(err.response?.data?.message || 'Reset failed. Try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="page auth-page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <motion.div
        className="auth-card"
        initial={{ opacity:0, y:20 }}
        animate={{ opacity:1, y:0 }}
        style={{ maxWidth: 440, padding: '48px 40px' }}
      >
        {done ? (
          <div style={{ textAlign:'center' }}>
            <CheckCircle size={48} style={{ margin:'0 auto 20px', display:'block', color:'#22c55e' }} />
            <h1 style={{ fontSize:'1.5rem', fontWeight:700 }}>Password reset!</h1>
            <p style={{ color:'#555', marginTop:8 }}>You can now sign in with your new password.</p>
            <motion.button
              className="btn btn-primary"
              style={{ marginTop:28, width:'100%' }}
              onClick={() => navigate('/auth')}
              whileHover={{ scale:1.02 }} whileTap={{ scale:.98 }}
            >
              Sign in
            </motion.button>
          </div>
        ) : (
          <>
            <div style={{ marginBottom:28 }}>
              <p className="eyebrow">Account security</p>
              <h1 style={{ fontSize:'1.75rem', fontWeight:700, letterSpacing:'-.03em', margin:'4px 0 8px' }}>
                Reset password
              </h1>
              <p style={{ color:'#888', fontSize:'.9rem' }}>Enter your new password below.</p>
            </div>

            <form onSubmit={handleSubmit} style={{ display:'flex', flexDirection:'column', gap:16 }}>
              <div className="auth-field">
                <label className="auth-label" htmlFor="reset-password">New password</label>
                <div className="auth-input-wrap">
                  <Lock size={15} className="auth-icon" />
                  <input
                    id="reset-password"
                    type="password"
                    className="auth-input"
                    placeholder="Min. 8 characters"
                    value={password}
                    onChange={e => setPassword(e.target.value)}
                    required minLength={8}
                  />
                </div>
              </div>

              <div className="auth-field">
                <label className="auth-label" htmlFor="reset-confirm">Confirm password</label>
                <div className="auth-input-wrap">
                  <Lock size={15} className="auth-icon" />
                  <input
                    id="reset-confirm"
                    type="password"
                    className="auth-input"
                    placeholder="Repeat new password"
                    value={confirm}
                    onChange={e => setConfirm(e.target.value)}
                    required
                  />
                </div>
              </div>

              <motion.button
                type="submit"
                className="btn btn-primary"
                disabled={loading}
                style={{ marginTop:8 }}
                whileHover={{ scale:1.02 }} whileTap={{ scale:.98 }}
              >
                {loading ? 'Resetting…' : 'Reset password'}
              </motion.button>
            </form>
          </>
        )}
      </motion.div>
    </main>
  )
}
