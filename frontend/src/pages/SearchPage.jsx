import { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
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
  const navigate  = useNavigate()
  const location  = useLocation()
  const inputRef  = useRef(null)
  const [query,   setQuery]   = useState(location.state?.prefill ?? '')
  const [loading, setLoading] = useState(false)
  const [error,   setError]   = useState('')
  const [gqe,     setGqe]     = useState(true)

  useEffect(() => { inputRef.current?.focus() }, [])

  const doSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return
    setError(''); setLoading(true)
    try {
      const result = await search(query.trim(), 10, gqe)
      navigate('/results', { state: { result, query: query.trim() } })
    } catch (err) {
      setError(err.response?.data?.message ?? 'Search failed. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }

  void location

  return (
    <main className="page search-page">
      <div className="search-bg" aria-hidden="true">
        <div className="search-blob sb-1" />
        <div className="search-blob sb-2" />
      </div>

      <div className="search-center fade-up">
        <p className="eyebrow">Semantic search</p>
        <h1 className="search-heading">
          What are you<br />looking for?
        </h1>
        <p className="search-desc">
          Describe a moment — by what's on screen, what's being said, or what's written.
        </p>

        <form id="search-form" onSubmit={doSearch} className="search-form">
          <div className={`search-box${loading ? ' search-box--loading' : ''}`}>
            <span className="search-icon" aria-hidden="true">
              {loading
                ? <div className="spinner spinner-sm" />
                : <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              }
            </span>
            <input
              ref={inputRef} id="search-query-input" type="search"
              className="search-input" value={query}
              placeholder="e.g. person pointing at a graph…"
              onChange={(e) => setQuery(e.target.value)}
              disabled={loading}
              aria-label="Search query"
            />
            <button id="search-submit-btn" type="submit" className="btn btn-primary search-btn"
              disabled={loading || !query.trim()}>
              {loading ? 'Searching…' : 'Search'}
            </button>
          </div>

          <div className="search-meta">
            <label className="gqe-toggle" htmlFor="gqe-cb">
              <input id="gqe-cb" type="checkbox" checked={gqe}
                onChange={(e) => setGqe(e.target.checked)} />
              <span className="gqe-track" aria-hidden="true" />
              <span className="gqe-label">Query expansion (GQE)</span>
            </label>
            <span className="gqe-hint">generates semantic variants for better recall</span>
          </div>
        </form>

        {error && <p className="search-error form-error" role="alert">{error}</p>}

        <div className="chips">
          <span className="chips-label">Try:</span>
          {CHIPS.map((c) => (
            <button key={c} type="button" className="chip" onClick={() => setQuery(c)}
              aria-label={`Use: ${c}`}>
              {c}
            </button>
          ))}
        </div>
      </div>
    </main>
  )
}
