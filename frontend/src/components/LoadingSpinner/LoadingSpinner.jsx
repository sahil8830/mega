import './LoadingSpinner.css'

export default function LoadingSpinner({ size = 'md', label, fullPage = false }) {
  return (
    <div className={`spinner-wrapper ${fullPage ? 'spinner-fullpage' : ''}`} role="status" aria-live="polite">
      <div className={`spinner spinner-${size}`} aria-hidden="true" />
      {label && <p className="spinner-label">{label}</p>}
      <span className="sr-only">{label ?? 'Loading...'}</span>
    </div>
  )
}
