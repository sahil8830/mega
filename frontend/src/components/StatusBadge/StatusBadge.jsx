const STATUS_CONFIG = {
  queued:   { label: 'Queued',   className: 'badge badge-queued',   dot: '●' },
  indexing: { label: 'Indexing', className: 'badge badge-indexing', dot: '◌' },
  indexed:  { label: 'Ready',    className: 'badge badge-indexed',  dot: '●' },
  error:    { label: 'Error',    className: 'badge badge-error',     dot: '●' },
}

export default function StatusBadge({ status }) {
  const config = STATUS_CONFIG[status] ?? STATUS_CONFIG.error
  return (
    <span className={config.className} aria-label={`Status: ${config.label}`}>
      <span aria-hidden="true" className="badge-dot">{config.dot}</span>
      {config.label}
    </span>
  )
}
