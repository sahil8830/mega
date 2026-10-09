import { useLocation, useNavigate } from 'react-router-dom'
import { useRef, useEffect, useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { ArrowLeft, Play, Eye, Zap } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { search as doSearch } from '../api/search'
import { useAuthStore } from '../store/authStore'
import './ResultsPage.css'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:3000'

function fmt(sec) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function Bar({ label, weight, score, color }) {
  return (
    <div className="ev-bar">
      <div className="ev-bar-header">
        <span className="ev-bar-label">{label}</span>
        <span className="ev-bar-nums">
          <span style={{ color }} className="ev-weight">{Math.round(weight * 100)}%</span>
          <span className="ev-score">{Math.round(score * 100)}% match</span>
        </span>
      </div>
      <div className="progress-bar">
        <motion.div
          className="progress-bar-fill"
          style={{ background: color }}
          initial={{ width: 0 }}
          animate={{ width: `${Math.round(weight * 100)}%` }}
          transition={{ duration: 0.6, ease: 'easeOut', delay: 0.1 }}
          role="progressbar"
          aria-valuenow={Math.round(weight * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    </div>
  )
}

export default function ResultsPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const playerRef  = useRef(null)   // native <video> element ref
  const hasSeeked   = useRef(false)  // prevent onCanPlay re-seek loop
  const token = useAuthStore(s => s.token)

  const state = location.state
  const [activeIdx, setActiveIdx]   = useState(0)
  const [rerunLoading, setRerunLoading] = useState(false)

  const result = state?.result
  const query = state?.query
  const active = result?.results?.[activeIdx]

  // Token-authed stream URL
  const videoSrc = active?.video_id
    ? `${API_BASE}/api/videos/${active.video_id}/stream?token=${token}`
    : null

  useEffect(() => {
    if (!state) navigate('/search', { replace: true })
  }, [state, navigate])

  // onCanPlay: seek only ONCE per video load (fires repeatedly on each buffer)
  const handleCanPlay = () => {
    if (hasSeeked.current) return          // already seeked — ignore
    if (playerRef.current && active?.start_time != null) {
      playerRef.current.currentTime = active.start_time
      hasSeeked.current = true
    }
  }

  // When user picks a different result, reset hasSeeked and seek if loaded
  useEffect(() => {
    hasSeeked.current = false              // allow next onCanPlay to seek
    const vid = playerRef.current
    if (!vid || active?.start_time == null) return
    if (vid.readyState >= 2) {             // already loaded — seek immediately
      vid.currentTime = active.start_time
      hasSeeked.current = true
    }
  }, [activeIdx])  // eslint-disable-line react-hooks/exhaustive-deps

  const handleSeek = () => {
    if (playerRef.current && active?.start_time != null) {
      playerRef.current.currentTime = active.start_time
      playerRef.current.play().catch(() => {})
    }
  }

  const handleRerun = async () => {
    if (!query || rerunLoading) return
    setRerunLoading(true)
    const toastId = toast.loading('Re-running search…')
    try {
      const res = await doSearch(query, 10, result?.gqeApplied ?? true)
      toast.success('Fresh results loaded', { id: toastId })
      navigate('/results', { state: { result: res, query }, replace: true })
    } catch {
      toast.error('Re-run failed', { id: toastId })
    } finally {
      setRerunLoading(false)
    }
  }

  if (!state) return null

  return (
    <main className="page results-page">
      <div className="results-body">

        {/* Header */}
        <motion.header
          className="results-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <motion.button
            id="results-back-btn"
            className="btn btn-ghost btn-sm results-back"
            onClick={() => navigate('/search')}
            whileHover={{ x: -3 }}
            whileTap={{ scale: 0.95 }}
          >
            <ArrowLeft size={16} /> Back
          </motion.button>

          <div className="results-query-wrap">
            <p className="eyebrow">Results for</p>
            <h1 className="results-query">"{query}"</h1>
            <p className="results-meta">
              {result.results.length} moment{result.results.length !== 1 ? 's' : ''} ·{' '}
              {result.gqeApplied
                ? <><Zap size={12} style={{ display:'inline', marginRight:2 }} />GQE applied</>
                : 'direct'
              } · dominant: <span className="results-modality">{result.modality}</span>
            </p>
          </div>

          <motion.button
            className="btn btn-ghost btn-sm"
            onClick={handleRerun}
            disabled={rerunLoading}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            style={{ marginLeft: 'auto' }}
          >
            {rerunLoading ? '⏳ Running…' : '🔁 Re-run'}
          </motion.button>
        </motion.header>

        {result.results.length === 0 ? (
          <motion.div
            className="results-empty"
            role="status"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <p className="results-empty-icon" aria-hidden="true">⊘</p>
            <h2>No matching moments</h2>
            <p>Try a different description, or turn off GQE for direct matching.</p>
            <button id="results-new-search-btn" className="btn btn-primary" onClick={() => navigate('/search')}>
              New search
            </button>
          </motion.div>
        ) : (
          <div className="results-layout">

            {/* Sidebar */}
            <aside className="results-aside" aria-label="Results list">
              <AnimatePresence>
                {result.results.map((r, i) => (
                  <motion.button
                    key={r.segment_id}
                    id={`result-item-${i}`}
                    className={`result-item${activeIdx === i ? ' result-item--on' : ''}`}
                    onClick={() => setActiveIdx(i)}
                    aria-pressed={activeIdx === i}
                    initial={{ opacity: 0, x: -16 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.3, delay: i * 0.04 }}
                    whileHover={{ x: 3 }}
                  >
                    <span className="ri-rank">#{i + 1}</span>
                    <span className="ri-info">
                      <span className="ri-time">{fmt(r.start_time)} – {fmt(r.end_time)}</span>
                      <span className="ri-score">{Math.round(r.fused_score * 100)}%</span>
                    </span>
                    {activeIdx === i && (
                      <motion.span
                        className="ri-active-dot"
                        layoutId="active-dot"
                        style={{ background: '#6c63ff', width: 6, height: 6, borderRadius: '50%', flexShrink: 0 }}
                      />
                    )}
                  </motion.button>
                ))}
              </AnimatePresence>
            </aside>

            {/* Main */}
            <div className="results-main">
              <section className="player-section" aria-label="Video player">
                <AnimatePresence mode="wait">
                  {videoSrc ? (
                    <motion.div
                      key={videoSrc}
                      className="player-wrapper"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      transition={{ duration: 0.3 }}
                    >
                      <video
                        ref={playerRef}
                        src={videoSrc}
                        controls
                        onCanPlay={handleCanPlay}
                        onError={(e) => console.error('[Video] error', e.target.error)}
                        preload="metadata"
                        controlsList="nodownload"
                        style={{
                          display: 'block',
                          width: '100%',
                          aspectRatio: '16 / 9',
                          background: '#000',
                          maxHeight: '60vh',
                        }}
                      />
                    </motion.div>
                  ) : (
                    <div className="player-loading">Loading video…</div>
                  )}
                </AnimatePresence>

                {active && (
                  <motion.div
                    className="player-bar"
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                  >
                    <span className="player-moment">
                      <Play size={12} style={{ marginRight: 4 }} />
                      {fmt(active.start_time)} → {fmt(active.end_time)}
                    </span>
                    <motion.button
                      id="results-seek-btn"
                      className="btn btn-secondary btn-sm"
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                      onClick={handleSeek}
                    >
                      ▶ Jump to {fmt(active.start_time)}
                    </motion.button>
                  </motion.div>
                )}
              </section>

              {/* Evidence panel */}
              {active && (
                <motion.section
                  className="evidence"
                  aria-label="Evidence"
                  key={activeIdx}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.35 }}
                >
                  <div className="ev-header">
                    <h2 className="ev-title">
                      <Eye size={16} style={{ marginRight: 6 }} />
                      Evidence
                    </h2>
                    <span className="ev-fused">
                      {Math.round(active.fused_score * 100)}<small>%</small>
                    </span>
                  </div>
                  <div className="ev-bars">
                    <Bar label="🎬 Visual (CLIP)"    weight={active.modality_weights.visual} score={active.visual_score} color="#a78bfa" />
                    <Bar label="🎙 Speech (Whisper)" weight={active.modality_weights.speech} score={active.speech_score} color="#22d3ee" />
                    <Bar label="📄 OCR (PaddleOCR)"  weight={active.modality_weights.ocr}    score={active.ocr_score}    color="#34d399" />
                  </div>
                  {result.gqeApplied && result.variants?.length > 0 && (
                    <div className="ev-variants">
                      <p className="eyebrow" style={{ marginBottom: 8 }}>GQE variants</p>
                      <ul>
                        {result.variants.slice(0, 3).map((v, i) => (
                          <motion.li
                            key={i}
                            className="ev-variant"
                            initial={{ opacity: 0, x: -8 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: i * 0.07 }}
                          >
                            "{v}"
                          </motion.li>
                        ))}
                      </ul>
                    </div>
                  )}
                </motion.section>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
