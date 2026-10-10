import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { motion } from 'framer-motion'
import { CheckCircle, XCircle, Loader } from 'lucide-react'
import client from '../api/client'
import './AuthPage.css'

export default function VerifyEmailPage() {
  const [params]   = useSearchParams()
  const navigate   = useNavigate()
  const [status, setStatus] = useState('loading') // loading | success | error
  const [msg,    setMsg]    = useState('')

  useEffect(() => {
    const token = params.get('token')
    if (!token) { setStatus('error'); setMsg('No token found in link.'); return }

    client.get(`/api/auth/verify-email?token=${token}`)
      .then(r => { setStatus('success'); setMsg(r.data.message) })
      .catch(e => { setStatus('error');   setMsg(e.response?.data?.message || 'Verification failed.') })
  }, [params])

  return (
    <main className="page auth-page" style={{ display:'flex', alignItems:'center', justifyContent:'center' }}>
      <motion.div
        className="auth-card"
        initial={{ opacity:0, y:20 }}
        animate={{ opacity:1, y:0 }}
        style={{ maxWidth: 440, textAlign:'center', padding: '48px 40px' }}
      >
        {status === 'loading' && (
          <>
            <Loader size={40} className="spin" style={{ margin:'0 auto 20px', display:'block', color:'#0a0a0a' }} />
            <h1 style={{ fontSize:'1.5rem', fontWeight:700 }}>Verifying…</h1>
            <p style={{ color:'#888', marginTop:8 }}>Please wait while we verify your email.</p>
          </>
        )}
        {status === 'success' && (
          <>
            <CheckCircle size={48} style={{ margin:'0 auto 20px', display:'block', color:'#22c55e' }} />
            <h1 style={{ fontSize:'1.5rem', fontWeight:700 }}>Email verified!</h1>
            <p style={{ color:'#555', marginTop:8 }}>{msg}</p>
            <motion.button
              className="btn btn-primary"
              style={{ marginTop:28, width:'100%' }}
              onClick={() => navigate('/auth')}
              whileHover={{ scale:1.02 }} whileTap={{ scale:.98 }}
            >
              Sign in
            </motion.button>
          </>
        )}
        {status === 'error' && (
          <>
            <XCircle size={48} style={{ margin:'0 auto 20px', display:'block', color:'#ef4444' }} />
            <h1 style={{ fontSize:'1.5rem', fontWeight:700 }}>Verification failed</h1>
            <p style={{ color:'#555', marginTop:8 }}>{msg}</p>
            <motion.button
              className="btn btn-secondary"
              style={{ marginTop:28, width:'100%' }}
              onClick={() => navigate('/auth')}
              whileHover={{ scale:1.02 }} whileTap={{ scale:.98 }}
            >
              Back to sign in
            </motion.button>
          </>
        )}
      </motion.div>
    </main>
  )
}
