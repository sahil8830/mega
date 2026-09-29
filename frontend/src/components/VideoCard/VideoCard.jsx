import StatusBadge from '../StatusBadge/StatusBadge'
import './VideoCard.css'

function formatSize(bytes) {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatDate(iso) {
  return new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
}

export default function VideoCard({ video, onClick }) {
  return (
    <article
      className="video-card card"
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label={`${video.title} — ${video.status}`}
      onKeyDown={(e) => e.key === 'Enter' && onClick?.()}
    >
      <div className="video-card-thumb">
        <div className="video-card-play" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
            <polygon points="5 3 19 12 5 21 5 3" />
          </svg>
        </div>
        {video.status === 'indexing' && (
          <div className="video-card-overlay" aria-hidden="true">
            <div className="spinner spinner-sm" />
            <span>Indexing…</span>
          </div>
        )}
      </div>
      <div className="video-card-body">
        <div className="video-card-top">
          <h3 className="video-card-title" title={video.title}>{video.title}</h3>
          <StatusBadge status={video.status} />
        </div>
        <p className="video-card-meta">{formatSize(video.sizeBytes)} · {formatDate(video.createdAt)}</p>
        {video.errorMessage && <p className="video-card-error" role="alert">{video.errorMessage}</p>}
      </div>
    </article>
  )
}
