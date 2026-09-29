import { useState, useRef, useCallback } from 'react'
import { uploadVideo, getVideoStatus } from '../api/videos'
import StatusBadge from '../components/StatusBadge/StatusBadge'
import './UploadPage.css'

export default function UploadPage() {
  const [file,      setFile]      = useState(null)
  const [title,     setTitle]     = useState('')
  const [pct,       setPct]       = useState(0)
  const [state,     setState]     = useState('idle')   // idle|uploading|polling|done|error
  const [video,     setVideo]     = useState(null)
  const [error,     setError]     = useState('')
  const [drag,      setDrag]      = useState(false)
  const fileRef  = useRef(null)
  const pollRef  = useRef(null)

  const stopPoll = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null } }

  const startPoll = (id) => {
    setState('polling')
    pollRef.current = setInterval(async () => {
      try {
        const s = await getVideoStatus(id)
        setVideo(s)
        if (s.status === 'indexed') { stopPoll(); setState('done') }
        if (s.status === 'error')   { stopPoll(); setState('error'); setError(s.errorMessage ?? 'Indexing failed.') }
      } catch {
        stopPoll(); setState('error'); setError('Lost connection during indexing.')
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
    else setError('Only video files are accepted.')
  }, [])

  const submit = async () => {
    if (!file) return
    setError(''); setPct(0); setState('uploading')
    try {
      const res = await uploadVideo(file, title || file.name, setPct)
      startPoll(res.videoId)
    } catch (err) {
      setError(err.response?.data?.message ?? 'Upload failed.'); setState('error')
    }
  }

  const reset = () => { stopPoll(); setFile(null); setTitle(''); setVideo(null); setError(''); setState('idle'); setPct(0) }

  return (
    <main className="page upload-page">
      <div className="page-body upload-body">
        <header className="upload-header">
          <p className="eyebrow">Admin panel</p>
          <h1 className="upload-title">Upload &amp; Index</h1>
          <p className="upload-sub">Drop a video to index it with CLIP, Whisper, and OCR.</p>
        </header>

        {state === 'idle' && (
          <>
            <div
              id="upload-dropzone"
              className={`dropzone${drag ? ' dropzone--over' : ''}${file ? ' dropzone--ready' : ''}`}
              onDragOver={(e) => { e.preventDefault(); setDrag(true) }}
              onDragLeave={() => setDrag(false)}
              onDrop={onDrop}
              onClick={() => fileRef.current?.click()}
              role="button" tabIndex={0} aria-label="Drop video or click to browse"
              onKeyDown={(e) => e.key === 'Enter' && fileRef.current?.click()}
            >
              <input ref={fileRef} id="upload-file-input" type="file"
                accept="video/mp4,video/quicktime,video/x-msvideo,video/webm"
                className="sr-only" aria-label="Choose video"
                onChange={(e) => e.target.files?.[0] && accept(e.target.files[0])} />

              <div className="dropzone-icon" aria-hidden="true">
                {file
                  ? <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="20 6 9 17 4 12"/></svg>
                  : <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
                }
              </div>
              {file
                ? <div className="dropzone-info"><span className="dropzone-filename">{file.name}</span><span className="dropzone-size">{(file.size/(1024*1024)).toFixed(1)} MB</span></div>
                : <div className="dropzone-text"><span className="dropzone-primary">Drop your video here</span><span className="dropzone-hint">mp4 · mov · avi · webm, up to 500 MB</span></div>
              }
            </div>

            {file && (
              <div className="upload-form fade-in">
                <div className="form-group">
                  <label htmlFor="upload-title" className="form-label">Title</label>
                  <input id="upload-title" type="text" className="form-input"
                    value={title} onChange={(e) => setTitle(e.target.value)}
                    placeholder="Give it a descriptive title" />
                </div>
                <div className="upload-actions">
                  <button id="upload-cancel-btn" className="btn btn-secondary" onClick={reset}>Cancel</button>
                  <button id="upload-submit-btn" className="btn btn-primary" onClick={submit}>Upload &amp; Index</button>
                </div>
              </div>
            )}
          </>
        )}

        {state === 'uploading' && (
          <div className="upload-progress fade-in" role="status" aria-live="polite">
            <div className="up-label">Uploading… <strong>{pct}%</strong></div>
            <div className="progress-bar" style={{height:'8px'}}>
              <div className="progress-bar-fill" style={{width:`${pct}%`}} />
            </div>
          </div>
        )}

        {(state === 'polling' || state === 'done' || (state === 'error' && video)) && video && (
          <div className="upload-status-card fade-in">
            <div className="status-card-top">
              <span className="status-card-name">{video.title}</span>
              <StatusBadge status={video.status} />
            </div>
            {state === 'polling' && (
              <div className="status-card-body" aria-live="polite">
                <div className="spinner spinner-sm" aria-hidden="true" />
                <span>Running CLIP · Whisper · OCR…</span>
              </div>
            )}
            {state === 'done' && (
              <div className="status-done" role="status">
                <p>Indexed and ready to search.</p>
                <div className="upload-actions">
                  <button id="upload-another-btn" className="btn btn-secondary" onClick={reset}>Upload another</button>
                  <a href="/search" className="btn btn-primary" id="upload-search-link">Search now →</a>
                </div>
              </div>
            )}
            {state === 'error' && error && <p className="form-error" role="alert">{error}</p>}
          </div>
        )}

        {error && state === 'error' && !video && (
          <div className="upload-err fade-in" role="alert">
            <p className="form-error">{error}</p>
            <button id="upload-err-retry" className="btn btn-secondary btn-sm" onClick={reset}>Try again</button>
          </div>
        )}
      </div>
    </main>
  )
}
