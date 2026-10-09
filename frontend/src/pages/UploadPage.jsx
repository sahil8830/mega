import { useState, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Upload, CheckCircle, AlertCircle, Loader, Film } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { uploadVideo, getVideoStatus } from '../api/videos'
import StatusBadge from '../components/StatusBadge/StatusBadge'
import './UploadPage.css'

export default function UploadPage() {
  const [file,  setFile]  = useState(null)
  const [title, setTitle] = useState('')
  const [pct,   setPct]   = useState(0)
  const [state, setState] = useState('idle')   // idle|uploading|polling|done|error
  const [video, setVideo] = useState(null)
  const [error, setError] = useState('')
  const [drag,  setDrag]  = useState(false)
  const fileRef  = useRef(null)
  const pollRef  = useRef(null)

  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }

  const startPoll = (id) => {
    setState('polling')
    pollRef.current = setInterval(async () => {
      try {
        const s = await getVideoStatus(id)
        setVideo(s)
        if (s.status === 'indexed') {
          stopPoll(); setState('done')
          toast.success('Video indexed and ready to search!')
        }
        if (s.status === 'error') {
          stopPoll(); setState('error'); setError(s.errorMessage ?? 'Indexing failed.')
          toast.error('Indexing failed.')
        }
      } catch {
        stopPoll(); setState('error'); setError('Lost connection during indexing.')
        toast.error('Lost connection during indexing.')
      }
    }, 2500)
  }

  const accept = (f) => {
    setFile(f); setTitle(f.name.replace(/\.[^/.]+$/, ''))
    setState('idle'); setError(''); setVideo(null)
  }

  const onDrop = useCallback((e) => {
    e.preventDefault(); setDrag(false)
    const f = e.dataTransfer.files[0]
    if (f?.type?.startsWith('video/')) accept(f)
    else { setError('Only video files are accepted.'); toast.error('Only video files are accepted.') }
  }, [])

  const submit = async () => {
    if (!file) return
    setError(''); setPct(0); setState('uploading')
    const toastId = toast.loading('Uploading video…')
    try {
      const res = await uploadVideo(file, title || file.name, (p) => {
        setPct(p)
        toast.loading(`Uploading… ${p}%`, { id: toastId })
      })
      toast.success('Upload complete! Indexing now…', { id: toastId })
      startPoll(res.videoId)
    } catch (err) {
      const msg = err.response?.data?.message ?? 'Upload failed.'
      toast.error(msg, { id: toastId })
      setError(msg); setState('error')
    }
  }

  const reset = () => { stopPoll(); setFile(null); setTitle(''); setVideo(null); setError(''); setState('idle'); setPct(0) }

  return (
    <main className="page upload-page">
      <div className="page-body upload-body">
        <motion.header
          className="upload-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <p className="eyebrow">Admin panel</p>
          <h1 className="upload-title">Upload &amp; Index</h1>
          <p className="upload-sub">Drop a video to index it with CLIP, Whisper, and OCR.</p>
        </motion.header>

        <AnimatePresence mode="wait">
          {state === 'idle' && (
            <motion.div
              key="idle"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              transition={{ duration: 0.3 }}
            >
              <motion.div
                id="upload-dropzone"
                className={`dropzone${drag ? ' dropzone--over' : ''}${file ? ' dropzone--ready' : ''}`}
                onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
                onDragLeave={() => setDrag(false)}
                onDrop={onDrop}
                onClick={() => fileRef.current?.click()}
                role="button" tabIndex={0} aria-label="Drop video or click to browse"
                onKeyDown={(e) => e.key === 'Enter' && fileRef.current?.click()}
                whileHover={{ borderColor: 'rgba(108,99,255,0.5)', scale: 1.01 }}
                animate={drag ? { borderColor: '#6c63ff', scale: 1.02 } : {}}
                transition={{ duration: 0.2 }}
              >
                <input ref={fileRef} id="upload-file-input" type="file"
                  accept="video/mp4,video/quicktime,video/x-msvideo,video/webm"
                  className="sr-only" aria-label="Choose video"
                  onChange={(e) => e.target.files?.[0] && accept(e.target.files[0])} />

                <motion.div
                  className="dropzone-icon"
                  aria-hidden="true"
                  animate={drag ? { rotate: [0, -10, 10, 0] } : {}}
                  transition={{ duration: 0.4 }}
                >
                  {file
                    ? <CheckCircle size={36} color="#34d399" />
                    : <Upload size={36} />
                  }
                </motion.div>

                {file
                  ? <div className="dropzone-info">
                      <span className="dropzone-filename">{file.name}</span>
                      <span className="dropzone-size">{(file.size / (1024 * 1024)).toFixed(1)} MB</span>
                    </div>
                  : <div className="dropzone-text">
                      <span className="dropzone-primary">Drop your video here</span>
                      <span className="dropzone-hint">mp4 · mov · avi · webm, up to 500 MB</span>
                    </div>
                }
              </motion.div>

              {file && (
                <motion.div
                  className="upload-form"
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <div className="form-group">
                    <label htmlFor="upload-title" className="form-label">Title</label>
                    <input id="upload-title" type="text" className="form-input"
                      value={title} onChange={(e) => setTitle(e.target.value)}
                      placeholder="Give it a descriptive title" />
                  </div>
                  <div className="upload-actions">
                    <motion.button id="upload-cancel-btn" className="btn btn-secondary" onClick={reset}
                      whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                      Cancel
                    </motion.button>
                    <motion.button id="upload-submit-btn" className="btn btn-primary" onClick={submit}
                      whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                      Upload &amp; Index
                    </motion.button>
                  </div>
                </motion.div>
              )}
            </motion.div>
          )}

          {state === 'uploading' && (
            <motion.div
              key="uploading"
              className="upload-progress"
              role="status" aria-live="polite"
              initial={{ opacity: 0, scale: 0.97 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0 }}
            >
              <div className="up-label">Uploading… <strong>{pct}%</strong></div>
              <div className="progress-bar" style={{ height: '8px' }}>
                <motion.div
                  className="progress-bar-fill"
                  style={{ width: `${pct}%` }}
                  transition={{ duration: 0.3 }}
                />
              </div>
            </motion.div>
          )}

          {(state === 'polling' || state === 'done' || (state === 'error' && video)) && video && (
            <motion.div
              key="status"
              className="upload-status-card"
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.4 }}
            >
              <div className="status-card-top">
                <span className="status-card-name">
                  <Film size={16} style={{ marginRight: 8 }} />
                  {video.title}
                </span>
                <StatusBadge status={video.status} />
              </div>

              {state === 'polling' && (
                <div className="status-card-body" aria-live="polite">
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
                    style={{ display: 'inline-flex' }}
                  >
                    <Loader size={16} />
                  </motion.div>
                  <span>Running CLIP · Whisper · OCR…</span>
                </div>
              )}

              {state === 'done' && (
                <motion.div
                  className="status-done"
                  role="status"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                >
                  <p><CheckCircle size={16} style={{ marginRight: 6, color: '#34d399' }} />Indexed and ready to search.</p>
                  <div className="upload-actions">
                    <motion.button id="upload-another-btn" className="btn btn-secondary" onClick={reset}
                      whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }}>
                      Upload another
                    </motion.button>
                    <motion.a href="/search" className="btn btn-primary" id="upload-search-link"
                      whileHover={{ scale: 1.03 }}>
                      Search now →
                    </motion.a>
                  </div>
                </motion.div>
              )}

              {state === 'error' && error && <p className="form-error" role="alert">{error}</p>}
            </motion.div>
          )}

          {error && state === 'error' && !video && (
            <motion.div
              key="error"
              className="upload-err"
              role="alert"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <AlertCircle size={20} color="#f87171" />
              <p className="form-error">{error}</p>
              <button id="upload-err-retry" className="btn btn-secondary btn-sm" onClick={reset}>Try again</button>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </main>
  )
}
