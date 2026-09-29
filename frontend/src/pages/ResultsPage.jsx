import { useLocation, useNavigate } from 'react-router-dom'
import { useRef, useEffect, useState } from 'react'
import { search as doSearch } from '../api/search'
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
          <span style={{color}} className="ev-weight">{Math.round(weight*100)}%</span>
          <span className="ev-score">{Math.round(score*100)}% match</span>
        </span>
      </div>
      <div className="progress-bar">
        <div className="progress-bar-fill" style={{width:`${Math.round(weight*100)}%`, background:color}}
          role="progressbar" aria-valuenow={Math.round(weight*100)} aria-valuemin={0} aria-valuemax={100} />
      </div>
    </div>
  )
}

export default function ResultsPage() {
  const location = useLocation()
  const navigate  = useNavigate()
  const videoRef  = useRef(null)

  const state = location.state
  const [activeIdx, setActiveIdx] = useState(0)

  const result  = state?.result
  const query   = state?.query
  const active  = result?.results?.[activeIdx]

  useEffect(() => {
    if (!state) navigate('/search', { replace: true })
  }, [state, navigate])

  useEffect(() => {
    const vid = videoRef.current
    if (!vid || !active) return
    const seek = () => { vid.currentTime = active.start_time }
    if (vid.readyState >= 1) seek()
    else vid.addEventListener('loadedmetadata', seek, { once: true })
  }, [activeIdx, active])

  if (!state) return null

  const src = active ? `${API_BASE}/storage/videos/${active.video_id}` : undefined

  return (
    <main className="page results-page">
      <div className="results-body">
        <header className="results-header fade-up">
          <button id="results-back-btn" className="btn btn-ghost btn-sm results-back" onClick={() => navigate('/search')}>
            ← Back
          </button>
          <div className="results-query-wrap">
            <p className="eyebrow">Results for</p>
            <h1 className="results-query">"{query}"</h1>
            <p className="results-meta">
              {result.results.length} moment{result.results.length !== 1 ? 's' : ''} ·{' '}
              {result.gqeApplied ? 'GQE applied' : 'direct'} ·{' '}
              dominant: <span className="results-modality">{result.modality}</span>
            </p>
          </div>
        </header>

        {result.results.length === 0 ? (
          <div className="results-empty" role="status">
            <p className="results-empty-icon" aria-hidden="true">⊘</p>
            <h2>No matching moments</h2>
            <p>Try a different description, or turn off GQE for direct matching.</p>
            <button id="results-new-search-btn" className="btn btn-primary" onClick={() => navigate('/search')}>New search</button>
          </div>
        ) : (
          <div className="results-layout fade-up">
            <aside className="results-aside" aria-label="Results list">
              {result.results.map((r, i) => (
                <button
                  key={r.segment_id}
                  id={`result-item-${i}`}
                  className={`result-item${activeIdx === i ? ' result-item--on' : ''}`}
                  onClick={() => setActiveIdx(i)}
                  aria-pressed={activeIdx === i}
                >
                  <span className="ri-rank">#{i+1}</span>
                  <span className="ri-info">
                    <span className="ri-time">{fmt(r.start_time)} – {fmt(r.end_time)}</span>
                    <span className="ri-score">{Math.round(r.fused_score*100)}%</span>
                  </span>
                </button>
              ))}
            </aside>

            <div className="results-main">
              {src && (
                <section className="player-section" aria-label="Video player">
                  <video ref={videoRef} id="results-video-player" className="player-video"
                    src={src} controls
                    aria-label={`Video at ${fmt(active?.start_time ?? 0)}`} />
                  {active && (
                    <div className="player-bar">
                      <span className="player-moment">{fmt(active.start_time)} → {fmt(active.end_time)}</span>
                      <button id="results-seek-btn" className="btn btn-secondary btn-sm"
                        onClick={() => { if (videoRef.current) { videoRef.current.currentTime = active.start_time; videoRef.current.play() } }}>
                        ▶ Jump
                      </button>
                    </div>
                  )}
                </section>
              )}

              {active && (
                <section className="evidence" aria-label="Evidence">
                  <div className="ev-header">
                    <h2 className="ev-title">Evidence</h2>
                    <span className="ev-fused">{Math.round(active.fused_score*100)}<small>%</small></span>
                  </div>
                  <div className="ev-bars">
                    <Bar label="🎬 Visual (CLIP)"    weight={active.modality_weights.visual} score={active.visual_score} color="#a78bfa" />
                    <Bar label="🎙 Speech (Whisper)" weight={active.modality_weights.speech} score={active.speech_score} color="#22d3ee" />
                    <Bar label="📄 OCR (PaddleOCR)"  weight={active.modality_weights.ocr}    score={active.ocr_score}    color="#34d399" />
                  </div>
                  {result.gqeApplied && result.variants.length > 0 && (
                    <div className="ev-variants">
                      <p className="eyebrow" style={{marginBottom:8}}>GQE variants</p>
                      <ul>
                        {result.variants.slice(0,3).map((v,i) => <li key={i} className="ev-variant">"{v}"</li>)}
                      </ul>
                    </div>
                  )}
                </section>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  )
}
