import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import { useAuthStore } from '../store/authStore'
import './LandingPage.css'

const TECH = [
  { name: 'CLIP',       who: 'OpenAI',   what: 'Visual scene understanding' },
  { name: 'Whisper',    who: 'OpenAI',   what: 'Speech recognition & transcription' },
  { name: 'PaddleOCR', who: 'Baidu',    what: 'On-screen text extraction' },
  { name: 'FAISS',     who: 'Meta AI',  what: '3-index vector similarity search' },
  { name: 'BullMQ',    who: 'Node.js',  what: 'Background indexing queue' },
  { name: 'MongoDB',   who: 'Database', what: 'Video metadata & job tracking' },
]

const HOW = [
  { n: '01', title: 'Upload',  body: 'Admin drops a video. Backend accepts it and queues a job.' },
  { n: '02', title: 'Index',   body: 'CLIP, Whisper, and OCR each process 10-second chunks in parallel.' },
  { n: '03', title: 'Store',   body: 'Three FAISS indices hold 512D embeddings per modality.' },
  { n: '04', title: 'Search',  body: 'Your query expands via GQE, hits all three indices, scores fused.' },
  { n: '05', title: 'Play',    body: 'Video player auto-seeks to the exact matched timestamp.' },
]

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
}
const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  show:   { opacity: 1, y: 0, transition: { duration: 0.45, ease: [.4,0,.2,1] } },
}

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore()

  return (
    <main className="landing page">

      {/* ── Hero ── */}
      <section className="lhero" aria-label="Hero">
        <div className="lhero-inner">
          {/* Left — copy */}
          <motion.div
            variants={stagger} initial="hidden" animate="show"
          >
            <motion.div className="lhero-tag" variants={fadeUp}>
              <span className="lhero-dot" aria-hidden="true" />
              B.Tech Project · WCE Sangli 2026–27
            </motion.div>

            <motion.h1 className="lhero-title" variants={fadeUp}>
              Find the exact moment<br />
              in any video,{' '}
              <em className="lhero-em">just by describing it</em>
            </motion.h1>

            <motion.p className="lhero-body" variants={fadeUp}>
              MEGA indexes your video library across three dimensions —
              what's visible, what's spoken, and what's written on screen —
              then retrieves the precise timestamp from a single search.
            </motion.p>

            <motion.div className="lhero-actions" variants={fadeUp}>
              <Link
                to={isAuthenticated() ? '/search' : '/register'}
                id="hero-cta-link"
                className="btn btn-primary btn-lg"
              >
                {isAuthenticated() ? 'Open search →' : 'Try it free →'}
              </Link>
              <Link to="/login" id="hero-login-link" className="lhero-secondary btn-lg btn btn-ghost">
                Sign in
              </Link>
            </motion.div>

            <motion.div className="lhero-stack" aria-label="Tech stack" variants={fadeUp}>
              {['CLIP', 'Whisper', 'PaddleOCR', 'FAISS', 'BullMQ'].map((t) => (
                <span key={t} className="stack-pill">{t}</span>
              ))}
            </motion.div>
          </motion.div>

          {/* Right — geometric decoration */}
          <div className="lhero-visual" aria-hidden="true">
            <motion.div className="lhero-geo lhero-geo--a"
              initial={{ opacity:0, scale:0.8, rotate:-10 }}
              animate={{ opacity:1, scale:1, rotate:0 }}
              transition={{ duration:.6, delay:.2, ease:[.4,0,.2,1] }}
            />
            <motion.div className="lhero-geo lhero-geo--b"
              initial={{ opacity:0, y:30 }}
              animate={{ opacity:1, y:0 }}
              transition={{ duration:.6, delay:.35, ease:[.4,0,.2,1] }}
            />
            <motion.div className="lhero-geo lhero-geo--c"
              initial={{ opacity:0, x:40 }}
              animate={{ opacity:1, x:0 }}
              transition={{ duration:.5, delay:.45, ease:[.4,0,.2,1] }}
            />
            <motion.div className="lhero-geo lhero-geo--d"
              initial={{ opacity:0, scale:0 }}
              animate={{ opacity:1, scale:1 }}
              transition={{ duration:.4, delay:.55, type:'spring', stiffness:200 }}
            />
            <motion.div className="lhero-geo lhero-geo--e"
              initial={{ opacity:0, rotate:30 }}
              animate={{ opacity:1, rotate:0 }}
              transition={{ duration:.5, delay:.5 }}
            />
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
            {HOW.map(({ n, title, body }, i) => (
              <motion.li
                key={n} className="lhow-step"
                initial={{ opacity:0, y:20 }}
                whileInView={{ opacity:1, y:0 }}
                viewport={{ once:true }}
                transition={{ duration:.4, delay:i*.08 }}
              >
                <span className="lhow-n" aria-hidden="true">// {n}</span>
                <h3 className="lhow-step-title">{title}</h3>
                <p className="lhow-step-body">{body}</p>
              </motion.li>
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
            {TECH.map(({ name, who, what }, i) => (
              <motion.div
                key={name} className="tech-card"
                initial={{ opacity:0 }}
                whileInView={{ opacity:1 }}
                viewport={{ once:true }}
                transition={{ duration:.35, delay:i*.06 }}
              >
                <div className="tech-card-top">
                  <span className="tech-name">{name}</span>
                  <span className="tech-who">{who}</span>
                </div>
                <p className="tech-what">{what}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="lcta" aria-label="Call to action">
        <div className="container">
          <div className="lcta-inner">
            <p className="eyebrow">Get started</p>
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
