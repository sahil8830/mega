import { Link } from 'react-router-dom'
import { useAuthStore } from '../store/authStore'
import './LandingPage.css'

const TECH = [
  { name: 'CLIP',       who: 'OpenAI',      what: 'Visual scene understanding' },
  { name: 'Whisper',    who: 'OpenAI',      what: 'Speech recognition & transcription' },
  { name: 'PaddleOCR', who: 'Baidu',        what: 'On-screen text extraction' },
  { name: 'FAISS',      who: 'Meta AI',     what: '3-index vector similarity search' },
  { name: 'BullMQ',     who: 'Node.js',     what: 'Background indexing queue' },
  { name: 'MongoDB',    who: 'Database',    what: 'Video metadata & job tracking' },
]

const HOW = [
  { n: '1', title: 'Upload', body: 'Admin drops a video. Backend accepts it and queues a job.' },
  { n: '2', title: 'Index',  body: 'CLIP, Whisper, and OCR each process 10-second chunks in parallel.' },
  { n: '3', title: 'Store',  body: 'Three separate FAISS indices hold 512D embeddings per modality.' },
  { n: '4', title: 'Search', body: 'Your query expands via GQE, hits all three indices, scores are fused.' },
  { n: '5', title: 'Play',   body: 'Video player auto-seeks to the exact matched timestamp.' },
]

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore()

  return (
    <main className="landing page">

      {/* ── Hero ── */}
      <section className="lhero" aria-label="Hero">
        <div className="lhero-noise" aria-hidden="true" />
        <div className="lhero-glow lhero-glow--a" aria-hidden="true" />
        <div className="lhero-glow lhero-glow--b" aria-hidden="true" />

        <div className="lhero-inner container">
          <div className="lhero-tag">
            <span className="lhero-dot" aria-hidden="true" />
            B.Tech Project · WCE Sangli 2026–27
          </div>

          <h1 className="lhero-title">
            Find the exact moment<br className="lhero-br" />
            in any video,{' '}
            <em className="lhero-em">just by describing it</em>
          </h1>

          <p className="lhero-body">
            MEGA indexes your video library across three dimensions —
            what's visible, what's spoken, and what's written on screen —
            then retrieves the precise timestamp from a single search.
          </p>

          <div className="lhero-actions">
            <Link
              to={isAuthenticated() ? '/search' : '/register'}
              id="hero-cta-link"
              className="btn btn-primary btn-lg"
            >
              {isAuthenticated() ? 'Open search →' : 'Try it free →'}
            </Link>
            <Link to="/login" id="hero-login-link" className="btn btn-ghost btn-lg lhero-secondary">
              Sign in
            </Link>
          </div>

          <div className="lhero-stack" aria-label="Tech stack">
            {['CLIP', 'Whisper', 'PaddleOCR', 'FAISS', 'BullMQ'].map((t) => (
              <span key={t} className="stack-pill">{t}</span>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section className="lhow" aria-labelledby="how-heading">
        <div className="container">
          <div className="lhow-head">
            <p className="eyebrow">Under the hood</p>
            <h2 id="how-heading" className="lhow-title">Five steps from upload to result</h2>
          </div>
          <ol className="lhow-steps">
            {HOW.map(({ n, title, body }) => (
              <li key={n} className="lhow-step">
                <span className="lhow-n" aria-hidden="true">{n}</span>
                <div className="lhow-content">
                  <h3 className="lhow-step-title">{title}</h3>
                  <p className="lhow-step-body">{body}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </section>

      {/* ── Tech table ── */}
      <section className="ltech" aria-labelledby="tech-heading">
        <div className="container">
          <div className="ltech-head">
            <p className="eyebrow">Technologies</p>
            <h2 id="tech-heading" className="ltech-title">Built on best-in-class AI</h2>
          </div>
          <div className="ltech-grid">
            {TECH.map(({ name, who, what }) => (
              <div key={name} className="tech-card">
                <div className="tech-card-top">
                  <span className="tech-name">{name}</span>
                  <span className="tech-who">{who}</span>
                </div>
                <p className="tech-what">{what}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="lcta" aria-label="Call to action">
        <div className="container">
          <div className="lcta-inner">
            <h2 className="lcta-title">Ready to search smarter?</h2>
            <p className="lcta-body">
              Upload a video, wait for indexing, then describe any moment in plain English.
            </p>
            <Link
              to={isAuthenticated() ? '/search' : '/register'}
              id="cta-main-link"
              className="btn btn-primary btn-lg"
            >
              {isAuthenticated() ? 'Search now →' : 'Get started →'}
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="lfooter" role="contentinfo">
        <div className="container lfooter-inner">
          <div>
            <p className="lfooter-team">Sahil Patil · Tenzin Dargyal · Pranav Chougule · Vrushabh Tonge</p>
            <p className="lfooter-school">Walchand College of Engineering, Sangli · Guide: Prof. A.S. Pawar</p>
          </div>
          <p className="lfooter-year">2026–27</p>
        </div>
      </footer>

    </main>
  )
}
