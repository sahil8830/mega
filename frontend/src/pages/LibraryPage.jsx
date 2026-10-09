import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion, AnimatePresence } from 'framer-motion'
import { Trash2, RefreshCw, Search, Film } from 'lucide-react'
import { toast } from 'react-hot-toast'
import { listVideos } from '../api/videos'
import client from '../api/client'
import VideoCard from '../components/VideoCard/VideoCard'
import LoadingSpinner from '../components/LoadingSpinner/LoadingSpinner'
import './LibraryPage.css'

export default function LibraryPage() {
  const [videos,     setVideos]     = useState([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [reindexing, setReindexing] = useState({})
  const [confirming, setConfirming] = useState({})
  const [deleting,   setDeleting]   = useState({})
  const navigate = useNavigate()

  const fetchVideos = () => {
    setLoading(true)
    listVideos()
      .then(setVideos)
      .catch(() => setError('Could not reach the backend. Is it running?'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchVideos() }, [])

  const handleClick = (video) => {
    if (video.status === 'indexed') navigate('/search', { state: { videoId: video._id } })
  }

  const handleReindex = async (e, video) => {
    e.stopPropagation()
    setReindexing(r => ({ ...r, [video._id]: true }))
    const toastId = toast.loading('Re-indexing…')
    try {
      await client.post(`/api/videos/${video._id}/reindex`)
      const poll = setInterval(async () => {
        try {
          const { data } = await client.get(`/api/videos/${video._id}/status`)
          if (data.status === 'indexed') {
            clearInterval(poll)
            setReindexing(r => ({ ...r, [video._id]: false }))
            toast.success('Re-indexed successfully!', { id: toastId })
            fetchVideos()
          } else if (data.status === 'failed') {
            clearInterval(poll)
            setReindexing(r => ({ ...r, [video._id]: false }))
            toast.error('Re-indexing failed.', { id: toastId })
          }
        } catch { clearInterval(poll) }
      }, 4000)
    } catch (err) {
      toast.error('Re-index failed.', { id: toastId })
      setReindexing(r => ({ ...r, [video._id]: false }))
    }
  }

  const handleDeleteClick = (e, id) => {
    e.stopPropagation()
    setConfirming(c => ({ ...c, [id]: true }))
  }

  const handleDeleteCancel = (e, id) => {
    e.stopPropagation()
    setConfirming(c => ({ ...c, [id]: false }))
  }

  const handleDeleteConfirm = async (e, id) => {
    e.stopPropagation()
    setDeleting(d => ({ ...d, [id]: true }))
    setConfirming(c => ({ ...c, [id]: false }))
    const toastId = toast.loading('Deleting video…')
    try {
      await client.delete(`/api/videos/${id}`)
      setVideos(vs => vs.filter(v => v._id !== id))
      toast.success('Video deleted', { id: toastId })
    } catch (err) {
      toast.error('Delete failed: ' + (err.response?.data?.message || err.message), { id: toastId })
    } finally {
      setDeleting(d => ({ ...d, [id]: false }))
    }
  }

  return (
    <main className="page library-page">
      <div className="page-body">
        <motion.header
          className="library-header"
          initial={{ opacity: 0, y: -16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
        >
          <div>
            <p className="eyebrow">Your collection</p>
            <h1 className="library-title">Video Library</h1>
          </div>
          {!loading && videos.length > 0 && (
            <p className="library-count">{videos.length} video{videos.length !== 1 ? 's' : ''}</p>
          )}
        </motion.header>

        {loading && <LoadingSpinner fullPage label="Loading videos…" />}

        {!loading && error && (
          <div className="lib-state" role="alert">
            <p className="lib-state-msg error">{error}</p>
            <button id="library-retry-btn" className="btn btn-secondary btn-sm" onClick={fetchVideos}>Retry</button>
          </div>
        )}

        {!loading && !error && videos.length === 0 && (
          <motion.div
            className="lib-state"
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <div className="lib-empty-icon" aria-hidden="true">
              <Film size={40} strokeWidth={1.2} />
            </div>
            <h2 className="lib-state-heading">No videos yet</h2>
            <p className="lib-state-msg">Upload a video to get started.</p>
          </motion.div>
        )}

        {!loading && !error && videos.length > 0 && (
          <section aria-label="Videos">
            <div className="library-grid">
              <AnimatePresence>
                {videos.map((v, idx) => (
                  <motion.div
                    key={v._id}
                    className="lib-card-wrap"
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.9 }}
                    transition={{ duration: 0.3, delay: idx * 0.05 }}
                    layout
                  >
                    <VideoCard video={v} onClick={() => handleClick(v)} />

                    <div className="lib-actions">
                      {v.status === 'indexed' && (
                        <motion.button
                          id={`reindex-btn-${v._id}`}
                          className="btn btn-ghost btn-sm lib-action-btn"
                          onClick={(e) => handleReindex(e, v)}
                          disabled={reindexing[v._id]}
                          title="Re-index with improved AI settings"
                          whileHover={{ scale: 1.05 }}
                          whileTap={{ scale: 0.95 }}
                        >
                          <RefreshCw size={13} style={{ marginRight: 4 }} />
                          {reindexing[v._id] ? 'Re-indexing…' : 'Re-index'}
                        </motion.button>
                      )}

                      {confirming[v._id] ? (
                        <div className="lib-confirm-row" onClick={e => e.stopPropagation()}>
                          <span className="lib-confirm-label">Delete?</span>
                          <motion.button
                            id={`delete-confirm-btn-${v._id}`}
                            className="btn btn-danger btn-sm lib-action-btn"
                            onClick={(e) => handleDeleteConfirm(e, v._id)}
                            whileTap={{ scale: 0.95 }}
                          >Yes</motion.button>
                          <motion.button
                            id={`delete-cancel-btn-${v._id}`}
                            className="btn btn-ghost btn-sm lib-action-btn"
                            onClick={(e) => handleDeleteCancel(e, v._id)}
                            whileTap={{ scale: 0.95 }}
                          >No</motion.button>
                        </div>
                      ) : (
                        <motion.button
                          id={`delete-btn-${v._id}`}
                          className="btn btn-ghost btn-sm lib-action-btn lib-delete-btn"
                          onClick={(e) => handleDeleteClick(e, v._id)}
                          disabled={deleting[v._id]}
                          title="Delete this video"
                          whileHover={{ scale: 1.05, color: '#f87171' }}
                          whileTap={{ scale: 0.95 }}
                        >
                          <Trash2 size={13} style={{ marginRight: 4 }} />
                          {deleting[v._id] ? 'Deleting…' : 'Delete'}
                        </motion.button>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          </section>
        )}
      </div>
    </main>
  )
}
