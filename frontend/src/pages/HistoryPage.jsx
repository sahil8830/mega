import { useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2, RefreshCw, Eye, Search, Clock, Loader } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { getHistory, getHistoryDetail, deleteHistory } from '../api/history'
import LoadingSpinner from '../components/LoadingSpinner/LoadingSpinner'
import './HistoryPage.css'

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
  const [confirm,  setConfirm]  = useState(null)
  const [viewing,  setViewing]  = useState(null)

  const load = useCallback(async (p = 1) => {
    setLoading(true); setError('')
    try {
      const data = await getHistory(p, 20)
      setItems(data.queries); setTotal(data.total)
      setPages(data.pages); setPage(data.page)
    } catch {
      setError('Could not load search history. Is the backend running?')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load(1) }, [load])

  const handleReplay = (item) => {
    navigate('/search', { state: { prefill: item.rawQuery, autoRun: true } })
  }

  const handleView = async (item) => {
    setViewing(item._id)
    const toastId = toast.loading('Loading saved results…')
    try {
      const detail = await getHistoryDetail(item._id)
      const results = detail.results
      if (!results || results.length === 0) {
        toast.error('No saved results. Use Re-run to search again.', { id: toastId })
        return
      }
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
      toast.success(`${mapped.length} saved results loaded`, { id: toastId })
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
      toast.error(err?.response?.data?.message ?? 'Failed to load results.', { id: toastId })
    } finally {
      setViewing(null)
    }
  }

  const handleDelete = async (queryId) => {
    setDeleting(d => ({ ...d, [queryId]: true }))
    setConfirm(null)
    const toastId = toast.loading('Deleting…')
    try {
      await deleteHistory(queryId)
      setItems(prev => prev.filter(i => i._id !== queryId))
      setTotal(t => t - 1)
      toast.success('Removed from history', { id: toastId })
    } catch {
      toast.error('Failed to delete.', { id: toastId })
    } finally {
      setDeleting(d => ({ ...d, [queryId]: false }))
    }
  }

  return (
    <main className="page history-page">
      <div className="page-body">
        <motion.header
          className="hist-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div>
            <p className="eyebrow">Your activity</p>
            <h1 className="hist-title">Search History</h1>
          </div>
          {!loading && total > 0 && (
            <p className="hist-count">{total} search{total !== 1 ? 'es' : ''}</p>
          )}
        </motion.header>

        {loading && <LoadingSpinner fullPage label="Loading history…" />}

        {!loading && error && (
          <div className="hist-state" role="alert">
            <p className="hist-state-msg error">{error}</p>
            <button id="history-retry-btn" className="btn btn-secondary btn-sm" onClick={() => load(page)}>Retry</button>
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <motion.div
            className="hist-state"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <div className="hist-empty-icon" aria-hidden="true">
              <Search size={40} strokeWidth={1.2} />
            </div>
            <h2 className="hist-state-heading">No searches yet</h2>
            <p className="hist-state-msg">Run a search and it will appear here.</p>
            <button id="history-go-search-btn" className="btn btn-primary" onClick={() => navigate('/search')}>
              Search now
            </button>
          </motion.div>
        )}

        {!loading && !error && items.length > 0 && (
          <>
            <ul className="hist-list" aria-label="Search history">
              <AnimatePresence>
                {items.map((item, idx) => {
                  const r = item.topResult
                  const videoTitle = r?.videoId?.title ?? null
                  return (
                    <motion.li
                      key={item._id}
                      className="hist-card"
                      initial={{ opacity: 0, y: 16 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, x: -24, scale: 0.97 }}
                      transition={{ duration: 0.3, delay: idx * 0.04 }}
                      layout
                    >
                      {/* Left */}
                      <div className="hist-card-main">
                        <div className="hist-card-top">
                          <ModalityDot modality={item.predictedModality} />
                          <span className="hist-query">"{item.rawQuery}"</span>
                          <span className="hist-time">
                            <Clock size={11} style={{ marginRight: 3 }} />
                            {timeAgo(item.createdAt)}
                          </span>
                        </div>
                        <div className="hist-card-meta">
                          {(item.expandedVariants?.length ?? 0) > 0 && (
                            <span className="hist-tag hist-tag--gqe">GQE</span>
                          )}
                          {videoTitle && (
                            <span className="hist-tag hist-tag--video">📹 {videoTitle}</span>
                          )}
                        </div>
                      </div>

                      {/* Right */}
                      <div className="hist-card-col">
                        <div className="hist-card-actions">
                          <motion.button
                            id={`hist-view-btn-${item._id}`}
                            className="btn btn-secondary btn-sm"
                            onClick={() => handleView(item)}
                            disabled={viewing === item._id}
                            title="View all saved results"
                            whileHover={{ scale: 1.04 }}
                            whileTap={{ scale: 0.96 }}
                          >
                            <Eye size={14} style={{ marginRight: 4 }} />
                            {viewing === item._id ? 'Loading…' : 'View all'}
                          </motion.button>

                          <motion.button
                            id={`hist-replay-btn-${item._id}`}
                            className="btn btn-ghost btn-sm"
                            onClick={() => handleReplay(item)}
                            title="Re-run this search"
                            whileHover={{ scale: 1.04 }}
                            whileTap={{ scale: 0.96 }}
                          >
                            <RefreshCw size={13} style={{ marginRight: 4 }} />
                            Re-run
                          </motion.button>

                          {confirm === item._id ? (
                            <div className="hist-confirm">
                              <span>Delete?</span>
                              <motion.button
                                id={`hist-del-confirm-${item._id}`}
                                className="btn btn-danger btn-sm"
                                onClick={() => handleDelete(item._id)}
                                whileTap={{ scale: 0.95 }}
                              >Yes</motion.button>
                              <motion.button
                                id={`hist-del-cancel-${item._id}`}
                                className="btn btn-ghost btn-sm"
                                onClick={() => setConfirm(null)}
                                whileTap={{ scale: 0.95 }}
                              >No</motion.button>
                            </div>
                          ) : (
                            <motion.button
                              id={`hist-del-btn-${item._id}`}
                              className="btn btn-ghost btn-sm hist-del-btn"
                              onClick={() => setConfirm(item._id)}
                              disabled={deleting[item._id]}
                              title="Remove from history"
                              whileHover={{ scale: 1.04, color: '#f87171' }}
                              whileTap={{ scale: 0.96 }}
                            >
                              {deleting[item._id] ? <div className="spinner spinner-sm" /> : <Trash2 size={14} />}
                            </motion.button>
                          )}
                        </div>
                      </div>
                    </motion.li>
                  )
                })}
              </AnimatePresence>
            </ul>

            {pages > 1 && (
              <div className="hist-pagination">
                <button id="history-prev-btn" className="btn btn-ghost btn-sm"
                  disabled={page <= 1} onClick={() => load(page - 1)}>← Prev</button>
                <span className="hist-page-label">Page {page} of {pages}</span>
                <button id="history-next-btn" className="btn btn-ghost btn-sm"
                  disabled={page >= pages} onClick={() => load(page + 1)}>Next →</button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  )
}
