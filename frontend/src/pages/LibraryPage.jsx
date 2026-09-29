import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { listVideos } from '../api/videos'
import VideoCard from '../components/VideoCard/VideoCard'
import LoadingSpinner from '../components/LoadingSpinner/LoadingSpinner'
import './LibraryPage.css'

export default function LibraryPage() {
  const [videos,  setVideos]  = useState([])
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState('')
  const navigate = useNavigate()

  useEffect(() => {
    let alive = true
    listVideos()
      .then((d) => { if (alive) setVideos(d) })
      .catch(() => { if (alive) setError('Could not reach the backend. Is it running?') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const handleClick = (video) => {
    if (video.status === 'indexed') navigate('/search', { state: { videoId: video._id } })
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
            <button id="library-retry-btn" className="btn btn-secondary btn-sm" onClick={() => window.location.reload()}>Retry</button>
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
            <p className="lib-state-msg">Ask an admin to upload and index some videos.</p>
          </div>
        )}

        {!loading && !error && videos.length > 0 && (
          <section aria-label="Videos">
            <div className="library-grid">
              {videos.map((v) => <VideoCard key={v._id} video={v} onClick={() => handleClick(v)} />)}
            </div>
          </section>
        )}
      </div>
    </main>
  )
}
