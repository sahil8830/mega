import { useEffect, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { X, Play } from 'lucide-react'
import { useAuthStore } from '../../store/authStore'
import './VideoPlayerModal.css'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:3000'

export default function VideoPlayerModal({ video, onClose }) {
  const token    = useAuthStore(s => s.token)
  const videoRef = useRef(null)

  const streamUrl = video
    ? `${API_BASE}/api/videos/${video._id}/stream?token=${token}`
    : null

  // Close on Escape key
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  // Pause video when modal closes
  useEffect(() => {
    return () => {
      if (videoRef.current) videoRef.current.pause()
    }
  }, [])

  return (
    <AnimatePresence>
      {video && (
        <motion.div
          className="vpm-backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-label={`Playing: ${video.title}`}
        >
          <motion.div
            className="vpm-panel"
            initial={{ opacity: 0, scale: 0.94, y: 24 }}
            animate={{ opacity: 1, scale: 1,    y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 16 }}
            transition={{ duration: 0.25, ease: [.4, 0, .2, 1] }}
            onClick={e => e.stopPropagation()}
          >
            {/* Header */}
            <div className="vpm-header">
              <div className="vpm-title-row">
                <Play size={14} className="vpm-title-icon" aria-hidden="true" />
                <h2 className="vpm-title" title={video.title}>{video.title}</h2>
              </div>
              <button
                id="vpm-close-btn"
                className="vpm-close"
                onClick={onClose}
                aria-label="Close player"
              >
                <X size={18} />
              </button>
            </div>

            {/* Player */}
            <div className="vpm-player">
              {streamUrl ? (
                <video
                  ref={videoRef}
                  src={streamUrl}
                  controls
                  autoPlay
                  preload="metadata"
                  controlsList="nodownload"
                  onError={(e) => console.error('[VideoModal] stream error', e.target.error)}
                  style={{ width: '100%', display: 'block', background: '#000' }}
                />
              ) : (
                <div className="vpm-loading">Loading…</div>
              )}
            </div>

            {/* Footer meta */}
            <div className="vpm-footer">
              <span className="vpm-meta">
                {(video.sizeBytes / (1024 * 1024)).toFixed(1)} MB
              </span>
              <span className="vpm-meta">
                {new Date(video.createdAt).toLocaleDateString('en-IN', {
                  day: 'numeric', month: 'short', year: 'numeric',
                })}
              </span>
              <span
                className={`badge badge-${video.status}`}
                style={{ marginLeft: 'auto' }}
              >
                {video.status}
              </span>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}
