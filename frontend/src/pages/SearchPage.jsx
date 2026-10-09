import { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Search, Sparkles, ChevronRight } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { search } from '../api/search'
import './SearchPage.css'

const CHIPS = [
  'Person writing on a whiteboard',
  'Crowd cheering at an event',
  'Someone explaining a diagram',
  'Text showing code on screen',
  'People shaking hands',
]

export default function SearchPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const inputRef = useRef(null)
  const [query,   setQuery]   = useState(location.state?.prefill ?? '')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [gqe,     setGqe]     = useState(true)

  const doSearch = async (q = query, useGqe = gqe) => {
    const trimmed = (typeof q === 'string' ? q : query).trim()
    if (!trimmed) return
    setError(''); setLoading(true)
    const toastId = toast.loading('Searching across all modalities…')
    try {
      const result = await search(trimmed, 10, useGqe)
      toast.success(`Found ${result.results?.length ?? 0} moments`, { id: toastId })
      navigate('/results', { state: { result, query: trimmed } })
    } catch (err) {
      const msg = err.response?.data?.message ?? 'Search failed. Is the backend running?'
      toast.error(msg, { id: toastId })
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  // Focus or auto-run when navigated from history
  useEffect(() => {
    if (location.state?.autoRun && location.state?.prefill) {
      doSearch(location.state.prefill)
    } else {
      inputRef.current?.focus()
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <main className="page search-page">
      {/* Clean white background — no blobs */}

      <motion.div
        className="search-center"
        initial={{ opacity: 0, y: 32 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        <p className="eyebrow">Semantic search</p>
        <h1 className="search-heading">
          What are you<br />looking for?
        </h1>
        <p className="search-desc">
          Describe a moment — by what's on screen, what's being said, or what's written.
        </p>

        <form id="search-form" onSubmit={(e) => { e.preventDefault(); doSearch() }} className="search-form">
          <motion.div
            className={`search-box${loading ? ' search-box--loading' : ''}`}
            whileFocusWithin={{ boxShadow: '0 0 0 2px rgba(108,99,255,0.5), 0 8px 32px rgba(108,99,255,0.2)' }}
            transition={{ duration: 0.2 }}
          >
            <span className="search-icon" aria-hidden="true">
              {loading
                ? <div className="spinner spinner-sm" />
                : <Search size={18} />
              }
            </span>
            <input
              ref={inputRef}
              id="search-query-input"
              type="search"
              className="search-input"
              value={query}
              placeholder="e.g. person pointing at a graph…"
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
              aria-label="Search query"
            />
            <motion.button
              id="search-submit-btn"
              type="submit"
              className="btn btn-primary search-btn"
              disabled={loading || !query.trim()}
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
            >
              {loading ? 'Searching…' : 'Search'}
            </motion.button>
          </motion.div>

          <div className="search-meta">
            <label className="gqe-toggle" htmlFor="gqe-cb">
              <input id="gqe-cb" type="checkbox" checked={gqe}
                onChange={(e) => setGqe(e.target.checked)} />
              <span className="gqe-track" aria-hidden="true" />
              <span className="gqe-label">
                <Sparkles size={12} style={{ marginRight: 4 }} />
                Query expansion (GQE)
              </span>
            </label>
            <span className="gqe-hint">generates semantic variants for better recall</span>
          </div>
        </form>

        <AnimatePresence>
          {error && (
            <motion.p
              className="search-error form-error"
              role="alert"
              initial={{ opacity: 0, y: -8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              {error}
            </motion.p>
          )}
        </AnimatePresence>

        <div className="chips">
          <span className="chips-label">Try:</span>
          {CHIPS.map((c) => (
            <motion.button
              key={c}
              type="button"
              className="chip"
              onClick={() => setQuery(c)}
              aria-label={`Use: ${c}`}
              whileHover={{ scale: 1.04, y: -2 }}
              whileTap={{ scale: 0.96 }}
            >
              {c} <ChevronRight size={12} />
            </motion.button>
          ))}
        </div>
      </motion.div>
    </main>
  )
}
