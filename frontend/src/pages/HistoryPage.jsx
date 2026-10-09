import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { getHistory, deleteHistory } from '../api/history'
import LoadingSpinner from '../components/LoadingSpinner/LoadingSpinner'
import './HistoryPage.css'

const API_BASE = import.meta.env.VITE_API_URL ?? 'http://localhost:3000'

function fmt(sec) {
  const m = Math.floor(sec / 60), s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins  <  1) return 'just now'
  if (mins  < 60) return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

function ModalityDot({ modality }) {
  const colors = { visual: '#a78bfa', speech: '#22d3ee', ocr: '#34d399', all: '#f59e0b' }
  return (
    <span
      className="hist-modality-dot"
      style={{ background: colors[modality] ?? '#9090b0' }}
      title={modality}
    />
  )
}

export default function HistoryPage() {
  const navigate  = useNavigate()
  const [items,    setItems]    = useState([])
  const [loading,  setLoading]  = useState(true)
  const [error,    setError]    = useState('')
  const [page,     setPage]     = useState(1)
  const [pages,    setPages]    = useState(1)
  const [total,    setTotal]    = useState(0)
  const [deleting, setDeleting] = useState({})
  const [confirm,  setConfirm]  = useState(null) // queryId to confirm delete
  const [viewing,  setViewing]  = useState(null) // queryId being fetched
  const [viewError, setViewError] = useState(null) // { id, msg }

  const load = useCallback(async (p = 1) => {
    setLoading(true)
    setError('')
    try {
      const data = await getHistory(p, 20)
      setItems(data.queries)
      setTotal(data.total)
      setPages(data.pages)
      setPage(data.page)
    } catch {
      setError('Could not load search history. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(1) }, [load])

  const handleReplay = (item) => {
    // Re-run the query fresh on the search page
    navigate('/search', { state: { prefill: item.rawQuery } })
  }

  const handleView = async (item) => {
    setViewing(item._id)
    setViewError(null)
    try {
      // Fetch ALL saved results for this query (not just rank=1)
      const detail = await getHistoryDetail(item._id)
      const results = detail.results

      if (!results || results.length === 0) {
        // Results weren't saved (old search or save failed)
        setViewError({ id: item._id, msg: 'No saved results found. Use Re-run to search again.' })
        return
      }

      // Reconstruct the full result shape that ResultsPage expects
      const mapped = results.map((r) => ({
        segment_id:       r.segmentId ?? r._id,
        video_id:         r.videoId?._id ?? r.videoId,
        chunk_id:         0,
        start_time:       r.startTime,
        end_time:         r.endTime,
        fused_score:      r.fusedScore ?? 0,
        visual_score:     r.evidence?.visualSimilarity ?? 0,
        speech_score:     r.evidence?.speechSimilarity ?? 0,
        ocr_score:        r.evidence?.ocrSimilarity    ?? 0,
        modality_weights: {
          visual: r.evidence?.visualWeight ?? 0.33,
          speech: r.evidence?.speechWeight ?? 0.33,
          ocr:    r.evidence?.ocrWeight    ?? 0.34,
        },
        rank: r.rank ?? 1,
      }))

      navigate('/results', {
        state: {
          query: item.rawQuery,
          result: {
            results:    mapped,
            modality:   item.predictedModality ?? 'all',
            gqeApplied: (item.expandedVariants?.length ?? 0) > 0,
            variants:   item.expandedVariants ?? [],
          },
        },
      })
    } catch (err) {
      const msg = err?.response?.data?.message ?? err?.message ?? 'Failed to load results.'
      console.error('[History] View failed:', msg)
      setViewError({ id: item._id, msg })
    } finally {
      setViewing(null)
    }
  }

  const handleDelete = async (queryId) => {
    setDeleting(d => ({ ...d, [queryId]: true }))
    setConfirm(null)
    try {
      await deleteHistory(queryId)
      setItems(prev => prev.filter(i => i._id !== queryId))
      setTotal(t => t - 1)
    } catch {
      alert('Failed to delete. Please try again.')
    } finally {
      setDeleting(d => ({ ...d, [queryId]: false }))
    }
  }

  return (
    <main className="page history-page">
      <div className="page-body">
        <header className="hist-header">
          <div>
            <p className="eyebrow">Your activity</p>
            <h1 className="hist-title">Search History</h1>
          </div>
          {!loading && total > 0 && (
            <p className="hist-count">{total} search{total !== 1 ? 'es' : ''}</p>
          )}
        </header>

        {loading && <LoadingSpinner fullPage label="Loading history…" />}

        {!loading && error && (
          <div className="hist-state" role="alert">
            <p className="hist-state-msg error">{error}</p>
            <button id="history-retry-btn" className="btn btn-secondary btn-sm" onClick={() => load(page)}>
              Retry
            </button>
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="hist-state">
            <div className="hist-empty-icon" aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
              </svg>
            </div>
            <h2 className="hist-state-heading">No searches yet</h2>
            <p className="hist-state-msg">Run a search and it will appear here.</p>
            <button id="history-go-search-btn" className="btn btn-primary" onClick={() => navigate('/search')}>
              Search now
            </button>
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <>
            <ul className="hist-list" aria-label="Search history">
              {items.map((item) => {
                const r = item.topResult
                const videoTitle = r?.videoId?.title ?? null
                return (
                  <li key={item._id} className="hist-card fade-up">
                    {/* Left — query info */}
                    <div className="hist-card-main">
                      <div className="hist-card-top">
                        <ModalityDot modality={item.predictedModality} />
                        <span className="hist-query">"{item.rawQuery}"</span>
                        <span className="hist-time">{timeAgo(item.createdAt)}</span>
                      </div>

                      <div className="hist-card-meta">
                        <span className="hist-tag">{item.resultCount ?? 0} result{item.resultCount !== 1 ? 's' : ''}</span>
                        {(item.expandedVariants?.length ?? 0) > 0 && (
                          <span className="hist-tag hist-tag--gqe">GQE</span>
                        )}
                        {item.predictedModality && (
                          <span className="hist-tag">{item.predictedModality}</span>
                        )}
                        {videoTitle && (
                          <span className="hist-tag hist-tag--video">📹 {videoTitle}</span>
                        )}
                        {r && (
                          <span className="hist-tag hist-tag--ts">
                            {fmt(r.startTime)} → {fmt(r.endTime)}
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Right — actions */}
                    <div className="hist-card-col">
                      <div className="hist-card-actions">
                        <button
                          id={`hist-view-btn-${item._id}`}
                          className="btn btn-secondary btn-sm"
                          onClick={() => handleView(item)}
                          disabled={viewing === item._id}
                          title="View all saved results"
                        >
                          {viewing === item._id ? '⏳ Loading…' : 'View all'}
                        </button>

                        <button
                          id={`hist-replay-btn-${item._id}`}
                          className="btn btn-ghost btn-sm"
                          onClick={() => handleReplay(item)}
                          title="Re-run this search"
                        >
                          🔁 Re-run
                        </button>

                        {confirm === item._id ? (
                          <div className="hist-confirm">
                            <span>Delete?</span>
                            <button
                              id={`hist-del-confirm-${item._id}`}
                              className="btn btn-danger btn-sm"
                              onClick={() => handleDelete(item._id)}
                            >Yes</button>
                            <button
                              id={`hist-del-cancel-${item._id}`}
                              className="btn btn-ghost btn-sm"
                              onClick={() => setConfirm(null)}
                            >No</button>
                          </div>
                        ) : (
                          <button
                            id={`hist-del-btn-${item._id}`}
                            className="btn btn-ghost btn-sm hist-del-btn"
                            onClick={() => setConfirm(item._id)}
                            disabled={deleting[item._id]}
                            title="Remove from history"
                          >
                            {deleting[item._id] ? '⏳' : '🗑'}
                          </button>
                        )}
                      </div>

                      {/* Error message below action row */}
                      {viewError?.id === item._id && (
                        <p className="hist-view-error">{viewError.msg}</p>
                      )}
                    </div>
                  </li>
                )
              })}
            </ul>

            {/* Pagination */}
            {pages > 1 && (
              <div className="hist-pagination">
                <button
                  id="history-prev-btn"
                  className="btn btn-ghost btn-sm"
                  disabled={page <= 1}
                  onClick={() => load(page - 1)}
                >← Prev</button>
                <span className="hist-page-label">Page {page} of {pages}</span>
                <button
                  id="history-next-btn"
                  className="btn btn-ghost btn-sm"
                  disabled={page >= pages}
                  onClick={() => load(page + 1)}
                >Next →</button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  )
}
