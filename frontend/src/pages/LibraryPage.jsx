import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listVideos } from '../api/videos'
import client from '../api/client'
import VideoCard from '../components/VideoCard/VideoCard'
import LoadingSpinner from '../components/LoadingSpinner/LoadingSpinner'
import './LibraryPage.css'

export default function LibraryPage() {
  const [videos,     setVideos]     = useState([])
  const [loading,    setLoading]    = useState(true)
  const [error,      setError]      = useState('')
  const [reindexing, setReindexing] = useState({})  // id → bool
  const [confirming, setConfirming] = useState({})  // id → bool
  const [deleting,   setDeleting]   = useState({})  // id → bool
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
    try {
      await client.post(`/api/videos/${video._id}/reindex`)
      const poll = setInterval(async () => {
        try {
          const { data } = await client.get(`/api/videos/${video._id}/status`)
          if (data.status === 'indexed' || data.status === 'failed') {
            clearInterval(poll)
            setReindexing(r => ({ ...r, [video._id]: false }))
            fetchVideos()
          }
        } catch { clearInterval(poll) }
      }, 4000)
    } catch (err) {
      console.error('Reindex failed:', err)
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
    try {
      await client.delete(`/api/videos/${id}`)
      setVideos(vs => vs.filter(v => v._id !== id))
    } catch (err) {
      console.error('Delete failed:', err)
      alert('Delete failed: ' + (err.response?.data?.message || err.message))
    } finally {
      setDeleting(d => ({ ...d, [id]: false }))
    }
  }

  return (
    <main className="page library-page">
      <div className="page-body">
        <header className="library-header">
          <div>
            <p className="eyebrow">Your collection</p>
            <h1 className="library-title">Video Library</h1>
          </div>
          {!loading && videos.length > 0 && (
            <p className="library-count">{videos.length} video{videos.length !== 1 ? 's' : ''}</p>
          )}
        </header>

        {loading && <LoadingSpinner fullPage label="Loading videos…" />}

        {!loading && error && (
          <div className="lib-state" role="alert">
            <p className="lib-state-msg error">{error}</p>
            <button id="library-retry-btn" className="btn btn-secondary btn-sm" onClick={fetchVideos}>Retry</button>
          </div>
        )}

        {!loading && !error && videos.length === 0 && (
          <div className="lib-state">
            <div className="lib-empty-icon" aria-hidden="true">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="2" y="7" width="20" height="15" rx="2"/><path d="M16 3H8L2 7h20l-6-4z"/>
              </svg>
            </div>
            <h2 className="lib-state-heading">No videos yet</h2>
            <p className="lib-state-msg">Upload a video to get started.</p>
          </div>
        )}

        {!loading && !error && videos.length > 0 && (
          <section aria-label="Videos">
            <div className="library-grid">
              {videos.map((v) => (
                <div key={v._id} className="lib-card-wrap">
                  <VideoCard video={v} onClick={() => handleClick(v)} />

                  {/* Action row */}
                  <div className="lib-actions">
                    {v.status === 'indexed' && (
                      <button
                        id={`reindex-btn-${v._id}`}
                        className="btn btn-ghost btn-sm lib-action-btn"
                        onClick={(e) => handleReindex(e, v)}
                        disabled={reindexing[v._id]}
                        title="Re-index with improved AI settings"
                      >
                        {reindexing[v._id] ? '⏳ Re-indexing…' : '🔄 Re-index'}
                      </button>
                    )}

                    {confirming[v._id] ? (
                      <div className="lib-confirm-row" onClick={e => e.stopPropagation()}>
                        <span className="lib-confirm-label">Delete?</span>
                        <button
                          id={`delete-confirm-btn-${v._id}`}
                          className="btn btn-danger btn-sm lib-action-btn"
                          onClick={(e) => handleDeleteConfirm(e, v._id)}
                        >Yes</button>
                        <button
                          id={`delete-cancel-btn-${v._id}`}
                          className="btn btn-ghost btn-sm lib-action-btn"
                          onClick={(e) => handleDeleteCancel(e, v._id)}
                        >No</button>
                      </div>
                    ) : (
                      <button
                        id={`delete-btn-${v._id}`}
                        className="btn btn-ghost btn-sm lib-action-btn lib-delete-btn"
                        onClick={(e) => handleDeleteClick(e, v._id)}
                        disabled={deleting[v._id]}
                        title="Delete this video"
                      >
                        {deleting[v._id] ? '⏳' : '🗑 Delete'}
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        )}

      </div>
    </main>
  )
}
